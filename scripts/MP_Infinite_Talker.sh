#!/usr/bin/env bash
# Wrapper for MP_Infinite_Talker.py
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/MP_Infinite_Talker.py" "$@"
