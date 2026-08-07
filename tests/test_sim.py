"""Testes do adaptador simulado (modo demo) e da fábrica de readers."""
from autodiag.cli import _infer_urgency
from autodiag.core.vehicle import decode_vin_local
from autodiag.elm327 import SimulatedELM327, create_reader
from autodiag.elm327.reader import ELM327Reader
from autodiag.elm327.sim import SIM_VIN


class TestSimulatedELM327:
    def test_connect_always_succeeds(self):
        assert SimulatedELM327().connect() is True

    def test_vin_is_valid_and_decodes_locally(self):
        vin = SimulatedELM327().get_vin()
        assert vin == SIM_VIN
        assert len(vin) == 17
        profile = decode_vin_local(vin)
        assert profile.make == "Volkswagen Brasil"
        assert profile.year == 2019

    def test_reports_lean_mixture_scenario(self):
        sim = SimulatedELM327(seed=42)
        assert [d.code for d in sim.get_dtcs()] == ["P0171", "P0300"]
        pids = sim.get_live_pids()
        assert pids.fuel_trim_short_b1 > 15  # mistura pobre
        assert pids.maf_g_s < 2.0
        assert 0 < pids.o2_b1s1_v < 0.3

    def test_clear_dtcs_empties_list(self):
        sim = SimulatedELM327()
        assert sim.clear_dtcs() is True
        assert sim.get_dtcs() == []

    def test_seed_makes_pids_deterministic(self):
        a = SimulatedELM327(seed=7).get_live_pids()
        b = SimulatedELM327(seed=7).get_live_pids()
        assert a.as_dict() == b.as_dict()

    def test_context_manager(self):
        with SimulatedELM327() as sim:
            assert sim.get_vin() == SIM_VIN

    def test_demo_scenario_is_flagged_critical(self):
        sim = SimulatedELM327(seed=1)
        # P0300 (falha de ignição) está no conjunto crítico da heurística
        assert _infer_urgency(sim.get_dtcs(), sim.get_live_pids()) == "critico"


class TestCreateReader:
    def test_demo_returns_simulated(self):
        assert isinstance(create_reader(demo=True), SimulatedELM327)

    def test_default_returns_real_reader(self):
        assert isinstance(create_reader(port="COM3"), ELM327Reader)


class TestDemoClearedPersistence:
    def test_cleared_state_survives_new_instance(self, tmp_path, monkeypatch):
        """Regressão: 'apague os DTCs no demo e escaneie de novo' não
        funcionava — cada scan (web ou CLI) cria um simulador novo e o
        estado de limpeza morria com a instância."""
        from autodiag.elm327 import create_reader

        monkeypatch.setenv("AUTODIAG_HOME", str(tmp_path))
        first = create_reader(demo=True)
        assert first.get_dtcs()  # cenário padrão P0171/P0300
        first.clear_dtcs()

        second = create_reader(demo=True)  # nova instância = novo scan
        assert second.get_dtcs() == []
        status = second.get_monitor_status()
        assert len(status.incomplete_monitors) >= 2
        assert second.get_distance_since_clear() == 7

    def test_expired_marker_returns_to_default_scenario(self, tmp_path, monkeypatch):
        import json as _json
        import time as _time

        from autodiag.elm327 import create_reader

        monkeypatch.setenv("AUTODIAG_HOME", str(tmp_path))
        (tmp_path / "demo_state.json").write_text(
            _json.dumps({"cleared_at": _time.time() - 3600}), encoding="utf-8"
        )
        reader = create_reader(demo=True)
        assert len(reader.get_dtcs()) == 2

    def test_direct_instances_stay_hermetic(self, tmp_path, monkeypatch):
        """Testes que instanciam SimulatedELM327 direto não leem nem gravam
        estado em disco."""
        from autodiag.elm327.sim import SimulatedELM327

        monkeypatch.setenv("AUTODIAG_HOME", str(tmp_path))
        sim = SimulatedELM327(seed=1)
        sim.clear_dtcs()
        assert not (tmp_path / "demo_state.json").exists()
        assert SimulatedELM327(seed=1).get_dtcs()  # nova instância volta ao padrão
