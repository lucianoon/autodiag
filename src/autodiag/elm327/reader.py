"""
ELM327 reader via pyserial.
Suporta USB (/dev/cu.usbserial-*), Bluetooth (/dev/cu.OBDII*) e Wi-Fi (TCP).
"""
import asyncio
import glob
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Any

import serial


@dataclass
class LivePIDs:
    rpm: int | None = None
    speed_kmh: int | None = None
    coolant_temp_c: int | None = None
    throttle_pct: float | None = None
    maf_g_s: float | None = None
    fuel_trim_short_b1: float | None = None
    fuel_trim_long_b1: float | None = None
    o2_b1s1_v: float | None = None
    intake_temp_c: int | None = None
    fuel_level_pct: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class DTCRecord:
    code: str
    status: str = "stored"  # stored | pending


def _auto_detect_port() -> str | None:
    candidates = (
        glob.glob("/dev/cu.usbserial-*")
        + glob.glob("/dev/cu.SLAB_USBtoUART*")
        + glob.glob("/dev/cu.usbmodem*")
        + glob.glob("/dev/cu.OBDII*")
        + glob.glob("/dev/cu.OBD*")
    )
    return candidates[0] if candidates else None


def _decode_dtcs(raw: str) -> list[DTCRecord]:
    PREFIX = {"0": "P0", "1": "P1", "2": "P2", "3": "P3",
               "4": "C0", "5": "C1", "6": "C2", "7": "C3",
               "8": "B0", "9": "B1", "A": "B2", "B": "B3",
               "C": "U0", "D": "U1", "E": "U2", "F": "U3"}
    bytes_ = re.sub(r"\s+", "", raw.upper().replace("43", "", 1).strip()).replace("NO DATA", "")
    dtcs = []
    for i in range(0, len(bytes_) - 2, 4):
        chunk = bytes_[i:i+4]
        if len(chunk) < 4 or chunk == "0000":
            continue
        prefix = PREFIX.get(chunk[0], "P?")
        code = prefix + chunk[1:]
        dtcs.append(DTCRecord(code=code.upper()))
    return dtcs


class ELM327Reader:
    BAUD = 38400
    TIMEOUT = 2.0

    def __init__(self, port: str | None = None, wifi_host: str | None = None, wifi_port: int = 35000):
        self._port = port
        self._wifi_host = wifi_host
        self._wifi_port = wifi_port
        self._ser: serial.Serial | None = None
        self._sock: socket.socket | None = None

    # ── conexão ──────────────────────────────────────────────────

    def connect(self) -> bool:
        if self._wifi_host:
            return self._connect_wifi()
        port = self._port or _auto_detect_port()
        if not port:
            raise ConnectionError("Nenhuma porta ELM327 encontrada. Especifique com --port.")
        self._ser = serial.Serial(port, baudrate=self.BAUD, timeout=self.TIMEOUT)
        return self._init_elm()

    def _connect_wifi(self) -> bool:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.TIMEOUT)
        self._sock.connect((self._wifi_host, self._wifi_port))
        return self._init_elm()

    def _init_elm(self) -> bool:
        self._send_raw("ATZ\r", wait=1.5)
        self._cmd("ATE0")   # echo off
        self._cmd("ATL0")   # linefeeds off
        self._cmd("ATS0")   # spaces off
        self._cmd("ATH0")   # headers off
        self._cmd("ATSP0")  # protocol auto
        r = self._cmd("0100")  # check connectivity
        return "UNABLE" not in r and "ERROR" not in r

    def disconnect(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
        if self._sock:
            self._sock.close()

    # ── leitura ───────────────────────────────────────────────────

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

    def clear_dtcs(self) -> bool:
        r = self._cmd("04")
        return "44" in r or "OK" in r.upper()

    def get_live_pids(self) -> LivePIDs:
        p = LivePIDs()

        def _query(pid: str) -> str:
            return self._cmd(f"01{pid}")

        def _parse(raw: str, pid: str) -> str | None:
            raw = raw.upper().replace(" ", "")
            tag = f"41{pid.upper()}"
            idx = raw.find(tag)
            if idx == -1:
                return None
            return raw[idx + len(tag):]

        # RPM — PID 0C — formula: (A*256+B)/4
        r = _parse(_query("0C"), "0C")
        if r and len(r) >= 4:
            p.rpm = (int(r[0:2], 16) * 256 + int(r[2:4], 16)) // 4

        # Velocidade — PID 0D — A km/h
        r = _parse(_query("0D"), "0D")
        if r and len(r) >= 2:
            p.speed_kmh = int(r[0:2], 16)

        # Temperatura — PID 05 — A-40
        r = _parse(_query("05"), "05")
        if r and len(r) >= 2:
            p.coolant_temp_c = int(r[0:2], 16) - 40

        # Borboleta — PID 11 — A*100/255
        r = _parse(_query("11"), "11")
        if r and len(r) >= 2:
            p.throttle_pct = round(int(r[0:2], 16) * 100 / 255, 1)

        # MAF — PID 10 — (A*256+B)/100 g/s
        r = _parse(_query("10"), "10")
        if r and len(r) >= 4:
            p.maf_g_s = round((int(r[0:2], 16) * 256 + int(r[2:4], 16)) / 100, 2)

        # Short fuel trim B1 — PID 06 — (A-128)*100/128 %
        r = _parse(_query("06"), "06")
        if r and len(r) >= 2:
            p.fuel_trim_short_b1 = round((int(r[0:2], 16) - 128) * 100 / 128, 1)

        # Long fuel trim B1 — PID 07
        r = _parse(_query("07"), "07")
        if r and len(r) >= 2:
            p.fuel_trim_long_b1 = round((int(r[0:2], 16) - 128) * 100 / 128, 1)

        # O2 B1S1 — PID 14 — A/200 V
        r = _parse(_query("14"), "14")
        if r and len(r) >= 2:
            p.o2_b1s1_v = round(int(r[0:2], 16) / 200, 2)

        # Temperatura do ar de admissão — PID 0F — A-40
        r = _parse(_query("0F"), "0F")
        if r and len(r) >= 2:
            p.intake_temp_c = int(r[0:2], 16) - 40

        # Nível de combustível — PID 2F — A*100/255
        r = _parse(_query("2F"), "2F")
        if r and len(r) >= 2:
            p.fuel_level_pct = round(int(r[0:2], 16) * 100 / 255, 1)

        return p

    # ── interno ───────────────────────────────────────────────────

    def _cmd(self, cmd: str, wait: float = 0.3) -> str:
        return self._send_raw(cmd + "\r", wait=wait)

    def _send_raw(self, data: str, wait: float = 0.3) -> str:
        raw = data.encode()
        if self._ser:
            self._ser.reset_input_buffer()
            self._ser.write(raw)
            time.sleep(wait)
            response = b""
            while self._ser.in_waiting:
                response += self._ser.read(self._ser.in_waiting)
                time.sleep(0.05)
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
            except socket.timeout:
                pass
            return b"".join(chunks).decode("ascii", errors="ignore").strip().replace(">", "")
        return ""
