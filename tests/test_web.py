"""Testes da API web (autodiag.web.server) com TestClient e banco isolado."""
import pytest
from fastapi.testclient import TestClient

from autodiag.web.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTODIAG_DB_PATH", str(tmp_path / "history.db"))
    with TestClient(app) as c:
        yield c


def test_index_serves_html_with_manifest(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "manifest.webmanifest" in resp.text
    assert 'name="viewport"' in resp.text


def test_manifest_is_served_and_valid(client):
    resp = client.get("/static/manifest.webmanifest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AutoDiag OBD2"
    assert data["display"] == "standalone"
    assert data["icons"]


def test_icon_is_served(client):
    resp = client.get("/static/icon.svg")
    assert resp.status_code == 200
    assert "svg" in resp.headers["content-type"]


def test_dtc_detail_resolves_catalog_code(client):
    resp = client.get("/api/dtc/p0310")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "P0310"
    assert "cilindro 10" in data["description"]


def test_dtc_detail_unknown_code_is_404(client):
    assert client.get("/api/dtc/P9999").status_code == 404


def test_dtc_search_covers_catalog(client):
    resp = client.get("/api/dtc", params={"q": "U015"})
    assert resp.status_code == 200
    codes = [r["code"] for r in resp.json()]
    assert "U0151" in codes


def test_summary_empty_db(client):
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_patch_missing_session_returns_404(client):
    resp = client.patch("/api/session/999", json={})
    assert resp.status_code == 404
    resp = client.patch("/api/session/999", json={"notes": "x"})
    assert resp.status_code == 404
