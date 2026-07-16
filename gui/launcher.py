#!/usr/bin/env python3
"""
EOSLANKit GUI — ferramenta universal para jogos com Epic Online Services (EOS).

Fluxo de uso:
  1. Selecione a pasta do jogo (ou o *-Shipping.exe)
  2. Clique Analisar
  3. Informe SteamID/Nick/AppID/Broadcasts se quiser customizar
  4. (Opcional) Aponte a steam_api64.dll Goldberg em "Goldberg fonte"
  5. Marque as acoes e Aplicar setup
  6. Play para abrir o launcher gerado
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

CREDITS_URL = "https://n3sec.com"
CREDITS_AUTHOR = "n3sec"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # gui/ para import splash

from detect import GameScan, scan_game  # noqa: E402
from goldberg import discover_source, save_default_source  # noqa: E402
from paths import app_root as _app_root, ensure_user_assets  # noqa: E402
from profile import GameProfile, load_profile, list_profiles  # noqa: E402
from restore_exe import restore_exe  # noqa: E402
from setup import SetupOptions, run_setup  # noqa: E402
from steam_settings import load_defaults  # noqa: E402
from steamless import discover_cli as steamless_discover_cli, save_default_cli as steamless_save_cli  # noqa: E402
from uninstall_proxy import uninstall_proxy  # noqa: E402

SETTINGS_PATH = _app_root() / "config" / "user_settings.json"


class EOSLANKitApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"EOSLANKit — Universal EOS LAN Tool  (by {CREDITS_AUTHOR})")
        self.geometry("920x760")
        self.minsize(820, 640)

        s = self._load_settings()
        defaults = load_defaults()

        self.game_path = tk.StringVar()
        self.clang_path = tk.StringVar(value=s.get("clang_path", ""))
        self.steam_id = tk.StringVar(value=s.get("steam_id", ""))
        self.account_name = tk.StringVar(value=s.get("account_name", ""))
        self.app_id = tk.StringVar(value=s.get("app_id", ""))
        self.broadcasts = tk.StringVar(
            value=s.get("broadcasts", ", ".join(defaults.get("default_broadcasts", [])))
        )
        self.goldberg_source = tk.StringVar(
            value=s.get("goldberg_source", defaults.get("goldberg_dll_source", ""))
        )
        self.steamless_cli = tk.StringVar(
            value=s.get("steamless_cli", defaults.get("steamless_cli_path", ""))
        )
        self.scan: GameScan | None = None
        self._busy = False

        self.opt_steamless = tk.BooleanVar(value=True)
        self.opt_goldberg = tk.BooleanVar(value=True)
        self.opt_steam = tk.BooleanVar(value=True)
        self.opt_build = tk.BooleanVar(value=True)
        self.opt_install = tk.BooleanVar(value=True)
        self.opt_patch = tk.BooleanVar(value=True)
        self.opt_launcher = tk.BooleanVar(value=True)
        self.opt_verify = tk.BooleanVar(value=True)

        self._build_ui()
        self._log(f"EOSLANKit  |  Made By: {CREDITS_AUTHOR}  |  {CREDITS_URL}")
        self._log("EOSLANKit pronto. Selecione a pasta ou o .exe de um jogo com EOS.")
        if self.goldberg_source.get():
            self._log(f"Goldberg fonte configurada: {self.goldberg_source.get()}")
        if self.steamless_cli.get():
            self._log(f"Steamless.CLI configurado: {self.steamless_cli.get()}")

    def _load_settings(self) -> dict:
        if SETTINGS_PATH.exists():
            try:
                return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_settings(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(
                {
                    "clang_path": self.clang_path.get().strip(),
                    "steam_id": self.steam_id.get().strip(),
                    "account_name": self.account_name.get().strip(),
                    "app_id": self.app_id.get().strip(),
                    "broadcasts": self.broadcasts.get().strip(),
                    "goldberg_source": self.goldberg_source.get().strip(),
                    "steamless_cli": self.steamless_cli.get().strip(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Setup LAN / offline para jogos UE + Steam + Epic Online Services",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            outer,
            text="Instala Goldberg (steam_api64), proxy EOSSDK, patch EXE (delay-load ou offsets conhecidos) e gera launcher.",
            wraplength=880,
        ).pack(anchor="w", pady=(0, 8))

        # --- 1. Jogo ---
        path_frm = ttk.LabelFrame(outer, text="1. Jogo alvo", padding=8)
        path_frm.pack(fill=tk.X, pady=4)
        row = ttk.Frame(path_frm)
        row.pack(fill=tk.X)
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.game_path).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(row, text="Pasta...", command=self._browse_folder).grid(row=0, column=1, padx=2)
        ttk.Button(row, text="EXE...", command=self._browse_exe).grid(row=0, column=2, padx=2)
        ttk.Button(row, text="Analisar", command=self._analyze).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(row, text="Perfis...", command=self._pick_profile).grid(row=0, column=4, padx=(6, 0))

        # --- 2. Detectado ---
        det_frm = ttk.LabelFrame(outer, text="2. Componentes detectados", padding=8)
        det_frm.pack(fill=tk.X, pady=4)
        det_frm.columnconfigure(1, weight=1)
        ttk.Label(det_frm, text="EOSSDK:").grid(row=0, column=0, sticky="w")
        self.eos_combo = ttk.Combobox(det_frm, state="readonly", width=80)
        self.eos_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        ttk.Label(det_frm, text="Executavel:").grid(row=1, column=0, sticky="w")
        self.exe_combo = ttk.Combobox(det_frm, state="readonly", width=80)
        self.exe_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=2)
        self.status_lbl = ttk.Label(det_frm, text="Nenhum jogo analisado.", foreground="#555")
        self.status_lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # --- 3. Goldberg + Steam ---
        gs_frm = ttk.LabelFrame(outer, text="3. Steam / Goldberg", padding=8)
        gs_frm.pack(fill=tk.X, pady=4)
        gs_frm.columnconfigure(1, weight=1)

        ttk.Label(gs_frm, text="steam_api64.dll fonte:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(gs_frm, textvariable=self.goldberg_source).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Button(gs_frm, text="...", width=3, command=self._browse_goldberg).grid(row=0, column=2, padx=2)
        ttk.Button(gs_frm, text="Auto", width=6, command=self._auto_goldberg).grid(row=0, column=3, padx=2)

        ttk.Label(gs_frm, text="Steamless.CLI.exe:").grid(row=1, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(gs_frm, textvariable=self.steamless_cli).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Button(gs_frm, text="...", width=3, command=self._browse_steamless).grid(row=1, column=2, padx=2)
        ttk.Button(gs_frm, text="Auto", width=6, command=self._auto_steamless).grid(row=1, column=3, padx=2)

        ttk.Label(gs_frm, text="SteamID64:").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(gs_frm, textvariable=self.steam_id, width=28).grid(row=2, column=1, sticky="w")
        ttk.Label(gs_frm, text="(vazio = 76561197960287930)", foreground="#666").grid(row=2, column=2, columnspan=2, sticky="w")

        ttk.Label(gs_frm, text="Nick:").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(gs_frm, textvariable=self.account_name, width=28).grid(row=3, column=1, sticky="w")
        ttk.Label(gs_frm, text="(vazio = Player)", foreground="#666").grid(row=3, column=2, columnspan=2, sticky="w")

        ttk.Label(gs_frm, text="AppID Steam:").grid(row=4, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(gs_frm, textvariable=self.app_id, width=16).grid(row=4, column=1, sticky="w")
        ttk.Label(gs_frm, text="(vazio = ler steam_appid.txt do jogo)", foreground="#666").grid(row=4, column=2, columnspan=2, sticky="w")

        ttk.Label(gs_frm, text="Broadcasts LAN:").grid(row=5, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(gs_frm, textvariable=self.broadcasts).grid(row=5, column=1, columnspan=3, sticky="ew", pady=2)

        # --- 4. Acoes ---
        opt_frm = ttk.LabelFrame(outer, text="4. Acoes", padding=8)
        opt_frm.pack(fill=tk.X, pady=4)
        row1 = ttk.Frame(opt_frm); row1.pack(fill=tk.X)
        row2 = ttk.Frame(opt_frm); row2.pack(fill=tk.X)
        ttk.Checkbutton(row1, text="Steamless (unpack DRM)", variable=self.opt_steamless).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(row1, text="Goldberg (steam_api64)", variable=self.opt_goldberg).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(row1, text="steam_settings + broadcasts", variable=self.opt_steam).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(row1, text="Compilar proxy EOS", variable=self.opt_build).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(row1, text="Instalar proxy (backup)", variable=self.opt_install).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(row2, text="Patch EXE (delay-load / known offsets)", variable=self.opt_patch).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(row2, text="Gerar Play-<Game>.bat", variable=self.opt_launcher).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(row2, text="Verificar setup", variable=self.opt_verify).pack(side=tk.LEFT, padx=6)

        # --- 5. Botoes ---
        btn_frm = ttk.Frame(outer)
        btn_frm.pack(fill=tk.X, pady=8)
        self.btn_apply = ttk.Button(btn_frm, text="Aplicar setup", command=self._apply)
        self.btn_apply.pack(side=tk.LEFT, padx=4)
        self.btn_play = ttk.Button(btn_frm, text="Jogar", command=self._play, state=tk.DISABLED)
        self.btn_play.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frm, text="Restaurar EOSSDK", command=self._restore_dll).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frm, text="Restaurar EXE", command=self._restore_exe).pack(side=tk.LEFT, padx=4)
        ttk.Separator(btn_frm, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(btn_frm, text="Clang:").pack(side=tk.LEFT)
        ttk.Entry(btn_frm, textvariable=self.clang_path, width=32).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frm, text="...", width=3, command=self._browse_clang).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 6))

        log_frm = ttk.LabelFrame(outer, text="Log", padding=4)
        log_frm.pack(fill=tk.BOTH, expand=True)
        self.log_box = scrolledtext.ScrolledText(log_frm, height=18, state=tk.DISABLED, font=("Consolas", 9))
        self.log_box.pack(fill=tk.BOTH, expand=True)

        credits = ttk.Frame(outer)
        credits.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(credits, text=f"Made By: {CREDITS_AUTHOR}  |  ", foreground="#555").pack(side=tk.LEFT)
        link = ttk.Label(credits, text=CREDITS_URL, foreground="#1a6ac2", cursor="hand2")
        link.pack(side=tk.LEFT)
        link.bind("<Button-1>", lambda _e: webbrowser.open(CREDITS_URL))

    # ---------- infra ----------
    def _log(self, msg: str) -> None:
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_apply.configure(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _browse_folder(self) -> None:
        p = filedialog.askdirectory(title="Pasta do jogo")
        if p:
            self.game_path.set(p)
            self._analyze()

    def _browse_exe(self) -> None:
        p = filedialog.askopenfilename(title="Executavel do jogo", filetypes=[("Executavel", "*.exe"), ("Todos", "*.*")])
        if p:
            self.game_path.set(p)
            self._analyze()

    def _browse_clang(self) -> None:
        p = filedialog.askdirectory(title="Pasta bin do LLVM/clang")
        if p:
            self.clang_path.set(p)

    def _browse_goldberg(self) -> None:
        p = filedialog.askopenfilename(title="Goldberg steam_api64.dll", filetypes=[("DLL", "*.dll")])
        if p:
            self.goldberg_source.set(p)
            save_default_source(Path(p))
            self._log(f"Goldberg fonte salva: {p}")

    def _auto_goldberg(self) -> None:
        root = None
        if self.scan:
            root = self.scan.game_root
        found = discover_source(root)
        if found:
            self.goldberg_source.set(str(found))
            self._log(f"Goldberg fonte detectada: {found}")
        else:
            messagebox.showinfo("EOSLANKit", "Nenhuma DLL Goldberg encontrada automaticamente. Aponte manualmente.")

    def _browse_steamless(self) -> None:
        p = filedialog.askopenfilename(
            title="Steamless.CLI.exe",
            filetypes=[("Executavel", "*.exe"), ("Todos", "*.*")],
        )
        if p:
            self.steamless_cli.set(p)
            steamless_save_cli(Path(p))
            self._log(f"Steamless.CLI salvo: {p}")

    def _auto_steamless(self) -> None:
        found = steamless_discover_cli()
        if found:
            self.steamless_cli.set(str(found))
            self._log(f"Steamless.CLI detectado: {found}")
        else:
            messagebox.showinfo(
                "EOSLANKit",
                "Steamless.CLI.exe nao encontrado.\n\n"
                "Baixe em https://github.com/atom0s/Steamless e aponte manualmente.",
            )

    def _pick_profile(self) -> None:
        profs = list_profiles()
        if not profs:
            messagebox.showinfo("EOSLANKit", "Nenhum perfil salvo ainda.")
            return
        win = tk.Toplevel(self)
        win.title("Perfis salvos")
        win.geometry("640x360")
        listbox = tk.Listbox(win, font=("Consolas", 9))
        listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for prof in profs:
            listbox.insert(tk.END, f"{prof.game_name or '?':<20} {prof.game_root}")

        def choose() -> None:
            sel = listbox.curselection()
            if not sel:
                return
            prof = profs[sel[0]]
            self.game_path.set(prof.game_root)
            self.steam_id.set(prof.steam_id)
            self.account_name.set(prof.account_name)
            self.app_id.set(prof.app_id)
            if prof.broadcasts:
                self.broadcasts.set(", ".join(prof.broadcasts))
            if prof.goldberg_source:
                self.goldberg_source.set(prof.goldberg_source)
            if getattr(prof, "steamless_cli", ""):
                self.steamless_cli.set(prof.steamless_cli)
            win.destroy()
            self._analyze()

        ttk.Button(win, text="Carregar", command=choose).pack(pady=4)

    def _selected_eos(self):
        if not self.scan or not self.scan.eos_targets:
            return None
        idx = self.eos_combo.current()
        if idx < 0:
            idx = 0
        return self.scan.eos_targets[idx]

    def _selected_exe(self):
        if not self.scan or not self.scan.exe_targets:
            return None
        idx = self.exe_combo.current()
        if idx < 0:
            idx = 0
        return self.scan.exe_targets[idx]

    def _broadcasts_list(self) -> list[str]:
        raw = self.broadcasts.get().strip()
        if not raw:
            return []
        return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]

    # ---------- actions ----------
    def _analyze(self) -> None:
        p = self.game_path.get().strip()
        if not p:
            messagebox.showwarning("EOSLANKit", "Selecione a pasta ou o executavel do jogo.")
            return
        try:
            self.scan = scan_game(p)
        except Exception as exc:
            messagebox.showerror("EOSLANKit", f"Falha na analise:\n{exc}")
            return

        eos_labels = [
            f"{e.path.relative_to(self.scan.game_root)}  [{e.status}, {e.size_bytes // 1024} KB, lib={e.library_name}]"
            for e in self.scan.eos_targets
        ]
        exe_labels = [
            f"{e.path.relative_to(self.scan.game_root)}"
            + (" [EOS delay-import]" if e.has_eos_delay_import else "")
            + (" [patchado]" if e.is_patched else "")
            + (" [bak]" if e.backup_exists else "")
            for e in self.scan.exe_targets
        ]

        self.eos_combo["values"] = eos_labels or ["(nao encontrada)"]
        self.exe_combo["values"] = exe_labels or ["(nao encontrado)"]
        self.eos_combo.current(0 if eos_labels else -1)
        self.exe_combo.current(0 if exe_labels else -1)

        parts = []
        if self.scan.primary_eos:
            parts.append(f"EOSSDK: {self.scan.primary_eos.path.name}")
        else:
            parts.append("EOSSDK: nao encontrada")
        parts.append(f"Steamworks: {len(self.scan.steamworks_dirs)}")
        if self.scan.warnings:
            parts.append(self.scan.warnings[0])
        self.status_lbl.configure(text=" | ".join(parts))

        # se tem perfil salvo, oferecer carregar app_id/broadcasts
        prof = load_profile(self.scan.game_root)
        if prof:
            if not self.app_id.get() and prof.app_id:
                self.app_id.set(prof.app_id)
            if not self.steam_id.get() and prof.steam_id:
                self.steam_id.set(prof.steam_id)
            if not self.account_name.get() and prof.account_name:
                self.account_name.set(prof.account_name)
            if not self.broadcasts.get() and prof.broadcasts:
                self.broadcasts.set(", ".join(prof.broadcasts))
            if not self.goldberg_source.get() and prof.goldberg_source:
                self.goldberg_source.set(prof.goldberg_source)
            if not self.steamless_cli.get() and getattr(prof, "steamless_cli", ""):
                self.steamless_cli.set(prof.steamless_cli)
            if prof.launcher_bat and Path(prof.launcher_bat).exists():
                self.btn_play.configure(state=tk.NORMAL)

        self._log("\n--- Analise ---")
        for line in self.scan.summary_lines():
            self._log(line)

    def _apply(self) -> None:
        if self._busy:
            return
        if not self.game_path.get().strip():
            messagebox.showwarning("EOSLANKit", "Selecione um jogo primeiro.")
            return
        if not self.scan:
            self._analyze()
        if not self.scan:
            return

        eos_sel = self._selected_eos()
        if (self.opt_build.get() or self.opt_install.get()) and eos_sel is None:
            messagebox.showerror("EOSLANKit", "EOSSDK nao encontrada neste jogo.")
            return

        self._save_settings()
        self._set_busy(True)
        self._log("\n=== Iniciando setup ===")

        opts = SetupOptions(
            do_steamless=self.opt_steamless.get(),
            do_build=self.opt_build.get(),
            do_install=self.opt_install.get(),
            do_patch=self.opt_patch.get(),
            do_steam_settings=self.opt_steam.get(),
            do_goldberg=self.opt_goldberg.get(),
            do_launcher=self.opt_launcher.get(),
            do_verify=self.opt_verify.get(),
        )

        game_path = self.game_path.get().strip()
        eos_path = self._selected_eos().path if eos_sel else None
        exe_sel = self._selected_exe()
        exe_path = exe_sel.path if exe_sel else None
        steam_id = self.steam_id.get().strip()
        account_name = self.account_name.get().strip()
        app_id = self.app_id.get().strip()
        broadcasts = self._broadcasts_list()
        goldberg = self.goldberg_source.get().strip()
        clang = self.clang_path.get().strip()
        steamless = self.steamless_cli.get().strip()

        def worker() -> None:
            try:
                result = run_setup(
                    game_path,
                    eos_path=eos_path,
                    exe_path=exe_path,
                    options=opts,
                    steam_id=steam_id,
                    account_name=account_name,
                    app_id=app_id,
                    broadcasts=broadcasts,
                    goldberg_source=goldberg,
                    clang_path=clang,
                    steamless_cli=steamless,
                )
                for line in result.log:
                    self.after(0, lambda l=line: self._log(l))

                if result.launcher_bat and result.launcher_bat.exists():
                    self.after(0, lambda: self.btn_play.configure(state=tk.NORMAL))

                ok = result.verify is None or result.verify.ok
                title = "EOSLANKit"
                msg = "Setup concluido com sucesso." if ok else "Setup concluido com AVISOS. Veja o log."
                self.after(0, self._analyze)
                self.after(0, lambda: (messagebox.showinfo if ok else messagebox.showwarning)(title, msg))
            except Exception as exc:
                self.after(0, lambda: self._log(f"ERRO: {exc}"))
                self.after(0, lambda: messagebox.showerror("EOSLANKit", str(exc)))
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _play(self) -> None:
        if not self.scan:
            return
        prof = load_profile(self.scan.game_root)
        bat = Path(prof.launcher_bat) if prof and prof.launcher_bat else None
        if not bat or not bat.exists():
            messagebox.showwarning("EOSLANKit", "Launcher nao gerado ainda. Rode 'Aplicar setup' com 'Gerar Play-<Game>.bat' marcado.")
            return
        self._log(f"Executando launcher: {bat}")
        try:
            os.startfile(str(bat))  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(bat.parent))

    def _restore_dll(self) -> None:
        eos = self._selected_eos()
        if not eos:
            messagebox.showwarning("EOSLANKit", "Nenhuma EOSSDK selecionada.")
            return
        if not messagebox.askyesno("EOSLANKit", f"Restaurar original de {eos.path.name}?"):
            return
        try:
            uninstall_proxy(eos.path)
            self._log(f"EOSSDK restaurada: {eos.path}")
            self._analyze()
        except Exception as exc:
            messagebox.showerror("EOSLANKit", str(exc))

    def _restore_exe(self) -> None:
        exe = self._selected_exe()
        if not exe:
            messagebox.showwarning("EOSLANKit", "Nenhum executavel selecionado.")
            return
        if not messagebox.askyesno("EOSLANKit", f"Restaurar backup de {exe.path.name}?"):
            return
        try:
            restore_exe(exe.path)
            self._log(f"EXE restaurado: {exe.path}")
            self._analyze()
        except Exception as exc:
            messagebox.showerror("EOSLANKit", str(exc))


def main() -> None:
    # 1) Extrai assets do bundle ANTES de qualquer coisa ler defaults.json.
    try:
        ensure_user_assets()
    except Exception:
        pass

    # 2) Uma unica raiz Tk. EOSLANKitApp e a raiz; splash e Toplevel dela.
    from splash import show_splash

    app = EOSLANKitApp()
    app.withdraw()

    splash = show_splash(app)
    if splash is not None:
        splash.set_status("Pronto")
        splash.signal_ready()
        try:
            app.wait_window(splash)
        except Exception:
            pass

    app.deiconify()
    app.mainloop()


if __name__ == "__main__":
    main()
