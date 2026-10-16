#!/usr/bin/env python3
"""
scripts/traktor_monitor.py - Cross-Platform Traktor Live Monitor & Audio Recorder Control
Works across macOS, Windows 10 & 11, and Linux (Bazzite / SteamOS / Fedora / Ubuntu).

Shows:
  • Traktor CPU % and memory footprint (RSS)
  • Tracks currently loaded / playing in decks (open audio files / session history)
  • Active recording file (open for write + real-time file size growth)
  • Audio interface from Traktor Settings + system audio defaults

Recording control:
  • macOS: System Events AppleScript menu click
  • Windows 10 & 11: PowerShell UI Automation / AppActivate hotkey dispatch
  • Live keys: s start · x stop · t toggle · r refresh · q quit
  • CLI: --start-recording / --stop-recording / --toggle-recording / --once / --list-menus
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import platform
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows" or os.name == "nt" or "microsoft" in platform.release().lower()
IS_LINUX = platform.system() == "Linux"

# Enable VT100 / ANSI escape processing on Windows 10 & 11 console
if IS_WINDOWS:
    try:
        os.system("")
    except Exception:
        pass

TRAKTOR_PROC = "Traktor"
TRAKTOR_BUNDLE_ID = "com.native-instruments.Traktor"

SETTINGS_CANDIDATES = [
    Path.home() / "Documents/Native Instruments/Traktor 3.11.1/Traktor Settings.tsi",
    Path.home() / "Documents/Native Instruments/Traktor 3/Traktor Settings.tsi",
    Path.home() / "Documents/Native Instruments/Traktor Pro 3/Traktor Settings.tsi",
    Path.home() / "Documents/Native Instruments/Traktor Pro 4/Traktor Settings.tsi",
    Path.home() / "Documents/Native Instruments/Traktor 3.10.0/Traktor Settings.tsi",
    Path.home() / "Documents/Native Instruments/Traktor 2/Traktor Settings.tsi",
]

RECORDING_DIRS = [
    Path.home() / "Documents/MPlanetarian/Documents/TRAKTOR_RECORDINGS/",
    Path.home() / "Documents/MPlanetarian/M_PRODUCTION/STREAM_OF_FREQUENCY_RECORDINGS_TRAKTOR_2026",
    Path.home() / "Music/Traktor/Recordings",
    Path.home() / "Documents/Native Instruments/Traktor 3.11.1/Recordings",
    Path.home() / "Documents/Native Instruments/Traktor 3/Recordings",
    Path.home() / "Documents/Native Instruments/Traktor Pro 3/Recordings",
    Path.home() / "Documents/Native Instruments/Traktor Pro 4/Recordings",
    Path.home() / "Documents/Native Instruments/Traktor 3.11.1",
    Path("D:/MIX_ARCHIVE/CONVERTED_WAV_FILES"),
    Path("D:/MIX_ARCHIVE"),
    Path("/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE/CONVERTED_WAV_FILES"),
    Path("/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE"),
]
if os.environ.get("MIX_ARCHIVE_DIR"):
    _env_arch = Path(os.environ["MIX_ARCHIVE_DIR"])
    RECORDING_DIRS.extend([_env_arch / "CONVERTED_WAV_FILES", _env_arch])

AUDIO_EXTS = (".mp3", ".flac", ".aiff", ".aif", ".wav", ".m4a", ".stem.mp4", ".ogg", ".aac")

RECORD_START_MENU_CANDIDATES: list[tuple[str, str]] = [
    ("File", "Start Recording"),
    ("File", "Start Audio Recording"),
    ("File", "Record"),
    ("Deck", "Start Recording"),
    ("View", "Start Recording"),
    ("Traktor", "Start Recording"),
    ("File", "Audio Recorder On"),
    ("Deck", "Audio Recorder On"),
    ("View", "Audio Recorder On"),
]

RECORD_STOP_MENU_CANDIDATES: list[tuple[str, str]] = [
    ("File", "Stop Recording"),
    ("File", "Stop Audio Recording"),
    ("Deck", "Stop Recording"),
    ("View", "Stop Recording"),
    ("Traktor", "Stop Recording"),
    ("File", "Audio Recorder On"),
    ("Deck", "Audio Recorder On"),
    ("View", "Audio Recorder On"),
]


THEME_CONFIG_FILE = Path.home() / ".config/mix-manager/theme"

THEMES: dict[str, dict[str, str]] = {
    "dreamworlds": {
        "id": "dreamworlds",
        "name": "MPlanetarian Dreamworlds [Default]",
        "desc": "Sweet Hot Pink, Electric Cyan, Amber Gold & Coral Red",
        "primary": "#f72585",
        "secondary": "#00e5ff",
        "accent": "#ffaa00",
        "border": "#845ec2",
        "text": "#f0f3f6",
        "text_dim": "#7f8ba4",
        "green": "#00f5d4",
        "red": "#ed254e",
        "yellow": "#ffaa00",
    },
    "dreamworlds_ultra": {
        "id": "dreamworlds_ultra",
        "name": "Dreamworlds Ultra MP Mix Manager",
        "desc": "Hot Purple, Traffic Light RGB & Electric Green",
        "primary": "#a64dff",
        "secondary": "#00ff00",
        "accent": "#ff9933",
        "border": "#7928ca",
        "text": "#d1d1e0",
        "text_dim": "#9999ff",
        "green": "#00ff00",
        "red": "#ff0000",
        "yellow": "#ff9933",
    },
    "cosmic_supernova": {
        "id": "cosmic_supernova",
        "name": "Cosmic Supernova [Special Edition]",
        "desc": "Aurora Aquamarine, Nebula Orchid, Solar Flare & Supernova Crimson",
        "primary": "#00f5d4",
        "secondary": "#e056fd",
        "accent": "#fee440",
        "border": "#5e60ce",
        "text": "#e2e8f0",
        "text_dim": "#7c8ba1",
        "green": "#00f5d4",
        "red": "#ff3366",
        "yellow": "#fee440",
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "Cyberpunk 2077",
        "desc": "Neon Hot Pink, Electric Cyan & High-Volt Yellow",
        "primary": "#ff0055",
        "secondary": "#00ffff",
        "accent": "#ffff00",
        "border": "#ff0055",
        "text": "#e0ffff",
        "text_dim": "#708090",
        "green": "#00ff9f",
        "red": "#ff0055",
        "yellow": "#ffff00",
    },
    "dracula": {
        "id": "dracula",
        "name": "Dracula",
        "desc": "Vampiric Purple, Coral Pink, Cyan & Neon Green",
        "primary": "#bd93f9",
        "secondary": "#8be9fd",
        "accent": "#ff79c6",
        "border": "#6272a4",
        "text": "#f8f8f2",
        "text_dim": "#6272a4",
        "green": "#50fa7b",
        "red": "#ff5555",
        "yellow": "#f1fa8c",
    },
    "nord": {
        "id": "nord",
        "name": "Nord Frost",
        "desc": "Arctic Slate, Frost Polar Ice & Sage Aurora",
        "primary": "#88c0d0",
        "secondary": "#81a1c1",
        "accent": "#a3be8c",
        "border": "#5e81ac",
        "text": "#eceff4",
        "text_dim": "#929cb0",
        "green": "#a3be8c",
        "red": "#bf616a",
        "yellow": "#ebcb8b",
    },
    "matrix": {
        "id": "matrix",
        "name": "The Matrix",
        "desc": "Pure Phosphor Green, Terminal Crimson & Mint",
        "primary": "#00ff66",
        "secondary": "#a6ff00",
        "accent": "#00cc44",
        "border": "#008f39",
        "text": "#d4ffd4",
        "text_dim": "#337733",
        "green": "#00ff66",
        "red": "#ff3333",
        "yellow": "#a6ff00",
    },
    "solarized": {
        "id": "solarized",
        "name": "Solarized Dark",
        "desc": "Solar Cyan, Solar Blue, Warm Amber & Terracotta",
        "primary": "#2aa198",
        "secondary": "#268bd2",
        "accent": "#b58900",
        "border": "#073642",
        "text": "#93a1a1",
        "text_dim": "#657b83",
        "green": "#859900",
        "red": "#dc322f",
        "yellow": "#b58900",
    },
    "tokyo": {
        "id": "tokyo",
        "name": "Tokyo Night",
        "desc": "Deep Violet, Tokyo Blue, Lavender & Coral",
        "primary": "#7aa2f7",
        "secondary": "#bb9af7",
        "accent": "#7dcfff",
        "border": "#565f89",
        "text": "#c0caf5",
        "text_dim": "#565f89",
        "green": "#9ece6a",
        "red": "#f7768e",
        "yellow": "#e0af68",
    },
    "monokai": {
        "id": "monokai",
        "name": "Monokai Pro",
        "desc": "Electric Pink, Vivid Blue, Lime & Tangerine",
        "primary": "#f92672",
        "secondary": "#66d9ef",
        "accent": "#a6e22e",
        "border": "#75715e",
        "text": "#f8f8f2",
        "text_dim": "#75715e",
        "green": "#a6e22e",
        "red": "#f92672",
        "yellow": "#fd971f",
    },
    "gruvbox": {
        "id": "gruvbox",
        "name": "Gruvbox Dark",
        "desc": "Warm Earth, Gold, Dusty Orange & Forest Sage",
        "primary": "#fabd2f",
        "secondary": "#fe8019",
        "accent": "#83a598",
        "border": "#665c54",
        "text": "#ebdbb2",
        "text_dim": "#928374",
        "green": "#b8bb26",
        "red": "#fb4934",
        "yellow": "#fabd2f",
    },
    "emerald": {
        "id": "emerald",
        "name": "Emerald Isle",
        "desc": "Deep Ocean, Spring Emerald, Mint & Rose",
        "primary": "#10b981",
        "secondary": "#06b6d4",
        "accent": "#34d399",
        "border": "#047857",
        "text": "#ecfdf5",
        "text_dim": "#6ee7b7",
        "green": "#10b981",
        "red": "#f43f5e",
        "yellow": "#fbbf24",
    },
    "classic": {
        "id": "classic",
        "name": "Classic Monochrome",
        "desc": "High-Contrast Monochrome / Standard ANSI",
        "primary": "#ffffff",
        "secondary": "#cccccc",
        "accent": "#aaaaaa",
        "border": "#777777",
        "text": "#ffffff",
        "text_dim": "#666666",
        "green": "#ffffff",
        "red": "#ffffff",
        "yellow": "#ffffff",
    },
}

THEME_ALIASES: dict[str, str] = {
    "default": "dreamworlds",
    "mplanetarian": "dreamworlds",
    "mplanetarian_dreamworlds": "dreamworlds",
    "ultra": "dreamworlds_ultra",
    "dreamworlds ultra": "dreamworlds_ultra",
    "dreamworlds-ultra": "dreamworlds_ultra",
    "hotpurple": "dreamworlds_ultra",
    "trafficlight": "dreamworlds_ultra",
    "supernova": "cosmic_supernova",
    "cosmic": "cosmic_supernova",
    "cosmic supernova": "cosmic_supernova",
    "cosmic-supernova": "cosmic_supernova",
    "tokyo_night": "tokyo",
    "tokyo-night": "tokyo",
    "tokyonight": "tokyo",
    "monochrome": "classic",
    "mono": "classic",
    "white": "classic",
    "ansi": "classic",
    "none": "classic",
    "off": "classic",
}


class ThemeColors:
    def __init__(self, theme_id: str, name: str, desc: str, raw_colors: dict[str, str], enabled: bool = True):
        self.id = theme_id
        self.name = name
        self.desc = desc
        self.enabled = enabled
        if enabled:
            self.reset = "\033[0m"
            self.bold = "\033[1m"
            self.dim = "\033[2m"
            self.primary = self._rgb(raw_colors["primary"])
            self.secondary = self._rgb(raw_colors["secondary"])
            self.accent = self._rgb(raw_colors["accent"])
            self.border = self._rgb(raw_colors["border"])
            self.text = self._rgb(raw_colors["text"])
            self.text_dim = self._rgb(raw_colors["text_dim"])
            self.green = self._rgb(raw_colors["green"])
            self.red = self._rgb(raw_colors["red"])
            self.yellow = self._rgb(raw_colors["yellow"])
        else:
            self.reset = ""
            self.bold = ""
            self.dim = ""
            self.primary = ""
            self.secondary = ""
            self.accent = ""
            self.border = ""
            self.text = ""
            self.text_dim = ""
            self.green = ""
            self.red = ""
            self.yellow = ""

    def _rgb(self, hex_str: str) -> str:
        h = hex_str.lstrip("#")
        return f"\033[38;2;{int(h[0:2],16)};{int(h[2:4],16)};{int(h[4:6],16)}m"


_ACTIVE_THEME_ID = "dreamworlds"


def resolve_theme_id(name: Optional[str]) -> str:
    if not name:
        return "dreamworlds"
    clean = name.strip().lower()
    if clean in THEMES:
        return clean
    if clean in THEME_ALIASES:
        return THEME_ALIASES[clean]
    for k in THEMES:
        if k in clean or clean in k:
            return k
    return "dreamworlds"


def get_theme(theme_id: Optional[str] = None, no_color: bool = False) -> ThemeColors:
    tid = resolve_theme_id(theme_id or _ACTIVE_THEME_ID)
    tinfo = THEMES.get(tid, THEMES["dreamworlds"])
    color_enabled = not no_color and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
    return ThemeColors(tid, tinfo["name"], tinfo["desc"], tinfo, enabled=color_enabled)


def load_saved_theme() -> str:
    for env_var in ("TRAKTOR_MONITOR_THEME", "CURRENT_THEME", "MIX_MANAGER_THEME"):
        val = os.environ.get(env_var, "").strip()
        if val:
            return resolve_theme_id(val)
    if THEME_CONFIG_FILE.exists():
        try:
            val = THEME_CONFIG_FILE.read_text(encoding="utf-8").strip()
            if val:
                return resolve_theme_id(val)
        except Exception:
            pass
    return "dreamworlds"


def save_active_theme(theme_id: str) -> bool:
    try:
        THEME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        THEME_CONFIG_FILE.write_text(theme_id + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def print_theme_list():
    active_tid = load_saved_theme()
    print(f"\n\033[1m🎛️  Traktor Live Monitor — Available Color Themes ({len(THEMES)} Themes):\033[0m\n")
    for tid, tinfo in THEMES.items():
        t = get_theme(tid)
        sample = f"{t.primary}■■■ {t.secondary}■■■ {t.accent}■■■ {t.green}■■■ {t.red}■■■{t.reset}"
        active_mark = f" \033[1m{t.green}★ ACTIVE\033[0m" if tid == active_tid else ""
        print(f"  \033[1m{t.secondary}{tid:<18}\033[0m  {sample}  \033[1m{t.text}{tinfo['name']}\033[0m{active_mark}")
        print(f"  {' '*18}  {t.text_dim}{tinfo['desc']}\033[0m\n")
    print(f"Switch themes live using the \033[1;36m[C]\033[0m key in Traktor Monitor, or launch with: \033[1;32m--theme <name>\033[0m\n")


@dataclass
class RecordingItem:
    path: str
    name: str
    size: int = 0
    mtime: float = 0.0
    is_active: bool = False
    is_growing: bool = False


@dataclass
class Snapshot:
    ts: datetime
    running: bool = False
    pid: Optional[int] = None
    cpu: float = 0.0
    mem_pct: float = 0.0
    rss_mb: float = 0.0
    threads: int = 0
    cpu_time: str = ""
    loaded_tracks: list[str] = field(default_factory=list)
    recording: Optional[str] = None
    recording_size: Optional[int] = None
    recording_growing: Optional[bool] = None
    recording_active: bool = False
    recording_prefix: str = ""
    recent_recordings: list[RecordingItem] = field(default_factory=list)
    device_traktor: str = ""
    sample_rate: str = ""
    latency: str = ""
    driver: str = ""
    system_in: str = ""
    system_out: str = ""
    notes: list[str] = field(default_factory=list)
    last_action: str = ""
    theme_id: str = "dreamworlds"
    theme_name: str = "MPlanetarian Dreamworlds"



def run(cmd: list[str], timeout: float = 3.0) -> str:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return r.stdout or ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def run_osascript(script: str, timeout: float = 12.0) -> tuple[bool, str]:
    """Run AppleScript on macOS; return (ok, stdout_or_stderr)."""
    if not IS_MACOS:
        return False, "osascript only available on macOS"
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, str(e)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return False, err or out or f"osascript exit {r.returncode}"
    return True, out


def find_traktor_pid() -> Optional[int]:
    """Find Traktor process ID across macOS, Linux, and Windows."""
    # 1. macOS detection
    if IS_MACOS:
        out = run(["pgrep", "-f", "Traktor.app/Contents/MacOS/Traktor$"])
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
        out = run(["pgrep", "-i", "-f", "Traktor"])
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
        return None

    # 2. Windows 10 & 11 detection
    if IS_WINDOWS:
        try:
            # Fast tasklist query
            out = subprocess.run(
                ["tasklist", "/fi", "imagename eq Traktor.exe", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            ).stdout or ""
            for line in out.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and "traktor" in parts[0].lower() and parts[1].isdigit():
                    return int(parts[1])
        except Exception:
            pass

        # Check Traktor Pro variations
        for img in ("Traktor Pro 3.exe", "Traktor Pro 4.exe", "Traktor Pro.exe"):
            try:
                out = subprocess.run(
                    ["tasklist", "/fi", f"imagename eq {img}", "/fo", "csv", "/nh"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                ).stdout or ""
                for line in out.splitlines():
                    parts = [p.strip('"') for p in line.split('","')]
                    if len(parts) >= 2 and parts[1].isdigit():
                        return int(parts[1])
            except Exception:
                pass

        # PowerShell fallback
        try:
            cmd = ["powershell.exe", "-NoProfile", "-Command",
                   "(Get-Process -Name Traktor* -ErrorAction SilentlyContinue | Select-Object -First 1).Id"]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=2.5, check=False).stdout.strip()
            if out.isdigit():
                return int(out)
        except Exception:
            pass
        return None

    # 3. Linux (Native or Wine / Bottles / Proton)
    out = run(["pgrep", "-i", "-f", "Traktor"])
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def open_traktor() -> bool:
    """Attempt to launch Native Instruments Traktor Pro on the host system."""
    if IS_MACOS:
        app_paths = [
            Path("/Applications/Native Instruments/Traktor Pro 3/Traktor.app"),
            Path("/Applications/Native Instruments/Traktor Pro 4/Traktor.app"),
            Path("/Applications/Native Instruments/Traktor 3/Traktor.app"),
            Path("/Applications/Traktor Pro 4.app"),
            Path("/Applications/Traktor Pro 3.app"),
            Path("/Applications/Traktor.app"),
        ]
        for p in app_paths:
            if p.exists():
                try:
                    subprocess.Popen(["open", str(p)])
                    return True
                except Exception:
                    pass

        try:
            r = subprocess.run(["open", "-b", TRAKTOR_BUNDLE_ID], capture_output=True, timeout=3.0)
            if r.returncode == 0:
                return True
        except Exception:
            pass

        for name in ("Traktor Pro 3", "Traktor Pro 4", "Traktor"):
            try:
                r = subprocess.run(["open", "-a", name], capture_output=True, timeout=3.0)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    if IS_WINDOWS:
        win_candidates = [
            r"C:\Program Files\Native Instruments\Traktor Pro 4\Traktor.exe",
            r"C:\Program Files\Native Instruments\Traktor Pro 3\Traktor.exe",
            r"C:\Program Files\Native Instruments\Traktor 2\Traktor.exe",
            r"C:\Program Files (x86)\Native Instruments\Traktor Pro 3\Traktor.exe",
        ]
        for p in win_candidates:
            if os.path.isfile(p):
                try:
                    os.startfile(p)
                    return True
                except Exception:
                    try:
                        subprocess.Popen([p])
                        return True
                    except Exception:
                        pass
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "", "Traktor.exe"])
            return True
        except Exception:
            pass
        return False

    if IS_LINUX:
        for cmd in ("traktor", "Traktor"):
            if shutil.which(cmd):
                try:
                    subprocess.Popen([cmd])
                    return True
                except Exception:
                    pass
    return False


def ensure_traktor_running(timeout: float = 12.0) -> Optional[int]:
    """If Traktor is not running already, open it and wait until its process is detected."""
    pid = find_traktor_pid()
    if pid:
        return pid

    print("\n🎛️  Traktor Pro is not currently running.")
    print("🚀 Launching Native Instruments Traktor Pro...")
    opened = open_traktor()
    if not opened:
        print("⚠️  Could not automatically launch Traktor. Waiting for manual start...\n")

    start_t = time.time()
    while time.time() - start_t < timeout:
        time.sleep(1.0)
        pid = find_traktor_pid()
        if pid:
            print(f"✓ Traktor Pro detected (PID: {pid}). Initializing live monitoring...")
            time.sleep(1.5)
            return pid
        elapsed = int(time.time() - start_t)
        print(f"⏳ Waiting for Traktor Pro to initialize ({elapsed}s)...", end="\r", flush=True)

    print("")
    return find_traktor_pid()


def process_stats(pid: int) -> dict:
    """Collect CPU %, memory (RSS MB), threads, and elapsed time."""
    # 1. macOS & Linux via ps
    if not IS_WINDOWS:
        out = run(["ps", "-p", str(pid), "-o", "%cpu=,%mem=,rss=,time="])
        parts = out.split()
        if len(parts) >= 4:
            try:
                cpu = float(parts[0])
                mem = float(parts[1])
                rss_kb = float(parts[2])
                t = parts[3]
                nthr = 0
                if IS_MACOS:
                    thr = run(["ps", "-M", "-p", str(pid)])
                    nthr = max(0, len([ln for ln in thr.splitlines() if ln.strip()]) - 1)
                elif os.path.isdir(f"/proc/{pid}/task"):
                    nthr = len(os.listdir(f"/proc/{pid}/task"))
                return {
                    "cpu": cpu,
                    "mem": mem,
                    "rss_mb": rss_kb / 1024.0,
                    "time": t,
                    "threads": nthr,
                }
            except Exception:
                pass

    # 2. Windows via PowerShell
    if IS_WINDOWS:
        try:
            ps_cmd = (
                f"$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
                "if ($p) { "
                "  $cpu = [math]::Round($p.CPU, 1); "
                "  $mem = [math]::Round($p.WorkingSet64 / 1MB, 1); "
                "  $thr = $p.Threads.Count; "
                "  $time = '{0:N1}s' -f $cpu; "
                "  Write-Output \"$cpu|$mem|$thr|$time\" "
                "}"
            )
            out = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            ).stdout.strip()
            if "|" in out:
                c, m, th, tm = out.split("|", 3)
                return {
                    "cpu": float(c or 0.0),
                    "mem": 0.0,
                    "rss_mb": float(m or 0.0),
                    "time": tm,
                    "threads": int(th or 0),
                }
        except Exception:
            pass

    return {"cpu": 0.0, "mem": 0.0, "rss_mb": 0.0, "time": "?", "threads": 0}


def find_settings() -> Optional[Path]:
    """Find Traktor Settings.tsi across macOS, Windows, and Linux."""
    for p in SETTINGS_CANDIDATES:
        if p.is_file():
            return p

    # Standard Documents search
    docs_dirs = [
        Path.home() / "Documents/Native Instruments",
        Path.home() / "Documents",
    ]
    if IS_WINDOWS:
        user_prof = os.environ.get("USERPROFILE")
        if user_prof:
            docs_dirs.append(Path(user_prof) / "Documents/Native Instruments")
    elif IS_LINUX:
        # Check Wine prefixes
        wine_dirs = [
            Path.home() / ".wine/drive_c/users",
            Path.home() / ".var/app/com.usebottles.bottles/data/bottles/bottles",
        ]
        for wd in wine_dirs:
            if wd.is_dir():
                for p in wd.glob("**/Native Instruments/**/Traktor Settings.tsi"):
                    if p.is_file():
                        return p

    for base in docs_dirs:
        if base.is_dir():
            try:
                for p in base.rglob("Traktor Settings.tsi"):
                    if p.is_file():
                        return p
            except Exception:
                pass
    return None


def parse_settings(path: Path) -> dict:
    """Extract audio device, sample rate, latency, driver, and recording folder."""
    info = {
        "device": "?",
        "sample_rate": "?",
        "latency": "?",
        "driver": "?",
        "recording_prefix": "",
        "recording_dir": "",
    }
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return info

    def grab(name: str) -> Optional[str]:
        m = re.search(
            rf'Name="{re.escape(name)}"[^>]*Value="([^"]*)"',
            text,
        )
        return m.group(1) if m else None

    # Multi-platform audio device names
    info["device"] = (
        grab("Audio.DeviceName.Win")
        or grab("Audio.DeviceName.Mac")
        or grab("Audio.DeviceName.ASIO")
        or grab("Audio.DeviceName.WASAPI")
        or grab("Audio.DeviceName.DirectSound")
        or grab("Audio.DeviceName")
        or "?"
    )
    info["sample_rate"] = grab("Audio.SampleRate") or grab("Audio.FS.SampleRate") or "?"
    info["latency"] = grab("Audio.Latency") or grab("Audio.FS.Latency") or "?"
    info["driver"] = grab("Audio.DriverName") or "?"
    info["recording_prefix"] = grab("Recording.Prefix") or ""
    rec_dir = grab("Recording.Directory") or grab("Recording.Path") or ""
    if rec_dir:
        info["recording_dir"] = rec_dir
        p = Path(rec_dir)
        if p not in RECORDING_DIRS:
            RECORDING_DIRS.insert(0, p)
    return info


def system_audio_defaults() -> tuple[str, str]:
    """Retrieve system default audio input and output across OSes."""
    # 1. macOS: system_profiler
    if IS_MACOS:
        out = run(["system_profiler", "SPAudioDataType"], timeout=6.0)
        default_in = default_out = "?"
        current_name = None
        for line in out.splitlines():
            stripped = line.strip()
            if stripped.endswith(":") and not stripped.startswith("Manufacturer") and not stripped.startswith(
                "Output"
            ) and not stripped.startswith("Input") and not stripped.startswith("Current") and not stripped.startswith(
                "Transport"
            ) and not stripped.startswith("Default"):
                name = stripped[:-1].strip()
                if name and name not in ("Audio", "Devices"):
                    current_name = name
            if "Default Input Device: Yes" in line and current_name:
                default_in = current_name
            if "Default Output Device: Yes" in line and current_name:
                default_out = current_name
        return default_in, default_out

    # 2. Windows 10 & 11: PowerShell CoreAudio / Win32_SoundDevice
    if IS_WINDOWS:
        try:
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "$d = Get-CimInstance Win32_SoundDevice | Select-Object -First 1 -ExpandProperty Name; if ($d) { $d } else { 'Default Audio Device' }",
            ]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0, check=False).stdout.strip()
            dev_name = out if out else "Windows Audio Endpoint"
            return dev_name, dev_name
        except Exception:
            return "Windows Audio Input", "Windows Audio Output"

    # 3. Linux: PipeWire / wpctl
    try:
        p = subprocess.run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"], capture_output=True, text=True, timeout=0.5, check=False)
        if p.returncode == 0 and p.stdout:
            for line in p.stdout.splitlines():
                if "node.description =" in line:
                    m = re.search(r'node\.description\s*=\s*"([^"]+)"', line)
                    if m:
                        return "PipeWire Input", m.group(1).strip()
    except Exception:
        pass

    return "System Default In", "System Default Out"


def get_latest_traktor_history_tracks() -> list[str]:
    """Parse newest Traktor History XML session file (history_*.nml) for loaded tracks."""
    history_dirs = [
        Path.home() / "Documents/Native Instruments/Traktor 3.11.1/History",
        Path.home() / "Documents/Native Instruments/Traktor 3/History",
        Path.home() / "Documents/Native Instruments/Traktor Pro 3/History",
        Path.home() / "Documents/Native Instruments/Traktor Pro 4/History",
    ]
    if IS_WINDOWS and os.environ.get("USERPROFILE"):
        history_dirs.append(Path(os.environ["USERPROFILE"]) / "Documents/Native Instruments/Traktor 3.11.1/History")

    history_files: list[Path] = []
    for hd in history_dirs:
        if hd.is_dir():
            try:
                for f in hd.glob("history_*.nml"):
                    history_files.append(f)
            except Exception:
                pass

    if not history_files:
        return []

    # Pick the most recently modified history file
    history_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_nml = history_files[0]

    # Only consider it active if modified within the last 4 hours
    if time.time() - latest_nml.stat().st_mtime > 14400:
        return []

    tracks: list[str] = []
    try:
        tree = ET.parse(latest_nml)
        root = tree.getroot()
        collection = root.find("COLLECTION")
        if collection is not None:
            entries = collection.findall("ENTRY")
            for entry in entries[-4:]:  # Last 4 loaded tracks (Decks A, B, C, D)
                title = entry.get("TITLE", "").strip()
                artist = entry.get("ARTIST", "").strip()
                loc = entry.find("LOCATION")
                fname = loc.get("FILE", "") if loc is not None else ""
                if title and artist:
                    tracks.append(f"{artist} - {title}")
                elif title:
                    tracks.append(title)
                elif fname:
                    tracks.append(fname)
    except Exception:
        pass
    return tracks


def lsof_tracks_and_recording(pid: int) -> tuple[list[str], Optional[str], Optional[int]]:
    """Inspect process file descriptors for loaded decks and active recordings."""
    loaded: list[str] = []
    recording: Optional[str] = None
    rec_size: Optional[int] = None

    # 1. macOS & Linux: lsof
    if not IS_WINDOWS and shutil.which("lsof"):
        out = run(["lsof", "-p", str(pid), "-F", "n"], timeout=5.0)
        paths = [line[1:] for line in out.splitlines() if line.startswith("n")]

        for p in paths:
            low = p.lower()
            if "/Library/" in p and "Native Instruments" not in p and "STREAM" not in p:
                if not any(low.endswith(ext) for ext in AUDIO_EXTS):
                    continue
            if any(low.endswith(ext) for ext in AUDIO_EXTS) or low.endswith(".wav"):
                if "STREAM_OF_FREQUENCY" in p or "/Recordings/" in p or "recording" in low:
                    recording = p
                    try:
                        rec_size = os.path.getsize(p)
                    except OSError:
                        rec_size = None
                elif any(low.endswith(ext) for ext in AUDIO_EXTS):
                    if p not in loaded:
                        loaded.append(p)

        # Refine write-mode detection with full lsof
        out2 = run(["lsof", "-p", str(pid)], timeout=5.0)
        for line in out2.splitlines():
            parts = line.split()
            if len(parts) >= 9:
                fd = parts[3]
                path = parts[-1]
                if "w" in fd and (path.endswith(".wav") or path.endswith(".aiff") or "STREAM_OF_FREQUENCY" in path):
                    recording = path
                    try:
                        rec_size = os.path.getsize(path)
                    except OSError:
                        pass

        nice = [Path(p).name for p in loaded]
        return nice, recording, rec_size

    # 2. Linux /proc/$pid/fd inspection (fast & lightweight fallback)
    if IS_LINUX and os.path.isdir(f"/proc/{pid}/fd"):
        try:
            for fd_name in os.listdir(f"/proc/{pid}/fd"):
                fd_path = os.path.join(f"/proc/{pid}/fd", fd_name)
                try:
                    target = os.readlink(fd_path)
                    low = target.lower()
                    if any(low.endswith(ext) for ext in AUDIO_EXTS):
                        if "stream_of_frequency" in low or "recording" in low:
                            recording = target
                            try:
                                rec_size = os.path.getsize(target)
                            except OSError:
                                pass
                        elif Path(target).name not in loaded:
                            loaded.append(Path(target).name)
                except OSError:
                    continue
        except Exception:
            pass

    # 3. Windows (or fallback): NML History & File Growth
    if not loaded:
        loaded = get_latest_traktor_history_tracks()

    return loaded, recording, rec_size


def detect_recording_by_growth(
    prefix: str, prev_size: Optional[int]
) -> tuple[Optional[str], Optional[int], Optional[bool]]:
    """Detect the newest recording file and check if it is actively growing."""
    candidates: list[Path] = []
    now = time.time()
    for d in RECORDING_DIRS:
        if not d.is_dir():
            continue
        try:
            for f in d.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in (".wav", ".aiff", ".aif", ".mp3"):
                    continue
                if prefix and prefix not in f.name and not f.name.startswith("MPlanetarian"):
                    pass
                candidates.append(f)
        except OSError:
            continue

    if not candidates:
        return None, None, None

    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        st = newest.stat()
        size = st.st_size
        mtime = st.st_mtime
    except OSError:
        return str(newest), None, None

    # Growing if size grew since last tick, or modified in the last 4 seconds
    growing = False
    if prev_size is not None and size > prev_size:
        growing = True
    elif (now - mtime) < 4.0 and size > 0:
        growing = True

    return str(newest), size, growing


def get_recent_recordings(
    limit: int = 3,
    active_path: Optional[str] = None,
    active_size: Optional[int] = None,
    active_growing: Optional[bool] = None,
    is_active: bool = False,
) -> list[RecordingItem]:
    """Return the last `limit` recordings across recording directories, ordered by newest first."""
    seen: dict[str, Path] = {}
    dirs_to_check: list[Path] = list(RECORDING_DIRS)
    if active_path:
        act_p = Path(active_path)
        try:
            if act_p.parent.is_dir() and act_p.parent not in dirs_to_check:
                dirs_to_check.insert(0, act_p.parent)
        except OSError:
            pass

    for d in dirs_to_check:
        if not d.is_dir():
            continue
        try:
            for f in d.iterdir():
                if f.name.startswith("."):
                    continue
                if not f.is_file():
                    continue
                if f.suffix.lower() not in (".wav", ".aiff", ".aif", ".mp3", ".flac", ".m4a", ".ogg"):
                    continue
                try:
                    seen[str(f.resolve())] = f
                except OSError:
                    pass
        except OSError:
            continue

    if active_path:
        act_p = Path(active_path)
        try:
            if act_p.is_file():
                seen[str(act_p.resolve())] = act_p
        except OSError:
            pass

    items: list[RecordingItem] = []
    now = time.time()
    act_resolved = None
    if active_path:
        try:
            act_resolved = str(Path(active_path).resolve())
        except OSError:
            act_resolved = str(active_path)

    for f in seen.values():
        try:
            st = f.stat()
            f_size = st.st_size
            f_mtime = st.st_mtime
            resolved = str(f.resolve())
            this_is_active = False
            this_is_growing = False

            if act_resolved and (resolved == act_resolved or str(f) == active_path):
                this_is_active = is_active
                this_is_growing = bool(active_growing)
                if active_size is not None:
                    f_size = active_size
                if is_active:
                    f_mtime = max(f_mtime, now)

            items.append(
                RecordingItem(
                    path=str(f),
                    name=f.name,
                    size=f_size,
                    mtime=f_mtime,
                    is_active=this_is_active,
                    is_growing=this_is_growing,
                )
            )
        except OSError:
            continue

    items.sort(key=lambda x: x.mtime, reverse=True)
    return items[:limit]


def is_recording_active(pid: Optional[int] = None) -> bool:
    """Best-effort check if Traktor is currently writing an audio file."""
    if pid is None:
        pid = find_traktor_pid()

    # macOS / Linux lsof check
    if pid and not IS_WINDOWS and shutil.which("lsof"):
        out = run(["lsof", "-p", str(pid)], timeout=3.0)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 9:
                fd = parts[3]
                path = parts[-1]
                if "w" in fd and (
                    path.endswith(".wav")
                    or path.endswith(".aiff")
                    or path.endswith(".aif")
                    or "STREAM_OF_FREQUENCY" in path
                    or "/Recordings/" in path
                ):
                    return True

    # Growth / modification check in recording directories
    now = time.time()
    for d in RECORDING_DIRS:
        if not d.is_dir():
            continue
        try:
            for f in d.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in (".wav", ".aiff", ".aif", ".mp3"):
                    continue
                try:
                    st = f.stat()
                    if now - st.st_mtime < 4.0 and st.st_size > 0:
                        return True
                except OSError:
                    continue
        except OSError:
            continue
    return False


def click_traktor_menu_item(menu_name: str, item_name: str) -> tuple[bool, str]:
    """macOS: Activate Traktor and click menu bar item via System Events."""
    if not IS_MACOS:
        return False, "Menu clicking is currently supported natively on macOS via System Events"
    menu_a = menu_name.replace("\\", "\\\\").replace('"', '\\"')
    item_a = item_name.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "System Events"
  set procs to every process whose bundle identifier is "{TRAKTOR_BUNDLE_ID}"
  if (count of procs) is 0 then
    set procs to every process whose name is "{TRAKTOR_PROC}"
  end if
  if (count of procs) is 0 then
    return "ERROR: Traktor is not running"
  end if
  set proc to item 1 of procs
  set frontmost of proc to true
  delay 0.25
  tell proc
    try
      click menu item "{item_a}" of menu "{menu_a}" of menu bar 1
      return "OK: clicked {menu_a} > {item_a}"
    on error errMsg number errNum
      return "ERROR: (" & errNum & ") " & errMsg
    end try
  end tell
end tell
'''
    ok, msg = run_osascript(script, timeout=12.0)
    if not ok or msg.startswith("ERROR:"):
        return False, msg
    return True, msg


def click_traktor_menu_item_fuzzy(want_start: bool) -> tuple[bool, str]:
    """macOS: Fuzzy scan Traktor menu bar items for recording controls."""
    if not IS_MACOS:
        return False, "Menu scanning is supported on macOS via Accessibility"
    script = f'''
tell application "System Events"
  set procs to every process whose bundle identifier is "{TRAKTOR_BUNDLE_ID}"
  if (count of procs) is 0 then
    set procs to every process whose name is "{TRAKTOR_PROC}"
  end if
  if (count of procs) is 0 then return "ERROR: Traktor is not running"
  set proc to item 1 of procs
  set frontmost of proc to true
  delay 0.25
  set wantStart to {"true" if want_start else "false"}
  tell proc
    set startHit to ""
    set stopHit to ""
    set toggleHit to ""
    try
      set menuNames to name of every menu bar item of menu bar 1
    on error errMsg
      return "ERROR: cannot read menu bar: " & errMsg
    end try
    repeat with mName in menuNames
      set mNameText to mName as text
      try
        set itemNames to name of every menu item of menu mNameText of menu bar 1
        repeat with iName in itemNames
          set iText to iName as text
          if iText is not "missing value" and iText is not "" then
            set lowerI to my toLower(iText)
            if lowerI contains "record" then
              if lowerI contains "stop" then
                if stopHit is "" then set stopHit to mNameText & "||" & iText
              else if lowerI contains "start" then
                if startHit is "" then set startHit to mNameText & "||" & iText
              else if lowerI contains "audio recorder on" or lowerI is "record" then
                if toggleHit is "" then set toggleHit to mNameText & "||" & iText
              end if
            end if
          end if
        end repeat
      end try
    end repeat
    set target to ""
    if wantStart then
      if startHit is not "" then set target to startHit
      else if toggleHit is not "" then set target to toggleHit
    else
      if stopHit is not "" then set target to stopHit
      else if toggleHit is not "" then set target to toggleHit
    end if
    if target is "" then
      return "ERROR: no recording menu item found in Traktor."
    end if
    set AppleScript's text item delimiters to "||"
    set parts to text items of target
    set AppleScript's text item delimiters to ""
    set menuName to item 1 of parts
    set itemName to item 2 of parts
    try
      click menu item itemName of menu menuName of menu bar 1
      return "OK: clicked " & menuName & " > " & itemName
    on error errMsg number errNum
      return "ERROR: (" & errNum & ") " & errMsg
    end try
  end tell
end tell

on toLower(t)
  set low to do shell script "printf %s " & quoted form of t & " | tr '[:upper:]' '[:lower:]'"
  return low
end toLower
'''
    ok, msg = run_osascript(script, timeout=18.0)
    if not ok or msg.startswith("ERROR:"):
        return False, msg
    return True, msg


def control_recording_windows(action: str) -> tuple[bool, str]:
    """Windows 10 & 11: Activate Traktor and send Audio Recorder key / UI Automation."""
    ps_script = f'''
$wshell = New-Object -ComObject WScript.Shell
$proc = Get-Process -Name Traktor* -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) {{
    Write-Output "ERROR: Traktor is not running"
    exit 1
}}
if ($wshell.AppActivate($proc.Id)) {{
    Start-Sleep -Milliseconds 250
    # Send mapped Audio Recorder key or standard shortcut
    $wshell.SendKeys("^(r)")
    Write-Output "OK: Sent Audio Recorder toggle signal to Traktor (PID $($proc.Id))"
    exit 0
}} else {{
    Write-Output "ERROR: Could not activate Traktor window"
    exit 1
}}
'''
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        out = res.stdout.strip()
        if res.returncode == 0 and out.startswith("OK:"):
            return True, f"Windows {action} signal dispatched: {out}"
        return False, out or res.stderr.strip()
    except Exception as e:
        return False, f"Windows recording dispatch failed: {e}"


def menu_control_recording(action: str) -> tuple[bool, str]:
    """Start, stop, or toggle Traktor recording across macOS, Windows, and Linux."""
    action = action.lower().strip()
    if action not in ("start", "stop", "toggle"):
        return False, f"Unknown action {action!r}; use start|stop|toggle"

    pid = find_traktor_pid()
    if not pid:
        return False, "Traktor is not running"

    active = is_recording_active(pid)
    if action == "toggle":
        want_start = not active
    elif action == "start":
        if active:
            return True, "Already recording (active file write / growth detected)"
        want_start = True
    else:  # stop
        want_start = False

    # 1. macOS Menu Automation
    if IS_MACOS:
        candidates = RECORD_START_MENU_CANDIDATES if want_start else RECORD_STOP_MENU_CANDIDATES
        errors: list[str] = []
        for menu_name, item_name in candidates:
            ok, msg = click_traktor_menu_item(menu_name, item_name)
            if ok:
                verb = "Started" if want_start else "Stopped"
                return True, f"{verb} via menu: {msg}"
            errors.append(f"{menu_name} > {item_name}: {msg}")

        ok, msg = click_traktor_menu_item_fuzzy(want_start=want_start)
        if ok:
            verb = "Started" if want_start else "Stopped"
            return True, f"{verb} via menu scan: {msg}"

        hint = (
            "Could not find a recording menu item. "
            "Grant Accessibility to this terminal, and/or in Traktor: "
            "Preferences → Controller Manager → add a Keyboard device → "
            "map a key to 'Audio Recorder On', then re-run."
        )
        return False, hint

    # 2. Windows 10 & 11 Automation
    if IS_WINDOWS:
        return control_recording_windows(action)

    # 3. Linux / generic
    return False, f"Direct menu dispatch not supported on this platform. Map a keyboard shortcut in Traktor Controller Manager."


def human_size(n: Optional[int]) -> str:
    if n is None:
        return "?"
    val = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.2f} PB"


def cpu_bar(pct: float, width: int = 20, theme: Optional[ThemeColors] = None) -> str:
    fill = int(min(pct, 100.0) / 100.0 * width)
    t = theme or get_theme()
    if pct < 50.0:
        bar_col = t.green
    elif pct < 80.0:
        bar_col = t.yellow
    else:
        bar_col = t.red
    filled_part = f"{bar_col}{'#' * fill}{t.reset}"
    empty_part = f"{t.text_dim}{'-' * (width - fill)}{t.reset}"
    return f"{t.border}[{t.reset}{filled_part}{empty_part}{t.border}]{t.reset}"


def clear_screen() -> None:
    if IS_WINDOWS:
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def format_recent_recordings(
    recordings: list[RecordingItem],
    box_w: int,
    term_h: int = 30,
    theme: Optional[ThemeColors] = None,
) -> list[str]:
    t = theme or get_theme()
    lines = []
    lines.append(f"{t.border}{'-' * box_w}{t.reset}")
    lines.append(f"  {t.bold}{t.primary}LAST 3 RECORDINGS (Newest at Top){t.reset}")
    lines.append(f"{t.border}{'-' * box_w}{t.reset}")
    if not recordings:
        lines.append(f"  {t.text_dim}(No audio recordings found in recording directories){t.reset}")
        return lines

    first_dir = str(Path(recordings[0].path).parent)
    show_all_paths = term_h >= 40

    for idx, r in enumerate(recordings, 1):
        status_badge = ""
        if r.is_active:
            if r.is_growing:
                status_badge = f"  {t.bold}{t.green}[● LIVE: Growing]{t.reset}"
            else:
                status_badge = f"  {t.bold}{t.red}[● LIVE: Active Write]{t.reset}"

        date_str = (
            datetime.fromtimestamp(r.mtime).strftime("%Y-%m-%d %H:%M:%S")
            if r.mtime
            else ""
        )
        lines.append(f"  {t.bold}{t.accent}[{idx}]{t.reset} {t.bold}{t.text}{r.name}{t.reset}{status_badge}")
        lines.append(f"      {t.secondary}Size:{t.reset} {t.text}{human_size(r.size):<10}{t.reset}  {t.border}│{t.reset}  {t.secondary}Modified:{t.reset} {t.text_dim}{date_str}{t.reset}")
        if show_all_paths or idx == 1 or str(Path(r.path).parent) != first_dir:
            lines.append(f"      {t.text_dim}Path: {r.path}{t.reset}")

    return lines


def render(s: Snapshot, theme: Optional[ThemeColors] = None) -> str:
    t = theme or get_theme(getattr(s, "theme_id", None))
    lines = []
    w, h = shutil.get_terminal_size((100, 30))
    box_w = min(w, 82)
    term_h = h

    title = "🎛️  TRAKTOR PRO LIVE MONITOR & RECORDER  🎛️"
    lines.append(f"{t.border}{'=' * box_w}{t.reset}")
    lines.append(f"{t.bold}{t.primary}{title.center(box_w)}{t.reset}")
    date_str = s.ts.strftime("%A, %B %d, %Y • %H:%M:%S")
    theme_sub = f"Theme: {t.name}"
    header_sub = f"{date_str}   │   {theme_sub}"
    if len(header_sub) > box_w - 4:
        header_sub = date_str
    lines.append(f"{t.text_dim}{header_sub.center(box_w)}{t.reset}")
    lines.append(f"{t.border}{'=' * box_w}{t.reset}")
    lines.append("")

    if not s.running:
        lines.append(f"  {t.bold}{t.secondary}STATUS{t.reset}     {t.bold}{t.yellow}Traktor is NOT running{t.reset}")
        lines.append("")
        lines.append(f"  {t.text_dim}Start Traktor Pro (macOS, Windows, or Linux) to begin live monitoring.{t.reset}")
        lines.append("")
        lines.extend(format_recent_recordings(s.recent_recordings, box_w, term_h, t))
    else:
        lines.append(f"  {t.bold}{t.secondary}STATUS{t.reset}     {t.bold}{t.green}● RUNNING{t.reset}   {t.text_dim}PID:{t.reset} {t.bold}{t.text}{s.pid}{t.reset}   {t.text_dim}Threads: ≈{t.reset}{t.text}{s.threads}{t.reset}")
        lines.append(
            f"  {t.bold}{t.secondary}CPU{t.reset}        {t.bold}{t.text}{s.cpu:5.1f}%{t.reset}  {cpu_bar(s.cpu, 20, t)}   "
            f"{t.secondary}RAM:{t.reset} {t.text}{s.rss_mb:6.1f} MB RSS{t.reset}   {t.secondary}CPU Time:{t.reset} {t.text_dim}{s.cpu_time}{t.reset}"
        )
        lines.append("")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.primary}AUDIO INTERFACE & HARDWARE{t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}Traktor Device{t.reset}      {t.text}{s.device_traktor or '?'}{t.reset}")
        lines.append(
            f"  {t.bold}{t.secondary}Driver / Clock{t.reset}      {t.text}{s.driver or '?'}{t.reset}  {t.border}│{t.reset}  "
            f"{t.secondary}Rate:{t.reset} {t.text}{s.sample_rate} Hz{t.reset}  {t.border}│{t.reset}  "
            f"{t.secondary}Buffer/Latency:{t.reset} {t.text}{s.latency}{t.reset}"
        )
        lines.append(f"  {t.bold}{t.secondary}System Default IN{t.reset}   {t.text_dim}{s.system_in}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}System Default OUT{t.reset}  {t.text_dim}{s.system_out}{t.reset}")
        lines.append("")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.primary}LOADED / ACTIVE TRACKS (Decks with Media Open){t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        if s.loaded_tracks:
            deck_colors = [t.secondary, t.accent, t.primary, t.green]
            for i, trk in enumerate(s.loaded_tracks, 1):
                col = deck_colors[(i - 1) % len(deck_colors)]
                d_name = f"Deck {chr(64+i) if i<=4 else str(i)}"
                lines.append(f"  {t.bold}{col}[{d_name}]{t.reset} {t.text}{trk}{t.reset}")
        else:
            lines.append(f"  {t.text_dim}(No audio tracks actively open or loaded on decks){t.reset}")
        lines.append("")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.primary}AUDIO RECORDER STATUS{t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        rec_badge = f"{t.bold}{t.red}● RECORDING (Active File Write){t.reset}" if s.recording_active else f"{t.text_dim}○ IDLE (Not Recording){t.reset}"
        lines.append(f"  {t.bold}{t.secondary}State{t.reset}    {rec_badge}")
        if s.recording_prefix:
            lines.append(f"  {t.bold}{t.secondary}Prefix{t.reset}   {t.text}{s.recording_prefix}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}Control{t.reset}  {t.bold}{t.green}[s]{t.reset} Start Rec  {t.border}│{t.reset}  {t.bold}{t.red}[x]{t.reset} Stop Rec  {t.border}│{t.reset}  {t.bold}{t.yellow}[t]{t.reset} Toggle Rec")
        lines.append("")
        lines.extend(format_recent_recordings(s.recent_recordings, box_w, term_h, t))

    if s.last_action:
        lines.append("")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.accent}LAST ACTION{t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.text}{s.last_action}{t.reset}")

    if s.notes:
        lines.append("")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.yellow}SYSTEM NOTES{t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        for n in s.notes:
            lines.append(f"  {t.yellow}•{t.reset} {t.text_dim}{n}{t.reset}")

    lines.append("")
    lines.append(f"{t.border}{'-' * box_w}{t.reset}")
    lines.append(
        f"  {t.bold}{t.accent}HOTKEYS:{t.reset}  "
        f"{t.bold}{t.primary}[Q]{t.reset} Quit  {t.border}│{t.reset}  "
        f"{t.bold}{t.primary}[R]{t.reset} Refresh  {t.border}│{t.reset}  "
        f"{t.bold}{t.secondary}[C]{t.reset} Theme ({t.id})  {t.border}│{t.reset}  "
        f"{t.bold}{t.green}[S]{t.reset} Start  {t.border}│{t.reset}  "
        f"{t.bold}{t.red}[X]{t.reset} Stop  {t.border}│{t.reset}  "
        f"{t.bold}{t.yellow}[T]{t.reset} Toggle"
    )
    lines.append(f"{t.border}{'=' * box_w}{t.reset}")
    return "\n".join(lines)


def take_snapshot(prev_rec_size: Optional[int], theme_id: Optional[str] = None) -> Snapshot:
    tid = resolve_theme_id(theme_id or _ACTIVE_THEME_ID)
    t = get_theme(tid)
    s = Snapshot(ts=datetime.now(), theme_id=tid, theme_name=t.name)
    settings_path = find_settings()
    if settings_path:
        conf = parse_settings(settings_path)
        s.device_traktor = conf["device"]
        s.sample_rate = conf["sample_rate"]
        s.latency = conf["latency"]
        s.driver = conf["driver"]
        s.recording_prefix = conf["recording_prefix"]
    else:
        s.notes.append("Traktor Settings.tsi not found (using system defaults)")

    try:
        s.system_in, s.system_out = system_audio_defaults()
    except Exception as e:
        s.notes.append(f"Audio device query notice: {e}")

    pid = find_traktor_pid()
    if not pid:
        s.running = False
        path, size, growing = detect_recording_by_growth(s.recording_prefix, prev_rec_size)
        s.recording, s.recording_size, s.recording_growing = path, size, growing
        s.recent_recordings = get_recent_recordings(
            limit=3,
            active_path=s.recording,
            active_size=s.recording_size,
            active_growing=s.recording_growing,
            is_active=False,
        )
        if not s.recording and s.recent_recordings:
            s.recording = s.recent_recordings[0].path
            s.recording_size = s.recent_recordings[0].size
        return s

    s.running = True
    s.pid = pid
    st = process_stats(pid)
    s.cpu = st["cpu"]
    s.mem_pct = st["mem"]
    s.rss_mb = st["rss_mb"]
    s.cpu_time = st["time"]
    s.threads = st["threads"]

    tracks, rec, rec_size = lsof_tracks_and_recording(pid)
    s.loaded_tracks = tracks
    if rec:
        s.recording = rec
        s.recording_size = rec_size
        if prev_rec_size is not None and rec_size is not None:
            s.recording_growing = rec_size > prev_rec_size
    else:
        path, size, growing = detect_recording_by_growth(s.recording_prefix, prev_rec_size)
        s.recording, s.recording_size, s.recording_growing = path, size, growing

    s.recording_active = is_recording_active(pid)
    if s.recording_growing is True:
        s.recording_active = True

    if s.recording_active and s.recording_growing is None and s.recording:
        try:
            s.recording_growing = (time.time() - os.path.getmtime(s.recording)) < 5.0
        except OSError:
            pass

    s.recent_recordings = get_recent_recordings(
        limit=3,
        active_path=s.recording,
        active_size=s.recording_size,
        active_growing=s.recording_growing,
        is_active=s.recording_active,
    )
    if not s.recording and s.recent_recordings:
        s.recording = s.recent_recordings[0].path
        s.recording_size = s.recent_recordings[0].size

    return s



def main() -> int:
    ap = argparse.ArgumentParser(
        description="Traktor live monitor (CPU, tracks, recording, audio I/O) + recording control (macOS, Windows, Linux)"
    )
    ap.add_argument("--interval", type=float, default=1.0, help="Refresh seconds (default 1)")
    ap.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    ap.add_argument(
        "--start-recording",
        action="store_true",
        help="Start Traktor Audio Recorder, then exit",
    )
    ap.add_argument(
        "--stop-recording",
        action="store_true",
        help="Stop Traktor Audio Recorder, then exit",
    )
    ap.add_argument(
        "--toggle-recording",
        action="store_true",
        help="Toggle Traktor Audio Recorder, then exit",
    )
    ap.add_argument(
        "--theme", "-t",
        type=str,
        default=None,
        help="Color theme name (e.g. dreamworlds, dreamworlds_ultra, cosmic_supernova, cyberpunk, dracula, nord, matrix, solarized, tokyo, monokai, gruvbox, emerald, classic)",
    )
    ap.add_argument(
        "--list-themes",
        action="store_true",
        help="List all 13 available color themes with colored previews, then exit",
    )
    ap.add_argument(
        "--set-theme",
        type=str,
        default=None,
        metavar="THEME",
        help="Set and persist the active color theme, then exit",
    )
    ap.add_argument(
        "--save-theme",
        action="store_true",
        help="Persist the selected theme to ~/.config/mix-manager/theme",
    )
    ap.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors (monochrome white-on-black)",
    )
    ap.add_argument(
        "--no-launch",
        action="store_true",
        help="Do not automatically launch Traktor if not running",
    )
    ap.add_argument(
        "--list-menus",
        action="store_true",
        help="List Traktor menu bar items (debug macOS) and exit",
    )
    args = ap.parse_args()

    if args.list_themes:
        print_theme_list()
        return 0

    if args.set_theme:
        tid = resolve_theme_id(args.set_theme)
        t = get_theme(tid)
        if save_active_theme(tid):
            print(f"\033[1;32m✓\033[0m Traktor Monitor theme set to: {t.primary}{t.name}{t.reset} ({tid})")
        else:
            print(f"\033[1;31m✗\033[0m Failed to save theme to ~/.config/mix-manager/theme", file=sys.stderr)
            return 1
        return 0

    if args.list_menus:
        if IS_MACOS:
            ok, msg = list_traktor_menu_items()
            print(msg)
            return 0 if ok and not msg.startswith("ERROR:") else 1
        else:
            print("Menu listing is only supported on macOS.")
            return 0

    rec_flags = sum(
        bool(x) for x in (args.start_recording, args.stop_recording, args.toggle_recording)
    )
    if rec_flags > 1:
        print("Use only one of --start-recording / --stop-recording / --toggle-recording", file=sys.stderr)
        return 2

    if args.start_recording:
        ok, msg = menu_control_recording("start")
        print(msg)
        return 0 if ok else 1
    if args.stop_recording:
        ok, msg = menu_control_recording("stop")
        print(msg)
        return 0 if ok else 1
    if args.toggle_recording:
        ok, msg = menu_control_recording("toggle")
        print(msg)
        return 0 if ok else 1

    # Resolve active theme
    global _ACTIVE_THEME_ID
    if args.theme:
        active_theme_id = resolve_theme_id(args.theme)
        if args.save_theme:
            save_active_theme(active_theme_id)
    else:
        active_theme_id = load_saved_theme()
    _ACTIVE_THEME_ID = active_theme_id
    active_theme = get_theme(active_theme_id, no_color=args.no_color)

    if not args.no_launch:
        ensure_traktor_running()

    prev_size: Optional[int] = None
    last_action = ""

    if args.once:
        s = take_snapshot(prev_size, active_theme_id)
        print(render(s, active_theme))
        return 0

    # Cross-platform live interactive loop
    # 1. Windows: msvcrt non-blocking keys
    if IS_WINDOWS:
        try:
            import msvcrt
            while True:
                s = take_snapshot(prev_size, active_theme_id)
                s.last_action = last_action
                if s.recording_size is not None:
                    prev_size = s.recording_size
                clear_screen()
                print(render(s, active_theme))

                end = time.time() + max(0.3, args.interval)
                while time.time() < end:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        try:
                            ch_str = ch.decode("utf-8", errors="ignore")
                        except Exception:
                            ch_str = str(ch)
                        if ch_str in ("q", "Q", "\x03"):
                            return 0
                        if ch_str in ("r", "R"):
                            break
                        if ch_str in ("c", "C", "m", "M"):
                            theme_keys = list(THEMES.keys())
                            cur_idx = theme_keys.index(active_theme_id) if active_theme_id in theme_keys else 0
                            active_theme_id = theme_keys[(cur_idx + 1) % len(theme_keys)]
                            _ACTIVE_THEME_ID = active_theme_id
                            active_theme = get_theme(active_theme_id, no_color=args.no_color)
                            save_active_theme(active_theme_id)
                            last_action = f"Theme switched to: {active_theme.name}"
                            break
                        if ch_str in ("s", "S"):
                            ok, msg = menu_control_recording("start")
                            last_action = ("OK: " if ok else "FAIL: ") + msg
                            break
                        if ch_str in ("x", "X"):
                            ok, msg = menu_control_recording("stop")
                            last_action = ("OK: " if ok else "FAIL: ") + msg
                            break
                        if ch_str in ("t", "T"):
                            ok, msg = menu_control_recording("toggle")
                            last_action = ("OK: " if ok else "FAIL: ") + msg
                            break
                    time.sleep(0.05)
        except KeyboardInterrupt:
            return 0

    # 2. Unix (macOS / Linux): termios & tty
    try:
        import select
        import tty
        import termios

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        raw = True
    except Exception:
        raw = False
        old = None
        fd = None

    try:
        while True:
            s = take_snapshot(prev_size, active_theme_id)
            s.last_action = last_action
            if s.recording_size is not None:
                prev_size = s.recording_size
            clear_screen()
            print(render(s, active_theme))

            end = time.time() + max(0.3, args.interval)
            while time.time() < end:
                if raw and fd is not None:
                    r, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch in ("q", "Q", "\x03"):
                            return 0
                        if ch in ("r", "R"):
                            break
                        if ch in ("c", "C", "m", "M"):
                            theme_keys = list(THEMES.keys())
                            cur_idx = theme_keys.index(active_theme_id) if active_theme_id in theme_keys else 0
                            active_theme_id = theme_keys[(cur_idx + 1) % len(theme_keys)]
                            _ACTIVE_THEME_ID = active_theme_id
                            active_theme = get_theme(active_theme_id, no_color=args.no_color)
                            save_active_theme(active_theme_id)
                            last_action = f"Theme switched to: {active_theme.name}"
                            break
                        if ch in ("s", "S"):
                            ok, msg = menu_control_recording("start")
                            last_action = ("OK: " if ok else "FAIL: ") + msg
                            break
                        if ch in ("x", "X"):
                            ok, msg = menu_control_recording("stop")
                            last_action = ("OK: " if ok else "FAIL: ") + msg
                            break
                        if ch in ("t", "T"):
                            ok, msg = menu_control_recording("toggle")
                            last_action = ("OK: " if ok else "FAIL: ") + msg
                            break
                else:
                    time.sleep(min(0.2, end - time.time()))
    except KeyboardInterrupt:
        return 0
    finally:
        if raw and old is not None and fd is not None:
            try:
                import termios
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass
        print("\nTraktor Live Monitor closed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
