#!/usr/bin/env bash
# ==============================================================================
# MP_Audio_Player.sh - Shell Launcher for MP Audio Player
# Part of MP_Mix_Manager_v0.4
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="python3"

if [ -f "$SCRIPT_DIR/scripts/resolve_mp_python.sh" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/scripts/resolve_mp_python.sh"
    PY="$(mp_python_bin 2>/dev/null || echo python3)"
fi

# Find and Execute
for f in "$SCRIPT_DIR/MP_Audio_Player.py" "$SCRIPT_DIR/scripts/MP_Audio_Player.py"; do
    if [ -f "$f" ]; then
        exec "$PY" "$f" "$@"
    fi
done

echo "Error: MP_Audio_Player.py not found!" >&2
exit 1
