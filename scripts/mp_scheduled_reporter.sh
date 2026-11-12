#!/usr/bin/env bash
# mp_scheduled_reporter.sh - Automated Schedule & Catch-Up Engine for MP Mix Reports
# Part of MP_Mix_Manager_v0.3
#
# Handles:
# 1. Automated once-per-day daily report generation at user-defined time (DAILY_REPORTS_TIME).
# 2. Catch-up execution: if manager was closed during scheduled time, updates as soon as opened.
# 3. Monthly and Yearly reports with automated scheduling and catch-up.
# 4. Respects config setting DAILY_REPORTS_ENABLED=true/false.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$HOME/.config/mix-manager"
mkdir -p "$CONFIG_DIR" 2>/dev/null || true

# Source config
CONFIG_FILE="${SCRIPT_DIR}/config.env"
[ ! -f "$CONFIG_FILE" ] && CONFIG_FILE="${CONFIG_DIR}/config.env"
if [ -f "$CONFIG_FILE" ]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
fi

# Default settings
DAILY_REPORTS_ENABLED="${DAILY_REPORTS_ENABLED:-true}"
DAILY_REPORTS_TIME="${DAILY_REPORTS_TIME:-10:00}"
MONTHLY_REPORTS_ENABLED="${MONTHLY_REPORTS_ENABLED:-true}"
YEARLY_REPORTS_ENABLED="${YEARLY_REPORTS_ENABLED:-true}"
LAST_DAILY_REPORT_DATE="${LAST_DAILY_REPORT_DATE:-}"
LAST_DAILY_EMAIL_DATE="${LAST_DAILY_EMAIL_DATE:-}"
LAST_MONTHLY_REPORT_DATE="${LAST_MONTHLY_REPORT_DATE:-}"
LAST_YEARLY_REPORT_DATE="${LAST_YEARLY_REPORT_DATE:-}"

# Resolve a Python interpreter that actually has the reporter dependencies
# (matplotlib / reportlab). `python3` on PATH is frequently Homebrew's build,
# which lacks them; using it made every report attempt fail silently, so the
# scheduler never recorded the run and retried every 60 seconds forever.
PYTHON_BIN=""
_resolve_python() {
    local cand
    for cand in "${MP_PYTHON:-}" /usr/bin/python3 python3; do
        [ -n "$cand" ] || continue
        if "$cand" -c 'import matplotlib, reportlab' >/dev/null 2>&1; then
            PYTHON_BIN="$cand"
            return 0
        fi
    done
    PYTHON_BIN="${MP_PYTHON:-python3}"
    return 0
}
_resolve_python
py() { "$PYTHON_BIN" "$@"; }

save_setting() {
    local key="$1"
    local val="$2"
    local cfg="${SCRIPT_DIR}/config.env"
    [ ! -f "$cfg" ] && cfg="${CONFIG_DIR}/config.env"
    local targets=("$cfg")
    [ -d "$CONFIG_DIR" ] && [ "$cfg" != "${CONFIG_DIR}/config.env" ] && targets+=("${CONFIG_DIR}/config.env")
    
    for f in "${targets[@]}"; do
        local found=0 out=""
        if [ -f "$f" ]; then
            while IFS= read -r line || [ -n "$line" ]; do
                if [[ "$line" =~ ^[[:space:]]*${key}= ]]; then
                    out+="${key}=\"${val}\""$'\n'
                    found=1
                else
                    out+="${line}"$'\n'
                fi
            done < "$f"
        fi
        (( !found )) && out+="${key}=\"${val}\""$'\n'
        printf '%s' "$out" > "$f" 2>/dev/null || true
    done
}

run_report() {
    local kind="$1"
    local py_script="${SCRIPT_DIR}/scripts/mp_report_generator.py"
    if [ ! -f "$py_script" ]; then
        echo "Error: mp_report_generator.py not found" >&2
        return 1
    fi
    py "$py_script" --kind "$kind"
}

check_and_run() {
    local today current_time current_month current_year
    today="$(date +%Y-%m-%d)"
    current_time="$(date +%H:%M)"
    current_month="$(date +%Y-%m)"
    current_year="$(date +%Y)"

    # 1. DAILY REPORT CHECK & CATCH-UP
    if [ "${DAILY_REPORTS_ENABLED:-true}" = "true" ]; then
        if [ "${LAST_DAILY_REPORT_DATE:-}" != "$today" ]; then
            # Compare current time with scheduled time (HH:MM)
            # If current_time >= DAILY_REPORTS_TIME, run now!
            # (Covers both normal scheduled run and catch-up when manager was closed during scheduled time)
            local cur_hm="${current_time//:/}"
            local sched_hm="${DAILY_REPORTS_TIME//:/}"
            # Strip leading zeros for arithmetic
            cur_hm=$((10#$cur_hm))
            sched_hm=$((10#$sched_hm))

            if [ "$cur_hm" -ge "$sched_hm" ]; then
                echo "Triggering scheduled/catch-up Daily Mix Report for $today..."
                if run_report "daily"; then
                    save_setting "LAST_DAILY_REPORT_DATE" "$today"
                    LAST_DAILY_REPORT_DATE="$today"
                    echo "Daily Mix Report completed and recorded."
                fi
            fi
        fi
    fi

    # 2. MONTHLY REPORT CHECK & CATCH-UP
    if [ "${MONTHLY_REPORTS_ENABLED:-true}" = "true" ]; then
        if [ "${LAST_MONTHLY_REPORT_DATE:-}" != "$current_month" ]; then
            echo "Triggering scheduled/catch-up Monthly Mix Report for $current_month..."
            if run_report "monthly"; then
                save_setting "LAST_MONTHLY_REPORT_DATE" "$current_month"
                LAST_MONTHLY_REPORT_DATE="$current_month"
                echo "Monthly Mix Report completed and recorded."
            fi
        fi
    fi

    # 3. YEARLY REPORT CHECK & CATCH-UP
    if [ "${YEARLY_REPORTS_ENABLED:-true}" = "true" ]; then
        if [ "${LAST_YEARLY_REPORT_DATE:-}" != "$current_year" ]; then
            echo "Triggering scheduled/catch-up Yearly Mix Report for $current_year..."
            if run_report "yearly"; then
                save_setting "LAST_YEARLY_REPORT_DATE" "$current_year"
                LAST_YEARLY_REPORT_DATE="$current_year"
                echo "Yearly Mix Report completed and recorded."
            fi
        fi
    fi

    # 4. DAILY CONSOLIDATED EMAIL DISPATCH (1:00 PM / 13:00)
    local email_script="${SCRIPT_DIR}/scripts/mp_daily_email_reporter.py"
    if [ -f "$email_script" ]; then
        if [ "${LAST_DAILY_EMAIL_DATE:-}" != "$today" ]; then
            local cur_hm="${current_time//:/}"
            cur_hm=$((10#$cur_hm))
            if [ "$cur_hm" -ge 1300 ]; then
                if py "$email_script" --send >/dev/null 2>&1; then
                    save_setting "LAST_DAILY_EMAIL_DATE" "$today"
                    LAST_DAILY_EMAIL_DATE="$today"
                fi
            fi
        fi
    fi

    # 5. DAILY AI BRAIN LOGS & MODELS REPORT CATCH-UP (10:05 AM or whenever launched)
    #
    # This used to run unconditionally on every 60s tick with no "already done
    # today" guard in the shell, so it re-executed the generator forever. The
    # generator does have its own once-per-day check, but it happens after an
    # expensive matplotlib/reportlab import, so each tick still burned ~0.8s of
    # CPU and ~200MB. Guard on a dated marker instead.
    local ai_script="${SCRIPT_DIR}/scripts/generate_ai_report_section.py"
    local ai_marker="${CONFIG_DIR}/.last_ai_brain_report"
    if [ -f "$ai_script" ]; then
        local cur_hm="${current_time//:/}"
        cur_hm=$((10#$cur_hm))
        if [ "$cur_hm" -ge 1005 ] && [ "$(cat "$ai_marker" 2>/dev/null || true)" != "$today" ]; then
            if py "$ai_script" --daily >/dev/null 2>&1; then
                printf '%s\n' "$today" > "$ai_marker"
            fi
        fi
    fi
}

start_daemon() {
    # Lightweight loop checking every 60 seconds.
    #
    # Singleton enforcement uses an flock on a shared lock file rather than a
    # pid file, because the pid file alone is racy: every manager launch spawns
    # `--check-or-run` and `--daemon` in parallel, so many daemons can pass the
    # "is the old pid alive?" test before any of them writes its pid. The lock
    # is held for the lifetime of the daemon and is released automatically when
    # it dies, so a crashed daemon never blocks a restart.
    local pid_file="${CONFIG_DIR}/mp_scheduled_reporter.pid"
    local lock_file="${CONFIG_DIR}/mp_scheduled_reporter.lock"

    # Reject dead/duplicate losers before forking at all.
    if [ -f "$pid_file" ]; then
        local old_pid
        old_pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            return 0
        fi
    fi

    # fd 9 holds the exclusive lock for the whole daemon lifetime.
    exec 9>>"$lock_file" || return 0
    if ! flock -n 9; then
        # Another daemon already owns the lock; this process is a duplicate.
        exec 9>&-
        return 0
    fi

    (
        # BASHPID is the pid of this subshell; $$ would be the parent's pid,
        # which made the pid file point at a long-dead process.
        echo "$BASHPID" > "$pid_file"
        # Exit on TERM/INT/HUP as well as EXIT, so `kill` actually stops the
        # daemon instead of just deleting its pid file and looping forever.
        trap 'rm -f "$pid_file"; [ -n "${SLEEP_PID:-}" ] && kill "$SLEEP_PID" 2>/dev/null; exit 0' INT TERM HUP
        trap 'rm -f "$pid_file"' EXIT
        while true; do
            # Reload config in case user toggled settings or updated scheduled time
            if [ -f "$CONFIG_FILE" ]; then
                # shellcheck source=/dev/null
                source "$CONFIG_FILE"
            fi
            check_and_run >/dev/null 2>&1 || true
            # Sleep in the background and `wait` for it: bash defers traps while
            # blocked in a foreground command, so a plain `sleep 60` made the
            # daemon ignore SIGTERM for up to a minute.
            sleep 60 &
            SLEEP_PID=$!
            wait "$SLEEP_PID" 2>/dev/null || true
            SLEEP_PID=""
        done
    ) &
    disown
}

print_status() {
    local today current_time
    today="$(date +%Y-%m-%d)"
    current_time="$(date +%H:%M)"
    echo "======================================================================"
    echo "      MP MIX ARCHIVE MANAGER — AUTOMATED REPORTING STATUS             "
    echo "======================================================================"
    echo "  Current System Time:        $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Daily Reports Enabled:      ${DAILY_REPORTS_ENABLED:-true}"
    echo "  Daily Scheduled Update Time: ${DAILY_REPORTS_TIME:-10:00}"
    echo "  Last Daily Report Run:      ${LAST_DAILY_REPORT_DATE:-Never}"
    echo "  Monthly Reports Enabled:    ${MONTHLY_REPORTS_ENABLED:-true}"
    echo "  Last Monthly Report Run:    ${LAST_MONTHLY_REPORT_DATE:-Never}"
    echo "  Yearly Reports Enabled:     ${YEARLY_REPORTS_ENABLED:-true}"
    echo "  Last Yearly Report Run:     ${LAST_YEARLY_REPORT_DATE:-Never}"
    echo "----------------------------------------------------------------------"
    if [ "${DAILY_REPORTS_ENABLED:-true}" = "true" ]; then
        if [ "${LAST_DAILY_REPORT_DATE:-}" = "$today" ]; then
            echo "  Daily Report Status:        ✔ Complete for today ($today)"
        else
            echo "  Daily Report Status:        ⚡ Scheduled for ${DAILY_REPORTS_TIME:-10:00} (or catch-up on next run)"
        fi
    else
        echo "  Daily Report Status:        ○ Disabled in configuration"
    fi
    local email_script="${SCRIPT_DIR}/scripts/mp_daily_email_reporter.py"
    if [ -f "$email_script" ]; then
        echo "----------------------------------------------------------------------"
        echo "  Daily Consolidated Email:   ⚡ Scheduled at 13:00 (1:00 PM) Daily"
        echo "  Email Rate Limit:           1 email per day (Strictly enforced)"
        echo "  Recipients:                 mplanetarian@mplanetarian.com, serotine@gmail.com, MathewKJohn2026@gmail.com"
    fi
    echo "======================================================================"
}

case "${1:-}" in
    --check-or-run|check)
        check_and_run
        ;;
    --daemon|daemon)
        start_daemon
        ;;
    --force-daily|daily)
        run_report "daily"
        save_setting "LAST_DAILY_REPORT_DATE" "$(date +%Y-%m-%d)"
        ;;
    --force-monthly|monthly)
        run_report "monthly"
        save_setting "LAST_MONTHLY_REPORT_DATE" "$(date +%Y-%m)"
        ;;
    --force-yearly|yearly)
        run_report "yearly"
        save_setting "LAST_YEARLY_REPORT_DATE" "$(date +%Y)"
        ;;
    --email-status|email-status)
        py "${SCRIPT_DIR}/scripts/mp_daily_email_reporter.py" --status
        ;;
    --email-send|email-send)
        py "${SCRIPT_DIR}/scripts/mp_daily_email_reporter.py" --send
        ;;
    --email-force|email-force)
        py "${SCRIPT_DIR}/scripts/mp_daily_email_reporter.py" --force
        ;;
    --status|status)
        print_status
        ;;
    *)
        check_and_run
        ;;
esac
