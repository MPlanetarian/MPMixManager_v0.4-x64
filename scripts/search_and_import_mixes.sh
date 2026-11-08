#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Universal Mix Search & Importer Shell Wrapper
# Optimized launch environment & binary validation
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANDIDATES=(
    "$SCRIPT_DIR/search_and_import_mixes.py"
    "$SCRIPT_DIR/scripts/search_and_import_mixes.py"
    "$(dirname "$SCRIPT_DIR")/scripts/search_and_import_mixes.py"
)

PY_SCRIPT=""
for candidate in "${CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
        PY_SCRIPT="$candidate"
        break
    fi
done

if [ -z "$PY_SCRIPT" ]; then
    echo -e "\033[0;31mError: search_and_import_mixes.py not found in candidate paths!\033[0m" >&2
    exit 1
fi

# Ensure Python unbuffered I/O is enabled so interactive progress bars don't stutter
export PYTHONUNBUFFERED=1

# Maximize file descriptor limits for heavy concurrent multi-file SMB reads
ulimit -n 4096 2>/dev/null || true

exec python3 "$PY_SCRIPT" "$@"