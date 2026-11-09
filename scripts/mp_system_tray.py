#!/usr/bin/env python3
"""One system tray icon shared by MP Mix Manager, MP Gui, and MP Liquid Player.

Right-click the icon to launch any of the three, or to close the console
manager and everything that belongs to it (the GUI, the Liquid Player,
playback, and the visualizer). The icon stays while at least one of the
three is open. A second launch focuses the window that is already open.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROLE_MANAGER = "manager"
ROLE_GUI = "gui"
ROLE_LIQUID = "liquid"

MENU_LAUNCH_GUI = "Launch MP Gui"
MENU_LAUNCH_LIQUID = "Launch MP Liquid Player"
MENU_LAUNCH_MANAGER = "Launch MP Mix Manager"
MENU_CLOSE_ALL = "Close MP Mix Manager (Closes everything)"

MENU_ENTRIES = (
    ("launch-gui", MENU_LAUNCH_GUI),
    ("launch-liquid", MENU_LAUNCH_LIQUID),
    ("launch-manager", MENU_LAUNCH_MANAGER),
    ("close-all", MENU_CLOSE_ALL),
)

FOCUS_TITLES = {
    ROLE_GUI: "MP Mix Manager (Liquid Glass",
    ROLE_LIQUID: "MP Audio Player (Liquid Glass",
    ROLE_MANAGER: "MP Mix Archive Manager",
}

CLOSE_WINDOW_TITLES = (
    "MP Mix Archive Manager",
    "MP Mix Manager (Liquid Glass",
    "MP Audio Player (Liquid Glass",
)

LIQUID_HOSTS = (
    "MP_Audio_Player_Liquid_Glass.py",
    "MP_Audio_Player_Liquid_Glass_OpenGL.py",
    "MP_Audio_Player_Liquid_Glass_macOS.py",
    "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
)

ABSENT_QUIT_SECONDS = 8
LAUNCH_GRACE_SECONDS = 20

_WRAPPERS = {"setsid", "nohup", "nice", "stdbuf", "timeout"}
_INTERPRETERS = {"bash", "sh", "dash", "python", "python3"}


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int
    cmdline: str
    environ: str = ""


class TrayLock:
    """One tray process. The lock file stays open for the life of the holder."""

    def __init__(self, path: Path):
        self.path = path
        self._fd = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            return self._acquire_windows()
        return self._acquire_posix()

    def _acquire_posix(self) -> bool:
        import fcntl

        fd = open(self.path, "a+")
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fd.close()
            return False
        fd.seek(0)
        fd.truncate()
        fd.write(str(os.getpid()))
        fd.flush()
        self._fd = fd
        return True

    def _acquire_windows(self) -> bool:
        import msvcrt

        # msvcrt locks a byte range, so the file has to contain that byte.
        if not self.path.exists() or self.path.stat().st_size < 1:
            self.path.write_bytes(b" " * 32)
        fd = open(self.path, "r+b")
        fd.seek(0)
        try:
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            fd.close()
            return False
        payload = str(os.getpid()).encode("ascii", "replace")[:31].ljust(32, b" ")
        fd.seek(0)
        fd.write(payload)
        fd.flush()
        self._fd = fd
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        if os.name == "nt":
            self._release_windows()
            return
        import fcntl

        try:
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
        finally:
            self._fd.close()
            self._fd = None

    def _release_windows(self) -> None:
        import msvcrt

        fd = self._fd
        self._fd = None
        try:
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            fd.close()

    @staticmethod
    def held(path: Path) -> bool:
        if not path.exists():
            return False
        if os.name == "nt":
            return TrayLock._held_windows(path)
        import fcntl

        fd = open(path, "a+")
        try:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            return False
        finally:
            fd.close()

    @staticmethod
    def _held_windows(path: Path) -> bool:
        import msvcrt

        if path.stat().st_size < 1:
            return False
        fd = open(path, "r+b")
        try:
            fd.seek(0)
            try:
                msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            try:
                fd.seek(0)
                msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            return False
        finally:
            fd.close()


def default_base_dir() -> Path:
    here = Path(__file__).resolve().parent
    base = here.parent
    if (base / "Mix_Archive_Manager.sh").is_file():
        return base
    if (here / "Mix_Archive_Manager.sh").is_file():
        return here
    return base


def config_dir() -> Path:
    override = os.environ.get("MP_TRAY_CONFIG_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".config" / "mix-manager"


def icon_file(base: Path) -> Path:
    png = base / "assets" / "mp_liquid_glass_icon.png"
    if png.is_file():
        return png
    return base / "assets" / "MP_Mix_Manager_Windows_Icon.ico"


def command_argv(cmdline: str) -> list[str]:
    """Drop setsid, nohup, and env so the real program is argv[0]."""
    parts = cmdline.split()
    index = 0
    while index < len(parts):
        name = Path(parts[index]).name
        if name in _WRAPPERS:
            index += 1
            while index < len(parts) and parts[index].startswith("-"):
                flag = parts[index]
                index += 1
                if flag in {"-n", "-p", "-o", "-s"} and index < len(parts):
                    index += 1
            continue
        if name == "env":
            index += 1
            while index < len(parts):
                token = parts[index]
                if token in {"-u", "--unset"}:
                    index += 2
                    continue
                if token.startswith("-u") and token != "-u":
                    index += 1
                    continue
                if token.startswith("-"):
                    index += 1
                    continue
                if "=" in token and not token.startswith("/"):
                    index += 1
                    continue
                break
            continue
        break
    return parts[index:]


def _basename_is(arg: str, script_name: str) -> bool:
    token = arg.strip("'\"")
    if not token or token.startswith("-") or any(ch.isspace() for ch in token):
        return False
    return Path(token).name == script_name


def invoked_script(cmdline: str, script_name: str) -> bool:
    argv = command_argv(cmdline)
    if not argv:
        return False
    if _basename_is(argv[0], script_name):
        return True
    exe = Path(argv[0]).name
    if exe in _INTERPRETERS or exe.startswith("python"):
        for arg in argv[1:]:
            if arg.startswith("-"):
                continue
            return _basename_is(arg, script_name)
    return False


def _hosted_by_gui(proc: ProcessInfo, by_pid: dict[int, ProcessInfo]) -> bool:
    # The GUI runs Mix_Archive_Manager.sh inside its own window. That shell
    # is not the console manager, even when its environment cannot be read.
    if "MP_GUI_SESSION=1" in proc.environ.split("\n"):
        return True
    seen: set[int] = set()
    current = proc.ppid
    while current > 1 and current not in seen:
        seen.add(current)
        parent = by_pid.get(current)
        if parent is None:
            return False
        for name in LIQUID_HOSTS:
            if invoked_script(parent.cmdline, name) and "--manager" in command_argv(parent.cmdline):
                return True
        current = parent.ppid
    return False


def _dedicated_manager_konsole(cmdline: str) -> bool:
    argv = command_argv(cmdline)
    if not argv or Path(argv[0]).name != "konsole":
        return False
    return "mix-archive-manager" in cmdline or "Mix_Archive_Manager.sh" in cmdline


def classify_process(
    proc: ProcessInfo,
    by_pid: dict[int, ProcessInfo] | None = None,
    self_pids: set[int] | None = None,
) -> str | None:
    if self_pids and proc.pid in self_pids:
        return None
    if "mp_system_tray" in proc.cmdline:
        return None
    parents = by_pid or {}
    for name in LIQUID_HOSTS:
        if invoked_script(proc.cmdline, name):
            if "--manager" in command_argv(proc.cmdline):
                return ROLE_GUI
            return ROLE_LIQUID
    if invoked_script(proc.cmdline, "MP_Gui.sh"):
        return ROLE_GUI
    if invoked_script(proc.cmdline, "launch-liquid-glass") or invoked_script(proc.cmdline, "launch_liquid_glass.sh"):
        return ROLE_LIQUID
    if (
        invoked_script(proc.cmdline, "Mix_Archive_Manager.sh")
        or invoked_script(proc.cmdline, "mix-archive-manager")
        or invoked_script(proc.cmdline, "launch-manager")
    ):
        if _hosted_by_gui(proc, parents):
            return None
        return ROLE_MANAGER
    if _dedicated_manager_konsole(proc.cmdline):
        return ROLE_MANAGER
    return None


def index_processes(processes: list[ProcessInfo]) -> dict[int, ProcessInfo]:
    return {proc.pid: proc for proc in processes}


def roles_present(
    processes: list[ProcessInfo],
    self_pids: set[int] | None = None,
) -> set[str]:
    by_pid = index_processes(processes)
    found: set[str] = set()
    for proc in processes:
        role = classify_process(proc, by_pid, self_pids)
        if role:
            found.add(role)
    return found


def manager_pids(
    processes: list[ProcessInfo],
    self_pids: set[int] | None = None,
) -> list[int]:
    by_pid = index_processes(processes)
    found = []
    for proc in processes:
        if classify_process(proc, by_pid, self_pids) == ROLE_MANAGER:
            found.append(proc.pid)
    return found


def launch_plan(role: str, base: Path, running: set[str]) -> dict[str, object]:
    title = FOCUS_TITLES[role]
    if role in running:
        return {"action": "focus", "title": title, "argv": []}
    if role == ROLE_GUI:
        argv = ["bash", str(base / "MP_Gui.sh")]
    elif role == ROLE_LIQUID:
        launcher = base / "scripts" / "launch-liquid-glass"
        if not launcher.is_file():
            launcher = base / "scripts" / "launch_liquid_glass.sh"
        argv = [str(launcher)]
    else:
        launcher = base / "bin" / "launch-manager"
        if not launcher.is_file():
            launcher = base / "bin" / "mix-archive-manager"
        argv = [str(launcher)]
    return {"action": "spawn", "title": title, "argv": argv}


def kill_all_script(base: Path) -> Path | None:
    for candidate in (
        base / "scripts" / "kill_all_mp_audio_players.sh",
        base / "kill_all_mp_audio_players.sh",
    ):
        if candidate.is_file():
            return candidate
    return None


def read_proc_table() -> list[ProcessInfo]:
    proc_root = Path("/proc")
    if proc_root.is_dir():
        found: list[ProcessInfo] = []
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "cmdline").read_bytes()
                stat = (entry / "stat").read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not raw:
                continue
            cmdline = raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
            environ = ""
            try:
                env_raw = (entry / "environ").read_bytes()
                environ = env_raw.replace(b"\x00", b"\n").decode("utf-8", "replace")
            except OSError:
                environ = ""
            ppid = _ppid_from_stat(stat)
            found.append(ProcessInfo(int(entry.name), ppid, cmdline, environ))
        return found
    return _read_proc_table_ps()


def _ppid_from_stat(stat_text: str) -> int:
    marker = stat_text.rfind(")")
    if marker < 0:
        return 0
    fields = stat_text[marker + 2 :].split()
    if len(fields) < 2:
        return 0
    try:
        return int(fields[1])
    except ValueError:
        return 0


def _read_proc_table_ps() -> list[ProcessInfo]:
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=,ppid=,command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    found: list[ProcessInfo] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        found.append(ProcessInfo(pid, ppid, parts[2], ""))
    return found


def focus_window(title: str) -> bool:
    wmctrl = _which("wmctrl")
    if not wmctrl:
        return False
    listed = subprocess.run([wmctrl, "-l"], capture_output=True, text=True, timeout=3, check=False)
    if listed.returncode != 0:
        return False
    for line in listed.stdout.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4 or title not in parts[3]:
            continue
        activated = subprocess.run(
            [wmctrl, "-i", "-a", parts[0]],
            capture_output=True,
            timeout=3,
            check=False,
        )
        return activated.returncode == 0
    return False


def close_windows(titles: tuple[str, ...] = CLOSE_WINDOW_TITLES) -> None:
    wmctrl = _which("wmctrl")
    if not wmctrl:
        return
    listed = subprocess.run([wmctrl, "-l"], capture_output=True, text=True, timeout=3, check=False)
    if listed.returncode != 0:
        return
    for line in listed.stdout.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        if any(title in parts[3] for title in titles):
            subprocess.run([wmctrl, "-i", "-c", parts[0]], capture_output=True, timeout=3, check=False)


def _which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(":"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _signal_pids(pids: list[int], sig: int) -> None:
    for pid in pids:
        if pid <= 1 or pid == os.getpid():
            continue
        try:
            os.kill(pid, sig)
        except OSError:
            continue


def _still_alive(pids: list[int]) -> list[int]:
    alive = []
    for pid in pids:
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        alive.append(pid)
    return alive


def shutdown_suite(base: Path) -> list[int]:
    """Stop playback, the GUI, the Liquid Player, and the console manager."""
    script = kill_all_script(base)
    if script is not None:
        try:
            subprocess.run(
                [str(script), "-q"],
                timeout=30,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                start_new_session=True,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    processes = read_proc_table()
    pids = manager_pids(processes, {os.getpid()})
    _signal_pids(pids, signal.SIGTERM)
    deadline = time.time() + 1.5
    alive = _still_alive(pids)
    while alive and time.time() < deadline:
        time.sleep(0.15)
        alive = _still_alive(pids)
    if alive:
        _signal_pids(alive, signal.SIGKILL)
    close_windows()
    return pids


def spawn_argv(argv: list[str], base: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "ab")
    env = os.environ.copy()
    env.pop("MP_SYSTEM_TRAY_CHILD", None)
    try:
        subprocess.Popen(
            argv,
            cwd=str(base),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
    finally:
        log_file.close()


def write_desktop_entry(base: Path, applications_dir: Path) -> Path:
    applications_dir.mkdir(parents=True, exist_ok=True)
    desktop = applications_dir / "mp-mix-manager-tray.desktop"
    script = base / "scripts" / "mp_system_tray.sh"
    icon = icon_file(base)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=MP Mix Manager\n"
        "Comment=Shared tray icon for MP Mix Manager, MP Gui, and MP Liquid Player\n"
        f"Exec={script} --stay\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;\n"
        "NoDisplay=true\n"
    )
    if not desktop.is_file() or desktop.read_text(encoding="utf-8") != content:
        desktop.write_text(content, encoding="utf-8")
    return desktop


def autostart_dir() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if config_home:
        return Path(config_home) / "autostart"
    return Path.home() / ".config" / "autostart"


def write_autostart_entry(base: Path, autostart: Path) -> Path:
    autostart.mkdir(parents=True, exist_ok=True)
    desktop = autostart / "mp-mix-manager-tray.desktop"
    script = base / "scripts" / "mp_system_tray.sh"
    icon = icon_file(base)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=MP Mix Manager\n"
        "Comment=Shared tray icon for MP Mix Manager, MP Gui, and MP Liquid Player\n"
        f"Exec={script} --stay\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;\n"
        "X-GNOME-Autostart-enabled=true\n"
        "StartupNotify=false\n"
    )
    if not desktop.is_file() or desktop.read_text(encoding="utf-8") != content:
        desktop.write_text(content, encoding="utf-8")
    return desktop


def _write_kded_autoload_ini(rc_path: Path, module: str, enabled: bool) -> None:
    section = f"[Module-{module}]"
    value = "true" if enabled else "false"
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    lines = rc_path.read_text(encoding="utf-8").splitlines(True) if rc_path.is_file() else []
    out: list[str] = []
    index = 0
    found = False
    while index < len(lines):
        if lines[index].strip() == section:
            found = True
            out.append(lines[index] if lines[index].endswith("\n") else lines[index] + "\n")
            index += 1
            wrote = False
            while index < len(lines) and not lines[index].startswith("["):
                stripped = lines[index].lstrip()
                if stripped.startswith("autoload=") or stripped.startswith("autoload "):
                    if not wrote:
                        out.append(f"autoload={value}\n")
                        wrote = True
                else:
                    out.append(lines[index])
                index += 1
            if not wrote:
                out.append(f"autoload={value}\n")
            continue
        out.append(lines[index])
        index += 1
    if not found:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        if out and out[-1].strip():
            out.append("\n")
        out.append(f"{section}\n")
        out.append(f"autoload={value}\n")
    rc_path.write_text("".join(out), encoding="utf-8")


def set_kded_autoload(module: str, enabled: bool, rc_path: Path | None = None) -> Path:
    path = rc_path or (Path.home() / ".config" / "kded5rc")
    _write_kded_autoload_ini(path, module, enabled)
    return path


def load_kded_module(module: str) -> bool:
    calls = (
        (
            "busctl",
            [
                "busctl",
                "--user",
                "--timeout=5",
                "call",
                "org.kde.kded6",
                "/kded",
                "org.kde.kded6",
                "loadModule",
                "s",
                module,
            ],
        ),
        (
            "qdbus",
            ["qdbus", "org.kde.kded6", "/kded", "org.kde.kded6.loadModule", module],
        ),
        (
            "busctl",
            [
                "busctl",
                "--user",
                "--timeout=5",
                "call",
                "org.kde.kded5",
                "/kded",
                "org.kde.kded5",
                "loadModule",
                "s",
                module,
            ],
        ),
    )
    for name, argv in calls:
        if not _which(name):
            continue
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                timeout=6,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return True
    return False


def enable_status_notifier_watcher(rc_paths: list[Path] | None = None) -> None:
    """KDE shows no tray icons unless statusnotifierwatcher is loaded."""
    paths = rc_paths or [
        Path.home() / ".config" / "kded5rc",
        Path.home() / ".config" / "kded6rc",
    ]
    for path in paths:
        set_kded_autoload("statusnotifierwatcher", True, path)
    load_kded_module("statusnotifierwatcher")


def wait_for_system_tray(seconds: float = 6.0) -> bool:
    from PySide6.QtWidgets import QSystemTrayIcon

    deadline = time.time() + seconds
    available = QSystemTrayIcon.isSystemTrayAvailable()
    while not available and time.time() < deadline:
        time.sleep(0.25)
        available = QSystemTrayIcon.isSystemTrayAvailable()
    return available


def stop_tray_holder(lock_path: Path, self_pid: int | None = None) -> None:
    if not lock_path.is_file():
        return
    try:
        pid = int(lock_path.read_text(encoding="utf-8").strip().split()[0])
    except (OSError, ValueError):
        return
    if pid <= 1 or pid == (self_pid or os.getpid()):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return


def applications_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if data_home:
        return Path(data_home) / "applications"
    return Path.home() / ".local" / "share" / "applications"


def install_tray(base: Path) -> int:
    if os.name == "nt":
        from install_desktop_shortcuts import run_windows_user_integration

        return run_windows_user_integration(base, "Install")
    enable_status_notifier_watcher()
    write_desktop_entry(base, applications_dir())
    write_autostart_entry(base, autostart_dir())
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return 0
    lock_path = config_dir() / "mp_system_tray.lock"
    stop_tray_holder(lock_path)
    script = base / "scripts" / "mp_system_tray.sh"
    spawn_argv([str(script), "--stay"], base, config_dir() / "mp_system_tray.log")
    deadline = time.time() + 5
    while time.time() < deadline:
        if TrayLock.held(lock_path):
            return 0
        time.sleep(0.1)
    return 0


def run_tray(base: Path, config: Path, stay: bool = False) -> int:
    os.environ.setdefault("QT_QPA_PLATFORMTHEME", "kde")
    enable_status_notifier_watcher()
    write_desktop_entry(base, applications_dir())
    write_autostart_entry(base, autostart_dir())

    from PySide6.QtGui import QAction, QCursor, QIcon
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("MP Mix Manager")
    app.setDesktopFileName("mp-mix-manager-tray")
    tray_available = wait_for_system_tray()

    icon = QIcon(str(icon_file(base)))
    if icon.isNull():
        icon = QIcon.fromTheme("audio-x-generic")
    tray = QSystemTrayIcon(icon)
    tray.setToolTip("MP Mix Manager")
    log_path = config / "mp_system_tray.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(
            f"ready pid={os.getpid()} tray={tray_available}\n"
        )

    menu = QMenu()
    state = {"busy_until": 0.0, "absent_since": None, "closing": False}

    def remember_launch() -> None:
        state["busy_until"] = time.time() + LAUNCH_GRACE_SECONDS
        state["absent_since"] = None

    def dispatch(action_id: str) -> None:
        if state["closing"]:
            return
        if action_id == "close-all":
            state["closing"] = True
            shutdown_suite(base)
            app.quit()
            return
        role = {
            "launch-gui": ROLE_GUI,
            "launch-liquid": ROLE_LIQUID,
            "launch-manager": ROLE_MANAGER,
        }[action_id]
        running = roles_present(read_proc_table(), {os.getpid()})
        plan = launch_plan(role, base, running)
        remember_launch()
        if plan["action"] == "focus":
            focus_window(str(plan["title"]))
            return
        spawn_argv(list(plan["argv"]), base, log_path)

    for action_id, label in MENU_ENTRIES:
        if action_id == "close-all":
            menu.addSeparator()
        action = QAction(label, menu)
        action.triggered.connect(lambda checked=False, ident=action_id: dispatch(ident))
        menu.addAction(action)

    tray.setContextMenu(menu)

    def on_activated(reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        ):
            menu.popup(QCursor.pos())

    tray.activated.connect(on_activated)
    tray.show()

    def poll() -> None:
        if state["closing"] or stay or time.time() < state["busy_until"]:
            return
        running = roles_present(read_proc_table(), {os.getpid()})
        if running:
            state["absent_since"] = None
            return
        now = time.time()
        if state["absent_since"] is None:
            state["absent_since"] = now
            return
        if now - state["absent_since"] >= ABSENT_QUIT_SECONDS:
            app.quit()

    from PySide6.QtCore import QTimer

    timer = QTimer()
    timer.setInterval(2000)
    timer.timeout.connect(poll)
    timer.start()

    def request_quit(*_args) -> None:
        app.quit()

    signal.signal(signal.SIGTERM, request_quit)
    signal.signal(signal.SIGINT, request_quit)
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if os.name == "nt":
        from install_desktop_shortcuts import run_windows_tray, run_windows_user_integration

        base = default_base_dir()
        if "--status" in args:
            return run_windows_user_integration(base, "Status")
        if "--install" in args:
            return run_windows_user_integration(base, "Install")
        return run_windows_tray(base, stay="--stay" in args)
    config = config_dir()
    lock_path = config / "mp_system_tray.lock"
    if "--status" in args:
        return 0 if TrayLock.held(lock_path) else 1
    if "--install" in args:
        return install_tray(default_base_dir())
    lock = TrayLock(lock_path)
    if not lock.acquire():
        return 0
    try:
        return run_tray(default_base_dir(), config, stay="--stay" in args)
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
