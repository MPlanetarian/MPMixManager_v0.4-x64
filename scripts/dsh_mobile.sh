#!/usr/bin/env bash
# ==============================================================================
# scripts/dsh_mobile.sh
# Purpose: Start, stop, restart, and monitor DeepSeek Harness (dsh-mobile)
#          Web UI server listening on port 3080 with LAN mobile access
#          (http://192.168.1.11:3080 / http://localhost:3080)
# Cross-Platform: Windows 10/11 (Git Bash, MSYS2, WSL), Linux (Fedora/Debian), macOS
# ==============================================================================

#!/bin/bash

# Configuration
DSH_DIR="/path/to/dsh-mobile"
LOG_FILE="$DSH_DIR/dsh-mobile.log"
DSH_PORT=8080
DSH_LAN_IP=$(hostname -I | awk '{print $1}')
DSH_LAN_URL="http://$DSH_LAN_IP:$DSH_PORT/?token="
DSH_LOCAL_URL="http://localhost:$DSH_PORT/?token="
DSH_START_BAT="$DSH_DIR/start-dsh.bat"

# Colors
BOLD='\e[1m'
GREEN='\e[32m'
YELLOW='\e[33m'
CYAN='\e[36m'
MAGENTA='\e[35m'
RED='\e[31m'
DIM='\e[2m'
NC='\e[0m'

# Functions
get_dsh_pids() { pgrep -f "dsh-mobile" || true }
is_dsh_running() { [ -n "$(get_dsh_pids)" ] }
stop_dsh() {
    local pids; pids=$(get_dsh_pids)
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null
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
    else
        echo -e "${YELLOW}dsh-mobile is not running.${NC}"
        return 0
    fi
}
start_dsh_bg() {
    if is_dsh_running; then
        echo -e "${YELLOW}dsh-mobile is already running.${NC}"
    else
        nohup "$DSH_START_BAT" >>"$LOG_FILE" 2>&1 &
        echo -e "${BOLD}${GREEN}✓ dsh-mobile has been started in the background.${NC}"
    fi
}
start_dsh_window() {
    if is_dsh_running; then
        echo -e "${YELLOW}dsh-mobile is already running.${NC}"
    else
        "$DSH_START_BAT"
    fi
}
open_dsh_browser() {
    local url="${DSH_LAN_URL}"
    if [ -f "$LOG_FILE" ]; then
        url=$(grep -oE "http[s]?://$DSH_LAN_IP:$DSH_PORT/\?token=[A-Za-z0-9_-]+" "$LOG_FILE" 2>/dev/null | tail -1 || true)
    fi
    echo -e "Opening in browser: ${BOLD}${GREEN}${url}${NC}"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    elif command -v google-chrome >/dev/null 2>&1; then
        google-chrome "$url" >/dev/null 2>&1 &
    elif command -v firefox >/dev/null 2>&1; then
        firefox "$url" >/dev/null 2>&1 &
    elif [ -n "$BROWSER" ]; then
        $BROWSER "$url" >/dev/null 2>&1 &
    else
        echo -e "Please open manually in your browser: ${BOLD}${CYAN}${url}${NC}"
    fi
}
show_status() {
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}        DEEPSEEK HARNESS (DSH-MOBILE) SERVER MANAGER                  ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo ""
    if is_dsh_running; then
        echo -e "  Server Status:  ${BOLD}${GREEN}● RUNNING${NC} (PID: ${YELLOW}$(get_dsh_pids)${NC})"
        echo -e "  Local URL:      ${BOLD}${CYAN}${DSH_LOCAL_URL}${NC}"
        echo -e "  Mobile LAN URL: ${BOLD}${GREEN}${DSH_LAN_URL}${NC}  ${DIM}(LAN access active)${NC}"
        echo -e "  Listen Port:    ${CYAN}${DSH_PORT}/tcp${NC}"
    else
        echo -e "  Server Status:  ${BOLD}${RED}○ STOPPED${NC}"
        echo -e "  Target LAN URL: ${DIM}${DSH_LAN_URL}${NC}"
    fi
    echo -e "  Harness Dir:    ${CYAN}${DSH_DIR}${NC}"
    if [ -d "$DSH_DIR/.git" ]; then
        echo -e "  Git Version:    ${DIM}$(git -C "$DSH_DIR" log -1 --format="%h (%s)" 2>/dev/null || true)${NC}"
    fi
    if [ -f "$DSH_START_BAT" ]; then
        echo -e "  Launcher Batch: ${CYAN}${DSH_START_BAT}${NC}"
    fi
    echo ""
}
view_logs() {
    echo -e "\n${BOLD}${BLUE}=== DSH-MOBILE LOG FILE ===${NC}\n"
    local log_file="${LOG_FILE:-X:/DEEPSEEK/dsh-mobile.log}"
    if [ -f "$log_file" ]; then
        echo -e "Log file: ${log_file} (Last 50 lines):\n"
        tail -n 50 "$log_file"
    else
        echo -e "Log file does not exist yet (server may have been launched in a dedicated terminal window)."
        echo -e "Target log path: ${log_file}"
    fi
    echo ""
    [ -t 0 ] && read -r -p "Press Enter to return..."
    return 0
}

# Main
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
        stop_dsh && start_dsh_bg
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
                        ;;
                    2)
                        start_dsh_bg
                        ;;
                    3)
                        open_dsh_browser
                        ;;
                    4)
                        stop_dsh
                        ;;
                    5)
                        stop_dsh && start_dsh_bg
                        ;;
                    6)
                        view_logs
                        ;;
                    7|[qQ])
                        break
                        ;;
                    *)
                        echo -e "\n${RED}Invalid option!${NC}"
                        ;;
                esac
                [ "$d_choice" -ge 1 ] && [ "$d_choice" -le 7 ] && read -r -p "Press Enter to continue..."
            done
        fi
        ;;
    *)
        echo "Usage: $(basename "$0") {start|start-bg|stop|restart|web|status|logs}"
        exit 1
        ;;
esac