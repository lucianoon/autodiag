"""Testes da decodificação ELM327 (autodiag.elm327.reader) — sem hardware."""
from autodiag.elm327.reader import ELM327Reader, LivePIDs, _decode_dtcs


class TestDecodeDtcs:
    def test_single_powertrain_code(self):
        dtcs = _decode_dtcs("43 01 71 00 00")
        assert [d.code for d in dtcs] == ["P0171"]

    def test_multiple_codes(self):
        dtcs = _decode_dtcs("4301710300")
        assert [d.code for d in dtcs] == ["P0171", "P0300"]

    def test_padding_zeros_are_ignored(self):
        assert _decode_dtcs("43 00 00 00 00 00 00") == []

    def test_empty_response(self):
        assert _decode_dtcs("") == []

    def test_chassis_code(self):
        # Primeiro nibble 0x4 => C0 (SAE J2012)
        dtcs = _decode_dtcs("43 40 31")
        assert [d.code for d in dtcs] == ["C0031"]

    def test_body_code(self):
        # Primeiro nibble 0x8 => B0
        dtcs = _decode_dtcs("43 80 01")
        assert [d.code for d in dtcs] == ["B0001"]

    def test_network_code(self):
        # Primeiro nibble 0xC => U0
        dtcs = _decode_dtcs("43 C1 00")
        assert [d.code for d in dtcs] == ["U0100"]

    def test_status_defaults_to_stored(self):
        dtcs = _decode_dtcs("43 01 71")
        assert dtcs[0].status == "stored"


class TestLivePIDsAsDict:
    def test_filters_none_values(self):
        pids = LivePIDs(rpm=800, coolant_temp_c=90)
        assert pids.as_dict() == {"rpm": 800, "coolant_temp_c": 90}

    def test_empty_when_nothing_set(self):
        assert LivePIDs().as_dict() == {}


class FakeReader(ELM327Reader):
    """Reader com respostas ELM327 pré-gravadas (sem porta serial)."""

    def __init__(self, responses: dict[str, str]):
        super().__init__(port="fake")
        self._responses = responses

    def _cmd(self, cmd: str, wait: float = 0.3) -> str:
        return self._responses.get(cmd, "NO DATA")


class TestGetLivePids:
    def test_decodes_all_supported_pids(self):
        reader = FakeReader({
            "010C": "41 0C 1A F8",  # rpm = (0x1A*256+0xF8)/4
            "010D": "41 0D 3C",     # 60 km/h
            "0105": "41 05 7B",     # 0x7B - 40 = 83 °C
            "0111": "41 11 3E",     # 62*100/255
            "0110": "41 10 01 F4",  # 500/100 g/s
            "0106": "41 06 80",     # (128-128)*100/128
            "0107": "41 07 85",     # (133-128)*100/128
            "0114": "41 14 80",     # 128/200 V
            "010F": "41 0F 46",     # 0x46 - 40 = 30 °C
            "012F": "41 2F FF",     # 255*100/255
        })
        p = reader.get_live_pids()
        assert p.rpm == 1726
        assert p.speed_kmh == 60
        assert p.coolant_temp_c == 83
        assert p.throttle_pct == 24.3
        assert p.maf_g_s == 5.0
        assert p.fuel_trim_short_b1 == 0.0
        assert p.fuel_trim_long_b1 == 3.9
        assert p.o2_b1s1_v == 0.64
        assert p.intake_temp_c == 30
        assert p.fuel_level_pct == 100.0

    def test_missing_pids_stay_none(self):
        reader = FakeReader({"010C": "41 0C 0B B8"})  # apenas RPM
        p = reader.get_live_pids()
        assert p.rpm == 750
        assert p.speed_kmh is None
        assert p.coolant_temp_c is None
        assert p.as_dict() == {"rpm": 750}

    def test_no_data_response_is_ignored(self):
        reader = FakeReader({})
        assert reader.get_live_pids().as_dict() == {}


class TestGetDtcsViaFake:
    def test_no_data_returns_empty_list(self):
        reader = FakeReader({"03": "NO DATA"})
        assert reader.get_dtcs() == []

    def test_decodes_stored_codes(self):
        reader = FakeReader({"03": "43 01 71 03 00"})
        assert [d.code for d in reader.get_dtcs()] == ["P0171", "P0300"]

    def test_clear_dtcs_ok(self):
        reader = FakeReader({"04": "44"})
        assert reader.clear_dtcs() is True
