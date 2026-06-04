"""FastAPI server — localhost:8080, all REST endpoints + WebSocket live stream."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="AHK-Python Automation API", version="1.0")

# ── WebSocket manager ─────────────────────────────────────────────────────────

class WSManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.remove(ws)

    async def broadcast(self, event: dict):
        dead = []
        for ws in self._clients:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.remove(ws)


_ws_manager = WSManager()


def emit_event(event_type: str, data: dict):
    """Call from sync code (engine) to broadcast a WebSocket event."""
    import asyncio
    event = {"type": event_type, "data": data, "time": _now()}
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_ws_manager.broadcast(event))
    except Exception:
        pass


def _now() -> str:
    import datetime
    return datetime.datetime.now().isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read(rel: str):
    from python.file_manager import read_json
    return read_json(rel) or []


def _write(rel: str, data):
    from python.file_manager import write_json
    write_json(rel, data)


def _find_by_id(items: list[dict], item_id: str) -> dict | None:
    return next((i for i in items if i.get("id") == item_id), None)


# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/status")
def get_status():
    from python.engine.variable_manager import get_manager
    from python.engine.trigger_manager  import get_manager as get_trig
    vars_count     = len(get_manager().all_variables())
    triggers_count = len(get_trig().all())
    return {"status": "running", "vars": vars_count, "triggers": triggers_count}


# ── Workflows ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/workflows")
def list_workflows():
    from python.file_manager import path
    lib = path("library/workflows")
    result = []
    if lib.exists():
        for d in lib.iterdir():
            wf_file = d / "workflow.json"
            from python.file_manager import read_json
            data = read_json(f"library/workflows/{d.name}/workflow.json")
            if data:
                result.append({"id": data.get("id"), "name": data.get("name"),
                                "version": data.get("current_version")})
    return result


@app.post("/api/v1/workflows/{workflow_id}/run")
def run_workflow(workflow_id: str):
    from python.gui.workflow_section import Workflow
    from python.file_manager import path
    for d in path("library/workflows").iterdir():
        from python.file_manager import read_json
        data = read_json(f"library/workflows/{d.name}/workflow.json")
        if data and data.get("id") == workflow_id:
            wf = Workflow.from_dict(data)
            from python.engine.workflow_runner import get_runner
            get_runner().run(wf)
            return {"status": "started"}
    raise HTTPException(status_code=404, detail="Workflow not found")


@app.post("/api/v1/workflows/{workflow_id}/stop")
def stop_workflow(workflow_id: str):
    from python.engine.workflow_runner import get_runner
    get_runner().stop(workflow_id)
    return {"status": "stopped"}


@app.get("/api/v1/workflows/{workflow_id}/status")
def workflow_status(workflow_id: str):
    from python.engine.workflow_runner import get_runner
    runner = get_runner()
    running = workflow_id in runner._running and runner._running[workflow_id].is_alive()
    return {"workflow_id": workflow_id, "running": running}


@app.get("/api/v1/workflows/{workflow_id}/versions")
def workflow_versions(workflow_id: str):
    from python.file_manager import path, read_json
    for d in path("library/workflows").iterdir():
        data = read_json(f"library/workflows/{d.name}/workflow.json")
        if data and data.get("id") == workflow_id:
            versions_dir = d / "versions"
            if versions_dir.exists():
                return [f.name for f in versions_dir.glob("*.json")]
    raise HTTPException(status_code=404, detail="Workflow not found")


# ── Variables ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/variables")
def list_variables():
    from python.engine.variable_manager import get_manager
    return [v.to_dict() for v in get_manager().all_variables()]


@app.post("/api/v1/variables")
def create_variable(body: dict):
    from python.engine.variable_manager import get_manager, VarScope, VarType
    mgr = get_manager()
    mgr.set(body["name"], body.get("value"), VarScope(body.get("scope", "global")),
            VarType(body.get("type", "string")))
    return {"status": "created"}


@app.put("/api/v1/variables/{name}")
def update_variable(name: str, body: dict):
    from python.engine.variable_manager import get_manager, VarScope, VarType
    mgr = get_manager()
    mgr.set(name, body.get("value"), VarScope(body.get("scope", "global")))
    return {"status": "updated"}


@app.delete("/api/v1/variables/{name}")
def delete_variable(name: str):
    from python.engine.variable_manager import get_manager, VarScope
    get_manager().delete(name, VarScope.GLOBAL)
    return {"status": "deleted"}


# ── Triggers ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/triggers")
def list_triggers():
    from python.engine.trigger_manager import get_manager
    return [t.to_dict() for t in get_manager().all()]


@app.post("/api/v1/triggers")
def create_trigger(body: dict):
    from python.engine.trigger_manager import get_manager, Trigger
    t = Trigger(body)
    ok = get_manager().add(t)
    if not ok:
        raise HTTPException(status_code=409, detail="Conflict detected")
    return {"status": "created", "id": t.id}


@app.put("/api/v1/triggers/{trigger_id}")
def update_trigger(trigger_id: str, body: dict):
    from python.engine.trigger_manager import get_manager, Trigger
    body["id"] = trigger_id
    t = Trigger(body)
    ok = get_manager().update(t)
    if not ok:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"status": "updated"}


@app.delete("/api/v1/triggers/{trigger_id}")
def delete_trigger(trigger_id: str):
    from python.engine.trigger_manager import get_manager
    get_manager().delete(trigger_id)
    return {"status": "deleted"}


@app.post("/api/v1/triggers/{trigger_id}/enable")
def enable_trigger(trigger_id: str):
    from python.engine.trigger_manager import get_manager
    get_manager().enable(trigger_id)
    return {"status": "enabled"}


@app.post("/api/v1/triggers/{trigger_id}/disable")
def disable_trigger(trigger_id: str):
    from python.engine.trigger_manager import get_manager
    get_manager().disable(trigger_id)
    return {"status": "disabled"}


# ── Steps ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/steps")
def list_steps():
    from python.file_manager import path, read_json
    steps = []
    d = path("library/steps")
    if d.exists():
        for f in d.glob("*.json"):
            data = read_json(str(f.relative_to(path(""))))
            if data:
                steps.append(data)
    return steps


@app.post("/api/v1/steps")
def create_step(body: dict):
    from python.file_manager import write_json
    name = body.get("name", "step")
    write_json(f"library/steps/{name}.json", body)
    return {"status": "created"}


@app.put("/api/v1/steps/{step_id}")
def update_step(step_id: str, body: dict):
    from python.file_manager import path, read_json, write_json
    for f in path("library/steps").glob("*.json"):
        data = read_json(str(f.relative_to(path(""))))
        if data and data.get("id") == step_id:
            data.update(body)
            write_json(str(f.relative_to(path(""))), data)
            return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Step not found")


@app.delete("/api/v1/steps/{step_id}")
def delete_step(step_id: str):
    from python.file_manager import path, read_json
    for f in path("library/steps").glob("*.json"):
        data = read_json(str(f.relative_to(path(""))))
        if data and data.get("id") == step_id:
            f.unlink()
            return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Step not found")


# ── Email templates ───────────────────────────────────────────────────────────

@app.get("/api/v1/email/templates")
def list_email_templates():
    from python.gui.email_section import EmailTemplate
    return [t.to_dict() for t in EmailTemplate.load_all()]


@app.post("/api/v1/email/templates")
def create_email_template(body: dict):
    from python.gui.email_section import EmailTemplate
    t = EmailTemplate.from_dict(body)
    t.save()
    return {"status": "created", "id": t.id}


@app.put("/api/v1/email/templates/{template_id}")
def update_email_template(template_id: str, body: dict):
    from python.gui.email_section import EmailTemplate
    for t in EmailTemplate.load_all():
        if t.id == template_id:
            updated = EmailTemplate.from_dict({**t.to_dict(), **body})
            updated.save()
            return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Template not found")


@app.post("/api/v1/email/send")
def send_email(body: dict):
    from python.engine.email_sender import send_email as _send
    ok = _send(body.get("template", {}), body.get("variables", {}))
    return {"status": "sent" if ok else "queued"}


# ── Export / Import ───────────────────────────────────────────────────────────

@app.get("/api/v1/export")
def export_data():
    import tempfile, os
    from python.engine.bundle_manager import export_full
    tmp = tempfile.mktemp(suffix=".bundle")
    export_full(tmp)
    with open(tmp, "rb") as f:
        data = f.read()
    os.unlink(tmp)
    from fastapi.responses import Response
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": "attachment; filename=export.bundle"})


@app.post("/api/v1/import")
async def import_data(body: dict):
    from python.engine.bundle_manager import import_bundle
    bundle_path = body.get("bundle_path", "")
    result = import_bundle(bundle_path, {})
    return result


# ── Logs ──────────────────────────────────────────────────────────────────────

@app.get("/api/v1/logs/workflows")
def logs_workflows():
    return _tail_logs("logs/workflows")


@app.get("/api/v1/logs/triggers")
def logs_triggers():
    return _tail_logs("logs/triggers")


@app.get("/api/v1/logs/email")
def logs_email():
    return _tail_logs("logs/email")


def _tail_logs(dir_path: str) -> list[dict]:
    from python.file_manager import path
    result = []
    d = path(dir_path)
    if not d.exists():
        return result
    for f in sorted(d.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        with f.open("r", encoding="utf-8") as fh:
            for line in fh.readlines()[-50:]:
                try:
                    result.append(json.loads(line))
                except Exception:
                    pass
    return result


# ── Backup ────────────────────────────────────────────────────────────────────

@app.post("/api/v1/backup")
def trigger_backup():
    from python.engine.backup_manager import create_backup
    p = create_backup("api")
    return {"status": "created", "path": str(p)}


# ── Guide (API schema) ────────────────────────────────────────────────────────

@app.get("/api/v1/guide")
def api_guide():
    routes = []
    for route in app.routes:
        if hasattr(route, "methods"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name,
            })
    return routes


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/status")
async def ws_status(ws: WebSocket):
    await _ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        _ws_manager.disconnect(ws)


# ── Startup / shutdown ────────────────────────────────────────────────────────

_server_thread: threading.Thread | None = None


def start_server():
    global _server_thread

    def run():
        uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")

    _server_thread = threading.Thread(target=run, daemon=True)
    _server_thread.start()


def stop_server():
    pass  # daemon thread exits with process
