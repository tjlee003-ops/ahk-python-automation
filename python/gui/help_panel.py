"""In-app help drawer — context-sensitive, searchable, per-section tooltips."""

from __future__ import annotations

import customtkinter as ctk

from python.engine.guide_generator import CHAPTERS, CONTENT

# Maps sidebar section keys to guide chapter slugs
SECTION_TO_CHAPTER = {
    "recorder":  "macro_recorder",
    "triggers":  "triggers",
    "variables": "variables",
    "workflows": "workflows",
    "email":     "email_templates",
}


class HelpPanel(ctk.CTkToplevel):
    """Floating help drawer. Opens to the chapter matching the active section."""

    def __init__(self, parent, active_section: str = "getting_started"):
        super().__init__(parent)
        self.title("Help")
        self.geometry("560x600")
        self.attributes("-topmost", True)
        self.resizable(True, True)
        self._build()
        chapter = SECTION_TO_CHAPTER.get(active_section, "getting_started")
        self._show_chapter(chapter)

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Search bar
        search_var = ctk.StringVar()
        search_var.trace_add("write", lambda *_: self._search(search_var.get()))
        search_entry = ctk.CTkEntry(self, placeholder_text="Search help…",
                                    textvariable=search_var)
        search_entry.grid(row=0, column=0, columnspan=2, padx=8, pady=8, sticky="ew")

        # Chapter list (left)
        self._nav = ctk.CTkScrollableFrame(self, width=160)
        self._nav.grid(row=1, column=0, padx=(8, 0), pady=4, sticky="ns")

        for slug, title in CHAPTERS:
            ctk.CTkButton(
                self._nav, text=title, height=28, anchor="w",
                fg_color="transparent", hover_color=("gray75", "gray30"),
                command=lambda s=slug: self._show_chapter(s),
            ).pack(fill="x", pady=1)

        # Content area (right)
        self._content = ctk.CTkTextbox(self, font=ctk.CTkFont(size=13))
        self._content.grid(row=1, column=1, padx=8, pady=4, sticky="nsew")
        self.grid_columnconfigure(1, weight=1)

    def _show_chapter(self, slug: str):
        import re
        html = CONTENT.get(slug, "")
        # Strip HTML tags for plain-text display
        text = re.sub(r"<[^>]+>", "", html)
        text = text.replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")
        self._content.configure(state="normal")
        self._content.delete("1.0", "end")
        self._content.insert("1.0", text.strip())
        self._content.configure(state="disabled")

    def _search(self, query: str):
        if not query:
            return
        q = query.lower()
        for slug, title in CHAPTERS:
            if q in CONTENT.get(slug, "").lower() or q in title.lower():
                self._show_chapter(slug)
                return
