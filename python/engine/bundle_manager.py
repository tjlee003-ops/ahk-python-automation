"""Import / Export — .bundle format (zip), dependency resolution, conflict resolution."""

from __future__ import annotations

import datetime
import json
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any

from python.file_manager import path, read_json, write_json

REFERENCE_BUNDLE = "templates/import_template.bundle"


# ── Manifest schema ───────────────────────────────────────────────────────────

def _make_manifest(assets: list[dict], export_type: str) -> dict:
    return {
        "id":          str(uuid.uuid4()),
        "export_type": export_type,
        "created":     datetime.datetime.now().isoformat(),
        "version":     1,
        "assets":      assets,
    }


# ── Export ────────────────────────────────────────────────────────────────────

def export_full(dest_path: str) -> str:
    """Export all data/ and library/ to a .bundle file."""
    assets = []
    dirs   = ["data", "library"]
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in dirs:
            src = path(d)
            if not src.exists():
                continue
            for f in src.rglob("*.json"):
                rel = f.relative_to(path(""))
                zf.write(f, rel)
                assets.append({"path": str(rel), "type": d})
        manifest = _make_manifest(assets, "full")
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return dest_path


def export_workflow(workflow_id: str, dest_path: str) -> str | None:
    """Export a single workflow with all resolved dependencies."""
    wf_data, deps = _resolve_workflow_deps(workflow_id)
    if not wf_data:
        return None

    assets = []
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        def add(rel_path: str, data: dict):
            assets.append({"path": rel_path, "type": _asset_type(rel_path)})
            zf.writestr(rel_path, json.dumps(data, indent=2))

        add(f"library/workflows/{wf_data['name']}/workflow.json", wf_data)
        for dep_type, dep_data in deps:
            add(dep_type, dep_data)

        manifest = _make_manifest(assets, "workflow")
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return dest_path


def export_selection(asset_paths: list[str], dest_path: str) -> str:
    """Export a custom selection of asset paths."""
    assets = []
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in asset_paths:
            src = path(rel)
            if src.exists():
                zf.write(src, rel)
                assets.append({"path": rel, "type": _asset_type(rel)})
        manifest = _make_manifest(assets, "selection")
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return dest_path


def _asset_type(rel_path: str) -> str:
    if "workflows" in rel_path:   return "workflow"
    if "steps"     in rel_path:   return "step"
    if "templates" in rel_path:   return "email_template"
    if "data"      in rel_path:   return "data"
    return "other"


def _resolve_workflow_deps(workflow_id: str) -> tuple[dict | None, list]:
    """Return (workflow_dict, list of (rel_path, dep_dict)) for all step deps."""
    lib = path("library/workflows")
    if not lib.exists():
        return None, []
    for wf_dir in lib.iterdir():
        wf_file = wf_dir / "workflow.json"
        if not wf_file.exists():
            continue
        data = read_json(str(wf_file.relative_to(path(""))))
        if data and data.get("id") == workflow_id:
            deps = []
            for node in data.get("nodes", []):
                step_id = node.get("step_id", "")
                if step_id:
                    dep = _find_step(step_id)
                    if dep:
                        deps.append((f"library/steps/{dep['name']}.json", dep))
            return data, deps
    return None, []


def _find_step(step_id: str) -> dict | None:
    steps_dir = path("library/steps")
    if not steps_dir.exists():
        return None
    for f in steps_dir.glob("*.json"):
        data = read_json(str(f.relative_to(path(""))))
        if data and data.get("id") == step_id:
            return data
    return None


# ── Import ────────────────────────────────────────────────────────────────────

class ConflictResolution:
    KEEP_EXISTING = "keep"
    OVERWRITE     = "overwrite"
    COPY          = "copy"


def read_bundle(bundle_path: str) -> tuple[dict, list[dict]]:
    """Return (manifest, list of asset previews with path + type)."""
    with zipfile.ZipFile(bundle_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode())
        previews = []
        for asset in manifest.get("assets", []):
            rel = asset["path"]
            if rel in zf.namelist():
                try:
                    data = json.loads(zf.read(rel).decode())
                    previews.append({
                        "path": rel,
                        "type": asset.get("type", "other"),
                        "name": data.get("name", rel),
                        "id":   data.get("id", ""),
                        "data": data,
                    })
                except Exception:
                    previews.append({"path": rel, "type": asset.get("type"), "data": None})
    return manifest, previews


def import_bundle(bundle_path: str,
                  resolutions: dict[str, str],
                  default_resolution: str = ConflictResolution.KEEP_EXISTING) -> dict:
    """Apply pre-restore auto-backup, then import assets with conflict resolution."""
    from python.engine.backup_manager import create_backup
    create_backup("pre_import")

    with zipfile.ZipFile(bundle_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode())
        imported = skipped = copied = 0

        for asset in manifest.get("assets", []):
            rel  = asset["path"]
            if rel not in zf.namelist():
                continue
            try:
                data = json.loads(zf.read(rel).decode())
            except Exception:
                continue

            dest = path(rel)
            resolution = resolutions.get(rel, default_resolution)

            if dest.exists() and resolution == ConflictResolution.KEEP_EXISTING:
                skipped += 1
                continue

            if dest.exists() and resolution == ConflictResolution.COPY:
                data["id"]   = str(uuid.uuid4())
                data["name"] = data.get("name", "imported") + " (copy)"
                rel_copy = rel.replace(".json", f"_{data['id'][:8]}.json")
                dest = path(rel_copy)
                copied += 1
            else:
                imported += 1

            dest.parent.mkdir(parents=True, exist_ok=True)
            write_json(str(dest.relative_to(path(""))), data)

    return {"imported": imported, "skipped": skipped, "copied": copied}


# ── Reference bundle (never deletable) ───────────────────────────────────────

def ensure_reference_bundle():
    """Create the reference template bundle if it doesn't exist."""
    dest = path(REFERENCE_BUNDLE)
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)

    sample_step = {
        "id": "EXAMPLE_STEP_ID",
        "name": "Example Step",
        "description": "Sample step for reference — shows all fields",
        "created": "2024-01-01T00:00:00",
        "version": 1,
        "tags": ["example"],
        "execution": {"default_mode": "ahk", "ahk": "Sleep, 100", "python": "time.sleep(0.1)"},
        "inputs": ["{{inputVar}}"],
        "outputs": ["{{outputVar}}"],
        "error_handler": "notify_user",
        "targeting": {"window_title": "Example App", "process": "example.exe", "control": "Edit1"},
    }
    sample_workflow = {
        "id": "EXAMPLE_WORKFLOW_ID",
        "name": "Example Workflow",
        "current_version": 1,
        "default_mode": "ahk",
        "nodes": [
            {"id": "node_1", "type": "step", "step_id": "EXAMPLE_STEP_ID",
             "label": "Do Thing", "position": {"x": 100, "y": 100},
             "next": "node_2", "error_handler": "stop"},
            {"id": "node_2", "type": "branch",
             "label": "Check total",
             "position": {"x": 100, "y": 200},
             "condition": "{{total}} > 1000", "yes": "", "no": ""},
        ],
        "annotations": [
            {"id": "note_1", "type": "sticky", "text": "Sample note",
             "position": {"x": 300, "y": 50}, "color": "yellow"},
        ],
    }

    assets = []
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("library/steps/Example Step.json",
                    json.dumps(sample_step, indent=2))
        assets.append({"path": "library/steps/Example Step.json", "type": "step"})
        zf.writestr("library/workflows/Example Workflow/workflow.json",
                    json.dumps(sample_workflow, indent=2))
        assets.append({"path": "library/workflows/Example Workflow/workflow.json",
                       "type": "workflow"})
        manifest = _make_manifest(assets, "reference")
        manifest["readonly"] = True
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
