"""
AutoDiag OBD2 — diagnóstico universal para veículos 2015+

Uso:
  autodiag scan                  # diagnóstico completo (detecta porta automaticamente)
  autodiag scan --port /dev/cu.x # porta específica
  autodiag scan --wifi 192.168.0.10  # adaptador Wi-Fi
  autodiag scan --no-ai          # sem análise Claude
  autodiag scan --demo           # sem hardware: veículo simulado (P0171 + P0300)
  autodiag history               # últimos 10 diagnósticos
  autodiag history --limit 20
  autodiag summary               # estatísticas gerais
  autodiag dtc P0171             # consultar DTC na base local
  autodiag clear                 # apagar DTCs do veículo
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / ".autodiag" / ".env")
load_dotenv(".env")

from autodiag.core.vehicle import VehicleProfile, decode_vin_nhtsa, decode_vin_local
from autodiag.elm327 import create_reader
from autodiag.elm327.reader import LivePIDs, DTCRecord
from autodiag.db.history import History, Session
from autodiag import ui


def _infer_urgency(dtcs: list[DTCRecord], pids: LivePIDs) -> str:
    CRITICAL = {"P0300","P0301","P0302","P0303","P0304","P0700","P0740","U0100","U0001","B0001","B0002","B1001","C0900"}
    ATTENTION = {"P0101","P0171","P0172","P0174","P0175","P0401","P0506","P0507","U0121","P0420","P0430","P0730","P0741"}
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
    except ConnectionError as e:
        ui.display.err(str(e))
        sys.exit(1)

    if not ok:
        ui.display.err("Falha ao inicializar ELM327. Verifique a conexão.")
        sys.exit(1)

    ui.display.ok("Adaptador conectado")

    # VIN
    ui.display.section("Lendo VIN")
    vin = reader.get_vin()
    ui.display.ok(f"VIN: {vin}" if vin else "VIN não disponível")

    vehicle: VehicleProfile
    if demo:
        vehicle = decode_vin_local(vin)  # VIN sintético: não consultar a NHTSA
    elif vin and len(vin) == 17:
        try:
            vehicle = await decode_vin_nhtsa(vin)
            ui.display.ok(f"Veículo: {vehicle.label}")
        except Exception:
            vehicle = decode_vin_local(vin)
    else:
        vehicle = VehicleProfile(vin=vin or "")

    ui.display.header(vehicle)

    # DTCs
    ui.display.section("Lendo DTCs")
    dtcs = reader.get_dtcs()
    ui.display.dtcs_table(dtcs)

    # PIDs
    ui.display.section("Lendo PIDs ao vivo")
    pids = reader.get_live_pids()
    ui.display.pids_table(pids)

    urgency = _infer_urgency(dtcs, pids)

    # IA
    diagnosis_text = ""
    if not getattr(args, "no_ai", False):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            ui.display.warn("ANTHROPIC_API_KEY não definida — análise IA ignorada.")
        else:
            ui.display.section("Análise com IA (Claude)")
            try:
                from autodiag.agents.diagnostic import analyze
                diagnosis_text = analyze(vehicle, dtcs, pids)
                ui.display.analysis_panel(diagnosis_text, urgency)
            except Exception as e:
                ui.display.warn(f"Erro na análise IA: {e}")

    # KM + notas
    km_raw = input("\n  Quilometragem atual (km): ").strip()
    km = int(km_raw.replace(".", "").replace(",", "")) if km_raw.isdigit() or km_raw.replace(".", "").replace(",", "").isdigit() else None
    notes = input("  Observações (opcional): ").strip()

    # Salvar
    session = Session(
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
        diagnosis=diagnosis_text,
        cost_min=0,
        cost_max=0,
        km=km,
        notes=notes,
    )
    sid = History().save(session)
    ui.display.ok(f"Diagnóstico salvo no histórico (ID #{sid})")
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
    except ConnectionError as e:
        ui.display.err(str(e))
        sys.exit(1)
    confirm = input("  Confirmar apagar todos os DTCs? [s/N]: ").strip().lower()
    if confirm != "s":
        ui.display.warn("Cancelado.")
        return
    ok = reader.clear_dtcs()
    reader.disconnect()
    if ok:
        ui.display.ok("DTCs apagados com sucesso.")
    else:
        ui.display.err("Falha ao apagar DTCs.")


def main():
    if sys.platform == "win32":
        # Console legado do Windows usa cp1252; a saída do rich exige UTF-8
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass

    parser = argparse.ArgumentParser(
        prog="autodiag",
        description="Diagnóstico OBD2 universal para veículos 2015+",
    )
    sub = parser.add_subparsers(dest="cmd")

    # scan
    p_scan = sub.add_parser("scan", help="Conectar e executar diagnóstico completo")
    p_scan.add_argument("--port", metavar="PORTA", help="Ex: /dev/cu.usbserial-1410")
    p_scan.add_argument("--wifi", metavar="HOST", help="IP do adaptador Wi-Fi (padrão: 192.168.0.10)")
    p_scan.add_argument("--no-ai", action="store_true", help="Pular análise com Claude")
    p_scan.add_argument("--demo", action="store_true",
                        help="Usar adaptador simulado (roda sem hardware OBD2)")

    # history
    p_hist = sub.add_parser("history", help="Mostrar histórico de diagnósticos")
    p_hist.add_argument("--limit", type=int, default=10, metavar="N")

    # summary
    sub.add_parser("summary", help="Estatísticas gerais")

    # dtc
    p_dtc = sub.add_parser("dtc", help="Consultar DTC na base local")
    p_dtc.add_argument("code", metavar="CODIGO", help="Ex: P0171")

    # clear
    p_clear = sub.add_parser("clear", help="Apagar DTCs do veículo")
    p_clear.add_argument("--port", metavar="PORTA")
    p_clear.add_argument("--demo", action="store_true",
                        help="Usar adaptador simulado (roda sem hardware OBD2)")

    # serve
    p_serve = sub.add_parser("serve", help="Iniciar interface web (http://localhost:8000)")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--open", action="store_true", help="Abrir browser automaticamente")

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
            import webbrowser, threading
            threading.Timer(1.0, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
        print(f"  AutoDiag web → http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
