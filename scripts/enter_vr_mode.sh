#!/usr/bin/env bash
# Desktop shortcut: MP Liquid Player VR Mode (Bigscreen).
# Refuses on every platform except Microsoft Windows with Bigscreen installed.

_RESOLVED_SRC="${BASH_SOURCE[0]}"
while [ -h "$_RESOLVED_SRC" ]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
    _RESOLVED_SRC="$(readlink "$_RESOLVED_SRC")"
    [[ $_RESOLVED_SRC != /* ]] && _RESOLVED_SRC="$_RESOLVED_DIR/$_RESOLVED_SRC"
done
SCRIPT_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
unset _RESOLVED_SRC _RESOLVED_DIR

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "VR Mode refused to load."
    echo "You must be on Microsoft Windows and have Bigscreen VR installed already."
    read -r -p "Press Enter to close..." _
    exit 1
fi

"$PYTHON_BIN" "$SCRIPT_DIR/bigscreen_vr.py" --root "$BASE_DIR"
status=$?
if [ "$status" -ne 0 ]; then
    echo
    read -r -p "Press Enter to close..." _
fi
exit "$status"
