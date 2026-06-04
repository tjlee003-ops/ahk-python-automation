; executor.ahk — AHK execution engine
; Receives EXECUTE / PAUSE / STOP commands via named pipe and runs steps.

global ExecPaused := false
global ExecStopped := false

; ── Pipe server (Python connects as client) ──────────────────────────────────
; The pipe is created here so Python can write to it before AHK reads.

CreatePipeServer() {
    global PipeName, PipeHandle
    PipeHandle := DllCall("CreateNamedPipe"
        , "Str",  PipeName
        , "UInt", 3           ; PIPE_ACCESS_DUPLEX
        , "UInt", 4           ; PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE
        , "UInt", 1           ; max instances
        , "UInt", 65536       ; out buffer
        , "UInt", 65536       ; in buffer
        , "UInt", 0           ; default timeout
        , "Ptr",  0
        , "Ptr")
    if (PipeHandle = -1 || PipeHandle = 0) {
        PipeHandle := 0
        return false
    }
    ; Wait for client (non-blocking via timer)
    SetTimer, WaitForClient, 500
    return true
}

WaitForClient() {
    global PipeHandle
    connected := DllCall("ConnectNamedPipe", "Ptr", PipeHandle, "Ptr", 0)
    if (connected || A_LastError = 535) {   ; 535 = ERROR_PIPE_CONNECTED
        SetTimer, WaitForClient, Off
        SetTimer, PipeReadLoop, 100
    }
}

PipeReadLoop() {
    global PipeHandle, ExecPaused, ExecStopped
    VarSetCapacity(buf, 65536, 0)
    bytesRead := 0
    ok := DllCall("ReadFile"
        , "Ptr",  PipeHandle
        , "Ptr",  &buf
        , "UInt", 65535
        , "UIntP", bytesRead
        , "Ptr",  0)
    if (!ok || bytesRead = 0)
        return
    msg := StrGet(&buf, bytesRead, "UTF-8")
    StringUpper, msgUpper, msg
    if (InStr(msgUpper, "EXECUTE"))
        ExecuteStep(msg)
    else if (InStr(msgUpper, "PAUSE"))
        ExecPaused := !ExecPaused
    else if (InStr(msgUpper, "STOP")) {
        ExecStopped := true
        ExecPaused := false
        Send {Blind}{Ctrl Up}{Alt Up}{Shift Up}   ; release any held modifiers
    }
}

; ── Step execution ───────────────────────────────────────────────────────────

ExecuteStep(msg) {
    global ExecPaused, ExecStopped
    ExecStopped := false

    ; Parse: "EXECUTE <script_path>" or "EXECUTE_INLINE <ahk_code>"
    if (RegExMatch(msg, "EXECUTE_INLINE\s+(.+)", m)) {
        RunAHKInline(m1)
    } else if (RegExMatch(msg, "EXECUTE\s+(.+)", m)) {
        scriptPath := Trim(m1)
        if FileExist(scriptPath)
            RunAHKFile(scriptPath)
        else
            PipeSend("STATUS:error:File not found: " . scriptPath)
    }
}

RunAHKFile(path) {
    PipeSend("STATUS:started")
    Run, % A_AhkPath . " """ . path . """",, Hide
    PipeSend("STATUS:success")
}

RunAHKInline(code) {
    ; Write to temp file then execute
    tmpFile := A_Temp . "\ahk_step_" . A_TickCount . ".ahk"
    FileAppend, %code%, %tmpFile%, UTF-8
    PipeSend("STATUS:started")
    RunWait, % A_AhkPath . " """ . tmpFile . """",, Hide
    FileDelete, %tmpFile%
    PipeSend("STATUS:success")
}

; ── Tray icon ────────────────────────────────────────────────────────────────

SetTrayIcon("idle")

SetTrayIcon(state) {
    if (state = "recording")
        Menu, Tray, Icon, shell32.dll, 132   ; red-ish dot
    else if (state = "executing")
        Menu, Tray, Icon, shell32.dll, 238   ; green arrow
    else
        Menu, Tray, Icon, shell32.dll, 15    ; grey cog (idle)
}

Menu, Tray, NoStandard
Menu, Tray, Add, Show App,      TrayShowApp
Menu, Tray, Add, Start Recording, TrayStartRec
Menu, Tray, Add, Stop AHK,      TrayStopAHK
Menu, Tray, Add,                ; separator
Menu, Tray, Add, Exit,          TrayExit

TrayShowApp:
    PipeSend("TOGGLE_GUI")
return
TrayStartRec:
    PipeSend("START_RECORDING")
return
TrayStopAHK:
    PipeSend("STOP")
return
TrayExit:
    ExitApp
return
