#!/usr/bin/env python3
"""Keep MP Gui and MP Liquid Player to four live instances at a time.

Every launch path asks this module before a window is created: the desktop
shortcuts, the global shortcut keys, the shared tray icon, the player menu,
VR Mode, and the Liquid Glass hosts themselves. A claim file per live process
makes the count atomic, so two launches that arrive together cannot both take
the last slot.

Only MP Gui (a --manager host) and MP Liquid Player are capped. The tracklist
viewer, the MP Liquid Visualizer, and the console manager are not.

Exit codes for the command line: 0 allowed / claimed, 3 at the limit,
2 bad usage. Launchers use 3 to focus the window that is already open.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

MAX_INSTANCES = 4

ROLE_GUI = "gui"
ROLE_PLAYER = "player"
ROLES = (ROLE_GUI, ROLE_PLAYER)
ROLE_LABELS = {
    ROLE_GUI: "MP Gui",
    ROLE_PLAYER: "MP Liquid Player",
}
FOCUS_TITLES = {
    ROLE_GUI: "MP Mix Manager (Liquid Glass",
    ROLE_PLAYER: "MP Audio Player (Liquid Glass",
}

# Liquid Glass hosts. All four draw either the player or the MP Gui window.
HOST_SCRIPTS = (
    "MP_Audio_Player_Liquid_Glass.py",
    "MP_Audio_Player_Liquid_Glass_OpenGL.py",
    "MP_Audio_Player_Liquid_Glass_macOS.py",
    "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
)

# A launcher claims a slot before it execs the host. A claim that outlives its
# launch window is stale even while the pid is alive (the pid may be recycled).
CLAIM_GRACE_SECONDS = 120.0
LOCK_STALE_SECONDS = 10.0
LOCK_WAIT_SECONDS = 3.0


def config_dir() -> Path:
    override = os.environ.get("MP_INSTANCE_CONFIG_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".config" / "mix-manager"


def state_dir() -> Path:
    path = Path(os.environ.get("MP_INSTANCE_STATE_DIR", "") or (config_dir() / "instances"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def limit_message(role: str) -> str:
    label = ROLE_LABELS.get(role, "MP instance")
    return (
        f"{label} is already open {MAX_INSTANCES} times. "
        f"Close one window before opening another ({MAX_INSTANCES} is the maximum)."
    )


def _command_tokens(cmdline: str) -> list[str]:
    return cmdline.replace("\x00", " ").split()


def role_from_cmdline(cmdline: str) -> str | None:
    """Return the capped role this command line draws, or None."""
    if not cmdline:
        return None
    lowered = cmdline.lower()
    if "mp_instance_limit" in lowered:
        return None
    # pgrep / pkill / grep lines only mention the host name as a pattern.
    if any(mark in lowered for mark in ("pgrep", "pkill", "grep ")):
        return None
    tokens = _command_tokens(cmdline)
    if any(tok in ("--self-test", "--list-fonts", "--embed-check") for tok in tokens):
        return None
    if any(tok.startswith("--set-font") for tok in tokens):
        return None
    if any(tok == "--tracklist" or tok.startswith("--tracklist=") for tok in tokens):
        return None
    host = None
    for token in tokens:
        if Path(token.strip("'\"")).name in HOST_SCRIPTS:
            host = token
            break
    if host is None:
        return None
    if "--manager" in tokens:
        return ROLE_GUI
    return ROLE_PLAYER


def _proc_table_from_proc() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if not raw:
            continue
        found.append((int(entry.name), raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()))
    return found


def _proc_table_from_ps() -> list[tuple[int, str]]:
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    found: list[tuple[int, str]] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        found.append((int(parts[0]), parts[1]))
    return found


def _proc_table_from_windows() -> list[tuple[int, str]]:
    script = (
        "Get-CimInstance Win32_Process | "
        "ForEach-Object { \"$($_.ProcessId) $($_.CommandLine)\" }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    found: list[tuple[int, str]] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        found.append((int(parts[0]), parts[1]))
    return found


def process_table() -> list[tuple[int, str]]:
    try:
        if sys.platform == "win32":
            return _proc_table_from_windows()
        found = _proc_table_from_proc()
        if found:
            return found
        return _proc_table_from_ps()
    except Exception:
        # Counting must never keep a window from opening. An unreadable
        # process table reports no live hosts.
        return []


def role_pids(role: str, table: list[tuple[int, str]] | None = None) -> set[int]:
    pids: set[int] = set()
    for pid, cmdline in table if table is not None else process_table():
        if role_from_cmdline(cmdline) == role:
            pids.add(pid)
    return pids


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:
        return False
    return True


def _role_state_dir(role: str) -> Path:
    path = state_dir() / role
    path.mkdir(parents=True, exist_ok=True)
    return path


def _claim_file(role: str, pid: int) -> Path:
    return _role_state_dir(role) / f"{int(pid)}.claim"


@contextmanager
def _state_lock(role: str):
    """Atomic mkdir lock, portable to Windows and avoidable stale locks."""
    lock = state_dir() / f"{role}.lock"
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            os.mkdir(lock)
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0.0
            if age > LOCK_STALE_SECONDS:
                try:
                    os.rmdir(lock)
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"instance lock is busy: {lock}")
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            os.rmdir(lock)
        except OSError:
            pass


def _live_claims(role: str, hosts: set[int]) -> set[int]:
    claims: set[int] = set()
    now = time.time()
    for path in _role_state_dir(role).glob("*.claim"):
        try:
            pid = int(path.stem)
        except ValueError:
            continue
        if not _pid_alive(pid):
            try:
                path.unlink()
            except OSError:
                pass
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            age = 0.0
        if pid in hosts or age <= CLAIM_GRACE_SECONDS:
            claims.add(pid)
        else:
            try:
                path.unlink()
            except OSError:
                pass
    return claims


def instance_count(role: str, exclude_pid: int | None = None) -> int:
    """Live hosts plus pending launch claims, counted once per process."""
    hosts = role_pids(role)
    if exclude_pid:
        hosts.discard(int(exclude_pid))
    try:
        with _state_lock(role):
            claims = _live_claims(role, hosts)
    except (TimeoutError, OSError):
        claims = set()
    return len(hosts | claims)


def at_limit(role: str, exclude_pid: int | None = None) -> bool:
    return instance_count(role, exclude_pid) >= MAX_INSTANCES


def claim_instance(role: str, pid: int | None = None) -> bool:
    """Reserve one of the four slots for pid. False when all four are taken."""
    pid = int(pid or os.getpid())
    try:
        with _state_lock(role):
            hosts = role_pids(role)
            # The caller may already look like a host (a Liquid Glass process
            # claiming for itself). It must not count against its own slot.
            hosts.discard(pid)
            claims = _live_claims(role, hosts)
            if pid in claims:
                return True
            if len(hosts | claims) >= MAX_INSTANCES:
                return False
            _claim_file(role, pid).write_text(f"{pid}\n", encoding="utf-8")
            return True
    except (TimeoutError, OSError):
        # Never let a broken lock file stop the app. Fall back to a plain count.
        return instance_count(role, exclude_pid=pid) < MAX_INSTANCES


def release_instance(role: str, pid: int | None = None) -> None:
    pid = int(pid or os.getpid())
    try:
        _claim_file(role, pid).unlink()
    except OSError:
        pass


def guard_process(role: str) -> bool:
    """Claim a slot for this process and release it at exit.

    The Liquid Glass hosts call this before they open a window, so a launch
    that skipped every wrapper still cannot become a fifth instance.
    """
    pid = os.getpid()
    if not claim_instance(role, pid):
        return False
    atexit.register(release_instance, role, pid)
    return True


def guard_launch(role: str) -> bool:
    """Reserve a slot for the window this launcher is about to exec.

    The claim belongs to the launcher pid, which exec keeps in place. When the
    launcher cannot be kept (a .bat that starts a detached process), the host
    claims for itself through guard_process.
    """
    return claim_instance(role, os.getpid())


def host_role(role: str) -> str:
    """The role a Liquid Glass host should count as, or "" when it is exempt."""
    return role if role in ROLES else ""


def host_allowed(role: str) -> bool:
    """Claim a slot for a Liquid Glass host. True when the window may open.

    The four host scripts call this before they draw anything, so a launch
    that skipped every launcher still cannot become a fifth window.
    """
    counted = host_role(role)
    if not counted:
        return True
    return guard_process(counted)


def focus_existing(role: str) -> bool:
    """Bring an already-open window of this role forward."""
    title = FOCUS_TITLES.get(role)
    if not title:
        return False
    if sys.platform == "win32":
        return _focus_windows_window(title)
    if sys.platform.startswith(("linux", "freebsd")):
        wmctrl = shutil.which("wmctrl")
        if not wmctrl:
            return False
        try:
            result = subprocess.run(
                [wmctrl, "-a", title],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    if sys.platform == "darwin":
        script = (
            'tell application "System Events"\n'
            "  repeat with proc in processes\n"
            "    try\n"
            "      repeat with w in windows of proc\n"
            f'        if name of w contains "{title}" then\n'
            "          set frontmost of proc to true\n"
            '          perform action "AXRaise" of w\n'
            "          return\n"
            "        end if\n"
            "      end repeat\n"
            "    end try\n"
            "  end repeat\n"
            "end tell\n"
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False
    return False


def _focus_windows_window(title: str) -> bool:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value.startswith(title):
            found.append(int(hwnd))
            return False
        return True

    try:
        user32.EnumWindows(_callback, 0)
        if not found:
            return False
        hwnd = found[0]
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        user32.ShowWindow(hwnd, 5)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def notify_limit(role: str, message: str | None = None) -> None:
    label = ROLE_LABELS.get(role, "MP Mix Manager")
    text = message or limit_message(role)
    print(text, file=sys.stderr)
    if sys.platform.startswith(("linux", "freebsd")):
        sender = shutil.which("notify-send")
        if sender:
            try:
                subprocess.run(
                    [sender, "-a", "MP Mix Manager", "-i", "dialog-warning", label, text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                pass
    elif sys.platform == "darwin":
        script = f'display notification "{text}" with title "{label}"'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass


def status() -> dict[str, dict[str, int]]:
    return {
        role: {"running": instance_count(role), "maximum": MAX_INSTANCES}
        for role in ROLES
    }


def _role_list(role: str) -> list[str]:
    return list(ROLES) if role == "all" else [role]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mp_instance_limit.py",
        description=f"Cap MP Gui and MP Liquid Player at {MAX_INSTANCES} instances.",
    )
    parser.add_argument(
        "command",
        choices=("status", "count", "check", "claim", "release", "notify", "focus"),
    )
    parser.add_argument("role", nargs="?", default="all", choices=(*ROLES, "all"))
    parser.add_argument("--pid", type=int, default=None)
    args = parser.parse_args(argv)

    if args.command == "status":
        print(json.dumps(status(), indent=2))
        return 0

    if args.command == "count":
        if args.role == "all":
            print(json.dumps({role: instance_count(role) for role in ROLES}))
        else:
            print(instance_count(args.role))
        return 0

    if args.command == "check":
        blocked = any(at_limit(role) for role in _role_list(args.role))
        return 3 if blocked else 0

    if args.command == "claim":
        if not claim_instance(args.role, args.pid):
            return 3
        return 0

    if args.command == "release":
        for role in _role_list(args.role):
            release_instance(role, args.pid)
        return 0

    if args.command == "notify":
        for role in _role_list(args.role):
            notify_limit(role)
        return 0

    if args.command == "focus":
        focused = False
        for role in _role_list(args.role):
            focused = focus_existing(role) or focused
        return 0 if focused else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
