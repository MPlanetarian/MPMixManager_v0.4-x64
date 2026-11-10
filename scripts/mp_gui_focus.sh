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

# Prints "pid command" lines for every Liquid Glass host.
# macOS pgrep -a lists ancestors and prints only the pid, so --manager is
# invisible. Linux pgrep -l omits arguments, so --manager needs -a there.
_mp_glass_process_lines() {
    if [ "$(uname -s)" = "Darwin" ]; then
        pgrep -fl 'MP_Audio_Player_Liquid_Glas[s]' 2>/dev/null || true
    else
        pgrep -af 'MP_Audio_Player_Liquid_Glas[s]' 2>/dev/null || true
    fi
}

# Prints pgrep lines for a Liquid Glass host started with --manager.
_mp_gui_manager_processes() {
    local line
    while IFS= read -r line; do
        case "$line" in
            *--manager*) printf '%s\n' "$line" ;;
        esac
    done < <(_mp_glass_process_lines)
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

# Bring the Liquid Player forward. Skips the --manager GUI.
# Returns 0 when a player host is running. On macOS the activate call has
# to come from this shell: the player's own AppKit call stays behind a
# fullscreen Terminal, and this Mac has no wmctrl.
mp_player_raise_host() {
    local line pid cmd
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        case "$line" in
            *--manager*) continue ;;
        esac
        pid="${line%% *}"
        cmd="${line#* }"
        if _mp_gui_line_is_windowed_host "$cmd"; then
            _mp_gui_activate_macos_pid "$pid" || true
            return 0
        fi
    done < <(_mp_glass_process_lines)
    return 1
}

# Bring a windowed --manager host forward. Returns 0 when one is running.
# Activation comes from this shell: the host's own AppKit call does not
# beat a fullscreen Terminal.
mp_gui_raise_host() {
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

# Move an already-open manager onto the primary display, then focus it.
_mp_gui_place_on_primary() {
    local here
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    [ -f "$here/desktop_launch_screen.py" ] || return 0
    python3 - "$here" << 'PY' || true
import sys
sys.path.insert(0, sys.argv[1])
from desktop_launch_screen import ensure_on_main_screen
ensure_on_main_screen("MP Mix Manager (Liquid Glass")
PY
}

# Returns 0 when a glass window is up (and focused, when the OS allows it).
mp_gui_focus_if_open() {
    if command -v wmctrl >/dev/null 2>&1; then
        if wmctrl -l 2>/dev/null | grep -q "MP Mix Manager (Liquid Glass"; then
            _mp_gui_place_on_primary
            wmctrl -a "MP Mix Manager (Liquid Glass" 2>/dev/null || true
            return 0
        fi
    fi
    mp_gui_raise_host
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
