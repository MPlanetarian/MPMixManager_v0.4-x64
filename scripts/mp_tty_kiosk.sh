#!/usr/bin/env bash
# Install or remove the MP Mix Manager console service.
# The unit binds the manager to /dev/tty1 and restarts it. tty2 stays a login.
# --print-unit writes the unit to stdout and does not need root.

set -euo pipefail
IFS=$'\n\t'

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
template="$script_dir/systemd/mp-mix-manager-tty.service.in"
unit_path="/etc/systemd/system/mp-mix-manager-tty.service"

action=""
user_name="${MP_TTY_USER:-}"
uid=""
group_name=""
home_dir=""
manager=""

usage() {
    printf '%s\n' "Usage: $0 --print-unit|--install|--remove [--user NAME] [--uid N] [--group NAME] [--home DIR] [--manager PATH]" >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --print-unit) action="print" ;;
        --install) action="install" ;;
        --remove) action="remove" ;;
        --user)
            user_name="${2:?}"
            shift
            ;;
        --uid)
            uid="${2:?}"
            shift
            ;;
        --group)
            group_name="${2:?}"
            shift
            ;;
        --home)
            home_dir="${2:?}"
            shift
            ;;
        --manager)
            manager="${2:?}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 2
            ;;
    esac
    shift
done

if [[ -z "$action" ]]; then
    usage
    exit 2
fi

fill_identity() {
    if [[ -z "$user_name" ]]; then
        user_name="${SUDO_USER:-${USER:-}}"
    fi
    if [[ -z "$user_name" || "$user_name" == "root" ]]; then
        printf '%s\n' "A non-root account is required for the TTY service." >&2
        return 1
    fi
    if [[ -z "$uid" || -z "$home_dir" || -z "$group_name" ]]; then
        local entry=""
        entry="$(getent passwd "$user_name" || true)"
        if [[ -z "$entry" ]]; then
            printf '%s\n' "No passwd entry for ${user_name}." >&2
            return 1
        fi
        local pw_uid="" pw_home=""
        IFS=: read -r _ _ pw_uid _ _ pw_home _ <<<"$entry"
        [[ -z "$uid" ]] && uid="$pw_uid"
        [[ -z "$home_dir" ]] && home_dir="$pw_home"
        if [[ -z "$group_name" ]]; then
            group_name="$(id -gn "$user_name")"
        fi
    fi
    if [[ -z "$manager" ]]; then
        manager="$root_dir/Mix_Archive_Manager.sh"
    fi
    if [[ ! -f "$manager" ]]; then
        printf '%s\n' "Manager script was not found: $manager" >&2
        return 1
    fi
    if [[ "$manager" == *" "* || "$home_dir" == *" "* || "$user_name" == *" "* ]]; then
        printf '%s\n' "The TTY service path cannot contain spaces." >&2
        return 1
    fi
}

render_unit() {
    fill_identity
    if [[ ! -f "$template" ]]; then
        printf '%s\n' "Unit template was not found: $template" >&2
        return 1
    fi
    local text=""
    text="$(<"$template")"
    text="${text//@USER@/$user_name}"
    text="${text//@GROUP@/$group_name}"
    text="${text//@UID@/$uid}"
    text="${text//@HOME@/$home_dir}"
    text="${text//@MANAGER@/$manager}"
    text="${text//@WORKDIR@/$root_dir}"
    printf '%s\n' "$text"
}

case "$action" in
    print)
        render_unit
        ;;
    install)
        if [[ "$(id -u)" -ne 0 ]]; then
            printf '%s\n' "Install the TTY service as root." >&2
            exit 1
        fi
        render_unit >"$unit_path"
        systemctl daemon-reload
        systemctl enable mp-mix-manager-tty.service
        loginctl enable-linger "$user_name" || true
        printf '%s\n' "Enabled mp-mix-manager-tty.service for ${user_name} on /dev/tty1."
        ;;
    remove)
        if [[ "$(id -u)" -ne 0 ]]; then
            printf '%s\n' "Remove the TTY service as root." >&2
            exit 1
        fi
        systemctl disable --now mp-mix-manager-tty.service 2>/dev/null || true
        systemctl unmask getty@tty1.service 2>/dev/null || true
        systemctl reset-failed mp-mix-manager-tty.service 2>/dev/null || true
        systemctl daemon-reload || true
        printf '%s\n' "Stopped mp-mix-manager-tty.service and restored getty@tty1."
        ;;
esac
