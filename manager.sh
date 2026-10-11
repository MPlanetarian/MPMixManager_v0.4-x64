#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - Local Launcher
# ==============================================================================

# Enable terminal window size tracking and resize signal handling
shopt -s checkwinsize 2>/dev/null || true
export PYTHONIOENCODING="utf-8"
export PYTHONUTF8=1

# Normalize HOME on Windows / Git Bash if needed
if command -v cygpath >/dev/null 2>&1; then
    if [ -n "$USERPROFILE" ] && { [ -z "$HOME" ] || [ ! -d "$HOME" ] || [ "$HOME" = "/home/$USER" ]; }; then
        _WIN_HOME="$(cygpath -u "$USERPROFILE" 2>/dev/null || true)"
        [ -n "$_WIN_HOME" ] && [ -d "$_WIN_HOME" ] && export HOME="$_WIN_HOME"
        unset _WIN_HOME
    fi
fi

# Prepend native Python 3.12 to PATH on Windows / Git Bash if available
for _py_cand in \
    "$LOCALAPPDATA/Programs/Python/Python312" \
    "$USERPROFILE/AppData/Local/Programs/Python/Python312" \
    "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312" \
    "/c/Program Files/Python312" \
    "/c/Program Files/Python311"; do
    _py_u="$_py_cand"
    command -v cygpath >/dev/null 2>&1 && _py_u="$(cygpath -u "$_py_cand" 2>/dev/null || echo "$_py_cand")"
    if [ -d "$_py_u" ] && [ -x "$_py_u/python.exe" ]; then
        export PATH="$_py_u:$_py_u/Scripts:$PATH"
        break
    fi
done
unset _py_cand _py_u

# ANSI Color Codes
CYAN='\033[38;5;51m'
PURPLE='\033[38;5;135m'
GREEN='\033[38;5;48m'
RESET='\033[0m'

# Clear terminal screen
clear

# Display CONGEN-style Header Banner (3-row compact isometric font)
# printf "${CYAN}%s${RESET}\n" "─────────────────────────────────────────────────────────────────────────────────"
# printf "${PURPLE}"
# cat << "EOF"
#  ▌
#  ▌  █▄▀█ █▀█   █▄▀█ █ ▀▄▀   █▀█ █▀▄ █▀▀ █ █ █ █ █▀▀   █▄▀█ █▀█ █▀▄ █▀█ █▀▀ █▀▄
#  ▌  █ ▀█ █▀▀   █ ▀█ █ █ █   █▀█ █▀▄ █▄▄ █▀█ █ █ ██▄   █ ▀█ █▀█ █ █ █▀█ █ █ █▀▄
#  ▌  ▀  ▀ ▀     ▀  ▀ ▀ ▀ ▀   ▀ ▀ ▀ ▀ ▀▀▀ ▀ ▀ ▀ ▀ ▀▀▀   ▀  ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀▀▀ ▀ ▀
#  ▌
# EOF
# printf "${CYAN}%s${RESET}\n" "─────────────────────────────────────────────────────────────────────────────────"
# printf "${GREEN} MP Mix Archive Manager  v0.3${RESET}\n\n"

# Resolve script source path across CLI, shortcut, or Explorer "Open With" launches
_RAW_PATH="${1:-${BASH_SOURCE[0]}}"

# If launched via Windows shell associations where arguments are dropped
if [ -z "$_RAW_PATH" ] || [ "$_RAW_PATH" = "bash" ] || [ "$_RAW_PATH" = "-bash" ]; then
    _CMD_LINE=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"ProcessId = \$PID\").CommandLine" 2>/dev/null | tr -d '\r')
    _MATCH=$(echo "$_CMD_LINE" | grep -oE '[A-Za-z]:\\[^"]+\.sh')
    [ -n "$_MATCH" ] && _RAW_PATH="$_MATCH"
fi

# Fallback: check fallback locations if still missing
if [ -z "$_RAW_PATH" ] || [ ! -e "$_RAW_PATH" ]; then
    _RAW_PATH="$0"
fi

# Convert to POSIX format and extract directory
command -v cygpath >/dev/null 2>&1 && _RAW_PATH="$(cygpath -u "$_RAW_PATH" 2>/dev/null || echo "$_RAW_PATH")"
_RAW_PATH="${_RAW_PATH//\\//}"
SCRIPT_DIR="$(cd -P "$(dirname "$_RAW_PATH")" >/dev/null 2>&1 && pwd)"

# Safety fallback if resolution ended up in system directories
if [ "$SCRIPT_DIR" = "/c/WINDOWS/system32" ] || [ -z "$SCRIPT_DIR" ]; then
    for _fallback in "$PWD" "/x/MP_Mix_Manager_v0.3" "/c/Users/${USER:-Mathe}/Downloads/MP_Mix_Manager_v0.3"; do
        if [ -f "$_fallback/Mix_Archive_Manager.sh" ]; then
            SCRIPT_DIR="$_fallback"
            break
        fi
    done
fi

cd "$SCRIPT_DIR"

# Verify target script exists before executing
if [ ! -f "$SCRIPT_DIR/Mix_Archive_Manager.sh" ]; then
    echo "Error: Mix_Archive_Manager.sh not found in: $SCRIPT_DIR"
    read -rp "Press Enter to exit..."
    exit 1
fi

# Execute core script
bash "$SCRIPT_DIR/Mix_Archive_Manager.sh" "$@"