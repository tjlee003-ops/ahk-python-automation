"""Email sender — Outlook COM stub + queue fallback."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from python.file_manager import read_json, write_json

QUEUE_PATH = "data/email_queue.json"


def send_email(template: dict, variables: dict[str, Any]) -> bool:
    """Send directly via Outlook COM. Falls back to queue if unavailable."""
    from python.engine.variable_manager import get_manager
    var_mgr = get_manager()

    def resolve(text: str) -> str:
        if not isinstance(text, str):
            return str(text) if text else ""
        for k, v in variables.items():
            text = text.replace(f"{{{{{k}}}}}", str(v))
        return var_mgr.resolve(text)

    resolved = {
        "to":      resolve(template.get("to", "")),
        "cc":      resolve(template.get("cc", "")),
        "bcc":     resolve(template.get("bcc", "")),
        "subject": resolve(template.get("subject", "")),
        "body":    resolve(template.get("body", "")),
    }

    try:
        # TODO: wire COM here
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To      = resolved["to"]
        mail.CC      = resolved["cc"]
        mail.BCC     = resolved["bcc"]
        mail.Subject = resolved["subject"]
        mail.Body    = resolved["body"]
        _attach_files(mail, template.get("attachments", []), variables, var_mgr)
        mail.Send()
        return True
    except Exception:
        _queue(template, variables)
        return False


def create_draft(template: dict, variables: dict[str, Any]) -> bool:
    """Save as Outlook draft."""
    try:
        # TODO: wire COM here
        import win32com.client
        from python.engine.variable_manager import get_manager
        var_mgr = get_manager()

        def resolve(t): return var_mgr.resolve(t) if isinstance(t, str) else str(t)

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To      = resolve(template.get("to", ""))
        mail.Subject = resolve(template.get("subject", ""))
        mail.Body    = resolve(template.get("body", ""))
        _attach_files(mail, template.get("attachments", []), variables, var_mgr)
        mail.Save()
        return True
    except Exception:
        _queue(template, variables, mode="draft")
        return False


def open_compose(template: dict, variables: dict[str, Any]) -> bool:
    """Open Outlook compose window pre-filled."""
    try:
        # TODO: wire COM here
        import win32com.client
        from python.engine.variable_manager import get_manager
        var_mgr = get_manager()

        def resolve(t): return var_mgr.resolve(t) if isinstance(t, str) else str(t)

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To      = resolve(template.get("to", ""))
        mail.Subject = resolve(template.get("subject", ""))
        mail.Body    = resolve(template.get("body", ""))
        mail.Display(False)
        return True
    except Exception:
        return False


def _attach_files(mail, attachments: list, variables: dict, var_mgr):
    for att in attachments:
        mode = att.get("mode", "variable")
        if mode == "variable":
            file_path = var_mgr.resolve(att.get("path", ""))
            if file_path:
                try:
                    mail.Attachments.Add(file_path)
                except Exception:
                    pass
        elif mode == "picker":
            paths = att.get("paths", [])
            for p in paths:
                try:
                    mail.Attachments.Add(p)
                except Exception:
                    pass


def _queue(template: dict, variables: dict, mode: str = "send"):
    queue = read_json(QUEUE_PATH) or []
    queue.append({
        "id": str(uuid.uuid4()),
        "queued_at": datetime.datetime.now().isoformat(),
        "mode": mode,
        "template": template,
        "variables": variables,
    })
    write_json(QUEUE_PATH, queue)


def flush_queue() -> int:
    """Attempt to send all queued emails. Returns count sent."""
    queue = read_json(QUEUE_PATH) or []
    if not queue:
        return 0
    remaining = []
    sent = 0
    for item in queue:
        ok = send_email(item["template"], item["variables"])
        if ok:
            sent += 1
        else:
            remaining.append(item)
    write_json(QUEUE_PATH, remaining)
    return sent
