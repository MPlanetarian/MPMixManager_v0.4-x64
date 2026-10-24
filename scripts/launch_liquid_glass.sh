#!/usr/bin/env bash
# ==============================================================================
# MP Liquid Glass Audio Player Desktop Launcher
# Launches the Liquid Glass standalone player with user-configured backend
# (Metal on Apple Silicon macOS, or OpenGL Core 3.3 [Default] / NVIDIA Vulkan on Linux).
# ==============================================================================

# Resolve symlinks so BASE_DIR is accurate even if invoked via ~/.local/bin symlink
_RESOLVED_SRC="${BASH_SOURCE[0]}"
while [ -h "$_RESOLVED_SRC" ]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
    _RESOLVED_SRC="$(readlink "$_RESOLVED_SRC")"
    [[ $_RESOLVED_SRC != /* ]] && _RESOLVED_SRC="$_RESOLVED_DIR/$_RESOLVED_SRC"
done
SCRIPT_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
[ ! -f "$BASE_DIR/MP_Audio_Player_Liquid_Glass_OpenGL.py" ] && [ ! -f "$BASE_DIR/MP_Audio_Player_Liquid_Glass.py" ] && BASE_DIR="$SCRIPT_DIR"

# Fallback candidate search when script is copied to ~/.local/bin/launch-liquid-glass
if [ ! -f "$BASE_DIR/MP_Audio_Player_Liquid_Glass_OpenGL.py" ] && [ ! -f "$BASE_DIR/MP_Audio_Player_Liquid_Glass.py" ]; then
    for _c in \
        "${MP_MIX_MANAGER_DIR:-}" \
        "$PWD" \
        "/var/home/mplanetarian/MP_Mix_Manager_v0.4" \
        "$HOME/MP_Mix_Manager_v0.4" \
        "/home/mplanetarian/MP_Mix_Manager_v0.4" \
        "/var/home/mplanetarian/MP_Mix_Manager_v0.3" \
        "$HOME/MP_Mix_Manager_v0.3"; do
        if [ -n "$_c" ] && { [ -f "$_c/MP_Audio_Player_Liquid_Glass_OpenGL.py" ] || [ -f "$_c/MP_Audio_Player_Liquid_Glass.py" ] || [ -f "$_c/MP_Audio_Player_Liquid_Glass_macOS.py" ]; }; then
            BASE_DIR="$_c"
            break
        fi
    done
fi
unset _RESOLVED_SRC _RESOLVED_DIR _c

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

# Ensure audio volume level is set to 100% and unmuted
if command -v wpctl >/dev/null 2>&1; then
    wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 2>/dev/null || true
    wpctl set-volume @DEFAULT_AUDIO_SINK@ 1.0 2>/dev/null || true
fi
if command -v pactl >/dev/null 2>&1; then
    pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null || true
    pactl set-sink-volume @DEFAULT_SINK@ 100% 2>/dev/null || true
    pactl list short sinks 2>/dev/null | awk '{print $1}' | while read -r _s; do
        pactl set-sink-mute "$_s" 0 2>/dev/null || true
        pactl set-sink-volume "$_s" 100% 2>/dev/null || true
    done
fi

# Ensure MP Audio Player engine volume is set to 100%
if [ -f "$BASE_DIR/MP_Audio_Player.py" ]; then
    python3 "$BASE_DIR/MP_Audio_Player.py" --vol 100 2>/dev/null || true
fi

# Single instance check: if MP Liquid is already running, activate window and exit
if pgrep -f "MP_Audio_Player_Liquid_Glass" >/dev/null 2>&1; then
    if command -v wmctrl >/dev/null 2>&1; then
        wmctrl -a "MP Audio Player (Liquid Glass" 2>/dev/null || true
    fi
    exit 0
fi

# Automatically start MP Liquid Visualizer with a random preset if not already running
if ! pgrep -f "MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan" >/dev/null 2>&1; then
    VIS_PY="$BASE_DIR/MP_Liquid_Visualizer.py"
    [ ! -f "$VIS_PY" ] && VIS_PY="$BASE_DIR/scripts/mp_liquid_visualizer_vulkan.py"
    if [ -f "$VIS_PY" ]; then
        nohup python3 "$VIS_PY" --preset random >> "$HOME/.config/mix-manager/liquid_visualizer.log" 2>&1 &
    fi
fi

mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
cd "$BASE_DIR" || exit 1
exec python3 "$TARGET_PY" "$@"
