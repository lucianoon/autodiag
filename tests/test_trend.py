"""Testes do módulo autodiag.core.trend — tendências, outliers e recorrência de DTCs."""
from autodiag.core.trend import build_vehicle_trends, compute_param_trend


def _sessions(values_by_key, dtc_lists, *, vin="9BWAB47X0LP123456"):
    """Gera lista de sessões dummies com valores por chave e listas de DTCs por scan."""
    n = max(
        max(len(v) for v in values_by_key.values()) if values_by_key else 0,
        len(dtc_lists),
    )
    out = []
    for i in range(n):
        row = {"id": n - i, "vin": vin, "vehicle_label": "VW",
               "ts": f"0{i+1}/07/2026 10:00", "dtc_codes": dtc_lists[i] or [],
               "urgency": "informativo"}
        for k, vals in values_by_key.items():
            row[k] = vals[i] if i < len(vals) else None
        out.append(row)
    return list(reversed(out))


def test_compute_param_trend_flat_within_bounds():
    series = [90, 91, 89, 92, 90, 91]
    t = compute_param_trend("coolant_temp", series)
    assert t.first == 90
    assert t.last == 91
    assert t.avg is not None
    assert abs(t.avg - 90.5) < 0.2
    assert t.direction == "flat"
    assert not any(a["level"] == "danger" for a in t.alerts)


def test_compute_param_trend_rising_coolant_over_threshold():
    series = [85, 88, 94, 100, 108]
    t = compute_param_trend("coolant_temp", series)
    assert t.direction == "up"
    assert t.pct_change is not None and t.pct_change > 0
    assert any(a["kind"] == "above_high" for a in t.alerts)


def test_compute_param_trend_fuel_trim_sym_deviation():
    series = [1.0, 2.0, 4.2, -18.5]
    t = compute_param_trend("fuel_trim_long", series)
    assert any(a["kind"] == "sym_deviation" and a["level"] == "danger"
               for a in t.alerts)


def test_compute_param_trend_outlier_triggers_z_alert():
    steady = [3.0, 3.1, 2.9, 3.05, 3.0, 3.1, 2.95, 3.0, 3.0, 11.7]
    t = compute_param_trend("maf", steady)
    kinds = {a["kind"] for a in t.alerts}
    assert "outlier_2s" in kinds or "outlier_25s" in kinds


def test_compute_param_trend_empty_and_null_stays_safe():
    assert compute_param_trend("rpm", []).last is None
    t = compute_param_trend("rpm", [None, None, "banana"])
    assert t.last is None
    assert t.avg is None
    assert t.alerts == []


def test_build_vehicle_trends_aggregates_dtcs_and_params():
    sessions = _sessions(
        values_by_key={
            "coolant_temp": [85, 86, 95, 102, 99],
            "maf":          [3.0, 3.1, 2.9, 3.0, 3.0],
            "fuel_trim_short": [1.0, 1.5, -2.0, 0.5, 1.2],
        },
        dtc_lists=[
            ["P0171"],
            ["P0171", "P0300"],
            [],
            ["P0171"],
            [],
        ],
    )
    res = build_vehicle_trends(sessions)
    assert "params" in res
    assert res["params"]["coolant_temp"]["direction"] == "up"
    assert res["params"]["coolant_temp"]["last"] == 99
    codes = {r["code"]: r["count"] for r in res["recurring_dtcs"]}
    assert codes["P0171"] == 3
    assert "P0300" not in codes


def test_build_vehicle_trends_empty_returns_safe_structure():
    res = build_vehicle_trends([])
    assert res["params"] == {}
    assert res["recurring_dtcs"] == []
    assert res["dtc_frequency"] == {}


def test_build_vehicle_trends_ignores_single_dtcs_for_recurring():
    sessions = _sessions(
        values_by_key={},
        dtc_lists=[["A"], ["B"], ["C"]],
    )
    res = build_vehicle_trends(sessions)
    assert res["recurring_dtcs"] == []
    assert res["dtc_frequency"] == {"A": 1, "B": 1, "C": 1}
