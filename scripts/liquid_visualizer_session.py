"""Close the MP Liquid Visualizer when the Liquid Player window exits.

The visualizer is a separate process. Launchers start it with nohup, and the
player starts it in a new session, so closing the player used to leave the
1400x1400 window on screen.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

_VISUALIZER_MARK = "MP_Liquid_Visualizer|mp_liquid_visualizer_vulkan"
_PLAYER_MARK = "MP_Audio_Player_Liquid_Glass"


def _pgrep(pattern: str) -> list[int]:
    me = os.getpid()
    found: list[int] = []
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-Command",
                 f'Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like "*{pattern.split("|")[0]}*" -or $_.CommandLine -like "*{pattern.split("|")[-1]}*" }} | Select-Object -ExpandProperty ProcessId'],
                stderr=subprocess.DEVNULL, text=True, timeout=4,
            )
        except (OSError, subprocess.SubprocessError):
            return found
        for line in out.split():
            if line.isdigit() and int(line) != me:
                found.append(int(line))
        return found
    if shutil.which("pgrep"):
        try:
            res = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.SubprocessError):
            return found
        for line in (res.stdout or "").split():
            if line.isdigit() and int(line) != me:
                found.append(int(line))
        return found
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    needles = pattern.split("|")
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except OSError:
            continue
        if any(needle in cmd for needle in needles):
            found.append(int(entry.name))
    return found


def visualizer_pids() -> list[int]:
    return _pgrep(_VISUALIZER_MARK)


def other_liquid_player_running() -> bool:
    """True when another Liquid Player window is still open."""
    return bool(_pgrep(_PLAYER_MARK))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _signal_visualizer(pid: int, sig: int) -> None:
    if pid <= 1 or pid == os.getpid():
        return
    if sys.platform == "win32":
        if sig != signal.SIGKILL and sig != signal.SIGTERM:
            return
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    try:
        same_group = os.getpgid(pid) == os.getpgrp()
    except OSError:
        return
    try:
        # A new session can be signalled as a group. The same group as the
        # player must be signalled by pid only, or the player would be hit too.
        if same_group:
            os.kill(pid, sig)
        else:
            os.killpg(pid, sig)
    except OSError:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def stop_companion_visualizer() -> None:
    """Close visualizer windows opened for this Liquid Player.

    Leave the window up when another Liquid Player is still open.
    """
    if other_liquid_player_running():
        return
    pids = visualizer_pids()
    if not pids:
        return
    for pid in pids:
        _signal_visualizer(pid, signal.SIGTERM)
    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        if not any(_alive(pid) for pid in pids):
            return
        time.sleep(0.05)
    for pid in pids:
        if _alive(pid):
            _signal_visualizer(pid, signal.SIGKILL)
