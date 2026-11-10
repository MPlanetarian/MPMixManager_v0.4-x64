#!/usr/bin/env bash
# MP_Mix_Manager_v0.4 - Local Launcher (Optimized & Non-Blocking)

shopt -s checkwinsize 2>/dev/null
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1

# Fast Windows Home & Python Path Normalization (Non-blocking)
if command -v cygpath &>/dev/null; then
    if [[ -n "$USERPROFILE" ]] && { [[ -z "$HOME" ]] || [[ ! -d "$HOME" ]] || [[ "$HOME" == "/home/$USER" ]]; }; then
        _h=$(cygpath -u "$USERPROFILE" 2>/dev/null) && [[ -d "$_h" ]] && export HOME="$_h"
    fi

    for _p in "$LOCALAPPDATA/Programs/Python/Python312" "$USERPROFILE/AppData/Local/Programs/Python/Python312" "/c/Program Files/Python312"; do
        if [[ -d "$_p" ]]; then
            _pu=$(cygpath -u "$_p" 2>/dev/null || echo "$_p")
            [[ -x "$_pu/python.exe" ]] && { export PATH="$_pu:$_pu/Scripts:$PATH"; break; }
        fi
    done
fi

# Resolve script path cleanly
_RAW="${BASH_SOURCE[0]:-$0}"
if [[ -z "$_RAW" || "$_RAW" == "bash" || "$_RAW" == "-bash" ]]; then
    _RAW="$PWD/manager.sh"
fi

while [[ -h "$_RAW" ]]; do
    _RESOLVED_DIR="$(cd -P "$(dirname "$_RAW")" >/dev/null 2>&1 && pwd)"
    _RAW="$(readlink "$_RAW")"
    [[ $_RAW != /* ]] && _RAW="$_RESOLVED_DIR/$_RAW"
done

if command -v cygpath &>/dev/null; then
    _RAW=$(cygpath -u "$_RAW" 2>/dev/null || echo "$_RAW")
fi

_RAW="${_RAW//\\//}"
DIR=$(cd -P -- "$(dirname -- "$_RAW")" 2>/dev/null && pwd)

# Fallback directory check if needed
if [[ "$DIR" == "/c/WINDOWS/system32" || -z "$DIR" ]]; then
    DIR="$PWD"
fi

cd "$DIR" || exit 1

# Start the Linux manager with the equalizer at Flat. The GUI launcher also
# does this when opened directly; repeating the reset is safe.
if [[ "$(uname -s 2>/dev/null)" == Linux && -f "$DIR/MP_Audio_Player.py" ]]; then
    _mp_python="${MP_PYTHON:-}"
    if [[ -z "$_mp_python" ]]; then
        command -v python3 >/dev/null 2>&1 && _mp_python="$(command -v python3)"
    fi
    [[ -n "$_mp_python" ]] && "$_mp_python" "$DIR/MP_Audio_Player.py" --reset-eq >/dev/null 2>&1 || true
fi

if [[ ! -f "Mix_Archive_Manager.sh" ]]; then
    echo "Error: Mix_Archive_Manager.sh not found in: $DIR"
    read -rp "Press Enter to exit..."
    exit 1
fi

# A plain run opens MP Gui. Named commands (update, --help, --version, and
# the other Mix_Archive_Manager.sh actions) stay on the CLI script.
_launch_gui=1
if [[ $# -gt 0 ]]; then
    case "$1" in
        --keep-theme|--no-visualizer|--theme|-t|--theme=*)
            _launch_gui=1
            ;;
        *)
            _launch_gui=0
            ;;
    esac
fi

if [[ "$_launch_gui" -eq 1 ]]; then
    if [[ ! -f "MP_Gui.sh" ]]; then
        echo "Error: MP_Gui.sh not found in: $DIR"
        read -rp "Press Enter to exit..."
        exit 1
    fi
    exec bash "MP_Gui.sh" "$@"
fi

exec bash "Mix_Archive_Manager.sh" "$@"
