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

# macOS check
if [ "$(uname -s)" = "Darwin" ]; then
    TARGET_PY="$BASE_DIR/MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py"
    [ ! -f "$TARGET_PY" ] && TARGET_PY="$BASE_DIR/scripts/MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py"
    if [ ! -f "$TARGET_PY" ]; then
        if [ "$(uname -m)" != "arm64" ]; then
            echo "Error: MP Audio Player Liquid Glass Metal requires Apple Silicon (M1/M2/M3/M4+). Intel Macs are not supported." >&2
            exit 1
        fi
        TARGET_PY="$BASE_DIR/MP_Audio_Player_Liquid_Glass_macOS.py"
        [ ! -f "$TARGET_PY" ] && TARGET_PY="$BASE_DIR/scripts/MP_Audio_Player_Liquid_Glass_macOS.py"
    fi
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
#if command -v wpctl >/dev/null 2>&1; then
#    wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 2>/dev/null || true
#    wpctl set-volume @DEFAULT_AUDIO_SINK@ 1.0 2>/dev/null || true
#fi
#if command -v pactl >/dev/null 2>&1; then
#    pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null || true
#    pactl set-sink-volume @DEFAULT_SINK@ 100% 2>/dev/null || true
#    pactl list short sinks 2>/dev/null | awk '{print $1}' | while read -r _s; do
#        pactl set-sink-mute "$_s" 0 2>/dev/null || true
#        pactl set-sink-volume "$_s" 100% 2>/dev/null || true
#    done
#fi

# Ensure MP Audio Player engine volume is set to 100%
#if [ -f "$BASE_DIR/MP_Audio_Player.py" ]; then
#    python3 "$BASE_DIR/MP_Audio_Player.py" --vol 100 2>/dev/null || true
#fi

# If a previous window opened on the Hisense, bring it back to the main screen.
python3 - "$BASE_DIR" << 'PY' || true
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from desktop_launch_screen import reposition_off_hisense
reposition_off_hisense()
PY

# One tray icon shared with MP Mix Manager and MP Gui.
_mp_tray=""
for _mp_tray in \
    "$BASE_DIR/scripts/mp_system_tray.sh" \
    "$SCRIPT_DIR/mp_system_tray.sh"
do
    if [ -f "$_mp_tray" ]; then
        if command -v setsid >/dev/null 2>&1; then
            setsid bash "$_mp_tray" --ensure >/dev/null 2>&1 </dev/null &
        else
            nohup bash "$_mp_tray" --ensure >/dev/null 2>&1 </dev/null &
        fi
        disown 2>/dev/null || true
        break
    fi
done
unset _mp_tray

# Single instance check: if MP Liquid is already running, activate window and exit.
# The Mix Manager GUI is this program with --manager and is not the player.
_liquid_player_already_open=0
_lg_line=""
if [ "$(uname -s)" = "Darwin" ]; then
    _lg_pgrep() { pgrep -fl 'MP_Audio_Player_Liquid_Glas[s]' 2>/dev/null || true; }
else
    _lg_pgrep() { pgrep -af 'MP_Audio_Player_Liquid_Glas[s]' 2>/dev/null || true; }
fi
while IFS= read -r _lg_line; do
    case "$_lg_line" in
        *--manager*) continue ;;
        *MP_Audio_Player_Liquid_Glass*) _liquid_player_already_open=1; break ;;
    esac
done < <(_lg_pgrep)
if [ "$_liquid_player_already_open" -eq 1 ]; then
    if [ "$(uname -s)" = "Darwin" ] && [ -f "$BASE_DIR/scripts/mp_gui_focus.sh" ]; then
        # shellcheck disable=SC1091
        source "$BASE_DIR/scripts/mp_gui_focus.sh"
        mp_player_raise_host || true
    elif command -v wmctrl >/dev/null 2>&1; then
        wmctrl -a "MP Audio Player (Liquid Glass" 2>/dev/null || true
    fi
    exit 0
fi
unset _lg_line _liquid_player_already_open

# Start the companion visualizer. The Liquid Player closes this window on exit.
if ! pgrep -f "MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan" >/dev/null 2>&1; then
    VIS_PY="$BASE_DIR/MP_Liquid_Visualizer.py"
    [ ! -f "$VIS_PY" ] && VIS_PY="$BASE_DIR/scripts/mp_liquid_visualizer_vulkan.py"
    if [ -f "$VIS_PY" ]; then
        nohup python3 "$VIS_PY" --preset random >> "$HOME/.config/mix-manager/liquid_visualizer.log" 2>&1 &
    fi
fi

mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
_VTE_BASE="${HOME}/.local/lib/mp-liquid-glass"
if [ -f "$_VTE_BASE/girepository-1.0/Vte-2.91.typelib" ]; then
    export LD_LIBRARY_PATH="${_VTE_BASE}/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export GI_TYPELIB_PATH="${_VTE_BASE}/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
fi
cd "$BASE_DIR" || exit 1
exec python3 "$TARGET_PY" "$@"
