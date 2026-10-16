#!/usr/bin/env python3
"""
mp_activity_tracker.py - Continuous User Activity & Operations Telemetry
Part of MP_Mix_Manager_v0.3

Continuously monitors and records user operations, audio playback, archive tasks,
and workflow transitions across the MP Mix Archive Manager for statistical and
predictive analytics.
"""

import os
import sys
import time
import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Base paths
SCRIPT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ACTIVITY_FILE = LOGS_DIR / "user_activity.jsonl"
USER_CONFIG_DIR = Path.home() / ".config" / "mix-manager"
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
USER_ACTIVITY_MIRROR = USER_CONFIG_DIR / "user_activity.jsonl"

try:
    from scripts.mp_logging import log_error as mp_log_error
except ImportError:
    try:
        from mp_logging import log_error as mp_log_error
    except ImportError:
        def mp_log_error(c, m, e=None, d=None):
            pass

def record_activity(action: str,
                    category: str = "general",
                    details: Optional[Dict[str, Any]] = None,
                    duration_sec: float = 0.0,
                    status: str = "success",
                    error_msg: Optional[str] = None) -> Dict[str, Any]:
    """
    Append an activity record to user_activity.jsonl.
    """
    now = datetime.now()
    entry = {
        "timestamp": now.isoformat(),
        "epoch": time.time(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "hour": now.hour,
        "action": action,
        "category": category,
        "duration_sec": round(float(duration_sec), 2),
        "status": status,
        "details": details or {},
        "error_msg": error_msg
    }

    line = json.dumps(entry) + "\n"

    # Write to primary log
    try:
        with open(ACTIVITY_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        mp_log_error("ActivityTracker", f"Failed writing to {ACTIVITY_FILE}", e)

    # Write to mirror in user config
    try:
        with open(USER_ACTIVITY_MIRROR, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

    # If error status, also log directly to MP_Error.log
    if status == "error" or error_msg:
        mp_log_error(f"Activity:{action}", error_msg or f"Failed during {action}", details=str(details))

    return entry

def load_activities(start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load activity records with optional filtering.
    """
    target_file = ACTIVITY_FILE if ACTIVITY_FILE.exists() else USER_ACTIVITY_MIRROR
    if not target_file.exists():
        seed_history_from_logs()
        target_file = ACTIVITY_FILE if ACTIVITY_FILE.exists() else USER_ACTIVITY_MIRROR
        if not target_file.exists():
            return []

    records = []
    try:
        with open(target_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    rec_date = rec.get("date", rec.get("timestamp", "")[:10])
                    if start_date and rec_date < start_date:
                        continue
                    if end_date and rec_date > end_date:
                        continue
                    if category and rec.get("category") != category:
                        continue
                    records.append(rec)
                except Exception:
                    continue
    except Exception as e:
        mp_log_error("ActivityTracker", f"Failed reading {target_file}", e)

    return records

def seed_history_from_logs() -> int:
    """
    Parse historical logs like running_history.log and command sessions
    to populate activity telemetry when starting fresh.
    """
    if ACTIVITY_FILE.exists() and ACTIVITY_FILE.stat().st_size > 1024:
        return 0

    running_history = SCRIPT_DIR / "running_history.log"
    if not running_history.exists():
        return 0

    count = 0
    records = []
    # Regular expression for timestamp lines or snapshot markers
    date_re = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})')

    try:
        with open(running_history, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = date_re.search(line)
                if m:
                    d_str, t_str = m.group(1), m.group(2)
                    try:
                        dt = datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M:%S")
                        epoch = dt.timestamp()
                    except Exception:
                        continue

                    # Extract command or process note
                    action = "System Snapshot & Process Monitor"
                    category = "system_monitor"
                    if "Mix" in line or "mix" in line:
                        action = "Mix Archive Operation"
                        category = "mix_management"
                    elif "Audio" in line or "player" in line or "cliamp" in line:
                        action = "Audio Playback Session"
                        category = "playback"
                    elif "WAN2GP" in line or "flux" in line or "ltx" in line:
                        action = "WAN2GP AI Video Synthesis"
                        category = "ai_generation"

                    rec = {
                        "timestamp": dt.isoformat(),
                        "epoch": epoch,
                        "date": d_str,
                        "time": t_str,
                        "hour": dt.hour,
                        "action": action,
                        "category": category,
                        "duration_sec": 5.0,
                        "status": "success",
                        "details": {"source": "running_history.log", "raw": line.strip()[:80]},
                        "error_msg": None
                    }
                    records.append(rec)
                    count += 1
                    if count >= 300:  # Sample representative historical points
                        break

        if records:
            with open(ACTIVITY_FILE, "a", encoding="utf-8") as out:
                for r in records:
                    out.write(json.dumps(r) + "\n")
    except Exception as e:
        mp_log_error("ActivityTracker", "Error seeding history from running_history.log", e)

    return count

def get_activity_summary(period: str = "daily") -> Dict[str, Any]:
    """
    Generate an operations summary for the specified period ('daily', 'monthly', 'yearly').
    """
    today = date.today()
    if period == "daily":
        start_date = today.strftime("%Y-%m-%d")
        end_date = start_date
    elif period == "weekly":
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
    elif period == "monthly":
        start_date = today.strftime("%Y-%m-01")
        end_date = today.strftime("%Y-%m-%d")
    elif period == "yearly":
        start_date = today.strftime("%Y-01-01")
        end_date = today.strftime("%Y-%m-%d")
    else:
        start_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

    records = load_activities(start_date=start_date, end_date=end_date)
    
    # If today has very few records, include recent records to ensure meaningful stats
    if len(records) < 5 and period == "daily":
        records = load_activities()[-30:]

    total_ops = len(records)
    total_duration = sum(r.get("duration_sec", 0.0) for r in records)
    actions_count: Dict[str, int] = {}
    categories_count: Dict[str, int] = {}
    errors_count = 0
    hourly_distribution: Dict[int, int] = {h: 0 for h in range(24)}

    for r in records:
        act = r.get("action", "unknown")
        cat = r.get("category", "general")
        hr = r.get("hour", 0)
        actions_count[act] = actions_count.get(act, 0) + 1
        categories_count[cat] = categories_count.get(cat, 0) + 1
        hourly_distribution[hr] = hourly_distribution.get(hr, 0) + 1
        if r.get("status") == "error":
            errors_count += 1

    top_actions = sorted(actions_count.items(), key=lambda x: x[1], reverse=True)[:8]

    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "total_operations": total_ops,
        "total_duration_sec": round(total_duration, 2),
        "total_duration_formatted": f"{int(total_duration // 3600)}h {int((total_duration % 3600) // 60)}m {int(total_duration % 60)}s",
        "categories_breakdown": categories_count,
        "top_actions": top_actions,
        "errors_count": errors_count,
        "hourly_distribution": hourly_distribution,
        "records_sample": records[-10:] if records else []
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MP Mix Manager Activity Tracker")
    parser.add_argument("--record", nargs="+", help="Record activity: <action> <category> [duration] [details]")
    parser.add_argument("--summary", choices=["daily", "monthly", "yearly", "all"], default="daily", help="Get summary")
    parser.add_argument("--seed", action="store_true", help="Seed historical telemetry")
    args = parser.parse_args()

    if args.seed:
        c = seed_history_from_logs()
        print(f"Seeded {c} historical activity records.")
    elif args.record:
        action = args.record[0]
        cat = args.record[1] if len(args.record) > 1 else "general"
        dur = float(args.record[2]) if len(args.record) > 2 else 0.0
        det = {"cli": True, "raw": " ".join(args.record[3:])} if len(args.record) > 3 else {}
        rec = record_activity(action, category=cat, duration_sec=dur, details=det)
        print(f"Activity recorded: {rec['action']} [{rec['category']}] ({rec['duration_sec']}s)")
    else:
        summ = get_activity_summary(args.summary)
        print(f"--- MP Mix Archive Manager {summ['period'].upper()} Summary ---")
        print(f"Total Operations: {summ['total_operations']}")
        print(f"Total Duration:   {summ['total_duration_formatted']}")
        print(f"Categories:       {json.dumps(summ['categories_breakdown'])}")
        print(f"Errors Logged:    {summ['errors_count']}")
        print("Top Actions:")
        for act, cnt in summ['top_actions']:
            print(f"  • {act}: {cnt}")
