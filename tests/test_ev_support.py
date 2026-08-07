"""Testes de cobertura EV BR: detecção VIN por WMI + tabela de DIDs UDS $22."""

from __future__ import annotations

from autodiag.core.ev_support import (
    PROP_COMBUSTION,
    PROP_ELECTRIC,
    PROP_HYBRID,
    PROP_PLUGIN_HYBRID,
    detectar_propulsao_por_vin,
    hv_fields_for_brand,
)


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
