#!/usr/bin/env python3
"""Start, stop, and query the MP Web Companion from the shared tray icon.

The tray menu offers a single **Start / Stop MP Web Audio** entry whose label
follows the service state: it reads *Stop* while the companion is serving and
*Start* while it is not.

Only Linux is wired up for now. The platform dispatch in :func:`toggle_companion`
is written as an explicit case-style table so adding macOS/Windows later means
adding one branch, not touching the menu code.

Restart notifications reach phones through the companion itself:

* Before a stop, the tray POSTs ``/api/announce`` so every dashboard still
  connected shows the message immediately.
* Every server launch gets a fresh instance id, reported by ``/api/status``.
  A dashboard that sees the id change knows the companion came back and
  auto-refreshes so the phone resumes the stream without a manual reload.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

MENU_START = "Start MP Web Audio"
MENU_STOP = "Stop MP Web Audio"

ANNOUNCE_PATH = "/api/announce"
ANNOUNCE_MESSAGE = "MP Audio Web Companion has been restarted"
# Give connected dashboards one poll cycle to pick the notice up before the
# service disappears.
ANNOUNCE_SETTLE_SECONDS = 2.2

_SERVICE_NAME = "mp-web-companion.service"
_SCRIPT_NAME = "mix_web_companion.py"


def scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def base_dir() -> Path:
    here = scripts_dir()
    return here.parent if here.name == "scripts" else here


def service_script() -> Optional[Path]:
    """The wrapper that owns start/stop/status for the companion."""
    for candidate in (scripts_dir() / "mix_web_companion.sh", base_dir() / "mix_web_companion.sh"):
        if candidate.is_file():
            return candidate
    return None


def _run(argv: list[str], timeout: float = 25.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        check=False,
    )


# ------------------------------------------------------------------------------
# STATE
# ------------------------------------------------------------------------------
def _systemd_active(unit: str) -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        result = _run(["systemctl", "--user", "is-active", "--quiet", unit], timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _pids() -> list[int]:
    if not shutil.which("pgrep"):
        return []
    try:
        result = _run(["pgrep", "-f", _SCRIPT_NAME], timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return []
    found = []
    for line in result.stdout.split():
        try:
            pid = int(line)
        except ValueError:
            continue
        if pid != os.getpid():
            found.append(pid)
    return found


def companion_running() -> bool:
    """True while the dashboard is being served on this machine."""
    if _systemd_active(_SERVICE_NAME):
        return True
    return bool(_pids())


def menu_label() -> str:
    """The label the tray should show right now."""
    return MENU_STOP if companion_running() else MENU_START


def target_port() -> int:
    override = os.environ.get("WEB_COMPANION_PORT", "").strip()
    if override.isdigit():
        return int(override)
    return 8888


# ------------------------------------------------------------------------------
# ANNOUNCE
# ------------------------------------------------------------------------------
def announce(message: str = ANNOUNCE_MESSAGE, port: Optional[int] = None) -> bool:
    """Push a notice to every connected dashboard. Best effort only."""
    url = f"http://127.0.0.1:{port or target_port()}{ANNOUNCE_PATH}"
    payload = json.dumps({"message": message}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


# ------------------------------------------------------------------------------
# START / STOP
# ------------------------------------------------------------------------------
def _via_script(action: str) -> bool:
    script = service_script()
    if script is None:
        return False
    try:
        result = _run(["bash", str(script), action])
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def start_companion() -> bool:
    """Start the service and wait until it answers."""
    if companion_running():
        return True
    _via_script("start")
    deadline = time.time() + 12
    while time.time() < deadline:
        if companion_running():
            return True
        time.sleep(0.25)
    return companion_running()


def stop_companion() -> bool:
    """Stop the service, after telling any connected dashboard what happened."""
    if not companion_running():
        return True
    announce()
    # Let the poll-based dashboards render the notice before the port closes.
    time.sleep(ANNOUNCE_SETTLE_SECONDS)
    _via_script("stop")
    deadline = time.time() + 12
    while time.time() < deadline:
        if not companion_running():
            return True
        time.sleep(0.25)
    return not companion_running()


def restart_companion() -> bool:
    """Stop then start, so the new instance id refreshes every dashboard."""
    stop_companion()
    return start_companion()


# ------------------------------------------------------------------------------
# PLATFORM DISPATCH (case statement)
# ------------------------------------------------------------------------------
def _toggle_linux() -> Optional[bool]:
    """Current state, toggled. Returns the new running state or None on error."""
    if companion_running():
        return False if stop_companion() else True
    return True if start_companion() else False


# One branch per platform, like a shell `case "$(uname -s)" in ... esac`.
# Values are attribute names, not bound functions, so the dispatch resolves at
# call time. That keeps the table patchable and mirrors how a shell case
# statement re-reads the current state on each entry.
_TOGGLE_CASES = {
    "Linux": "_toggle_linux",
}


def _resolve_case(platform_name: str) -> Optional[str]:
    """Return the handler attribute name for a platform, or None."""
    handler = _TOGGLE_CASES.get(platform_name)
    if handler and callable(globals().get(handler)):
        return handler
    return None


def toggle_companion(platform_name: Optional[str] = None) -> dict:
    """Flip the companion on or off.

    Returns a payload the tray (and tests) can act on, e.g.
    ``{"supported": True, "running": False, "action": "stop"}``.
    """
    if platform_name is None:
        platform_name = _platform_case_name()
    handler_name = _resolve_case(platform_name)
    if handler_name is None:
        return {
            "supported": False,
            "action": "unsupported",
            "platform": platform_name,
            "running": companion_running(),
        }
    was_running = companion_running()
    running = globals()[handler_name]()
    if running is None:
        return {
            "supported": True,
            "action": "error",
            "platform": platform_name,
            "running": was_running,
        }
    return {
        "supported": True,
        "action": "stop" if was_running else "start",
        "platform": platform_name,
        "running": running,
        "success": running == (not was_running),
        "label": MENU_STOP if running else MENU_START,
    }


def _platform_case_name() -> str:
    """Map ``uname -s`` to the names used in the case table."""
    if sys.platform.startswith("linux"):
        return "Linux"
    if sys.platform == "darwin":
        return "Darwin"
    return "Windows" if os.name == "nt" else sys.platform
