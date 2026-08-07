import asyncio
import csv
import io
import json
import os
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path.home() / ".autodiag" / ".env")
load_dotenv(".env")

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from autodiag.core.config import (
    PERSONAS_META,
    Branding,
    get_branding,
    list_personas,
    load_config,
    set_persona,
    update_branding,
)
from autodiag.core.diagnosis import infer_urgency
from autodiag.core.dtc import full_database, lookup
from autodiag.core.ev_support import (
    SUPPORT_LEVEL_LABELS,
    detectar_propulsao_por_vin,
    hv_fields_for_brand,
)
from autodiag.core.pdf import render_url_to_pdf
from autodiag.core.readiness import build_readiness_summary
from autodiag.core.report import build_report, render_report_html
from autodiag.core.trend import build_vehicle_trends
from autodiag.core.triage import build_guided_triage
from autodiag.core.vehicle import VehicleProfile, decode_vin_local
from autodiag.db.history import History, Session
from autodiag.elm327 import OBDReader, create_reader
from autodiag.elm327.reader import DTCRecord, list_ports

STARTUP_TS = time.time()
app = FastAPI(title="AutoDiag")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
    expose_headers=["X-Request-Id", "Content-Disposition"],
)

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
            if k == "tags":
                if not isinstance(v, list):
                    raise HTTPException(status_code=400, detail="tags deve ser lista")
                if not all(isinstance(t, str) for t in v):
                    raise HTTPException(status_code=400, detail="tags deve ser lista de strings")
                if len(v) > 16:
                    raise HTTPException(status_code=400, detail="maximo 16 tags")
                cleaned_tags: list[str] = []
                for t in v:
                    t_clean = t.strip()[:80]
                    if t_clean:
                        cleaned_tags.append(t_clean)
                patch["tags"] = cleaned_tags
            if k == "notes":
                if not isinstance(v, str):
                    raise HTTPException(status_code=400, detail="notes deve ser string")
                patch["notes"] = v.strip()[:4000]
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


@app.delete("/api/session/{sid}")
async def api_delete_session(
    sid: int,
    purge: bool = Query(default=False, description="Remove permanentemente em vez de soft-delete"),
):
    with History() as history:
        ok = history.delete_session(sid, purge=purge)
    if not ok:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {"deleted": True, "purged": purge, "id": sid}


@app.get("/api/branding")
async def api_get_branding():
    from dataclasses import asdict

    return asdict(get_branding())


@app.put("/api/branding")
async def api_put_branding(body: dict[str, Any] = _DEFAULT_BODY_FACTORY):
    from dataclasses import asdict

    updated = update_branding({k: str(body.get(k, "")) for k in Branding.__dataclass_fields__})
    return asdict(updated)


@app.get("/api/ev-info")
async def api_ev_info(vin: str | None = None) -> dict[str, Any]:
    """Detecta propulsão BEV/PHEV/HEV/ICE por VIN e retorna:
    - marca + confiança + motivo
    - nivel de suporte EV BR + label PT-BR
    - lista de campos HV conhecidos (DIDs UDS 0x22) da marca

    Se VIN None/inválido, retorna objeto vazio com level='not_tested'.
    """
    ev = detectar_propulsao_por_vin(vin)
    marca = ev.marca
    return {
        "vin": vin or "",
        "marca": marca,
        "propensao": ev.propensao,
        "confianca": ev.confianca,
        "motivo": ev.motivo,
        "is_ev_any": ev.is_ev_any(),
        "ev_support_level": ev.ev_support_level,
        "level_label": SUPPORT_LEVEL_LABELS.get(ev.ev_support_level, ""),
        "fields_hv": hv_fields_for_brand(marca),
    }


@app.get("/api/persona")
async def api_get_persona() -> dict[str, Any]:
    """Retorna persona ativa + lista de personas disponíveis + meta."""
    cfg = load_config()
    active = cfg.persona if cfg.persona in PERSONAS_META else "mechanic"
    return {
        "personas": list_personas(),
        "active_id": active,
        "active_meta": PERSONAS_META.get(active) or PERSONAS_META["mechanic"],
        "selected": bool(cfg.persona_selected),
    }


@app.put("/api/persona")
async def api_put_persona(body: dict[str, Any] = _DEFAULT_BODY_FACTORY) -> dict[str, Any]:
    """Altera a persona ativa. `id` obrigatório (mechanic|shop_boss|inspector|fleet).

    `mark_selected: true` por padrão → suprime o onboarding inicial da persona
    nas próximas visitas (pode ser re-aberto no modal do header).
    """
    pid = str((body or {}).get("id") or "").strip()
    mark = bool((body or {}).get("mark_selected", True))
    chosen = set_persona(pid, mark_selected=mark)
    return {
        "ok": True,
        "active_id": chosen,
        "active_meta": PERSONAS_META.get(chosen) or PERSONAS_META["mechanic"],
        "selected": mark,
    }


@app.get("/api/app-context")
async def api_app_context() -> dict[str, Any]:
    """Contexto de inicialização da SPA: branding + persona + health mínimo.

    Evita 3 viagens separadas em telas lentas.
    """
    from dataclasses import asdict

    cfg = load_config()
    active = cfg.persona if cfg.persona in PERSONAS_META else "mechanic"
    return {
        "branding": asdict(cfg.branding),
        "persona": {
            "personas": list_personas(),
            "active_id": active,
            "active_meta": PERSONAS_META.get(active) or PERSONAS_META["mechanic"],
            "selected": bool(cfg.persona_selected),
        },
        "version": "0.4.0",
        "tenant": (get_branding().workshop_name.strip() or "")[:24] or "Oficina",
    }


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
async def report(sid: int, request: Request):
    with History() as history:
        row = history.get(sid)
        if not row:
            return HTMLResponse(f"Sessão {sid} não encontrada", status_code=404)
        prev = history.previous_for_vin(row.get("vin") or "", before_id=sid)
        vhist = history.list_by_vin(row.get("vin") or "", limit=8)
    url = str(request.url_for("report_download", sid=sid))
    rep = build_report(row, prev, vehicle_history=vhist, download_url=url)
    return render_report_html(rep)


@app.get("/report/{sid}/download", response_class=HTMLResponse)
async def report_download(sid: int, request: Request):
    with History() as history:
        row = history.get(sid)
        if not row:
            return HTMLResponse(f"Sessão {sid} não encontrada", status_code=404)
        prev = history.previous_for_vin(row.get("vin") or "", before_id=sid)
        vhist = history.list_by_vin(row.get("vin") or "", limit=8)
    url = str(request.url_for("report_download", sid=sid))
    rep = build_report(row, prev, vehicle_history=vhist, download_url=url)
    html = render_report_html(rep)
    return HTMLResponse(
        html,
        headers={
            "Content-Disposition": f'attachment; filename="autodiag-report-{sid}.html"'
        },
    )


@app.get("/report/{sid}/pdf")
async def report_pdf(sid: int, request: Request):
    with History() as history:
        row = history.get(sid)
    if not row:
        return HTMLResponse(f"Sessão {sid} não encontrada", status_code=404)
    vin_token = (
        (row.get("vin") or "").strip()[-6:]
        if (row.get("vin") or "").strip()
        else "veiculo"
    )
    ts_token = datetime.now().strftime("%Y%m%d-%H%M")
    filename = f"autodiag-report-{vin_token}-{ts_token}.pdf"
    report_url = str(request.url_for("report", sid=sid))
    pdf_path: Path | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="autodiag-pdf-")
        os.close(fd)
        pdf_path = Path(tmp_path)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, render_url_to_pdf, report_url, pdf_path)
    except RuntimeError as e:
        if pdf_path is not None and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
        return JSONResponse(
            {"error": "playwright_required", "detail": str(e)}, status_code=503
        )
    except Exception as e:
        if pdf_path is not None and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=500, detail=f"Falha ao gerar PDF: {e}"
        ) from e

    def iter_cleanup() -> Any:
        fh = open(pdf_path, "rb")
        try:
            while True:
                chunk = fh.read(1024 * 256)
                if not chunk:
                    break
                yield chunk
        finally:
            fh.close()
            try:
                pdf_path.unlink()
            except Exception:
                pass

    return StreamingResponse(
        iter_cleanup(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/ping")
async def api_ping() -> dict[str, Any]:
    """Endpoint público para healthcheck / keep-alive / supervisão de container.

    Retorna sempre o mesmo shape `{ping}`. Não toca no DB, não bloqueia,
    serve para load balancers (AWS ALB, Caddy, Traefik, K8s readinessProbe)
    validarem que o processo respondeu HTTP 200 em <500ms.
    """
    return {"ping": "pong", "ts": time.time()}


@app.get("/health")
@app.get("/api/health")
async def api_health() -> JSONResponse:
    """Health detalhado para monitoramento em escala (Prometheus, Datadog, etc.).

    Expõe: versão do pacote, pid do processo, tempo de uptime em segundos,
    tamanho do banco SQLite em bytes, tenant id (workshop_name + 6 primeiros
    chars do hostname ou AUTODIAG_TENANT), contagem sumária de sessões no
    histórico. Se o DB não abrir → retorna HTTP 503 `{status:"degraded"}`
    em vez de crash (bom pra alertas em grafana/prometheus).
    """
    import importlib.metadata as _meta

    version: str = "0.4.0"
    try:
        version = _meta.version("autodiag") or version
    except Exception:
        pass

    now = time.time()
    uptime_s = max(0.0, now - STARTUP_TS)
    tenant_from_env = os.environ.get("AUTODIAG_TENANT", "").strip()
    tenant_id = tenant_from_env or (
        (get_branding().workshop_name.strip() or "")[:24] or "unknown"
    )
    pid = os.getpid()
    db_path = None
    db_size_bytes = 0
    total_sessions = 0
    critical_sessions = 0
    status_ok = True
    last_scan: str | None = None
    try:
        with History() as h:
            rows = h.summary()
            total_sessions = int(rows.get("total_sessions") or 0)
            critical_sessions = int(rows.get("critical") or 0)
            last_row = rows.get("last_session") or {}
            last_scan = str(last_row.get("ts")) if last_row else None
            db_path = Path(h._con.execute("PRAGMA database_list").fetchone()[2])
            if db_path and db_path.exists():
                db_size_bytes = db_path.stat().st_size
    except Exception as _e:
        status_ok = False
    iso_startup = datetime.fromtimestamp(STARTUP_TS, tz=UTC).isoformat()
    payload: dict[str, Any] = {
        "status": "ok" if status_ok else "degraded",
        "service": "autodiag",
        "version": version,
        "pid": pid,
        "uptime_seconds": round(uptime_s, 3),
        "started_at": iso_startup,
        "tenant": tenant_id,
        "database": {
            "path": str(db_path) if db_path else None,
            "size_bytes": db_size_bytes,
            "sessions": total_sessions,
            "critical_sessions": critical_sessions,
            "last_scan_ts": last_scan,
        },
    }
    code = 200 if status_ok else 503
    return JSONResponse(payload, status_code=code)


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
    q: asyncio.Queue[dict | list | None] = asyncio.Queue()

    def run() -> None:
        samples: list[dict] = []
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
                samples.append({"t": i + 1, "pids": pids})
                loop.call_soon_threadsafe(
                    q.put_nowait, {"type": "tick", "t": i + 1, "pids": pids}
                )
                time.sleep(1.0)
        finally:
            try:
                reader.disconnect()
            except Exception:
                pass
            loop.call_soon_threadsafe(q.put_nowait, samples)

    threading.Thread(target=run, daemon=True).start()

    async def generate():
        while True:
            event = await q.get()
            if isinstance(event, list):
                payload = {
                    "type": "done",
                    "duration": duration,
                    "samples": event,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break
            if event is None:
                yield 'data: {"type":"done","samples":[]}\n\n'
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
