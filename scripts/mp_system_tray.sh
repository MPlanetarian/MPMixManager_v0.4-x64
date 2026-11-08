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

PY="$SCRIPT_DIR/mp_system_tray.py"
if [ ! -f "$PY" ]; then
    echo "mp_system_tray.py was not found beside this script." >&2
    exit 1
fi

if [ "${1:-}" = "--status" ]; then
    exec python3 "$PY" --status
fi

if ! python3 -c "import PySide6.QtWidgets" >/dev/null 2>&1; then
    exit 0
fi

CONFIG_DIR="${MP_TRAY_CONFIG_DIR:-${HOME}/.config/mix-manager}"
mkdir -p "$CONFIG_DIR" 2>/dev/null || true
LOG_FILE="$CONFIG_DIR/mp_system_tray.log"

if [ "${1:-}" = "--ensure" ]; then
    if python3 "$PY" --status >/dev/null 2>&1; then
        exit 0
    fi
    export QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-kde}"
    if command -v setsid >/dev/null 2>&1; then
        setsid python3 "$PY" >>"$LOG_FILE" 2>&1 </dev/null &
    else
        nohup python3 "$PY" >>"$LOG_FILE" 2>&1 </dev/null &
    fi
    exit 0
fi

export QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-kde}"
exec python3 "$PY" "$@"
