"""Convert Python step definitions to equivalent AHK script strings."""

from __future__ import annotations
from typing import Any


STEP_CONVERTERS: dict[str, callable] = {}


def register(step_type: str):
    def decorator(fn):
        STEP_CONVERTERS[step_type] = fn
        return fn
    return decorator


def convert(step: dict[str, Any]) -> str | None:
    """Return AHK script string for step, or None if no converter exists."""
    fn = STEP_CONVERTERS.get(step.get("type"))
    return fn(step) if fn else None


# ── Built-in converters ──────────────────────────────────────────────────────

@register("click")
def _click(step):
    x = step.get("x", 0)
    y = step.get("y", 0)
    button = step.get("button", "Left")
    return f'Click, {x}, {y}, {button}'


@register("type_text")
def _type_text(step):
    text = step.get("text", "").replace("`", "``").replace("{", "{{").replace("}", "}}")
    return f'SendInput, {text}'


@register("wait")
def _wait(step):
    ms = int(step.get("ms", 1000))
    return f'Sleep, {ms}'


@register("window_focus")
def _window_focus(step):
    title = step.get("window_title", "")
    return f'WinActivate, {title}'


@register("open_file")
def _open_file(step):
    path = step.get("path", "")
    return f'Run, {path}'


@register("clipboard")
def _clipboard(step):
    action = step.get("action", "copy")
    if action == "copy":
        return "Send, ^c"
    elif action == "paste":
        return "Send, ^v"
    elif action == "set":
        text = step.get("value", "")
        return f'Clipboard := "{text}"\nClipWait, 1'
    return ""


@register("notify")
def _notify(step):
    title = step.get("title", "Notification")
    msg = step.get("message", "")
    return f'TrayTip, {title}, {msg}, 3'


@register("log")
def _log(step):
    msg = step.get("message", "")
    return f'FileAppend, %A_Now% {msg}`n, %A_ScriptDir%\\..\\logs\\workflows\\ahk.log'
