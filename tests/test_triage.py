from autodiag.core.triage import build_guided_triage
from autodiag.elm327.reader import DTCRecord, LivePIDs


def test_triage_clean_scan():
    triage = build_guided_triage([], LivePIDs(), "informativo")
    assert triage["headline"] == "Scan limpo"
    assert triage["drive_advice"] == "pode_rodar"


def test_triage_lean_misfire_pattern():
    dtcs = [DTCRecord("P0171"), DTCRecord("P0300")]
    pids = LivePIDs(fuel_trim_short_b1=22.0, fuel_trim_long_b1=14.0, maf_g_s=1.2)
    triage = build_guided_triage(dtcs, pids, "atencao")
    assert "Mistura pobre" in triage["headline"]
    assert triage["drive_advice"] == "cautela"
    assert any("Fuel trim curto" in o["label"] for o in triage["observations"])
    assert any("MAF" in o["label"] for o in triage["observations"])
    assert any("entrada falsa de ar" in c.lower() for c in triage["likely_causes"])


def test_triage_overheat_is_stop():
    triage = build_guided_triage([], LivePIDs(coolant_temp_c=112), "critico")
    assert triage["drive_advice"] == "pare"
    assert triage["headline"] == "Superaquecimento detectado"
    assert any("Não continuar rodando" in x for x in triage["dont_do"])

