from __future__ import annotations

from autodiag.core.dtc import lookup

_FAMILY_RANGES: dict[str, tuple[int, int]] = {
    "P00": (10000, 120000),
    "P01": (15000, 120000),
    "P02": (18000, 180000),
    "P03": (20000, 150000),
    "P04": (15000, 250000),
    "P05": (25000, 180000),
    "P06": (25000, 180000),
    "P07": (60000, 350000),
    "P08": (80000, 400000),
    "P09": (20000, 180000),
    "B0": (30000, 180000),
    "B1": (8000, 80000),
    "C0": (20000, 120000),
    "C1": (12000, 100000),
    "U0": (25000, 220000),
    "U1": (20000, 180000),
}
_DEFAULT_RANGE = (15000, 150000)

_SEVERITY_MULT: dict[str, tuple[float, float]] = {
    "critico": (1.15, 1.25),
    "atencao": (1.00, 1.05),
    "informativo": (0.90, 0.85),
}
_DEFAULT_SEV_MULT = (1.0, 1.0)


def _family(code: str) -> str:
    c = code.strip().upper()
    if len(c) < 3:
        return c[:2] if c else ""
    if c[0] in "PUBC":
        if c[1].isdigit() and c[2].isdigit():
            return c[:3] if c[0] == "P" else c[:2]
    return c[:2]


def estimate_dtc_cost(code: str) -> tuple[int, int, str, str]:
    """Estima faixa de custo para um único DTC.

    Retorna (min_cents, max_cents, description, severity_label).
    Valores em centavos de Real (1 unidade = R$ 0,01).
    """
    norm = code.strip().upper()
    fam = _family(norm)
    info = lookup(norm)
    if info is not None:
        desc = info.description
        severity = info.severity
    else:
        desc = ""
        severity = "informativo"
    base_min, base_max = _FAMILY_RANGES.get(fam, _DEFAULT_RANGE)
    sm_min, sm_max = _SEVERITY_MULT.get(severity, _DEFAULT_SEV_MULT)
    min_c = int(round(base_min * sm_min))
    max_c = int(round(base_max * sm_max))
    if max_c < min_c:
        max_c = min_c
    return min_c, max_c, desc, severity


def estimate_session_costs(
    codes: list[str],
) -> tuple[int, int, list[dict]]:
    """Estima faixa total para uma lista de DTCs.

    Retorna (total_min_cents, total_max_cents, detalhes).
    detalhes = [{code, description, min_cents, max_cents, severity].
    """
    if not codes:
        return 0, 0, []
    seen: set[str] = set()
    items: list[dict] = []
    total_min = 0
    total_max = 0
    for raw in codes:
        code = (raw or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        mn, mx, desc, sev = estimate_dtc_cost(code)
        total_min += mn
        total_max += mx
        items.append(
            {
                "code": code,
                "description": desc,
                "min_cents": mn,
                "max_cents": mx,
                "severity": sev,
            }
        )
    return total_min, total_max, items


def format_brl(cents: int) -> str:
    value = float(cents) / 100.0
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"
