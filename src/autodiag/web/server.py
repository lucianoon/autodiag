import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / ".autodiag" / ".env")
load_dotenv(".env")

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from autodiag.core.diagnosis import infer_urgency
from autodiag.core.dtc import DTC_DATABASE, lookup
from autodiag.core.vehicle import VehicleProfile, decode_vin_local
from autodiag.db.history import History, Session
from autodiag.elm327 import create_reader
from autodiag.elm327.reader import DTCRecord, list_ports

app = FastAPI(title="AutoDiag")

_STATIC = Path(__file__).parent / "static"


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
    return History().summary()


@app.get("/api/history")
async def api_history(limit: int = Query(10, ge=1, le=100)):
    return History().list(limit)


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
    for code, info in DTC_DATABASE.items():
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

            send({"type": "status", "message": "Lendo PIDs ao vivo..."})
            pids = reader.get_live_pids()
            send({"type": "pids", "pids": pids.as_dict()})

            urgency = infer_urgency(all_dtcs, pids)

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

            sid = History().save(
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
                    cost_min=0,
                    cost_max=0,
                    km=None,
                    notes="",
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
