#!/usr/bin/env python3
"""Perfil persistido por jogo (config/profiles/<hash>.json).

Guarda: game_root, shipping_exe, eos_dll, app_id, backups criados,
paths onde steam_settings foi escrito, launcher gerado. Serve para
reaplicar/restaurar sem re-detectar tudo.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from paths import app_root as _app_root

PROFILES_DIR = _app_root() / "config" / "profiles"


def profile_id(game_root: Path) -> str:
    return hashlib.sha1(str(Path(game_root).resolve()).lower().encode("utf-8")).hexdigest()[:16]


def profile_path(game_root: Path) -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR / f"{profile_id(game_root)}.json"


@dataclass
class GameProfile:
    game_root: str
    game_name: str = ""
    app_id: str = ""
    steam_id: str = ""
    account_name: str = ""
    shipping_exe: str = ""
    eos_dll: str = ""
    eos_backup: str = ""
    exe_backup: str = ""
    goldberg_source: str = ""
    goldberg_installed: list[str] = field(default_factory=list)
    steam_settings_dirs: list[str] = field(default_factory=list)
    launcher_bat: str = ""
    launcher_ps1: str = ""
    broadcasts: list[str] = field(default_factory=list)
    steamless_cli: str = ""
    steamless_backup: str = ""
    steamless_was_wrapped: bool = False
    last_apply: float = 0.0
    notes: str = ""


def load_profile(game_root: Path) -> GameProfile | None:
    p = profile_path(game_root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    fields = {f: data.get(f) for f in GameProfile.__dataclass_fields__.keys()}
    return GameProfile(**{k: v for k, v in fields.items() if v is not None})


def save_profile(profile: GameProfile) -> Path:
    profile.last_apply = time.time()
    p = profile_path(Path(profile.game_root))
    p.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")
    return p


def list_profiles() -> list[GameProfile]:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    out: list[GameProfile] = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            fields = {k: data.get(k) for k in GameProfile.__dataclass_fields__.keys()}
            out.append(GameProfile(**{k: v for k, v in fields.items() if v is not None}))
        except Exception:
            continue
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "show":
        prof = load_profile(Path(sys.argv[2]))
        print(json.dumps(asdict(prof), indent=2) if prof else "sem perfil")
    else:
        for prof in list_profiles():
            print(f"[{prof.game_name or '?'}] {prof.game_root} (app_id={prof.app_id})")
