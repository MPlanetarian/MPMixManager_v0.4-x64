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
printf "${CYAN}%s${RESET}\n" "─────────────────────────────────────────────────────────────────────────────────"
printf "${PURPLE}"
cat << "EOF"
 ▌
 ▌  █▄▀█ █▀█   █▄▀█ █ ▀▄▀   █▀█ █▀▄ █▀▀ █ █ █ █ █▀▀   █▄▀█ █▀█ █▀▄ █▀█ █▀▀ █▀▄
 ▌  █ ▀█ █▀▀   █ ▀█ █ █ █   █▀█ █▀▄ █▄▄ █▀█ █ █ ██▄   █ ▀█ █▀█ █ █ █▀█ █ █ █▀▄
 ▌  ▀  ▀ ▀     ▀  ▀ ▀ ▀ ▀   ▀ ▀ ▀ ▀ ▀▀▀ ▀ ▀ ▀ ▀ ▀▀▀   ▀  ▀ ▀ ▀ ▀ ▀ ▀ ▀ ▀▀▀ ▀ ▀
 ▌
EOF
printf "${CYAN}%s${RESET}\n" "─────────────────────────────────────────────────────────────────────────────────"
printf "${GREEN} MP Mix Archive Manager  v0.3${RESET}\n\n"

# Resolve script path and locate backend
_RESOLVED_SRC="${BASH_SOURCE[0]}"
_RESOLVED_SRC="${_RESOLVED_SRC//\\//}"
command -v cygpath >/dev/null 2>&1 && _RESOLVED_SRC="$(cygpath -u "$_RESOLVED_SRC" 2>/dev/null || echo "$_RESOLVED_SRC")"
while [ -h "$_RESOLVED_SRC" ]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"
    _RESOLVED_SRC="$(readlink "$_RESOLVED_SRC")"
    _RESOLVED_SRC="${_RESOLVED_SRC//\\//}"
    command -v cygpath >/dev/null 2>&1 && _RESOLVED_SRC="$(cygpath -u "$_RESOLVED_SRC" 2>/dev/null || echo "$_RESOLVED_SRC")"
    [[ $_RESOLVED_SRC != /* ]] && _RESOLVED_SRC="$_RESOLVED_DIR/$_RESOLVED_SRC"
done
SCRIPT_DIR="$(cd -P "$(dirname "$_RESOLVED_SRC")" >/dev/null 2>&1 && pwd)"

if [ ! -f "$SCRIPT_DIR/Mix_Archive_Manager.sh" ]; then
    for _c in \
        "$PWD" \
        "$HOME/Downloads/MP_Mix_Manager_v0.3" \
        "/c/Users/${USER:-Mathe}/Downloads/MP_Mix_Manager_v0.3" \
        "$HOME/MP_Mix_Manager_v0.3" \
        "$HOME/MP_Mix_Manager_v0.1"; do
        if [ -f "$_c/Mix_Archive_Manager.sh" ]; then
            SCRIPT_DIR="$_c"
            break
        fi
    done
fi

unset _RESOLVED_SRC _RESOLVED_DIR _c

# Execute core management script
exec bash "$SCRIPT_DIR/Mix_Archive_Manager.sh" "$@"
