"""Carrega configuracao compartilhada do EOSLANKit."""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from paths import app_root as _app_root, bundled_root as _bundled_root


def _resolve_config_path() -> Path:
    """Prefere config editavel ao lado do .exe; se nao existir, usa o do bundle."""
    disk = _app_root() / "config" / "intercepted.json"
    if disk.exists():
        return disk
    return _bundled_root() / "config" / "intercepted.json"


CONFIG_PATH = _resolve_config_path()


@lru_cache(maxsize=1)
def load_config() -> dict:
    return json.loads(_resolve_config_path().read_text(encoding="utf-8"))
