#!/usr/bin/env bash
# MP_Mix_Manager_v0.3 - Local Launcher (Optimized)

shopt -s checkwinsize 2>/dev/null
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1

# Windows Home & Python Path Normalization
if command -v cygpath &>/dev/null; then
    # Fix HOME if empty or default git-bash home
    if [ -n "$USERPROFILE" ] && { [ -z "$HOME" ] || [ ! -d "$HOME" ] || [ "$HOME" = "/home/$USER" ]; }; then
        _h=$(cygpath -u "$USERPROFILE" 2>/dev/null) && [ -d "$_h" ] && export HOME="$_h"
    fi

    # Prepend Python 3.12/3.11 to PATH if found
    for _p in "$LOCALAPPDATA/Programs/Python/Python312" "$USERPROFILE/AppData/Local/Programs/Python/Python312" "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312" "/c/Program Files/Python312" "/c/Program Files/Python311"; do
        _pu=$(cygpath -u "$_p" 2>/dev/null || echo "$_p")
        [ -x "$_pu/python.exe" ] && { export PATH="$_pu:$_pu/Scripts:$PATH"; break; }
    done
fi

clear

# Resolve Script Path (handles CLI, Shortcut, and Explorer "Open With")
_RAW="${1:-${BASH_SOURCE[0]}}"

# Fallback if path is missing or invalid (common in Windows shell associations)
if [ -z "$_RAW" ] || [ "$_RAW" = "bash" ] || [ "$_RAW" = "-bash" ] || [ ! -e "$_RAW" ]; then
    # Try to extract path from process command line
    _cmd=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"ProcessId = \$PID\").CommandLine" 2>/dev/null | tr -d '\r')
    _m=$(echo "$_cmd" | grep -oE '[A-Za-z]:\$$^"]+\.sh')
    [ -n "$_m" ] && _RAW="$_m"
    
    # Final fallback to $0 if still missing
    [ -z "$_RAW" ] && _RAW="$0"
fi

# Normalize path to POSIX and get directory
command -v cygpath &>/dev/null && _RAW=$(cygpath -u "$_RAW" 2>/dev/null || echo "$_RAW")
_RAW="${_RAW//\\//}"
DIR=$(cd -P "$(dirname "$_RAW")" &>/dev/null && pwd)

# Safety fallback if resolved to system dir or empty
if [ "$DIR" = "/c/WINDOWS/system32" ] || [ -z "$DIR" ]; then
    for _fb in "$PWD" "/x/MP_Mix_Manager_v0.3" "/c/Users/${USER:-Mathe}/Downloads/MP_Mix_Manager_v0.3"; do
        [ -f "$_fb/Mix_Archive_Manager.sh" ] && { DIR="$_fb"; break; }
    done
fi

cd "$DIR" || exit 1

# Verify and Execute
if [ ! -f "Mix_Archive_Manager.sh" ]; then
    echo "Error: Mix_Archive_Manager.sh not found in: $DIR"
    read -rp "Press Enter to exit..."
    exit 1
fi

exec bash "Mix_Archive_Manager.sh" "$@"