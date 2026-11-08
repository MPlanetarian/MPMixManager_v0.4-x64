#!/usr/bin/env python3
"""
mp_reports_calendar.py - MP Reporter 12-Month Scheduled Reports Calendar Viewer
Provides interactive +12 months forward projection of all scheduled Daily, Weekly,
Monthly, and Yearly reports along with automated Daily Email brief dispatches.
"""

import sys
import os
import re
import argparse
import calendar
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple

TASKS_DIR = "/var/home/mplanetarian/MP_REPORTER/tasks"
EMAIL_CONFIG = "/var/home/mplanetarian/MP_REPORTER/email_config.env"

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_BLUE = "\033[1;34m"
CLR_MAGENTA = "\033[1;35m"
CLR_CYAN = "\033[1;36m"
CLR_WHITE = "\033[1;37m"
CLR_BG_BLUE = "\033[44m\033[1;37m"
CLR_BG_MAGENTA = "\033[45m\033[1;37m"

DAY_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


def load_task_configs() -> List[Dict[str, Any]]:
    """Loads all task configuration files from MP_REPORTER/tasks/."""
    tasks = []
    if not os.path.isdir(TASKS_DIR):
        return tasks

    for fname in sorted(os.listdir(TASKS_DIR)):
        if not fname.endswith(".conf"):
            continue
        filepath = os.path.join(TASKS_DIR, fname)
        cfg: Dict[str, Any] = {"file": fname}
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"').strip("'")

        # Normalize
        cfg["ENABLED"] = cfg.get("ENABLED", "true").lower() in ("true", "1", "yes")
        cfg["KIND"] = cfg.get("KIND", "daily").lower()
        cfg["TIME"] = cfg.get("TIME", "10:00")
        cfg["TASK_ID"] = cfg.get("TASK_ID", fname[:-5])
        cfg["DESCRIPTION"] = cfg.get("DESCRIPTION", cfg["TASK_ID"])
        cfg["DAY_OF_WEEK"] = cfg.get("DAY_OF_WEEK", "Mon")
        try:
            cfg["DAY_OF_MONTH"] = int(cfg.get("DAY_OF_MONTH", "1"))
        except ValueError:
            cfg["DAY_OF_MONTH"] = 1
        cfg["DAY_OF_YEAR"] = cfg.get("DAY_OF_YEAR", "01-01")
        tasks.append(cfg)

    return tasks


def load_email_config() -> Dict[str, Any]:
    """Loads email scheduling configuration from email_config.env."""
    cfg = {
        "EMAIL_REPORTS_ENABLED": True,
        "EMAIL_SCHEDULED_TIME": "13:00",
        "EMAIL_RECIPIENTS": "",
    }
    if os.path.isfile(EMAIL_CONFIG):
        with open(EMAIL_CONFIG, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in cfg:
                        if k == "EMAIL_REPORTS_ENABLED":
                            cfg[k] = v.lower() in ("true", "1", "yes")
                        else:
                            cfg[k] = v
    return cfg


def get_events_for_date(d: date, tasks: List[Dict[str, Any]], email_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns all scheduled events for a specific calendar date."""
    events = []
    weekday_idx = d.weekday()  # Monday is 0, Sunday is 6
    day_num = d.day
    mm_dd = f"{d.month:02d}-{d.day:02d}"

    for t in tasks:
        if not t.get("ENABLED", True):
            continue

        kind = t.get("KIND", "daily")
        is_match = False

        if kind == "daily":
            is_match = True
        elif kind == "weekly":
            dow_str = str(t.get("DAY_OF_WEEK", "Mon")).strip().lower()
            target_idx = DAY_MAP.get(dow_str, 0)
            if weekday_idx == target_idx:
                is_match = True
        elif kind == "monthly":
            dom = t.get("DAY_OF_MONTH", 1)
            # handle month length edge cases (e.g. Feb 30 -> last day of month)
            last_day = calendar.monthrange(d.year, d.month)[1]
            effective_dom = min(dom, last_day)
            if day_num == effective_dom:
                is_match = True
        elif kind == "yearly":
            doy = t.get("DAY_OF_YEAR", "01-01")
            if mm_dd == doy:
                is_match = True

        if is_match:
            events.append({
                "type": kind,
                "time": t.get("TIME", "10:00"),
                "task_id": t.get("TASK_ID"),
                "description": t.get("DESCRIPTION"),
                "voice": t.get("VOICE_LABEL", t.get("VOICE_NAME", "Stephen Hawking")),
                "pdf_bucket": t.get("PDF_BUCKET", "REPORTS"),
            })

    # Automated daily email dispatch
    if email_cfg.get("EMAIL_REPORTS_ENABLED", True):
        events.append({
            "type": "email",
            "time": email_cfg.get("EMAIL_SCHEDULED_TIME", "13:00"),
            "task_id": "DAILY_EMAIL_BRIEF",
            "description": f"Automated Email Dispatch ({email_cfg.get('EMAIL_RECIPIENTS', 'Configured Recipients')})",
            "voice": "Stephen Hawking Matrix Audio Attachment",
            "pdf_bucket": "EMAIL_DISPATCH",
        })

    # Sort by time
    events.sort(key=lambda x: x["time"])
    return events


def render_month_calendar(year: int, month: int, tasks: List[Dict[str, Any]], email_cfg: Dict[str, Any], today: date) -> List[str]:
    """Renders a single month's calendar box with status badges."""
    cal = calendar.Calendar(firstweekday=0) # Monday first
    month_days = cal.monthdayscalendar(year, month)
    month_name = calendar.month_name[month]
    title = f"{month_name} {year}"

    lines = []
    lines.append(f"{CLR_BOLD}{CLR_CYAN}┌─────────────────────────────────────────────────────────────┐{CLR_RESET}")
    lines.append(f"{CLR_BOLD}{CLR_CYAN}│{CLR_RESET}  {CLR_BOLD}{title.center(55)}{CLR_RESET}  {CLR_BOLD}{CLR_CYAN}│{CLR_RESET}")
    lines.append(f"{CLR_BOLD}{CLR_CYAN}├──────┬──────┬──────┬──────┬──────┬──────┬───────────────────┤{CLR_RESET}")
    lines.append(f"{CLR_BOLD}{CLR_CYAN}│{CLR_RESET} "
                 f"{CLR_WHITE}Mon{CLR_RESET}  {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} "
                 f"{CLR_WHITE}Tue{CLR_RESET}  {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} "
                 f"{CLR_WHITE}Wed{CLR_RESET}  {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} "
                 f"{CLR_WHITE}Thu{CLR_RESET}  {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} "
                 f"{CLR_WHITE}Fri{CLR_RESET}  {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} "
                 f"{CLR_YELLOW}Sat{CLR_RESET}  {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} "
                 f"{CLR_YELLOW}Sun{CLR_RESET}               {CLR_BOLD}{CLR_CYAN}│{CLR_RESET}")
    lines.append(f"{CLR_BOLD}{CLR_CYAN}├──────┼──────┼──────┼──────┼──────┼──────┼───────────────────┤{CLR_RESET}")

    for week in month_days:
        day_cells = []
        badge_cells = []
        for day in week:
            if day == 0:
                day_cells.append("    ")
                badge_cells.append("    ")
            else:
                d = date(year, month, day)
                is_today = (d == today)
                events = get_events_for_date(d, tasks, email_cfg)

                # Day cell
                if is_today:
                    day_str = f"{CLR_BG_MAGENTA}{day:2d}*{CLR_RESET}"
                elif d.weekday() >= 5:
                    day_str = f"{CLR_YELLOW}{day:2d} {CLR_RESET}"
                else:
                    day_str = f"{CLR_WHITE}{day:2d} {CLR_RESET}"
                day_cells.append(day_str)

                # Badges: D=Daily, W=Weekly, M=Monthly, Y=Yearly, E=Email
                b_types = {e["type"] for e in events}
                badges = ""
                if "yearly" in b_types:
                    badges += f"{CLR_RED}Y{CLR_RESET}"
                if "monthly" in b_types:
                    badges += f"{CLR_MAGENTA}M{CLR_RESET}"
                if "weekly" in b_types:
                    badges += f"{CLR_BLUE}W{CLR_RESET}"
                if "daily" in b_types:
                    badges += f"{CLR_GREEN}D{CLR_RESET}"
                if "email" in b_types:
                    badges += f"{CLR_YELLOW}E{CLR_RESET}"

                # Pad to 4 printable characters
                raw_badge_len = ("Y" if "yearly" in b_types else "") + \
                                ("M" if "monthly" in b_types else "") + \
                                ("W" if "weekly" in b_types else "") + \
                                ("D" if "daily" in b_types else "") + \
                                ("E" if "email" in b_types else "")
                padding = " " * max(0, 4 - len(raw_badge_len))
                badge_cells.append(badges + padding)

        # Build week row
        week_line_1 = f"{CLR_BOLD}{CLR_CYAN}│{CLR_RESET} " + f" {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} ".join(day_cells[:6]) + f" {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} {day_cells[6]}               {CLR_BOLD}{CLR_CYAN}│{CLR_RESET}"
        week_line_2 = f"{CLR_BOLD}{CLR_CYAN}│{CLR_RESET} " + f" {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} ".join(badge_cells[:6]) + f" {CLR_BOLD}{CLR_CYAN}│{CLR_RESET} {badge_cells[6]}               {CLR_BOLD}{CLR_CYAN}│{CLR_RESET}"
        lines.append(week_line_1)
        lines.append(week_line_2)

    lines.append(f"{CLR_BOLD}{CLR_CYAN}└──────┴──────┴──────┴──────┴──────┴──────┴───────────────────┘{CLR_RESET}")
    return lines


def render_12_month_year_grid(start_date: date, tasks: List[Dict[str, Any]], email_cfg: Dict[str, Any]) -> str:
    """Renders a full 12-month forward calendar overview with metrics."""
    out = []
    out.append(f"\n{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}")
    out.append(f"{CLR_BOLD}{CLR_GREEN}       MP REPORTER - 12-MONTH SCHEDULED REPORTS CALENDAR (+12 MONTHS AHEAD)            {CLR_RESET}")
    out.append(f"{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}")
    out.append(f"{CLR_DIM}Projection Horizon: {start_date.strftime('%B %Y')} through {(start_date + timedelta(days=365)).strftime('%B %Y')}{CLR_RESET}\n")

    # Metrics calculation
    total_days = 365
    daily_runs = 0
    weekly_runs = 0
    monthly_runs = 0
    yearly_runs = 0
    email_runs = 0

    curr = start_date
    for _ in range(total_days):
        evs = get_events_for_date(curr, tasks, email_cfg)
        for e in evs:
            t = e["type"]
            if t == "daily":
                daily_runs += 1
            elif t == "weekly":
                weekly_runs += 1
            elif t == "monthly":
                monthly_runs += 1
            elif t == "yearly":
                yearly_runs += 1
            elif t == "email":
                email_runs += 1
        curr += timedelta(days=1)

    out.append(f"{CLR_BOLD}SCHEDULED RUN PROJECTIONS OVER THE NEXT 12 MONTHS:{CLR_RESET}")
    out.append(f"  • {CLR_GREEN}[D] Daily Report Jobs:{CLR_RESET}   {CLR_BOLD}{daily_runs:4d}{CLR_RESET} executions scheduled")
    out.append(f"  • {CLR_BLUE}[W] Weekly Report Jobs:{CLR_RESET}  {CLR_BOLD}{weekly_runs:4d}{CLR_RESET} executions scheduled (Every Monday 10:00)")
    out.append(f"  • {CLR_MAGENTA}[M] Monthly Report Jobs:{CLR_RESET} {CLR_BOLD}{monthly_runs:4d}{CLR_RESET} executions scheduled (1st of every month)")
    out.append(f"  • {CLR_RED}[Y] Yearly Report Jobs:{CLR_RESET}  {CLR_BOLD}{yearly_runs:4d}{CLR_RESET} executions scheduled (Annual on Jan 01)")
    out.append(f"  • {CLR_YELLOW}[E] Daily Email Briefs:{CLR_RESET}  {CLR_BOLD}{email_runs:4d}{CLR_RESET} dispatches scheduled ({email_cfg.get('EMAIL_SCHEDULED_TIME', '13:00')})\n")

    # Legend
    out.append(f"{CLR_BOLD}DAY BADGE LEGEND:{CLR_RESET}")
    out.append(f"  {CLR_GREEN}[D]{CLR_RESET} Daily Report  "
               f"  {CLR_BLUE}[W]{CLR_RESET} Weekly Report  "
               f"  {CLR_MAGENTA}[M]{CLR_RESET} Monthly Report  "
               f"  {CLR_RED}[Y]{CLR_RESET} Yearly Report  "
               f"  {CLR_YELLOW}[E]{CLR_RESET} Email Brief  "
               f"  {CLR_BG_MAGENTA} ##*{CLR_RESET} Current Day\n")

    # Render 12 months sequentially (2 months side-by-side or stacked)
    # Stacked month view with mini-tables
    curr_year = start_date.year
    curr_month = start_date.month

    for i in range(12):
        target_year = curr_year + ((curr_month - 1 + i) // 12)
        target_month = ((curr_month - 1 + i) % 12) + 1
        month_lines = render_month_calendar(target_year, target_month, tasks, email_cfg, start_date)
        out.extend(month_lines)
        out.append("")

    return "\n".join(out)


def render_upcoming_timeline(start_date: date, days: int, tasks: List[Dict[str, Any]], email_cfg: Dict[str, Any]) -> str:
    """Renders a chronological timeline for the next N days."""
    out = []
    out.append(f"\n{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}")
    out.append(f"{CLR_BOLD}{CLR_CYAN}        CHRONOLOGICAL REPORT SCHEDULE TIMELINE (NEXT {days} DAYS)                      {CLR_RESET}")
    out.append(f"{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}\n")

    out.append(f"{CLR_BOLD}{'DATE':<12} {'DAY':<5} {'TIME':<7} {'KIND':<9} {'TASK ID / DESCRIPTION':<36} {'AUDIO / VOICE'}{CLR_RESET}")
    out.append(f"{CLR_DIM}{'─'*12} {'─'*5} {'─'*7} {'─'*9} {'─'*36} {'─'*20}{CLR_RESET}")

    curr = start_date
    event_count = 0

    for _ in range(days):
        evs = get_events_for_date(curr, tasks, email_cfg)
        is_today = (curr == start_date)
        date_str = curr.strftime("%Y-%m-%d")
        day_name = curr.strftime("%a")

        if is_today:
            date_display = f"{CLR_BG_MAGENTA}{date_str}*{CLR_RESET}"
        else:
            date_display = f"{CLR_WHITE}{date_str}{CLR_RESET}"

        for idx, e in enumerate(evs):
            event_count += 1
            t = e["type"]
            kind_color = CLR_GREEN
            if t == "weekly":
                kind_color = CLR_BLUE
            elif t == "monthly":
                kind_color = CLR_MAGENTA
            elif t == "yearly":
                kind_color = CLR_RED
            elif t == "email":
                kind_color = CLR_YELLOW

            kind_badge = f"{kind_color}{t.upper():<9}{CLR_RESET}"
            time_str = f"{CLR_BOLD}{e['time']}{CLR_RESET}"
            desc = e["description"]
            if len(desc) > 34:
                desc = desc[:31] + "..."
            task_info = f"{CLR_BOLD}{desc:<36}{CLR_RESET}"
            voice_info = f"{CLR_CYAN}{e.get('voice', 'N/A')}{CLR_RESET}"

            # Only show date on the first event of the day
            d_col = date_display if idx == 0 else " "*12
            day_col = f"{CLR_DIM}{day_name}{CLR_RESET}" if idx == 0 else " "*5

            out.append(f"{d_col:<22} {day_col:<14} {time_str:<16} {kind_badge} {task_info} {voice_info}")

        curr += timedelta(days=1)

    out.append(f"\n{CLR_BOLD}Total Scheduled Executions in Range:{CLR_RESET} {event_count}")
    return "\n".join(out)


def render_task_summary_table(tasks: List[Dict[str, Any]], email_cfg: Dict[str, Any]) -> str:
    """Renders a clean overview table of all tasks and their configured schedules."""
    out = []
    out.append(f"\n{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}")
    out.append(f"{CLR_BOLD}{CLR_GREEN}                    CONFIGURED MP REPORTER TASKS & DISPATCHES                           {CLR_RESET}")
    out.append(f"{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}\n")

    out.append(f"{CLR_BOLD}{'STATUS':<9} {'KIND':<8} {'SCHEDULE / TIMING':<20} {'TASK ID / NAME':<34} {'BUCKET'}{CLR_RESET}")
    out.append(f"{CLR_DIM}{'─'*9} {'─'*8} {'─'*20} {'─'*34} {'─'*16}{CLR_RESET}")

    for t in tasks:
        enabled = t.get("ENABLED", True)
        stat = f"{CLR_GREEN}ACTIVE{CLR_RESET}" if enabled else f"{CLR_RED}DISABLED{CLR_RESET}"
        kind = t.get("KIND", "daily").upper()

        if kind == "DAILY":
            sched = f"Daily at {t.get('TIME')}"
        elif kind == "WEEKLY":
            sched = f"Every {t.get('DAY_OF_WEEK')} at {t.get('TIME')}"
        elif kind == "MONTHLY":
            sched = f"Day {t.get('DAY_OF_MONTH'):02d} at {t.get('TIME')}"
        elif kind == "YEARLY":
            sched = f"Annual {t.get('DAY_OF_YEAR')} {t.get('TIME')}"
        else:
            sched = f"At {t.get('TIME')}"

        task_id = t.get("TASK_ID", "")
        if len(task_id) > 32:
            task_id = task_id[:30] + ".."
        bucket = t.get("PDF_BUCKET", "")

        out.append(f"{stat:<18} {kind:<8} {sched:<20} {task_id:<34} {bucket}")

    # Email line
    e_enabled = email_cfg.get("EMAIL_REPORTS_ENABLED", True)
    e_stat = f"{CLR_GREEN}ACTIVE{CLR_RESET}" if e_enabled else f"{CLR_RED}DISABLED{CLR_RESET}"
    e_time = email_cfg.get("EMAIL_SCHEDULED_TIME", "13:00")
    e_recips = email_cfg.get("EMAIL_RECIPIENTS", "Configured Recipients")
    if len(e_recips) > 32:
        e_recips = e_recips[:30] + ".."
    out.append(f"{e_stat:<18} {'EMAIL':<8} {'Daily at ' + e_time:<20} {e_recips:<34} {'EMAIL_DISPATCH'}")

    return "\n".join(out)


def interactive_calendar_browser(today: date, tasks: List[Dict[str, Any]], email_cfg: Dict[str, Any]):
    """Provides an interactive terminal browser for navigating months."""
    curr_year = today.year
    curr_month = today.month

    while True:
        os.system("clear")
        print(f"\n{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}      MP REPORTER - INTERACTIVE 12-MONTH REPORT CALENDAR VIEWER                        {CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_WHITE}========================================================================================{CLR_RESET}")

        # Render month
        lines = render_month_calendar(curr_year, curr_month, tasks, email_cfg, today)
        for l in lines:
            print(f"  {l}")

        # Events for this month
        cal = calendar.Calendar(firstweekday=0)
        m_days = [d for d in cal.itermonthdays(curr_year, curr_month) if d > 0]
        month_events = []
        for d in m_days:
            dt = date(curr_year, curr_month, d)
            evs = get_events_for_date(dt, tasks, email_cfg)
            for e in evs:
                month_events.append((dt, e))

        print(f"\n  {CLR_BOLD}SCHEDULED EVENTS IN {calendar.month_name[curr_month].upper()} {curr_year}:{CLR_RESET}")
        if not month_events:
            print(f"    {CLR_DIM}No scheduled tasks found in this month.{CLR_RESET}")
        else:
            for dt, e in month_events[:15]:
                t = e["type"]
                k_clr = CLR_GREEN if t == "daily" else (CLR_BLUE if t == "weekly" else (CLR_MAGENTA if t == "monthly" else (CLR_RED if t == "yearly" else CLR_YELLOW)))
                print(f"    • {dt.strftime('%Y-%m-%d')} ({dt.strftime('%a')}) [{k_clr}{t.upper():<7}{CLR_RESET}] {e['time']} - {CLR_BOLD}{e['description']}{CLR_RESET} ({e.get('voice', '')})")
            if len(month_events) > 15:
                print(f"    {CLR_DIM}... and {len(month_events) - 15} more daily/email events ...{CLR_RESET}")

        print(f"\n{CLR_BOLD}{CLR_WHITE}----------------------------------------------------------------------------------------{CLR_RESET}")
        print(f"  {CLR_BOLD}NAVIGATION COMMANDS:{CLR_RESET}")
        print(f"  [n] Next Month    [p] Previous Month   [t] Today's Month    [y] Full 12-Month Year View")
        print(f"  [l] 30-Day Timeline                   [s] All Tasks Table  [q] Return to Mix Manager Menu")
        print(f"{CLR_BOLD}{CLR_WHITE}----------------------------------------------------------------------------------------{CLR_RESET}")

        choice = input(f"  {CLR_BOLD}Select command [n/p/t/y/l/s/q]: {CLR_RESET}").strip().lower()

        if choice in ("q", "quit", "exit", ""):
            break
        elif choice in ("n", "next"):
            curr_month += 1
            if curr_month > 12:
                curr_month = 1
                curr_year += 1
        elif choice in ("p", "prev"):
            curr_month -= 1
            if curr_month < 1:
                curr_month = 12
                curr_year -= 1
        elif choice in ("t", "today"):
            curr_year = today.year
            curr_month = today.month
        elif choice in ("y", "year"):
            os.system("clear")
            print(render_12_month_year_grid(today, tasks, email_cfg))
            input(f"\n{CLR_BOLD}Press [Enter] to return to Interactive Calendar...{CLR_RESET}")
        elif choice in ("l", "timeline"):
            os.system("clear")
            print(render_upcoming_timeline(today, 30, tasks, email_cfg))
            input(f"\n{CLR_BOLD}Press [Enter] to return to Interactive Calendar...{CLR_RESET}")
        elif choice in ("s", "tasks"):
            os.system("clear")
            print(render_task_summary_table(tasks, email_cfg))
            input(f"\n{CLR_BOLD}Press [Enter] to return to Interactive Calendar...{CLR_RESET}")


def main():
    parser = argparse.ArgumentParser(description="MP Reporter 12-Month Scheduled Reports Calendar Viewer")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive monthly calendar browser")
    parser.add_argument("--year-grid", action="store_true", help="Print full 12-month calendar grid for the year ahead")
    parser.add_argument("--timeline", type=int, nargs="?", const=30, help="Print chronological timeline for N days (default: 30)")
    parser.add_argument("--tasks", action="store_true", help="Display summary table of all configured reporter tasks")
    parser.add_argument("--month", type=str, help="Render specific month in YYYY-MM format")

    args = parser.parse_args()

    today = date.today()
    tasks = load_task_configs()
    email_cfg = load_email_config()

    if args.interactive:
        interactive_calendar_browser(today, tasks, email_cfg)
    elif args.year_grid:
        print(render_12_month_year_grid(today, tasks, email_cfg))
    elif args.timeline is not None:
        print(render_upcoming_timeline(today, args.timeline, tasks, email_cfg))
    elif args.tasks:
        print(render_task_summary_table(tasks, email_cfg))
    elif args.month:
        try:
            parts = args.month.split("-")
            y = int(parts[0])
            m = int(parts[1])
            for line in render_month_calendar(y, m, tasks, email_cfg, today):
                print(line)
        except Exception as e:
            print(f"Invalid month format: {args.month}. Use YYYY-MM. Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default behavior when run directly: print year grid followed by upcoming timeline
        print(render_12_month_year_grid(today, tasks, email_cfg))
        print(render_upcoming_timeline(today, 14, tasks, email_cfg))


if __name__ == "__main__":
    main()
