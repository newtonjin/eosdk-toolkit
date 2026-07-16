#!/usr/bin/env python3
"""Gera .def genérico a partir de qualquer EOSSDK*.dll."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from config_loader import load_config
from pe import PEFile


def generate_def(eos_dll: Path, out_path: Path, library_name: str | None = None,
                 orig_name_stem: str | None = None) -> tuple[int, int, str]:
    """Gera o .def da proxy in-process. Retorna (total_exports, hooked, library_name)."""
    cfg = load_config()
    intercepted = set(cfg["intercepted_exports"])
    orig_stem = orig_name_stem or Path(cfg["orig_dll_name"]).stem

    eos_path = Path(eos_dll)
    if not eos_path.is_file():
        raise FileNotFoundError(f"DLL nao encontrada: {eos_path}")

    pe = PEFile(eos_path)
    exports = pe.export_names()
    if not exports:
        raise RuntimeError("Nenhum export encontrado na DLL")

    if library_name:
        lib = library_name
    elif eos_path.stem.endswith("_orig"):
        lib = eos_path.stem[: -len("_orig")] + "-Win64-Shipping"
    else:
        lib = eos_path.stem

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"LIBRARY {lib}", "EXPORTS"]
    for name in exports:
        if name in intercepted:
            lines.append(f"    {name}")
        else:
            lines.append(f"    {name} = {orig_stem}.{name}")
    out_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return len(exports), len(intercepted), lib


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera module.def para proxy EOS")
    ap.add_argument("--eos-dll", required=True, help="Caminho da EOSSDK original (ou EOSSDK_orig.dll)")
    ap.add_argument("--out", default=str(ROOT / "build" / "eossdk_proxy.def"))
    ap.add_argument("--library-name", default=None, help="Nome que o jogo importa (ex: EOSSDK-Win64-Shipping)")
    ap.add_argument("--orig-name", default=None, help="Nome da DLL backup sem extensao (default: config)")
    args = ap.parse_args()

    try:
        total, hooked, lib = generate_def(
            Path(args.eos_dll), Path(args.out),
            library_name=args.library_name,
            orig_name_stem=args.orig_name,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    cfg = load_config()
    orig_stem = args.orig_name or Path(cfg["orig_dll_name"]).stem
    print(f"Gerado: {args.out}")
    print(f"  DLL alvo : {lib}")
    print(f"  Exports  : {total}")
    print(f"  Hook     : {hooked}")
    print(f"  Forward  : {total - hooked} -> {orig_stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
