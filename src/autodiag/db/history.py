import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path.home() / ".autodiag" / "history.db"


@dataclass
class Session:
    id: int | None
    ts: str
    vin: str
    vehicle_label: str
    dtc_codes: list[str]
    urgency: str
    rpm: int | None
    speed: int | None
    coolant_temp: int | None
    maf: float | None
    fuel_trim_short: float | None
    fuel_trim_long: float | None
    o2: float | None
    diagnosis: str
    cost_min: int
    cost_max: int
    km: int | None
    notes: str


class History:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(path))
        self._con.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts            TEXT NOT NULL,
                vin           TEXT,
                vehicle_label TEXT,
                dtc_codes     TEXT,
                urgency       TEXT,
                rpm           INTEGER,
                speed         INTEGER,
                coolant_temp  INTEGER,
                maf           REAL,
                fuel_trim_short REAL,
                fuel_trim_long  REAL,
                o2            REAL,
                diagnosis     TEXT,
                cost_min      INTEGER DEFAULT 0,
                cost_max      INTEGER DEFAULT 0,
                km            INTEGER,
                notes         TEXT
            )
        """)
        self._con.commit()

    def save(self, s: Session) -> int:
        cur = self._con.execute("""
            INSERT INTO sessions
              (ts, vin, vehicle_label, dtc_codes, urgency, rpm, speed,
               coolant_temp, maf, fuel_trim_short, fuel_trim_long, o2,
               diagnosis, cost_min, cost_max, km, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            s.ts, s.vin, s.vehicle_label,
            json.dumps(s.dtc_codes, ensure_ascii=False),
            s.urgency, s.rpm, s.speed, s.coolant_temp,
            s.maf, s.fuel_trim_short, s.fuel_trim_long, s.o2,
            s.diagnosis, s.cost_min, s.cost_max, s.km, s.notes,
        ))
        self._con.commit()
        rowid = cur.lastrowid
        assert rowid is not None  # INSERT sempre gera rowid
        return rowid

    def list(self, limit: int = 10) -> list[dict]:
        rows = self._con.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["dtc_codes"] = json.loads(d["dtc_codes"] or "[]")
            result.append(d)
        return result

    def get(self, sid: int) -> dict | None:
        row = self._con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["dtc_codes"] = json.loads(d["dtc_codes"] or "[]")
        return d

    def summary(self) -> dict:
        total = self._con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        critical = self._con.execute(
            "SELECT COUNT(*) FROM sessions WHERE urgency='critico'"
        ).fetchone()[0]
        last = self._con.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        rows = self._con.execute("SELECT dtc_codes FROM sessions").fetchall()
        freq: dict[str, int] = {}
        for row in rows:
            for code in json.loads(row[0] or "[]"):
                freq[code] = freq.get(code, 0) + 1
        top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "total": total,
            "critical": critical,
            "last": dict(last) if last else None,
            "top_dtcs": top,
        }
