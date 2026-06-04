"""Named pipe bridge between Python and AHK.

Python is the pipe CLIENT — AHK creates the server side.
Protocol:
  Python → AHK:  EXECUTE <path>  |  EXECUTE_INLINE <code>  |  PAUSE  |  STOP
                 TOGGLE_GUI  |  START_RECORDING  |  VARIABLE_LIBRARY
  AHK → Python:  STATUS:started  |  STATUS:success  |  STATUS:error:<msg>
                 OUTPUT:<var>=<value>
"""

from __future__ import annotations

import threading
import time
from typing import Callable

try:
    import win32file
    import win32pipe
    import pywintypes
    _WIN32 = True
except ImportError:
    _WIN32 = False

PIPE_NAME = r"\\.\pipe\AHKPythonBridge"
DEFAULT_TIMEOUT = 10  # seconds


class AHKBridge:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._handle = None
        self._lock = threading.Lock()
        self._listeners: list[Callable[[str], None]] = []

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        if not _WIN32:
            return False
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                self._handle = win32file.CreateFile(
                    PIPE_NAME,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0, None,
                    win32file.OPEN_EXISTING,
                    0, None
                )
                win32pipe.SetNamedPipeHandleState(
                    self._handle,
                    win32pipe.PIPE_READMODE_MESSAGE,
                    None, None
                )
                threading.Thread(target=self._read_loop, daemon=True).start()
                return True
            except pywintypes.error:
                time.sleep(0.5)
        return False

    def disconnect(self):
        if self._handle:
            try:
                win32file.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None

    @property
    def connected(self) -> bool:
        return self._handle is not None

    # ── Send ──────────────────────────────────────────────────────────────────

    def send(self, message: str) -> bool:
        if not self.connected:
            return False
        with self._lock:
            try:
                win32file.WriteFile(self._handle, (message + "\n").encode("utf-8"))
                return True
            except Exception:
                self._handle = None
                return False

    def execute_file(self, path: str) -> bool:
        return self.send(f"EXECUTE {path}")

    def execute_inline(self, code: str) -> bool:
        return self.send(f"EXECUTE_INLINE {code}")

    def pause(self) -> bool:
        return self.send("PAUSE")

    def stop(self) -> bool:
        return self.send("STOP")

    def toggle_gui(self) -> bool:
        return self.send("TOGGLE_GUI")

    def start_recording(self) -> bool:
        return self.send("START_RECORDING")

    def variable_library(self) -> bool:
        return self.send("VARIABLE_LIBRARY")

    # ── Receive ───────────────────────────────────────────────────────────────

    def on_message(self, fn: Callable[[str], None]):
        self._listeners.append(fn)

    def _read_loop(self):
        while self.connected:
            try:
                _, data = win32file.ReadFile(self._handle, 65536)
                msg = data.decode("utf-8").strip()
                if msg:
                    for fn in self._listeners:
                        fn(msg)
            except Exception:
                self._handle = None
                break


# Module-level singleton
_bridge: AHKBridge | None = None


def get_bridge() -> AHKBridge:
    global _bridge
    if _bridge is None:
        _bridge = AHKBridge()
    return _bridge
