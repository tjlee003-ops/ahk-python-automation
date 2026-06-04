"""Workflow canvas — drag-and-drop node editor, 15 step types, branch/loop nodes."""

from __future__ import annotations

import json
import uuid
import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk
import tkinter as tk

from python.file_manager import path, write_json, read_json

STEP_TYPES = [
    "open_file", "window_focus", "click", "type_text", "clipboard",
    "wait", "branch", "loop", "send_email", "log", "notify",
    "run_step", "run_workflow", "stop", "error_handler",
]

BRANCH_OPERATORS = [
    "equals", "not equals", "greater than", "less than", "between",
    "contains", "starts with", "ends with", "is empty", "is not empty",
    "variable equals variable",
]

LOOP_MODES = ["repeat", "until_condition", "forever", "list_iteration"]

NODE_W, NODE_H = 160, 60
BRANCH_COLOR  = "#1565C0"
LOOP_COLOR    = "#6A1B9A"
STEP_COLOR    = "#1B5E20"
ERROR_COLOR   = "#B71C1C"
ANNO_COLOR    = "#F9A825"


# ── Data model ────────────────────────────────────────────────────────────────

class Node:
    def __init__(self, node_type: str = "step", x: int = 100, y: int = 100):
        self.id       = str(uuid.uuid4())
        self.type     = node_type   # step | branch | loop | annotation
        self.step_id  = ""
        self.label    = node_type.title()
        self.x        = x
        self.y        = y
        self.next     = ""
        self.yes      = ""          # branch yes
        self.no       = ""          # branch no
        self.body     = ""          # loop body
        self.config: dict[str, Any] = {}
        self.error_handler = "stop"
        self.exec_mode = "ahk"
        self.comment   = ""
        self.state     = "idle"     # idle | running | success | error | skipped

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "step_id": self.step_id,
            "label": self.label, "position": {"x": self.x, "y": self.y},
            "next": self.next, "yes": self.yes, "no": self.no,
            "body": self.body, "config": self.config,
            "error_handler": self.error_handler,
            "exec_mode": self.exec_mode, "comment": self.comment,
        }

    @staticmethod
    def from_dict(d: dict) -> "Node":
        n = Node(d.get("type", "step"), d.get("position", {}).get("x", 0),
                 d.get("position", {}).get("y", 0))
        n.id = d.get("id", n.id)
        n.step_id = d.get("step_id", "")
        n.label   = d.get("label", n.type.title())
        n.next    = d.get("next", "")
        n.yes     = d.get("yes", "")
        n.no      = d.get("no", "")
        n.body    = d.get("body", "")
        n.config  = d.get("config", {})
        n.error_handler = d.get("error_handler", "stop")
        n.exec_mode     = d.get("exec_mode", "ahk")
        n.comment       = d.get("comment", "")
        return n


class Annotation:
    def __init__(self, text: str = "", x: int = 0, y: int = 0, color: str = "yellow"):
        self.id    = str(uuid.uuid4())
        self.type  = "sticky"
        self.text  = text
        self.x     = x
        self.y     = y
        self.color = color

    def to_dict(self) -> dict:
        return {"id": self.id, "type": self.type, "text": self.text,
                "position": {"x": self.x, "y": self.y}, "color": self.color}

    @staticmethod
    def from_dict(d: dict) -> "Annotation":
        a = Annotation(d.get("text", ""), d.get("position", {}).get("x", 0),
                        d.get("position", {}).get("y", 0), d.get("color", "yellow"))
        a.id = d.get("id", a.id)
        return a


class Workflow:
    def __init__(self, name: str = "Untitled"):
        self.id      = str(uuid.uuid4())
        self.name    = name
        self.version = 1
        self.mode    = "ahk"
        self.nodes: dict[str, Node] = {}
        self.annotations: list[Annotation] = []

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "current_version": self.version,
            "default_mode": self.mode,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "annotations": [a.to_dict() for a in self.annotations],
        }

    @staticmethod
    def from_dict(d: dict) -> "Workflow":
        w = Workflow(d.get("name", "Untitled"))
        w.id      = d.get("id", w.id)
        w.version = d.get("current_version", 1)
        w.mode    = d.get("default_mode", "ahk")
        for nd in d.get("nodes", []):
            n = Node.from_dict(nd)
            w.nodes[n.id] = n
        for ad in d.get("annotations", []):
            w.annotations.append(Annotation.from_dict(ad))
        return w

    def save(self):
        dest = path(f"library/workflows/{self.name}")
        dest.mkdir(parents=True, exist_ok=True)
        versions = dest / "versions"
        versions.mkdir(exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        write_json(f"library/workflows/{self.name}/versions/v{self.version}_{ts}.json",
                   self.to_dict())
        write_json(f"library/workflows/{self.name}/workflow.json", self.to_dict())

    @staticmethod
    def load(name: str) -> "Workflow | None":
        data = read_json(f"library/workflows/{name}/workflow.json")
        return Workflow.from_dict(data) if data else None


# ── Canvas widget ─────────────────────────────────────────────────────────────

class WorkflowCanvas(tk.Canvas):
    def __init__(self, master, workflow: Workflow, **kw):
        super().__init__(master, bg="#1a1a2e", **kw)
        self._wf = workflow
        self._selected: str | None = None
        self._drag_data: dict = {}
        self._pan_data: dict = {}
        self._offset = [0, 0]
        self._scale  = 1.0
        self._show_annotations = True
        self._canvas_items: dict[str, int] = {}  # node_id → canvas item id

        self.bind("<ButtonPress-1>",   self._on_lclick)
        self.bind("<B1-Motion>",       self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<ButtonPress-2>",   self._on_rclick)
        self.bind("<ButtonPress-3>",   self._on_rclick)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<MouseWheel>",      self._on_scroll)
        self.bind("a",                 lambda e: self._toggle_annotations())
        self.focus_set()

        self.render()

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        self.delete("all")
        ox, oy = self._offset
        sc = self._scale

        # Draw connections
        for node in self._wf.nodes.values():
            sx = int((node.x + NODE_W / 2 + ox) * sc)
            sy = int((node.y + NODE_H + oy) * sc)
            for target_id in filter(None, [node.next, node.yes, node.no, node.body]):
                target = self._wf.nodes.get(target_id)
                if target:
                    tx = int((target.x + NODE_W / 2 + ox) * sc)
                    ty = int((target.y + oy) * sc)
                    color = "#4CAF50" if node.yes == target_id else \
                            "#F44336" if node.no  == target_id else "#90CAF9"
                    self.create_line(sx, sy, tx, ty, fill=color, width=2, arrow=tk.LAST)

        # Draw nodes
        for node in self._wf.nodes.values():
            self._draw_node(node, ox, oy, sc)

        # Draw annotations
        if self._show_annotations:
            for ann in self._wf.annotations:
                ax = int((ann.x + ox) * sc)
                ay = int((ann.y + oy) * sc)
                self.create_rectangle(ax, ay, ax + 140, ay + 60,
                                      fill=ANNO_COLOR, outline="#F57F17")
                self.create_text(ax + 6, ay + 6, text=ann.text, anchor="nw",
                                  fill="black", width=128)

        # Mini-map
        self._draw_minimap()

    def _draw_node(self, node: Node, ox: int, oy: int, sc: float):
        nx = int((node.x + ox) * sc)
        ny = int((node.y + oy) * sc)
        nw = int(NODE_W * sc)
        nh = int(NODE_H * sc)

        color = {
            "branch": BRANCH_COLOR,
            "loop":   LOOP_COLOR,
            "error_handler": ERROR_COLOR,
        }.get(node.type, STEP_COLOR)

        state_outline = {
            "running": "#FFD600",
            "success": "#4CAF50",
            "error":   "#F44336",
            "skipped": "#9E9E9E",
        }.get(node.state, "#FFFFFF")

        tag = f"node_{node.id}"
        item = self.create_rectangle(nx, ny, nx + nw, ny + nh,
                                      fill=color, outline=state_outline,
                                      width=2 if node.state != "idle" else 1,
                                      tags=(tag,))
        self._canvas_items[node.id] = item
        self.create_text(nx + nw // 2, ny + nh // 2,
                          text=node.label, fill="white",
                          font=("Arial", max(8, int(11 * sc))), tags=(tag,))
        if node.comment:
            self.create_text(nx + 4, ny - 10, text=f"💬 {node.comment[:20]}",
                              fill="#FFD600", anchor="w",
                              font=("Arial", max(7, int(9 * sc))))
        if node.id == self._selected:
            self.create_rectangle(nx - 3, ny - 3, nx + nw + 3, ny + nh + 3,
                                   outline="#FFD600", width=2, dash=(4, 2))

    def _draw_minimap(self):
        w, h = self.winfo_width() or 800, self.winfo_height() or 600
        mm_w, mm_h = 120, 80
        mm_x, mm_y = w - mm_w - 8, h - mm_h - 8
        self.create_rectangle(mm_x, mm_y, mm_x + mm_w, mm_y + mm_h,
                               fill="#111122", outline="#333355")
        if not self._wf.nodes:
            return
        xs = [n.x for n in self._wf.nodes.values()]
        ys = [n.y for n in self._wf.nodes.values()]
        min_x, max_x = min(xs), max(xs) + NODE_W
        min_y, max_y = min(ys), max(ys) + NODE_H
        span_x = max(max_x - min_x, 1)
        span_y = max(max_y - min_y, 1)
        for node in self._wf.nodes.values():
            rx = mm_x + int((node.x - min_x) / span_x * mm_w)
            ry = mm_y + int((node.y - min_y) / span_y * mm_h)
            color = BRANCH_COLOR if node.type == "branch" else \
                    LOOP_COLOR if node.type == "loop" else STEP_COLOR
            self.create_rectangle(rx, ry, rx + 8, ry + 5, fill=color, outline="")

    # ── Interaction ───────────────────────────────────────────────────────────

    def _node_at(self, x: int, y: int) -> str | None:
        ox, oy = self._offset
        sc = self._scale
        cx = x / sc - ox
        cy = y / sc - oy
        for node in self._wf.nodes.values():
            if node.x <= cx <= node.x + NODE_W and node.y <= cy <= node.y + NODE_H:
                return node.id
        return None

    def _on_lclick(self, event):
        nid = self._node_at(event.x, event.y)
        self._selected = nid
        if nid:
            node = self._wf.nodes[nid]
            self._drag_data = {"id": nid, "start_x": event.x, "start_y": event.y,
                                "node_x": node.x, "node_y": node.y}
        else:
            self._drag_data = {}
            self._pan_data = {"x": event.x, "y": event.y}
        self.render()

    def _on_drag(self, event):
        if self._drag_data:
            sc = self._scale
            dx = (event.x - self._drag_data["start_x"]) / sc
            dy = (event.y - self._drag_data["start_y"]) / sc
            node = self._wf.nodes[self._drag_data["id"]]
            node.x = int(self._drag_data["node_x"] + dx)
            node.y = int(self._drag_data["node_y"] + dy)
            self.render()
        elif self._pan_data:
            self._offset[0] += (event.x - self._pan_data["x"]) / self._scale
            self._offset[1] += (event.y - self._pan_data["y"]) / self._scale
            self._pan_data = {"x": event.x, "y": event.y}
            self.render()

    def _on_release(self, _event):
        self._drag_data = {}
        self._pan_data  = {}

    def _on_rclick(self, event):
        nid = self._node_at(event.x, event.y)
        menu = tk.Menu(self, tearoff=0)
        if nid:
            menu.add_command(label="Edit", command=lambda: self._edit_node(nid))
            menu.add_command(label="Duplicate", command=lambda: self._duplicate_node(nid))
            menu.add_command(label="Add Comment", command=lambda: self._add_comment(nid))
            menu.add_separator()
            menu.add_command(label="Delete", command=lambda: self._delete_node(nid))
        else:
            for st in STEP_TYPES:
                menu.add_command(
                    label=st.replace("_", " ").title(),
                    command=lambda t=st, ex=event: self._add_node(t, ex.x, ex.y))
            menu.add_separator()
            menu.add_command(label="Add Sticky Note",
                              command=lambda: self._add_annotation(event.x, event.y))
        menu.tk_popup(event.x_root, event.y_root)

    def _on_double_click(self, event):
        nid = self._node_at(event.x, event.y)
        if nid:
            self._edit_node(nid)
        else:
            self._add_annotation(event.x, event.y)

    def _on_scroll(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self._scale = max(0.3, min(3.0, self._scale * factor))
        self.render()

    # ── Node operations ───────────────────────────────────────────────────────

    def _add_node(self, node_type: str, cx: int, cy: int):
        sc = self._scale
        ox, oy = self._offset
        x = int(cx / sc - ox)
        y = int(cy / sc - oy)
        node = Node(node_type, x, y)
        node.label = node_type.replace("_", " ").title()
        self._wf.nodes[node.id] = node
        self._selected = node.id
        self.render()

    def _delete_node(self, nid: str):
        self._wf.nodes.pop(nid, None)
        for n in self._wf.nodes.values():
            if n.next == nid:   n.next = ""
            if n.yes  == nid:   n.yes  = ""
            if n.no   == nid:   n.no   = ""
            if n.body == nid:   n.body = ""
        self._selected = None
        self.render()

    def _duplicate_node(self, nid: str):
        src = self._wf.nodes.get(nid)
        if not src:
            return
        n = Node.from_dict(src.to_dict())
        n.id = str(uuid.uuid4())
        n.x += 20
        n.y += 20
        n.next = n.yes = n.no = n.body = ""
        self._wf.nodes[n.id] = n
        self.render()

    def _edit_node(self, nid: str):
        node = self._wf.nodes.get(nid)
        if node:
            NodeEditDialog(self, node, on_save=lambda: self.render())

    def _add_comment(self, nid: str):
        node = self._wf.nodes.get(nid)
        if not node:
            return
        dialog = ctk.CTkInputDialog(text="Comment:", title="Add Comment")
        val = dialog.get_input()
        if val:
            node.comment = val
            self.render()

    def _add_annotation(self, cx: int, cy: int):
        sc = self._scale
        ox, oy = self._offset
        x = int(cx / sc - ox)
        y = int(cy / sc - oy)
        dialog = ctk.CTkInputDialog(text="Sticky note text:", title="Add Note")
        text = dialog.get_input()
        if text:
            self._wf.annotations.append(Annotation(text, x, y))
            self.render()

    def _toggle_annotations(self):
        self._show_annotations = not self._show_annotations
        self.render()

    def set_node_state(self, node_id: str, state: str):
        node = self._wf.nodes.get(node_id)
        if node:
            node.state = state
            self.render()

    def save(self):
        self._wf.version += 1
        self._wf.save()


# ── Node edit dialog ──────────────────────────────────────────────────────────

class NodeEditDialog(ctk.CTkToplevel):
    def __init__(self, parent, node: Node, on_save=None):
        super().__init__(parent)
        self.title(f"Edit Node — {node.label}")
        self.geometry("460x380")
        self.grab_set()
        self._node = node
        self._on_save = on_save
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self)
        f.pack(fill="both", expand=True, padx=12, pady=10)

        def row(label, default=""):
            fr = ctk.CTkFrame(f, fg_color="transparent")
            fr.pack(fill="x", pady=3)
            ctk.CTkLabel(fr, text=label, width=130, anchor="w").pack(side="left")
            e = ctk.CTkEntry(fr)
            e.pack(side="left", fill="x", expand=True)
            if default:
                e.insert(0, default)
            return e

        node = self._node
        self._label = row("Label", node.label)
        self._step_id = row("Step ID", node.step_id)

        if node.type == "branch":
            self._cond = row("Condition", node.config.get("condition", ""))
            self._yes  = row("Yes → node ID", node.yes)
            self._no   = row("No  → node ID", node.no)

        elif node.type == "loop":
            fr = ctk.CTkFrame(f, fg_color="transparent")
            fr.pack(fill="x", pady=3)
            ctk.CTkLabel(fr, text="Loop mode", width=130, anchor="w").pack(side="left")
            self._loop_mode = ctk.CTkOptionMenu(fr, values=LOOP_MODES)
            self._loop_mode.set(node.config.get("mode", "repeat"))
            self._loop_mode.pack(side="left")
            self._loop_count = row("Count / condition", str(node.config.get("count", "")))
            self._body = row("Body node ID", node.body)
            self._next = row("Next node ID", node.next)

        else:
            self._next = row("Next node ID", node.next)
            fr = ctk.CTkFrame(f, fg_color="transparent")
            fr.pack(fill="x", pady=3)
            ctk.CTkLabel(fr, text="Error handler", width=130, anchor="w").pack(side="left")
            self._err = ctk.CTkOptionMenu(
                fr, values=["stop", "skip", "retry", "run_error_workflow", "notify_user"])
            self._err.set(node.error_handler)
            self._err.pack(side="left")
            fr2 = ctk.CTkFrame(f, fg_color="transparent")
            fr2.pack(fill="x", pady=3)
            ctk.CTkLabel(fr2, text="Exec mode", width=130, anchor="w").pack(side="left")
            self._mode = ctk.CTkOptionMenu(fr2, values=["ahk", "python"])
            self._mode.set(node.exec_mode)
            self._mode.pack(side="left")

        ctk.CTkButton(self, text="Save", command=self._save).pack(pady=8)

    def _save(self):
        n = self._node
        n.label   = self._label.get()
        n.step_id = self._step_id.get() if hasattr(self, "_step_id") else n.step_id

        if n.type == "branch":
            n.config["condition"] = self._cond.get()
            n.yes = self._yes.get()
            n.no  = self._no.get()
        elif n.type == "loop":
            n.config["mode"]  = self._loop_mode.get()
            n.config["count"] = self._loop_count.get()
            n.body = self._body.get()
            n.next = self._next.get()
        else:
            n.next         = self._next.get()
            n.error_handler = self._err.get()
            n.exec_mode    = self._mode.get()

        if self._on_save:
            self._on_save()
        self.destroy()


# ── Workflow section (tab content) ────────────────────────────────────────────

class WorkflowSection(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._workflow = Workflow("New Workflow")
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(self, height=44, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(toolbar, text="💾 Save", width=80,
                       command=self._save).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(toolbar, text="▶ Run", width=70,
                       command=self._run).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, text="📂 Load", width=80,
                       command=self._load_dialog).pack(side="left", padx=2, pady=6)

        name_label = ctk.CTkLabel(toolbar, text="Name:")
        name_label.pack(side="left", padx=(12, 2))
        self._name_entry = ctk.CTkEntry(toolbar, width=140)
        self._name_entry.insert(0, self._workflow.name)
        self._name_entry.pack(side="left")

        mode_label = ctk.CTkLabel(toolbar, text="Mode:")
        mode_label.pack(side="left", padx=(12, 2))
        self._mode = ctk.CTkOptionMenu(toolbar, values=["ahk", "python"], width=90)
        self._mode.set(self._workflow.mode)
        self._mode.pack(side="left")

        self._canvas = WorkflowCanvas(self, self._workflow, highlightthickness=0)
        self._canvas.grid(row=1, column=0, sticky="nsew")

        self.bind("<Control-s>", lambda _: self._save())

    def _save(self):
        self._workflow.name = self._name_entry.get() or "Untitled"
        self._workflow.mode = self._mode.get()
        self._canvas.save()

    def _run(self):
        from python.engine.workflow_runner import get_runner
        runner = get_runner()
        runner.run(self._workflow, canvas=self._canvas)

    def _load_dialog(self):
        lib = path("library/workflows")
        workflows = [p.name for p in lib.iterdir() if p.is_dir()] if lib.exists() else []
        if not workflows:
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Load Workflow")
        dlg.geometry("300x300")
        dlg.grab_set()
        lb = ctk.CTkScrollableFrame(dlg)
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        for wname in workflows:
            ctk.CTkButton(lb, text=wname,
                           command=lambda n=wname, d=dlg: self._load(n, d)).pack(
                fill="x", pady=2)

    def _load(self, name: str, dialog):
        wf = Workflow.load(name)
        if wf:
            self._workflow = wf
            self._name_entry.delete(0, "end")
            self._name_entry.insert(0, wf.name)
            self._mode.set(wf.mode)
            self._canvas._wf = wf
            self._canvas.render()
        dialog.destroy()
