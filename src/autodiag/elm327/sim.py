"""
Adaptador ELM327 simulado — executa o AutoDiag completo sem hardware.

Simula um VW Gol 2019 com mistura pobre (P0171) e falha de ignição
detectada (P0300): fuel trim de curto prazo alto, MAF baixo e sonda
lambda presa em tensão baixa — o quadro clássico de entrada falsa de ar.
"""
import json
import os
import random
import time
from pathlib import Path
from typing import Any

from autodiag.core.ev_support import (
    PROP_COMBUSTION,
    apply_hv_formula,
    detectar_propulsao_por_vin,
)
from autodiag.elm327.reader import DTCRecord, FreezeFrame, LivePIDs, MonitorStatus

SIM_VIN = "9BWAB45U0KP042788"  # 9BW = Volkswagen Brasil, K = 2019


# Payloads brutos 2 bytes big-endian para cada marca simulada HV.
# Aplicação via apply_hv_formula: ex SoC 52.3% U16*0.1 → 523.
_SIM_BRAND_HV_RAW_SAMPLES: dict[str, dict[int, bytes]] = {
    "BYD": {
        # U16 * 0.1. → 52.3% = 523 → bytes 0x020B
        0x0101: (int(52.3 / 0.1)).to_bytes(2, "big", signed=False),
        0x0102: (int(398.6 / 0.1)).to_bytes(2, "big", signed=False),
        0x0103: (int(-8.2 / 0.1)).to_bytes(2, "big", signed=True),
        0x0104: (int((27.4 + 40) / 0.1)).to_bytes(2, "big", signed=True),
        0x0105: (int(18.6 / 0.25)).to_bytes(2, "big", signed=True),
        0x0106: (int(95.1 / 0.1)).to_bytes(2, "big", signed=False),
    },
    "GWM": {
        0x0201: (int(64.8 / 0.1)).to_bytes(2, "big"),
        0x0202: (int(402.0 / 0.1)).to_bytes(2, "big"),
        0x0203: (int((33.1 + 40) / 0.1)).to_bytes(2, "big", signed=True),
    },
    "Tesla": {
        # Tesla uses U16 * 0.05:
        0x0301: (int(58.6 / 0.05)).to_bytes(2, "big"),
        0x0302: (int(403.2 / 0.05)).to_bytes(2, "big"),
        0x0303: (int(96.4 / 0.05)).to_bytes(2, "big"),
    },
    "Renault-Brasil": {
        0x0401: (int(44.2 / 0.1)).to_bytes(2, "big"),
        0x0402: (int(387.4 / 0.1)).to_bytes(2, "big"),
    },
    "Volkswagen": {
        0x0501: (int(71.3 / 0.1)).to_bytes(2, "big"),
    },
}


# Validade do estado "DTCs apagados" do demo persistido em disco. Depois
# disso o veículo simulado volta ao cenário padrão P0171/P0300.
_DEMO_CLEARED_TTL_S = 30 * 60


def _demo_state_path() -> Path:
    home = os.environ.get("AUTODIAG_HOME")
    base = Path(home).expanduser() if home else Path.home() / ".autodiag"
    return base / "demo_state.json"


class SimulatedELM327:
    """Mesma interface pública do ELM327Reader, com respostas sintéticas.

    Use ``seed`` para leituras determinísticas (testes).

    ``persist_state=True`` (usado por ``create_reader(demo=True)``) grava a
    limpeza de DTCs num marcador em disco com validade curta — sem isso,
    "apague os DTCs e escaneie de novo" não funcionaria entre requisições
    web ou execuções da CLI, já que cada scan cria um simulador novo.
    Instanciar direto (testes) mantém o estado apenas em memória.
    """

    def __init__(self, seed: int | None = None, persist_state: bool = False):
        self._rng = random.Random(seed)
        self._dtcs = [DTCRecord("P0171"), DTCRecord("P0300")]
        self._cleared = False
        self._persist = persist_state
        if persist_state and self._read_persisted_cleared():
            self._cleared = True
            self._dtcs = []

    def _read_persisted_cleared(self) -> bool:
        try:
            data = json.loads(_demo_state_path().read_text(encoding="utf-8"))
            cleared_at = float(data.get("cleared_at") or 0)
            # `>= 0`, não `> 0`: no Windows o time.time() tem resolução de ~15,6 ms, então
            # a gravação do marcador e esta leitura caem no mesmo tick e a diferença é
            # exatamente 0.0 — o que descartava a limpeza que acabou de acontecer. O limite
            # inferior existe para rejeitar carimbo no futuro (relógio ajustado para trás),
            # e continua fazendo isso, porque aí a diferença é negativa.
            return 0 <= time.time() - cleared_at < _DEMO_CLEARED_TTL_S
        except Exception:
            return False

    def _write_persisted_cleared(self) -> None:
        try:
            path = _demo_state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"cleared_at": time.time()}), encoding="utf-8"
            )
        except Exception:
            pass

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
        # Após uma limpeza de DTCs, os monitores voltam a "incompleto" até o
        # veículo cumprir os ciclos de condução — o quadro típico de um scan
        # apagado antes de uma vistoria.
        complete = not self._cleared
        return MonitorStatus(
            mil_on=bool(self._dtcs),
            dtc_count=len(self._dtcs),
            ignition="spark",
            monitors={
                "Falha de ignição (misfire)": complete,
                "Sistema de combustível": complete,
                "Componentes (CCM)": True,
                "Catalisador": complete,
                "Sistema EVAP": complete,
                "Sonda lambda": complete,
                "Aquecedor da sonda lambda": complete,
                "EGR/VVT": complete,
            },
            raw="SIMULATED",
        )

    def get_warmups_since_clear(self) -> int | None:
        return 2 if self._cleared else 48

    def get_distance_since_clear(self) -> int | None:
        return 7 if self._cleared else 1246

    def get_freeze_frame(self) -> FreezeFrame:
        return FreezeFrame(
            raw="SIMULATED FREEZE FRAME",
            dtc_code=self._dtcs[0].code if self._dtcs else None,
            rpm=1720,
            coolant_temp_c=98,
            speed_kmh=54,
            engine_load_pct=43.9,
            throttle_pct=19.6,
            maf_g_s=2.2,
            fuel_trim_short_b1=18.8,
            fuel_trim_long_b1=9.4,
            o2_b1s1_v=0.12,
            intake_temp_c=36,
            mileage_km=68420,
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
        self._cleared = True
        if self._persist:
            self._write_persisted_cleared()
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

    # ── UDS $22 HV simulado (batch EV-P3) ──────────────────────────

    def read_high_voltage(
        self,
        fields: list[dict[str, Any]],
        vin: str | None = None,
        request_header: str = "7E4",
    ) -> dict[str, Any]:
        """Mesma assinatura de ``ELM327Reader.read_high_voltage``.

        Se ``vin`` aponta para um WMI que tem dados HV de simulação
        (BYD/GWM/Tesla/Renault-Brasil/VW EV), devolve dicionário com chaves
        ``did_XXXX`` e nome do campo + valor numérico (o mesmo padrão dupla-chave
        do leitor real). Para WMI ICE devolve ``{}`` vazio.
        """
        if not fields:
            return {}
        det_vin = vin or self.get_vin()
        ev_info = detectar_propulsao_por_vin(det_vin)
        if ev_info.propensao == PROP_COMBUSTION:
            return {}
        marca = ev_info.marca
        samples: dict[int, bytes] | None = None
        if marca:
            samples = _SIM_BRAND_HV_RAW_SAMPLES.get(marca) or _SIM_BRAND_HV_RAW_SAMPLES.get(
                marca.split("-")[0]
            )
        if not samples:
            return {}
        out: dict[str, Any] = {}
        rng = self._rng
        for field in fields:
            did_int: int = int(field.get("id") or 0)
            if did_int <= 0 or did_int not in samples:
                continue
            raw = samples[did_int]
            formula = str(field.get("formula") or "")
            name = str(field.get("name") or f"did_{did_int:04X}")
            base_val = apply_hv_formula(raw, formula)
            if base_val is None:
                continue
            # Introduz ruído realista (~±0.8%) para simular scan com temperatura
            # de célula e corrente oscilando em tempo real.
            jitter = 1.0 + rng.uniform(-0.008, 0.008)
            if isinstance(base_val, int):
                # Mantém int se era raw U16 sem escala
                val: int | float = int(base_val * jitter)
            else:
                # Preserve 2 casas decimais das fórmulas padrão.
                val = round(float(base_val) * jitter, 2)
            key_hex = f"did_{did_int:04X}"
            out[key_hex] = val
            out[name] = val
        return out
