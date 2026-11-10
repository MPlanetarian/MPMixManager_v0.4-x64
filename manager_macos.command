#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - macOS Double-Clickable Launcher
# Double-click this script in Finder to run MP Mix Archive Manager in Terminal.app
# ==============================================================================
_RESOLVED_SRC="${BASH_SOURCE[0]}"
while [ -h "$_RESOLVED_SRC" ]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
    _RESOLVED_SRC="$(readlink "$_RESOLVED_SRC")"
    [[ $_RESOLVED_SRC != /* ]] && _RESOLVED_SRC="$_RESOLVED_DIR/$_RESOLVED_SRC"
done
SCRIPT_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
unset _RESOLVED_SRC _RESOLVED_DIR
cd "$SCRIPT_DIR" || exit 1

# Ensure Virtual Environment, Homebrew, and local tools are available in PATH
if [ -d "$SCRIPT_DIR/venv" ] && [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi
export PATH="${SCRIPT_DIR}/venv/bin:/opt/homebrew/bin:/usr/local/bin:$SCRIPT_DIR/bin:$SCRIPT_DIR:$HOME/.local/bin:$PATH"
export OS_TYPE="macos"

# Keep this command's Terminal window visible on the main display while
# Manager startup finishes and any companion windows are opened.
if [ -f "$SCRIPT_DIR/scripts/place_manager_terminal_on_primary.py" ]; then
    _manager_tty="$(tty 2>/dev/null || true)"
    if [ -n "$_manager_tty" ]; then
        mkdir -p "$HOME/.config/mix-manager" 2>/dev/null || true
        nohup python3 "$SCRIPT_DIR/scripts/place_manager_terminal_on_primary.py" "$_manager_tty" \
            >>"$HOME/.config/mix-manager/manager_display.log" 2>&1 </dev/null &
        disown 2>/dev/null || true
    fi
    unset _manager_tty
fi

if [ -x "/opt/homebrew/bin/bash" ]; then
    exec /opt/homebrew/bin/bash "$SCRIPT_DIR/Mix_Archive_Manager.sh" "$@"
elif [ -x "/usr/local/bin/bash" ]; then
    exec /usr/local/bin/bash "$SCRIPT_DIR/Mix_Archive_Manager.sh" "$@"
elif command -v bash >/dev/null 2>&1; then
    exec bash "$SCRIPT_DIR/Mix_Archive_Manager.sh" "$@"
fi
