"""Settings panel — backup controls, restore, schedule, general preferences."""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
import tkinter.filedialog as fd

from python.engine.backup_manager import (
    create_backup, list_backups, preview_backup, restore_backup
)
from python.file_manager import read_json, write_json


class SettingsSection(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._settings = read_json("data/settings.json") or {}
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        tabs.add("General")
        tabs.add("Backup & Restore")

        self._build_general(tabs.tab("General"))
        self._build_backup(tabs.tab("Backup & Restore"))

    # ── General ───────────────────────────────────────────────────────────────

    def _build_general(self, tab):
        f = ctk.CTkFrame(tab, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=12, pady=10)

        def row(label, key, values=None, default=""):
            fr = ctk.CTkFrame(f, fg_color="transparent")
            fr.pack(fill="x", pady=4)
            ctk.CTkLabel(fr, text=label, width=180, anchor="w").pack(side="left")
            if values:
                w = ctk.CTkOptionMenu(fr, values=values)
                w.set(str(self._settings.get(key, default)))
            else:
                w = ctk.CTkEntry(fr)
                w.insert(0, str(self._settings.get(key, default)))
            w.pack(side="left", fill="x", expand=True)
            return w, key

        self._fields = []
        self._fields.append(row("Theme", "theme", ["dark", "light", "system"], "dark"))
        self._fields.append(row("Default execution mode", "default_execution_mode",
                                ["ahk", "python"], "ahk"))
        self._fields.append(row("Autosave interval (seconds)",
                                "autosave_interval_seconds", default="3"))

        ctk.CTkButton(f, text="Save Settings", command=self._save_general).pack(
            pady=12, anchor="w")

    def _save_general(self):
        for widget, key in self._fields:
            val = widget.get() if hasattr(widget, "get") else widget.get()
            try:
                val = int(val)
            except (ValueError, TypeError):
                pass
            self._settings[key] = val
        write_json("data/settings.json", self._settings)

    # ── Backup & Restore ──────────────────────────────────────────────────────

    def _build_backup(self, tab):
        f = ctk.CTkFrame(tab, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=12, pady=10)

        # Schedule option
        fr = ctk.CTkFrame(f, fg_color="transparent")
        fr.pack(fill="x", pady=4)
        ctk.CTkLabel(fr, text="Backup schedule", width=160, anchor="w").pack(side="left")
        self._schedule_opt = ctk.CTkOptionMenu(
            fr, values=["disabled", "daily", "weekly", "on_close"])
        self._schedule_opt.set(
            self._settings.get("backup", {}).get("schedule", "daily"))
        self._schedule_opt.pack(side="left")

        # Keep last N
        fr2 = ctk.CTkFrame(f, fg_color="transparent")
        fr2.pack(fill="x", pady=4)
        ctk.CTkLabel(fr2, text="Keep last N backups", width=160, anchor="w").pack(side="left")
        self._keep_last = ctk.CTkEntry(fr2, width=60)
        self._keep_last.insert(0, str(self._settings.get("backup", {}).get("keep_last", 10)))
        self._keep_last.pack(side="left")

        # Include logs
        self._include_logs_var = ctk.BooleanVar(
            value=self._settings.get("backup", {}).get("include_logs", False))
        ctk.CTkCheckBox(f, text="Include logs in backup",
                         variable=self._include_logs_var).pack(
            anchor="w", pady=4)

        # Actions
        btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        btn_frame.pack(fill="x", pady=8)
        ctk.CTkButton(btn_frame, text="Backup Now", width=120,
                       command=self._backup_now).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Restore…", width=100,
                       command=self._restore_dialog).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Save Settings", width=120,
                       command=self._save_backup_settings).pack(side="left", padx=4)

        # Backup list
        ctk.CTkLabel(f, text="Existing backups:",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 2))
        self._backup_list = ctk.CTkScrollableFrame(f, height=160)
        self._backup_list.pack(fill="x")
        self._refresh_backup_list()

    def _save_backup_settings(self):
        if "backup" not in self._settings:
            self._settings["backup"] = {}
        self._settings["backup"]["schedule"]     = self._schedule_opt.get()
        self._settings["backup"]["keep_last"]    = int(self._keep_last.get() or 10)
        self._settings["backup"]["include_logs"] = self._include_logs_var.get()
        write_json("data/settings.json", self._settings)

    def _backup_now(self):
        p = create_backup("manual")
        self._refresh_backup_list()

    def _restore_dialog(self):
        backups = list_backups()
        if not backups:
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Restore Backup")
        dlg.geometry("500x400")
        dlg.grab_set()

        scroll = ctk.CTkScrollableFrame(dlg, label_text="Select backup to restore")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        for b in backups:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{b['name']}  ({b['size_kb']} KB)",
                         anchor="w").pack(side="left", padx=6)
            ctk.CTkButton(row, text="Preview", width=70,
                           command=lambda bp=b["path"]: self._show_preview(bp)).pack(
                side="right", padx=2)
            ctk.CTkButton(row, text="Restore", width=70,
                           command=lambda bp=b["path"], d=dlg: self._do_restore(bp, d)).pack(
                side="right", padx=2)

    def _show_preview(self, zip_path: str):
        files = preview_backup(zip_path)
        dlg = ctk.CTkToplevel(self)
        dlg.title("Backup Contents")
        dlg.geometry("400x400")
        box = ctk.CTkTextbox(dlg)
        box.pack(fill="both", expand=True, padx=8, pady=8)
        box.insert("1.0", "\n".join(files))
        box.configure(state="disabled")

    def _do_restore(self, zip_path: str, dialog):
        dialog.destroy()
        pre = restore_backup(zip_path)
        self._refresh_backup_list()

    def _refresh_backup_list(self):
        for w in self._backup_list.winfo_children():
            w.destroy()
        for b in list_backups():
            ctk.CTkLabel(self._backup_list,
                         text=f"{b['name']}  —  {b['size_kb']} KB",
                         anchor="w",
                         font=ctk.CTkFont(size=11)).pack(
                anchor="w", padx=6, pady=1)
