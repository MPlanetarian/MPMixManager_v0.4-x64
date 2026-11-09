#!/usr/bin/env bash
# Put MP Mix Manager on the signed-in Windows user's Desktop, Start Menu, and
# notification area. Python is not required. Git Bash and WSL both call this.
# Usage: install_windows_user.sh <install-root> [--ensure-tray|--status|--tray-foreground] [--stay]
set -euo pipefail

ROOT="${1:-}"
if [ -z "$ROOT" ]; then
    echo "install_windows_user.sh: the install root is required." >&2
    exit 2
fi
shift

ACTION="Install"
STAY=0
for _arg in "$@"; do
    case "$_arg" in
        --ensure-tray) ACTION="EnsureTray" ;;
        --status) ACTION="Status" ;;
        --tray-foreground) ACTION="Tray" ;;
        --stay) STAY=1 ;;
        *)
            echo "install_windows_user.sh: unknown option $_arg" >&2
            exit 2
            ;;
    esac
done

to_windows_path() {
    local p="$1"
    if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$p"
        return
    fi
    if command -v wslpath >/dev/null 2>&1; then
        wslpath -w "$p"
        return
    fi
    case "$p" in
        /mnt/[a-zA-Z]/*)
            local drive rest
            drive=$(printf '%s' "$p" | cut -c6 | tr '[:lower:]' '[:upper:]')
            rest=$(printf '%s' "$p" | cut -c8-)
            printf '%s:\\%s\n' "$drive" "${rest//\//\\}"
            ;;
        /[a-zA-Z]/*)
            local drive rest
            drive=$(printf '%s' "$p" | cut -c2 | tr '[:lower:]' '[:upper:]')
            rest=$(printf '%s' "$p" | cut -c4-)
            printf '%s:\\%s\n' "$drive" "${rest//\//\\}"
            ;;
        *)
            printf '%s\n' "$p"
            ;;
    esac
}

find_powershell() {
    if command -v powershell.exe >/dev/null 2>&1; then
        command -v powershell.exe
        return 0
    fi
    local root="${SYSTEMROOT:-${WINDIR:-}}"
    local cand
    if [ -n "$root" ]; then
        cand="$root/System32/WindowsPowerShell/v1.0/powershell.exe"
        if [ -f "$cand" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    fi
    for cand in \
        /c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
        /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
    do
        if [ -f "$cand" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}

PS_EXE="$(find_powershell)" || {
    echo "Windows PowerShell was not found." >&2
    exit 1
}
WIN_ROOT="$(to_windows_path "$ROOT")"
# Git Bash rewrites arguments that look like Unix paths. The paths below are
# already Windows paths, so that rewrite has to stay off.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

if [ "$ACTION" = "Tray" ]; then
    TRAY="$(to_windows_path "$ROOT/scripts/windows_tray.ps1")"
    if [ "$STAY" = 1 ]; then
        exec "$PS_EXE" -NoProfile -ExecutionPolicy Bypass -STA -File "$TRAY" -Root "$WIN_ROOT" -Stay
    fi
    exec "$PS_EXE" -NoProfile -ExecutionPolicy Bypass -STA -File "$TRAY" -Root "$WIN_ROOT"
fi

SCRIPT="$(to_windows_path "$ROOT/scripts/windows_user_integration.ps1")"
exec "$PS_EXE" -NoProfile -ExecutionPolicy Bypass -File "$SCRIPT" -Root "$WIN_ROOT" -Action "$ACTION"
