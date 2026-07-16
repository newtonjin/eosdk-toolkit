#!/usr/bin/env python3
"""Verificacoes pos-instalacao: valida se o setup EOSLANKit esta consistente."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from config_loader import load_config
from pe import PEFile


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class VerifyReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def to_lines(self) -> list[str]:
        out = []
        for c in self.checks:
            mark = "OK  " if c.ok else "FAIL"
            out.append(f"[{mark}] {c.name}" + (f"  ({c.detail})" if c.detail else ""))
        return out


def _exports(path: Path) -> int:
    try:
        return len(PEFile(path).export_names())
    except Exception:
        return -1


def verify_install(
    game_root: Path,
    eos_dll: Path | None = None,
    shipping_exe: Path | None = None,
) -> VerifyReport:
    cfg = load_config()
    orig_name = cfg["orig_dll_name"]
    proxy_max = int(cfg.get("proxy_max_size_bytes", 524288))
    orig_min = int(cfg.get("original_min_size_bytes", 1048576))

    rep = VerifyReport()
    root = Path(game_root).resolve()
    rep.checks.append(Check("Pasta do jogo existe", root.is_dir(), str(root)))

    if eos_dll is not None:
        active = Path(eos_dll)
        backup = active.parent / orig_name
        rep.checks.append(Check("EOSSDK ativa presente", active.is_file(), str(active)))
        rep.checks.append(Check("EOSSDK_orig backup presente", backup.is_file(), str(backup)))
        if active.is_file():
            sz = active.stat().st_size
            rep.checks.append(Check(
                "Tamanho da proxy compativel",
                sz <= proxy_max,
                f"{sz} bytes (max {proxy_max})",
            ))
            n = _exports(active)
            rep.checks.append(Check("Proxy exporta funcoes EOS_*", n > 100, f"{n} exports"))
        if backup.is_file():
            sz = backup.stat().st_size
            rep.checks.append(Check(
                "Backup tem tamanho de DLL original",
                sz >= orig_min,
                f"{sz} bytes (min {orig_min})",
            ))
            n = _exports(backup)
            rep.checks.append(Check("Backup exporta funcoes EOS_*", n > 100, f"{n} exports"))

    # steam_settings escrito em pelo menos 1 lugar
    ss_present = 0
    for p in root.glob("**/steam_settings/configs.user.ini"):
        ss_present += 1
    rep.checks.append(Check(
        "steam_settings escritos",
        ss_present > 0,
        f"{ss_present} configs.user.ini encontrados",
    ))

    # Goldberg em pelo menos raiz ou Steamworks
    goldberg_targets = []
    for cand in (
        root / "steam_api64.dll",
        *root.glob("Engine/Binaries/ThirdParty/Steamworks/Steamv*/Win64/steam_api64.dll"),
    ):
        if cand.is_file():
            goldberg_targets.append(cand)
    rep.checks.append(Check(
        "steam_api64.dll instalada",
        len(goldberg_targets) > 0,
        f"{len(goldberg_targets)} caminhos",
    ))

    if shipping_exe is not None:
        exe = Path(shipping_exe)
        bak = exe.with_suffix(exe.suffix + ".eoslankit.bak")
        legacy_bak = exe.with_suffix(exe.suffix + ".original_backup")
        rep.checks.append(Check(
            "EXE shipping presente",
            exe.is_file(),
            str(exe),
        ))
        rep.checks.append(Check(
            "Backup do EXE presente",
            bak.is_file() or legacy_bak.is_file(),
            str(bak if bak.is_file() else legacy_bak),
        ))

    return rep


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Verifica setup EOSLANKit no jogo")
    ap.add_argument("--game", required=True)
    ap.add_argument("--eos-dll", default="")
    ap.add_argument("--exe", default="")
    args = ap.parse_args()

    rep = verify_install(
        Path(args.game),
        Path(args.eos_dll) if args.eos_dll else None,
        Path(args.exe) if args.exe else None,
    )
    for line in rep.to_lines():
        print(line)
    print(f"\nResultado: {'OK' if rep.ok else 'FALHAS'}")
    return 0 if rep.ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
