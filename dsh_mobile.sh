#!/usr/bin/env bash
# ==============================================================================
# scripts/dsh_mobile.sh
# Purpose: Start, stop, restart, and monitor DeepSeek Harness (dsh-mobile)
#          Web UI server listening on port 3080 with LAN mobile access
#          (http://192.168.1.11:3080 / http://localhost:3080)
# Cross-Platform: Windows 10/11 (Git Bash, MSYS2, WSL), Linux (Fedora/Debian), macOS
# ==============================================================================

# Prevent MSYS path conversion of Windows / flags (e.g. /c, /F, /T, /PID)
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u 2>/dev/null || echo 1000)}"
export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:$PATH"

# Platform Detection
OS_TYPE="linux"
case "$(uname -s 2>/dev/null)" in
    Darwin*) OS_TYPE="macos" ;;
    CYGWIN*|MINGW*|MSYS*) OS_TYPE="windows" ;;
    FreeBSD*) OS_TYPE="freebsd" ;;
    Linux*)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            OS_TYPE="wsl"
        else
            OS_TYPE="linux"
        fi
        ;;
    *) OS_TYPE="linux" ;;
esac

# Locate DeepSeek Harness directory
if [ -z "${DSH_DIR:-}" ]; then
    if [ -d "X:/DEEPSEEK/deepseek-harness" ]; then
        DSH_DIR="X:/DEEPSEEK/deepseek-harness"
    elif [ -d "/x/DEEPSEEK/deepseek-harness" ]; then
        DSH_DIR="/x/DEEPSEEK/deepseek-harness"
    elif [ -d "C:/DEEPSEEK/deepseek-harness" ]; then
        DSH_DIR="C:/DEEPSEEK/deepseek-harness"
    elif [ -d "/var/home/mplanetarian/beszel-hub/deepseek-harness" ]; then
        DSH_DIR="/var/home/mplanetarian/beszel-hub/deepseek-harness"
    elif [ -d "$HOME/beszel-hub/deepseek-harness" ]; then
        DSH_DIR="$HOME/beszel-hub/deepseek-harness"
    elif [ -d "/var/home/mplanetarian/deepseek-harness" ]; then
        DSH_DIR="/var/home/mplanetarian/deepseek-harness"
    elif [ -d "$HOME/deepseek-harness" ]; then
        DSH_DIR="$HOME/deepseek-harness"
    else
        DSH_DIR="X:/DEEPSEEK/deepseek-harness"
    fi
fi

# Locate Windows Launcher batch script
DSH_START_BAT=""
if [ -f "X:/DEEPSEEK/start_dsh_web.bat" ]; then
    DSH_START_BAT="X:/DEEPSEEK/start_dsh_web.bat"
elif [ -f "/x/DEEPSEEK/start_dsh_web.bat" ]; then
    DSH_START_BAT="/x/DEEPSEEK/start_dsh_web.bat"
elif [ -f "X:/STARTAI/start_dsh_web.bat" ]; then
    DSH_START_BAT="X:/STARTAI/start_dsh_web.bat"
fi

DSH_PORT="${DSH_PORT:-3080}"
DSH_LAN_IP="${DSH_LAN_IP:-}"
if [ -z "$DSH_LAN_IP" ]; then
    if [ "$OS_TYPE" = "windows" ] && command -v ipconfig.exe >/dev/null 2>&1; then
        DSH_LAN_IP=$(ipconfig.exe 2>/dev/null | grep -i "IPv4" | grep -v "127.0.0.1" | head -1 | sed -e 's/.*: *\([0-9.]*\).*/\1/' | tr -d ' \r')
    fi
    if [ -z "$DSH_LAN_IP" ] && command -v ip >/dev/null 2>&1; then
        DSH_LAN_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -1)
    fi
    [ -z "$DSH_LAN_IP" ] && DSH_LAN_IP="192.168.1.11"
fi
DSH_LOCAL_URL="http://localhost:${DSH_PORT}"
DSH_LAN_URL="http://${DSH_LAN_IP}:${DSH_PORT}"

# Preferred Log File
if [ "$OS_TYPE" = "windows" ] && [ -d "X:/DEEPSEEK" ]; then
    LOG_FILE="X:/DEEPSEEK/dsh-mobile.log"
else
    LOG_FILE="/tmp/dsh-mobile.log"
fi

ensure_lan_bridge() {
    if command -v systemctl >/dev/null 2>&1; then
        if ! systemctl --user is-active --quiet dsh-mobile-bridge.service 2>/dev/null; then
            systemctl --user start dsh-mobile-bridge.service 2>/dev/null || true
        fi
    fi
}

is_dsh_running() {
    # 1. Fast HTTP probe with curl (Any response code other than 000 indicates active server)
    if command -v curl >/dev/null 2>&1; then
        local code
        code=$(curl -s -m 2 -o /dev/null -w "%{http_code}" "http://${DSH_LAN_IP}:${DSH_PORT}/" 2>/dev/null || true)
        if [ "$code" != "000" ] && [ -n "$code" ]; then
            return 0
        fi
        code=$(curl -s -m 2 -o /dev/null -w "%{http_code}" "http://127.0.0.1:${DSH_PORT}/" 2>/dev/null || true)
        if [ "$code" != "000" ] && [ -n "$code" ]; then
            return 0
        fi
    fi

    # 2. Windows socket check via netstat.exe
    if [ "$OS_TYPE" = "windows" ] && command -v netstat.exe >/dev/null 2>&1; then
        if netstat.exe -ano 2>/dev/null | grep -E ":${DSH_PORT}\s+.*LISTENING" >/dev/null 2>&1; then
            return 0
        fi
    fi

    # 3. Linux socket check via ss
    if command -v ss >/dev/null 2>&1; then
        if ss -tuln 2>/dev/null | grep -E ":${DSH_PORT}\s" >/dev/null 2>&1; then
            return 0
        fi
    fi

    # 4. macOS / Unix socket check via lsof
    if command -v lsof >/dev/null 2>&1; then
        if lsof -iTCP:"${DSH_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
    fi

    # 5. Process check via pgrep
    if command -v pgrep >/dev/null 2>&1; then
        if pgrep -f "dsh.*web|apps/cli/src/bin\.ts.*web" >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

get_dsh_pids() {
    local pids=""

    # 1. Windows netstat.exe listening PIDs
    if [ "$OS_TYPE" = "windows" ] && command -v netstat.exe >/dev/null 2>&1; then
        pids=$(netstat.exe -ano 2>/dev/null | grep -E ":${DSH_PORT}\s+.*LISTENING" | sed -e 's/.*LISTENING *//' | tr -d '\r' | sort -u | tr '\n' ' ')
    fi

    # 2. Windows powershell process fallback if port not yet bound
    if [ -z "$pids" ] && [ "$OS_TYPE" = "windows" ] && command -v powershell.exe >/dev/null 2>&1; then
        pids=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name = 'node.exe'\" | Where-Object { \$_.CommandLine -like '*apps/cli/src/bin.ts*web*' -or \$_.CommandLine -like '*dsh*web*' }).ProcessId" 2>/dev/null | tr -d '\r' | tr '\n' ' ')
    fi

    # 3. pgrep process check
    if [ -z "$pids" ] && command -v pgrep >/dev/null 2>&1; then
        pids=$(pgrep -f "dsh.*web|apps/cli/src/bin\.ts.*web" 2>/dev/null | tr '\n' ' ')
    fi

    # 4. Unix lsof port check
    if [ -z "$pids" ] && command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti:"${DSH_PORT}" 2>/dev/null | tr '\n' ' ')
    fi

    echo "$pids"
}

start_dsh_window() {
    echo -e "\n${BOLD}${BLUE}=== LAUNCHING DSH-MOBILE (TERMINAL WINDOW) ===${NC}"
    ensure_lan_bridge
    if is_dsh_running; then
        local pids
        pids=$(get_dsh_pids)
        echo -e "${GREEN}✓ dsh-mobile is already running (PID: ${pids% }).${NC}"
        echo -e "  • Local URL:  ${BOLD}${CYAN}${DSH_LOCAL_URL}${NC}"
        echo -e "  • Mobile LAN: ${BOLD}${GREEN}${DSH_LAN_URL}${NC}"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "DeepSeek Harness" -i "dialog-information" "DeepSeek Harness" "dsh-mobile is already running (${DSH_LAN_URL})." 2>/dev/null || true
        fi
        return 0
    fi

    if [ ! -d "$DSH_DIR" ]; then
        echo -e "${RED}Error: DeepSeek Harness directory not found at '$DSH_DIR'!${NC}"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "DeepSeek Harness" -i "dialog-error" "DeepSeek Harness" "Directory not found at $DSH_DIR" 2>/dev/null || true
        fi
        return 1
    fi

    echo -e "Starting dsh web on port ${DSH_PORT} with LAN trust for ${DSH_LAN_IP}..."
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -a "DeepSeek Harness" -i "utilities-terminal" "DeepSeek Harness" "Launching dsh-mobile on ${DSH_LAN_URL}..." 2>/dev/null || true
    fi

    local TITLE="DeepSeek Harness (dsh-mobile)"

    if [ "$OS_TYPE" = "windows" ]; then
        local win_dsh_dir
        win_dsh_dir=$(cygpath -w "$DSH_DIR" 2>/dev/null || echo "$DSH_DIR")
        if [ -n "$DSH_START_BAT" ] && [ -f "$DSH_START_BAT" ]; then
            local bat_path
            bat_path=$(cygpath -w "$DSH_START_BAT" 2>/dev/null || echo "$DSH_START_BAT")
            cmd.exe /c start "$TITLE" "$bat_path" >/dev/null 2>&1 &
        else
            cmd.exe /c start "$TITLE" cmd.exe /k "set DSH_HOME=$win_dsh_dir && set HF_HOME=X:\DeepSeekHarness\cache\huggingface && set TORCH_HOME=X:\DeepSeekHarness\cache\torch && cd /d $win_dsh_dir && node --import tsx/esm apps/cli/src/bin.ts web --host $DSH_LAN_IP --port $DSH_PORT" >/dev/null 2>&1 &
        fi
    elif command -v konsole >/dev/null 2>&1; then
        local CMD="cd \"$DSH_DIR\" && pnpm dsh web --trusted-host ${DSH_LAN_IP}:${DSH_PORT} --trusted-host ${DSH_LAN_IP} --no-open; echo ''; echo 'dsh web finished. Press [Enter] to close...'; read -r"
        konsole --new-tab -p tabtitle="$TITLE" --workdir "$DSH_DIR" -e bash -c "$CMD" &
    elif command -v xdg-terminal-exec >/dev/null 2>&1; then
        local CMD="cd \"$DSH_DIR\" && pnpm dsh web --trusted-host ${DSH_LAN_IP}:${DSH_PORT} --trusted-host ${DSH_LAN_IP} --no-open; echo ''; echo 'dsh web finished. Press [Enter] to close...'; read -r"
        nohup xdg-terminal-exec bash -c "$CMD" >/dev/null 2>&1 &
    elif command -v gnome-terminal >/dev/null 2>&1; then
        local CMD="cd \"$DSH_DIR\" && pnpm dsh web --trusted-host ${DSH_LAN_IP}:${DSH_PORT} --trusted-host ${DSH_LAN_IP} --no-open; echo ''; echo 'dsh web finished. Press [Enter] to close...'; read -r"
        nohup gnome-terminal --title="$TITLE" --working-directory="$DSH_DIR" -- bash -c "$CMD" >/dev/null 2>&1 &
    elif command -v xterm >/dev/null 2>&1; then
        local CMD="cd \"$DSH_DIR\" && pnpm dsh web --trusted-host ${DSH_LAN_IP}:${DSH_PORT} --trusted-host ${DSH_LAN_IP} --no-open; echo ''; echo 'dsh web finished. Press [Enter] to close...'; read -r"
        nohup xterm -T "$TITLE" -e bash -c "cd \"$DSH_DIR\" && $CMD" >/dev/null 2>&1 &
    else
        start_dsh_bg
        return $?
    fi

    echo -e "${GREEN}✓ Launch command dispatched to new terminal.${NC}"
    echo -e "Waiting for DeepSeek Harness port ${DSH_PORT} to listen..."
    local ready=false
    for _ in {1..20}; do
        if is_dsh_running; then
            ready=true
            break
        fi
        sleep 0.5
    done

    if [ "$ready" = "true" ]; then
        local pids
        pids=$(get_dsh_pids)
        echo -e "${BOLD}${GREEN}✓ dsh-mobile is online and listening!${NC}"
        echo -e "  • Status:     ${GREEN}RUNNING${NC}"
        echo -e "  • PID(s):     ${YELLOW}${pids% }${NC}"
        echo -e "  • Local URL:  ${BOLD}${CYAN}${DSH_LOCAL_URL}${NC}"
        echo -e "  • Mobile LAN: ${BOLD}${GREEN}${DSH_LAN_URL}${NC}"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "DeepSeek Harness" -i "dialog-ok" "DeepSeek Harness" "✓ dsh-mobile is live on ${DSH_LAN_URL}" 2>/dev/null || true
        fi
        return 0
    else
        echo -e "${YELLOW}Terminal window launched. Web server initializing on ${DSH_LAN_URL}...${NC}"
        return 0
    fi
}

start_dsh_bg() {
    echo -e "\n${BOLD}${BLUE}=== STARTING DSH-MOBILE (BACKGROUND DAEMON) ===${NC}"
    ensure_lan_bridge
    if is_dsh_running; then
        local pids
        pids=$(get_dsh_pids)
        echo -e "${GREEN}✓ dsh-mobile is already running (PID: ${pids% }).${NC}"
        echo -e "  • Local URL:  ${BOLD}${CYAN}${DSH_LOCAL_URL}${NC}"
        echo -e "  • Mobile LAN: ${BOLD}${GREEN}${DSH_LAN_URL}${NC}"
        return 0
    fi

    if [ ! -d "$DSH_DIR" ]; then
        echo -e "${RED}Error: DeepSeek Harness directory not found at '$DSH_DIR'!${NC}"
        return 1
    fi

    local log_dir
    log_dir=$(dirname "$LOG_FILE")
    [ -d "$log_dir" ] || mkdir -p "$log_dir"

    echo -e "Launching dsh web in background..."
    if [ "$OS_TYPE" = "windows" ]; then
        export DSH_HOME="$(cygpath -w "$DSH_DIR" 2>/dev/null || echo "$DSH_DIR")"
        export HF_HOME="X:\DeepSeekHarness\cache\huggingface"
        export TORCH_HOME="X:\DeepSeekHarness\cache\torch"
        [ -d "X:/DeepSeekHarness/cache" ] || mkdir -p "X:/DeepSeekHarness/cache"
        (cd "$DSH_DIR" && nohup node --import tsx/esm apps/cli/src/bin.ts web --host "${DSH_LAN_IP}" --port "${DSH_PORT}" --no-open >"$LOG_FILE" 2>&1 &)
    else
        (cd "$DSH_DIR" && nohup pnpm dsh web --trusted-host "${DSH_LAN_IP}:${DSH_PORT}" --trusted-host "${DSH_LAN_IP}" --no-open >"$LOG_FILE" 2>&1 &)
    fi

    echo -e "Waiting for server to listen on port ${DSH_PORT}..."
    local ready=false
    for _ in {1..20}; do
        if is_dsh_running; then
            ready=true
            break
        fi
        sleep 0.5
    done

    if [ "$ready" = "true" ]; then
        local pids
        pids=$(get_dsh_pids)
        echo -e "${BOLD}${GREEN}✓ dsh-mobile successfully started!${NC}"
        echo -e "  • Status:     ${GREEN}RUNNING${NC}"
        echo -e "  • PID(s):     ${YELLOW}${pids% }${NC}"
        echo -e "  • Local URL:  ${BOLD}${CYAN}${DSH_LOCAL_URL}${NC}"
        echo -e "  • Mobile LAN: ${BOLD}${GREEN}${DSH_LAN_URL}${NC}"
        echo -e "  • Log File:   ${LOG_FILE}"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "DeepSeek Harness" -i "dialog-ok" "DeepSeek Harness" "✓ dsh-mobile is live on ${DSH_LAN_URL}" 2>/dev/null || true
        fi
        return 0
    else
        echo -e "${RED}Warning: dsh-mobile did not bind port ${DSH_PORT} within 10s.${NC}"
        echo -e "${YELLOW}Check logs with: tail -n 20 ${LOG_FILE}${NC}"
        return 1
    fi
}

stop_dsh() {
    echo -e "\n${BOLD}${BLUE}=== STOPPING DSH-MOBILE ===${NC}"
    local pids
    pids=$(get_dsh_pids)
    if [ -z "$pids" ] && ! is_dsh_running; then
        echo -e "${YELLOW}dsh-mobile is not currently running.${NC}"
        return 0
    fi

    echo -e "Stopping dsh-mobile processes (PID: ${YELLOW}${pids% }${NC})..."

    if [ "$OS_TYPE" = "windows" ]; then
        for pid in $pids; do
            [ -n "$pid" ] && taskkill.exe //F //T //PID "$pid" 2>/dev/null || true
        done
        sleep 1
        local rem_pids
        rem_pids=$(get_dsh_pids)
        for pid in $rem_pids; do
            [ -n "$pid" ] && taskkill.exe //F //T //PID "$pid" 2>/dev/null || true
        done
        # Clean up any lingering node instances running apps/cli/src/bin.ts web
        if command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name = 'node.exe'\" | Where-Object { \$_.CommandLine -like '*apps/cli/src/bin.ts*web*' -or \$_.CommandLine -like '*dsh*web*' }).ProcessId | ForEach-Object { Stop-Process -Id \$_ -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1 || true
        fi
    else
        for pid in $pids; do
            kill -TERM "$pid" 2>/dev/null || true
        done

        local stopped=false
        for _ in {1..10}; do
            if ! is_dsh_running; then
                stopped=true
                break
            fi
            sleep 0.5
        done

        if [ "$stopped" = "false" ]; then
            echo -e "${YELLOW}Forcing termination with SIGKILL...${NC}"
            local rem_pids
            rem_pids=$(get_dsh_pids)
            for pid in $rem_pids; do
                kill -9 "$pid" 2>/dev/null || true
            done
            if command -v fuser >/dev/null 2>&1; then
                fuser -k "${DSH_PORT}/tcp" >/dev/null 2>&1 || true
            fi
            sleep 0.5
        fi
    fi

    sleep 0.5
    if ! is_dsh_running; then
        echo -e "${BOLD}${GREEN}✓ dsh-mobile has been stopped successfully.${NC}"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "DeepSeek Harness" -i "dialog-information" "DeepSeek Harness" "dsh-mobile has been stopped." 2>/dev/null || true
        fi
        return 0
    else
        echo -e "${RED}Error: Failed to stop some dsh-mobile processes.${NC}"
        return 1
    fi
}

restart_dsh() {
    echo -e "\n${BOLD}${BLUE}=== RESTARTING DSH-MOBILE ===${NC}"
    stop_dsh
    sleep 1
    start_dsh_window
}

open_dsh_browser() {
    echo -e "\n${BOLD}${BLUE}=== OPENING DSH-MOBILE WEB UI ===${NC}"
    if ! is_dsh_running; then
        echo -e "${YELLOW}dsh-mobile is not currently running. Starting it now...${NC}"
        start_dsh_window
        sleep 2
    fi

    local target_url="${DSH_LAN_URL}"
    local check_logs=("$LOG_FILE" "X:/DEEPSEEK/dsh-mobile.log" "/tmp/dsh-mobile.log")
    for lf in "${check_logs[@]}"; do
        if [ -f "$lf" ]; then
            local token_url
            token_url=$(grep -oE "http[s]?://${DSH_LAN_IP}:${DSH_PORT}/\?token=[A-Za-z0-9_-]+" "$lf" 2>/dev/null | tail -1 || true)
            if [ -n "$token_url" ]; then
                target_url="$token_url"
                break
            fi
        fi
    done

    echo -e "Opening in browser: ${BOLD}${GREEN}${target_url}${NC}"
    if [ "$OS_TYPE" = "windows" ]; then
        cmd.exe /c start "" "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    elif command -v google-chrome >/dev/null 2>&1; then
        google-chrome "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    elif command -v firefox >/dev/null 2>&1; then
        firefox "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    elif [ "$OS_TYPE" = "macos" ]; then
        open "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    else
        echo -e "Please open manually in your browser: ${BOLD}${CYAN}${target_url}${NC}"
    fi
}

show_status() {
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}        DEEPSEEK HARNESS (DSH-MOBILE) SERVER MANAGER                  ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo ""
    local pids
    pids=$(get_dsh_pids)
    if is_dsh_running; then
        echo -e "  Server Status:  ${BOLD}${GREEN}● RUNNING${NC} (PID: ${YELLOW}${pids% }${NC})"
        echo -e "  Local URL:      ${BOLD}${CYAN}${DSH_LOCAL_URL}${NC}"
        echo -e "  Mobile LAN URL: ${BOLD}${GREEN}${DSH_LAN_URL}${NC}  ${DIM}(LAN access active)${NC}"
        echo -e "  Listen Port:    ${CYAN}${DSH_PORT}/tcp${NC}"
    else
        echo -e "  Server Status:  ${BOLD}${RED}○ STOPPED${NC}"
        echo -e "  Target LAN URL: ${DIM}${DSH_LAN_URL}${NC}"
    fi
    echo -e "  Harness Dir:    ${CYAN}${DSH_DIR}${NC}"
    if [ -d "$DSH_DIR" ]; then
        local dsh_git=""
        if [ -d "$DSH_DIR/.git" ]; then
            dsh_git=$(git -C "$DSH_DIR" log -1 --format="%h (%s)" 2>/dev/null || true)
            [ -n "$dsh_git" ] && echo -e "  Git Version:    ${DIM}${dsh_git}${NC}"
        fi
    fi
    if [ -n "$DSH_START_BAT" ] && [ -f "$DSH_START_BAT" ]; then
        echo -e "  Launcher Batch: ${CYAN}${DSH_START_BAT}${NC}"
    fi
    echo ""
}

view_logs() {
    echo -e "\n${BOLD}${BLUE}=== DSH-MOBILE LOG FILE ===${NC}\n"
    local found_log=""
    if [ -f "$LOG_FILE" ]; then
        found_log="$LOG_FILE"
    elif [ -f "X:/DEEPSEEK/dsh-mobile.log" ]; then
        found_log="X:/DEEPSEEK/dsh-mobile.log"
    elif [ -f "/tmp/dsh-mobile.log" ]; then
        found_log="/tmp/dsh-mobile.log"
    fi

    if [ -n "$found_log" ]; then
        echo -e "Log file: ${found_log} (Last 50 lines):\n"
        tail -n 50 "$found_log"
    else
        echo -e "Log file does not exist yet (server may have been launched in a dedicated terminal window)."
        echo -e "Target log path: ${LOG_FILE}"
    fi
    echo ""
    read -r -p "Press Enter to return..."
}

interactive_menu() {
    while true; do
        clear
        show_status
        echo -e "${BOLD}${MAGENTA}----------------------------------------------------------------------${NC}"
        echo -e "${BOLD}Select a DeepSeek Harness operation:${NC}\n"
        echo -e "  ${BOLD}${CYAN} 1)${NC} Launch dsh-mobile in ${BOLD}${GREEN}Terminal Window / Tab${NC} (Standard)"
        echo -e "  ${BOLD}${CYAN} 2)${NC} Launch dsh-mobile in ${BOLD}${YELLOW}Background Daemon${NC} (Log to file)"
        echo -e "  ${BOLD}${CYAN} 3)${NC} Open dsh-mobile Web UI in ${BOLD}${CYAN}Browser${NC} (${DSH_LAN_URL})"
        echo -e "  ${BOLD}${CYAN} 4)${NC} Stop Running dsh-mobile Server"
        echo -e "  ${BOLD}${CYAN} 5)${NC} Restart dsh-mobile Server"
        echo -e "  ${BOLD}${CYAN} 6)${NC} View Server Log File (${LOG_FILE})"
        echo -e "  ${BOLD}${CYAN} 7)${NC} Return to Previous Menu\n"
        read -r -p "Enter choice [1-7, or q to return]: " d_choice

        case "$d_choice" in
            1)
                start_dsh_window
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            2)
                start_dsh_bg
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            3)
                open_dsh_browser
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            4)
                stop_dsh
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            5)
                restart_dsh
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            6)
                view_logs
                ;;
            7|[qQ])
                return 0
                ;;
            *)
                echo -e "\n${RED}Invalid option!${NC}"
                sleep 1
                ;;
        esac
    done
}

case "${1:-}" in
    start|launch|window|term)
        start_dsh_window
        ;;
    start-bg|bg|daemon)
        start_dsh_bg
        ;;
    stop)
        stop_dsh
        ;;
    restart)
        restart_dsh
        ;;
    web|browser|open|dashboard)
        open_dsh_browser
        ;;
    status)
        show_status
        ;;
    logs)
        view_logs
        ;;
    "")
        if [ ! -t 0 ] || [ -z "${TERM:-}" ]; then
            start_dsh_window
        else
            interactive_menu
        fi
        ;;
    *)
        echo "Usage: $(basename "$0") {start|start-bg|stop|restart|web|status|logs}"
        exit 1
        ;;
esac
