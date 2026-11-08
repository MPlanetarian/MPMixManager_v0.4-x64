#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - MP Video Image Directory Output Monitor (FLUX / LTX / WAN2GP)
# ==============================================================================
_SOURCE="${BASH_SOURCE[0]}"
while [ -h "$_SOURCE" ]; do
    _DIR="$(cd -P "$(dirname "$_SOURCE")" >/dev/null 2>&1 && pwd)"
    _SOURCE="$(readlink "$_SOURCE")"
    [[ $_SOURCE != /* ]] && _SOURCE="$_DIR/$_SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$_SOURCE")" >/dev/null 2>&1 && pwd)"

for _cfg in "$SCRIPT_DIR/config.env" "$SCRIPT_DIR/../config.env" "$PWD/config.env" "$HOME/MP_Mix_Manager_v0.3/config.env" "/var/home/mplanetarian/MP_Mix_Manager_v0.3/config.env"; do
    if [ -f "$_cfg" ]; then
        source "$_cfg" 2>/dev/null || true
        break
    fi
done

PY_SCRIPT="$SCRIPT_DIR/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"
[ ! -f "$PY_SCRIPT" ] && PY_SCRIPT="$SCRIPT_DIR/scripts/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"
[ ! -f "$PY_SCRIPT" ] && PY_SCRIPT="$HOME/MP_Mix_Manager_v0.3/scripts/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"
[ ! -f "$PY_SCRIPT" ] && PY_SCRIPT="/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"

exec python3 "$PY_SCRIPT" "$@"
