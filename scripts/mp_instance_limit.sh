#!/usr/bin/env bash
# ==============================================================================
# Shared instance cap for MP Gui and MP Liquid Player.
#
# Every launcher sources this file before it opens a window. The real counter
# lives in mp_instance_limit.py so the shell, the Python entry points, and the
# Liquid Glass hosts all see the same four slots. A claim is atomic, so two
# launches that arrive together cannot both take the last slot.
#
# Only MP Gui and MP Liquid Player are capped. The console manager, the
# tracklist viewer, and the MP Liquid Visualizer are not.
# ==============================================================================

MP_INSTANCE_MAX=4

_mp_instance_helper() {
    local dir
    dir="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    if [ -f "$dir/mp_instance_limit.py" ]; then
        printf '%s\n' "$dir/mp_instance_limit.py"
        return 0
    fi
    return 1
}

_mp_instance_python() {
    if [ -n "${MP_INSTANCE_PYTHON:-}" ] && [ -x "${MP_INSTANCE_PYTHON}" ]; then
        printf '%s\n' "$MP_INSTANCE_PYTHON"
        return 0
    fi
    if [ -n "${MP_PY:-}" ] && [ -x "${MP_PY}" ]; then
        printf '%s\n' "$MP_PY"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        printf '%s\n' python3
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        printf '%s\n' python
        return 0
    fi
    return 1
}

# 0 = a slot is free, 3 = all four are taken, 1 = the helper is unavailable.
mp_instance_check() {
    local role="$1" helper py
    helper="$(_mp_instance_helper)" || return 1
    py="$(_mp_instance_python)" || return 1
    "$py" "$helper" check "$role" >/dev/null 2>&1
    return $?
}

# Live windows plus pending launch claims. Prints 0 when counting is impossible.
mp_instance_count() {
    local role="$1" helper py value
    helper="$(_mp_instance_helper)" || { printf '0\n'; return 0; }
    py="$(_mp_instance_python)" || { printf '0\n'; return 0; }
    value="$("$py" "$helper" count "$role" 2>/dev/null)" || value=""
    case "$value" in
        ''|*[!0-9]*) printf '0\n' ;;
        *) printf '%s\n' "$value" ;;
    esac
    return 0
}

# Reserve a slot for a pid. Defaults to this shell, which keeps its pid across
# exec. 0 = reserved, 3 = at the limit.
mp_instance_claim() {
    local role="$1" pid="${2:-${BASHPID:-$$}}" helper py
    helper="$(_mp_instance_helper)" || return 1
    py="$(_mp_instance_python)" || return 1
    "$py" "$helper" claim "$role" --pid "$pid" >/dev/null 2>&1
    return $?
}

mp_instance_release() {
    local role="$1" pid="${2:-${BASHPID:-$$}}" helper py
    helper="$(_mp_instance_helper)" || return 0
    py="$(_mp_instance_python)" || return 0
    "$py" "$helper" release "$role" --pid "$pid" >/dev/null 2>&1 || true
    return 0
}

# Tell the user why nothing opened. Never let a missing notifier fail a launch.
mp_instance_notify_limit() {
    local role="$1" helper py
    helper="$(_mp_instance_helper)" || return 0
    py="$(_mp_instance_python)" || return 0
    "$py" "$helper" notify "$role" >/dev/null 2>&1 || true
    return 0
}

# Raise a window that is already open. Returns non-zero when none is on screen.
mp_instance_focus() {
    local role="$1" helper py
    helper="$(_mp_instance_helper)" || return 1
    py="$(_mp_instance_python)" || return 1
    "$py" "$helper" focus "$role" >/dev/null 2>&1
    return $?
}

# Limit message text for shell prompts.
mp_instance_limit_message() {
    case "$1" in
        gui) printf 'MP Gui is already open %s times. Close a window first (%s is the maximum).\n' "$MP_INSTANCE_MAX" "$MP_INSTANCE_MAX" ;;
        player) printf 'MP Liquid Player is already open %s times. Close a window first (%s is the maximum).\n' "$MP_INSTANCE_MAX" "$MP_INSTANCE_MAX" ;;
        *) printf 'MP Mix Manager is already open %s times.\n' "$MP_INSTANCE_MAX" ;;
    esac
}
