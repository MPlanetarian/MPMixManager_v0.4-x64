#!/usr/bin/env bash
# ==============================================================================
# MP Liquid Glass Audio Player Desktop Launcher
# Launches the Liquid Glass standalone player with user-configured backend
# (Metal on Apple Silicon macOS, or OpenGL Core 3.3 [Default] / NVIDIA Vulkan on Linux).
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
[ ! -f "$BASE_DIR/MP_Audio_Player_Liquid_Glass_OpenGL.py" ] && BASE_DIR="$SCRIPT_DIR"

CONFIG_FILE="$HOME/.config/mix-manager/config.env"
[ ! -f "$CONFIG_FILE" ] && CONFIG_FILE="$BASE_DIR/config.env"

TARGET_PY=""

# macOS Apple Silicon check
if [ "$(uname -s)" = "Darwin" ]; then
    if [ "$(uname -m)" != "arm64" ]; then
        echo "Error: MP Audio Player Liquid Glass Metal requires Apple Silicon (M1/M2/M3/M4+). Intel Macs are not supported." >&2
        exit 1
    fi
    TARGET_PY="$BASE_DIR/MP_Audio_Player_Liquid_Glass_macOS.py"
    [ ! -f "$TARGET_PY" ] && TARGET_PY="$BASE_DIR/scripts/MP_Audio_Player_Liquid_Glass_macOS.py"
fi

if [ -z "$TARGET_PY" ]; then
    BACKEND="opengl"
    if [ -f "$CONFIG_FILE" ]; then
        VAL=$(grep -E "^LIQUID_GLASS_BACKEND=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"'\'' ')
        [ -n "$VAL" ] && BACKEND="$(echo "$VAL" | tr '[:upper:]' '[:lower:]')"
    fi

    if [ "$BACKEND" = "vulkan" ]; then
        TARGET_PY="$BASE_DIR/MP_Audio_Player_Liquid_Glass.py"
        [ ! -f "$TARGET_PY" ] && TARGET_PY="$BASE_DIR/scripts/MP_Audio_Player_Liquid_Glass.py"
    fi

    if [ -z "$TARGET_PY" ] || [ ! -f "$TARGET_PY" ]; then
        TARGET_PY="$BASE_DIR/MP_Audio_Player_Liquid_Glass_OpenGL.py"
        [ ! -f "$TARGET_PY" ] && TARGET_PY="$BASE_DIR/scripts/MP_Audio_Player_Liquid_Glass_OpenGL.py"
    fi

    if [ ! -f "$TARGET_PY" ]; then
        TARGET_PY="$BASE_DIR/MP_Audio_Player_Liquid_Glass.py"
    fi
fi

mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
cd "$BASE_DIR" || exit 1
exec python3 "$TARGET_PY" "$@"
