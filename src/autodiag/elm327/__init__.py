"""Camada de acesso ao adaptador OBD2 — real (ELM327) ou simulado (demo)."""
from typing import Any, Protocol

from autodiag.elm327.reader import (
    DTCRecord,
    ELM327Error,
    ELM327Reader,
    FreezeFrame,
    LivePIDs,
    MonitorStatus,
)
from autodiag.elm327.sim import SimulatedELM327


class OBDReader(Protocol):
    """Interface comum entre o adaptador real e o simulado."""

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def get_vin(self) -> str: ...
    def get_dtcs(self) -> list[DTCRecord]: ...
    def get_pending_dtcs(self) -> list[DTCRecord]: ...
    def get_permanent_dtcs(self) -> list[DTCRecord]: ...
    def get_monitor_status(self) -> MonitorStatus: ...
    def get_warmups_since_clear(self) -> int | None: ...
    def get_distance_since_clear(self) -> int | None: ...
    def get_freeze_frame(self) -> FreezeFrame: ...
    def get_control_module_voltage(self) -> float | None: ...
    def get_supported_pids(self) -> list[str]: ...
    def clear_dtcs(self) -> bool: ...
    def get_live_pids(self) -> LivePIDs: ...
    def read_high_voltage(
        self,
        fields: list[dict[str, Any]],
        vin: str | None = None,
        request_header: str = "7E4",
    ) -> dict[str, Any]: ...


def create_reader(
    port: str | None = None,
    wifi_host: str | None = None,
    demo: bool = False,
) -> OBDReader:
    """Retorna o adaptador simulado quando ``demo=True``; caso contrário, o real."""
    if demo:
        # persist_state: a limpeza de DTCs no demo sobrevive entre execuções
        # (CLI) e requisições (web) por 30 min — é o que permite demonstrar a
        # detecção de limpeza recente com "apague e escaneie de novo".
        return SimulatedELM327(persist_state=True)
    return ELM327Reader(port=port, wifi_host=wifi_host)


__all__ = [
    "DTCRecord",
    "ELM327Error",
    "ELM327Reader",
    "FreezeFrame",
    "LivePIDs",
    "MonitorStatus",
    "OBDReader",
    "SimulatedELM327",
    "create_reader",
]
