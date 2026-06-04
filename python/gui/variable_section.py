"""Variable section UI — list, add, edit, delete, scope promotion."""

from __future__ import annotations

import customtkinter as ctk

from python.engine.variable_manager import VarScope, VarType, get_manager


class VariableSection(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._mgr = get_manager()
        self._build()
        self.refresh()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(toolbar, text="+ Add Variable", width=130,
                       command=self._add_dialog).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(toolbar, text="📚 Var Library", width=130,
                       command=self._open_library).pack(side="left", padx=2, pady=6)

        # Scrollable list
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._scroll.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        # Header row
        for col, text in enumerate(["Name", "Value", "Type", "Scope", "Actions"]):
            ctk.CTkLabel(self._scroll, text=text,
                         font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=col, padx=6, pady=4, sticky="w")

    def refresh(self):
        for widget in self._scroll.winfo_children():
            info = widget.grid_info()
            if info and int(info.get("row", 0)) > 0:
                widget.destroy()

        for i, var in enumerate(self._mgr.all_variables(), start=1):
            ctk.CTkLabel(self._scroll, text=var.name).grid(
                row=i, column=0, padx=6, pady=2, sticky="w")
            ctk.CTkLabel(self._scroll, text=str(var.value)).grid(
                row=i, column=1, padx=6, pady=2, sticky="w")
            ctk.CTkLabel(self._scroll, text=var.type.value).grid(
                row=i, column=2, padx=6, pady=2, sticky="w")
            ctk.CTkLabel(self._scroll, text=var.scope.value).grid(
                row=i, column=3, padx=6, pady=2, sticky="w")

            actions = ctk.CTkFrame(self._scroll, fg_color="transparent")
            actions.grid(row=i, column=4, padx=4, pady=2)
            ctk.CTkButton(actions, text="Edit", width=50,
                           command=lambda v=var: self._edit_dialog(v)).pack(
                side="left", padx=2)
            ctk.CTkButton(actions, text="Del", width=44, fg_color="#B71C1C",
                           hover_color="#D32F2F",
                           command=lambda v=var: self._delete(v)).pack(
                side="left", padx=2)

    def _delete(self, var):
        self._mgr.delete(var.name, var.scope)
        self.refresh()

    def _add_dialog(self):
        _VarDialog(self, on_save=self._on_save)

    def _edit_dialog(self, var):
        _VarDialog(self, var=var, on_save=self._on_save)

    def _on_save(self, name, value, var_type, scope, description):
        self._mgr.set(name, value, VarScope(scope), VarType(var_type))
        self.refresh()

    def _open_library(self):
        VarLibraryOverlay(self)


class _VarDialog(ctk.CTkToplevel):
    def __init__(self, parent, var=None, on_save=None):
        super().__init__(parent)
        self.title("Variable" if var is None else f"Edit — {var.name}")
        self.geometry("400x320")
        self.grab_set()
        self._var = var
        self._on_save = on_save
        self._build(var)

    def _build(self, var):
        fields = ctk.CTkFrame(self)
        fields.pack(fill="both", expand=True, padx=16, pady=12)

        def row(label, widget_factory, default=""):
            f = ctk.CTkFrame(fields, fg_color="transparent")
            f.pack(fill="x", pady=4)
            ctk.CTkLabel(f, text=label, width=90, anchor="w").pack(side="left")
            w = widget_factory(f)
            w.pack(side="left", fill="x", expand=True)
            if hasattr(w, "insert") and default:
                w.insert(0, default)
            return w

        self._name  = row("Name",  lambda p: ctk.CTkEntry(p),
                          var.name if var else "")
        self._value = row("Value", lambda p: ctk.CTkEntry(p),
                          str(var.value) if var else "")
        self._type  = row("Type",  lambda p: ctk.CTkOptionMenu(
            p, values=[t.value for t in VarType]))
        self._scope = row("Scope", lambda p: ctk.CTkOptionMenu(
            p, values=[s.value for s in VarScope]))
        self._desc  = row("Description", lambda p: ctk.CTkEntry(p),
                          var.description if var else "")

        if var:
            self._type.set(var.type.value)
            self._scope.set(var.scope.value)

        ctk.CTkButton(self, text="Save", command=self._save).pack(pady=8)

    def _save(self):
        if self._on_save:
            self._on_save(
                self._name.get(),
                self._value.get(),
                self._type.get(),
                self._scope.get(),
                self._desc.get(),
            )
        self.destroy()


class VarLibraryOverlay(ctk.CTkToplevel):
    """Floating searchable variable library. Click to copy {{placeholder}}."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Variable Library")
        self.geometry("360x480")
        self.attributes("-topmost", True)
        self._mgr = get_manager()
        self._build()

    def _build(self):
        search_var = ctk.StringVar()
        search_var.trace_add("write", lambda *_: self._filter(search_var.get()))

        ctk.CTkEntry(self, placeholder_text="Search…",
                     textvariable=search_var).pack(
            fill="x", padx=8, pady=8)

        self._list = ctk.CTkScrollableFrame(self)
        self._list.grid_columnconfigure(0, weight=1)
        self._list.pack(fill="both", expand=True, padx=8, pady=4)

        self._filter("")

    def _filter(self, query: str):
        for w in self._list.winfo_children():
            w.destroy()

        q = query.lower()
        for var in self._mgr.all_variables():
            if q and q not in var.name.lower():
                continue
            placeholder = f"{{{{{var.name}}}}}"
            row = ctk.CTkFrame(self._list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=var.name, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=var.scope.value,
                         font=ctk.CTkFont(size=10),
                         text_color="gray").pack(side="left")
            ctk.CTkButton(row, text="Copy", width=52,
                           command=lambda p=placeholder: self._copy(p)).pack(
                side="right", padx=4)

    def _copy(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
