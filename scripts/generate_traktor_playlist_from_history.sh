#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Traktor Pro History Playlist Generator
# Exclusively supported on macOS.
# ==============================================================================

set -eo pipefail 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PYTHON_CMD=$(command -v python3 || command -v python || echo "/usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3" | tr ' ' '\n' | head -n1)

GEN_PY="$SCRIPT_DIR/generate_traktor_playlist_from_history.py"
if [ ! -f "$GEN_PY" ]; then
    for dir in "$SCRIPT_DIR/scripts" "$PWD/scripts" "$PWD"; do
        if [ -f "$dir/generate_traktor_playlist_from_history.py" ]; then
            GEN_PY="$dir/generate_traktor_playlist_from_history.py"
            break
        fi
    done
fi

if [ ! -f "$GEN_PY" ]; then
    echo "Error: generate_traktor_playlist_from_history.py not found in $SCRIPT_DIR or subdirectories." >&2
    exit 1
fi

exec "$PYTHON_CMD" "$GEN_PY" "$@" # 50 to 27