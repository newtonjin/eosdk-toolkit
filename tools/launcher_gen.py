#!/usr/bin/env python3
"""Gera launcher Play-<Game>.bat no diretorio do jogo.

Comportamento:
  - Roda o executavel *-Shipping.exe direto (bypassa launcher da Steam/Epic)
  - Fixa steam_appid.txt ao lado do Shipping.exe se app_id fornecido
  - Prefere <name>-Unpacked.exe se existir (sobrevive a Steam validation/updates)
  - Zero PowerShell / zero API user32 -> nao dispara heuristica AV

Nota: versoes anteriores geravam um .ps1 com Add-Type + PostMessage(WM_KEYDOWN)
para fechar popups residuais do EOS. Windows Defender flagava como keylogger e
quarantenava o .bat + .ps1. Se aparecer popup EOS, o usuario dismiss manualmente.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from config_loader import load_config


BAT_TEMPLATE = r"""@echo off
:: EOSLANKit - Made By: n3sec (https://n3sec.com)
:: Launcher offline/LAN para {game_name}
title EOSLANKit - {game_name}
setlocal enabledelayedexpansion

set "GAME_ROOT=%~dp0"
set "SHIPPING_REL={shipping_rel}"
set "APP_ID={app_id}"

:: Prefere -Unpacked.exe se existir (sobrevive a Steam validation).
set "TARGET_EXE=%GAME_ROOT%!SHIPPING_REL!"
set "UNPACKED_EXE=%TARGET_EXE:.exe=-Unpacked.exe%"
if exist "!UNPACKED_EXE!" (
    set "TARGET_EXE=!UNPACKED_EXE!"
    echo Usando executavel unpacked persistente: !TARGET_EXE!
)

if not exist "!TARGET_EXE!" (
    echo ERRO: Executavel nao encontrado:
    echo   !TARGET_EXE!
    pause
    exit /b 1
)

:: steam_appid.txt ao lado do Shipping (necessario pro Goldberg).
if not "!APP_ID!"=="" (
    for %%I in ("!TARGET_EXE!") do set "EXE_DIR=%%~dpI"
    > "!EXE_DIR!steam_appid.txt" echo|set /p="!APP_ID!"
)

echo EOSLANKit - Made By: n3sec  ^|  https://n3sec.com
echo Executando: !TARGET_EXE!
start "" "!TARGET_EXE!"
endlocal
"""


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    return s or "Game"


def _game_name_from_shipping(shipping: Path) -> str:
    stem = shipping.stem  # ex: Palworld-Win64-Shipping
    m = re.match(r"^(.*)-Win\d+-Shipping$", stem)
    if m:
        return m.group(1)
    return stem.replace("-Shipping", "")


def generate_launcher(
    game_root: Path,
    shipping_exe: Path,
    app_id: str = "",
    game_name: str = "",
    dismiss_max: int = 3,
    timeout_sec: int = 120,
) -> tuple[Path, Path | None]:
    """Escreve Play-<Game>.bat em game_root. Retorna (bat, None).

    Legado: retornava (bat, ps1). O .ps1 foi removido porque Windows Defender
    quarantenava por causa de PostMessage(WM_KEYDOWN) + Add-Type user32.
    """
    del dismiss_max, timeout_sec  # legado, ignorado
    cfg = load_config()
    prefix = cfg.get("launcher_batch_prefix", "Play")

    root = Path(game_root).resolve()
    shipping = Path(shipping_exe).resolve()

    if not game_name:
        game_name = _game_name_from_shipping(shipping)
    safe = _safe_name(game_name)
    bat_name = f"{prefix}-{safe}.bat"
    bat_path = root / bat_name

    # Remove .ps1 legado se ainda existir (evita reincidencia de Defender).
    old_ps1 = root / f"{prefix}-{safe}.ps1"
    if old_ps1.exists():
        try:
            old_ps1.unlink()
        except OSError:
            pass

    try:
        shipping_rel = shipping.relative_to(root).as_posix().replace("/", "\\")
    except ValueError:
        shipping_rel = str(shipping)

    bat_body = BAT_TEMPLATE.format(
        game_name=game_name,
        shipping_rel=shipping_rel,
        app_id=app_id or "",
    )

    bat_path.write_text(bat_body, encoding="ascii")
    return bat_path, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera Play-<Game>.bat")
    ap.add_argument("--game", required=True, help="Pasta do jogo")
    ap.add_argument("--exe", required=True, help="Caminho do *-Shipping.exe")
    ap.add_argument("--app-id", default="")
    ap.add_argument("--name", default="", help="Nome do jogo (sobrescreve autodetect)")
    args = ap.parse_args()

    bat, _ = generate_launcher(Path(args.game), Path(args.exe), args.app_id, args.name)
    print(f"OK: {bat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
