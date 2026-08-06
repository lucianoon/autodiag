"""Testes de branding / app config local."""
from __future__ import annotations

import json

import pytest

from autodiag.core.config import (
    get_branding,
    load_config,
    save_config,
    update_branding,
)


@pytest.fixture
def cfg_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTODIAG_HOME", str(tmp_path))
    from autodiag.core.config import set_config_root

    set_config_root(tmp_path)
    return tmp_path


def test_default_branding_returns_empty(cfg_home):
    b = get_branding()
    assert b.workshop_name == ""
    assert b.notes_header == ""
    assert (cfg_home / "config.json").exists() is False


def test_roundtrip_update_branding(cfg_home):
    patch = {
        "workshop_name": "Oficina do Zé",
        "mechanic_name": "Zé Mecânico",
        "phone": "(11) 99999-1234",
        "email": "ze@oficina.ao",
        "address": "Rua das Oficinas, 123",
        "logo_url": "https://exemplo.com/logo.png",
        "notes_header": "Observações do seu amigo mecânico",
    }
    update_branding(patch)
    b = get_branding()
    for k, v in patch.items():
        assert getattr(b, k) == v
    cfg = load_config()
    assert cfg.branding.workshop_name == "Oficina do Zé"
    with open(cfg_home / "config.json", encoding="utf-8") as fh:
        raw = json.load(fh)
    assert raw["branding"]["phone"] == patch["phone"]


def test_update_branding_partial_and_empty_strings(cfg_home):
    update_branding({"workshop_name": "Garagem da Maria", "logo_url": "  "})
    assert get_branding().workshop_name == "Garagem da Maria"
    update_branding({"workshop_name": ""})
    assert get_branding().workshop_name == ""


def test_save_config_explicit(cfg_home):
    cfg = load_config()
    cfg.branding.mechanic_name = "Tia Maria"
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.branding.mechanic_name == "Tia Maria"
