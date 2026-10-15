#!/usr/bin/env bash
# ==============================================================================
# MP_Mix_Manager_v0.3 - MP Video Image Directory Output Monitor (FLUX / LTX / WAN2GP)
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for _cfg in "$SCRIPT_DIR/config.env" "$SCRIPT_DIR/../config.env" "$PWD/config.env" "$HOME/MP_Mix_Manager_v0.3/config.env"; do
    if [ -f "$_cfg" ]; then
        source "$_cfg" 2>/dev/null || true
        break
    fi
done

PY_SCRIPT="$SCRIPT_DIR/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"
[ ! -f "$PY_SCRIPT" ] && PY_SCRIPT="$SCRIPT_DIR/scripts/MP_Video_Image_Dir_WAN2GP_Output_Monitor.py"

exec python3 "$PY_SCRIPT" "$@"
