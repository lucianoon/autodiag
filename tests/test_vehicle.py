"""Testes da decodificação local de VIN (autodiag.core.vehicle)."""
from autodiag.core.vehicle import VehicleProfile, decode_vin_local


class TestDecodeVinLocal:
    def test_known_wmi_and_year(self):
        # WMI 9BW = Volkswagen Brasil; posição 10 (índice 9) = 'L' = 2020
        profile = decode_vin_local("9BWAB47X0LP123456")
        assert profile.vin == "9BWAB47X0LP123456"
        assert profile.make == "Volkswagen Brasil"
        assert profile.year == 2020

    def test_input_is_normalized(self):
        profile = decode_vin_local("  9bwab47x0lp123456 ")
        assert profile.vin == "9BWAB47X0LP123456"
        assert profile.make == "Volkswagen Brasil"

    def test_unknown_wmi_keeps_raw_prefix(self):
        profile = decode_vin_local("ZZZAB47X0LP123456")
        assert profile.make == "WMI:ZZZ"

    def test_unknown_year_char_gives_zero(self):
        # 'Z' não está na tabela de anos
        profile = decode_vin_local("9BWAB47X0ZP123456")
        assert profile.year == 0

    def test_wrong_length_returns_bare_profile(self):
        profile = decode_vin_local("ABC123")
        assert profile.vin == "ABC123"
        assert profile.make == ""
        assert profile.year == 0

    def test_year_table_covers_2015_plus(self):
        for char, year in [("F", 2015), ("K", 2019), ("P", 2023), ("T", 2026)]:
            vin = f"9BWAB47X0{char}P123456"
            assert decode_vin_local(vin).year == year


class TestVehicleProfileLabel:
    def test_full_label(self):
        p = VehicleProfile(make="Toyota", model="Corolla", year=2020)
        assert p.label == "Toyota Corolla 2020"

    def test_partial_label_skips_empty_fields(self):
        p = VehicleProfile(make="Fiat")
        assert p.label == "Fiat"

    def test_empty_profile_has_fallback_label(self):
        assert VehicleProfile().label == "Veículo desconhecido"
