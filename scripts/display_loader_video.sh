#!/usr/bin/env bash
# ==============================================================================
# scripts/display_loader_video.sh
# Purpose: Display MP_loader.mp4 while MP Mix Archive Manager is loading in console.
#          Skips playback if an instance of the manager is already open.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ANSI Color definitions
NC='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
CYAN='\033[38;2;0;193;228m'
MAGENTA='\033[38;2;247;37;133m'
YELLOW='\033[38;2;255;170;0m'
GREEN='\033[38;2;0;229;255m'
RED='\033[38;2;237;37;78m'

# Check if another instance of Mix Archive Manager is already running
is_manager_already_open() {
    local my_pid="${1:-$$}"
    local p

    # 1. Check bridge status JSON for active manager session
    local bridge_file="${HOME}/.config/mix-manager/bridge_status.json"
    if [ -f "$bridge_file" ]; then
        local saved_pid
        saved_pid=$(grep -o '"pid": *[0-9]*' "$bridge_file" 2>/dev/null | grep -o '[0-9]*' || true)
        if [[ -n "$saved_pid" && "$saved_pid" != "$my_pid" && "$saved_pid" != "${PPID:-0}" ]]; then
            if kill -0 "$saved_pid" 2>/dev/null; then
                if [ -r "/proc/$saved_pid/cmdline" ]; then
                    if grep -qa -E "Mix_Archive_Manager|manager\.sh" "/proc/$saved_pid/cmdline" 2>/dev/null; then
                        return 0
                    fi
                else
                    return 0
                fi
            fi
        fi
    fi

    # 2. Check process table for running Mix_Archive_Manager.sh
    if command -v pgrep &>/dev/null; then
        local pids
        pids=$(pgrep -f "Mix_Archive_Manager\.sh" 2>/dev/null || true)
        for p in $pids; do
            [[ -z "$p" ]] && continue
            [[ "$p" == "$my_pid" || "$p" == "${PPID:-0}" ]] && continue
            local p_ppid=""
            if [ -d "/proc/$p" ]; then
                p_ppid=$(awk '{print $4}' "/proc/$p/stat" 2>/dev/null || true)
            else
                p_ppid=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ' || true)
            fi
            [[ "$p_ppid" == "$my_pid" ]] && continue

            if kill -0 "$p" 2>/dev/null; then
                return 0
            fi
        done
    fi

    return 1
}

# Locate MP_loader.mp4
find_loader_video_path() {
    local cand
    for cand in "${LOADER_VIDEO_FILE:-}" \
                "$SCRIPT_DIR/MP_loader.mp4" \
                "$SCRIPT_DIR/assets/MP_loader.mp4" \
                "/var/home/mplanetarian/MP_Mix_Manager_v0.3/MP_loader.mp4" \
                "$SCRIPT_DIR/gemini_generated_video_BEB1D608.mp4" \
                "/var/home/mplanetarian/GoogleDrive/gemini_generated_video_BEB1D608.mp4"; do
        if [ -n "$cand" ] && [ -s "$cand" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}

# Display loader video whilst manager is loading
display_startup_loader_video() {
    local force="${1:-0}"
    local my_pid="$$"

    # Respect user configuration disable switch
    if [ "$force" -ne 1 ] && [ "${SHOW_LOADER_VIDEO:-true}" = "false" ]; then
        return 0
    fi

    # Do not display for fast non-interactive CLI actions
    if [ "$force" -ne 1 ] && [ -n "${CLI_INITIAL_ACTION:-}" ]; then
        return 0
    fi

    # If manager is already open, do not display it!
    if [ "$force" -ne 1 ] && is_manager_already_open "$my_pid"; then
        return 0
    fi

    # Locate video file
    local loader_vid
    loader_vid="$(find_loader_video_path)" || return 0
    [ -z "$loader_vid" ] && return 0

    # Render loading console card
    local cur_cols="${COLUMNS:-80}"
    local box_w=74
    if command -v _set_menu_box_width &>/dev/null; then
        _set_menu_box_width box_w "$cur_cols" 2>/dev/null || box_w=74
    fi
    local inner_w=$(( box_w - 2 ))
    local text_w=$(( box_w - 6 ))
    local h_border
    printf -v h_border '%*s' "$inner_w" ''
    h_border="${h_border// /─}"
    local title="MP Mix Archive Manager (v0.3.6 Beta)"
    local sub="⚡ Loading workspace, archive statistics & environment..."
    local hint="Press [Esc], [Space], [Enter] or [q] to skip intro"

    printf '\033[?25l'
    clear 2>/dev/null || true
    echo ""
    echo -e "  ${BOLD}${MAGENTA}╭${h_border}╮${NC}"
    printf "  ${BOLD}${MAGENTA}│${NC}  ${BOLD}${CYAN}%-${text_w}s${NC}  ${BOLD}${MAGENTA}│${NC}\n" "$title"
    printf "  ${BOLD}${MAGENTA}│${NC}  ${YELLOW}%-${text_w}s${NC}  ${BOLD}${MAGENTA}│${NC}\n" "$sub"
    printf "  ${BOLD}${MAGENTA}│${NC}  ${DIM}%-${text_w}s${NC}  ${BOLD}${MAGENTA}│${NC}\n" "$hint"
    echo -e "  ${BOLD}${MAGENTA}╰${h_border}╯${NC}"
    echo ""

    # Launch video player if GUI display environment is available
    local player_pid=""
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] || [ "${OS_TYPE:-}" = "macos" ] || [ "${OS_TYPE:-}" = "windows" ]; then
        if command -v ffplay &>/dev/null; then
            ffplay -autoexit -noborder -alwaysontop -window_title "MP Mix Archive Manager" -loglevel quiet "$loader_vid" &>/dev/null &
            player_pid=$!
        elif command -v mpv &>/dev/null; then
            mpv --ontop --no-border --title="MP Mix Archive Manager" --no-terminal "$loader_vid" &>/dev/null &
            player_pid=$!
        elif command -v cvlc &>/dev/null; then
            cvlc --play-and-exit --video-on-top --no-video-title-show "$loader_vid" &>/dev/null &
            player_pid=$!
        elif command -v vlc &>/dev/null; then
            vlc --play-and-exit --video-on-top --no-video-title-show "$loader_vid" &>/dev/null &
            player_pid=$!
        elif [ "${OS_TYPE:-}" = "macos" ]; then
            open -a "QuickTime Player" "$loader_vid" &>/dev/null &
            player_pid=$!
        elif [ "${OS_TYPE:-}" = "windows" ]; then
            cmd.exe /c start "" "$loader_vid" &>/dev/null &
            player_pid=$!
        fi
    fi

    # Warm up caches in parallel while video is loading
    if command -v load_header_cache &>/dev/null; then
        load_header_cache 2>/dev/null || true
    fi

    # Wait for player completion or interactive skip keypress in console
    if [ -n "$player_pid" ]; then
        local waited=0
        while kill -0 "$player_pid" 2>/dev/null; do
            local key=""
            if read -rsn1 -t 0.1 key 2>/dev/null; then
                case "$key" in
                    $'\e'|[qQ]|""|" ")
                        kill -9 "$player_pid" 2>/dev/null || true
                        break
                        ;;
                esac
            fi
            ((waited++))
            # Safety timeout of 10.5 seconds (video is 10.0s)
            [ "$waited" -ge 105 ] && break
        done
        wait "$player_pid" 2>/dev/null || true
    else
        # In pure headless / no-display environments, provide a brief 1.2s loading beat
        sleep 1.2
    fi

    clear 2>/dev/null || true
    printf '\033[?25h' 2>/dev/null || true
    return 0
}

# Standalone execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        --check-only)
            if is_manager_already_open "$$"; then
                echo "ALREADY_OPEN"
                exit 0
            else
                echo "NOT_OPEN"
                exit 1
            fi
            ;;
        --path)
            find_loader_video_path
            exit 0
            ;;
        --force|-f)
            display_startup_loader_video 1
            exit 0
            ;;
        *)
            display_startup_loader_video 0
            exit 0
            ;;
    esac
fi
