"""Utilidades compartilhadas para patch delay-load EOS."""
from __future__ import annotations

from config_loader import load_config
from pe import PEFile


def find_eos_delay_module(pe: PEFile) -> tuple[str, dict[str, int]]:
    cfg = load_config()
    patch_map: dict[str, int] = cfg.get("exe_patch_returns", {})

    for mod in pe.delay_imports():
        if "eossdk" in mod.dll_name.lower() or mod.dll_name.lower().startswith("eos"):
            iat_map = {f.name: f.iat_rva for f in mod.functions if f.name in patch_map}
            if iat_map:
                return mod.dll_name, iat_map
    raise RuntimeError("Delay-import EOSSDK nao encontrado no executavel")


def locate_stub_offsets(pe: PEFile, iat_map: dict[str, int]) -> dict[str, int]:
    stubs = pe.scan_lea_iat_stubs(set(iat_map.values()))
    va_to_fn = {pe.image_base + rva: fn for fn, rva in iat_map.items()}

    fn_to_off: dict[str, int] = {}
    for off, va_hex in stubs.items():
        fn = va_to_fn.get(int(va_hex, 16))
        if fn:
            fn_to_off[fn] = off
    return fn_to_off


def exe_has_eos_delay_import(exe_path) -> tuple[bool, list[str]]:
    """Leve: so le tabela delay-import (sem scan de .text). Retorna (False, []) se PE malformado."""
    from pathlib import Path

    cfg = load_config()
    patch_names = set(cfg.get("exe_patch_returns", {}).keys())
    try:
        pe = PEFile(Path(exe_path))
        for mod in pe.delay_imports():
            if "eossdk" in mod.dll_name.lower() or mod.dll_name.lower().startswith("eos"):
                patchable = [f.name for f in mod.functions if f.name in patch_names]
                return True, patchable
    except Exception:
        return False, []
    return False, []


def exe_patch_status(exe_path, quick: bool = False) -> tuple[bool, list[str], bool]:
    """Retorna (has_eos_delay, patchable_fns, any_patched). quick=True evita scan completo."""
    from pathlib import Path

    has, patchable = exe_has_eos_delay_import(exe_path)
    if not has:
        return False, [], False
    if quick:
        return True, patchable, False

    try:
        pe = PEFile(Path(exe_path))
        _, iat_map = find_eos_delay_module(pe)
        fn_to_off = locate_stub_offsets(pe, iat_map)
        patched = any(pe.is_already_patched(off) for off in fn_to_off.values())
        return True, patchable, patched
    except Exception:
        return True, patchable, False
