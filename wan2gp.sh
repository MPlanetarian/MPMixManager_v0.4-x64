#!/bin/bash

# Configuration Loading
for _cfg in $(echo "/etc/wan2gp.env $HOME/.wan2gp.env"); do
    if [ -f "$_cfg" ]; then
        source "$_cfg" 2>/dev/null || true
        break
    fi
done

ACTION="${1:-2}"

stop_wan2gp() {
    pids=$(pgrep -f "python.*wgp\.py" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "\033[0;33mStopping WAN2GP (PID: $pids)...\033[0m"
        kill -TERM $pids 2>/dev/null || true
        sleep 2
        remaining=$(pgrep -f "python.*wgp\.py" 2>/dev/null || true)
        if [ -n "$remaining" ]; then
            kill -9 $remaining 2>/dev/null || true
            taskkill.exe /F /PID $remaining 2>/dev/null || true
        fi
        echo -e "\033[0;32m✓ WAN2GP stopped.\033[0m"
    else
        echo -e "\033[0;33mWAN2GP is not currently running.\033[0m"
    fi
}

status_wan2gp() {
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
if [[ "$PROFILE" != "2" && "$PROFILE" != "4.5" && "$PROFILE" != "1" && "$PROFILE" != "3" && "$PROFILE" != "4" ]]; then
    PROFILE="2"
fi

# Disable systemd-oomd if active on Linux
if systemctl is-active --quiet systemd-oomd 2>/dev/null; then
    sudo systemctl stop systemd-oomd 2>/dev/null || true
    sudo systemctl mask systemd-oomd 2>/dev/null || true
fi

# Resolve WAN2GP App Root
APP_DIR="${WAN2GP_DIR:-}"
for d in "X:/WAN2GP/Wan2GP" "D:/WAN2GP/Wan2GP" "/var/home/mplanetarian/pinokio/api/wan.git/app" "$HOME/pinokio/api/wan.git/app"; do
    if [ -d "$d" ]; then
        APP_DIR="$d"
        break
    fi
done

if [ -z "$APP_DIR" ]; then
    echo -e "\033[0;31m[-] Error: WAN2GP application directory not found!\033[0m"
    echo -e "\033[0;33mPlease set WAN2GP_DIR in config.env to the path containing wgp.py.\033[0m"
    exit 1
fi

cd "$APP_DIR" || exit 1

# Resolve Python environment
PYTHON_BIN="${WAN2GP_PYTHON:-}"
for p in "X:/WAN2GP/conda_envs/wan2gp/python.exe" "$APP_DIR/venv/Scripts/python.exe" "$APP_DIR/venv/bin/python"; do
    if [ -x "$p" ]; then
        PYTHON_BIN="$p"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    fi
fi

# Activate virtualenv if available
if [ -f "$APP_DIR/venv/bin/activate" ]; then
    source "$APP_DIR/venv/bin/activate" 2>/dev/null || true
elif [ -f "$APP_DIR/venv/Scripts/activate" ]; then
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
    for d in "/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS" "$HOME/Documents/WAN2GP_OUTPUTS"; do
        if [ -d "$d" ]; then
            WAN_OUTPUT_DIR="$d"
            break
        fi
    done
fi
mkdir -p "$WAN_OUTPUT_DIR" 2>/dev/null || true

echo -e "  Outputs Directory: \033[1;36m$WAN_OUTPUT_DIR\033[0m"
echo -e "  App Directory:     \033[1;36m$APP_DIR\033[0m"
echo -e "  Python:            \033[1;36m$PYTHON_BIN\033[0m\n"

export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export CUDA_VISIBLE_DEVICES="0"

"$PYTHON_BIN" wgp.py --multiple-images --advanced --listen --profile "$PROFILE" --attention sage --output-dir "$WAN_OUTPUT_DIR"