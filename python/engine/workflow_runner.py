"""Execution engine — variable resolution, AHK bridge, branch evaluator, loop engine."""

from __future__ import annotations

import datetime
import logging
import threading
import time
from typing import Any, TYPE_CHECKING

from python.engine.variable_manager import get_manager as get_var_manager
from python.file_manager import read_json, write_json

if TYPE_CHECKING:
    from python.gui.workflow_section import Workflow, WorkflowCanvas

logger = logging.getLogger(__name__)

ERROR_HANDLERS = ("stop", "skip", "retry", "run_error_workflow", "notify_user")

BRANCH_OPS = {
    "equals":                  lambda a, b: str(a) == str(b),
    "not equals":              lambda a, b: str(a) != str(b),
    "greater than":            lambda a, b: float(a) > float(b),
    "less than":               lambda a, b: float(a) < float(b),
    "between":                 lambda a, b: float(b.split(",")[0]) <= float(a) <= float(b.split(",")[1]),
    "contains":                lambda a, b: str(b) in str(a),
    "starts with":             lambda a, b: str(a).startswith(str(b)),
    "ends with":               lambda a, b: str(a).endswith(str(b)),
    "is empty":                lambda a, b: str(a).strip() == "",
    "is not empty":            lambda a, b: str(a).strip() != "",
    "variable equals variable": lambda a, b: str(a) == str(b),
}


class StepResult:
    def __init__(self, success: bool, outputs: dict[str, Any] | None = None,
                 error: str = ""):
        self.success = success
        self.outputs = outputs or {}
        self.error   = error


class WorkflowRunner:
    def __init__(self):
        self._running: dict[str, threading.Thread] = {}  # workflow_id → thread
        self._stop_flags: dict[str, bool] = {}
        self._canvas_ref = None
        self._log_callback = None

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, workflow, canvas=None, companion=None):
        wid = workflow.id
        if wid in self._running and self._running[wid].is_alive():
            return
        self._stop_flags[wid] = False
        t = threading.Thread(
            target=self._run_workflow,
            args=(workflow, canvas, companion),
            daemon=True,
        )
        self._running[wid] = t
        t.start()

    def stop(self, workflow_id: str):
        self._stop_flags[workflow_id] = True

    def stop_all(self):
        for wid in list(self._stop_flags):
            self._stop_flags[wid] = True
        from python.engine.ahk_bridge import get_bridge
        get_bridge().stop()

    def set_log_callback(self, fn):
        self._log_callback = fn

    # ── Workflow lifecycle ────────────────────────────────────────────────────

    def _run_workflow(self, workflow, canvas, companion):
        var_mgr = get_var_manager()
        var_mgr.begin_workflow(workflow.name)

        self._log(f"Workflow '{workflow.name}' started.", "info")
        self._write_log(workflow.name, "started")

        # Find starting node (first node with no incoming edges)
        incoming = set()
        for n in workflow.nodes.values():
            for ref in (n.next, n.yes, n.no, n.body):
                if ref:
                    incoming.add(ref)
        start_nodes = [n for n in workflow.nodes.values() if n.id not in incoming]
        current_id = start_nodes[0].id if start_nodes else (
            list(workflow.nodes.keys())[0] if workflow.nodes else None)

        loop_stack: list[dict] = []  # for nested loops

        while current_id:
            if self._stop_flags.get(workflow.id):
                self._log("Workflow stopped.", "warning")
                break

            node = workflow.nodes.get(current_id)
            if not node:
                break

            self._set_canvas_state(canvas, current_id, "running")
            result = self._execute_node(node, workflow, var_mgr, canvas, companion)

            if result.success:
                self._set_canvas_state(canvas, current_id, "success")
                for k, v in result.outputs.items():
                    var_mgr.set(k, v)
                current_id = self._next_node(node, result, var_mgr, loop_stack)
            else:
                self._set_canvas_state(canvas, current_id, "error")
                handler = node.error_handler
                if handler == "stop":
                    self._log(f"Step failed: {result.error}. Stopping.", "error")
                    break
                elif handler == "skip":
                    self._log(f"Step failed: {result.error}. Skipping.", "warning")
                    self._set_canvas_state(canvas, current_id, "skipped")
                    current_id = node.next or None
                elif handler == "retry":
                    retries = node.config.get("retry_count", 3)
                    node.config["_retried"] = node.config.get("_retried", 0) + 1
                    if node.config["_retried"] <= retries:
                        self._log(f"Retrying step ({node.config['_retried']}/{retries})…", "warning")
                        time.sleep(1)
                        # don't advance current_id — retry same node
                    else:
                        node.config["_retried"] = 0
                        self._log(f"Retry limit reached: {result.error}", "error")
                        break
                elif handler == "notify_user":
                    self._log(f"Step error: {result.error}", "error")
                    current_id = node.next or None
                else:
                    break

        var_mgr.end_workflow()
        self._log(f"Workflow '{workflow.name}' complete.", "success")
        self._write_log(workflow.name, "complete")
        self._running.pop(workflow.id, None)

    # ── Node execution ────────────────────────────────────────────────────────

    def _execute_node(self, node, workflow, var_mgr, canvas, companion) -> StepResult:
        if node.type == "branch":
            return self._eval_branch(node, var_mgr)
        if node.type == "loop":
            return StepResult(True)  # loop logic handled in _next_node
        if node.type == "stop":
            self._stop_flags[workflow.id] = True
            return StepResult(True)

        # Resolve all config values
        resolved_config: dict[str, Any] = {}
        for k, v in node.config.items():
            resolved_config[k] = var_mgr.resolve(v) if isinstance(v, str) else v

        mode = node.exec_mode or workflow.mode
        if mode == "ahk":
            return self._execute_ahk(node, resolved_config)
        else:
            return self._execute_python(node, resolved_config, var_mgr, companion)

    def _execute_ahk(self, node, config: dict) -> StepResult:
        from python.engine.ahk_bridge import get_bridge
        from python.converters.py_to_ahk import convert
        bridge = get_bridge()

        step_def = {"type": node.type, **config}
        code = convert(step_def)
        if not code:
            return StepResult(False, error=f"No AHK converter for step type '{node.type}'")

        if bridge.connected:
            ok = bridge.execute_inline(code)
            return StepResult(ok, error="" if ok else "AHK bridge send failed")
        # Fallback: write temp file
        import tempfile, subprocess, sys
        tmp = tempfile.NamedTemporaryFile(suffix=".ahk", delete=False, mode="w", encoding="utf-8")
        tmp.write(code)
        tmp.close()
        try:
            subprocess.run(["AutoHotkey.exe", tmp.name], timeout=30)
            return StepResult(True)
        except Exception as e:
            return StepResult(False, error=str(e))

    def _execute_python(self, node, config: dict, var_mgr, companion) -> StepResult:
        t = node.type
        try:
            if t == "wait":
                time.sleep(config.get("ms", 1000) / 1000.0)
            elif t == "log":
                self._log(var_mgr.resolve(config.get("message", "")), "info")
            elif t == "notify":
                self._log(f"[NOTIFY] {config.get('message', '')}", "info")
            elif t == "clipboard":
                import pyperclip
                action = config.get("action", "copy")
                if action == "set":
                    pyperclip.copy(config.get("value", ""))
                elif action == "get":
                    val = pyperclip.paste()
                    return StepResult(True, {"clipboardContent": val})
            elif t == "run_step":
                return self._run_library_step(config.get("step_id", ""), var_mgr)
            elif t == "run_workflow":
                sub = self._load_workflow(config.get("workflow_id", ""))
                if sub:
                    self.run(sub)
                    return StepResult(True)
                return StepResult(False, error="Sub-workflow not found")
            elif t == "send_email":
                from python.engine.email_sender import send_email
                send_email(config, {})
            return StepResult(True)
        except Exception as e:
            return StepResult(False, error=str(e))

    # ── Branch evaluator ──────────────────────────────────────────────────────

    def _eval_branch(self, node, var_mgr) -> StepResult:
        condition = node.config.get("condition", "")
        resolved  = var_mgr.resolve(condition)
        # Simple truthiness check if already resolved to true/false
        if resolved.lower() in ("true", "1", "yes"):
            node.config["_branch_taken"] = "yes"
        elif resolved.lower() in ("false", "0", "no"):
            node.config["_branch_taken"] = "no"
        else:
            # Try operator-based evaluation: "left OP right"
            taken = self._eval_condition_str(condition, var_mgr)
            node.config["_branch_taken"] = "yes" if taken else "no"
        return StepResult(True)

    def _eval_condition_str(self, condition: str, var_mgr) -> bool:
        for op in sorted(BRANCH_OPS.keys(), key=len, reverse=True):
            if op in condition:
                parts = condition.split(op, 1)
                left  = var_mgr.resolve(parts[0].strip())
                right = var_mgr.resolve(parts[1].strip())
                try:
                    return BRANCH_OPS[op](left, right)
                except Exception:
                    return False
        # Fallback: eval as Python expression
        try:
            env: dict = {}
            for v in var_mgr.all_variables():
                env[v.name] = v.value
            return bool(eval(condition, {"__builtins__": {}}, env))  # noqa: S307
        except Exception:
            return False

    # ── Loop engine ───────────────────────────────────────────────────────────

    def _next_node(self, node, result: StepResult, var_mgr, loop_stack: list) -> str | None:
        if node.type == "branch":
            taken = node.config.get("_branch_taken", "yes")
            return node.yes if taken == "yes" else node.no

        if node.type == "loop":
            mode  = node.config.get("mode", "repeat")
            count = node.config.get("count", 1)
            idx   = node.config.get("_loop_index", 0)

            if mode == "repeat":
                total = int(var_mgr.resolve(str(count))) if isinstance(count, str) else int(count)
                if idx < total:
                    node.config["_loop_index"] = idx + 1
                    var_mgr.set_loop_index(idx + 1)
                    return node.body
                else:
                    node.config["_loop_index"] = 0
                    var_mgr.set_loop_index(0)
                    return node.next or None

            elif mode == "until_condition":
                cond = node.config.get("condition", "false")
                if not self._eval_condition_str(cond, var_mgr):
                    node.config["_loop_index"] = idx + 1
                    var_mgr.set_loop_index(idx + 1)
                    return node.body
                else:
                    node.config["_loop_index"] = 0
                    return node.next or None

            elif mode == "forever":
                node.config["_loop_index"] = idx + 1
                var_mgr.set_loop_index(idx + 1)
                return node.body

            elif mode == "list_iteration":
                items_var = node.config.get("list_var", "")
                items = var_mgr.get(items_var)
                if isinstance(items, list) and idx < len(items):
                    var_mgr.set("loopItem", items[idx])
                    node.config["_loop_index"] = idx + 1
                    var_mgr.set_loop_index(idx + 1)
                    return node.body
                else:
                    node.config["_loop_index"] = 0
                    return node.next or None

        return node.next or None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run_library_step(self, step_id: str, var_mgr) -> StepResult:
        import os
        lib = __import__("python.file_manager", fromlist=["path"]).path
        for f in lib("library/steps").glob("*.json"):
            data = read_json(str(f.relative_to(lib(""))))
            if data and data.get("id") == step_id:
                from python.engine.ahk_bridge import get_bridge
                bridge = get_bridge()
                code = data.get("execution", {}).get("ahk", "")
                if code and bridge.connected:
                    bridge.execute_inline(code)
                return StepResult(True)
        return StepResult(False, error=f"Step {step_id} not found in library")

    def _load_workflow(self, workflow_id: str):
        from python.gui.workflow_section import Workflow
        lib = __import__("python.file_manager", fromlist=["path"]).path
        for wf_dir in lib("library/workflows").iterdir():
            data = read_json(f"library/workflows/{wf_dir.name}/workflow.json")
            if data and data.get("id") == workflow_id:
                return Workflow.from_dict(data)
        return None

    def _set_canvas_state(self, canvas, node_id: str, state: str):
        if canvas:
            canvas.after(0, canvas.set_node_state, node_id, state)

    def _log(self, msg: str, level: str = "info"):
        if self._log_callback:
            self._log_callback(msg, level)
        logger.info(msg)

    def _write_log(self, workflow_name: str, status: str):
        import os
        log_path = f"logs/workflows/{workflow_name}_{datetime.datetime.now():%Y%m%d}.jsonl"
        entry = {"time": datetime.datetime.now().isoformat(),
                 "workflow": workflow_name, "status": status}
        from python.file_manager import path
        p = path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            import json
            f.write(json.dumps(entry) + "\n")


# Module-level singleton
_runner: WorkflowRunner | None = None


def get_runner() -> WorkflowRunner:
    global _runner
    if _runner is None:
        _runner = WorkflowRunner()
    return _runner
