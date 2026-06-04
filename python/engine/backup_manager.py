"""Backup system — scheduled/manual backup, restore, retention policy."""

from __future__ import annotations

import datetime
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable

from python.file_manager import path, read_json

BACKUP_DIRS   = ["data", "library", "exports"]
BACKUP_DEST   = "backups"
RETENTION_KEY = "backup"


def _settings() -> dict:
    return read_json("data/settings.json") or {}


def _backup_dest() -> Path:
    s = _settings()
    dest = s.get("backup", {}).get("destination", BACKUP_DEST)
    p = path(dest)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _include_logs() -> bool:
    return _settings().get("backup", {}).get("include_logs", False)


def _keep_last() -> int:
    return _settings().get("backup", {}).get("keep_last", 10)


# ── Create backup ─────────────────────────────────────────────────────────────

def create_backup(tag: str = "manual") -> Path:
    ts   = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    name = f"{ts}_{tag}.zip"
    dest = _backup_dest() / name

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for dir_name in BACKUP_DIRS:
            src = path(dir_name)
            if src.exists():
                for file in src.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(path("")))
        if _include_logs():
            src = path("logs")
            if src.exists():
                for file in src.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(path("")))

    _apply_retention()
    return dest


def _apply_retention():
    dest   = _backup_dest()
    keep   = _keep_last()
    zips   = sorted(dest.glob("*.zip"), key=lambda f: f.stat().st_mtime)
    excess = len(zips) - keep
    for f in zips[:excess]:
        f.unlink()


# ── List backups ──────────────────────────────────────────────────────────────

def list_backups() -> list[dict]:
    dest = _backup_dest()
    result = []
    for f in sorted(dest.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        result.append({
            "name":     f.name,
            "path":     str(f),
            "size_kb":  round(f.stat().st_size / 1024, 1),
            "modified": datetime.datetime.fromtimestamp(
                f.stat().st_mtime).isoformat(),
        })
    return result


# ── Preview backup ────────────────────────────────────────────────────────────

def preview_backup(zip_path: str) -> list[str]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        return zf.namelist()


# ── Restore ───────────────────────────────────────────────────────────────────

def restore_backup(zip_path: str) -> Path:
    """Auto-backup current state, then restore from zip. Returns pre-restore backup path."""
    pre = create_backup("pre_restore")
    root = path("")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(root)
    return pre


# ── Scheduler ────────────────────────────────────────────────────────────────

class BackupScheduler:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._running = False
        self._on_backup: Callable[[Path], None] | None = None

    def start(self, on_backup: Callable[[Path], None] | None = None):
        self._on_backup = on_backup
        self._running   = True
        self._thread    = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            s       = _settings()
            cfg     = s.get("backup", {})
            schedule = cfg.get("schedule", "disabled")
            if schedule == "disabled":
                time.sleep(60)
                continue

            now       = datetime.datetime.now()
            sched_t   = cfg.get("time", "09:00")
            h, m      = map(int, sched_t.split(":"))
            target    = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)

            if schedule == "weekly":
                # fire on Monday only
                days_ahead = (0 - target.weekday()) % 7
                target += datetime.timedelta(days=days_ahead)

            wait = (target - now).total_seconds()
            time.sleep(wait)

            if self._running:
                p = create_backup("auto")
                if self._on_backup:
                    self._on_backup(p)


_scheduler: BackupScheduler | None = None


def get_scheduler() -> BackupScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackupScheduler()
    return _scheduler
