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


def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
    except OSError:
        return ""


def _ppid(pid: int) -> int:
    try:
        text = Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    for line in text.splitlines():
        if line.startswith("PPid:"):
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                return int(parts[1])
    return 0


def _is_descendant(pid: int, ancestor: int) -> bool:
    seen: set[int] = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        parent = _ppid(pid)
        if parent == ancestor:
            return True
        pid = parent
    return False


def visualizer_pids() -> list[int]:
    return _pgrep(_VISUALIZER_MARK)


def other_liquid_player_running() -> bool:
    """True when another Liquid Glass host window is still open.

    A shell launcher whose command line contains the player script, and this
    process's own parent, are not another window. Counting those used to skip
    the visualizer shutdown.
    """
    me = os.getpid()
    parent = os.getppid()
    for pid in _pgrep(_PLAYER_MARK):
        if pid in (me, parent) or pid <= 1:
            continue
        cmd = _cmdline(pid).lower()
        if "pgrep" in cmd or "pkill" in cmd:
            continue
        if "mp_audio_player_liquid_glass" not in cmd:
            continue
        if _is_descendant(pid, me):
            continue
        return True
    return False


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
        pgid = os.getpgid(pid)
    except OSError:
        return
    try:
        # Signal the visualizer's own group only when it is the leader.
        # killpg(pid) fails when the process is not a group leader, and
        # killpg of a shared shell group would stop the player too.
        if pgid == pid and pgid != os.getpgrp():
            os.killpg(pgid, sig)
        else:
            os.kill(pid, sig)
    except OSError:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def stop_companion_visualizer(force: bool = False) -> None:
    """Close visualizer windows opened for this Liquid Glass window.

    Leave the window up when another Liquid Glass host is still open,
    unless force is set (the Mix Manager GUI always closes it).
    """
    if not force and other_liquid_player_running():
        return
    pids = visualizer_pids()
    if not pids:
        return
    for pid in pids:
        _signal_visualizer(pid, signal.SIGTERM)
    deadline = time.monotonic() + 0.6
    while time.monotonic() < deadline:
        if not any(_alive(pid) for pid in pids):
            return
        time.sleep(0.05)
    for pid in pids:
        if _alive(pid):
            _signal_visualizer(pid, signal.SIGKILL)


def _playback_engine_pids() -> list[int]:
    """MP Audio Player engines. Liquid Glass host windows are not engines."""
    me = os.getpid()
    found: list[int] = []
    for pid in _pgrep("MP_Audio_Player.py"):
        if pid == me or pid <= 1:
            continue
        cmd = _cmdline(pid)
        if "Liquid_Glass" in cmd or "liquid_glass" in cmd:
            continue
        if "MP_Audio_Player.py" not in cmd and "mp_audio_player.py" not in cmd.lower():
            continue
        found.append(pid)
    return found


def _send_player_stop() -> None:
    """Ask a running player daemon to stop before its process is signalled."""
    config = Path.home() / ".config" / "mix-manager"
    sock_path = config / "mp_audio_player.sock"
    port_path = config / "mp_audio_player.port"
    try:
        import socket
        if sock_path.is_socket() or sock_path.exists():
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(0.4)
                sock.connect(str(sock_path))
                sock.sendall(b'{"cmd":"stop"}')
                try:
                    sock.recv(256)
                except OSError:
                    pass
                sock.close()
                return
            except OSError:
                pass
        port = 0
        try:
            port = int(port_path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            port = 0
        if port > 0:
            sock = socket.create_connection(("127.0.0.1", port), 0.4)
            sock.settimeout(0.4)
            sock.sendall(b'{"cmd":"stop"}')
            try:
                sock.recv(256)
            except OSError:
                pass
            sock.close()
    except OSError:
        pass


def stop_companion_playback() -> None:
    """Stop music started from the Mix Manager GUI. The glass host stays up."""
    _send_player_stop()
    pids = _playback_engine_pids()
    for pid in pids:
        _signal_visualizer(pid, signal.SIGTERM)
    deadline = time.monotonic() + 0.45
    while time.monotonic() < deadline:
        if not any(_alive(pid) for pid in pids):
            return
        time.sleep(0.05)
    for pid in pids:
        if _alive(pid):
            _signal_visualizer(pid, signal.SIGKILL)
