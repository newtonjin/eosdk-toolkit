#!/usr/bin/env python3
"""Orquestrador: build, install, goldberg, steam_settings, patch, launcher, verify."""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from paths import app_root as _app_root, bundled_root as _bundled_root


def _asset_root() -> Path:
    """Prefere assets extraidos ao lado do .exe; fallback para o bundle."""
    disk = _app_root()
    if (disk / "build" / "build.ps1").exists():
        return disk
    return _bundled_root()


from config_loader import load_config
from detect import GameScan, scan_game, source_dll_for_build
from exe_patcher import PatchResult, patch_executable
from install_proxy import install_proxy
from launcher_gen import generate_launcher
from profile import GameProfile, load_profile, save_profile
from steam_settings import apply_steam_settings, load_defaults
from steamless import SteamlessResult, unpack_exe
from uninstall_proxy import uninstall_proxy
from restore_exe import restore_exe
from verify import VerifyReport, verify_install


@dataclass
class SetupOptions:
    do_steamless: bool = True
    do_build: bool = True
    do_install: bool = True
    do_patch: bool = True
    do_steam_settings: bool = True
    do_goldberg: bool = True
    do_launcher: bool = True
    do_verify: bool = True
    dry_run_patch: bool = False


@dataclass
class SetupResult:
    scan: GameScan
    profile: GameProfile | None = None
    proxy_path: Path | None = None
    installed_to: Path | None = None
    patch_results: list[PatchResult] | None = None
    steam_settings_paths: list[Path] = field(default_factory=list)
    goldberg_installed: list[Path] = field(default_factory=list)
    launcher_bat: Path | None = None
    launcher_ps1: Path | None = None
    verify: VerifyReport | None = None
    steamless: SteamlessResult | None = None
    log: list[str] = field(default_factory=list)


def build_proxy(eos_dll: Path, library_name: str, out_dir: Path | None = None, clang_path: str = "") -> Path:
    from gen_def import generate_def

    assets = _asset_root()
    out_dir = out_dir or (_app_root() / "build")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"{library_name}.dll"
    out_dll = out_dir / out_name

    def_path = out_dir / "eossdk_proxy.def"
    generate_def(Path(eos_dll), def_path, library_name=library_name)

    ps_args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(assets / "build" / "build.ps1"),
               "-EosDll", str(eos_dll),
               "-OutName", out_name,
               "-LibraryName", library_name,
               "-BuildDir", str(out_dir)]
    if clang_path:
        ps_args.extend(["-ClangPath", clang_path])

    build = subprocess.run(ps_args, capture_output=True, text=True, cwd=str(assets))
    if build.returncode != 0:
        raise RuntimeError(build.stderr or build.stdout or "build falhou")
    if not out_dll.exists():
        raise RuntimeError(f"Proxy nao gerada: {out_dll}")
    return out_dll


def run_setup(
    game_path: str | Path,
    eos_path: Path | None = None,
    exe_path: Path | None = None,
    options: SetupOptions | None = None,
    steam_id: str = "",
    account_name: str = "",
    app_id: str = "",
    broadcasts: list[str] | None = None,
    goldberg_source: str | Path = "",
    clang_path: str = "",
    steamless_cli: str | Path = "",
) -> SetupResult:
    options = options or SetupOptions()
    result = SetupResult(scan=scan_game(game_path))
    log = result.log
    scan = result.scan

    eos = None
    if eos_path:
        eos = next((e for e in scan.eos_targets if e.path.resolve() == Path(eos_path).resolve()), None)
    if eos is None:
        eos = scan.primary_eos

    exe = None
    if exe_path:
        exe = next((e for e in scan.exe_targets if e.path.resolve() == Path(exe_path).resolve()), None)
    if exe is None:
        exe = scan.primary_exe

    cfg = load_config()
    defaults = load_defaults()

    log.append(f"Jogo   : {scan.game_root}")
    if eos:
        log.append(f"EOSSDK : {eos.path.name} -> library {eos.library_name}")
    if exe:
        log.append(f"EXE    : {exe.path}")

    profile = load_profile(scan.game_root) or GameProfile(game_root=str(scan.game_root))
    profile.app_id = app_id or profile.app_id
    profile.steam_id = steam_id or profile.steam_id
    profile.account_name = account_name or profile.account_name
    if broadcasts is not None:
        profile.broadcasts = broadcasts

    # --- Steamless (remove DRM stub Steam do EXE) ---
    if options.do_steamless and exe is not None:
        cli = Path(steamless_cli).resolve() if steamless_cli else None
        log.append("Verificando Steam DRM stub no EXE...")
        try:
            sres = unpack_exe(exe.path, cli_path=cli, replace=True)
        except Exception as exc:
            log.append(f"AVISO: Steamless falhou ({exc}); prosseguindo com EXE original.")
            sres = None
        if sres is not None:
            result.steamless = sres
            for line in sres.log:
                log.append(f"  {line}")
            if sres.replaced:
                profile.steamless_was_wrapped = True
                if sres.backup:
                    profile.steamless_backup = str(sres.backup)
                if cli:
                    profile.steamless_cli = str(cli)

    # --- Goldberg ---
    if options.do_goldberg:
        from goldberg import install_goldberg, discover_source

        src = Path(goldberg_source).resolve() if goldberg_source else None
        if src is None:
            auto = discover_source(scan.game_root)
            if auto is not None:
                src = auto
                log.append(f"Goldberg fonte (auto): {src}")
        if src is None:
            log.append("AVISO: Goldberg nao instalado (fonte nao encontrada). Passe --goldberg-source.")
        else:
            log.append(f"Instalando Goldberg: {src}")
            gres = install_goldberg(scan.game_root, src)
            result.goldberg_installed = list(gres.installed)
            for p in gres.installed:
                log.append(f"  Goldberg -> {p}")
            for p in gres.skipped:
                log.append(f"  Goldberg SKIP {p[0]} ({p[1]})")
            profile.goldberg_source = str(src)
            profile.goldberg_installed = [str(p) for p in gres.installed]

    # --- steam_settings ---
    if options.do_steam_settings:
        log.append("Aplicando steam_settings...")
        ss_paths = apply_steam_settings(
            scan.game_root,
            steam_id=steam_id,
            account_name=account_name,
            app_id=app_id,
            broadcasts=broadcasts,
        )
        result.steam_settings_paths = ss_paths
        for p in ss_paths:
            log.append(f"  steam_settings -> {p}")
        profile.steam_settings_dirs = [str(p) for p in ss_paths]

    # --- Build proxy ---
    proxy_path = None
    if options.do_build:
        if eos is None:
            raise FileNotFoundError("EOSSDK nao encontrada. Nao ha o que compilar.")
        src_dll = source_dll_for_build(eos, cfg)
        log.append(f"Build fonte: {src_dll}")
        proxy_path = build_proxy(src_dll, eos.library_name, clang_path=clang_path)
        log.append(f"Proxy compilada: {proxy_path}")
    else:
        if eos is not None:
            proxy_path = ROOT / "build" / f"{eos.library_name}.dll"
    result.proxy_path = proxy_path if proxy_path and proxy_path.exists() else None

    # --- Install proxy ---
    if options.do_install:
        if eos is None:
            raise FileNotFoundError("EOSSDK nao encontrada para instalar.")
        if not proxy_path or not proxy_path.exists():
            raise FileNotFoundError("Proxy nao encontrada. Compile primeiro.")
        log.append("Instalando proxy EOS...")
        installed = install_proxy(
            scan.game_root, proxy_path, eos_dll=eos.path,
            steam_id=steam_id or profile.steam_id,
            account_name=account_name or profile.account_name,
        )
        result.installed_to = installed
        log.append(f"Proxy instalada em: {installed}")
        profile.eos_dll = str(eos.path)
        profile.eos_backup = str(eos.path.parent / cfg["orig_dll_name"])

    # --- Patch EXE ---
    if options.do_patch:
        if exe is None:
            log.append("AVISO: nenhum EXE selecionado; patch ignorado.")
        else:
            log.append(f"Patch EXE: {exe.path.name}")
            patches = patch_executable(exe.path, dry_run=options.dry_run_patch)
            result.patch_results = patches
            applied = sum(1 for p in patches if p.applied)
            already = sum(1 for p in patches if p.reason == "ja patchado")
            mode = patches[0].mode if patches else "?"
            log.append(f"  modo: {mode}  aplicados: {applied}  ja patchados: {already}  falhas: {len(patches) - applied - already}")
            for p in patches:
                status = "OK" if p.applied else ("skip" if p.reason == "ja patchado" else "FAIL")
                off = f"0x{p.offset:X}" if p.offset >= 0 else "-"
                log.append(f"    [{status}] {p.function} @ {off} EAX={p.return_value} {p.reason}")
            profile.shipping_exe = str(exe.path)
            profile.exe_backup = str(exe.path.with_suffix(exe.path.suffix + ".eoslankit.bak"))

            # Sincroniza -Unpacked.exe (se existir) com a versao patchada
            # para o launcher poder preferir ele sem perder o patch.
            unpacked_fixed = exe.path.with_name(exe.path.stem + "-Unpacked" + exe.path.suffix)
            if unpacked_fixed.exists() and not options.dry_run_patch:
                try:
                    import shutil as _sh
                    _sh.copy2(exe.path, unpacked_fixed)
                    log.append(f"  Sincronizado {unpacked_fixed.name} com a versao patchada.")
                except OSError as exc:
                    log.append(f"  AVISO: falha ao sincronizar unpacked ({exc})")

    # --- Launcher ---
    if options.do_launcher and exe is not None:
        log.append("Gerando launcher...")
        bat, ps1 = generate_launcher(
            scan.game_root,
            exe.path,
            app_id=app_id or profile.app_id,
        )
        result.launcher_bat = bat
        result.launcher_ps1 = ps1
        log.append(f"  {bat}")
        if ps1 is not None:
            log.append(f"  {ps1}")
        profile.launcher_bat = str(bat)
        profile.launcher_ps1 = str(ps1) if ps1 else ""

    # --- Verify ---
    if options.do_verify:
        log.append("Verificando setup...")
        rep = verify_install(
            scan.game_root,
            eos_dll=eos.path if eos else None,
            shipping_exe=exe.path if exe else None,
        )
        result.verify = rep
        for line in rep.to_lines():
            log.append(f"  {line}")

    # --- Persist profile ---
    if exe is not None:
        profile.game_name = exe.path.name.split("-Win")[0]
    profile.last_apply = time.time()
    saved = save_profile(profile)
    result.profile = profile
    log.append(f"Perfil salvo: {saved}")

    return result
