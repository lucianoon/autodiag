"""Camada de acesso ao adaptador OBD2 — real (ELM327) ou simulado (demo)."""
from typing import Protocol

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
    def get_freeze_frame(self) -> FreezeFrame: ...
    def get_control_module_voltage(self) -> float | None: ...
    def get_supported_pids(self) -> list[str]: ...
    def clear_dtcs(self) -> bool: ...
    def get_live_pids(self) -> LivePIDs: ...


def create_reader(
    port: str | None = None,
    wifi_host: str | None = None,
    demo: bool = False,
) -> OBDReader:
    """Retorna o adaptador simulado quando ``demo=True``; caso contrário, o real."""
    if demo:
        return SimulatedELM327()
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
