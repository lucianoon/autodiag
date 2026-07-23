"""Testes do histórico SQLite (autodiag.db.history) usando banco temporário."""
import pytest

from autodiag.db.history import History, Session


def _session(**overrides) -> Session:
    base = dict(
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
    return History(path=tmp_path / "history.db")


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
