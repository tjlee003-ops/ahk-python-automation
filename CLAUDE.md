# AHK + Python Automation Application

## Project Overview

A Windows desktop workflow automation application. The user designs, records, and runs automated workflows through a GUI. AutoHotKey (AHK) handles global hotkeys and lightweight execution; Python + CustomTkinter handles the GUI and complex logic. Everything is stored as human-readable JSON.

## Tech Stack

| Layer | Technology |
|---|---|
| Global hotkeys / execution | AutoHotKey (AHK) |
| GUI + application logic | Python 3.x + CustomTkinter |
| Macro capture | pynput |
| API server | FastAPI (localhost:8080) |
| Data persistence | JSON files |
| Outlook integration | win32com.client (stubbed) |

## Folder Structure

```
ahk-python-automation/
├── ahk/
│   ├── main.ahk              # Entry point, global hotkeys, app launcher
│   ├── executor.ahk          # AHK execution engine
│   └── generated/            # Auto-generated AHK scripts from Python converter
├── python/
│   ├── main.py               # App entry point
│   ├── gui/
│   │   ├── app_shell.py      # Main window, sidebar, tabs, tray
│   │   ├── macro_recorder.py
│   │   ├── trigger_section.py
│   │   ├── variable_section.py
│   │   ├── workflow_section.py
│   │   └── email_section.py
│   ├── engine/
│   │   ├── ahk_bridge.py     # Named pipe AHK <-> Python communication
│   │   ├── workflow_runner.py
│   │   ├── trigger_manager.py
│   │   └── variable_manager.py
│   └── converters/
│       └── py_to_ahk.py      # Python-to-AHK converter
├── data/
│   ├── variables.json
│   ├── triggers.json
│   ├── settings.json
│   └── email_queue.json
├── library/
│   ├── steps/
│   ├── workflows/
│   ├── subworkflows/
│   ├── templates/
│   └── workflow_templates/
├── logs/
│   ├── recordings/
│   ├── triggers/
│   ├── workflows/
│   └── email/
├── exports/
├── backups/
├── docs/
│   └── user_guide.html
└── templates/
    └── import_template.bundle  # Reference bundle — never deletable
```

## Build Order

Build in this sequence — each layer depends on the one before it:

1. **Project scaffold** — create all folders, empty JSON files, requirements.txt
2. **AHK layer** — main.ahk with global hotkeys, executor.ahk stub
3. **App shell** — CustomTkinter window, sidebar, tabs, tray icon, console panel
4. **Variable manager** — variable types, scope, expressions, system vars, persistence
5. **Macro recorder** — pynput capture, log display, auto-filter, playback, extract dialog
6. **Trigger manager** — all 9 trigger types, priority queue, retry logic, trigger log
7. **Workflow canvas** — drag-and-drop node editor, all 15 step types, branch + loop nodes
8. **Execution engine** — variable resolution, AHK bridge, branch evaluator, loop engine, error handlers
9. **Email templates** — template editor, variable placeholders, 3 attachment modes, Outlook COM stub, queue
10. **Runtime Companion Window** — input variables, loop options, auto-save, Variable Library overlay
11. **Backup system** — scheduled + manual backup, restore, retention policy
12. **Import / Export** — .bundle format, dependency resolution, conflict resolution, reference template
13. **API server** — FastAPI on localhost:8080, all endpoints, WebSocket live stream
14. **User guide** — in-app help panel + user_guide.html generation

---

## Section Specs

### 1. AHK Layer

**Global hotkeys (defined in main.ahk):**
- `{Ctrl}{Alt}{Numpad1}` — show/hide Python GUI
- `{Ctrl}{Alt}{Numpad2}` — start macro recording; show Windows toast with Cancel
- `{Ctrl}{Alt}{Pause}` — pause active AHK execution
- `{Ctrl}{Alt}{Esc}` — cancel/stop active AHK execution
- `{Ctrl}{Alt}{V}` — open Variable Library overlay

**Startup:** AHK placed in Windows Startup folder (not registry).

**Execution modes:**
- AHK = default for all steps (faster, lighter)
- Python = fallback or explicit override
- `py_to_ahk.py` converts Python step definitions to AHK where possible; user sees both versions side-by-side

**AHK <-> Python communication:** named pipe. Python writes EXECUTE/PAUSE/STOP; AHK writes STATUS/OUTPUT back. Timeout = configurable (default 10s).

---

### 2. App Shell (`gui/app_shell.py`)

**Layout:**
```
┌─────────────────────────────────────────────┐
│  [Logo] App Name        [Stop All]  [_ ⊟ ✕] │  ← Top bar
├─────────────────────────────────────────────┤
│  [Workflow 1 ▶] [Workflow 2 ⏸] [+ New]      │  ← Workflow tabs
├──────────┬──────────────────────────────────┤
│          │                                  │
│  🔴 Rec  │                                  │
│  ⚡ Trig │       Active section content     │
│  {} Vars │                                  │
│  ▶ Flow  │                                  │
│  ✉ Email │                                  │
│          │                                  │
├──────────┴──────────────────────────────────┤
│  Console/Log panel (collapsible)            │
├─────────────────────────────────────────────┤
│  Status: Idle │ Vars: 4 │ Mode: AHK         │  ← Bottom bar
└─────────────────────────────────────────────┘
```

**Key behaviors:**
- AHK spawns Python on first hotkey press; subsequent presses toggle show/hide
- Theme syncs with Windows system setting (dark by default)
- Minimizes to tray; right-click tray = Show App / Start Recording / Stop AHK / Exit
- Tray icon color = idle (grey) / recording (red) / executing (green)
- Stop All: sends STOP to AHK pipe → cancels all Python workflow threads → closes Companion Windows
- Console panel: timestamped, color-coded (green=success, yellow=warning, red=error, blue=info), auto-saved per run

---

### 3. Macro Recorder (`gui/macro_recorder.py`)

**Capture engine:** pynput in a background thread.

**Captured events:** keystroke, mouse click (with window/control context), mouse movement, scroll, window focus change, delay.

**Window-aware targeting hierarchy:**
1. Control name/ID (most reliable)
2. Window title + process name
3. URL (browsers only)
4. Screen coordinates (fallback — show warning to user)

**Auto-filter on stop:** strip mouse movements <50ms with no click; collapse redundant moves between clicks on same control. Show count of removed events with Undo option.

**Playback:** replay via AHK at 0.5×/1×/2× speed; highlight current log entry; stop and highlight red on failure.

**Extract dialog fields:** step name, description, execution mode (AHK/Python), variable substitution for any hardcoded values.

**Step Library:** each extracted step saved as JSON to `library/steps/{name}.json`.

**Step JSON schema:**
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string",
  "created": "ISO8601",
  "version": 1,
  "tags": [],
  "execution": {
    "default_mode": "ahk",
    "ahk": "AHK script string",
    "python": "Python code string"
  },
  "inputs": ["{{varName}}"],
  "outputs": ["{{varName}}"],
  "error_handler": "notify_user",
  "targeting": {
    "window_title": "string",
    "process": "string",
    "control": "string"
  }
}
```

---

### 4. Variable Section (`engine/variable_manager.py` + `gui/variable_section.py`)

**Types:** String, Number, Boolean, List, DateTime, Window

**Scopes:**
- Global — persisted to `data/variables.json`, survives restarts
- Workflow — saved inside workflow JSON, lives for one run
- Step — in-memory only, lives for one step execution

**Scope promotion allowed** (Step → Workflow → Global). No demotion.

**Expressions:** evaluate inline math (`retryCount + 1`) and string ops (`.toUpperCase()`, string concatenation) at runtime.

**Built-in system variables (read-only, refresh each step):**
`{{today}}`, `{{now}}`, `{{activeWindow}}`, `{{clipboardContent}}`, `{{userName}}`, `{{screenWidth}}`, `{{screenHeight}}`, `{{workflowName}}`, `{{loopIndex}}`

**Runtime Companion Window (separate floating panel):**
- Opens when workflow starts, stays until complete
- Lists all input variables with editable fields
- Auto-saves every 3 seconds
- `+ Add Variable` creates inline if not exists
- Loop options: Run once / Repeat N / Until condition / Forever
- `{{loopIndex}}` shows current iteration
- Stop button = clean halt
- `📚 Vars` button or `{Ctrl}{Alt}{V}` = Variable Library overlay (searchable, click to copy placeholder)

---

### 5. Trigger Section (`engine/trigger_manager.py` + `gui/trigger_section.py`)

**Trigger types:** Hotkey, Schedule, Window Event, File Event, Clipboard, Variable Watch, Manual, Email Received (Outlook COM — stubbed), Chained

**Trigger editor has 4 sections:**
1. Condition (what fires it)
2. Preconditions (window must be open, time window, cooldown)
3. Variable Injection (data passed to workflow at fire time)
4. Target Workflow (which workflow + execution mode + Companion Window setting)

**Priority:** Critical > High > Normal > Low. Simultaneous triggers queue by priority.

**Retry strategies:**
- Time-based: retry every N seconds, up to X attempts
- Status-based: wait until another trigger completes or variable reaches value

**On retry exhaustion:** log failure, optionally fire alert workflow.

**Conflict detection:** duplicate hotkeys blocked; duplicate file watch paths warned; circular chains (A→B→A) blocked.

**Schedule modes:** Once, Daily, Weekdays, Weekly, Interval, Custom CRON.

**Trigger JSON schema (in `data/triggers.json`):**
```json
{
  "id": "uuid",
  "name": "string",
  "type": "file_event",
  "enabled": true,
  "priority": "high",
  "condition": { "watch_path": "C:\\path\\", "event": "created", "filter": "*.pdf" },
  "preconditions": { "ensure_window": "App Name", "wait_timeout": 10, "cooldown_seconds": 30, "time_window": { "start": "08:00", "end": "18:00" } },
  "retry": { "strategy": "time_based", "interval_seconds": 30, "max_attempts": 3, "on_exhaustion": "alert_workflow" },
  "injects": ["{{fileName}}", "{{filePath}}", "{{triggerTime}}"],
  "target_workflow": "uuid",
  "execution_mode": "ahk"
}
```

---

### 6. Workflow Section (`gui/workflow_section.py`)

**Canvas:** drag-and-drop node editor. Each step = node. Lines between nodes = execution order. Mini-map in corner. Zoom/pan. Right-click node = edit/duplicate/delete.

**15 built-in step types:** Open File/App, Window Focus, Click, Type Text, Clipboard, Wait, Branch, Loop, Send Email, Log, Notify, Run Step, Run Workflow, Stop, Error Handler.

**Branch node operators:** equals, not equals, greater than, less than, between, contains, starts with, ends with, is empty, is not empty, variable equals variable.

**Loop modes:** N times, until condition, forever, list iteration. `{{loopIndex}}` always reflects current iteration.

**Per-step error handlers:** stop, skip and continue, retry N times, run error workflow, notify user.

**Per-step execution mode override:** AHK or Python (overrides workflow default).

**Execution view:** current step pulses; completed = green; failed = red; skipped = grey.

**Version history:** auto-snapshot on every save; stored in `library/workflows/{name}/versions/`. Restore creates new snapshot (nothing deleted).

**Sub-workflows:** select nodes → Group as Sub-Workflow → saved as purple node in Step Library. Has explicit inputs/outputs. Versioned independently.

**Canvas annotations:** sticky notes (double-click empty area) and inline node comments (right-click → Add Comment). Toggle with `A` key.

**Workflow JSON schema:**
```json
{
  "id": "uuid",
  "name": "string",
  "current_version": 1,
  "default_mode": "ahk",
  "nodes": [
    { "id": "node_1", "type": "step", "step_id": "uuid", "position": { "x": 100, "y": 100 }, "next": "node_2", "error_handler": "stop" },
    { "id": "node_2", "type": "branch", "condition": "{{total}} > 1000", "yes": "node_3", "no": "node_4" },
    { "id": "node_3", "type": "loop", "mode": "repeat", "count": "{{itemCount}}", "body": "node_5", "next": "node_6" }
  ],
  "annotations": [
    { "id": "note_1", "type": "sticky", "text": "string", "position": { "x": 0, "y": 0 }, "color": "yellow" }
  ]
}
```

---

### 7. Email Templates (`gui/email_section.py`)

**Template fields:** name, category, subject (supports `{{vars}}`), body (rich text, supports `{{vars}}`), To/CC/BCC (supports `{{vars}}`), attachments, execution mode.

**Variable autocomplete:** type `{{` → dropdown of all vars. `📚 Vars` button opens Variable Library overlay.

**Preview mode:** renders template with live variable values. Unresolved vars highlighted orange.

**Three attachment modes:**
1. Named variable — `{{reportName}}.pdf` — prompts for location if not found at send time
2. Save as draft — Outlook compose opens pre-filled; user attaches manually
3. File explorer picker — native Windows open dialog; selected files listed; user clicks Send

**Three execution modes:** Send Directly, Open for Review, Save as Draft.

**Outlook COM (stubbed in `engine/email_sender.py`):**
```python
def send_email(template, variables): pass  # win32com.client.Dispatch("Outlook.Application")
def create_draft(template, variables): pass
def open_compose(template, variables): pass
```

When Outlook unavailable → emails queue in `data/email_queue.json` → auto-send on reconnect.

---

### 8. Execution Engine (`engine/workflow_runner.py`)

**Lifecycle:** Trigger fires → inject variables → open Companion Window → resolve starting node → step execution loop → workflow complete.

**Step execution loop:**
1. Resolve `{{variables}}` in step config
2. Check preconditions (window exists, etc.)
3. Determine execution mode (AHK or Python)
4. Execute
5. Capture output variables
6. Log result to console
7. Evaluate next node

**Unresolved variable:** pause execution, prompt user in Companion Window to supply value or skip.

**AHK bridge (`engine/ahk_bridge.py`):** named pipe. Send: `EXECUTE step.ahk`, `PAUSE`, `STOP`. Receive: `STATUS:success`, `OUTPUT:varName=value`. Timeout = configurable.

**Branch evaluator:** resolve left + right operands → apply operator → route to YES or NO node.

**Loop engine:** init `{{loopIndex}} = 0` → execute body → increment → evaluate exit condition → repeat or exit.

**Stop All:** 1) STOP to AHK pipe 2) AHK releases held keys 3) cancel all Python threads 4) reset loop counters 5) close Companion Windows 6) log stop with timestamp and final variable state.

---

### 9. Backup System

**What's backed up:** `data/`, `library/`, `exports/`. Logs excluded by default (toggle in settings).

**Modes:** Manual (Settings → Backup Now), Scheduled (Daily/Weekly/On Close/Disabled), Pre-import auto-backup, Pre-update auto-backup.

**Storage:** `backups/YYYY-MM-DD_HHMM_auto.zip` or `_manual.zip`. User-configurable destination. Retention = keep last N (default 10).

**Restore:** preview contents → confirm → auto-backup current state → restore → restart app.

---

### 10. Import / Export

**Export types:**
- Full Export — entire `data/` and `library/`
- Workflow Bundle — workflow + all deps auto-resolved (steps, variables, email templates)
- Custom Selection — user picks assets

**Bundle format:** `.bundle` = zip containing JSON assets + `manifest.json`.

**Import:** drag-and-drop or Settings → Import File. Reads manifest, shows preview. Conflict resolution per item: Keep Existing / Overwrite / Import as Copy. "Apply to all" checkbox. Pre-import auto-backup always runs.

**Reference template bundle** at `templates/import_template.bundle` — never deletable. Contains annotated sample JSON for every asset type with inline comments. Serves as the schema reference for power users and AI tools.

---

### 11. API Server (`python/api/`)

**Framework:** FastAPI. Runs on `http://127.0.0.1:8080`. Starts with app, stops on close. No auth (localhost only). All JSON.

**Endpoints:**

```
GET/POST/PUT/DELETE  /api/v1/workflows
POST                 /api/v1/workflows/{id}/run
POST                 /api/v1/workflows/{id}/stop
GET                  /api/v1/workflows/{id}/status
GET                  /api/v1/workflows/{id}/versions

GET/POST/PUT/DELETE  /api/v1/variables
GET/POST/PUT/DELETE  /api/v1/triggers
POST                 /api/v1/triggers/{id}/enable
POST                 /api/v1/triggers/{id}/disable
GET/POST/PUT/DELETE  /api/v1/steps
GET/POST/PUT         /api/v1/email/templates
POST                 /api/v1/email/send

GET                  /api/v1/export
POST                 /api/v1/import
GET                  /api/v1/logs/workflows
GET                  /api/v1/logs/triggers
GET                  /api/v1/logs/email
GET                  /api/v1/status
GET                  /api/v1/guide       ← returns full API schema as JSON
POST                 /api/v1/backup
```

**WebSocket:** `ws://127.0.0.1:8080/ws/status` — live event stream.

Event types: `step_started`, `step_completed`, `branch_taken`, `variable_changed`, `loop_iteration`, `workflow_complete`, `workflow_error`. Each includes `workflow`, `step`, `data`, `time`.

---

### 12. User Guide

**In-app:** `?` button in top bar → right-side drawer. Context-sensitive (opens to active section's chapter). Searchable. Per-section `?` icon tooltips.

**Standalone:** `docs/user_guide.html` — self-contained, no internet required. Auto-regenerated on app update.

**Chapters:** Getting Started, AHK Layer, Macro Recorder, Variables, Triggers, Workflows (Canvas / Branching / Loops / Sub-workflows), Email Templates, Import/Export, Backup & Restore, API Reference, Keyboard Shortcuts.

---

## Settings Schema (`data/settings.json`)

```json
{
  "theme": "system",
  "default_execution_mode": "ahk",
  "ahk_path": "ahk/main.ahk",
  "startup_with_windows": true,
  "autosave_interval_seconds": 3,
  "log_retention": { "enabled": true, "days": 30 },
  "companion_window": { "default_open": true, "always_on_top": true },
  "backup": { "enabled": true, "schedule": "daily", "time": "09:00", "keep_last": 10, "destination": "backups/", "include_logs": false },
  "hotkeys": {
    "show_app": "^!Numpad1",
    "start_recording": "^!Numpad2",
    "pause_ahk": "^!Pause",
    "stop_ahk": "^!Escape",
    "variable_library": "^!v"
  }
}
```

---

## Keyboard Shortcuts

| Hotkey | Action |
|---|---|
| `{Ctrl}{Alt}{Num1}` | Show / hide app |
| `{Ctrl}{Alt}{Num2}` | Start macro recording |
| `{Ctrl}{Alt}{Pause}` | Pause AHK execution |
| `{Ctrl}{Alt}{Esc}` | Stop AHK execution |
| `{Ctrl}{Alt}{V}` | Variable Library overlay |
| `?` (in app) | Open help panel |
| `A` (on canvas) | Toggle annotation visibility |
| `{Ctrl}{S}` (on canvas) | Save workflow |
| `{Ctrl}{Z}` (on canvas) | Undo canvas action |

---

## Dependencies (`requirements.txt`)

```
customtkinter
pynput
fastapi
uvicorn
pywin32
watchdog
pydantic
```

---

## Notes for Claude Code

- Build each section as a self-contained module before wiring them together
- The AHK bridge is the most critical integration point — get it solid before building the execution engine
- Outlook COM (`win32com`) should be fully stubbed with clear `# TODO: wire COM here` comments — do not require Outlook to be present for the app to run
- The `.bundle` format is just a zip — use Python's `zipfile` module
- All file I/O should go through a central `FileManager` class to keep paths consistent
- Use `uuid4()` for all IDs
- Every JSON write should be atomic (write to temp file, rename) to prevent corruption
- The API server should run in a background thread so it does not block the GUI
- Start with dark theme hardcoded; wire system theme detection after core features work
