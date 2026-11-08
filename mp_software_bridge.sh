#!/usr/bin/env bash
# =============================================================================
#  MP Software Bridge - CLI Wrapper
#  Connects MP Mix Manager & Congen with real-time telemetry & IPC validation
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PYTHON_BIN="$(type -p python3 || type -p python || true)"

if [[ -z "$PYTHON_BIN" ]]; then
    echo "Error: Python 3 is required for MP Software Bridge." >&2
    exit 1
fi

BRIDGE_PY="$SCRIPT_DIR/scripts/mp_software_bridge.py"
if [[ ! -f "$BRIDGE_PY" && -f "$SCRIPT_DIR/../scripts/mp_software_bridge.py" ]]; then
    BRIDGE_PY="$SCRIPT_DIR/../scripts/mp_software_bridge.py"
fi

if [[ ! -f "$BRIDGE_PY" ]]; then
    echo "Error: mp_software_bridge.py not found at $BRIDGE_PY" >&2
    exit 1
fi

exec "$PYTHON_BIN" "$BRIDGE_PY" "$@"
