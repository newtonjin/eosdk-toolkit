#!/usr/bin/env python3
"""Instala Goldberg steam_api64.dll em todos os caminhos Steamworks do jogo.

Fonte da DLL pode ser:
  1. Path informado (parametro / GUI)
  2. defaults.json: goldberg_dll_source
  3. steam_api64.dll ja presente na raiz do jogo (se claramente Goldberg)
  4. Backup steam_api64.dll.orig ao lado de uma instalacao previa
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from config_loader import load_config
from paths import app_root as _app_root

DEFAULTS_PATH = _app_root() / "config" / "defaults.json"
BACKUP_SUFFIX = ".steamorig"


def _defaults() -> dict:
    if DEFAULTS_PATH.exists():
        return json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    return {}


def save_default_source(dll_path: Path) -> None:
    """Persiste o caminho fonte para uso futuro."""
    data = _defaults()
    data["goldberg_dll_source"] = str(dll_path)
    DEFAULTS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_like_goldberg(path: Path) -> bool:
    """Heuristica leve: DLLs Goldberg tem string 'Goldberg' em algum lugar."""
    if not path.is_file():
        return False
    try:
        blob = path.read_bytes()
    except OSError:
        return False
    for needle in (b"Goldberg", b"GBE Fork", b"gbe_fork", b"Nemirtingas"):
        if needle in blob:
            return True
    return False


def _steamworks_dirs(game_root: Path, cfg: dict) -> list[Path]:
    """Todos os Steamv*/Win64 encontrados sob o jogo."""
    dirs: list[Path] = []
    globs = cfg.get("steamworks_search_globs", [])
    for pattern in globs:
        pattern = pattern.replace("\\", "/")
        try:
            for hit in game_root.glob(pattern):
                if hit.is_dir():
                    dirs.append(hit)
        except OSError:
            pass
    return dirs


def _extra_win64_dirs(game_root: Path) -> list[Path]:
    """Diretorios Win64 comuns onde ficam DLLs auxiliares (Pal/Binaries/Win64 etc)."""
    hits: list[Path] = []
    for name in ("Pal", "ShooterGame", "Game"):
        p = game_root / name / "Binaries" / "Win64"
        if p.is_dir():
            hits.append(p)
    p = game_root / "Binaries" / "Win64"
    if p.is_dir():
        hits.append(p)
    return hits


def goldberg_target_paths(game_root: Path) -> list[Path]:
    """
    Lista todos os alvos onde steam_api64.dll deve ser copiada.
    - Raiz do jogo
    - Todo Engine/Binaries/ThirdParty/Steamworks/Steamv*/Win64/
    - Pal/Binaries/Win64, Binaries/Win64 (jogos que carregam steam_api do binario)
    """
    cfg = load_config()
    root = Path(game_root).resolve()
    targets: list[Path] = [root]
    targets.extend(_steamworks_dirs(root, cfg))
    targets.extend(_extra_win64_dirs(root))
    # Dedup preservando ordem
    seen: set[Path] = set()
    out: list[Path] = []
    for d in targets:
        rp = d.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(d)
    return out


def discover_source(game_root: Path | None = None) -> Path | None:
    """
    Tenta descobrir automaticamente uma DLL Goldberg utilizavel.
    Ordem: defaults.goldberg_dll_source -> DLL na raiz do jogo (se Goldberg) -> backup .steamorig
    """
    defaults = _defaults()
    src = (defaults.get("goldberg_dll_source") or "").strip()
    if src:
        p = Path(src)
        if p.is_file() and _looks_like_goldberg(p):
            return p

    if game_root is not None:
        root = Path(game_root)
        for cand in (root / "steam_api64.dll", root / "steam_api.dll"):
            if _looks_like_goldberg(cand):
                return cand
    return None


@dataclass
class GoldbergResult:
    source: Path
    installed: list[Path] = field(default_factory=list)
    backups: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def install_goldberg(
    game_root: Path,
    source_dll: Path | None = None,
    dll_name: str = "steam_api64.dll",
    backup_originals: bool = True,
) -> GoldbergResult:
    """Copia a DLL Goldberg para todas as pastas Steamworks do jogo."""
    root = Path(game_root).resolve()
    src = source_dll or discover_source(root)
    if src is None:
        raise FileNotFoundError(
            "Fonte Goldberg nao encontrada. Configure defaults.goldberg_dll_source "
            "ou passe uma steam_api64.dll Goldberg como source_dll."
        )
    src = Path(src).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Goldberg DLL nao existe: {src}")

    src_hash = _sha256(src)
    result = GoldbergResult(source=src)

    for target_dir in goldberg_target_paths(root):
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / dll_name

        if dest.is_file():
            try:
                if _sha256(dest) == src_hash:
                    result.skipped.append((dest, "ja instalada (hash igual)"))
                    continue
            except OSError:
                pass
            if backup_originals:
                bak = dest.with_suffix(dest.suffix + BACKUP_SUFFIX)
                if not bak.exists() and not _looks_like_goldberg(dest):
                    shutil.copy2(dest, bak)
                    result.backups.append(bak)

        shutil.copy2(src, dest)
        result.installed.append(dest)

    return result


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Instala Goldberg steam_api64.dll no jogo")
    ap.add_argument("--game", required=True, help="Pasta do jogo")
    ap.add_argument("--source", default="", help="Caminho da steam_api64.dll Goldberg")
    ap.add_argument("--save-source", action="store_true", help="Persistir --source em defaults.json")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    src = Path(args.source).resolve() if args.source else None
    if src and args.save_source:
        save_default_source(src)

    try:
        result = install_goldberg(Path(args.game), src, backup_originals=not args.no_backup)
    except FileNotFoundError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print(f"Fonte: {result.source}")
    for p in result.installed:
        print(f"  OK    {p}")
    for p in result.backups:
        print(f"  BAK   {p}")
    for p, reason in result.skipped:
        print(f"  SKIP  {p}  ({reason})")
    print(f"\nInstalado em {len(result.installed)} caminho(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
