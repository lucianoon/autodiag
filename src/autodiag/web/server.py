import asyncio
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path.home() / ".autodiag" / ".env")

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from autodiag.core.dtc import lookup, DTC_DATABASE
from autodiag.core.vehicle import decode_vin_local, VehicleProfile
from autodiag.db.history import History, Session
from autodiag.elm327.reader import ELM327Reader, DTCRecord, LivePIDs

app = FastAPI(title="AutoDiag")

_STATIC = Path(__file__).parent / "static"


def _infer_urgency(dtcs: list[DTCRecord], pids: LivePIDs) -> str:
    CRITICAL = {"P0300","P0301","P0302","P0303","P0304","P0700","P0740",
                "U0100","U0001","B0001","B0002","B1001","C0900"}
    ATTENTION = {"P0101","P0171","P0172","P0174","P0175","P0401","P0506",
                 "P0507","U0121","P0420","P0430","P0730","P0741"}
    codes = {d.code for d in dtcs}
    if codes & CRITICAL:
        return "critico"
    if pids.coolant_temp_c and pids.coolant_temp_c > 108:
        return "critico"
    if codes & ATTENTION:
        return "atencao"
    if pids.fuel_trim_short_b1 and abs(pids.fuel_trim_short_b1) > 15:
        return "atencao"
    if pids.maf_g_s is not None and pids.maf_g_s < 2.0:
        return "atencao"
    if dtcs:
        return "atencao"
    return "informativo"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return (_STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/summary")
async def api_summary():
    return History().summary()


@app.get("/api/history")
async def api_history(limit: int = Query(10, ge=1, le=100)):
    return History().list(limit)


@app.get("/api/dtc/{code}")
async def api_dtc(code: str):
    info = lookup(code.upper())
    if not info:
        return JSONResponse({"error": f"DTC {code.upper()} não encontrado"}, status_code=404)
    return {"code": info.code, "description": info.description,
            "severity": info.severity, "system": info.system, "causes": info.causes}


@app.get("/api/dtc")
async def api_dtc_search(q: str = Query("")):
    q_up = q.upper().strip()
    q_lo = q.lower().strip()
    results = []
    for code, info in DTC_DATABASE.items():
        if q_up in code or q_lo in info.description.lower():
            results.append({"code": info.code, "description": info.description,
                            "severity": info.severity, "system": info.system})
    return results[:20]


@app.get("/api/scan/stream")
async def api_scan_stream(
    port: str = Query(None),
    wifi: str = Query(None),
    no_ai: bool = Query(False),
):
    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()

    def send(data: dict):
        loop.call_soon_threadsafe(q.put_nowait, data)

    def run():
        try:
            send({"type": "status", "message": "Conectando ao adaptador ELM327..."})
            reader = ELM327Reader(port=port, wifi_host=wifi)
            connected = reader.connect()
            if not connected:
                send({"type": "error", "message": "Falha ao inicializar ELM327. Verifique a conexão."})
                return
            send({"type": "status", "message": "Adaptador conectado"})

            # VIN
            send({"type": "status", "message": "Lendo VIN..."})
            vin = reader.get_vin()
            vehicle = decode_vin_local(vin) if vin else VehicleProfile()
            if vin and len(vin) == 17:
                try:
                    import httpx as _httpx
                    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
                    res = _httpx.get(url, timeout=6.0).json().get("Results", [{}])[0]
                    vehicle.make = res.get("Make") or vehicle.make
                    vehicle.model = res.get("Model") or ""
                    yr = res.get("ModelYear") or ""
                    if yr.isdigit():
                        vehicle.year = int(yr)
                except Exception:
                    pass
            send({"type": "vin", "vin": vin or "—", "vehicle": vehicle.label})

            # DTCs
            send({"type": "status", "message": "Lendo DTCs..."})
            dtcs = reader.get_dtcs()
            dtc_list = []
            for d in dtcs:
                info = lookup(d.code)
                dtc_list.append({
                    "code": d.code,
                    "description": info.description if info else "—",
                    "severity": info.severity if info else "informativo",
                    "system": info.system if info else "—",
                })
            send({"type": "dtcs", "dtcs": dtc_list})

            # PIDs
            send({"type": "status", "message": "Lendo PIDs ao vivo..."})
            pids = reader.get_live_pids()
            send({"type": "pids", "pids": pids.as_dict()})
            reader.disconnect()

            urgency = _infer_urgency(dtcs, pids)

            # IA
            analysis = ""
            if not no_ai and os.environ.get("ANTHROPIC_API_KEY"):
                send({"type": "status", "message": "Analisando com Claude..."})
                try:
                    from autodiag.agents.diagnostic import analyze
                    analysis = analyze(vehicle, dtcs, pids)
                    send({"type": "analysis", "text": analysis})
                except Exception as e:
                    send({"type": "warn", "message": f"Erro na análise IA: {e}"})

            # Salvar
            sid = History().save(Session(
                id=None,
                ts=datetime.now().strftime("%d/%m/%Y %H:%M"),
                vin=vehicle.vin,
                vehicle_label=vehicle.label,
                dtc_codes=[d.code for d in dtcs],
                urgency=urgency,
                rpm=pids.rpm,
                speed=pids.speed_kmh,
                coolant_temp=pids.coolant_temp_c,
                maf=pids.maf_g_s,
                fuel_trim_short=pids.fuel_trim_short_b1,
                fuel_trim_long=pids.fuel_trim_long_b1,
                o2=pids.o2_b1s1_v,
                diagnosis=analysis,
                cost_min=0,
                cost_max=0,
                km=None,
                notes="",
            ))
            send({"type": "saved", "session_id": sid, "urgency": urgency})

        except ConnectionError as e:
            send({"type": "error", "message": str(e)})
        except Exception as e:
            send({"type": "error", "message": f"Erro inesperado: {e}"})
        finally:
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
