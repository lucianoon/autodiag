"""
ELM327 reader via pyserial.
Suporta USB, Bluetooth serial e Wi-Fi (TCP) em Windows, Linux e macOS.
"""

import glob
import re
import socket
import time
from dataclasses import dataclass
from typing import Any

import serial
from serial.tools import list_ports as serial_list_ports


class ELM327Error(ConnectionError):
    """Falha de comunicação com o adaptador ELM327."""


@dataclass
class LivePIDs:
    engine_load_pct: float | None = None
    rpm: int | None = None
    speed_kmh: int | None = None
    coolant_temp_c: int | None = None
    timing_advance_deg: float | None = None
    fuel_pressure_kpa: int | None = None
    throttle_pct: float | None = None
    maf_g_s: float | None = None
    commanded_equivalence_ratio: float | None = None
    fuel_trim_short_b1: float | None = None
    fuel_trim_long_b1: float | None = None
    o2_b1s1_v: float | None = None
    o2_b1s2_v: float | None = None
    o2_b2s1_v: float | None = None
    o2_b2s2_v: float | None = None
    intake_temp_c: int | None = None
    fuel_level_pct: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class DTCRecord:
    code: str
    status: str = "stored"  # stored | pending | permanent


@dataclass
class MonitorStatus:
    mil_on: bool | None = None
    dtc_count: int | None = None
    raw: str = ""

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"raw": self.raw}
        if self.mil_on is not None:
            data["mil_on"] = self.mil_on
        if self.dtc_count is not None:
            data["dtc_count"] = self.dtc_count
        return data


_PORT_KEYWORDS = (
    "obdii",
    "obd-ii",
    "obd",
    "elm327",
    "elm",
    "ch340",
    "ch341",
    "cp210",
    "ftdi",
    "pl2303",
    "usb serial",
    "usb-serial",
    "usbserial",
)


def list_ports() -> list[str]:
    ports: list[str] = []
    for port in sorted(serial_list_ports.comports(), key=lambda item: item.device):
        haystack = " ".join(
            part for part in (port.device, port.description, port.manufacturer) if part
        ).lower()
        if any(keyword in haystack for keyword in _PORT_KEYWORDS):
            ports.append(port.device)

    ports.extend(
        glob.glob("/dev/cu.usbserial-*")
        + glob.glob("/dev/cu.SLAB_USBtoUART*")
        + glob.glob("/dev/cu.usbmodem*")
        + glob.glob("/dev/cu.OBDII*")
        + glob.glob("/dev/cu.OBD*")
        + glob.glob("/dev/rfcomm*")
    )
    return sorted(set(ports))


def _auto_detect_port() -> str | None:
    ports = list_ports()
    return ports[0] if ports else None


def _decode_dtcs(
    raw: str,
    *,
    status: str = "stored",
    response_prefix: str = "43",
) -> list[DTCRecord]:
    prefix_map = {
        "0": "P0",
        "1": "P1",
        "2": "P2",
        "3": "P3",
        "4": "C0",
        "5": "C1",
        "6": "C2",
        "7": "C3",
        "8": "B0",
        "9": "B1",
        "A": "B2",
        "B": "B3",
        "C": "U0",
        "D": "U1",
        "E": "U2",
        "F": "U3",
    }
    bytes_ = re.sub(r"\s+", "", raw.upper().strip()).replace("NO DATA", "")
    bytes_ = bytes_.replace(response_prefix.upper(), "", 1)
    dtcs = []
    for index in range(0, len(bytes_) - 2, 4):
        chunk = bytes_[index : index + 4]
        if len(chunk) < 4 or chunk == "0000":
            continue
        code = prefix_map.get(chunk[0], "P?") + chunk[1:]
        dtcs.append(DTCRecord(code=code.upper(), status=status))
    return dtcs


def _extract_payload(raw: str, response_tag: str) -> str | None:
    compact = re.sub(r"\s+", "", raw.upper())
    index = compact.find(response_tag.upper())
    if index == -1:
        return None
    return compact[index + len(response_tag) :]


class ELM327Reader:
    BAUD = 38400
    TIMEOUT = 2.0

    def __init__(
        self,
        port: str | None = None,
        wifi_host: str | None = None,
        wifi_port: int = 35000,
    ):
        self._port = port
        self._wifi_host = wifi_host
        self._wifi_port = wifi_port
        self._ser: serial.Serial | None = None
        self._sock: socket.socket | None = None

    def connect(self) -> bool:
        if self._wifi_host:
            return self._connect_wifi()
        port = self._port or _auto_detect_port()
        if not port:
            raise ELM327Error("Nenhuma porta ELM327 encontrada. Especifique com --port.")
        try:
            self._ser = serial.Serial(port, baudrate=self.BAUD, timeout=self.TIMEOUT)
        except (serial.SerialException, OSError) as exc:
            raise ELM327Error(f"Falha ao abrir a porta {port}: {exc}") from exc
        return self._init_elm()

    def _connect_wifi(self) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.TIMEOUT)
            self._sock.connect((self._wifi_host, self._wifi_port))
        except OSError as exc:
            raise ELM327Error(
                f"Falha ao conectar em {self._wifi_host}:{self._wifi_port}: {exc}"
            ) from exc
        return self._init_elm()

    def _init_elm(self) -> bool:
        self._send_raw("ATZ\r", wait=1.5)
        self._cmd("ATE0")
        self._cmd("ATL0")
        self._cmd("ATS0")
        self._cmd("ATH0")
        self._cmd("ATSP0")
        response = self._cmd("0100")
        return "UNABLE" not in response and "ERROR" not in response

    def disconnect(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
        if self._sock:
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "ELM327Reader":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.disconnect()

    def get_vin(self) -> str:
        raw = self._cmd("0902")
        raw = re.sub(r"49 02 0[0-9A-F] ", "", raw, flags=re.IGNORECASE)
        raw = raw.replace(" ", "").replace("\r", "").replace("\n", "")
        try:
            return bytes.fromhex(raw).decode("ascii", errors="ignore").strip()
        except Exception:
            return raw[:17] if len(raw) >= 17 else raw

    def get_dtcs(self) -> list[DTCRecord]:
        raw = self._cmd("03")
        if "NO DATA" in raw or "NODATA" in raw:
            return []
        return _decode_dtcs(raw)

    def get_pending_dtcs(self) -> list[DTCRecord]:
        raw = self._cmd("07")
        if "NO DATA" in raw or "NODATA" in raw:
            return []
        return _decode_dtcs(raw, status="pending", response_prefix="47")

    def get_permanent_dtcs(self) -> list[DTCRecord]:
        raw = self._cmd("0A")
        if "NO DATA" in raw or "NODATA" in raw:
            return []
        return _decode_dtcs(raw, status="permanent", response_prefix="4A")

    def get_monitor_status(self) -> MonitorStatus:
        raw = self._cmd("0101")
        payload = _extract_payload(raw, "4101")
        status = MonitorStatus(raw=raw)
        if payload and len(payload) >= 2:
            a = int(payload[0:2], 16)
            status.mil_on = bool(a & 0x80)
            status.dtc_count = a & 0x7F
        return status

    def get_control_module_voltage(self) -> float | None:
        raw = self._cmd("ATRV")
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*V", raw.upper())
        return float(match.group(1)) if match else None

    def get_supported_pids(self) -> list[str]:
        raw = self._cmd("0100")
        payload = _extract_payload(raw, "4100")
        if not payload or len(payload) < 8:
            return []
        bits = int(payload[:8], 16)
        supported = []
        for index in range(32):
            if bits & (1 << (31 - index)):
                supported.append(f"{index + 1:02X}")
        return supported

    def clear_dtcs(self) -> bool:
        response = self._cmd("04")
        return "44" in response or "OK" in response.upper()

    def get_live_pids(self) -> LivePIDs:
        pids = LivePIDs()

        def _query(pid: str) -> str:
            return self._cmd(f"01{pid}")

        def _parse(raw: str, pid: str) -> str | None:
            compact = raw.upper().replace(" ", "")
            tag = f"41{pid.upper()}"
            index = compact.find(tag)
            if index == -1:
                return None
            return compact[index + len(tag) :]

        response = _parse(_query("04"), "04")
        if response and len(response) >= 2:
            pids.engine_load_pct = round(int(response[0:2], 16) * 100 / 255, 1)

        response = _parse(_query("0C"), "0C")
        if response and len(response) >= 4:
            pids.rpm = (int(response[0:2], 16) * 256 + int(response[2:4], 16)) // 4

        response = _parse(_query("0D"), "0D")
        if response and len(response) >= 2:
            pids.speed_kmh = int(response[0:2], 16)

        response = _parse(_query("05"), "05")
        if response and len(response) >= 2:
            pids.coolant_temp_c = int(response[0:2], 16) - 40

        response = _parse(_query("0E"), "0E")
        if response and len(response) >= 2:
            pids.timing_advance_deg = round(int(response[0:2], 16) / 2 - 64, 1)

        response = _parse(_query("0A"), "0A")
        if response and len(response) >= 2:
            pids.fuel_pressure_kpa = int(response[0:2], 16) * 3

        response = _parse(_query("11"), "11")
        if response and len(response) >= 2:
            pids.throttle_pct = round(int(response[0:2], 16) * 100 / 255, 1)

        response = _parse(_query("10"), "10")
        if response and len(response) >= 4:
            pids.maf_g_s = round((int(response[0:2], 16) * 256 + int(response[2:4], 16)) / 100, 2)

        response = _parse(_query("44"), "44")
        if response and len(response) >= 4:
            pids.commanded_equivalence_ratio = round(
                (int(response[0:2], 16) * 256 + int(response[2:4], 16)) / 32768,
                3,
            )

        response = _parse(_query("06"), "06")
        if response and len(response) >= 2:
            pids.fuel_trim_short_b1 = round((int(response[0:2], 16) - 128) * 100 / 128, 1)

        response = _parse(_query("07"), "07")
        if response and len(response) >= 2:
            pids.fuel_trim_long_b1 = round((int(response[0:2], 16) - 128) * 100 / 128, 1)

        response = _parse(_query("14"), "14")
        if response and len(response) >= 2:
            pids.o2_b1s1_v = round(int(response[0:2], 16) / 200, 2)

        response = _parse(_query("15"), "15")
        if response and len(response) >= 2:
            pids.o2_b1s2_v = round(int(response[0:2], 16) / 200, 2)

        response = _parse(_query("18"), "18")
        if response and len(response) >= 2:
            pids.o2_b2s1_v = round(int(response[0:2], 16) / 200, 2)

        response = _parse(_query("19"), "19")
        if response and len(response) >= 2:
            pids.o2_b2s2_v = round(int(response[0:2], 16) / 200, 2)

        response = _parse(_query("0F"), "0F")
        if response and len(response) >= 2:
            pids.intake_temp_c = int(response[0:2], 16) - 40

        response = _parse(_query("2F"), "2F")
        if response and len(response) >= 2:
            pids.fuel_level_pct = round(int(response[0:2], 16) * 100 / 255, 1)

        return pids

    def _cmd(self, cmd: str, wait: float = 0.3, retries: int = 1) -> str:
        response = self._send_raw(cmd + "\r", wait=wait)
        for _ in range(retries):
            if response:
                break
            response = self._send_raw(cmd + "\r", wait=wait)
        return response

    def _send_raw(self, data: str, wait: float = 0.3) -> str:
        raw = data.encode("ascii")
        if self._ser:
            self._ser.reset_input_buffer()
            self._ser.write(raw)
            deadline = time.monotonic() + max(wait, self.TIMEOUT)
            response = b""
            while time.monotonic() < deadline:
                waiting = self._ser.in_waiting
                if waiting:
                    response += self._ser.read(waiting)
                    if b">" in response:
                        break
                else:
                    time.sleep(0.02)
            return response.decode("ascii", errors="ignore").strip().replace(">", "")

        if self._sock:
            self._sock.sendall(raw)
            time.sleep(wait)
            chunks = []
            try:
                while True:
                    chunk = self._sock.recv(1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    if b">" in chunk:
                        break
            except TimeoutError:
                pass
            return b"".join(chunks).decode("ascii", errors="ignore").strip().replace(">", "")

        return ""
