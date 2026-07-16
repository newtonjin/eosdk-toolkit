#!/usr/bin/env python3
"""Gera/atualiza steam_settings do Goldberg para o jogo detectado.

Escreve em todos os caminhos onde o Goldberg pode ler os configs:
  - Raiz do jogo
  - Engine/Binaries/ThirdParty/Steamworks/Steamv*/Win64/  (qualquer versao)
  - Pal/Binaries/Win64/, Binaries/Win64/ quando existirem
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from config_loader import ROOT, load_config
from paths import app_root as _app_root, bundled_root as _bundled_root


def _defaults_path() -> Path:
    disk = _app_root() / "config" / "defaults.json"
    if disk.exists():
        return disk
    return _bundled_root() / "config" / "defaults.json"


DEFAULTS_PATH = _defaults_path()


def load_defaults() -> dict:
    path = _defaults_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "default_steam_id": "76561197960287930",
        "default_account_name": "Player",
        "default_language": "brazilian",
        "default_ip_country": "BR",
        "default_broadcasts": ["25.255.255.255", "255.255.255.255"],
    }


def normalize_steam_id(raw: str, defaults: dict | None = None) -> str:
    defaults = defaults or load_defaults()
    s = (raw or "").strip()
    if not s:
        return str(defaults["default_steam_id"])
    digits = re.sub(r"\D", "", s)
    if len(digits) < 17:
        raise ValueError(f"SteamID invalido (precisa 17 digitos): {raw}")
    return digits


def steam_settings_dirs(game_root: Path) -> list[Path]:
    """Todas as pastas onde o Goldberg pode ler steam_settings."""
    cfg = load_config()
    root = Path(game_root).resolve()
    settings_name = cfg.get("steam_settings_dir_name", "steam_settings")

    dirs: list[Path] = [root / settings_name]

    # Steamworks Steamv*/Win64 (versao independente)
    for pattern in cfg.get("steamworks_search_globs", []):
        pattern = pattern.replace("\\", "/")
        try:
            for hit in root.glob(pattern):
                if hit.is_dir():
                    dirs.append(hit / settings_name)
        except OSError:
            pass

    # Diretorios de binarios com steam_api ao lado (UE convencional)
    for name in ("Pal", "ShooterGame", "Game"):
        win64 = root / name / "Binaries" / "Win64"
        if win64.is_dir():
            dirs.append(win64 / settings_name)
    win64 = root / "Binaries" / "Win64"
    if win64.is_dir():
        dirs.append(win64 / settings_name)

    # Dedup preservando ordem
    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        rp = d.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(d)
    return out


def configs_user_ini(account_name: str, steam_id: str, language: str, ip_country: str) -> str:
    return f"""[user::general]
account_name={account_name}
account_steamid={steam_id}
language={language}
ip_country={ip_country}

[user::saves]
local_save_path=./GSE Saves
saves_folder_name=GSE Saves
"""


def configs_main_ini() -> str:
    return """[main::general]
new_app_ticket=1
gc_token=1
block_unknown_clients=0

[main::connectivity]
offline=0
disable_lan_only=1
disable_networking=0
listen_port=47584
disable_lobby_creation=0
"""


def configs_app_ini(app_id: str) -> str:
    aid = (app_id or "").strip()
    path_line = f"{aid}=./" if aid else ""
    return f"""[app::general]
is_beta_branch=0
branch_name=public

[app::dlcs]
unlock_all=1

[app::paths]
{path_line}

[app::cloud_save::general]
create_default_dir=0
create_specific_dirs=0
"""


def custom_broadcasts_txt(entries: list[str]) -> str:
    lines = ["# Broadcast Goldberg para descoberta LAN (edite conforme sua VPN)"]
    for e in entries:
        e = (e or "").strip()
        if e:
            lines.append(e)
    return "\n".join(lines) + "\n"


def _read_app_id(root: Path) -> str:
    candidates = [
        root / "steam_appid.txt",
        root / "Pal" / "Binaries" / "Win64" / "steam_appid.txt",
        root / "Binaries" / "Win64" / "steam_appid.txt",
    ]
    for c in candidates:
        if c.is_file():
            try:
                v = c.read_text(encoding="utf-8", errors="ignore").strip()
                if v.isdigit():
                    return v
            except OSError:
                pass
    return ""


def apply_steam_settings(
    game_root: Path,
    steam_id: str = "",
    account_name: str = "",
    language: str = "",
    ip_country: str = "",
    app_id: str = "",
    broadcasts: list[str] | None = None,
) -> list[Path]:
    """
    Escreve steam_settings em todos os caminhos relevantes.
    Campos vazios usam defaults de config/defaults.json.
    """
    defaults = load_defaults()
    sid = normalize_steam_id(steam_id, defaults)
    name = (account_name or "").strip() or defaults.get("default_account_name", "Player")
    lang = (language or "").strip() or defaults.get("default_language", "brazilian")
    country = (ip_country or "").strip() or defaults.get("default_ip_country", "BR")
    bcs = broadcasts if broadcasts is not None else defaults.get("default_broadcasts", [])

    aid = (app_id or "").strip() or defaults.get("default_app_id", "") or _read_app_id(Path(game_root).resolve())

    user_ini = configs_user_ini(name, sid, lang, country)
    main_ini = configs_main_ini()
    app_ini = configs_app_ini(aid)
    broadcasts_body = custom_broadcasts_txt(bcs)

    written: list[Path] = []
    root = Path(game_root).resolve()

    for base in steam_settings_dirs(root):
        base.mkdir(parents=True, exist_ok=True)
        (base / "configs.user.ini").write_text(user_ini, encoding="utf-8")
        (base / "configs.main.ini").write_text(main_ini, encoding="utf-8")
        (base / "configs.app.ini").write_text(app_ini, encoding="utf-8")
        (base / "custom_broadcasts.txt").write_text(broadcasts_body, encoding="utf-8")
        if aid:
            (base / "steam_appid.txt").write_text(aid, encoding="utf-8")
        written.append(base)

    # steam_appid.txt tambem na raiz e em binarios (jogos leem local variado)
    if aid:
        appid_dests = [root / "steam_appid.txt"]
        for name in ("Pal", "ShooterGame", "Game"):
            p = root / name / "Binaries" / "Win64" / "steam_appid.txt"
            if p.parent.is_dir():
                appid_dests.append(p)
        p = root / "Binaries" / "Win64" / "steam_appid.txt"
        if p.parent.is_dir():
            appid_dests.append(p)
        for dest in appid_dests:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(aid, encoding="utf-8")

    return written


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: steam_settings.py <pasta_jogo> [steam_id] [account_name] [app_id]")
        raise SystemExit(1)
    paths = apply_steam_settings(
        Path(sys.argv[1]),
        steam_id=sys.argv[2] if len(sys.argv) > 2 else "",
        account_name=sys.argv[3] if len(sys.argv) > 3 else "",
        app_id=sys.argv[4] if len(sys.argv) > 4 else "",
    )
    for p in paths:
        print(f"OK: {p}")
