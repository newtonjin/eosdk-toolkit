r"""Resolucao de caminhos para dev-mode e frozen (PyInstaller).

Dev mode:
  APP_DATA_ROOT = BUNDLED_ROOT = repo root

Frozen:
  BUNDLED_ROOT  = _MEIPASS (somente-leitura, extraido pelo PyInstaller)
  APP_DATA_ROOT = onde defaults.json / profiles / known_offsets sao escritos

  Precedencia para APP_DATA_ROOT (frozen):
    1. $EOSLANKIT_DATA        (override manual)
    2. <exe_dir>\EOSLANKitData\ se ja existe   (modo portable)
    3. %LOCALAPPDATA%\EOSLANKit\
    4. fallback <exe_dir>\EOSLANKitData\ (cria)

Dados do usuario NUNCA ficam dentro de dist\EOSLANKit\ para o PyInstaller
poder limpar essa pasta em rebuilds sem conflito de arquivos travados.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _dev_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundled_root() -> Path:
    """Assets read-only. Frozen: _MEIPASS. Dev: repo root."""
    if is_frozen():
        mp = getattr(sys, "_MEIPASS", None)
        if mp:
            return Path(mp)
    return _dev_root()


def app_data_root() -> Path:
    """Onde config/, profiles/, build/ (proxy DLL compilada) sao escritos."""
    if not is_frozen():
        return _dev_root()

    env = (os.environ.get("EOSLANKIT_DATA") or "").strip()
    if env:
        return Path(env)

    try:
        exe_dir = Path(sys.executable).resolve().parent
    except OSError:
        exe_dir = Path.cwd()

    portable = exe_dir / "EOSLANKitData"
    if portable.exists():
        return portable

    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        return Path(localappdata) / "EOSLANKit"

    return portable  # sera criado on-demand


# Compat: modulos legados importam app_root
def app_root() -> Path:
    return app_data_root()


APP_ROOT = app_data_root()
APP_DATA_ROOT = APP_ROOT
BUNDLED_ROOT = bundled_root()


_SEED_FILES = (
    ("config/defaults.json",       True),   # editable
    ("config/intercepted.json",    True),   # pode ser customizada
    ("config/known_offsets.json",  True),
)


def ensure_user_assets(subdirs: tuple[str, ...] = ()) -> list[Path]:
    """Semeia arquivos default do bundle para APP_DATA_ROOT na primeira execucao.

    Cria a estrutura:
        <app_data>/config/defaults.json
        <app_data>/config/intercepted.json
        <app_data>/config/known_offsets.json
        <app_data>/config/profiles/     (vazio)
        <app_data>/build/               (vazio)

    Nao copia src/ nem build/build.ps1 (leitura via BUNDLED_ROOT).
    """
    copied: list[Path] = []
    if not is_frozen():
        return copied

    data = app_data_root()
    try:
        (data / "config" / "profiles").mkdir(parents=True, exist_ok=True)
        (data / "build").mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    bundle = bundled_root()
    for rel, _ in _SEED_FILES:
        src = bundle / rel
        dst = data / rel
        if src.is_file() and not dst.exists():
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(dst)
            except OSError:
                pass
    return copied
