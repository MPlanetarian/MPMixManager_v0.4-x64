#!/usr/bin/env bash
# ==============================================================================
# Beszel Monitoring Server & Agent Manager (Cross-Platform Windows/Linux)
# ==============================================================================
BESZEL_HUB_PORT=8090
BESZEL_AGENT_PORT=8091
BESZEL_URL="http://localhost:${BESZEL_HUB_PORT}"

is_port_listening() {
    local port=$1
    if command -v netstat >/dev/null 2>&1; then
        netstat -an | grep LISTENING | grep ":$port " >/dev/null && return 0
    fi
    if command -v curl >/dev/null 2>&1; then
        curl -s -m 1 -o /dev/null "http://localhost:${port}" 2>/dev/null && return 0
    fi
    return 1
}

is_running() {
    local name=$1
    local port=$2
    if is_port_listening "$port"; then
        return 0
    fi
    if command -v tasklist.exe >/dev/null 2>&1; then
        tasklist.exe //FI "IMAGENAME eq ${name}.exe" 2>/dev/null | grep -qi "${name}.exe" && return 0
    fi
    if command -v podman >/dev/null 2>&1; then
        podman ps --filter "name=${name}" --format "{{.Names}}" 2>/dev/null | grep -q "^${name}$" && return 0
    fi
    return 1
}

start() {
    local name=$1
    local port=$2
    local cmd=$3
    if is_running "$name" "$port"; then
        echo "${name} is already running on port ${port}."
        return 0
    fi

    powershell.exe -NoProfile -Command "Start-Process -FilePath '$cmd' -ArgumentList 'serve --http 0.0.0.0:${port} --dir X:\BESZEL\beszel-data' -WorkingDirectory 'X:\BESZEL'" || powershell.exe -NoProfile -Command "Start-Process -FilePath '$cmd' -WorkingDirectory 'X:\BESZEL'"

    sleep 2
    if is_running "$name" "$port"; then
        echo "${name} started successfully on port ${port}."
    else
        echo "${name} launch triggered."
    fi
}

stop() {
    local name=$1
    if command -v taskkill.exe >/dev/null 2>&1; then
        taskkill.exe //F //IM "${name}.exe" 2>/dev/null && echo "Terminated ${name}.exe"
    fi
    if command -v podman >/dev/null 2>&1; then
        podman stop "$name" 2>/dev/null
    fi
}

open_dashboard() {
    echo "Opening ${BESZEL_URL} in browser..."
    if command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start "${BESZEL_URL}"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "${BESZEL_URL}"
    fi
}

view_logs() {
    echo "=== BESZEL LOGS ==="
    if [ -d "X:/BESZEL/beszel-data" ]; then
        tail -n 50 "X:/BESZEL/beszel-data/beszel.log" 2>/dev/null || echo "No local log file found in X:/BESZEL/beszel-data."
    elif command -v podman >/dev/null 2>&1; then
        podman logs --tail 50 beszel 2>/dev/null
    fi
    read -r -p "Press [Enter] to continue..."
}

interactive_menu() {
    while true; do
        clear
        echo "======================================================================"
        echo "                    BESZEL MONITORING SUITE STATUS                    "
        echo "======================================================================"
        echo ""
        echo -e "  Beszel Hub:      \033[1;32m● RUNNING\033[0m (Port :${BESZEL_HUB_PORT})" || echo -e "  Beszel Hub:      \033[1;31m○ STOPPED\033[0m"
        echo -e "  Beszel Agent:    \033[1;32m● RUNNING\033[0m (Port :${BESZEL_AGENT_PORT})" || echo -e "  Beszel Agent:    \033[1;31m○ STOPPED\033[0m"
        if command -v nvidia-smi.exe >/dev/null 2>&1; then
            nvidia-smi.exe --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null
        fi
        echo ""
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
            1) start "beszel" "$BESZEL_HUB_PORT" "X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat" || start "beszel" "$BESZEL_HUB_PORT" "X:\BESZEL\beszel.exe"; start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\start_beszel_agent.bat" || start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\beszel-agent.exe"; sleep 1 ;;
            2) start "beszel" "$BESZEL_HUB_PORT" "X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat" || start "beszel" "$BESZEL_HUB_PORT" "X:\BESZEL\beszel.exe"; sleep 1 ;;
            3) start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\start_beszel_agent.bat" || start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\beszel-agent.exe"; sleep 1 ;;
            4) open_dashboard; sleep 1 ;;
            5) stop "beszel"; stop "beszel-agent"; sleep 1 ;;
            6) stop "beszel"; sleep 1 ;;
            7) stop "beszel-agent"; sleep 1 ;;
            8) stop "beszel"; stop "beszel-agent"; sleep 1; start "beszel" "$BESZEL_HUB_PORT" "X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat" || start "beszel" "$BESZEL_HUB_PORT" "X:\BESZEL\beszel.exe"; start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\start_beszel_agent.bat" || start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\beszel-agent.exe"; sleep 1 ;;
            9) view_logs ;;
            10|[qQ]) break ;;
            *) echo "Invalid option!"; sleep 1 ;;
        esac
    done
}

case "${1:-}" in
    start|start-both)
        start "beszel" "$BESZEL_HUB_PORT" "X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat" || start "beszel" "$BESZEL_HUB_PORT" "X:\BESZEL\beszel.exe"
        start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\start_beszel_agent.bat" || start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\beszel-agent.exe"
        ;;
    start-hub|hub)
        start "beszel" "$BESZEL_HUB_PORT" "X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat" || start "beszel" "$BESZEL_HUB_PORT" "X:\BESZEL\beszel.exe"
        ;;
    start-agent|agent)
        start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\start_beszel_agent.bat" || start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\beszel-agent.exe"
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
        start "beszel" "$BESZEL_HUB_PORT" "X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat" || start "beszel" "$BESZEL_HUB_PORT" "X:\BESZEL\beszel.exe"
        start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\start_beszel_agent.bat" || start "beszel-agent" "$BESZEL_AGENT_PORT" "X:\BESZEL\beszel-agent.exe"
        ;;
    logs)
        view_logs
        ;;
    status)
        echo "Beszel Hub Port: $BESZEL_HUB_PORT"
        echo "Beszel Agent Port: $BESZEL_AGENT_PORT"
        ;;
    "")
        interactive_menu
        ;;
    *)
        echo "Usage: $(basename "$0") {start|start-hub|start-agent|open|stop|stop-hub|stop-agent|restart|logs|status}"
        exit 1
        ;;
esac