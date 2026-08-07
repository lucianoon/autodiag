from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_DIR_LOCK = threading.Lock()
_OVERRIDE_DIR: Path | None = None


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

    def to_dict(self) -> dict[str, Any]:
        return {"branding": asdict(self.branding)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        b_data = (data or {}).get("branding") or {}
        fields = Branding.__dataclass_fields__
        return cls(branding=Branding(**{k: b_data.get(k, "") for k in fields}))


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
