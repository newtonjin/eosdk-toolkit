# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para EOSLANKit — onedir portable.

Gera dist/EOSLANKit/EOSLANKit.exe + assets extraidos ao lado. Na primeira
execucao, tools/paths.ensure_user_assets() copia config/build/src do bundle
para o diretorio do .exe (writable). Nao inclui Steamless.CLI ou steam_api64.dll
Goldberg — usuario aponta na GUI (licencas de terceiros).

Uso: pyinstaller EOSLANKit.spec  (rode via build-exe.ps1)
"""
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).resolve()

DATAS = [
    (str(ROOT / "config"), "config"),
    (str(ROOT / "build"),  "build"),
    (str(ROOT / "src"),    "src"),
    (str(ROOT / "tools"),  "tools"),
    (str(ROOT / "gui"),    "gui"),
]

HIDDEN_IMPORTS = [
    "config_loader", "detect", "exe_patcher", "gen_def", "goldberg",
    "install_proxy", "launcher_gen", "paths", "patch_utils", "pe",
    "profile", "restore_exe", "setup", "steam_settings", "steamless",
    "uninstall_proxy", "verify",
    "splash",
]

a = Analysis(
    [str(ROOT / "gui" / "launcher.py")],
    pathex=[str(ROOT / "tools"), str(ROOT / "gui")],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "notebook"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EOSLANKit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,               # sem console: janela pura
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    manifest=None,
    version=None,
    contents_directory="_internal",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EOSLANKit",
)
