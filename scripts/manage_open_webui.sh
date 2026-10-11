#!/usr/bin/env bash
# ==============================================================================
# scripts/manage_open_webui.sh
# Purpose: Start, stop, restart, open browser, and monitor Open WebUI
#          Web Chat AI Harness
#          Supports native Windows (conda env / start_openwebui.bat :8080)
#          and Linux (systemd / standalone :42004)
# ==============================================================================

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

# Operating System Detection
if [ -z "${OS_TYPE:-}" ]; then
    OS_TYPE="linux"
    case "$(uname -s)" in
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
fi

if [ "$OS_TYPE" = "windows" ]; then
    DEFAULT_PORT="8080"
else
    DEFAULT_PORT="42004"
fi
OPEN_WEBUI_HOST="${OPEN_WEBUI_HOST:-0.0.0.0}"
OPEN_WEBUI_PORT="${OPEN_WEBUI_PORT:-$DEFAULT_PORT}"
OPEN_WEBUI_PATH="${OPEN_WEBUI_PATH:-/auth?redirect=%2F}"
OPEN_WEBUI_LOCAL_URL="http://127.0.0.1:${OPEN_WEBUI_PORT}${OPEN_WEBUI_PATH}"
OPEN_WEBUI_SERVICE="open-webui.service"
OPEN_WEBUI_START_BAT=""
CONDA_BAT=""

if [ "$OS_TYPE" = "windows" ]; then
    for b_cand in "X:/OPENWEBUI/start_openwebui.bat" "X:\OPENWEBUI\start_openwebui.bat" "X:/STARTAI/start_openwebui.bat"; do
        if [ -f "$b_cand" ]; then
            OPEN_WEBUI_START_BAT="$b_cand"
            break
        fi
    done

    for c_cand in "C:/ProgramData/anaconda3/condabin/conda.bat" "C:\ProgramData\anaconda3\condabin\conda.bat" "$USERPROFILE/anaconda3/condabin/conda.bat"; do
        if [ -f "$c_cand" ]; then
            CONDA_BAT="$c_cand"
            break
        fi
    done

    OPEN_WEBUI_BIN="X:/OPENWEBUI/env/Scripts/open-webui.exe"
    OPEN_WEBUI_DIR="X:/OPENWEBUI"
    OPEN_WEBUI_DATA="X:/OPENWEBUI/data"
    LOG_FILE="X:/OPENWEBUI/open-webui.log"
else
    OPEN_WEBUI_BIN="${OPEN_WEBUI_BIN:-/home/mplanetarian/pinokio/api/open-webui/app/env/bin/open-webui}"
    OPEN_WEBUI_DIR="${OPEN_WEBUI_DIR:-/home/mplanetarian/pinokio/api/open-webui/app}"
    OPEN_WEBUI_DATA="${OPEN_WEBUI_DIR}/data"
    LOG_FILE="/tmp/open-webui.log"
fi

OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_API_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:${OLLAMA_PORT}}"

get_lan_ip() {
    local ip=""
    if [ "$OS_TYPE" = "windows" ] && command -v ipconfig.exe >/dev/null 2>&1; then
        ip=$(ipconfig.exe 2>/dev/null | grep -i "IPv4" | head -n 1 | awk -F': ' '{print $2}' | tr -d '\r ')
    fi
    if [ -z "$ip" ]; then
        ip=$(ip -4 addr show wlp2s0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || hostname -I 2>/dev/null | awk '{print $1}')
    fi
    echo "$ip"
}

update_active_port() {
    if curl -s -I --connect-timeout 1 "http://127.0.0.1:${OPEN_WEBUI_PORT}/" 2>/dev/null | grep -qi "HTTP/"; then
        return 0
    fi
    for p in 8080 42004; do
        if [ "$p" != "$OPEN_WEBUI_PORT" ] && curl -s -I --connect-timeout 1 "http://127.0.0.1:${p}/" 2>/dev/null | grep -qi "HTTP/"; then
            OPEN_WEBUI_PORT="$p"
            OPEN_WEBUI_LOCAL_URL="http://127.0.0.1:${OPEN_WEBUI_PORT}${OPEN_WEBUI_PATH}"
            return 0
        fi
    done
    return 1
}

is_webui_running() {
    if update_active_port; then
        return 0
    fi

    if [ "$OS_TYPE" = "windows" ]; then
        if command -v netstat.exe >/dev/null 2>&1; then
            if netstat.exe -ano 2>/dev/null | grep -E ":${OPEN_WEBUI_PORT}\s+.*LISTENING" >/dev/null 2>&1; then
                return 0
            fi
            for p in 8080 42004; do
                if netstat.exe -ano 2>/dev/null | grep -E ":${p}\s+.*LISTENING" >/dev/null 2>&1; then
                    OPEN_WEBUI_PORT="$p"
                    OPEN_WEBUI_LOCAL_URL="http://127.0.0.1:${OPEN_WEBUI_PORT}${OPEN_WEBUI_PATH}"
                    return 0
                fi
            done
        fi
        if command -v tasklist.exe >/dev/null 2>&1 && tasklist.exe //FI "IMAGENAME eq open-webui.exe" 2>/dev/null | grep -qi "open-webui.exe"; then
            return 0
        fi
    else
        if systemctl --user is-active --quiet "$OPEN_WEBUI_SERVICE" 2>/dev/null; then
            return 0
        elif pgrep -f "open-webui serve" >/dev/null 2>&1; then
            return 0
        elif ss -tuln 2>/dev/null | grep -q ":${OPEN_WEBUI_PORT} "; then
            return 0
        fi
    fi
    return 1
}

get_webui_pids() {
    local pids=""
    if [ "$OS_TYPE" = "windows" ]; then
        if command -v netstat.exe >/dev/null 2>&1; then
            pids=$(netstat.exe -ano 2>/dev/null | grep -E ":${OPEN_WEBUI_PORT}\s+.*LISTENING" | awk '{print $5}' | sort -u | tr '\n' ' ')
        fi
        if [ -z "$pids" ] && command -v tasklist.exe >/dev/null 2>&1; then
            pids=$(tasklist.exe //FI "IMAGENAME eq open-webui.exe" //FO CSV //NH 2>/dev/null | awk -F'","' '{print $2}' | tr -d '"\r ' | tr '\n' ' ')
        fi
    else
        pids=$(pgrep -f "open-webui serve" 2>/dev/null | tr '\n' ' ')
        if [ -z "$pids" ] && systemctl --user is-active --quiet "$OPEN_WEBUI_SERVICE" 2>/dev/null; then
            pids=$(systemctl --user show "$OPEN_WEBUI_SERVICE" -p MainPID 2>/dev/null | cut -d'=' -f2)
            [ "$pids" = "0" ] && pids=""
        fi
    fi
    echo "$pids"
}

is_ollama_running() {
    if curl -s --connect-timeout 1 "${OLLAMA_API_URL}/" 2>/dev/null | grep -qi "Ollama is running"; then
        return 0
    elif [ "$OS_TYPE" = "windows" ]; then
        if command -v netstat.exe >/dev/null 2>&1 && netstat.exe -ano 2>/dev/null | grep -E ":${OLLAMA_PORT}\s+.*LISTENING" >/dev/null 2>&1; then
            return 0
        fi
    elif pgrep -f "ollama serve" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

open_webui_browser() {
    update_active_port || true
    local target_url="$OPEN_WEBUI_LOCAL_URL"
    echo -e "\n${BOLD}${CYAN}Opening Open WebUI in browser:${NC} ${BOLD}${YELLOW}${target_url}${NC}\n"
    if [ "$OS_TYPE" = "windows" ]; then
        cmd.exe /c start "" "$target_url" >/dev/null 2>&1 &
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    elif command -v google-chrome >/dev/null 2>&1; then
        google-chrome "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    elif command -v firefox >/dev/null 2>&1; then
        firefox "$target_url" >/dev/null 2>&1 &
        disown 2>/dev/null || true
    else
        echo -e "${YELLOW}Please open the URL in your browser: ${target_url}${NC}"
    fi
}

start_webui_bg() {
    echo -e "\n${BOLD}${BLUE}=== STARTING OPEN WEBUI (BACKGROUND SERVICE) ===${NC}"
    if is_webui_running; then
        local pids
        pids=$(get_webui_pids)
        echo -e "${GREEN}✓ Open WebUI server is already running (PID: ${pids% }, URL: ${OPEN_WEBUI_LOCAL_URL}).${NC}"
        return 0
    fi

    # Ensure backend Ollama is running if possible
    if ! is_ollama_running; then
        echo -e "  ${YELLOW}Notice: Ollama backend is not detected. Starting Ollama in background...${NC}"
        local olm_script=""
        if [ -f "$(dirname "${BASH_SOURCE[0]}")/manage_ollama.sh" ]; then
            olm_script="$(dirname "${BASH_SOURCE[0]}")/manage_ollama.sh"
        elif [ -f "scripts/manage_ollama.sh" ]; then
            olm_script="scripts/manage_ollama.sh"
        fi
        if [ -n "$olm_script" ]; then
            bash "$olm_script" start >/dev/null 2>&1 || true
        fi
    fi

    if [ "$OS_TYPE" = "windows" ]; then
        local bg_bat="X:/OPENWEBUI/start_openwebui_bg.bat"
        local win_conda win_env win_data win_log
        win_conda="$(cygpath -w "$CONDA_BAT" 2>/dev/null || echo "$CONDA_BAT")"
        win_env="X:\OPENWEBUI\env"
        win_data="X:\OPENWEBUI\data"
        win_log="$(cygpath -w "$LOG_FILE" 2>/dev/null || echo "$LOG_FILE")"

        [ -d "X:/OPENWEBUI/data" ] || mkdir -p "X:/OPENWEBUI/data" 2>/dev/null || true

        cat << EOFBAT > "$bg_bat"
@echo off
if exist "${win_conda}" call "${win_conda}" activate "${win_env}"
set DATA_DIR=${win_data}
set OLLAMA_BASE_URL=${OLLAMA_API_URL}
set WEBUI_HOST=${OPEN_WEBUI_HOST}
set WEBUI_PORT=${OPEN_WEBUI_PORT}
cd /d "X:\OPENWEBUI"
open-webui serve --host ${OPEN_WEBUI_HOST} --port ${OPEN_WEBUI_PORT} > "${win_log}" 2>&1
EOFBAT

        echo -e "Launching Open WebUI standalone daemon on Windows [listening on ${OPEN_WEBUI_HOST}:${OPEN_WEBUI_PORT}]..."
        if command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -Command "([wmiclass]'win32_process').Create('cmd.exe /c X:\OPENWEBUI\start_openwebui_bg.bat')" >/dev/null 2>&1 &
        else
            cmd.exe /c start /b "" "X:\OPENWEBUI\start_openwebui_bg.bat" >/dev/null 2>&1 &
        fi
    else
        if systemctl --user list-unit-files "$OPEN_WEBUI_SERVICE" >/dev/null 2>&1; then
            echo -e "Starting Open WebUI via systemd user service (${OPEN_WEBUI_SERVICE})..."
            systemctl --user start "$OPEN_WEBUI_SERVICE" 2>/dev/null || true
        elif [ -x "$OPEN_WEBUI_BIN" ]; then
            echo -e "Starting Open WebUI standalone daemon..."
            mkdir -p "$OPEN_WEBUI_DATA" 2>/dev/null || true
            nohup env DATA_DIR="$OPEN_WEBUI_DATA" OLLAMA_BASE_URL="$OLLAMA_API_URL" "$OPEN_WEBUI_BIN" serve --host "$OPEN_WEBUI_HOST" --port "$OPEN_WEBUI_PORT" >"$LOG_FILE" 2>&1 &
        else
            echo -e "${RED}Error: Neither systemd service '$OPEN_WEBUI_SERVICE' nor executable '$OPEN_WEBUI_BIN' found!${NC}"
            return 1
        fi
    fi

    echo -e "Waiting for Open WebUI endpoint to become responsive..."
    local ready=false
    for _ in {1..30}; do
        if update_active_port; then
            ready=true
            break
        elif curl -s -I --connect-timeout 1 "http://127.0.0.1:${OPEN_WEBUI_PORT}/" 2>/dev/null | grep -qi "HTTP/"; then
            ready=true
            break
        fi
        sleep 0.5
    done

    local LAN_IP
    LAN_IP=$(get_lan_ip)

    if [ "$ready" = "true" ]; then
        local pids
        pids=$(get_webui_pids)
        echo -e "${BOLD}${GREEN}✓ Open WebUI server successfully started!${NC}"
        echo -e "  • Status:       ${GREEN}RUNNING${NC}"
        echo -e "  • Local Web UI: ${BOLD}${CYAN}${OPEN_WEBUI_LOCAL_URL}${NC}"
        [ -n "$LAN_IP" ] && echo -e "  • LAN Endpoint: ${BOLD}${CYAN}http://${LAN_IP}:${OPEN_WEBUI_PORT}${OPEN_WEBUI_PATH}${NC}"
        echo -e "  • PID(s):       ${YELLOW}${pids% }${NC}"
        echo -e "  • Log File:     ${LOG_FILE}"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "Open WebUI" -i "dialog-ok" "Open WebUI" "✓ Open WebUI is live on http://${LAN_IP:-127.0.0.1}:${OPEN_WEBUI_PORT}" 2>/dev/null || true
        fi
        return 0
    else
        echo -e "${RED}Warning: Open WebUI did not respond on http://127.0.0.1:${OPEN_WEBUI_PORT} within 15s.${NC}"
        echo -e "${YELLOW}Check service logs with option 6 or tail -n 25 ${LOG_FILE}${NC}"
        return 1
    fi
}

start_webui_window() {
    echo -e "\n${BOLD}${BLUE}=== STARTING OPEN WEBUI (TERMINAL WINDOW) ===${NC}"
    if is_webui_running; then
        local pids
        pids=$(get_webui_pids)
        echo -e "${GREEN}✓ Open WebUI server is already running (PID: ${pids% }, URL: ${OPEN_WEBUI_LOCAL_URL}).${NC}"
        return 0
    fi

    # Ensure backend Ollama is running if possible
    if ! is_ollama_running; then
        echo -e "  ${YELLOW}Notice: Ollama backend is not detected. Starting Ollama in background...${NC}"
        local olm_script=""
        if [ -f "$(dirname "${BASH_SOURCE[0]}")/manage_ollama.sh" ]; then
            olm_script="$(dirname "${BASH_SOURCE[0]}")/manage_ollama.sh"
        elif [ -f "scripts/manage_ollama.sh" ]; then
            olm_script="scripts/manage_ollama.sh"
        fi
        if [ -n "$olm_script" ]; then
            bash "$olm_script" start >/dev/null 2>&1 || true
        fi
    fi

    if [ "$OS_TYPE" = "windows" ]; then
        echo -e "Launching Open WebUI in a new Windows terminal window..."
        if [ -n "$OPEN_WEBUI_START_BAT" ] && [ -f "$OPEN_WEBUI_START_BAT" ]; then
            cmd.exe /c start "Open WebUI Server" cmd.exe /k "call $(cygpath -w "$OPEN_WEBUI_START_BAT" 2>/dev/null || echo "$OPEN_WEBUI_START_BAT")" >/dev/null 2>&1 &
        else
            local win_conda
            win_conda="$(cygpath -w "$CONDA_BAT" 2>/dev/null || echo "$CONDA_BAT")"
            cmd.exe /c start "Open WebUI Server" cmd.exe /k "call \"$win_conda\" activate X:\OPENWEBUI\env && set DATA_DIR=X:\OPENWEBUI\data && set OLLAMA_BASE_URL=${OLLAMA_API_URL} && cd /d X:\OPENWEBUI && open-webui serve --host ${OPEN_WEBUI_HOST} --port ${OPEN_WEBUI_PORT}" >/dev/null 2>&1 &
        fi
        echo -e "Waiting for Open WebUI to initialize..."
        sleep 3
        if is_webui_running; then
            echo -e "${BOLD}${GREEN}✓ Open WebUI server running in new window (${OPEN_WEBUI_LOCAL_URL}).${NC}"
            return 0
        else
            echo -e "${YELLOW}Terminal window launched. Please check the new window for server logs.${NC}"
            return 0
        fi
    fi

    local TITLE="Open WebUI Server (:${OPEN_WEBUI_PORT})"
    local CMD
    if [ -x "$OPEN_WEBUI_BIN" ]; then
        CMD="cd '${OPEN_WEBUI_DIR}' && env DATA_DIR='${OPEN_WEBUI_DATA}' OLLAMA_BASE_URL='${OLLAMA_API_URL}' '${OPEN_WEBUI_BIN}' serve --host '${OPEN_WEBUI_HOST}' --port '${OPEN_WEBUI_PORT}'; echo ''; echo 'Server exited. Press [Enter] to close...'; read -r"
    else
        CMD="systemctl --user start ${OPEN_WEBUI_SERVICE} && journalctl --user -u ${OPEN_WEBUI_SERVICE} -f; echo ''; read -r"
    fi

    echo -e "Opening terminal window for Open WebUI [listening on ${OPEN_WEBUI_PORT}]..."
    if command -v konsole >/dev/null 2>&1; then
        konsole --new-tab -p tabtitle="$TITLE" -e bash -c "$CMD" &
    elif command -v xdg-terminal-exec >/dev/null 2>&1; then
        nohup xdg-terminal-exec bash -c "$CMD" >/dev/null 2>&1 &
    elif command -v gnome-terminal >/dev/null 2>&1; then
        nohup gnome-terminal --title="$TITLE" -- bash -c "$CMD" >/dev/null 2>&1 &
    elif command -v xterm >/dev/null 2>&1; then
        nohup xterm -T "$TITLE" -e bash -c "$CMD" >/dev/null 2>&1 &
    else
        start_webui_bg
        return $?
    fi

    echo -e "Waiting for Open WebUI to initialize..."
    sleep 2
    return 0
}

stop_webui() {
    echo -e "\n${BOLD}${YELLOW}Stopping Open WebUI Server...${NC}"
    if ! is_webui_running; then
        echo -e "${YELLOW}Open WebUI server is not currently running.${NC}"
        return 0
    fi

    local pids
    pids=$(get_webui_pids)
    echo -e "Terminating Open WebUI process(es): ${pids% }..."

    if [ "$OS_TYPE" = "windows" ]; then
        for pid in $pids; do
            [ -n "$pid" ] && taskkill.exe //F //T //PID "$pid" 2>/dev/null || true
        done
        taskkill.exe //F //IM "open-webui.exe" 2>/dev/null || true
        if command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { \$_.CommandLine -like '*open-webui*' -or \$_.CommandLine -like '*start_openwebui*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1 || true
        fi
        sleep 1

        if ! is_webui_running; then
            echo -e "${BOLD}${GREEN}✓ Open WebUI server stopped successfully.${NC}"
            return 0
        fi

        # Force terminate any remaining process on the port
        local rem_pids
        rem_pids=$(get_webui_pids)
        for pid in $rem_pids; do
            [ -n "$pid" ] && taskkill.exe //F //T //PID "$pid" 2>/dev/null || true
        done
        sleep 0.5
        if ! is_webui_running; then
            echo -e "${BOLD}${GREEN}✓ Open WebUI server force terminated.${NC}"
            return 0
        else
            echo -e "${RED}Error: Unable to terminate all Open WebUI processes.${NC}"
            return 1
        fi
    else
        if systemctl --user list-unit-files "$OPEN_WEBUI_SERVICE" >/dev/null 2>&1; then
            systemctl --user stop "$OPEN_WEBUI_SERVICE" 2>/dev/null || true
        fi
        if [ -n "$pids" ]; then
            kill $pids 2>/dev/null || true
            sleep 1
            pids=$(get_webui_pids)
            [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
        fi
        if ! is_webui_running; then
            echo -e "${BOLD}${GREEN}✓ Open WebUI server successfully stopped.${NC}"
            return 0
        else
            echo -e "${RED}Warning: Open WebUI process could not be terminated.${NC}"
            return 1
        fi
    fi
}

restart_webui() {
    echo -e "\n${BOLD}${BLUE}=== RESTARTING OPEN WEBUI SERVER ===${NC}"
    stop_webui
    sleep 1
    start_webui_bg
}

show_status() {
    update_active_port || true
    local LAN_IP
    LAN_IP=$(get_lan_ip)

    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}             OPEN WEBUI — WEB CHAT AI HARNESS SUITE                  ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

    if is_webui_running; then
        local pids
        pids=$(get_webui_pids)
        echo -e "  Server Status:    ${BOLD}${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
        echo -e "  Local Web UI URL: ${BOLD}${CYAN}${OPEN_WEBUI_LOCAL_URL}${NC}"
        [ -n "$LAN_IP" ] && echo -e "  LAN Endpoint:     ${BOLD}${CYAN}http://${LAN_IP}:${OPEN_WEBUI_PORT}${OPEN_WEBUI_PATH}${NC}"
        echo -e "  HTTP Health:      ${GREEN}HTTP 200 OK (Open WebUI)${NC}"
        if [ "$OS_TYPE" = "windows" ]; then
            echo -e "  Runtime Backend:  ${GREEN}Native Windows${NC} (Conda env: X:/OPENWEBUI/env)"
            [ -n "$OPEN_WEBUI_START_BAT" ] && [ -f "$OPEN_WEBUI_START_BAT" ] && echo -e "  Launcher Batch:   ${CYAN}${OPEN_WEBUI_START_BAT}${NC}"
        else
            echo -e "  Service Unit:     ${GREEN}${OPEN_WEBUI_SERVICE}${NC} (systemd user service)"
        fi
    else
        echo -e "  Server Status:    ${BOLD}${RED}○ STOPPED${NC}"
        echo -e "  Local Web UI URL: ${BOLD}${CYAN}${OPEN_WEBUI_LOCAL_URL}${NC} (Offline)"
        [ -n "$LAN_IP" ] && echo -e "  LAN Endpoint:     ${BOLD}${CYAN}http://${LAN_IP}:${OPEN_WEBUI_PORT}${OPEN_WEBUI_PATH}${NC} (Offline)"
        if [ "$OS_TYPE" = "windows" ]; then
            echo -e "  Runtime Backend:  ${YELLOW}Native Windows${NC} (Conda env: X:/OPENWEBUI/env)"
            [ -n "$OPEN_WEBUI_START_BAT" ] && [ -f "$OPEN_WEBUI_START_BAT" ] && echo -e "  Launcher Batch:   ${CYAN}${OPEN_WEBUI_START_BAT}${NC}"
        else
            echo -e "  Service Unit:     ${YELLOW}${OPEN_WEBUI_SERVICE}${NC}"
        fi
    fi

    # Ollama backend status
    if is_ollama_running; then
        echo -e "  Ollama Backend:   ${BOLD}${GREEN}● CONNECTED${NC} (${OLLAMA_API_URL})"
    else
        echo -e "  Ollama Backend:   ${BOLD}${RED}○ OFFLINE${NC} (${OLLAMA_API_URL})"
    fi

    # GPU info
    if command -v nvidia-smi >/dev/null 2>&1; then
        local gpu_info
        gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -n 1)
        [ -n "$gpu_info" ] && echo -e "  Hardware Accel:   ${GREEN}${gpu_info}${NC} (CUDA Enabled)"
    fi

    echo ""
    echo -e "${BOLD}Installed Local Models Available for Web Chat:${NC}"
    if is_ollama_running; then
        local model_list
        model_list=$(curl -s "${OLLAMA_API_URL}/api/tags" 2>/dev/null)
        if [ -n "$model_list" ] && command -v jq >/dev/null 2>&1; then
            echo "$model_list" | jq -r '.models[]? | "  • \(.name) (\((.size / 1073741824 * 10 | floor) / 10) GB, \(.details.parameter_size // "N/A"))"' 2>/dev/null
        else
            echo -e "  ${GREEN}Ollama models online at ${OLLAMA_API_URL}${NC}"
        fi
    else
        local found_offline=false
        local manifest_dir="X:/OLLAMA/models/manifests"
        if [ -d "$manifest_dir" ]; then
            while IFS= read -r mf; do
                [ -z "$mf" ] && continue
                local tag="$(basename "$mf")"
                local parent="$(dirname "$mf")"
                local mname="$(basename "$parent")"
                echo -e "  • ${mname}:${tag}"
                found_offline=true
            done < <(find "$manifest_dir" -type f 2>/dev/null)
        fi
        if [ "$found_offline" = "false" ]; then
            echo -e "  ${YELLOW}(Start Ollama server to feed local models into Open WebUI)${NC}"
        fi
    fi
    echo ""
}

view_logs() {
    clear
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}                     OPEN WEBUI SERVER LOGS                           ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

    local found_log=""
    local check_logs=()
    if [ "$OS_TYPE" = "windows" ]; then
        check_logs+=("$LOG_FILE" "X:/OPENWEBUI/open-webui.log" "X:/OPENWEBUI/data/open-webui.log")
    fi
    check_logs+=("/tmp/open-webui.log")

    if [ "$OS_TYPE" != "windows" ] && systemctl --user list-unit-files "$OPEN_WEBUI_SERVICE" >/dev/null 2>&1; then
        echo -e "Showing last 50 log entries from systemd journal (${OPEN_WEBUI_SERVICE}):\n"
        journalctl --user -u "$OPEN_WEBUI_SERVICE" -n 50 --no-pager 2>/dev/null || true
    else
        for lf in "${check_logs[@]}"; do
            if [ -f "$lf" ] && [ -s "$lf" ]; then
                found_log="$lf"
                break
            fi
        done
        if [ -z "$found_log" ]; then
            for lf in "${check_logs[@]}"; do
                if [ -f "$lf" ]; then
                    found_log="$lf"
                    break
                fi
            done
        fi
        if [ -n "$found_log" ]; then
            echo -e "Log file: ${found_log} (Last 50 lines):\n"
            tail -n 50 "$found_log"
        else
            echo -e "Log file does not exist yet (server may have been started in a dedicated terminal window)."
            echo -e "Target log paths: ${LOG_FILE}"
        fi
    fi
    echo ""
    read -r -p "Press Enter to return..."
}

interactive_menu() {
    while true; do
        clear
        show_status
        echo -e "${BOLD}${MAGENTA}----------------------------------------------------------------------${NC}"
        echo -e "${BOLD}Select an Open WebUI operation:${NC}\n"
        echo -e "  ${BOLD}${CYAN} 1)${NC} Open Web Chat in Browser (${BOLD}${GREEN}${OPEN_WEBUI_LOCAL_URL}${NC})"
        echo -e "  ${BOLD}${CYAN} 2)${NC} Start Open WebUI Server (${BOLD}${GREEN}Background Service${NC}) [open-webui serve]"
        echo -e "  ${BOLD}${CYAN} 3)${NC} Start Open WebUI Server in ${BOLD}${YELLOW}New Terminal Window${NC} (Live Logs)"
        echo -e "  ${BOLD}${CYAN} 4)${NC} Stop Running Open WebUI Server"
        echo -e "  ${BOLD}${CYAN} 5)${NC} Restart Open WebUI Server"
        local log_target="$LOG_FILE"
        [ "$OS_TYPE" != "windows" ] && log_target="$OPEN_WEBUI_SERVICE"
        echo -e "  ${BOLD}${CYAN} 6)${NC} View Service Status & Logs (${log_target})"
        echo -e "  ${BOLD}${CYAN} 7)${NC} Return to Previous Menu\n"
        read -r -p "Enter choice [1-7, or q to return]: " w_choice

        case "$w_choice" in
            1)
                if ! is_webui_running; then
                    echo -e "\n${YELLOW}Open WebUI is not running. Starting server first...${NC}"
                    start_webui_bg
                    sleep 1
                fi
                open_webui_browser
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            2)
                start_webui_bg
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            3)
                start_webui_window
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            4)
                stop_webui
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            5)
                restart_webui
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
    open|launch|browser|chat)
        if ! is_webui_running; then
            start_webui_bg
            sleep 1
        fi
        open_webui_browser
        ;;
    start|serve|bg)
        start_webui_bg
        ;;
    start-window|window|terminal)
        start_webui_window
        ;;
    stop)
        stop_webui
        ;;
    restart)
        restart_webui
        ;;
    status)
        show_status
        ;;
    logs)
        view_logs
        ;;
    "")
        interactive_menu
        ;;
    *)
        echo "Usage: $(basename "$0") {open|start|start-window|stop|restart|status|logs}"
        exit 1
        ;;
esac
