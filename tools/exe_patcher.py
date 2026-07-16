#!/usr/bin/env python3
"""
Patch automatico dos stubs delay-load EOS no executavel.

Dois modos:
  1. Delay-import (padrao MSVC): parse delay-import + scan LEA RAX/JMP.
  2. Fallback known_offsets: quando delay-import EOSSDK nao existe (ex: Palworld),
     usa offsets pre-mapeados em config/known_offsets.json indexado por sha256 do EXE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from config_loader import load_config
from patch_utils import find_eos_delay_module, locate_stub_offsets
from paths import app_root as _app_root
from pe import PEFile

KNOWN_OFFSETS_PATH = _app_root() / "config" / "known_offsets.json"


@dataclass
class PatchResult:
    function: str
    offset: int
    return_value: int
    applied: bool
    reason: str = ""
    mode: str = ""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_known_offsets() -> dict:
    if not KNOWN_OFFSETS_PATH.exists():
        return {"entries": {}}
    try:
        return json.loads(KNOWN_OFFSETS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": {}}


def _save_known_offsets(data: dict) -> None:
    KNOWN_OFFSETS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_offsets(exe_sha256: str, exe_name: str, fn_to_off: dict[str, int], game: str = "", notes: str = "") -> None:
    """Persiste offsets descobertos em known_offsets.json (modo 'aprender')."""
    data = _load_known_offsets()
    entry = {
        "game": game or exe_name.split("-Win")[0],
        "exe_name": exe_name,
        "notes": notes or "Registrado automaticamente pelo EOSLANKit.",
        "offsets": {
            fn: {"offset": f"0x{off:X}", "return": 1 if "Count" in fn else 2}
            for fn, off in fn_to_off.items()
        },
    }
    data.setdefault("entries", {})[exe_sha256] = entry
    _save_known_offsets(data)


def _lookup_known(exe_sha256: str) -> dict | None:
    return _load_known_offsets().get("entries", {}).get(exe_sha256)


def patch_executable(exe_path: Path, dry_run: bool = False) -> list[PatchResult]:
    """Aplica patch preferindo delay-import; se falhar, tenta known_offsets."""
    cfg = load_config()
    patch_map: dict[str, int] = cfg.get("exe_patch_returns", {})
    results: list[PatchResult] = []

    pe: PEFile | None = None
    parse_err = ""
    try:
        pe = PEFile(exe_path)
    except Exception as exc:
        parse_err = str(exc)

    fn_to_off: dict[str, int] = {}
    mode = ""

    if pe is not None:
        try:
            _, iat_map = find_eos_delay_module(pe)
            fn_to_off = locate_stub_offsets(pe, iat_map)
            if fn_to_off:
                mode = "delay-import"
        except (RuntimeError, Exception):
            pass

    known_entry: dict | None = None
    if not fn_to_off:
        exe_sha = _sha256(exe_path)
        known_entry = _lookup_known(exe_sha)
        if known_entry:
            mode = "known-offsets"
            for fn, spec in known_entry.get("offsets", {}).items():
                off_raw = spec.get("offset")
                if isinstance(off_raw, str):
                    off = int(off_raw, 16) if off_raw.lower().startswith("0x") else int(off_raw)
                else:
                    off = int(off_raw)
                fn_to_off[fn] = off

    if not fn_to_off:
        reason = "nem delay-import EOSSDK nem entry em known_offsets.json (adicione manualmente ou registre com --learn)"
        if parse_err:
            reason = f"PE ilegivel ({parse_err}); tente outro shipping exe"
        return [
            PatchResult(fn, -1, ret_val, False, reason, mode="none")
            for fn, ret_val in patch_map.items()
        ]

    if pe is None:
        return [
            PatchResult(fn, -1, ret_val, False, f"PE ilegivel: {parse_err}", mode="none")
            for fn, ret_val in patch_map.items()
        ]

    # Merge patch_map (defaults) com known_entry (que pode sobrescrever returns)
    effective_returns: dict[str, int] = dict(patch_map)
    if known_entry:
        for fn, spec in known_entry.get("offsets", {}).items():
            ret_val = spec.get("return")
            if ret_val is not None:
                effective_returns[fn] = int(ret_val)

    for fn, off in fn_to_off.items():
        ret_val = effective_returns.get(fn, 1)
        if pe.is_already_patched(off):
            results.append(PatchResult(fn, off, ret_val, False, "ja patchado", mode=mode))
            continue

        b0, b1 = pe.data[off], pe.data[off + 1]
        if not (b0 == 0x48 and b1 == 0x8D):
            results.append(PatchResult(fn, off, ret_val, False, f"bytes inesperados {b0:02X} {b1:02X}", mode=mode))
            continue

        patch = pe.build_mov_eax_ret_patch(ret_val)
        if not dry_run:
            pe.patch_bytes(off, patch)
        results.append(PatchResult(fn, off, ret_val, True, mode=mode))

    # Funcoes do patch_map que nem delay-import nem known cobriram
    covered = set(fn_to_off.keys())
    for fn, ret_val in patch_map.items():
        if fn in covered:
            continue
        results.append(PatchResult(fn, -1, ret_val, False, "stub nao localizado", mode=mode))

    if not dry_run and any(r.applied for r in results):
        pe.save(exe_path)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Patch delay-load EOS no EXE")
    ap.add_argument("--exe", required=True, help="Executavel do jogo")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--learn", action="store_true",
                    help="Se localizados via delay-import, registrar offsets em known_offsets.json")
    ap.add_argument("--game", default="", help="Nome do jogo para --learn")
    args = ap.parse_args()

    exe = Path(args.exe)
    if not exe.is_file():
        print(f"ERRO: EXE nao encontrado: {exe}", file=sys.stderr)
        return 1

    if not args.no_backup and not args.dry_run:
        backup = exe.with_suffix(exe.suffix + ".eoslankit.bak")
        if not backup.exists():
            shutil.copy2(exe, backup)
            print(f"Backup: {backup}")

    try:
        results = patch_executable(exe, dry_run=args.dry_run)
    except RuntimeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    if args.learn:
        applied = {r.function: r.offset for r in results if r.applied and r.offset >= 0}
        if applied and results and results[0].mode == "delay-import":
            record_offsets(_sha256(exe), exe.name, applied, game=args.game)
            print(f"Aprendido em known_offsets.json (sha256={_sha256(exe)[:16]}...)")

    print(f"\n{'='*60}")
    print(f"EXE : {exe}")
    print(f"Modo: {results[0].mode if results else '-'}")
    print(f"Data: {datetime.now().isoformat(timespec='seconds')}")
    print(f"{'='*60}")
    for r in results:
        status = "OK" if r.applied else "SKIP"
        off = f"0x{r.offset:X}" if r.offset >= 0 else "-"
        extra = f" ({r.reason})" if r.reason else ""
        print(f"  [{status}] {r.function:<40} @ {off}  EAX={r.return_value}{extra}")

    applied = sum(1 for r in results if r.applied)
    already = sum(1 for r in results if r.reason == "ja patchado")
    print(f"\n{applied}/{len(results)} patches aplicados; {already} ja estavam.")
    return 0 if applied > 0 or already > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
