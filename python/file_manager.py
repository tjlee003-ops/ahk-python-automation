"""Central file I/O — all paths flow through here; writes are atomic."""

import json
import os
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent


def path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def read_json(rel_path: str) -> any:
    full = path(rel_path)
    if not full.exists():
        return None
    with full.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(rel_path: str, data: any) -> None:
    """Atomic write: write to temp file then rename."""
    full = path(rel_path)
    full.parent.mkdir(parents=True, exist_ok=True)
    tmp = full.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(full)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def ensure_dirs() -> None:
    """Create all required project directories if they don't exist."""
    dirs = [
        "ahk/generated",
        "python/gui",
        "python/engine",
        "python/converters",
        "python/api",
        "data",
        "library/steps",
        "library/workflows",
        "library/subworkflows",
        "library/templates",
        "library/workflow_templates",
        "logs/recordings",
        "logs/triggers",
        "logs/workflows",
        "logs/email",
        "exports",
        "backups",
        "docs",
        "templates",
    ]
    for d in dirs:
        path(d).mkdir(parents=True, exist_ok=True)
