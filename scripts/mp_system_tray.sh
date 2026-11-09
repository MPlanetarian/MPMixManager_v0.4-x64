#!/usr/bin/env bash
# Shared system tray for MP Mix Manager, MP Gui, and MP Liquid Player.
# --ensure   start the tray in the background when it is not already running
# --status   exit 0 when the tray is running
# --stay     keep the icon up even if none of the three apps is open

_RESOLVED_SRC="${BASH_SOURCE[0]}"
while [ -h "$_RESOLVED_SRC" ]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
    _RESOLVED_SRC="$(readlink "$_RESOLVED_SRC")"
    [[ $_RESOLVED_SRC != /* ]] && _RESOLVED_SRC="$_RESOLVED_DIR/$_RESOLVED_SRC"
done
SCRIPT_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
unset _RESOLVED_SRC _RESOLVED_DIR

_is_windows_host() {
    case "$(uname -s)" in
        CYGWIN*|MINGW*|MSYS*) return 0 ;;
    esac
    if [ -r /proc/version ] && grep -qi microsoft /proc/version 2>/dev/null; then
        return 0
    fi
    return 1
}

_is_darwin_host() {
    [ "$(uname -s)" = "Darwin" ]
}

# Windows 10/11 has no StatusNotifier host. The notification icon and the
# per-user shortcuts are created by PowerShell, including when python3 is only
# the Microsoft Store alias.
if _is_windows_host; then
    ROOT_DIR="$(cd -P "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
    HELPER="$SCRIPT_DIR/install_windows_user.sh"
    if [ ! -f "$HELPER" ]; then
        echo "install_windows_user.sh was not found beside this script." >&2
        exit 1
    fi
    case "${1:-}" in
        --status)
            exec bash "$HELPER" "$ROOT_DIR" --status
            ;;
        --install)
            exec bash "$HELPER" "$ROOT_DIR"
            ;;
        --ensure)
            exec bash "$HELPER" "$ROOT_DIR" --ensure-tray
            ;;
        --stay)
            exec bash "$HELPER" "$ROOT_DIR" --tray-foreground --stay
            ;;
        *)
            exec bash "$HELPER" "$ROOT_DIR" --tray-foreground
            ;;
    esac
fi

PY="$SCRIPT_DIR/mp_system_tray.py"
if [ ! -f "$PY" ]; then
    echo "mp_system_tray.py was not found beside this script." >&2
    exit 1
fi

if [ "${1:-}" = "--status" ]; then
    exec python3 "$PY" --status
fi

# macOS uses an AppKit menu-bar icon. PySide6 and the KDE theme are not used.
if ! _is_darwin_host && ! python3 -c "import PySide6.QtWidgets" >/dev/null 2>&1; then
    exit 0
fi

CONFIG_DIR="${MP_TRAY_CONFIG_DIR:-${HOME}/.config/mix-manager}"
mkdir -p "$CONFIG_DIR" 2>/dev/null || true
LOG_FILE="$CONFIG_DIR/mp_system_tray.log"

if [ "${1:-}" = "--ensure" ]; then
    shift
    if python3 "$PY" --status >/dev/null 2>&1; then
        exit 0
    fi
    if ! _is_darwin_host; then
        export QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-kde}"
    fi
    if command -v setsid >/dev/null 2>&1; then
        setsid python3 "$PY" "$@" >>"$LOG_FILE" 2>&1 </dev/null &
    else
        nohup python3 "$PY" "$@" >>"$LOG_FILE" 2>&1 </dev/null &
    fi
    exit 0
fi

if ! _is_darwin_host; then
    export QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-kde}"
fi
exec python3 "$PY" "$@"
