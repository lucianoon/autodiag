"""
Adaptador ELM327 simulado — executa o AutoDiag completo sem hardware.

Simula um VW Gol 2019 com mistura pobre (P0171) e falha de ignição
detectada (P0300): fuel trim de curto prazo alto, MAF baixo e sonda
lambda presa em tensão baixa — o quadro clássico de entrada falsa de ar.
"""
import random

from autodiag.elm327.reader import DTCRecord, LivePIDs, MonitorStatus

SIM_VIN = "9BWAB45U0KP042788"  # 9BW = Volkswagen Brasil, K = 2019


class SimulatedELM327:
    """Mesma interface pública do ELM327Reader, com respostas sintéticas.

    Use ``seed`` para leituras determinísticas (testes).
    """

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._dtcs = [DTCRecord("P0171"), DTCRecord("P0300")]

    # ── conexão ──────────────────────────────────────────────────

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def __enter__(self) -> "SimulatedELM327":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    # ── leitura ───────────────────────────────────────────────────

    def get_vin(self) -> str:
        return SIM_VIN

    def get_dtcs(self) -> list[DTCRecord]:
        return list(self._dtcs)

    def get_pending_dtcs(self) -> list[DTCRecord]:
        return []

    def get_permanent_dtcs(self) -> list[DTCRecord]:
        return []

    def get_monitor_status(self) -> MonitorStatus:
        return MonitorStatus(
            mil_on=bool(self._dtcs),
            dtc_count=len(self._dtcs),
            raw="SIMULATED",
        )

    def get_control_module_voltage(self) -> float | None:
        return 12.5

    def get_supported_pids(self) -> list[str]:
        return [
            "04",
            "05",
            "06",
            "07",
            "0C",
            "0D",
            "0F",
            "10",
            "11",
            "14",
            "2F",
        ]

    def clear_dtcs(self) -> bool:
        self._dtcs = []
        return True

    def get_live_pids(self) -> LivePIDs:
        rng = self._rng
        return LivePIDs(
            rpm=850 + rng.randint(-30, 30),
            speed_kmh=0,
            coolant_temp_c=92 + rng.randint(-2, 2),
            throttle_pct=round(14.9 + rng.uniform(-0.5, 0.5), 1),
            maf_g_s=round(1.8 + rng.uniform(-0.15, 0.15), 2),
            fuel_trim_short_b1=round(18.0 + rng.uniform(-1.5, 1.5), 1),
            fuel_trim_long_b1=round(12.5 + rng.uniform(-1.0, 1.0), 1),
            o2_b1s1_v=round(0.12 + rng.uniform(-0.03, 0.03), 2),
            intake_temp_c=31 + rng.randint(-2, 2),
            fuel_level_pct=round(58.0 + rng.uniform(-1.0, 1.0), 1),
        )
