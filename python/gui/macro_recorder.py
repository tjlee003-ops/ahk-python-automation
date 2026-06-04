"""Macro recorder — pynput capture, auto-filter, playback, extract dialog."""

from __future__ import annotations

import datetime
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import customtkinter as ctk

from python.file_manager import path, write_json
from python.engine.variable_manager import get_manager

try:
    from pynput import keyboard as kb, mouse as ms
    _PYNPUT = True
except ImportError:
    _PYNPUT = False

try:
    import win32gui, win32process
    import psutil
    _WIN32 = True
except ImportError:
    _WIN32 = False

RECORDINGS_DIR = "logs/recordings"


# ── Event model ──────────────────────────────────────────────────────────────

class RecordedEvent:
    def __init__(self, kind: str, data: dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.ts = time.time()
        self.kind = kind   # keystroke | click | move | scroll | focus | delay
        self.data = data

    def summary(self) -> str:
        if self.kind == "keystroke":
            return f"Key: {self.data.get('key')}"
        if self.kind == "click":
            return f"Click {self.data.get('button')} at ({self.data.get('x')},{self.data.get('y')}) — {self.data.get('window','')}"
        if self.kind == "move":
            return f"Move ({self.data.get('x')},{self.data.get('y')})"
        if self.kind == "scroll":
            return f"Scroll dy={self.data.get('dy')}"
        if self.kind == "focus":
            return f"Focus: {self.data.get('title')}"
        if self.kind == "delay":
            return f"Delay {self.data.get('ms')}ms"
        return self.kind

    def to_dict(self) -> dict:
        return {"id": self.id, "ts": self.ts, "kind": self.kind, "data": self.data}


# ── Capture engine ────────────────────────────────────────────────────────────

class CaptureEngine:
    def __init__(self):
        self._events: list[RecordedEvent] = []
        self._running = False
        self._kb_listener = None
        self._ms_listener = None
        self._last_move_time = 0.0
        self._last_move_pos = (0, 0)
        self._last_focus = ""

    def start(self):
        self._events.clear()
        self._running = True
        if _PYNPUT:
            self._kb_listener = kb.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._ms_listener = ms.Listener(
                on_click=self._on_click,
                on_move=self._on_move,
                on_scroll=self._on_scroll,
            )
            self._kb_listener.start()
            self._ms_listener.start()
        threading.Thread(target=self._focus_poll, daemon=True).start()

    def stop(self) -> list[RecordedEvent]:
        self._running = False
        if self._kb_listener:
            self._kb_listener.stop()
        if self._ms_listener:
            self._ms_listener.stop()
        return list(self._events)

    # ── pynput callbacks ──────────────────────────────────────────────────────

    def _on_key_press(self, key):
        try:
            k = key.char if hasattr(key, "char") and key.char else str(key)
        except Exception:
            k = str(key)
        self._add(RecordedEvent("keystroke", {"key": k, "action": "press"}))

    def _on_key_release(self, key):
        pass  # only capture press

    def _on_click(self, x, y, button, pressed):
        if not pressed:
            return
        win_title, process, control = self._window_context(x, y)
        self._add(RecordedEvent("click", {
            "x": x, "y": y,
            "button": str(button).split(".")[-1],
            "window": win_title,
            "process": process,
            "control": control,
        }))

    def _on_move(self, x, y):
        now = time.time()
        if now - self._last_move_time > 0.1:  # throttle
            self._last_move_time = now
            self._last_move_pos = (x, y)
            self._add(RecordedEvent("move", {"x": x, "y": y}))

    def _on_scroll(self, x, y, dx, dy):
        self._add(RecordedEvent("scroll", {"x": x, "y": y, "dx": dx, "dy": dy}))

    def _focus_poll(self):
        while self._running:
            if _WIN32:
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd)
                    if title and title != self._last_focus:
                        self._last_focus = title
                        self._add(RecordedEvent("focus", {"title": title, "hwnd": hwnd}))
                except Exception:
                    pass
            time.sleep(0.5)

    def _window_context(self, x: int, y: int) -> tuple[str, str, str]:
        if not _WIN32:
            return "", "", ""
        try:
            hwnd = win32gui.WindowFromPoint((x, y))
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid).name() if pid else ""
            ctrl = win32gui.GetClassName(hwnd)
            return title, proc, ctrl
        except Exception:
            return "", "", ""

    def _add(self, event: RecordedEvent):
        if self._events:
            delay_ms = int((event.ts - self._events[-1].ts) * 1000)
            if delay_ms > 50:
                self._events.append(RecordedEvent("delay", {"ms": delay_ms}))
        self._events.append(event)


# ── Auto-filter ────────────────────────────────────────────────────────────────

def auto_filter(events: list[RecordedEvent]) -> tuple[list[RecordedEvent], int]:
    """Strip mouse moves <50ms with no click; collapse redundant moves."""
    filtered = []
    removed = 0
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.kind == "move":
            # Look ahead: skip move if next meaningful event is a click on same control
            j = i + 1
            while j < len(events) and events[j].kind in ("move", "delay"):
                j += 1
            if j < len(events) and events[j].kind == "click":
                click = events[j]
                if (ev.data.get("x") == click.data.get("x") and
                        ev.data.get("y") == click.data.get("y")):
                    removed += 1
                    i += 1
                    continue
            next_delay = events[i + 1] if i + 1 < len(events) else None
            if next_delay and next_delay.kind == "delay" and next_delay.data.get("ms", 999) < 50:
                removed += 1
                i += 1
                continue
        filtered.append(ev)
        i += 1
    return filtered, removed


# ── Step JSON builder ─────────────────────────────────────────────────────────

def build_step_json(name: str, description: str, mode: str,
                    events: list[RecordedEvent]) -> dict:
    from python.converters.py_to_ahk import convert

    ahk_lines = []
    py_lines = []
    inputs = []

    for ev in events:
        step = {"type": ev.kind, **ev.data}
        ahk = convert(step) or f"; {ev.summary()}"
        ahk_lines.append(ahk)
        py_lines.append(f"# {ev.summary()}")

    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "created": datetime.datetime.now().isoformat(),
        "version": 1,
        "tags": [],
        "execution": {
            "default_mode": mode,
            "ahk": "\n".join(ahk_lines),
            "python": "\n".join(py_lines),
        },
        "inputs": inputs,
        "outputs": [],
        "error_handler": "notify_user",
        "targeting": {},
    }


# ── UI ────────────────────────────────────────────────────────────────────────

class MacroRecorderSection(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._engine = CaptureEngine()
        self._events: list[RecordedEvent] = []
        self._recording = False
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Controls
        ctrl = ctk.CTkFrame(self, height=50, corner_radius=0)
        ctrl.grid(row=0, column=0, sticky="ew")

        self._rec_btn = ctk.CTkButton(ctrl, text="⏺ Record", width=110,
                                       fg_color="#B71C1C", hover_color="#D32F2F",
                                       command=self._toggle_recording)
        self._rec_btn.pack(side="left", padx=8, pady=8)

        self._play_speed = ctk.CTkOptionMenu(ctrl, values=["0.5×", "1×", "2×"], width=70)
        self._play_speed.set("1×")
        self._play_speed.pack(side="left", padx=4, pady=8)

        self._play_btn = ctk.CTkButton(ctrl, text="▶ Play", width=80,
                                        command=self._playback)
        self._play_btn.pack(side="left", padx=4, pady=8)

        self._extract_btn = ctk.CTkButton(ctrl, text="Extract Step", width=110,
                                           command=self._extract_dialog)
        self._extract_btn.pack(side="left", padx=4, pady=8)

        self._filter_info = ctk.CTkLabel(ctrl, text="")
        self._filter_info.pack(side="left", padx=10)

        # Event log
        self._log = ctk.CTkScrollableFrame(self)
        self._log.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._log.grid_columnconfigure(0, weight=1)

    def _toggle_recording(self):
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self._recording = True
        self._rec_btn.configure(text="⏹ Stop", fg_color="#388E3C", hover_color="#4CAF50")
        for w in self._log.winfo_children():
            w.destroy()
        self._engine.start()

    def _stop_recording(self):
        self._recording = False
        raw = self._engine.stop()
        self._events, removed = auto_filter(raw)
        self._rec_btn.configure(text="⏺ Record", fg_color="#B71C1C", hover_color="#D32F2F")
        self._render_log()
        if removed:
            self._filter_info.configure(
                text=f"Auto-filtered {removed} events",
                text_color="gray")

    def _render_log(self, highlight: int = -1):
        for w in self._log.winfo_children():
            w.destroy()
        for i, ev in enumerate(self._events):
            color = "#4CAF50" if i < highlight else "#F44336" if i == highlight else None
            row = ctk.CTkFrame(self._log, fg_color="transparent")
            row.pack(fill="x", pady=1)
            lbl = ctk.CTkLabel(row, text=f"{i+1:3}. {ev.summary()}", anchor="w",
                                text_color=color)
            lbl.pack(side="left", padx=6)

    def _playback(self):
        if not self._events:
            return
        speed_map = {"0.5×": 0.5, "1×": 1.0, "2×": 2.0}
        speed = speed_map.get(self._play_speed.get(), 1.0)

        def run():
            bridge = None
            try:
                from python.engine.ahk_bridge import get_bridge
                bridge = get_bridge()
            except Exception:
                pass

            for i, ev in enumerate(self._events):
                self.after(0, self._render_log, i)
                if ev.kind == "delay":
                    time.sleep(ev.data.get("ms", 0) / 1000.0 / speed)
                elif bridge and bridge.connected:
                    from python.converters.py_to_ahk import convert
                    code = convert({"type": ev.kind, **ev.data})
                    if code:
                        bridge.execute_inline(code)
                        time.sleep(0.05 / speed)
            self.after(0, self._render_log)

        threading.Thread(target=run, daemon=True).start()

    def _extract_dialog(self):
        if not self._events:
            return
        ExtractDialog(self, self._events)


class ExtractDialog(ctk.CTkToplevel):
    def __init__(self, parent, events: list[RecordedEvent]):
        super().__init__(parent)
        self.title("Extract Step")
        self.geometry("440x320")
        self.grab_set()
        self._events = events
        self._build()

    def _build(self):
        f = ctk.CTkFrame(self)
        f.pack(fill="both", expand=True, padx=16, pady=12)

        def row(label, widget_factory, default=""):
            fr = ctk.CTkFrame(f, fg_color="transparent")
            fr.pack(fill="x", pady=4)
            ctk.CTkLabel(fr, text=label, width=120, anchor="w").pack(side="left")
            w = widget_factory(fr)
            w.pack(side="left", fill="x", expand=True)
            if hasattr(w, "insert") and default:
                w.insert(0, default)
            return w

        self._name = row("Step name", lambda p: ctk.CTkEntry(p))
        self._desc = row("Description", lambda p: ctk.CTkEntry(p))
        self._mode = row("Execution mode",
                          lambda p: ctk.CTkOptionMenu(p, values=["ahk", "python"]))

        ctk.CTkButton(self, text="Save to Library", command=self._save).pack(pady=10)

    def _save(self):
        name = self._name.get().strip()
        if not name:
            return
        step = build_step_json(name, self._desc.get(),
                               self._mode.get(), self._events)
        dest = path(f"library/steps/{name}.json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_json(f"library/steps/{name}.json", step)
        self.destroy()
