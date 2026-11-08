#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Standard CUE Sheet Generator & Splitter Wrapper
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/generate_cue_sheet.py"

if [ ! -f "$PY_SCRIPT" ]; then
    PY_SCRIPT="$SCRIPT_DIR/scripts/generate_cue_sheet.py"
fi

if [ ! -f "$PY_SCRIPT" ]; then
    echo "Error: generate_cue_sheet.py not found."
    exit 1
fi

exec python3 "$PY_SCRIPT" "$@"