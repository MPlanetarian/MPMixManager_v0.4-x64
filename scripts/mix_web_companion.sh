#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.4 - Studio & DJ Booth Mobile Web Companion Wrapper
# ==============================================================================
# Runs the zero-dependency companion server (mix_web_companion.py) and can
# register it as a login/boot service:
#
#   Linux   -> systemd --user unit  (mp-web-companion.service)
#   macOS   -> launchd LaunchAgent   (com.mplanetarian.mp-web-companion)
#
# Usage:
#   mix_web_companion.sh start|stop|restart|status
#   mix_web_companion.sh install     create the service, enable it, start it
#   mix_web_companion.sh uninstall   stop and remove the service
#   mix_web_companion.sh enable      enable autostart (creating the unit if needed)
#   mix_web_companion.sh disable     disable autostart
#   mix_web_companion.sh logs        show the service log
#   mix_web_companion.sh open        open the dashboard in a browser
#   mix_web_companion.sh <args...>   run the Python server directly
# ==============================================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"
[ "$(basename "$SCRIPT_DIR")" = "scripts" ] && APP_DIR="$(dirname "$SCRIPT_DIR")"

PY_SCRIPT="$SCRIPT_DIR/mix_web_companion.py"
[ ! -f "$PY_SCRIPT" ] && PY_SCRIPT="$APP_DIR/scripts/mix_web_companion.py"

# Source config if available (app root first, then the script directory)
if [ -f "$APP_DIR/config.env" ]; then
    # shellcheck disable=SC1091
    source "$APP_DIR/config.env"
elif [ -f "$SCRIPT_DIR/config.env" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/config.env"
fi

HOST="${WEB_COMPANION_HOST:-0.0.0.0}"
PORT="${WEB_COMPANION_PORT:-8888}"
SERVICE_NAME="mp-web-companion.service"
LAUNCHD_LABEL="com.mplanetarian.mp-web-companion"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LOG_DIR="$HOME/.config/mix-manager"
LOG_FILE="$LOG_DIR/mp-web-companion.log"
UNIT_PATH="$HOME/.config/systemd/user/$SERVICE_NAME"

is_macos() { [ "$(uname -s 2>/dev/null)" = "Darwin" ]; }

# systemd --user is only useful when this is a real login session with a bus.
have_user_systemd() {
    command -v systemctl >/dev/null 2>&1 || return 1
    systemctl --user show-environment >/dev/null 2>&1 || return 1
}

# Pick an interpreter that can actually run the server. macOS has no "python3"
# in a non-interactive launchd PATH, so the absolute system interpreter is used.
resolve_python() {
    local cand
    for cand in "${MP_PYTHON:-}" \
                "$APP_DIR/scripts/venv/bin/python3" \
                "$APP_DIR/.venv/bin/python3" \
                "$(command -v python3 2>/dev/null)" \
                /usr/bin/python3 \
                /opt/homebrew/bin/python3 \
                /usr/local/bin/python3 \
                "$(command -v python 2>/dev/null)"; do
        [ -n "$cand" ] && [ -x "$cand" ] || continue
        if "$cand" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}

PYTHON_BIN="$(resolve_python || true)"

get_lan_ip() {
    "${PYTHON_BIN:-python3}" -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "127.0.0.1"
}

get_pids() {
    pgrep -f "mix_web_companion.py" 2>/dev/null | tr '\n' ' '
}

service_active() {
    if is_macos; then
        if [ -f "$LAUNCHD_PLIST" ] && command -v launchctl >/dev/null 2>&1; then
            launchctl print "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 && return 0
        fi
        [ -n "$(get_pids)" ]
        return
    fi
    if have_user_systemd && systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        return 0
    fi
    [ -n "$(get_pids)" ]
}

# ------------------------------------------------------------------------------
# Service definition
# ------------------------------------------------------------------------------
write_systemd_unit() {
    [ -n "$PYTHON_BIN" ] || { echo "✗ No usable Python 3.8+ interpreter found."; return 1; }
    mkdir -p "$(dirname "$UNIT_PATH")"

    # The archive lives on removable/external disks. Requiring their mount units
    # here is what makes the service come up with a populated library at boot
    # instead of starting before /mnt/1TB_BKP_005 exists and streaming nothing.
    local mount_units="" path candidate mount_unit
    local probe_dir
    probe_dir="$(sed -n 's/^MIX_ARCHIVE_DIR="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$APP_DIR/config.env" 2>/dev/null | head -1)"
    for path in "$probe_dir" \
                $(sed -n 's/^EXTRA_MIX_ARCHIVE_DIRS="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$APP_DIR/config.env" 2>/dev/null | tr ';,' '  '); do
        [ -n "$path" ] || continue
        # Walk up to the real mountpoint: the unit row names /mnt/1TB_BKP_005,
        # not the MIX_ARCHIVE folder inside it.
        candidate="$path"
        while [ -n "$candidate" ] && [ "$candidate" != "/" ]; do
            mount_unit="$(systemctl list-units --type=mount --all --no-legend --plain 2>/dev/null \
                | awk -v p="$candidate" '$0 ~ p {print $1; exit}')"
            if [ -z "$mount_unit" ]; then
                mount_unit="$(systemctl --user list-units --type=mount --all --no-legend --plain 2>/dev/null \
                    | awk -v p="$candidate" '$0 ~ p {print $1; exit}')"
            fi
            [ -n "$mount_unit" ] && break
            candidate="$(dirname "$candidate")"
        done
        if [ -n "$mount_unit" ]; then
            case " $mount_units " in
                *" $mount_unit "*) ;;
                *) mount_units="$mount_units $mount_unit" ;;
            esac
        fi
    done

    cat >"$UNIT_PATH" <<EOF
[Unit]
Description=MP Mix Manager Mobile Web Companion (DJ Booth Remote)
Documentation=file://$APP_DIR/README.md
After=network-online.target$mount_units
Wants=network-online.target$mount_units
# Soft ordering only: if an archive drive is unplugged the dashboard still
# answers and the Music library keeps working, instead of the unit refusing
# to start until the disk is attached.

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart="$PYTHON_BIN" "$PY_SCRIPT" --host "$HOST" --port "$PORT"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    echo "✓ Wrote systemd user unit: $UNIT_PATH"
}

write_launchd_plist() {
    [ -n "$PYTHON_BIN" ] || { echo "✗ No usable Python 3.8+ interpreter found."; return 1; }
    mkdir -p "$(dirname "$LAUNCHD_PLIST")" "$LOG_DIR"

    # macOS TCC (Privacy & Security) judges a background job by the bundle that
    # owns it. A bare python3 launchd job has no bundle, so it is denied read
    # access to /Volumes until someone grants Full Disk Access by hand. Running
    # it from a minimal .app gives the job a stable bundle identity that can be
    # approved once in System Settings -> Privacy & Security -> Full Disk Access.
    local bundle="$APP_DIR/MP Web Companion.app"
    local macos_dir="$bundle/Contents/MacOS"
    mkdir -p "$macos_dir"
    cat >"$bundle/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key>
	<string>MP Web Companion</string>
	<key>CFBundleDisplayName</key>
	<string>MP Web Companion</string>
	<key>CFBundleIdentifier</key>
	<string>com.mplanetarian.mp-web-companion</string>
	<key>CFBundleExecutable</key>
	<string>mp-web-companion</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>$(cat "$APP_DIR/VERSION" 2>/dev/null | awk '{print $1}' || echo 0.4.3)</string>
	<key>LSUIElement</key>
	<true/>
</dict>
</plist>
EOF
    cat >"$macos_dir/mp-web-companion" <<EOF
#!/bin/bash
# Bundle entry point: launchd starts this, TCC attributes access to the bundle.
exec "$PYTHON_BIN" "$PY_SCRIPT" --host "$HOST" --port "$PORT"
EOF
    chmod +x "$macos_dir/mp-web-companion"

    cat >"$LAUNCHD_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LAUNCHD_LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>$macos_dir/mp-web-companion</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$APP_DIR</string>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<dict>
		<key>SuccessfulExit</key>
		<false/>
	</dict>
	<key>ProcessType</key>
	<string>Interactive</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
		<key>PYTHONUNBUFFERED</key>
		<string>1</string>
	</dict>
	<key>StandardOutPath</key>
	<string>$LOG_FILE</string>
	<key>StandardErrorPath</key>
	<string>$LOG_FILE</string>
</dict>
</plist>
EOF
    chmod 644 "$LAUNCHD_PLIST"
    echo "✓ Wrote launchd agent: $LAUNCHD_PLIST"
    echo "  (app bundle: $bundle)"
}

write_service() {
    if is_macos; then
        write_launchd_plist
    else
        write_systemd_unit
    fi
}

# ------------------------------------------------------------------------------
# Start / stop
# ------------------------------------------------------------------------------
start_service() {
    echo "Starting Mobile Web Companion..."
    if is_macos; then
        if [ -f "$LAUNCHD_PLIST" ]; then
            launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
            if launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST" >/dev/null 2>&1; then
                launchctl kickstart "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
                echo "✓ Mobile Web Companion started via launchd ($LAUNCHD_LABEL)."
            else
                echo "⚠ launchd start failed; attempting direct background launch..."
            fi
        fi
        if ! service_active && [ -n "$PYTHON_BIN" ]; then
            mkdir -p "$LOG_DIR"
            nohup "$PYTHON_BIN" "$PY_SCRIPT" --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
            sleep 1
        fi
    else
        if have_user_systemd && [ -f "$UNIT_PATH" ]; then
            systemctl --user daemon-reload
            systemctl --user start "$SERVICE_NAME"
            sleep 1
            if systemctl --user is-active --quiet "$SERVICE_NAME"; then
                echo "✓ Mobile Web Companion started via systemd service ($SERVICE_NAME)."
            elif [ -n "$PYTHON_BIN" ]; then
                echo "⚠ systemd start failed; attempting direct background launch..."
                mkdir -p "$LOG_DIR"
                nohup "$PYTHON_BIN" "$PY_SCRIPT" --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
                sleep 1
            fi
        elif [ -n "$PYTHON_BIN" ]; then
            mkdir -p "$LOG_DIR"
            nohup "$PYTHON_BIN" "$PY_SCRIPT" --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
            sleep 1
        fi
    fi
    show_status
}

stop_service() {
    echo "Stopping Mobile Web Companion..."
    if is_macos; then
        if [ -f "$LAUNCHD_PLIST" ]; then
            launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
        fi
    elif have_user_systemd && [ -f "$UNIT_PATH" ]; then
        systemctl --user stop "$SERVICE_NAME" >/dev/null 2>&1 || true
    fi
    local pids
    pids="$(get_pids)"
    if [ -n "$pids" ]; then
        # shellcheck disable=SC2086
        kill $pids 2>/dev/null || true
        # Wait for the port to be released; a fixed sleep let "restart" race the
        # old process and bind-fail, which looked like a service that would not
        # start.
        local waited=0
        while [ -n "$(get_pids)" ] && [ "$waited" -lt 50 ]; do
            sleep 0.1
            waited=$((waited + 1))
        done
        pids="$(get_pids)"
        if [ -n "$pids" ]; then
            # shellcheck disable=SC2086
            kill -9 $pids 2>/dev/null || true
            sleep 0.3
        fi
    fi
    echo "✓ Mobile Web Companion stopped."
}

show_status() {
    local lan_ip pids
    lan_ip="$(get_lan_ip)"
    pids="$(get_pids)"
    if service_active; then
        echo "● Mobile Web Companion is RUNNING"
        [ -n "$pids" ] && echo "  • PID(s):         $pids"
        echo "  • Local Address:  http://localhost:${PORT}"
        echo "  • Mobile LAN URL: http://${lan_ip}:${PORT}"
        if is_macos; then
            echo "  • Autostart:      $(launchd_enabled)"
        else
            echo "  • Autostart:      $(systemd_enabled)"
        fi
    else
        echo "○ Mobile Web Companion is STOPPED"
        echo "  • Target Mobile LAN URL: http://${lan_ip}:${PORT}"
        if is_macos; then
            echo "  • Autostart:      $(launchd_enabled)"
        else
            echo "  • Autostart:      $(systemd_enabled)"
        fi
    fi
    macos_privacy_warning
}

# ------------------------------------------------------------------------------
# Autostart
# ------------------------------------------------------------------------------
systemd_enabled() {
    if [ -f "$UNIT_PATH" ] && have_user_systemd; then
        systemctl --user is-enabled "$SERVICE_NAME" 2>/dev/null || echo "disabled"
    elif [ -f "$UNIT_PATH" ]; then
        echo "unit present (no user bus)"
    else
        echo "not installed"
    fi
}

launchd_enabled() {
    if [ -f "$LAUNCHD_PLIST" ]; then
        echo "enabled (RunAtLoad)"
    else
        echo "not installed"
    fi
}

# macOS TCC denies a background job access to external volumes until the job's
# bundle is approved in System Settings > Privacy & Security > Full Disk Access.
# Surface that instead of reporting a healthy server that streams nothing.
macos_privacy_warning() {
    is_macos || return 0
    [ -n "${PYTHON_BIN:-}" ] || return 0
    local probe_dir
    probe_dir="$(sed -n 's/^MIX_ARCHIVE_DIR="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$APP_DIR/config.env" 2>/dev/null | head -1)"
    [ -n "$probe_dir" ] && [ -d "$probe_dir" ] || return 0
    "$PYTHON_BIN" - "$probe_dir" <<'PY' || true
import os, sys
path = sys.argv[1]
try:
    os.listdir(path)
except PermissionError:
    print("  ⚠ macOS privacy block: this background service cannot read")
    print("    " + path)
    print("    Approve 'MP Web Companion.app' in System Settings > Privacy &")
    print("    Security > Full Disk Access, then run: restart")
    print("    (this wrapper can open that pane: mix_web_companion.sh grant)")
sys.exit(0)
PY
}

enable_autostart() {
    if is_macos; then
        [ -f "$LAUNCHD_PLIST" ] || write_launchd_plist || return 1
        launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
        if launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST" >/dev/null 2>&1; then
            echo "✓ Autostart enabled for $LAUNCHD_LABEL (runs at login)."
        else
            echo "⚠ launchd bootstrap failed; the plist will still load at next login."
        fi
        return 0
    fi

    [ -f "$UNIT_PATH" ] || write_systemd_unit || return 1
    if have_user_systemd; then
        systemctl --user daemon-reload
        systemctl --user enable "$SERVICE_NAME"
        # A user unit only starts at boot when lingering is enabled for the user.
        if ! loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q "Linger=yes"; then
            loginctl enable-linger "$USER" >/dev/null 2>&1 \
                && echo "✓ Enabled lingering so the service starts at boot before login." \
                || echo "⚠ Run 'sudo loginctl enable-linger $USER' so it starts at boot before login."
        fi
        echo "✓ Autostart enabled for $SERVICE_NAME."
    else
        echo "⚠ No systemd user bus in this session. The unit is written and will"
        echo "  activate at next login: systemctl --user enable --now $SERVICE_NAME"
    fi
}

disable_autostart() {
    if is_macos; then
        launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" >/dev/null 2>&1 || true
        rm -f "$LAUNCHD_PLIST"
        echo "✓ Autostart disabled and agent removed."
        return 0
    fi
    if have_user_systemd; then
        systemctl --user disable "$SERVICE_NAME" >/dev/null 2>&1 || true
    fi
    echo "✓ Autostart disabled for $SERVICE_NAME."
}

install_service() {
    write_service || return 1
    enable_autostart
    start_service
}

uninstall_service() {
    stop_service
    disable_autostart
    rm -f "$UNIT_PATH" "$LAUNCHD_PLIST"
    if is_macos; then
        rm -rf "$APP_DIR/MP Web Companion.app"
    fi
    if have_user_systemd; then
        systemctl --user daemon-reload >/dev/null 2>&1 || true
    fi
    echo "✓ Service files removed."
}

case "${1:-}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 1
        start_service
        ;;
    status)
        show_status
        ;;
    grant|privacy)
        # macOS only: take the user straight to the pane where the companion
        # bundle is approved, then restart so the grant takes effect.
        if ! is_macos; then
            echo "This command is only needed on macOS."
            exit 0
        fi
        if [ -d "$APP_DIR/MP Web Companion.app" ]; then
            open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles" 2>/dev/null \
                || open "/System/Applications/System Settings.app" 2>/dev/null || true
            echo "Add this app to Full Disk Access, then run: $0 restart"
            echo "  $APP_DIR/MP Web Companion.app"
        else
            echo "Run '$0 install' first to create the app bundle."
        fi
        ;;
    install|enable)
        if [ "${1:-}" = "install" ]; then
            install_service
        else
            enable_autostart
            service_active || start_service
        fi
        ;;
    disable)
        disable_autostart
        ;;
    uninstall)
        uninstall_service
        ;;
    logs)
        [ -f "$LOG_FILE" ] && tail -n "${2:-40}" "$LOG_FILE" || echo "No log at $LOG_FILE"
        ;;
    open|browse)
        LAN_IP="$(get_lan_ip)"
        target="http://${LAN_IP}:${PORT}"
        echo "Opening $target in default browser..."
        if command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$target" >/dev/null 2>&1 &
        elif command -v open >/dev/null 2>&1; then
            open "$target" >/dev/null 2>&1 &
        fi
        ;;
    *)
        exec "${PYTHON_BIN:-python3}" "$PY_SCRIPT" "$@"
        ;;
esac
