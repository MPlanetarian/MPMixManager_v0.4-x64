#!/usr/bin/env python3
"""
MP Mix Manager v0.3 - Studio & DJ Booth Mobile Web Companion
Lightweight, standalone HTTP & REST server providing a modern, theme-adaptive
web dashboard accessible from phones, tablets, and remote browsers on the local LAN.
Displays live mix playback, tracklists, EQ visualizers, and remote playback controls.
Automatically synchronizes with the active theme currently running in Manager.
"""

import argparse
import html
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PORT = 8888

# ------------------------------------------------------------------------------
# THEME ENGINE — Palettes matching Mix_Archive_Manager.sh
# ------------------------------------------------------------------------------
THEMES: Dict[str, Dict[str, Any]] = {
    "cosmic_supernova": {
        "id": "cosmic_supernova",
        "name": "Cosmic Supernova [Special Edition]",
        "bg": "#0a0814",
        "card_bg": "#14112c",
        "card_border": "rgba(224, 86, 253, 0.32)",
        "card_shadow": "0 12px 35px rgba(10, 8, 20, 0.85)",
        "text_main": "#e2e8f0",
        "text_dim": "#7c8ba1",
        "accent_primary": "#00f5d4",     # Aurora Aquamarine
        "accent_secondary": "#e056fd",   # Nebula Orchid
        "accent_tertiary": "#fee440",    # Solar Flare Gold
        "accent_crimson": "#ff3366",     # Supernova Crimson
        "header_gradient": "linear-gradient(135deg, #ff3366 0%, #e056fd 50%, #00f5d4 100%)",
        "btn_gradient": "linear-gradient(135deg, #e056fd, #ff3366)",
        "btn_shadow": "0 4px 18px rgba(224, 86, 253, 0.45)",
        "progress_fill": "linear-gradient(90deg, #5e60ce, #e056fd, #00f5d4)",
        "badge_bg": "rgba(0, 245, 212, 0.15)",
        "badge_color": "#00f5d4",
        "eq_bar": "#00f5d4",
        "eq_peak": "#ff3366",
    },
    "dreamworlds": {
        "id": "dreamworlds",
        "name": "MPlanetarian Dreamworlds",
        "bg": "#0d0f18",
        "card_bg": "#151928",
        "card_border": "rgba(247, 37, 133, 0.28)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.65)",
        "text_main": "#f0f3f6",
        "text_dim": "#7f8ba4",
        "accent_primary": "#f72585",     # Neon Pink
        "accent_secondary": "#00e5ff",   # Electric Cyan
        "accent_tertiary": "#ffaa00",    # Amber Gold
        "accent_crimson": "#ed254e",     # Coral Red
        "header_gradient": "linear-gradient(135deg, #f72585 0%, #00e5ff 100%)",
        "btn_gradient": "linear-gradient(135deg, #f72585, #ed254e)",
        "btn_shadow": "0 4px 18px rgba(247, 37, 133, 0.4)",
        "progress_fill": "linear-gradient(90deg, #f72585, #00e5ff)",
        "badge_bg": "rgba(0, 229, 255, 0.15)",
        "badge_color": "#00e5ff",
        "eq_bar": "#00e5ff",
        "eq_peak": "#f72585",
    },
    "dreamworlds_ultra": {
        "id": "dreamworlds_ultra",
        "name": "Dreamworlds Ultra MP Mix Manager",
        "bg": "#000000",
        "card_bg": "#110e20",
        "card_border": "rgba(166, 77, 255, 0.38)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.9)",
        "text_main": "#d1d1e0",
        "text_dim": "#9999ff",
        "accent_primary": "#a64dff",     # Hot Purple
        "accent_secondary": "#00ff00",   # Traffic Green
        "accent_tertiary": "#ff9933",    # Amber
        "accent_crimson": "#ff0000",     # Alert Red
        "header_gradient": "linear-gradient(135deg, #a64dff 0%, #00ff00 100%)",
        "btn_gradient": "linear-gradient(135deg, #a64dff, #ff0000)",
        "btn_shadow": "0 4px 18px rgba(166, 77, 255, 0.45)",
        "progress_fill": "linear-gradient(90deg, #00ff00, #ff9933, #ff0000)",
        "badge_bg": "rgba(0, 255, 0, 0.15)",
        "badge_color": "#00ff00",
        "eq_bar": "#00ff00",
        "eq_peak": "#ff0000",
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "Cyberpunk 2077",
        "bg": "#080812",
        "card_bg": "#121026",
        "card_border": "rgba(255, 0, 85, 0.35)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.8)",
        "text_main": "#e0ffff",
        "text_dim": "#708090",
        "accent_primary": "#ff0055",     # Neon Pink
        "accent_secondary": "#00ffff",   # Cyan
        "accent_tertiary": "#ffff00",    # Neon Yellow
        "accent_crimson": "#ff0055",
        "header_gradient": "linear-gradient(135deg, #ff0055 0%, #ffff00 50%, #00ffff 100%)",
        "btn_gradient": "linear-gradient(135deg, #ff0055, #ff00aa)",
        "btn_shadow": "0 4px 18px rgba(255, 0, 85, 0.5)",
        "progress_fill": "linear-gradient(90deg, #ff0055, #ffff00, #00ffff)",
        "badge_bg": "rgba(0, 255, 255, 0.15)",
        "badge_color": "#00ffff",
        "eq_bar": "#00ffff",
        "eq_peak": "#ff0055",
    },
    "dracula": {
        "id": "dracula",
        "name": "Dracula",
        "bg": "#282a36",
        "card_bg": "#343746",
        "card_border": "rgba(189, 147, 249, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#f8f8f2",
        "text_dim": "#6272a4",
        "accent_primary": "#bd93f9",     # Purple
        "accent_secondary": "#ff79c6",   # Pink
        "accent_tertiary": "#8be9fd",    # Cyan
        "accent_crimson": "#ff5555",
        "header_gradient": "linear-gradient(135deg, #bd93f9 0%, #ff79c6 100%)",
        "btn_gradient": "linear-gradient(135deg, #bd93f9, #ff79c6)",
        "btn_shadow": "0 4px 18px rgba(189, 147, 249, 0.4)",
        "progress_fill": "linear-gradient(90deg, #bd93f9, #ff79c6, #8be9fd)",
        "badge_bg": "rgba(139, 233, 253, 0.15)",
        "badge_color": "#8be9fd",
        "eq_bar": "#50fa7b",
        "eq_peak": "#ff79c6",
    },
    "nord": {
        "id": "nord",
        "name": "Nord Frost",
        "bg": "#242933",
        "card_bg": "#2e3440",
        "card_border": "rgba(136, 192, 208, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.5)",
        "text_main": "#eceff4",
        "text_dim": "#929cb0",
        "accent_primary": "#88c0d0",     # Frost Cyan
        "accent_secondary": "#81a1c1",   # Frost Blue
        "accent_tertiary": "#a3be8c",    # Aurora Green
        "accent_crimson": "#bf616a",
        "header_gradient": "linear-gradient(135deg, #88c0d0 0%, #81a1c1 100%)",
        "btn_gradient": "linear-gradient(135deg, #5e81ac, #88c0d0)",
        "btn_shadow": "0 4px 18px rgba(136, 192, 208, 0.35)",
        "progress_fill": "linear-gradient(90deg, #5e81ac, #88c0d0, #a3be8c)",
        "badge_bg": "rgba(136, 192, 208, 0.15)",
        "badge_color": "#88c0d0",
        "eq_bar": "#88c0d0",
        "eq_peak": "#bf616a",
    },
    "matrix": {
        "id": "matrix",
        "name": "The Matrix",
        "bg": "#070b07",
        "card_bg": "#0e180e",
        "card_border": "rgba(0, 255, 102, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 20, 0, 0.8)",
        "text_main": "#d4ffd4",
        "text_dim": "#448844",
        "accent_primary": "#00ff66",     # Neon Green
        "accent_secondary": "#a6ff00",   # Lime
        "accent_tertiary": "#00cc44",
        "accent_crimson": "#ff3333",
        "header_gradient": "linear-gradient(135deg, #00ff66 0%, #a6ff00 100%)",
        "btn_gradient": "linear-gradient(135deg, #008f39, #00ff66)",
        "btn_shadow": "0 4px 18px rgba(0, 255, 102, 0.4)",
        "progress_fill": "linear-gradient(90deg, #008f39, #00ff66)",
        "badge_bg": "rgba(0, 255, 102, 0.15)",
        "badge_color": "#00ff66",
        "eq_bar": "#00ff66",
        "eq_peak": "#a6ff00",
    },
    "solarized": {
        "id": "solarized",
        "name": "Solarized Dark",
        "bg": "#00212b",
        "card_bg": "#073642",
        "card_border": "rgba(42, 161, 152, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 15, 20, 0.7)",
        "text_main": "#93a1a1",
        "text_dim": "#657b83",
        "accent_primary": "#2aa198",     # Cyan
        "accent_secondary": "#268bd2",   # Blue
        "accent_tertiary": "#b58900",    # Yellow
        "accent_crimson": "#dc322f",
        "header_gradient": "linear-gradient(135deg, #2aa198 0%, #268bd2 100%)",
        "btn_gradient": "linear-gradient(135deg, #268bd2, #2aa198)",
        "btn_shadow": "0 4px 18px rgba(42, 161, 152, 0.35)",
        "progress_fill": "linear-gradient(90deg, #268bd2, #2aa198)",
        "badge_bg": "rgba(42, 161, 152, 0.15)",
        "badge_color": "#2aa198",
        "eq_bar": "#2aa198",
        "eq_peak": "#cb4b16",
    },
    "tokyo": {
        "id": "tokyo",
        "name": "Tokyo Night",
        "bg": "#1a1b26",
        "card_bg": "#24283b",
        "card_border": "rgba(122, 162, 247, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#c0caf5",
        "text_dim": "#565f89",
        "accent_primary": "#7aa2f7",     # Blue
        "accent_secondary": "#bb9af7",   # Magenta
        "accent_tertiary": "#7dcfff",    # Cyan
        "accent_crimson": "#f7768e",
        "header_gradient": "linear-gradient(135deg, #7aa2f7 0%, #bb9af7 100%)",
        "btn_gradient": "linear-gradient(135deg, #7aa2f7, #bb9af7)",
        "btn_shadow": "0 4px 18px rgba(122, 162, 247, 0.4)",
        "progress_fill": "linear-gradient(90deg, #7aa2f7, #bb9af7, #7dcfff)",
        "badge_bg": "rgba(125, 207, 255, 0.15)",
        "badge_color": "#7dcfff",
        "eq_bar": "#7aa2f7",
        "eq_peak": "#f7768e",
    },
    "monokai": {
        "id": "monokai",
        "name": "Monokai Pro",
        "bg": "#1e1f1c",
        "card_bg": "#272822",
        "card_border": "rgba(249, 38, 114, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#f8f8f2",
        "text_dim": "#75715e",
        "accent_primary": "#f92672",     # Pink
        "accent_secondary": "#66d9ef",   # Cyan
        "accent_tertiary": "#a6e22e",    # Green
        "accent_crimson": "#f92672",
        "header_gradient": "linear-gradient(135deg, #f92672 0%, #66d9ef 100%)",
        "btn_gradient": "linear-gradient(135deg, #f92672, #ae81ff)",
        "btn_shadow": "0 4px 18px rgba(249, 38, 114, 0.4)",
        "progress_fill": "linear-gradient(90deg, #f92672, #ae81ff, #66d9ef)",
        "badge_bg": "rgba(102, 217, 239, 0.15)",
        "badge_color": "#66d9ef",
        "eq_bar": "#a6e22e",
        "eq_peak": "#f92672",
    },
    "gruvbox": {
        "id": "gruvbox",
        "name": "Gruvbox Dark",
        "bg": "#1d2021",
        "card_bg": "#282828",
        "card_border": "rgba(250, 189, 47, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.6)",
        "text_main": "#ebdbb2",
        "text_dim": "#a89984",
        "accent_primary": "#fabd2f",     # Yellow
        "accent_secondary": "#fe8019",   # Orange
        "accent_tertiary": "#8ec07c",    # Aqua
        "accent_crimson": "#fb4934",
        "header_gradient": "linear-gradient(135deg, #fabd2f 0%, #fe8019 100%)",
        "btn_gradient": "linear-gradient(135deg, #d65d0e, #fabd2f)",
        "btn_shadow": "0 4px 18px rgba(250, 189, 47, 0.35)",
        "progress_fill": "linear-gradient(90deg, #d65d0e, #fabd2f, #8ec07c)",
        "badge_bg": "rgba(250, 189, 47, 0.15)",
        "badge_color": "#fabd2f",
        "eq_bar": "#fabd2f",
        "eq_peak": "#fb4934",
    },
    "emerald": {
        "id": "emerald",
        "name": "Emerald Isle",
        "bg": "#081410",
        "card_bg": "#10261e",
        "card_border": "rgba(46, 204, 113, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 20, 15, 0.7)",
        "text_main": "#e0f2ec",
        "text_dim": "#528c77",
        "accent_primary": "#2ecc71",     # Emerald
        "accent_secondary": "#4ee0b5",   # Mint
        "accent_tertiary": "#f1c40f",    # Gold
        "accent_crimson": "#e74c3c",
        "header_gradient": "linear-gradient(135deg, #2ecc71 0%, #4ee0b5 100%)",
        "btn_gradient": "linear-gradient(135deg, #27ae60, #2ecc71)",
        "btn_shadow": "0 4px 18px rgba(46, 204, 113, 0.4)",
        "progress_fill": "linear-gradient(90deg, #1abc9c, #2ecc71, #4ee0b5)",
        "badge_bg": "rgba(78, 224, 181, 0.15)",
        "badge_color": "#4ee0b5",
        "eq_bar": "#2ecc71",
        "eq_peak": "#f1c40f",
    },
    "classic": {
        "id": "classic",
        "name": "Classic ANSI",
        "bg": "#101010",
        "card_bg": "#1a1a1a",
        "card_border": "rgba(0, 205, 205, 0.3)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.8)",
        "text_main": "#e0e0e0",
        "text_dim": "#888888",
        "accent_primary": "#00cdcd",     # Cyan
        "accent_secondary": "#cd00cd",   # Magenta
        "accent_tertiary": "#00cd00",    # Green
        "accent_crimson": "#cd0000",
        "header_gradient": "linear-gradient(135deg, #00cdcd 0%, #cd00cd 100%)",
        "btn_gradient": "linear-gradient(135deg, #0077aa, #00cdcd)",
        "btn_shadow": "0 4px 18px rgba(0, 205, 205, 0.35)",
        "progress_fill": "linear-gradient(90deg, #0077aa, #00cdcd)",
        "badge_bg": "rgba(0, 205, 205, 0.15)",
        "badge_color": "#00cdcd",
        "eq_bar": "#00cdcd",
        "eq_peak": "#cd00cd",
    },
    "retro_terminal": {
        "id": "retro_terminal",
        "name": "Old Style Unix Terminal Retro Mode (White on Black)",
        "bg": "#000000",
        "card_bg": "#0a0a0a",
        "card_border": "rgba(255, 255, 255, 0.4)",
        "card_shadow": "0 12px 35px rgba(0, 0, 0, 0.95)",
        "text_main": "#ffffff",
        "text_dim": "#aaaaaa",
        "accent_primary": "#ffffff",
        "accent_secondary": "#cccccc",
        "accent_tertiary": "#ffffff",
        "accent_crimson": "#ffffff",
        "header_gradient": "linear-gradient(135deg, #ffffff 0%, #aaaaaa 100%)",
        "btn_gradient": "linear-gradient(135deg, #333333, #111111)",
        "btn_shadow": "0 4px 18px rgba(255, 255, 255, 0.2)",
        "progress_fill": "linear-gradient(90deg, #666666, #ffffff)",
        "badge_bg": "rgba(255, 255, 255, 0.15)",
        "badge_color": "#ffffff",
        "eq_bar": "#ffffff",
        "eq_peak": "#ffffff",
    }
}

THEME_ALIASES: Dict[str, str] = {
    "mplanetarian_dreamworlds": "dreamworlds",
    "mplanetarian": "dreamworlds",
    "default": "dreamworlds",
    "ultra": "dreamworlds_ultra",
    "dreamworlds ultra": "dreamworlds_ultra",
    "dreamworlds_ultra_mp_mix_manager": "dreamworlds_ultra",
    "cosmic": "cosmic_supernova",
    "supernova": "cosmic_supernova",
    "cosmic supernova": "cosmic_supernova",
    "cosmic supernova [special]": "cosmic_supernova",
    "cosmic supernova [special edition]": "cosmic_supernova",
    "cosmic_supernova_mp_mix_manager": "cosmic_supernova",
    "the matrix": "matrix",
    "tokyo night": "tokyo",
    "solarized dark": "solarized",
    "monokai pro": "monokai",
    "gruvbox dark": "gruvbox",
    "emerald isle": "emerald",
    "classic ansi": "classic",
    "retro_terminal": "retro_terminal",
    "unix_terminal": "retro_terminal",
    "retro_unix": "retro_terminal",
    "old_style_unix": "retro_terminal",
    "white_on_black": "retro_terminal",
    "retro": "retro_terminal",
    "terminal": "retro_terminal",
    "vt100": "retro_terminal",
    "old style unix terminal retro mode (white on black)": "retro_terminal",
    "old style unix terminal": "retro_terminal",
}

CLI_THEME: Optional[str] = None
_tracklist_cache: Dict[str, str] = {}


def get_base_dir() -> Path:
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "scripts" else p.parent


def get_current_theme_id(cli_theme: Optional[str] = None) -> str:
    """Detect current theme with priority: CLI arg -> Env var -> Manager config -> Default."""
    # 1. Explicit CLI override
    if cli_theme:
        k = cli_theme.strip().lower()
        if k in THEME_ALIASES: return THEME_ALIASES[k]
        if k in THEMES: return k

    # 2. Environment variable (set by Manager launch)
    env_theme = os.environ.get("CURRENT_THEME", "").strip().lower()
    if env_theme:
        if env_theme in THEME_ALIASES: return THEME_ALIASES[env_theme]
        if env_theme in THEMES: return env_theme

    # 3. Manager persistent saved theme: ~/.config/mix-manager/theme
    theme_file = Path.home() / ".config" / "mix-manager" / "theme"
    if theme_file.is_file():
        try:
            saved = theme_file.read_text(encoding="utf-8").strip().lower()
            if saved in THEME_ALIASES: return THEME_ALIASES[saved]
            if saved in THEMES: return saved
        except Exception:
            pass

    return "cosmic_supernova" if "cosmic_supernova" in THEMES else "dreamworlds"


def get_theme_palette(cli_theme: Optional[str] = None) -> Dict[str, Any]:
    tid = get_current_theme_id(cli_theme)
    return THEMES.get(tid, THEMES["dreamworlds"])


def get_local_ip() -> str:
    """Detect LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def is_pid_alive(pid: Any) -> bool:
    try:
        pid_int = int(pid)
        if sys.platform == "win32":
            import ctypes
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            h = k.OpenProcess(0x1000, False, pid_int)
            if h:
                ec = ctypes.c_ulong()
                ok = k.GetExitCodeProcess(h, ctypes.byref(ec))
                k.CloseHandle(h)
                return bool(ok and ec.value == 259)
            return False
        else:
            os.kill(pid_int, 0)
            return True
    except (OSError, ValueError, TypeError):
        return False


# ------------------------------------------------------------------------------
# MP AUDIO PLAYER IPC & STATUS RETRIEVAL
# ------------------------------------------------------------------------------
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
SOCKET_PATH = CONFIG_DIR / "mp_audio_player.sock"
PORT_FILE = CONFIG_DIR / "mp_audio_player.port"
STATE_FILE = CONFIG_DIR / "mp_player_state.json"
PID_FILE = CONFIG_DIR / "mp_player.pid"


def query_mp_player_socket() -> Optional[Dict[str, Any]]:
    """Query live state directly from MP Audio Player IPC socket."""
    has_unix = hasattr(socket, "AF_UNIX")
    if (has_unix and not SOCKET_PATH.exists()) or (not has_unix and not PORT_FILE.exists()):
        return None
    try:
        s = socket.socket(socket.AF_UNIX if has_unix else socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.35)
        s.connect(str(SOCKET_PATH) if has_unix else ("127.0.0.1", int(PORT_FILE.read_text().strip())))
        s.sendall(json.dumps({"cmd": "status"}).encode("utf-8"))
        raw = s.recv(65536).decode("utf-8")
        s.close()
        if raw:
            res = json.loads(raw)
            if isinstance(res, dict) and res.get("status") == "ok":
                return res.get("data")
    except Exception:
        pass
    return None


def read_mp_player_state_file() -> Optional[Dict[str, Any]]:
    """Read state from JSON state file if present and recent."""
    if not STATE_FILE.is_file():
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def send_mp_player_command(cmd: str, **kwargs) -> bool:
    """Send playback control command to MP Audio Player via IPC."""
    has_unix = hasattr(socket, "AF_UNIX")
    if (has_unix and not SOCKET_PATH.exists()) or (not has_unix and not PORT_FILE.exists()):
        return False
    try:
        s = socket.socket(socket.AF_UNIX if has_unix else socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(str(SOCKET_PATH) if has_unix else ("127.0.0.1", int(PORT_FILE.read_text().strip())))
        payload = {"cmd": cmd, **kwargs}
        s.sendall(json.dumps(payload).encode("utf-8"))
        raw = s.recv(4096).decode("utf-8")
        s.close()
        if raw:
            res = json.loads(raw)
            return res.get("status") == "ok"
    except Exception:
        pass
    return False


def is_mp_player_active() -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check whether MP Audio Player is running and retrieve its state."""
    # 1. Try socket IPC
    st = query_mp_player_socket()
    if st and is_pid_alive(st.get("pid")):
        return True, st

    # 2. Try state file + PID validation
    st = read_mp_player_state_file()
    if st:
        pid = st.get("pid")
        if not pid and PID_FILE.is_file():
            try: pid = int(PID_FILE.read_text().strip())
            except Exception: pid = None
        if is_pid_alive(pid):
            return True, st

    return False, None


# ------------------------------------------------------------------------------
# TRACKLIST RESOLUTION & METADATA PARSING
# ------------------------------------------------------------------------------
def find_tracklist_for_mix(mix_file: str) -> str:
    """Find matching tracklist .txt file with smart caching."""
    if not mix_file:
        return ""
    if mix_file in _tracklist_cache:
        return _tracklist_cache[mix_file]

    p = Path(mix_file).expanduser().resolve()
    base = get_base_dir()
    stem = p.stem

    # Exact stem match in same directory
    exact = p.parent / f"{stem}.txt"
    if exact.is_file():
        _tracklist_cache[mix_file] = str(exact)
        return str(exact)

    candidate_dirs = [
        p.parent,
        p.parent / "FLAC_CONVERTED_OUTPUTS",
        p.parent.parent / "FLAC_CONVERTED_OUTPUTS",
        base / "FLAC_CONVERTED_OUTPUTS",
        base / "MIX_ARCHIVE" / "FLAC_CONVERTED_OUTPUTS",
        Path.home() / "GoogleDrive" / "MIX_ARCHIVE" / "FLAC_CONVERTED_OUTPUTS"
    ]

    for d in candidate_dirs:
        if d.is_dir():
            c = d / f"{stem}.txt"
            if c.is_file():
                _tracklist_cache[mix_file] = str(c)
                return str(c)

    # Match by mix number (e.g. 033, 089)
    m = re.search(r'[_\ -](\d{2,3})([_\ -]|$)', stem)
    mix_num = m.group(1) if m else None

    if mix_num:
        for d in candidate_dirs:
            if d.is_dir():
                try:
                    for f in d.iterdir():
                        if f.is_file() and f.suffix.lower() == ".txt":
                            fname = f.name
                            if mix_num in fname:
                                _tracklist_cache[mix_file] = str(f)
                                return str(f)
                except Exception:
                    pass

    _tracklist_cache[mix_file] = ""
    return ""


def parse_tracklist_file(tracklist_path: str) -> Dict[str, Any]:
    """Parse artist, title, album, and track items from tracklist .txt."""
    if not tracklist_path or not os.path.isfile(tracklist_path):
        return {"metadata": {}, "tracks": []}
    try:
        with open(tracklist_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        metadata: Dict[str, str] = {}
        tracks: List[str] = []
        in_tracklist = False
        for line in content.splitlines():
            s = line.strip()
            if not s:
                continue
            if "TRACKLIST" in s.upper():
                in_tracklist = True
                continue
            if s.startswith("Artist:") and "artist" not in metadata:
                metadata["artist"] = s.split(":", 1)[1].strip()
            elif s.startswith("Album:") and "album" not in metadata:
                metadata["album"] = s.split(":", 1)[1].strip()
            elif s.startswith("Title:") and "title" not in metadata:
                metadata["title"] = s.split(":", 1)[1].strip()

            if in_tracklist:
                if s.startswith("=") or s.startswith("-"):
                    continue
                if re.match(r'^\d{1,3}[\.\:\-\s]', s):
                    tracks.append(s)
            else:
                if re.match(r'^\d{1,3}[\.\:\-]\s+', s):
                    tracks.append(s)
        return {"metadata": metadata, "tracks": tracks}
    except Exception:
        return {"metadata": {}, "tracks": []}


def clean_track_title(raw_title: str, raw_path: str, tl_meta: Dict[str, str]) -> Tuple[str, str, str]:
    """Derive clean display title, artist, and album."""
    # 1. Use tracklist metadata if present
    if tl_meta.get("title"):
        title = tl_meta["title"]
        artist = tl_meta.get("artist", "MPlanetarian")
        album = tl_meta.get("album", "Stream of Frequency")
        return title, artist, album

    if not raw_title and raw_path:
        raw_title = Path(raw_path).name

    stem = Path(raw_title).stem
    clean = re.sub(r'[\uf000-\uf8ff]', ':', stem).strip()
    clean = clean.replace('_', ' ')
    clean = re.sub(r'\s+', ' ', clean).strip()

    artist = "MPlanetarian"
    album = "Stream of Frequency"
    title = clean

    if " - " in clean:
        parts = clean.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()

    return title, artist, album


# ------------------------------------------------------------------------------
# STATUS & PLAYBACK ENGINE
# ------------------------------------------------------------------------------
def get_playback_status(cli_theme: Optional[str] = None) -> Dict[str, Any]:
    """Query player status prioritizing MP Audio Player, then MPRIS/playerctl, then Audacious."""
    active_theme = get_theme_palette(cli_theme)
    status: Dict[str, Any] = {
        "player": "None",
        "state": "stopped",
        "title": "No Mix Playing",
        "raw_title": "",
        "artist": "MPlanetarian",
        "album": "",
        "position": "00:00",
        "duration": "00:00",
        "position_sec": 0.0,
        "duration_sec": 0.0,
        "progress_pct": 0.0,
        "active_file": "",
        "format": "",
        "sample_rate": "",
        "channels": "",
        "volume": 85,
        "pitch_percent": 0,
        "pitch_factor": 1.0,
        "levels": [0.0] * 24,
        "peaks": [0.0] * 24,
        "mini_eq": "",
        "tracklist": [],
        "tracklist_total": 0,
        "theme": active_theme
    }

    # 1. Check MP Audio Player first
    mp_active, mp_data = is_mp_player_active()
    if mp_active and mp_data:
        status["player"] = "MP Audio Player"
        status["state"] = str(mp_data.get("state", "stopped")).lower()
        raw_title = str(mp_data.get("title", ""))
        active_path = str(mp_data.get("path", ""))
        status["raw_title"] = raw_title
        status["active_file"] = active_path
        status["position"] = str(mp_data.get("position_fmt", "00:00"))
        status["duration"] = str(mp_data.get("duration_fmt", "--:--"))
        status["position_sec"] = float(mp_data.get("position_sec", 0.0))
        status["duration_sec"] = float(mp_data.get("duration_sec", 0.0))
        status["progress_pct"] = float(mp_data.get("progress_pct", 0.0))
        status["volume"] = int(mp_data.get("volume", 85))
        status["pitch_percent"] = int(mp_data.get("pitch_percent", 0))
        status["pitch_factor"] = float(mp_data.get("pitch_factor", 1.0))
        status["levels"] = mp_data.get("levels", [0.0] * 24)
        status["peaks"] = mp_data.get("peaks", [0.0] * 24)
        status["mini_eq"] = str(mp_data.get("mini_eq", ""))

        sr = mp_data.get("sample_rate", 0)
        status["sample_rate"] = f"{round(sr / 1000.0, 1)} kHz" if sr else ""
        ch = mp_data.get("channels", 2)
        status["channels"] = "Stereo" if ch == 2 else ("Mono" if ch == 1 else f"{ch} Ch")
        if active_path:
            status["format"] = Path(active_path).suffix.lstrip(".").upper()

        # Parse tracklist and metadata
        tl_path = find_tracklist_for_mix(active_path)
        tl_info = parse_tracklist_file(tl_path) if tl_path else {"metadata": {}, "tracks": []}
        title, artist, album = clean_track_title(raw_title, active_path, tl_info.get("metadata", {}))
        status["title"] = title
        status["artist"] = artist
        status["album"] = album
        status["tracklist"] = tl_info.get("tracks", [])
        status["tracklist_total"] = len(status["tracklist"])
        return status

    # 2. Try playerctl if available
    if shutil.which("playerctl"):
        try:
            p_state = subprocess.check_output(["playerctl", "status"], stderr=subprocess.DEVNULL).decode('utf-8').strip().lower()
            p_title = subprocess.check_output(["playerctl", "metadata", "title"], stderr=subprocess.DEVNULL).decode('utf-8').strip()
            p_artist = subprocess.check_output(["playerctl", "metadata", "artist"], stderr=subprocess.DEVNULL).decode('utf-8').strip()
            p_pos = float(subprocess.check_output(["playerctl", "position"], stderr=subprocess.DEVNULL).decode('utf-8').strip() or 0)
            status["state"] = p_state
            status["title"] = p_title or "DJ Mix Session"
            status["artist"] = p_artist or "MPlanetarian"
            status["player"] = "MPRIS / playerctl"
            status["position"] = f"{int(p_pos // 60):02d}:{int(p_pos % 60):02d}"
            status["position_sec"] = p_pos
            return status
        except Exception:
            pass

    # 3. Try audacious / qdbus
    if shutil.which("qdbus"):
        try:
            aud_state = subprocess.check_output(["qdbus", "org.mpris.MediaPlayer2.audacious", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player.PlaybackStatus"], stderr=subprocess.DEVNULL).decode('utf-8').strip().lower()
            if aud_state:
                status["player"] = "Audacious"
                status["state"] = aud_state
                status["title"] = "Audacious Active Mix"
                return status
        except Exception:
            pass

    return status


def control_player(action: str, params: Optional[Dict[str, List[str]]] = None) -> bool:
    """Send playback control commands routing to MP Audio Player IPC or playerctl."""
    params = params or {}
    mp_active, _ = is_mp_player_active()

    if mp_active:
        if action in ("play-pause", "toggle"):
            return send_mp_player_command("play_pause")
        elif action == "play":
            return send_mp_player_command("play")
        elif action == "pause":
            return send_mp_player_command("pause")
        elif action == "next":
            return send_mp_player_command("next")
        elif action in ("previous", "prev"):
            return send_mp_player_command("prev")
        elif action == "seek_forward":
            return send_mp_player_command("seek", seconds=30.0)
        elif action == "seek_backward":
            return send_mp_player_command("seek", seconds=-30.0)
        elif action == "seek":
            sec = float(params.get("seconds", [10.0])[0])
            return send_mp_player_command("seek", seconds=sec)
        elif action == "seek_to":
            pos = float(params.get("position", [0.0])[0])
            return send_mp_player_command("seek_to", position=pos)
        elif action == "vol_up":
            return send_mp_player_command("vol_up", step=5)
        elif action == "vol_down":
            return send_mp_player_command("vol_down", step=5)
        elif action == "set_volume":
            vol = int(params.get("volume", [85])[0])
            return send_mp_player_command("set_volume", volume=vol)
        elif action == "mute":
            return send_mp_player_command("mute")
        elif action == "pitch_up":
            return send_mp_player_command("pitch_up", step=1)
        elif action == "pitch_down":
            return send_mp_player_command("pitch_down", step=1)
        elif action == "reset_pitch":
            return send_mp_player_command("reset_pitch")

    # Fallback to playerctl
    if shutil.which("playerctl"):
        if action in ["play-pause", "play", "pause", "next", "previous"]:
            subprocess.run(["playerctl", action], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif action == "seek_forward":
            subprocess.run(["playerctl", "position", "30+"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif action == "seek_backward":
            subprocess.run(["playerctl", "position", "30-"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    return False


# ------------------------------------------------------------------------------
# DYNAMIC HTML TEMPLATE
# ------------------------------------------------------------------------------
def render_html_page(theme: Dict[str, Any]) -> str:
    """Render companion HTML pre-injected with current Manager theme variables."""
    t = theme
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>MP Mix Manager — DJ Booth Remote</title>
    <style>
        :root {{
            --bg: {t['bg']};
            --card-bg: {t['card_bg']};
            --card-border: {t['card_border']};
            --card-shadow: {t['card_shadow']};
            --text-main: {t['text_main']};
            --text-dim: {t['text_dim']};
            --accent-primary: {t['accent_primary']};
            --accent-secondary: {t['accent_secondary']};
            --accent-tertiary: {t['accent_tertiary']};
            --accent-crimson: {t['accent_crimson']};
            --header-gradient: {t['header_gradient']};
            --btn-gradient: {t['btn_gradient']};
            --btn-shadow: {t['btn_shadow']};
            --progress-fill: {t['progress_fill']};
            --badge-bg: {t['badge_bg']};
            --badge-color: {t['badge_color']};
            --eq-bar: {t['eq_bar']};
            --eq-peak: {t['eq_peak']};
        }}
        * {{
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 16px 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            transition: background-color 0.35s ease, color 0.35s ease;
        }}
        .header {{
            text-align: center;
            margin-bottom: 16px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 1.75rem;
            background: var(--header-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }}
        .header p {{
            margin: 4px 0 8px 0;
            font-size: 0.85rem;
            color: var(--text-dim);
            font-weight: 500;
        }}
        .theme-pill {{
            display: inline-block;
            font-size: 0.72rem;
            padding: 3px 12px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-dim);
            border: 1px solid var(--card-border);
            letter-spacing: 0.5px;
            font-weight: 600;
            transition: all 0.3s ease;
        }}
        .card {{
            background-color: var(--card-bg);
            border-radius: 18px;
            padding: 22px;
            width: 100%;
            max-width: 520px;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--card-border);
            margin-bottom: 16px;
            transition: background-color 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease;
        }}
        .badges-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            margin-bottom: 12px;
        }}
        .badge {{
            background: var(--badge-bg);
            color: var(--badge-color);
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            border: 1px solid var(--badge-color);
            transition: all 0.25s ease;
        }}
        .badge-source {{
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-dim);
            border-color: rgba(255, 255, 255, 0.12);
        }}
        .track-info {{
            text-align: center;
            width: 100%;
            margin-bottom: 14px;
        }}
        .track-title {{
            font-size: 1.25rem;
            font-weight: 800;
            margin: 0 0 6px 0;
            line-height: 1.35;
            color: var(--text-main);
            word-break: break-word;
        }}
        .track-artist {{
            font-size: 0.95rem;
            color: var(--accent-primary);
            font-weight: 600;
            margin: 0 0 6px 0;
        }}
        .track-specs {{
            font-size: 0.75rem;
            color: var(--text-dim);
            letter-spacing: 0.5px;
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 4px;
        }}
        .spec-chip {{
            background: rgba(255, 255, 255, 0.04);
            padding: 2px 8px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        /* Visualizer */
        .visualizer-container {{
            width: 100%;
            height: 48px;
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 3px;
            margin: 12px 0 16px 0;
            padding: 0 4px;
            background: rgba(0, 0, 0, 0.25);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .v-bar {{
            flex: 1;
            max-width: 14px;
            height: 4%;
            background: var(--eq-bar);
            border-radius: 2px 2px 0 0;
            transition: height 0.08s ease-out;
            box-shadow: 0 0 5px var(--eq-bar);
            position: relative;
        }}
        /* Progress Bar */
        .progress-box {{
            width: 100%;
            margin-bottom: 16px;
        }}
        .progress-bar-bg {{
            width: 100%;
            height: 9px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 5px;
            cursor: pointer;
            overflow: hidden;
            position: relative;
            touch-action: none;
        }}
        .progress-bar-fill {{
            height: 100%;
            width: 0%;
            background: var(--progress-fill);
            border-radius: 5px;
            transition: width 0.15s ease-out;
        }}
        .time-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: var(--text-dim);
            font-weight: 600;
            font-variant-numeric: tabular-nums;
            margin-top: 6px;
        }}
        /* Controls */
        .controls-row {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            width: 100%;
            margin-top: 8px;
        }}
        button {{
            background: rgba(255, 255, 255, 0.07);
            color: var(--text-main);
            border: 1px solid var(--card-border);
            padding: 12px 16px;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.1s ease, background-color 0.15s ease, box-shadow 0.15s ease;
            user-select: none;
        }}
        button:active {{
            transform: scale(0.94);
            background: var(--accent-primary);
            color: #000;
        }}
        .btn-main {{
            background: var(--btn-gradient);
            color: #fff;
            padding: 14px 24px;
            font-size: 1.15rem;
            box-shadow: var(--btn-shadow);
            border: none;
            flex-grow: 1;
            max-width: 180px;
        }}
        .btn-sub {{
            padding: 10px 14px;
            font-size: 0.88rem;
        }}
        /* Secondary Controls */
        .sec-controls {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            width: 100%;
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
        }}
        .control-group {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex: 1;
            justify-content: center;
        }}
        .control-pill {{
            font-size: 0.78rem;
            color: var(--text-dim);
            font-weight: 700;
            min-width: 52px;
            text-align: center;
            font-variant-numeric: tabular-nums;
        }}
        .btn-mini {{
            padding: 6px 10px;
            font-size: 0.78rem;
            border-radius: 8px;
        }}
        /* Tracklist Section */
        .tracklist-card {{
            max-height: 280px;
            display: flex;
            flex-direction: column;
        }}
        .tl-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.07);
        }}
        .tl-header h3 {{
            margin: 0;
            font-size: 0.92rem;
            color: var(--accent-secondary);
            font-weight: 800;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .tl-count {{
            font-size: 0.72rem;
            color: var(--text-dim);
            font-weight: 700;
        }}
        .tl-items {{
            overflow-y: auto;
            flex: 1;
            padding-right: 4px;
            list-style: none;
            margin: 0;
            padding-left: 0;
        }}
        .tl-item {{
            padding: 6px 10px;
            margin-bottom: 4px;
            border-radius: 6px;
            font-size: 0.82rem;
            line-height: 1.35;
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.02);
            border-left: 3px solid var(--accent-primary);
        }}
        .tl-item:nth-child(even) {{
            background: rgba(255, 255, 255, 0.04);
        }}
        .footer {{
            margin-top: auto;
            text-align: center;
            font-size: 0.72rem;
            color: var(--text-dim);
            opacity: 0.75;
            padding: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>MP MIX MANAGER</h1>
        <p>Studio & DJ Booth Mobile Companion</p>
        <div id="themeBadge" class="theme-pill">🎨 {html.escape(t['name'])}</div>
    </div>

    <div class="card now-playing">
        <div class="badges-row">
            <div id="playBadge" class="badge">STANDBY</div>
            <div id="sourceBadge" class="badge badge-source">CHECKING...</div>
        </div>

        <div class="track-info">
            <div id="trackTitle" class="track-title">Connecting to MP Mix Session...</div>
            <div id="trackArtist" class="track-artist">—</div>
            <div id="trackSpecs" class="track-specs">
                <span id="specFormat" class="spec-chip">FLAC / WAV</span>
                <span id="specRate" class="spec-chip">48 kHz</span>
                <span id="specChannels" class="spec-chip">Stereo</span>
            </div>
        </div>

        <!-- 24-Bar Audio Visualizer -->
        <div class="visualizer-container" id="visContainer">
            {"".join(f'<div class="v-bar" id="vb{i}"></div>' for i in range(24))}
        </div>

        <!-- Progress & Time -->
        <div class="progress-box">
            <div class="progress-bar-bg" id="progressBg" onclick="seekClick(event)">
                <div class="progress-bar-fill" id="progressBar"></div>
            </div>
            <div class="time-row">
                <span id="posTime">00:00</span>
                <span id="durTime">--:--</span>
            </div>
        </div>

        <!-- Primary Controls -->
        <div class="controls-row">
            <button class="btn-sub" onclick="sendAction('seek_backward')" title="Rewind 30s">⏪ 30s</button>
            <button onclick="sendAction('previous')" title="Previous Track">⏮</button>
            <button class="btn-main" id="btnPlayPause" onclick="sendAction('play-pause')">⏯ Play</button>
            <button onclick="sendAction('next')" title="Next Track">⏭</button>
            <button class="btn-sub" onclick="sendAction('seek_forward')" title="Forward 30s">30s ⏩</button>
        </div>

        <!-- Secondary Controls: Volume & Pitch -->
        <div class="sec-controls">
            <div class="control-group">
                <button class="btn-mini" onclick="sendAction('vol_down')">🔉 -</button>
                <span class="control-pill" id="volPill">Vol: 85%</span>
                <button class="btn-mini" onclick="sendAction('vol_up')">+ 🔊</button>
                <button class="btn-mini" onclick="sendAction('mute')">🔇</button>
            </div>
            <div class="control-group">
                <button class="btn-mini" onclick="sendAction('pitch_down')">[-]</button>
                <span class="control-pill" id="pitchPill">Pitch: 0%</span>
                <button class="btn-mini" onclick="sendAction('pitch_up')">[+]</button>
                <button class="btn-mini" onclick="sendAction('reset_pitch')">0</button>
            </div>
        </div>
    </div>

    <!-- Tracklist Card -->
    <div class="card tracklist-card" id="tlCard" style="display: none;">
        <div class="tl-header">
            <h3>📜 Mix Tracklist</h3>
            <span class="tl-count" id="tlCount">0 Tracks</span>
        </div>
        <ul class="tl-items" id="tlItems"></ul>
    </div>

    <div class="footer">
        MP Mix Manager v0.3 • MPlanetarian Dreamworlds Productions
    </div>

    <script>
        let currentThemeId = "{t['id']}";
        let currentDurationSec = 0;
        let lastLoadedMix = "";

        function applyTheme(themeObj) {{
            if (!themeObj || !themeObj.id || themeObj.id === currentThemeId) return;
            currentThemeId = themeObj.id;
            const root = document.documentElement;
            const vars = themeObj.vars || themeObj;
            for (const [k, v] of Object.entries(vars)) {{
                if (typeof v === 'string') {{
                    root.style.setProperty('--' + k.replace(/_/g, '-'), v);
                }}
            }}
            const badge = document.getElementById('themeBadge');
            if (badge && themeObj.name) {{
                badge.innerText = '🎨 ' + themeObj.name;
            }}
        }}

        function updateVisualizer(levels, isPlaying) {{
            for (let i = 0; i < 24; i++) {{
                const bar = document.getElementById('vb' + i);
                if (!bar) continue;
                if (!isPlaying) {{
                    bar.style.height = '4%';
                    continue;
                }}
                const lvl = (levels && levels[i] !== undefined) ? levels[i] : 0.05;
                const h = Math.max(4, Math.min(100, Math.round(lvl * 100)));
                bar.style.height = h + '%';
            }}
        }}

        function seekClick(e) {{
            if (!currentDurationSec || currentDurationSec <= 0) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const pct = Math.max(0, Math.min(1, clickX / rect.width));
            const seekPos = pct * currentDurationSec;
            sendAction('seek_to', {{ position: seekPos.toFixed(1) }});
        }}

        async function fetchStatus() {{
            try {{
                const res = await fetch('/api/status');
                const data = await res.json();

                // 1. Dynamic theme sync
                if (data.theme && data.theme.id !== currentThemeId) {{
                    applyTheme(data.theme);
                }}

                // 2. Playback identity
                document.getElementById('trackTitle').innerText = data.title || "No Mix Playing";
                const artistStr = data.album ? (data.artist + " • " + data.album) : (data.artist || "MPlanetarian");
                document.getElementById('trackArtist').innerText = artistStr;

                // 3. Status Badges
                const badge = document.getElementById('playBadge');
                const state = (data.state || "stopped").toLowerCase();
                badge.innerText = state.toUpperCase();
                if (state === 'playing') {{
                    badge.style.background = 'var(--badge-bg)';
                    badge.style.color = 'var(--badge-color)';
                    badge.style.borderColor = 'var(--badge-color)';
                    document.getElementById('btnPlayPause').innerText = '⏸ Pause';
                }} else {{
                    badge.style.background = 'rgba(255, 170, 0, 0.15)';
                    badge.style.color = '#ffaa00';
                    badge.style.borderColor = '#ffaa00';
                    document.getElementById('btnPlayPause').innerText = '⏯ Play';
                }}

                const srcBadge = document.getElementById('sourceBadge');
                srcBadge.innerText = (data.player || "None").toUpperCase();

                // 4. Progress & Time
                document.getElementById('posTime').innerText = data.position || "00:00";
                document.getElementById('durTime').innerText = data.duration || "--:--";
                currentDurationSec = data.duration_sec || 0;
                const pct = Math.max(0, Math.min(100, data.progress_pct || 0));
                document.getElementById('progressBar').style.width = pct + '%';

                // 5. Specs chips
                document.getElementById('specFormat').innerText = data.format || "AUDIO";
                document.getElementById('specRate').innerText = data.sample_rate || "48.0 kHz";
                document.getElementById('specChannels').innerText = data.channels || "Stereo";

                // 6. Volume & Pitch
                document.getElementById('volPill').innerText = 'Vol: ' + (data.volume ?? 85) + '%';
                const p = data.pitch_percent || 0;
                document.getElementById('pitchPill').innerText = 'Pitch: ' + (p > 0 ? '+' : '') + p + '%';

                // 7. Visualizer
                updateVisualizer(data.levels, state === 'playing');

                // 8. Tracklist population
                if (data.tracklist && data.tracklist.length > 0) {{
                    const tlCard = document.getElementById('tlCard');
                    tlCard.style.display = 'flex';
                    document.getElementById('tlCount').innerText = data.tracklist.length + ' Tracks';
                    const key = (data.active_file || data.title);
                    if (key !== lastLoadedMix) {{
                        lastLoadedMix = key;
                        const listEl = document.getElementById('tlItems');
                        listEl.innerHTML = '';
                        data.tracklist.forEach(t => {{
                            const li = document.createElement('li');
                            li.className = 'tl-item';
                            li.innerText = t;
                            listEl.appendChild(li);
                        }});
                    }}
                }} else {{
                    document.getElementById('tlCard').style.display = 'none';
                }}
            }} catch (e) {{}}
        }}

        async function sendAction(act, params = {{}}) {{
            let url = '/api/control?action=' + encodeURIComponent(act);
            for (const [k, v] of Object.entries(params)) {{
                url += '&' + encodeURIComponent(k) + '=' + encodeURIComponent(v);
            }}
            try {{
                await fetch(url, {{ method: 'POST' }});
                setTimeout(fetchStatus, 150);
            }} catch (e) {{}}
        }}

        setInterval(fetchStatus, 1000);
        fetchStatus();
    </script>
</body>
</html>
"""


# ------------------------------------------------------------------------------
# HTTP SERVER & API HANDLER
# ------------------------------------------------------------------------------
class CompanionHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            current_theme = get_theme_palette(CLI_THEME)
            html_content = render_html_page(current_theme)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        elif url.path == "/api/status":
            status = get_playback_status(CLI_THEME)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode("utf-8"))
        elif url.path == "/api/theme":
            theme = get_theme_palette(CLI_THEME)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(theme).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/api/control":
            params = urllib.parse.parse_qs(url.query)
            action = params.get("action", [""])[0]
            success = control_player(action, params)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "action": action}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet logging for mobile polling


def main():
    global CLI_THEME
    parser = argparse.ArgumentParser(description="MP Mix Manager Mobile Web Companion")
    parser.add_argument("--port", "-p", type=int, default=PORT, help=f"Server port (default: {PORT})")
    parser.add_argument("--theme", "-t", type=str, default=None, help="Theme name override (e.g. cosmic_supernova, dreamworlds, dracula, matrix, nord)")
    args = parser.parse_args()

    CLI_THEME = args.theme
    active_theme = get_theme_palette(CLI_THEME)
    ip = get_local_ip()

    server_address = ('0.0.0.0', args.port)
    httpd = http.server.ThreadingHTTPServer(server_address, CompanionHandler)

    print(f"\n======================================================================")
    print(f"  🌌 MP MIX ARCHIVE MANAGER — MOBILE WEB COMPANION")
    print(f"======================================================================")
    print(f"  • Active Theme:   {active_theme['name']} ({active_theme['id']})")
    print(f"  • Local Machine:  http://localhost:{args.port}")
    print(f"  • Phone / Tablet: http://{ip}:{args.port}")
    print(f"======================================================================\n")
    print("Press Ctrl+C to stop the companion server.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Web Companion...")
        httpd.server_close()


if __name__ == "__main__":
    main()
