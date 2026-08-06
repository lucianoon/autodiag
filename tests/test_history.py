"""Testes do histórico SQLite (autodiag.db.history) usando banco temporário."""
from typing import Any

import pytest

from autodiag.db.history import History, Session


def _session(**overrides: Any) -> Session:
    base: dict[str, Any] = dict(
        id=None,
        ts="01/07/2026 10:00",
        vin="9BWAB47X0LP123456",
        vehicle_label="Volkswagen Brasil 2020",
        dtc_codes=["P0171"],
        urgency="atencao",
        rpm=800,
        speed=0,
        coolant_temp=90,
        maf=3.5,
        fuel_trim_short=2.3,
        fuel_trim_long=1.1,
        o2=0.45,
        diagnosis="",
        cost_min=0,
        cost_max=0,
        km=42000,
        notes="teste",
    )
    base.update(overrides)
    return Session(**base)


@pytest.fixture
def history(tmp_path):
    with History(path=tmp_path / "history.db") as h:
        yield h


def test_save_returns_incrementing_ids(history):
    assert history.save(_session()) == 1
    assert history.save(_session()) == 2


def test_get_roundtrip(history):
    sid = history.save(_session(dtc_codes=["P0300", "U0100"], urgency="critico"))
    row = history.get(sid)
    assert row is not None
    assert row["vin"] == "9BWAB47X0LP123456"
    assert row["dtc_codes"] == ["P0300", "U0100"]
    assert row["urgency"] == "critico"
    assert row["km"] == 42000


def test_get_missing_returns_none(history):
    assert history.get(999) is None


def test_list_orders_newest_first_and_respects_limit(history):
    for i in range(5):
        history.save(_session(notes=f"n{i}"))
    rows = history.list(limit=3)
    assert len(rows) == 3
    assert [r["id"] for r in rows] == [5, 4, 3]


def test_list_empty_db(history):
    assert history.list() == []


def test_summary_counts_and_top_dtcs(history):
    history.save(_session(dtc_codes=["P0171"], urgency="atencao"))
    history.save(_session(dtc_codes=["P0171", "P0300"], urgency="critico"))
    history.save(_session(dtc_codes=[], urgency="informativo"))
    data = history.summary()
    assert data["total"] == 3
    assert data["critical"] == 1
    assert data["top_dtcs"][0] == ("P0171", 2)
    assert data["last"]["urgency"] == "informativo"


def test_summary_empty_db(history):
    data = history.summary()
    assert data["total"] == 0
    assert data["critical"] == 0
    assert data["last"] is None
    assert data["top_dtcs"] == []


def test_list_by_vin_filters_and_orders(history):
    v1 = "9BWAB47X0LP123456"
    v2 = "1G1JC5SH3D4100001"
    history.save(_session(vin=v1, notes="v1-a"))
    history.save(_session(vin=v2, notes="v2-a"))
    history.save(_session(vin=v1, notes="v1-b"))
    rows = history.list_by_vin(v1, limit=10)
    assert all(r["vin"] == v1 for r in rows)
    assert len(rows) == 2
    assert [r["id"] for r in rows] == [3, 1]


def test_list_by_vin_empty_or_unknown(history):
    assert history.list_by_vin("") == []
    assert history.list_by_vin("NONEXISTENT") == []


def test_list_vehicles_groups_by_vin(history):
    v1 = "9BWAB47X0LP123456"
    v2 = "1G1JC5SH3D4100001"
    history.save(_session(vin=v1, vehicle_label="VW 2020", urgency="atencao",
                          ts="01/07/2026 10:00"))
    history.save(_session(vin=v2, vehicle_label="GM 2013", urgency="informativo",
                          ts="02/07/2026 10:00"))
    history.save(_session(vin=v1, vehicle_label="VW 2020", urgency="critico",
                          ts="03/07/2026 10:00"))
    history.save(_session(vin="", vehicle_label="sem vin", urgency="informativo",
                          ts="04/07/2026 10:00"))
    vehicles = history.list_vehicles()
    vins = [v["vin"] for v in vehicles]
    assert "" not in vins
    assert vins == [v1, v2]
    vw = next(v for v in vehicles if v["vin"] == v1)
    assert vw["session_count"] == 2
    assert vw["last_urgency"] == "critico"
    assert vw["vehicle_label"] == "VW 2020"


def test_list_vehicles_empty(history):
    assert history.list_vehicles() == []


def test_update_session_notes_only(history):
    sid = history.save(_session(notes="antes", tags=None))
    updated = history.update_session(sid, notes="depois")
    assert updated is not None
    assert updated["notes"] == "depois"
    assert updated["tags"] is None
    row = history.get(sid)
    assert row["notes"] == "depois"


def test_update_session_tags_roundtrip(history):
    sid = history.save(_session(tags=None, notes=""))
    tags = ["troca de oleo", "P0171", "vw gol"]
    updated = history.update_session(sid, tags=tags)
    assert updated is not None
    assert updated["tags"] == tags
    assert updated["notes"] == ""


def test_update_session_missing_sid(history):
    assert history.update_session(9999, notes="x") is None


def test_tags_migration_incremental(tmp_path):
    """Banco criado sem coluna tags/freeze_frame sofre upgrade incremental."""
    import sqlite3

    db_path = tmp_path / "old.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY, ts TEXT, vin TEXT, vehicle_label TEXT,"
        " dtc_codes TEXT, urgency TEXT, rpm INTEGER, speed INTEGER, coolant_temp INTEGER,"
        " maf REAL, fuel_trim_short REAL, fuel_trim_long REAL, o2 REAL, diagnosis TEXT,"
        " cost_min INTEGER, cost_max INTEGER, km INTEGER, notes TEXT)"
    )
    con.execute(
        "INSERT INTO sessions VALUES (1, 't', 'VIN','', '[]','info',1,2,3,4,5,6,7,'',8,9,10,'n')"
    )
    con.commit()
    con.close()

    with History(path=db_path) as hist:
        row = hist.get(1)
        assert row is not None
        assert row["tags"] is None
        assert row["freeze_frame"] is None

        sid2 = hist.save(_session(tags=["novo"], freeze_frame={"rpm": 2400}))
        r2 = hist.get(sid2)
        assert r2 is not None
        assert r2["tags"] == ["novo"]
        assert r2["freeze_frame"] == {"rpm": 2400}


def test_freeze_frame_roundtrip(history):
    ff = {
        "dtc_code": "P0171", "rpm": 1720, "coolant_temp_c": 98,
        "fuel_trim_short_b1": 18.8, "raw": "42 02 ...",
    }
    sid = history.save(_session(freeze_frame=ff))
    row = history.get(sid)
    assert row["freeze_frame"] == ff
    listed = history.list(limit=1)[0]
    assert listed["freeze_frame"] == ff


def test_readiness_roundtrip(history):
    rd = {
        "ignition": "spark",
        "monitors": {"Catalisador": False, "Sistema EVAP": False},
        "incomplete": ["Catalisador", "Sistema EVAP"],
        "distance_since_clear_km": 7,
        "clear_assessment": {"verdict": "suspeito", "confidence": "alta"},
    }
    sid = history.save(_session(readiness=rd))
    row = history.get(sid)
    assert row is not None
    assert row["readiness"] == rd


def test_readiness_column_migrates_on_old_db(tmp_path):
    import sqlite3

    db_path = tmp_path / "old2.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY, ts TEXT, vin TEXT, vehicle_label TEXT,"
        " dtc_codes TEXT, urgency TEXT, rpm INTEGER, speed INTEGER, coolant_temp INTEGER,"
        " maf REAL, fuel_trim_short REAL, fuel_trim_long REAL, o2 REAL, diagnosis TEXT,"
        " cost_min INTEGER, cost_max INTEGER, km INTEGER, notes TEXT)"
    )
    con.commit()
    con.close()

    with History(path=db_path) as hist:
        sid = hist.save(_session(readiness={"monitors": {"Catalisador": True}}))
        row = hist.get(sid)
        assert row is not None
        assert row["readiness"] == {"monitors": {"Catalisador": True}}
