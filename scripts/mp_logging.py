#!/usr/bin/env python3
"""
mp_logging.py - Centralized Error and Event Logging for MP Mix Archive Manager
Part of MP_Mix_Manager_v0.3
Logs errors cleanly to MP_Error.log with timestamp, caller context, and stack traces.
"""

import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Resolve base directories
SCRIPT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Primary MP_Error.log paths
PRIMARY_ERROR_LOG = SCRIPT_DIR / "MP_Error.log"
BACKUP_ERROR_LOG = CONFIG_DIR / "MP_Error.log"

def get_error_log_path() -> Path:
    """Return writable path for MP_Error.log."""
    try:
        PRIMARY_ERROR_LOG.touch(exist_ok=True)
        return PRIMARY_ERROR_LOG
    except (PermissionError, OSError):
        BACKUP_ERROR_LOG.touch(exist_ok=True)
        return BACKUP_ERROR_LOG

def log_error(component: str, message: str, exc: Exception = None, details: str = None) -> None:
    """Log an error entry to MP_Error.log."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = get_error_log_path()
    
    lines = [
        f"[{now_str}] [ERROR] [{component}] {message}"
    ]
    if details:
        lines.append(f"  Details: {details}")
    if exc is not None:
        lines.append(f"  Exception: {type(exc).__name__}: {exc}")
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        lines.append(f"  Traceback:\n{tb.rstrip()}")
    lines.append("-" * 70)
    
    entry = "\n".join(lines) + "\n"
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        sys.stderr.write(f"Failed writing to {log_path}: {e}\n{entry}")

def log_warning(component: str, message: str) -> None:
    """Log a warning entry to MP_Error.log."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = get_error_log_path()
    entry = f"[{now_str}] [WARNING] [{component}] {message}\n"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def get_recent_errors(limit: int = 25) -> list[str]:
    """Retrieve the most recent error entries from MP_Error.log."""
    log_path = get_error_log_path()
    if not log_path.exists():
        return []
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        entries = content.strip().split("-" * 70)
        recent = [e.strip() for e in entries if e.strip()]
        return recent[-limit:]
    except Exception:
        return []

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--tail":
        errs = get_recent_errors(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
        if not errs:
            print("No errors logged in MP_Error.log.")
        else:
            for e in errs:
                print(e)
                print("-" * 70)
    elif len(sys.argv) > 2 and sys.argv[1] == "--log":
        comp = sys.argv[2]
        msg = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "Unknown error"
        log_error(comp, msg)
        print(f"Logged error to {get_error_log_path()}")
    else:
        print(f"MP_Error.log location: {get_error_log_path()}")
