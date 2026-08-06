"""Testes do parecer padronizado de vistoria (core.inspection)."""
from autodiag.core.inspection import (
    APROVADO,
    APROVADO_COM_RESSALVAS,
    REINSPECIONAR,
    REPROVADO,
    build_inspection_verdict,
)
from autodiag.core.report import build_report, render_report_html


def _session(**overrides) -> dict:
    base: dict = {
        "id": 1,
        "ts": "06/08/2026 10:00",
        "vin": "9BWAB45U0KP042788",
        "vehicle_label": "VW Gol 2019",
        "dtc_codes": [],
        "urgency": "informativo",
        "diagnosis": "",
        "triage": None,
        "cost_min": 0,
        "cost_max": 0,
        "km": 68000,
        "notes": "",
        "tags": None,
        "freeze_frame": None,
        "readiness": None,
        "rpm": 850,
        "speed": 0,
        "coolant_temp": 92,
        "maf": 1.8,
        "fuel_trim_short": 2.0,
        "fuel_trim_long": 1.0,
        "o2": 0.45,
    }
    base.update(overrides)
    return base


def _readiness(verdict: str, confidence: str = "alta", incomplete: list[str] | None = None):
    return {
        "monitors": {},
        "incomplete": incomplete or [],
        "clear_assessment": {
            "verdict": verdict,
            "confidence": confidence,
            "evidence": ["evidência de teste"],
            "recommendation": "",
        },
    }


class TestVerdictRules:
    def test_clean_vehicle_is_approved(self):
        v = build_inspection_verdict(_session(readiness=_readiness("normal")))
        assert v.verdict == APROVADO

    def test_critical_urgency_fails(self):
        v = build_inspection_verdict(
            _session(dtc_codes=["P0300"], urgency="critico", readiness=_readiness("normal"))
        )
        assert v.verdict == REPROVADO
        assert any("P0300" in r for r in v.reasons)

    def test_suspected_clear_requires_reinspection(self):
        v = build_inspection_verdict(
            _session(readiness=_readiness("suspeito", confidence="alta"))
        )
        assert v.verdict == REINSPECIONAR
        assert "100+ km" in v.recommendation

    def test_critical_beats_suspected_clear(self):
        v = build_inspection_verdict(
            _session(dtc_codes=["U0100"], urgency="critico", readiness=_readiness("suspeito"))
        )
        assert v.verdict == REPROVADO

    def test_dtcs_with_attention_urgency_pass_with_caveats(self):
        v = build_inspection_verdict(
            _session(dtc_codes=["P0171"], urgency="atencao", readiness=_readiness("normal"))
        )
        assert v.verdict == APROVADO_COM_RESSALVAS
        assert any("P0171" in r for r in v.reasons)

    def test_missing_readiness_does_not_break(self):
        v = build_inspection_verdict(_session(readiness=None))
        assert v.verdict == APROVADO

    def test_as_dict_shape(self):
        d = build_inspection_verdict(_session()).as_dict()
        assert set(d) == {"verdict", "label", "reasons", "recommendation"}


class TestReportIntegration:
    def test_report_shows_verdict_banner(self):
        row = _session(readiness=_readiness("suspeito"))
        html = render_report_html(build_report(row, None))
        assert "Parecer de vistoria" in html
        assert "Reinspeção necessária" in html

    def test_report_shows_approval_for_clean_vehicle(self):
        html = render_report_html(build_report(_session(readiness=_readiness("normal")), None))
        assert "Parecer de vistoria: Aprovado" in html
