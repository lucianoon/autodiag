from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

PARAM_THRESHOLDS: dict[str, dict[str, Any]] = {
    "coolant_temp": {
        "label": "Temp. motor", "unit": "°C",
        "hi": 105, "lo": 70, "mode": "high_bad",
    },
    "rpm": {
        "label": "RPM", "unit": "rpm",
        "hi": None, "lo": 600, "mode": "neutral",
    },
    "maf": {
        "label": "MAF", "unit": "g/s",
        "hi": None, "lo": 2.0, "mode": "neutral",
    },
    "fuel_trim_short": {
        "label": "Fuel trim curto B1", "unit": "%",
        "hi": 15, "lo": None, "mode": "sym_bad",
    },
    "fuel_trim_long": {
        "label": "Fuel trim longo B1", "unit": "%",
        "hi": 10, "lo": None, "mode": "sym_bad",
    },
    "o2": {
        "label": "O2 B1S1", "unit": "V",
        "hi": 0.9, "lo": 0.1, "mode": "range_good",
    },
    "speed": {
        "label": "Velocidade", "unit": "km/h",
        "hi": None, "lo": None, "mode": "neutral",
    },
}


@dataclass
class ParamTrend:
    key: str
    label: str
    unit: str
    values: list[float] = field(default_factory=list)
    first: float | None = None
    last: float | None = None
    avg: float | None = None
    stdev: float | None = None
    slope: float = 0.0
    delta: float = 0.0
    pct_change: float | None = None
    direction: str = "flat"
    alerts: list[dict[str, Any]] = field(default_factory=list)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _stdev(values: list[float], mean: float) -> float | None:
    n = len(values)
    if n < 2:
        return None
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(variance)


def _slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    return num / den if den else 0.0


def _threshold_alerts(
    value: float | None,
    key: str,
) -> list[dict[str, Any]]:
    if value is None:
        return []
    meta = PARAM_THRESHOLDS.get(key)
    if not meta:
        return []
    alerts: list[dict[str, Any]] = []
    hi, lo, mode = meta["hi"], meta["lo"], meta["mode"]
    if mode == "high_bad":
        if hi is not None and value > hi:
            alerts.append({"level": "danger", "kind": "above_high",
                           "message": f"{value:.1f} acima do limite ({hi}{meta['unit']})"})
        elif lo is not None and value < lo:
            alerts.append({"level": "warning", "kind": "below_low",
                           "message": f"{value:.1f} abaixo do esperado ({lo}{meta['unit']})"})
    elif mode == "sym_bad":
        if hi is not None and abs(value) > hi:
            alerts.append({"level": "danger", "kind": "sym_deviation",
                           "message": f"Desvio de {value:+.1f}{meta['unit']} (limite ±{hi})"})
        elif hi is not None and abs(value) > hi * 0.6:
            alerts.append({"level": "warning", "kind": "sym_trending",
                           "message": f"Desvio significativo: {value:+.1f}{meta['unit']}"})
    elif mode == "range_good":
        if hi is not None and value > hi:
            alerts.append({"level": "warning", "kind": "above_high",
                           "message": f"{value:.2f}{meta['unit']} — sinal acima do esperado"})
        elif lo is not None and value < lo:
            alerts.append({"level": "warning", "kind": "below_low",
                           "message": f"{value:.2f}{meta['unit']} — sinal abaixo do esperado"})
    return alerts


def _outlier_alerts(
    values: list[float],
    last: float | None,
    avg: float | None,
    stdev: float | None,
) -> list[dict[str, Any]]:
    if last is None or avg is None or stdev is None or stdev == 0:
        return []
    z = (last - avg) / stdev
    if abs(z) >= 2.5:
        return [{
            "level": "danger",
            "kind": "outlier_25s",
            "message": f"Valor atual é desvio de {z:+.1f}σ da média (outlier severo)",
        }]
    if abs(z) >= 2.0:
        return [{
            "level": "warning",
            "kind": "outlier_2s",
            "message": f"Valor atual é desvio de {z:+.1f}σ da média",
        }]
    return []


def _direction(delta: float, pct_change: float | None, slope: float) -> str:
    if pct_change is None:
        return "flat"
    if abs(pct_change) >= 5 or abs(slope) > 0.5:
        return "up" if (delta > 0 or slope > 0) else "down"
    return "flat"


def compute_param_trend(key: str, raw_values: list[Any]) -> ParamTrend:
    meta = PARAM_THRESHOLDS.get(key) or {"label": key, "unit": "", "mode": "neutral"}
    nums: list[float] = []
    for v in raw_values:
        try:
            if v is None:
                continue
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    trend = ParamTrend(key=key, label=meta["label"], unit=meta["unit"], values=list(nums))
    if not nums:
        return trend
    trend.first = nums[0]
    trend.last = nums[-1]
    trend.avg = _mean(nums)
    trend.stdev = _stdev(nums, trend.avg) if trend.avg is not None else None
    trend.slope = _slope(nums)
    trend.delta = trend.last - trend.first
    trend.pct_change = None if trend.first == 0 else (trend.delta / abs(trend.first)) * 100
    trend.direction = _direction(trend.delta, trend.pct_change, trend.slope)
    trend.alerts.extend(_threshold_alerts(trend.last, key))
    trend.alerts.extend(_outlier_alerts(nums, trend.last, trend.avg, trend.stdev))
    return trend


def build_vehicle_trends(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    if not sessions:
        return {"params": {}, "recurring_dtcs": [], "dtc_frequency": {}}
    ordered = list(reversed(sessions))
    params: dict[str, Any] = {}
    for key in PARAM_THRESHOLDS:
        raw = [s.get(key) for s in ordered]
        t = compute_param_trend(key, raw)
        params[key] = {
            "label": t.label,
            "unit": t.unit,
            "first": t.first,
            "last": t.last,
            "avg": round(t.avg, 2) if t.avg is not None else None,
            "stdev": round(t.stdev, 3) if t.stdev is not None else None,
            "slope": round(t.slope, 3),
            "delta": round(t.delta, 2),
            "pct_change": round(t.pct_change, 1) if t.pct_change is not None else None,
            "direction": t.direction,
            "alerts": t.alerts,
            "series": t.values,
        }
    dtc_freq: dict[str, int] = {}
    for s in sessions:
        for code in s.get("dtc_codes") or []:
            dtc_freq[code] = dtc_freq.get(code, 0) + 1
    recurring = [
        {"code": code, "count": count}
        for code, count in sorted(dtc_freq.items(), key=lambda x: -x[1])
        if count >= 2
    ]
    return {"params": params, "recurring_dtcs": recurring, "dtc_frequency": dtc_freq}
