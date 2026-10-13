#!/usr/bin/env bash
# MP_Mix_Manager_v0.3 - Local Launcher (Optimized)

shopt -s checkwinsize 2>/dev/null
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1

# Windows Home & Python Path Normalization
if command -v cygpath &>/dev/null; then
    if [[ -n "$USERPROFILE" ]] && { [[ -z "$HOME" ]] || [[ ! -d "$HOME" ]] || [[ "$HOME" == "/home/$USER" ]]; }; then
        _h=$(cygpath -u "$USERPROFILE" 2>/dev/null) && [[ -d "$_h" ]] && export HOME="$_h"
    fi

    for _p in "$LOCALAPPDATA/Programs/Python/Python312" "$USERPROFILE/AppData/Local/Programs/Python/Python312" "/c/Users/${USER:-Mathe}/AppData/Local/Programs/Python/Python312" "/c/Program Files/Python312" "/c/Program Files/Python311"; do
        _pu=$(cygpath -u "$_p" 2>/dev/null || echo "$_p")
        [[ -x "$_pu/python.exe" ]] && { export PATH="$_pu:$_pu/Scripts:$PATH"; break; }
    done
fi

clear

# Resolve script path cleanly with double brackets
_RAW="${BASH_SOURCE[0]:-$0}"
if [[ -z "$_RAW" || "$_RAW" == "bash" || "$_RAW" == "-bash" ]]; then
    _RAW="$PWD/manager.sh"
fi

if command -v cygpath &>/dev/null; then
    _RAW=$(cygpath -u "$_RAW" 2>/dev/null || echo "$_RAW")
fi

_RAW="${_RAW//\\//}"
DIR=$(cd -P -- "$(dirname -- "$_RAW")" 2>/dev/null && pwd)

# Safety fallback if resolved to system32 or empty
if [[ "$DIR" == "/c/WINDOWS/system32" || -z "$DIR" ]]; then
    for _fb in "$PWD" "/x/MP_Mix_Manager_v0.3" "/c/Users/${USER:-Mathe}/Downloads/MP_Mix_Manager_v0.3"; do
        if [[ -f "$_fb/Mix_Archive_Manager.sh" ]]; then
            DIR="$_fb"
            break
        fi
    done
fi

cd "$DIR" || exit 1

if [[ ! -f "Mix_Archive_Manager.sh" ]]; then
    echo "Error: Mix_Archive_Manager.sh not found in: $DIR"
    read -rp "Press Enter to exit..."
    exit 1
fi

exec bash "Mix_Archive_Manager.sh" "$@"