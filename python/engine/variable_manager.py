"""Variable manager — types, scopes, expressions, system vars, persistence."""

from __future__ import annotations

import datetime
import re
import uuid
from enum import Enum
from typing import Any

from python.file_manager import read_json, write_json

VARIABLES_PATH = "data/variables.json"

# ── Types & Scopes ────────────────────────────────────────────────────────────

class VarType(str, Enum):
    STRING   = "string"
    NUMBER   = "number"
    BOOLEAN  = "boolean"
    LIST     = "list"
    DATETIME = "datetime"
    WINDOW   = "window"


class VarScope(str, Enum):
    GLOBAL   = "global"    # persisted to variables.json
    WORKFLOW = "workflow"  # lives for one run
    STEP     = "step"      # in-memory, single step


# ── System variables (read-only, refreshed each step) ────────────────────────

def _system_vars() -> dict[str, Any]:
    try:
        import win32gui
        active_window = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    except Exception:
        active_window = ""

    try:
        import win32api
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
    except Exception:
        screen_w = screen_h = 0

    try:
        import os
        user_name = os.environ.get("USERNAME", "")
    except Exception:
        user_name = ""

    try:
        import pyperclip
        clipboard = pyperclip.paste()
    except Exception:
        clipboard = ""

    now = datetime.datetime.now()
    return {
        "today":            now.strftime("%Y-%m-%d"),
        "now":              now.isoformat(),
        "activeWindow":     active_window,
        "clipboardContent": clipboard,
        "userName":         user_name,
        "screenWidth":      screen_w,
        "screenHeight":     screen_h,
    }


# ── Variable record ───────────────────────────────────────────────────────────

class Variable:
    def __init__(self, name: str, value: Any, var_type: VarType = VarType.STRING,
                 scope: VarScope = VarScope.GLOBAL, description: str = ""):
        self.id = str(uuid.uuid4())
        self.name = name
        self.value = value
        self.type = var_type
        self.scope = scope
        self.description = description

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
            "scope": self.scope.value,
            "description": self.description,
        }

    @staticmethod
    def from_dict(d: dict) -> "Variable":
        v = Variable(
            name=d["name"],
            value=d.get("value"),
            var_type=VarType(d.get("type", "string")),
            scope=VarScope(d.get("scope", "global")),
            description=d.get("description", ""),
        )
        v.id = d.get("id", v.id)
        return v


# ── Manager ───────────────────────────────────────────────────────────────────

class VariableManager:
    def __init__(self):
        self._global: dict[str, Variable] = {}    # name → Variable
        self._workflow: dict[str, Variable] = {}
        self._step: dict[str, Variable] = {}
        self._workflow_name = ""
        self._loop_index = 0
        self._load_globals()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_globals(self):
        data = read_json(VARIABLES_PATH) or []
        for d in data:
            v = Variable.from_dict(d)
            self._global[v.name] = v

    def save_globals(self):
        write_json(VARIABLES_PATH, [v.to_dict() for v in self._global.values()])

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def set(self, name: str, value: Any, scope: VarScope = VarScope.GLOBAL,
            var_type: VarType = VarType.STRING):
        v = Variable(name, value, var_type, scope)
        if scope == VarScope.GLOBAL:
            self._global[name] = v
            self.save_globals()
        elif scope == VarScope.WORKFLOW:
            self._workflow[name] = v
        else:
            self._step[name] = v

    def get(self, name: str) -> Any:
        # Resolution order: step → workflow → global → system
        for store in (self._step, self._workflow, self._global):
            if name in store:
                return store[name].value
        sys_vars = _system_vars()
        return sys_vars.get(name)

    def delete(self, name: str, scope: VarScope = VarScope.GLOBAL):
        store = {
            VarScope.GLOBAL:   self._global,
            VarScope.WORKFLOW: self._workflow,
            VarScope.STEP:     self._step,
        }[scope]
        store.pop(name, None)
        if scope == VarScope.GLOBAL:
            self.save_globals()

    def promote(self, name: str, to_scope: VarScope):
        """Promote a variable to a higher scope (step→workflow→global)."""
        order = [VarScope.STEP, VarScope.WORKFLOW, VarScope.GLOBAL]
        for store, scope in ((self._step, VarScope.STEP),
                              (self._workflow, VarScope.WORKFLOW),
                              (self._global, VarScope.GLOBAL)):
            if name in store:
                if order.index(to_scope) > order.index(scope):
                    v = store[name]
                    v.scope = to_scope
                    self.set(name, v.value, to_scope, v.type)
                return

    def all_variables(self) -> list[Variable]:
        seen = set()
        result = []
        for store in (self._step, self._workflow, self._global):
            for name, var in store.items():
                if name not in seen:
                    seen.add(name)
                    result.append(var)
        return result

    # ── Scope lifecycle ───────────────────────────────────────────────────────

    def begin_workflow(self, workflow_name: str):
        self._workflow_name = workflow_name
        self._workflow.clear()
        self._loop_index = 0

    def end_workflow(self):
        self._workflow.clear()
        self._step.clear()
        self._workflow_name = ""

    def begin_step(self):
        self._step.clear()

    def set_loop_index(self, i: int):
        self._loop_index = i

    # ── Resolution ────────────────────────────────────────────────────────────

    def resolve(self, text: str, extra: dict[str, Any] | None = None) -> str:
        """Replace {{varName}} placeholders and evaluate inline expressions."""
        if not isinstance(text, str):
            return text

        # Inject ephemeral extras (e.g. loop vars)
        extras = extra or {}
        extras.update({"loopIndex": self._loop_index,
                       "workflowName": self._workflow_name})

        def replacer(m: re.Match) -> str:
            expr = m.group(1).strip()
            # Simple name lookup first
            if re.fullmatch(r"[A-Za-z_]\w*", expr):
                val = extras.get(expr, self.get(expr))
                return "" if val is None else str(val)
            # Evaluate expression (math + string ops)
            return self._eval_expr(expr, extras)

        return re.sub(r"\{\{(.+?)\}\}", replacer, text)

    def _eval_expr(self, expr: str, extras: dict[str, Any]) -> str:
        env: dict[str, Any] = {}
        for name, var in {**{n: v.value for n, v in self._global.items()},
                           **{n: v.value for n, v in self._workflow.items()},
                           **{n: v.value for n, v in self._step.items()}}.items():
            env[name] = var
        env.update(_system_vars())
        env.update(extras)
        # Expose simple string methods
        env["toUpperCase"] = str.upper
        env["toLowerCase"] = str.lower
        try:
            result = eval(expr, {"__builtins__": {}}, env)  # noqa: S307
            return str(result)
        except Exception:
            return f"{{{{{expr}}}}}"  # return unresolved on error


# Module-level singleton
_manager: VariableManager | None = None


def get_manager() -> VariableManager:
    global _manager
    if _manager is None:
        _manager = VariableManager()
    return _manager
