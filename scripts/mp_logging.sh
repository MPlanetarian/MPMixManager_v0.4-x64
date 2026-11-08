#!/usr/bin/env bash
# mp_logging.sh - Shell Error and Event Logger for MP Mix Archive Manager
# Part of MP_Mix_Manager_v0.3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$HOME/.config/mix-manager"
mkdir -p "$CONFIG_DIR" 2>/dev/null || true

MP_ERROR_LOG="${SCRIPT_DIR}/MP_Error.log"
BACKUP_ERROR_LOG="${CONFIG_DIR}/MP_Error.log"

get_mp_error_log() {
    if touch "$MP_ERROR_LOG" 2>/dev/null; then
        echo "$MP_ERROR_LOG"
    else
        touch "$BACKUP_ERROR_LOG" 2>/dev/null || true
        echo "$BACKUP_ERROR_LOG"
    fi
}

log_mp_error() {
    local comp="${1:-MixManager}"
    local msg="${2:-Unspecified error occurred}"
    local details="${3:-}"
    local log_file
    log_file="$(get_mp_error_log)"
    local stamp
    stamp="$(date '+%Y-%m-%d %H:%M:%S')"

    {
        echo "[$stamp] [ERROR] [$comp] $msg"
        [ -n "$details" ] && echo "  Details: $details"
        echo "----------------------------------------------------------------------"
    } >> "$log_file" 2>/dev/null || true
}

log_mp_warning() {
    local comp="${1:-MixManager}"
    local msg="${2:-Warning}"
    local log_file
    log_file="$(get_mp_error_log)"
    local stamp
    stamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$stamp] [WARNING] [$comp] $msg" >> "$log_file" 2>/dev/null || true
}

view_mp_errors() {
    local log_file
    log_file="$(get_mp_error_log)"
    if [ ! -s "$log_file" ]; then
        echo -e "\033[32m✔ No errors logged in MP_Error.log.\033[0m"
        return 0
    fi
    echo -e "\033[1;35m======================================================================\033[0m"
    echo -e "\033[1;35m                    MP MIX MANAGER ERROR LOG                          \033[0m"
    echo -e "\033[1;35m======================================================================\033[0m"
    echo -e "\033[2mFile: $log_file\033[0m\n"
    tail -n 40 "$log_file"
}

# If run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        --tail|tail)
            view_mp_errors
            ;;
        --log)
            shift
            log_mp_error "$@"
            ;;
        *)
            echo "MP_Error.log is located at: $(get_mp_error_log)"
            ;;
    esac
fi
