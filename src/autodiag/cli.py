"""
AutoDiag OBD2 — diagnóstico universal para veículos 2015+

Uso:
  autodiag scan                  # diagnóstico completo (detecta porta automaticamente)
  autodiag scan --port /dev/cu.x # porta específica
  autodiag scan --wifi 192.168.0.10  # adaptador Wi-Fi
  autodiag scan --no-ai          # sem análise IA
  autodiag scan --model gpt-4.1-mini  # escolher o modelo
  autodiag scan --demo           # sem hardware: veículo simulado (P0171 + P0300)
  autodiag history               # últimos 10 diagnósticos
  autodiag history --limit 20
  autodiag summary               # estatísticas gerais
  autodiag dtc P0171             # consultar DTC na base local
  autodiag clear                 # apagar DTCs do veículo
"""

import argparse
import asyncio
import io
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / ".autodiag" / ".env")
load_dotenv(".env")

from autodiag import ui
from autodiag.core.diagnosis import infer_urgency
from autodiag.core.report import build_report, render_report_html
from autodiag.core.triage import build_guided_triage
from autodiag.core.vehicle import VehicleProfile, decode_vin_local, decode_vin_nhtsa
from autodiag.db.history import History, Session
from autodiag.elm327 import create_reader
from autodiag.elm327.reader import DTCRecord, LivePIDs


def _infer_urgency(dtcs: list[DTCRecord], pids: LivePIDs) -> str:
    return infer_urgency(dtcs, pids)


async def cmd_scan(args):
    demo = getattr(args, "demo", False)
    if demo:
        ui.display.section("Modo demo — adaptador ELM327 simulado")
    else:
        ui.display.section("Conectando ao adaptador ELM327")

    wifi_host = args.wifi if hasattr(args, "wifi") else None
    reader = create_reader(port=getattr(args, "port", None), wifi_host=wifi_host, demo=demo)

    try:
        ok = reader.connect()
        if not ok:
            ui.display.err("Falha ao inicializar ELM327. Verifique a conexão.")
            sys.exit(1)

        ui.display.ok("Adaptador conectado")

        ui.display.section("Status do veículo")
        battery_voltage = reader.get_control_module_voltage()
        monitor_status = reader.get_monitor_status()
        supported_pids = reader.get_supported_pids()
        ui.display.vehicle_status_panel(battery_voltage, monitor_status, supported_pids)

        ui.display.section("Lendo VIN")
        vin = reader.get_vin()
        ui.display.ok(f"VIN: {vin}" if vin else "VIN não disponível")

        vehicle: VehicleProfile
        if demo:
            vehicle = decode_vin_local(vin)
        elif vin and len(vin) == 17:
            try:
                vehicle = await decode_vin_nhtsa(vin)
                ui.display.ok(f"Veículo: {vehicle.label}")
            except Exception:
                vehicle = decode_vin_local(vin)
        else:
            vehicle = VehicleProfile(vin=vin or "")

        ui.display.header(vehicle)

        ui.display.section("Lendo DTCs")
        dtcs = reader.get_dtcs()
        pending_dtcs = reader.get_pending_dtcs()
        permanent_dtcs = reader.get_permanent_dtcs()
        all_dtcs = dtcs + pending_dtcs + permanent_dtcs
        ui.display.dtcs_table(all_dtcs)

        freeze_frame: dict | None = None
        try:
            ff_raw = reader.get_freeze_frame()
            freeze_frame = ff_raw.as_dict()
            if any(freeze_frame.get(k) not in (None, "") for k in freeze_frame if k != "raw"):
                ui.display.freeze_frame_panel(freeze_frame)
        except Exception as _e:
            freeze_frame = None

        ui.display.section("Lendo PIDs ao vivo")
        pids = reader.get_live_pids()
        ui.display.pids_table(pids)

        urgency = infer_urgency(all_dtcs, pids)
        triage = build_guided_triage(all_dtcs, pids, urgency)
        ui.display.triage_panel(triage, urgency)

        diagnosis_text = ""
        if not getattr(args, "no_ai", False):
            from autodiag.agents.diagnostic import (
                AIUnavailableError,
                analyze,
                describe,
                is_configured,
            )

            if not is_configured():
                ui.display.warn(
                    "Nenhum modelo configurado — análise IA ignorada. Defina "
                    "ANTHROPIC_API_KEY, OPENAI_API_KEY ou AUTODIAG_BASE_URL."
                )
            else:
                model = getattr(args, "model", None)
                ui.display.section(f"Análise com IA ({model or describe()})")
                try:
                    diagnosis_text = analyze(vehicle, all_dtcs, pids, model=model)
                    ui.display.analysis_panel(diagnosis_text, urgency)
                except AIUnavailableError as e:
                    ui.display.warn(str(e))
                except Exception as e:
                    ui.display.warn(f"Erro na análise IA: {e}")

        km_raw = input("\n  Quilometragem atual (km): ").strip()
        km_digits = km_raw.replace(".", "").replace(",", "")
        km = int(km_digits) if km_digits.isdigit() else None
        notes = input("  Observações (opcional): ").strip()

        session = Session(
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
            diagnosis=diagnosis_text,
            triage=triage,
            cost_min=0,
            cost_max=0,
            km=km,
            notes=notes,
            freeze_frame=freeze_frame,
        )
        sid = History().save(session)
        ui.display.ok(f"Diagnóstico salvo no histórico (ID #{sid})")
    except ConnectionError as e:
        ui.display.err(str(e))
        sys.exit(1)
    finally:
        reader.disconnect()


def cmd_history(args):
    limit = getattr(args, "limit", 10)
    sessions = History().list(limit)
    ui.display.history_table(sessions)


def cmd_summary(_args):
    data = History().summary()
    ui.display.summary_panel(data)


def cmd_dtc(args):
    ui.display.dtc_info_panel(args.code.upper())


def cmd_clear(args):
    ui.display.section("Apagando DTCs")
    reader = create_reader(port=getattr(args, "port", None), demo=getattr(args, "demo", False))
    try:
        reader.connect()
        confirm = input("  Confirmar apagar todos os DTCs? [s/N]: ").strip().lower()
        if confirm != "s":
            ui.display.warn("Cancelado.")
            return
        ok = reader.clear_dtcs()
    except ConnectionError as e:
        ui.display.err(str(e))
        sys.exit(1)
    finally:
        reader.disconnect()
    if ok:
        ui.display.ok("DTCs apagados com sucesso.")
    else:
        ui.display.err("Falha ao apagar DTCs.")


def cmd_report(args):
    sid = int(args.id)
    history = History()
    row = history.get(sid)
    if not row:
        ui.display.err(f"Sessão {sid} não encontrada.")
        sys.exit(1)
    prev = history.previous_for_vin(row.get("vin") or "", before_id=sid)
    rep = build_report(row, prev)
    html = render_report_html(rep)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as f:
        f.write(html)
        path = f.name
    ui.display.ok(f"Relatório gerado: {path}")
    if getattr(args, "open", False):
        import webbrowser

        webbrowser.open(f"file://{path}")


def main():
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if isinstance(stream, io.TextIOWrapper):
                try:
                    stream.reconfigure(encoding="utf-8", errors="replace")
                except OSError:
                    pass

    parser = argparse.ArgumentParser(
        prog="autodiag",
        description="Diagnóstico OBD2 universal para veículos 2015+",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan", help="Conectar e executar diagnóstico completo")
    p_scan.add_argument("--port", metavar="PORTA", help="Ex: /dev/cu.usbserial-1410")
    p_scan.add_argument("--wifi", metavar="HOST", help="IP do adaptador Wi-Fi, ex: 192.168.0.10")
    p_scan.add_argument("--no-ai", action="store_true", help="Pular análise com IA")
    p_scan.add_argument(
        "--model",
        metavar="MODELO",
        help=(
            "Modelo a usar (sobrescreve AUTODIAG_MODEL). "
            "Ex: claude-opus-5, gpt-4.1-mini, llama3.1"
        ),
    )
    p_scan.add_argument(
        "--demo",
        action="store_true",
        help="Usar adaptador simulado (roda sem hardware OBD2)",
    )

    p_hist = sub.add_parser("history", help="Mostrar histórico de diagnósticos")
    p_hist.add_argument("--limit", type=int, default=10, metavar="N")

    sub.add_parser("summary", help="Estatísticas gerais")

    p_dtc = sub.add_parser("dtc", help="Consultar DTC na base local")
    p_dtc.add_argument("code", metavar="CODIGO", help="Ex: P0171")

    p_clear = sub.add_parser("clear", help="Apagar DTCs do veículo")
    p_clear.add_argument("--port", metavar="PORTA")
    p_clear.add_argument(
        "--demo",
        action="store_true",
        help="Usar adaptador simulado (roda sem hardware OBD2)",
    )

    p_serve = sub.add_parser("serve", help="Iniciar interface web (http://localhost:8000)")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--open", action="store_true", help="Abrir browser automaticamente")

    p_report = sub.add_parser("report", help="Gerar relatório HTML de uma sessão")
    p_report.add_argument("id", metavar="ID", help="ID da sessão no histórico")
    p_report.add_argument("--open", action="store_true", help="Abrir relatório no browser")

    args = parser.parse_args()

    if args.cmd == "scan":
        asyncio.run(cmd_scan(args))
    elif args.cmd == "history":
        cmd_history(args)
    elif args.cmd == "summary":
        cmd_summary(args)
    elif args.cmd == "dtc":
        cmd_dtc(args)
    elif args.cmd == "clear":
        cmd_clear(args)
    elif args.cmd == "serve":
        import uvicorn

        from autodiag.web.server import app

        if getattr(args, "open", False):
            import threading
            import webbrowser

            threading.Timer(1.0, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
        print(f"  AutoDiag web → http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.cmd == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
