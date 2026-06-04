"""Email template editor — rich text, variable autocomplete, preview, 3 attachment modes."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import customtkinter as ctk
import tkinter as tk

from python.file_manager import path, write_json, read_json
from python.engine.variable_manager import get_manager as get_var_mgr

TEMPLATES_PATH = "library/templates"


# ── Template model ────────────────────────────────────────────────────────────

class EmailTemplate:
    def __init__(self):
        self.id          = str(uuid.uuid4())
        self.name        = ""
        self.category    = ""
        self.to          = ""
        self.cc          = ""
        self.bcc         = ""
        self.subject     = ""
        self.body        = ""
        self.attachments: list[dict] = []
        self.exec_mode   = "send_directly"  # send_directly | open_for_review | save_as_draft

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "category": self.category,
            "to": self.to, "cc": self.cc, "bcc": self.bcc,
            "subject": self.subject, "body": self.body,
            "attachments": self.attachments,
            "exec_mode": self.exec_mode,
        }

    @staticmethod
    def from_dict(d: dict) -> "EmailTemplate":
        t = EmailTemplate()
        t.id         = d.get("id", t.id)
        t.name       = d.get("name", "")
        t.category   = d.get("category", "")
        t.to         = d.get("to", "")
        t.cc         = d.get("cc", "")
        t.bcc        = d.get("bcc", "")
        t.subject    = d.get("subject", "")
        t.body       = d.get("body", "")
        t.attachments = d.get("attachments", [])
        t.exec_mode  = d.get("exec_mode", "send_directly")
        return t

    def save(self):
        dest = path(TEMPLATES_PATH)
        dest.mkdir(parents=True, exist_ok=True)
        write_json(f"{TEMPLATES_PATH}/{self.name}.json", self.to_dict())

    @staticmethod
    def load_all() -> list["EmailTemplate"]:
        p = path(TEMPLATES_PATH)
        if not p.exists():
            return []
        result = []
        for f in p.glob("*.json"):
            data = read_json(str(f.relative_to(path(""))))
            if data:
                result.append(EmailTemplate.from_dict(data))
        return result


# ── Email section ─────────────────────────────────────────────────────────────

class EmailSection(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._templates = EmailTemplate.load_all()
        self._current: EmailTemplate | None = None
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Left panel — template list
        left = ctk.CTkFrame(self, width=180, corner_radius=0)
        left.grid(row=0, column=0, sticky="ns")
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Templates",
                     font=ctk.CTkFont(weight="bold")).pack(pady=6, padx=6, anchor="w")
        ctk.CTkButton(left, text="+ New", height=28,
                       command=self._new_template).pack(padx=6, pady=4, fill="x")

        self._template_list = ctk.CTkScrollableFrame(left)
        self._template_list.pack(fill="both", expand=True, padx=4, pady=4)

        self._refresh_list()

        # Right panel — editor
        self._editor = ctk.CTkFrame(self, corner_radius=0)
        self._editor.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self._editor.grid_columnconfigure(1, weight=1)
        self._editor.grid_rowconfigure(7, weight=1)

        self._build_editor()

    def _build_editor(self):
        f = self._editor
        row = 0

        def labeled_entry(label, attr, r):
            ctk.CTkLabel(f, text=label, anchor="w", width=70).grid(
                row=r, column=0, padx=6, pady=3, sticky="w")
            e = ctk.CTkEntry(f)
            e.grid(row=r, column=1, padx=4, pady=3, sticky="ew")
            setattr(self, attr, e)
            self._add_var_autocomplete(e)

        labeled_entry("Name",     "_e_name",    0)
        labeled_entry("Category", "_e_cat",     1)
        labeled_entry("To",       "_e_to",      2)
        labeled_entry("CC",       "_e_cc",      3)
        labeled_entry("BCC",      "_e_bcc",     4)
        labeled_entry("Subject",  "_e_subject", 5)

        ctk.CTkLabel(f, text="Body", anchor="w", width=70).grid(
            row=6, column=0, padx=6, pady=3, sticky="nw")
        self._e_body = ctk.CTkTextbox(f, height=160,
                                       font=ctk.CTkFont(size=12))
        self._e_body.grid(row=6, column=1, padx=4, pady=3, sticky="nsew")
        f.grid_rowconfigure(6, weight=1)
        self._e_body.bind("<KeyRelease>", self._highlight_unresolved)

        # Attachments
        att_frame = ctk.CTkFrame(f, corner_radius=4)
        att_frame.grid(row=7, column=0, columnspan=2,
                        padx=6, pady=4, sticky="ew")
        ctk.CTkLabel(att_frame, text="Attachments:",
                     font=ctk.CTkFont(weight="bold")).pack(
            side="left", padx=8, pady=6)
        ctk.CTkButton(att_frame, text="+ Variable", width=100,
                       command=lambda: self._add_attachment("variable")).pack(
            side="left", padx=4, pady=4)
        ctk.CTkButton(att_frame, text="+ Pick File", width=100,
                       command=self._pick_attachment_file).pack(
            side="left", padx=4, pady=4)
        ctk.CTkButton(att_frame, text="Draft mode", width=100,
                       command=lambda: self._add_attachment("draft")).pack(
            side="left", padx=4, pady=4)

        self._att_list_label = ctk.CTkLabel(f, text="No attachments",
                                             font=ctk.CTkFont(size=11))
        self._att_list_label.grid(row=8, column=0, columnspan=2,
                                   padx=6, pady=2, sticky="w")

        # Execution mode + actions
        bottom = ctk.CTkFrame(f, corner_radius=0)
        bottom.grid(row=9, column=0, columnspan=2, padx=4, pady=6, sticky="ew")

        ctk.CTkLabel(bottom, text="Mode:").pack(side="left", padx=6)
        self._exec_mode = ctk.CTkOptionMenu(
            bottom,
            values=["send_directly", "open_for_review", "save_as_draft"])
        self._exec_mode.pack(side="left", padx=4)

        ctk.CTkButton(bottom, text="💾 Save", width=80,
                       command=self._save_template).pack(side="left", padx=8)
        ctk.CTkButton(bottom, text="👁 Preview", width=90,
                       command=self._preview).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="✉ Send", width=80,
                       command=self._send).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="📚 Vars", width=80,
                       command=self._open_var_library).pack(side="left", padx=4)

    # ── Template list ─────────────────────────────────────────────────────────

    def _refresh_list(self):
        for w in self._template_list.winfo_children():
            w.destroy()
        for t in self._templates:
            ctk.CTkButton(self._template_list, text=t.name, height=28, anchor="w",
                           command=lambda tpl=t: self._load_template(tpl)).pack(
                fill="x", pady=2)

    def _new_template(self):
        self._load_template(EmailTemplate())

    def _load_template(self, t: EmailTemplate):
        self._current = t
        for attr, field in (("name", "_e_name"), ("category", "_e_cat"),
                             ("to", "_e_to"), ("cc", "_e_cc"), ("bcc", "_e_bcc"),
                             ("subject", "_e_subject")):
            e = getattr(self, field)
            e.delete(0, "end")
            e.insert(0, getattr(t, attr))
        self._e_body.delete("1.0", "end")
        self._e_body.insert("1.0", t.body)
        self._exec_mode.set(t.exec_mode)
        self._refresh_att_label()

    def _save_template(self):
        if not self._current:
            return
        t = self._current
        t.name     = self._e_name.get()
        t.category = self._e_cat.get()
        t.to       = self._e_to.get()
        t.cc       = self._e_cc.get()
        t.bcc      = self._e_bcc.get()
        t.subject  = self._e_subject.get()
        t.body     = self._e_body.get("1.0", "end").strip()
        t.exec_mode = self._exec_mode.get()
        t.save()
        if t not in self._templates:
            self._templates.append(t)
        self._refresh_list()

    # ── Attachments ───────────────────────────────────────────────────────────

    def _add_attachment(self, mode: str):
        if not self._current:
            return
        if mode == "variable":
            dlg = ctk.CTkInputDialog(text="Variable path (e.g. {{reportName}}.pdf):",
                                     title="Attachment Variable")
            val = dlg.get_input()
            if val:
                self._current.attachments.append({"mode": "variable", "path": val})
        elif mode == "draft":
            self._current.attachments.append({"mode": "draft"})
        self._refresh_att_label()

    def _pick_attachment_file(self):
        if not self._current:
            return
        import tkinter.filedialog as fd
        files = fd.askopenfilenames(title="Select attachments")
        for f in files:
            self._current.attachments.append({"mode": "picker", "paths": [f]})
        self._refresh_att_label()

    def _refresh_att_label(self):
        if not self._current or not self._current.attachments:
            self._att_list_label.configure(text="No attachments")
            return
        names = []
        for a in self._current.attachments:
            if a["mode"] == "variable":
                names.append(a.get("path", "var"))
            elif a["mode"] == "picker":
                names.extend(Path(p).name for p in a.get("paths", []))
            else:
                names.append("[draft mode]")
        self._att_list_label.configure(text="  ".join(names))

    # ── Variable autocomplete ─────────────────────────────────────────────────

    def _add_var_autocomplete(self, entry: ctk.CTkEntry):
        def on_key(event):
            text = entry.get()
            pos  = entry.index(tk.INSERT)
            if text[max(0, pos-2):pos] == "{{":
                self._show_var_popup(entry)
        entry.bind("<KeyRelease>", on_key)

    def _show_var_popup(self, entry: ctk.CTkEntry):
        popup = ctk.CTkToplevel(self)
        popup.wm_overrideredirect(True)
        x = entry.winfo_rootx()
        y = entry.winfo_rooty() + entry.winfo_height()
        popup.geometry(f"200x150+{x}+{y}")
        popup.attributes("-topmost", True)

        scroll = ctk.CTkScrollableFrame(popup)
        scroll.pack(fill="both", expand=True)

        for var in get_var_mgr().all_variables():
            ctk.CTkButton(scroll, text=var.name, height=26, anchor="w",
                           command=lambda n=var.name, p=popup, e=entry:
                           self._insert_var(e, n, p)).pack(fill="x", pady=1)

        popup.bind("<FocusOut>", lambda _: popup.destroy())
        popup.focus_set()

    def _insert_var(self, entry: ctk.CTkEntry, name: str, popup):
        pos = entry.index(tk.INSERT)
        entry.insert(pos, f"{name}}}")
        popup.destroy()

    # ── Preview ───────────────────────────────────────────────────────────────

    def _preview(self):
        if not self._current:
            return
        var_mgr = get_var_mgr()
        PreviewWindow(self, self._current, var_mgr)

    # ── Send ──────────────────────────────────────────────────────────────────

    def _send(self):
        if not self._current:
            return
        self._save_template()
        from python.engine.email_sender import send_email, create_draft, open_compose
        t = self._current
        mode = t.exec_mode
        if mode == "send_directly":
            send_email(t.to_dict(), {})
        elif mode == "save_as_draft":
            create_draft(t.to_dict(), {})
        elif mode == "open_for_review":
            open_compose(t.to_dict(), {})

    def _open_var_library(self):
        from python.gui.variable_section import VarLibraryOverlay
        VarLibraryOverlay(self)

    def _highlight_unresolved(self, _event=None):
        body = self._e_body.get("1.0", "end")
        # Highlighting unresolved {{vars}} with orange is limited in CTkTextbox;
        # handled visually in PreviewWindow instead.


# ── Preview window ────────────────────────────────────────────────────────────

class PreviewWindow(ctk.CTkToplevel):
    def __init__(self, parent, template: EmailTemplate, var_mgr):
        super().__init__(parent)
        self.title("Email Preview")
        self.geometry("560x480")
        self._template = template
        self._var_mgr  = var_mgr
        self._build()

    def _build(self):
        def resolve(text: str) -> str:
            resolved = self._var_mgr.resolve(text)
            return resolved

        f = ctk.CTkFrame(self)
        f.pack(fill="both", expand=True, padx=12, pady=10)
        f.grid_columnconfigure(1, weight=1)

        for r, (label, value) in enumerate([
            ("To",      resolve(self._template.to)),
            ("CC",      resolve(self._template.cc)),
            ("Subject", resolve(self._template.subject)),
        ]):
            ctk.CTkLabel(f, text=label + ":", anchor="w", width=70,
                         font=ctk.CTkFont(weight="bold")).grid(
                row=r, column=0, padx=6, pady=3, sticky="w")
            ctk.CTkLabel(f, text=value, anchor="w").grid(
                row=r, column=1, padx=4, pady=3, sticky="w")

        ctk.CTkLabel(f, text="Body:", font=ctk.CTkFont(weight="bold")).grid(
            row=3, column=0, padx=6, pady=3, sticky="nw")
        body_box = ctk.CTkTextbox(f, font=ctk.CTkFont(size=12))
        body_box.grid(row=3, column=1, padx=4, pady=3, sticky="nsew")
        f.grid_rowconfigure(3, weight=1)

        body_text = resolve(self._template.body)
        body_box.insert("1.0", body_text)

        # Highlight unresolved {{...}} in orange (best-effort with tags)
        import re
        for match in re.finditer(r"\{\{[^}]+\}\}", body_text):
            start_idx = f"1.0+{match.start()}c"
            end_idx   = f"1.0+{match.end()}c"
            try:
                body_box.tag_add("unresolved", start_idx, end_idx)
                body_box.tag_config("unresolved", foreground="#FF9800")
            except Exception:
                pass
        body_box.configure(state="disabled")
