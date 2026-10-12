#!/usr/bin/env bash
# ==============================================================================
# Beszel Monitoring Server & Agent Manager (Cross-Platform Windows/Linux)
# ==============================================================================

BESZEL_DIR="X:/BESZEL"
[ ! -d "$BESZEL_DIR" ] && [ -d "/x/BESZEL" ] && BESZEL_DIR="/x/BESZEL"
[ ! -d "$BESZEL_DIR" ] && BESZEL_DIR="$HOME/BESZEL"

BESZEL_HUB_PORT=8090
BESZEL_AGENT_PORT=45876
BESZEL_URL="http://localhost:${BESZEL_HUB_PORT}"

is_port_listening() {
    local port="$1"
    if command -v netstat.exe >/dev/null 2>&1; then
        netstat.exe -ano 2>/dev/null | grep -E ":${port}\s+.*LISTENING" >/dev/null 2>&1 && return 0
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln 2>/dev/null | grep -E ":${port}\s+" >/dev/null 2>&1 && return 0
    fi
    if command -v curl >/dev/null 2>&1; then
        curl -s -m 1 -o /dev/null "http://localhost:${port}" 2>/dev/null && return 0
    fi
    return 1
}

is_hub_running() {
    if is_port_listening "$BESZEL_HUB_PORT"; then
        return 0
    fi
    if command -v tasklist.exe >/dev/null 2>&1; then
        tasklist.exe //FI "IMAGENAME eq beszel.exe" 2>/dev/null | grep -qi "beszel.exe" && return 0
    fi
    if command -v podman >/dev/null 2>&1; then
        podman ps --filter "name=beszel" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel$" && return 0
    fi
    return 1
}

is_agent_running() {
    if is_port_listening "$BESZEL_AGENT_PORT"; then
        return 0
    fi
    if command -v tasklist.exe >/dev/null 2>&1; then
        tasklist.exe //FI "IMAGENAME eq beszel-agent.exe" 2>/dev/null | grep -qi "beszel-agent.exe" && return 0
    fi
    if command -v podman >/dev/null 2>&1; then
        podman ps --filter "name=beszel-agent" --format "{{.Names}}" 2>/dev/null | grep -q "^beszel-agent$" && return 0
    fi
    return 1
}

start_hub() {
    echo "=== STARTING BESZEL HUB ==="
    if is_hub_running; then
        echo "Beszel Hub is already running on port ${BESZEL_HUB_PORT}."
        return 0
    fi

    if [ -f "/x/MP_Mix_Manager_v0.3/start_beszel_hub.bat" ] || [ -f "X:/MP_Mix_Manager_v0.3/start_beszel_hub.bat" ]; then
        powershell.exe -NoProfile -Command "Start-Process -FilePath 'X:\MP_Mix_Manager_v0.3\start_beszel_hub.bat'"
    elif [ -f "X:/BESZEL/beszel.exe" ] || [ -f "/x/BESZEL/beszel.exe" ]; then
        powershell.exe -NoProfile -Command "Start-Process -FilePath 'X:\BESZEL\beszel.exe' -ArgumentList 'serve --http 0.0.0.0:${BESZEL_HUB_PORT} --dir X:\BESZEL\beszel-data' -WorkingDirectory 'X:\BESZEL'"
    else
        echo "Error: start_beszel_hub.bat or beszel.exe not found."
        return 1
    fi

    sleep 2
    if is_hub_running; then
        echo "Beszel Hub started successfully on port ${BESZEL_HUB_PORT}."
    else
        echo "Beszel Hub launch triggered."
    fi
}

start_agent() {
    echo "=== STARTING BESZEL AGENT ==="
    if is_agent_running; then
        echo "Beszel Agent is already running."
        return 0
    fi

    if [ -f "X:/BESZEL/start_beszel_agent.bat" ] || [ -f "/x/BESZEL/start_beszel_agent.bat" ]; then
        powershell.exe -NoProfile -Command "Start-Process -FilePath 'X:\BESZEL\start_beszel_agent.bat'"
    elif [ -f "X:/BESZEL/beszel-agent.exe" ] || [ -f "/x/BESZEL/beszel-agent.exe" ]; then
        powershell.exe -NoProfile -Command "Start-Process -FilePath 'X:\BESZEL\beszel-agent.exe' -WorkingDirectory 'X:\BESZEL'"
    else
        echo "Error: start_beszel_agent.bat or beszel-agent.exe not found."
        return 1
    fi

    sleep 1
    if is_agent_running; then
        echo "Beszel Agent started successfully."
    else
        echo "Beszel Agent launch triggered."
    fi
}

stop_hub() {
    echo "=== STOPPING BESZEL HUB ==="
    if command -v taskkill.exe >/dev/null 2>&1; then
        taskkill.exe //F //IM beszel.exe 2>/dev/null && echo "Terminated beszel.exe"
    fi
    if command -v podman >/dev/null 2>&1; then
        podman stop beszel 2>/dev/null
    fi
}

stop_agent() {
    echo "=== STOPPING BESZEL AGENT ==="
    if command -v taskkill.exe >/dev/null 2>&1; then
        taskkill.exe //F //IM beszel-agent.exe 2>/dev/null && echo "Terminated beszel-agent.exe"
    fi
    if command -v podman >/dev/null 2>&1; then
        podman stop beszel-agent 2>/dev/null
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

while true; do
    clear
    echo "======================================================================"
    echo "                    BESZEL MONITORING SUITE STATUS                    "
    echo "======================================================================"
    echo ""
    if is_hub_running; then
        echo -e "  Beszel Hub:      \033[1;32m● RUNNING\033[0m (Port :${BESZEL_HUB_PORT})"
    else
        echo -e "  Beszel Hub:      \033[1;31m○ STOPPED\033[0m"
    fi

    if is_agent_running; then
        echo -e "  Beszel Agent:    \033[1;32m● RUNNING\033[0m (Port :${BESZEL_AGENT_PORT})"
    else
        echo -e "  Beszel Agent:    \033[1;31m○ STOPPED\033[0m"
    fi

    if command -v nvidia-smi.exe >/dev/null 2>&1; then
        gpu_info=$(nvidia-smi.exe --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null)
        echo "  NVIDIA GPU:      ${gpu_info}"
    fi
    echo ""
    echo "----------------------------------------------------------------------"
    echo "Select a Beszel operation:"
    echo ""
    echo "   1) Start Both (Beszel Hub & Agent)"
    echo "   2) Start Beszel Hub Only (Web Dashboard Server on :8090)"
    echo "   3) Start Beszel Agent Only (Metrics & GPU Passthrough)"
    echo "   4) Open Beszel Web Dashboard in Browser (${BESZEL_URL})"
    echo "   5) Stop Both (Beszel Hub & Agent)"
    echo "   6) Stop Beszel Hub"
    echo "   7) Stop Beszel Agent"
    echo "   8) Restart Both (Re-launch Native Services)"
    echo "   9) View Beszel Logs (Hub & Agent)"
    echo "  10) Return to Previous Menu"
    echo ""
    read -r -p "Enter choice [1-10, or q to return]: " b_choice

    case "$b_choice" in
        1) start_hub; start_agent; sleep 1 ;;
        2) start_hub; sleep 1 ;;
        3) start_agent; sleep 1 ;;
        4) open_dashboard; sleep 1 ;;
        5) stop_hub; stop_agent; sleep 1 ;;
        6) stop_hub; sleep 1 ;;
        7) stop_agent; sleep 1 ;;
        8) stop_hub; stop_agent; sleep 1; start_hub; start_agent; sleep 1 ;;
        9) view_logs ;;
        10|[qQ]) break ;;
        *) echo "Invalid option!"; sleep 1 ;;
    esac
done