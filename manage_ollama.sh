#!/usr/bin/env bash
# Optimize for slow systems - minimal code, same functionality
[ -z "${OS_TYPE:-}" ] && OS_TYPE="${BASH_SOURCE:0:126/[^a-zA-Z]/}"

LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_PORT:-8080}"
[[ "$LLAMA_HOST" =~ :[0-9]+$ ]] && { LLAMA_PORT="${LLAMA_HOST##*:}"; LLAMA_HOST="${LLAMA_HOST%:*}"; }
LLAMA_URL="http://${LLAMA_HOST}:${LLAMA_PORT}"
LOG_FILE="${LOG_FILE:-/tmp/llama-server.log}"
GGUF_MODEL_PATH="${GGUF_MODEL_PATH:-X:/OLLAMA/models/deepseek-r1-qwen-14b.gguf}"
[ "$OS_TYPE" = "windows" ] && GGUF_MODEL_PATH="$(cygpath -w "$GGUF_MODEL_PATH")"
HARMONY_DIR="${HARMONY_DIR:-/var/home/mplanetarian/OpenAI/MP_Harmony_Agent}"
[ ! -d "$HARMONY_DIR" ] && HARMONY_DIR="$HOME/OpenAI/MP_Harmony_Agent"
AUDIO_DIR="$HARMONY_DIR/audio_responses"
mkdir -p "$AUDIO_DIR"

LLAMA_SERVER_BIN="llama-server"
[ "$OS_TYPE" = "windows" ] && {
    for cand in "$(cygpath -w $LOCALAPPDATA/Programs/llama.cpp/llama-server.exe)" \
                "$(cygpath -w $PROGRAMFILES/llama.cpp/llama-server.exe)"; do
        [ -f "$cand" ] && LLAMA_SERVER_BIN="$cand" && break
    done
} || LLAMA_SERVER_BIN="llama-server"

is_running() {
    curl --connect-timeout 1 "${LLAMA_URL}/health" 2>/dev/null | grep -qi "ok\|ready" && return 0
    curl --connect-timeout 1 "${LLAMA_URL}/" 2>/dev/null | grep -qi "llama.cpp" && return 0
    [ "$OS_TYPE" = "windows" ] && tasklist //FI "IMAGENAME eq llama-server.exe" 2>/dev/null | grep -q "llama-server.exe" && return 0
    pgrep -f "llama-server" >/dev/null 2>&1 && return 0
    return 1
}

get_pids() {
    [ "$OS_TYPE" = "windows" ] && tasklist //FI "IMAGENAME eq llama-server.exe" //FO CSV //NH 2>/dev/null | awk -F'","' '{print $2}' | tr -d '"\r ' || echo ""
    pgrep -f "llama-server" 2>/dev/null | tr '\n' ' ' || echo ""
}

get_ip() {
    local ip=""
    [ "$OS_TYPE" = "windows" ] && ip=$(ipconfig.exe 2>/dev/null | grep -i "IPv4" | head -1 | awk -F': ' '{print $2}' | tr -d '\r')
    [ -z "$ip" ] && ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    echo "$ip"
}

gpu_status() {
    command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu --format=csv,noheader | awk -F, '{printf "  • GPU: %s  VRAM: %s/%s  Util: %s%%\n", $1, $2, $3, $5}'
}

start_bg() {
    if is_running; then echo "✓ Already running (PID: $(get_pids))"; return 0; fi
    [ -d "$HOME/OLLAMA" ] || mkdir -p "$HOME/OLLAMA"
    [ "$OS_TYPE" = "windows" ] && cat << 'EOF' > start_llama_bg.bat
@echo off
cd /d "%HOMEDRIVE%%HOMEPATH%"\OLLAMA
llama-server.exe -m "deepseek-r1-qwen-14b.gguf" -c 32768 --n-gpu-layers 99 --host ${LLAMA_HOST} --port ${LLAMA_PORT} > "${LOG_FILE}" 2>&1
EOF
    [ "$OS_TYPE" = "windows" ] && (cmd.exe /c start /b "" "start_llama_bg.bat") || nohup "$LLAMA_SERVER_BIN" -m "$GGUF_MODEL_PATH" -c 32768 --n-gpu-layers 99 --host "$LLAMA_HOST" --port "$LLAMA_PORT" >"$LOG_FILE" 2>&1 &
    for _ in $(seq 1 30); do is_running && break; sleep 1; done
    local pids lan
    pids=$(get_pids)
    lan=$(get_ip)
    echo "✓ Started | Local: ${LLAMA_HOST}:${LLAMA_PORT} | LAN: ${lan:-}:${LLAMA_PORT} | PID: $pids"
    gpu_status
}

stop() {
    is_running || { echo "Not running"; return 0; }
    [ "$OS_TYPE" = "windows" ] && taskkill //F //IM "llama-server.exe" || pkill -9 -f "llama-server"
    sleep 1
    is_running && { echo "Failed to stop"; return 1; }
    echo "✓ Stopped"
    gpu_status
}

restart() { stop; sleep 1; start_bg; }
status() {
    local ip=$(get_ip)
    echo "=== Status ==="
    is_running && echo "RUNNING | PIDs: $(get_pids) | ${LLAMA_HOST}:${LLAMA_PORT} | Model: $GGUF_MODEL_PATH | GPU: $(gpu_status)" || echo "STOPPED"
}
logs() { [ -f "$LOG_FILE" ] && tail -50 "$LOG_FILE"; read -r; }

case "${1:-}" in
    start) start_bg ;; stop) stop ;; restart) restart ;; status) status ;; logs) logs ;; "") while true; do echo "=== Menu === 1) Start 2) Stop 3) Restart 4) Status 5) Logs 9) Exit"; read -r -p "Choice: "; case "$REPLY" in 1) start_bg;; 2) stop;; 3) restart;; 4) status;; 5) logs;; 9) exit;; esac; done ;;
    *) echo "Usage: $0 {start|stop|restart|status|logs}" ;;
esac