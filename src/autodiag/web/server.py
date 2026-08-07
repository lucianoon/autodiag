import asyncio
import csv
import io
import ipaddress
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
    hv_request_header_for_brand,
)
from autodiag.core.pdf import render_html_to_pdf
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


def _cors_origins() -> list[str]:
    raw = os.environ.get("AUTODIAG_CORS_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()]


# CORS é opt-in: a SPA é servida pela própria API (same-origin) e não precisa
# de CORS. `allow_origins=["*"]` permitia que qualquer site aberto no
# navegador lesse o histórico (VINs, placas, notas de cliente) e disparasse
# DELETEs sem credencial. Para integrar um front externo, defina
# AUTODIAG_CORS_ORIGINS="https://app.exemplo.com,https://outro.com".
if _cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
        expose_headers=["X-Request-Id", "Content-Disposition"],
    )


def _host_from_header(value: str) -> str:
    v = (value or "").strip().lower()
    if v.startswith("["):  # IPv6 literal: [::1]:8000
        return v[1 : v.find("]")] if "]" in v else ""
    return v.split(":")[0]


def _host_allowed(host: str) -> bool:
    h = host.rstrip(".")
    if not h:
        return False
    # "testserver" é o Host padrão do TestClient do FastAPI/Starlette.
    if h in ("localhost", "testserver") or h.endswith((".localhost", ".local")):
        return True
    try:
        ipaddress.ip_address(h)
        return True  # IP literal (acesso via LAN/celular)
    except ValueError:
        pass
    extra = os.environ.get("AUTODIAG_ALLOWED_HOSTS", "")
    return h in {e.strip().lower() for e in extra.split(",") if e.strip()}


@app.middleware("http")
async def _trusted_host_guard(request: Request, call_next):
    # Bloqueia DNS rebinding e Host forjado: só atende requisições cujo Host
    # é local, um IP literal ou um domínio autorizado via
    # AUTODIAG_ALLOWED_HOSTS (necessário atrás de proxy com domínio próprio).
    host = _host_from_header(request.headers.get("host", ""))
    if not _host_allowed(host):
        return JSONResponse(
            {
                "error": "host_not_allowed",
                "detail": (
                    "Host não autorizado. Para servir sob um domínio, defina "
                    "AUTODIAG_ALLOWED_HOSTS=seu.dominio.com"
                ),
            },
            status_code=400,
        )
    return await call_next(request)

_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC), name="static")

_DEFAULT_BODY_FACTORY = Body(default_factory=dict)

# Um Chromium por vez na geração de PDF (ver report_pdf).
_PDF_SEMAPHORE = asyncio.Semaphore(1)


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
    allowed = {"notes": (str,), "tags": (list,), "hv_data": (dict,), "km": (int, str, type(None)),
               "vin": (str, type(None)), "vehicle_label": (str, type(None))}
    patch: dict[str, Any] = {}
    for k, _t in allowed.items():
        if k not in body:
            continue
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
            continue
        if k == "notes":
            if not isinstance(v, str):
                raise HTTPException(status_code=400, detail="notes deve ser string")
            patch["notes"] = v.strip()[:4000]
            continue
        if k == "hv_data":
            if not isinstance(v, dict):
                raise HTTPException(status_code=400, detail="hv_data deve ser objeto JSON")
            if len(v) > 128:
                raise HTTPException(status_code=400, detail="hv_data maximo 128 chaves")
            cleaned_hv: dict[str, Any] = {}
            for hk, hv in v.items():
                if not isinstance(hk, str) or len(hk) > 64:
                    continue
                if hv is None or isinstance(hv, (str, int, float, bool)):
                    cleaned_hv[hk] = hv[:120] if isinstance(hv, str) else hv
            patch["hv_data"] = cleaned_hv
            continue
        if k == "km":
            if v is None or v == "":
                patch["km"] = None
                continue
            try:
                km_num = int(v)
            except (TypeError, ValueError) as _e:
                    raise HTTPException(
                        status_code=400, detail="km invalido (int esperado)"
                    ) from _e
            if km_num < 0 or km_num > 99_999_999:
                raise HTTPException(
                    status_code=400,
                    detail="km fora do intervalo [0..99.999.999]",
                )
            patch["km"] = km_num
            continue
        if k == "vin":
            if v is None:
                patch["vin"] = None
                continue
            if not isinstance(v, str):
                raise HTTPException(
                    status_code=400, detail="vin invalido (string esperada)"
                )
            cleaned = v.strip().upper()[:30]
            patch["vin"] = cleaned or None
            continue
        if k == "vehicle_label":
            if v is None:
                patch["vehicle_label"] = None
                continue
            if not isinstance(v, str):
                msg = "vehicle_label invalido (string esperada)"
                raise HTTPException(status_code=400, detail=msg)
            cleaned = v.strip()[:200]
            patch["vehicle_label"] = cleaned or None
            continue
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
        prev = history.previous_for_vin(row.get("vin") or "", before_id=sid)
        vhist = history.list_by_vin(row.get("vin") or "", limit=8)
    vin_token = (
        (row.get("vin") or "").strip()[-6:]
        if (row.get("vin") or "").strip()
        else "veiculo"
    )
    ts_token = datetime.now().strftime("%Y%m%d-%H%M")
    filename = f"autodiag-report-{vin_token}-{ts_token}.pdf"
    # O HTML é renderizado aqui e injetado via set_content: o Chromium nunca
    # busca uma URL derivada do header Host (SSRF), nem depende do server
    # estar acessível de dentro do sandbox do browser.
    url = str(request.url_for("report_download", sid=sid))
    rep = build_report(row, prev, vehicle_history=vhist, download_url=url)
    report_html = render_report_html(rep)
    pdf_path: Path | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="autodiag-pdf-")
        os.close(fd)
        pdf_path = Path(tmp_path)
        loop = asyncio.get_running_loop()
        # Cada render sobe um Chromium (~200 MB); o semáforo impede que uma
        # rajada de requests vire DoS de memória.
        async with _PDF_SEMAPHORE:
            await loop.run_in_executor(None, render_html_to_pdf, report_html, pdf_path)
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
    vin: str | None = Query(None),
    vehicle_label: str | None = Query(None),
    km: int | None = Query(None),
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
            vin_elm = reader.get_vin()
            vin_param_clean = vin.strip() if vin and isinstance(vin, str) else None
            if vin_param_clean:
                # Usuário cadastrou o VIN manualmente (ou modo demo ou
                # preenchimento de formulário): sempre prioriza o manual
                final_vin = vin_param_clean
            elif vin_elm and len(vin_elm) >= 5:
                final_vin = vin_elm
            else:
                final_vin = None
            vehicle = decode_vin_local(final_vin) if final_vin else VehicleProfile()
            vehicle.vin = final_vin or vehicle.vin
            manual_label = (vehicle_label or "").strip()
            if final_vin and len(final_vin) == 17 and not demo:
                try:
                    import httpx as _httpx

                    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{final_vin}?format=json"
                    result = _httpx.get(url, timeout=6.0).json().get("Results", [{}])[0]
                    make_get = result.get("Make") or None
                    if make_get and not manual_label:
                        vehicle.make = make_get
                        vehicle.model = result.get("Model") or vehicle.model
                        year = result.get("ModelYear") or ""
                        if year.isdigit():
                            vehicle.year = int(year)
                except Exception:
                    pass
            final_label = manual_label or vehicle.label or "Veículo sem VIN"
            send({"type": "vin", "vin": vehicle.vin or "—", "vehicle": final_label})

            ev_prop = detectar_propulsao_por_vin(final_vin)
            hv_data: dict[str, Any] | None = None

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

            # ── UDS $22 Alta Tensão (HV): por último na fase de leitura, de
            # propósito — se a troca de header CAN falhar num veículo real,
            # DTCs, readiness, freeze frame e PIDs já foram capturados.
            if ev_prop.is_ev_any():
                marca_hv = ev_prop.marca
                campos = hv_fields_for_brand(marca_hv)
                hv_header = hv_request_header_for_brand(marca_hv)
                send({
                    "type": "status",
                    "message": (
                        f"Veículo {ev_prop.propensao.upper()} detectado ({marca_hv or 'marca?'}). "
                        f"Lendo campos HV via UDS $22 (AT SH {hv_header})..."
                    ),
                })
                try:
                    reader_hv_result: dict[str, Any] = reader.read_high_voltage(
                        campos,
                        vin=final_vin,
                        request_header=hv_header,
                    ) or {}
                    if reader_hv_result:
                        hv_data = dict(reader_hv_result)
                        send({
                            "type": "hv_data",
                            "hv_data": hv_data,
                            "ev_support_level": ev_prop.ev_support_level,
                            "count": len({k for k in hv_data if k.startswith("did_")}),
                        })
                        total_dids = len([c for c in campos if c.get("id") and c["id"] > 0])
                        msg = (
                            f"Alta Tensão OK: {len({k for k in hv_data if k.startswith('did_')})}/"
                            f"{total_dids} DIDs respondidos (UDS $22)."
                        )
                        send({"type": "status", "message": msg})
                    else:
                        send({
                            "type": "warn",
                            "message": (
                                "Campos HV: nenhuma ECU HV respondeu UDS $22 via ELM "
                                "(ECU pode exigir seed-key ou interface J2534/CAN-FD). "
                                "Campos ficarão N/D no relatório."
                            ),
                        })
                except Exception as _hv_exc:  # nunca falha o scan por erro em HV
                    send({
                        "type": "warn",
                        "message": (
                            "Leitura HV abortada (ex: timeout ELM). Pode continuar "
                            "com os campos OBD2 padrão. Erro: "
                            f"{str(_hv_exc)[:120]}"
                        ),
                    })
                    hv_data = None

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
                        vehicle_label=final_label,
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
                        km=km,
                        notes="",
                        freeze_frame=freeze_frame,
                        readiness=readiness,
                        hv_data=hv_data if hv_data else None,
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
