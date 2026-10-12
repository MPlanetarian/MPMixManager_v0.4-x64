#!/usr/bin/env bash
# ==============================================================================
# MP_Audio_Player.sh - Shell Launcher for MP Audio Player
# Part of MP_Mix_Manager_v0.3
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="python3"

# Windows/Git Bash Python Detection
if [[ "$(uname -s)" =~ (MINGW|MSYS|CYGWIN) ]]; then
    if command -v py &>/dev/null && py -3 --version &>/dev/null; then
        PY="py -3"
    elif [ -x "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312/python.exe" ]; then
        PY="/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312/python.exe"
    elif command -v python &>/dev/null && [[ ! "$(type -p python)" =~ WindowsApps ]]; then
        PY="python"
    fi
fi

# Find and Execute
for f in "$SCRIPT_DIR/MP_Audio_Player.py" "$SCRIPT_DIR/scripts/MP_Audio_Player.py"; do
    if [ -f "$f" ]; then
        exec $PY "$f" "$@"
    fi
done

echo "Error: MP_Audio_Player.py not found!" >&2
exit 1
