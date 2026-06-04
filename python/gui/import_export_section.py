"""Import / Export UI — drag-drop, conflict resolution dialog, asset preview."""

from __future__ import annotations

import tkinter.filedialog as fd

import customtkinter as ctk

from python.engine.bundle_manager import (
    ConflictResolution, export_full, export_selection, export_workflow,
    import_bundle, read_bundle,
)


class ImportExportSection(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure((0, 1), weight=1)

        # Export panel
        export_frame = ctk.CTkFrame(self, corner_radius=6)
        export_frame.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        ctk.CTkLabel(export_frame, text="Export",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            pady=10, padx=12, anchor="w")

        ctk.CTkButton(export_frame, text="Export Full (data + library)",
                       command=self._export_full).pack(
            fill="x", padx=12, pady=4)
        ctk.CTkButton(export_frame, text="Export Workflow Bundle…",
                       command=self._export_workflow).pack(
            fill="x", padx=12, pady=4)
        ctk.CTkButton(export_frame, text="Export Custom Selection…",
                       command=self._export_selection).pack(
            fill="x", padx=12, pady=4)

        # Import panel
        import_frame = ctk.CTkFrame(self, corner_radius=6)
        import_frame.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")

        ctk.CTkLabel(import_frame, text="Import",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            pady=10, padx=12, anchor="w")

        drop_zone = ctk.CTkLabel(
            import_frame,
            text="Drop .bundle file here\nor click to browse",
            height=80,
            corner_radius=6,
            fg_color=("gray80", "gray25"),
        )
        drop_zone.pack(fill="x", padx=12, pady=8)
        drop_zone.bind("<Button-1>", lambda _: self._browse_import())

        ctk.CTkButton(import_frame, text="Browse .bundle…",
                       command=self._browse_import).pack(
            fill="x", padx=12, pady=4)
        ctk.CTkButton(import_frame, text="View Reference Template",
                       command=self._view_reference).pack(
            fill="x", padx=12, pady=4)

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_full(self):
        dest = fd.asksaveasfilename(
            title="Export full bundle",
            defaultextension=".bundle",
            filetypes=[("Bundle files", "*.bundle")],
        )
        if dest:
            export_full(dest)

    def _export_workflow(self):
        dlg = ctk.CTkInputDialog(text="Workflow ID to export:", title="Export Workflow")
        wid = dlg.get_input()
        if not wid:
            return
        dest = fd.asksaveasfilename(
            title="Save workflow bundle",
            defaultextension=".bundle",
            filetypes=[("Bundle files", "*.bundle")],
        )
        if dest:
            export_workflow(wid, dest)

    def _export_selection(self):
        AssetPickerDialog(self, on_export=self._do_export_selection)

    def _do_export_selection(self, paths: list[str]):
        if not paths:
            return
        dest = fd.asksaveasfilename(
            title="Save selection bundle",
            defaultextension=".bundle",
            filetypes=[("Bundle files", "*.bundle")],
        )
        if dest:
            export_selection(paths, dest)

    # ── Import ────────────────────────────────────────────────────────────────

    def _browse_import(self):
        src = fd.askopenfilename(
            title="Open .bundle",
            filetypes=[("Bundle files", "*.bundle"), ("All files", "*.*")],
        )
        if src:
            self._run_import(src)

    def _run_import(self, src: str):
        try:
            manifest, previews = read_bundle(src)
        except Exception as e:
            return
        ConflictDialog(self, previews, on_confirm=lambda res, default:
                       self._do_import(src, res, default))

    def _do_import(self, src: str, resolutions: dict, default: str):
        result = import_bundle(src, resolutions, default)

    def _view_reference(self):
        from python.engine.bundle_manager import ensure_reference_bundle
        from python.file_manager import path
        ensure_reference_bundle()
        ref = str(path("templates/import_template.bundle"))
        try:
            manifest, previews = read_bundle(ref)
            PreviewDialog(self, previews, readonly=True)
        except Exception:
            pass


# ── Conflict resolution dialog ────────────────────────────────────────────────

class ConflictDialog(ctk.CTkToplevel):
    def __init__(self, parent, previews: list[dict], on_confirm=None):
        super().__init__(parent)
        self.title("Import — Conflict Resolution")
        self.geometry("600x480")
        self.grab_set()
        self._previews  = previews
        self._on_confirm = on_confirm
        self._resolutions: dict[str, ctk.StringVar] = {}
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Choose how to handle each asset:",
                     font=ctk.CTkFont(weight="bold")).pack(padx=12, pady=8, anchor="w")

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=8, pady=4)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        from python.file_manager import path
        options = [ConflictResolution.KEEP_EXISTING,
                   ConflictResolution.OVERWRITE,
                   ConflictResolution.COPY]

        for i, asset in enumerate(self._previews):
            ctk.CTkLabel(scroll, text=asset["name"] or asset["path"],
                         anchor="w").grid(row=i, column=0, padx=6, pady=3, sticky="w")
            ctk.CTkLabel(scroll, text=asset["type"],
                         font=ctk.CTkFont(size=11),
                         text_color="gray").grid(row=i, column=1, padx=4, pady=3)

            var = ctk.StringVar(value=ConflictResolution.KEEP_EXISTING)
            self._resolutions[asset["path"]] = var
            existing = path(asset["path"]).exists()
            om = ctk.CTkOptionMenu(scroll, variable=var,
                                    values=options,
                                    fg_color="#B71C1C" if existing else None)
            om.grid(row=i, column=2, padx=4, pady=3)

        # Apply to all
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(bottom, text="Apply to all:").pack(side="left", padx=4)
        self._default_var = ctk.StringVar(value=ConflictResolution.KEEP_EXISTING)
        ctk.CTkOptionMenu(bottom, variable=self._default_var,
                           values=[ConflictResolution.KEEP_EXISTING,
                                   ConflictResolution.OVERWRITE,
                                   ConflictResolution.COPY],
                           command=self._apply_to_all).pack(side="left", padx=4)

        ctk.CTkButton(self, text="Import", command=self._confirm).pack(pady=8)

    def _apply_to_all(self, val: str):
        for var in self._resolutions.values():
            var.set(val)

    def _confirm(self):
        resolutions = {p: v.get() for p, v in self._resolutions.items()}
        if self._on_confirm:
            self._on_confirm(resolutions, self._default_var.get())
        self.destroy()


class PreviewDialog(ctk.CTkToplevel):
    def __init__(self, parent, previews: list[dict], readonly: bool = False):
        super().__init__(parent)
        self.title("Bundle Contents" + (" (Read-only)" if readonly else ""))
        self.geometry("500x400")
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        for asset in previews:
            ctk.CTkLabel(scroll,
                         text=f"{asset['type']:12}  {asset['name'] or asset['path']}",
                         font=ctk.CTkFont(family="Courier New", size=11),
                         anchor="w").pack(fill="x", padx=4, pady=1)


class AssetPickerDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_export=None):
        super().__init__(parent)
        self.title("Select Assets to Export")
        self.geometry("500x420")
        self.grab_set()
        self._on_export = on_export
        self._vars: dict[str, ctk.BooleanVar] = {}
        self._build()

    def _build(self):
        from python.file_manager import path
        scroll = ctk.CTkScrollableFrame(self, label_text="Check assets to include:")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        dirs = ["library/workflows", "library/steps", "library/templates"]
        for d in dirs:
            p = path(d)
            if not p.exists():
                continue
            for f in p.rglob("*.json"):
                rel = str(f.relative_to(path("")))
                var = ctk.BooleanVar(value=False)
                self._vars[rel] = var
                ctk.CTkCheckBox(scroll, text=rel, variable=var).pack(
                    anchor="w", padx=6, pady=1)

        ctk.CTkButton(self, text="Export Selected",
                       command=self._confirm).pack(pady=8)

    def _confirm(self):
        selected = [p for p, v in self._vars.items() if v.get()]
        if self._on_export:
            self._on_export(selected)
        self.destroy()
