#!/usr/bin/env bash
# ==============================================================================
# MP_Liquid_Visualizer — Native Vulkan borderless 3D visualizer (1094x734 on macOS, the Liquid Player size on Linux, 700x700 elsewhere)
# Cross-Platform: macOS (MoltenVK) / Windows 10 & 11 / Linux
# ==============================================================================
set -euo pipefail

# Ensure Homebrew and standard paths are present on macOS
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN=""
# Prefer an interpreter that can import the visualizer's dependencies.
# Homebrew's python3 comes first on PATH but is not the system GTK python.
_resolver="${SCRIPT_DIR}/resolve_mp_python.sh"
[ ! -f "$_resolver" ] && _resolver="${PROJECT_ROOT}/scripts/resolve_mp_python.sh"
if [ -f "$_resolver" ]; then
    # shellcheck disable=SC1090
    source "$_resolver"
    PYTHON_BIN="$(mp_visualizer_python_bin 2>/dev/null || true)"
fi
unset _resolver
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        echo "Error: Python 3 not found in PATH." >&2
        exit 1
    fi
fi

if [[ -f "${PROJECT_ROOT}/MP_Liquid_Visualizer.py" ]]; then
    exec "$PYTHON_BIN" "${PROJECT_ROOT}/MP_Liquid_Visualizer.py" "$@"
elif [[ -f "${SCRIPT_DIR}/mp_liquid_visualizer_vulkan.py" ]]; then
    exec "$PYTHON_BIN" "${SCRIPT_DIR}/mp_liquid_visualizer_vulkan.py" "$@"
else
    echo "Error: MP_Liquid_Visualizer.py not found in ${PROJECT_ROOT}" >&2
    exit 1
fi
