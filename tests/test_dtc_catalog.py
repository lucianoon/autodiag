"""Testes do catálogo estendido de DTCs (core.dtc_catalog)."""
import re

from autodiag.core.dtc import DTC_DATABASE, full_database, lookup
from autodiag.core.dtc_catalog import build_catalog, catalog_size

_VALID_SEVERITIES = {"critico", "atencao", "informativo"}
_CODE_RE = re.compile(r"^[PCBU]\d{4}$")


def test_catalog_has_hundreds_of_codes():
    assert catalog_size() >= 500


def test_full_database_merges_catalog_and_curated():
    full = full_database()
    assert len(full) >= catalog_size()
    for code in DTC_DATABASE:
        assert code in full


def test_curated_database_takes_precedence():
    # P0171 existe nos dois; a versão curada tem causas específicas.
    info = full_database()["P0171"]
    assert "Sensor MAF sujo" in info.causes
    assert lookup("p0171").causes == info.causes


def test_all_generated_codes_are_wellformed():
    for code, info in build_catalog().items():
        assert _CODE_RE.match(code), code
        assert info.code == code
        assert info.description
        assert info.severity in _VALID_SEVERITIES, code
        assert info.system
        assert info.causes, code


def test_numbering_is_decimal_not_hex():
    # P0309 + 1 deve gerar P0310 (cilindro 10), nunca P030A.
    cat = build_catalog()
    assert "P0310" in cat
    assert "P030A" not in cat
    assert "cilindro 10" in cat["P0310"].description


def test_per_cylinder_families_cover_12_cylinders():
    cat = build_catalog()
    assert "falha de ignição" in cat["P0312"].description.lower()
    assert "Injetor do cilindro 12" in cat["P0212"].description
    assert "cilindro 12" in cat["P0296"].description.lower()


def test_o2_sensor_sextets_cover_both_banks():
    cat = build_catalog()
    assert "B1S1" in cat["P0130"].description
    assert "B2S3" in cat["P0165"].description
    assert "resposta lenta" in cat["P0165"].description


def test_network_codes_carry_module_and_severity():
    cat = build_catalog()
    assert "airbag" in cat["U0151"].description.lower()
    assert cat["U0151"].severity == "critico"
    assert cat["U0164"].severity == "informativo"


def test_lookup_falls_back_to_catalog():
    info = lookup("p2135")
    assert info is not None
    assert "borboleta" in info.description.lower()


def test_misfires_are_critical():
    cat = build_catalog()
    for cyl in range(1, 13):
        assert cat[f"P{301 + cyl - 1:04d}"].severity == "critico"
