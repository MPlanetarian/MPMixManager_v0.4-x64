#!/usr/bin/env python3
"""MP Visualizer Idle Screensaver Daemon.

Watches the desktop for user inactivity and launches the MP Liquid Visualizer
in screensaver mode once the idle threshold is reached. It is deliberately
small and dependency-free so it can be started from the MP Mix Manager, a
.desktop autostart entry, or by hand.

Behaviour
---------
* Polls :func:`mp_liquid_visualizer_vulkan.idle_seconds` once every few seconds.
* When idle time reaches ``--idle`` seconds it launches the visualizer with
  ``--screensaver`` and waits for it to exit (any key or mouse press ends it).
* After the saver exits it waits ``--cooldown`` seconds before it can trigger
  again, so brushing the mouse does not immediately restart it.
* Stops cleanly on SIGTERM/SIGINT, and never leaves an orphaned visualizer.

Usage
-----
    mp_visualizer_idle_saver.py --idle 300 --dwell 45
    mp_visualizer_idle_saver.py --status
    mp_visualizer_idle_saver.py --stop
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "MP_Liquid_Visualizer.py").is_file():
    ROOT = Path(__file__).resolve().parent
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

CONFIG_DIR = Path.home() / ".config" / "mix-manager"
PID_FILE = CONFIG_DIR / "visualizer_idle_saver.pid"
STATE_FILE = CONFIG_DIR / "visualizer_idle_saver.json"
LOG_FILE = CONFIG_DIR / "liquid_visualizer.log"

DEFAULT_IDLE = 300.0      # 5 minutes
DEFAULT_DWELL = 45.0      # seconds per preset inside the saver
DEFAULT_COOLDOWN = 20.0   # seconds before the saver may trigger again
POLL = 2.0


def _visualizer_entry() -> Optional[Path]:
    for cand in (ROOT / "MP_Liquid_Visualizer.py", ROOT / "scripts" / "mp_liquid_visualizer_vulkan.py"):
        if cand.is_file():
            return cand
    return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _running_pid() -> Optional[int]:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if _pid_alive(pid) else None


def _write_state(state: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def stop_daemon() -> int:
    pid = _running_pid()
    if not pid:
        PID_FILE.unlink(missing_ok=True)
        _write_state({"running": False})
        print("MP Visualizer idle saver is not running.")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        print(f"Could not stop PID {pid}: {exc}", file=sys.stderr)
        return 1
    for _ in range(50):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    PID_FILE.unlink(missing_ok=True)
    _write_state({"running": False})
    print(f"Stopped MP Visualizer idle saver (PID {pid}).")
    return 0


def show_status() -> int:
    pid = _running_pid()
    state = read_state()
    if not pid:
        print("MP Visualizer idle saver: NOT RUNNING")
        prev = state.get("last_exit")
        if prev:
            print(f"  Last session ended: {prev}")
        return 0
    print(f"MP Visualizer idle saver: RUNNING (PID {pid})")
    print(f"  Idle threshold : {state.get('idle_threshold', '?')}s")
    print(f"  Preset dwell   : {state.get('dwell', '?')}s")
    print(f"  Launches so far: {state.get('launches', 0)}")
    idle = state.get("last_idle")
    if idle is not None:
        print(f"  Current idle   : {float(idle):.0f}s")
    return 0


def _launch_saver(dwell: float, preset: Optional[str], windowed: bool) -> subprocess.Popen:
    entry = _visualizer_entry()
    if entry is None:
        raise RuntimeError("MP_Liquid_Visualizer.py was not found")
    cmd = [sys.executable, str(entry), "--screensaver", "--saver-dwell", str(dwell)]
    if preset:
        cmd += ["--saver-preset", preset]
    if windowed:
        cmd.append("--saver-windowed")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_FILE, "a", encoding="utf-8")  # noqa: SIM115 - handed to the child
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True,
        )
    finally:
        log.close()
    return proc


def run(idle_threshold: float, dwell: float, cooldown: float,
        preset: Optional[str], windowed: bool) -> int:
    from mp_liquid_visualizer_vulkan import idle_seconds

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    state = {
        "running": True, "pid": os.getpid(),
        "idle_threshold": idle_threshold, "dwell": dwell,
        "launches": int(read_state().get("launches", 0)),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_state(state)
    stopping = {"flag": False}

    def _stop(_signum, _frame):
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    print(f"MP Visualizer idle saver started (PID {os.getpid()}).", flush=True)
    print(f"  Triggers after {idle_threshold:.0f}s idle, {dwell:.0f}s per preset.", flush=True)

    next_allowed = 0.0
    try:
        while not stopping["flag"]:
            idle = 0.0
            try:
                idle = float(idle_seconds())
            except Exception:
                idle = 0.0
            state["last_idle"] = round(idle, 1)
            _write_state(state)

            if idle >= idle_threshold and time.time() >= next_allowed:
                proc = None
                try:
                    proc = _launch_saver(dwell, preset, windowed)
                except Exception as exc:
                    print(f"[idle-saver] launch failed: {exc}", file=sys.stderr, flush=True)
                if proc is not None:
                    state["launches"] = int(state.get("launches", 0)) + 1
                    state["last_launch"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    _write_state(state)
                    print(f"[idle-saver] launched saver (PID {proc.pid})", flush=True)
                    while not stopping["flag"] and proc.poll() is None:
                        time.sleep(0.5)
                    if proc.poll() is None:
                        try:
                            proc.terminate()
                            proc.wait(timeout=5)
                        except Exception:
                            pass
                    # Give the desktop a moment to register the wake input.
                    next_allowed = time.time() + cooldown
                    print("[idle-saver] saver closed; cooling down.", flush=True)
            time.sleep(POLL)
    finally:
        state["running"] = False
        state["last_exit"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_state(state)
        PID_FILE.unlink(missing_ok=True)
    print("MP Visualizer idle saver stopped.", flush=True)
    return 0


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="mp_visualizer_idle_saver",
                                 description="Launch the MP Visualizer as a screensaver after a period of desktop inactivity.")
    ap.add_argument("--idle", type=float, default=DEFAULT_IDLE, help="Idle seconds before the saver starts (default: 300)")
    ap.add_argument("--dwell", type=float, default=DEFAULT_DWELL, help="Seconds per preset inside the saver (default: 45)")
    ap.add_argument("--cooldown", type=float, default=DEFAULT_COOLDOWN, help="Seconds before it may trigger again after closing (default: 20)")
    ap.add_argument("--preset", type=str, default=None, help="Lock the saver to a single preset instead of cycling")
    ap.add_argument("--windowed", action="store_true", help="Run the saver in a window instead of fullscreen")
    ap.add_argument("--stop", action="store_true", help="Stop a running idle saver and exit")
    ap.add_argument("--status", action="store_true", help="Report whether the idle saver is running")
    args = ap.parse_args(argv)

    if args.stop:
        return stop_daemon()
    if args.status:
        return show_status()
    if _running_pid():
        print("MP Visualizer idle saver is already running. Use --stop first.", file=sys.stderr)
        return 1
    return run(max(5.0, args.idle), max(0.0, args.dwell), max(0.0, args.cooldown), args.preset, args.windowed)


if __name__ == "__main__":
    raise SystemExit(main())
