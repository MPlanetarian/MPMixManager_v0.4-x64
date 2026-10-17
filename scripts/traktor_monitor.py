#!/usr/bin/env python3
"""
scripts/traktor_monitor.py - Ultra High-Performance Cross-Platform Traktor Live Monitor & Recorder Control
Optimized for low-spec / slow systems with zero subprocess churn, /proc direct I/O, and aggressive caching.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows" or os.name == "nt" or "microsoft" in platform.release().lower()
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    try:
        os.system("")
    except Exception:
        pass

TRAKTOR_PROC = "Traktor"
TRAKTOR_BUNDLE_ID = "com.native-instruments.Traktor"
AUDIO_EXTS = (".mp3", ".flac", ".aiff", ".aif", ".wav", ".m4a", ".stem.mp4", ".ogg", ".aac")
THEME_CONFIG_FILE = Path.home() / ".config/mix-manager/theme"

SETTINGS_CANDIDATES = [
    Path.home() / f"Documents/Native Instruments/Traktor {v}/Traktor Settings.tsi"
    for v in ("3.11.1", "3", "Pro 3", "Pro 4", "3.10.0", "2")
]

RECORDING_DIRS = [
    Path.home() / "Documents/MPlanetarian/Documents/TRAKTOR_RECORDINGS",
    Path.home() / "Documents/MPlanetarian/M_PRODUCTION/STREAM_OF_FREQUENCY_RECORDINGS_TRAKTOR_2026",
    Path.home() / "Music/Traktor/Recordings",
    *(Path.home() / f"Documents/Native Instruments/Traktor {v}/Recordings" for v in ("3.11.1", "3", "Pro 3", "Pro 4")),
    Path.home() / "Documents/Native Instruments/Traktor 3.11.1",
    Path("D:/MIX_ARCHIVE/CONVERTED_WAV_FILES"),
    Path("D:/MIX_ARCHIVE"),
    Path("/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE/CONVERTED_WAV_FILES"),
    Path("/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE"),
]
if os.environ.get("MIX_ARCHIVE_DIR"):
    _ea = Path(os.environ["MIX_ARCHIVE_DIR"])
    RECORDING_DIRS.extend([_ea / "CONVERTED_WAV_FILES", _ea])

RECORD_START_MENU_CANDIDATES: list[tuple[str, str]] = [
    (m, "Start Recording") for m in ("File", "Deck", "View", "Traktor")
] + [("File", "Start Audio Recording"), ("File", "Record")] + [
    (m, "Audio Recorder On") for m in ("File", "Deck", "View")
]

RECORD_STOP_MENU_CANDIDATES: list[tuple[str, str]] = [
    (m, "Stop Recording") for m in ("File", "Deck", "View", "Traktor")
] + [("File", "Stop Audio Recording")] + [
    (m, "Audio Recorder On") for m in ("File", "Deck", "View")
]

THEMES: dict[str, tuple[str, str, str, str, str, str, str, str, str, str, str]] = {
    "dreamworlds": ("MPlanetarian Dreamworlds [Default]", "Sweet Hot Pink, Electric Cyan, Amber Gold & Coral Red", "#f72585", "#00e5ff", "#ffaa00", "#845ec2", "#f0f3f6", "#7f8ba4", "#00f5d4", "#ed254e", "#ffaa00"),
    "dreamworlds_ultra": ("Dreamworlds Ultra MP Mix Manager", "Hot Purple, Traffic Light RGB & Electric Green", "#a64dff", "#00ff00", "#ff9933", "#7928ca", "#d1d1e0", "#9999ff", "#00ff00", "#ff0000", "#ff9933"),
    "cosmic_supernova": ("Cosmic Supernova [Special Edition]", "Aurora Aquamarine, Nebula Orchid, Solar Flare & Supernova Crimson", "#00f5d4", "#e056fd", "#fee440", "#5e60ce", "#e2e8f0", "#7c8ba1", "#00f5d4", "#ff3366", "#fee440"),
    "cyberpunk": ("Cyberpunk 2077", "Neon Hot Pink, Electric Cyan & High-Volt Yellow", "#ff0055", "#00ffff", "#ffff00", "#ff0055", "#e0ffff", "#708090", "#00ff9f", "#ff0055", "#ffff00"),
    "dracula": ("Dracula", "Vampiric Purple, Coral Pink, Cyan & Neon Green", "#bd93f9", "#8be9fd", "#ff79c6", "#6272a4", "#f8f8f2", "#6272a4", "#50fa7b", "#ff5555", "#f1fa8c"),
    "nord": ("Nord Frost", "Arctic Slate, Frost Polar Ice & Sage Aurora", "#88c0d0", "#81a1c1", "#a3be8c", "#5e81ac", "#eceff4", "#929cb0", "#a3be8c", "#bf616a", "#ebcb8b"),
    "matrix": ("The Matrix", "Pure Phosphor Green, Terminal Crimson & Mint", "#00ff66", "#a6ff00", "#00cc44", "#008f39", "#d4ffd4", "#337733", "#00ff66", "#ff3333", "#a6ff00"),
    "solarized": ("Solarized Dark", "Solar Cyan, Solar Blue, Warm Amber & Terracotta", "#2aa198", "#268bd2", "#b58900", "#073642", "#93a1a1", "#657b83", "#859900", "#dc322f", "#b58900"),
    "tokyo": ("Tokyo Night", "Deep Violet, Tokyo Blue, Lavender & Coral", "#7aa2f7", "#bb9af7", "#7dcfff", "#565f89", "#c0caf5", "#565f89", "#9ece6a", "#f7768e", "#e0af68"),
    "monokai": ("Monokai Pro", "Electric Pink, Vivid Blue, Lime & Tangerine", "#f92672", "#66d9ef", "#a6e22e", "#75715e", "#f8f8f2", "#75715e", "#a6e22e", "#f92672", "#fd971f"),
    "gruvbox": ("Gruvbox Dark", "Warm Earth, Gold, Dusty Orange & Forest Sage", "#fabd2f", "#fe8019", "#83a598", "#665c54", "#ebdbb2", "#928374", "#b8bb26", "#fb4934", "#fabd2f"),
    "emerald": ("Emerald Isle", "Deep Ocean, Spring Emerald, Mint & Rose", "#10b981", "#06b6d4", "#34d399", "#047857", "#ecfdf5", "#6ee7b7", "#10b981", "#f43f5e", "#fbbf24"),
    "classic": ("Classic Monochrome", "High-Contrast Monochrome / Standard ANSI", "#ffffff", "#cccccc", "#aaaaaa", "#777777", "#ffffff", "#666666", "#ffffff", "#ffffff", "#ffffff"),
    "retro_terminal": ("Old Style Unix Terminal Retro Mode (White on Black)", "Monochrome VT100: White Text Only on Black Background", "#ffffff", "#ffffff", "#ffffff", "#777777", "#ffffff", "#888888", "#ffffff", "#ffffff", "#ffffff"),
}

THEME_ALIASES: dict[str, str] = {
    "default": "dreamworlds", "mplanetarian": "dreamworlds", "mplanetarian_dreamworlds": "dreamworlds",
    "ultra": "dreamworlds_ultra", "dreamworlds ultra": "dreamworlds_ultra", "dreamworlds-ultra": "dreamworlds_ultra",
    "hotpurple": "dreamworlds_ultra", "trafficlight": "dreamworlds_ultra", "supernova": "cosmic_supernova",
    "cosmic": "cosmic_supernova", "cosmic supernova": "cosmic_supernova", "cosmic-supernova": "cosmic_supernova",
    "tokyo_night": "tokyo", "tokyo-night": "tokyo", "tokyonight": "tokyo",
    "monochrome": "classic", "mono": "classic", "white": "classic", "ansi": "classic", "none": "classic", "off": "classic",
    "retro_terminal": "retro_terminal", "unix_terminal": "retro_terminal", "retro_unix": "retro_terminal",
    "old_style_unix": "retro_terminal", "unix_retro": "retro_terminal", "white_on_black": "retro_terminal",
    "retro": "retro_terminal", "terminal": "retro_terminal", "vt100": "retro_terminal",
    "old style unix terminal retro mode (white on black)": "retro_terminal",
    "old style unix terminal": "retro_terminal",
}

class ThemeColors:
    def __init__(self, tid: str, enabled: bool = True):
        self.id = tid
        row = THEMES.get(tid, THEMES["dreamworlds"])
        self.name, self.desc = row[0], row[1]
        c = [f"\033[38;2;{int(x[1:3],16)};{int(x[3:5],16)};{int(x[5:7],16)}m" if enabled else "" for x in row[2:]]
        self.primary, self.secondary, self.accent, self.border, self.text, self.text_dim, self.green, self.red, self.yellow = c
        self.reset, self.bold, self.dim = ("\033[0m", "\033[1m", "\033[2m") if enabled else ("", "", "")

_ACTIVE_THEME_ID = "dreamworlds"

def resolve_theme_id(name: Optional[str]) -> str:
    if not name: return "dreamworlds"
    clean = name.strip().lower()
    return clean if clean in THEMES else THEME_ALIASES.get(clean, next((k for k in THEMES if k in clean or clean in k), "dreamworlds"))

def get_theme(theme_id: Optional[str] = None, no_color: bool = False) -> ThemeColors:
    tid = resolve_theme_id(theme_id or _ACTIVE_THEME_ID)
    color_enabled = not no_color and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
    return ThemeColors(tid, enabled=color_enabled)

def load_saved_theme() -> str:
    for ev in ("TRAKTOR_MONITOR_THEME", "CURRENT_THEME", "MIX_MANAGER_THEME"):
        v = os.environ.get(ev, "").strip()
        if v: return resolve_theme_id(v)
    try:
        return resolve_theme_id(THEME_CONFIG_FILE.read_text("utf-8").strip())
    except Exception:
        return "dreamworlds"

def save_active_theme(tid: str) -> bool:
    try:
        THEME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        THEME_CONFIG_FILE.write_text(tid + "\n", "utf-8")
        return True
    except Exception:
        return False

def print_theme_list():
    act = load_saved_theme()
    print(f"\n\033[1m🎛️  Traktor Live Monitor — Available Color Themes ({len(THEMES)} Themes):\033[0m\n")
    for tid, tinfo in THEMES.items():
        t = get_theme(tid)
        sample = f"{t.primary}■■■ {t.secondary}■■■ {t.accent}■■■ {t.green}■■■ {t.red}■■■{t.reset}"
        mark = f" \033[1m{t.green}★ ACTIVE\033[0m" if tid == act else ""
        print(f"  \033[1m{t.secondary}{tid:<18}\033[0m  {sample}  \033[1m{t.text}{tinfo[0]}\033[0m{mark}\n  {' '*18}  {t.text_dim}{tinfo[1]}\033[0m\n")
    print("Switch themes live using the \033[1;36m[C]\033[0m key in Traktor Monitor, or launch with: \033[1;32m--theme <name>\033[0m\n")

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
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False).stdout or ""
    except Exception:
        return ""

def run_osascript(script: str, timeout: float = 12.0) -> tuple[bool, str]:
    if not IS_MACOS: return False, "osascript only available on macOS"
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout, check=False)
        out, err = (r.stdout or "").strip(), (r.stderr or "").strip()
        return (r.returncode == 0, out if r.returncode == 0 else (err or out or f"osascript exit {r.returncode}"))
    except Exception as e:
        return False, str(e)

# Zero-churn state caches
_CACHED_PID: Optional[int] = None
_CPU_CACHE: dict[int, tuple[float, float]] = {}
_SETTINGS_PATH_CACHE: Optional[Path] = None
_SETTINGS_CHECK_TIME = 0.0
_SETTINGS_DATA_CACHE: tuple[float, dict] = (0.0, {})
_AUDIO_DEFAULTS_CACHE: tuple[float, tuple[str, str]] = (0.0, ("", ""))
_RECORDINGS_SCAN_CACHE: tuple[float, list[Path], Optional[str], Optional[int], Optional[bool], list[RecordingItem]] = (0.0, [], None, None, None, [])

def find_traktor_pid() -> Optional[int]:
    global _CACHED_PID
    my_pid = os.getpid()
    if _CACHED_PID:
        try:
            if IS_WINDOWS:
                out = run(["tasklist", "/fi", f"PID eq {_CACHED_PID}", "/fo", "csv", "/nh"], timeout=1.0)
                if "traktor" in out.lower(): return _CACHED_PID
            else:
                os.kill(_CACHED_PID, 0)
                if IS_LINUX and os.path.exists(f"/proc/{_CACHED_PID}/cmdline"):
                    with open(f"/proc/{_CACHED_PID}/cmdline", "rb") as f:
                        cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore").lower()
                        if "traktor" in cmd and "traktor_monitor" not in cmd: return _CACHED_PID
                elif IS_MACOS:
                    return _CACHED_PID
        except OSError:
            _CACHED_PID = None

    if IS_LINUX:
        try:
            for entry in os.scandir("/proc"):
                if entry.name.isdigit():
                    p = int(entry.name)
                    if p == my_pid: continue
                    try:
                        with open(f"/proc/{p}/cmdline", "rb") as f:
                            raw = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore").lower()
                        if "traktor" in raw and "traktor_monitor" not in raw:
                            _CACHED_PID = p
                            return p
                    except OSError:
                        pass
        except OSError:
            pass

    if IS_MACOS:
        for cmd in (["pgrep", "-f", "Traktor.app/Contents/MacOS/Traktor$"], ["pgrep", "-i", "-f", "Traktor"]):
            for line in run(cmd).splitlines():
                if line.strip().isdigit() and int(line.strip()) != my_pid:
                    _CACHED_PID = int(line.strip())
                    return _CACHED_PID

    if IS_WINDOWS:
        for img in ("Traktor.exe", "Traktor Pro 3.exe", "Traktor Pro 4.exe", "Traktor Pro.exe"):
            for line in run(["tasklist", "/fi", f"imagename eq {img}", "/fo", "csv", "/nh"], timeout=1.5).splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and parts[1].isdigit():
                    _CACHED_PID = int(parts[1])
                    return _CACHED_PID
        try:
            cmd = ["powershell.exe", "-NoProfile", "-Command", "(Get-Process -Name Traktor* -ErrorAction SilentlyContinue | Select-Object -First 1).Id"]
            out = run(cmd, timeout=2.5).strip()
            if out.isdigit():
                _CACHED_PID = int(out)
                return _CACHED_PID
        except Exception:
            pass
    return None

def open_traktor() -> bool:
    if IS_MACOS:
        for p in ("/Applications/Native Instruments/Traktor Pro 3/Traktor.app", "/Applications/Native Instruments/Traktor Pro 4/Traktor.app", "/Applications/Traktor Pro 3.app", "/Applications/Traktor.app"):
            if os.path.exists(p):
                try: subprocess.Popen(["open", p]); return True
                except Exception: pass
        for cmd in (["open", "-b", TRAKTOR_BUNDLE_ID], *(["open", "-a", a] for a in ("Traktor Pro 3", "Traktor Pro 4", "Traktor"))):
            try:
                if subprocess.run(cmd, capture_output=True, timeout=2.0).returncode == 0: return True
            except Exception: pass
        return False
    if IS_WINDOWS:
        for p in (r"C:\Program Files\Native Instruments\Traktor Pro 4\Traktor.exe", r"C:\Program Files\Native Instruments\Traktor Pro 3\Traktor.exe", r"C:\Program Files\Native Instruments\Traktor 2\Traktor.exe"):
            if os.path.isfile(p):
                try: os.startfile(p); return True
                except Exception:
                    try: subprocess.Popen([p]); return True
                    except Exception: pass
        try: subprocess.Popen(["cmd.exe", "/c", "start", "", "Traktor.exe"]); return True
        except Exception: return False
    if IS_LINUX:
        for cmd in ("traktor", "Traktor"):
            if shutil.which(cmd):
                try: subprocess.Popen([cmd]); return True
                except Exception: pass
    return False

def ensure_traktor_running(timeout: float = 12.0) -> Optional[int]:
    pid = find_traktor_pid()
    if pid: return pid
    print("\n🎛️  Traktor Pro is not currently running.\n🚀 Launching Native Instruments Traktor Pro...")
    if not open_traktor():
        print("⚠️  Could not automatically launch Traktor. Waiting for manual start...\n")
    start_t = time.time()
    while time.time() - start_t < timeout:
        time.sleep(1.0)
        pid = find_traktor_pid()
        if pid:
            print(f"✓ Traktor Pro detected (PID: {pid}). Initializing live monitoring...")
            time.sleep(1.5)
            return pid
        print(f"⏳ Waiting for Traktor Pro to initialize ({int(time.time() - start_t)}s)...", end="\r", flush=True)
    print("")
    return find_traktor_pid()

def process_stats(pid: int) -> dict:
    if IS_LINUX and os.path.exists(f"/proc/{pid}/stat"):
        try:
            with open(f"/proc/{pid}/stat", "r") as f:
                fields = f.read().split(")")[-1].split()
            utime, stime = float(fields[11]), float(fields[12])
            nthr = int(fields[17])
            rss_kb = 0.0
            if os.path.exists(f"/proc/{pid}/status"):
                with open(f"/proc/{pid}/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_kb = float(line.split()[1])
                            break
            now = time.time()
            total_ticks = utime + stime
            cpu = 0.0
            if pid in _CPU_CACHE:
                prev_t, prev_ticks = _CPU_CACHE[pid]
                dt = now - prev_t
                if dt > 0.1:
                    cpu = max(0.0, min(100.0 * (os.cpu_count() or 1), round(((total_ticks - prev_ticks) / 100.0 / dt) * 100.0, 1)))
            _CPU_CACHE[pid] = (now, total_ticks)
            secs = int(total_ticks / 100.0)
            cpu_time = f"{secs//3600:02d}:{(secs%3600)//60:02d}:{secs%60:02d}" if secs >= 3600 else f"{secs//60:02d}:{secs%60:02d}"
            return {"cpu": cpu, "mem": 0.0, "rss_mb": round(rss_kb / 1024.0, 1), "time": cpu_time, "threads": nthr}
        except Exception:
            pass

    if not IS_WINDOWS:
        out = run(["ps", "-p", str(pid), "-o", "%cpu=,%mem=,rss=,time="])
        parts = out.split()
        if len(parts) >= 4:
            try:
                nthr = 0
                if IS_MACOS:
                    nthr = max(0, len([l for l in run(["ps", "-M", "-p", str(pid)]).splitlines() if l.strip()]) - 1)
                elif os.path.isdir(f"/proc/{pid}/task"):
                    nthr = len(os.listdir(f"/proc/{pid}/task"))
                return {"cpu": float(parts[0]), "mem": float(parts[1]), "rss_mb": round(float(parts[2]) / 1024.0, 1), "time": parts[3], "threads": nthr}
            except Exception: pass

    if IS_WINDOWS:
        try:
            ps_cmd = f"$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; if ($p) {{ Write-Output \"$([math]::Round($p.CPU,1))|$([math]::Round($p.WorkingSet64/1MB,1))|$($p.Threads.Count)|$p.CPU\" }}"
            out = run(["powershell.exe", "-NoProfile", "-Command", ps_cmd], timeout=2.0).strip()
            if "|" in out:
                c, m, th, tm = out.split("|", 3)
                return {"cpu": float(c or 0.0), "mem": 0.0, "rss_mb": float(m or 0.0), "time": f"{float(c or 0.0):.1f}s", "threads": int(th or 0)}
        except Exception: pass
    return {"cpu": 0.0, "mem": 0.0, "rss_mb": 0.0, "time": "?", "threads": 0}

def find_settings() -> Optional[Path]:
    global _SETTINGS_PATH_CACHE, _SETTINGS_CHECK_TIME
    now = time.time()
    if _SETTINGS_PATH_CACHE and _SETTINGS_PATH_CACHE.is_file():
        return _SETTINGS_PATH_CACHE
    if now - _SETTINGS_CHECK_TIME < 8.0:
        return _SETTINGS_PATH_CACHE
    _SETTINGS_CHECK_TIME = now
    for p in SETTINGS_CANDIDATES:
        if p.is_file():
            _SETTINGS_PATH_CACHE = p
            return p
    docs = [Path.home() / "Documents/Native Instruments", Path.home() / "Documents"]
    if IS_WINDOWS and os.environ.get("USERPROFILE"):
        docs.append(Path(os.environ["USERPROFILE"]) / "Documents/Native Instruments")
    elif IS_LINUX:
        for wd in (Path.home() / ".wine/drive_c/users", Path.home() / ".var/app/com.usebottles.bottles/data/bottles/bottles"):
            if wd.is_dir():
                for p in wd.glob("**/Native Instruments/**/Traktor Settings.tsi"):
                    if p.is_file():
                        _SETTINGS_PATH_CACHE = p
                        return p
    for base in docs:
        if base.is_dir():
            for p in base.glob("Traktor Settings.tsi"):
                if p.is_file():
                    _SETTINGS_PATH_CACHE = p
                    return p
            for sub in ("Traktor 3.11.1", "Traktor 3", "Traktor Pro 3", "Traktor Pro 4"):
                cand = base / sub / "Traktor Settings.tsi"
                if cand.is_file():
                    _SETTINGS_PATH_CACHE = cand
                    return cand
    return None

def parse_settings(path: Path) -> dict:
    global _SETTINGS_DATA_CACHE
    try:
        mtime = path.stat().st_mtime
        if _SETTINGS_DATA_CACHE[0] == mtime:
            return _SETTINGS_DATA_CACHE[1]
        text = path.read_text("utf-8", errors="replace")
    except OSError:
        return _SETTINGS_DATA_CACHE[1] if _SETTINGS_DATA_CACHE[1] else {"device": "?", "sample_rate": "?", "latency": "?", "driver": "?", "recording_prefix": "", "recording_dir": ""}

    def grab(name: str) -> Optional[str]:
        m = re.search(rf'Name="{re.escape(name)}"[^>]*Value="([^"]*)"', text)
        return m.group(1) if m else None

    info = {
        "device": (grab("Audio.DeviceName.Win") or grab("Audio.DeviceName.Mac") or grab("Audio.DeviceName.ASIO") or grab("Audio.DeviceName.WASAPI") or grab("Audio.DeviceName.DirectSound") or grab("Audio.DeviceName") or "?"),
        "sample_rate": grab("Audio.SampleRate") or grab("Audio.FS.SampleRate") or "?",
        "latency": grab("Audio.Latency") or grab("Audio.FS.Latency") or "?",
        "driver": grab("Audio.DriverName") or "?",
        "recording_prefix": grab("Recording.Prefix") or "",
        "recording_dir": grab("Recording.Directory") or grab("Recording.Path") or "",
    }
    if info["recording_dir"]:
        p = Path(info["recording_dir"])
        if p not in RECORDING_DIRS:
            RECORDING_DIRS.insert(0, p)
    _SETTINGS_DATA_CACHE = (mtime, info)
    return info

def system_audio_defaults() -> tuple[str, str]:
    global _AUDIO_DEFAULTS_CACHE
    now = time.time()
    if now - _AUDIO_DEFAULTS_CACHE[0] < 30.0 and _AUDIO_DEFAULTS_CACHE[1][0]:
        return _AUDIO_DEFAULTS_CACHE[1]

    if IS_MACOS:
        out = run(["system_profiler", "SPAudioDataType"], timeout=6.0)
        din, dout, cur = "?", "?", None
        for line in out.splitlines():
            s = line.strip()
            if s.endswith(":") and not any(s.startswith(k) for k in ("Manufacturer", "Output", "Input", "Current", "Transport", "Default")):
                name = s[:-1].strip()
                if name and name not in ("Audio", "Devices"): cur = name
            if "Default Input Device: Yes" in line and cur: din = cur
            if "Default Output Device: Yes" in line and cur: dout = cur
        _AUDIO_DEFAULTS_CACHE = (now, (din, dout))
        return din, dout

    if IS_WINDOWS:
        try:
            cmd = ["powershell.exe", "-NoProfile", "-Command", "$d = Get-CimInstance Win32_SoundDevice | Select-Object -First 1 -ExpandProperty Name; if ($d) { $d } else { 'Default Audio Device' }"]
            out = run(cmd, timeout=2.0).strip() or "Windows Audio Endpoint"
            _AUDIO_DEFAULTS_CACHE = (now, (out, out))
            return out, out
        except Exception:
            return "Windows Audio Input", "Windows Audio Output"

    if IS_LINUX:
        try:
            p = subprocess.run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"], capture_output=True, text=True, timeout=0.5, check=False)
            if p.returncode == 0 and p.stdout:
                for line in p.stdout.splitlines():
                    if "node.description =" in line:
                        m = re.search(r'node\.description\s*=\s*"([^"]+)"', line)
                        if m:
                            res = ("PipeWire Input", m.group(1).strip())
                            _AUDIO_DEFAULTS_CACHE = (now, res)
                            return res
        except Exception: pass
    return "System Default In", "System Default Out"

def get_latest_traktor_history_tracks() -> list[str]:
    dirs = [Path.home() / f"Documents/Native Instruments/Traktor {v}/History" for v in ("3.11.1", "3", "Pro 3", "Pro 4")]
    if IS_WINDOWS and os.environ.get("USERPROFILE"):
        dirs.append(Path(os.environ["USERPROFILE"]) / "Documents/Native Instruments/Traktor 3.11.1/History")
    files = [f for hd in dirs if hd.is_dir() for f in hd.glob("history_*.nml")]
    if not files: return []
    latest = max(files, key=lambda x: x.stat().st_mtime)
    if time.time() - latest.stat().st_mtime > 14400: return []
    try:
        col = ET.parse(latest).getroot().find("COLLECTION")
        if col is not None:
            tracks = []
            for e in col.findall("ENTRY")[-4:]:
                t, a = e.get("TITLE", "").strip(), e.get("ARTIST", "").strip()
                loc = e.find("LOCATION")
                tracks.append(f"{a} - {t}" if t and a else (t or (loc.get("FILE", "") if loc is not None else "")))
            return tracks
    except Exception: pass
    return []

def lsof_tracks_and_recording(pid: int) -> tuple[list[str], Optional[str], Optional[int]]:
    loaded: list[str] = []
    recording: Optional[str] = None
    rec_size: Optional[int] = None

    if IS_LINUX and os.path.isdir(f"/proc/{pid}/fd"):
        try:
            for entry in os.scandir(f"/proc/{pid}/fd"):
                try:
                    target = os.readlink(entry.path)
                    low = target.lower()
                    if any(low.endswith(ext) for ext in AUDIO_EXTS):
                        if "stream_of_frequency" in low or "recording" in low:
                            recording = target
                            try: rec_size = os.path.getsize(target)
                            except OSError: pass
                        else:
                            name = Path(target).name
                            if name not in loaded: loaded.append(name)
                except OSError: pass
            if loaded or recording:
                return loaded, recording, rec_size
        except OSError: pass

    if not IS_WINDOWS and shutil.which("lsof"):
        out = run(["lsof", "-p", str(pid), "-F", "fn"], timeout=4.0)
        cur_fd = ""
        for line in out.splitlines():
            if line.startswith("f"):
                cur_fd = line[1:]
            elif line.startswith("n"):
                p = line[1:]
                low = p.lower()
                if "/Library/" in p and "Native Instruments" not in p and "STREAM" not in p:
                    if not any(low.endswith(ext) for ext in AUDIO_EXTS): continue
                if any(low.endswith(ext) for ext in AUDIO_EXTS) or low.endswith(".wav"):
                    if "STREAM_OF_FREQUENCY" in p or "/Recordings/" in p or "recording" in low or "w" in cur_fd:
                        recording = p
                        try: rec_size = os.path.getsize(p)
                        except OSError: pass
                    elif any(low.endswith(ext) for ext in AUDIO_EXTS):
                        name = Path(p).name
                        if name not in loaded: loaded.append(name)
        if loaded or recording:
            return loaded, recording, rec_size

    if not loaded:
        loaded = get_latest_traktor_history_tracks()
    return loaded, recording, rec_size

def scan_recordings(
    prev_rec_size: Optional[int],
    active_path: Optional[str] = None,
    active_size: Optional[int] = None,
    is_active: bool = False,
    limit: int = 3,
) -> tuple[Optional[str], Optional[int], Optional[bool], list[RecordingItem]]:
    global _RECORDINGS_SCAN_CACHE
    now = time.time()
    last_scan_t, known_dirs, c_rec, c_size, c_grow, c_items = _RECORDINGS_SCAN_CACHE

    dirs_to_check: list[Path] = [d for d in RECORDING_DIRS if d.is_dir()]
    if active_path:
        ap = Path(active_path)
        try:
            if ap.parent.is_dir() and ap.parent not in dirs_to_check:
                dirs_to_check.insert(0, ap.parent)
        except OSError: pass

    if now - last_scan_t < 1.8 and c_items:
        rec, size, growing = c_rec, c_size, c_grow
        if active_path and os.path.isfile(active_path):
            try:
                st = os.stat(active_path)
                size = st.st_size
                growing = (prev_rec_size is not None and size > prev_rec_size) or (now - st.st_mtime < 4.0 and size > 0)
                rec = active_path
            except OSError: pass
        items = list(c_items)
        if items and active_path:
            for item in items:
                if item.path == active_path:
                    item.size = size or item.size
                    item.is_active = is_active
                    item.is_growing = bool(growing)
        return rec, size, growing, items[:limit]

    seen: dict[str, Path] = {}
    for d in dirs_to_check:
        try:
            for f in d.iterdir():
                if f.name.startswith(".") or not f.is_file(): continue
                if f.suffix.lower() in (".wav", ".aiff", ".aif", ".mp3", ".flac", ".m4a", ".ogg"):
                    try: seen[str(f.resolve())] = f
                    except OSError: pass
        except OSError: continue

    if active_path:
        ap = Path(active_path)
        try:
            if ap.is_file(): seen[str(ap.resolve())] = ap
        except OSError: pass

    items: list[RecordingItem] = []
    act_res = str(Path(active_path).resolve()) if active_path and os.path.exists(active_path) else (active_path or "")
    for f in seen.values():
        try:
            st = f.stat()
            f_size, f_mtime = st.st_size, st.st_mtime
            resolved = str(f.resolve())
            this_act = bool(act_res and (resolved == act_res or str(f) == active_path) and is_active)
            this_grow = False
            if this_act:
                if active_size is not None: f_size = active_size
                f_mtime = max(f_mtime, now)
                this_grow = (prev_rec_size is not None and f_size > prev_rec_size) or ((now - st.st_mtime) < 4.0 and f_size > 0)
            items.append(RecordingItem(str(f), f.name, f_size, f_mtime, this_act, this_grow))
        except OSError: continue

    items.sort(key=lambda x: x.mtime, reverse=True)
    rec, size, growing = None, None, None
    if items:
        newest = items[0]
        rec = newest.path
        size = newest.size
        growing = (prev_rec_size is not None and size > prev_rec_size) or (now - newest.mtime < 4.0 and size > 0)
    _RECORDINGS_SCAN_CACHE = (now, dirs_to_check, rec, size, growing, items)
    return rec, size, growing, items[:limit]

def is_recording_active(pid: Optional[int] = None) -> bool:
    if pid is None: pid = find_traktor_pid()
    if pid and IS_LINUX and os.path.isdir(f"/proc/{pid}/fd"):
        try:
            for entry in os.scandir(f"/proc/{pid}/fd"):
                try:
                    target = os.readlink(entry.path).lower()
                    if ("recording" in target or "stream_of_frequency" in target) and any(target.endswith(ext) for ext in (".wav", ".aiff", ".aif")):
                        return True
                except OSError: pass
        except OSError: pass

    if pid and not IS_WINDOWS and shutil.which("lsof"):
        for line in run(["lsof", "-p", str(pid)], timeout=3.0).splitlines():
            parts = line.split()
            if len(parts) >= 9 and "w" in parts[3]:
                low = parts[-1].lower()
                if low.endswith((".wav", ".aiff", ".aif")) or "stream_of_frequency" in low or "/recordings/" in low:
                    return True

    now = time.time()
    for d in RECORDING_DIRS:
        if not d.is_dir(): continue
        try:
            for f in d.iterdir():
                if f.is_file() and f.suffix.lower() in (".wav", ".aiff", ".aif", ".mp3"):
                    try:
                        st = f.stat()
                        if now - st.st_mtime < 4.0 and st.st_size > 0: return True
                    except OSError: pass
        except OSError: pass
    return False

def click_traktor_menu_item(menu_name: str, item_name: str) -> tuple[bool, str]:
    if not IS_MACOS: return False, "Menu clicking is currently supported natively on macOS via System Events"
    m_a, i_a = menu_name.replace('"', '\\"'), item_name.replace('"', '\\"')
    script = f'''tell application "System Events"
  set procs to every process whose bundle identifier is "{TRAKTOR_BUNDLE_ID}"
  if (count of procs) is 0 then set procs to every process whose name is "{TRAKTOR_PROC}"
  if (count of procs) is 0 then return "ERROR: Traktor is not running"
  tell item 1 of procs
    set frontmost to true
    delay 0.25
    try
      click menu item "{i_a}" of menu "{m_a}" of menu bar 1
      return "OK: clicked {m_a} > {i_a}"
    on error errMsg number errNum
      return "ERROR: (" & errNum & ") " & errMsg
    end try
  end tell
end tell'''
    ok, msg = run_osascript(script, timeout=12.0)
    return (False, msg) if not ok or msg.startswith("ERROR:") else (True, msg)

def click_traktor_menu_item_fuzzy(want_start: bool) -> tuple[bool, str]:
    if not IS_MACOS: return False, "Menu scanning is supported on macOS via Accessibility"
    script = f'''tell application "System Events"
  set procs to every process whose bundle identifier is "{TRAKTOR_BUNDLE_ID}"
  if (count of procs) is 0 then set procs to every process whose name is "{TRAKTOR_PROC}"
  if (count of procs) is 0 then return "ERROR: Traktor is not running"
  tell item 1 of procs
    set frontmost to true
    delay 0.25
    set wantStart to {"true" if want_start else "false"}
    set hit to ""
    repeat with m in every menu bar item of menu bar 1
      set mName to name of m as text
      try
        repeat with mi in every menu item of menu mName of menu bar 1
          set iName to name of mi as text
          set low to do shell script "printf %s " & quoted form of iName & " | tr '[:upper:]' '[:lower:]'"
          if low contains "record" then
            if wantStart and (low contains "start" or low contains "audio recorder on" or low is "record") then set hit to mName & "||" & iName
            if (not wantStart) and (low contains "stop" or low contains "audio recorder on" or low is "record") then set hit to mName & "||" & iName
          end if
        end repeat
      end try
    end repeat
    if hit is "" then return "ERROR: no recording menu item found in Traktor."
    set AppleScript's text item delimiters to "||"
    set parts to text items of hit
    try
      click menu item (item 2 of parts) of menu (item 1 of parts) of menu bar 1
      return "OK: clicked " & (item 1 of parts) & " > " & (item 2 of parts)
    on error errMsg number errNum
      return "ERROR: (" & errNum & ") " & errMsg
    end try
  end tell
end tell'''
    ok, msg = run_osascript(script, timeout=18.0)
    return (False, msg) if not ok or msg.startswith("ERROR:") else (True, msg)

def list_traktor_menu_items() -> tuple[bool, str]:
    if not IS_MACOS: return False, "Menu listing is only supported on macOS."
    script = f'''tell application "System Events"
  set procs to every process whose bundle identifier is "{TRAKTOR_BUNDLE_ID}"
  if (count of procs) is 0 then set procs to every process whose name is "{TRAKTOR_PROC}"
  if (count of procs) is 0 then return "ERROR: Traktor is not running"
  tell item 1 of procs
    set out to ""
    repeat with m in every menu bar item of menu bar 1
      set mName to name of m as text
      set out to out & "[" & mName & "]\n"
      try
        repeat with mi in every menu item of menu mName of menu bar 1
          set iName to name of mi as text
          if iName is not "missing value" and iName is not "" then set out to out & "  - " & iName & "\n"
        end repeat
      end try
    end repeat
    return out
  end tell
end tell'''
    return run_osascript(script, timeout=10.0)

def control_recording_windows(action: str) -> tuple[bool, str]:
    ps_script = f'''$wshell = New-Object -ComObject WScript.Shell
$proc = Get-Process -Name Traktor* -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) {{ Write-Output "ERROR: Traktor is not running"; exit 1 }}
if ($wshell.AppActivate($proc.Id)) {{ Start-Sleep -Milliseconds 250; $wshell.SendKeys("^(r)"); Write-Output "OK: Sent Audio Recorder toggle signal to Traktor (PID $($proc.Id))"; exit 0 }}
else {{ Write-Output "ERROR: Could not activate Traktor window"; exit 1 }}'''
    try:
        res = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=5.0, check=False)
        out = res.stdout.strip()
        return (True, f"Windows {action} signal dispatched: {out}") if res.returncode == 0 and out.startswith("OK:") else (False, out or res.stderr.strip())
    except Exception as e:
        return False, f"Windows recording dispatch failed: {e}"

def menu_control_recording(action: str) -> tuple[bool, str]:
    action = action.lower().strip()
    if action not in ("start", "stop", "toggle"):
        return False, f"Unknown action {action!r}; use start|stop|toggle"
    pid = find_traktor_pid()
    if not pid: return False, "Traktor is not running"
    active = is_recording_active(pid)
    if action == "toggle": want_start = not active
    elif action == "start":
        if active: return True, "Already recording (active file write / growth detected)"
        want_start = True
    else: want_start = False

    if IS_MACOS:
        candidates = RECORD_START_MENU_CANDIDATES if want_start else RECORD_STOP_MENU_CANDIDATES
        for menu_name, item_name in candidates:
            ok, msg = click_traktor_menu_item(menu_name, item_name)
            if ok: return True, f"{'Started' if want_start else 'Stopped'} via menu: {msg}"
        ok, msg = click_traktor_menu_item_fuzzy(want_start)
        if ok: return True, f"{'Started' if want_start else 'Stopped'} via menu scan: {msg}"
        return False, "Could not find a recording menu item. Map a shortcut in Traktor Controller Manager."
    if IS_WINDOWS:
        return control_recording_windows(action)
    return False, "Direct menu dispatch not supported on this platform. Map a keyboard shortcut in Traktor Controller Manager."

def human_size(n: Optional[int]) -> str:
    if n is None: return "?"
    val = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024.0: return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.2f} PB"

def cpu_bar(pct: float, width: int = 20, theme: Optional[ThemeColors] = None) -> str:
    t = theme or get_theme()
    fill = int(min(pct, 100.0) / 100.0 * width)
    bar_col = t.green if pct < 50.0 else (t.yellow if pct < 80.0 else t.red)
    return f"{t.border}[{t.reset}{bar_col}{'#' * fill}{t.reset}{t.text_dim}{'-' * (width - fill)}{t.reset}{t.border}]{t.reset}"

def clear_screen() -> None:
    if IS_WINDOWS: os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

def format_recent_recordings(recordings: list[RecordingItem], box_w: int, term_h: int = 30, theme: Optional[ThemeColors] = None) -> list[str]:
    t = theme or get_theme()
    lines = [f"{t.border}{'-' * box_w}{t.reset}", f"  {t.bold}{t.primary}LAST 3 RECORDINGS (Newest at Top){t.reset}", f"{t.border}{'-' * box_w}{t.reset}"]
    if not recordings:
        lines.append(f"  {t.text_dim}(No audio recordings found in recording directories){t.reset}")
        return lines
    first_dir = str(Path(recordings[0].path).parent)
    show_all = term_h >= 40
    for idx, r in enumerate(recordings, 1):
        badge = f"  {t.bold}{t.green}[● LIVE: Growing]{t.reset}" if r.is_active and r.is_growing else (f"  {t.bold}{t.red}[● LIVE: Active Write]{t.reset}" if r.is_active else "")
        d_str = datetime.fromtimestamp(r.mtime).strftime("%Y-%m-%d %H:%M:%S") if r.mtime else ""
        lines.append(f"  {t.bold}{t.accent}[{idx}]{t.reset} {t.bold}{t.text}{r.name}{t.reset}{badge}")
        lines.append(f"      {t.secondary}Size:{t.reset} {t.text}{human_size(r.size):<10}{t.reset}  {t.border}│{t.reset}  {t.secondary}Modified:{t.reset} {t.text_dim}{d_str}{t.reset}")
        if show_all or idx == 1 or str(Path(r.path).parent) != first_dir:
            lines.append(f"      {t.text_dim}Path: {r.path}{t.reset}")
    return lines

def render(s: Snapshot, theme: Optional[ThemeColors] = None) -> str:
    t = theme or get_theme(getattr(s, "theme_id", None))
    lines = []
    w, h = shutil.get_terminal_size((100, 30))
    box_w = min(w, 82)
    title = "🎛️  TRAKTOR PRO LIVE MONITOR & RECORDER  🎛️"
    lines.append(f"{t.border}{'=' * box_w}{t.reset}")
    lines.append(f"{t.bold}{t.primary}{title.center(box_w)}{t.reset}")
    date_str = s.ts.strftime("%A, %B %d, %Y • %H:%M:%S")
    sub = f"{date_str}   │   Theme: {t.name}"
    lines.append(f"{t.text_dim}{(sub if len(sub) <= box_w - 4 else date_str).center(box_w)}{t.reset}")
    lines.append(f"{t.border}{'=' * box_w}{t.reset}\n")

    if not s.running:
        lines.append(f"  {t.bold}{t.secondary}STATUS{t.reset}     {t.bold}{t.yellow}Traktor is NOT running{t.reset}\n")
        lines.append(f"  {t.text_dim}Start Traktor Pro (macOS, Windows, or Linux) to begin live monitoring.{t.reset}\n")
        lines.extend(format_recent_recordings(s.recent_recordings, box_w, h, t))
    else:
        lines.append(f"  {t.bold}{t.secondary}STATUS{t.reset}     {t.bold}{t.green}● RUNNING{t.reset}   {t.text_dim}PID:{t.reset} {t.bold}{t.text}{s.pid}{t.reset}   {t.text_dim}Threads: ≈{t.reset}{t.text}{s.threads}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}CPU{t.reset}        {t.bold}{t.text}{s.cpu:5.1f}%{t.reset}  {cpu_bar(s.cpu, 20, t)}   {t.secondary}RAM:{t.reset} {t.text}{s.rss_mb:6.1f} MB RSS{t.reset}   {t.secondary}CPU Time:{t.reset} {t.text_dim}{s.cpu_time}{t.reset}\n")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.primary}AUDIO INTERFACE & HARDWARE{t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}Traktor Device{t.reset}      {t.text}{s.device_traktor or '?'}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}Driver / Clock{t.reset}      {t.text}{s.driver or '?'}{t.reset}  {t.border}│{t.reset}  {t.secondary}Rate:{t.reset} {t.text}{s.sample_rate} Hz{t.reset}  {t.border}│{t.reset}  {t.secondary}Buffer/Latency:{t.reset} {t.text}{s.latency}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}System Default IN{t.reset}   {t.text_dim}{s.system_in}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}System Default OUT{t.reset}  {t.text_dim}{s.system_out}{t.reset}\n")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.primary}LOADED / ACTIVE TRACKS (Decks with Media Open){t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        if s.loaded_tracks:
            deck_cols = [t.secondary, t.accent, t.primary, t.green]
            for i, trk in enumerate(s.loaded_tracks, 1):
                col = deck_cols[(i - 1) % len(deck_cols)]
                lines.append(f"  {t.bold}{col}[Deck {chr(64+i) if i<=4 else str(i)}]{t.reset} {t.text}{trk}{t.reset}")
        else:
            lines.append(f"  {t.text_dim}(No audio tracks actively open or loaded on decks){t.reset}")
        lines.append(f"\n{t.border}{'-' * box_w}{t.reset}")
        lines.append(f"  {t.bold}{t.primary}AUDIO RECORDER STATUS{t.reset}")
        lines.append(f"{t.border}{'-' * box_w}{t.reset}")
        rec_badge = f"{t.bold}{t.red}● RECORDING (Active File Write){t.reset}" if s.recording_active else f"{t.text_dim}○ IDLE (Not Recording){t.reset}"
        lines.append(f"  {t.bold}{t.secondary}State{t.reset}    {rec_badge}")
        if s.recording_prefix: lines.append(f"  {t.bold}{t.secondary}Prefix{t.reset}   {t.text}{s.recording_prefix}{t.reset}")
        lines.append(f"  {t.bold}{t.secondary}Control{t.reset}  {t.bold}{t.green}[s]{t.reset} Start Rec  {t.border}│{t.reset}  {t.bold}{t.red}[x]{t.reset} Stop Rec  {t.border}│{t.reset}  {t.bold}{t.yellow}[t]{t.reset} Toggle Rec\n")
        lines.extend(format_recent_recordings(s.recent_recordings, box_w, h, t))

    if s.last_action:
        lines.extend(["", f"{t.border}{'-' * box_w}{t.reset}", f"  {t.bold}{t.accent}LAST ACTION{t.reset}", f"{t.border}{'-' * box_w}{t.reset}", f"  {t.text}{s.last_action}{t.reset}"])
    if s.notes:
        lines.extend(["", f"{t.border}{'-' * box_w}{t.reset}", f"  {t.bold}{t.yellow}SYSTEM NOTES{t.reset}", f"{t.border}{'-' * box_w}{t.reset}"])
        for n in s.notes: lines.append(f"  {t.yellow}•{t.reset} {t.text_dim}{n}{t.reset}")

    lines.extend([
        "", f"{t.border}{'-' * box_w}{t.reset}",
        f"  {t.bold}{t.accent}HOTKEYS:{t.reset}  {t.bold}{t.primary}[Q]{t.reset} Quit  {t.border}│{t.reset}  {t.bold}{t.primary}[R]{t.reset} Refresh  {t.border}│{t.reset}  {t.bold}{t.secondary}[C]{t.reset} Theme ({t.id})  {t.border}│{t.reset}  {t.bold}{t.green}[S]{t.reset} Start  {t.border}│{t.reset}  {t.bold}{t.red}[X]{t.reset} Stop  {t.border}│{t.reset}  {t.bold}{t.yellow}[T]{t.reset} Toggle",
        f"{t.border}{'=' * box_w}{t.reset}"
    ])
    return "\n".join(lines)

def take_snapshot(prev_rec_size: Optional[int], theme_id: Optional[str] = None) -> Snapshot:
    tid = resolve_theme_id(theme_id or _ACTIVE_THEME_ID)
    s = Snapshot(ts=datetime.now(), theme_id=tid, theme_name=get_theme(tid).name)
    sp = find_settings()
    if sp:
        conf = parse_settings(sp)
        s.device_traktor, s.sample_rate, s.latency, s.driver, s.recording_prefix = conf["device"], conf["sample_rate"], conf["latency"], conf["driver"], conf["recording_prefix"]
    else:
        s.notes.append("Traktor Settings.tsi not found (using system defaults)")
    try:
        s.system_in, s.system_out = system_audio_defaults()
    except Exception as e:
        s.notes.append(f"Audio device query notice: {e}")

    pid = find_traktor_pid()
    if not pid:
        s.running = False
        rec, size, grow, recents = scan_recordings(prev_rec_size, is_active=False)
        s.recording, s.recording_size, s.recording_growing, s.recent_recordings = rec, size, grow, recents
        return s

    s.running = True
    s.pid = pid
    st = process_stats(pid)
    s.cpu, s.mem_pct, s.rss_mb, s.cpu_time, s.threads = st["cpu"], st["mem"], st["rss_mb"], st["time"], st["threads"]

    tracks, rec, rec_size = lsof_tracks_and_recording(pid)
    s.loaded_tracks = tracks
    s.recording_active = is_recording_active(pid)

    r_path, r_size, r_grow, recents = scan_recordings(prev_rec_size, active_path=rec, active_size=rec_size, is_active=s.recording_active)
    s.recording = rec or r_path
    s.recording_size = rec_size if rec_size is not None else r_size
    s.recording_growing = (prev_rec_size is not None and s.recording_size is not None and s.recording_size > prev_rec_size) or r_grow
    if s.recording_growing: s.recording_active = True
    s.recent_recordings = recents
    return s

def get_key_nonblocking(fd: Optional[int]) -> Optional[str]:
    if IS_WINDOWS:
        try:
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                try: return ch.decode("utf-8", "ignore")
                except Exception: return str(ch)
        except Exception: pass
        return None
    elif fd is not None:
        try:
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r: return sys.stdin.read(1)
        except Exception: pass
    return None

def main() -> int:
    global _ACTIVE_THEME_ID
    ap = argparse.ArgumentParser(description="Traktor live monitor (CPU, tracks, recording, audio I/O) + recording control (macOS, Windows, Linux)")
    ap.add_argument("--interval", type=float, default=1.0, help="Refresh seconds (default 1)")
    ap.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    ap.add_argument("--start-recording", action="store_true", help="Start Traktor Audio Recorder, then exit")
    ap.add_argument("--stop-recording", action="store_true", help="Stop Traktor Audio Recorder, then exit")
    ap.add_argument("--toggle-recording", action="store_true", help="Toggle Traktor Audio Recorder, then exit")
    ap.add_argument("--theme", "-t", type=str, default=None, help="Color theme name")
    ap.add_argument("--list-themes", action="store_true", help="List all available color themes, then exit")
    ap.add_argument("--set-theme", type=str, default=None, metavar="THEME", help="Set and persist the active color theme, then exit")
    ap.add_argument("--save-theme", action="store_true", help="Persist the selected theme to ~/.config/mix-manager/theme")
    ap.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    ap.add_argument("--no-launch", action="store_true", help="Do not automatically launch Traktor if not running")
    ap.add_argument("--list-menus", action="store_true", help="List Traktor menu bar items (debug macOS) and exit")
    args = ap.parse_args()

    if args.list_themes:
        print_theme_list(); return 0
    if args.set_theme:
        tid = resolve_theme_id(args.set_theme)
        t = get_theme(tid)
        if save_active_theme(tid): print(f"\033[1;32m✓\033[0m Traktor Monitor theme set to: {t.primary}{t.name}{t.reset} ({tid})"); return 0
        print("✗ Failed to save theme to ~/.config/mix-manager/theme", file=sys.stderr); return 1
    if args.list_menus:
        if IS_MACOS:
            ok, msg = list_traktor_menu_items()
            print(msg); return 0 if ok and not msg.startswith("ERROR:") else 1
        print("Menu listing is only supported on macOS."); return 0

    if sum(bool(x) for x in (args.start_recording, args.stop_recording, args.toggle_recording)) > 1:
        print("Use only one of --start-recording / --stop-recording / --toggle-recording", file=sys.stderr); return 2
    for act, flag in (("start", args.start_recording), ("stop", args.stop_recording), ("toggle", args.toggle_recording)):
        if flag:
            ok, msg = menu_control_recording(act)
            print(msg); return 0 if ok else 1

    active_theme_id = resolve_theme_id(args.theme) if args.theme else load_saved_theme()
    if args.theme and args.save_theme: save_active_theme(active_theme_id)
    _ACTIVE_THEME_ID = active_theme_id
    active_theme = get_theme(active_theme_id, no_color=args.no_color)

    if not args.no_launch: ensure_traktor_running()

    prev_size: Optional[int] = None
    last_action = ""

    if args.once:
        s = take_snapshot(prev_size, active_theme_id)
        print(render(s, active_theme)); return 0

    fd, old_term = None, None
    if not IS_WINDOWS:
        try:
            import termios, tty
            fd = sys.stdin.fileno()
            old_term = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except Exception:
            fd, old_term = None, None

    try:
        while True:
            s = take_snapshot(prev_size, active_theme_id)
            s.last_action = last_action
            if s.recording_size is not None: prev_size = s.recording_size
            clear_screen()
            print(render(s, active_theme))

            end = time.time() + max(0.3, args.interval)
            while time.time() < end:
                ch = get_key_nonblocking(fd)
                if ch:
                    if ch in ("q", "Q", "\x03"): return 0
                    if ch in ("r", "R"): break
                    if ch in ("c", "C", "m", "M"):
                        keys = list(THEMES.keys())
                        cur_i = keys.index(active_theme_id) if active_theme_id in keys else 0
                        active_theme_id = keys[(cur_i + 1) % len(keys)]
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
                time.sleep(0.04)
    except KeyboardInterrupt:
        return 0
    finally:
        if old_term is not None and fd is not None:
            try:
                import termios
                termios.tcsetattr(fd, termios.TCSADRAIN, old_term)
            except Exception: pass
        print("\nTraktor Live Monitor closed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
