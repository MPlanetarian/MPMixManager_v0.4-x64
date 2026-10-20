#!/usr/bin/env bash
# ==============================================================================
# scripts/display_loader_video.sh
# Purpose: Display MP_loader.mp4 while MP Mix Archive Manager is loading in console.
#          Skips playback if an instance of the manager is already open.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${VERSION:-}" ]; then
    if [ -f "$SCRIPT_DIR/VERSION" ]; then
        VERSION="$(head -n 1 "$SCRIPT_DIR/VERSION" | tr -d '\r\n')"
    else
        VERSION="0.3.6 Beta"
    fi
fi
export VERSION

if [ -z "${OS_TYPE:-}" ] || [ "${OS_TYPE:-}" = "linux" -a -n "${WINDIR:-}" ] || [[ "${OS_TYPE:-}" = "linux" && "$(uname -s 2>/dev/null)" =~ (MINGW|MSYS|CYGWIN) ]]; then
    case "$(uname -s 2>/dev/null)" in
        Darwin*) OS_TYPE="macos" ;;
        CYGWIN*|MINGW*|MSYS*) OS_TYPE="windows" ;;
        FreeBSD*) OS_TYPE="freebsd" ;;
        *)
            if [[ "${OSTYPE:-}" =~ (msys|cygwin|win32) ]] || [ -n "${WINDIR:-}" ] || [ -n "${SYSTEMROOT:-}" ]; then
                OS_TYPE="windows"
            else
                OS_TYPE="linux"
            fi
            ;;
    esac
fi
export OS_TYPE

# Ensure Homebrew and standard bins are in PATH for macOS
if [ "$OS_TYPE" = "macos" ] || [ "$(uname -s)" = "Darwin" ]; then
    export PATH="/opt/homebrew/bin:/usr/local/bin:$SCRIPT_DIR/bin:$SCRIPT_DIR:$HOME/.local/bin:$PATH"
fi

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
                    local proc_args
                    proc_args="$(ps -p "$saved_pid" -o args= 2>/dev/null || ps -p "$saved_pid" -o comm= 2>/dev/null || true)"
                    if [[ "$proc_args" =~ (Mix_Archive_Manager|manager\.sh|manager_macos) ]]; then
                        return 0
                    fi
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
    local cand_list=()
    if [ -n "${LOADER_VIDEO_FILE:-}" ]; then
        cand_list+=("${LOADER_VIDEO_FILE}" "$SCRIPT_DIR/${LOADER_VIDEO_FILE}")
    fi
    cand_list+=(
        "$SCRIPT_DIR/MP_loader.mp4"
        "$SCRIPT_DIR/assets/MP_loader.mp4"
        "/var/home/mplanetarian/MP_Mix_Manager_v0.3/MP_loader.mp4"
        "$SCRIPT_DIR/gemini_generated_video_BEB1D608.mp4"
        "/var/home/mplanetarian/GoogleDrive/gemini_generated_video_BEB1D608.mp4"
    )
    for cand in "${cand_list[@]}"; do
        if [ -n "$cand" ] && [ -f "$cand" ] && [ -s "$cand" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}

# Console skip during the loader. Empty input is Enter.
# Bash 3.2 (stock macOS) rejects a fractional read timeout, which made the
# wait loop finish immediately and close the movie before it appeared.
_loader_skip_requested() {
    local key="" timeout="0.1" rc=0
    if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
        timeout="1"
    fi
    if IFS= read -rsn1 -t "$timeout" key </dev/tty 2>/dev/null; then
        case "$key" in
            $'\e'|[qQ]|""|" ") return 0 ;;
        esac
        return 1
    else
        rc=$?
    fi
    # A rejected timeout or a missing tty returns at once. Pace the loop.
    if [ "$rc" -le 128 ]; then
        sleep 1
    fi
    return 1
}

# macOS has QuickTime Player on every system. open(1) starts playback without
# an Automation prompt. A later AppleScript only presses play / presentation
# and is allowed to fail.
play_macos_loader_video() {
    local vid="$1"
    [ -n "$vid" ] && [ -f "$vid" ] || return 1
    if ! type open >/dev/null 2>&1; then
        return 1
    fi
    open -a "QuickTime Player" "$vid" >/dev/null 2>&1 || return 1
    if type osascript >/dev/null 2>&1; then
        osascript - "$vid" >/dev/null 2>&1 <<'APPLESCRIPT' &
on run argv
    set movieName to item 1 of argv
    delay 0.6
    tell application "QuickTime Player"
        if (count of documents) is 0 then return
        repeat with movieDoc in documents
            try
                if name of movieDoc contains "MP_loader" or POSIX path of movieDoc contains movieName then
                    tell movieDoc
                        play
                        try
                            set presenting to true
                        end try
                    end tell
                    return
                end if
            end try
        end repeat
        try
            tell front document to play
        end try
    end tell
end run
APPLESCRIPT
    fi
    return 0
}

close_macos_loader_video() {
    type osascript >/dev/null 2>&1 || return 0
    osascript >/dev/null 2>&1 <<'APPLESCRIPT' || true
tell application "QuickTime Player"
    if it is not running then return
    repeat with movieDoc in documents
        try
            if name of movieDoc contains "MP_loader" then close movieDoc
        end try
    end repeat
    try
        if (count of documents) is 0 then quit
    end try
end tell
APPLESCRIPT
}

# "yes" once QuickTime is actually playing the loader, "no" once that
# document has stopped, or empty when AppleScript cannot see the player.
_macos_loader_playback_state() {
    type osascript >/dev/null 2>&1 || return 0
    osascript 2>/dev/null <<'APPLESCRIPT' || true
tell application "System Events"
    if not (exists process "QuickTime Player") then
        return "no"
    end if
end tell
tell application "QuickTime Player"
    if (count of documents) is 0 then return "no"
    repeat with movieDoc in documents
        try
            if name of movieDoc contains "MP_loader" then
                if playing of movieDoc then return "yes"
                return "no"
            end if
        end try
    end repeat
end tell
return ""
APPLESCRIPT
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
    local title="MP Mix Archive Manager (v${VERSION#v})"
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
    local is_gui=0
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] || [ "${OS_TYPE:-}" = "macos" ] || [ "${OS_TYPE:-}" = "windows" ] || [ "${OS_TYPE:-}" = "wsl" ] || [ "$(uname -s 2>/dev/null)" = "Darwin" ] || [[ "$(uname -s 2>/dev/null)" =~ (MINGW|MSYS|CYGWIN) ]]; then
        is_gui=1
    fi

    # Prepare Windows-native path format if needed
    local win_loader_vid="$loader_vid"
    if [ "${OS_TYPE:-}" = "windows" ] || [[ "$(uname -s 2>/dev/null)" =~ (MINGW|MSYS|CYGWIN) ]]; then
        if command -v cygpath &>/dev/null; then
            win_loader_vid="$(cygpath -w "$loader_vid" 2>/dev/null || echo "$loader_vid")"
        fi
    fi

    # Locate media players across platforms & Windows standard installations
    local ffplay_bin=""
    if command -v ffplay &>/dev/null; then
        ffplay_bin="$(command -v ffplay)"
    elif [ -n "${LOCALAPPDATA:-}" ] && [ -x "$LOCALAPPDATA/Microsoft/WinGet/Links/ffplay.exe" ]; then
        ffplay_bin="$LOCALAPPDATA/Microsoft/WinGet/Links/ffplay.exe"
    elif [ -x "/c/Users/${USER:-Mathe}/AppData/Local/Microsoft/WinGet/Links/ffplay.exe" ]; then
        ffplay_bin="/c/Users/${USER:-Mathe}/AppData/Local/Microsoft/WinGet/Links/ffplay.exe"
    elif [ -x "/c/ffmpeg/bin/ffplay.exe" ]; then
        ffplay_bin="/c/ffmpeg/bin/ffplay.exe"
    elif [ -x "/c/ProgramData/chocolatey/bin/ffplay.exe" ]; then
        ffplay_bin="/c/ProgramData/chocolatey/bin/ffplay.exe"
    fi

    local mpv_bin=""
    if command -v mpv &>/dev/null; then
        mpv_bin="$(command -v mpv)"
    elif [ -x "/c/Program Files/mpv/mpv.exe" ]; then
        mpv_bin="/c/Program Files/mpv/mpv.exe"
    elif [ -n "${LOCALAPPDATA:-}" ] && [ -x "$LOCALAPPDATA/Programs/mpv/mpv.exe" ]; then
        mpv_bin="$LOCALAPPDATA/Programs/mpv/mpv.exe"
    elif [ -x "/c/ProgramData/chocolatey/bin/mpv.exe" ]; then
        mpv_bin="/c/ProgramData/chocolatey/bin/mpv.exe"
    fi

    local vlc_bin=""
    if command -v cvlc &>/dev/null; then
        vlc_bin="$(command -v cvlc)"
    elif command -v vlc &>/dev/null; then
        vlc_bin="$(command -v vlc)"
    elif [ -x "/Applications/VLC.app/Contents/MacOS/VLC" ]; then
        vlc_bin="/Applications/VLC.app/Contents/MacOS/VLC"
    elif [ -x "/c/Program Files/VideoLAN/VLC/vlc.exe" ]; then
        vlc_bin="/c/Program Files/VideoLAN/VLC/vlc.exe"
    elif [ -x "/c/Program Files (x86)/VideoLAN/VLC/vlc.exe" ]; then
        vlc_bin="/c/Program Files (x86)/VideoLAN/VLC/vlc.exe"
    fi

    if [ "$is_gui" -eq 1 ]; then
        if { [ "${OS_TYPE:-}" = "macos" ] || [ "$(uname -s 2>/dev/null)" = "Darwin" ]; } && play_macos_loader_video "$loader_vid"; then
            # QuickTime plays the logo on macOS. ffplay, mpv, and VLC stay as
            # fallbacks when QuickTime cannot open the file.
            player_pid="quicktime"
        elif [ -n "$ffplay_bin" ]; then
            "$ffplay_bin" -autoexit -noborder -alwaysontop -window_title "MP Mix Archive Manager" -loglevel quiet "$loader_vid" </dev/null &>/dev/null &
            player_pid=$!
        elif [ -n "$mpv_bin" ]; then
            "$mpv_bin" --ontop --no-border --title="MP Mix Archive Manager" --no-terminal "$loader_vid" </dev/null &>/dev/null &
            player_pid=$!
        elif [ -n "$vlc_bin" ]; then
            "$vlc_bin" --play-and-exit --video-on-top --no-video-title-show "$loader_vid" </dev/null &>/dev/null &
            player_pid=$!
        elif [ "${OS_TYPE:-}" = "windows" ] || [[ "$(uname -s 2>/dev/null)" =~ (MINGW|MSYS|CYGWIN) ]]; then
            local ps_bin=""
            if command -v powershell.exe &>/dev/null; then
                ps_bin="powershell.exe"
            elif [ -x "/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]; then
                ps_bin="/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
            fi
            if [ -n "$ps_bin" ]; then
                local win_esc_vid="${win_loader_vid//\'/\'\'}"
                "$ps_bin" -NoProfile -Command "
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase;
\$w = New-Object Windows.Window;
\$w.Title = 'MP Mix Archive Manager';
\$w.WindowStyle = 'None';
\$w.AllowsTransparency = \$true;
\$w.Background = [Windows.Media.Brushes]::Black;
\$w.Topmost = \$true;
\$w.WindowStartupLocation = 'CenterScreen';
\$w.Width = 800;
\$w.Height = 450;
\$m = New-Object Windows.Controls.MediaElement;
\$m.LoadedBehavior = 'Play';
\$m.Source = [Uri]'$win_esc_vid';
\$m.Add_MediaEnded({ \$w.Close() });
\$w.Add_KeyDown({ param(\$s,\$e) \$w.Close() });
\$w.Add_MouseDown({ param(\$s,\$e) \$w.Close() });
\$w.Content = \$m;
\$w.ShowDialog() | Out-Null
" </dev/null &>/dev/null &
                player_pid=$!
            else
                cmd.exe /c start "" "$win_loader_vid" &>/dev/null &
                player_pid=$!
            fi
        fi
    fi

    # Warm up caches in parallel while video is loading
    if command -v load_header_cache &>/dev/null; then
        load_header_cache 2>/dev/null || true
    fi

    # Wait for player completion or interactive skip keypress in console
    if [ -n "$player_pid" ]; then
        local waited=0
        local seen_playing=0
        local wait_limit=105
        local poll_every=10
        # Stock macOS bash 3.2 can only wait in whole seconds.
        if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
            wait_limit=11
            poll_every=1
        fi
        if [ "$player_pid" = "quicktime" ]; then
            while [ "$waited" -lt "$wait_limit" ]; do
                if _loader_skip_requested; then
                    break
                fi
                if [ $((waited % poll_every)) -eq 0 ]; then
                    local qt_state=""
                    qt_state="$(_macos_loader_playback_state | tr -d '[:space:]' || true)"
                    if [ "$qt_state" = "yes" ]; then
                        seen_playing=1
                    elif [ "$qt_state" = "no" ] && [ "$seen_playing" -eq 1 ]; then
                        break
                    fi
                fi
                waited=$((waited + 1))
            done
            close_macos_loader_video "$loader_vid"
        else
            while kill -0 "$player_pid" 2>/dev/null; do
                if _loader_skip_requested; then
                    kill -9 "$player_pid" 2>/dev/null || true
                    break
                fi
                waited=$((waited + 1))
                # Safety timeout of about 10.5 seconds (video is 10.0s)
                [ "$waited" -ge "$wait_limit" ] && break
            done
            wait "$player_pid" 2>/dev/null || true
        fi
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
