#!/usr/bin/env bash
# ==============================================================================
# scripts/manage_mp_reporter.sh
# Purpose: Comprehensive MP Reporter Suite Management for MP Mix Archive Manager
# Features:
#   - View Daily, Weekly, Monthly, Yearly & AI Reports (Text, PDF, Hawking Audio)
#   - 12-Month Scheduled Reports Calendar Viewer (+12 Months Forward Projection)
#   - Schedule & Enable/Disable Reports & Systemd Timers
#   - Edit Existing Report Tasks (Frequency, Schedule Day/Time, Voice, Script)
#   - Create New Daily, Weekly, Monthly & Yearly Reports Wizard
#   - Update Email Recipients, Delivery Times & SMTP Settings
#   - Run / Force Generate Any Report On-Demand
#   - Mathematical Telemetry, Multi-Archive Stats & Error Auditing
# ==============================================================================
set -uo pipefail

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
WHITE='\033[1;37m'
NC='\033[0m'

safe_clear() {
    /usr/bin/clear 2>/dev/null || true
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MP_REPORTER_DIR="/var/home/mplanetarian/MP_REPORTER"
TASKS_DIR="${MP_REPORTER_DIR}/tasks"
EMAIL_CONFIG="${MP_REPORTER_DIR}/email_config.env"
REPORTER_SH="${MP_REPORTER_DIR}/MP_Reporter.sh"
CALENDAR_PY="${SCRIPT_DIR}/scripts/mp_reports_calendar.py"
GEN_PY="${SCRIPT_DIR}/scripts/mp_report_generator.py"
EMAIL_SH="${SCRIPT_DIR}/scripts/mp_email_manager.sh"

press_enter() {
    echo ""
    read -r -p "Press [Enter] to continue..." || true
}

open_pdf() {
    local pdf="$1"
    if [ -f "$pdf" ]; then
        echo -e "${DIM}Opening PDF report in default viewer: ${pdf}...${NC}"
        xdg-open "$pdf" 2>/dev/null || kde-open "$pdf" 2>/dev/null || open "$pdf" 2>/dev/null || true
    else
        echo -e "${YELLOW}Notice: PDF file not found at ${pdf}${NC}"
    fi
}

play_audio() {
    local audio="$1"
    if [ -f "$audio" ] && [ -s "$audio" ]; then
        echo -e "\n${BOLD}${CYAN}Stephen Hawking Voice Narration found:${NC} ${DIM}${audio}${NC}"
        read -r -p "Would you like to play this audio now? [Y/n]: " ans || true
        case "${ans:-y}" in
            [yY]|[yY][eE][sS]|"")
                echo -e "${GREEN}Playing Stephen Hawking voice narration (Press Ctrl+C to cancel)...${NC}"
                if command -v pw-play &>/dev/null; then
                    pw-play "$audio" 2>/dev/null || true
                elif command -v paplay &>/dev/null; then
                    paplay "$audio" 2>/dev/null || true
                elif command -v ffplay &>/dev/null; then
                    ffplay -nodisp -autoexit "$audio" 2>/dev/null || true
                elif command -v aplay &>/dev/null; then
                    aplay -q "$audio" 2>/dev/null || true
                else
                    echo -e "${RED}No audio player (pw-play, paplay, ffplay, aplay) found.${NC}"
                fi
                ;;
            *)
                echo -e "${DIM}Audio playback skipped.${NC}"
                ;;
        esac
    fi
}

# ------------------------------------------------------------------------------
# 1. VIEW REPORTS (Daily, Weekly, Monthly, Yearly, AI)
# ------------------------------------------------------------------------------
view_reports_menu() {
    while true; do
        safe_clear
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}       VIEW REPORTS: DAILY, WEEKLY, MONTHLY, YEARLY & AI LOGS         ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
        echo -e "  ${BOLD}${CYAN}1)${NC} View Today's Daily Mix Report        ${DIM}(Latest Daily PDF, Text & Hawking Voice)${NC}"
        echo -e "  ${BOLD}${CYAN}2)${NC} View Current Weekly Mix Report       ${DIM}(Latest Weekly Performance & Stats)${NC}"
        echo -e "  ${BOLD}${CYAN}3)${NC} View Current Monthly Mix Report      ${DIM}(Latest Monthly Trends & Analysis)${NC}"
        echo -e "  ${BOLD}${CYAN}4)${NC} View Current Yearly Mix Report       ${DIM}(Latest Annual Projections & Growth)${NC}"
        echo -e "  ${BOLD}${CYAN}5)${NC} View Daily AI Brain Logs Report      ${DIM}(Gemini, Grok, Harmony, Ollama & WebUI)${NC}"
        echo -e "  ${BOLD}${CYAN}6)${NC} View Daily Bazzite System Report     ${DIM}(OS, Hardware, Memory & Storage Health)${NC}"
        echo -e "  ${BOLD}${CYAN}0)${NC} Return to Reports Menu\n"

        read -r -p "Enter choice [0-6]: " v_choice || true
        case "$v_choice" in
            1)
                safe_clear
                echo -e "${BOLD}${MAGENTA}=== TODAY'S DAILY MIX ARCHIVE REPORT ===${NC}\n"
                local txt="$SCRIPT_DIR/REPORTS/DAILY_REPORTS/latest_daily_report.txt"
                local pdf="$SCRIPT_DIR/REPORTS/DAILY_REPORTS/latest_daily_report.pdf"
                if [ ! -f "$txt" ]; then
                    echo -e "${YELLOW}Generating Today's Daily Report now...${NC}\n"
                    python3 "$GEN_PY" --kind daily --print-summary
                else
                    cat "$txt"
                fi
                open_pdf "$pdf"
                local audio
                audio=$(ls -t "$MP_REPORTER_DIR/TTS_AUDIO/"*DAILY_REPORT_TASK_002_MIX_MANAGER*.wav 2>/dev/null | head -n 1 || true)
                [ -z "$audio" ] && audio=$(ls -t "$MP_REPORTER_DIR/TTS_AUDIO/"*Daily_Audio_Transcript*.wav 2>/dev/null | head -n 1 || true)
                [ -n "$audio" ] && play_audio "$audio"
                press_enter
                ;;
            2)
                safe_clear
                echo -e "${BOLD}${MAGENTA}=== CURRENT WEEKLY MIX ARCHIVE REPORT ===${NC}\n"
                local txt="$SCRIPT_DIR/REPORTS/WEEKLY_REPORTS/latest_weekly_report.txt"
                local pdf="$SCRIPT_DIR/REPORTS/WEEKLY_REPORTS/latest_weekly_report.pdf"
                if [ ! -f "$txt" ]; then
                    echo -e "${YELLOW}Generating Current Weekly Report now...${NC}\n"
                    python3 "$GEN_PY" --kind weekly --print-summary
                else
                    cat "$txt"
                fi
                open_pdf "$pdf"
                local audio
                audio=$(ls -t "$MP_REPORTER_DIR/TTS_AUDIO/"*WEEKLY_REPORT_TASK_001_MIX_MANAGER*.wav 2>/dev/null | head -n 1 || true)
                [ -n "$audio" ] && play_audio "$audio"
                press_enter
                ;;
            3)
                safe_clear
                echo -e "${BOLD}${MAGENTA}=== CURRENT MONTHLY MIX ARCHIVE REPORT ===${NC}\n"
                local txt="$SCRIPT_DIR/REPORTS/MONTHLY_REPORTS/latest_monthly_report.txt"
                local pdf="$SCRIPT_DIR/REPORTS/MONTHLY_REPORTS/latest_monthly_report.pdf"
                if [ ! -f "$txt" ]; then
                    echo -e "${YELLOW}Generating Current Monthly Report now...${NC}\n"
                    python3 "$GEN_PY" --kind monthly --print-summary
                else
                    cat "$txt"
                fi
                open_pdf "$pdf"
                local audio
                audio=$(ls -t "$MP_REPORTER_DIR/TTS_AUDIO/"*MONTHLY_REPORT_TASK_001_MIX_MANAGER*.wav 2>/dev/null | head -n 1 || true)
                [ -n "$audio" ] && play_audio "$audio"
                press_enter
                ;;
            4)
                safe_clear
                echo -e "${BOLD}${MAGENTA}=== CURRENT YEARLY MIX ARCHIVE REPORT ===${NC}\n"
                local txt="$SCRIPT_DIR/REPORTS/YEARLY_REPORTS/latest_yearly_report.txt"
                local pdf="$SCRIPT_DIR/REPORTS/YEARLY_REPORTS/latest_yearly_report.pdf"
                if [ ! -f "$txt" ]; then
                    echo -e "${YELLOW}Generating Current Yearly Report now...${NC}\n"
                    python3 "$GEN_PY" --kind yearly --print-summary
                else
                    cat "$txt"
                fi
                open_pdf "$pdf"
                local audio
                audio=$(ls -t "$MP_REPORTER_DIR/TTS_AUDIO/"*YEARLY_REPORT_TASK_001_MIX_MANAGER*.wav 2>/dev/null | head -n 1 || true)
                [ -n "$audio" ] && play_audio "$audio"
                press_enter
                ;;
            5)
                safe_clear
                echo -e "${BOLD}${MAGENTA}=== DAILY AI BRAIN LOGS, MODELS & ACTIVITIES REPORT ===${NC}\n"
                local txt="$MP_REPORTER_DIR/PDF_REPORTS/DAILY_REPORTS/latest_ai_report.txt"
                local pdf
                pdf=$(ls -t "$MP_REPORTER_DIR/PDF_REPORTS/DAILY_REPORTS/"*DAILY_REPORT_TASK_003_AI*.pdf 2>/dev/null | head -n 1 || true)
                if [ -f "$txt" ]; then
                    cat "$txt"
                else
                    echo -e "${CYAN}Harvesting and summarizing latest AI Brain Logs...${NC}\n"
                    python3 "$SCRIPT_DIR/scripts/generate_ai_report_section.py" --summary
                fi
                [ -n "$pdf" ] && open_pdf "$pdf"
                local audio
                audio=$(ls -t "$MP_REPORTER_DIR/TTS_AUDIO/"*DAILY_REPORT_TASK_003_AI*.wav 2>/dev/null | head -n 1 || true)
                [ -z "$audio" ] && audio="$MP_REPORTER_DIR/TTS_AUDIO/latest_DAILY_REPORT_TASK_003_AI.wav"
                [ -f "$audio" ] && play_audio "$audio"
                press_enter
                ;;
            6)
                safe_clear
                echo -e "${BOLD}${MAGENTA}=== DAILY BAZZITE SYSTEM OPERATIONS REPORT ===${NC}\n"
                local pdf
                pdf=$(ls -t "$MP_REPORTER_DIR/PDF_REPORTS/DAILY_REPORTS/"*DAILY_REPORT_TASK_001*.pdf 2>/dev/null | head -n 1 || true)
                if [ -n "$pdf" ]; then
                    echo -e "${GREEN}Found latest system report: ${pdf}${NC}"
                    open_pdf "$pdf"
                else
                    echo -e "${YELLOW}No system report PDF found yet.${NC}"
                fi
                local audio
                audio=$(ls -t "$MP_REPORTER_DIR/TTS_AUDIO/"*DAILY_REPORT_TASK_001*.wav 2>/dev/null | head -n 1 || true)
                [ -n "$audio" ] && play_audio "$audio"
                press_enter
                ;;
            0|[qQ]|[eE][xX][iI][tT])
                return 0
                ;;
            *)
                echo -e "${RED}Invalid choice!${NC}"
                sleep 1
                ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# 2. 12-MONTH CALENDAR VIEWER (+12 MONTHS AHEAD)
# ------------------------------------------------------------------------------
view_calendar_menu() {
    while true; do
        safe_clear
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}      12-MONTH SCHEDULED REPORTS CALENDAR VIEWER (+12 MONTHS)         ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
        echo -e "  ${BOLD}${CYAN}1)${NC} Interactive Monthly Calendar Browser ${GREEN}[Recommended]${NC} ${DIM}(Prev/Next Month)${NC}"
        echo -e "  ${BOLD}${CYAN}2)${NC} Full 12-Month Calendar Grid View     ${DIM}(Overview of entire 12-month year ahead)${NC}"
        echo -e "  ${BOLD}${CYAN}3)${NC} Chronological 30-Day Schedule Timeline${DIM}(Day-by-day timetable & task details)${NC}"
        echo -e "  ${BOLD}${CYAN}4)${NC} Chronological 90-Day Schedule Timeline${DIM}(Quarterly projection)${NC}"
        echo -e "  ${BOLD}${CYAN}5)${NC} Configured Tasks Matrix & Summary     ${DIM}(All Daily, Weekly, Monthly & Yearly tasks)${NC}"
        echo -e "  ${BOLD}${CYAN}0)${NC} Return to Reports Menu\n"

        read -r -p "Enter choice [0-5] (default: 1): " c_choice || true
        case "${c_choice:-1}" in
            1)
                python3 "$CALENDAR_PY" --interactive
                ;;
            2)
                safe_clear
                python3 "$CALENDAR_PY" --year-grid | less -R
                ;;
            3)
                safe_clear
                python3 "$CALENDAR_PY" --timeline 30 | less -R
                ;;
            4)
                safe_clear
                python3 "$CALENDAR_PY" --timeline 90 | less -R
                ;;
            5)
                safe_clear
                python3 "$CALENDAR_PY" --tasks
                press_enter
                ;;
            0|[qQ]|[eE][xX][iI][tT])
                return 0
                ;;
            *)
                echo -e "${RED}Invalid choice!${NC}"
                sleep 1
                ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# 3. SCHEDULE & MANAGE REPORTS (SYSTEMD TIMERS & TASKS)
# ------------------------------------------------------------------------------
manage_schedules_menu() {
    while true; do
        safe_clear
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}         SCHEDULE & MANAGE REPORT SYSTEMD USER TIMERS                 ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

        echo -e "${BOLD}Current Configured Tasks & Systemd Timer States:${NC}\n"
        printf "  ${BOLD}%-3s %-32s %-9s %-18s %-12s${NC}\n" "NUM" "TASK ID" "KIND" "SCHEDULE" "TIMER STATUS"
        echo -e "  ─────────────────────────────────────────────────────────────────────────"

        local tasks=()
        shopt -s nullglob
        local confs=("${TASKS_DIR}"/*.conf)
        shopt -u nullglob

        local i=1
        for conf in "${confs[@]}"; do
            local tid="" kind="" enabled="" time="" dow="" dom="" doy=""
            tid=$(grep -E '^TASK_ID=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
            kind=$(grep -E '^KIND=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
            enabled=$(grep -E '^ENABLED=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
            time=$(grep -E '^TIME=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
            dow=$(grep -E '^DAY_OF_WEEK=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
            dom=$(grep -E '^DAY_OF_MONTH=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
            doy=$(grep -E '^DAY_OF_YEAR=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)

            [ -z "$tid" ] && tid="$(basename "$conf" .conf)"
            [ -z "$kind" ] && kind="daily"
            [ -z "$time" ] && time="10:00"

            local sched="Daily ${time}"
            case "$kind" in
                weekly)  sched="${dow:-Mon} ${time}" ;;
                monthly) sched="Day ${dom:-01} ${time}" ;;
                yearly)  sched="${doy:-01-01} ${time}" ;;
            esac

            local timer_status="${RED}Inactive${NC}"
            if systemctl --user is-active --quiet "mp-reporter-${tid}.timer" 2>/dev/null; then
                timer_status="${GREEN}Active (Running)${NC}"
            elif [ "$enabled" = "true" ]; then
                timer_status="${YELLOW}Enabled (Stopped)${NC}"
            else
                timer_status="${DIM}Disabled${NC}"
            fi

            tasks+=("$tid|$conf")
            printf "  ${CYAN}%2d)${NC} %-32s %-9s %-18s %b\n" "$i" "$tid" "${kind^^}" "$sched" "$timer_status"
            ((i++))
        done

        # Email timer status
        local email_timer_status="${RED}Inactive${NC}"
        if systemctl --user is-active --quiet mp-reporter-daily-email.timer 2>/dev/null; then
            email_timer_status="${GREEN}Active (13:00 Daily)${NC}"
        fi
        echo -e "  ─────────────────────────────────────────────────────────────────────────"
        printf "  ${CYAN} E)${NC} %-32s %-9s %-18s %b\n" "DAILY_EMAIL_BRIEF" "EMAIL" "Daily 13:00" "$email_timer_status"
        echo ""

        echo -e "  ${BOLD}${CYAN}e <num>)${NC} Enable task timer      ${BOLD}${CYAN}d <num>)${NC} Disable task timer"
        echo -e "  ${BOLD}${CYAN}A)${NC} Enable ALL task timers         ${BOLD}${CYAN}D)${NC} Disable ALL task timers"
        echo -e "  ${BOLD}${CYAN}T)${NC} Toggle Email 13:00 Timer       ${BOLD}${CYAN}L)${NC} View Active Systemd Timers List"
        echo -e "  ${BOLD}${CYAN}0)${NC} Return to Reports Menu\n"

        read -r -p "Enter action: " s_act || true
        case "$s_act" in
            [eE]\ [0-9]*)
                local idx="${s_act#* }"
                if (( idx >= 1 && idx <= ${#tasks[@]} )); then
                    local sel="${tasks[$((idx-1))]}"
                    local tid="${sel%%|*}"
                    echo -e "\n${GREEN}Enabling task timer for ${tid}...${NC}"
                    bash "$REPORTER_SH" enable "$tid"
                else
                    echo -e "${RED}Invalid task index.${NC}"
                fi
                press_enter
                ;;
            [dD]\ [0-9]*)
                local idx="${s_act#* }"
                if (( idx >= 1 && idx <= ${#tasks[@]} )); then
                    local sel="${tasks[$((idx-1))]}"
                    local tid="${sel%%|*}"
                    echo -e "\n${YELLOW}Disabling task timer for ${tid}...${NC}"
                    bash "$REPORTER_SH" disable "$tid"
                else
                    echo -e "${RED}Invalid task index.${NC}"
                fi
                press_enter
                ;;
            [aA])
                echo -e "\n${GREEN}Enabling ALL configured task timers...${NC}"
                for item in "${tasks[@]}"; do
                    local tid="${item%%|*}"
                    bash "$REPORTER_SH" enable "$tid" || true
                done
                press_enter
                ;;
            [dD])
                echo -e "\n${YELLOW}Disabling ALL configured task timers...${NC}"
                for item in "${tasks[@]}"; do
                    local tid="${item%%|*}"
                    bash "$REPORTER_SH" disable "$tid" || true
                done
                press_enter
                ;;
            [tT])
                if systemctl --user is-active --quiet mp-reporter-daily-email.timer 2>/dev/null; then
                    echo -e "\n${YELLOW}Disabling daily email briefing timer...${NC}"
                    bash "$EMAIL_SH" disable-timer
                else
                    echo -e "\n${GREEN}Enabling daily email briefing timer...${NC}"
                    bash "$EMAIL_SH" enable-timer
                fi
                press_enter
                ;;
            [lL])
                safe_clear
                echo -e "${BOLD}${CYAN}=== ACTIVE SYSTEMD USER TIMERS ===${NC}\n"
                systemctl --user list-timers --all 'mp-reporter*' --no-pager || true
                press_enter
                ;;
            0|[qQ]|[eE][xX][iI][tT])
                return 0
                ;;
            *)
                echo -e "${RED}Invalid selection!${NC}"
                sleep 1
                ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# 4. EDIT EXISTING REPORT TASKS
# ------------------------------------------------------------------------------
edit_task_menu() {
    while true; do
        safe_clear
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}              EDIT EXISTING REPORT TASK CONFIGURATION                 ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

        shopt -s nullglob
        local confs=("${TASKS_DIR}"/*.conf)
        shopt -u nullglob

        if [ ${#confs[@]} -eq 0 ]; then
            echo -e "${YELLOW}No report tasks found in ${TASKS_DIR}.${NC}"
            press_enter
            return 0
        fi

        echo -e "${BOLD}Select a task to edit:${NC}\n"
        local i=1
        for conf in "${confs[@]}"; do
            local tid desc kind
            tid=$(grep -E '^TASK_ID=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || basename "$conf" .conf)
            kind=$(grep -E '^KIND=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "daily")
            desc=$(grep -E '^DESCRIPTION=' "$conf" 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "$tid")
            printf "  ${CYAN}%2d)${NC} ${BOLD}%-32s${NC} [%-7s] %s\n" "$i" "$tid" "${kind^^}" "$desc"
            ((i++))
        done
        echo -e "  ${CYAN} 0)${NC} Return to Reports Menu\n"

        read -r -p "Select task number [0-$((i-1))]: " t_sel || true
        if [[ "$t_sel" =~ ^[0-9]+$ ]] && (( t_sel >= 1 && t_sel <= ${#confs[@]} )); then
            local target_conf="${confs[$((t_sel-1))]}"
            edit_task_file "$target_conf"
        elif [ "$t_sel" = "0" ] || [[ "$t_sel" =~ ^[qQ] ]]; then
            return 0
        else
            echo -e "${RED}Invalid task number.${NC}"
            sleep 1
        fi
    done
}

edit_task_file() {
    local conf="$1"
    while true; do
        safe_clear
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}             EDITING TASK: $(basename "$conf")                        ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

        # Load values
        local tid enabled kind time dow dom doy script desc voice
        tid=$(grep -E '^TASK_ID=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
        enabled=$(grep -E '^ENABLED=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "true")
        kind=$(grep -E '^KIND=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "daily")
        time=$(grep -E '^TIME=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "10:00")
        dow=$(grep -E '^DAY_OF_WEEK=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "Mon")
        dom=$(grep -E '^DAY_OF_MONTH=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "01")
        doy=$(grep -E '^DAY_OF_YEAR=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "01-01")
        script=$(grep -E '^REPORT_SCRIPT=' "$conf" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
        desc=$(grep -E '^DESCRIPTION=' "$conf" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
        voice=$(grep -E '^VOICE_LABEL=' "$conf" 2>/dev/null | cut -d= -f2- | tr -d '"' || echo "Stephen Hawking (Enters the Matrix)")

        echo -e "  Task ID:          ${BOLD}${CYAN}${tid}${NC}"
        echo -e "  Enabled Status:   $([ "$enabled" = "true" ] && echo -e "${GREEN}ENABLED${NC}" || echo -e "${RED}DISABLED${NC}")"
        echo -e "  Period (Kind):    ${BOLD}${YELLOW}${kind^^}${NC}"
        echo -e "  Schedule Time:    ${BOLD}${WHITE}${time}${NC} (24-hour HH:MM)"
        case "$kind" in
            weekly)  echo -e "  Day of Week:      ${BOLD}${WHITE}${dow}${NC} (Mon..Sun)" ;;
            monthly) echo -e "  Day of Month:     ${BOLD}${WHITE}${dom}${NC} (1..31)" ;;
            yearly)  echo -e "  Day of Year:      ${BOLD}${WHITE}${doy}${NC} (MM-DD)" ;;
        esac
        echo -e "  Description:      ${BOLD}${WHITE}${desc}${NC}"
        echo -e "  Voice Engine:     ${CYAN}${voice}${NC}"
        echo -e "  Script Path:      ${DIM}${script}${NC}\n"

        echo -e "  ${BOLD}Select field to edit:${NC}"
        echo -e "  ${CYAN}1)${NC} Toggle Enabled / Disabled"
        echo -e "  ${CYAN}2)${NC} Change Schedule Time (HH:MM)"
        echo -e "  ${CYAN}3)${NC} Change Schedule Frequency / Period (daily, weekly, monthly, yearly)"
        echo -e "  ${CYAN}4)${NC} Change Schedule Day (Day of Week / Month / Year)"
        echo -e "  ${CYAN}5)${NC} Change Description"
        echo -e "  ${CYAN}6)${NC} Change Report Script Path"
        echo -e "  ${CYAN}7)${NC} Save & Re-apply Systemd Timer"
        echo -e "  ${CYAN}0)${NC} Done / Back to Tasks List\n"

        read -r -p "Enter choice [0-7]: " e_ch || true
        case "$e_ch" in
            1)
                if [ "$enabled" = "true" ]; then
                    sed -i 's/^ENABLED=.*/ENABLED=false/' "$conf"
                else
                    sed -i 's/^ENABLED=.*/ENABLED=true/' "$conf"
                fi
                ;;
            2)
                read -r -p "Enter new schedule time [HH:MM] (e.g. 10:00): " new_time || true
                if [[ "$new_time" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
                    sed -i "s/^TIME=.*/TIME=${new_time}/" "$conf"
                    echo -e "${GREEN}Time updated to ${new_time}.${NC}"
                else
                    echo -e "${RED}Invalid time format. Please use HH:MM (24-hour).${NC}"
                fi
                sleep 1
                ;;
            3)
                echo -e "Select period: 1) daily  2) weekly  3) monthly  4) yearly"
                read -r -p "Choice [1-4]: " p_ch || true
                case "$p_ch" in
                    1) sed -i 's/^KIND=.*/KIND=daily/' "$conf" ; sed -i 's/^PDF_BUCKET=.*/PDF_BUCKET=DAILY_REPORTS/' "$conf" ;;
                    2) sed -i 's/^KIND=.*/KIND=weekly/' "$conf"; sed -i 's/^PDF_BUCKET=.*/PDF_BUCKET=WEEKLY_REPORTS/' "$conf" ;;
                    3) sed -i 's/^KIND=.*/KIND=monthly/' "$conf"; sed -i 's/^PDF_BUCKET=.*/PDF_BUCKET=MONTHLY_REPORTS/' "$conf" ;;
                    4) sed -i 's/^KIND=.*/KIND=yearly/' "$conf"; sed -i 's/^PDF_BUCKET=.*/PDF_BUCKET=YEARLY_REPORTS/' "$conf" ;;
                esac
                ;;
            4)
                if [ "$kind" = "weekly" ]; then
                    read -r -p "Enter Day of Week [Mon/Tue/Wed/Thu/Fri/Sat/Sun]: " new_dow || true
                    if grep -q '^DAY_OF_WEEK=' "$conf"; then
                        sed -i "s/^DAY_OF_WEEK=.*/DAY_OF_WEEK=${new_dow}/" "$conf"
                    else
                        echo "DAY_OF_WEEK=${new_dow}" >> "$conf"
                    fi
                elif [ "$kind" = "monthly" ]; then
                    read -r -p "Enter Day of Month [1-31]: " new_dom || true
                    printf -v new_dom "%02d" "$new_dom"
                    if grep -q '^DAY_OF_MONTH=' "$conf"; then
                        sed -i "s/^DAY_OF_MONTH=.*/DAY_OF_MONTH=${new_dom}/" "$conf"
                    else
                        echo "DAY_OF_MONTH=${new_dom}" >> "$conf"
                    fi
                elif [ "$kind" = "yearly" ]; then
                    read -r -p "Enter Day of Year [MM-DD] (e.g. 01-01): " new_doy || true
                    if grep -q '^DAY_OF_YEAR=' "$conf"; then
                        sed -i "s/^DAY_OF_YEAR=.*/DAY_OF_YEAR=${new_doy}/" "$conf"
                    else
                        echo "DAY_OF_YEAR=${new_doy}" >> "$conf"
                    fi
                fi
                ;;
            5)
                read -r -p "Enter new description: " new_desc || true
                if [ -n "$new_desc" ]; then
                    sed -i "s|^DESCRIPTION=.*|DESCRIPTION=${new_desc}|" "$conf"
                fi
                ;;
            6)
                read -r -p "Enter full path to report script: " new_scr || true
                if [ -n "$new_scr" ]; then
                    sed -i "s|^REPORT_SCRIPT=.*|REPORT_SCRIPT=${new_scr}|" "$conf"
                fi
                ;;
            7)
                echo -e "\n${GREEN}Applying updates and re-enabling systemd timer...${NC}"
                bash "$REPORTER_SH" enable "$tid"
                press_enter
                ;;
            0|[qQ])
                return 0
                ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# 5. CREATE NEW DAILY, WEEKLY, MONTHLY OR YEARLY REPORT (WIZARD)
# ------------------------------------------------------------------------------
create_new_report_wizard() {
    safe_clear
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}     CREATE NEW REPORT TASK WIZARD: DAILY, WEEKLY, MONTHLY, YEARLY    ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

    echo -e "${BOLD}Step 1: Select Report Frequency / Kind${NC}"
    echo -e "  ${CYAN}1)${NC} Daily Report   ${DIM}(Executes every day at specified time)${NC}"
    echo -e "  ${CYAN}2)${NC} Weekly Report  ${DIM}(Executes once per week on specified day, e.g. Mon)${NC}"
    echo -e "  ${CYAN}3)${NC} Monthly Report ${DIM}(Executes once per month on specified day of month, e.g. 1st)${NC}"
    echo -e "  ${CYAN}4)${NC} Yearly Report  ${DIM}(Executes once per year on specified date, e.g. Jan 01)${NC}"
    echo -e "  ${CYAN}0)${NC} Cancel Wizard\n"

    read -r -p "Enter period choice [1-4]: " p_choice || true
    local kind="" bucket=""
    case "$p_choice" in
        1) kind="daily"; bucket="DAILY_REPORTS" ;;
        2) kind="weekly"; bucket="WEEKLY_REPORTS" ;;
        3) kind="monthly"; bucket="MONTHLY_REPORTS" ;;
        4) kind="yearly"; bucket="YEARLY_REPORTS" ;;
        *) echo -e "${DIM}Wizard cancelled.${NC}"; sleep 1; return 0 ;;
    esac

    # Step 2: Task ID
    local default_id="${kind^^}_REPORT_TASK_$(date +%s | tail -c 5)"
    echo -e "\n${BOLD}Step 2: Task Identifier${NC}"
    read -r -p "Enter unique Task ID (letters, numbers, underscores) [default: ${default_id}]: " user_id || true
    local task_id="${user_id:-$default_id}"
    task_id=$(echo "$task_id" | tr -c 'a-zA-Z0-9_' '_' | sed 's/_$//')

    local conf_file="${TASKS_DIR}/${task_id}.conf"
    if [ -f "$conf_file" ]; then
        echo -e "${RED}Error: Task ${task_id} already exists at ${conf_file}!${NC}"
        press_enter
        return 1
    fi

    # Step 3: Schedule details
    local dow="Mon" dom="01" doy="01-01"
    if [ "$kind" = "weekly" ]; then
        echo -e "\n${BOLD}Step 3: Day of Week${NC}"
        read -r -p "Enter Day of Week (Mon, Tue, Wed, Thu, Fri, Sat, Sun) [default: Mon]: " user_dow || true
        dow="${user_dow:-Mon}"
    elif [ "$kind" = "monthly" ]; then
        echo -e "\n${BOLD}Step 3: Day of Month${NC}"
        read -r -p "Enter Day of Month (1-31) [default: 1]: " user_dom || true
        printf -v dom "%02d" "${user_dom:-1}"
    elif [ "$kind" = "yearly" ]; then
        echo -e "\n${BOLD}Step 3: Day of Year${NC}"
        read -r -p "Enter Day of Year in MM-DD format [default: 01-01]: " user_doy || true
        doy="${user_doy:-01-01}"
    fi

    # Step 4: Execution Time
    echo -e "\n${BOLD}Step 4: Scheduled Execution Time${NC}"
    read -r -p "Enter Execution Time in 24-hr HH:MM format [default: 10:00]: " user_time || true
    local exec_time="${user_time:-10:00}"

    # Step 5: Description
    echo -e "\n${BOLD}Step 5: Report Description${NC}"
    read -r -p "Enter brief description [default: ${kind^^} Scheduled System Report]: " user_desc || true
    local description="${user_desc:-${kind^^} Scheduled System Report}"

    # Step 6: Report Script
    echo -e "\n${BOLD}Step 6: Generator Script Path${NC}"
    echo -e "  Presets available:"
    echo -e "  1) Mix Manager Bridge: /var/home/mplanetarian/Documents/BASH_SCRIPTS/MP_Gen_Mix_Manager_Report.sh ${kind}"
    echo -e "  2) AI Brain Logs Bridge: /var/home/mplanetarian/Documents/BASH_SCRIPTS/MP_Gen_AI_Report.sh"
    echo -e "  3) Custom Script / Command Path"
    read -r -p "Select preset [1-3, default: 1]: " scr_opt || true
    local script_path=""
    case "${scr_opt:-1}" in
        1) script_path="/var/home/mplanetarian/Documents/BASH_SCRIPTS/MP_Gen_Mix_Manager_Report.sh ${kind}" ;;
        2) script_path="/var/home/mplanetarian/Documents/BASH_SCRIPTS/MP_Gen_AI_Report.sh" ;;
        3)
            read -r -p "Enter full path to script: " custom_scr || true
            script_path="${custom_scr}"
            ;;
        *) script_path="/var/home/mplanetarian/Documents/BASH_SCRIPTS/MP_Gen_Mix_Manager_Report.sh ${kind}" ;;
    esac

    # Review & Confirm
    safe_clear
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}                   REVIEW NEW REPORT TASK CONFIG                      ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
    echo -e "  Task ID:          ${BOLD}${CYAN}${task_id}${NC}"
    echo -e "  Frequency:        ${BOLD}${YELLOW}${kind^^}${NC}"
    echo -e "  Time:             ${BOLD}${WHITE}${exec_time}${NC}"
    [ "$kind" = "weekly" ]  && echo -e "  Day of Week:      ${BOLD}${WHITE}${dow}${NC}"
    [ "$kind" = "monthly" ] && echo -e "  Day of Month:     ${BOLD}${WHITE}${dom}${NC}"
    [ "$kind" = "yearly" ]  && echo -e "  Day of Year:      ${BOLD}${WHITE}${doy}${NC}"
    echo -e "  Bucket:           ${bucket}"
    echo -e "  Description:      ${description}"
    echo -e "  Voice Engine:     Stephen Hawking (Enters the Matrix)"
    echo -e "  Generator Script: ${script_path}\n"

    read -r -p "Create this task and write configuration? [Y/n]: " conf_ok || true
    case "${conf_ok:-y}" in
        [yY]|[yY][eE][sS]|"")
            cat > "$conf_file" <<EOF
# MP_Reporter task configuration
TASK_ID=${task_id}
ENABLED=true
KIND=${kind}
TIME=${exec_time}
TIMEZONE=Europe/London
PDF_BUCKET=${bucket}
REPORT_SCRIPT=${script_path}
DESCRIPTION=${description}
VOICE_NAME=stephen_hawking_matrix
VOICE_LABEL=Stephen Hawking (Enters the Matrix)
EOF
            if [ "$kind" = "weekly" ]; then
                echo "DAY_OF_WEEK=${dow}" >> "$conf_file"
            elif [ "$kind" = "monthly" ]; then
                echo "DAY_OF_MONTH=${dom}" >> "$conf_file"
            elif [ "$kind" = "yearly" ]; then
                echo "DAY_OF_YEAR=${doy}" >> "$conf_file"
            fi

            echo -e "\n${GREEN}Successfully created task config at ${conf_file}!${NC}"

            read -r -p "Enable and start systemd user timer now? [Y/n]: " en_ok || true
            case "${en_ok:-y}" in
                [yY]|[yY][eE][sS]|"")
                    echo -e "\n${GREEN}Enabling systemd timer...${NC}"
                    bash "$REPORTER_SH" enable "$task_id"
                    ;;
            esac
            press_enter
            ;;
        *)
            echo -e "${YELLOW}Task creation cancelled.${NC}"
            sleep 1
            ;;
    esac
}

# ------------------------------------------------------------------------------
# 6. UPDATE EMAIL RECIPIENTS & SETTINGS
# ------------------------------------------------------------------------------
update_email_recipients_menu() {
    while true; do
        safe_clear
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}        UPDATE REPORT EMAIL RECIPIENTS & DELIVERY SETTINGS            ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"

        local recips="" enabled="true" time="13:00" smtp_user=""
        if [ -f "$EMAIL_CONFIG" ]; then
            recips=$(grep -E '^EMAIL_RECIPIENTS=' "$EMAIL_CONFIG" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
            enabled=$(grep -E '^EMAIL_REPORTS_ENABLED=' "$EMAIL_CONFIG" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "true")
            time=$(grep -E '^EMAIL_SCHEDULED_TIME=' "$EMAIL_CONFIG" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "13:00")
            smtp_user=$(grep -E '^SMTP_USER=' "$EMAIL_CONFIG" 2>/dev/null | cut -d= -f2 | tr -d '"' || true)
        fi

        echo -e "  Email Reports Status:     $([ "$enabled" = "true" ] && echo -e "${GREEN}ENABLED${NC}" || echo -e "${RED}DISABLED${NC}")"
        echo -e "  Scheduled Daily Send:     ${BOLD}${CYAN}${time}${NC} (24-hour format)"
        echo -e "  SMTP Outbound User:       ${WHITE}${smtp_user}${NC}"
        echo -e "  Active Recipients:        ${BOLD}${GREEN}${recips}${NC}\n"

        echo -e "  ${BOLD}Select an action:${NC}"
        echo -e "  ${CYAN}1)${NC} Update Recipient Email Addresses ${DIM}(Comma-separated list)${NC}"
        echo -e "  ${CYAN}2)${NC} Change Scheduled Daily Delivery Time ${DIM}(e.g. 13:00)${NC}"
        echo -e "  ${CYAN}3)${NC} Toggle Automated Daily Email Dispatch ON / OFF"
        echo -e "  ${CYAN}4)${NC} Configure / Update Google / iCloud App Password"
        echo -e "  ${CYAN}5)${NC} Test SMTP Server Authentication & Connection"
        echo -e "  ${CYAN}6)${NC} Force Send Daily Email Briefing Now ${DIM}(Test Outbound Dispatch)${NC}"
        echo -e "  ${CYAN}0)${NC} Return to Reports Menu\n"

        read -r -p "Enter choice [0-6]: " em_ch || true
        case "$em_ch" in
            1)
                echo -e "\nCurrent Recipients: ${CYAN}${recips}${NC}"
                echo -e "${DIM}Enter comma-separated email addresses (e.g. user1@domain.com, user2@domain.com):${NC}"
                read -r -p "New Recipients: " new_recips || true
                if [ -n "$new_recips" ]; then
                    sed -i "s|^EMAIL_RECIPIENTS=.*|EMAIL_RECIPIENTS=\"${new_recips}\"|" "$EMAIL_CONFIG"
                    echo -e "\n${GREEN}Recipients updated successfully!${NC}"
                fi
                sleep 1
                ;;
            2)
                read -r -p "Enter new delivery time [HH:MM] (default 13:00): " new_time || true
                if [[ "$new_time" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
                    sed -i "s/^EMAIL_SCHEDULED_TIME=.*/EMAIL_SCHEDULED_TIME=\"${new_time}\"/" "$EMAIL_CONFIG"
                    echo -e "${GREEN}Email scheduled time updated to ${new_time}.${NC}"
                else
                    echo -e "${RED}Invalid time format.${NC}"
                fi
                sleep 1
                ;;
            3)
                if [ "$enabled" = "true" ]; then
                    sed -i 's/^EMAIL_REPORTS_ENABLED=.*/EMAIL_REPORTS_ENABLED="false"/' "$EMAIL_CONFIG"
                    echo -e "${YELLOW}Email reports disabled.${NC}"
                else
                    sed -i 's/^EMAIL_REPORTS_ENABLED=.*/EMAIL_REPORTS_ENABLED="true"/' "$EMAIL_CONFIG"
                    echo -e "${GREEN}Email reports enabled.${NC}"
                fi
                sleep 1
                ;;
            4)
                bash "$EMAIL_SH" configure-password
                press_enter
                ;;
            5)
                echo -e "\n${YELLOW}Testing SMTP Server Connection...${NC}\n"
                bash "$EMAIL_SH" test-smtp
                press_enter
                ;;
            6)
                echo -e "\n${YELLOW}Force-sending daily email report...${NC}\n"
                bash "$EMAIL_SH" force-send
                press_enter
                ;;
            0|[qQ])
                return 0
                ;;
            *)
                echo -e "${RED}Invalid choice!${NC}"
                sleep 1
                ;;
        esac
    done
}

# ------------------------------------------------------------------------------
# 7. RUN / FORCE GENERATE ANY REPORT NOW
# ------------------------------------------------------------------------------
run_report_now_menu() {
    safe_clear
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
    echo -e "${BOLD}${MAGENTA}             RUN / FORCE GENERATE ANY REPORT ON-DEMAND                ${NC}"
    echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
    echo -e "  ${BOLD}${CYAN}1)${NC} Generate Daily Mix Report Now        ${DIM}(Force Update & Mathematical Analysis)${NC}"
    echo -e "  ${BOLD}${CYAN}2)${NC} Generate Weekly Mix Report Now       ${DIM}(Force Update & 7-Day Performance)${NC}"
    echo -e "  ${BOLD}${CYAN}3)${NC} Generate Monthly Mix Report Now      ${DIM}(Force Update & Trend Analysis)${NC}"
    echo -e "  ${BOLD}${CYAN}4)${NC} Generate Yearly Mix Report Now       ${DIM}(Force Update & Annual Projections)${NC}"
    echo -e "  ${BOLD}${CYAN}5)${NC} Generate AI Brain Logs Report Now    ${DIM}(Google Gemini, Grok, Ollama, Hawking Voice)${NC}"
    echo -e "  ${BOLD}${CYAN}6)${NC} Generate Bazzite System Report Now   ${DIM}(OS, Hardware, Memory & Storage Health)${NC}"
    echo -e "  ${BOLD}${CYAN}7)${NC} Run All Active Tasks Now             ${DIM}(Sequential execution of all enabled tasks)${NC}"
    echo -e "  ${BOLD}${CYAN}0)${NC} Return to Reports Menu\n"

    read -r -p "Enter choice [0-7]: " r_ch || true
    case "$r_ch" in
        1)
            echo -e "\n${GREEN}Running Daily Mix Report...${NC}\n"
            bash "$REPORTER_SH" run DAILY_REPORT_TASK_002_MIX_MANAGER
            press_enter
            ;;
        2)
            echo -e "\n${GREEN}Running Weekly Mix Report...${NC}\n"
            bash "$REPORTER_SH" run WEEKLY_REPORT_TASK_001_MIX_MANAGER
            press_enter
            ;;
        3)
            echo -e "\n${GREEN}Running Monthly Mix Report...${NC}\n"
            bash "$REPORTER_SH" run MONTHLY_REPORT_TASK_001_MIX_MANAGER
            press_enter
            ;;
        4)
            echo -e "\n${GREEN}Running Yearly Mix Report...${NC}\n"
            bash "$REPORTER_SH" run YEARLY_REPORT_TASK_001_MIX_MANAGER
            press_enter
            ;;
        5)
            echo -e "\n${GREEN}Running AI Brain Logs Report...${NC}\n"
            bash "$REPORTER_SH" run DAILY_REPORT_TASK_003_AI
            press_enter
            ;;
        6)
            echo -e "\n${GREEN}Running Bazzite System Report...${NC}\n"
            bash "$REPORTER_SH" run DAILY_REPORT_TASK_001
            press_enter
            ;;
        7)
            echo -e "\n${GREEN}Running ALL configured tasks...${NC}\n"
            shopt -s nullglob
            for conf in "${TASKS_DIR}"/*.conf; do
                local tid
                tid=$(grep -E '^TASK_ID=' "$conf" 2>/dev/null | cut -d= -f2 | tr -d '"' || basename "$conf" .conf)
                echo -e "\n${BOLD}${CYAN}>>> Executing Task: ${tid} <<<${NC}"
                bash "$REPORTER_SH" run "$tid" || true
            done
            shopt -u nullglob
            press_enter
            ;;
        0|[qQ])
            return 0
            ;;
    esac
}

# ------------------------------------------------------------------------------
# MAIN INTERACTIVE MENU LOOP
# ------------------------------------------------------------------------------
main_menu() {
    while true; do
        safe_clear
        local d_status="${RED}DISABLED${NC}"
        [ "${DAILY_REPORTS_ENABLED:-true}" = "true" ] && d_status="${GREEN}ENABLED${NC}"
        local w_status="${GREEN}ENABLED${NC} (Mon 10:00)"
        local m_status="${GREEN}ENABLED${NC} (01 10:00)"
        local y_status="${GREEN}ENABLED${NC} (01-01 10:00)"
        local e_status="${GREEN}ENABLED${NC} (13:00)"

        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "${BOLD}${MAGENTA}       MP REPORTER SUITE, AUTOMATED SCHEDULES & TELEMETRY             ${NC}"
        echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
        echo -e "  Daily: ${d_status} │ Weekly: ${w_status} │ Monthly: ${m_status} │ Yearly: ${y_status} │ Email: ${e_status}\n"

        echo -e "  ${BOLD}REPORT VIEWING & SCHEDULE CALENDAR:${NC}"
        echo -e "  ${BOLD}${CYAN}1)${NC} View Reports (Daily, Weekly, Monthly, Yearly, AI) ${DIM}(Text, PDF & Hawking Audio)${NC}"
        echo -e "  ${BOLD}${CYAN}2)${NC} 12-Month Scheduled Reports Calendar View        ${DIM}(Interactive forward calendar +12 Months)${NC}"
        echo ""
        echo -e "  ${BOLD}TASK MANAGEMENT & SCHEDULING:${NC}"
        echo -e "  ${BOLD}${CYAN}3)${NC} Schedule & Enable/Disable Reports & Timers       ${DIM}(Systemd user timers & auto-run)${NC}"
        echo -e "  ${BOLD}${CYAN}4)${NC} Edit Existing Report Tasks                       ${DIM}(Frequency, Day, Time, Voice, Script)${NC}"
        echo -e "  ${BOLD}${CYAN}5)${NC} Create New Daily, Weekly, Monthly or Yearly Report${DIM}(Interactive task creation wizard)${NC}"
        echo -e "  ${BOLD}${CYAN}6)${NC} Update Report Email Recipients & Settings        ${DIM}(Recipient addresses & 13:00 send)${NC}"
        echo -e "  ${BOLD}${CYAN}7)${NC} Run / Force Generate Any Report Now             ${DIM}(On-demand generation & audio synthesis)${NC}"
        echo ""
        echo -e "  ${BOLD}EMAIL AUTOMATION & DASHBOARDS:${NC}"
        echo -e "  ${BOLD}${CYAN}8)${NC} Automated Daily Email Briefing & SMTP Settings   ${DIM}(Test build, SMTP auth, timer)${NC}"
        echo -e "  ${BOLD}${CYAN}9)${NC} Multi-Archive Statistics Dashboard               ${DIM}(SOF_Archive_Stats.sh)${NC}"
        echo -e "  ${BOLD}${CYAN}10)${NC} Master Tracklist HTML & Multi-Folder Statistics ${DIM}(Tracklist analyzer)${NC}"
        echo -e "  ${BOLD}${CYAN}11)${NC} Advanced Math Formulas & Predictive Analytics   ${DIM}(Skew, Kurtosis, Entropy, Holt)${NC}"
        echo -e "  ${BOLD}${CYAN}12)${NC} Continuous User Operations Telemetry Log        ${DIM}(Live activity & workflow tracking)${NC}"
        echo -e "  ${BOLD}${CYAN}13)${NC} View / Inspect MP_Error.log                     ${DIM}(Error logging audit)${NC}"
        echo -e "  ${BOLD}${CYAN}14)${NC} Launch Standalone MP Reporter Menu              ${DIM}(Full MP_Reporter.sh CLI)${NC}"
        echo ""
        echo -e "  ${BOLD}${CYAN}0)${NC} Return to Main Menu ${DIM}(or Esc / q)${NC}\n"

        read -r -p "Enter choice [0-14]: " choice || true
        case "$choice" in
            1) view_reports_menu ;;
            2) view_calendar_menu ;;
            3) manage_schedules_menu ;;
            4) edit_task_menu ;;
            5) create_new_report_wizard ;;
            6) update_email_recipients_menu ;;
            7) run_report_now_menu ;;
            8)
                safe_clear
                bash "$EMAIL_SH" status
                echo ""
                echo -e "  ${BOLD}${CYAN}1)${NC} Test Build (Generate Consolidated Single PDF & Stephen Hawking Audio)"
                echo -e "  ${BOLD}${CYAN}2)${NC} Configure Google / iCloud Email App-Specific Password"
                echo -e "  ${BOLD}${CYAN}3)${NC} Test Outbound SMTP Server Authentication"
                echo -e "  ${BOLD}${CYAN}4)${NC} Force Send Daily Email Briefing Now (Override 1/day limit)"
                echo -e "  ${BOLD}${CYAN}5)${NC} Enable Systemd 13:00 Daily Timer"
                echo -e "  ${BOLD}${CYAN}6)${NC} Disable Systemd 13:00 Daily Timer"
                echo -e "  ${BOLD}${CYAN}0)${NC} Return to Reports Menu\n"
                read -r -p "Enter choice [0-6]: " ech || true
                case "$ech" in
                    1) bash "$EMAIL_SH" dry-run; press_enter ;;
                    2) bash "$EMAIL_SH" configure-password; press_enter ;;
                    3) bash "$EMAIL_SH" test-smtp; press_enter ;;
                    4) bash "$EMAIL_SH" force-send; press_enter ;;
                    5) bash "$EMAIL_SH" enable-timer; press_enter ;;
                    6) bash "$EMAIL_SH" disable-timer; press_enter ;;
                esac
                ;;
            9)
                echo -e "\n${BOLD}${YELLOW}Loading Multi-Archive Statistics Dashboard...${NC}\n"
                if [ -x "$SCRIPT_DIR/SOF_Archive_Stats.sh" ]; then
                    "$SCRIPT_DIR/SOF_Archive_Stats.sh"
                elif [ -f "$SCRIPT_DIR/SOF_Archive_Stats.sh" ]; then
                    bash "$SCRIPT_DIR/SOF_Archive_Stats.sh"
                fi
                press_enter
                ;;
            10)
                safe_clear
                echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
                echo -e "${BOLD}${MAGENTA}          MASTER TRACKLIST HTML & MULTI-FOLDER AUDIT                  ${NC}"
                echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
                python3 "$SCRIPT_DIR/scripts/mp_tracklist_analyzer.py"
                press_enter
                ;;
            11)
                safe_clear
                echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
                echo -e "${BOLD}${MAGENTA}    ADVANCED MATHEMATICAL FORMULAS & PREDICTIVE ANALYTICS DASHBOARD   ${NC}"
                echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
                python3 "$SCRIPT_DIR/scripts/mp_analytics_engine.py"
                press_enter
                ;;
            12)
                safe_clear
                echo -e "${BOLD}${MAGENTA}======================================================================${NC}"
                echo -e "${BOLD}${MAGENTA}           CONTINUOUS USER OPERATIONS & ACTIVITY TELEMETRY            ${NC}"
                echo -e "${BOLD}${MAGENTA}======================================================================${NC}\n"
                python3 "$SCRIPT_DIR/scripts/mp_activity_tracker.py" --summary daily
                press_enter
                ;;
            13)
                safe_clear
                bash "$SCRIPT_DIR/scripts/mp_logging.sh" --tail
                press_enter
                ;;
            14)
                bash "$REPORTER_SH" menu
                ;;
            0|[qQ]|[eE][xX][iI][tT])
                return 0
                ;;
            *)
                echo -e "\n${RED}Invalid option!${NC}"
                sleep 1
                ;;
        esac
    done
}

case "${1:-}" in
    view|view-reports)
        view_reports_menu
        ;;
    calendar|cal|12-months)
        view_calendar_menu
        ;;
    schedule|schedules|timers)
        manage_schedules_menu
        ;;
    edit|edit-tasks)
        edit_task_menu
        ;;
    create|create-task|new)
        create_new_report_wizard
        ;;
    email|recipients)
        update_email_recipients_menu
        ;;
    run|generate)
        shift
        if [ -n "${1:-}" ]; then
            bash "$REPORTER_SH" run "$@"
        else
            run_report_now_menu
        fi
        ;;
    "")
        main_menu
        ;;
    *)
        echo "Usage: $(basename "$0") {view|calendar|schedule|edit|create|email|run}"
        exit 1
        ;;
esac
