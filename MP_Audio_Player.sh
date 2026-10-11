#!/usr/bin/env bash
# ==============================================================================
# MP_Audio_Player.sh - Shell Launcher for MP Audio Player
# Part of MP_Mix_Manager_v0.3
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="python3"
if [[ "$(uname -s)" =~ (MINGW|MSYS|CYGWIN) ]]; then
    if command -v py >/dev/null 2>&1 && py -3 --version >/dev/null 2>&1; then
        PYTHON_EXEC="py -3"
    elif [ -x "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312/python.exe" ]; then
        PYTHON_EXEC="/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312/python.exe"
    elif command -v python >/dev/null 2>&1 && [[ ! "$(type -p python)" =~ WindowsApps ]]; then
        PYTHON_EXEC="python"
    fi
fi

if [ -f "$SCRIPT_DIR/MP_Audio_Player.py" ]; then
    exec $PYTHON_EXEC "$SCRIPT_DIR/MP_Audio_Player.py" "$@"
elif [ -f "$SCRIPT_DIR/scripts/MP_Audio_Player.py" ]; then
    exec $PYTHON_EXEC "$SCRIPT_DIR/scripts/MP_Audio_Player.py" "$@"
else
    echo "Error: MP_Audio_Player.py not found!" >&2
    exit 1
fi
