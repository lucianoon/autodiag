from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from autodiag.core.dtc import lookup, severity_color
from autodiag.core.vehicle import VehicleProfile
from autodiag.elm327.reader import DTCRecord, LivePIDs

console = Console()


def header(vehicle: VehicleProfile | None = None):
    subtitle = vehicle.label if vehicle else "Conectando..."
    console.print(Panel.fit(
        f"[bold cyan]AutoDiag OBD2[/]\n[dim]{subtitle}[/]",
        border_style="cyan",
    ))


def section(title: str):
    console.print(f"\n[bold yellow]── {title}[/]")


def ok(msg: str):
    console.print(f"  [green]✓[/] {msg}")


def warn(msg: str):
    console.print(f"  [yellow]⚠[/] {msg}")


def err(msg: str):
    console.print(f"  [red]✗[/] {msg}")


def dtcs_table(dtcs: list[DTCRecord]):
    if not dtcs:
        ok("Nenhum DTC armazenado")
        return
    t = Table(title=f"{len(dtcs)} DTC(s) encontrado(s)", box=box.SIMPLE)
    t.add_column("Código", style="bold", width=8)
    t.add_column("Descrição")
    t.add_column("Sistema", width=18)
    t.add_column("Urgência", width=12)
    for dtc in dtcs:
        info = lookup(dtc.code)
        desc = info.description if info else "—"
        system = info.system if info else "—"
        sev = info.severity if info else "informativo"
        color = severity_color(sev)
        t.add_row(dtc.code, desc, system, f"[{color}]{sev}[/]")
    console.print(t)


def pids_table(pids: LivePIDs):
    t = Table(title="PIDs ao vivo", box=box.SIMPLE)
    t.add_column("Parâmetro", style="dim", width=26)
    t.add_column("Valor", justify="right", width=14)
    t.add_column("Status", justify="center", width=6)

    def row(name: str, val, unit: str, lo=None, hi=None):
        if val is None:
            return
        st, sc = "✓", "green"
        if lo is not None and val < lo:
            st, sc = "⚠", "yellow"
        if hi is not None and abs(val) > hi:
            st, sc = "✗", "red"
        t.add_row(name, f"{val} {unit}", f"[{sc}]{st}[/]")

    row("RPM",                   pids.rpm,              "rpm", 600, 5500)
    row("Velocidade",            pids.speed_kmh,        "km/h")
    row("Temperatura motor",     pids.coolant_temp_c,   "°C",  None, 105)
    row("Temperatura admissão",  pids.intake_temp_c,    "°C")
    row("Borboleta",             pids.throttle_pct,     "%")
    row("MAF",                   pids.maf_g_s,          "g/s", 2.0, None)
    row("Fuel trim curto B1",    pids.fuel_trim_short_b1, "%", None, 15)
    row("Fuel trim longo B1",    pids.fuel_trim_long_b1,  "%", None, 10)
    row("O2 B1S1",               pids.o2_b1s1_v,        "V",  0.1, None)
    row("Nível combustível",     pids.fuel_level_pct,   "%",  10,  None)
    console.print(t)


def analysis_panel(text: str, urgency: str = "informativo"):
    color = {"critico": "red", "atencao": "yellow", "informativo": "green"}.get(urgency, "white")
    console.print(Panel(text, title="Análise IA", border_style=color))


def history_table(sessions: list[dict]):
    if not sessions:
        warn("Nenhum diagnóstico registrado.")
        return
    t = Table(title="Histórico de diagnósticos", box=box.SIMPLE)
    t.add_column("ID", width=4)
    t.add_column("Data", width=17)
    t.add_column("Veículo")
    t.add_column("DTCs")
    t.add_column("Urgência", width=12)
    t.add_column("KM", width=8)
    for s in sessions:
        color = {"critico": "red", "atencao": "yellow", "informativo": "green"}.get(s.get("urgency", ""), "white")
        t.add_row(
            str(s["id"]),
            s["ts"],
            s.get("vehicle_label") or "—",
            ", ".join(s["dtc_codes"]) or "—",
            f"[{color}]{s.get('urgency', '—')}[/]",
            str(s.get("km") or "—"),
        )
    console.print(t)


def summary_panel(data: dict):
    section("Resumo")
    console.print(f"  Total de diagnósticos: [bold]{data['total']}[/]")
    console.print(f"  Diagnósticos críticos: [bold red]{data['critical']}[/]")
    if data.get("top_dtcs"):
        console.print("\n  DTCs mais frequentes:")
        for code, cnt in data["top_dtcs"]:
            console.print(f"    [yellow]{code}[/]: {cnt}x")


def dtc_info_panel(code: str):
    from autodiag.core.dtc import lookup
    info = lookup(code)
    if not info:
        warn(f"DTC {code} não encontrado na base local.")
        return
    color = severity_color(info.severity)
    lines = [
        f"[bold]{info.description}[/]",
        f"Sistema: {info.system}",
        f"Urgência: [{color}]{info.severity}[/]",
        "",
        "Causas prováveis:",
    ] + [f"  • {c}" for c in info.causes]
    console.print(Panel("\n".join(lines), title=f"DTC {info.code}", border_style=color))
