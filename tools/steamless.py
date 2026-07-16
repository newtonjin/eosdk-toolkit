#!/usr/bin/env python3
"""Wrapper para Steamless.CLI.exe: detecta e remove DRM stub Steam do EXE.

Steamless.CLI nao vem embutido no EOSLANKit (licenca/tamanho). Aponte o caminho
via GUI ou defaults.json ->  steamless_cli_path. Download oficial:
  https://github.com/atom0s/Steamless

Fluxo:
  1. Detecta stub Steam DRM no EXE (markers no header/secoes .bind).
  2. Chama Steamless.CLI.exe --exe <exe> -> gera <exe>.unpacked.exe
  3. Backup do original como <exe>.steamdrm.bak
  4. Substitui <exe> pelo .unpacked.exe.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from paths import app_root as _app_root

DEFAULTS_PATH = _app_root() / "config" / "defaults.json"
BACKUP_SUFFIX = ".steamdrm.bak"


def _defaults() -> dict:
    if DEFAULTS_PATH.exists():
        try:
            return json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_default_cli(cli_path: Path) -> None:
    data = _defaults()
    data["steamless_cli_path"] = str(cli_path)
    DEFAULTS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------- Deteccao do DRM ----------

# Markers usados por Steamless para reconhecer variantes do stub Steam DRM.
# Presenca desses bytes/strings em qualquer secao indica EXE wrapped.
_DRM_MARKERS = (
    b".bind",           # secao .bind (Steam Stub v2/v3)
    b"SteamStub",
    b".stub",
    b"kernel32.dll\x00LoadLibraryA",  # combinacao comum em stubs unpackers
)


def detect_steam_drm(exe_path: Path) -> tuple[bool, str]:
    """
    Retorna (is_wrapped, evidence). Nao roda Steamless — so olha bytes rapidos.
    Le apenas os primeiros 2 MB do EXE (headers + .bind ficam no comeco).
    """
    exe_path = Path(exe_path)
    if not exe_path.is_file():
        return False, ""
    try:
        with exe_path.open("rb") as f:
            head = f.read(2 * 1024 * 1024)
    except OSError:
        return False, ""

    # Marker mais confiavel: nome de secao ".bind" nos section headers.
    if b".bind\x00\x00\x00" in head[:0x1000] or b".bind\x00" in head[:0x2000]:
        return True, ".bind section"

    for marker in _DRM_MARKERS:
        if marker in head:
            return True, marker.decode("ascii", "ignore") or "stub marker"
    return False, ""


# ---------- Descoberta de Steamless.CLI ----------

_KNOWN_CLI_PATHS = (
    r"C:\Program Files\Steamless\Steamless.CLI.exe",
    r"C:\Program Files (x86)\Steamless\Steamless.CLI.exe",
    r"C:\Tools\Steamless\Steamless.CLI.exe",
)


def discover_cli() -> Path | None:
    """Ordem: defaults -> caminhos conhecidos -> PATH."""
    cfg_path = (_defaults().get("steamless_cli_path") or "").strip()
    if cfg_path:
        p = Path(cfg_path)
        if p.is_file():
            return p

    for cand in _KNOWN_CLI_PATHS:
        p = Path(cand)
        if p.is_file():
            return p

    from shutil import which
    hit = which("Steamless.CLI.exe") or which("Steamless.CLI")
    if hit:
        return Path(hit)
    return None


# ---------- Unpack ----------

@dataclass
class SteamlessResult:
    exe: Path
    was_wrapped: bool
    evidence: str = ""
    ran: bool = False
    unpacked_path: Path | None = None
    backup: Path | None = None
    replaced: bool = False
    stdout: str = ""
    stderr: str = ""
    log: list[str] = field(default_factory=list)


def unpack_exe(
    exe_path: Path,
    cli_path: Path | None = None,
    replace: bool = True,
    keep_unpacked_copy: bool = True,
    timeout: int = 300,
) -> SteamlessResult:
    """
    Roda Steamless.CLI no EXE. Se replace=True substitui original pelo unpacked
    e cria backup <exe>.steamdrm.bak.

    Idempotente: se o EXE nao tem DRM detectavel, retorna sem rodar Steamless.
    """
    exe_path = Path(exe_path).resolve()
    result = SteamlessResult(exe=exe_path, was_wrapped=False)

    is_wrapped, evidence = detect_steam_drm(exe_path)
    result.was_wrapped = is_wrapped
    result.evidence = evidence

    if not is_wrapped:
        result.log.append("Steam DRM stub nao detectado — Steamless nao necessario.")
        # Backup ja existe? significa que ja rodamos antes.
        bak = exe_path.with_suffix(exe_path.suffix + BACKUP_SUFFIX)
        if bak.exists():
            result.backup = bak
            result.log.append(f"Backup previo presente: {bak.name} (ja unpacked)")
        return result

    cli = Path(cli_path) if cli_path else discover_cli()
    if cli is None or not cli.is_file():
        result.log.append("Steamless.CLI.exe nao localizado. Configure em defaults.steamless_cli_path.")
        return result

    result.log.append(f"Steam DRM detectado ({evidence}). Rodando Steamless: {cli}")

    unpacked = exe_path.with_suffix(exe_path.suffix + ".unpacked")
    if unpacked.exists():
        try:
            unpacked.unlink()
        except OSError:
            pass

    try:
        proc = subprocess.run(
            [str(cli), str(exe_path), "--exp", "--keepbind"],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError as exc:
        result.log.append(f"Falha ao executar Steamless: {exc}")
        return result
    except subprocess.TimeoutExpired:
        result.log.append(f"Steamless timeout ({timeout}s)")
        return result

    result.ran = True
    result.stdout = proc.stdout or ""
    result.stderr = proc.stderr or ""

    if not unpacked.exists():
        result.log.append(f"Steamless nao gerou {unpacked.name} (rc={proc.returncode})")
        if result.stderr:
            result.log.append(f"stderr: {result.stderr[:400]}")
        return result

    # Renomeia game.exe.unpacked -> game-Unpacked.exe (arquivo fixo, .exe valido).
    fixed_unpacked = exe_path.with_name(exe_path.stem + "-Unpacked" + exe_path.suffix)
    try:
        if fixed_unpacked.exists():
            fixed_unpacked.unlink()
        shutil.move(str(unpacked), str(fixed_unpacked))
    except OSError:
        # Se rename falhar, tenta copiar e apagar o original.
        try:
            shutil.copy2(unpacked, fixed_unpacked)
            unpacked.unlink()
        except OSError:
            fixed_unpacked = unpacked  # ultimo recurso: nome antigo

    result.unpacked_path = fixed_unpacked
    result.log.append(f"Unpacked persistente: {fixed_unpacked.name}")

    if replace:
        bak = exe_path.with_suffix(exe_path.suffix + BACKUP_SUFFIX)
        if not bak.exists():
            shutil.copy2(exe_path, bak)
            result.backup = bak
            result.log.append(f"Backup original: {bak.name}")
        else:
            result.backup = bak
            result.log.append(f"Backup ja existe: {bak.name} (mantendo)")

        shutil.copy2(fixed_unpacked, exe_path)
        result.replaced = True
        result.log.append(f"EXE substituido pelo unpacked: {exe_path.name}")

        if not keep_unpacked_copy:
            try:
                fixed_unpacked.unlink()
                result.unpacked_path = None
            except OSError:
                pass

    return result


def restore_exe(exe_path: Path) -> bool:
    """Restaura EXE a partir do backup .steamdrm.bak."""
    exe_path = Path(exe_path).resolve()
    bak = exe_path.with_suffix(exe_path.suffix + BACKUP_SUFFIX)
    if not bak.is_file():
        return False
    shutil.copy2(bak, exe_path)
    return True


# ---------- CLI ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Remove Steam DRM stub do EXE via Steamless.CLI")
    ap.add_argument("--exe", required=True, help="Executavel Steam-wrapped")
    ap.add_argument("--cli", default="", help="Caminho Steamless.CLI.exe")
    ap.add_argument("--save-cli", action="store_true", help="Persistir --cli em defaults.json")
    ap.add_argument("--detect-only", action="store_true", help="So detecta DRM, nao roda unpacker")
    ap.add_argument("--no-replace", action="store_true", help="Nao substituir o EXE original")
    ap.add_argument("--restore", action="store_true", help="Restaurar do .steamdrm.bak")
    args = ap.parse_args()

    exe = Path(args.exe)
    if not exe.is_file():
        print(f"ERRO: EXE nao encontrado: {exe}", file=sys.stderr)
        return 1

    if args.restore:
        ok = restore_exe(exe)
        print("OK, restaurado do backup." if ok else "AVISO: backup .steamdrm.bak nao encontrado.")
        return 0 if ok else 2

    cli = Path(args.cli).resolve() if args.cli else None
    if cli and args.save_cli:
        save_default_cli(cli)

    if args.detect_only:
        wrapped, evidence = detect_steam_drm(exe)
        print(f"Steam DRM: {'SIM' if wrapped else 'NAO'} ({evidence or '-'})")
        return 0 if wrapped else 3

    result = unpack_exe(exe, cli_path=cli, replace=not args.no_replace)
    for line in result.log:
        print(line)
    if result.stderr:
        print(f"stderr: {result.stderr.strip()}")
    if not result.was_wrapped:
        return 0
    if result.was_wrapped and not result.replaced and not args.no_replace:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
