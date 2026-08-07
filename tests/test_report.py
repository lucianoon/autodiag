from typing import Any

import pytest

from autodiag.core.config import update_branding
from autodiag.core.report import build_report, render_report_html
from autodiag.db.history import History, Session


def _session(**overrides: Any) -> Session:
    base: dict[str, Any] = dict(
        id=None,
        ts="01/08/2026 10:00",
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
        notes="",
        triage={"headline": "Mistura pobre", "drive_advice": "cautela"},
    )
    base.update(overrides)
    return Session(**base)


@pytest.fixture
def history(tmp_path):
    with History(path=tmp_path / "history.db") as h:
        yield h


@pytest.fixture
def isolated_cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTODIAG_HOME", str(tmp_path))
    from autodiag.core.config import set_config_root

    set_config_root(tmp_path)
    yield


def test_previous_for_vin(history):
    first = history.save(_session(dtc_codes=["P0171"], rpm=750))
    second = history.save(_session(dtc_codes=["P0171", "P0300"], rpm=900))
    prev = history.previous_for_vin("9BWAB47X0LP123456", before_id=second)
    assert prev is not None
    assert prev["id"] == first
    assert prev["rpm"] == 750


def test_report_builds_diffs_and_renders_html(history):
    history.save(_session(dtc_codes=["P0171"], rpm=750))
    sid = history.save(_session(dtc_codes=["P0171", "P0300"], rpm=900))
    row = history.get(sid)
    assert row is not None
    prev = history.previous_for_vin(row["vin"], before_id=sid)
    rep = build_report(row, prev)
    assert "P0300" in rep.diff["dtc_added"]
    html = render_report_html(rep)
    assert f"Relatório #{sid}" in html
    assert f"/report/{sid}/download" in html
    assert "P0300" in html


def test_branding_renders_workshop_name_in_html(history, isolated_cfg):
    update_branding({
        "workshop_name": "Oficina do Pedrão",
        "mechanic_name": "Pedrão",
        "phone": "(11) 98888-0000",
    })
    sid = history.save(_session())
    row = history.get(sid)
    rep = build_report(row, None)
    html = render_report_html(rep)
    assert "Oficina do Pedrão" in html
    assert "Pedrão" in html
    assert "(11) 98888-0000" in html


def test_notes_block_renders_if_not_empty(history):
    tags = ["P0171", "troca filtro"]
    sid = history.save(
        _session(notes="Trocar filtro de combustível.", tags=tags)
    )
    row = history.get(sid)
    rep = build_report(row, None)
    html = render_report_html(rep)
    assert "Trocar filtro de combustível." in html
    assert "P0171" in html
    assert "troca filtro" in html


def test_freeze_frame_renders_in_html(history):
    sid = history.save(_session(freeze_frame={
        "dtc_code": "P0171",
        "rpm": 1720,
        "coolant_temp_c": 98,
        "fuel_trim_short_b1": 18.8,
    }))
    row = history.get(sid)
    rep = build_report(row, None)
    html = render_report_html(rep)
    assert "Freeze Frame" in html
    assert "P0171" in html
    assert "1720" in html


def test_cost_block_appears_with_dtcs_and_estimated_values(history):
    sid = history.save(_session(dtc_codes=["P0301", "P0171", "P0420"]))
    row = history.get(sid)
    rep = build_report(row, None)
    html = render_report_html(rep)
    assert "Orçamento estimado" in html
    assert "Faixa total:" in html
    # Deve conter pelo menos 3 códigos na tabela de detalhe
    for dtc in ("P0301", "P0171", "P0420"):
        assert dtc in html
    # Aviso legal sobre valores estimados Sudeste BR aparece no rodapé
    assert "Sudeste do Brasil" in html


def test_cost_block_shows_zero_when_no_dtcs(history):
    sid = history.save(_session(dtc_codes=[], cost_min=0, cost_max=0))
    row = history.get(sid)
    rep = build_report(row, None)
    html = render_report_html(rep)
    assert "Orçamento estimado" in html
    assert "Não há falhas identificadas" in html
    assert "R$ 0,00" in html

