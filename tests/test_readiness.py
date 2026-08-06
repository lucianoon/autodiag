"""Testes de prontidão dos monitores e detecção de limpeza recente de DTCs."""
from autodiag.core.readiness import (
    VERDICT_INCONCLUSIVO,
    VERDICT_NORMAL,
    VERDICT_SUSPEITO,
    assess_recent_clear,
    build_readiness_summary,
)
from autodiag.elm327.reader import MonitorStatus
from autodiag.elm327.sim import SimulatedELM327


def _status(monitors: dict[str, bool] | None, dtc_count: int = 0) -> MonitorStatus:
    return MonitorStatus(mil_on=dtc_count > 0, dtc_count=dtc_count, monitors=monitors)


class TestAssessRecentClear:
    def test_no_monitor_data_is_inconclusive(self):
        result = assess_recent_clear(_status(None))
        assert result.verdict == VERDICT_INCONCLUSIVO

    def test_all_complete_no_dtcs_is_normal(self):
        result = assess_recent_clear(
            _status({"Catalisador": True, "Sistema EVAP": True, "Sonda lambda": True})
        )
        assert result.verdict == VERDICT_NORMAL
        assert result.confidence == "alta"

    def test_zero_dtcs_incomplete_monitors_low_distance_is_high_confidence_suspicion(self):
        result = assess_recent_clear(
            _status({"Catalisador": False, "Sistema EVAP": False, "Sonda lambda": True}),
            distance_since_clear_km=7,
        )
        assert result.verdict == VERDICT_SUSPEITO
        assert result.confidence == "alta"
        assert any("7 km" in e for e in result.evidence)

    def test_low_warmups_also_triggers_strong_signal(self):
        result = assess_recent_clear(
            _status({"Catalisador": False, "Sistema EVAP": False}),
            warmups_since_clear=2,
        )
        assert result.verdict == VERDICT_SUSPEITO
        assert result.confidence == "alta"

    def test_zero_dtcs_incomplete_monitors_without_counters_is_medium_suspicion(self):
        result = assess_recent_clear(
            _status({"Catalisador": False, "Sistema EVAP": False, "Sonda lambda": True})
        )
        assert result.verdict == VERDICT_SUSPEITO
        assert result.confidence == "media"

    def test_single_incomplete_monitor_is_not_suspicious(self):
        result = assess_recent_clear(
            _status({"Catalisador": False, "Sistema EVAP": True, "Sonda lambda": True})
        )
        assert result.verdict == VERDICT_NORMAL

    def test_dtcs_present_with_incomplete_monitors_is_normal(self):
        # As falhas já retornaram após a limpeza: não é quadro de ocultação.
        result = assess_recent_clear(
            _status({"Catalisador": False, "Sistema EVAP": False}, dtc_count=2),
            distance_since_clear_km=30,
        )
        assert result.verdict == VERDICT_NORMAL

    def test_high_mileage_since_clear_is_not_strong_signal(self):
        result = assess_recent_clear(
            _status({"Catalisador": False, "Sistema EVAP": False}),
            distance_since_clear_km=850,
            warmups_since_clear=60,
        )
        assert result.verdict == VERDICT_SUSPEITO
        assert result.confidence == "media"


class TestBuildReadinessSummary:
    def test_summary_is_json_serializable_structure(self):
        status = MonitorStatus(
            mil_on=False,
            dtc_count=0,
            ignition="spark",
            monitors={"Catalisador": False, "Sistema EVAP": False},
        )
        summary = build_readiness_summary(status, warmups_since_clear=2, distance_since_clear_km=7)
        assert summary["ignition"] == "spark"
        assert summary["incomplete"] == ["Catalisador", "Sistema EVAP"]
        assert summary["distance_since_clear_km"] == 7
        assert summary["clear_assessment"]["verdict"] == VERDICT_SUSPEITO

    def test_summary_omits_absent_counters(self):
        summary = build_readiness_summary(_status({"Catalisador": True}))
        assert "warmups_since_clear" not in summary
        assert "distance_since_clear_km" not in summary


class TestSimulatorTamperScenario:
    def test_fresh_sim_has_complete_monitors_and_history(self):
        sim = SimulatedELM327(seed=1)
        status = sim.get_monitor_status()
        assert status.monitors
        assert not status.incomplete_monitors
        assert sim.get_distance_since_clear() > 100

    def test_clearing_dtcs_in_demo_produces_suspicious_scan(self):
        sim = SimulatedELM327(seed=1)
        sim.clear_dtcs()
        status = sim.get_monitor_status()
        summary = build_readiness_summary(
            status,
            warmups_since_clear=sim.get_warmups_since_clear(),
            distance_since_clear_km=sim.get_distance_since_clear(),
        )
        assert status.dtc_count == 0
        assert len(status.incomplete_monitors) >= 2
        assert summary["clear_assessment"]["verdict"] == VERDICT_SUSPEITO
        assert summary["clear_assessment"]["confidence"] == "alta"
