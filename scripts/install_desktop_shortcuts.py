#!/usr/bin/env python3
"""Install the four MP desktop shortcuts on Linux, macOS, and Windows.

A first install, and the first launch of MP Mix Manager, puts these on the
Desktop and in the application menu:

  MP Liquid Player
  MP Mix Manager
  MP Gui
  MP Liquid Visualizer
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHORTCUT_NAMES = (
    "MP Liquid Player",
    "MP Mix Manager",
    "MP Gui",
    "MP Liquid Visualizer",
)

STALE_SHORTCUT_NAMES = (
    "MP_Liquid.desktop",
    "MP Liquid.desktop",
    "MP_Liquid_Glass_Audio_Player.desktop",
    "MP Liquid Glass Audio Player.desktop",
    "Mix_Archive_Manager.desktop",
    "Mix Archive Manager.desktop",
    "Mix Archive Manager.command",
    "Mix Archive Manager.bat",
    "MP_Liquid.command",
)


def detect_platform() -> str:
    system = sys.platform
    if system == "darwin":
        return "macos"
    if system in {"win32", "cygwin", "msys"}:
        return "windows"
    release = platform.release().lower()
    if os.environ.get("WSL_DISTRO_NAME") or "microsoft" in release:
        return "windows"
    return "linux"


def is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in platform.release().lower()
    except Exception:
        return False


def shortcut_targets(root: Path) -> dict[str, dict]:
    """Launch commands for the four shortcuts. Paths stay inside this install."""
    root = Path(root)
    icon = root / "assets" / "mp_liquid_glass_icon.png"
    win_icon = root / "assets" / "MP_Mix_Manager_Windows_Icon.ico"
    return {
        "MP Liquid Player": {
            "comment": "Launch MP Liquid Player",
            "script": root / "scripts" / "launch_liquid_glass.sh",
            "windows_bat": root / "launch_liquid_glass.bat",
            "terminal": False,
            "categories": "AudioVideo;Audio;Player;",
            "icon": icon,
            "windows_icon": win_icon,
        },
        "MP Mix Manager": {
            "comment": "Launch MP Mix Manager",
            "script": root / "Mix_Archive_Manager.sh",
            "windows_bat": root / "manager.bat",
            "terminal": True,
            "categories": "AudioVideo;Audio;Utility;",
            "icon": icon,
            "windows_icon": win_icon,
        },
        "MP Gui": {
            "comment": "Launch MP Gui",
            "script": root / "MP_Gui.sh",
            "windows_bat": None,
            "terminal": False,
            "categories": "AudioVideo;Audio;Utility;",
            "icon": icon,
            "windows_icon": win_icon,
        },
        "MP Liquid Visualizer": {
            "comment": "Launch MP Liquid Visualizer",
            "script": root / "scripts" / "launch_liquid_visualizer.sh",
            "windows_bat": None,
            "terminal": False,
            "categories": "AudioVideo;Audio;Player;",
            "icon": icon,
            "windows_icon": win_icon,
        },
    }


def _windows_profile() -> Path | None:
    raw = os.environ.get("USERPROFILE", "").strip().strip('"')
    if raw:
        return Path(raw)
    return None


def _is_public_windows_folder(path: str) -> bool:
    norm = path.replace("/", "\\").rstrip("\\").lower()
    return norm.endswith("\\users\\public\\desktop")


def _powershell() -> str | None:
    for name in ("powershell.exe", "pwsh.exe", "pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    system = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    candidate = Path(system) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if candidate.is_file():
        return str(candidate)
    return None


def _decode_powershell(raw: bytes) -> str:
    # powershell.exe writes UTF-16 to a pipe. Reading that as the console
    # code page puts the shortcuts in a path that is not the user profile.
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:80]:
        return raw.decode("utf-16")
    return raw.decode("utf-8", errors="replace")


def _query_windows_folder(powershell: str, name: str) -> str:
    command = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        f"[Environment]::GetFolderPath('{name}')"
    )
    try:
        raw = subprocess.check_output(
            [powershell, "-NoProfile", "-Command", command],
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = []
    for line in _decode_powershell(raw).splitlines():
        stripped = line.strip().strip("\x00")
        if stripped and not stripped.startswith("#<"):
            lines.append(stripped)
    return lines[-1] if lines else ""


def desktop_dir_for(platform_name: str) -> Path:
    if platform_name == "windows":
        found = _windows_special_folder("Desktop")
        if found is not None:
            return found
        profile = _windows_profile()
        if profile is not None:
            return profile / "Desktop"
    if platform_name == "linux":
        xdg = shutil.which("xdg-user-dir")
        if xdg:
            try:
                out = subprocess.check_output([xdg, "DESKTOP"], text=True, timeout=2).strip()
                if out:
                    return Path(out)
            except (OSError, subprocess.SubprocessError):
                pass
    return Path.home() / "Desktop"


def apps_dir_for(platform_name: str) -> Path:
    if platform_name == "macos":
        return Path.home() / "Applications"
    if platform_name == "windows":
        found = _windows_special_folder("Programs")
        if found is not None:
            return found
        profile = _windows_profile()
        if profile is not None:
            return profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return Path.home() / ".local" / "share" / "applications"


def _windows_special_folder(name: str) -> Path | None:
    queries = ["DesktopDirectory", "Desktop"] if name == "Desktop" else [name]
    powershell = _powershell()
    if powershell:
        for query in queries:
            found = _query_windows_folder(powershell, query)
            if found and not _is_public_windows_folder(found):
                return Path(found)
    profile = _windows_profile()
    if profile is None:
        return None
    if name == "Desktop":
        return profile / "Desktop"
    if name == "Programs":
        return profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if name == "Startup":
        return profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return None


def linux_desktop_entry(name: str, spec: dict, root: Path) -> str:
    script = Path(spec["script"])
    exec_line = "bash " + _desktop_quote(str(script))
    icon = spec.get("icon")
    icon_value = str(icon) if icon else "mp_liquid_glass_icon"
    terminal = "true" if spec.get("terminal") else "false"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        f"Name={name}\n"
        f"GenericName={name}\n"
        f"Comment={spec['comment']}\n"
        f"Path={root}\n"
        f"Exec={exec_line}\n"
        f"Icon={icon_value}\n"
        f"Terminal={terminal}\n"
        f"Categories={spec['categories']}\n"
        "StartupNotify=true\n"
    )


def mac_command(spec: dict) -> str:
    script = shlex.quote(str(spec["script"]))
    return (
        "#!/bin/bash\n"
        "export PATH=\"/opt/homebrew/bin:/usr/local/bin:$PATH\"\n"
        "if [ -x /opt/homebrew/bin/bash ]; then\n"
        f"    exec /opt/homebrew/bin/bash {script} \"$@\"\n"
        "elif [ -x /usr/local/bin/bash ]; then\n"
        f"    exec /usr/local/bin/bash {script} \"$@\"\n"
        "else\n"
        f"    exec /bin/bash {script} \"$@\"\n"
        "fi\n"
    )


def windows_launcher_cmd(name: str, spec: dict, root: Path) -> str:
    """A .cmd the Desktop shortcut can open when no ready-made .bat exists."""
    if name == "MP Liquid Visualizer":
        visualizer = str(root / "MP_Liquid_Visualizer.py")
        return (
            "@echo off\n"
            "setlocal\n"
            f"cd /d \"{root}\"\n"
            f"where python >nul 2>&1 && python \"{visualizer}\" %* && exit /b 0\n"
            f"where py >nul 2>&1 && py -3 \"{visualizer}\" %* && exit /b 0\n"
            "echo Python was not found. Install Python 3 and try again.\n"
            "pause\n"
            "exit /b 1\n"
        )
    script = str(spec["script"]).replace("\\", "/")
    return (
        "@echo off\n"
        "setlocal\n"
        "set \"BASH=\"\n"
        "if exist \"%ProgramFiles%\\Git\\bin\\bash.exe\" set \"BASH=%ProgramFiles%\\Git\\bin\\bash.exe\"\n"
        "if not defined BASH if exist \"%ProgramFiles(x86)%\\Git\\bin\\bash.exe\" set \"BASH=%ProgramFiles(x86)%\\Git\\bin\\bash.exe\"\n"
        "if not defined BASH if exist \"%LOCALAPPDATA%\\Programs\\Git\\bin\\bash.exe\" set \"BASH=%LOCALAPPDATA%\\Programs\\Git\\bin\\bash.exe\"\n"
        "if not defined BASH (\n"
        "    echo Git Bash was not found. Install Git for Windows and try again.\n"
        "    pause\n"
        "    exit /b 1\n"
        ")\n"
        f"\"%BASH%\" \"{script}\" %*\n"
        "exit /b %ERRORLEVEL%\n"
    )


def _desktop_quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _remove_stale(directory: Path) -> None:
    if not directory.is_dir():
        return
    for name in STALE_SHORTCUT_NAMES:
        stale = directory / name
        if stale.is_file() or stale.is_symlink():
            try:
                stale.unlink()
            except OSError:
                pass


def _write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(0o755)


def _trust_desktop_file(path: Path) -> None:
    gio = shutil.which("gio")
    if not gio:
        return
    try:
        subprocess.run(
            [gio, "set", str(path), "metadata::trusted", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def write_powershell_lnk(lnk: Path, target: Path, arguments: str, workdir: Path, description: str, icon: Path | None) -> bool:
    powershell = _powershell()
    if not powershell:
        return False
    env = os.environ.copy()
    env.update({
        "MP_LNK": str(lnk),
        "MP_LNK_TARGET": str(target),
        "MP_LNK_ARGS": arguments or "",
        "MP_LNK_CWD": str(workdir),
        "MP_LNK_DESC": description or "",
        "MP_LNK_ICON": str(icon) if icon and Path(icon).is_file() else "",
    })
    script = (
        "$s = New-Object -ComObject WScript.Shell\n"
        "$l = $s.CreateShortcut($env:MP_LNK)\n"
        "$l.TargetPath = $env:MP_LNK_TARGET\n"
        "$l.Arguments = $env:MP_LNK_ARGS\n"
        "$l.WorkingDirectory = $env:MP_LNK_CWD\n"
        "$l.Description = $env:MP_LNK_DESC\n"
        "if ($env:MP_LNK_ICON) { $l.IconLocation = $env:MP_LNK_ICON }\n"
        "$l.WindowStyle = 1\n"
        "$l.Save()\n"
    )
    subprocess.run(
        [powershell, "-NoProfile", "-Command", script],
        env=env,
        check=True,
        timeout=20,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def windows_link_target(name: str, spec: dict, root: Path, launcher_dir: Path) -> tuple[Path, str]:
    """Return the .lnk target and arguments for one shortcut."""
    if is_wsl():
        script = shlex.quote(str(spec["script"]))
        return Path(r"C:\Windows\System32\wsl.exe"), f"bash {script}"
    bat = spec.get("windows_bat")
    if bat and Path(bat).is_file():
        return Path(bat), ""
    cmd = launcher_dir / f"{name}.cmd"
    cmd.parent.mkdir(parents=True, exist_ok=True)
    cmd.write_text(windows_launcher_cmd(name, spec, root), encoding="utf-8", newline="\r\n")
    return cmd, ""


def _windows_creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_windows_user_integration(root: Path, action: str = "Install") -> int:
    """Create the signed-in user's shortcuts and tray. No Python GUI toolkit."""
    script = Path(root) / "scripts" / "windows_user_integration.ps1"
    powershell = _powershell()
    if powershell is None or not script.is_file():
        return 1
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script),
            "-Root", str(root),
            "-Action", action,
        ],
        check=False,
        creationflags=_windows_creationflags(),
    )
    return result.returncode


def run_windows_tray(root: Path, stay: bool = False) -> int:
    script = Path(root) / "scripts" / "windows_tray.ps1"
    powershell = _powershell()
    if powershell is None or not script.is_file():
        return 1
    argv = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-STA",
        "-File", str(script),
        "-Root", str(root),
    ]
    if stay:
        argv.append("-Stay")
    result = subprocess.run(argv, check=False, creationflags=_windows_creationflags())
    return result.returncode


def _delegate_windows_shortcuts(
    platform_name: str,
    desktop_dir: Path | None,
    apps_dir: Path | None,
    launcher_dir: Path | None,
    link_writer,
) -> bool:
    return (
        platform_name == "windows"
        and desktop_dir is None
        and apps_dir is None
        and launcher_dir is None
        and link_writer is None
        and os.name == "nt"
    )


def install_desktop_shortcuts(
    root: Path | None = None,
    platform_name: str | None = None,
    desktop_dir: Path | None = None,
    apps_dir: Path | None = None,
    launcher_dir: Path | None = None,
    link_writer=None,
) -> list[Path]:
    """Write the four shortcuts. Returns the desktop paths."""
    root = Path(root) if root else ROOT
    platform_name = platform_name or detect_platform()
    if _delegate_windows_shortcuts(platform_name, desktop_dir, apps_dir, launcher_dir, link_writer):
        code = run_windows_user_integration(root, "Install")
        if code in (0, 3):
            desktop = desktop_dir_for("windows")
            return [desktop / f"{name}.lnk" for name in SHORTCUT_NAMES]
    desktop = Path(desktop_dir) if desktop_dir else desktop_dir_for(platform_name)
    apps = Path(apps_dir) if apps_dir else apps_dir_for(platform_name)
    launchers = Path(launcher_dir) if launcher_dir else Path.home() / ".config" / "mix-manager" / "launchers"
    desktop.mkdir(parents=True, exist_ok=True)
    apps.mkdir(parents=True, exist_ok=True)
    _remove_stale(desktop)
    _remove_stale(apps)

    targets = shortcut_targets(root)
    written: list[Path] = []
    for name in SHORTCUT_NAMES:
        spec = targets[name]
        if platform_name == "macos":
            content = mac_command(spec)
            for directory in (desktop, apps):
                path = directory / f"{name}.command"
                _write_text(path, content, executable=True)
            written.append(desktop / f"{name}.command")
        elif platform_name == "windows":
            target, arguments = windows_link_target(name, spec, root, launchers)
            icon = spec.get("windows_icon")
            for directory in (desktop, apps):
                path = directory / f"{name}.lnk"
                writer = link_writer or write_powershell_lnk
                writer(path, target, arguments, root, spec["comment"], icon)
            written.append(desktop / f"{name}.lnk")
        else:
            content = linux_desktop_entry(name, spec, root)
            for directory in (desktop, apps):
                path = directory / f"{name}.desktop"
                _write_text(path, content, executable=True)
                _trust_desktop_file(path)
            written.append(desktop / f"{name}.desktop")
    if platform_name == "linux":
        updater = shutil.which("update-desktop-database")
        if updater:
            try:
                subprocess.run([updater, str(apps)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass
    return written


def desktop_shortcuts_present(desktop: Path, platform_name: str) -> bool:
    suffix = { "macos": ".command", "windows": ".lnk" }.get(platform_name, ".desktop")
    return all((desktop / f"{name}{suffix}").is_file() for name in SHORTCUT_NAMES)


def ensure_installed(root: Path | None = None) -> bool:
    """Create any of the four shortcuts that are not already on the Desktop."""
    root = Path(root) if root else ROOT
    platform_name = detect_platform()
    desktop = desktop_dir_for(platform_name)
    if desktop_shortcuts_present(desktop, platform_name):
        return False
    install_desktop_shortcuts(root, platform_name=platform_name, desktop_dir=desktop)
    return True


def main() -> int:
    root = ROOT
    args = sys.argv[1:]
    if "--root" in args:
        root = Path(args[args.index("--root") + 1])
    paths = install_desktop_shortcuts(root)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
