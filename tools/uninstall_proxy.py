#!/usr/bin/env python3
"""Restaura EOSSDK original (remove proxy)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from config_loader import load_config


def uninstall_proxy(eos_dll: Path) -> Path:
    cfg = load_config()
    orig_name = cfg["orig_dll_name"]
    backup = eos_dll.parent / orig_name
    if not backup.exists():
        raise FileNotFoundError(f"Backup nao encontrado: {backup}")

    dest = eos_dll
    import shutil

    print(f"Restaurando {orig_name} -> {dest.name}")
    shutil.copy2(backup, dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Restaura EOSSDK original")
    ap.add_argument("--eos-dll", required=True, help="Caminho da EOSSDK ativa no jogo")
    args = ap.parse_args()

    try:
        dest = uninstall_proxy(Path(args.eos_dll))
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print(f"Restaurado: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
