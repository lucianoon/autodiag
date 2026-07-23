"""Testes da heurística de urgência (autodiag.cli._infer_urgency)."""
from autodiag.cli import _infer_urgency
from autodiag.elm327.reader import DTCRecord, LivePIDs


def _dtcs(*codes: str) -> list[DTCRecord]:
    return [DTCRecord(code=c) for c in codes]


def test_no_data_is_informative():
    assert _infer_urgency([], LivePIDs()) == "informativo"


def test_critical_dtc():
    assert _infer_urgency(_dtcs("P0300"), LivePIDs()) == "critico"


def test_critical_dtc_wins_over_attention():
    assert _infer_urgency(_dtcs("P0171", "U0100"), LivePIDs()) == "critico"


def test_overheating_is_critical_even_without_dtcs():
    assert _infer_urgency([], LivePIDs(coolant_temp_c=115)) == "critico"


def test_normal_temperature_is_not_critical():
    assert _infer_urgency([], LivePIDs(coolant_temp_c=90)) == "informativo"


def test_attention_dtc():
    assert _infer_urgency(_dtcs("P0420"), LivePIDs()) == "atencao"


def test_high_short_fuel_trim_is_attention():
    assert _infer_urgency([], LivePIDs(fuel_trim_short_b1=18.0)) == "atencao"


def test_negative_fuel_trim_uses_absolute_value():
    assert _infer_urgency([], LivePIDs(fuel_trim_short_b1=-20.0)) == "atencao"


def test_low_maf_is_attention():
    assert _infer_urgency([], LivePIDs(maf_g_s=1.5)) == "atencao"


def test_unknown_dtc_still_raises_attention():
    assert _infer_urgency(_dtcs("P1234"), LivePIDs()) == "atencao"
