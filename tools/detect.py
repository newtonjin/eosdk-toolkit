#!/usr/bin/env python3
"""Detecta subsistema EOS (EOSSDK) em qualquer jogo UE/Steam."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from config_loader import load_config

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class EosTarget:
    path: Path
    library_name: str
    is_proxy_installed: bool
    has_backup: bool
    export_count: int | None = None
    size_bytes: int = 0

    @property
    def status(self) -> str:
        if self.is_proxy_installed:
            return "Proxy instalada"
        if self.has_backup:
            return "Backup presente"
        return "Original"


@dataclass
class ExeTarget:
    path: Path
    has_eos_delay_import: bool
    patchable_functions: list[str] = field(default_factory=list)
    is_patched: bool = False
    backup_exists: bool = False
    sha256: str = ""


@dataclass
class SteamworksHit:
    win_dir: Path                # .../Steamv153/Win64/
    has_goldberg: bool = False   # se ja tem steam_api64 tipo Goldberg


@dataclass
class GameScan:
    game_root: Path
    input_path: Path
    eos_targets: list[EosTarget]
    exe_targets: list[ExeTarget]
    steamworks_dirs: list[SteamworksHit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def primary_eos(self) -> EosTarget | None:
        return self.eos_targets[0] if self.eos_targets else None

    @property
    def primary_exe(self) -> ExeTarget | None:
        for exe in self.exe_targets:
            if exe.has_eos_delay_import:
                return exe
        return self.exe_targets[0] if self.exe_targets else None

    def summary_lines(self) -> list[str]:
        lines = [f"Raiz detectada: {self.game_root}"]
        if not self.eos_targets:
            lines.append("EOSSDK: nao encontrada")
        else:
            lines.append(f"EOSSDK: {len(self.eos_targets)} candidato(s)")
            for eos in self.eos_targets:
                lines.append(f"  - {eos.path.name} [{eos.status}] ({eos.size_bytes // 1024} KB)")
        if not self.exe_targets:
            lines.append("Executavel: nao encontrado")
        else:
            lines.append(f"Executaveis: {len(self.exe_targets)} candidato(s)")
            for exe in self.exe_targets[:5]:
                flags = []
                if exe.has_eos_delay_import:
                    flags.append("delay-import EOS")
                if exe.is_patched:
                    flags.append("patchado")
                if exe.backup_exists:
                    flags.append("backup")
                extra = f" ({', '.join(flags)})" if flags else ""
                lines.append(f"  - {exe.path.name}{extra}")
        if self.steamworks_dirs:
            lines.append(f"Steamworks: {len(self.steamworks_dirs)} path(s)")
            for sw in self.steamworks_dirs:
                tag = " [Goldberg]" if sw.has_goldberg else ""
                lines.append(f"  - {sw.win_dir}{tag}")
        for w in self.warnings:
            lines.append(f"AVISO: {w}")
        return lines

    def summary(self) -> str:
        return "\n".join(self.summary_lines())


def _find_game_root(path: Path) -> Path:
    """Sobe ate encontrar diretorio com Engine/ (marca padrao UE)."""
    p = path.resolve()
    if p.is_file():
        p = p.parent

    cur = p
    for _ in range(10):
        if not cur.exists():
            break
        try:
            names = {c.name for c in cur.iterdir() if c.is_dir()}
        except OSError:
            break
        if "Engine" in names:
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return p


def _game_binary_win_dirs(root: Path) -> list[Path]:
    """
    Retorna todos os subdirs <Something>/Binaries/Win64|Win32 dentro do root.
    Cobre Palworld (Pal/), ShooterGame, JogosCustom, etc, sem depender de nome fixo.
    """
    out: list[Path] = []
    try:
        for child in root.iterdir():
            if not child.is_dir() or child.name in {"Engine", "steam_settings"}:
                continue
            for arch in ("Win64", "Win32"):
                cand = child / "Binaries" / arch
                if cand.is_dir():
                    out.append(cand)
    except OSError:
        pass
    for arch in ("Win64", "Win32"):
        cand = root / "Binaries" / arch
        if cand.is_dir():
            out.append(cand)
    for arch in ("Win64", "Win32"):
        cand = root / "Engine" / "Binaries" / arch
        if cand.is_dir():
            out.append(cand)
    return out


def _eos_candidates(root: Path) -> list[Path]:
    """DLLs EOSSDK* nos diretorios binarios do jogo (rapido)."""
    hits: list[Path] = []
    for win_dir in _game_binary_win_dirs(root):
        try:
            for hit in win_dir.iterdir():
                if hit.is_file() and hit.name.upper().startswith("EOSSDK") and hit.suffix.lower() == ".dll":
                    hits.append(hit)
        except OSError:
            pass
    # Fallback glob se nada achado
    if not hits:
        try:
            for hit in root.glob("**/EOSSDK*.dll"):
                hits.append(hit)
                if len(hits) >= 12:
                    break
        except OSError:
            pass
    return hits


def _shipping_candidates(root: Path) -> list[Path]:
    hits: list[Path] = []
    for win_dir in _game_binary_win_dirs(root):
        try:
            for hit in win_dir.iterdir():
                if hit.is_file() and hit.suffix.lower() == ".exe" and "Shipping" in hit.name:
                    hits.append(hit)
        except OSError:
            pass
    return hits


def _steamworks_candidates(root: Path) -> list[SteamworksHit]:
    hits: list[SteamworksHit] = []
    for pattern in (
        "Engine/Binaries/ThirdParty/Steamworks/Steamv*/Win64",
        "Engine/Binaries/ThirdParty/Steamworks/Steamv*/Win32",
        "Binaries/ThirdParty/Steamworks/Steamv*/Win64",
    ):
        try:
            for hit in root.glob(pattern):
                if not hit.is_dir():
                    continue
                dll = hit / "steam_api64.dll"
                has_g = False
                if dll.is_file():
                    try:
                        blob = dll.read_bytes()
                        has_g = any(m in blob for m in (b"Goldberg", b"GBE Fork", b"gbe_fork"))
                    except OSError:
                        has_g = False
                hits.append(SteamworksHit(hit, has_g))
        except OSError:
            pass
    return hits


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _rank_eos(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    score = 0
    if "win64" in name:
        score += 20
    if "shipping" in name:
        score += 10
    if "_orig" in name:
        score -= 5
    return (-score, name)


def _build_eos_target(path: Path, cfg: dict) -> EosTarget:
    proxy_max = int(cfg.get("proxy_max_size_bytes", 524288))
    backup_name = cfg["orig_dll_name"]
    backup = path.parent / backup_name
    size = path.stat().st_size
    is_proxy = size <= proxy_max and backup.exists()
    library_name = path.stem
    if path.stem.endswith("_orig"):
        for sibling in sorted(path.parent.glob("EOSSDK*.dll")):
            if sibling == path or sibling.name == backup_name:
                continue
            if sibling.stat().st_size > proxy_max:
                library_name = sibling.stem
                break
        else:
            library_name = path.stem[: -len("_orig")] + "-Win64-Shipping"
    return EosTarget(
        path=path,
        library_name=library_name,
        is_proxy_installed=is_proxy,
        has_backup=backup.exists(),
        export_count=None,
        size_bytes=size,
    )


def _analyze_exe(path: Path, quick: bool = True) -> ExeTarget:
    has_delay = False
    patchable: list[str] = []
    is_patched = False
    backup_new = path.with_suffix(path.suffix + ".eoslankit.bak")
    backup_legacy = path.with_suffix(path.suffix + ".original_backup")

    if not quick:
        try:
            from patch_utils import exe_patch_status

            has_delay, patchable, is_patched = exe_patch_status(path, quick=False)
        except Exception:
            pass

    return ExeTarget(
        path=path,
        has_eos_delay_import=has_delay,
        patchable_functions=patchable,
        is_patched=is_patched,
        backup_exists=backup_new.exists() or backup_legacy.exists(),
        sha256="",
    )


def scan_game(path: str | Path, compute_sha: bool = False) -> GameScan:
    cfg = load_config()
    input_path = Path(path).resolve()
    game_root = _find_game_root(input_path)
    warnings: list[str] = []

    eos_files = _eos_candidates(game_root)

    # Preferir DLL ativa (nao backup _orig) para instalacao
    active = [p for p in eos_files if not p.stem.endswith("_orig")]
    if not active and eos_files:
        active = eos_files
    ranked = sorted(set(active), key=_rank_eos)
    eos_targets = [_build_eos_target(p, cfg) for p in ranked]

    if not eos_targets:
        warnings.append("Nenhuma EOSSDK encontrada. Jogo pode nao usar Epic Online Services.")

    exe_files = _shipping_candidates(game_root)
    if input_path.is_file() and input_path.suffix.lower() == ".exe" and input_path not in exe_files:
        exe_files.insert(0, input_path)

    exe_targets: list[ExeTarget] = []
    for p in sorted(set(exe_files), key=lambda x: x.name.lower())[:6]:
        et = _analyze_exe(p, quick=True)
        if compute_sha:
            et.sha256 = _sha256(p)
        exe_targets.append(et)

    steamworks = _steamworks_candidates(game_root)

    if eos_targets and any(not e.has_eos_delay_import for e in exe_targets):
        warnings.append("Patch EXE: sera tentado via known_offsets se delay-import EOS ausente.")

    return GameScan(game_root, input_path, eos_targets, exe_targets, steamworks, warnings)


def source_dll_for_build(eos: EosTarget, cfg: dict | None = None) -> Path:
    """Retorna a DLL original usada para gerar exports (backup se proxy ja instalada)."""
    cfg = cfg or load_config()
    backup = eos.path.parent / cfg["orig_dll_name"]
    if eos.is_proxy_installed and backup.exists():
        return backup
    if eos.path.stem.endswith("_orig"):
        return eos.path
    if eos.size_bytes <= int(cfg.get("proxy_max_size_bytes", 524288)) and backup.exists():
        return backup
    return eos.path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: detect.py <pasta_do_jogo|exe> [--sha]")
        raise SystemExit(1)
    do_sha = "--sha" in sys.argv
    print(scan_game(sys.argv[1], compute_sha=do_sha).summary())
