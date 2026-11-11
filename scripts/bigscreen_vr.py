#!/usr/bin/env python3
"""Windows-only Bigscreen VR mode for the MP Liquid Player.

Bigscreen Beta is Steam app 457550. The Windows executable is Bigscreen.exe
(also shipped as BigScreen.exe). Steam puts it in a library's
steamapps/common/Bigscreen folder. The Oculus PC build uses
Software/bigscreen-bigscreen/Bigscreen. This lookup is path-based because
the manager is developed on Linux and cannot see a Windows install from here.

VR Mode starts Bigscreen first, so the headset is already loading in. The MP
Liquid Player only appears on the desktop after that, centered on the primary
monitor, in the Retro Linux Memories theme, and paused. The player host writes
its placed geometry to a ready file. Once that report says the player is
centered, this launcher starts the music. Any other operating system, or a
Windows machine without Bigscreen, is refused every time.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

STEAM_APP_ID = "457550"
VR_THEME = "retro_linux_memories"
VR_PLAYER_COLS = 84
VR_PLAYER_ROWS = 26
VR_CHAR_W = 9
VR_CHAR_H = 18
VR_BEZEL = 7
VR_OPENGL_EXTRA_H = 44
VR_READY_FILE = "vr_player_ready.json"
VR_READY_TOLERANCE = 24
VR_PLAYER_TIMEOUT = 45.0
VR_BIGSCREEN_LOAD_DELAY = 2.5
VR_PLAY_RETRIES = 40
VR_PLAY_RETRY_DELAY = 0.25
VR_VISUALIZER_CAP = 1600
VR_FRAME = 80
VR_BACKDROP_DELAY = 0.35

REFUSAL_MESSAGE = (
    "VR Mode refused to load.\n"
    "You must be on Microsoft Windows and have Bigscreen VR installed already."
)

_UNSET = object()
_PATH_RE = re.compile(r'"path"\s+"([^"]+)"')

_STEAM_TAILS = (
    Path("Program Files (x86)") / "Steam" / "steamapps" / "common",
    Path("Program Files") / "Steam" / "steamapps" / "common",
)
_OCULUS_TAILS = (
    Path("Program Files (x86)") / "Oculus" / "Software" / "Software" / "bigscreen-bigscreen",
    Path("Program Files") / "Oculus" / "Software" / "Software" / "bigscreen-bigscreen",
)
_APP_FOLDERS = ("Bigscreen", "BigScreen")
_LIBRARY_VDF_TAILS = (
    Path("Program Files (x86)") / "Steam" / "steamapps" / "libraryfolders.vdf",
    Path("Program Files") / "Steam" / "steamapps" / "libraryfolders.vdf",
)
_REGISTRY_KEYS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 457550",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 457550",
)


def is_microsoft_windows(platform_name: str | None = None) -> bool:
    """Native Microsoft Windows. WSL stays Linux and is refused."""
    name = (platform_name if platform_name is not None else sys.platform).lower()
    return name in {"win32", "windows", "cygwin", "msys"}


# ---------------------------------------------------------------------------
# VR layout, shared with the Liquid Player host through the environment
# ---------------------------------------------------------------------------

def vr_layout_active() -> bool:
    return os.environ.get("MP_VR_LAYOUT") == "1"


def vr_player_grid() -> tuple[int, int]:
    """Character grid for the centered VR player. The launcher sets the env."""
    try:
        cols = int(os.environ.get("MP_VR_PLAYER_COLS", VR_PLAYER_COLS))
        rows = int(os.environ.get("MP_VR_PLAYER_ROWS", VR_PLAYER_ROWS))
    except ValueError:
        cols, rows = VR_PLAYER_COLS, VR_PLAYER_ROWS
    return max(40, cols), max(12, rows)


def vr_point(kind: str = "player") -> tuple[int, int] | None:
    """Top-left written by the VR launcher."""
    if not vr_layout_active():
        return None
    prefix = "MP_VR_PLAYER" if kind == "player" else "MP_VR_VISUALIZER"
    try:
        return int(os.environ[f"{prefix}_X"]), int(os.environ[f"{prefix}_Y"])
    except (KeyError, ValueError):
        return None


def vr_screen_rect() -> tuple[int, int, int, int] | None:
    """Primary monitor rectangle the launcher selected for this session."""
    if not vr_layout_active():
        return None
    try:
        return (
            int(os.environ["MP_VR_SCREEN_X"]),
            int(os.environ["MP_VR_SCREEN_Y"]),
            int(os.environ["MP_VR_SCREEN_W"]),
            int(os.environ["MP_VR_SCREEN_H"]),
        )
    except (KeyError, ValueError):
        return None


def vr_config_dir() -> Path:
    raw = (os.environ.get("MP_VR_CONFIG_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config" / "mix-manager"


def player_pixels(cols: int, rows: int, backend: str = "opengl") -> tuple[int, int]:
    extra = 0 if str(backend).lower() == "vulkan" else VR_OPENGL_EXTRA_H
    width = int(cols) * VR_CHAR_W + 2 * VR_BEZEL
    height = int(rows) * VR_CHAR_H + 2 * VR_BEZEL + extra
    return width, height


def vr_visualizer_side() -> int | None:
    if not vr_layout_active():
        return None
    try:
        side = int(os.environ["MP_VR_VISUALIZER_SIZE"])
    except (KeyError, ValueError):
        return None
    return side if side >= 64 else None


def visualizer_side(screen_w: int, screen_h: int) -> int:
    """Largest square backdrop that still fits the screen, capped for VR."""
    side = min(int(screen_w), int(screen_h)) - 48
    side = min(side, VR_VISUALIZER_CAP)
    side = max(480, side)
    return int(min(side, int(screen_w), int(screen_h)))


def player_grid_for(side: int, backend: str = "opengl") -> tuple[int, int, int, int]:
    """Cols, rows, and pixels for a player that stays inside the backdrop."""
    room = max(240, int(side) - 2 * VR_FRAME)
    extra = 0 if str(backend).lower() == "vulkan" else VR_OPENGL_EXTRA_H
    cols = min(VR_PLAYER_COLS, max(40, (room - 2 * VR_BEZEL) // VR_CHAR_W))
    rows = min(VR_PLAYER_ROWS, max(12, (room - 2 * VR_BEZEL - extra) // VR_CHAR_H))
    width, height = player_pixels(cols, rows, backend)
    return int(cols), int(rows), int(width), int(height)


def _center(origin: int, screen: int, size: int) -> int:
    return int(origin) + max(0, (int(screen) - int(size)) // 2)


def vr_layout(screen_x: int, screen_y: int, screen_w: int, screen_h: int, backend: str = "opengl") -> dict:
    """Player centered. The visualizer is the larger square on that same center."""
    side = visualizer_side(screen_w, screen_h)
    cols, rows, player_w, player_h = player_grid_for(side, backend)
    player = (
        _center(screen_x, screen_w, player_w),
        _center(screen_y, screen_h, player_h),
        player_w,
        player_h,
    )
    visualizer = (
        _center(screen_x, screen_w, side),
        _center(screen_y, screen_h, side),
        side,
        side,
    )
    return {
        "theme": VR_THEME,
        "backend": backend,
        "cols": cols,
        "rows": rows,
        "player": player,
        "visualizer": visualizer,
    }


def center_player_on_screen(width: int, height: int, rect=None) -> tuple[int, int]:
    """Top-left that centers a window of this size on the primary desktop."""
    screen = rect if rect is not None else vr_screen_rect()
    if screen is None:
        screen = windows_primary_screen()
    return _center(screen[0], screen[2], width), _center(screen[1], screen[3], height)


# ---------------------------------------------------------------------------
# Player ready report: written by the Liquid Player host, read by the launcher
# ---------------------------------------------------------------------------

def player_ready_file(config_dir: Path | None = None) -> Path:
    return (Path(config_dir) if config_dir else vr_config_dir()) / VR_READY_FILE


def publish_player_ready(x: int, y: int, width: int, height: int, config_dir: Path | None = None) -> dict:
    """Record the placed player geometry so the launcher can start the music."""
    expected = None
    screen = vr_screen_rect()
    if screen is not None:
        expected = center_player_on_screen(width, height, screen)
    centered = expected is None or (
        abs(int(x) - expected[0]) <= VR_READY_TOLERANCE
        and abs(int(y) - expected[1]) <= VR_READY_TOLERANCE
    )
    record = {
        "pid": os.getpid(),
        "x": int(x),
        "y": int(y),
        "width": int(width),
        "height": int(height),
        "centered": bool(centered),
        "theme": VR_THEME,
        "timestamp": time.time(),
    }
    path = player_ready_file(config_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(record), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
    return record


def read_player_ready(config_dir: Path | None = None) -> dict | None:
    try:
        raw = player_ready_file(config_dir).read_text(encoding="utf-8")
        record = json.loads(raw)
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def clear_player_ready(config_dir: Path | None = None) -> None:
    try:
        player_ready_file(config_dir).unlink()
    except OSError:
        pass


def player_ready_centered(config_dir: Path | None = None, not_before: float = 0.0) -> bool:
    record = read_player_ready(config_dir)
    if not isinstance(record, dict):
        return False
    try:
        stamp = float(record.get("timestamp") or 0.0)
    except (TypeError, ValueError):
        return False
    if stamp and stamp < float(not_before):
        return False
    return bool(record.get("centered"))


def wait_for_player_ready(
    config_dir: Path | None = None,
    timeout: float = VR_PLAYER_TIMEOUT,
    not_before: float = 0.0,
    sleeper=None,
    interval: float = 0.25,
) -> bool:
    """Poll the ready file until the player reports itself centered."""
    sleep = sleeper or time.sleep
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        if player_ready_centered(config_dir, not_before=not_before):
            return True
        sleep(interval)
    return player_ready_centered(config_dir, not_before=not_before)


# ---------------------------------------------------------------------------
# Bigscreen lookup
# ---------------------------------------------------------------------------

def steam_library_roots(vdf_text: str) -> list[Path]:
    roots = []
    for raw in _PATH_RE.findall(vdf_text or ""):
        roots.append(Path(raw.replace("\\\\", "\\")))
    return roots


def _bigscreen_exe(folder: Path) -> Path | None:
    folder = Path(folder)
    if folder.is_file() and folder.name.lower() == "bigscreen.exe":
        return folder
    if not folder.is_dir():
        return None
    for name in ("Bigscreen.exe", "BigScreen.exe"):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    try:
        for child in folder.iterdir():
            if child.is_file() and child.name.lower() == "bigscreen.exe":
                return child
    except OSError:
        return None
    return None


def _folders_under(base: Path):
    yield base
    for name in _APP_FOLDERS:
        yield base / name


def find_bigscreen_exe(drive_roots=None, library_vdf_texts=None, extra_dirs=None) -> Path | None:
    """First Bigscreen.exe under the published Steam and Oculus locations."""
    bases: list[Path] = []
    for root in drive_roots or []:
        root = Path(root)
        for tail in _STEAM_TAILS:
            bases.extend(_folders_under(root / tail))
        for tail in _OCULUS_TAILS:
            bases.extend(_folders_under(root / tail))
    for text in library_vdf_texts or []:
        for library in steam_library_roots(text):
            common = library / "steamapps" / "common"
            bases.extend(_folders_under(common))
    for extra in extra_dirs or []:
        bases.extend(_folders_under(Path(extra)))
    seen = set()
    for base in bases:
        key = str(base)
        if key in seen:
            continue
        seen.add(key)
        found = _bigscreen_exe(base)
        if found is not None:
            return found
    return None


def _windows_drive_roots() -> list[Path]:
    roots = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZAB":
        root = Path(f"{letter}:/")
        if root.exists():
            roots.append(root)
    return roots


def _read_library_vdfs(drive_roots) -> list[str]:
    texts = []
    for root in drive_roots:
        for tail in _LIBRARY_VDF_TAILS:
            path = Path(root) / tail
            try:
                if path.is_file():
                    texts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return texts


def _registry_install_locations() -> list[str]:
    if sys.platform != "win32":
        return []
    import winreg
    found = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key in _REGISTRY_KEYS:
            try:
                with winreg.OpenKey(hive, key) as handle:
                    value, _ = winreg.QueryValueEx(handle, "InstallLocation")
            except OSError:
                continue
            if value:
                found.append(str(value))
    return found


def find_installed_bigscreen(platform_name: str | None = None) -> Path | None:
    if not is_microsoft_windows(platform_name):
        return None
    drives = _windows_drive_roots()
    return find_bigscreen_exe(drives, _read_library_vdfs(drives), _registry_install_locations())


def windows_primary_screen() -> tuple[int, int, int, int]:
    """Primary monitor rectangle (x, y, width, height). Falls back to 1920x1080."""
    if sys.platform != "win32":
        return (0, 0, 1920, 1080)
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    found: dict = {}

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)
    def _callback(monitor, _hdc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)) and info.dwFlags & 1:
            rect = info.rcMonitor
            found["rect"] = (int(rect.left), int(rect.top), int(rect.right - rect.left), int(rect.bottom - rect.top))
        return True

    user32.EnumDisplayMonitors(None, None, _callback, 0)
    rect = found.get("rect")
    if not rect or rect[2] < 64 or rect[3] < 64:
        width = int(user32.GetSystemMetrics(0) or 1920)
        height = int(user32.GetSystemMetrics(1) or 1080)
        return (0, 0, width, height)
    return rect


# ---------------------------------------------------------------------------
# Player selection and launch helpers
# ---------------------------------------------------------------------------

def liquid_backend(root: Path, config_dir: Path) -> str:
    for path in (config_dir / "config.env", Path(root) / "config.env"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("LIQUID_GLASS_BACKEND="):
                value = line.split("=", 1)[1].strip().strip("\"'").lower()
                if value:
                    return value
    return "opengl"


def liquid_player_script(root: Path, backend: str) -> Path | None:
    root = Path(root)
    vulkan = root / "MP_Audio_Player_Liquid_Glass.py"
    opengl = root / "MP_Audio_Player_Liquid_Glass_OpenGL.py"
    if backend == "vulkan" and vulkan.is_file():
        return vulkan
    if opengl.is_file():
        return opengl
    if vulkan.is_file():
        return vulkan
    return None


def visualizer_script(root: Path) -> Path | None:
    root = Path(root)
    for path in (root / "MP_Liquid_Visualizer.py", root / "scripts" / "mp_liquid_visualizer_vulkan.py"):
        if path.is_file():
            return path
    return None


def apply_retro_linux_memories(config_dir: Path) -> None:
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "theme").write_text(VR_THEME + "\n", encoding="utf-8")


def vr_layout_env(layout: dict, config_dir: Path, screen: tuple[int, int, int, int]) -> dict:
    player_x, player_y, _player_w, _player_h = layout["player"]
    vis_x, vis_y, side, _side = layout["visualizer"]
    env = os.environ.copy()
    env.update({
        "MP_VR_LAYOUT": "1",
        "MP_VR_MODE": "1",
        "MP_VR_CONFIG_DIR": str(Path(config_dir)),
        "MP_VR_SCREEN_X": str(screen[0]),
        "MP_VR_SCREEN_Y": str(screen[1]),
        "MP_VR_SCREEN_W": str(screen[2]),
        "MP_VR_SCREEN_H": str(screen[3]),
        "MP_VR_PLAYER_X": str(player_x),
        "MP_VR_PLAYER_Y": str(player_y),
        "MP_VR_PLAYER_COLS": str(layout["cols"]),
        "MP_VR_PLAYER_ROWS": str(layout["rows"]),
        "MP_VR_VISUALIZER_X": str(vis_x),
        "MP_VR_VISUALIZER_Y": str(vis_y),
        "MP_VR_VISUALIZER_SIZE": str(side),
        "MP_LIQUID_GLASS": "1",
    })
    return env


def player_command(python: str, player: Path, theme: str) -> list[str]:
    """The Liquid Player opens centered and paused. The launcher plays the music."""
    return [
        python,
        str(player),
        "--theme",
        theme,
        "--no-visualizer",
        "--start-paused",
    ]


def _default_spawn(command, env, cwd, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "a", encoding="utf-8")
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": log, "cwd": str(cwd), "env": env}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000208
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(list(command), **kwargs)


def _run_player_command(root: Path, python: str | None, args: list[str], log_path: Path | None = None, timeout: float = 5.0):
    player = Path(root) / "MP_Audio_Player.py"
    if not player.is_file():
        return None
    command = [python or sys.executable or "python", str(player), *args]
    log = None
    try:
        if log_path is not None:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            log = open(log_path, "a", encoding="utf-8")
        return subprocess.run(
            command,
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=log if log is not None else subprocess.DEVNULL,
            stderr=log if log is not None else subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if log is not None:
            log.close()


def pause_player(root: Path, python: str | None = None, log_path: Path | None = None) -> bool:
    """Pause any music that was already playing before VR Mode opens."""
    done = _run_player_command(root, python, ["--pause"], log_path)
    return bool(done is not None and done.returncode == 0)


def start_player_music(
    root: Path,
    python: str | None = None,
    log_path: Path | None = None,
    sleeper=None,
    retries: int = VR_PLAY_RETRIES,
    interval: float = VR_PLAY_RETRY_DELAY,
) -> bool:
    """Resume the paused MP Audio Player daemon.

    The daemon binds its IPC socket after it scans the archive, so the command
    is retried. A responsive daemon answers 0 and the music starts.
    """
    sleep = sleeper or time.sleep
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        done = _run_player_command(root, python, ["--cmd", "play"], log_path)
        if done is not None and done.returncode == 0:
            return True
        if attempt + 1 < attempts:
            sleep(interval)
    return False


def _raise_player_over_visualizer() -> None:
    """Put the visualizer directly behind the Liquid Player on Windows."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    player = None
    visualizer = None

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        nonlocal player, visualizer
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title.startswith("MP Audio Player (Liquid Glass"):
            player = hwnd
        elif title.startswith("MP Liquid Visualizer"):
            visualizer = hwnd
        return True

    user32.EnumWindows(_callback, 0)
    if not player or not visualizer:
        return
    swp = 0x0001 | 0x0002 | 0x0010
    user32.SetWindowPos(visualizer, player, 0, 0, 0, 0, swp)


def _raise_player_window() -> None:
    """Bring the Liquid Player window to the front after it is centered."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    player = None

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        nonlocal player
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value.startswith("MP Audio Player (Liquid Glass"):
            player = hwnd
        return True

    user32.EnumWindows(_callback, 0)
    if not player:
        return
    swp = 0x0001 | 0x0002
    user32.SetWindowPos(player, -1, 0, 0, 0, 0, swp)
    user32.SetForegroundWindow(player)


def enter_vr_mode(
    root: Path | None = None,
    platform_name: str | None = None,
    bigscreen_exe=_UNSET,
    screen=None,
    config_dir: Path | None = None,
    spawn=None,
    sleeper=None,
    ready_waiter=None,
    music_starter=None,
    player_pauser=None,
    load_delay: float = VR_BIGSCREEN_LOAD_DELAY,
) -> int:
    """Load VR Mode, or refuse when this is not Windows with Bigscreen installed."""
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    windows = is_microsoft_windows(platform_name)
    if bigscreen_exe is _UNSET:
        exe = find_installed_bigscreen(platform_name if platform_name is not None else ("windows" if windows else "linux"))
    else:
        exe = Path(bigscreen_exe) if bigscreen_exe else None
    if not windows or exe is None or not Path(exe).is_file():
        print(REFUSAL_MESSAGE)
        return 1

    config = Path(config_dir) if config_dir else Path.home() / ".config" / "mix-manager"
    backend = liquid_backend(root, config)
    player = liquid_player_script(root, backend)
    if player is None:
        print(REFUSAL_MESSAGE)
        return 1
    visualizer = visualizer_script(root)

    apply_retro_linux_memories(config)
    rect = tuple(screen) if screen is not None else windows_primary_screen()
    layout = vr_layout(rect[0], rect[1], rect[2], rect[3], backend)
    env = vr_layout_env(layout, config, rect)
    launch = spawn or _default_spawn
    sleep = sleeper or time.sleep
    log_path = config / "vr_mode.log"
    python = sys.executable or "python"
    live = spawn is None

    clear_player_ready(config)

    # Pause music that was already playing. It resumes after the player is centered.
    pauser = player_pauser
    if pauser is None and live:
        pauser = lambda: pause_player(root, python, log_path)
    if pauser is not None:
        pauser()

    # 1. Bigscreen first: the headset is already loading in.
    launch([str(exe)], env, exe.parent, log_path)

    # 2. Nothing appears on the desktop until Bigscreen is loading.
    if load_delay:
        sleep(load_delay)

    # 3. The visualizer backdrop opens first so it can sit behind the player.
    if visualizer is not None:
        launch([python, str(visualizer), "--preset", "random"], env, root, log_path)
        sleep(VR_BACKDROP_DELAY)

    # 4. The Liquid Player opens centered on the primary desktop, paused.
    launched_at = time.time()
    launch(player_command(python, player, VR_THEME), env, root, log_path)

    # 5. Only when the player reports itself centered does the music start.
    wait = ready_waiter
    if wait is None and live:
        wait = lambda: wait_for_player_ready(config, VR_PLAYER_TIMEOUT, not_before=launched_at, sleeper=sleep)
    if wait is not None and not wait():
        print("VR Mode: the MP Liquid Player did not report a centered window; music not started.")
        return 1

    if live:
        _raise_player_over_visualizer()
        _raise_player_window()

    starter = music_starter
    if starter is None and live:
        starter = lambda: start_player_music(root, python, log_path, sleeper=sleep)
    if starter is not None:
        starter()
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parent.parent
    if "--root" in args:
        root = Path(args[args.index("--root") + 1])
    return enter_vr_mode(root)


if __name__ == "__main__":
    raise SystemExit(main())
