"""Generate docs/user_guide.html — self-contained, no internet required."""

from __future__ import annotations

from python.file_manager import path

CHAPTERS = [
    ("getting_started",   "Getting Started"),
    ("ahk_layer",         "AHK Layer"),
    ("macro_recorder",    "Macro Recorder"),
    ("variables",         "Variables"),
    ("triggers",          "Triggers"),
    ("workflows",         "Workflows"),
    ("email_templates",   "Email Templates"),
    ("import_export",     "Import / Export"),
    ("backup_restore",    "Backup & Restore"),
    ("api_reference",     "API Reference"),
    ("keyboard_shortcuts","Keyboard Shortcuts"),
]

CONTENT: dict[str, str] = {
    "getting_started": """
<h2>Getting Started</h2>
<p>AHK-Python Automation lets you design, record, and run automated workflows on Windows.
AutoHotKey handles global hotkeys and fast execution; Python + CustomTkinter handles the GUI.</p>
<h3>Quick start</h3>
<ol>
  <li>Install dependencies: <code>pip install -r requirements.txt</code></li>
  <li>Run the app: <code>python -m python.main</code></li>
  <li>The GUI opens. Use the sidebar to navigate sections.</li>
  <li>Press <kbd>Ctrl+Alt+Num2</kbd> to start recording a macro.</li>
</ol>
<h3>First workflow</h3>
<ol>
  <li>Click <strong>▶ Flow</strong> in the sidebar.</li>
  <li>Right-click the canvas → add steps.</li>
  <li>Press <kbd>Ctrl+S</kbd> to save, then click <strong>▶ Run</strong>.</li>
</ol>
""",
    "ahk_layer": """
<h2>AHK Layer</h2>
<p>AutoHotKey runs as a background process and communicates with Python via a named pipe
(<code>\\\\.\pipe\AHKPythonBridge</code>).</p>
<h3>Global hotkeys</h3>
<table>
  <tr><th>Hotkey</th><th>Action</th></tr>
  <tr><td>Ctrl+Alt+Num1</td><td>Show / hide the app window</td></tr>
  <tr><td>Ctrl+Alt+Num2</td><td>Start / stop macro recording</td></tr>
  <tr><td>Ctrl+Alt+Pause</td><td>Pause active AHK execution</td></tr>
  <tr><td>Ctrl+Alt+Esc</td><td>Stop / cancel active AHK execution</td></tr>
  <tr><td>Ctrl+Alt+V</td><td>Open Variable Library overlay</td></tr>
</table>
<h3>Execution modes</h3>
<p><strong>AHK mode</strong> — default, faster, lighter. Uses AutoHotKey to run each step.</p>
<p><strong>Python mode</strong> — fallback or explicit override. Runs steps directly in Python.</p>
<p>The <code>py_to_ahk.py</code> converter generates AHK equivalents for all step types.
Both versions are shown side-by-side in the Extract Step dialog.</p>
""",
    "macro_recorder": """
<h2>Macro Recorder</h2>
<p>Records keystrokes, mouse clicks, scroll events, window focus changes, and delays.</p>
<h3>Recording</h3>
<ol>
  <li>Click <strong>⏺ Record</strong> or press <kbd>Ctrl+Alt+Num2</kbd>.</li>
  <li>Perform actions in any application.</li>
  <li>Click <strong>⏹ Stop</strong> — events are auto-filtered and displayed in the log.</li>
</ol>
<h3>Auto-filter</h3>
<p>On stop, mouse movements under 50 ms with no click are removed, and redundant moves
between clicks on the same control are collapsed. The count of removed events is shown
with an Undo option.</p>
<h3>Playback</h3>
<p>Click <strong>▶ Play</strong> at 0.5×, 1×, or 2× speed. The current step highlights in the log.
A failure highlights in red and stops playback.</p>
<h3>Extract to Library</h3>
<ol>
  <li>Click <strong>Extract Step</strong>.</li>
  <li>Enter a name, description, and execution mode.</li>
  <li>The step is saved as JSON to <code>library/steps/</code> and appears in the Step Library.</li>
</ol>
""",
    "variables": """
<h2>Variables</h2>
<h3>Types</h3>
<p>String, Number, Boolean, List, DateTime, Window.</p>
<h3>Scopes</h3>
<ul>
  <li><strong>Global</strong> — persisted to <code>data/variables.json</code>, survives restarts.</li>
  <li><strong>Workflow</strong> — saved inside the workflow, lives for one run.</li>
  <li><strong>Step</strong> — in-memory only, lives for one step execution.</li>
</ul>
<p>Scope promotion is allowed (Step → Workflow → Global). Demotion is not.</p>
<h3>Using variables</h3>
<p>Reference any variable with <code>{{variableName}}</code> in any text field.
Inline expressions are also supported: <code>{{retryCount + 1}}</code>.</p>
<h3>System variables (read-only)</h3>
<table>
  <tr><th>Variable</th><th>Value</th></tr>
  <tr><td>{{today}}</td><td>Current date (YYYY-MM-DD)</td></tr>
  <tr><td>{{now}}</td><td>Current datetime (ISO 8601)</td></tr>
  <tr><td>{{activeWindow}}</td><td>Title of the foreground window</td></tr>
  <tr><td>{{clipboardContent}}</td><td>Current clipboard text</td></tr>
  <tr><td>{{userName}}</td><td>Windows username</td></tr>
  <tr><td>{{screenWidth}} / {{screenHeight}}</td><td>Screen dimensions</td></tr>
  <tr><td>{{workflowName}}</td><td>Name of the running workflow</td></tr>
  <tr><td>{{loopIndex}}</td><td>Current loop iteration (0-based)</td></tr>
</table>
<h3>Variable Library overlay</h3>
<p>Press <kbd>Ctrl+Alt+V</kbd> or click <strong>📚 Vars</strong> to open the searchable overlay.
Click any variable to copy its <code>{{placeholder}}</code> to the clipboard.</p>
""",
    "triggers": """
<h2>Triggers</h2>
<p>Triggers fire workflows automatically based on conditions.</p>
<h3>Trigger types</h3>
<table>
  <tr><th>Type</th><th>Description</th></tr>
  <tr><td>Hotkey</td><td>Global keyboard shortcut</td></tr>
  <tr><td>Schedule</td><td>Once, Daily, Weekdays, Weekly, Interval, Custom CRON</td></tr>
  <tr><td>Window Event</td><td>Window opened, closed, or focused</td></tr>
  <tr><td>File Event</td><td>File created, modified, or deleted in a watched folder</td></tr>
  <tr><td>Clipboard</td><td>Clipboard content changes (optional regex filter)</td></tr>
  <tr><td>Variable Watch</td><td>A variable reaches a specific value</td></tr>
  <tr><td>Manual</td><td>Triggered by the user or via API</td></tr>
  <tr><td>Email Received</td><td>Outlook email arrives matching criteria (stubbed)</td></tr>
  <tr><td>Chained</td><td>Fires when another trigger completes</td></tr>
</table>
<h3>Priority</h3>
<p>Critical &gt; High &gt; Normal &gt; Low. Simultaneous triggers are queued by priority.</p>
<h3>Retry strategies</h3>
<p><strong>Time-based:</strong> retry every N seconds, up to X attempts.<br>
<strong>Status-based:</strong> wait until a variable reaches a value.<br>
On exhaustion: log failure and optionally fire an alert workflow.</p>
<h3>Conflict detection</h3>
<ul>
  <li>Duplicate hotkeys are blocked.</li>
  <li>Duplicate file watch paths show a warning.</li>
  <li>Circular chains (A→B→A) are blocked.</li>
</ul>
""",
    "workflows": """
<h2>Workflows</h2>
<h3>Canvas</h3>
<p>Drag-and-drop node editor. Each step is a node; lines show execution order.
Right-click on an empty area to add a step. Right-click a node to edit, duplicate, or delete.</p>
<ul>
  <li><strong>Zoom:</strong> mouse wheel</li>
  <li><strong>Pan:</strong> click and drag empty canvas</li>
  <li><strong>Toggle annotations:</strong> press <kbd>A</kbd></li>
  <li><strong>Save:</strong> <kbd>Ctrl+S</kbd></li>
</ul>
<h3>Step types</h3>
<p>Open File/App, Window Focus, Click, Type Text, Clipboard, Wait, Branch, Loop,
Send Email, Log, Notify, Run Step, Run Workflow, Stop, Error Handler.</p>
<h3>Branch nodes</h3>
<p>Conditions: equals, not equals, greater/less than, between, contains, starts/ends with,
is empty, is not empty, variable equals variable.</p>
<p>Routes to a <strong>Yes</strong> node or <strong>No</strong> node based on the result.</p>
<h3>Loop nodes</h3>
<p>Modes: Repeat N, Until condition, Forever, List iteration.<br>
<code>{{loopIndex}}</code> is updated each iteration.</p>
<h3>Per-step settings</h3>
<ul>
  <li><strong>Error handler:</strong> stop, skip and continue, retry N times, run error workflow, notify user.</li>
  <li><strong>Execution mode override:</strong> AHK or Python (overrides workflow default).</li>
</ul>
<h3>Version history</h3>
<p>A snapshot is saved on every save to <code>library/workflows/{name}/versions/</code>.
Restoring a version creates a new snapshot — nothing is deleted.</p>
<h3>Sub-workflows</h3>
<p>Select nodes → right-click → Group as Sub-Workflow. Saved as a purple node in the Step Library.
Sub-workflows have explicit inputs/outputs and are versioned independently.</p>
<h3>Annotations</h3>
<p>Double-click empty canvas to add a sticky note.
Right-click a node → Add Comment to add an inline node comment.</p>
""",
    "email_templates": """
<h2>Email Templates</h2>
<p>Create reusable email templates with variable placeholders.</p>
<h3>Fields</h3>
<p>Name, Category, To, CC, BCC, Subject, Body — all support <code>{{variables}}</code>.</p>
<h3>Variable autocomplete</h3>
<p>Type <code>{{</code> in any field to trigger the variable dropdown.
Click <strong>📚 Vars</strong> to open the Variable Library overlay.</p>
<h3>Preview</h3>
<p>Click <strong>👁 Preview</strong> to render the template with live variable values.
Unresolved variables are highlighted in orange.</p>
<h3>Attachment modes</h3>
<ol>
  <li><strong>Named variable</strong> — e.g. <code>{{reportName}}.pdf</code>. Prompts for location if not found at send time.</li>
  <li><strong>Save as draft</strong> — Outlook compose opens pre-filled; user attaches manually.</li>
  <li><strong>File explorer picker</strong> — native Windows open dialog; selected files are listed.</li>
</ol>
<h3>Execution modes</h3>
<ul>
  <li><strong>Send Directly</strong> — sends immediately via Outlook COM.</li>
  <li><strong>Open for Review</strong> — opens Outlook compose window pre-filled.</li>
  <li><strong>Save as Draft</strong> — saves to Outlook drafts folder.</li>
</ul>
<p>If Outlook is unavailable, emails queue in <code>data/email_queue.json</code>
and auto-send on reconnect.</p>
""",
    "import_export": """
<h2>Import / Export</h2>
<h3>Export types</h3>
<ul>
  <li><strong>Full Export</strong> — all <code>data/</code> and <code>library/</code> assets.</li>
  <li><strong>Workflow Bundle</strong> — one workflow plus all resolved dependencies (steps, variables, email templates).</li>
  <li><strong>Custom Selection</strong> — you pick which assets to include.</li>
</ul>
<h3>Bundle format</h3>
<p>A <code>.bundle</code> file is a ZIP containing JSON assets plus a <code>manifest.json</code>
that lists all included assets with their types.</p>
<h3>Import</h3>
<ol>
  <li>Drag-and-drop a <code>.bundle</code> file onto the import zone, or click <strong>Browse .bundle…</strong>.</li>
  <li>The manifest is read and a preview is shown.</li>
  <li>For each asset, choose: <strong>Keep Existing</strong> / <strong>Overwrite</strong> / <strong>Import as Copy</strong>.</li>
  <li>Use the "Apply to all" checkbox to set a default resolution.</li>
  <li>A pre-import backup is always created automatically before applying changes.</li>
</ol>
<h3>Reference template</h3>
<p>The file <code>templates/import_template.bundle</code> is a read-only reference bundle
containing annotated sample JSON for every asset type. It serves as the schema reference
for power users and API integrations. It cannot be deleted.</p>
""",
    "backup_restore": """
<h2>Backup &amp; Restore</h2>
<h3>What is backed up</h3>
<p><code>data/</code>, <code>library/</code>, and <code>exports/</code>.
Logs are excluded by default (toggle in Settings → Backup &amp; Restore).</p>
<h3>Backup modes</h3>
<ul>
  <li><strong>Manual</strong> — Settings → Backup Now.</li>
  <li><strong>Scheduled</strong> — Daily, Weekly, On Close, or Disabled.</li>
  <li><strong>Pre-import auto-backup</strong> — always runs before any import.</li>
  <li><strong>Pre-restore auto-backup</strong> — always runs before any restore.</li>
</ul>
<h3>Storage</h3>
<p>Backups are stored as <code>backups/YYYY-MM-DD_HHMM_auto.zip</code> or <code>_manual.zip</code>.
The destination folder is configurable. Retention keeps the last N backups (default: 10).</p>
<h3>Restore</h3>
<ol>
  <li>Settings → Restore… → select a backup.</li>
  <li>Click Preview to see the contents before restoring.</li>
  <li>Click Restore — a pre-restore backup is created, then the files are extracted.</li>
  <li>Restart the app to apply all changes.</li>
</ol>
""",
    "api_reference": """
<h2>API Reference</h2>
<p>The REST API runs at <code>http://127.0.0.1:8080</code>. No authentication (localhost only).
All requests and responses use JSON.</p>
<h3>Endpoints</h3>
<table>
  <tr><th>Method</th><th>Path</th><th>Description</th></tr>
  <tr><td>GET</td><td>/api/v1/status</td><td>App status and counts</td></tr>
  <tr><td>GET/POST/PUT/DELETE</td><td>/api/v1/workflows</td><td>Workflow CRUD</td></tr>
  <tr><td>POST</td><td>/api/v1/workflows/{id}/run</td><td>Run a workflow</td></tr>
  <tr><td>POST</td><td>/api/v1/workflows/{id}/stop</td><td>Stop a workflow</td></tr>
  <tr><td>GET</td><td>/api/v1/workflows/{id}/status</td><td>Running status</td></tr>
  <tr><td>GET</td><td>/api/v1/workflows/{id}/versions</td><td>Version history</td></tr>
  <tr><td>GET/POST/PUT/DELETE</td><td>/api/v1/variables</td><td>Variable CRUD</td></tr>
  <tr><td>GET/POST/PUT/DELETE</td><td>/api/v1/triggers</td><td>Trigger CRUD</td></tr>
  <tr><td>POST</td><td>/api/v1/triggers/{id}/enable</td><td>Enable trigger</td></tr>
  <tr><td>POST</td><td>/api/v1/triggers/{id}/disable</td><td>Disable trigger</td></tr>
  <tr><td>GET/POST/PUT/DELETE</td><td>/api/v1/steps</td><td>Step library CRUD</td></tr>
  <tr><td>GET/POST/PUT</td><td>/api/v1/email/templates</td><td>Email template CRUD</td></tr>
  <tr><td>POST</td><td>/api/v1/email/send</td><td>Send email from template</td></tr>
  <tr><td>GET</td><td>/api/v1/export</td><td>Download full bundle</td></tr>
  <tr><td>POST</td><td>/api/v1/import</td><td>Import a bundle file</td></tr>
  <tr><td>GET</td><td>/api/v1/logs/workflows</td><td>Recent workflow logs</td></tr>
  <tr><td>GET</td><td>/api/v1/logs/triggers</td><td>Recent trigger logs</td></tr>
  <tr><td>GET</td><td>/api/v1/logs/email</td><td>Recent email logs</td></tr>
  <tr><td>POST</td><td>/api/v1/backup</td><td>Trigger a manual backup</td></tr>
  <tr><td>GET</td><td>/api/v1/guide</td><td>Full API schema as JSON</td></tr>
</table>
<h3>WebSocket</h3>
<p>Connect to <code>ws://127.0.0.1:8080/ws/status</code> for a live event stream.</p>
<p>Event types: <code>step_started</code>, <code>step_completed</code>, <code>branch_taken</code>,
<code>variable_changed</code>, <code>loop_iteration</code>, <code>workflow_complete</code>,
<code>workflow_error</code>.</p>
<p>Each event includes: <code>type</code>, <code>data</code>, <code>time</code>.</p>
""",
    "keyboard_shortcuts": """
<h2>Keyboard Shortcuts</h2>
<table>
  <tr><th>Shortcut</th><th>Action</th></tr>
  <tr><td>Ctrl+Alt+Num1</td><td>Show / hide app window</td></tr>
  <tr><td>Ctrl+Alt+Num2</td><td>Start / stop macro recording</td></tr>
  <tr><td>Ctrl+Alt+Pause</td><td>Pause AHK execution</td></tr>
  <tr><td>Ctrl+Alt+Esc</td><td>Stop AHK execution</td></tr>
  <tr><td>Ctrl+Alt+V</td><td>Open Variable Library overlay</td></tr>
  <tr><td>? (in app)</td><td>Open help panel</td></tr>
  <tr><td>A (on canvas)</td><td>Toggle annotation visibility</td></tr>
  <tr><td>Ctrl+S (on canvas)</td><td>Save workflow</td></tr>
  <tr><td>Ctrl+Z (on canvas)</td><td>Undo canvas action</td></tr>
</table>
""",
}


def generate(dest: str | None = None) -> str:
    dest = dest or str(path("docs/user_guide.html"))

    nav_links = "\n".join(
        f'<li><a href="#{slug}">{title}</a></li>'
        for slug, title in CHAPTERS
    )
    chapters_html = "\n".join(
        f'<section id="{slug}">{CONTENT.get(slug, "")}</section>'
        for slug, _ in CHAPTERS
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AHK-Python Automation — User Guide</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Segoe UI, sans-serif; background: #1a1a2e; color: #e0e0e0;
          display: flex; min-height: 100vh; }}
  nav {{ width: 220px; background: #16213e; padding: 24px 12px; position: sticky;
         top: 0; height: 100vh; overflow-y: auto; flex-shrink: 0; }}
  nav h2 {{ color: #90CAF9; font-size: 13px; text-transform: uppercase;
             letter-spacing: 1px; margin-bottom: 12px; }}
  nav ul {{ list-style: none; }}
  nav li {{ margin: 4px 0; }}
  nav a {{ color: #90CAF9; text-decoration: none; font-size: 14px;
            display: block; padding: 4px 8px; border-radius: 4px; }}
  nav a:hover {{ background: #0f3460; }}
  main {{ flex: 1; padding: 32px 40px; max-width: 900px; }}
  h2 {{ color: #90CAF9; font-size: 22px; margin: 32px 0 12px; border-bottom: 1px solid #333; padding-bottom: 6px; }}
  h3 {{ color: #64B5F6; font-size: 16px; margin: 20px 0 8px; }}
  p  {{ line-height: 1.7; margin-bottom: 10px; }}
  ul, ol {{ margin: 8px 0 12px 24px; line-height: 1.7; }}
  li {{ margin-bottom: 4px; }}
  code, kbd {{ background: #0d1b2a; border: 1px solid #333; border-radius: 3px;
               padding: 1px 5px; font-family: Consolas, monospace; font-size: 13px; color: #80CBC4; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ border: 1px solid #333; padding: 8px 12px; text-align: left; font-size: 14px; }}
  th {{ background: #0f3460; color: #90CAF9; }}
  tr:nth-child(even) {{ background: #16213e; }}
  section {{ margin-bottom: 48px; }}
  input#search {{ width: 100%; padding: 6px 10px; margin-bottom: 12px;
                  background: #0d1b2a; border: 1px solid #333; color: #e0e0e0;
                  border-radius: 4px; font-size: 13px; }}
</style>
</head>
<body>
<nav>
  <h2>AHK Automation</h2>
  <input id="search" placeholder="Search…" oninput="filterNav(this.value)">
  <ul id="nav-list">
    {nav_links}
  </ul>
</nav>
<main>
  {chapters_html}
</main>
<script>
function filterNav(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('#nav-list li').forEach(li => {{
    li.style.display = li.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
  if (!q) return;
  document.querySelectorAll('main section').forEach(sec => {{
    sec.style.display = sec.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    import os
    os.makedirs(str(path("docs")), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(html)
    return dest
