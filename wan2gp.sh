#!/usr/bin/env bash
# ==============================================================================
# wan2gp.sh - WAN2GP Launcher and Management Script
# Usage:
#   ./wan2gp.sh [2|4.5]        Launch WAN2GP in Profile 2 (fast) or 4.5 (low VRAM)
#   ./wan2gp.sh stop           Stop running WAN2GP instance
#   ./wan2gp.sh status         Check running status
#   ./wan2gp.sh restart [prof] Restart in chosen profile
# ==============================================================================

# Cross-platform pgrep & pkill polyfills
if ! command -v pgrep >/dev/null 2>&1; then
    pgrep() {
        local flag_f=false
        local flag_x=false
        local flag_i=false
        local pattern=""
        while [ $# -gt 0 ]; do
            case "$1" in
                -f) flag_f=true; shift ;;
                -x) flag_x=true; shift ;;
                -i) flag_i=true; shift ;;
                -a|-fa|-l) shift ;;
                -*) shift ;;
                *) pattern="$1"; shift ;;
            esac
        done
        [ -z "$pattern" ] && return 1

        local matches=""
        if [ "$flag_i" = true ]; then
            matches=$(ps -ef 2>/dev/null | grep -iE -- "$pattern" | grep -v "grep" || true)
        else
            matches=$(ps -ef 2>/dev/null | grep -E -- "$pattern" | grep -v "grep" || true)
        fi

        if [ -n "$matches" ]; then
            echo "$matches" | awk '{print $2}'
            return 0
        fi

        if command -v tasklist.exe >/dev/null 2>&1; then
            local win_matches
            win_matches=$(MSYS_NO_PATHCONV=1 tasklist.exe /FO CSV /NH 2>/dev/null | grep -iE -- "$pattern" || true)
            if [ -n "$win_matches" ]; then
                echo "$win_matches" | cut -d',' -f2 | tr -d '"'
                return 0
            fi
        fi
        return 1
    }
    export -f pgrep 2>/dev/null || true
fi

if ! command -v pkill >/dev/null 2>&1; then
    pkill() {
        local sig="TERM"
        local pattern=""
        while [ $# -gt 0 ]; do
            case "$1" in
                -9|-KILL) sig="KILL"; shift ;;
                -15|-TERM) sig="TERM"; shift ;;
                -f|-i|-x) shift ;;
                -*) shift ;;
                *) pattern="$1"; shift ;;
            esac
        done
        [ -z "$pattern" ] && return 1
        local pids
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            for pid in $pids; do
                kill -$sig "$pid" 2>/dev/null || true
            done
            return 0
        fi
        return 1
    }
    export -f pkill 2>/dev/null || true
fi

# Load config if present
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for _cfg in "$_SCRIPT_DIR/config.env" "$_SCRIPT_DIR/../config.env" "$PWD/config.env" "/x/MP_Mix_Manager_v0.3/config.env" "X:/MP_Mix_Manager_v0.3/config.env" "$HOME/MP_Mix_Manager_v0.3/config.env"; do
    if [ -f "$_cfg" ]; then
        # shellcheck disable=SC1090
        source "$_cfg" 2>/dev/null || true
        break
    fi
done

ACTION="${1:-2}"

stop_wan2gp() {
    local pids
    pids=$(pgrep -f "python.*wgp\.py" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "\033[0;33mStopping WAN2GP (PID: $pids)...\033[0m"
        for p in $pids; do
            kill -TERM "$p" 2>/dev/null || true
        done
        sleep 2
        local remaining
        remaining=$(pgrep -f "python.*wgp\.py" 2>/dev/null || true)
        if [ -n "$remaining" ]; then
            for p in $remaining; do
                kill -9 "$p" 2>/dev/null || true
                if command -v taskkill.exe >/dev/null 2>&1; then
                    taskkill.exe /F /PID "$p" 2>/dev/null || true
                fi
            done
        fi
        echo -e "\033[0;32m✓ WAN2GP stopped.\033[0m"
    else
        echo -e "\033[0;33mWAN2GP is not currently running.\033[0m"
    fi
}

status_wan2gp() {
    local pids
    pids=$(pgrep -f "python.*wgp\.py" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "\033[0;32m[RUNNING] WAN2GP is active with PID: $pids\033[0m"
        ps -o pid,user,%cpu,%mem,etime,args -p $pids 2>/dev/null || ps -ef 2>/dev/null | grep -E "$pids" || true
    else
        echo -e "\033[0;31m[STOPPED] WAN2GP is not running.\033[0m"
    fi
}

if [ "$ACTION" = "stop" ]; then
    stop_wan2gp
    exit 0
elif [ "$ACTION" = "status" ]; then
    status_wan2gp
    exit 0
elif [ "$ACTION" = "restart" ]; then
    stop_wan2gp
    shift
    ACTION="${1:-2}"
    echo "Restarting with profile $ACTION..."
    sleep 1
fi

PROFILE="$ACTION"
if [ "$PROFILE" != "2" ] && [ "$PROFILE" != "4.5" ] && [ "$PROFILE" != "1" ] && [ "$PROFILE" != "3" ] && [ "$PROFILE" != "4" ]; then
    PROFILE="2"
fi

# Disable systemd-oomd if active on Linux to prevent premature OOM kills
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet systemd-oomd 2>/dev/null; then
    sudo systemctl stop systemd-oomd 2>/dev/null || true
    sudo systemctl mask systemd-oomd 2>/dev/null || true
fi

# Resolve WAN2GP App Root
APP_DIR="${WAN2GP_DIR:-}"
[ -z "$APP_DIR" ] && [ -d "X:/WAN2GP/Wan2GP" ] && APP_DIR="X:/WAN2GP/Wan2GP"
[ -z "$APP_DIR" ] && [ -d "D:/WAN2GP/Wan2GP" ] && APP_DIR="D:/WAN2GP/Wan2GP"
[ -z "$APP_DIR" ] && [ -d "/var/home/mplanetarian/pinokio/api/wan.git/app" ] && APP_DIR="/var/home/mplanetarian/pinokio/api/wan.git/app"
[ -z "$APP_DIR" ] && [ -d "$HOME/pinokio/api/wan.git/app" ] && APP_DIR="$HOME/pinokio/api/wan.git/app"

if [ -z "$APP_DIR" ] || [ ! -d "$APP_DIR" ]; then
    echo -e "\033[0;31m[-] Error: WAN2GP application directory not found!\033[0m"
    echo -e "\033[0;33mPlease set WAN2GP_DIR in config.env to the path containing wgp.py.\033[0m"
    exit 1
fi

cd "$APP_DIR" || exit 1

# Resolve Python environment
PYTHON_BIN="${WAN2GP_PYTHON:-}"
[ -z "$PYTHON_BIN" ] && [ -x "X:/WAN2GP/conda_envs/wan2gp/python.exe" ] && PYTHON_BIN="X:/WAN2GP/conda_envs/wan2gp/python.exe"
[ -z "$PYTHON_BIN" ] && [ -x "$APP_DIR/venv/Scripts/python.exe" ] && PYTHON_BIN="$APP_DIR/venv/Scripts/python.exe"
[ -z "$PYTHON_BIN" ] && [ -x "$APP_DIR/venv/bin/python" ] && PYTHON_BIN="$APP_DIR/venv/bin/python"
if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    fi
fi

# Activate virtualenv if available
if [ -f "$APP_DIR/venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$APP_DIR/venv/bin/activate" 2>/dev/null || true
elif [ -f "$APP_DIR/venv/Scripts/activate" ]; then
    # shellcheck source=/dev/null
    source "$APP_DIR/venv/Scripts/activate" 2>/dev/null || true
fi

# Locate site-packages and export NVIDIA library paths if on Linux
if [ "$(uname -s)" = "Linux" ]; then
    SITE_PKGS=$("$PYTHON_BIN" -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
    if [ -n "$SITE_PKGS" ]; then
        export LD_LIBRARY_PATH="$SITE_PKGS/nvidia/cudnn/lib:$SITE_PKGS/nvidia/cublas/lib:$SITE_PKGS/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH:-}"
    fi
fi

echo -e "\033[1;36m==================================================\033[0m"
echo -e "\033[1;36m       STARTING WAN2GP (Profile: $PROFILE)        \033[0m"
echo -e "\033[1;36m==================================================\033[0m"
if [ "$PROFILE" = "2" ]; then
    echo -e "\033[0;32mMode: Profile 2 (HighRAM_LowVRAM) - High Speed VRAM-resident for 2B models\033[0m"
elif [ "$PROFILE" = "4.5" ]; then
    echo -e "\033[0;33mMode: Profile 4.5 (LowRAM_LowVRAM) - Aggressive PCIe offload for 14B models\033[0m"
fi
echo ""

# Resolve output directory
WAN_OUTPUT_DIR="${WAN2GP_OUTPUTS:-D:/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS}"
if [ ! -d "$WAN_OUTPUT_DIR" ]; then
    if [ -d "/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS" ]; then
        WAN_OUTPUT_DIR="/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS"
    elif [ -d "$HOME/Documents/WAN2GP_OUTPUTS" ]; then
        WAN_OUTPUT_DIR="$HOME/Documents/WAN2GP_OUTPUTS"
    fi
fi
mkdir -p "$WAN_OUTPUT_DIR" 2>/dev/null || true

echo -e "  Outputs Directory: \033[1;36m$WAN_OUTPUT_DIR\033[0m"
echo -e "  App Directory:     \033[1;36m$APP_DIR\033[0m"
echo -e "  Python:            \033[1;36m$PYTHON_BIN\033[0m\n"

# Run WAN2GP with selected profile (listening on 0.0.0.0 for LAN + localhost access)
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export CUDA_VISIBLE_DEVICES="0"

"$PYTHON_BIN" wgp.py --multiple-images --advanced --listen --profile "$PROFILE" --attention sage --output-dir "$WAN_OUTPUT_DIR"
