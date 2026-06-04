"""Runtime Companion Window — input variables, loop options, auto-save, var library overlay."""

from __future__ import annotations

import threading
import time

import customtkinter as ctk

from python.engine.variable_manager import VarScope, VarType, get_manager


class CompanionWindow(ctk.CTkToplevel):
    def __init__(self, workflow_name: str, on_stop=None):
        super().__init__()
        self.title(f"Running: {workflow_name}")
        self.geometry("360x500")
        self.attributes("-topmost", True)
        self.resizable(True, True)

        self._workflow_name = workflow_name
        self._on_stop       = on_stop
        self._var_mgr       = get_manager()
        self._autosave_thread: threading.Thread | None = None
        self._alive = True

        self._build()
        self._start_autosave()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, height=40, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text=f"▶ {self._workflow_name}",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            side="left", padx=10, pady=8)
        ctk.CTkButton(hdr, text="■ Stop", width=70, fg_color="#B71C1C",
                       hover_color="#D32F2F",
                       command=self._stop).pack(side="right", padx=6, pady=6)
        ctk.CTkButton(hdr, text="📚 Vars", width=80,
                       command=self._open_library).pack(side="right", padx=2, pady=6)

        # Variable list
        self._scroll = ctk.CTkScrollableFrame(self, label_text="Variables")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self._scroll.grid_columnconfigure((0, 1), weight=1)

        self._add_var_btn = ctk.CTkButton(self, text="+ Add Variable", height=30,
                                           command=self._add_variable_inline)
        self._add_var_btn.grid(row=2, column=0, padx=6, pady=2, sticky="ew")

        # Loop options
        loop_frame = ctk.CTkFrame(self, corner_radius=6)
        loop_frame.grid(row=3, column=0, padx=6, pady=4, sticky="ew")

        ctk.CTkLabel(loop_frame, text="Loop mode:",
                     font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=8, pady=4, sticky="w")
        self._loop_mode = ctk.CTkOptionMenu(
            loop_frame, values=["Run once", "Repeat N", "Until condition", "Forever"])
        self._loop_mode.grid(row=0, column=1, padx=6, pady=4)

        self._loop_param = ctk.CTkEntry(loop_frame, placeholder_text="N or condition…")
        self._loop_param.grid(row=1, column=0, columnspan=2,
                               padx=8, pady=4, sticky="ew")
        loop_frame.grid_columnconfigure(1, weight=1)

        # Loop index display
        self._loop_index_label = ctk.CTkLabel(loop_frame, text="loopIndex: 0",
                                               font=ctk.CTkFont(size=11))
        self._loop_index_label.grid(row=2, column=0, columnspan=2,
                                     padx=8, pady=2, sticky="w")

        self.refresh_vars()
        self.protocol("WM_DELETE_WINDOW", self._stop)

    # ── Variable display ──────────────────────────────────────────────────────

    def refresh_vars(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        vars_ = [v for v in self._var_mgr.all_variables()
                 if v.scope.value in ("workflow", "global")]
        for i, v in enumerate(vars_):
            ctk.CTkLabel(self._scroll, text=v.name, anchor="w").grid(
                row=i, column=0, padx=6, pady=3, sticky="w")
            entry = ctk.CTkEntry(self._scroll)
            entry.insert(0, str(v.value))
            entry.grid(row=i, column=1, padx=4, pady=3, sticky="ew")
            entry.bind("<FocusOut>",
                       lambda e, name=v.name, ent=entry, scope=v.scope:
                       self._update_var(name, ent.get(), scope))

    def update_loop_index(self, idx: int):
        self._loop_index_label.configure(text=f"loopIndex: {idx}")

    def _update_var(self, name: str, value: str, scope):
        self._var_mgr.set(name, value, scope)

    def _add_variable_inline(self):
        dlg = ctk.CTkInputDialog(text="Variable name:", title="Add Variable")
        name = dlg.get_input()
        if name:
            self._var_mgr.set(name, "", VarScope.WORKFLOW)
            self.refresh_vars()

    def _open_library(self):
        from python.gui.variable_section import VarLibraryOverlay
        VarLibraryOverlay(self)

    # ── Loop options accessors ────────────────────────────────────────────────

    def get_loop_mode(self) -> str:
        return self._loop_mode.get()

    def get_loop_param(self) -> str:
        return self._loop_param.get()

    # ── Auto-save ─────────────────────────────────────────────────────────────

    def _start_autosave(self):
        def loop():
            while self._alive:
                time.sleep(3)
                if self._alive:
                    self._var_mgr.save_globals()
        self._autosave_thread = threading.Thread(target=loop, daemon=True)
        self._autosave_thread.start()

    # ── Stop ──────────────────────────────────────────────────────────────────

    def _stop(self):
        self._alive = False
        if self._on_stop:
            self._on_stop()
        self.destroy()
