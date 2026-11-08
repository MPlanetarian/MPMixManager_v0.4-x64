#!/usr/bin/env bash
# Focus an existing MP Gui liquid-glass window.
# A --manager process is not enough: the macOS Metal host never maps a window,
# and this Mac has no wmctrl. Missing wmctrl must not count as "already open".

_mp_gui_activate_macos_pid() {
    local pid="$1"
    [ -n "$pid" ] || return 1
    [ "$(uname -s)" = "Darwin" ] || return 1
    python3 - "$pid" <<'PY' || return 1
import ctypes
import sys

pid = int(sys.argv[1])
try:
    objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
    ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
except OSError:
    sys.exit(1)
objc.objc_getClass.restype = ctypes.c_void_p
objc.objc_getClass.argtypes = [ctypes.c_char_p]
objc.sel_registerName.restype = ctypes.c_void_p
objc.sel_registerName.argtypes = [ctypes.c_char_p]
send = objc.objc_msgSend
cls = objc.objc_getClass(b"NSRunningApplication")
sel_pid = objc.sel_registerName(b"runningApplicationWithProcessIdentifier:")
sel_act = objc.sel_registerName(b"activateWithOptions:")
send.restype = ctypes.c_void_p
send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
app = send(cls, sel_pid, pid)
if not app:
    sys.exit(1)
# NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps
send.restype = ctypes.c_bool
send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulonglong]
ok = send(app, sel_act, 3)
sys.exit(0 if ok else 1)
PY
}

# Prints pgrep -fl lines for a Liquid Glass host started with --manager.
_mp_gui_manager_processes() {
    pgrep -fl 'MP_Audio_Player_Liquid_Glas[s].*--manager' 2>/dev/null || true
}

# Windowed hosts draw the manager. The Metal macOS file does not.
_mp_gui_line_is_windowed_host() {
    local cmd="$1"
    case "$cmd" in
        *MP_Audio_Player_Liquid_Glass_OpenGL*|*MP_Audio_Player_Liquid_Glass.py*)
            return 0
            ;;
    esac
    return 1
}

# Returns 0 when a glass window is up (and focused, when the OS allows it).
mp_gui_focus_if_open() {
    if command -v wmctrl >/dev/null 2>&1; then
        if wmctrl -l 2>/dev/null | grep -q "MP Mix Manager (Liquid Glass"; then
            wmctrl -a "MP Mix Manager (Liquid Glass" 2>/dev/null || true
            return 0
        fi
    fi
    local line pid cmd
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        pid="${line%% *}"
        cmd="${line#* }"
        if _mp_gui_line_is_windowed_host "$cmd"; then
            _mp_gui_activate_macos_pid "$pid" || true
            return 0
        fi
    done < <(_mp_gui_manager_processes)
    return 1
}

# Stop a leftover Metal --manager. It keeps G from opening a window and
# never maps one of its own. Windowed hosts are left alone.
mp_gui_stop_windowless_hosts() {
    local line pid cmd
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        pid="${line%% *}"
        cmd="${line#* }"
        case "$cmd" in
            *MP_Audio_Player_Liquid_Glass_OpenGL*|*MP_Audio_Player_Liquid_Glass.py*)
                continue
                ;;
            *MP_Audio_Player_Liquid_Glass_macOS.py*)
                pkill -TERM -P "$pid" 2>/dev/null || true
                kill "$pid" 2>/dev/null || true
                ;;
        esac
    done < <(_mp_gui_manager_processes)
}
