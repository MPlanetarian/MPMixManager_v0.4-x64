#!/usr/bin/env bash
# ==============================================================================
# MP_Liquid_Visualizer — Native Vulkan 1400x1400 Borderless 3D Visualizer Launcher
# Cross-Platform: macOS (MoltenVK) / Windows 10 & 11 / Linux
# ==============================================================================
set -euo pipefail

# Ensure Homebrew and standard paths are present on macOS
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Error: Python 3 not found in PATH." >&2
    exit 1
fi

if [[ -f "${PROJECT_ROOT}/MP_Liquid_Visualizer.py" ]]; then
    exec "$PYTHON_BIN" "${PROJECT_ROOT}/MP_Liquid_Visualizer.py" "$@"
elif [[ -f "${SCRIPT_DIR}/mp_liquid_visualizer_vulkan.py" ]]; then
    exec "$PYTHON_BIN" "${SCRIPT_DIR}/mp_liquid_visualizer_vulkan.py" "$@"
else
    echo "Error: MP_Liquid_Visualizer.py not found in ${PROJECT_ROOT}" >&2
    exit 1
fi
