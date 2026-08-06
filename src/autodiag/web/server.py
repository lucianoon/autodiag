import asyncio
import csv
import io
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path.home() / ".autodiag" / ".env")
load_dotenv(".env")

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from autodiag.core.config import Branding, get_branding, update_branding
from autodiag.core.diagnosis import infer_urgency
from autodiag.core.dtc import full_database, lookup
from autodiag.core.readiness import build_readiness_summary
from autodiag.core.report import build_report, render_report_html
from autodiag.core.trend import build_vehicle_trends
from autodiag.core.triage import build_guided_triage
from autodiag.core.vehicle import VehicleProfile, decode_vin_local
from autodiag.db.history import History, Session
from autodiag.elm327 import OBDReader, create_reader
from autodiag.elm327.reader import DTCRecord, list_ports

app = FastAPI(title="AutoDiag")

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC), name="static")

_DEFAULT_BODY_FACTORY = Body(default_factory=dict)


def _dtc_payload(dtcs: list[DTCRecord]) -> list[dict]:
    payload = []
    for dtc in dtcs:
        info = lookup(dtc.code)
        payload.append(
            {
                "code": dtc.code,
                "status": dtc.status,
                "description": info.description if info else "—",
                "severity": info.severity if info else "informativo",
                "system": info.system if info else "—",
            }
        )
    return payload


@app.get("/", response_class=HTMLResponse)
async def index():
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/summary")
async def api_summary():
    with History() as history:
        return history.summary()


@app.get("/api/history")
async def api_history(limit: int = Query(10, ge=1, le=100)):
    with History() as history:
        return history.list(limit)


@app.get("/api/session/{sid}")
async def api_session(sid: int):
    with History() as history:
        row = history.get(sid)
    if not row:
        return JSONResponse({"error": f"Sessão {sid} não encontrada"}, status_code=404)
    return row


@app.patch("/api/session/{sid}")
async def api_patch_session(
    sid: int,
    body: dict[str, Any] = _DEFAULT_BODY_FACTORY,
):
    allowed = {"notes": str, "tags": list}
    patch: dict[str, Any] = {}
    for k, _t in allowed.items():
        if k in body:
            v = body.get(k)
            if k == "tags" and not isinstance(v, list):
                raise HTTPException(status_code=400, detail="tags deve ser lista")
            if k == "notes" and not isinstance(v, str):
                raise HTTPException(status_code=400, detail="notes deve ser string")
            patch[k] = v
    with History() as history:
        if not patch:
            row = history.get(sid)
            if row is None:
                raise HTTPException(status_code=404, detail="Sessão não encontrada")
            return row
        updated = history.update_session(sid, **patch)
    if updated is None:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return updated


@app.get("/api/branding")
async def api_get_branding():
    from dataclasses import asdict

    return asdict(get_branding())


@app.put("/api/branding")
async def api_put_branding(body: dict[str, Any] = _DEFAULT_BODY_FACTORY):
    from dataclasses import asdict

    updated = update_branding({k: str(body.get(k, "")) for k in Branding.__dataclass_fields__})
    return asdict(updated)


@app.get("/api/vehicles")
async def api_vehicles():
    with History() as history:
        return history.list_vehicles()


@app.get("/api/vehicle/{vin}/history")
async def api_vehicle_history(vin: str, limit: int = Query(10, ge=1, le=100)):
    with History() as history:
        return history.list_by_vin(vin, limit=limit)


@app.get("/api/vehicle/{vin}/trends")
async def api_vehicle_trends(vin: str, limit: int = Query(50, ge=2, le=500)):
    with History() as history:
        sessions = history.list_by_vin(vin, limit=limit)
    return build_vehicle_trends(sessions)


@app.get("/api/vehicle/{vin}/export.json")
async def api_vehicle_export_json(vin: str, limit: int = Query(500, ge=1, le=5000)):
    with History() as history:
        sessions = history.list_by_vin(vin, limit=limit)
    trends = build_vehicle_trends(sessions)
    payload = {"vin": vin, "sessions": sessions, "trends": trends}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="autodiag-{vin}.json"'},
    )


@app.get("/api/vehicle/{vin}/export.csv")
async def api_vehicle_export_csv(vin: str, limit: int = Query(500, ge=1, le=5000)):
    with History() as history:
        sessions = history.list_by_vin(vin, limit=limit)
    cols = [
        "id", "ts", "vin", "vehicle_label", "urgency",
        "coolant_temp", "rpm", "maf", "fuel_trim_short", "fuel_trim_long",
        "o2", "speed", "km",
        "dtc_codes", "tags", "cost_min", "cost_max", "notes",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for s in sessions:
        row = {k: s.get(k) for k in cols}
        row["dtc_codes"] = ",".join(s.get("dtc_codes") or [])
        row["tags"] = ",".join(s.get("tags") or [])
        writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    body = buf.getvalue().encode("utf-8-sig")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="autodiag-{vin}.csv"'},
    )


@app.get("/report/{sid}", response_class=HTMLResponse)
async def report(sid: int):
    with History() as history:
        row = history.get(sid)
        if not row:
            return HTMLResponse(f"Sessão {sid} não encontrada", status_code=404)
        prev = history.previous_for_vin(row.get("vin") or "", before_id=sid)
        vhist = history.list_by_vin(row.get("vin") or "", limit=8)
    rep = build_report(row, prev, vehicle_history=vhist)
    return render_report_html(rep)


@app.get("/report/{sid}/download", response_class=HTMLResponse)
async def report_download(sid: int):
    with History() as history:
        row = history.get(sid)
        if not row:
            return HTMLResponse(f"Sessão {sid} não encontrada", status_code=404)
        prev = history.previous_for_vin(row.get("vin") or "", before_id=sid)
        vhist = history.list_by_vin(row.get("vin") or "", limit=8)
    rep = build_report(row, prev, vehicle_history=vhist)
    html = render_report_html(rep)
    return HTMLResponse(
        html,
        headers={
            "Content-Disposition": f'attachment; filename="autodiag-report-{sid}.html"'
        },
    )


@app.get("/api/ports")
async def api_ports():
    return {"ports": list_ports()}


@app.get("/api/dtc/{code}")
async def api_dtc(code: str):
    info = lookup(code.upper())
    if not info:
        return JSONResponse({"error": f"DTC {code.upper()} não encontrado"}, status_code=404)
    return {
        "code": info.code,
        "description": info.description,
        "severity": info.severity,
        "system": info.system,
        "causes": info.causes,
    }


@app.get("/api/dtc")
async def api_dtc_search(q: str = Query("")):
    q_up = q.upper().strip()
    q_lo = q.lower().strip()
    results = []
    for code, info in sorted(full_database().items()):
        if q_up in code or q_lo in info.description.lower():
            results.append(
                {
                    "code": info.code,
                    "description": info.description,
                    "severity": info.severity,
                    "system": info.system,
                }
            )
    return results[:20]


@app.get("/api/scan/stream")
async def api_scan_stream(
    port: str = Query(None),
    wifi: str = Query(None),
    no_ai: bool = Query(False),
    demo: bool = Query(False),
):
    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()

    def send(data: dict):
        loop.call_soon_threadsafe(q.put_nowait, data)

    def run():
        reader = create_reader(port=port, wifi_host=wifi, demo=demo)
        try:
            if demo:
                send({"type": "status", "message": "Modo demo — adaptador ELM327 simulado"})
            else:
                send({"type": "status", "message": "Conectando ao adaptador ELM327..."})

            connected = reader.connect()
            if not connected:
                send(
                    {
                        "type": "error",
                        "message": "Falha ao inicializar ELM327. Verifique a conexão.",
                    }
                )
                return
            send({"type": "status", "message": "Adaptador conectado"})

            send({"type": "status", "message": "Coletando status do veículo..."})
            battery_voltage = reader.get_control_module_voltage()
            monitor_status = reader.get_monitor_status()
            supported_pids = reader.get_supported_pids()
            send(
                {
                    "type": "vehicle_status",
                    "battery_voltage": battery_voltage,
                    "monitor_status": monitor_status.as_dict(),
                    "supported_pids": supported_pids,
                }
            )

            send({"type": "status", "message": "Lendo VIN..."})
            vin = reader.get_vin()
            vehicle = decode_vin_local(vin) if vin else VehicleProfile()
            if vin and len(vin) == 17 and not demo:
                try:
                    import httpx as _httpx

                    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
                    result = _httpx.get(url, timeout=6.0).json().get("Results", [{}])[0]
                    vehicle.make = result.get("Make") or vehicle.make
                    vehicle.model = result.get("Model") or ""
                    year = result.get("ModelYear") or ""
                    if year.isdigit():
                        vehicle.year = int(year)
                except Exception:
                    pass
            send({"type": "vin", "vin": vin or "—", "vehicle": vehicle.label})

            send({"type": "status", "message": "Lendo DTCs..."})
            dtcs = reader.get_dtcs()
            pending_dtcs = reader.get_pending_dtcs()
            permanent_dtcs = reader.get_permanent_dtcs()
            all_dtcs = dtcs + pending_dtcs + permanent_dtcs
            send({"type": "dtcs", "dtcs": _dtc_payload(all_dtcs)})

            send({"type": "status", "message": "Verificando prontidão dos monitores..."})
            readiness: dict | None = None
            try:
                readiness = build_readiness_summary(
                    monitor_status,
                    warmups_since_clear=reader.get_warmups_since_clear(),
                    distance_since_clear_km=reader.get_distance_since_clear(),
                )
                send({"type": "readiness", "readiness": readiness})
            except Exception as _e:
                readiness = None

            send({"type": "status", "message": "Freeze Frame (momento do DTC)..."})
            freeze_frame: dict | None = None
            try:
                ff_raw = reader.get_freeze_frame()
                freeze_frame = ff_raw.as_dict()
                if any(freeze_frame.get(k) not in (None, "") for k in freeze_frame if k != "raw"):
                    send({"type": "freeze_frame", "freeze_frame": freeze_frame})
            except Exception as _e:
                freeze_frame = None

            send({"type": "status", "message": "Lendo PIDs ao vivo..."})
            pids = reader.get_live_pids()
            send({"type": "pids", "pids": pids.as_dict()})

            urgency = infer_urgency(all_dtcs, pids)
            triage = build_guided_triage(all_dtcs, pids, urgency)
            send({"type": "triage", "triage": triage, "urgency": urgency})

            analysis = ""
            if not no_ai:
                from autodiag.agents.diagnostic import analyze, describe, is_configured

                if is_configured():
                    send({"type": "status", "message": f"Analisando com {describe()}..."})
                    try:
                        analysis = analyze(vehicle, all_dtcs, pids)
                        send({"type": "analysis", "text": analysis})
                    except Exception as e:
                        send({"type": "warn", "message": f"Erro na análise IA: {e}"})

            with History() as history:
                sid = history.save(
                    Session(
                        id=None,
                        ts=datetime.now().strftime("%d/%m/%Y %H:%M"),
                        vin=vehicle.vin,
                        vehicle_label=vehicle.label,
                        dtc_codes=[d.code for d in all_dtcs],
                        urgency=urgency,
                        rpm=pids.rpm,
                        speed=pids.speed_kmh,
                        coolant_temp=pids.coolant_temp_c,
                        maf=pids.maf_g_s,
                        fuel_trim_short=pids.fuel_trim_short_b1,
                        fuel_trim_long=pids.fuel_trim_long_b1,
                        o2=pids.o2_b1s1_v,
                        diagnosis=analysis,
                        triage=triage,
                        cost_min=0,
                        cost_max=0,
                        km=None,
                        notes="",
                        freeze_frame=freeze_frame,
                        readiness=readiness,
                    )
                )
            send({"type": "saved", "session_id": sid, "urgency": urgency})
        except ConnectionError as e:
            send({"type": "error", "message": str(e)})
        except Exception as e:
            send({"type": "error", "message": f"Erro inesperado: {e}"})
        finally:
            reader.disconnect()
            loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=run, daemon=True).start()

    async def generate():
        while True:
            event = await q.get()
            if event is None:
                yield 'data: {"type":"done"}\n\n'
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/scan/live")
async def scan_live(
    port: str | None = None,
    wifi_host: str | None = None,
    demo: bool = False,
    duration: int = 60,
):
    """Captura contínua de live PIDs por `duration` segundos (~1Hz)."""
    duration = max(1, min(duration, 600))
    reader: OBDReader = create_reader(port=port, wifi_host=wifi_host, demo=demo)
    loop = asyncio.get_event_loop()
    stop_flag = threading.Event()
    q: asyncio.Queue[dict | None] = asyncio.Queue()

    def run() -> None:
        try:
            connected = reader.connect()
            if not connected:
                loop.call_soon_threadsafe(
                    q.put_nowait,
                    {"type": "error", "message": "Falha ao conectar ELM327."},
                )
                return
            for i in range(duration):
                if stop_flag.is_set():
                    break
                try:
                    pids = reader.get_live_pids().as_dict()
                except Exception:
                    pids = {}
                loop.call_soon_threadsafe(
                    q.put_nowait, {"type": "tick", "t": i + 1, "pids": pids}
                )
                time.sleep(1.0)
        finally:
            try:
                reader.disconnect()
            except Exception:
                pass
            loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=run, daemon=True).start()

    async def generate():
        while True:
            event = await q.get()
            if event is None:
                yield 'data: {"type":"done"}\n\n'
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    async def on_disconnect() -> None:
        stop_flag.set()

    resp = StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    # FastAPI expõe o request via state em versões recentes. Como workaround,
    # usamos cleanup por timeout do lado do gerador quando receber None.
    _ = on_disconnect
    return resp
