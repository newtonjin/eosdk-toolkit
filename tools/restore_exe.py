#!/usr/bin/env python3
"""Restaura executavel a partir do backup .eoslankit.bak"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def restore_exe(exe_path: Path) -> Path:
    backup = exe_path.with_suffix(exe_path.suffix + ".eoslankit.bak")
    if not backup.exists():
        raise FileNotFoundError(f"Backup nao encontrado: {backup}")
    shutil.copy2(backup, exe_path)
    return exe_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Restaura EXE original")
    ap.add_argument("--exe", required=True)
    args = ap.parse_args()
    exe = Path(args.exe)
    try:
        restore_exe(exe)
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print(f"Restaurado: {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
