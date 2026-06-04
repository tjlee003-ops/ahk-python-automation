"""Main application window — sidebar, tabs, console panel, tray icon."""

from __future__ import annotations

import datetime
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    pass

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ROOT = Path(__file__).parent.parent.parent

# Console log colours
LOG_COLORS = {
    "success": "#4CAF50",
    "warning": "#FFC107",
    "error":   "#F44336",
    "info":    "#2196F3",
}

SIDEBAR_ITEMS = [
    ("🔴", "Rec",   "recorder"),
    ("⚡", "Trig",  "triggers"),
    ("{}", "Vars",  "variables"),
    ("▶",  "Flow",  "workflows"),
    ("✉",  "Email", "email"),
]


class AppShell(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AHK-Python Automation")
        self.geometry("1100x700")
        self.minsize(800, 500)

        self._active_section = "workflows"
        self._section_frames: dict[str, ctk.CTkFrame] = {}
        self._workflow_tabs: list[dict] = []
        self._console_visible = True

        self._build_layout()
        self._setup_tray()
        self._setup_keybindings()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=0)    # top bar
        self.grid_rowconfigure(1, weight=0)    # workflow tabs
        self.grid_rowconfigure(2, weight=1)    # main content
        self.grid_rowconfigure(3, weight=0)    # console
        self.grid_rowconfigure(4, weight=0)    # status bar
        self.grid_columnconfigure(0, weight=0) # sidebar
        self.grid_columnconfigure(1, weight=1) # content

        self._build_topbar()
        self._build_workflow_tabs()
        self._build_sidebar()
        self._build_content_area()
        self._build_console()
        self._build_statusbar()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=44, corner_radius=0)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(bar, text="⚙ AHK Automation", font=ctk.CTkFont(size=15, weight="bold"))
        logo.grid(row=0, column=0, padx=12, pady=8)

        stop_btn = ctk.CTkButton(bar, text="■ Stop All", width=90, fg_color="#B71C1C",
                                  hover_color="#D32F2F", command=self._stop_all)
        stop_btn.grid(row=0, column=2, padx=4, pady=6)

        help_btn = ctk.CTkButton(bar, text="?", width=32, command=self._open_help)
        help_btn.grid(row=0, column=3, padx=2, pady=6)

        min_btn = ctk.CTkButton(bar, text="—", width=32, command=self._minimize_to_tray)
        min_btn.grid(row=0, column=4, padx=2, pady=6)

    def _build_workflow_tabs(self):
        self._tab_bar = ctk.CTkFrame(self, height=36, corner_radius=0, fg_color=("gray85", "gray20"))
        self._tab_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        new_btn = ctk.CTkButton(self._tab_bar, text="+ New", width=70,
                                 height=28, command=self._new_workflow_tab)
        new_btn.pack(side="left", padx=4, pady=4)

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=80, corner_radius=0)
        sidebar.grid(row=2, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        for icon, label, key in SIDEBAR_ITEMS:
            btn = ctk.CTkButton(
                sidebar,
                text=f"{icon}\n{label}",
                width=72, height=60,
                fg_color="transparent",
                hover_color=("gray75", "gray30"),
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(pady=2, padx=4)

    def _build_content_area(self):
        self._content = ctk.CTkFrame(self, corner_radius=0)
        self._content.grid(row=2, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Placeholder frames — real section widgets injected by each module
        for _, _, key in SIDEBAR_ITEMS:
            f = ctk.CTkFrame(self._content, corner_radius=0)
            f.grid(row=0, column=0, sticky="nsew")
            lbl = ctk.CTkLabel(f, text=f"{key.title()} — loading…",
                               font=ctk.CTkFont(size=14))
            lbl.place(relx=0.5, rely=0.5, anchor="center")
            self._section_frames[key] = f

        self._show_section(self._active_section)

    def _build_console(self):
        self._console_frame = ctk.CTkFrame(self, height=140, corner_radius=0)
        self._console_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        self._console_frame.grid_columnconfigure(0, weight=1)
        self._console_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self._console_frame, height=24, corner_radius=0,
                               fg_color=("gray80", "gray25"))
        header.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(header, text="Console", font=ctk.CTkFont(size=11)).pack(side="left", padx=8)
        toggle_btn = ctk.CTkButton(header, text="▼", width=28, height=20,
                                    command=self._toggle_console)
        toggle_btn.pack(side="right", padx=4)

        self._console_text = ctk.CTkTextbox(self._console_frame, height=110,
                                             font=ctk.CTkFont(family="Courier New", size=11))
        self._console_text.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        self._console_text.configure(state="disabled")

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=24, corner_radius=0, fg_color=("gray80", "gray22"))
        bar.grid(row=4, column=0, columnspan=2, sticky="ew")

        self._status_label = ctk.CTkLabel(bar, text="Status: Idle",
                                           font=ctk.CTkFont(size=11))
        self._status_label.pack(side="left", padx=10)

        self._var_count_label = ctk.CTkLabel(bar, text="Vars: 0",
                                              font=ctk.CTkFont(size=11))
        self._var_count_label.pack(side="left", padx=10)

        self._mode_label = ctk.CTkLabel(bar, text="Mode: AHK",
                                         font=ctk.CTkFont(size=11))
        self._mode_label.pack(side="left", padx=10)

    # ── Section switching ─────────────────────────────────────────────────────

    def _show_section(self, key: str):
        self._active_section = key
        for k, frame in self._section_frames.items():
            if k == key:
                frame.tkraise()

    def register_section(self, key: str, widget: ctk.CTkFrame):
        """Called by section modules to inject their widget into the shell."""
        old = self._section_frames.get(key)
        if old:
            old.destroy()
        widget.grid(in_=self._content, row=0, column=0, sticky="nsew")
        self._section_frames[key] = widget
        if self._active_section == key:
            widget.tkraise()

    # ── Workflow tabs ─────────────────────────────────────────────────────────

    def _new_workflow_tab(self):
        idx = len(self._workflow_tabs) + 1
        name = f"Workflow {idx}"
        tab = {"name": name, "status": "idle"}
        self._workflow_tabs.append(tab)
        self._render_workflow_tabs()

    def _render_workflow_tabs(self):
        for widget in self._tab_bar.winfo_children():
            widget.destroy()

        for i, tab in enumerate(self._workflow_tabs):
            status_icon = "▶" if tab["status"] == "running" else "⏸" if tab["status"] == "paused" else ""
            lbl = f"{tab['name']} {status_icon}".strip()
            btn = ctk.CTkButton(
                self._tab_bar, text=lbl, height=28, width=120,
                command=lambda t=tab: self._select_workflow_tab(t),
            )
            btn.pack(side="left", padx=2, pady=4)

        new_btn = ctk.CTkButton(self._tab_bar, text="+ New", width=70, height=28,
                                 command=self._new_workflow_tab)
        new_btn.pack(side="left", padx=4, pady=4)

    def _select_workflow_tab(self, tab: dict):
        self._show_section("workflows")

    # ── Console ───────────────────────────────────────────────────────────────

    def log(self, message: str, level: str = "info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self._console_text.configure(state="normal")
        self._console_text.insert("end", line)
        self._console_text.configure(state="disabled")
        self._console_text.see("end")

    def _toggle_console(self):
        self._console_visible = not self._console_visible
        if self._console_visible:
            self._console_frame.grid()
        else:
            self._console_frame.grid_remove()

    # ── Status bar helpers ────────────────────────────────────────────────────

    def set_status(self, text: str):
        self._status_label.configure(text=f"Status: {text}")

    def set_var_count(self, n: int):
        self._var_count_label.configure(text=f"Vars: {n}")

    def set_mode(self, mode: str):
        self._mode_label.configure(text=f"Mode: {mode.upper()}")

    # ── Stop All ──────────────────────────────────────────────────────────────

    def _stop_all(self):
        from python.engine.ahk_bridge import get_bridge
        get_bridge().stop()
        self.set_status("Stopped")
        self.log("Stop All triggered.", "warning")

    # ── Tray ──────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (64, 64), color=(80, 80, 80))
            draw = ImageDraw.Draw(img)
            draw.ellipse([16, 16, 48, 48], fill=(150, 150, 150))

            menu = pystray.Menu(
                pystray.MenuItem("Show App", lambda: self.after(0, self.deiconify)),
                pystray.MenuItem("Start Recording", lambda: self._tray_start_rec()),
                pystray.MenuItem("Stop AHK", lambda: self._stop_all()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", lambda: self.after(0, self._quit)),
            )
            self._tray_icon = pystray.Icon("AHKAutomation", img, "AHK Automation", menu)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        except ImportError:
            self._tray_icon = None

    def _tray_start_rec(self):
        from python.engine.ahk_bridge import get_bridge
        get_bridge().start_recording()

    def _minimize_to_tray(self):
        self.withdraw()

    # ── Keybindings ───────────────────────────────────────────────────────────

    def _setup_keybindings(self):
        self.bind("<Control-s>", lambda e: self._save_active_workflow())

    def _save_active_workflow(self):
        self.log("Workflow saved.", "success")

    # ── Help ──────────────────────────────────────────────────────────────────

    def _open_help(self):
        from python.gui.help_panel import HelpPanel
        HelpPanel(self, active_section=self._active_section)

    # ── Window close ─────────────────────────────────────────────────────────

    def _on_close(self):
        self._minimize_to_tray()

    def _quit(self):
        if self._tray_icon:
            self._tray_icon.stop()
        self.destroy()


def launch():
    app = AppShell()
    app.mainloop()
