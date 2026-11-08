#!/bin/bash
# scripts/monitor_bluetooth_audio.sh - Launcher for MP Mix Manager Bluetooth Audio Monitor
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PY_SCRIPT=""
for candidate in \
    "$SCRIPT_DIR/monitor_bluetooth_audio.py" \
    "$SCRIPT_DIR/scripts/monitor_bluetooth_audio.py" \
    "$PARENT_DIR/scripts/monitor_bluetooth_audio.py" \
    "$PARENT_DIR/monitor_bluetooth_audio.py"; do
    if [ -f "$candidate" ]; then
        PY_SCRIPT="$candidate"
        break
    fi
done

if [ -n "$PY_SCRIPT" ] && [ -f "$PY_SCRIPT" ]; then
    exec python3 "$PY_SCRIPT" "$@"
else
    echo "Error: monitor_bluetooth_audio.py not found!" >&2
    exit 1
fi
