from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_DIR_LOCK = threading.Lock()
_OVERRIDE_DIR: Path | None = None

PERSONA_MECHANIC = "mechanic"
PERSONA_SHOP_BOSS = "shop_boss"
PERSONA_INSPECTOR = "inspector"
PERSONA_FLEET = "fleet"
PERSONA_EV_SPECIALIST = "ev_specialist"

PERSONAS_META: dict[str, dict[str, str]] = {
    PERSONA_MECHANIC: {
        "label": "Mecânico",
        "emoji": "🔧",
        "tagline": "Diagnóstico no veículo, rápido e preciso",
        "default_home_tab": "scan",
    },
    PERSONA_SHOP_BOSS: {
        "label": "Dono(a) de Oficina",
        "emoji": "🏪",
        "tagline": "Painel de controle da oficina: faturamento, KPIs, tendências",
        "default_home_tab": "dashboard",
    },
    PERSONA_INSPECTOR: {
        "label": "Vistoriador Seminovos",
        "emoji": "🔍",
        "tagline": "Checklist de compra, relatórios limpos e prontos para o cliente",
        "default_home_tab": "report",
    },
    PERSONA_FLEET: {
        "label": "Gestor(a) de Frota",
        "emoji": "🚚",
        "tagline": "Histórico de cada veículo, custos e prevenção",
        "default_home_tab": "evolucao",
    },
    PERSONA_EV_SPECIALIST: {
        "label": "Eletricista VE/BEV Alta Tensão",
        "emoji": "🔋",
        "tagline": "SoC, SoH, temp. célula BMS, motor tração, carga CC/CA",
        "default_home_tab": "scan",
    },
}

DEFAULT_PERSONA = PERSONA_MECHANIC


def list_personas() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for key, meta in PERSONAS_META.items():
        out.append({"id": key, **meta})
    return out


def _resolve_dir() -> Path:
    env = os.environ.get("AUTODIAG_HOME")
    if env:
        return Path(env)
    with _DEFAULT_DIR_LOCK:
        global _OVERRIDE_DIR
        if _OVERRIDE_DIR is not None:
            return _OVERRIDE_DIR
        return Path.home() / ".autodiag"


def set_config_root(path: Path | str) -> None:
    """Override global config root (for tests)."""
    with _DEFAULT_DIR_LOCK:
        global _OVERRIDE_DIR
        _OVERRIDE_DIR = Path(path)


DEFAULT_CONFIG_PATH = _resolve_dir() / "config.json"


def _default_path() -> Path:
    return _resolve_dir() / "config.json"


@dataclass
class Branding:
    workshop_name: str = ""
    mechanic_name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    logo_url: str = ""
    notes_header: str = ""


@dataclass
class AppConfig:
    branding: Branding = field(default_factory=Branding)
    persona: str = DEFAULT_PERSONA
    persona_selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "branding": asdict(self.branding),
            "persona": self.persona,
            "persona_selected": bool(self.persona_selected),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        b_data = (data or {}).get("branding") or {}
        fields = Branding.__dataclass_fields__
        branding = Branding(**{k: b_data.get(k, "") for k in fields})
        raw_persona = str((data or {}).get("persona") or "").strip()
        persona = (
            raw_persona if raw_persona in PERSONAS_META else DEFAULT_PERSONA
        )
        persona_selected = bool((data or {}).get("persona_selected"))
        return cls(
            branding=branding,
            persona=persona,
            persona_selected=persona_selected,
        )


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> AppConfig:
    p = Path(path) if path else _default_path()
    if not p.exists():
        return AppConfig()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return AppConfig.from_dict(raw or {})
    except (json.JSONDecodeError, OSError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    p = Path(path) if path else _default_path()
    _ensure_dir(p.parent)
    p.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def get_branding() -> Branding:
    return load_config().branding


def get_persona() -> str:
    cfg = load_config()
    return cfg.persona if cfg.persona in PERSONAS_META else DEFAULT_PERSONA


def set_persona(persona_id: str, *, mark_selected: bool = True) -> str:
    key = str(persona_id or "").strip()
    if key not in PERSONAS_META:
        key = DEFAULT_PERSONA
    cfg = load_config()
    cfg.persona = key
    if mark_selected:
        cfg.persona_selected = True
    save_config(cfg)
    return key


_MAX_FIELD_LEN = 160


def _is_safe_logo_url(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    safe_prefixes = (
        "http://",
        "https://",
        "data:image/png;base64,",
        "data:image/jpeg;base64,",
        "data:image/svg+xml;base64,",
    )
    if v.startswith(safe_prefixes):
        return len(v) <= 2000
    return False


def _clean_branding_patch(patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    fields = Branding.__dataclass_fields__
    for k, v in (patch or {}).items():
        if k not in fields or not isinstance(v, str):
            continue
        cleaned = v.strip()
        if len(cleaned) > _MAX_FIELD_LEN:
            cleaned = cleaned[:_MAX_FIELD_LEN]
        if k == "logo_url":
            if not _is_safe_logo_url(cleaned):
                cleaned = ""
        out[k] = cleaned
    return out


def update_branding(patch: dict[str, Any]) -> Branding:
    cfg = load_config()
    cleaned = _clean_branding_patch(patch)
    for k, v in cleaned.items():
        setattr(cfg.branding, k, v)
    save_config(cfg)
    return cfg.branding
