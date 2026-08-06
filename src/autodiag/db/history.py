from __future__ import annotations

import builtins
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".autodiag" / "history.db"


def _default_db_path() -> Path:
    custom_path = os.environ.get("AUTODIAG_DB_PATH")
    if custom_path:
        return Path(custom_path).expanduser()
    return DB_PATH


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
    triage: dict | None = None
    tags: list[str] | None = None
    freeze_frame: dict | None = None


class History:
    def __init__(self, path: Path | None = None):
        path = path or _default_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(path))
        self._con.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        # No Windows, a conexão aberta mantém o arquivo .db travado;
        # fechar explicitamente permite mover/apagar o banco.
        self._con.close()

    def __enter__(self) -> History:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

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
                triage_json   TEXT,
                cost_min      INTEGER DEFAULT 0,
                cost_max      INTEGER DEFAULT 0,
                km            INTEGER,
                notes         TEXT
            )
        """)
        cols = {row[1] for row in self._con.execute("PRAGMA table_info(sessions)").fetchall()}
        if "triage_json" not in cols:
            self._con.execute("ALTER TABLE sessions ADD COLUMN triage_json TEXT")
        if "tags" not in cols:
            self._con.execute("ALTER TABLE sessions ADD COLUMN tags TEXT")
        if "freeze_frame" not in cols:
            self._con.execute("ALTER TABLE sessions ADD COLUMN freeze_frame TEXT")
        self._con.commit()

    def save(self, s: Session) -> int:
        cur = self._con.execute("""
            INSERT INTO sessions
              (ts, vin, vehicle_label, dtc_codes, urgency, rpm, speed,
               coolant_temp, maf, fuel_trim_short, fuel_trim_long, o2,
               diagnosis, triage_json, cost_min, cost_max, km, notes, tags,
               freeze_frame)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            s.ts, s.vin, s.vehicle_label,
            json.dumps(s.dtc_codes, ensure_ascii=False),
            s.urgency, s.rpm, s.speed, s.coolant_temp,
            s.maf, s.fuel_trim_short, s.fuel_trim_long, s.o2,
            s.diagnosis,
            json.dumps(s.triage, ensure_ascii=False) if s.triage is not None else None,
            s.cost_min, s.cost_max, s.km, s.notes,
            json.dumps(s.tags, ensure_ascii=False) if s.tags is not None else None,
            json.dumps(s.freeze_frame, ensure_ascii=False)
            if s.freeze_frame is not None else None,
        ))
        self._con.commit()
        rowid = cur.lastrowid
        assert rowid is not None  # INSERT sempre gera rowid
        return rowid

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["dtc_codes"] = json.loads(d.get("dtc_codes") or "[]")
        d["triage"] = json.loads(d.get("triage_json") or "null")
        d["tags"] = json.loads(d.get("tags") or "null")
        d["freeze_frame"] = json.loads(d.get("freeze_frame") or "null")
        d.pop("triage_json", None)
        return d

    def update_session(self, sid: int, *, notes: str | None = None,
                       tags: list[str] | None = None) -> dict | None:
        existing = self.get(sid)
        if existing is None:
            return None
        updates: list[str] = []
        params: list[Any] = []
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if not updates:
            return existing
        params.append(sid)
        self._con.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        self._con.commit()
        return self.get(sid)

    def list(self, limit: int = 10) -> builtins.list[dict[str, Any]]:
        rows = self._con.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by_vin(self, vin: str, limit: int = 10) -> builtins.list[dict[str, Any]]:
        if not vin:
            return []
        rows = self._con.execute(
            "SELECT * FROM sessions WHERE vin=? ORDER BY id DESC LIMIT ?",
            (vin, limit),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, sid: int) -> dict | None:
        row = self._con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def previous_for_vin(self, vin: str, *, before_id: int) -> dict | None:
        if not vin:
            return None
        row = self._con.execute(
            "SELECT * FROM sessions WHERE vin=? AND id < ? ORDER BY id DESC LIMIT 1",
            (vin, before_id),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["dtc_codes"] = json.loads(d["dtc_codes"] or "[]")
        d["triage"] = json.loads(d["triage_json"] or "null")
        d.pop("triage_json", None)
        return d

    def list_vehicles(self) -> builtins.list[dict[str, Any]]:
        rows = self._con.execute("""
            SELECT vin, vehicle_label, urgency, id, ts
            FROM sessions
            WHERE vin IS NOT NULL AND vin <> ''
            ORDER BY id DESC
        """).fetchall()
        seen: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in rows:
            vin = row["vin"]
            if not vin:
                continue
            if vin not in seen:
                seen[vin] = {
                    "vin": vin,
                    "vehicle_label": row["vehicle_label"] or "—",
                    "last_urgency": row["urgency"] or "informativo",
                    "last_ts": row["ts"] or "",
                    "last_id": row["id"],
                    "session_count": 0,
                }
                order.append(vin)
            seen[vin]["session_count"] += 1
        return [seen[v] for v in order]

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
        last_row = dict(last) if last else None
        if last_row is not None:
            last_row["dtc_codes"] = json.loads(last_row.get("dtc_codes") or "[]")
            last_row["triage"] = json.loads(last_row.get("triage_json") or "null")
            last_row.pop("triage_json", None)
        return {
            "total": total,
            "critical": critical,
            "last": last_row,
            "top_dtcs": top,
        }
