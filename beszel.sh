#!/usr/bin/env bash
# ==============================================================================
# Beszel Monitoring Server & Agent Manager (Cross-Platform Windows/Linux)
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
fi

BESZEL_HUB_PORT="${BESZEL_HUB_PORT:-8090}"
BESZEL_AGENT_PORT="${BESZEL_AGENT_PORT:-45876}"
BESZEL_URL="http://localhost:${BESZEL_HUB_PORT}"

if [ "$OS_TYPE" = "windows" ]; then
    BESZEL_DIR="X:/BESZEL"
    [ ! -d "$BESZEL_DIR" ] && [ -d "/x/BESZEL" ] && BESZEL_DIR="/x/BESZEL"
    [ ! -d "$BESZEL_DIR" ] && [ -d "C:/BESZEL" ] && BESZEL_DIR="C:/BESZEL"
    [ ! -d "$BESZEL_DIR" ] && BESZEL_DIR="$HOME/BESZEL"
else
    BESZEL_DIR="${BESZEL_DIR:-/var/home/mplanetarian/beszel-hub}"
    [ ! -d "$BESZEL_DIR" ] && [ -d "$HOME/beszel-hub" ] && BESZEL_DIR="$HOME/beszel-hub"
fi

is_port_listening() {
    local port=$1
    if command -v ss >/dev/null 2>&1; then
        ss -tuln 2>/dev/null | grep -E ":${port}\b" >/dev/null && return 0
    fi
    if command -v netstat.exe >/dev/null 2>&1; then
        netstat.exe -ano 2>/dev/null | grep -E ":${port}\s+.*LISTENING" >/dev/null && return 0
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln 2>/dev/null | grep -E ":${port}\b" >/dev/null && return 0
    fi
    if command -v curl >/dev/null 2>&1; then
        curl -s -m 1 -o /dev/null "http://localhost:${port}" 2>/dev/null && return 0
    fi
    return 1
}

is_running() {
    local name=$1
    local port=$2
    if [ -n "$port" ] && is_port_listening "$port"; then
        return 0
    fi
    if [ "$name" = "beszel-agent" ] || [ "$name" = "agent" ]; then
        if is_port_listening 45876 || is_port_listening 8091; then
            return 0
        fi
    fi

    if [ "$OS_TYPE" = "windows" ]; then
        if command -v tasklist.exe >/dev/null 2>&1; then
            tasklist.exe //FI "IMAGENAME eq ${name}.exe" 2>/dev/null | grep -qi "${name}.exe" && return 0
        fi
    fi

    if command -v podman >/dev/null 2>&1; then
        podman ps --filter "name=${name}" --format "{{.Names}}" 2>/dev/null | grep -q "^${name}$" && return 0
    fi
    if command -v docker >/dev/null 2>&1; then
        docker ps --filter "name=${name}" --format "{{.Names}}" 2>/dev/null | grep -q "^${name}$" && return 0
    fi

    if [ "$name" = "beszel" ] || [ "$name" = "hub" ]; then
        if pgrep -f "beszel.*serve" >/dev/null 2>&1 || pgrep -x "beszel" >/dev/null 2>&1; then
            return 0
        fi
    elif [ "$name" = "beszel-agent" ] || [ "$name" = "agent" ]; then
        if pgrep -f "beszel-agent" >/dev/null 2>&1 || pgrep -x "beszel-agent" >/dev/null 2>&1; then
            return 0
        fi
    fi

    return 1
}

start_hub_linux() {
    if is_running "beszel" "$BESZEL_HUB_PORT"; then
        echo "Beszel Hub is already running on port ${BESZEL_HUB_PORT}."
        return 0
    fi

    echo "Starting Beszel Hub..."
    if command -v podman >/dev/null 2>&1; then
        local sock_path="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"
        if command -v systemctl >/dev/null 2>&1; then
            if ! systemctl --user is-active podman.socket >/dev/null 2>&1 || [ ! -S "$sock_path" ]; then
                systemctl --user start podman.socket 2>/dev/null || true
            fi
        fi

        if podman ps -a --filter "name=beszel" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel$"; then
            podman start beszel >/dev/null 2>&1 || true
            sleep 1
        fi

        if ! podman ps --filter "name=beszel" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel$"; then
            if [ -f "$BESZEL_DIR/launch_beszel_hub_replace.sh" ]; then
                (cd "$BESZEL_DIR" && bash ./launch_beszel_hub_replace.sh >/dev/null 2>&1 || true)
            elif [ -f "/var/home/mplanetarian/beszel-hub/launch_beszel_hub_replace.sh" ]; then
                (cd "/var/home/mplanetarian/beszel-hub" && bash ./launch_beszel_hub_replace.sh >/dev/null 2>&1 || true)
            else
                mkdir -p "$BESZEL_DIR/beszel_data" 2>/dev/null || true
                podman run --replace -d \
                  --name beszel \
                  --restart unless-stopped \
                  -p "${BESZEL_HUB_PORT}:8090" \
                  -v "$BESZEL_DIR/beszel_data:/beszel_data:Z" \
                  docker.io/henrygd/beszel:latest >/dev/null 2>&1 || true
            fi
        fi
    elif command -v docker >/dev/null 2>&1; then
        if docker ps -a --filter "name=beszel" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel$"; then
            docker start beszel >/dev/null 2>&1 || true
        else
            docker run -d --name beszel --restart unless-stopped -p "${BESZEL_HUB_PORT}:8090" docker.io/henrygd/beszel:latest >/dev/null 2>&1 || true
        fi
    elif command -v beszel >/dev/null 2>&1 && [ "$(readlink -f "$(command -v beszel)")" != "$(readlink -f "$0")" ]; then
        nohup beszel serve --http "0.0.0.0:${BESZEL_HUB_PORT}" >/dev/null 2>&1 &
    fi

    sleep 2
    if is_running "beszel" "$BESZEL_HUB_PORT"; then
        echo "Beszel Hub started successfully on port ${BESZEL_HUB_PORT}."
    else
        echo "Beszel Hub launch triggered."
    fi
}

start_agent_linux() {
    if is_running "beszel-agent" "$BESZEL_AGENT_PORT"; then
        echo "Beszel Agent is already running."
        return 0
    fi

    echo "Starting Beszel Agent..."
    if command -v podman >/dev/null 2>&1; then
        local sock_path="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"
        if command -v systemctl >/dev/null 2>&1; then
            if ! systemctl --user is-active podman.socket >/dev/null 2>&1 || [ ! -S "$sock_path" ]; then
                systemctl --user start podman.socket 2>/dev/null || true
            fi
        fi

        if podman ps -a --filter "name=beszel-agent" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel-agent$"; then
            podman start beszel-agent >/dev/null 2>&1 || true
            sleep 1
        fi

        if ! podman ps --filter "name=beszel-agent" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel-agent$"; then
            if [ -f "$BESZEL_DIR/launch_beszel_agent_replace.sh" ]; then
                (cd "$BESZEL_DIR" && bash ./launch_beszel_agent_replace.sh >/dev/null 2>&1 || true)
            elif [ -f "/var/home/mplanetarian/beszel-hub/launch_beszel_agent_replace.sh" ]; then
                (cd "/var/home/mplanetarian/beszel-hub" && bash ./launch_beszel_agent_replace.sh >/dev/null 2>&1 || true)
            else
                podman run --replace -d \
                  --name beszel-agent \
                  --network host \
                  --restart unless-stopped \
                  --security-opt label=disable \
                  --device nvidia.com/gpu=all \
                  --group-add keep-groups \
                  --ipc=host \
                  -v "$sock_path:/var/run/docker.sock:ro" \
                  -e PORT="${BESZEL_AGENT_PORT}" \
                  -e HUB_URL="${BESZEL_URL}" \
                  docker.io/henrygd/beszel-agent-nvidia:latest >/dev/null 2>&1 || true
            fi
        fi
    elif command -v docker >/dev/null 2>&1; then
        if docker ps -a --filter "name=beszel-agent" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel-agent$"; then
            docker start beszel-agent >/dev/null 2>&1 || true
        fi
    elif command -v beszel-agent >/dev/null 2>&1; then
        nohup beszel-agent >/dev/null 2>&1 &
    fi

    sleep 2
    if is_running "beszel-agent" "$BESZEL_AGENT_PORT"; then
        echo "Beszel Agent started successfully."
    else
        echo "Beszel Agent launch triggered."
    fi
}

start_hub_windows() {
    local cmd="${1:-}"
    if is_running "beszel" "$BESZEL_HUB_PORT"; then
        echo "Beszel Hub is already running on port ${BESZEL_HUB_PORT}."
        return 0
    fi

    if [ -z "$cmd" ]; then
        for cand in \
            "X:\MP_Mix_Manager_v0.4\start_beszel_hub.bat" \
            "X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat" \
            "X:\BESZEL\start_beszel_hub.bat" \
            "X:\BESZEL\beszel.exe" \
            "C:\BESZEL\beszel.exe"; do
            local cand_unix; cand_unix=$(echo "$cand" | sed 's|\\|/|g; s|^X:|/x|i; s|^C:|/c|i')
            if [ -f "$cand_unix" ] || [ -f "$cand" ]; then
                cmd="$cand"
                break
            fi
        done
        [ -z "$cmd" ] && cmd="X:\BESZEL\beszel.exe"
    fi

    echo "Starting Beszel Hub on Windows..."
    if command -v powershell.exe >/dev/null 2>&1; then
        if [[ "$cmd" == *.bat ]]; then
            powershell.exe -NoProfile -Command "Start-Process -FilePath '$cmd' -WorkingDirectory 'X:\BESZEL'" || powershell.exe -NoProfile -Command "Start-Process -FilePath '$cmd'"
        else
            powershell.exe -NoProfile -Command "Start-Process -FilePath '$cmd' -ArgumentList 'serve --http 0.0.0.0:${BESZEL_HUB_PORT} --dir X:\BESZEL\beszel-data' -WorkingDirectory 'X:\BESZEL'" || powershell.exe -NoProfile -Command "Start-Process -FilePath '$cmd' -WorkingDirectory 'X:\BESZEL'"
        fi
    else
        cmd.exe /c start "" "$cmd" 2>/dev/null || true
    fi

    sleep 2
    if is_running "beszel" "$BESZEL_HUB_PORT"; then
        echo "Beszel Hub started successfully on port ${BESZEL_HUB_PORT}."
    else
        echo "Beszel Hub launch triggered."
    fi
}

start_agent_windows() {
    local cmd="${1:-}"
    if is_running "beszel-agent" "$BESZEL_AGENT_PORT"; then
        echo "Beszel Agent is already running on port ${BESZEL_AGENT_PORT}."
        return 0
    fi

    if [ -z "$cmd" ]; then
        for cand in \
            "X:\BESZEL\start_beszel_agent.bat" \
            "X:\BESZEL\beszel-agent.exe" \
            "C:\BESZEL\beszel-agent.exe"; do
            local cand_unix; cand_unix=$(echo "$cand" | sed 's|\\|/|g; s|^X:|/x|i; s|^C:|/c|i')
            if [ -f "$cand_unix" ] || [ -f "$cand" ]; then
                cmd="$cand"
                break
            fi
        done
        [ -z "$cmd" ] && cmd="X:\BESZEL\beszel-agent.exe"
    fi

    echo "Starting Beszel Agent on Windows..."
    if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "Start-Process -FilePath '$cmd' -WorkingDirectory 'X:\BESZEL'"
    else
        cmd.exe /c start "" "$cmd" 2>/dev/null || true
    fi

    sleep 2
    if is_running "beszel-agent" "$BESZEL_AGENT_PORT"; then
        echo "Beszel Agent started successfully."
    else
        echo "Beszel Agent launch triggered."
    fi
}

start() {
    local name="${1:-beszel}"
    local port="${2:-$BESZEL_HUB_PORT}"
    local cmd="${3:-}"

    if [ "$name" = "beszel" ] || [ "$name" = "hub" ]; then
        if [ "$OS_TYPE" = "windows" ]; then
            start_hub_windows "$cmd"
        else
            start_hub_linux
        fi
    elif [ "$name" = "beszel-agent" ] || [ "$name" = "agent" ]; then
        if [ "$OS_TYPE" = "windows" ]; then
            start_agent_windows "$cmd"
        else
            start_agent_linux
        fi
    fi
}

stop_hub_windows() {
    if command -v taskkill.exe >/dev/null 2>&1; then
        taskkill.exe //F //IM "beszel.exe" 2>/dev/null && echo "Terminated beszel.exe"
    fi
}

stop_agent_windows() {
    if command -v taskkill.exe >/dev/null 2>&1; then
        taskkill.exe //F //IM "beszel-agent.exe" 2>/dev/null && echo "Terminated beszel-agent.exe"
    fi
}

stop_hub_linux() {
    if command -v podman >/dev/null 2>&1; then
        podman stop beszel 2>/dev/null && echo "Stopped beszel podman container."
    fi
    if command -v docker >/dev/null 2>&1; then
        docker stop beszel 2>/dev/null
    fi
    pkill -f "beszel.*serve" 2>/dev/null || true
}

stop_agent_linux() {
    if command -v podman >/dev/null 2>&1; then
        podman stop beszel-agent 2>/dev/null && echo "Stopped beszel-agent podman container."
    fi
    if command -v docker >/dev/null 2>&1; then
        docker stop beszel-agent 2>/dev/null
    fi
    pkill -f "beszel-agent" 2>/dev/null || true
}

stop() {
    local name="${1:-beszel}"
    if [ "$name" = "beszel" ] || [ "$name" = "hub" ]; then
        if [ "$OS_TYPE" = "windows" ]; then
            stop_hub_windows
        else
            stop_hub_linux
        fi
    elif [ "$name" = "beszel-agent" ] || [ "$name" = "agent" ]; then
        if [ "$OS_TYPE" = "windows" ]; then
            stop_agent_windows
        else
            stop_agent_linux
        fi
    else
        if [ "$OS_TYPE" = "windows" ]; then
            command -v taskkill.exe >/dev/null 2>&1 && taskkill.exe //F //IM "${name}.exe" 2>/dev/null
        fi
        command -v podman >/dev/null 2>&1 && podman stop "$name" 2>/dev/null
        command -v docker >/dev/null 2>&1 && docker stop "$name" 2>/dev/null
        pkill -f "$name" 2>/dev/null || true
    fi
}

open_dashboard() {
    echo "Opening ${BESZEL_URL} in browser..."
    if [ "$OS_TYPE" = "windows" ]; then
        if command -v cmd.exe >/dev/null 2>&1; then
            cmd.exe /c start "${BESZEL_URL}"
        fi
    elif [ "$OS_TYPE" = "macos" ]; then
        open "${BESZEL_URL}" 2>/dev/null || true
    else
        if command -v xdg-open >/dev/null 2>&1; then
            xdg-open "${BESZEL_URL}" >/dev/null 2>&1 &
        elif command -v google-chrome >/dev/null 2>&1; then
            google-chrome "${BESZEL_URL}" >/dev/null 2>&1 &
        elif command -v firefox >/dev/null 2>&1; then
            firefox "${BESZEL_URL}" >/dev/null 2>&1 &
        fi
    fi
}

view_logs() {
    echo "=== BESZEL LOGS ==="
    if [ "$OS_TYPE" = "windows" ]; then
        if [ -d "X:/BESZEL/beszel-data" ] && [ -f "X:/BESZEL/beszel-data/beszel.log" ]; then
            tail -n 50 "X:/BESZEL/beszel-data/beszel.log" 2>/dev/null
        elif [ -f "X:/BESZEL/beszel.log" ]; then
            tail -n 50 "X:/BESZEL/beszel.log" 2>/dev/null
        else
            echo "No local log file found in X:/BESZEL."
        fi
    else
        if command -v podman >/dev/null 2>&1; then
            echo "--- Beszel Hub Logs (Podman) ---"
            podman logs --tail 30 beszel 2>/dev/null || echo "No beszel container logs."
            echo ""
            echo "--- Beszel Agent Logs (Podman) ---"
            podman logs --tail 30 beszel-agent 2>/dev/null || echo "No beszel-agent container logs."
        elif [ -f "$BESZEL_DIR/beszel_data/beszel.log" ]; then
            tail -n 50 "$BESZEL_DIR/beszel_data/beszel.log" 2>/dev/null
        elif [ -f "$BESZEL_DIR/beszel-data/beszel.log" ]; then
            tail -n 50 "$BESZEL_DIR/beszel-data/beszel.log" 2>/dev/null
        else
            echo "No container or local log file found."
        fi
    fi
    read -r -p "Press [Enter] to continue..."
}

show_status() {
    echo "======================================================================"
    echo "                    BESZEL MONITORING SUITE STATUS                    "
    echo "======================================================================"
    echo ""
    if is_running "beszel" "$BESZEL_HUB_PORT"; then
        echo -e "  Beszel Hub:      \033[1;32m● RUNNING\033[0m (Port :${BESZEL_HUB_PORT})"
    else
        echo -e "  Beszel Hub:      \033[1;31m○ STOPPED\033[0m"
    fi
    if is_running "beszel-agent" "$BESZEL_AGENT_PORT"; then
        echo -e "  Beszel Agent:    \033[1;32m● RUNNING\033[0m (Port :${BESZEL_AGENT_PORT})"
    else
        echo -e "  Beszel Agent:    \033[1;31m○ STOPPED\033[0m"
    fi
    if [ "$OS_TYPE" = "windows" ] && command -v nvidia-smi.exe >/dev/null 2>&1; then
        nvidia-smi.exe --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null
    elif command -v nvidia-smi >/dev/null 2>&1; then
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null
    fi
    echo ""
}

interactive_menu() {
    while true; do
        clear
        show_status
        echo "----------------------------------------------------------------------"
        echo "Select a Beszel operation:"
        echo ""
        echo "   1) Start Both (Beszel Hub & Agent)"
        echo "   2) Start Beszel Hub Only"
        echo "   3) Start Beszel Agent Only"
        echo "   4) Open Beszel Web Dashboard in Browser"
        echo "   5) Stop Both"
        echo "   6) Stop Beszel Hub"
        echo "   7) Stop Beszel Agent"
        echo "   8) Restart Both"
        echo "   9) View Beszel Logs"
        echo "  10) Return to Previous Menu"
        echo ""
        read -r -p "Enter choice [1-10, or q to return]: " b_choice

        case "$b_choice" in
            1) start "beszel" "$BESZEL_HUB_PORT"; start "beszel-agent" "$BESZEL_AGENT_PORT"; sleep 1 ;;
            2) start "beszel" "$BESZEL_HUB_PORT"; sleep 1 ;;
            3) start "beszel-agent" "$BESZEL_AGENT_PORT"; sleep 1 ;;
            4) open_dashboard; sleep 1 ;;
            5) stop "beszel"; stop "beszel-agent"; sleep 1 ;;
            6) stop "beszel"; sleep 1 ;;
            7) stop "beszel-agent"; sleep 1 ;;
            8) stop "beszel"; stop "beszel-agent"; sleep 1; start "beszel" "$BESZEL_HUB_PORT"; start "beszel-agent" "$BESZEL_AGENT_PORT"; sleep 1 ;;
            9) view_logs ;;
            10|[qQ]) break ;;
            *) echo "Invalid option!"; sleep 1 ;;
        esac
    done
}

case "${1:-}" in
    start|start-both)
        start "beszel" "$BESZEL_HUB_PORT"
        start "beszel-agent" "$BESZEL_AGENT_PORT"
        ;;
    start-hub|hub)
        start "beszel" "$BESZEL_HUB_PORT"
        ;;
    start-agent|agent)
        start "beszel-agent" "$BESZEL_AGENT_PORT"
        ;;
    open|web|browser|dashboard)
        open_dashboard
        ;;
    stop|stop-both)
        stop "beszel"
        stop "beszel-agent"
        ;;
    stop-hub)
        stop "beszel"
        ;;
    stop-agent)
        stop "beszel-agent"
        ;;
    restart)
        stop "beszel"
        stop "beszel-agent"
        sleep 1
        start "beszel" "$BESZEL_HUB_PORT"
        start "beszel-agent" "$BESZEL_AGENT_PORT"
        ;;
    logs)
        view_logs
        ;;
    status)
        show_status
        ;;
    "")
        interactive_menu
        ;;
    *)
        echo "Usage: $(basename "$0") {start|start-hub|start-agent|open|stop|stop-hub|stop-agent|restart|logs|status}"
        exit 1
        ;;
esac
