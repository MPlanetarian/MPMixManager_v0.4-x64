#!/usr/bin/env bash
# ==============================================================================
# Traktor Kontrol S4 Hardware MIDI Controller Support Script
# MP Mix Archive Manager v0.4.0 Stable
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

PYTHON_SCRIPT="$SCRIPT_DIR/traktor_s4_midi.py"
[ ! -f "$PYTHON_SCRIPT" ] && PYTHON_SCRIPT="$PROJECT_ROOT/scripts/traktor_s4_midi.py"
[ ! -f "$PYTHON_SCRIPT" ] && PYTHON_SCRIPT="$PROJECT_ROOT/traktor_s4_midi.py"

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: traktor_s4_midi.py not found!" >&2
    exit 1
fi

python3 "$PYTHON_SCRIPT" "$@"
