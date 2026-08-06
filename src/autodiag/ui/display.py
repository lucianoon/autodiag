from rich import box
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from autodiag.core.dtc import lookup, severity_color
from autodiag.core.vehicle import VehicleProfile
from autodiag.elm327.reader import DTCRecord, LivePIDs, MonitorStatus

console = Console()


def header(vehicle: VehicleProfile | None = None):
    subtitle = vehicle.label if vehicle else "Conectando..."
    console.print(Panel.fit(
        f"[bold cyan]AutoDiag OBD2[/]\n[dim]{subtitle}[/]",
        border_style="cyan",
    ))


def section(title: str):
    console.print(f"\n[bold yellow]── {title}[/]")


# ok/warn/err recebem texto que não controlamos — mensagens de exceção, nomes
# de modelo, instruções com extras entre colchetes. O rich leria "[openai]" como
# tag de estilo, então "pip install 'autodiag[openai]'" sairia como
# "pip install 'autodiag'". escape() neutraliza os colchetes.
def ok(msg: str):
    console.print(f"  [green]✓[/] {escape(msg)}")


def warn(msg: str):
    console.print(f"  [yellow]⚠[/] {escape(msg)}")


def err(msg: str):
    console.print(f"  [red]✗[/] {escape(msg)}")


def dtcs_table(dtcs: list[DTCRecord]):
    if not dtcs:
        ok("Nenhum DTC armazenado")
        return
    t = Table(title=f"{len(dtcs)} DTC(s) encontrado(s)", box=box.SIMPLE)
    t.add_column("Código", style="bold", width=8)
    t.add_column("Status", width=12)
    t.add_column("Descrição")
    t.add_column("Sistema", width=18)
    t.add_column("Urgência", width=12)
    for dtc in dtcs:
        info = lookup(dtc.code)
        desc = info.description if info else "—"
        system = info.system if info else "—"
        sev = info.severity if info else "informativo"
        color = severity_color(sev)
        t.add_row(dtc.code, dtc.status, desc, system, f"[{color}]{sev}[/]")
    console.print(t)


def vehicle_status_panel(
    battery_voltage: float | None,
    monitor_status: MonitorStatus,
    supported_pids: list[str],
):
    t = Table(title="Status OBD", box=box.SIMPLE)
    t.add_column("Item", style="dim")
    t.add_column("Valor", justify="right")

    voltage = f"{battery_voltage:.1f} V" if battery_voltage is not None else "—"
    if monitor_status.mil_on is None:
        mil = "—"
    else:
        mil = "acesa" if monitor_status.mil_on else "apagada"
    dtc_count = str(monitor_status.dtc_count) if monitor_status.dtc_count is not None else "—"
    pids = f"{len(supported_pids)} PIDs" if supported_pids else "—"

    t.add_row("Tensão módulo/adaptador", voltage)
    t.add_row("MIL / luz de injeção", mil)
    t.add_row("DTCs reportados pela ECU", dtc_count)
    t.add_row("PIDs suportados", pids)
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

    row("Carga calculada",       pids.engine_load_pct,  "%")
    row("RPM",                   pids.rpm,              "rpm", 600, 5500)
    row("Velocidade",            pids.speed_kmh,        "km/h")
    row("Temperatura motor",     pids.coolant_temp_c,   "°C",  None, 105)
    row("Temperatura admissão",  pids.intake_temp_c,    "°C")
    row("Avanço de ignição",     pids.timing_advance_deg, "°")
    row("Pressão combustível",   pids.fuel_pressure_kpa, "kPa")
    row("Borboleta",             pids.throttle_pct,     "%")
    row("MAF",                   pids.maf_g_s,          "g/s", 2.0, None)
    row("Lambda comandada",      pids.commanded_equivalence_ratio, "λ")
    row("Fuel trim curto B1",    pids.fuel_trim_short_b1, "%", None, 15)
    row("Fuel trim longo B1",    pids.fuel_trim_long_b1,  "%", None, 10)
    row("O2 B1S1",               pids.o2_b1s1_v,        "V",  0.1, None)
    row("O2 B1S2",               pids.o2_b1s2_v,        "V",  0.1, None)
    row("O2 B2S1",               pids.o2_b2s1_v,        "V",  0.1, None)
    row("O2 B2S2",               pids.o2_b2s2_v,        "V",  0.1, None)
    row("Nível combustível",     pids.fuel_level_pct,   "%",  10,  None)
    console.print(t)


def analysis_panel(text: str, urgency: str = "informativo"):
    color = {"critico": "red", "atencao": "yellow", "informativo": "green"}.get(urgency, "white")
    # Saída de modelo é texto arbitrário: um "[CRITICO]" desapareceria e um
    # "[/PCV]" derrubaria o painel com MarkupError. Text() não parseia marcação.
    console.print(Panel(Text(text), title="Análise IA", border_style=color))


def triage_panel(triage: dict, urgency: str = "informativo"):
    if not triage:
        return
    sev_colors = {"critico": "red", "atencao": "yellow", "informativo": "green"}
    color = sev_colors.get(urgency, "white")
    drive = triage.get("drive_advice") or "—"
    drive_map = {"pare": "PARE", "cautela": "RODE COM CAUTELA", "pode_rodar": "PODE RODAR"}
    drive_label = drive_map.get(drive, drive.upper())

    headline = triage.get("headline") or ""
    header_lines: list[str] = []
    if headline:
        header_lines.append(f"[bold]{escape(headline)}[/]")
    header_lines.append(f"Orientação: [bold]{escape(drive_label)}[/]")

    obs = triage.get("observations") or []
    items: list = [Text.from_markup("\n".join(header_lines))]
    if obs:
        t = Table(box=box.SIMPLE, show_header=True)
        t.add_column("Sinal", style="dim")
        t.add_column("Valor", justify="right")
        t.add_column("Nível", width=12)
        for o in obs:
            sev = o.get("severity") or "informativo"
            sev_color = sev_colors.get(sev, "white")
            t.add_row(
                escape(o.get("label") or "—"),
                escape(o.get("value") or "—"),
                f"[{sev_color}]{escape(sev)}[/]",
            )
        items.append(t)

    def bullets(title: str, values: list[str]) -> Text | None:
        if not values:
            return None
        lines = [f"[bold]{escape(title)}[/]"] + [f"• {escape(v)}" for v in values]
        return Text.from_markup("\n".join(lines))

    for section in (
        bullets("Causas prováveis", triage.get("likely_causes") or []),
        bullets("Testes sugeridos (ordem)", triage.get("recommended_tests") or []),
        bullets("O que não fazer", triage.get("dont_do") or []),
    ):
        if section is not None:
            items.append(section)

    console.print(Panel(Group(*items), title="Triagem guiada", border_style=color))


def freeze_frame_panel(ff: dict):
    if not isinstance(ff, dict):
        return
    pairs = [
        ("dtc_code",        "DTC congelado",        ""),
        ("rpm",             "RPM",                  "rpm"),
        ("speed_kmh",       "Velocidade",           "km/h"),
        ("coolant_temp_c",  "Temp. motor",          "°C"),
        ("engine_load_pct", "Carga do motor",       "%"),
        ("throttle_pct",    "Travão (throttle)",    "%"),
        ("maf_g_s",         "MAF",                  "g/s"),
        ("fuel_trim_short_b1","FT curto B1",        "%"),
        ("fuel_trim_long_b1","FT longo B1",         "%"),
        ("o2_b1s1_v",       "O2 B1S1",              "V"),
        ("intake_temp_c",   "Temp. admissão",       "°C"),
        ("mileage_km",      "Odômetro do frame",    "km"),
    ]
    t = Table(box=box.SIMPLE, show_header=True)
    t.add_column("Parâmetro", style="dim")
    t.add_column("Valor", justify="right")
    for key, label, unit in pairs:
        v = ff.get(key)
        if v in (None, ""):
            continue
        if isinstance(v, float):
            text = f"{v:.1f}"
        else:
            is_dtc = isinstance(v, str) and v.startswith(("P", "C", "B", "U"))
            text = (
                f"[bold]{escape(str(v))}[/]" if is_dtc else str(v)
            )
        t.add_row(label, f"{text} {unit}".strip())
    if t.row_count:
        section("❄ Freeze Frame")
        console.print(t)


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
        colors = {"critico": "red", "atencao": "yellow", "informativo": "green"}
        color = colors.get(s.get("urgency", ""), "white")
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
