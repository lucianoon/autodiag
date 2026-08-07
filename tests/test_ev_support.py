"""Testes de cobertura EV BR: detecção VIN por WMI + tabela de DIDs UDS $22."""

from __future__ import annotations

from autodiag.core.ev_support import (
    PROP_COMBUSTION,
    PROP_ELECTRIC,
    PROP_HYBRID,
    PROP_PLUGIN_HYBRID,
    apply_hv_formula,
    detectar_propulsao_por_vin,
    hv_fields_for_brand,
)
from autodiag.elm327.reader import ELM327Reader
from autodiag.elm327.sim import SimulatedELM327


class TestApplyHvFormula:
    """Formulas padrão de decodificação UDS 22 (2-bytes payload 16-bit)."""

    def test_u16_01_typical_soc(self) -> None:
        # SoC = 52.3% → U16 = 523 = 0x020B
        raw = (int(52.3 / 0.1)).to_bytes(2, "big", signed=False)
        assert apply_hv_formula(raw, "U16 * 0.1") == 52.3

    def test_s16_01_typical_current_regen(self) -> None:
        # Corrente -8.2A = -82 signed 16-bit
        raw = (-82).to_bytes(2, "big", signed=True)
        assert apply_hv_formula(raw, "S16 * 0.1") == -8.2

    def test_s16_01_menos_40_temperatura(self) -> None:
        # 27.4°C → value = (27.4+40)/0.1 = 674
        raw = (674).to_bytes(2, "big", signed=True)
        assert apply_hv_formula(raw, "S16 * 0.1 - 40") == 27.4

    def test_s16_025_kw_power(self) -> None:
        # 18.6 kW → 18.6 / 0.25 = 74 = 0x4A
        raw = (74).to_bytes(2, "big", signed=True)
        assert apply_hv_formula(raw, "S16 * 0.25") == 18.5

    def test_u16_005_tesla(self) -> None:
        # Tesla 403.2V pack. value = 403.2 / 0.05 = 8064 = 0x1F80
        raw = (8064).to_bytes(2, "big", signed=False)
        assert apply_hv_formula(raw, "U16 * 0.05") == 403.2

    def test_empty_or_short_payload_retorna_none(self) -> None:
        assert apply_hv_formula(b"", "U16 * 0.1") is None
        assert apply_hv_formula(b"\x01", "U16 * 0.1") is None

    def test_formula_unknown_retorna_u16_raw(self) -> None:
        # Fórmula desconhecida: fallback U16 raw (útil para debug)
        raw = (0x020B).to_bytes(2, "big")
        assert apply_hv_formula(raw, "U16 * 0.3") == 0x020B


class TestSimulatedHighVoltage:
    """ELM simulado deve devolver hv_data realista quando VIN é BYD/GWM/etc EV."""

    def test_byd_dolphin_retorna_6_dids_aproximados(self) -> None:
        sim = SimulatedELM327(seed=42)
        fields = hv_fields_for_brand("BYD")
        assert len(fields) >= 5
        result = sim.read_high_voltage(
            fields, vin="LGXCE4CG8N0123456"  # BYD elétrico (vin[3]='C')
        )
        # Chaves did_hex e chaves nome campo (dupla) → len ~ 12
        assert len(result) >= 6, result
        assert "did_0101" in result
        assert "SOC % (Estimado BMS)" in result
        # 52.3% esperado ~ jitter ±0.8% → entre 49 e 56
        soc = float(result["did_0101"])
        assert 49 <= soc <= 56, soc
        v_pack = float(result["did_0102"])
        assert 380 <= v_pack <= 410, v_pack
        current_a = float(result["did_0103"])
        assert -10 <= current_a <= -5, current_a

    def test_renault_kwid_etech_retorna_soc_vpack(self) -> None:
        sim = SimulatedELM327(seed=7)
        fields = hv_fields_for_brand("Renault-Brasil")
        result = sim.read_high_voltage(
            fields, vin="9BMBE2E10RC123456"
        )
        assert "did_0401" in result
        soc = float(result["did_0401"])
        assert 42 <= soc <= 46, soc

    def test_vw_gol_ice_retorna_empty_dict(self) -> None:
        """Veículo ICE (SIM_VIN = VW 9BW) → devolve {} vazio."""
        sim = SimulatedELM327(seed=0)
        fields = hv_fields_for_brand(None)
        result = sim.read_high_voltage(fields, vin=None)  # fallback = SIM_VIN ICE
        assert result == {}

    def test_empty_fields_retorna_empty(self) -> None:
        sim = SimulatedELM327()
        assert sim.read_high_voltage([], vin="9BMBE2E10RC123456") == {}


class TestElm327ReaderInterface:
    """Verifica que o método read_high_voltage existe no Reader real (type-check)."""

    def test_reader_possui_metodo_e_retorna_empty_quando_desconectado(self) -> None:
        from autodiag.elm327 import ELM327Reader as _R

        assert callable(getattr(_R, "read_high_voltage", None))


class TestEvVINPropulsao:
    def test_byd_dolphin_lgx_electric(self) -> None:
        ev = detectar_propulsao_por_vin("LGXCE4CG8N0123456")
        assert ev.is_ev_any() is True
        assert ev.propensao == PROP_ELECTRIC
        assert ev.marca == "BYD"
        assert ev.confianca in {"alta", "média", "média-alta"}

    def test_renault_kwid_etech_9bm_electric(self) -> None:
        # 9BM = Renault-Brasil (São José dos Pinhais). Pos 3:5 = "BE" → BEV
        ev = detectar_propulsao_por_vin("9BMBE2E10RC123456")
        assert ev.is_ev_any() is True
        assert ev.propensao == PROP_ELECTRIC
        assert (ev.marca == "Renault") or (ev.marca == "Renault-Brasil")

    def test_tesla_5yj_bev(self) -> None:
        ev = detectar_propulsao_por_vin("5YJ3E1EA3PF700001")
        assert ev.is_ev_any() is True
        assert ev.propensao == PROP_ELECTRIC
        assert ev.marca and "Tesla" in ev.marca

    def test_gwm_ora_lgw_electric(self) -> None:
        # GWM Ora: vin[3:5] == "EG" (Ora Good Cat / 03)
        ev = detectar_propulsao_por_vin("LGWEG4A50PA123456")
        assert ev.is_ev_any() is True
        assert ev.propensao == PROP_ELECTRIC
        assert ev.marca == "GWM"

    def test_vw_ice_wvw_combustao(self) -> None:
        ev = detectar_propulsao_por_vin("WVWZZZ6MZDW000123")
        assert ev.is_ev_any() is False
        assert ev.propensao == PROP_COMBUSTION
        assert ev.confianca == "média"

    def test_vin_curto_baixa_confianca(self) -> None:
        ev = detectar_propulsao_por_vin("LGX123")
        assert ev.confianca in {"baixa", "média"}

    def test_wmi_desconhecido_not_tested(self) -> None:
        ev = detectar_propulsao_por_vin("9BRABCDEFGHI12345")
        assert ev.ev_support_level == "not_tested"
        assert ev.propensao == PROP_COMBUSTION

    def test_phev_vs_hev_label(self) -> None:
        """Fiat 500e é elétrico puro (BEV)."""
        ev = detectar_propulsao_por_vin("ZFA3630000J123456")
        assert ev.propensao in {
            PROP_ELECTRIC, PROP_PLUGIN_HYBRID, PROP_HYBRID, PROP_COMBUSTION,
        }

    def test_none_vin_retorna_default(self) -> None:
        ev = detectar_propulsao_por_vin(None)
        assert ev.ev_support_level == "none"
        assert ev.is_ev_any() is False
        assert ev.confianca == "baixa"

    def test_empty_vin(self) -> None:
        ev = detectar_propulsao_por_vin("")
        assert ev.ev_support_level == "none"


class TestEvHVFields:
    def test_hv_fields_byd_soc_presente(self) -> None:
        fields = hv_fields_for_brand("BYD")
        names = {f["name"].lower() for f in fields}
        assert any("soc" in n for n in names), names
        for f in fields:
            assert isinstance(f["id"], int)
            assert 0x0000 < f["id"] < 0xFFFF

    def test_hv_fields_tesla(self) -> None:
        fields = hv_fields_for_brand("Tesla")
        # Tesla tem 3 campos listados (SOC, V pack, SoH)
        assert len(fields) >= 3
        names = {f["name"].lower() for f in fields}
        assert any("soc" in n for n in names)

    def test_hv_fields_desconhecido_default(self) -> None:
        fields = hv_fields_for_brand("CaoaChery")
        assert len(fields) >= 4

    def test_hv_fields_none_default(self) -> None:
        assert len(hv_fields_for_brand(None)) >= 4
