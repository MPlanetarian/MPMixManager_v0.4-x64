#!/usr/bin/env bash
# ==============================================================================
# kill_all_mp_audio_players.sh - Terminate all MP Audio Player instances
# Part of MP_Mix_Manager_v0.4
#
# Terminates all running MP Audio Player instances:
#  - MP_Audio_Player.py (Standalone GUI, Terminal UI, Mini/Micro Player, Daemon)
#  - MP_Audio_Player.sh launchers
#  - MP_Audio_Player_Liquid_Glass*.py (Liquid Glass OpenGL/Vulkan/Metal players)
#  - launch_liquid_glass.sh / launch-liquid-glass
#  - MP_Liquid_Visualizer.py / mp_liquid_visualizer_vulkan.py
#  - traktor_s4_midi.py (MIDI controller companion)
#  - Bluetooth pactl subscribe monitors spawned by player
# Cleans up lock, socket, PID, and state files.
# ==============================================================================

set -uo pipefail

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PATH="$HOME/.local/bin:$PATH"

UNAME_S="$(uname -s 2>/dev/null || echo "Unknown")"
SCRIPT_PID="$$"
SCRIPT_BASHPID="${BASHPID:-$$}"

# Color codes (only when in terminal)
if [ -t 1 ]; then
    BOLD="\033[1m"
    DIM="\033[2m"
    GREEN="\033[38;2;0;255;0m"
    RED="\033[38;2;255;0;0m"
    AMBER="\033[38;2;255;153;51m"
    CYAN="\033[38;2;0;229;255m"
    PURPLE="\033[38;2;166;77;255m"
    NC="\033[0m"
else
    BOLD=""
    DIM=""
    GREEN=""
    RED=""
    AMBER=""
    CYAN=""
    PURPLE=""
    NC=""
fi

QUIET=0
for arg in "$@"; do
    case "$arg" in
        -q|--quiet) QUIET=1 ;;
        -h|--help)
            echo "Usage: $(basename "$0") [OPTIONS]"
            echo ""
            echo "Terminate all active MP Audio Player instances, daemons, and visualizers."
            echo ""
            echo "Options:"
            echo "  -q, --quiet   Suppress console output"
            echo "  -h, --help    Show this help message"
            exit 0
            ;;
    esac
done

log_info() {
    [ "$QUIET" -eq 1 ] && return 0
    echo -e "${PURPLE}♫${NC} ${BOLD}$1${NC}"
}

log_detail() {
    [ "$QUIET" -eq 1 ] && return 0
    echo -e "  ${DIM}• $1${NC}"
}

log_success() {
    [ "$QUIET" -eq 1 ] && return 0
    echo -e "${GREEN}✓${NC} ${BOLD}$1${NC}"
}

log_info "Initiating shutdown of all MP Audio Player instances..."

CONFIG_DIR="${HOME}/.config/mix-manager"
PID_FILE="${CONFIG_DIR}/mp_player.pid"
PORT_FILE="${CONFIG_DIR}/mp_audio_player.port"
SOCK_FILE="${CONFIG_DIR}/mp_audio_player.sock"
STATE_FILE="${CONFIG_DIR}/mp_player_state.json"
S4_PID_FILE="${CONFIG_DIR}/traktor_s4_midi.pid"

# ------------------------------------------------------------------------------
# 1. Attempt graceful IPC stop if socket or port is active
# ------------------------------------------------------------------------------
PY=""
if command -v python3 &>/dev/null; then
    PY="python3"
elif command -v python &>/dev/null; then
    PY="python"
fi

if [ -n "$PY" ]; then
    PORT=""
    [ -f "$PORT_FILE" ] && IFS= read -r PORT < "$PORT_FILE" 2>/dev/null || true
    MP_STOP_PORT="$PORT" MP_STOP_SOCK="$SOCK_FILE" "$PY" - &>/dev/null << 'PYSTOP' || true
import os, socket
sent = False
sock_path = os.environ.get("MP_STOP_SOCK", "")
if sock_path and os.path.exists(sock_path) and hasattr(socket, "AF_UNIX"):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.3)
        s.connect(sock_path)
        s.sendall(b'{"cmd":"stop"}')
        try:
            s.recv(1024)
        except Exception:
            pass
        s.close()
        sent = True
    except Exception:
        pass
if not sent:
    try:
        port = int(os.environ.get("MP_STOP_PORT", "0"))
        if port > 0:
            sock = socket.create_connection(("127.0.0.1", port), 0.3)
            sock.settimeout(0.3)
            sock.sendall(b'{"cmd":"stop"}')
            try:
                sock.recv(1024)
            except Exception:
                pass
            sock.close()
    except Exception:
        pass
PYSTOP
fi

# ------------------------------------------------------------------------------
# 2. Collect process IDs to terminate
# ------------------------------------------------------------------------------
declare -a PIDS_TO_KILL=()

# Known PID from pid file
if [ -f "$PID_FILE" ]; then
    P_PID=""
    IFS= read -r P_PID < "$PID_FILE" 2>/dev/null || true
    if [[ "$P_PID" =~ ^[0-9]+$ ]] && [ "$P_PID" -gt 1 ]; then
        PIDS_TO_KILL+=("$P_PID")
    fi
fi

# Known PID from Traktor S4 MIDI file
if [ -f "$S4_PID_FILE" ]; then
    S4_PID=""
    IFS= read -r S4_PID < "$S4_PID_FILE" 2>/dev/null || true
    if [[ "$S4_PID" =~ ^[0-9]+$ ]] && [ "$S4_PID" -gt 1 ]; then
        PIDS_TO_KILL+=("$S4_PID")
    fi
fi

# Search running processes across Linux/macOS
if [[ ! "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then
    PATTERNS=(
        "MP_Audio_Player\.py"
        "MP_Audio_Player\.sh"
        "MP_Audio_Player_Liquid_Glass"
        "MP_Liquid_Visualizer"
        "mp_liquid_visualizer"
        "launch_liquid_glass"
        "launch-liquid-glass"
        "launch_liquid_visualizer"
        "traktor_s4_midi\.py"
        "get_mp_audio_player_file"
    )

    RAW_PIDS=""
    for pat in "${PATTERNS[@]}"; do
        p_out="$(pgrep -f "$pat" 2>/dev/null || true)"
        [ -n "$p_out" ] && RAW_PIDS="${RAW_PIDS}"$'\n'"${p_out}"
    done

    # Fallback to ps inspection to catch full commandlines
    ps_pids="$(ps -eo pid,command 2>/dev/null | grep -iE '(MP_Audio_Player|Liquid_Glass|Liquid_Visualizer|launch-liquid-glass|launch_liquid_glass)' | grep -v -E "(grep|kill_all_mp_audio_players|$SCRIPT_PID)" | awk '{print $1}' || true)"
    [ -n "$ps_pids" ] && RAW_PIDS="${RAW_PIDS}"$'\n'"${ps_pids}"

    if [ -n "$RAW_PIDS" ]; then
        UNIQ_PIDS=$(printf '%s\n' "$RAW_PIDS" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u)
        for p in $UNIQ_PIDS; do
            [ "$p" -le 1 ] && continue
            [ "$p" -eq "$SCRIPT_PID" ] && continue
            [ "$p" -eq "$SCRIPT_BASHPID" ] && continue
            PIDS_TO_KILL+=("$p")
        done
    fi
fi

# Deduplicate PIDS_TO_KILL array
if [ "${#PIDS_TO_KILL[@]}" -gt 0 ]; then
    UNIQUE_PIDS=($(printf "%s\n" "${PIDS_TO_KILL[@]}" | sort -u))
else
    UNIQUE_PIDS=()
fi

KILLED_COUNT=0

# ------------------------------------------------------------------------------
# 3. Terminate processes
# ------------------------------------------------------------------------------
if [[ "$UNAME_S" =~ (MINGW|MSYS|CYGWIN) ]]; then
    # Windows native termination
    powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*MP_Audio_Player*' -or \$_.CommandLine -like '*Liquid_Glass*' -or \$_.CommandLine -like '*Liquid_Visualizer*' -or \$_.CommandLine -like '*traktor_s4_midi*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" &>/dev/null || true
    taskkill.exe /F /FI "WINDOWTITLE eq MP Audio Player*" &>/dev/null || true
    taskkill.exe /F /FI "WINDOWTITLE eq MP Mini Audio Player*" &>/dev/null || true
    taskkill.exe /F /FI "WINDOWTITLE eq MP Micro Audio Player*" &>/dev/null || true
    taskkill.exe /F /FI "WINDOWTITLE eq MP Liquid*" &>/dev/null || true
    KILLED_COUNT=${#UNIQUE_PIDS[@]}
else
    # Linux & macOS termination
    if [ "${#UNIQUE_PIDS[@]}" -gt 0 ]; then
        log_detail "Sending SIGTERM to ${#UNIQUE_PIDS[@]} process(es): ${UNIQUE_PIDS[*]}"
        for p in "${UNIQUE_PIDS[@]}"; do
            kill -TERM "$p" 2>/dev/null || true
        done

        # Grace period for clean shutdown
        sleep 0.25

        # Check alive and force kill
        for p in "${UNIQUE_PIDS[@]}"; do
            if kill -0 "$p" 2>/dev/null; then
                log_detail "Process $p still running — sending SIGKILL"
                kill -KILL "$p" 2>/dev/null || true
            fi
            ((KILLED_COUNT++)) || true
        done
    fi

    # Extra sweeping safety net with pkill
    pkill -9 -f "MP_Audio_Player\.py" 2>/dev/null || true
    pkill -9 -f "MP_Audio_Player_Liquid_Glass" 2>/dev/null || true
    pkill -9 -f "MP_Liquid_Visualizer" 2>/dev/null || true
    pkill -9 -f "mp_liquid_visualizer_vulkan" 2>/dev/null || true
    pkill -9 -f "launch[-_]liquid[-_]glass" 2>/dev/null || true
    pkill -9 -f "launch_liquid_visualizer" 2>/dev/null || true
    pkill -9 -f "traktor_s4_midi\.py" 2>/dev/null || true

    # Clean up orphaned pactl subscribe processes spawned by bluetooth router
    pkill -9 -f "pactl subscribe" 2>/dev/null || true

    # Close matching GUI / X11 / Wayland windows if wmctrl is available
    if command -v wmctrl &>/dev/null; then
        wmctrl -lp 2>/dev/null | while read -r win_id desktop_num win_pid host win_title; do
            if [[ "$win_title" == *"MP Audio Player"* || "$win_title" == *"MP Mini Audio Player"* || "$win_title" == *"MP Micro Audio Player"* || "$win_title" == *"Liquid Glass"* || "$win_title" == *"MP_Liquid"* ]]; then
                wmctrl -c "$win_id" 2>/dev/null || true
            fi
        done
    fi
fi

# ------------------------------------------------------------------------------
# 4. Cleanup runtime, PID, and socket files
# ------------------------------------------------------------------------------
rm -f "$PID_FILE" "$PORT_FILE" "$SOCK_FILE" "$S4_PID_FILE" 2>/dev/null || true

# Atomically update state file to stopped
if [ -f "$STATE_FILE" ] && [ -n "$PY" ]; then
    "$PY" -c '
import json, sys
sf = sys.argv[1]
try:
    with open(sf, "r", encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict):
        d["running"] = False
        d["state"] = "stopped"
        with open(sf, "w", encoding="utf-8") as f:
            json.dump(d, f)
except Exception:
    with open(sf, "w", encoding="utf-8") as f:
        f.write("{\"running\": false, \"state\": \"stopped\"}\n")
' "$STATE_FILE" 2>/dev/null || printf '%s\n' '{"running": false, "state": "stopped"}' > "$STATE_FILE" 2>/dev/null || true
else
    mkdir -p "$CONFIG_DIR" 2>/dev/null || true
    printf '%s\n' '{"running": false, "state": "stopped"}' > "$STATE_FILE" 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# 5. User Feedback and Desktop Notification
# ------------------------------------------------------------------------------
SUMMARY_MSG="All MP Audio Players terminated."
if [ "$KILLED_COUNT" -gt 0 ]; then
    SUMMARY_MSG="Terminated $KILLED_COUNT MP Audio Player instance(s) and cleared runtime state."
fi

log_success "$SUMMARY_MSG"

if command -v notify-send &>/dev/null; then
    notify-send -a "MP Audio Player" \
        -i "media-playback-stop" \
        "MP Audio Player" \
        "$SUMMARY_MSG" 2>/dev/null || true
fi

exit 0
