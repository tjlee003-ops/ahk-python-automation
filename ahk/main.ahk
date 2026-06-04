; main.ahk — entry point, global hotkeys, app launcher
#SingleInstance Force
#Persistent
SetWorkingDir %A_ScriptDir%\..

; ── Named pipe handles ──────────────────────────────────────────────────────
global PipeName := "\\.\pipe\AHKPythonBridge"
global PipeHandle := 0
global PythonPID := 0

; ── Startup ─────────────────────────────────────────────────────────────────
OnExit("Cleanup")
SetTimer, ConnectPipe, -500   ; try to connect shortly after launch

; ── Global hotkeys ──────────────────────────────────────────────────────────

; Show / hide Python GUI
^!Numpad1::
    if (PythonPID = 0)
        LaunchPython()
    else
        PipeSend("TOGGLE_GUI")
return

; Start macro recording
^!Numpad2::
    PipeSend("START_RECORDING")
    TrayTip, AHK Automation, Recording started — press Ctrl+Alt+Num2 again to stop., 2
return

; Pause active execution
^!Pause::
    PipeSend("PAUSE")
return

; Stop / cancel active execution
^!Escape::
    PipeSend("STOP")
return

; Open Variable Library overlay
^!v::
    PipeSend("VARIABLE_LIBRARY")
return

; ── Functions ───────────────────────────────────────────────────────────────

LaunchPython() {
    global PythonPID
    pythonExe := "pythonw.exe"
    scriptPath := A_ScriptDir . "\..\python\main.py"
    Run, %pythonExe% "%scriptPath%",, Hide, pid
    PythonPID := pid
    SetTimer, ConnectPipe, -2000   ; give Python time to start
}

ConnectPipe() {
    global PipeHandle, PipeName
    if (PipeHandle != 0)
        return
    PipeHandle := DllCall("CreateFile"
        , "Str",  PipeName
        , "UInt", 0xC0000000   ; GENERIC_READ | GENERIC_WRITE
        , "UInt", 0
        , "Ptr",  0
        , "UInt", 3            ; OPEN_EXISTING
        , "UInt", 0
        , "Ptr",  0
        , "Ptr")
    if (PipeHandle = -1 || PipeHandle = 0) {
        PipeHandle := 0
        SetTimer, ConnectPipe, -3000   ; retry
    }
}

PipeSend(msg) {
    global PipeHandle
    if (PipeHandle = 0) {
        MsgBox, 48, AHK Bridge, Pipe not connected. Is Python running?
        return
    }
    bytes := StrPut(msg . "`n", "UTF-8") - 1
    VarSetCapacity(buf, bytes)
    StrPut(msg . "`n", &buf, bytes, "UTF-8")
    DllCall("WriteFile"
        , "Ptr",  PipeHandle
        , "Ptr",  &buf
        , "UInt", bytes
        , "Ptr",  0
        , "Ptr",  0)
}

PipeRead(ByRef out) {
    global PipeHandle
    VarSetCapacity(buf, 4096, 0)
    bytesRead := 0
    ok := DllCall("ReadFile"
        , "Ptr",  PipeHandle
        , "Ptr",  &buf
        , "UInt", 4095
        , "UIntP", bytesRead
        , "Ptr",  0)
    if (ok && bytesRead > 0)
        out := StrGet(&buf, bytesRead, "UTF-8")
    else
        out := ""
}

Cleanup() {
    global PipeHandle
    if (PipeHandle != 0)
        DllCall("CloseHandle", "Ptr", PipeHandle)
}

; ── Include execution engine ─────────────────────────────────────────────────
#Include %A_ScriptDir%\executor.ahk
