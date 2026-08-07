from __future__ import annotations

from autodiag.core.cost_estimates import (
    _DEFAULT_RANGE,
    estimate_dtc_cost,
    estimate_session_costs,
    format_brl,
)


class TestFormatBrl:
    def test_zero(self):
        assert format_brl(0) == "R$ 0,00"

    def test_cem_reais(self):
        assert format_brl(10000) == "R$ 100,00"

    def test_milhar(self):
        assert format_brl(123456) == "R$ 1.234,56"

    def test_dez_mil(self):
        assert format_brl(1234567) == "R$ 12.345,67"


class TestEstimateDTCCost:
    def test_unknown_code_uses_default_range(self):
        mn, mx, desc, sev = estimate_dtc_cost("ZX999")
        default_min, default_max = _DEFAULT_RANGE
        assert mn >= int(default_min * 0.85)
        assert mx >= mn
        assert desc == ""
        assert sev == "informativo"

    def test_powertrain_p01_mistura_pobre(self):
        mn, mx, desc, sev = estimate_dtc_cost("P0171")
        assert mn > 0
        assert mx >= mn
        assert "mistura" in desc.lower() or "sistema" in desc.lower() or len(desc) > 0
        assert sev in {"critico", "atencao", "informativo"}

    def test_misfire_p0300_critico(self):
        mn, mx, desc, sev = estimate_dtc_cost("P0300")
        assert sev == "critico"
        # Valor mínimo do misfire (critico) tem que ser >= 20000 cents * 1.15
        assert mn >= int(20000 * 1.15) - 1

    def test_airbag_b_security(self):
        mn, mx, desc, sev = estimate_dtc_cost("B0001")
        # familia B0 -> minimo 30000 cents
        assert mn >= int(30000 * 0.90) - 1

    def test_transmissao_p07xx_critico(self):
        mn, mx, desc, sev = estimate_dtc_cost("P0731")
        assert sev == "critico"
        # familia P07: minimo 60k centavos
        assert mn >= 60000 - 1


class TestEstimateSessionCosts:
    def test_empty_list(self):
        mn, mx, items = estimate_session_costs([])
        assert mn == 0 and mx == 0 and items == []

    def test_single_code_has_returns_detail(self):
        mn, mx, items = estimate_session_costs(["P0300"])
        assert mn > 0
        assert mx >= mn
        assert len(items) == 1
        assert items[0]["code"] == "P0300"
        assert items[0]["severity"] == "critico"
        assert items[0]["min_cents"] > 0

    def test_duplicate_codes_collapsed(self):
        mn, mx, items = estimate_session_costs(["P0171", "P0171", "P0172"])
        assert len(items) == 2
        codes_found = sorted(i["code"] for i in items)
        assert codes_found == ["P0171", "P0172"]

    def test_total_is_sum_of_individual(self):
        codes = ["P0301", "P0302"]  # dois cilindros misfire
        mn_ind = estimate_session_costs([codes[0]])[0] + estimate_session_costs([codes[1]])[0]
        mn_total, _, items = estimate_session_costs(codes)
        assert mn_total == mn_ind
        assert len(items) == 2

    def test_mixed_families_sums(self):
        mn, mx, items = estimate_session_costs(["P0171", "B0001", "U0100"])
        assert len(items) == 3
        codes = sorted(i["code"] for i in items)
        assert set(codes) == {"P0171", "B0001", "U0100"}
        # Cada item tem faixa coerente
        for i in items:
            assert i["min_cents"] > 0
            assert i["max_cents"] >= i["min_cents"]
            assert i["severity"] in {"critico", "atencao", "informativo"}

    def test_invalid_codes_ignored(self):
        mn, mx, items = estimate_session_costs(["", "   ", None])  # type: ignore[list-item]
        assert mn == 0
        assert mx == 0
        assert items == []
