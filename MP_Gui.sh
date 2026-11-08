#!/usr/bin/env bash
# ==============================================================================
# MP Mix Manager GUI
# Opens Mix Archive Manager inside the MP Liquid Player liquid-glass window.
# The same glass, bezel, opacity slider, and VTE terminal are used, and the
# window follows ~/.config/mix-manager/theme (the built-in themes).
#
# The shared theme file is set to Retro Linux Memories on launch so the window
# matches that theme immediately. That also changes an already-open terminal
# manager, which uses the same file. Pass --keep-theme to leave it alone.
# Pass --theme NAME to write a different theme instead.
#
# Closing this window stops playback and closes the MP Liquid Visualizer,
# even when the Liquid Player window is still open.
# ==============================================================================

_RESOLVED_SRC="${BASH_SOURCE[0]}"
while [ -h "$_RESOLVED_SRC" ]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
    _RESOLVED_SRC="$(readlink "$_RESOLVED_SRC")"
    [[ $_RESOLVED_SRC != /* ]] && _RESOLVED_SRC="$_RESOLVED_DIR/$_RESOLVED_SRC"
done
BASE_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
[ ! -f "$BASE_DIR/MP_Audio_Player_Liquid_Glass_OpenGL.py" ] && [ ! -f "$BASE_DIR/MP_Audio_Player_Liquid_Glass.py" ] && [ ! -f "$BASE_DIR/Mix_Archive_Manager.sh" ] && BASE_DIR="$(dirname "$BASE_DIR")"
unset _RESOLVED_SRC _RESOLVED_DIR

CONFIG_FILE="$HOME/.config/mix-manager/config.env"
[ ! -f "$CONFIG_FILE" ] && CONFIG_FILE="$BASE_DIR/config.env"

TARGET_PY=""

# Same host order as scripts/launch_liquid_glass.sh. The Metal macOS file
# loads a device pointer and writes the manager to stdout; it does not open
# a window. OpenGL macOS is the host that draws this GUI.
if [ "$(uname -s)" = "Darwin" ]; then
    TARGET_PY="$BASE_DIR/MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py"
    [ ! -f "$TARGET_PY" ] && TARGET_PY="$BASE_DIR/scripts/MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py"
    if [ ! -f "$TARGET_PY" ]; then
        if [ "$(uname -m)" != "arm64" ]; then
            echo "Error: MP Mix Manager GUI Liquid Glass Metal requires Apple Silicon (M1/M2/M3/M4+). Intel Macs are not supported." >&2
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

if [ ! -f "$TARGET_PY" ] || [ ! -f "$BASE_DIR/Mix_Archive_Manager.sh" ]; then
    echo "Error: MP Mix Manager GUI could not find the Liquid Glass host or Mix_Archive_Manager.sh." >&2
    exit 1
fi

KEEP_THEME=0
THEME_NAME="retro_linux_memories"
NO_VISUALIZER=0
NEW_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --keep-theme)
            KEEP_THEME=1
            shift
            ;;
        --no-visualizer)
            NO_VISUALIZER=1
            NEW_ARGS+=("$1")
            shift
            ;;
        --theme|-t)
            if [ $# -ge 2 ]; then
                THEME_NAME="$2"
                shift 2
            else
                shift
            fi
            ;;
        --theme=*)
            THEME_NAME="${1#--theme=}"
            shift
            ;;
        *)
            NEW_ARGS+=("$1")
            shift
            ;;
    esac
done

# Focus the existing manager window. A process with no mapped window is not
# already open, including the Metal macOS host and a machine without wmctrl.
if [ -f "$BASE_DIR/scripts/mp_gui_focus.sh" ]; then
    # shellcheck disable=SC1091
    source "$BASE_DIR/scripts/mp_gui_focus.sh"
    if mp_gui_focus_if_open; then
        exit 0
    fi
    mp_gui_stop_windowless_hosts
fi

# One tray icon shared with the console manager and MP Liquid Player.
if [ -f "$BASE_DIR/scripts/mp_system_tray.sh" ]; then
    if command -v setsid >/dev/null 2>&1; then
        setsid bash "$BASE_DIR/scripts/mp_system_tray.sh" --ensure >/dev/null 2>&1 </dev/null &
    else
        nohup bash "$BASE_DIR/scripts/mp_system_tray.sh" --ensure >/dev/null 2>&1 </dev/null &
    fi
    disown 2>/dev/null || true
fi

mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
if [ "$KEEP_THEME" -eq 0 ]; then
    printf '%s\n' "$THEME_NAME" > "$HOME/.config/mix-manager/theme"
fi

if command -v wpctl >/dev/null 2>&1; then
    wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 2>/dev/null || true
    wpctl set-volume @DEFAULT_AUDIO_SINK@ 1.0 2>/dev/null || true
fi
if command -v pactl >/dev/null 2>&1; then
    pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null || true
    pactl set-sink-volume @DEFAULT_SINK@ 100% 2>/dev/null || true
fi

python3 - "$BASE_DIR" << 'PY' || true
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from desktop_launch_screen import reposition_off_hisense
reposition_off_hisense()
PY

if [ "$NO_VISUALIZER" -eq 0 ] && ! pgrep -f "MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan" >/dev/null 2>&1; then
    VIS_PY="$BASE_DIR/MP_Liquid_Visualizer.py"
    [ ! -f "$VIS_PY" ] && VIS_PY="$BASE_DIR/scripts/mp_liquid_visualizer_vulkan.py"
    if [ -f "$VIS_PY" ]; then
        nohup python3 "$VIS_PY" --preset random >> "$HOME/.config/mix-manager/liquid_visualizer.log" 2>&1 &
    fi
fi

_VTE_BASE="${HOME}/.local/lib/mp-liquid-glass"
if [ -f "$_VTE_BASE/girepository-1.0/Vte-2.91.typelib" ]; then
    export LD_LIBRARY_PATH="${_VTE_BASE}/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export GI_TYPELIB_PATH="${_VTE_BASE}/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
fi
cd "$BASE_DIR" || exit 1
exec python3 "$TARGET_PY" --manager "${NEW_ARGS[@]}"
