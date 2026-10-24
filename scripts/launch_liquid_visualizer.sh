#!/usr/bin/env bash
# ==============================================================================
# MP_Liquid_Visualizer — Native Vulkan 1400x1400 Borderless 3D Visualizer Launcher
# Preset 1: Cosmic Dreamworlds (Liquid)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/MP_Liquid_Visualizer.py" ]]; then
    exec python3 "${PROJECT_ROOT}/MP_Liquid_Visualizer.py" "$@"
elif [[ -f "${SCRIPT_DIR}/mp_liquid_visualizer_vulkan.py" ]]; then
    exec python3 "${SCRIPT_DIR}/mp_liquid_visualizer_vulkan.py" "$@"
else
    echo "Error: MP_Liquid_Visualizer.py not found in ${PROJECT_ROOT}" >&2
    exit 1
fi
