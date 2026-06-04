"""Trigger section UI — list, add/edit triggers, trigger log."""

from __future__ import annotations

import customtkinter as ctk

from python.engine.trigger_manager import (
    Priority, Trigger, TriggerType, get_manager
)


class TriggerSection(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._mgr = get_manager()
        self._build()
        self.refresh()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(toolbar, text="+ Add Trigger", width=130,
                       command=self._add_dialog).pack(side="left", padx=8, pady=6)

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._scroll.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        for col, text in enumerate(["Name", "Type", "Priority", "Enabled", "Target", "Actions"]):
            ctk.CTkLabel(self._scroll, text=text,
                         font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=col, padx=6, pady=4, sticky="w")

        # Log panel
        log_frame = ctk.CTkFrame(self, height=120, corner_radius=0)
        log_frame.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(log_frame, text="Trigger Log",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=2)
        self._log = ctk.CTkTextbox(log_frame, height=90,
                                    font=ctk.CTkFont(family="Courier New", size=11))
        self._log.pack(fill="x", padx=4, pady=2)
        self._log.configure(state="disabled")

    def refresh(self):
        for widget in self._scroll.winfo_children():
            info = widget.grid_info()
            if info and int(info.get("row", 0)) > 0:
                widget.destroy()

        for i, t in enumerate(self._mgr.all(), start=1):
            ctk.CTkLabel(self._scroll, text=t.name).grid(
                row=i, column=0, padx=6, pady=2, sticky="w")
            ctk.CTkLabel(self._scroll, text=t.type.value).grid(
                row=i, column=1, padx=6, pady=2, sticky="w")
            ctk.CTkLabel(self._scroll, text=t.priority.value).grid(
                row=i, column=2, padx=6, pady=2, sticky="w")

            enabled_var = ctk.BooleanVar(value=t.enabled)
            chk = ctk.CTkCheckBox(self._scroll, text="", variable=enabled_var,
                                   command=lambda tid=t.id, v=enabled_var: self._toggle(tid, v))
            chk.grid(row=i, column=3, padx=6, pady=2)

            ctk.CTkLabel(self._scroll, text=t.target_workflow or "—").grid(
                row=i, column=4, padx=6, pady=2, sticky="w")

            actions = ctk.CTkFrame(self._scroll, fg_color="transparent")
            actions.grid(row=i, column=5, padx=4, pady=2)
            ctk.CTkButton(actions, text="Edit", width=50,
                           command=lambda trig=t: self._edit_dialog(trig)).pack(
                side="left", padx=2)
            ctk.CTkButton(actions, text="▶ Fire", width=56,
                           command=lambda tid=t.id: self._fire(tid)).pack(
                side="left", padx=2)
            ctk.CTkButton(actions, text="Del", width=44, fg_color="#B71C1C",
                           hover_color="#D32F2F",
                           command=lambda tid=t.id: self._delete(tid)).pack(
                side="left", padx=2)

    def _toggle(self, tid: str, var: ctk.BooleanVar):
        if var.get():
            self._mgr.enable(tid)
        else:
            self._mgr.disable(tid)

    def _fire(self, tid: str):
        self._mgr.fire(tid)
        self._append_log(f"Manual fire: {tid}")

    def _delete(self, tid: str):
        self._mgr.delete(tid)
        self.refresh()

    def _add_dialog(self):
        TriggerDialog(self, on_save=self._on_save)

    def _edit_dialog(self, t: Trigger):
        TriggerDialog(self, trigger=t, on_save=self._on_save)

    def _on_save(self, t: Trigger):
        if t.id in {x.id for x in self._mgr.all()}:
            self._mgr.update(t)
        else:
            ok = self._mgr.add(t)
            if not ok:
                self._append_log("Conflict detected — trigger not saved.")
        self.refresh()

    def _append_log(self, msg: str):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log.configure(state="normal")
        self._log.insert("end", f"[{ts}] {msg}\n")
        self._log.configure(state="disabled")
        self._log.see("end")


class TriggerDialog(ctk.CTkToplevel):
    """4-section trigger editor: Condition, Preconditions, Var Injection, Target."""

    def __init__(self, parent, trigger: Trigger | None = None, on_save=None):
        super().__init__(parent)
        self.title("Add Trigger" if trigger is None else f"Edit — {trigger.name}")
        self.geometry("520x560")
        self.grab_set()
        self._trigger = trigger
        self._on_save = on_save
        self._build()

    def _build(self):
        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)

        for tab in ("Condition", "Preconditions", "Var Injection", "Target"):
            tabs.add(tab)

        self._build_condition(tabs.tab("Condition"))
        self._build_preconditions(tabs.tab("Preconditions"))
        self._build_injection(tabs.tab("Var Injection"))
        self._build_target(tabs.tab("Target"))

        ctk.CTkButton(self, text="Save Trigger", command=self._save).pack(pady=8)

    def _field(self, parent, label: str, default: str = "") -> ctk.CTkEntry:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=3)
        ctk.CTkLabel(f, text=label, width=140, anchor="w").pack(side="left")
        e = ctk.CTkEntry(f)
        e.pack(side="left", fill="x", expand=True)
        if default:
            e.insert(0, default)
        return e

    def _build_condition(self, tab):
        t = self._trigger
        self._name  = self._field(tab, "Name",  t.name if t else "")
        self._type  = self._option(tab, "Type",
                                    [x.value for x in TriggerType],
                                    t.type.value if t else "manual")
        self._cond_detail = self._field(tab, "Condition detail (JSON)",
                                         str(t.condition) if t else "")

    def _build_preconditions(self, tab):
        t = self._trigger
        pre = t.preconditions if t else {}
        self._ensure_window = self._field(tab, "Ensure window open",
                                           pre.get("ensure_window", ""))
        self._cooldown      = self._field(tab, "Cooldown (seconds)",
                                           str(pre.get("cooldown_seconds", "")))
        self._time_start    = self._field(tab, "Time window start (HH:MM)",
                                           pre.get("time_window", {}).get("start", ""))
        self._time_end      = self._field(tab, "Time window end (HH:MM)",
                                           pre.get("time_window", {}).get("end", ""))

    def _build_injection(self, tab):
        t = self._trigger
        self._injects = self._field(tab, "Injected vars (comma-sep)",
                                     ", ".join(t.injects) if t else "")

    def _build_target(self, tab):
        t = self._trigger
        self._target = self._field(tab, "Target workflow ID",
                                    t.target_workflow if t else "")
        self._priority = self._option(tab, "Priority",
                                       [p.value for p in Priority],
                                       t.priority.value if t else "normal")
        self._exec_mode = self._option(tab, "Execution mode",
                                        ["ahk", "python"],
                                        t.execution_mode if t else "ahk")

    def _option(self, parent, label: str, values: list[str], current: str = "") -> ctk.CTkOptionMenu:
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=3)
        ctk.CTkLabel(f, text=label, width=140, anchor="w").pack(side="left")
        om = ctk.CTkOptionMenu(f, values=values)
        om.pack(side="left")
        if current:
            om.set(current)
        return om

    def _save(self):
        import ast
        try:
            cond = ast.literal_eval(self._cond_detail.get()) if self._cond_detail.get() else {}
        except Exception:
            cond = {}

        pre: dict = {}
        if self._ensure_window.get():
            pre["ensure_window"] = self._ensure_window.get()
        if self._cooldown.get():
            pre["cooldown_seconds"] = int(self._cooldown.get())
        if self._time_start.get() and self._time_end.get():
            pre["time_window"] = {"start": self._time_start.get(),
                                  "end": self._time_end.get()}

        injects = [v.strip() for v in self._injects.get().split(",") if v.strip()]

        data = {
            "id": self._trigger.id if self._trigger else None,
            "name": self._name.get(),
            "type": self._type.get(),
            "enabled": True,
            "priority": self._priority.get(),
            "condition": cond,
            "preconditions": pre,
            "retry": {},
            "injects": injects,
            "target_workflow": self._target.get(),
            "execution_mode": self._exec_mode.get(),
        }
        if not data["id"]:
            import uuid
            data["id"] = str(uuid.uuid4())

        t = Trigger(data)
        if self._on_save:
            self._on_save(t)
        self.destroy()
