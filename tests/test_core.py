import tempfile
import unittest
from pathlib import Path

from autodiag.core.diagnosis import infer_urgency
from autodiag.db.history import History, Session
from autodiag.elm327.reader import (
    DTCRecord,
    LivePIDs,
    _decode_dtcs,
    _extract_payload,
)


class DTCDecodeTests(unittest.TestCase):
    def test_decodes_powertrain_code(self):
        codes = [dtc.code for dtc in _decode_dtcs("43 01 71 00 00 00 00")]

        self.assertEqual(codes, ["P0171"])

    def test_decodes_network_code(self):
        codes = [dtc.code for dtc in _decode_dtcs("43 C1 23 00 00 00 00")]

        self.assertEqual(codes, ["U0123"])

    def test_decodes_pending_code_status(self):
        dtcs = _decode_dtcs("47 01 71 00 00", status="pending", response_prefix="47")

        self.assertEqual(dtcs[0].code, "P0171")
        self.assertEqual(dtcs[0].status, "pending")

    def test_ignores_empty_codes(self):
        codes = [dtc.code for dtc in _decode_dtcs("43 00 00 00 00 00 00")]

        self.assertEqual(codes, [])

    def test_extracts_pid_payload(self):
        self.assertEqual(_extract_payload("41 01 83 07 65 04", "4101"), "83076504")


class DiagnosisTests(unittest.TestCase):
    def test_critical_dtc_wins(self):
        urgency = infer_urgency([DTCRecord("P0300")], LivePIDs())

        self.assertEqual(urgency, "critico")

    def test_hot_coolant_is_critical(self):
        urgency = infer_urgency([], LivePIDs(coolant_temp_c=110))

        self.assertEqual(urgency, "critico")

    def test_clean_scan_is_informative(self):
        urgency = infer_urgency([], LivePIDs())

        self.assertEqual(urgency, "informativo")


class HistoryTests(unittest.TestCase):
    def test_saves_and_summarizes_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            # O context manager garante a conexão fechada antes da limpeza do
            # TemporaryDirectory — no Windows, arquivo aberto não pode ser apagado.
            with History(Path(tmp) / "history.db") as history:
                sid = history.save(Session(
                    id=None,
                    ts="07/07/2026 20:00",
                    vin="",
                    vehicle_label="Veiculo teste",
                    dtc_codes=["P0171"],
                    urgency="atencao",
                    rpm=900,
                    speed=0,
                    coolant_temp=90,
                    maf=3.2,
                    fuel_trim_short=8.0,
                    fuel_trim_long=5.0,
                    o2=0.7,
                    diagnosis="",
                    cost_min=0,
                    cost_max=0,
                    km=12345,
                    notes="",
                ))

                self.assertEqual(sid, 1)
                self.assertEqual(history.list()[0]["dtc_codes"], ["P0171"])
                self.assertEqual(history.summary()["top_dtcs"], [("P0171", 1)])


if __name__ == "__main__":
    unittest.main()
