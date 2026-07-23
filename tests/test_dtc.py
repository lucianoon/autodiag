"""Testes da base local de DTCs (autodiag.core.dtc)."""
from autodiag.core.dtc import DTC_DATABASE, DTCInfo, lookup, severity_color


class TestLookup:
    def test_known_code(self):
        info = lookup("P0171")
        assert info is not None
        assert info.code == "P0171"
        assert info.severity == "atencao"
        assert info.system == "Motor/Emissões"
        assert len(info.causes) > 0

    def test_lookup_is_case_insensitive(self):
        assert lookup("p0300") == lookup("P0300")

    def test_lookup_strips_whitespace(self):
        assert lookup("  P0420  ") == lookup("P0420")

    def test_unknown_code_returns_none(self):
        assert lookup("P9999") is None

    def test_empty_string_returns_none(self):
        assert lookup("") is None


class TestDatabaseConsistency:
    def test_keys_match_code_field(self):
        for key, info in DTC_DATABASE.items():
            assert key == info.code

    def test_severities_are_valid(self):
        valid = {"critico", "atencao", "informativo"}
        for info in DTC_DATABASE.values():
            assert info.severity in valid, info.code

    def test_all_entries_have_description_and_system(self):
        for info in DTC_DATABASE.values():
            assert info.description
            assert info.system

    def test_codes_follow_obd2_format(self):
        for code in DTC_DATABASE:
            assert code[0] in "PCBU"
            assert len(code) == 5
            assert all(c in "0123456789ABCDEF" for c in code[1:])


class TestSeverityColor:
    def test_known_severities(self):
        assert severity_color("critico") == "red"
        assert severity_color("atencao") == "yellow"
        assert severity_color("informativo") == "cyan"

    def test_unknown_severity_defaults_to_white(self):
        assert severity_color("qualquer") == "white"


def test_dtcinfo_defaults():
    info = DTCInfo("P0000", "teste", "informativo", "Motor")
    assert info.causes == []
