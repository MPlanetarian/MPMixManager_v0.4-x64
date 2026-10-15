#!/usr/bin/env bash
# ==============================================================================
# scripts/manage_ollama.sh
# Purpose: Start, stop, restart, and monitor Ollama Server (ollama serve)
#          Supports native Windows (ollama.exe / start_ollama.bat)
#          and Linux (distrobox container / systemd)
# ==============================================================================

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
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

OLLAMA_CONTAINER="${OLLAMA_CONTAINER:-ollama-container}"
OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
if [[ "$OLLAMA_HOST" =~ :[0-9]+$ ]]; then
    OLLAMA_PORT="${OLLAMA_HOST##*:}"
    OLLAMA_HOST="${OLLAMA_HOST%:*}"
fi
OLLAMA_BIND="${OLLAMA_HOST}:${OLLAMA_PORT}"
OLLAMA_URL="http://${OLLAMA_HOST}:${OLLAMA_PORT}"
if [ "$OLLAMA_HOST" = "0.0.0.0" ]; then
    OLLAMA_CHECK_URL="http://127.0.0.1:${OLLAMA_PORT}"
else
    OLLAMA_CHECK_URL="${OLLAMA_URL}"
fi

# Locate Ollama executable and launcher files
OLLAMA_BIN="ollama"
OLLAMA_START_BAT=""
if [ "$OS_TYPE" = "windows" ]; then
    for cand in \
        "C:/Users/${USER:-Mathe}/AppData/Local/Programs/Ollama/ollama.exe" \
        "$LOCALAPPDATA/Programs/Ollama/ollama.exe" \
        "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Ollama/ollama.exe" \
        "/c/Program Files/Ollama/ollama.exe"; do
        if [ -x "$cand" ] || [ -f "$cand" ]; then
            OLLAMA_BIN="$cand"
            break
        fi
    done
    if [ "$OLLAMA_BIN" = "ollama" ] && command -v ollama.exe >/dev/null 2>&1; then
        OLLAMA_BIN="ollama.exe"
    fi

    for b_cand in "X:/OLLAMA/start_ollama.bat" "X:\OLLAMA\start_ollama.bat" "X:/STARTAI/start_ollama.bat"; do
        if [ -f "$b_cand" ]; then
            OLLAMA_START_BAT="$b_cand"
            break
        fi
    done

    export OLLAMA_MODELS="${OLLAMA_MODELS:-X:\OLLAMA\models}"
    export OLLAMA_ORIGINS="${OLLAMA_ORIGINS:-*}"
    LOG_FILE="X:/OLLAMA/ollama-serve.log"
else
    LOG_FILE="/tmp/ollama-serve.log"
fi

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

is_ollama_running() {
    if curl -s --connect-timeout 1 "${OLLAMA_CHECK_URL}/" 2>/dev/null | grep -qi "Ollama is running"; then
        return 0
    elif curl -s --connect-timeout 1 "http://127.0.0.1:${OLLAMA_PORT}/" 2>/dev/null | grep -qi "Ollama is running"; then
        return 0
    elif [ "$OS_TYPE" = "windows" ]; then
        if command -v netstat.exe >/dev/null 2>&1 && netstat.exe -ano 2>/dev/null | grep -E ":${OLLAMA_PORT}\s+.*LISTENING" >/dev/null 2>&1; then
            return 0
        fi
        if command -v tasklist.exe >/dev/null 2>&1 && tasklist.exe //FI "IMAGENAME eq ollama.exe" 2>/dev/null | grep -qi "ollama.exe"; then
            return 0
        fi
    elif pgrep -f "ollama serve" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

get_ollama_pids() {
    if [ "$OS_TYPE" = "windows" ]; then
        local pids=""
        if command -v netstat.exe >/dev/null 2>&1; then
            pids=$(netstat.exe -ano 2>/dev/null | grep -E ":${OLLAMA_PORT}\s+.*LISTENING" | awk '{print $5}' | sort -u | tr '\n' ' ')
        fi
        if [ -z "$pids" ] && command -v tasklist.exe >/dev/null 2>&1; then
            pids=$(tasklist.exe //FI "IMAGENAME eq ollama.exe" //FO CSV //NH 2>/dev/null | awk -F'","' '{print $2}' | tr -d '"\r ' | tr '\n' ' ')
        fi
        echo "$pids"
    else
        pgrep -f "ollama serve" 2>/dev/null | tr '\n' ' '
    fi
}

ensure_container_started() {
    [ "$OS_TYPE" = "windows" ] && return 0
    if command -v podman >/dev/null 2>&1; then
        if ! podman ps --filter "name=${OLLAMA_CONTAINER}" --format "{{.Names}}" 2>/dev/null | grep -q "^${OLLAMA_CONTAINER}$"; then
            echo -e "  ${YELLOW}Starting podman container '${OLLAMA_CONTAINER}'...${NC}"
            podman start "$OLLAMA_CONTAINER" >/dev/null 2>&1 || true
            sleep 1
        fi
    fi
}

start_ollama_bg() {
    echo -e "\n${BOLD}${BLUE}=== STARTING OLLAMA SERVER (BACKGROUND) ===${NC}"
    if is_ollama_running; then
        local pids
        pids=$(get_ollama_pids)
        echo -e "${GREEN}✓ Ollama server is already running (PID: ${pids% }, URL: ${OLLAMA_CHECK_URL}).${NC}"
        return 0
    fi

    if [ "$OS_TYPE" = "windows" ]; then
        export OLLAMA_MODELS="${OLLAMA_MODELS:-X:\OLLAMA\models}"
        export OLLAMA_ORIGINS="${OLLAMA_ORIGINS:-*}"
        export OLLAMA_HOST="${OLLAMA_BIND}"
        export OLLAMA_FLASH_ATTENTION="1"
        export OLLAMA_KV_CACHE_TYPE="q8_0"
        export OLLAMA_CONTEXT_LENGTH="32768"
        [ -d "X:/OLLAMA/models" ] || mkdir -p "X:/OLLAMA/models" 2>/dev/null || true
        [ -d "X:/OLLAMA" ] || mkdir -p "X:/OLLAMA" 2>/dev/null || true

        local bg_bat="X:/OLLAMA/start_ollama_bg.bat"
        local win_bin win_models win_log win_err
        win_bin="$(cygpath -w "$OLLAMA_BIN" 2>/dev/null || echo "$OLLAMA_BIN")"
        win_models="$(cygpath -w "$OLLAMA_MODELS" 2>/dev/null || echo "$OLLAMA_MODELS")"
        win_log="$(cygpath -w "$LOG_FILE" 2>/dev/null || echo "$LOG_FILE")"
        win_err="$(cygpath -w "${LOG_FILE%.*}.err" 2>/dev/null || echo "${LOG_FILE%.*}.err")"

        cat << EOFBAT > "$bg_bat"
@echo off
set OLLAMA_MODELS=${win_models}
set OLLAMA_ORIGINS=*
set OLLAMA_HOST=${OLLAMA_BIND}
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_CONTEXT_LENGTH=32768
set OLLAMA_NUM_PARALLEL=1
set OLLAMA_GPU_OVERHEAD=536870912
set OLLAMA_VULKAN=0
if not exist "${win_models}" mkdir "${win_models}"
cd /d "X:\OLLAMA"
"${win_bin}" serve > "${win_log}" 2> "${win_err}"
EOFBAT

        echo -e "Launching 'ollama serve' in background on Windows [listening on ${OLLAMA_BIND}, models in ${OLLAMA_MODELS}]..."
        if command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -Command "([wmiclass]'win32_process').Create('cmd.exe /c X:\OLLAMA\start_ollama_bg.bat')" >/dev/null 2>&1 &
        else
            cmd.exe /c start /b "" "X:\OLLAMA\start_ollama_bg.bat" >/dev/null 2>&1 &
        fi
    else
        ensure_container_started
        if systemctl --user is-enabled ollama.service >/dev/null 2>&1; then
            echo -e "Starting Ollama Server via systemd service (ollama.service)..."
            systemctl --user restart ollama.service >/dev/null 2>&1 || true
        else
            echo -e "Launching 'ollama serve' in background via distrobox (${OLLAMA_CONTAINER}) [listening on ${OLLAMA_BIND}]..."
            nohup distrobox enter -T "$OLLAMA_CONTAINER" -- env \
                LD_LIBRARY_PATH="/run/host/usr/lib64:/run/host/usr/lib64/nvidia:\${LD_LIBRARY_PATH:-}" \
                OLLAMA_HOST="${OLLAMA_BIND}" \
                OLLAMA_ORIGINS="*" \
                OLLAMA_FLASH_ATTENTION="1" \
                OLLAMA_KV_CACHE_TYPE="q8_0" \
                OLLAMA_CONTEXT_LENGTH="32768" \
                OLLAMA_NUM_PARALLEL="1" \
                OLLAMA_GPU_OVERHEAD="536870912" \
                OLLAMA_VULKAN="0" \
                ollama serve >"$LOG_FILE" 2>&1 &
        fi
    fi

    echo -e "Waiting for Ollama API endpoint to become responsive..."
    local ready=false
    for _ in {1..20}; do
        if curl -s --connect-timeout 1 "${OLLAMA_CHECK_URL}/" 2>/dev/null | grep -qi "Ollama is running"; then
            ready=true
            break
        elif curl -s --connect-timeout 1 "http://127.0.0.1:${OLLAMA_PORT}/" 2>/dev/null | grep -qi "Ollama is running"; then
            ready=true
            break
        fi
        sleep 0.5
    done

    local LAN_IP
    LAN_IP=$(get_lan_ip)

    if [ "$ready" = "true" ]; then
        local pids
        pids=$(get_ollama_pids)
        echo -e "${BOLD}${GREEN}✓ Ollama server successfully started!${NC}"
        echo -e "  • Status:       ${GREEN}RUNNING${NC}"
        echo -e "  • Local:        ${BOLD}${CYAN}http://127.0.0.1:${OLLAMA_PORT}${NC}"
        [ -n "$LAN_IP" ] && echo -e "  • LAN Endpoint: ${BOLD}${CYAN}http://${LAN_IP}:${OLLAMA_PORT}${NC}"
        echo -e "  • PID(s):       ${YELLOW}${pids% }${NC}"
        echo -e "  • Log File:     ${LOG_FILE}"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send -a "Ollama" -i "dialog-ok" "Ollama Server" "✓ Ollama server is live on http://${LAN_IP:-127.0.0.1}:${OLLAMA_PORT}" 2>/dev/null || true
        fi
        return 0
    else
        echo -e "${RED}Warning: Ollama server did not respond on ${OLLAMA_CHECK_URL} within 10s.${NC}"
        echo -e "${YELLOW}Check logs with: tail -n 20 ${LOG_FILE}${NC}"
        return 1
    fi
}

start_ollama_window() {
    echo -e "\n${BOLD}${BLUE}=== STARTING OLLAMA SERVER (TERMINAL WINDOW) ===${NC}"
    if is_ollama_running; then
        local pids
        pids=$(get_ollama_pids)
        echo -e "${GREEN}✓ Ollama server is already running (PID: ${pids% }, URL: ${OLLAMA_CHECK_URL}).${NC}"
        return 0
    fi

    if [ "$OS_TYPE" = "windows" ]; then
        export OLLAMA_MODELS="${OLLAMA_MODELS:-X:\OLLAMA\models}"
        export OLLAMA_ORIGINS="${OLLAMA_ORIGINS:-*}"
        export OLLAMA_HOST="${OLLAMA_BIND}"
        [ -d "X:/OLLAMA/models" ] || mkdir -p "X:/OLLAMA/models" 2>/dev/null || true
        [ -d "X:/OLLAMA" ] || mkdir -p "X:/OLLAMA" 2>/dev/null || true

        echo -e "Launching Ollama Server in new Windows terminal window..."
        if [ -n "$OLLAMA_START_BAT" ] && [ -f "$OLLAMA_START_BAT" ]; then
            cmd.exe /c start "Ollama Server" "$(cygpath -w "$OLLAMA_START_BAT" 2>/dev/null || echo "$OLLAMA_START_BAT")" >/dev/null 2>&1 &
        else
            local win_bin
            win_bin="$(cygpath -w "$OLLAMA_BIN" 2>/dev/null || echo "$OLLAMA_BIN")"
            cmd.exe /c start "Ollama Server" cmd.exe /k "set OLLAMA_MODELS=X:\OLLAMA\models && set OLLAMA_ORIGINS=* && set OLLAMA_HOST=${OLLAMA_BIND} && \"$win_bin\" serve" >/dev/null 2>&1 &
        fi

        echo -e "Waiting for Ollama to initialize..."
        sleep 2
        if is_ollama_running; then
            echo -e "${BOLD}${GREEN}✓ Ollama server running in new window (${OLLAMA_CHECK_URL}).${NC}"
            return 0
        else
            echo -e "${YELLOW}Terminal window launched. Please check the new window for server logs.${NC}"
            return 0
        fi
    fi

    ensure_container_started

    local TITLE="Ollama Server (${OLLAMA_CONTAINER})"
    local OLLAMA_ENV="LD_LIBRARY_PATH=/run/host/usr/lib64:/run/host/usr/lib64/nvidia:\${LD_LIBRARY_PATH:-} OLLAMA_HOST=${OLLAMA_BIND} OLLAMA_ORIGINS=\"*\" OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_NUM_PARALLEL=1 OLLAMA_GPU_OVERHEAD=536870912 OLLAMA_VULKAN=0"
    local CMD="distrobox enter ${OLLAMA_CONTAINER} -- env ${OLLAMA_ENV} ollama serve; echo ''; echo 'Ollama server exited. Press [Enter] to close...'; read -r"

    echo -e "Opening terminal window for 'ollama serve' [listening on ${OLLAMA_BIND}]..."
    if command -v konsole >/dev/null 2>&1; then
        konsole --new-tab -p tabtitle="$TITLE" -e bash -c "$CMD" &
    elif command -v xdg-terminal-exec >/dev/null 2>&1; then
        nohup xdg-terminal-exec bash -c "$CMD" >/dev/null 2>&1 &
    elif command -v gnome-terminal >/dev/null 2>&1; then
        nohup gnome-terminal --title="$TITLE" -- bash -c "$CMD" >/dev/null 2>&1 &
    elif command -v xterm >/dev/null 2>&1; then
        nohup xterm -T "$TITLE" -e bash -c "$CMD" >/dev/null 2>&1 &
    else
        start_ollama_bg
        return $?
    fi

    echo -e "Waiting for Ollama to initialize..."
    sleep 2
    if is_ollama_running; then
        echo -e "${BOLD}${GREEN}✓ Ollama server running in new window (${OLLAMA_CHECK_URL}).${NC}"
        return 0
    else
        echo -e "${YELLOW}Terminal window launched. Please check the new window for server logs.${NC}"
        return 0
    fi
}

stop_ollama() {
    echo -e "\n${BOLD}${YELLOW}Stopping Ollama Server...${NC}"
    if ! is_ollama_running; then
        echo -e "${YELLOW}Ollama server is not currently running.${NC}"
        return 0
    fi

    local pids
    pids=$(get_ollama_pids)
    echo -e "Terminating Ollama process(es): ${pids% }..."

    if [ "$OS_TYPE" = "windows" ]; then
        for pid in $pids; do
            [ -n "$pid" ] && taskkill.exe //F //T //PID "$pid" 2>/dev/null || true
        done
        taskkill.exe //F //IM "ollama.exe" 2>/dev/null || true
        if command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { \$_.CommandLine -like '*start_ollama*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1 || true
        fi
        sleep 1

        if ! is_ollama_running; then
            echo -e "${BOLD}${GREEN}✓ Ollama server stopped successfully.${NC}"
            return 0
        fi

        # Force terminate any remaining process on the port
        local rem_pids
        rem_pids=$(get_ollama_pids)
        for pid in $rem_pids; do
            [ -n "$pid" ] && taskkill.exe //F //T //PID "$pid" 2>/dev/null || true
        done
        sleep 0.5
        if ! is_ollama_running; then
            echo -e "${BOLD}${GREEN}✓ Ollama server force terminated.${NC}"
            return 0
        else
            echo -e "${RED}Error: Unable to terminate all Ollama processes.${NC}"
            return 1
        fi
    else
        if systemctl --user is-active --quiet ollama.service 2>/dev/null; then
            systemctl --user stop ollama.service >/dev/null 2>&1 || true
        fi
        # Graceful TERM on Linux
        distrobox enter -T "$OLLAMA_CONTAINER" -- pkill -TERM -f "ollama serve" 2>/dev/null || true
        pkill -TERM -f "ollama serve" 2>/dev/null || true

        sleep 1.5

        if ! is_ollama_running; then
            echo -e "${BOLD}${GREEN}✓ Ollama server stopped successfully.${NC}"
            if command -v notify-send >/dev/null 2>&1; then
                notify-send -a "Ollama" -i "dialog-ok" "Ollama Server" "✓ Ollama server stopped." 2>/dev/null || true
            fi
            return 0
        else
            echo -e "${RED}Process still running. Force killing...${NC}"
            distrobox enter -T "$OLLAMA_CONTAINER" -- pkill -9 -f "ollama serve" 2>/dev/null || true
            pkill -9 -f "ollama serve" 2>/dev/null || true
            sleep 1
            if ! is_ollama_running; then
                echo -e "${BOLD}${GREEN}✓ Ollama server force terminated.${NC}"
                return 0
            else
                echo -e "${RED}Error: Unable to terminate all Ollama processes.${NC}"
                return 1
            fi
        fi
    fi
}

restart_ollama() {
    echo -e "\n${BOLD}${MAGENTA}Restarting Ollama Server...${NC}"
    stop_ollama
    sleep 1
    start_ollama_bg
}

show_status() {
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}                    OLLAMA SERVER STATUS & MODELS                     ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

    local LAN_IP
    LAN_IP=$(get_lan_ip)

    if is_ollama_running; then
        local pids
        pids=$(get_ollama_pids)
        echo -e "  Server Status:    ${BOLD}${GREEN}● RUNNING${NC}${pids:+ (PID: ${pids% })}"
        echo -e "  Local Endpoint:   ${BOLD}${CYAN}http://127.0.0.1:${OLLAMA_PORT}${NC}"
        [ -n "$LAN_IP" ] && echo -e "  LAN Endpoint:     ${BOLD}${CYAN}http://${LAN_IP}:${OLLAMA_PORT}${NC}"
        if [ "$OS_TYPE" = "windows" ]; then
            echo -e "  HTTP Health:      ${GREEN}HTTP 200 OK (Ollama is running)${NC}"
            echo -e "  Runtime Backend:  ${GREEN}Native Windows${NC} (Models: ${OLLAMA_MODELS:-X:\OLLAMA\models})"
            [ -n "$OLLAMA_START_BAT" ] && [ -f "$OLLAMA_START_BAT" ] && echo -e "  Launcher Batch:   ${CYAN}${OLLAMA_START_BAT}${NC}"
        else
            if systemctl --user is-active --quiet ollama-caddy.service 2>/dev/null; then
                echo -e "  HTTPS Endpoints:  ${BOLD}${CYAN}https://${LAN_IP:-127.0.0.1}:8443${NC} | ${BOLD}${CYAN}https://${LAN_IP:-127.0.0.1}:11436${NC}"
            fi
            echo -e "  HTTP Health:      ${GREEN}HTTP 200 OK (Ollama is running)${NC}"
            echo -e "  Container:        ${GREEN}${OLLAMA_CONTAINER}${NC} (distrobox/podman)"
        fi
    else
        echo -e "  Server Status:    ${BOLD}${RED}○ STOPPED${NC}"
        echo -e "  Local Endpoint:   ${BOLD}${CYAN}http://127.0.0.1:${OLLAMA_PORT}${NC} (Offline)"
        [ -n "$LAN_IP" ] && echo -e "  LAN Endpoint:     ${BOLD}${CYAN}http://${LAN_IP}:${OLLAMA_PORT}${NC} (Offline)"
        if [ "$OS_TYPE" = "windows" ]; then
            echo -e "  Runtime Backend:  ${YELLOW}Native Windows${NC} (Models: ${OLLAMA_MODELS:-X:\OLLAMA\models})"
            [ -n "$OLLAMA_START_BAT" ] && [ -f "$OLLAMA_START_BAT" ] && echo -e "  Launcher Batch:   ${CYAN}${OLLAMA_START_BAT}${NC}"
        else
            echo -e "  Container:        ${YELLOW}${OLLAMA_CONTAINER}${NC}"
        fi
    fi

    # GPU info
    if command -v nvidia-smi >/dev/null 2>&1; then
        local gpu_info
        gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -n 1)
        [ -n "$gpu_info" ] && echo -e "  Hardware Accel:   ${GREEN}${gpu_info}${NC} (CUDA Enabled)"
    fi

    echo ""
    echo -e "${BOLD}Installed Local Models in Ollama:${NC}"
    if is_ollama_running; then
        local model_list
        model_list=$(curl -s "${OLLAMA_CHECK_URL}/api/tags" 2>/dev/null)
        if [ -n "$model_list" ] && command -v jq >/dev/null 2>&1; then
            echo "$model_list" | jq -r '.models[]? | "  • \(.name) (\((.size / 1073741824 * 10 | floor) / 10) GB, \(.details.parameter_size // "N/A"), \(.details.quantization_level // "N/A"))"' 2>/dev/null
        elif [ "$OS_TYPE" = "windows" ]; then
            "$OLLAMA_BIN" list 2>/dev/null | sed 's/^/  /' || true
        else
            distrobox enter -T "$OLLAMA_CONTAINER" -- ollama list 2>/dev/null | sed 's/^/  /'
        fi
    else
        local found_offline=false
        local manifest_dir="X:/OLLAMA/models/manifests"
        [ ! -d "$manifest_dir" ] && [ -n "$OLLAMA_MODELS" ] && manifest_dir="$(cygpath -u "$OLLAMA_MODELS" 2>/dev/null)/manifests"
        if [ -d "$manifest_dir" ]; then
            echo -e "  ${YELLOW}(Server stopped - detected models in storage):${NC}"
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
            echo -e "  ${YELLOW}(Start server to query models via API)${NC}"
        fi
    fi
    echo ""
}

run_chat_cli() {
    if ! is_ollama_running; then
        echo -e "\n${YELLOW}Ollama server is not running. Starting server first...${NC}"
        start_ollama_bg
        sleep 1
    fi

    echo -e "\n${BOLD}${BLUE}=== CHAT WITH LOCAL OLLAMA MODEL ===${NC}\n"
    local models=()
    if is_ollama_running && command -v jq >/dev/null 2>&1; then
        mapfile -t models < <(curl -s "${OLLAMA_CHECK_URL}/api/tags" 2>/dev/null | jq -r '.models[]?.name' 2>/dev/null)
    fi

    if [ ${#models[@]} -eq 0 ]; then
        if [ "$OS_TYPE" = "windows" ]; then
            mapfile -t models < <("$OLLAMA_BIN" list 2>/dev/null | awk 'NR>1 {print $1}')
        else
            mapfile -t models < <(distrobox enter -T "$OLLAMA_CONTAINER" -- ollama list 2>/dev/null | awk 'NR>1 {print $1}')
        fi
    fi

    if [ ${#models[@]} -eq 0 ]; then
        local manifest_dir="X:/OLLAMA/models/manifests"
        [ ! -d "$manifest_dir" ] && [ -n "$OLLAMA_MODELS" ] && manifest_dir="$(cygpath -u "$OLLAMA_MODELS" 2>/dev/null)/manifests"
        if [ -d "$manifest_dir" ]; then
            while IFS= read -r mf; do
                [ -z "$mf" ] && continue
                local tag="$(basename "$mf")"
                local parent="$(dirname "$mf")"
                local mname="$(basename "$parent")"
                models+=("${mname}:${tag}")
            done < <(find "$manifest_dir" -type f 2>/dev/null)
        fi
    fi

    if [ ${#models[@]} -eq 0 ]; then
        echo -e "${RED}No local models found in Ollama.${NC}"
        read -r -p "Press Enter to return..."
        return 1
    fi

    echo "Select a model to run:"
    local idx=1
    for m in "${models[@]}"; do
        printf "  %2d) %s\n" "$idx" "$m"
        ((idx++))
    done
    echo "   0) Cancel"
    echo ""
    read -r -p "Enter choice [1-${#models[@]}]: " m_choice
    if [ "$m_choice" = "0" ] || [ -z "$m_choice" ]; then
        return 0
    fi

    if [[ "$m_choice" =~ ^[0-9]+$ ]] && [ "$m_choice" -ge 1 ] && [ "$m_choice" -le ${#models[@]} ]; then
        local chosen_model="${models[$((m_choice - 1))]}"
        echo -e "\n${BOLD}${GREEN}Launching interactive chat with '${chosen_model}'...${NC}\n"
        echo -e "${CYAN}Type /bye or press Ctrl+D to exit the chat.${NC}\n"
        if [ "$OS_TYPE" = "windows" ]; then
            if command -v winpty >/dev/null 2>&1 && [ -t 0 ]; then
                winpty "$OLLAMA_BIN" run "$chosen_model"
            else
                "$OLLAMA_BIN" run "$chosen_model"
            fi
        else
            distrobox enter "$OLLAMA_CONTAINER" -- ollama run "$chosen_model"
        fi
    else
        echo -e "${RED}Invalid selection.${NC}"
        sleep 1
    fi
}

run_voice_chat_cli() {
    local target_model="${1:-}"
    local target_voice="${2:-}"

    if ! is_ollama_running; then
        echo -e "\n${YELLOW}Ollama server is not running. Starting server first...${NC}"
        start_ollama_bg
        sleep 1
    fi

    echo -e "\n${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}          VOICE CHAT SESSION WITH LOCAL OLLAMA MODELS                 ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

    local models=()
    if is_ollama_running && command -v jq >/dev/null 2>&1; then
        mapfile -t models < <(curl -s "${OLLAMA_CHECK_URL}/api/tags" 2>/dev/null | jq -r '.models[]?.name' 2>/dev/null)
    fi

    if [ ${#models[@]} -eq 0 ]; then
        if [ "$OS_TYPE" = "windows" ]; then
            mapfile -t models < <("$OLLAMA_BIN" list 2>/dev/null | awk 'NR>1 {print $1}')
        else
            mapfile -t models < <(distrobox enter -T "$OLLAMA_CONTAINER" -- ollama list 2>/dev/null | awk 'NR>1 {print $1}')
        fi
    fi

    if [ ${#models[@]} -eq 0 ]; then
        local manifest_dir="X:/OLLAMA/models/manifests"
        [ ! -d "$manifest_dir" ] && [ -n "$OLLAMA_MODELS" ] && manifest_dir="$(cygpath -u "$OLLAMA_MODELS" 2>/dev/null)/manifests"
        if [ -d "$manifest_dir" ]; then
            while IFS= read -r mf; do
                [ -z "$mf" ] && continue
                local tag="$(basename "$mf")"
                local parent="$(dirname "$mf")"
                local mname="$(basename "$parent")"
                models+=("${mname}:${tag}")
            done < <(find "$manifest_dir" -type f 2>/dev/null)
        fi
    fi

    if [ ${#models[@]} -eq 0 ]; then
        echo -e "${RED}No local models found in Ollama.${NC}"
        read -r -p "Press Enter to return..."
        return 1
    fi

    local chosen_model="$target_model"
    if [ -z "$chosen_model" ]; then
        echo "Select a local model to start voice chat with:"
        local idx=1
        for m in "${models[@]}"; do
            printf "  %2d) %s\n" "$idx" "$m"
            ((idx++))
        done
        echo "   0) Cancel"
        echo ""
        read -r -p "Enter choice [1-${#models[@]}]: " m_choice
        if [ "$m_choice" = "0" ] || [ -z "$m_choice" ]; then
            return 0
        fi

        if [[ "$m_choice" =~ ^[0-9]+$ ]] && [ "$m_choice" -ge 1 ] && [ "$m_choice" -le ${#models[@]} ]; then
            chosen_model="${models[$((m_choice - 1))]}"
        else
            echo -e "${RED}Invalid selection.${NC}"
            sleep 1
            return 1
        fi
    fi

    local chosen_voice="$target_voice"
    local chosen_voice_name=""
    if [ -n "$chosen_voice" ]; then
        case "$chosen_voice" in
            morpheus) chosen_voice_name="Morpheus (The Matrix)" ;;
            neo) chosen_voice_name="Neo (The Matrix)" ;;
            trinity) chosen_voice_name="Trinity (The Matrix)" ;;
            oracle|the_oracle) chosen_voice="oracle"; chosen_voice_name="The Oracle (The Matrix)" ;;
            zion|hamann) chosen_voice="zion"; chosen_voice_name="Zion (Councillor Hamann)" ;;
            *) chosen_voice="agent_smith"; chosen_voice_name="Agent Smith (The Matrix)" ;;
        esac
    else
        echo -e "\nSelect a Matrix Voice character (or press Enter for Agent Smith):"
        echo -e "  1) Agent Smith (The Matrix) [Default]"
        echo -e "  2) Morpheus (The Matrix)"
        echo -e "  3) Neo (The Matrix)"
        echo -e "  4) Trinity (The Matrix)"
        echo -e "  5) The Oracle (The Matrix)"
        echo -e "  6) Zion (Councillor Hamann)"
        echo ""
        read -r -p "Enter voice choice [1-6, Enter=1]: " v_choice

        case "$v_choice" in
            2) chosen_voice="morpheus"; chosen_voice_name="Morpheus (The Matrix)" ;;
            3) chosen_voice="neo"; chosen_voice_name="Neo (The Matrix)" ;;
            4) chosen_voice="trinity"; chosen_voice_name="Trinity (The Matrix)" ;;
            5) chosen_voice="oracle"; chosen_voice_name="The Oracle (The Matrix)" ;;
            6) chosen_voice="zion"; chosen_voice_name="Zion (Councillor Hamann)" ;;
            *) chosen_voice="agent_smith"; chosen_voice_name="Agent Smith (The Matrix)" ;;
        esac
    fi

    # Locate Voice Chat Engine (local-voice-talk / local_voice_talk.py)
    local voice_bin=""
    for cand in \
        "$(command -v local-voice-talk 2>/dev/null)" \
        "$HOME/bin/local-voice-talk" \
        "/var/home/mplanetarian/bin/local-voice-talk" \
        "$HOME/.local/bin/local-voice-talk"; do
        if [ -n "$cand" ] && [ -x "$cand" ]; then
            voice_bin="$cand"
            break
        fi
    done

    local voice_py="/var/home/mplanetarian/voice-ai/local_voice_talk.py"
    local voice_venv_py="/var/home/mplanetarian/voice-ai/bin/python"

    local pids
    pids=$(get_ollama_pids)

    export VOICE_AI_TTS_VOICE="${chosen_voice}"

    echo -e "\n${BOLD}${GREEN}Starting real-time Voice Chat session with '${chosen_model}'...${NC}"
    echo -e "  • Model:        ${BOLD}${YELLOW}${chosen_model}${NC}"
    echo -e "  • Ollama URL:   ${BOLD}${CYAN}${OLLAMA_CHECK_URL}${NC}${pids:+ (PID: ${pids% })}"
    echo -e "  • Voice:        ${BOLD}${MAGENTA}${chosen_voice_name}${NC} [id: ${CYAN}${chosen_voice}${NC}]"
    echo -e "  • Voice Engine: ${BOLD}${CYAN}Whisper STT + XTTS-v2 Neural Voice Clone${NC}"
    echo -e "  • Controls:     ${DIM}Press [Enter] to speak via mic, type text to query, /voice to change, /quit to exit${NC}\n"
    sleep 1

    if [ -n "$voice_bin" ]; then
        OLLAMA_URL="${OLLAMA_CHECK_URL}" "$voice_bin" --model "$chosen_model" --voice "$chosen_voice"
    elif [ -f "$voice_py" ] && [ -x "$voice_venv_py" ]; then
        OLLAMA_URL="${OLLAMA_CHECK_URL}" "$voice_venv_py" "$voice_py" --model "$chosen_model" --voice "$chosen_voice"
    elif [ "$OS_TYPE" = "windows" ]; then
        if command -v local-voice-talk >/dev/null 2>&1; then
            OLLAMA_URL="${OLLAMA_CHECK_URL}" local-voice-talk --model "$chosen_model" --voice "$chosen_voice"
        elif [ -f "X:/voice-ai/local_voice_talk.py" ]; then
            python "X:/voice-ai/local_voice_talk.py" --model "$chosen_model" --voice "$chosen_voice"
        else
            echo -e "${RED}Error: Voice Chat engine (local-voice-talk) not installed on Windows.${NC}"
            read -r -p "Press Enter to return..."
            return 1
        fi
    else
        echo -e "${RED}Error: Voice Chat engine not found!${NC}"
        echo -e "${YELLOW}Expected executable: ${HOME}/bin/local-voice-talk or ${voice_py}${NC}"
        read -r -p "Press Enter to return..."
        return 1
    fi
}

view_logs() {
    clear
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}                       OLLAMA SERVER LOGS                             ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

    local found_log=""
    local check_logs=()
    if [ "$OS_TYPE" = "windows" ]; then
        [ -n "$LOG_FILE" ] && check_logs+=("${LOG_FILE%.*}.err" "$LOG_FILE")
        check_logs+=("X:/OLLAMA/ollama-serve.err" "X:/OLLAMA/ollama-serve.log" "/x/OLLAMA/ollama-serve.err" "/x/OLLAMA/ollama-serve.log")
        if [ -n "$LOCALAPPDATA" ]; then
            local u_local
            u_local="$(cygpath -u "$LOCALAPPDATA" 2>/dev/null || echo "$LOCALAPPDATA")"
            check_logs+=("$u_local/Ollama/server.log" "$u_local/Ollama/app.log")
        fi
        check_logs+=("$HOME/AppData/Local/Ollama/server.log" "$HOME/AppData/Local/Ollama/app.log")
    else
        [ -n "$LOG_FILE" ] && check_logs+=("$LOG_FILE")
    fi
    check_logs+=("/tmp/ollama-serve.log" "/tmp/ollama.log")

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
        echo -e "Target log paths: ${LOG_FILE:-X:/OLLAMA/ollama-serve.log}"
    fi
    echo ""
    read -r -p "Press Enter to return..."
}

interactive_menu() {
    while true; do
        clear
        show_status
        echo -e "${BOLD}${MAGENTA}----------------------------------------------------------------------${NC}"
        echo -e "${BOLD}Select an Ollama operation:${NC}\n"
        echo -e "  ${BOLD}${CYAN} 1)${NC} Start Ollama Server (${BOLD}${GREEN}Background Daemon${NC}) [ollama serve]"
        echo -e "  ${BOLD}${CYAN} 2)${NC} Start Ollama Server in ${BOLD}${YELLOW}New Terminal Window${NC} (Live Logs)"
        echo -e "  ${BOLD}${CYAN} 3)${NC} Stop Running Ollama Server"
        echo -e "  ${BOLD}${CYAN} 4)${NC} Restart Ollama Server"
        echo -e "  ${BOLD}${CYAN} 5)${NC} Chat with a Local Model (Interactive CLI: Qwen, LLaMA...)"
        echo -e "  ${BOLD}${CYAN} 6)${NC} Start Voice Chat with Local Models (${BOLD}${MAGENTA}Matrix Cast: Smith, Morpheus, Neo, Trinity, Oracle, Zion${NC})"
        echo -e "  ${BOLD}${CYAN} 7)${NC} View Server Log File (${LOG_FILE})"
        echo -e "  ${BOLD}${CYAN} 8)${NC} Return to Previous Menu\n"
        read -r -p "Enter choice [1-8, or q to return]: " o_choice

        case "$o_choice" in
            1)
                start_ollama_bg
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            2)
                start_ollama_window
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            3)
                stop_ollama
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            4)
                restart_ollama
                echo ""
                read -r -p "Press Enter to continue..."
                ;;
            5)
                run_chat_cli
                ;;
            6)
                run_voice_chat_cli
                ;;
            7)
                view_logs
                ;;
            8|[qQ])
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
    start|serve|bg)
        start_ollama_bg
        ;;
    start-window|window|terminal)
        start_ollama_window
        ;;
    stop)
        stop_ollama
        ;;
    restart)
        restart_ollama
        ;;
    status)
        show_status
        ;;
    models|list)
        if [ "$OS_TYPE" = "windows" ]; then
            "$OLLAMA_BIN" list
        else
            distrobox enter -T "$OLLAMA_CONTAINER" -- ollama list
        fi
        ;;
    chat|run)
        shift
        if [ -n "$1" ]; then
            if [ "$OS_TYPE" = "windows" ]; then
                if command -v winpty >/dev/null 2>&1 && [ -t 0 ]; then
                    winpty "$OLLAMA_BIN" run "$1"
                else
                    "$OLLAMA_BIN" run "$1"
                fi
            else
                distrobox enter "$OLLAMA_CONTAINER" -- ollama run "$1"
            fi
        else
            run_chat_cli
        fi
        ;;
    voice|voice-chat|talk|voice-talk)
        shift
        run_voice_chat_cli "$@"
        ;;
    logs)
        view_logs
        ;;
    "")
        interactive_menu
        ;;
    *)
        echo "Usage: $(basename "$0") {start|start-window|stop|restart|status|models|chat|voice|logs}"
        exit 1
        ;;
esac
