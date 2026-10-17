#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Studio & DJ Booth Mobile Web Companion Wrapper
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/mix_web_companion.py"
[ ! -f "$PY_SCRIPT" ] && PY_SCRIPT="$SCRIPT_DIR/scripts/mix_web_companion.py"

# Source config if available
if [ -f "$SCRIPT_DIR/config.env" ]; then
    source "$SCRIPT_DIR/config.env"
fi

HOST="${WEB_COMPANION_HOST:-0.0.0.0}"
PORT="${WEB_COMPANION_PORT:-8888}"
SERVICE_NAME="mp-web-companion.service"

get_lan_ip() {
    python3 -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "127.0.0.1"
}

get_pids() {
    pgrep -f "mix_web_companion.py" 2>/dev/null | tr '\n' ' '
}

case "${1:-}" in
    start)
        echo "Starting Mobile Web Companion..."
        if command -v systemctl &>/dev/null && [ -f "$HOME/.config/systemd/user/$SERVICE_NAME" ]; then
            systemctl --user daemon-reload
            systemctl --user start "$SERVICE_NAME"
            sleep 1
            if systemctl --user is-active --quiet "$SERVICE_NAME"; then
                echo "✓ Mobile Web Companion started via systemd service ($SERVICE_NAME)."
            else
                echo "⚠ systemd start failed; attempting direct background launch..."
                nohup python3 "$PY_SCRIPT" --host "$HOST" --port "$PORT" >/dev/null 2>&1 &
            fi
        else
            nohup python3 "$PY_SCRIPT" --host "$HOST" --port "$PORT" >/dev/null 2>&1 &
            sleep 1
        fi
        "$0" status
        ;;
    stop)
        echo "Stopping Mobile Web Companion..."
        if command -v systemctl &>/dev/null && [ -f "$HOME/.config/systemd/user/$SERVICE_NAME" ]; then
            systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
        fi
        pids=$(get_pids)
        if [ -n "$pids" ]; then
            kill $pids 2>/dev/null || true
            sleep 0.5
        fi
        echo "✓ Mobile Web Companion stopped."
        ;;
    restart)
        "$0" stop
        sleep 1
        "$0" start
        ;;
    status)
        LAN_IP=$(get_lan_ip)
        pids=$(get_pids)
        active=false
        if command -v systemctl &>/dev/null && systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            active=true
        elif [ -n "$pids" ]; then
            active=true
        fi

        if [ "$active" = "true" ]; then
            echo "● Mobile Web Companion is RUNNING"
            [ -n "$pids" ] && echo "  • PID(s):         $pids"
            echo "  • Local Address:  http://localhost:${PORT}"
            echo "  • Mobile LAN URL: http://${LAN_IP}:${PORT}"
        else
            echo "○ Mobile Web Companion is STOPPED"
            echo "  • Target Mobile LAN URL: http://${LAN_IP}:${PORT}"
        fi
        ;;
    enable)
        if command -v systemctl &>/dev/null && [ -f "$HOME/.config/systemd/user/$SERVICE_NAME" ]; then
            systemctl --user daemon-reload
            systemctl --user enable "$SERVICE_NAME"
            echo "✓ Autostart enabled for $SERVICE_NAME."
        else
            echo "Service file not found at $HOME/.config/systemd/user/$SERVICE_NAME"
        fi
        ;;
    disable)
        if command -v systemctl &>/dev/null; then
            systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
            echo "✓ Autostart disabled for $SERVICE_NAME."
        fi
        ;;
    open|browse)
        LAN_IP=$(get_lan_ip)
        target="http://${LAN_IP}:${PORT}"
        echo "Opening $target in default browser..."
        if command -v xdg-open &>/dev/null; then
            xdg-open "$target" &>/dev/null &
        elif command -v open &>/dev/null; then
            open "$target" &>/dev/null &
        fi
        ;;
    *)
        exec python3 "$PY_SCRIPT" "$@"
        ;;
esac
