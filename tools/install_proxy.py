#!/usr/bin/env python3
"""Instala proxy EOS compilada no diretório do jogo."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from config_loader import load_config
from detect import scan_game


_ID_LEN = 32  # Epic/Product IDs no EOS sao ~32 hex chars.


def _derive_id(prefix: str, steam_id: str, account_name: str) -> str:
    """Deriva um ID estavel de 32 chars a partir do SteamID + nick.

    Mesmo SteamID+nick -> mesmo ID (consistente entre execucoes).
    SteamIDs distintos -> IDs distintos (players separados no LAN).
    """
    seed = f"{prefix}|{steam_id or ''}|{account_name or ''}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:_ID_LEN].upper()


def write_id_file(dll_path: Path, steam_id: str = "", account_name: str = "") -> Path:
    """Escreve <dll>.eoslkid com 2 linhas: EpicId, ProductId."""
    epic = _derive_id("EPIC", steam_id, account_name)
    prod = _derive_id("PROD", steam_id, account_name)
    id_path = dll_path.with_suffix(dll_path.suffix + ".eoslkid")
    id_path.write_text(f"{epic}\n{prod}\n", encoding="ascii")
    return id_path


def install_proxy(
    game_path: Path,
    proxy_dll: Path,
    eos_dll: Path | None = None,
    force: bool = False,
    steam_id: str = "",
    account_name: str = "",
) -> Path:
    scan = scan_game(game_path)
    target = eos_dll
    if target is None:
        if not scan.primary_eos:
            raise FileNotFoundError("EOSSDK nao encontrada na pasta do jogo")
        target = scan.primary_eos.path

    target = Path(target).resolve()
    cfg = load_config()
    orig_name = cfg["orig_dll_name"]
    target_dir = target.parent
    backup = target_dir / orig_name

    if not backup.exists():
        print(f"[1] Backup: {target.name} -> {orig_name}")
        shutil.copy2(target, backup)
    else:
        print(f"[1] Backup ja existe: {backup}")

    if target.resolve() == proxy_dll.resolve() and not force:
        print("[2] Proxy ja instalada (mesmo arquivo)")
    else:
        dest = target_dir / target.name
        print(f"[2] Instalando proxy -> {dest}")
        shutil.copy2(proxy_dll, dest)
        target = dest

    id_file = write_id_file(target, steam_id=steam_id, account_name=account_name)
    print(f"[3] IDs EOS escritos -> {id_file.name}")
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description="Instala EOSSDK proxy no jogo")
    ap.add_argument("--game", required=True, help="Pasta do jogo ou EXE")
    ap.add_argument("--proxy", required=True, help="Caminho da proxy compilada")
    ap.add_argument("--eos-dll", default="", help="EOSSDK alvo (opcional)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--steam-id", default="", help="SteamID64 para derivar Epic/Product IDs")
    ap.add_argument("--account-name", default="", help="Nick para derivar Epic/Product IDs")
    args = ap.parse_args()

    proxy = Path(args.proxy)
    if not proxy.is_file():
        print(f"ERRO: proxy nao encontrada: {proxy}", file=sys.stderr)
        return 1

    eos = Path(args.eos_dll) if args.eos_dll else None
    try:
        dest = install_proxy(Path(args.game), proxy, eos_dll=eos, force=args.force,
                             steam_id=args.steam_id, account_name=args.account_name)
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    print(f"\nInstalado: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
