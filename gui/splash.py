"""Splash transparente EOSLANKit - 'Made by n3sec' + loading."""
from __future__ import annotations

import time
import tkinter as tk
import webbrowser
from tkinter import ttk

CREDITS_AUTHOR = "n3sec"
CREDITS_URL = "https://n3sec.com"
TRANSPARENT_KEY = "#010203"  # chroma-key para transparencia real no Windows


class Splash(tk.Toplevel):
    """Toplevel sem bordas com fundo transparente."""

    def __init__(self, master: tk.Misc, min_duration_ms: int = 1800) -> None:
        super().__init__(master)
        self._closed = False
        self._min_duration_ms = min_duration_ms
        self._ready_requested = False
        self._start = time.monotonic()

        try:
            self.overrideredirect(True)
        except tk.TclError:
            pass
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        # Tenta transparencia real; se falhar, fica com fundo escuro solido.
        self._has_transparency = False
        try:
            self.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
            self.configure(bg=TRANSPARENT_KEY)
            self._has_transparency = True
        except tk.TclError:
            self.configure(bg="#0f1116")

        w, h = 540, 260
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
        except tk.TclError:
            sw, sh = 1920, 1080
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        card = tk.Frame(self, bg="#0f1116", highlightthickness=1, highlightbackground="#2a2f3a")
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.92, relheight=0.88)

        tk.Label(card, text="EOSLANKit", bg="#0f1116", fg="#e6edf3",
                 font=("Segoe UI", 22, "bold")).pack(pady=(28, 4))
        tk.Label(card, text="Universal EOS LAN Tool", bg="#0f1116", fg="#8b95a7",
                 font=("Segoe UI", 10)).pack()

        tk.Label(card, text=f"Made by {CREDITS_AUTHOR}", bg="#0f1116", fg="#e6edf3",
                 font=("Segoe UI", 13, "bold")).pack(pady=(24, 2))

        link = tk.Label(card, text=CREDITS_URL, bg="#0f1116", fg="#5ca8ff",
                        cursor="hand2", font=("Segoe UI", 10, "underline"))
        link.pack()
        link.bind("<Button-1>", lambda _e: self._open_url())

        try:
            self.progress = ttk.Progressbar(card, mode="indeterminate", length=380)
            self.progress.pack(pady=(24, 4))
            self.progress.start(12)
        except tk.TclError:
            self.progress = None

        self.status = tk.Label(card, text="Carregando...", bg="#0f1116", fg="#8b95a7",
                               font=("Segoe UI", 9))
        self.status.pack(pady=(2, 0))

        try:
            self.update_idletasks()
        except tk.TclError:
            pass

    def _open_url(self) -> None:
        try:
            webbrowser.open(CREDITS_URL)
        except Exception:
            pass

    def set_status(self, text: str) -> None:
        if self._closed:
            return
        try:
            self.status.configure(text=text)
            self.update_idletasks()
        except tk.TclError:
            pass

    def signal_ready(self) -> None:
        self._ready_requested = True
        self._maybe_close()

    def _maybe_close(self) -> None:
        if self._closed:
            return
        elapsed_ms = (time.monotonic() - self._start) * 1000.0
        remaining = max(0.0, self._min_duration_ms - elapsed_ms)
        if self._ready_requested and remaining == 0:
            self.close()
        else:
            try:
                self.after(80 if self._ready_requested else 200, self._maybe_close)
            except tk.TclError:
                self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.progress is not None:
                self.progress.stop()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass


def show_splash(master: tk.Misc, min_duration_ms: int = 1800) -> Splash | None:
    """Cria e exibe o splash. Retorna None se qualquer coisa falhar (fail-safe)."""
    try:
        sp = Splash(master, min_duration_ms=min_duration_ms)
        sp.after(120, sp._maybe_close)
        try:
            master.update()
        except tk.TclError:
            pass
        return sp
    except Exception:
        return None
