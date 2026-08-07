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

    def _cmd(self, cmd: str, wait: float = 0.3, retries: int = 0) -> str:
        _ = (wait, retries)
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


class TestFreezeFrame:
    def test_decodes_p0171_freeze(self):
        """Comando 02 (Freeze Frame): resposta `42 <PID 02 + DTC 4B>` seguido de
        blocos (PID + 1B ou + 2B) conforme o parser."""
        reader = FakeReader({
            # DTC congelado: PID 02 + 01 71 00 (4 bytes) => P0171
            # Depois (PID 0C 2B): 25 80 -> rpm = 9600/4 = 2400
            # (PID 05 1B): 8A -> 138-40 = 98°C
            # (PID 0D 1B): 36 = 54 km/h
            # (PID 04 1B): 70 = 112*100/255 = 43.9
            # (PID 11 1B): 32 = 50*100/255 = 19.6 (throttle)
            # (PID 10 2B): 00 DC = 220/100 = 2.2 g/s
            # (PID 06 1B): 98 = (152-128)*100/128 = 18.75
            # (PID 07 1B): 8C = (140-128)*100/128 = 9.375
            # (PID 14 1B): 18 = 24/200 = 0.12 V
            # (PID 0F 1B): 4C = 76-40 = 36°C
            "02": (
                "42 02 01 71 00"
                " 0C 25 80"
                " 05 8A"
                " 0D 36"
                " 04 70"
                " 11 32"
                " 10 00 DC"
                " 06 98"
                " 07 8C"
                " 14 18"
                " 0F 4C"
            ),
        })
        ff = reader.get_freeze_frame()
        assert ff.dtc_code == "P0171"
        assert ff.rpm == 2400
        assert ff.coolant_temp_c == 98
        assert ff.speed_kmh == 54
        assert abs(float(ff.engine_load_pct or 0) - 43.9) < 0.2
        assert abs(float(ff.throttle_pct or 0) - 19.6) < 0.3
        assert ff.maf_g_s == 2.2
        assert abs(float(ff.fuel_trim_short_b1 or 0) - 18.8) < 0.1
        assert abs(float(ff.fuel_trim_long_b1 or 0) - 9.4) < 0.1
        assert ff.o2_b1s1_v == 0.12
        assert ff.intake_temp_c == 36

    def test_no_data_returns_empty_frame(self):
        ff = FakeReader({"02": "NO DATA"}).get_freeze_frame()
        assert ff.dtc_code is None
        assert ff.rpm is None



class TestMonitorStatus:
    def test_parses_spark_readiness_bytes(self):
        # A=0x00 (MIL off, 0 DTCs); B=0x27 (contínuos suportados, combustível
        # incompleto, centelha); C=0xE5 (cat/EVAP/sonda/aquecedor/EGR
        # suportados); D=0x05 (catalisador e EVAP incompletos).
        reader = FakeReader({"0101": "41 01 00 27 E5 05"})
        status = reader.get_monitor_status()
        assert status.mil_on is False
        assert status.dtc_count == 0
        assert status.ignition == "spark"
        spark_mon = status.monitors or {}
        assert bool(spark_mon["Sistema de combustível"]) is False
        assert bool(spark_mon["Falha de ignição (misfire)"]) is True
        assert bool(spark_mon["Catalisador"]) is False
        assert bool(spark_mon["Sistema EVAP"]) is False
        assert bool(spark_mon["Sonda lambda"]) is True
        assert set(status.incomplete_monitors) == {
            "Sistema de combustível", "Catalisador", "Sistema EVAP",
        }

    def test_parses_compression_ignition_table(self):
        # B=0x0F: contínuos suportados + bit3 (compressão); C=0x03: NMHC + NOx;
        # D=0x02: NOx incompleto.
        reader = FakeReader({"0101": "41 01 81 0F 03 02"})
        status = reader.get_monitor_status()
        assert status.mil_on is True
        assert status.dtc_count == 1
        assert status.ignition == "compression"
        monitors = status.monitors or {}
        assert bool(monitors["Catalisador NMHC"]) is True
        assert bool(monitors["Pós-tratamento NOx/SCR"]) is False

    def test_short_payload_keeps_monitors_none(self):
        reader = FakeReader({"0101": "41 01 02"})
        status = reader.get_monitor_status()
        assert status.dtc_count == 2
        assert status.monitors is None
        assert status.incomplete_monitors == []

    def test_as_dict_includes_readiness_fields(self):
        reader = FakeReader({"0101": "41 01 00 27 E5 05"})
        data = reader.get_monitor_status().as_dict()
        assert data["ignition"] == "spark"
        assert "Catalisador" in data["monitors"]
        assert "Catalisador" in data["incomplete_monitors"]


class TestClearCounters:
    def test_warmups_since_clear(self):
        reader = FakeReader({"0130": "41 30 30"})
        assert reader.get_warmups_since_clear() == 48

    def test_distance_since_clear(self):
        reader = FakeReader({"0131": "41 31 04 DE"})
        assert reader.get_distance_since_clear() == 1246

    def test_no_data_returns_none(self):
        reader = FakeReader({})
        assert reader.get_warmups_since_clear() is None
        assert reader.get_distance_since_clear() is None


class RecordingReader(ELM327Reader):
    """FakeReader que grava cada comando enviado ao ELM."""

    def __init__(self, responses: dict[str, str]):
        super().__init__(port="fake")
        self._responses = responses
        self.commands: list[str] = []

    def _cmd(self, cmd: str, wait: float = 0.3, retries: int = 0) -> str:
        _ = (wait, retries)
        self.commands.append(cmd)
        return self._responses.get(cmd, "NO DATA")


class TestReadHighVoltageHeaders:
    FIELDS = [{"id": 0x0101, "name": "SoC", "unit": "%", "formula": "U16 * 0.1"}]

    def test_uses_brand_request_header_and_restores_broadcast(self):
        reader = RecordingReader({
            "AT SH 79B": "OK",
            "ATE0": "OK",
            "220101": "62 01 01 13 88",
        })
        out = reader.read_high_voltage(self.FIELDS, request_header="79B")
        assert out.get("did_0101") == 500.0
        assert "AT SH 79B" in reader.commands
        # Nunca envia request no ID de RESPOSTA do BMS.
        assert "AT SH 7BB" not in reader.commands
        # Restaura o broadcast OBD2 7DF — 7E0 silenciaria DTCs/PIDs num BEV.
        assert reader.commands[-1] == "AT SH 7DF"
        assert "AT SH 7E0" not in reader.commands

    def test_default_header_is_generic_ev_powertrain(self):
        reader = RecordingReader({"AT SH 7E4": "OK", "ATE0": "OK"})
        reader.read_high_voltage(self.FIELDS)
        assert "AT SH 7E4" in reader.commands
        assert reader.commands[-1] == "AT SH 7DF"

    def test_broadcast_restored_even_on_header_error(self):
        reader = RecordingReader({"AT SH 7E4": "ERROR"})
        out = reader.read_high_voltage(self.FIELDS)
        assert out == {}
        assert reader.commands[-1] == "AT SH 7DF"

    def test_header_input_is_sanitized(self):
        reader = RecordingReader({})
        reader.read_high_voltage(self.FIELDS, request_header="7E4; ATZ")
        joined = " | ".join(reader.commands)
        assert "ATZ" not in joined.replace("AT SH", "")
