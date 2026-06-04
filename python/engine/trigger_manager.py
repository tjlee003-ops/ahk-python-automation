"""Trigger manager — all 9 trigger types, priority queue, retry logic."""

from __future__ import annotations

import datetime
import fnmatch
import re
import threading
import time
import uuid
from enum import Enum
from typing import Any, Callable

from python.file_manager import read_json, write_json

TRIGGERS_PATH = "data/triggers.json"


class TriggerType(str, Enum):
    HOTKEY       = "hotkey"
    SCHEDULE     = "schedule"
    WINDOW_EVENT = "window_event"
    FILE_EVENT   = "file_event"
    CLIPBOARD    = "clipboard"
    VAR_WATCH    = "variable_watch"
    MANUAL       = "manual"
    EMAIL        = "email_received"
    CHAINED      = "chained"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    NORMAL   = "normal"
    LOW      = "low"


PRIORITY_ORDER = {Priority.CRITICAL: 0, Priority.HIGH: 1,
                  Priority.NORMAL: 2, Priority.LOW: 3}


# ── Trigger record ────────────────────────────────────────────────────────────

class Trigger:
    def __init__(self, data: dict):
        self.id             = data.get("id", str(uuid.uuid4()))
        self.name           = data.get("name", "")
        self.type           = TriggerType(data.get("type", "manual"))
        self.enabled        = data.get("enabled", True)
        self.priority       = Priority(data.get("priority", "normal"))
        self.condition      = data.get("condition", {})
        self.preconditions  = data.get("preconditions", {})
        self.retry          = data.get("retry", {})
        self.injects        = data.get("injects", [])
        self.target_workflow = data.get("target_workflow", "")
        self.execution_mode = data.get("execution_mode", "ahk")
        self._retry_count   = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "type": self.type.value, "enabled": self.enabled,
            "priority": self.priority.value,
            "condition": self.condition,
            "preconditions": self.preconditions,
            "retry": self.retry,
            "injects": self.injects,
            "target_workflow": self.target_workflow,
            "execution_mode": self.execution_mode,
        }

    @staticmethod
    def from_dict(d: dict) -> "Trigger":
        return Trigger(d)


# ── Fire event ────────────────────────────────────────────────────────────────

class TriggerFireEvent:
    def __init__(self, trigger: Trigger, injected: dict[str, Any]):
        self.trigger  = trigger
        self.injected = injected
        self.fired_at = datetime.datetime.now().isoformat()


# ── Manager ───────────────────────────────────────────────────────────────────

class TriggerManager:
    def __init__(self):
        self._triggers: dict[str, Trigger] = {}
        self._queue: list[TriggerFireEvent] = []
        self._queue_lock = threading.Lock()
        self._on_fire: Callable[[TriggerFireEvent], None] | None = None
        self._running = False
        self._watchers: list[threading.Thread] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        data = read_json(TRIGGERS_PATH) or []
        for d in data:
            t = Trigger.from_dict(d)
            self._triggers[t.id] = t

    def save(self):
        write_json(TRIGGERS_PATH, [t.to_dict() for t in self._triggers.values()])

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add(self, trigger: Trigger) -> bool:
        if not self._validate(trigger):
            return False
        self._triggers[trigger.id] = trigger
        self.save()
        return True

    def update(self, trigger: Trigger) -> bool:
        if trigger.id not in self._triggers:
            return False
        if not self._validate(trigger):
            return False
        self._triggers[trigger.id] = trigger
        self.save()
        return True

    def delete(self, trigger_id: str):
        self._triggers.pop(trigger_id, None)
        self.save()

    def enable(self, trigger_id: str):
        if trigger_id in self._triggers:
            self._triggers[trigger_id].enabled = True
            self.save()

    def disable(self, trigger_id: str):
        if trigger_id in self._triggers:
            self._triggers[trigger_id].enabled = False
            self.save()

    def all(self) -> list[Trigger]:
        return list(self._triggers.values())

    # ── Validation / conflict detection ──────────────────────────────────────

    def _validate(self, trigger: Trigger) -> bool:
        for existing in self._triggers.values():
            if existing.id == trigger.id:
                continue
            if (existing.type == TriggerType.HOTKEY and
                    trigger.type == TriggerType.HOTKEY and
                    existing.condition.get("hotkey") == trigger.condition.get("hotkey")):
                return False  # duplicate hotkey
            if (existing.type == TriggerType.FILE_EVENT and
                    trigger.type == TriggerType.FILE_EVENT and
                    existing.condition.get("watch_path") == trigger.condition.get("watch_path")):
                pass  # warn but allow
        if trigger.type == TriggerType.CHAINED:
            if self._has_cycle(trigger.id, trigger.condition.get("source_trigger", "")):
                return False
        return True

    def _has_cycle(self, start_id: str, next_id: str, visited: set | None = None) -> bool:
        if visited is None:
            visited = set()
        if next_id in visited or next_id == start_id:
            return True
        visited.add(next_id)
        t = self._triggers.get(next_id)
        if t and t.type == TriggerType.CHAINED:
            return self._has_cycle(start_id, t.condition.get("source_trigger", ""), visited)
        return False

    # ── Runtime ───────────────────────────────────────────────────────────────

    def start(self, on_fire: Callable[[TriggerFireEvent], None]):
        self._on_fire = on_fire
        self._running = True
        threading.Thread(target=self._queue_processor, daemon=True).start()
        self._start_watchers()

    def stop(self):
        self._running = False

    def fire(self, trigger_id: str, injected: dict[str, Any] | None = None):
        t = self._triggers.get(trigger_id)
        if not t or not t.enabled:
            return
        if not self._check_preconditions(t):
            self._schedule_retry(t, injected or {})
            return
        event = TriggerFireEvent(t, injected or {})
        with self._queue_lock:
            self._queue.append(event)
            self._queue.sort(key=lambda e: PRIORITY_ORDER[e.trigger.priority])

    def _queue_processor(self):
        while self._running:
            with self._queue_lock:
                event = self._queue.pop(0) if self._queue else None
            if event and self._on_fire:
                self._on_fire(event)
            time.sleep(0.05)

    def _check_preconditions(self, t: Trigger) -> bool:
        pre = t.preconditions
        if not pre:
            return True
        now = datetime.datetime.now().time()
        tw = pre.get("time_window")
        if tw:
            start = datetime.time.fromisoformat(tw.get("start", "00:00"))
            end   = datetime.time.fromisoformat(tw.get("end",   "23:59"))
            if not (start <= now <= end):
                return False
        ensure = pre.get("ensure_window")
        if ensure:
            try:
                import win32gui
                titles = []
                win32gui.EnumWindows(
                    lambda hwnd, _: titles.append(win32gui.GetWindowText(hwnd)), None)
                if not any(ensure.lower() in t.lower() for t in titles):
                    return False
            except Exception:
                pass
        return True

    def _schedule_retry(self, t: Trigger, injected: dict[str, Any]):
        retry = t.retry
        if not retry:
            return
        max_attempts = retry.get("max_attempts", 3)
        if t._retry_count >= max_attempts:
            t._retry_count = 0
            exhaustion = retry.get("on_exhaustion")
            if exhaustion == "alert_workflow" and self._on_fire:
                pass  # could fire an alert workflow here
            return
        t._retry_count += 1
        interval = retry.get("interval_seconds", 30)
        threading.Timer(interval, self.fire, args=(t.id, injected)).start()

    # ── Watchers ──────────────────────────────────────────────────────────────

    def _start_watchers(self):
        for t in self._triggers.values():
            if not t.enabled:
                continue
            if t.type == TriggerType.FILE_EVENT:
                self._start_file_watcher(t)
            elif t.type == TriggerType.SCHEDULE:
                self._start_schedule_watcher(t)
            elif t.type == TriggerType.CLIPBOARD:
                self._start_clipboard_watcher(t)
            elif t.type == TriggerType.VAR_WATCH:
                self._start_var_watcher(t)

    def _start_file_watcher(self, trigger: Trigger):
        watch_path = trigger.condition.get("watch_path", "")
        event_type = trigger.condition.get("event", "created")
        filt = trigger.condition.get("filter", "*")

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def __init__(self, mgr, trig):
                    self._mgr = mgr
                    self._trig = trig

                def on_created(self, ev):
                    if event_type == "created" and fnmatch.fnmatch(ev.src_path, filt):
                        import os
                        self._mgr.fire(self._trig.id, {
                            "fileName": os.path.basename(ev.src_path),
                            "filePath": ev.src_path,
                            "triggerTime": datetime.datetime.now().isoformat(),
                        })

                def on_modified(self, ev):
                    if event_type == "modified" and fnmatch.fnmatch(ev.src_path, filt):
                        self._mgr.fire(self._trig.id, {"filePath": ev.src_path})

                def on_deleted(self, ev):
                    if event_type == "deleted" and fnmatch.fnmatch(ev.src_path, filt):
                        self._mgr.fire(self._trig.id, {"filePath": ev.src_path})

            obs = Observer()
            obs.schedule(_Handler(self, trigger), watch_path, recursive=False)
            obs.start()
        except Exception:
            pass

    def _start_schedule_watcher(self, trigger: Trigger):
        def run():
            while self._running:
                cond = trigger.condition
                mode = cond.get("mode", "once")
                scheduled_time = cond.get("time", "")

                now = datetime.datetime.now()
                if mode == "once":
                    target = datetime.datetime.fromisoformat(scheduled_time) if scheduled_time else now
                    wait = (target - now).total_seconds()
                    if wait > 0:
                        time.sleep(wait)
                    self.fire(trigger.id)
                    return
                elif mode in ("daily", "weekdays", "weekly"):
                    t_str = cond.get("time", "09:00")
                    h, m = map(int, t_str.split(":"))
                    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if target <= now:
                        target += datetime.timedelta(days=1)
                    wait = (target - now).total_seconds()
                    time.sleep(wait)
                    day_ok = True
                    if mode == "weekdays" and datetime.datetime.now().weekday() >= 5:
                        day_ok = False
                    if day_ok:
                        self.fire(trigger.id)
                elif mode == "interval":
                    seconds = cond.get("interval_seconds", 3600)
                    time.sleep(seconds)
                    self.fire(trigger.id)
                else:
                    time.sleep(60)

        threading.Thread(target=run, daemon=True).start()

    def _start_clipboard_watcher(self, trigger: Trigger):
        def run():
            last = ""
            while self._running:
                try:
                    import pyperclip
                    current = pyperclip.paste()
                    pattern = trigger.condition.get("pattern", "")
                    if current != last:
                        last = current
                        if not pattern or re.search(pattern, current):
                            self.fire(trigger.id, {"clipboardContent": current})
                except Exception:
                    pass
                time.sleep(1)

        threading.Thread(target=run, daemon=True).start()

    def _start_var_watcher(self, trigger: Trigger):
        def run():
            from python.engine.variable_manager import get_manager
            mgr = get_manager()
            var_name = trigger.condition.get("variable", "")
            watch_value = trigger.condition.get("value")
            last = None
            while self._running:
                current = mgr.get(var_name)
                if current != last and (watch_value is None or str(current) == str(watch_value)):
                    last = current
                    self.fire(trigger.id, {var_name: current})
                time.sleep(0.5)

        threading.Thread(target=run, daemon=True).start()


# Module-level singleton
_manager: TriggerManager | None = None


def get_manager() -> TriggerManager:
    global _manager
    if _manager is None:
        _manager = TriggerManager()
    return _manager
