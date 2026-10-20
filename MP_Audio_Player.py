#!/usr/bin/env python3
"""
MP_Audio_Player.py - High-Resolution Audio Player & Custom Animated Equalizer
Part of MP_Mix_Manager_v0.3 (Dreamworlds Productions)

Features:
  - Universal audio playback supporting FLAC, WAV, MP3, AAC, OGG, and AIFF.
  - Multi-band Custom Animated Equalizer (Real-time FFT, Dual Stereo L/R, VU Meters, Oscilloscope).
  - Seamless archive scanning across all configured MP Mix Archive Manager locations.
  - Interactive terminal TUI with live spectrum visualization, playlist browser, and filter search.
  - Headless background daemon mode with Unix socket IPC & JSON state synchronization.
  - Full remote control from CLI or anywhere in Mix_Archive_Manager.sh (Space: Play/Pause, Next/Prev, Vol, Seek).
"""

from __future__ import annotations
import os, re, sys, time, datetime, math, random, json, socket, select, shutil, argparse, threading, subprocess, unicodedata, queue, collections
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

def _get_app_version() -> str:
    ver = os.environ.get("VERSION")
    if ver:
        return ver.strip()
    s_dir = Path(__file__).resolve().parent
    for cand in [s_dir / "VERSION", s_dir.parent / "VERSION"]:
        if cand.is_file():
            try:
                return cand.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return "0.3.6 Beta"

VERSION = _get_app_version()

try:
    from mp_activity_tracker import record_activity
    from mp_logging import log_error as mp_log_error
except ImportError:
    try:
        from scripts.mp_activity_tracker import record_activity
        from scripts.mp_logging import log_error as mp_log_error
    except ImportError:
        def record_activity(*args, **kwargs): pass
        def mp_log_error(*args, **kwargs): pass

np = sf = sd = None

def _ensure_numpy():
    global np
    if np is None:
        try:
            import numpy as _np
            np = _np
        except ImportError:
            sys.exit("Error: numpy is required for MP_Audio_Player.py")
    return np

def _ensure_audio_backends():
    global np, sf, sd
    _ensure_numpy()
    if sf is None:
        try: import soundfile as sf
        except ImportError: pass
    if sd is None:
        try: import sounddevice as sd
        except ImportError: pass

try:
    import termios, tty
except ImportError:
    termios = tty = None

# ANSI TrueColor Palette
BOLD, DIM, ITALIC, NC = "\033[1m", "\033[2m", "\033[3m", "\033[0m"
COLOR_HOT_PURPLE = "\033[38;2;166;77;255m"
COLOR_INDIGO_BLUE = "\033[38;2;102;102;255m"
COLOR_LILAC = "\033[38;2;153;153;255m"
COLOR_TRAFFIC_GREEN = "\033[38;2;0;255;0m"
COLOR_TRAFFIC_AMBER = "\033[38;2;255;153;51m"
COLOR_TRAFFIC_RED = "\033[38;2;255;0;0m"
COLOR_MAIN_FG = "\033[38;2;209;209;224m"
COLOR_NEON_PINK = "\033[38;2;247;37;133m"
COLOR_ELECTRIC_CYAN = "\033[38;2;0;229;255m"
WHITE = "\033[1;37m"

RED, GREEN, YELLOW = COLOR_TRAFFIC_RED, COLOR_TRAFFIC_GREEN, COLOR_TRAFFIC_AMBER
MAGENTA, CYAN = COLOR_HOT_PURPLE, COLOR_LILAC

CONFIG_DIR = Path.home() / ".config" / "mix-manager"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SOCKET_PATH, PORT_FILE = CONFIG_DIR / "mp_audio_player.sock", CONFIG_DIR / "mp_audio_player.port"
STATE_FILE, PID_FILE = CONFIG_DIR / "mp_player_state.json", CONFIG_DIR / "mp_player.pid"
DURATION_CACHE_FILE = CONFIG_DIR / "track_durations.json"

AUDIO_EXTENSIONS = ('.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac', '.aiff', '.wma')
UNICODE_BLOCKS = [' ', ' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']

# Git Bash on this PC uses Lucida Console or Consolas. Neither font includes the
# eighth-block caps (▂▃▅▆▇), the prism peaks (✦ ◆ ━), or the playlist triangle (▶).
# Those cells render as the wrong glyph. WGL4 substitutes below are in both fonts.
_PRISM_LEVELS_FULL = (" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")
_PRISM_LEVELS_LIMITED = (" ", "▄", "▄", "▄", "▄", "█", "█", "█", "█")
PLAYLIST_ACTIVE_MARK = "\u25ba"  # ►


def _use_limited_console_glyphs() -> bool:
    if os.name == "nt" or sys.platform in ("win32", "cygwin"):
        return True
    return bool(os.environ.get("MSYSTEM"))


def prism_level_glyph(eighth: int) -> str:
    level = max(0, min(8, int(eighth)))
    table = _PRISM_LEVELS_LIMITED if _use_limited_console_glyphs() else _PRISM_LEVELS_FULL
    return table[level]


def prism_peak_glyph(hot: bool, column: int = 0) -> str:
    if _use_limited_console_glyphs():
        return "\u25b2" if hot else "\u2500"  # ▲ sits on the bar; ─ is the hold line
    if hot:
        return "\u2726" if (column % 2 == 0) else "\u25c6"
    return "\u2501"


def meter_peak_glyph() -> str:
    """Peak mark above a Dual Stereo or Master Spectrum bar."""
    if _use_limited_console_glyphs():
        return "\u2500"  # ─
    return "\u2594"  # ▔


def meter_level_char(frac: float, peak_here: bool) -> str:
    if frac >= 1.0:
        return "█"
    if frac > 0.0:
        return prism_level_glyph(max(1, min(8, int(frac * 8))))
    if peak_here:
        return meter_peak_glyph()
    return " "


# Stardust marks missing from Lucida Console and Consolas, mapped to marks both fonts draw.
_STARDUST_SAFE = {
    "✦": "•",
    "✧": "°",
    "⋆": "·",
    "◆": "•",
    "╵": "│",
    "▔": "─",
    "⠄": "·",
    "⠂": ".",
    "⠁": ".",
    "⠈": "'",
    "⡀": ".",
}


def console_symbol(ch: str) -> str:
    if not _use_limited_console_glyphs():
        return ch
    return _STARDUST_SAFE.get(ch, ch)


def stardust_dust_choices(tier: str) -> List[str]:
    if _use_limited_console_glyphs():
        return {
            "hot": ["•", "°", "·", "˙", "+"],
            "mid": ["•", "°", "·", "˙", ".", "*"],
            "low": ["·", "˙", ".", "*", "'", ","],
        }[tier]
    return {
        "hot": ["✦", "✧", "⋆", "•", "°"],
        "mid": ["•", "°", "·", "˙", "⠄", "⠂"],
        "low": ["·", "˙", "⠄", "⠂", "⠁", "⠈", "⡀"],
    }[tier]


def music_library_label(folder_name: str) -> str:
    """Label for a configured music folder. ALL covers every folder the user has added."""
    name = str(folder_name or "ALL").strip() or "ALL"
    if name.upper() in ("ALL", "ALL_MUSIC_FOLDERS"):
        return "All Music Folders"
    return name

def is_cloud_or_remote_path(p: Union[str, Path, None]) -> bool:
    if not p: return False
    s = str(p)
    if s.startswith(("\\\\", "//", "smb://")): return True
    return any(k in s for k in ("GoogleDrive", "google3:", "MUSIC_SMB", "/run/media/", "/mnt/", "/media/", "/gvfs/smb-share:"))

def get_base_dir() -> Path:
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "scripts" else p.parent

try:
    _scripts_dir = str(get_base_dir() / "scripts")
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from monitor_bluetooth_audio import BluetoothAudioRouter, get_bluetooth_audio_status
except Exception:
    BluetoothAudioRouter = None
    get_bluetooth_audio_status = None


def parse_env_file(filepath: Path) -> Dict[str, str]:
    env = {}
    if filepath.is_file():
        try:
            for line in filepath.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"\'')
        except Exception:
            pass
    return env

def format_seconds(seconds: float) -> str:
    if seconds < 0 or math.isnan(seconds): return "00:00"
    s = int(seconds)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}" if h > 0 else f"{m:02d}:{sec:02d}"

def _run_bg(cmd: Union[List[str], str]) -> bool:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False

def _run_checked(cmd: List[str], timeout: float = 2.0) -> bool:
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=timeout)
        return res.returncode == 0
    except Exception:
        return False

def _normalize_reveal_path(target_path: Union[str, Path, None]) -> Optional[str]:
    """Turn a player path into a local filesystem path. file:// and Git-bash /x/ paths are accepted."""
    if target_path is None:
        return None
    raw = str(target_path).strip().strip('"')
    if not raw:
        return None
    if raw.lower().startswith("file:"):
        from urllib.parse import unquote, urlparse
        parsed = urlparse(raw)
        raw = unquote(parsed.path or "")
        if os.name == "nt" and len(raw) >= 3 and raw[0] == "/" and raw[2] == ":":
            raw = raw[1:]
    raw = os.path.expanduser(raw)
    if os.name == "nt":
        slash = raw.replace("\\", "/")
        drive = re.match(r"^/([a-zA-Z])/(.*)$", slash)
        if drive and not os.path.exists(raw):
            raw = drive.group(1).upper() + ":\\" + drive.group(2).replace("/", "\\")
        raw = os.path.normpath(raw)
    else:
        raw = os.path.abspath(raw)
    return raw

def choose_file_manager_target(current_path: Union[str, Path, None], selected_path: Union[str, Path, None] = None) -> Optional[str]:
    """Prefer the loaded track, then the highlighted playlist row. Both must exist on disk."""
    for candidate in (current_path, selected_path):
        normalized = _normalize_reveal_path(candidate)
        if normalized and os.path.exists(normalized):
            return normalized
    return None

def windows_explorer_select_command(path: str) -> str:
    """Command line Explorer actually parses. Quotes belong around the path only.

    subprocess lists turn this into "/select,C:\\My Mix.flac", and Explorer then
    opens Documents instead of the file.
    """
    shown = path.replace('"', "")
    if os.name == "nt":
        shown = os.path.normpath(shown)
    return f'explorer.exe /select,"{shown}"'

def _windows_shell_select(path: str) -> bool:
    """Ask Explorer to open the parent folder and highlight the file."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        norm = os.path.normpath(path)
        ole32.CoInitialize.argtypes = [ctypes.c_void_p]
        ole32.CoInitialize.restype = ctypes.c_long
        ole32.CoInitialize(None)
        shell32.ILCreateFromPathW.argtypes = [ctypes.c_wchar_p]
        shell32.ILCreateFromPathW.restype = ctypes.c_void_p
        shell32.ILFree.argtypes = [ctypes.c_void_p]
        shell32.ILFree.restype = None
        shell32.SHOpenFolderAndSelectItems.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_ulong
        ]
        shell32.SHOpenFolderAndSelectItems.restype = ctypes.c_long
        pidl = shell32.ILCreateFromPathW(norm)
        if not pidl:
            return False
        try:
            return int(shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0)) == 0
        finally:
            shell32.ILFree(pidl)
    except Exception:
        return False

def _file_uri(path: str) -> str:
    from urllib.parse import quote
    text = str(path).replace("\\", "/")
    if re.match(r"^[a-zA-Z]:/", text):
        return "file:///" + quote(text, safe="/:")
    if not text.startswith("/"):
        text = "/" + text
    return "file://" + quote(text, safe="/:")

def _reveal_folder(path: str, is_file: bool) -> str:
    if not is_file:
        return path
    text = str(path).rstrip("\\/")
    cut = max(text.rfind("/"), text.rfind("\\"))
    return text[:cut] if cut > 0 else text

def reveal_launch_plan(path: str, platform: str, is_file: Optional[bool] = None) -> List[Tuple[str, Union[List[str], str]]]:
    """Ordered open attempts for one path. mode is 'checked' or 'bg'."""
    kind = platform.lower()
    if kind in ("linux", "freebsd", "darwin"):
        target = str(path)
    else:
        target = _normalize_reveal_path(path) or str(path)
    file_target = os.path.isfile(target) if is_file is None else bool(is_file)
    folder = _reveal_folder(target, file_target)
    plan: List[Tuple[str, Union[List[str], str]]] = []
    if kind == "darwin":
        if file_target:
            plan.append(("bg", ["open", "-R", target]))
        else:
            plan.append(("bg", ["open", folder]))
        return plan

    if kind == "win32":
        if file_target:
            plan.append(("bg", windows_explorer_select_command(target)))
        else:
            plan.append(("bg", ["explorer.exe", folder]))
        return plan

    if kind == "wsl":
        plan.append(("wsl", target if file_target else folder))
        plan.append(("bg", ["wslview", folder]))
        return plan

    # Linux and FreeBSD. ShowItems selects the file in the desktop's file manager.
    if file_target:
        uri = _file_uri(target)
        name = target[len(folder) + 1:] if folder and target.startswith(folder) else os.path.basename(target)
        plan.append(("checked", [
            "dbus-send", "--session", "--type=method_call",
            "--dest=org.freedesktop.FileManager1",
            "/org/freedesktop/FileManager1",
            "org.freedesktop.FileManager1.ShowItems",
            f"array:string:{uri}", "string:",
        ]))
        plan.append(("checked", [
            "gdbus", "call", "--session",
            "--dest", "org.freedesktop.FileManager1",
            "--object-path", "/org/freedesktop/FileManager1",
            "--method", "org.freedesktop.FileManager1.ShowItems",
            f"['{uri}']", "",
        ]))
        plan.append(("checked", [
            "dbus-send", "--session", "--type=method_call",
            "--dest=org.xfce.FileManager",
            "/org/xfce/FileManager",
            "org.xfce.FileManager.DisplayFolderAndSelect",
            f"string:{folder}", f"string:{name}", "string:",
        ]))
        plan.extend([
            ("bg", ["dolphin", "--select", target]),
            ("bg", ["nautilus", "--select", target]),
            ("bg", ["nemo", target]),
            ("bg", ["caja", target]),
        ])
    plan.extend([
        ("bg", ["thunar", folder]),
        ("bg", ["pcmanfm-qt", folder]),
        ("bg", ["pcmanfm", folder]),
        ("bg", ["gio", "open", folder]),
        ("bg", ["xdg-open", folder]),
    ])
    return plan

def _execute_reveal_plan(plan: List[Tuple[str, Union[List[str], str]]], which=None) -> bool:
    finder = which or shutil.which
    for mode, cmd in plan:
        if mode == "wsl":
            win_path = str(cmd)
            if not (finder("wslpath") and finder("explorer.exe")):
                continue
            try:
                converted = subprocess.run(["wslpath", "-w", win_path], capture_output=True, text=True, timeout=2).stdout.strip()
            except Exception:
                converted = ""
            if not converted:
                continue
            select = os.path.isfile(win_path)
            launched = windows_explorer_select_command(converted) if select else f'explorer.exe "{converted}"'
            if _run_bg(["cmd.exe", "/c", launched]):
                return True
            continue
        if isinstance(cmd, str):
            if mode == "bg" and _run_bg(cmd):
                return True
            continue
        program = cmd[0]
        if program in ("dbus-send", "gdbus") and not finder(program):
            continue
        if program not in ("dbus-send", "gdbus") and not finder(program):
            continue
        if mode == "checked":
            if _run_checked(cmd):
                return True
        elif _run_bg(cmd):
            return True
    return False

def open_in_file_manager(target_path: Union[str, Path, None]) -> bool:
    normalized = _normalize_reveal_path(target_path)
    if not normalized or not os.path.exists(normalized):
        return False

    if sys.platform == "win32" and os.path.isfile(normalized):
        if _windows_shell_select(normalized):
            return True

    if sys.platform == "darwin":
        platform = "darwin"
    elif sys.platform == "win32":
        platform = "win32"
    elif Path("/proc/version").exists():
        try:
            wsl = "microsoft" in Path("/proc/version").read_text(errors="ignore").lower()
        except Exception:
            wsl = False
        platform = "wsl" if wsl else ("freebsd" if sys.platform.startswith("freebsd") else "linux")
    elif sys.platform.startswith("freebsd"):
        platform = "freebsd"
    else:
        platform = "linux"
    return _execute_reveal_plan(reveal_launch_plan(normalized, platform))

def find_tracklist_for_mix(mix_file: Union[str, Path, None]) -> Optional[str]:
    if not mix_file: return None
    p = Path(mix_file).expanduser().resolve()
    if not p.exists(): return None

    exact = p.parent / f"{p.stem}.txt"
    if exact.is_file(): return str(exact)

    base = get_base_dir()
    candidate_dirs = [d for d in {p.parent, p.parent / "FLAC_CONVERTED_OUTPUTS", p.parent.parent / "FLAC_CONVERTED_OUTPUTS",
                                  base / "FLAC_CONVERTED_OUTPUTS", base, p.parent.parent} if d.is_dir()]

    for d in candidate_dirs:
        c = d / f"{p.stem}.txt"
        if c.is_file(): return str(c)

    patterns = [
        re.search(r'[_\ -](\d{2,3})([_\ -]|$)', p.stem),
        re.search(r'(\d{4}-\d{2}-\d{2})', p.stem)
    ]
    tokens = [m.group(1) for m in patterns if m]
    clean = re.sub(r'[_\ -]+', ' ', re.sub(r'MPlanetarian|Stream|of|Frequency|Part|WMI|Mix', '', p.stem, flags=re.I)).strip()
    words = [w.lower() for w in clean.split() if len(w) >= 4]

    for d in candidate_dirs:
        try:
            for f in d.iterdir():
                if f.is_file() and f.suffix.lower() == ".txt":
                    fname = f.name.lower()
                    if any(t in fname for t in tokens) or (words and any(w in fname for w in words)):
                        return str(f)
        except Exception:
            pass

    sh_script = base / "Mix_Archive_Manager.sh"
    if sh_script.is_file():
        try:
            res = subprocess.run(["bash", "-c", f'source "{sh_script}" 2>/dev/null; find_mix_tracklist "{p}" 2>/dev/null'],
                                 capture_output=True, text=True, timeout=1.5)
            out_p = res.stdout.strip()
            if out_p and os.path.isfile(out_p): return out_p
        except Exception:
            pass
    return None

def open_tracklist_window(target_tracklist: Union[str, Path, None], audio_path: Optional[Union[str, Path]] = None) -> bool:
    if not target_tracklist: return False
    tl = Path(target_tracklist).expanduser().resolve()
    if not tl.is_file(): return False

    base = get_base_dir()
    v_sh = base / "scripts" / "view_tracklist_console.sh"
    if not v_sh.is_file(): v_sh = base / "view_tracklist_console.sh"
    t_str, v_str, title = str(tl), str(v_sh), "Mix Tracklist Viewer"
    a_str = str(Path(audio_path).expanduser().resolve()) if audio_path and os.path.exists(str(audio_path)) else ""
    if a_str:
        os.environ["MP_TRACKLIST_AUDIO_FILE"] = a_str
    sh_args = [v_str, t_str] + ([a_str] if a_str else [])

    cust = os.environ.get("TRACKLIST_VIEWER")
    if cust and cust not in ("console", "auto") and shutil.which(cust) and _run_bg([cust, t_str]):
        return True

    if sys.platform.startswith(("linux", "freebsd")):
        if shutil.which("konsole") and v_sh.is_file():
            if _run_bg(["konsole", "--hide-menubar", "--hide-tabbar", "--separate", "--qwindowtitle", title,
                        "-p", f"tabtitle={title}", "-p", "TerminalMargin=0", "-p", "TerminalColumns=95", "-p", "TerminalRows=35", "-e", "bash"] + sh_args):
                threading.Thread(target=lambda: (time.sleep(0.15), shutil.which("xprop") and subprocess.run(
                    ["xprop", "-name", title, "-f", "_MOTIF_WM_HINTS", "32c", "-set", "_MOTIF_WM_HINTS", "0x2, 0x0, 0x0, 0x0, 0x0"], capture_output=True)), daemon=True).start()
                return True
        xfce_cmd = f"bash '{v_str}' '{t_str}'" + (f" '{a_str}'" if a_str else "")
        for term, args in [
            ("gnome-terminal", [f"--title={title}", "--hide-menubar", "--", "bash"] + sh_args),
            ("xfce4-terminal", [f"--title={title}", "--hide-menubar", "--hide-borders", "-e", xfce_cmd]),
            ("alacritty", ["--title", title, "-e", "bash"] + sh_args),
            ("foot", ["-T", title, "bash"] + sh_args),
            ("xterm", ["-title", title, "-bd", "0", "-geometry", "95x35", "-e", "bash"] + sh_args),
            ("xdg-open", [t_str])
        ]:
            if shutil.which(term) and _run_bg([term] + args): return True
    elif sys.platform == "darwin":
        if v_sh.is_file():
            mac_args = f'\\"{v_str}\\" \\"{t_str}\\"' + (f' \\"{a_str}\\"' if a_str else "")
            cmd = f'tell application "Terminal" to do script "bash {mac_args}"'
            if _run_bg(["osascript", "-e", cmd]): return True
        return _run_bg(["open", t_str])
    elif sys.platform == "win32":
        try:
            os.startfile(t_str)
            return True
        except Exception:
            pass
    return False

def export_playlist_m3u(mixes: List[Dict[str, Any]], target_path: Union[str, Path, None]) -> Tuple[bool, str]:
    if not target_path: return False, "Destination path cannot be empty"
    try:
        tp = Path(str(target_path).strip()).expanduser()
        if tp.suffix.lower() != ".m3u": tp = tp.with_suffix(".m3u")
        tp.parent.mkdir(parents=True, exist_ok=True)
        with open(tp, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for m in mixes:
                title = m.get("name", Path(m.get("path", "")).stem)
                f.write(f"#EXTINF:-1,{title}\n{m.get('path')}\n")
        return True, str(tp.resolve())
    except Exception as e:
        return False, str(e)


def open_image_viewer(image_path: Union[str, Path]) -> bool:
    """Opens an image file (e.g. Spek spectrogram or cover art) in the system's preferred viewer."""
    ip = Path(image_path).expanduser().resolve()
    if not ip.is_file(): return False
    t_str = str(ip)
    if sys.platform.startswith(("linux", "freebsd")):
        for viewer in ["gwenview", "loupe", "eog", "feh", "xdg-open"]:
            if shutil.which(viewer):
                if _run_bg([viewer, t_str]):
                    return True
    elif sys.platform == "darwin":
        return _run_bg(["open", "-a", "Preview", t_str]) or _run_bg(["open", t_str])
    elif sys.platform == "win32":
        try:
            os.startfile(t_str)
            return True
        except Exception: pass
    return False


def get_default_spek_dir(base_dir: Optional[Path] = None, mode: str = "MIX_ARCHIVE", audio_path: Optional[str] = None) -> Path:
    """Resolves local storage directory for Spek spectrograms (SPEK_OUTPUTS)."""
    base = base_dir or get_base_dir()
    cand_dirs: List[Path] = []

    mix_arc = os.environ.get("MIX_ARCHIVE_DIR")
    if not mix_arc:
        for cfg_cand in [base / "config.env", Path.home() / ".config" / "mix-manager" / "config.env"]:
            if cfg_cand.is_file():
                try:
                    for line in cfg_cand.read_text(encoding="utf-8").splitlines():
                        if line.strip().startswith("MIX_ARCHIVE_DIR="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and os.path.isdir(val):
                                mix_arc = val
                                break
                except Exception:
                    pass
            if mix_arc:
                break

    if mix_arc and os.path.isdir(mix_arc):
        cand_dirs.append(Path(mix_arc) / "SPEK_OUTPUTS")

    cand_dirs.append(base / "SPEK_OUTPUTS")
    cand_dirs.append(Path.home() / ".config" / "mix-manager" / "SPEK_OUTPUTS")

    for d in cand_dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d.resolve()
        except Exception:
            pass

    fallback = base / "SPEK_OUTPUTS"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()


def get_recording_output_dir(base_dir: Optional[Path] = None) -> Path:
    """Resolves local storage directory for MP Audio Player recordings (MP_AUDIOWAV_REC_OUTPUT)."""
    base = base_dir or get_base_dir()
    cand_dirs: List[Path] = []

    mix_arc = os.environ.get("MIX_ARCHIVE_DIR")
    if not mix_arc:
        for cfg_cand in [base / "config.env", Path.home() / ".config" / "mix-manager" / "config.env"]:
            if cfg_cand.is_file():
                try:
                    for line in cfg_cand.read_text(encoding="utf-8").splitlines():
                        if line.strip().startswith("MIX_ARCHIVE_DIR="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and os.path.isdir(val):
                                mix_arc = val
                                break
                except Exception:
                    pass
            if mix_arc:
                break

    if mix_arc and os.path.isdir(mix_arc):
        cand_dirs.append(Path(mix_arc) / "MP_AUDIOWAV_REC_OUTPUT")

    cand_dirs.append(base / "MP_AUDIOWAV_REC_OUTPUT")
    cand_dirs.append(Path.home() / ".config" / "mix-manager" / "MP_AUDIOWAV_REC_OUTPUT")

    for d in cand_dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d.resolve()
        except Exception:
            pass

    fallback = base / "MP_AUDIOWAV_REC_OUTPUT"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()


# Maximum file size per WAV recording part before rolling over to a new file (3GB)
REC_MAX_FILE_BYTES = 3 * 1024 * 1024 * 1024


def find_existing_spek(audio_path: Optional[Union[str, Path]], mode: str = "MIX_ARCHIVE", output_dir: Optional[Union[str, Path]] = None) -> Optional[str]:
    """Checks if a Spek spectrogram image already exists on disk for the given audio file."""
    if not audio_path:
        return None
    p = Path(audio_path).expanduser()
    stem = p.stem
    clean_stem = re.sub(r'[\/\\:\*\?"<>\|]', '_', stem)
    base = get_base_dir()

    cand_dirs: List[Path] = []
    if output_dir:
        cand_dirs.append(Path(output_dir))
    cand_dirs.append(get_default_spek_dir(base, mode=mode, audio_path=str(audio_path)))
    if p.parent.is_dir():
        cand_dirs.append(p.parent / "SPEK_OUTPUTS")
        cand_dirs.append(p.parent)
        if p.parent.parent.is_dir():
            cand_dirs.append(p.parent.parent / "SPEK_OUTPUTS")
    cand_dirs.append(base / "SPEK_OUTPUTS")

    seen_dirs = set()
    names: List[str] = []
    for s in (clean_stem, stem):
        for n in (f"{s}_spectrogram.png", f"{s}.spek.png", f"{s}.spek", f"{s}_spectrogram.jpg"):
            if n not in names:
                names.append(n)

    for d in cand_dirs:
        try:
            rd = str(d.resolve())
        except Exception:
            rd = str(d)
        if rd in seen_dirs or not d.is_dir():
            continue
        seen_dirs.add(rd)
        for name in names:
            cand = d / name
            try:
                if cand.is_file() and cand.stat().st_size > 0:
                    return str(cand.resolve())
            except Exception:
                pass
    return None


def generate_track_spek(audio_path: str, mode: str = "MIX_ARCHIVE", output_dir: Optional[Union[str, Path]] = None, force: bool = False) -> Tuple[bool, str]:
    """
    Generates a 1080p high-resolution spectrogram analysis (Spek) from an audio track or mix,
    saving the output locally into the configured SPEK_OUTPUTS folder.
    If the spectrogram already exists (and force is False), returns the existing file immediately.
    """
    if not audio_path or not os.path.isfile(audio_path):
        return False, "Audio file not found"

    if not force:
        existing = find_existing_spek(audio_path, mode=mode, output_dir=output_dir)
        if existing:
            return True, existing

    out_dir = Path(output_dir) if output_dir else get_default_spek_dir(get_base_dir(), mode=mode, audio_path=audio_path)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Failed to create SPEK output directory: {e}"

    stem = Path(audio_path).stem
    clean_stem = re.sub(r'[\/\\:\*\?"<>\|]', '_', stem)
    spek_file = out_dir / f"{clean_stem}_spectrogram.png"

    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-lavfi", "showspectrumpic=s=1920x1080:mode=combined:color=intensity:scale=log",
        "-update", "1", "-frames:v", "1", str(spek_file)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if spek_file.is_file() and spek_file.stat().st_size > 0:
            return True, str(spek_file.resolve())
        return False, "FFmpeg failed to produce spectrogram image"
    except Exception as exc:
        return False, f"Spectrogram generation error: {exc}"

def choose_export_m3u_gui() -> Optional[str]:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")): return None
    dt = os.path.join(os.path.expanduser("~/Desktop" if os.path.isdir(os.path.expanduser("~/Desktop")) else "~"), "MP_Archive_Playlist.m3u")
    for cmd in [
        ["kdialog", "--title", "Export MP Mix Archive Playlist (.m3u)", "--getsavefilename", dt, "*.m3u | M3U Playlist (*.m3u)"],
        ["zenity", "--file-selection", "--save", "--confirm-overwrite", f"--filename={dt}", "--file-filter=M3U Playlist (*.m3u) | *.m3u"]
    ]:
        if shutil.which(cmd[0]):
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else ""
            except Exception: pass
    return None

def choose_audio_file_gui() -> Optional[str]:
    """GUI file open dialog using kdialog, zenity, powershell, or applescript."""
    if sys.platform == "win32":
        try:
            ps_cmd = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.windows.forms') | Out-Null; "
                "$f = New-Object System.Windows.Forms.OpenFileDialog; "
                "$f.Filter = 'Audio Files (*.flac;*.wav;*.mp3;*.ogg;*.aac;*.m4a)|*.flac;*.wav;*.mp3;*.ogg;*.aac;*.m4a|All Files (*.*)|*.*'; "
                "$f.Title = 'Open Audio File in MP Audio Player'; "
                "if($f.ShowDialog() -eq 'OK'){ Write-Host $f.FileName }"
            )
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=120).stdout.strip()
            if out and os.path.isfile(out): return out
            return "" if out == "" else None
        except Exception:
            pass

    if sys.platform == "darwin":
        try:
            osa = 'choose file of type {"public.audio", "wav", "flac", "mp3", "ogg", "aac", "m4a"} with prompt "Open Audio File in MP Audio Player"'
            res = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True, timeout=120).stdout.strip()
            if res:
                p_res = subprocess.run(["osascript", "-e", f'POSIX path of "{res}"'], capture_output=True, text=True, timeout=10).stdout.strip()
                if p_res and os.path.isfile(p_res): return p_res
            return ""
        except Exception:
            pass

    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        home = os.path.expanduser("~")
        for cmd in [
            ["kdialog", "--title", "Open Audio File in MP Audio Player", "--getopenfilename", home, "*.flac *.wav *.mp3 *.ogg *.aac *.m4a *.aiff | Audio Files (*.flac *.wav *.mp3 *.ogg *.aac *.m4a *.aiff)"],
            ["zenity", "--file-selection", "--title=Open Audio File in MP Audio Player", f"--filename={home}/", "--file-filter=Audio Files (*.flac, *.wav, *.mp3, *.ogg, *.aac, *.m4a) | *.flac *.wav *.mp3 *.ogg *.aac *.m4a *.FLAC *.WAV *.MP3"],
        ]:
            if shutil.which(cmd[0]):
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else ""
                except Exception: pass
    return None

class MixArchiveScanner:
    def __init__(self, base_dir: Union[Path, str]):
        self.base_dir = Path(base_dir)
        self.mixes: List[Dict[str, Any]] = []
        self._load_and_scan()

    def _get_archive_dirs(self) -> List[Path]:
        dirs, seen = [], set()
        def add(p_str):
            if not p_str: return
            try:
                p = Path(os.path.expanduser(str(p_str).strip().strip('"\''))).resolve()
                if p.is_dir() and str(p) not in seen:
                    seen.add(str(p))
                    dirs.append(p)
            except Exception: pass

        def parse(extra):
            if extra:
                for part in re.split(r'[;\n,]|(?<!^[a-zA-Z]):(?![\\/])', extra): add(part)

        add(os.environ.get("MIX_ARCHIVE_DIR"))
        parse(os.environ.get("EXTRA_MIX_ARCHIVE_DIRS") or os.environ.get("MIX_ARCHIVE_DIRS"))

        env_files = [self.base_dir / "config.env", CONFIG_DIR / "config.env", Path(__file__).resolve().parent / "config.env"]
        if sys.platform == "win32": env_files.append(Path("B:/MIX_ARCHIVE/config.env"))
        for ef in env_files:
            cfg = parse_env_file(ef)
            add(cfg.get("MIX_ARCHIVE_DIR"))
            parse(cfg.get("EXTRA_MIX_ARCHIVE_DIRS") or cfg.get("MIX_ARCHIVE_DIRS"))

        for name in ("MIX_ARCHIVE", "FLAC_CONVERTED_OUTPUTS", "MP3_CONVERTED_OUTPUTS", "WAV_CONVERTED_OUTPUTS"):
            add(self.base_dir / name)

        if sys.platform == "win32":
            for d in ("B:/MIX_ARCHIVE", "B:/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS", "X:/MIX_ARCHIVE"): add(d)
            for l in ("B", "D", "E", "F", "G", "N", "V", "X", "Z"): add(f"{l}:/MIX_ARCHIVE")
        else:
            for p in ("/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE",
                      "/run/media/mplanetarian/DATA/MIX_ARCHIVE2/FLAC_CONVERTED_OUTPUTS",
                      os.path.expanduser("~/GoogleDrive/MIX_ARCHIVE")):
                add(p)

        # Fallback audio discovery paths only when user has not configured specific mix archives
        if not dirs:
            for fallback in (self.base_dir / "MIX_ARCHIVE", self.base_dir / "FLAC_CONVERTED_OUTPUTS",
                             self.base_dir, Path.home() / "Music"):
                if fallback != Path.home() and fallback != Path("/"):
                    add(fallback)

        return dirs

    def _load_and_scan(self):
        seen, collected = set(), []
        home_path = Path.home()
        for ad in self._get_archive_dirs():
            if not ad.is_dir() or ad == home_path or ad == Path("/"): continue
            for root, subdirs, files in os.walk(ad):
                subdirs[:] = [d for d in subdirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', '.git', 'venv', '.venv')]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in AUDIO_EXTENSIONS:
                        fp = os.path.join(root, f)
                        if fp not in seen:
                            seen.add(fp)
                            try:
                                st = os.stat(fp)
                                collected.append({"name": f, "path": fp, "size_mb": st.st_size / (1024*1024),
                                                  "mtime": st.st_mtime, "ext": ext[1:].upper()})
                            except OSError: pass
        self.mixes = sorted(collected, key=lambda x: x["mtime"], reverse=True)

    def get_mixes(self, query: str = "") -> List[Dict[str, Any]]:
        q = query.lower()
        return [m for m in self.mixes if q in m["name"].lower() or q in m["path"].lower()] if q else self.mixes

    def get_latest_mix(self) -> Optional[Dict[str, Any]]:
        return self.mixes[0] if self.mixes else None

class MusicFolderPlaylistScanner:
    """Scanner for DJ Tracks Database from user-configured MUSIC Folders (local drives & SMB shares).
    Does NOT use MIX_ARCHIVE folders at all.
    Loads from pre-generated .json cache or .m3u8 playlists in PLAYLISTS_GENERATED.
    """
    def __init__(self, folder_name: Union[str, Path, None] = "ALL", playlist_path: Union[str, Path, None] = None):
        if folder_name and (str(folder_name).endswith((".json", ".m3u", ".m3u8")) or os.path.exists(str(folder_name))):
            playlist_path = folder_name
            folder_name = "ALL"
            m = re.match(r'^DJ_Tracks_(.+)\.(?:json|m3u8?)$', os.path.basename(str(playlist_path)), re.I)
            if m and m.group(1).upper() != "ALL_MUSIC_FOLDERS":
                folder_name = m.group(1)
        self.folder_name = str(folder_name or "ALL").upper()
        self.base_dir = get_base_dir()
        self.mixes: List[Dict[str, Any]] = []
        self.playlist_path = Path(playlist_path) if playlist_path else None
        self._load_playlist()

    def _load_playlist(self):
        pl_dir = self.base_dir / "PLAYLISTS_GENERATED"
        if not self.playlist_path or not self.playlist_path.is_file():
            candidates = [
                pl_dir / f"DJ_Tracks_{self.folder_name}.json",
                pl_dir / f"DJ_Tracks_{self.folder_name}.m3u8",
                pl_dir / "DJ_Tracks_ALL_MUSIC_FOLDERS.json",
                pl_dir / "DJ_Tracks_ALL_MUSIC_FOLDERS.m3u8"
            ]
            for c in candidates:
                if c.is_file():
                    self.playlist_path = c
                    break

        if not self.playlist_path or not self.playlist_path.is_file():
            return

        p_str = str(self.playlist_path)
        if p_str.endswith(".json"):
            try:
                with open(self.playlist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for m in data:
                            if "duration_fmt" not in m:
                                m["duration_fmt"] = "00:00"
                        self.mixes = data
                        return
            except Exception:
                pass

        try:
            with open(self.playlist_path, "r", encoding="utf-8", errors="ignore") as f:
                cur_title = ""
                cur_dur = "00:00"
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#EXTINF:"):
                        payload = line[8:]
                        if "," in payload:
                            dur_part, cur_title = payload.split(",", 1)
                            try:
                                d_val = float(dur_part.strip())
                                cur_dur = format_seconds(d_val) if d_val > 0 else "00:00"
                            except ValueError:
                                cur_dur = "00:00"
                        else:
                            cur_title = payload
                            cur_dur = "00:00"
                    elif not line.startswith("#"):
                        ext = os.path.splitext(line)[1].lower()
                        bname = os.path.basename(line)
                        self.mixes.append({
                            "name": bname,
                            "title": cur_title or os.path.splitext(bname)[0],
                            "path": line,
                            "ext": ext[1:].upper() if ext else "AUDIO",
                            "size_mb": 0.0,
                            "duration_fmt": cur_dur,
                            "mtime": time.time(),
                            "folder": self.folder_name
                        })
                        cur_title = ""
                        cur_dur = "00:00"
        except Exception:
            pass

    def get_mixes(self, query: str = "") -> List[Dict[str, Any]]:
        q = query.lower()
        if not q:
            return self.mixes
        return [m for m in self.mixes if q in m["name"].lower() or q in m["path"].lower() or q in m.get("title", "").lower()]

    def get_latest_mix(self) -> Optional[Dict[str, Any]]:
        return self.mixes[0] if self.mixes else None

class AudioResampler:
    def __init__(self):
        _ensure_numpy()
        self.reset()

    def reset(self):
        self.buffer = np.zeros((0, 2), dtype=np.float32)
        self.in_pos = 0.0

    def _to_stereo(self, arr: np.ndarray) -> np.ndarray:
        if arr.ndim == 1 or arr.shape[1] == 1:
            c = arr if arr.ndim == 1 else arr[:, 0]
            return np.column_stack((c, c)).astype(np.float32)
        return arr[:, :2].astype(np.float32)

    def process(self, read_func, out_frames: int, speed_ratio: float) -> np.ndarray:
        if abs(speed_ratio - 1.0) < 1e-4 and self.in_pos == 0.0 and len(self.buffer) == 0:
            raw = read_func(out_frames)
            return np.zeros((0, 2), dtype=np.float32) if len(raw) == 0 else self._to_stereo(raw)

        t_out = self.in_pos + np.arange(out_frames, dtype=np.float64) * speed_ratio
        needed = int(np.ceil(t_out[-1])) + 4

        while len(self.buffer) < needed:
            more = read_func(max(1024, needed - len(self.buffer)))
            if len(more) == 0: break
            stereo_more = self._to_stereo(more)
            self.buffer = np.vstack((self.buffer, stereo_more)) if len(self.buffer) else stereo_more

        if len(self.buffer) == 0:
            return np.zeros((0, 2), dtype=np.float32)

        self.in_pos = t_out[-1] + speed_ratio
        if len(self.buffer) <= int(np.ceil(t_out[-1])):
            pad = int(np.ceil(t_out[-1])) + 4 - len(self.buffer)
            self.buffer = np.vstack((self.buffer, np.zeros((pad, 2), dtype=np.float32)))

        t_in = np.arange(len(self.buffer), dtype=np.float64)
        out = np.column_stack((np.interp(t_out, t_in, self.buffer[:, 0]), np.interp(t_out, t_in, self.buffer[:, 1]))).astype(np.float32)

        discard = int(np.floor(self.in_pos))
        if discard > 0:
            self.buffer = self.buffer[discard:]
            self.in_pos -= discard
        return out

class AudioSource:
    """Abstract interface for robust audio input sources with seek, read, and tell."""
    def read(self, frames: int) -> np.ndarray: raise NotImplementedError
    def seek(self, frame: int): raise NotImplementedError
    def tell(self) -> int: raise NotImplementedError
    def total_frames(self) -> int: raise NotImplementedError
    def close(self): raise NotImplementedError

class SoundFileAudioSource(AudioSource):
    """Robust SoundFile reader with retry, exponential backoff, and transparent reconnect on FUSE / cloud network dropouts."""
    def __init__(self, path: str, initial_sf: Optional[Any] = None):
        _ensure_audio_backends()
        self.path = str(path)
        self.sf = initial_sf
        self._current_frame = 0
        if self.sf is None:
            self._open_with_retry(max_retries=4)
        self.samplerate = int(self.sf.samplerate)
        self.channels = int(self.sf.channels)
        self.frames = int(getattr(self.sf, "frames", 0))

    def _open_with_retry(self, max_retries: int = 4, target_frame: int = 0):
        _ensure_audio_backends()
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                if self.sf:
                    try: self.sf.close()
                    except Exception: pass
                    self.sf = None
                self.sf = sf.SoundFile(self.path)
                if target_frame > 0:
                    try:
                        self.sf.seek(target_frame)
                    except Exception:
                        pass
                try:
                    self._current_frame = int(self.sf.tell())
                except Exception:
                    self._current_frame = target_frame
                return
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    time.sleep(0.25 * attempt)
        if last_exc:
            raise last_exc

    def read(self, frames: int) -> np.ndarray:
        for attempt in range(1, 4):
            try:
                if self.sf is None:
                    self._open_with_retry(max_retries=3, target_frame=self._current_frame)
                data = self.sf.read(frames, dtype='float32')
                self._current_frame += len(data)
                return data
            except Exception as e:
                try:
                    mp_log_error("MP_Audio_Player", f"SoundFile read glitch on remote mix, retrying: {self.path}", e)
                except Exception:
                    pass
                try:
                    self._open_with_retry(max_retries=3, target_frame=self._current_frame)
                except Exception:
                    pass
                if attempt == 3:
                    return np.zeros((0, self.channels), dtype=np.float32)
                time.sleep(0.15 * attempt)
        return np.zeros((0, self.channels), dtype=np.float32)

    def seek(self, frame: int):
        target = max(0, min(frame, max(0, self.frames - 1) if self.frames > 0 else frame))
        for attempt in range(1, 4):
            try:
                if self.sf is None:
                    self._open_with_retry(max_retries=2, target_frame=target)
                    return
                self.sf.seek(target)
                try:
                    self._current_frame = int(self.sf.tell())
                except Exception:
                    self._current_frame = target
                return
            except Exception:
                try:
                    self._open_with_retry(max_retries=2, target_frame=target)
                    return
                except Exception:
                    if attempt == 3:
                        self._current_frame = target

    def tell(self) -> int:
        try:
            if self.sf:
                pos = int(self.sf.tell())
                self._current_frame = pos
                return pos
        except Exception:
            pass
        return self._current_frame

    def total_frames(self) -> int:
        return self.frames

    def close(self):
        if self.sf:
            try: self.sf.close()
            except Exception: pass
            self.sf = None

class FFmpegAudioSource(AudioSource):
    """Universal audio decoder fallback using FFmpeg PCM pipe for AAC/M4A/WMA or damaged soundfile headers."""
    def __init__(self, path: str, target_samplerate: int = 44100):
        _ensure_audio_backends()
        self.path = str(path)
        self.samplerate = target_samplerate
        self.channels = 2
        self._current_frame = 0
        self.proc: Optional[subprocess.Popen] = None
        self.frames = self._probe_frames()
        self._start_ffmpeg(start_sec=0.0)

    def _probe_frames(self) -> int:
        _ensure_audio_backends()
        try:
            dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", self.path]
            dur_out = subprocess.check_output(dur_cmd, stderr=subprocess.DEVNULL, timeout=6).decode().strip()
            dur = float(dur_out) if dur_out else 0.0

            sr_cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate", "-of", "default=noprint_wrappers=1:nokey=1", self.path]
            sr_out = subprocess.check_output(sr_cmd, stderr=subprocess.DEVNULL, timeout=6).decode().strip()
            if sr_out and sr_out.isdigit():
                self.samplerate = int(sr_out)
            return int(dur * self.samplerate)
        except Exception:
            pass
        return 0

    def _start_ffmpeg(self, start_sec: float = 0.0):
        _ensure_audio_backends()
        self.close()
        cmd = ["ffmpeg", "-v", "error"]
        if start_sec > 0:
            cmd.extend(["-ss", f"{start_sec:.3f}"])
        cmd.extend(["-i", self.path, "-vn", "-f", "f32le", "-ac", "2", "-ar", str(self.samplerate), "pipe:1"])
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=131072)
            self._current_frame = int(start_sec * self.samplerate)
        except Exception as e:
            try:
                mp_log_error("MP_Audio_Player", f"Failed starting FFmpeg reader: {self.path}", e)
            except Exception:
                pass
            self.proc = None

    def read(self, frames: int) -> np.ndarray:
        _ensure_audio_backends()
        if not self.proc or not self.proc.stdout:
            return np.zeros((0, 2), dtype=np.float32)
        bytes_needed = frames * 2 * 4
        try:
            raw = self.proc.stdout.read(bytes_needed)
            if not raw:
                return np.zeros((0, 2), dtype=np.float32)
            arr = np.frombuffer(raw, dtype=np.float32)
            n_frames = len(arr) // 2
            arr = arr[:n_frames * 2].reshape((n_frames, 2))
            self._current_frame += n_frames
            return arr
        except Exception:
            return np.zeros((0, 2), dtype=np.float32)

    def seek(self, frame: int):
        sec = float(frame) / float(self.samplerate) if self.samplerate > 0 else 0.0
        self._start_ffmpeg(start_sec=sec)

    def tell(self) -> int:
        return self._current_frame

    def total_frames(self) -> int:
        return self.frames

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=0.3)
            except Exception:
                try: self.proc.kill()
                except Exception: pass
            self.proc = None

def open_audio_source(path: str) -> AudioSource:
    """Opens audio source with retry, exponential backoff, and FFmpeg fallback."""
    last_exc = None
    ext = os.path.splitext(str(path))[1].lower()
    if ext in ('.m4a', '.aac', '.wma', '.alac'):
        try: return FFmpegAudioSource(path)
        except Exception as e: last_exc = e

    try: return SoundFileAudioSource(path)
    except Exception as e: last_exc = e

    try: return FFmpegAudioSource(path)
    except Exception as e: last_exc = e

    raise last_exc or RuntimeError(f"Unable to open audio source: {path}")

class AudioPrefetchBuffer:
    """Thread-safe ring buffer providing glitch-free zero-latency reads for PortAudio callbacks."""
    def __init__(self, sample_rate: int, buffer_sec: float = 12.0):
        self.sample_rate = sample_rate
        self.max_frames = int(buffer_sec * sample_rate)
        self.chunks = collections.deque()
        self.chunk_offset = 0
        self.available_frames = 0
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)
        self.eof = False

    def clear(self):
        with self.lock:
            self.chunks.clear()
            self.chunk_offset = 0
            self.available_frames = 0
            self.eof = False
            self.not_full.notify_all()

    def set_eof(self):
        with self.lock:
            self.eof = True
            self.not_empty.notify_all()

    def is_empty(self) -> bool:
        with self.lock:
            return self.available_frames == 0

    def health_sec(self) -> float:
        with self.lock:
            return float(self.available_frames) / float(self.sample_rate) if self.sample_rate > 0 else 0.0

    def write(self, data: np.ndarray, timeout: float = 0.5) -> bool:
        if len(data) == 0: return True
        data_stereo = self._to_stereo(data)
        n = len(data_stereo)
        with self.lock:
            while self.available_frames + n > self.max_frames:
                if not self.not_full.wait(timeout=timeout):
                    return False
            self.chunks.append(data_stereo)
            self.available_frames += n
            self.not_empty.notify_all()
            return True

    def read(self, frames: int) -> np.ndarray:
        with self.lock:
            if self.available_frames == 0:
                return np.zeros((0, 2), dtype=np.float32)
            n = min(frames, self.available_frames)
            parts = []
            collected = 0
            while collected < n and self.chunks:
                front = self.chunks[0]
                avail = len(front) - self.chunk_offset
                needed = n - collected
                if avail <= needed:
                    parts.append(front[self.chunk_offset:])
                    collected += avail
                    self.chunks.popleft()
                    self.chunk_offset = 0
                else:
                    parts.append(front[self.chunk_offset:self.chunk_offset + needed])
                    self.chunk_offset += needed
                    collected += needed
                    break
            self.available_frames -= collected
            self.not_full.notify_all()
            if len(parts) == 1: return parts[0]
            elif parts: return np.vstack(parts)
            return np.zeros((0, 2), dtype=np.float32)

    def _to_stereo(self, arr: np.ndarray) -> np.ndarray:
        if arr.ndim == 1: return np.column_stack((arr, arr)).astype(np.float32)
        elif arr.shape[1] == 1: return np.column_stack((arr[:, 0], arr[:, 0])).astype(np.float32)
        elif arr.shape[1] > 2: return arr[:, :2].astype(np.float32)
        return arr.astype(np.float32)

class AudioFeederThread(threading.Thread):
    """Background worker fetching ahead into prefetch buffer with retry and cloud stall tolerance."""
    def __init__(self, source: AudioSource, audio_buffer: AudioPrefetchBuffer, engine: Any, chunk_frames: int = 16384):
        super().__init__(name="AudioFeederThread", daemon=True)
        self.source = source
        self.audio_buffer = audio_buffer
        self.engine = engine
        self.chunk_frames = chunk_frames
        self._running = True
        self._seek_target: Optional[int] = None
        self._seek_lock = threading.Lock()
        self._wake_cond = threading.Condition(threading.Lock())
        self.current_frame = 0

    def request_seek(self, frame: int):
        with self._seek_lock:
            self._seek_target = frame
        with self._wake_cond:
            self._wake_cond.notify_all()
        with self.audio_buffer.lock:
            self.audio_buffer.not_full.notify_all()

    def stop(self):
        self._running = False
        with self._wake_cond:
            self._wake_cond.notify_all()
        with self.audio_buffer.lock:
            self.audio_buffer.not_full.notify_all()
            self.audio_buffer.not_empty.notify_all()

    def run(self):
        read_chunk_size = self.chunk_frames
        total_frames = self.source.total_frames()

        while self._running:
            seek_target = None
            with self._seek_lock:
                if self._seek_target is not None:
                    seek_target = self._seek_target
                    self._seek_target = None

            if seek_target is not None:
                try:
                    self.source.seek(seek_target)
                    self.current_frame = seek_target
                    self.audio_buffer.clear()
                except Exception as e:
                    try: mp_log_error("MP_Audio_Player", f"Feeder seek error: {e}", e)
                    except Exception: pass

            if self.audio_buffer.available_frames >= self.audio_buffer.max_frames:
                with self._wake_cond:
                    self._wake_cond.wait(timeout=0.08)
                continue

            try:
                chunk = self.source.read(read_chunk_size)
            except Exception as e:
                try: mp_log_error("MP_Audio_Player", f"Feeder read error: {e}", e)
                except Exception: pass
                time.sleep(0.2)
                continue

            if len(chunk) > 0:
                self.current_frame = self.source.tell()
                written = False
                while self._running and not written and self._seek_target is None:
                    written = self.audio_buffer.write(chunk, timeout=0.1)
            else:
                cur_pos = self.source.tell()
                total_frames = self.source.total_frames()
                if total_frames > 0 and cur_pos < (total_frames - (read_chunk_size * 2)):
                    # Transient disk/network read hitch - never set EOF prematurely on remote/large mix
                    time.sleep(0.15)
                    continue

                got_data = False
                for _ in range(4):
                    time.sleep(0.1)
                    try:
                        verify_chunk = self.source.read(read_chunk_size)
                        if len(verify_chunk) > 0:
                            self.audio_buffer.write(verify_chunk)
                            self.current_frame = self.source.tell()
                            got_data = True
                            break
                    except Exception:
                        pass
                if got_data:
                    continue

                # Truly at end of stream
                if total_frames <= 0 or cur_pos >= (total_frames - (read_chunk_size * 2)):
                    self.audio_buffer.set_eof()
                    while self._running and self._seek_target is None:
                        with self._wake_cond:
                            self._wake_cond.wait(timeout=0.2)

class AudioEngine:
    def __init__(self, playlist: List[Dict[str, Any]], auto_bluetooth: bool = True, mode: str = "MIX_ARCHIVE"):
        _ensure_audio_backends()
        self.mode = str(mode or "MIX_ARCHIVE").upper()
        self.playlist = playlist
        self.play_queue: List[Dict[str, Any]] = []
        self._queue_lock = threading.Lock()
        self.current_index = 0
        self.current_track = playlist[0] if playlist else None
        self.state, self.volume, self.muted, self.shuffle, self.repeat_mode = "stopped", 0.85, False, False, "all"
        self.position_sec, self.duration_sec, self.sample_rate, self.channels = 0.0, 0.0, 44100, 2
        self.pitch_percent, self.pitch_factor = 0, 1.0
        self.resampler = AudioResampler()
        self.sf_file, self.stream = None, None
        self.audio_source: Optional[AudioSource] = None
        self.audio_buffer: Optional[AudioPrefetchBuffer] = None
        self.feeder: Optional[AudioFeederThread] = None
        self.output_rate, self.output_device_name, self.stream_error = 44100, "", None
        self._sf_lock, self._sf_refs, self._sf_retired = threading.Lock(), 0, []
        self._next_stream_retry = 0.0

        self.num_bands = 24
        self.band_edges = np.logspace(np.log10(28), np.log10(18500), self.num_bands + 1)
        self.levels = np.zeros(self.num_bands, dtype=np.float32)
        self.levels_left = np.zeros(self.num_bands, dtype=np.float32)
        self.levels_right = np.zeros(self.num_bands, dtype=np.float32)
        self.smoothed_levels = np.zeros(self.num_bands, dtype=np.float32)
        self.smoothed_levels_left = np.zeros(self.num_bands, dtype=np.float32)
        self.smoothed_levels_right = np.zeros(self.num_bands, dtype=np.float32)
        self.peaks = np.zeros(self.num_bands, dtype=np.float32)
        self.peaks_left = np.zeros(self.num_bands, dtype=np.float32)
        self.peaks_right = np.zeros(self.num_bands, dtype=np.float32)
        self.peak_decay_timers = np.zeros(self.num_bands, dtype=np.float32)
        self.peak_decay_timers_left = np.zeros(self.num_bands, dtype=np.float32)
        self.peak_decay_timers_right = np.zeros(self.num_bands, dtype=np.float32)
        self.recent_mono_buffer = np.zeros(512, dtype=np.float32)
        self.rms_level, self.peak_db = 0.0, -60.0
        self.track_ended, self.pending_seek_sec = False, None
        self.hanning_window = np.hanning(1024).astype(np.float32)
        self.fft_scale = 1024.0 / 2.0
        self._cached_bt_info: Dict[str, Any] = {}
        self._last_bt_query: float = 0.0

        # Recording state (MP_AUDIOWAV_REC_OUTPUT, max 3GB per WAV file)
        self.is_recording = False
        self.recording_current_path = ""
        self.recording_bytes_written = 0
        self.recording_duration_sec = 0.0
        self._rec_queue: Optional[queue.Queue] = None
        self._rec_worker_thread: Optional[threading.Thread] = None
        self._rec_lock = threading.Lock()
        self._rec_part_index = 1
        self._rec_base_stem = ""
        self._rec_dir: Optional[Path] = None
        self._rec_samplerate = 48000

        self._ensure_stream()

        self.auto_bluetooth = auto_bluetooth
        self.bt_router: Optional[Any] = None
        if BluetoothAudioRouter is not None:
            try:
                self.bt_router = BluetoothAudioRouter(
                    target_pid=os.getpid(),
                    on_route_change=self._on_bt_route_change,
                    auto_switch=self.auto_bluetooth
                )
                self.bt_router.start()
            except Exception:
                pass
    def _on_bt_route_change(self, device_name: str, is_bluetooth: bool, action: str, codec: Optional[str] = None):
        self._ensure_stream()
        if getattr(self, "bt_router", None):
            try:
                self._cached_bt_info = self.bt_router.get_status(force_probe=True)
                self._last_bt_query = time.time()
                if is_bluetooth and self._cached_bt_info.get("bluetooth_codec"):
                    codec = self._cached_bt_info["bluetooth_codec"]
            except Exception:
                pass
        if is_bluetooth:
            badge = f" [Bluetooth {codec}]" if codec else " [Bluetooth]"
            self.output_device_name = f"{device_name}{badge}"
        else:
            self.output_device_name = device_name
        self._sync_state_file()

    def set_pitch(self, pitch_pct: int):
        self.pitch_percent = max(-20, min(20, int(pitch_pct)))
        self.pitch_factor = 1.0 + (self.pitch_percent / 100.0)

    def change_pitch(self, delta_pct: int = 1): self.set_pitch(self.pitch_percent + delta_pct)
    def reset_pitch(self): self.set_pitch(0)

    def _stream_alive(self) -> bool:
        try: return bool(self.stream and self.stream.active)
        except Exception: return False

    def _close_stream(self):
        s, self.stream = self.stream, None
        if s:
            for fn in (s.abort, s.stop, s.close):
                try: fn()
                except Exception: pass

    def _stream_attempts(self) -> List[Tuple[Optional[int], int, Any]]:
        attempts, seen = [], set()
        def add(d, r, e):
            k = (d if d is None else int(d), int(r), e is not None)
            if r > 0 and k not in seen:
                seen.add(k)
                attempts.append((d, int(r), e))

        if sd is None: return attempts
        if sys.platform == "win32":
            try:
                for host in sd.query_hostapis():
                    if "WASAPI" in str(host.get("name", "")).upper():
                        dev = host.get("default_output_device", -1)
                        if dev is not None and int(dev) >= 0:
                            extra = sd.WasapiSettings(exclusive=False, auto_convert=True)
                            nat = int(sd.query_devices(int(dev)).get("default_samplerate") or 48000)
                            for rate in (nat, 48000, 44100): add(int(dev), rate, extra)
            except Exception: pass
            try: add(None, int(sd.query_devices(kind="output").get("default_samplerate") or 48000), None)
            except Exception: pass
            for rate in (48000, 44100): add(None, rate, None)
        else:
            try:
                info = sd.query_devices(kind="output")
                nat = int(info.get("default_samplerate") or 48000)
                add(None, nat, None)
            except Exception: pass
            add(None, 48000, None)
            add(None, 44100, None)
        return attempts

    def _open_output_stream(self) -> bool:
        if sd is None:
            self.stream_error = "sounddevice is not installed"
            return False
        errors = []
        for dev, rate, extra in self._stream_attempts():
            s = None
            try:
                kw = dict(
                    samplerate=rate,
                    channels=2,
                    dtype="float32",
                    callback=self._audio_callback,
                    blocksize=1024,
                    latency="high"
                )
                if extra: kw["extra_settings"] = extra
                if dev is not None: kw["device"] = dev
                s = sd.OutputStream(**kw)
                s.start()
                new_rate = int(round(float(s.samplerate)))
                if new_rate != self.output_rate: self.resampler.reset()
                self.output_rate, self.stream, self.stream_error = new_rate or rate, s, None
                try:
                    didx = s.device[-1] if isinstance(s.device, (list, tuple)) else s.device
                    self.output_device_name = str(sd.query_devices(didx)["name"])
                except Exception: self.output_device_name = "default"
                if getattr(self, "bt_router", None):
                    try:
                        threading.Thread(target=self.bt_router.check_and_route, daemon=True).start()
                    except Exception: pass
                return True
            except Exception as exc:
                errors.append(f"{dev}@{rate}: {exc}")
                if s:
                    try: s.close()
                    except Exception: pass
        self.stream = None
        self.stream_error = "; ".join(errors)[-400:] if errors else "no output device"
        return False

    def _ensure_stream(self) -> bool:
        if self._stream_alive(): return True
        if time.time() < self._next_stream_retry: return False
        self._close_stream()
        ok = self._open_output_stream()
        if not ok: self._next_stream_retry = time.time() + 1.5
        return ok

    def _acquire_sf(self):
        with self._sf_lock:
            if self.sf_file: self._sf_refs += 1
            return self.sf_file

    def _release_sf(self):
        closing = []
        with self._sf_lock:
            if self._sf_refs > 0: self._sf_refs -= 1
            if self._sf_refs == 0 and self._sf_retired:
                closing, self._sf_retired = self._sf_retired, []
        for old in closing:
            try: old.close()
            except Exception: pass

    def _retire_sf(self, old_sf):
        if not old_sf: return
        closing = []
        with self._sf_lock:
            if self._sf_refs == 0: closing = [old_sf]
            else: self._sf_retired.append(old_sf)
        for old in closing:
            try: old.close()
            except Exception: pass

    def _stop_feeder(self):
        f = getattr(self, "feeder", None)
        if f:
            self.feeder = None
            try: f.stop()
            except Exception: pass
        b = getattr(self, "audio_buffer", None)
        if b:
            try: b.clear()
            except Exception: pass
        s = getattr(self, "audio_source", None)
        if s:
            self.audio_source = None
            try: s.close()
            except Exception: pass

    def load_track(self, index: int, start_playing: bool = True) -> bool:
        if not self.playlist or not (0 <= index < len(self.playlist)): return False
        self.current_index = index
        self.current_track = self.playlist[index]
        self._stop_feeder()
        try:
            track_path = self.current_track["path"]
            source = open_audio_source(track_path)
            self.audio_source = source
            self.sample_rate = source.samplerate
            self.channels = source.channels
            tot_fr = source.total_frames()
            self.duration_sec = float(tot_fr) / float(self.sample_rate) if self.sample_rate > 0 else 0.0
            self.current_track["duration_sec"] = self.duration_sec
            self.current_track["duration_fmt"] = format_seconds(self.duration_sec)
            self.position_sec = 0.0
            self.resampler.reset()

            freqs = np.fft.rfftfreq(1024, 1.0 / self.sample_rate)
            self.band_indices = []
            for i in range(self.num_bands):
                idx = np.where((freqs >= self.band_edges[i]) & (freqs < self.band_edges[i + 1]))[0]
                if len(idx) == 0:
                    idx = np.array([min(len(freqs) - 1, max(0, int(self.band_edges[i] / (self.sample_rate / 2) * len(freqs))))])
                self.band_indices.append(idx)

            new_sf = getattr(source, "sf", source)
            with self._sf_lock:
                old_sf, self.sf_file = self.sf_file, new_sf
            self._retire_sf(old_sf)

            # Prefetch ring buffer: 12 seconds in RAM to absorb cloud network stalls
            self.audio_buffer = AudioPrefetchBuffer(self.sample_rate, buffer_sec=12.0)
            self.feeder = AudioFeederThread(self.audio_source, self.audio_buffer, self)
            self.feeder.start()

            # Pre-buffer initial frames so playback begins immediately and smoothly
            min_prebuffer = int(0.5 * self.sample_rate)
            t_start = time.time()
            while (time.time() - t_start < 1.0) and (self.audio_buffer.available_frames < min_prebuffer) and not self.audio_buffer.eof:
                time.sleep(0.04)

            self._ensure_stream()
            self.state = "playing" if start_playing else "paused"
            self._sync_state_file()
            if start_playing:
                try:
                    record_activity(
                        "Play Mix / Audio File",
                        category="playback",
                        details={
                            "track_name": self.current_track.get("name"),
                            "track_path": self.current_track.get("path"),
                            "duration_sec": round(self.duration_sec, 2),
                            "sample_rate": self.sample_rate
                        },
                        status="success"
                    )
                except Exception:
                    pass
            return True
        except Exception as exc:
            self.state = "stopped"
            try:
                mp_log_error("MP_Audio_Player", f"Failed loading track: {self.current_track.get('path', '')}", exc)
            except Exception:
                pass
            return False

    def _sync_state_file(self):
        try:
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.get_status_dict(), default=float), encoding="utf-8")
            tmp.replace(STATE_FILE)
        except Exception: pass

    def _audio_callback(self, outdata, frames, time_info, status):
        try: self._render_audio(outdata, frames)
        except Exception as exc:
            self.stream_error = str(exc)
            outdata.fill(0)

    def _render_audio(self, outdata, frames):
        try:
            buf = getattr(self, "audio_buffer", None)
            if buf is None or self.state != "playing":
                outdata.fill(0)
                return

            out_rate = float(self.output_rate or 48000)
            speed_ratio = (float(self.sample_rate) / out_rate) * self.pitch_factor
            data = self.resampler.process(lambda n: buf.read(n), frames, speed_ratio)
            read_frames = len(data)

            feeder = getattr(self, "feeder", None)
            if feeder and self.sample_rate > 0:
                buffered = buf.available_frames
                read_pos = feeder.current_frame
                played = max(0, read_pos - buffered)
                self.position_sec = min(self.duration_sec, float(played) / float(self.sample_rate))
            else:
                self.position_sec += float(max(read_frames, 0) * self.pitch_factor) / out_rate

            if read_frames <= 0:
                outdata.fill(0)
                if buf.eof and buf.is_empty():
                    self.track_ended = True
                return

            eff_vol = 0.0 if self.muted else self.volume
            stereo_data = data if data.ndim > 1 and data.shape[1] >= 2 else (np.column_stack((data, data)) if data.ndim == 1 else np.column_stack((data[:, 0], data[:, 0])))
            stereo_data = stereo_data[:, :2]
            mono_data = np.mean(stereo_data, axis=1)

            if eff_vol != 1.0:
                stereo_data = np.ascontiguousarray(stereo_data * np.float32(eff_vol))

            ncopy = min(read_frames, frames, len(stereo_data))
            if buf.eof and buf.is_empty() and np.all(stereo_data[:ncopy] == 0):
                outdata.fill(0)
                self.track_ended = True
                return

            outdata[:ncopy] = stereo_data[:ncopy]
            if ncopy < frames:
                outdata[ncopy:].fill(0)
                if buf.eof and buf.is_empty():
                    self.track_ended = True

            if self.is_recording and self._rec_queue is not None and ncopy > 0:
                try:
                    self._rec_queue.put_nowait(np.copy(stereo_data[:ncopy]))
                except Exception:
                    pass

            self._compute_fft_spectrum(stereo_data[:ncopy], mono_data[:ncopy])
        except Exception as exc:
            self.stream_error = str(exc)
            outdata.fill(0)

    def _compute_fft_spectrum(self, stereo_data: np.ndarray, mono_data: np.ndarray):
        try:
            fft_size = 1024
            m = np.pad(mono_data, (0, max(0, fft_size - len(mono_data))))[:fft_size]
            l = np.pad(stereo_data[:, 0], (0, max(0, fft_size - len(stereo_data))))[:fft_size]
            r = np.pad(stereo_data[:, 1], (0, max(0, fft_size - len(stereo_data))))[:fft_size]
            w = self.hanning_window
            scale = self.fft_scale
            m_fft, l_fft, r_fft = np.abs(np.fft.rfft(m * w)) / scale, np.abs(np.fft.rfft(l * w)) / scale, np.abs(np.fft.rfft(r * w)) / scale

            for b in range(self.num_bands):
                idx = self.band_indices[b]
                boost = (1.0 + (1.2 / (1.0 + b * 0.28))) * 4.6
                self.levels[b] = min(1.0, max(0.0, float(np.mean(m_fft[idx]) * boost)))
                self.levels_left[b] = min(1.0, max(0.0, float(np.mean(l_fft[idx]) * boost)))
                self.levels_right[b] = min(1.0, max(0.0, float(np.mean(r_fft[idx]) * boost)))

                # Mono responsive ballistics
                if self.levels[b] > self.smoothed_levels[b]:
                    self.smoothed_levels[b] = self.smoothed_levels[b] * 0.15 + self.levels[b] * 0.85
                else:
                    self.smoothed_levels[b] = self.smoothed_levels[b] * 0.80 + self.levels[b] * 0.20

                if self.smoothed_levels[b] >= self.peaks[b]:
                    self.peaks[b], self.peak_decay_timers[b] = self.smoothed_levels[b], 0.0
                else:
                    self.peak_decay_timers[b] += 0.025
                    if self.peak_decay_timers[b] > 0.15:
                        self.peaks[b] = max(0.0, self.peaks[b] - (0.035 + (self.peak_decay_timers[b] - 0.15) * 0.08))

                # Left channel responsive ballistics
                if self.levels_left[b] > self.smoothed_levels_left[b]:
                    self.smoothed_levels_left[b] = self.smoothed_levels_left[b] * 0.15 + self.levels_left[b] * 0.85
                else:
                    self.smoothed_levels_left[b] = self.smoothed_levels_left[b] * 0.80 + self.levels_left[b] * 0.20

                if self.smoothed_levels_left[b] >= self.peaks_left[b]:
                    self.peaks_left[b], self.peak_decay_timers_left[b] = self.smoothed_levels_left[b], 0.0
                else:
                    self.peak_decay_timers_left[b] += 0.025
                    if self.peak_decay_timers_left[b] > 0.15:
                        self.peaks_left[b] = max(0.0, self.peaks_left[b] - (0.035 + (self.peak_decay_timers_left[b] - 0.15) * 0.08))

                # Right channel responsive ballistics
                if self.levels_right[b] > self.smoothed_levels_right[b]:
                    self.smoothed_levels_right[b] = self.smoothed_levels_right[b] * 0.15 + self.levels_right[b] * 0.85
                else:
                    self.smoothed_levels_right[b] = self.smoothed_levels_right[b] * 0.80 + self.levels_right[b] * 0.20

                if self.smoothed_levels_right[b] >= self.peaks_right[b]:
                    self.peaks_right[b], self.peak_decay_timers_right[b] = self.smoothed_levels_right[b], 0.0
                else:
                    self.peak_decay_timers_right[b] += 0.025
                    if self.peak_decay_timers_right[b] > 0.15:
                        self.peaks_right[b] = max(0.0, self.peaks_right[b] - (0.035 + (self.peak_decay_timers_right[b] - 0.15) * 0.08))

            self.recent_mono_buffer = m[:512]
            self.rms_level = float(np.sqrt(np.mean(m ** 2)))
            self.peak_db = 20.0 * np.log10(max(1e-5, np.max(np.abs(m))))
        except Exception: pass

    def check_track_end(self):
        if self.track_ended:
            self.track_ended = False
            if self.repeat_mode == "one": self.seek(0)
            elif self.repeat_mode == "all" or bool(self.play_queue) or self.current_index < len(self.playlist) - 1: self.next_track()
            else: self.stop_playback()

    def play(self):
        if getattr(self, "audio_source", None) is None or getattr(self, "feeder", None) is None or self.state == "stopped":
            self.load_track(self.current_index, True)
        else:
            self.state = "playing"
            self._ensure_stream()
            if getattr(self, "bt_router", None) and hasattr(self.bt_router, "running") and not self.bt_router.running:
                try: self.bt_router.start()
                except Exception: pass
            self._sync_state_file()

    def pause(self):
        self.state = "paused"
        self._sync_state_file()

    def toggle_play_pause(self): self.pause() if self.state == "playing" else self.play()

    def stop_playback(self):
        self.state, self.position_sec = "stopped", 0.0
        self._stop_feeder()
        with self._sf_lock:
            old_sf, self.sf_file = self.sf_file, None
        self._retire_sf(old_sf)
        self.smoothed_levels.fill(0)
        self.smoothed_levels_left.fill(0)
        self.smoothed_levels_right.fill(0)
        self.peaks.fill(0)
        self.peaks_left.fill(0)
        self.peaks_right.fill(0)
        self._sync_state_file()

    def queue_track(self, track_or_path: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        with self._queue_lock:
            track_dict: Optional[Dict[str, Any]] = None
            if isinstance(track_or_path, dict):
                track_dict = dict(track_or_path)
            elif isinstance(track_or_path, str) and track_or_path:
                tp = str(track_or_path)
                for t in self.playlist:
                    if t.get("path") == tp or t.get("name") == os.path.basename(tp):
                        track_dict = dict(t)
                        break
                if track_dict is None:
                    ext = os.path.splitext(tp)[1].lstrip(".").upper()
                    sz = os.path.getsize(tp) / (1024 * 1024) if os.path.isfile(tp) else 0.0
                    track_dict = {"name": os.path.basename(tp), "path": tp, "size_mb": sz, "mtime": time.time(), "ext": ext}
            if track_dict:
                self.play_queue.append(track_dict)
                self._sync_state_file()
                return {"queued": True, "track": track_dict, "queue_len": len(self.play_queue)}
            return {"queued": False, "queue_len": len(self.play_queue)}

    def dequeue_next(self) -> Optional[Dict[str, Any]]:
        with self._queue_lock:
            if self.play_queue:
                t = self.play_queue.pop(0)
                self._sync_state_file()
                return t
        return None

    def clear_queue(self) -> int:
        with self._queue_lock:
            n = len(self.play_queue)
            self.play_queue.clear()
            self._sync_state_file()
            return n

    def get_queue(self) -> List[Dict[str, Any]]:
        with self._queue_lock:
            return list(self.play_queue)

    def _step_track(self, direction: int):
        if direction > 0:
            queued_item = self.dequeue_next()
            if queued_item:
                qpath = queued_item.get("path")
                for i, t in enumerate(self.playlist):
                    if t.get("path") == qpath:
                        if self.load_track(i, True):
                            return
                        break
                else:
                    self.playlist.insert(0, queued_item)
                    if self.load_track(0, True):
                        return
        if not self.playlist: return
        n = len(self.playlist)
        for s in range(1, min(10, n) + 1):
            if self.shuffle and n > 1:
                idx = random.choice([i for i in range(n) if i != self.current_index])
            else:
                idx = (self.current_index + s * direction) % n
            if self.load_track(idx, True): return

    def next_track(self): self._step_track(1)
    def prev_track(self):
        if self.position_sec > 5.0: self.seek(0)
        else: self._step_track(-1)

    def seek(self, target_sec: float):
        if self.duration_sec > 0:
            target = max(0.0, min(self.duration_sec - 1.0, float(target_sec)))
            self.position_sec = target
            feeder = getattr(self, "feeder", None)
            if feeder and self.sample_rate > 0:
                feeder.request_seek(int(target * self.sample_rate))
            self.resampler.reset()

    def seek_relative(self, delta_sec: float): self.seek(self.position_sec + delta_sec)
    def set_volume(self, vol_pct: int):
        self.volume, self.muted = max(0.0, min(1.0, float(vol_pct) / 100.0)), False
        self._sync_state_file()
    def change_volume(self, delta_pct: int): self.set_volume(int(self.volume * 100) + delta_pct)
    def toggle_mute(self):
        self.muted = not self.muted
        self._sync_state_file()
    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self._sync_state_file()
    def cycle_repeat(self):
        modes = ["all", "one", "off"]
        self.repeat_mode = modes[(modes.index(self.repeat_mode) + 1) % len(modes)]
        self._sync_state_file()

    def start_recording(self) -> str:
        with self._rec_lock:
            if self.is_recording:
                return self.recording_current_path

            rec_dir = get_recording_output_dir()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            curr_title = ""
            if self.current_track and isinstance(self.current_track, dict):
                curr_title = str(self.current_track.get("name") or self.current_track.get("title", ""))
            if curr_title:
                clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', os.path.splitext(curr_title)[0])[:32].strip("_")
                name_suffix = f"_{clean}" if clean else ""
            else:
                name_suffix = ""

            self._rec_base_stem = f"MP_REC_{timestamp}{name_suffix}"
            self._rec_dir = rec_dir
            self._rec_part_index = 1
            part_filename = f"{self._rec_base_stem}_pt{self._rec_part_index:02d}.wav"
            self.recording_current_path = str(self._rec_dir / part_filename)
            self.recording_bytes_written = 0
            self.recording_duration_sec = 0.0
            self._rec_samplerate = int(self.output_rate or self.sample_rate or 48000)

            self.is_recording = True
            self._rec_queue = queue.Queue(maxsize=1200)
            self._rec_worker_thread = threading.Thread(target=self._recording_worker, daemon=True)
            self._rec_worker_thread.start()
            self._sync_state_file()
            return self.recording_current_path

    def stop_recording(self) -> Tuple[bool, str]:
        with self._rec_lock:
            if not self.is_recording:
                return False, ""
            self.is_recording = False
            last_path = self.recording_current_path
            if self._rec_queue is not None:
                try:
                    self._rec_queue.put_nowait(None)
                except Exception:
                    pass
            self.recording_current_path = ""
            self._sync_state_file()
            return True, last_path

    def toggle_recording(self) -> Tuple[bool, str]:
        if self.is_recording:
            _, path = self.stop_recording()
            return False, path
        else:
            path = self.start_recording()
            return True, path

    def _recording_worker(self):
        samplerate = getattr(self, "_rec_samplerate", 48000)
        # 3GB maximum size per WAV recording part: REC_MAX_FILE_BYTES bytes
        max_wav_bytes = getattr(self, "_rec_max_bytes", None) or REC_MAX_FILE_BYTES
        current_file = None
        current_file_bytes = 0

        def _open_wav(fpath: str):
            _ensure_audio_backends()
            if sf is not None:
                return sf.SoundFile(str(fpath), mode="w", samplerate=samplerate, channels=2, subtype="PCM_16", format="WAV")
            import wave
            wf = wave.open(str(fpath), "wb")
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            return wf

        try:
            current_file = _open_wav(self.recording_current_path)
        except Exception:
            self.is_recording = False
            return

        while True:
            try:
                chunk = self._rec_queue.get(timeout=0.2)
            except Exception:
                if not self.is_recording and (self._rec_queue is None or self._rec_queue.empty()):
                    break
                continue

            if chunk is None:
                break

            chunk_len = len(chunk)
            if chunk_len <= 0:
                continue

            # 2 channels * 16-bit (2 bytes) = 4 bytes per frame
            chunk_bytes = chunk_len * 4

            # Automatically split when current file hits or would exceed 3GB
            if current_file_bytes + chunk_bytes >= max_wav_bytes:
                try:
                    current_file.close()
                except Exception:
                    pass
                with self._rec_lock:
                    self._rec_part_index += 1
                    next_filename = f"{self._rec_base_stem}_pt{self._rec_part_index:02d}.wav"
                    self.recording_current_path = str(self._rec_dir / next_filename)
                try:
                    current_file = _open_wav(self.recording_current_path)
                    current_file_bytes = 0
                except Exception:
                    break

            try:
                if sf is not None and isinstance(current_file, sf.SoundFile):
                    current_file.write(chunk)
                else:
                    i16 = np.clip(chunk * 32767.0, -32768, 32767).astype(np.int16)
                    current_file.writeframes(i16.tobytes())
                current_file_bytes += chunk_bytes
                self.recording_bytes_written += chunk_bytes
                self.recording_duration_sec += chunk_len / float(samplerate)
            except Exception:
                pass

        if current_file:
            try:
                current_file.close()
            except Exception:
                pass
        self._sync_state_file()

    def get_mini_visualizer(self) -> str:
        if self.state != "playing": return "·······"
        step = max(1, self.num_bands // 8)
        return "".join(prism_level_glyph(int(self.smoothed_levels[i] * 8)) for i in range(0, self.num_bands, step)[:8])

    def get_status_dict(self) -> Dict[str, Any]:
        pct = round((self.position_sec / self.duration_sec * 100.0), 1) if self.duration_sec > 0 else 0.0
        now = time.time()
        if getattr(self, "bt_router", None):
            if not self._cached_bt_info or (now - self._last_bt_query > 1.0):
                try:
                    self._cached_bt_info = self.bt_router.get_status()
                    self._last_bt_query = now
                except Exception:
                    pass
            bt_info = self._cached_bt_info
        else:
            bt_info = {}
        is_bt = bool(bt_info.get("bluetooth_connected", False))
        bt_dev = str(bt_info.get("bluetooth_device", ""))
        bt_codec = str(bt_info.get("bluetooth_codec", ""))
        cur_out = str(self.output_device_name or "")
        if is_bt and bt_dev:
            cur_out = f"{bt_dev} [Bluetooth {bt_codec}]" if bt_codec else f"{bt_dev} [Bluetooth]"
        return {
            "running": True, "state": str(self.state), "mode": str(self.mode), "index": int(self.current_index),
            "total_tracks": len(self.playlist), "title": str(self.current_track["name"] if self.current_track else "No Track Loaded"),
            "path": str(self.current_track["path"] if self.current_track else ""), "position_sec": round(float(self.position_sec), 2),
            "duration_sec": round(float(self.duration_sec), 2), "position_fmt": format_seconds(self.position_sec),
            "duration_fmt": format_seconds(self.duration_sec), "progress_pct": float(pct), "volume": int(self.volume * 100),
            "pitch_percent": int(self.pitch_percent), "pitch_factor": round(float(self.pitch_factor), 3), "muted": bool(self.muted),
            "shuffle": bool(self.shuffle), "repeat": str(self.repeat_mode), "sample_rate": int(self.sample_rate),
            "recording": bool(self.is_recording), "recording_file": str(self.recording_current_path),
            "recording_bytes": int(self.recording_bytes_written),
            "recording_duration": round(float(self.recording_duration_sec), 2),
            "queue_len": len(self.play_queue),
            "queue": [t.get("path") for t in self.play_queue if isinstance(t, dict)],
            "output_rate": int(self.output_rate or 0), "output_device": cur_out,
            "bluetooth_connected": is_bt, "bluetooth_device": bt_dev, "bluetooth_codec": bt_codec,
            "bluetooth_auto_route": bool(getattr(self, "auto_bluetooth", True)),
            "audio_error": str(self.stream_error or ""), "channels": int(self.channels), "mini_eq": self.get_mini_visualizer(),
            "levels": [round(float(x), 3) for x in self.smoothed_levels], "peaks": [round(float(x), 3) for x in self.peaks],
            "levels_left": [round(float(x), 3) for x in self.smoothed_levels_left], "levels_right": [round(float(x), 3) for x in self.smoothed_levels_right],
            "peaks_left": [round(float(x), 3) for x in self.peaks_left], "peaks_right": [round(float(x), 3) for x in self.peaks_right],
            "waveform": [round(float(x), 3) for x in self.recent_mono_buffer[::7][:80]] if hasattr(self, "recent_mono_buffer") else [],
            "rms_level": round(float(self.rms_level), 4), "peak_db": round(float(self.peak_db), 1), "pid": os.getpid()
        }

class PlayerIPCServer:
    def __init__(self, engine: AudioEngine):
        self.engine, self.running, self.sock = engine, True, None

    def start(self):
        if hasattr(socket, "AF_UNIX"):
            if SOCKET_PATH.exists():
                try: SOCKET_PATH.unlink()
                except OSError: pass
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.bind(str(SOCKET_PATH))
        else:
            if PORT_FILE.exists():
                try: PORT_FILE.unlink()
                except OSError: pass
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind(("127.0.0.1", 0))
            PORT_FILE.write_text(str(self.sock.getsockname()[1]))

        self.sock.listen(10)
        self.sock.setblocking(False)
        PID_FILE.write_text(str(os.getpid()))

        threading.Thread(target=self._server_loop, daemon=True).start()
        threading.Thread(target=self._state_sync_loop, daemon=True).start()

    def _server_loop(self):
        while self.running:
            try:
                r, _, _ = select.select([self.sock], [], [], 0.2)
                if r:
                    conn, _ = self.sock.accept()
                    threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception: pass

    def _handle_client(self, conn: socket.socket):
        try:
            conn.settimeout(2.0)
            data = conn.recv(4096).decode('utf-8')
            if not data: return
            req = json.loads(data)
            cmd = req.get("cmd")
            res: Dict[str, Any] = {"status": "ok"}

            if cmd == "status": res["data"] = self.engine.get_status_dict()
            elif cmd == "play":
                f = req.get("file")
                if f:
                    def _load_bg(target_f):
                        for i, t in enumerate(self.engine.playlist):
                            if t["path"] == target_f or t["name"] == os.path.basename(target_f):
                                self.engine.load_track(i, True); return
                        self.engine.playlist.insert(0, {"name": os.path.basename(target_f), "path": target_f, "size_mb": 0, "mtime": time.time(), "ext": os.path.splitext(target_f)[1][1:].upper()})
                        self.engine.load_track(0, True)
                    threading.Thread(target=_load_bg, args=(f,), daemon=True).start()
                else: self.engine.play()
            elif cmd == "pause": self.engine.pause()
            elif cmd in ("toggle", "play_pause"):
                self.engine.toggle_play_pause()
                res["state"] = self.engine.state
            elif cmd in ("stop", "quit"):
                self.engine.stop_playback()
                self.running = False
                for p in (STATE_FILE, SOCKET_PATH, PORT_FILE, PID_FILE):
                    try: p.unlink()
                    except OSError: pass
                conn.sendall(json.dumps(res).encode('utf-8'))
                conn.close()
                os._exit(0)
            elif cmd == "next": threading.Thread(target=self.engine.next_track, daemon=True).start()
            elif cmd == "prev": threading.Thread(target=self.engine.prev_track, daemon=True).start()
            elif cmd == "seek": self.engine.seek_relative(float(req.get("seconds", 10.0)))
            elif cmd == "seek_to": self.engine.seek(float(req.get("position", 0.0)))
            elif cmd == "set_volume": self.engine.set_volume(int(req.get("volume", 85)))
            elif cmd == "vol_up": self.engine.change_volume(int(req.get("step", 5)))
            elif cmd == "vol_down": self.engine.change_volume(-int(req.get("step", 5)))
            elif cmd in ("pitch_up", "pitch_down", "set_pitch", "reset_pitch"):
                if cmd == "pitch_up": self.engine.change_pitch(int(req.get("step", 1)))
                elif cmd == "pitch_down": self.engine.change_pitch(-int(req.get("step", 1)))
                elif cmd == "set_pitch": self.engine.set_pitch(int(req.get("percent", 0)))
                else: self.engine.reset_pitch()
                res.update(pitch_percent=self.engine.pitch_percent, pitch_factor=self.engine.pitch_factor)
            elif cmd == "mute":
                self.engine.toggle_mute()
                res["muted"] = self.engine.muted
            elif cmd == "shuffle":
                self.engine.toggle_shuffle()
                res["shuffle"] = self.engine.shuffle
            elif cmd == "repeat":
                self.engine.cycle_repeat()
                res["repeat"] = self.engine.repeat_mode
            elif cmd in ("record", "toggle_record"):
                is_rec, rec_f = self.engine.toggle_recording()
                res.update(recording=is_rec, recording_file=rec_f)
            elif cmd == "start_record":
                rec_f = self.engine.start_recording()
                res.update(recording=True, recording_file=rec_f)
            elif cmd == "stop_record":
                ok, rec_f = self.engine.stop_recording()
                res.update(recording=False, recording_file=rec_f)
            elif cmd == "select_index": threading.Thread(target=self.engine.load_track, args=(int(req.get("index", 0)), True), daemon=True).start()
            elif cmd == "queue":
                f = req.get("file") or req.get("track")
                q_res = self.engine.queue_track(f) if f else {"queued": False, "queue_len": len(self.engine.play_queue)}
                res.update(q_res)
            elif cmd == "get_queue":
                res["queue"] = self.engine.get_queue()
                res["queue_len"] = len(res["queue"])
            elif cmd == "clear_queue":
                cleared = self.engine.clear_queue()
                res["cleared"] = cleared
            elif cmd == "get_playlist": res["playlist"] = [{"index": i, "name": t["name"], "path": t["path"], "ext": t["ext"]} for i, t in enumerate(self.engine.playlist[:100])]
            elif cmd in ("open_file_manager", "reveal"):
                tf = req.get("file") or (self.engine.current_track.get("path") if self.engine.current_track else "")
                target = choose_file_manager_target(tf)
                res["success"] = bool(target) and open_in_file_manager(target)
            elif cmd in ("route_bluetooth", "switch_bluetooth"):
                if getattr(self.engine, "bt_router", None):
                    ok = self.engine.bt_router.route_to_bluetooth()
                    res["routed"] = ok
                    res["bluetooth"] = self.engine.bt_router.get_status()
                else:
                    res["status"] = "error"
                    res["message"] = "Bluetooth router not available"
            elif cmd in ("revert_audio", "fallback_audio"):
                if getattr(self.engine, "bt_router", None):
                    ok = self.engine.bt_router.route_to_fallback()
                    res["reverted"] = ok
                    res["bluetooth"] = self.engine.bt_router.get_status()
                else:
                    res["status"] = "error"
                    res["message"] = "Bluetooth router not available"
            elif cmd == "bluetooth_status":
                if getattr(self.engine, "bt_router", None):
                    res["bluetooth"] = self.engine.bt_router.get_status()
                else:
                    res["bluetooth"] = {"bluetooth_connected": False}
            elif cmd == "toggle_bluetooth_auto":
                if getattr(self.engine, "bt_router", None):
                    self.engine.auto_bluetooth = not getattr(self.engine, "auto_bluetooth", True)
                    self.engine.bt_router.auto_switch = self.engine.auto_bluetooth
                    res["auto_switch"] = self.engine.auto_bluetooth
                else:
                    res["status"] = "error"
            elif cmd == "set_mode":
                self.engine.mode = str(req.get("mode", "MIX_ARCHIVE")).upper()
                res["mode"] = self.engine.mode
            elif cmd == "load_playlist":
                pl = req.get("playlist", [])
                mode = str(req.get("mode", "MUSIC")).upper()
                pl_path = req.get("playlist_path")
                folder_name = req.get("folder_name")
                if not pl:
                    if mode == "MUSIC" or pl_path or folder_name:
                        m_scanner = MusicFolderPlaylistScanner(folder_name=folder_name or "ALL", playlist_path=pl_path or "")
                        pl = m_scanner.get_mixes()
                        mode = "MUSIC"
                    else:
                        a_scanner = MixArchiveScanner(get_base_dir())
                        pl = a_scanner.get_mixes()
                        mode = "MIX_ARCHIVE"
                self.engine.playlist = pl
                self.engine.mode = mode
                if pl and req.get("play", False):
                    self.engine.load_track(0, True)
                res["loaded"] = len(pl)
                res["mode"] = self.engine.mode
            elif cmd in ("generate_spek", "spek"):
                tf = req.get("file") or (self.engine.current_track.get("path") if self.engine.current_track else None)
                if not tf and self.engine.playlist:
                    tf = self.engine.playlist[0].get("path")
                if tf:
                    ok, spek_res = generate_track_spek(tf, mode=self.engine.mode)
                    res["success"] = ok
                    res["spek_path"] = spek_res if ok else ""
                    if not ok:
                        res["status"] = "error"
                        res["message"] = spek_res
                else:
                    res["status"] = "error"
                    res["message"] = "No track available for Spek generation"


            conn.sendall(json.dumps(res, default=float).encode('utf-8'))
        except Exception as e:
            try: conn.sendall(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
            except Exception: pass
        finally:
            try: conn.close()
            except Exception: pass

    def _state_sync_loop(self):
        while self.running:
            self.engine._sync_state_file()
            time.sleep(0.02)

def _cleanup_stale_daemon_files():
    for p in (PID_FILE, SOCKET_PATH, PORT_FILE):
        try:
            if p.exists(): p.unlink()
        except OSError: pass
    try:
        STATE_FILE.write_text(json.dumps({"running": False, "state": "stopped"}), encoding="utf-8")
    except OSError: pass

def send_ipc_command(cmd: str, **kwargs) -> Optional[Dict[str, Any]]:
    has_unix = hasattr(socket, "AF_UNIX")
    use_unix = has_unix and SOCKET_PATH.exists()
    use_port = not use_unix and PORT_FILE.exists()
    if not use_unix and not use_port: return None
    for _ in range(4):
        try:
            s = socket.socket(socket.AF_UNIX if use_unix else socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.5)
            s.connect(str(SOCKET_PATH) if use_unix else ("127.0.0.1", int(PORT_FILE.read_text().strip())))
            payload = {"cmd": cmd, **kwargs}
            s.sendall(json.dumps(payload).encode('utf-8'))
            raw = s.recv(65536).decode('utf-8')
            s.close()
            if raw: return json.loads(raw)
        except (ConnectionRefusedError, FileNotFoundError):
            break
        except Exception:
            time.sleep(0.08)
    return None

def is_player_daemon_running() -> bool:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if sys.platform == "win32":
                import ctypes
                k = ctypes.WinDLL("kernel32", use_last_error=True)
                h = k.OpenProcess(0x1000, False, pid)
                if h:
                    ec = ctypes.c_ulong()
                    ok = k.GetExitCodeProcess(h, ctypes.byref(ec))
                    k.CloseHandle(h)
                    if ok and ec.value == 259: return True
            else:
                os.kill(pid, 0)
                try:
                    cmd_path = Path(f"/proc/{pid}/cmdline")
                    if cmd_path.exists():
                        cmd_str = cmd_path.read_text(errors="ignore")
                        if "MP_Audio_Player" in cmd_str or "python" in cmd_str:
                            return True
                    else:
                        return True
                except Exception:
                    return True
        except (OSError, ValueError):
            pass
        _cleanup_stale_daemon_files()

    if hasattr(socket, "AF_UNIX") and SOCKET_PATH.exists():
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.8)
            s.connect(str(SOCKET_PATH))
            s.close()
            return True
        except (ConnectionRefusedError, FileNotFoundError):
            try: SOCKET_PATH.unlink()
            except OSError: pass
        except Exception:
            return True
    elif not hasattr(socket, "AF_UNIX") and PORT_FILE.exists():
        try:
            port = int(PORT_FILE.read_text().strip())
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.8)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except (ConnectionRefusedError, OSError):
            try: PORT_FILE.unlink()
            except OSError: pass
        except Exception:
            return True
    return False

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_WIN_CONSOLE = None

def _char_display_width(ch: str) -> int:
    return 0 if (ch in ("\ufe0e", "\ufe0f") or unicodedata.combining(ch)) else (2 if ord(ch) >= 0x1F000 or unicodedata.east_asian_width(ch) in ("W", "F") else 1)

def _display_width(text: str) -> int:
    return sum(_char_display_width(c) for c in _ANSI_RE.sub("", text))

def _clip_display(text: str, max_cols: int) -> str:
    if max_cols <= 0: return ""
    out, cols, i, n = [], 0, 0, len(text)
    while i < n:
        if text[i] == "\033":
            m = _ANSI_RE.match(text, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
        w = _char_display_width(text[i])
        if cols + w > max_cols: break
        out.append(text[i])
        cols += w
        i += 1
    if i < n: out.append(NC)
    return "".join(out)

def _boxed_rule(left: str, text: str, right: str, inner: int, color: str) -> str:
    inner = max(4, int(inner))
    sh = text if _display_width(text) <= inner else _clip_display(text, inner)
    return f"  {color}{left}{sh}{'─' * (inner - _display_width(sh))}{right}{NC}"

def _fit_text_line(cands: List[str], max_cols: int) -> str:
    for l in cands:
        if _display_width(l) <= max_cols: return l
    return _clip_display(cands[-1] if cands else "", max_cols)

def _win_console_begin():
    global _WIN_CONSOLE
    if sys.platform != "win32": return None
    try:
        import msvcrt, ctypes
        h = msvcrt.get_osfhandle(sys.stdout.fileno())
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        m = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(m)): return None
        k.SetConsoleMode(h, (m.value | 0x0004) & ~0x0002)
        _WIN_CONSOLE = {"handle": h, "mode": m.value, "kernel32": k}
        return _WIN_CONSOLE
    except Exception: return None

def _win_visible_size(fallback: Tuple[int, int] = (80, 24)) -> Tuple[int, int]:
    try:
        s = shutil.get_terminal_size(fallback)
        return int(s.columns), int(s.lines)
    except Exception: return fallback

def _win_console_end(state):
    global _WIN_CONSOLE
    if state:
        try: state["kernel32"].SetConsoleMode(state["handle"], state["mode"])
        except Exception: pass
    _WIN_CONSOLE = None

def _present_frame(lines: List[str], width: int, height: int):
    usable = max(1, width - 1)
    clipped = [_clip_display(l, usable) + "\033[K" for l in lines[:height]]
    clipped.extend(["\033[K"] * (height - len(clipped)))
    frame = "\n".join(clipped[:-1]) + ("\n" + clipped[-1] if len(clipped) > 1 else "")
    sys.stdout.write(f"\033[?2026h\033[?7l\033[H{frame}\033[?2026l")
    sys.stdout.flush()

class EqualizerVisualizer:
    STYLES = ["stereo_eq", "neon_prism_eq", "stardust_particles_eq", "master_spectrum", "analog_vu", "oscilloscope"]
    STYLE_NAMES = {
        "stereo_eq": "Dual Stereo (Default)",
        "neon_prism_eq": "Neon Chroma Prism (Thin Hi-Res)",
        "stardust_particles_eq": "Stardust Chroma (Thin Lines & Falling Dust)",
        "master_spectrum": "Master Spectrum (24-Band)",
        "analog_vu": "Analog Studio VU",
        "oscilloscope": "Oscilloscope Waveform",
    }
    THEMES = ["dreamworlds_ultra", "cosmic_supernova", "dreamworlds_neon", "retro_studio", "cyber_neon", "phosphor", "ice_cold", "retro_terminal"]

    def __init__(self, default_style: Optional[str] = None, default_theme: Optional[str] = None, theme: Optional[str] = None, style: Optional[str] = None):
        _ensure_numpy()
        self.style_idx = self.theme_idx = 0
        self.dust_particles: List[Dict[str, Any]] = []
        self.last_dust_update: float = time.time()
        self.dust_rng = random.Random()
        try:
            th_file = CONFIG_DIR / "theme"
            saved = theme or default_theme or (th_file.read_text(encoding="utf-8").strip().lower() if th_file.is_file() else None)
            if saved:
                self.set_theme(saved)
        except Exception:
            pass

        try:
            eq_file = CONFIG_DIR / "eq_style"
            target_style = style or default_style
            if target_style and target_style in self.STYLES:
                self.style_idx = self.STYLES.index(target_style)
            elif eq_file.is_file():
                saved_eq = eq_file.read_text(encoding="utf-8").strip().lower()
                if saved_eq in self.STYLES:
                    self.style_idx = self.STYLES.index(saved_eq)
                elif saved_eq in ("neon", "prism", "chroma", "neon_prism"):
                    self.style_idx = self.STYLES.index("neon_prism_eq")
                elif saved_eq in ("stardust", "particles", "dust", "falling_dust", "stardust_eq", "chroma_dust", "stardust_particles_eq"):
                    self.style_idx = self.STYLES.index("stardust_particles_eq")
        except Exception:
            pass

    @property
    def style(self) -> str: return self.STYLES[self.style_idx]
    @property
    def theme(self) -> str: return self.THEMES[self.theme_idx]

    @theme.setter
    def theme(self, name: str):
        self.set_theme(name)

    def set_theme(self, name: str):
        clean = str(name).strip().lower()
        if clean in self.THEMES:
            self.theme_idx = self.THEMES.index(clean)
        elif clean in ("retro_terminal", "unix_terminal", "retro_unix", "white_on_black", "old_style_unix", "terminal", "classic"):
            self.theme_idx = self.THEMES.index("retro_terminal")
        elif clean in ("cosmic_supernova", "cosmic", "supernova"):
            self.theme_idx = self.THEMES.index("cosmic_supernova")
        elif clean in ("cyberpunk", "cyber", "cyber_neon"):
            self.theme_idx = self.THEMES.index("cyber_neon")
        elif clean in ("matrix", "phosphor"):
            self.theme_idx = self.THEMES.index("phosphor")
        elif clean in ("nord", "ice_cold"):
            self.theme_idx = self.THEMES.index("ice_cold")
        elif clean in ("dracula", "dreamworlds_neon"):
            self.theme_idx = self.THEMES.index("dreamworlds_neon")
        elif clean in ("gruvbox", "retro_studio"):
            self.theme_idx = self.THEMES.index("retro_studio")
        elif clean in ("dreamworlds_ultra", "dreamworlds", "default", "mplanetarian"):
            self.theme_idx = self.THEMES.index("dreamworlds_ultra")

    def cycle_style(self):
        self.style_idx = (self.style_idx + 1) % len(self.STYLES)
        try: (CONFIG_DIR / "eq_style").write_text(self.style, encoding="utf-8")
        except Exception: pass

    def cycle_theme(self):
        self.theme_idx = (self.theme_idx + 1) % len(self.THEMES)
        try: (CONFIG_DIR / "theme").write_text(self.theme, encoding="utf-8")
        except Exception: pass

    def get_style_display_name(self) -> str:
        return self.STYLE_NAMES.get(self.style, self.style.replace("_", " ").title())

    def get_theme_palette(self) -> Dict[str, str]:
        t = self.theme
        if t == "cosmic_supernova":
            return {
                "highlight": "\033[38;2;224;86;253m",  # Nebula Orchid
                "active": "\033[38;2;0;245;212m",      # Aurora Mint
                "border": "\033[38;2;224;86;253m",
                "accent": "\033[38;2;76;201;240m",
            }
        elif t == "dreamworlds_neon":
            return {
                "highlight": COLOR_ELECTRIC_CYAN,
                "active": COLOR_NEON_PINK,
                "border": COLOR_NEON_PINK,
                "accent": COLOR_ELECTRIC_CYAN,
            }
        elif t == "retro_studio":
            return {
                "highlight": "\033[38;2;241;196;15m",  # Amber Gold
                "active": "\033[38;2;230;126;34m",      # Studio Orange
                "border": "\033[38;2;241;196;15m",
                "accent": "\033[38;2;243;156;18m",
            }
        elif t in ("cyber_neon", "cyberpunk"):
            return {
                "highlight": "\033[38;2;76;201;240m",  # Cyber Cyan
                "active": "\033[38;2;255;0;85m",       # Neon Pink
                "border": "\033[38;2;76;201;240m",
                "accent": "\033[38;2;255;0;85m",
            }
        elif t in ("phosphor", "matrix"):
            return {
                "highlight": "\033[38;2;57;255;20m",   # Phosphor Green
                "active": "\033[38;2;166;255;0m",      # Mint Green
                "border": "\033[38;2;57;255;20m",
                "accent": "\033[38;2;0;255;102m",
            }
        elif t in ("ice_cold", "nord"):
            return {
                "highlight": "\033[38;2;0;229;255m",   # Polar Ice Cyan
                "active": "\033[38;2;136;192;208m",    # Frost Slate
                "border": "\033[38;2;0;229;255m",
                "accent": "\033[38;2;129;161;193m",
            }
        elif t in ("retro_terminal", "classic"):
            return {
                "highlight": "\033[1;37m",             # High-contrast White
                "active": "\033[1;37m",
                "border": "\033[1;37m",
                "accent": "\033[1;37m",
            }
        else:  # dreamworlds_ultra, dreamworlds, default
            return {
                "highlight": COLOR_HOT_PURPLE,         # Hot Purple
                "active": COLOR_NEON_PINK,             # Neon Pink
                "border": COLOR_HOT_PURPLE,
                "accent": COLOR_ELECTRIC_CYAN,
            }

    def _get_neon_prism_color(self, c_frac: float, r_frac: float, is_peak: bool = False, is_cap: bool = False) -> str:
        t = self.theme
        if is_peak:
            if r_frac > 0.85:
                return "\033[38;2;255;255;255m\033[1m"
            elif r_frac > 0.5:
                return "\033[38;2;255;235;120m\033[1m"
            else:
                return "\033[38;2;0;255;255m\033[1m"

        if t == "cosmic_supernova":
            # Interstellar Supernova: Aurora Mint -> Pulsar Cyan -> Nebula Orchid -> Supernova Crimson
            if c_frac < 0.25:
                s = c_frac / 0.25
                r, g, b = 0.0, 0.96 - 0.17 * s, 0.83 + 0.11 * s
            elif c_frac < 0.55:
                s = (c_frac - 0.25) / 0.30
                r, g, b = 0.30 + 0.58 * s, 0.79 - 0.45 * s, 0.94 + 0.05 * s
            elif c_frac < 0.80:
                s = (c_frac - 0.55) / 0.25
                r, g, b = 0.88 + 0.12 * s, 0.34 - 0.14 * s, 0.99 - 0.59 * s
            else:
                s = (c_frac - 0.80) / 0.20
                r, g, b = 1.0, 0.20 - 0.10 * s, 0.40 - 0.25 * s
        elif t in ("dreamworlds_ultra", "dreamworlds"):
            # Multi-stop chromatic rainbow: Magenta -> Electric Indigo -> Cyan -> Emerald -> Solar Gold -> Tangerine -> Hot Pink
            h = (c_frac * 0.88 + 0.82) % 1.0
            h6 = h * 6.0
            i = int(h6)
            f = h6 - i
            q = 1.0 - f
            if i == 0:   r, g, b = 1.0, f, 0.1
            elif i == 1: r, g, b = q, 1.0, 0.1
            elif i == 2: r, g, b = 0.1, 1.0, f
            elif i == 3: r, g, b = 0.1, q, 1.0
            elif i == 4: r, g, b = f, 0.1, 1.0
            else:        r, g, b = 1.0, 0.1, q
        elif t == "dreamworlds_neon":
            # Cyber Neon: Electric Cyan -> Deep Lilac -> Hot Magenta -> Flame Orange
            if c_frac < 0.33:
                s = c_frac / 0.33
                r, g, b = 0.0, 0.90 - 0.50 * s, 1.0
            elif c_frac < 0.66:
                s = (c_frac - 0.33) / 0.33
                r, g, b = 0.70 * s + 0.20, 0.10, 1.0 - 0.20 * s
            else:
                s = (c_frac - 0.66) / 0.34
                r, g, b = 1.0, 0.15 + 0.40 * s, 0.50 - 0.50 * s
        elif t == "retro_studio":
            # Japanese Studio Vintage: Emerald Green -> Amber Gold -> Ruby Red
            if c_frac < 0.5:
                s = c_frac / 0.5
                r, g, b = 0.10 + 0.70 * s, 0.85 + 0.15 * s, 0.20 - 0.15 * s
            else:
                s = (c_frac - 0.5) / 0.5
                r, g, b = 0.90 + 0.10 * s, 0.85 - 0.60 * s, 0.10
        elif t == "cyber_neon":
            r = 0.45 + 0.50 * math.sin(c_frac * math.pi)
            g = 0.10 + 0.70 * c_frac
            b = 0.95 - 0.20 * c_frac
        elif t == "phosphor":
            r, g, b = 0.10 * (1.0 - c_frac), 0.95, 0.20
        elif t == "retro_terminal":
            r, g, b = 1.0, 1.0, 1.0
        else: # ice_cold
            r = 0.10 + 0.75 * (c_frac ** 1.5)
            g = 0.50 + 0.45 * c_frac
            b = 1.0

        v = 0.62 + 0.38 * r_frac
        if is_cap and r_frac > 0.70:
            r = min(1.0, r * 1.25 + 0.15)
            g = min(1.0, g * 1.25 + 0.15)
            b = min(1.0, b * 1.25 + 0.15)
        else:
            r, g, b = r * v, g * v, b * v

        return f"\033[38;2;{int(r*255)};{int(g*255)};{int(b*255)}m"

    def render_neon_prism_eq(self, levels_l: np.ndarray, levels_r: np.ndarray,
                             peaks_l: np.ndarray, peaks_r: np.ndarray,
                             width: int = 80, height: int = 7,
                             rms: float = 0.0, peak_db: float = -60.0) -> List[str]:
        lines = []
        is_wide = (width >= 96)
        n = 21 if is_wide else 16

        # Resample levels & peaks across the n thin frequency bands
        if len(levels_l) > 1:
            x_in = np.linspace(0.0, 1.0, len(levels_l))
            x_out = np.linspace(0.0, 1.0, n)
            bl = np.interp(x_out, x_in, levels_l)
            br = np.interp(x_out, x_in, levels_r)
            pl = np.interp(x_out, x_in, peaks_l) if len(peaks_l) > 1 else bl
            pr = np.interp(x_out, x_in, peaks_r) if len(peaks_r) > 1 else br
        else:
            bl = br = pl = pr = np.zeros(n)

        # Dynamic transient beat pulse
        is_beat = (rms > 0.13 or peak_db > -5.0)
        bolt_col = f"\033[1;38;2;255;255;255m" if is_beat else (f"\033[1;38;2;255;215;0m" if rms > 0.07 else f"{COLOR_HOT_PURPLE}")
        div_col = f"\033[1;38;2;247;37;133m" if is_beat else f"{COLOR_HOT_PURPLE}"

        if is_wide:
            header = f"╭── {bolt_col}⚡{NC}{BOLD}{MAGENTA} LEFT (21-BAND NEON PRISM) ───────────┬── {bolt_col}⚡{NC}{BOLD}{MAGENTA} RIGHT (21-BAND NEON PRISM) ──────────╮"
        else:
            header = f"╭── {bolt_col}⚡{NC}{BOLD}{MAGENTA} LEFT (16-BAND PRISM) ─────────┬── {bolt_col}⚡{NC}{BOLD}{MAGENTA} RIGHT (16-BAND PRISM) ────────╮"
        lines.append(f"  {BOLD}{MAGENTA}{header}{NC}")

        for r in range(height - 1, -1, -1):
            r_frac = (r + 1) / float(height)

            def _side(bands, pks):
                parts = []
                for c in range(n):
                    frac = bands[c] * height - r
                    c_frac = c / float(n - 1)
                    pk = pks[c] if c < len(pks) else 0.0
                    is_pk = (int(round(pk * height)) == r)

                    if frac >= 1.0:
                        col = self._get_neon_prism_color(c_frac, r_frac, is_cap=(frac < 2.0))
                        ch = "█"
                    elif frac > 0.0:
                        col = self._get_neon_prism_color(c_frac, r_frac, is_cap=True)
                        ch = prism_level_glyph(max(1, min(8, int(frac * 8))))
                    elif is_pk:
                        if pk >= 0.90:
                            col = "\033[38;2;255;255;255m\033[1m"
                            ch = prism_peak_glyph(True, c)
                        else:
                            col = self._get_neon_prism_color(c_frac, r_frac, is_peak=True)
                            ch = prism_peak_glyph(False, c)
                    else:
                        ch = " "

                    parts.append(f"{col}{ch}{NC} " if ch != " " else "  ")

                if is_wide:
                    return " " + "".join(parts)
                else:
                    return "  " + "".join(parts) + "  "

            lines.append(f"  {BOLD}{MAGENTA}│{NC}{_side(bl, pl)}{div_col}│{NC}{_side(br, pr)}{BOLD}{MAGENTA}│{NC}")

        if is_wide:
            lbl = "│ 30 60 125 250 500 1k 2k 4k 8k 12k 16k 18k │ 30 60 125 250 500 1k 2k 4k 8k 12k 16k 18k │"
            bot = "╰───────────────────────────────────────────┴───────────────────────────────────────────╯"
        else:
            lbl = "│  32  64  125 250 500  1k  4k  16k  │  32  64  125 250 500  1k  4k  16k  │"
            bot = "╰────────────────────────────────────┴────────────────────────────────────╯"

        lines.extend([f"  {DIM}{CYAN}{lbl}{NC}", f"  {BOLD}{MAGENTA}{bot}{NC}"])
        return lines

    def _get_stardust_rgb(self, c_frac: float, r_frac: float, is_peak: bool = False, is_sparkle: bool = False) -> Tuple[int, int, int]:
        if is_sparkle:
            return (255, 255, 255) if r_frac > 0.75 else (255, 235, 140)
        if is_peak:
            if r_frac > 0.85:
                return (255, 255, 255)
            elif r_frac > 0.50:
                return (255, 235, 120)
            else:
                return (0, 255, 255)

        t = self.theme
        if t == "cosmic_supernova":
            # Interstellar Supernova: Aurora Mint -> Pulsar Cyan -> Nebula Orchid -> Supernova Crimson
            if c_frac < 0.25:
                s = c_frac / 0.25
                r, g, b = 0.0, 0.96 - 0.17 * s, 0.83 + 0.11 * s
            elif c_frac < 0.55:
                s = (c_frac - 0.25) / 0.30
                r, g, b = 0.30 + 0.58 * s, 0.79 - 0.45 * s, 0.94 + 0.05 * s
            elif c_frac < 0.80:
                s = (c_frac - 0.55) / 0.25
                r, g, b = 0.88 + 0.12 * s, 0.34 - 0.14 * s, 0.99 - 0.59 * s
            else:
                s = (c_frac - 0.80) / 0.20
                r, g, b = 1.0, 0.20 - 0.10 * s, 0.40 - 0.25 * s
        elif t in ("dreamworlds_ultra", "dreamworlds"):
            # Multi-stop iridescent rainbow: Magenta -> Electric Indigo -> Cyan -> Emerald -> Solar Gold -> Tangerine -> Hot Pink
            h = (c_frac * 0.88 + 0.82) % 1.0
            h6 = h * 6.0
            i = int(h6)
            f = h6 - i
            q = 1.0 - f
            if i == 0:   r, g, b = 1.0, f, 0.08
            elif i == 1: r, g, b = q, 1.0, 0.08
            elif i == 2: r, g, b = 0.08, 1.0, f
            elif i == 3: r, g, b = 0.08, q, 1.0
            elif i == 4: r, g, b = f, 0.08, 1.0
            else:        r, g, b = 1.0, 0.08, q
        elif t == "dreamworlds_neon":
            # Cyber Neon: Electric Cyan -> Deep Lilac -> Hot Magenta -> Flame Orange
            if c_frac < 0.33:
                s = c_frac / 0.33
                r, g, b = 0.0, 0.90 - 0.50 * s, 1.0
            elif c_frac < 0.66:
                s = (c_frac - 0.33) / 0.33
                r, g, b = 0.70 * s + 0.20, 0.10, 1.0 - 0.20 * s
            else:
                s = (c_frac - 0.66) / 0.34
                r, g, b = 1.0, 0.15 + 0.40 * s, 0.50 - 0.50 * s
        elif t == "retro_studio":
            # Japanese Studio Vintage: Emerald Green -> Amber Gold -> Ruby Red
            if c_frac < 0.5:
                s = c_frac / 0.5
                r, g, b = 0.10 + 0.70 * s, 0.85 + 0.15 * s, 0.20 - 0.15 * s
            else:
                s = (c_frac - 0.5) / 0.5
                r, g, b = 0.90 + 0.10 * s, 0.85 - 0.60 * s, 0.10
        elif t == "cyber_neon":
            r = 0.45 + 0.50 * math.sin(c_frac * math.pi)
            g = 0.10 + 0.70 * c_frac
            b = 0.95 - 0.20 * c_frac
        elif t == "phosphor":
            r, g, b = 0.10 * (1.0 - c_frac), 0.95, 0.20
        else: # ice_cold
            r = 0.10 + 0.75 * (c_frac ** 1.5)
            g = 0.50 + 0.45 * c_frac
            b = 1.0

        v = 0.58 + 0.42 * r_frac
        return (int(min(255, max(0, r * v * 255))),
                int(min(255, max(0, g * v * 255))),
                int(min(255, max(0, b * v * 255))))

    def _get_stardust_color(self, c_frac: float, r_frac: float, is_peak: bool = False, is_sparkle: bool = False) -> str:
        r, g, b = self._get_stardust_rgb(c_frac, r_frac, is_peak=is_peak, is_sparkle=is_sparkle)
        return f"\033[38;2;{r};{g};{b}m"

    def render_stardust_particles_eq(self, levels_l: np.ndarray, levels_r: np.ndarray,
                                     peaks_l: np.ndarray, peaks_r: np.ndarray,
                                     width: int = 80, height: int = 7,
                                     rms: float = 0.0, peak_db: float = -60.0) -> List[str]:
        lines = []
        is_wide = (width >= 96)
        n = 21 if is_wide else 16
        ch_w = 43 if is_wide else 36

        # Resample levels & peaks across the thin frequency needles
        if len(levels_l) > 1:
            x_in = np.linspace(0.0, 1.0, len(levels_l))
            x_out = np.linspace(0.0, 1.0, n)
            bl = np.interp(x_out, x_in, levels_l)
            br = np.interp(x_out, x_in, levels_r)
            pl = np.interp(x_out, x_in, peaks_l) if len(peaks_l) > 1 else bl
            pr = np.interp(x_out, x_in, peaks_r) if len(peaks_r) > 1 else br
        else:
            bl = br = pl = pr = np.zeros(n)

        now = time.time()
        is_beat = (rms > 0.13 or peak_db > -5.0)
        spark_col = "\033[1;38;2;255;255;255m" if is_beat else ("\033[1;38;2;255;215;0m" if rms > 0.07 else f"{COLOR_HOT_PURPLE}")
        div_col = "\033[1;38;2;247;37;133m" if is_beat else f"{COLOR_HOT_PURPLE}"

        spark = console_symbol("✦")
        if is_wide:
            col_map = [1 + b * 2 for b in range(n)]
            left_hdr = f"── {spark_col}{spark}{NC}{BOLD}{MAGENTA} LEFT (21-BAND CHROMA STARDUST) "
            left_hdr = left_hdr + "─" * (43 - _display_width(left_hdr))
            right_hdr = f"── {spark_col}{spark}{NC}{BOLD}{MAGENTA} RIGHT (21-BAND CHROMA STARDUST) "
            right_hdr = right_hdr + "─" * (43 - _display_width(right_hdr))
            header = f"╭{left_hdr}┬{right_hdr}╮"
        else:
            col_map = [2 + b * 2 for b in range(n)]
            left_hdr = f"── {spark_col}{spark}{NC}{BOLD}{MAGENTA} LEFT (16-BAND CHROMA DUST) "
            left_hdr = left_hdr + "─" * (36 - _display_width(left_hdr))
            right_hdr = f"── {spark_col}{spark}{NC}{BOLD}{MAGENTA} RIGHT (16-BAND CHROMA DUST) "
            right_hdr = right_hdr + "─" * (36 - _display_width(right_hdr))
            header = f"╭{left_hdr}┬{right_hdr}╮"

        lines.append(f"  {BOLD}{MAGENTA}{header}{NC}")

        # Particle generation & ejection from active frequency bands
        for ch_idx, (bands, pks) in enumerate([(bl, pl), (br, pr)]):
            for b in range(n):
                val = float(bands[b])
                pk = float(pks[b]) if b < len(pks) else val
                if val > 0.15 and (self.dust_rng.random() < val * 0.40):
                    h_val = min(float(height - 1), val * height)
                    if val > 0.70 or pk > 0.85:
                        sym = self.dust_rng.choice(stardust_dust_choices("hot"))
                    elif val > 0.35:
                        sym = self.dust_rng.choice(stardust_dust_choices("mid"))
                    else:
                        sym = self.dust_rng.choice(stardust_dust_choices("low"))
                    c_frac = b / float(n - 1)
                    col_rgb = self._get_stardust_rgb(c_frac, min(1.0, val), is_sparkle=(val > 0.75))
                    self.dust_particles.append({
                        "ch": ch_idx,
                        "x": float(col_map[b]) + self.dust_rng.uniform(-0.4, 0.4),
                        "y": float(h_val) + self.dust_rng.uniform(0.1, 0.8),
                        "vx": self.dust_rng.uniform(-0.5, 0.5),
                        "vy": self.dust_rng.uniform(0.7, 1.8),
                        "symbol": sym,
                        "color_rgb": col_rgb,
                        "life": self.dust_rng.uniform(1.8, 3.8),
                        "max_life": 3.8,
                        "sway_freq": self.dust_rng.uniform(1.8, 3.6),
                        "sway_amp": self.dust_rng.uniform(0.3, 0.8),
                        "twinkle_phase": self.dust_rng.uniform(0.0, 6.28),
                        "twinkle_speed": self.dust_rng.uniform(3.0, 9.0),
                    })

        # Extra transient beat eruption
        if is_beat and len(self.dust_particles) < 70:
            for _ in range(self.dust_rng.randint(2, 4)):
                rb = self.dust_rng.randint(0, n - 1)
                r_col = col_map[rb]
                r_frac = min(1.0, max(0.2, float(bl[rb])))
                c_frac = rb / float(n - 1)
                self.dust_particles.append({
                    "ch": self.dust_rng.choice([0, 1]),
                    "x": float(r_col) + self.dust_rng.uniform(-0.6, 0.6),
                    "y": float(min(height - 1, bl[rb] * height + self.dust_rng.uniform(0.5, 1.5))),
                    "vx": self.dust_rng.uniform(-0.8, 0.8),
                    "vy": self.dust_rng.uniform(0.6, 1.5),
                    "symbol": self.dust_rng.choice(stardust_dust_choices("hot")),
                    "color_rgb": (255, 255, 255) if self.dust_rng.random() < 0.4 else self._get_stardust_rgb(c_frac, r_frac, is_sparkle=True),
                    "life": self.dust_rng.uniform(2.0, 4.0),
                    "max_life": 4.0,
                    "sway_freq": self.dust_rng.uniform(2.0, 4.0),
                    "sway_amp": self.dust_rng.uniform(0.5, 1.1),
                    "twinkle_phase": self.dust_rng.uniform(0.0, 6.28),
                    "twinkle_speed": self.dust_rng.uniform(5.0, 12.0),
                })

        if len(self.dust_particles) > 75:
            self.dust_particles = self.dust_particles[-75:]

        # Physics update for floating dust motes
        dt = max(0.005, min(0.10, now - self.last_dust_update))
        self.last_dust_update = now
        alive = []
        for p in self.dust_particles:
            p["life"] -= dt
            if p["life"] <= 0.0:
                continue
            sway = math.sin(now * p["sway_freq"] + p["twinkle_phase"]) * p["sway_amp"]
            p["x"] += (p["vx"] + sway) * dt
            p["x"] = max(0.0, min(float(ch_w - 1), p["x"]))
            p["y"] -= p["vy"] * dt
            if p["y"] < 0.0:
                continue
            alive.append(p)
        self.dust_particles = alive

        # Render channel grids (thin lines + dust particles)
        channel_grids = []
        for ch_idx, (bands, pks) in enumerate([(bl, pl), (br, pr)]):
            grid_c = [[" " for _ in range(ch_w)] for _ in range(height)]
            grid_col = [["" for _ in range(ch_w)] for _ in range(height)]

            for b in range(n):
                col = col_map[b]
                c_frac = b / float(n - 1)
                val = float(bands[b])
                h_val = val * height
                crest_r = int(h_val)
                rem = h_val - crest_r
                pk_val = float(pks[b]) if b < len(pks) else val
                pk_r = min(height - 1, max(0, int(round(pk_val * height)))) if pk_val > 0.08 else -1

                for r in range(height):
                    r_frac = (r + 1) / float(height)
                    if r < crest_r:
                        grid_c[r][col] = "│"
                        grid_col[r][col] = self._get_stardust_color(c_frac, r_frac)
                    elif r == crest_r:
                        if rem > 0.65:
                            grid_c[r][col] = "│"
                            grid_col[r][col] = self._get_stardust_color(c_frac, r_frac)
                        elif rem > 0.25:
                            grid_c[r][col] = console_symbol("╵")
                            grid_col[r][col] = self._get_stardust_color(c_frac, r_frac)
                        elif rem > 0.05:
                            grid_c[r][col] = "·"
                            grid_col[r][col] = self._get_stardust_color(c_frac, r_frac)
                    elif r == pk_r:
                        if pk_val >= 0.85:
                            grid_c[r][col] = console_symbol("✦")
                            grid_col[r][col] = "\033[1;38;2;255;255;255m"
                        elif pk_val >= 0.50:
                            grid_c[r][col] = console_symbol("✧")
                            grid_col[r][col] = self._get_stardust_color(c_frac, r_frac, is_peak=True)
                        else:
                            grid_c[r][col] = "·"
                            grid_col[r][col] = self._get_stardust_color(c_frac, r_frac, is_peak=True)

            for p in self.dust_particles:
                if p["ch"] != ch_idx:
                    continue
                pr = int(round(p["y"]))
                pc = int(round(p["x"]))
                if not (0 <= pr < height and 0 <= pc < ch_w):
                    continue
                life_ratio = max(0.0, min(1.0, p["life"] / p["max_life"]))
                twinkle = math.sin(now * p["twinkle_speed"] + p["twinkle_phase"])

                if twinkle > 0.78 and life_ratio > 0.25:
                    p_col = "\033[1;38;2;255;255;255m"
                    if _use_limited_console_glyphs():
                        p_sym = p["symbol"] if p["symbol"] in ("•", "°", "·", "˙", "+") else "•"
                    else:
                        p_sym = p["symbol"] if p["symbol"] in ("✦", "✧", "⋆", "•") else "✦"
                else:
                    r_c, g_c, b_c = p["color_rgb"]
                    fade = life_ratio * (0.60 + 0.40 * max(0.0, twinkle))
                    if pr == 0:
                        fade *= 0.6
                    rr = max(20, min(255, int(r_c * fade)))
                    gg = max(20, min(255, int(g_c * fade)))
                    bb = max(20, min(255, int(b_c * fade)))
                    p_col = f"\033[38;2;{rr};{gg};{bb}m"
                    p_sym = console_symbol(p["symbol"])
                    if life_ratio < 0.20 and p_sym in ("✦", "✧", "•", "°"):
                        p_sym = "·"

                if grid_c[pr][pc] == " ":
                    grid_c[pr][pc] = p_sym
                    grid_col[pr][pc] = p_col
                elif p_sym in ("✦", "✧", "⋆") and twinkle > 0.78:
                    grid_c[pr][pc] = p_sym
                    grid_col[pr][pc] = p_col
                else:
                    for off in (+1, -1):
                        adj = pc + off
                        if 0 <= adj < ch_w and grid_c[pr][adj] == " ":
                            grid_c[pr][adj] = p_sym
                            grid_col[pr][adj] = p_col
                            break

            channel_grids.append((grid_c, grid_col))

        (gl_c, gl_col), (gr_c, gr_col) = channel_grids
        for r in range(height - 1, -1, -1):
            def _fmt(gc, gcol):
                return "".join(f"{gcol[r][c]}{gc[r][c]}{NC}" if gc[r][c] != " " else " " for c in range(ch_w))
            l_str = _fmt(gl_c, gl_col)
            r_str = _fmt(gr_c, gr_col)
            lines.append(f"  {BOLD}{MAGENTA}│{NC}{l_str}{div_col}│{NC}{r_str}{BOLD}{MAGENTA}│{NC}")

        if is_wide:
            lbl = "│ 30 60 125 250 500 1k 2k 4k 8k 12k 16k 18k │ 30 60 125 250 500 1k 2k 4k 8k 12k 16k 18k │"
            bot = "╰───────────────────────────────────────────┴───────────────────────────────────────────╯"
        else:
            lbl = "│  32  64  125 250 500  1k  4k  16k  │  32  64  125 250 500  1k  4k  16k  │"
            bot = "╰────────────────────────────────────┴────────────────────────────────────╯"

        lines.extend([f"  {DIM}{CYAN}{lbl}{NC}", f"  {BOLD}{MAGENTA}{bot}{NC}"])
        return lines

    def _get_bar_color(self, fraction: float) -> str:
        t = self.theme
        if t == "cosmic_supernova":
            # Interstellar Supernova: Aurora Mint (0-35%) -> Pulsar Cyan (35-65%) -> Nebula Orchid (65-85%) -> Supernova Crimson (85-100%)
            if fraction < 0.35:
                return "\033[38;2;0;245;212m"
            elif fraction < 0.65:
                return "\033[38;2;76;201;240m"
            elif fraction < 0.85:
                return "\033[38;2;224;86;253m"
            else:
                return "\033[38;2;255;51;102m"
        if t in ("dreamworlds_ultra", "dreamworlds"):
            return COLOR_TRAFFIC_GREEN if fraction < 0.60 else (COLOR_TRAFFIC_AMBER if fraction < 0.85 else COLOR_TRAFFIC_RED)
        if t == "dreamworlds_neon":
            return "\033[38;2;0;229;255m" if fraction < 0.4 else ("\033[38;2;247;37;133m" if fraction < 0.75 else "\033[38;2;255;140;0m")
        if t == "retro_studio":
            return "\033[38;2;46;204;113m" if fraction < 0.6 else ("\033[38;2;241;196;15m" if fraction < 0.85 else "\033[38;2;231;76;60m")
        if t == "cyber_neon": return "\033[38;2;114;9;183m" if fraction < 0.5 else "\033[38;2;76;201;240m"
        if t == "phosphor": return "\033[38;2;57;255;20m"
        return "\033[38;2;30;144;255m" if fraction < 0.5 else "\033[38;2;224;255;255m"

    def render_stereo_eq(self, levels_l: np.ndarray, levels_r: np.ndarray, peaks: np.ndarray, width: int = 80, height: int = 7) -> List[str]:
        lines = []
        is_wide = (width >= 96)
        n = 12 if is_wide else 8
        widths = [3, 3, 4, 4, 4, 3, 3, 3, 3, 4, 4, 4] if is_wide else [2] * 8
        if len(levels_l) > n:
            x_in = np.linspace(0.0, 1.0, len(levels_l))
            x_out = np.linspace(0.0, 1.0, n)
            bl = np.interp(x_out, x_in, levels_l)
            br = np.interp(x_out, x_in, levels_r)
        else:
            bl = levels_l[:n] if len(levels_l) >= n else np.pad(levels_l, (0, max(0, n - len(levels_l))))
            br = levels_r[:n] if len(levels_r) >= n else np.pad(levels_r, (0, max(0, n - len(levels_r))))

        header = f"╭── LEFT CHANNEL ({n}-BAND) " + ("─────────────────┬── RIGHT CHANNEL (12-BAND) ────────────────╮" if is_wide else "───────────┬── RIGHT CHANNEL (8-BAND) ──────────╮")
        lines.append(f"  {BOLD}{MAGENTA}{header}{NC}")

        for r in range(height - 1, -1, -1):
            col = self._get_bar_color(r / float(height))
            def _side(bands, pk_off):
                parts = []
                for c in range(n):
                    pk = peaks[(c + pk_off) % len(peaks)] if len(peaks) > 0 else 0.0
                    frac = bands[c] * height - r
                    ch = meter_level_char(frac, int(pk * height) == r)
                    w = widths[c] if is_wide else 2
                    parts.append(f" {ch} " if w == 3 else f" {ch*2} ")
                return (" " if is_wide else "  ") + "".join(parts) + ("" if is_wide else "  ")
            lines.append(f"  │{col}{_side(bl, 0)}{NC}│{col}{_side(br, n)}{NC}│")

        lbl = "│ 30 60 125 250 500 1k 2k 4k 8k 12k 16k 18k │ 30 60 125 250 500 1k 2k 4k 8k 12k 16k 18k │" if is_wide else "│  32  64  125 250 500  1k  4k  16k  │  32  64  125 250 500  1k  4k  16k  │"
        bot = "╰───────────────────────────────────────────┴───────────────────────────────────────────╯" if is_wide else "╰────────────────────────────────────┴────────────────────────────────────╯"
        lines.extend([f"  {DIM}{CYAN}{lbl}{NC}", f"  {BOLD}{MAGENTA}{bot}{NC}"])
        return lines

    def render_master_spectrum(self, levels: np.ndarray, peaks: np.ndarray, height: int = 7) -> List[str]:
        lines = [f"  {BOLD}{MAGENTA}╭── HIGH-RESOLUTION MASTER FREQUENCY SPECTRUM (30Hz - 18kHz) ──────────────╮{NC}"]
        if len(levels) > 1:
            x_old, x_new = np.linspace(0, 1, len(levels)), np.linspace(0, 1, 24)
            il, ip = np.interp(x_new, x_old, levels), np.interp(x_new, x_old, peaks) if len(peaks) > 1 else np.zeros(24)
        else: il = ip = np.zeros(24)

        for r in range(height - 1, -1, -1):
            col = self._get_bar_color(r / float(height))
            row_chars = []
            for c, val in enumerate(il):
                frac = val * height - r
                ch = meter_level_char(frac, int(ip[c] * height) == r)
                row_chars.append(f"{ch*2} ")
            lines.append(f"  │ {col}{''.join(row_chars)}{NC} │")

        lines.extend([f"  {DIM}{CYAN}│  32  63  125  250  500   1k   2k   4k   8k  12k  16k  18k    PEAK HOLD {console_symbol('✦')} │{NC}",
                      f"  {BOLD}{MAGENTA}╰──────────────────────────────────────────────────────────────────────────╯{NC}"])
        return lines

    def render_analog_vu(self, peak_db: float, levels_l: np.ndarray, levels_r: np.ndarray) -> List[str]:
        lines = [f"  {BOLD}{MAGENTA}╭── DUAL ANALOG STUDIO VU METERS (PEAK & RMS BALLISTICS) ──────────────────╮{NC}",
                 "  │  -40   -30   -20   -10   -7   -5   -3   -1    0  +1  +2  +3 dB           │"]
        blen = 46
        for name, val in (("LEFT  CHANNEL", np.mean(levels_l) if len(levels_l) else 0.0), ("RIGHT CHANNEL", np.mean(levels_r) if len(levels_r) else 0.0)):
            filled = int(val * blen)
            meter = "".join(f"{self._get_bar_color(i / blen)}█{NC}" if i < filled else f"{DIM}░{NC}" for i in range(blen))
            clip = f"{BOLD}{RED}[CLIP]{NC}" if filled >= blen - 1 else f"{DIM}[SAFE]{NC}"
            lines.append(f"  │  {BOLD}{CYAN}{name}{NC} [{meter}] {clip}   │")
        lines.extend([f"  │  Peak Audio Level: {BOLD}{YELLOW}{peak_db:+6.1f} dBFS{NC}  │  Master Headroom: {BOLD}{GREEN}{max(0.0, -peak_db):5.1f} dB{NC}             │",
                      f"  {BOLD}{MAGENTA}╰──────────────────────────────────────────────────────────────────────────╯{NC}"])
        return lines

    def render_oscilloscope(self, levels: np.ndarray, status: Optional[Dict[str, Any]] = None,
                            width: int = 80, height: int = 5) -> List[str]:
        if status is None:
            status = {}

        if width >= 80:
            iw = 70
            box_w = 76
            top_line = f"  {BOLD}{MAGENTA}╭── DYNAMIC OSCILLOSCOPE AUDIO WAVEFORM ───────────────────────────────────╮{NC}"
            bot_line = f"  {BOLD}{MAGENTA}╰──────────────────────────────────────────────────────────────────────────╯{NC}"
        else:
            box_w = max(24, min(76, width - 4))
            iw = max(16, box_w - 6)
            box_w = iw + 6
            hdr = "── OSCILLOSCOPE WAVEFORM "
            if box_w - 2 >= len(hdr):
                fill = "─" * (box_w - 2 - len(hdr))
                top_line = f"  {BOLD}{MAGENTA}╭{hdr}{fill}╮{NC}"
            else:
                fill = "─" * (box_w - 2)
                top_line = f"  {BOLD}{MAGENTA}╭{fill}╮{NC}"
            bot_fill = "─" * (box_w - 2)
            bot_line = f"  {BOLD}{MAGENTA}╰{bot_fill}╯{NC}"

        hh = max(1, height // 2)
        state = status.get("state", "stopped")
        is_playing = (state == "playing")
        rms = float(status.get("rms_level", 0.0))
        pitch_pct = int(status.get("pitch_percent", 0))
        pitch_mul = max(0.5, min(2.0, 1.0 + (pitch_pct / 100.0)))
        now = time.time()

        waveform = status.get("waveform", [])
        wf_arr = np.array(waveform, dtype=float) if waveform else np.zeros(0)
        has_live_pcm = len(wf_arr) >= 16 and float(np.max(np.abs(wf_arr))) > 0.01

        x_dst = np.linspace(0.0, 1.0, iw)

        if is_playing:
            bass = float(np.mean(levels[:4])) if len(levels) >= 4 else max(0.15, rms)
            mid = float(np.mean(levels[4:14])) if len(levels) >= 14 else rms * 0.7
            treble = float(np.mean(levels[14:])) if len(levels) >= 15 else rms * 0.4
            dyn_amp = max(0.25, min(1.0, rms * 2.2 + (float(np.max(levels)) * 0.8 if len(levels) else 0.0)))

            sweep_bass = now * (3.5 * pitch_mul)
            sweep_mid = now * (6.0 * pitch_mul)
            sweep_treble = now * (10.0 * pitch_mul)

            synth_w1 = np.sin(x_dst * (2.0 * math.pi) - sweep_bass) * (0.60 * max(0.2, bass))
            synth_w2 = np.sin(x_dst * (4.0 * math.pi) + sweep_mid) * (0.28 * max(0.1, mid))
            synth_w3 = np.sin(x_dst * (6.0 * math.pi) - sweep_treble) * (0.14 * max(0.05, treble))
            synth_pts = np.clip((synth_w1 + synth_w2 + synth_w3) * dyn_amp * 1.5, -0.98, 0.98)

            if has_live_pcm:
                x_src = np.linspace(0.0, 1.0, len(wf_arr))
                pcm_interp = np.interp(x_dst, x_src, wf_arr)
                max_abs = max(0.15, float(np.max(np.abs(pcm_interp))))
                pcm_scaled = (pcm_interp / max_abs) * min(1.0, max(0.25, rms * 2.0))
                pts = np.clip(0.65 * pcm_scaled + 0.35 * synth_pts, -0.98, 0.98)
            else:
                pts = synth_pts
        elif state == "paused":
            pts = np.sin(x_dst * (2.0 * math.pi) + now * 1.2) * 0.18
        else:
            pts = np.zeros(iw)

        y_floats = [float(p) * hh for p in pts]
        y_indices = [max(-hh, min(hh, int(round(yf)))) for yf in y_floats]

        lines = [top_line]
        center_x = iw // 2

        for r in range(hh, -hh - 1, -1):
            row_chars = []
            for i in range(iw):
                prev_y = y_indices[i - 1] if i > 0 else y_indices[i]
                curr_y = y_indices[i]
                r_min = min(prev_y, curr_y)
                r_max = max(prev_y, curr_y)

                if r_min <= r <= r_max:
                    c_frac = i / float(max(1, iw - 1))
                    curr_yf = y_floats[i]
                    intensity = min(1.0, abs(curr_yf) / float(hh) * 0.85 + rms * 0.35)
                    is_crest = (abs(curr_y) == hh and abs(curr_yf) >= hh * 0.75)
                    color = self._get_neon_prism_color(c_frac, intensity, is_peak=is_crest)

                    if r_min == r_max:
                        ch = "━"
                    elif curr_y > prev_y:
                        ch = "╱" if r in (r_min, r_max) else "│"
                    else:
                        ch = "╲" if r in (r_min, r_max) else "│"
                    row_chars.append(f"{color}{BOLD}{ch}{NC}")
                else:
                    is_tick = ((i - center_x) % 10 == 0)
                    if r == 0:
                        ch = "┼" if is_tick else "·"
                        row_chars.append(f"{DIM}{ch}{NC}")
                    elif is_tick:
                        row_chars.append(f"{DIM}·{NC}")
                    else:
                        row_chars.append(" ")

            row_content = "".join(row_chars)
            lines.append(f"  {BOLD}{MAGENTA}│{NC}  {row_content}  {BOLD}{MAGENTA}│{NC}")

        lines.append(bot_line)
        return lines

    def render_vertical_pitch_fader(self, pitch_pct: int, total_lines: int = 10) -> List[str]:
        p = max(-20, min(20, int(pitch_pct)))
        frows = max(3, total_lines - 2)
        has_hint = (frows % 2 == 0)
        track_rows = (frows - 1) if has_hint else frows
        crow = track_rows // 2

        if p == 0:
            krow = crow
        elif p > 0:
            krow = crow - int(round((p / 20.0) * crow))
        else:
            krow = crow + int(round((-p / 20.0) * (track_rows - 1 - crow)))

        lines = [f"{COLOR_HOT_PURPLE}╭── DJ PITCH ────────────╮{NC}"]

        for r in range(track_rows):
            if r == krow and r == crow:
                tag = f"{BOLD}{COLOR_TRAFFIC_GREEN}◄ 0.0% [CENTER]{NC}"
                lines.append(f"{COLOR_HOT_PURPLE}│{NC} {COLOR_TRAFFIC_GREEN}[▓█0█▓]{NC} {tag}{COLOR_HOT_PURPLE}│{NC}")
            elif r == krow:
                kcol = COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE
                tag_str = f"◄ {p:+d}% ({1.0 + p/100:.2f}x)"
                lines.append(f"{COLOR_HOT_PURPLE}│{NC} {kcol}[▓███▓]{NC} {BOLD}{kcol}{tag_str:<14}{NC} {COLOR_HOT_PURPLE}│{NC}")
            elif r == crow:
                lines.append(f"{COLOR_HOT_PURPLE}│{NC} {COLOR_INDIGO_BLUE}─── 0 ───{NC} {DIM}{COLOR_LILAC}CENTER (0%){NC}  {COLOR_HOT_PURPLE}│{NC}")
            elif r == 0:
                lines.append(f"{COLOR_HOT_PURPLE}│{NC}    {COLOR_TRAFFIC_AMBER}▲{NC}     {DIM}+20% MAX{NC}      {COLOR_HOT_PURPLE}│{NC}")
            elif r == track_rows - 1:
                lines.append(f"{COLOR_HOT_PURPLE}│{NC}    {COLOR_INDIGO_BLUE}▼{NC}     {DIM}-20% MIN{NC}      {COLOR_HOT_PURPLE}│{NC}")
            else:
                sp = " " * 19
                lines.append(f"{COLOR_HOT_PURPLE}│{NC}    {COLOR_INDIGO_BLUE}│{NC}{sp}{COLOR_HOT_PURPLE}│{NC}")

        if has_hint:
            lines.append(f"{COLOR_HOT_PURPLE}│{NC}  {DIM}[+/-: 1% • 0: Reset]{NC}  {COLOR_HOT_PURPLE}│{NC}")

        lines.append(f"{COLOR_HOT_PURPLE}╰────────────────────────╯{NC}")
        return lines

    def render_horizontal_pitch_bar(self, pitch_pct: int, width: int = 36, max_cols: Optional[int] = None) -> str:
        p = max(-20, min(20, int(pitch_pct)))
        w = max(11, width)
        if w % 2 == 0:
            w -= 1
        cpos = w // 2
        kpos = cpos if p == 0 else max(0, min(w - 1, cpos + int(round((p / 20.0) * cpos))))

        def _track(tw, kp, cp):
            chars = []
            for i in range(tw):
                if i == kp:
                    chars.append(f"{BOLD}{COLOR_TRAFFIC_GREEN if p == 0 else (COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE)}●{NC}")
                elif i == cp:
                    chars.append(f"{COLOR_TRAFFIC_GREEN}┼{NC}")
                elif i < cp:
                    chars.append(f"{DIM}━{NC}" if (i < kp and p < 0) else (f"{COLOR_INDIGO_BLUE}━{NC}" if kp <= i < cp else f"{DIM}─{NC}"))
                else:
                    chars.append(f"{COLOR_TRAFFIC_AMBER}━{NC}" if cp < i <= kp else f"{DIM}─{NC}")
            return "".join(chars)

        stag = f"{BOLD}{COLOR_TRAFFIC_GREEN}0.0% [CENTER DETENT]{NC}" if p == 0 else f"{BOLD}{COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE}{p:+d}% ({1.0 + p/100:.2f}x){NC}"
        pfx = f"  {BOLD}{COLOR_HOT_PURPLE}🎚 DJ PITCH:{NC} {DIM}-20%{NC} ["
        sfx = f"] {DIM}+20%{NC}  {stag}  {DIM}[+/-: 1% • 0: Reset]{NC}"

        if max_cols and (_display_width(pfx) + w + _display_width(sfx) > max_cols):
            sfx = f"] {DIM}+20%{NC}  {stag}"
            if _display_width(pfx) + w + _display_width(sfx) > max_cols:
                sfx = f"] {DIM}+20%{NC}  {BOLD}{COLOR_TRAFFIC_GREEN if p == 0 else (COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE)}{p:+d}%{NC}"
            avail = max_cols - _display_width(pfx) - _display_width(sfx)
            if avail < w:
                w = max(7, avail)
                if w % 2 == 0:
                    w -= 1
                cpos = w // 2
                kpos = cpos if p == 0 else max(0, min(w - 1, cpos + int(round((p / 20.0) * cpos))))

        return f"{pfx}{_track(w, kpos, cpos)}{sfx}"

    def render(self, status: Dict[str, Any], width: int = 80, height: int = 7) -> List[str]:
        levels = np.array(status.get("levels", [0.0]*24))
        peaks = np.array(status.get("peaks", [0.0]*24))
        ll = np.array(status.get("levels_left", levels))
        lr = np.array(status.get("levels_right", levels))
        pl = np.array(status.get("peaks_left", peaks))
        pr = np.array(status.get("peaks_right", peaks))
        rms = float(status.get("rms_level", 0.0))
        peak_db = float(status.get("peak_db", -60.0))

        s = self.style
        if s == "neon_prism_eq":
            lines = self.render_neon_prism_eq(ll, lr, pl, pr, width=width, height=height, rms=rms, peak_db=peak_db)
        elif s == "stardust_particles_eq":
            lines = self.render_stardust_particles_eq(ll, lr, pl, pr, width=width, height=height, rms=rms, peak_db=peak_db)
        elif s == "master_spectrum":
            lines = self.render_master_spectrum(levels, peaks, height=height)
        elif s == "analog_vu":
            lines = self.render_analog_vu(peak_db, ll, lr)
        elif s == "oscilloscope":
            lines = self.render_oscilloscope(levels, status=status, width=width, height=height)
        else:
            lines = self.render_stereo_eq(ll, lr, peaks, width=width, height=height)

        if width >= 122:
            faders = self.render_vertical_pitch_fader(int(status.get("pitch_percent", 0)), total_lines=len(lines))
            return [f"{el}{' ' * max(0, 91 - _display_width(el))}  {fl}" for el, fl in zip(lines, faders)]
        return lines


def _get_dynamic_gradient(step: float) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    """Generates non-repeating dynamic color gradients and ambient background tints via irrational phase modulation."""
    r = int(127.5 + 127.5 * math.sin(step * 0.6180339887 + 0.3))
    g = int(127.5 + 127.5 * math.sin(step * 0.8408964152 + 2.1))
    b = int(127.5 + 127.5 * math.sin(step * 0.7071067811 + 4.2))

    r2 = int(127.5 + 127.5 * math.sin(step * 0.6180339887 + 3.14159))
    g2 = int(127.5 + 127.5 * math.sin(step * 0.8408964152 + 5.28318))
    b2 = int(127.5 + 127.5 * math.sin(step * 0.7071067811 + 1.04719))

    # Dynamic ambient background tint: rich, evolving chromatic hues clearly visible at 30% opacity
    bg_r = int(60 + 52 * math.sin(step * 0.41 + 0.5))
    bg_g = int(48 + 42 * math.sin(step * 0.53 + 2.4))
    bg_b = int(78 + 58 * math.sin(step * 0.47 + 4.1))

    return (r, g, b), (r2, g2, b2), (bg_r, bg_g, bg_b)


def _setup_mini_terminal_appearance():
    """Configures 30% background transparency and colorscheme for Konsole and other terminals."""
    if sys.platform.startswith(("linux", "freebsd")):
        k_dir = Path.home() / ".local" / "share" / "konsole"
        if k_dir.is_dir():
            try:
                c_scheme = k_dir / "MP_Mini_Player.colorscheme"
                c_content = (
                    "[Background]\nColor=16,18,28\nOpacity=0.30\n\n"
                    "[BackgroundFaint]\nColor=18,22,34\n\n"
                    "[Color0]\nColor=16,18,28\n[Color1]\nColor=247,37,133\n[Color2]\nColor=0,229,255\n"
                    "[Color3]\nColor=255,170,0\n[Color4]\nColor=102,102,255\n[Color5]\nColor=166,77,255\n"
                    "[Color6]\nColor=0,193,228\n[Color7]\nColor=209,209,224\n"
                )
                c_scheme.write_text(c_content, encoding="utf-8")
                prof = k_dir / "MP_Mini_Player.profile"
                if not prof.exists():
                    prof.write_text(
                        "[Appearance]\nColorScheme=MP_Mini_Player\nFont=Monospace,11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1,,0,0\n\n"
                        "[General]\nEnvironment=TERM=xterm-256color,COLORTERM=truecolor\nInheritContainerContext=true\n"
                        "Name=MP_Mini_Player\nParent=FALLBACK/\nTerminalColumns=74\nTerminalRows=14\n\n"
                        "[Terminal Features]\nBlinkingCursorEnabled=true\n",
                        encoding="utf-8"
                    )
            except Exception:
                pass
        if os.environ.get("KONSOLE_VERSION") or os.environ.get("KONSOLE_DBUS_SERVICE"):
            try:
                sys.stdout.write("\033]50;ColorScheme=MP_Mini_Player\a")
                sys.stdout.flush()
            except Exception:
                pass


def launch_mini_player_window(mode: str = "MIX_ARCHIVE", folder_name: str = "ALL", playlist_path: str = "",
                              theme: Optional[str] = None, style: Optional[str] = None) -> bool:
    """Spawns an independent MP Mini Audio Player instance in a dedicated compact transparent terminal window."""
    script_path = str(Path(__file__).resolve())
    py_exe = sys.executable or "python3"
    title = "MP Mini Audio Player"
    cmd_args = [py_exe, script_path, "--interactive", "--mini"]
    if mode == "MUSIC":
        cmd_args.append("--music-mode")
        if folder_name and folder_name != "ALL":
            cmd_args.extend(["--music-folder", str(folder_name)])
        if playlist_path:
            cmd_args.extend(["--playlist", str(playlist_path)])
    if theme:
        cmd_args.extend(["--theme", str(theme)])
    if style:
        cmd_args.extend(["--style", str(style)])

    if sys.platform.startswith(("linux", "freebsd")):
        _setup_mini_terminal_appearance()

        if shutil.which("konsole"):
            k_cmd = ["konsole", "--profile", "MP_Mini_Player", "--hide-menubar", "--hide-tabbar", "--separate",
                     "--qwindowtitle", title, "-p", f"tabtitle={title}",
                     "-p", "TerminalColumns=74", "-p", "TerminalRows=14", "-e"] + cmd_args
            if _run_bg(k_cmd):
                if shutil.which("xprop"):
                    threading.Thread(target=lambda: (time.sleep(0.2), subprocess.run(
                        ["xprop", "-name", title, "-f", "_NET_WM_WINDOW_OPACITY", "32c", "-set", "_NET_WM_WINDOW_OPACITY", "0x4d000000"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)), daemon=True).start()
                return True

        for term, targs in [
            ("gnome-terminal", [f"--title={title}", "--geometry=74x14", "--"] + cmd_args),
            ("xfce4-terminal", [f"--title={title}", "--geometry=74x14", "--hide-menubar", "--hide-borders", "-e", " ".join(f'"{a}"' for a in cmd_args)]),
            ("alacritty", ["--title", title, "-o", "window.opacity=0.30", "-o", "window.dimensions.columns=74", "-o", "window.dimensions.lines=14", "-e"] + cmd_args),
            ("foot", ["-T", title, "-w", "74x14", "-a", "0.30"] + cmd_args),
            ("xterm", ["-title", title, "-geometry", "74x14", "-e"] + cmd_args),
            ("xdg-terminal-exec", cmd_args)
        ]:
            if shutil.which(term) and _run_bg([term] + targs if isinstance(targs, list) else [term, targs]):
                return True

    elif sys.platform == "darwin":
        c_str = " ".join(f'\\"{a}\\"' for a in cmd_args)
        apple_sc = f'tell application "Terminal" to do script "{c_str}"'
        if _run_bg(["osascript", "-e", apple_sc]):
            return True

    elif sys.platform == "win32":
        if shutil.which("wt.exe"):
            if _run_bg(["wt.exe", "-w", "new", "--title", title, "-p", "Command Prompt", "--size", "74,14"] + cmd_args):
                return True
        c_str = " ".join(f'"{a}"' for a in cmd_args)
        try:
            subprocess.Popen(f'start "{title}" {c_str}', shell=True)
            return True
        except Exception:
            pass

    return False


def launch_player_window(mode: str = "MIX_ARCHIVE", folder_name: str = "ALL", playlist_path: str = "",
                         theme: Optional[str] = None, style: Optional[str] = None) -> bool:
    """Spawns an interactive MP Audio Player instance in a dedicated new terminal window."""
    script_path = str(Path(__file__).resolve())
    py_exe = sys.executable or "python3"
    title = "MP Audio Player"
    cmd_args = [py_exe, script_path, "--interactive"]
    if mode == "MUSIC":
        cmd_args.append("--music-mode")
        if folder_name and folder_name != "ALL":
            cmd_args.extend(["--music-folder", str(folder_name)])
        if playlist_path:
            cmd_args.extend(["--playlist", str(playlist_path)])
    if theme:
        cmd_args.extend(["--theme", str(theme)])
    if style:
        cmd_args.extend(["--style", str(style)])

    if sys.platform.startswith(("linux", "freebsd")):
        if shutil.which("konsole"):
            k_cmd = ["konsole", "--separate", "--workdir", str(Path.cwd()),
                     "--qwindowtitle", title, "-p", f"tabtitle={title}", "-e"] + cmd_args
            if _run_bg(k_cmd):
                return True

        for term, targs in [
            ("xdg-terminal-exec", cmd_args),
            ("gnome-terminal", [f"--title={title}", "--"] + cmd_args),
            ("xfce4-terminal", [f"--title={title}", "-e", " ".join(f'"{a}"' for a in cmd_args)]),
            ("alacritty", ["--title", title, "-e"] + cmd_args),
            ("foot", ["-T", title] + cmd_args),
            ("xterm", ["-title", title, "-e"] + cmd_args),
        ]:
            if shutil.which(term) and _run_bg([term] + targs if isinstance(targs, list) else [term, targs]):
                return True

    elif sys.platform == "darwin":
        c_str = " ".join(f'\\"{a}\\"' for a in cmd_args)
        apple_sc = f'tell application "Terminal" to do script "{c_str}"'
        if _run_bg(["osascript", "-e", apple_sc]):
            return True

    elif sys.platform == "win32":
        if shutil.which("wt.exe"):
            if _run_bg(["wt.exe", "-w", "new", "--title", title, "-p", "Command Prompt"] + cmd_args):
                return True
        c_str = " ".join(f'"{a}"' for a in cmd_args)
        try:
            subprocess.Popen(f'start "{title}" {c_str}', shell=True)
            return True
        except Exception:
            pass

    return False


class TerminalPlayerUI:
    def __init__(self, engine: Optional[AudioEngine], scanner: Union[MixArchiveScanner, MusicFolderPlaylistScanner], is_remote: bool = False,
                 default_style: Optional[str] = None, default_theme: Optional[str] = None,
                 mode: str = "MIX_ARCHIVE", folder_name: str = "ALL", ui_size_mode: str = "NORMAL"):
        self.engine, self.scanner, self.is_remote = engine, scanner, is_remote
        self.mode = str(mode or "MIX_ARCHIVE").upper()
        self.folder_name = str(folder_name or "ALL").upper()
        self.ui_size_mode = str(ui_size_mode or "NORMAL").upper()
        self.visualizer = EqualizerVisualizer(default_style=default_style, default_theme=default_theme)
        self.running = True
        self.search_mode, self.search_query, self.export_mode, self.export_path = False, "", False, ""
        self.selected_row, self.scroll_offset, self.notification_msg, self.notification_time = 0, 0, "", 0.0
        self._last_seen_bt_device: Optional[str] = None
        self._last_seen_bt_state: Optional[bool] = None

        # Track Audio Inspector HUD State
        self.inspector_hud_active = False

        # Background Track Duration Resolver (MUSIC Mode)
        self._duration_cache: Dict[str, str] = {}
        if DURATION_CACHE_FILE.exists():
            try:
                loaded = json.loads(DURATION_CACHE_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._duration_cache.update(loaded)
            except Exception: pass
        self._duration_queue: Optional[queue.Queue] = None
        self._duration_in_queue: set = set(self._duration_cache.keys())
        self._duration_worker_started = False

        self.cached_status = {"title": "Loading...", "path": "", "state": "stopped", "position_fmt": "00:00",
                              "duration_fmt": "00:00", "progress_pct": 0.0, "volume": 85, "muted": False,
                              "shuffle": False, "repeat": "all", "mode": self.mode,
                              "recording": False, "recording_file": "", "recording_bytes": 0, "recording_duration": 0.0,
                              "levels": [0.0]*24, "peaks": [0.0]*24,
                              "levels_left": [0.0]*24, "levels_right": [0.0]*24,
                              "peaks_left": [0.0]*24, "peaks_right": [0.0]*24,
                              "waveform": [0.0]*80,
                              "rms_level": 0.0, "peak_db": -60.0}

    def _save_duration_cache(self):
        try:
            tmp = DURATION_CACHE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._duration_cache), encoding="utf-8")
            tmp.replace(DURATION_CACHE_FILE)
        except Exception: pass

    def _start_duration_worker(self):
        if self._duration_worker_started:
            return
        self._duration_worker_started = True
        self._duration_queue = queue.Queue()

        def _worker():
            _ensure_audio_backends()
            last_save = time.time()
            while self.running:
                try:
                    if not self._duration_queue:
                        break
                    item = self._duration_queue.get(timeout=0.4)
                except Exception:
                    continue
                path, m_ref = item
                if path in self._duration_cache:
                    continue
                if self.engine and getattr(self.engine, "state", "") == "playing" and is_cloud_or_remote_path(path):
                    time.sleep(0.08)
                try:
                    if sf is not None and os.path.isfile(path):
                        if is_cloud_or_remote_path(path):
                            time.sleep(0.12)
                        info = sf.info(path)
                        dfmt = format_seconds(info.duration)
                        self._duration_cache[path] = dfmt
                        if isinstance(m_ref, dict):
                            m_ref["duration_fmt"] = dfmt
                            m_ref["duration_sec"] = info.duration
                        if time.time() - last_save > 5.0:
                            self._save_duration_cache()
                            last_save = time.time()
                    else:
                        self._duration_cache[path] = "00:00"
                except Exception:
                    self._duration_cache[path] = "00:00"
                finally:
                    if self._duration_queue:
                        self._duration_queue.task_done()
            self._save_duration_cache()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _request_duration(self, m: Dict[str, Any]):
        p = m.get("path")
        if not p or p in self._duration_cache or p in self._duration_in_queue:
            return
        if not self._duration_worker_started:
            self._start_duration_worker()
        self._duration_in_queue.add(p)
        if self._duration_queue:
            self._duration_queue.put((p, m))

    def _get_status(self) -> Dict[str, Any]:
        if self.is_remote:
            if STATE_FILE.exists():
                try:
                    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and data.get("title") and data.get("title") != "Loading...":
                        self.cached_status = data
                except Exception:
                    pass
            elif not self.cached_status.get("title") or self.cached_status.get("title") == "Loading...":
                res = send_ipc_command("status")
                if res and isinstance(res.get("data"), dict):
                    self.cached_status = res["data"]
            if self.cached_status.get("mode"):
                self.mode = str(self.cached_status.get("mode")).upper()
            return self.cached_status
        st = self.engine.get_status_dict() if self.engine else self.cached_status
        if st.get("mode"):
            self.mode = str(st.get("mode")).upper()
        return st

    def _sync_initial_selection(self, status: Dict[str, Any]):
        cp = status.get("path")
        if cp and cp != getattr(self, "_last_path", None):
            self._last_path = cp
            if not self.search_query:
                for i, m in enumerate(self._get_active_tracks()):
                    if m["path"] == cp:
                        self.selected_row = i
                        break

    def _send_cmd(self, cmd: str, **kwargs):
        if self.is_remote:
            threading.Thread(target=send_ipc_command, args=(cmd,), kwargs=kwargs, daemon=True).start()
        elif self.engine:
            e = self.engine
            mapping = {
                "toggle": e.toggle_play_pause, "pause": e.pause, "next": e.next_track, "prev": e.prev_track,
                "reset_pitch": e.reset_pitch, "mute": e.toggle_mute, "shuffle": e.toggle_shuffle,
                "repeat": e.cycle_repeat, "stop": e.stop_playback,
                "record": e.toggle_recording, "toggle_record": e.toggle_recording,
                "start_record": e.start_recording, "stop_record": e.stop_recording
            }
            if cmd in mapping: mapping[cmd]()
            elif cmd == "play":
                f = kwargs.get("file")
                if f:
                    for i, t in enumerate(e.playlist):
                        if t["path"] == f: e.load_track(i, True); break
                    else:
                        e.playlist.insert(0, {"name": os.path.basename(f), "path": f, "size_mb": 0, "mtime": time.time(), "ext": os.path.splitext(f)[1][1:].upper()})
                        e.load_track(0, True)
                else: e.play()
            elif cmd == "seek": e.seek_relative(kwargs.get("seconds", 10.0))
            elif cmd == "vol_up": e.change_volume(kwargs.get("step", 5))
            elif cmd == "vol_down": e.change_volume(-kwargs.get("step", 5))
            elif cmd == "pitch_up": e.change_pitch(kwargs.get("step", 1))
            elif cmd == "pitch_down": e.change_pitch(-kwargs.get("step", 1))
            elif cmd == "set_pitch": e.set_pitch(kwargs.get("percent", 0))
            elif cmd == "select_index": e.load_track(kwargs.get("index", 0), True)
            elif cmd == "queue":
                f = kwargs.get("file") or kwargs.get("track")
                if f: e.queue_track(f)
            elif cmd == "clear_queue": e.clear_queue()
            elif cmd == "open_file_manager":
                tf = kwargs.get("file") or (e.current_track.get("path") if e.current_track else "")
                target = choose_file_manager_target(tf)
                if target:
                    open_in_file_manager(target)

    def _get_active_tracks(self) -> List[Dict[str, Any]]:
        return self.scanner.get_mixes(self.search_query)

    def _render_inspector_hud(self, st: Optional[Dict[str, Any]] = None, iw: Optional[int] = None) -> List[str]:
        if st is None: st = self._get_status()
        if iw is None:
            w, _ = _win_visible_size((80, 24))
            iw = 115 if w >= 122 else max(20, w - 6)
        tp = st.get("path", "")
        tname = st.get("title", os.path.basename(tp))
        folder = next((m.get("folder") for m in getattr(self.scanner, "mixes", []) if m.get("path") == tp and m.get("folder")), None) or self.folder_name
        is_net = tp.startswith(("\\\\", "//")) or is_cloud_or_remote_path(tp)
        folder_desc = f"{'SMB Share' if is_net else 'Local Drive'} [{folder}] • Music Library"
        smb_url = tp
        max_str_len = max(20, iw - 22)
        disp_title = (tname[:max_str_len-3] + "...") if len(tname) > max_str_len else tname
        disp_smb = (smb_url[:max_str_len-3] + "...") if len(smb_url) > max_str_len else smb_url
        ext = os.path.splitext(tp)[1][1:].upper() or "FLAC"
        sr = st.get("sample_rate", 44100)
        ch = st.get("channels", 2)
        ch_str = "Stereo" if ch == 2 else ("Mono" if ch == 1 else f"{ch} Channels")
        dev = st.get("output_device", "Default Audio Device")
        p_pct = st.get("pitch_percent", 0)

        hud = [
            f"  {BOLD}{COLOR_HOT_PURPLE}╭── ✦ TRACK AUDIO INSPECTOR (METADATA & HARDWARE HUD) ───────────────────────╮{NC}",
            f"  {BOLD}{COLOR_HOT_PURPLE}│{NC} {BOLD}{WHITE}Track Title{NC}  : {disp_title}",
            f"  {BOLD}{COLOR_HOT_PURPLE}│{NC} {BOLD}{CYAN}Folder / Src{NC} : {folder_desc}",
            f"  {BOLD}{COLOR_HOT_PURPLE}│{NC} {BOLD}{CYAN}Format/Codec{NC} : {ext} Lossless • {sr/1000:.1f} kHz • {ch_str}",
            f"  {BOLD}{COLOR_HOT_PURPLE}│{NC} {BOLD}{CYAN}Time Position{NC}: {st.get('position_fmt','00:00')} / {st.get('duration_fmt','00:00')} ({st.get('progress_pct',0):.1f}%)",
            f"  {BOLD}{COLOR_HOT_PURPLE}│{NC} {BOLD}{CYAN}Volume/Pitch{NC} : Volume: {st.get('volume', 85)}%  │  Pitch: {p_pct:+d}%",
            f"  {BOLD}{COLOR_HOT_PURPLE}│{NC} {BOLD}{CYAN}Audio Engine{NC} : Output Rate: {st.get('output_rate', 44100)/1000:.1f} kHz • Device: {dev}",
            f"  {BOLD}{COLOR_HOT_PURPLE}│{NC} {BOLD}{CYAN}{'Network Path' if is_net else 'File Path   '}{NC} : {disp_smb}",
            f"  {BOLD}{COLOR_HOT_PURPLE}╰── [G] Generate Spek • Press [I], [Esc], or [Enter] to Close ─────────────╯{NC}"
        ]
        return hud

    def _get_target_path(self) -> Tuple[Optional[str], Optional[str]]:
        mixes = self._get_active_tracks()
        if mixes and 0 <= self.selected_row < len(mixes):
            return mixes[self.selected_row].get("path"), mixes[self.selected_row].get("name")
        st = self._get_status()
        if st.get("path"): return st.get("path"), st.get("title")
        latest = self.scanner.get_latest_mix()
        return (latest["path"], latest["name"]) if latest else (None, None)

    def _generate_selected_spek(self):
        tp, tn = self._get_target_path()
        if not tp or not os.path.isfile(tp):
            self.notification_msg = "No audio track available for Spek generation."
            self.notification_time = time.time() + 3.0
            return
        existing = find_existing_spek(tp, mode=self.mode)
        if existing and os.path.isfile(existing):
            sz_kb = os.path.getsize(existing) // 1024
            self.notification_msg = f"✔ Spek exists — Opening: {os.path.basename(existing)} ({sz_kb} KB)"
            self.notification_time = time.time() + 4.0
            if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                open_image_viewer(existing)
            return
        track_name = tn or os.path.basename(tp)
        self.notification_msg = f"⚡ Generating Spek: {track_name[:30]}..."
        self.notification_time = time.time() + 60.0

        def _worker():
            ok, res = generate_track_spek(tp, mode=self.mode)
            if ok:
                sz_kb = os.path.getsize(res) // 1024
                self.notification_msg = f"✔ Spek saved: {os.path.basename(res)} ({sz_kb} KB)"
                self.notification_time = time.time() + 5.0
                if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                    open_image_viewer(res)
            else:
                self.notification_msg = f"✖ Spek failed: {res[:35]}"
                self.notification_time = time.time() + 4.0

        threading.Thread(target=_worker, daemon=True).start()

    def _open_selected_in_file_manager(self):
        st = self._get_status()
        current = st.get("path") or ""
        mixes = self._get_active_tracks()
        selected = ""
        if mixes and 0 <= self.selected_row < len(mixes):
            selected = mixes[self.selected_row].get("path") or ""
        target = choose_file_manager_target(current, selected)
        if not target:
            self.notification_msg = "No audio file to show in File Manager."
            self.notification_time = time.time() + 3.0
            return
        ok = open_in_file_manager(target)
        name = os.path.basename(target)
        self.notification_msg = f"{'Opened in' if ok else 'Failed to open'} File Manager: {name}"
        self.notification_time = time.time() + 3.0

    def _toggle_recording(self):
        if self.is_remote:
            res = send_ipc_command("toggle_record")
            is_rec = bool(res.get("recording", False))
            rec_file = str(res.get("recording_file", ""))
        elif self.engine:
            is_rec, rec_file = self.engine.toggle_recording()
        else:
            return

        self.cached_status["recording"] = is_rec
        self.cached_status["recording_file"] = rec_file
        if is_rec:
            bname = os.path.basename(rec_file)
            self.notification_msg = f"● RECORDING TO WAV STARTED: {bname} (3GB Max / File)"
        else:
            self.notification_msg = "■ RECORDING STOPPED & SAVED TO MP_AUDIOWAV_REC_OUTPUT"
        self.notification_time = time.time() + 4.0

    def _view_selected_tracklist(self):
        tp, tn = self._get_target_path()
        if not tp:
            self.notification_msg = "No mix selected to view tracklist."
            self.notification_time = time.time() + 3.0
            return
        tl = find_tracklist_for_mix(tp)
        if tl and os.path.isfile(tl):
            ok = open_tracklist_window(tl, tp)
            self.notification_msg = f"{'Opened' if ok else 'Failed to open'} Tracklist: {os.path.basename(tl)}"
        else:
            self.notification_msg = f"No tracklist found for: {tn or os.path.basename(tp)}"
        self.notification_time = time.time() + 3.5

    def _open_audio_file(self):
        chosen = choose_audio_file_gui()
        if chosen == "":
            self.notification_msg = "Open file cancelled."
            self.notification_time = time.time() + 2.5
            return
        if chosen and os.path.isfile(chosen):
            self._send_cmd("play", file=chosen)
            ext = os.path.splitext(chosen)[1].lower()
            item = {
                "name": os.path.basename(chosen),
                "path": chosen,
                "size_mb": os.path.getsize(chosen) / (1024 * 1024),
                "mtime": time.time(),
                "ext": ext[1:].upper()
            }
            if not any(m["path"] == chosen for m in self.scanner.mixes):
                self.scanner.mixes.insert(0, item)
            self.selected_row = 0
            self.notification_msg = f"Playing: {os.path.basename(chosen)}"
            self.notification_time = time.time() + 3.5
            return
        self.notification_msg = "No audio file selected. Press [F] for File Manager."
        self.notification_time = time.time() + 3.0

    def _export_playlist(self):
        mixes = self.scanner.get_mixes(self.search_query)
        if not mixes:
            self.notification_msg = "No mixes in playlist to export."
            self.notification_time = time.time() + 3.0
            return
        chosen = choose_export_m3u_gui()
        if chosen == "":
            self.notification_msg = "Export cancelled."
            self.notification_time = time.time() + 2.5
            return
        if chosen:
            ok, res = export_playlist_m3u(mixes, chosen)
            self.notification_msg = f"Exported {len(mixes)} mixes to: {os.path.basename(res)}" if ok else f"Export failed: {res}"
            self.notification_time = time.time() + 4.0
            return
        self.export_mode = True
        self.export_path = os.path.join(os.path.expanduser("~/Desktop" if os.path.isdir(os.path.expanduser("~/Desktop")) else "~"), "MP_Archive_Playlist.m3u")

    def _queue_selected(self):
        tp, tn = self._get_target_path()
        if not tp:
            self.notification_msg = "No mix selected to queue."
            self.notification_time = time.time() + 2.5
            return
        bname = tn or os.path.basename(tp)
        self._send_cmd("queue", file=tp)
        if not self.is_remote and self.engine:
            q_len = len(self.engine.play_queue)
        else:
            cur_q = list(self.cached_status.get("queue", []))
            if tp not in cur_q: cur_q.append(tp)
            self.cached_status["queue"] = cur_q
            self.cached_status["queue_len"] = len(cur_q)
            q_len = len(cur_q)
        self.notification_msg = f"✔ Queued Mix: {bname} (#{q_len} in Queue)"
        self.notification_time = time.time() + 3.5

    def run(self):
        fd = sys.stdin.fileno() if sys.stdin.isatty() else None
        old_settings = None
        if fd is not None and termios and tty:
            try:
                old_settings = termios.tcgetattr(fd)
                tty.setcbreak(fd)
                new = termios.tcgetattr(fd)
                new[1] |= termios.OPOST
                termios.tcsetattr(fd, termios.TCSADRAIN, new)
            except Exception: pass

        cstate = _win_console_begin()
        if self.ui_size_mode == "MINI":
            _setup_mini_terminal_appearance()
            sys.stdout.write("\033]0;MP Mini Audio Player\007")
        elif self.ui_size_mode == "MICRO":
            _setup_mini_terminal_appearance()
            sys.stdout.write("\033]0;MP Micro Audio Player\007")
        else:
            sys.stdout.write("\033]0;MP Audio Player\007")
        sys.stdout.write("\033[?1049h\033[?25l\033[?7l\033[2J\033[H")
        sys.stdout.flush()
        threading.Thread(target=self._input_loop, daemon=True).start()

        try:
            while self.running:
                if not self.is_remote and self.engine: self.engine.check_track_end()
                self._draw_frame()
                time.sleep(0.02)
        except (KeyboardInterrupt, SystemExit): pass
        finally:
            self.running = False
            if self.engine and not self.is_remote:
                try: self.engine.stop_recording()
                except Exception: pass
            if fd is not None and old_settings and termios:
                try: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except Exception: pass
            sys.stdout.write("\033]111\007\033[49m\033[?7h\033[?25h\033[?1049l\033]0;MP Audio Player\007")
            sys.stdout.flush()
            _win_console_end(cstate)

    def _input_loop(self):
        if not sys.stdin.isatty(): return
        if sys.platform == "win32":
            import msvcrt
            keymap = {b"H": b"\x1b[A", b"P": b"\x1b[B", b"M": b"\x1b[C", b"K": b"\x1b[D",
                      b"G": b"\x1b[H", b"O": b"\x1b[F", b"I": b"\x1b[5~", b"Q": b"\x1b[6~"}
            while self.running:
                try:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        self._process_key(keymap.get(msvcrt.getch(), b"") if ch in (b"\x00", b"\xe0") else ch)
                    else: time.sleep(0.02)
                except Exception: time.sleep(0.02)
            return

        fd = sys.stdin.fileno()
        while self.running:
            try:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r and self.running:
                    d = os.read(fd, 32)
                    if d == b"\x1b":
                        r2, _, _ = select.select([fd], [], [], 0.03)
                        if r2: d += os.read(fd, 31)
                    self._process_key(d)
            except Exception: pass

    def _process_key(self, data: bytes):
        if not data: return
        if self.export_mode:
            if data in (b"\r", b"\n"):
                self.export_mode = False
                mixes = self.scanner.get_mixes(self.search_query)
                target = self.export_path.strip() or os.path.expanduser("~/Desktop/MP_Archive_Playlist.m3u")
                ok, res = export_playlist_m3u(mixes, target)
                self.notification_msg = f"Exported {len(mixes)} mixes to: {os.path.basename(res)}" if ok else f"Export failed: {res}"
                self.notification_time = time.time() + 4.0
            elif data == b"\x1b":
                self.export_mode = False
                self.notification_msg, self.notification_time = "Export cancelled", time.time() + 2.5
            elif data in (b"\x7f", b"\x08"): self.export_path = self.export_path[:-1]
            else:
                try: self.export_path += data.decode("utf-8", "ignore")
                except Exception: pass
            return

        if self.search_mode:
            if data in (b"\r", b"\n"): self.search_mode = False
            elif data == b"\x1b": self.search_mode, self.search_query = False, ""
            elif data in (b"\x7f", b"\x08"): self.search_query, self.selected_row = self.search_query[:-1], 0
            elif data in (b"\x1b[A", b"\x1bOA"): self._navigate_list(-1)
            elif data in (b"\x1b[B", b"\x1bOB"): self._navigate_list(1)
            else:
                try:
                    c = data.decode("utf-8", "ignore")
                    if c.isprintable(): self.search_query, self.selected_row = self.search_query + c, 0
                except Exception: pass
            return

        if getattr(self, "inspector_hud_active", False):
            if data in (b"g", b"G"):
                self._generate_selected_spek()
                return
            if data in (b"\x1b", b"i", b"I", b"\r", b"\n", b"q", b"Q", b" "):
                self.inspector_hud_active = False
                return

        if data in (b"i", b"I"):
            self.inspector_hud_active = not self.inspector_hud_active
            return

        # Up / Down / Navigation keys
        if data in (b"\x1b[A", b"\x1bOA", b"k", b"K"):
            self._navigate_list(-1)
        elif data in (b"\x1b[B", b"\x1bOB", b"j", b"J"):
            self._navigate_list(1)
        elif data in (b"\x1b[5~",):
            self._navigate_list(-5)
        elif data in (b"\x1b[6~",):
            self._navigate_list(5)
        elif data in (b"\x1b[H", b"\x1b[1~", b"\x1b[7~", b"\x1bOH"):
            self.selected_row = 0
        elif data in (b"\x1b[F", b"\x1b[4~", b"\x1b[8~", b"\x1bOF"):
            filtered = self._get_active_tracks()
            if filtered: self.selected_row = len(filtered) - 1
        elif data in (b"\x1b[D", b"\x1bOD"):
            self._send_cmd("seek", seconds=-10.0)
        elif data in (b"\x1b[C", b"\x1bOC"):
            self._send_cmd("seek", seconds=10.0)
        elif data in (b"\r", b"\n"):
            mixes = self._get_active_tracks()
            if mixes and 0 <= self.selected_row < len(mixes):
                chosen = mixes[self.selected_row]
                if self.is_remote: self._send_cmd("play", file=chosen["path"])
                elif self.engine:
                    for i, t in enumerate(self.engine.playlist):
                        if t["path"] == chosen["path"]: self._send_cmd("select_index", index=i); break
                    else: self._send_cmd("play", file=chosen["path"])
        elif data == b" ": self._send_cmd("toggle")
        elif data in (b"n", b"N", b">"): self._send_cmd("next")
        elif data in (b"p", b"P", b"<"): self._send_cmd("prev")
        elif data in (b"+", b"="): self._send_cmd("pitch_up", step=1)
        elif data in (b"-", b"_"): self._send_cmd("pitch_down", step=1)
        elif data == b"0": self._send_cmd("reset_pitch")
        elif data in (b"]", b"}", b"v"):
            self._send_cmd("vol_up", step=5)
            self.cached_status["volume"] = min(100, int(self.cached_status.get("volume", 85)) + 5)
            self.cached_status["muted"] = False
        elif data in (b"[", b"{", b"V"):
            self._send_cmd("vol_down", step=5)
            self.cached_status["volume"] = max(0, int(self.cached_status.get("volume", 85)) - 5)
            self.cached_status["muted"] = False
        elif data in (b"u", b"U"):
            self._send_cmd("mute")
            is_muted = self.engine.muted if (self.engine and not self.is_remote) else not self.cached_status.get("muted", False)
            self.cached_status["muted"] = is_muted
            self.notification_msg = f"Audio: {'MUTED' if is_muted else 'UNMUTED'}"
            self.notification_time = time.time() + 2.0
        elif data in (b"s", b"S"):
            self._send_cmd("shuffle")
            shuf_on = self.engine.shuffle if (self.engine and not self.is_remote) else not self.cached_status.get("shuffle", False)
            self.cached_status["shuffle"] = shuf_on
            self.notification_msg = f"Shuffle: {'ON' if shuf_on else 'OFF'}"
            self.notification_time = time.time() + 2.5
        elif data in (b"m", b"M"):
            if self.ui_size_mode == "MINI":
                self.ui_size_mode = "MICRO"
                _setup_mini_terminal_appearance()
                sys.stdout.write("\033]0;MP Micro Audio Player\007")
                sys.stdout.flush()
            elif self.ui_size_mode == "MICRO":
                self.ui_size_mode = "MINI"
                _setup_mini_terminal_appearance()
                sys.stdout.write("\033]0;MP Mini Audio Player\007")
                sys.stdout.flush()
            else:
                p_path = getattr(self.scanner, "playlist_path", "")
                ok = launch_mini_player_window(mode=self.mode, folder_name=self.folder_name,
                                               playlist_path=p_path, theme=self.visualizer.theme,
                                               style=self.visualizer.style)
                self.notification_msg = "✦ Launched MP Mini Audio Player in new window" if ok else "Failed to open Mini Player window"
                self.notification_time = time.time() + 3.0
        elif data in (b"r", b"R"):
            self._toggle_recording()
        elif data in (b"l", b"L"):
            self._send_cmd("repeat")
            modes = ["all", "one", "off"]
            cur_rep = self.engine.repeat_mode if (self.engine and not self.is_remote) else self.cached_status.get("repeat", "all")
            next_rep = modes[(modes.index(cur_rep) + 1) % len(modes)] if cur_rep in modes else "all"
            self.cached_status["repeat"] = next_rep
            self.notification_msg = f"Repeat: {next_rep.upper()}"
            self.notification_time = time.time() + 2.5
        elif (data in (b"e", b"E") if self.ui_size_mode in ("MINI", "MICRO") else data == b"e"):
            self.visualizer.cycle_style()
            st_name = self.visualizer.get_style_display_name()
            self.notification_msg = f"Visualizer: {st_name}"
            self.notification_time = time.time() + 2.5
        elif data in (b"c", b"C"):
            self.visualizer.cycle_theme()
            th_name = self.visualizer.theme.replace("_", " ").title()
            self.notification_msg = f"Color Theme: {th_name}"
            self.notification_time = time.time() + 2.5
        elif data in (b"b", b"B"):
            self.running = False
        elif data in (b"a", b"A"):
            if self.is_remote:
                st_bt = send_ipc_command("route_bluetooth")
                b_info = st_bt.get("bluetooth", {}) if st_bt else {}
                if b_info.get("bluetooth_connected"):
                    c_str = f" ({b_info.get('bluetooth_codec')})" if b_info.get('bluetooth_codec') else ""
                    self.notification_msg = f"🎧 Bluetooth Audio Routed: {b_info.get('bluetooth_device')}{c_str}"
                else:
                    self.notification_msg = "No Bluetooth audio device connected. (Checked)"
            elif self.engine and getattr(self.engine, "bt_router", None):
                ok = self.engine.bt_router.route_to_bluetooth()
                st_bt = self.engine.bt_router.get_status()
                if st_bt.get("bluetooth_connected"):
                    c_str = f" ({st_bt.get('bluetooth_codec')})" if st_bt.get('bluetooth_codec') else ""
                    self.notification_msg = f"🎧 Bluetooth Audio Routed: {st_bt.get('bluetooth_device')}{c_str}"
                else:
                    self.notification_msg = "No Bluetooth audio device connected."
            self.notification_time = time.time() + 3.5
        elif data in (b"o", b"O"): self._open_audio_file()
        elif data in (b"t", b"T"): self._view_selected_tracklist()
        elif (data in (b"w", b"W") if self.ui_size_mode in ("MINI", "MICRO") else data in (b"E", b"w", b"W")): self._export_playlist()
        elif data == b"/": self.search_mode, self.search_query = True, ""
        elif data in (b"f", b"F"): self._open_selected_in_file_manager()
        elif data in (b"q", b"Q"): self._queue_selected()
        elif data in (b"x", b"X"): self._send_cmd("stop"); self.running = False
        elif data in (b"\x1b", b"\x03"): self.running = False

    def _navigate_list(self, delta: int):
        m = self._get_active_tracks()
        if m: self.selected_row = max(0, min(len(m) - 1, self.selected_row + delta))

    def _draw_frame(self):
        w, h = _win_visible_size((80, 24))
        w, h = max(40, w), max(5, h)
        st = self._get_status()

        if self.ui_size_mode == "MINI":
            self._draw_mini_frame(w, h, st)
            return
        if self.ui_size_mode == "MICRO":
            self._draw_micro_frame(w, h, st)
            return

        self._sync_initial_selection(st)
        lines = []

        # Check for Bluetooth connect/disconnect notification
        is_bt = bool(st.get("bluetooth_connected", False))
        bt_dev = st.get("bluetooth_device", "")
        if self._last_seen_bt_state is not None:
            if is_bt and not self._last_seen_bt_state:
                codec = st.get("bluetooth_codec", "")
                c_str = f" ({codec})" if codec else ""
                self.notification_msg = f"🎧 Auto-switched to Bluetooth: {bt_dev}{c_str}"
                self.notification_time = time.time() + 4.0
            elif not is_bt and self._last_seen_bt_state:
                self.notification_msg = "🔊 Bluetooth disconnected — Reverted to System Audio"
                self.notification_time = time.time() + 4.0
        self._last_seen_bt_state = is_bt
        self._last_seen_bt_device = bt_dev

        iw = 115 if w >= 122 else max(20, w - 6)

        if self.mode == "MUSIC":
            btitle = "✦ MP AUDIO PLAYER — MUSIC MODE (TRACKS LIBRARY) ✦"[:max(0, iw - 1)]
            bsub = f"Music Library  •  {music_library_label(self.folder_name)}  •  Local Drives & SMB Shares"[:max(0, iw - 1)]
        else:
            btitle = "✦ MP AUDIO PLAYER — DREAMWORLDS ULTRA AUDIO MODE ✦"[:max(0, iw - 1)]
            bsub = "Dreamworlds Productions  •  Hot Purple & Traffic Light Edition"[:max(0, iw - 1)]
        lines.extend([f"  {BOLD}{COLOR_HOT_PURPLE}╭{'─'*iw}╮{NC}", f"  {BOLD}{COLOR_HOT_PURPLE}│{btitle.center(iw)}│{NC}",
                      f"  {BOLD}{COLOR_LILAC}│{bsub.center(iw)}│{NC}", f"  {BOLD}{COLOR_HOT_PURPLE}╰{'─'*iw}╯{NC}"])

        tname = st.get("title", "Unknown Mix")
        maxlen = max(58, iw - 20)
        if len(tname) > maxlen: tname = tname[:maxlen - 3] + "..."
        ch_str = "Stereo" if st.get("channels", 2) == 2 else "Mono"
        sr, ext = st.get("sample_rate", 44100), os.path.splitext(st.get("path", ""))[1][1:].upper() or "FLAC"
        badge = f"{BOLD}{GREEN}▶ PLAYING{NC}" if st.get("state") == "playing" else (f"{BOLD}{YELLOW}⏸ PAUSED{NC}" if st.get("state") == "paused" else f"{BOLD}{RED}⏹ STOPPED{NC}")
        mode_badge = f" {BOLD}{COLOR_TRAFFIC_GREEN}[MUSIC MODE]{NC}" if self.mode == "MUSIC" else f" {DIM}{COLOR_HOT_PURPLE}[MIX ARCHIVE]{NC}"

        is_rec = bool(st.get("recording", False))
        flash_on = (int(time.time() * 1.5) % 2 == 0)
        rec_badge = f"  {BOLD}{COLOR_TRAFFIC_RED}● REC{NC}" if (is_rec and flash_on) else (f"  {DIM}{RED}○ REC{NC}" if is_rec else "")

        lines.append(f"  {badge}{mode_badge}{rec_badge}  {BOLD}{COLOR_NEON_PINK}♫  {tname}{NC}")

        if is_rec:
            rec_f = os.path.basename(st.get("recording_file", ""))
            rec_mb = float(st.get("recording_bytes", 0)) / (1024 * 1024)
            rec_dur = format_seconds(float(st.get("recording_duration", 0.0)))
            rec_dot_sub = f"{BOLD}{COLOR_TRAFFIC_RED}●{NC}" if flash_on else f"{DIM}{RED}○{NC}"
            lines.append(f"  {rec_dot_sub} {BOLD}{COLOR_TRAFFIC_RED}RECORDING TO WAV:{NC} {BOLD}{COLOR_ELECTRIC_CYAN}{rec_f}{NC} {DIM}[{rec_mb:.1f} MB  •  {rec_dur}  •  Max 3GB/WAV]{NC}")

        out_name = bt_dev or st.get("output_device", "Speakers")
        if is_bt or ("bluetooth" in str(out_name).lower()):
            bt_badge = f"{BOLD}{COLOR_NEON_PINK}🎧 Output: {out_name}{NC}"
        else:
            bt_badge = f"{DIM}{CYAN}🔊 Output: {out_name}{NC}"

        if w >= 106:
            lines.append(f"  {DIM}{CYAN}Format: {ext}{' Lossless' if w>=116 else ''}  │  Sample Rate: {sr/1000:.1f} kHz  │  Channels: {ch_str}  │  {bt_badge}{NC}")
        else:
            lines.append(f"  {DIM}{CYAN}Format: {ext}  │  {sr/1000:.1f} kHz  │  {bt_badge}{NC}")

        pct = float(st.get("progress_pct", 0.0))
        bw = max(20, min(54, iw - 42))
        fw = int((pct / 100.0) * bw)
        bstr = "━" * fw + "●" + "─" * max(0, bw - fw - 1)
        lines.extend([f"  {COLOR_ELECTRIC_CYAN}{st.get('position_fmt', '00:00')}{NC}  {COLOR_HOT_PURPLE}{bstr}{NC}  {COLOR_ELECTRIC_CYAN}{st.get('duration_fmt', '00:00')}{NC}  ({pct:.1f}%)",
                      self.visualizer.render_horizontal_pitch_bar(int(st.get("pitch_percent", 0)), width=bw, max_cols=max(20, w - 1)), ""])

        vis_h = 7 if h >= 34 else (5 if h >= 28 else 3)
        lines.extend(self.visualizer.render(st, width=w, height=vis_h) + [""])

        active_tracks = self._get_active_tracks()
        if self.export_mode: lines.append(f"  {BOLD}{COLOR_TRAFFIC_AMBER}Export Playlist (.m3u) Path: [{self.export_path}█]  (Enter: Save, Esc: Cancel){NC}")
        elif self.search_mode: lines.append(f"  {BOLD}{CYAN}Filter / Search: [{self.search_query}█]{NC}")
        elif self.search_query: lines.append(f"  {BOLD}Search Filter: '{self.search_query}' (Press '/' to search)")
        elif time.time() < self.notification_time and self.notification_msg: lines.append(f"  {BOLD}{COLOR_TRAFFIC_GREEN}📂 {self.notification_msg}{NC}")

        if self.inspector_hud_active:
            lines.extend(self._render_inspector_hud(st, iw))
        else:
            pal = self.visualizer.get_theme_palette()
            hl_col = pal.get("highlight", COLOR_HOT_PURPLE)
            act_col = pal.get("active", COLOR_NEON_PINK)
            b_col = f"{BOLD}{pal.get('border', COLOR_HOT_PURPLE)}"

            q_len = int(st.get("queue_len", 0))
            q_paths = list(st.get("queue", []))
            q_badge = f" • Queue: {q_len}" if q_len > 0 else ""

            box_label = f"── MUSIC LIBRARY: {music_library_label(self.folder_name)} ({len(active_tracks)} Tracks{q_badge}) " if self.mode == "MUSIC" else f"── MP MIX ARCHIVE PLAYLIST ({len(active_tracks)} Mixes Available{q_badge}) "
            lines.append(_boxed_rule("┌", box_label, "┐", iw, b_col))
            vrows = max(0, h - len(lines) - 4)
            if vrows <= 0: self.scroll_offset = max(0, self.selected_row)
            elif self.selected_row < self.scroll_offset: self.scroll_offset = self.selected_row
            elif self.selected_row >= self.scroll_offset + vrows: self.scroll_offset = self.selected_row - vrows + 1

            avail_name = max(4, iw - 23)
            if not active_tracks:
                empty_msg1 = "No audio tracks found in playlist." if self.mode == "MUSIC" else "No audio mixes found in archive. (Mix archive folders not yet configured)"
                empty_msg2 = "Option 1: add a local drive or SMB folder, then generate its playlist." if self.mode == "MUSIC" else "Press [O] to open an audio file, [F] for File Manager, or Option 14 to configure archive."
                for em in (empty_msg1, empty_msg2):
                    pad = " " * max(0, iw - _display_width(em) - 2)
                    lines.append(f"  {b_col}│{NC} {COLOR_TRAFFIC_AMBER}{em}{NC}{pad}{b_col}│{NC}")
                for _ in range(max(0, vrows - 2)):
                    lines.append(f"  {b_col}│{NC}{' ' * iw}{b_col}│{NC}")
            else:
                for i in range(self.scroll_offset, min(len(active_tracks), self.scroll_offset + vrows)):
                    m = active_tracks[i]
                    act, sel = (m["path"] == st.get("path")), (i == self.selected_row)
                    in_q = (m["path"] in q_paths)
                    raw_name = str(m.get("name", ""))
                    if _display_width(raw_name) > avail_name:
                        mn = _clip_display(raw_name, max(1, avail_name - 3)) + "..." if avail_name > 3 else _clip_display(raw_name, avail_name)
                    else:
                        mn = raw_name
                    name_pad = " " * max(0, avail_name - _display_width(mn))
                    if act:
                        pfx = f"{PLAYLIST_ACTIVE_MARK} "
                    elif in_q:
                        q_idx = q_paths.index(m["path"]) + 1
                        pfx = f"Q{q_idx}" if q_idx < 10 else "Q*"
                    else:
                        pfx = "  "
                    ext_str = f"{m.get('ext', ''):<4}"[:4]
                    if self.mode == "MUSIC":
                        dur = m.get("duration_fmt")
                        if not dur or dur == "00:00":
                            if act and st.get("duration_fmt"):
                                dur = st.get("duration_fmt")
                                m["duration_fmt"] = dur
                                self._duration_cache[m["path"]] = dur
                            elif m.get("duration_sec"):
                                dur = format_seconds(m["duration_sec"])
                                m["duration_fmt"] = dur
                                self._duration_cache[m["path"]] = dur
                            elif m.get("path") in getattr(self, "_duration_cache", {}):
                                dur = self._duration_cache[m["path"]]
                                m["duration_fmt"] = dur
                            else:
                                dur = "00:00"
                                self._request_duration(m)
                        field_str = f"{dur:>6s}"
                    else:
                        sz_str = f"{m.get('size_mb', 0):.0f}MB"
                        field_str = f"{sz_str:>6s}"

                    if len(field_str) > 6:
                        excess = len(field_str) - 6
                        name_pad = name_pad[:-excess] if len(name_pad) >= excess else ""

                    inner_plain = f" {pfx}[{i+1:4d}] {mn}{name_pad} {ext_str} {field_str} "
                    curr_w = _display_width(inner_plain)
                    if curr_w < iw:
                        inner_plain += " " * (iw - curr_w)
                    elif curr_w > iw:
                        inner_plain = _clip_display(inner_plain, iw)

                    if sel:
                        lstr = f"  {b_col}│{NC}\033[7m{BOLD}{hl_col}{inner_plain}\033[0m{b_col}│{NC}"
                    elif act:
                        lstr = f"  {b_col}│{NC}{BOLD}{act_col}{inner_plain}{NC}{b_col}│{NC}"
                    elif in_q:
                        lstr = f"  {b_col}│{NC}{BOLD}{COLOR_ELECTRIC_CYAN}{inner_plain}{NC}{b_col}│{NC}"
                    else:
                        lstr = f"  {b_col}│{NC}{inner_plain}{b_col}│{NC}"
                    lines.append(lstr)

            if self.mode == "MUSIC":
                lines.append(_boxed_rule("└", "── ↑/↓: Scroll • Enter: Play • Q: Queue • Space: Pause • G: Spek • I: Inspector • /: Search • b/Esc: Exit ", "┘", iw, b_col))
            else:
                lines.append(_boxed_rule("└", "── ↑/↓: Scroll  •  Enter: Play  •  Q: Queue  •  G: Spek  •  O: Open  •  T: Tracklist  •  E: Export  •  F: Files  •  /: Search ", "┘", iw, b_col))

        shuf = f"{COLOR_TRAFFIC_GREEN}ON{NC}" if st.get("shuffle") else f"{DIM}OFF{NC}"
        rep = f"{COLOR_TRAFFIC_GREEN}{st.get('repeat', 'all').upper()}{NC}"
        vol = f"{st.get('volume', 85)}%" if not st.get("muted") else f"{COLOR_TRAFFIC_RED}MUTED{NC}"
        pval = int(st.get("pitch_percent", 0))
        pcol = COLOR_TRAFFIC_GREEN if pval == 0 else (COLOR_TRAFFIC_AMBER if pval > 0 else COLOR_INDIGO_BLUE)
        pbadge = f"{pcol}{pval:+d}% ({1.0 + pval/100:.2f}x){NC}"

        eq_name = self.visualizer.get_style_display_name()
        th_name = self.visualizer.theme.replace("_", " ").title()

        lines.append(_fit_text_line([
            f"  🔊 Vol: {BOLD}{COLOR_ELECTRIC_CYAN}{vol}{NC}  │  🎚 Pitch: {BOLD}{pbadge}  │  🎛 EQ: {BOLD}{COLOR_NEON_PINK}{eq_name}{NC}  │  🔀 Shuf: {shuf}  │  🔁 Rep: {rep}  │  🎨 {BOLD}{COLOR_HOT_PURPLE}{th_name}{NC}",
            f"  Vol: {BOLD}{COLOR_ELECTRIC_CYAN}{vol}{NC}  │  Pitch: {BOLD}{pbadge}  │  EQ: {BOLD}{COLOR_NEON_PINK}{eq_name}{NC}  │  Shuf: {shuf}  │  Rep: {rep}",
            f"  Vol {vol}  Pitch {pbadge}  EQ {eq_name}  Shuf {shuf}  Rep {rep}"
        ], max(20, w - 1)))

        if self.mode == "MUSIC":
            lines.append(_fit_text_line([
                f"  {BOLD}{COLOR_TRAFFIC_GREEN}TRACK CONTROLS:{NC} {COLOR_ELECTRIC_CYAN}[Space] Play/Pause  [R] Record WAV  [M] Mini Mode  [Q] Queue  [G] Spek  [I] Track Inspector  [/] Search  [n/p] Skip  [+/-] Pitch  [v/V] Vol  [u] Mute  [b/Esc] Exit{NC}",
                f"  {COLOR_TRAFFIC_GREEN}CONTROLS:{NC} [Space] Play  [R] Rec WAV  [M] Mini Mode  [Q] Queue  [G] Spek  [I] Inspector  [/] Search  [n/p] Skip  [+/-] Pitch  [v/V] Vol  [u] Mute  [b/Esc] Exit",
                f"  Space Play  [R] Rec  [M] Mini  [Q] Queue  [G] Spek  [I] Inspector  [/] Search  n/p Skip  [u] Mute  b/Esc Exit"
            ], max(20, w - 1)))
            lines.append(_fit_text_line([
                f"  {DIM}[0] Pitch Reset  [u] Mute  [s] Shuffle  [l] Repeat  [e] EQ Style  [c] Color Theme  [a] Audio/BT  [O] Open  [F] Files{NC}",
                f"  {DIM}0 Reset  u Mute  s Shuf  l Rep  e EQ  c Theme  a BT  O Open  F Files{NC}",
                f"  {DIM}0 Reset  u Mute  s Shuf  l Rep  e EQ  c Theme  b/Esc Exit{NC}"
            ], max(20, w - 1)))
        else:
            lines.append(_fit_text_line([
                f"  {DIM}[Space] Play/Pause  [R] Record WAV  [M] Mini Mode  [Q] Queue  [G] Spek  [+/-] Pitch ±1% (±20% max)  [0] Pitch Reset  [v/V] Vol  [u] Mute  [s] Shuffle  [l] Repeat  [n/p] Next/Prev  [a] Audio/BT  [O] Open  [T] Tracklist  [E] Export  [F] Files  [e] EQ  [b/Esc] Exit{NC}",
                f"  {DIM}Space Play  R Rec  M Mini  Q Queue  G Spek  +/- Pitch  0 Reset  v/V Vol  u Mute  s Shuf  l Rep  n/p Skip  a BT  O Open  T List  E Export  F Files  e EQ  b/Esc Exit{NC}",
                f"  {DIM}Space Play  R Rec  M Mini  Q Queue  G Spek  +/- Pitch  v/V Vol  u Mute  s Shuf  l Rep  n/p Skip  a BT  O Open  b/Esc Exit{NC}"
            ], max(20, w - 1)))

        _present_frame(lines, w, h)

    def _draw_mini_frame(self, w: int, h: int, st: Dict[str, Any]):
        lines = []
        t_now = time.time()
        g1, g2, gbg = _get_dynamic_gradient(t_now)
        c_g1 = f"\033[38;2;{g1[0]};{g1[1]};{g1[2]}m"
        c_g2 = f"\033[38;2;{g2[0]};{g2[1]};{g2[2]}m"

        # Dynamically change terminal background color via OSC 11 for transparent consoles
        sys.stdout.write(f"\033]11;#{gbg[0]:02x}{gbg[1]:02x}{gbg[2]:02x}\007\033]0;MP Mini Audio Player\007")

        iw = max(24, min(w - 4, 74))

        # Title Box - MP Mini Audio Player
        title_text = "✦ MP MINI AUDIO PLAYER ✦"
        lines.append(f"  {BOLD}{c_g1}╭{'─'*iw}╮{NC}")
        lines.append(f"  {BOLD}{c_g1}│{c_g2}{title_text.center(iw)}{c_g1}│{NC}")
        lines.append(f"  {BOLD}{c_g1}╰{'─'*iw}╯{NC}")

        # Track name & Playback Badge
        tname = st.get("title", "Unknown Track")
        avail_title = max(18, iw - 18)
        if _display_width(tname) > avail_title:
            tname = _clip_display(tname, avail_title - 3) + "..."
        state = st.get("state", "stopped")
        badge = f"{BOLD}{GREEN}▶ PLAY{NC}" if state == "playing" else (f"{BOLD}{YELLOW}⏸ PAUSE{NC}" if state == "paused" else f"{BOLD}{RED}⏹ STOP{NC}")
        mode_badge = f"{DIM}{c_g1}[MUSIC]{NC}" if self.mode == "MUSIC" else f"{DIM}{c_g1}[MIX]{NC}"
        is_rec = bool(st.get("recording", False))
        flash_on = (int(time.time() * 1.5) % 2 == 0)
        rec_badge = f" {BOLD}{COLOR_TRAFFIC_RED}● REC{NC}" if (is_rec and flash_on) else (f" {DIM}{RED}○ REC{NC}" if is_rec else "")
        lines.append(f"  {badge} {mode_badge}{rec_badge} {BOLD}{c_g2}♫ {tname}{NC}")

        # Format & Output Device
        ext = os.path.splitext(st.get("path", ""))[1][1:].upper() or "FLAC"
        sr = st.get("sample_rate", 44100)
        ch_str = "Stereo" if st.get("channels", 2) == 2 else "Mono"
        out_dev = st.get("output_device", "Speakers")
        is_bt = bool(st.get("bluetooth_connected", False))
        dev_str = f"🎧 {out_dev}" if is_bt else f"🔊 {out_dev}"
        if _display_width(dev_str) > 22:
            dev_str = dev_str[:19] + "..."
        lines.append(f"  {DIM}{CYAN}{ext} • {sr/1000:.1f}kHz • {ch_str}  │  {dev_str}{NC}")

        # Progress bar & duration
        pct = float(st.get("progress_pct", 0.0))
        bw = max(16, min(34, iw - 30))
        fw = int((pct / 100.0) * bw)
        bstr = "━" * fw + "●" + "─" * max(0, bw - fw - 1)
        pos_str = st.get("position_fmt", "00:00")
        dur_str = st.get("duration_fmt", "00:00")
        lines.append(f"  {COLOR_ELECTRIC_CYAN}{pos_str}{NC} {c_g1}{bstr}{NC} {COLOR_ELECTRIC_CYAN}{dur_str}{NC} {DIM}({pct:.1f}%){NC}")

        # Volume & Pitch & EQ & Theme
        vol = f"{st.get('volume', 85)}%" if not st.get("muted") else f"{COLOR_TRAFFIC_RED}MUTED{NC}"
        pval = int(st.get("pitch_percent", 0))
        pbadge = f"{COLOR_TRAFFIC_GREEN}0%{NC}" if pval == 0 else f"{COLOR_TRAFFIC_AMBER}{pval:+d}%{NC}"
        eq_name = self.visualizer.get_style_display_name()
        th_name = self.visualizer.theme.replace("_", " ").title()
        lines.append(f"  🔊 {BOLD}{COLOR_ELECTRIC_CYAN}{vol}{NC} │ 🎚 {pbadge} │ 🎛 {BOLD}{c_g2}{eq_name[:16]}{NC} │ 🎨 {c_g1}{th_name[:14]}{NC}")

        # Equalizer enabled (mini mode)
        vis_h = 3 if h >= 14 else 2
        vis_lines = self.visualizer.render(st, width=iw + 4, height=vis_h)
        lines.extend(vis_lines)

        # Controls & Notifications
        if time.time() < self.notification_time and self.notification_msg:
            lines.append(f"  {BOLD}{COLOR_TRAFFIC_GREEN}📂 {self.notification_msg}{NC}")
        else:
            lines.append(f"  {c_g1}[Space]{NC} Play  {c_g1}[Q]{NC} Queue  {c_g1}[R]{NC} Rec  {c_g1}[G]{NC} Spek  {c_g1}[n/p]{NC} Skip  {c_g1}[v/V]{NC} Vol  {c_g1}[s]{NC} Shuf  {c_g1}[e]{NC} EQ  {c_g1}[c]{NC} Theme  {c_g2}[M]{NC} Micro  {c_g1}[b]{NC} Close")

        _present_frame(lines, w, h)

    def _draw_micro_frame(self, w: int, h: int, st: Dict[str, Any]):
        lines = []
        t_now = time.time()
        g1, g2, gbg = _get_dynamic_gradient(t_now)
        c_g1 = f"\033[38;2;{g1[0]};{g1[1]};{g1[2]}m"
        c_g2 = f"\033[38;2;{g2[0]};{g2[1]};{g2[2]}m"

        sys.stdout.write(f"\033]11;#{gbg[0]:02x}{gbg[1]:02x}{gbg[2]:02x}\007\033]0;MP Micro Audio Player\007")

        iw = max(24, min(w - 4, 70))
        tname = st.get("title", "Unknown Track")
        avail = max(10, iw - 43)
        if _display_width(tname) > avail:
            tname = _clip_display(tname, avail - 2) + ".."

        state = st.get("state", "stopped")
        badge = f"{BOLD}{GREEN}▶{NC}" if state == "playing" else (f"{BOLD}{YELLOW}⏸{NC}" if state == "paused" else f"{BOLD}{RED}⏹{NC}")
        pos_str = st.get("position_fmt", "00:00")
        dur_str = st.get("duration_fmt", "00:00")
        vol = f"{st.get('volume', 85)}%"
        pval = int(st.get("pitch_percent", 0))
        pbadge = f"{pval:+d}%" if pval != 0 else "0%"

        # Dynamic micro-meter responding to active EQ style
        cur_style = self.visualizer.style
        levels = np.array(st.get("levels", [0.0] * 24))
        if cur_style == "oscilloscope":
            wave_chars = ["─", "∿", "~", "≈", "∽", "∿"]
            meter_bars = []
            for i in range(14):
                val = levels[i % len(levels)] if len(levels) else 0.0
                wave_val = math.sin(i * 0.7 + t_now * 8.0) * val
                idx = max(0, min(len(wave_chars) - 1, int(abs(wave_val) * (len(wave_chars) - 1))))
                meter_bars.append(f"{c_g2}{wave_chars[idx] if val > 0.05 else '─'}{NC}")
            meter_str = "".join(meter_bars)
        elif cur_style == "analog_vu":
            ll = np.mean(st.get("levels_left", levels)) if len(levels) else 0.0
            lr = np.mean(st.get("levels_right", levels)) if len(levels) else 0.0
            l_bar = int(min(5, round(ll * 5)))
            r_bar = int(min(5, round(lr * 5)))
            meter_str = f"{c_g1}L{NC}{c_g2}{'█'*l_bar}{DIM}{'░'*(5-l_bar)}{NC} {c_g1}R{NC}{c_g2}{'█'*r_bar}{DIM}{'░'*(5-r_bar)}{NC}"
        elif cur_style == "stardust_particles_eq":
            dust_chars = [console_symbol(ch) for ch in (" ", "·", "˙", ":", "⋆", "✦", "◆", "█")]
            meter_bars = []
            for i, val in enumerate(levels[:14]):
                idx = min(len(dust_chars) - 1, int(val * len(dust_chars)))
                meter_bars.append(f"{c_g2}{dust_chars[idx]}{NC}")
            meter_str = "".join(meter_bars)
        elif cur_style == "neon_prism_eq":
            meter_bars = []
            for i, val in enumerate(levels[:14]):
                idx = min(8, int(val * 9))
                col = self.visualizer._get_neon_prism_color(i / 13.0, val)
                meter_bars.append(f"{col}{prism_level_glyph(idx)}{NC}")
            meter_str = "".join(meter_bars)
        else:
            meter_bars = []
            for val in levels[:14]:
                idx = min(8, int(val * 9))
                meter_bars.append(f"{c_g2}{prism_level_glyph(idx)}{NC}")
            meter_str = "".join(meter_bars)

        eq_name = self.visualizer.get_style_display_name()
        th_name = self.visualizer.theme.replace("_", " ").title()

        is_rec = bool(st.get("recording", False))
        flash_on = (int(time.time() * 1.5) % 2 == 0)
        rec_dot = f" {BOLD}{COLOR_TRAFFIC_RED}●{NC}" if (is_rec and flash_on) else (f" {DIM}{RED}○{NC}" if is_rec else "")

        rem_dash = max(0, iw - 28)
        lines.append(f"  {BOLD}{c_g1}╭─ ✦ MP MICRO AUDIO PLAYER ✦ {'─' * rem_dash}╮{NC}")
        row1_inner = f" {badge}{rec_dot} {BOLD}{c_g2}{tname}{NC} │ {COLOR_ELECTRIC_CYAN}{pos_str}/{dur_str}{NC} │ Vol: {vol} │ {c_g1}Pitch: {pbadge}{NC} "
        row1_pad = max(0, iw - _display_width(row1_inner))
        lines.append(f"  {BOLD}{c_g1}│{NC}{row1_inner}{' ' * row1_pad}{BOLD}{c_g1}│{NC}")

        row2_inner = f" 🎛 [{meter_str}] │ EQ: {BOLD}{c_g2}{eq_name[:14]}{NC} │ 🎨 {c_g1}{th_name[:10]}{NC} │ {c_g2}[M] Mini{NC} "
        row2_pad = max(0, iw - _display_width(row2_inner))
        lines.append(f"  {BOLD}{c_g1}│{NC}{row2_inner}{' ' * row2_pad}{BOLD}{c_g1}│{NC}")
        lines.append(f"  {BOLD}{c_g1}╰{'─' * iw}╯{NC}")

        # Equalizer display in micro mode
        if h >= 9:
            vis_h = 2 if h >= 12 else 1
            vis_lines = self.visualizer.render(st, width=iw + 4, height=vis_h)
            lines.extend(vis_lines)

        if time.time() < self.notification_time and self.notification_msg:
            lines.append(f"  {BOLD}{COLOR_TRAFFIC_GREEN}📂 {self.notification_msg}{NC}")
        else:
            lines.append(_fit_text_line([
                f"  {c_g1}[Space]{NC} Play  {c_g1}[Q]{NC} Que  {c_g1}[R]{NC} Rec  {c_g1}[G]{NC} Spek  {c_g1}[n/p]{NC} Skip  {c_g1}[v/V]{NC} Vol  {c_g1}[s]{NC} Shuf  {c_g1}[e]{NC} EQ  {c_g1}[c]{NC} Theme  {c_g2}[M]{NC} Mini  {c_g1}[b]{NC} Close",
                f"  {c_g1}[Space]{NC} Play  {c_g1}[Q]{NC} Que  {c_g1}[R]{NC} Rec  {c_g1}[n/p]{NC} Skip  {c_g1}[v/V]{NC} Vol  {c_g1}[s]{NC} Shuf  {c_g1}[e]{NC} EQ  {c_g1}[c]{NC} Theme  {c_g2}[M]{NC} Mini  {c_g1}[b]{NC} Close",
                f"  {c_g1}Space{NC} Play  {c_g1}Q{NC} Que  {c_g1}R{NC} Rec  {c_g1}n/p{NC} Skip  {c_g1}v/V{NC} Vol  {c_g1}s{NC} Shuf  {c_g1}e{NC} EQ  {c_g1}c{NC} Theme  {c_g2}M{NC} Mini  {c_g1}b{NC} Close"
            ], max(20, w - 1)))

        _present_frame(lines, w, h)

def _spawn_player_daemon(file_path: Optional[str] = None, auto_bluetooth: bool = True,
                         mode: str = "MIX_ARCHIVE", music_folder: Optional[str] = None,
                         playlist_path: Optional[str] = None) -> Optional[int]:
    if not is_player_daemon_running():
        _cleanup_stale_daemon_files()

    cmd = [sys.executable, str(Path(__file__).resolve()), "--daemon"]
    if not auto_bluetooth: cmd.append("--no-bluetooth-auto")
    if mode == "MUSIC":
        cmd.append("--music-mode")
        if music_folder:
            cmd.extend(["--music-folder", str(music_folder)])
        if playlist_path:
            cmd.extend(["--playlist", str(playlist_path)])
    if file_path:
        norm_p = os.path.abspath(file_path) if os.path.exists(file_path) else str(file_path)
        cmd.append(norm_p)
    repo_base = str(get_base_dir())
    try:
        proc = subprocess.Popen(cmd,
                                cwd=repo_base,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        try: PID_FILE.write_text(str(proc.pid))
        except OSError: pass
        return proc.pid
    except Exception as exc:
        try: mp_log_error("MP_Audio_Player", f"Failed spawning player daemon: {exc}", exc)
        except Exception: pass
        return None

def _install_windows_console_close():
    if sys.platform != "win32": return
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    ht = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
    cb = ht(lambda c: (os._exit(0) if c in (2, 5, 6) else 0))
    k.SetConsoleCtrlHandler(cb, 1)

def main():
    parser = argparse.ArgumentParser(description=f"MP Audio Player (MP Mix Manager v{VERSION}) - High Resolution Playback & Custom Animated Equalizer")
    parser.add_argument("--version", "-v", action="version", version=f"MP Audio Player (MP Mix Manager v{VERSION})")
    parser.add_argument("file", nargs="?", help="Audio file path to play immediately")
    parser.add_argument("--daemon", action="store_true", help="Run as headless background audio daemon")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive TUI player")
    parser.add_argument("--play", nargs="?", const="", help="Play / resume audio")
    parser.add_argument("--pause", action="store_true", help="Pause playback")
    parser.add_argument("--toggle", action="store_true", help="Toggle play/pause")
    parser.add_argument("--stop", action="store_true", help="Stop playback")
    parser.add_argument("--next", action="store_true", help="Skip to next track")
    parser.add_argument("--prev", action="store_true", help="Skip to previous track")
    parser.add_argument("--pitch", type=int, help="Set DJ pitch percentage (-20 to +20)")
    parser.add_argument("--pitch-up", type=int, nargs="?", const=1, help="Increase DJ pitch percentage (default: +1%%)")
    parser.add_argument("--pitch-down", type=int, nargs="?", const=1, help="Decrease DJ pitch percentage (default: -1%%)")
    parser.add_argument("--pitch-reset", action="store_true", help="Reset DJ pitch percentage to 0%%")
    parser.add_argument("--vol", type=str, help="Set volume (e.g. 85, +5, -5)")
    parser.add_argument("--seek", type=float, help="Seek relative seconds")
    parser.add_argument("--status", action="store_true", help="Output JSON playback status")
    parser.add_argument("--status-line", action="store_true", help="Output single-line formatted status")
    parser.add_argument("--play-latest", action="store_true", help="Play the newest mix from archive")
    parser.add_argument("--get-latest-mix", action="store_true", help="Print path of newest mix in archive")
    parser.add_argument("--list-mixes", action="store_true", help="Print all available mixes in archive")
    parser.add_argument("--open-file-manager", "-f", action="store_true", help="Open mix or archive in file manager")
    parser.add_argument("--tracklist", "-t", action="store_true", help="Open tracklist for mix")
    parser.add_argument("--export-playlist", "-e", nargs="?", const="default", help="Export playlist to .m3u")
    parser.add_argument("--style", "--eq", type=str, choices=EqualizerVisualizer.STYLES, help="Set equalizer visualizer style")
    parser.add_argument("--theme", type=str, choices=EqualizerVisualizer.THEMES, help="Set color theme")
    parser.add_argument("--cmd", type=str, help="Send arbitrary IPC command")
    parser.add_argument("--music-mode", action="store_true", help="Launch in DJ Tracks MUSIC Mode")
    parser.add_argument("--music-folder", type=str, default="ALL", help="Configured music folder id, or ALL")
    parser.add_argument("--playlist", type=str, default="", help="Path to pre-generated playlist (.json or .m3u8)")
    parser.add_argument("--no-bluetooth-auto", action="store_true", help="Disable automatic Bluetooth audio routing")
    parser.add_argument("--bluetooth-status", action="store_true", help="Print current Bluetooth audio router status")
    parser.add_argument("--bluetooth-route", action="store_true", help="Route active audio to connected Bluetooth headphones")
    parser.add_argument("--mini", action="store_true", help="Launch in compact MP Mini Audio Player mode")
    parser.add_argument("--micro", action="store_true", help="Launch in ultra-compact MP Micro Audio Player mode")
    parser.add_argument("--spek", "--generate-spek", "-g", action="store_true", help="Generate 1080p spectrogram (Spek) for active or target audio track/mix and store locally")
    parser.add_argument("--new-window", "--window", "-w", action="store_true", help="Launch interactive MP Audio Player in a new dedicated window")
    parser.add_argument("--only-if-running", action="store_true", help="Only perform toggle/action if player daemon is currently running")
    parser.add_argument("--shuffle", action="store_true", help="Toggle shuffle mode (on/off)")
    parser.add_argument("--repeat", action="store_true", help="Cycle repeat mode (all -> one -> off)")
    parser.add_argument("--queue", "-q", type=str, nargs="?", const="", help="Queue audio file or mix to play next")
    parser.add_argument("--clear-queue", action="store_true", help="Clear playback queue")
    parser.add_argument("--record", "--toggle-record", "-r", action="store_true", help="Toggle live WAV recording to MP_AUDIOWAV_REC_OUTPUT (max 3GB per WAV)")

    args, _ = parser.parse_known_args()
    base_dir = get_base_dir()
    is_music = bool(args.music_mode or args.playlist or (args.music_folder and args.music_folder != "ALL"))
    current_mode = "MUSIC" if is_music else "MIX_ARCHIVE"
    folder_target = args.music_folder if is_music else "ALL"

    if args.get_latest_mix:
        latest = MixArchiveScanner(base_dir).get_latest_mix()
        if latest: print(latest["path"]); sys.exit(0)
        sys.exit(1)

    if args.list_mixes:
        scanner = MusicFolderPlaylistScanner(folder_target, playlist_path=args.playlist) if is_music else MixArchiveScanner(base_dir)
        for m in scanner.get_mixes():
            if is_music:
                dur = m.get("duration_fmt", "00:00")
                print(f"{m['path']}\t{dur}\t{m['name']}")
            else:
                print(f"{m['path']}\t{m['size_mb']:.1f}MB\t{m['name']}")
        sys.exit(0)

    daemon_running = is_player_daemon_running()

    if args.bluetooth_status:
        if daemon_running:
            res = send_ipc_command("bluetooth_status")
            print(json.dumps(res.get("bluetooth", {}) if res else {}, indent=2))
        elif get_bluetooth_audio_status:
            print(json.dumps(get_bluetooth_audio_status(), indent=2))
        else:
            print(json.dumps({"bluetooth_connected": False, "error": "Router unavailable"}, indent=2))
        sys.exit(0)

    if args.bluetooth_route:
        if daemon_running:
            res = send_ipc_command("route_bluetooth")
            ok = bool(res and res.get("routed"))
            print("✔ Sent route command to player daemon:" if ok else "✖ Failed to route to Bluetooth:")
            print(json.dumps(res or {}, indent=2))
        elif BluetoothAudioRouter:
            r = BluetoothAudioRouter()
            ok = r.route_to_bluetooth()
            print("✔ Routed system audio to Bluetooth" if ok else "✖ Failed to route to Bluetooth")
        sys.exit(0)

    if args.open_file_manager or args.tracklist:
        tp = None
        if daemon_running:
            st = send_ipc_command("status")
            if st and "data" in st and st["data"].get("path"): tp = st["data"]["path"]
        if not tp or not os.path.exists(tp):
            latest = MixArchiveScanner(base_dir).get_latest_mix()
            if latest: tp = latest["path"]
        if args.open_file_manager:
            target = choose_file_manager_target(tp)
            ok = bool(target) and open_in_file_manager(target)
            print(f"✔ Opened in file manager: {target}" if ok else "✖ Failed to open file manager")
            sys.exit(0 if ok else 1)
        else:
            tl = find_tracklist_for_mix(tp) if tp else None
            if tl and os.path.isfile(tl) and open_tracklist_window(tl, tp):
                print(f"✔ Opened tracklist: {tl}"); sys.exit(0)
            print("✖ Tracklist not found" if tp else "✖ No mix available", file=sys.stderr)
            sys.exit(1)

    if args.export_playlist is not None:
        mixes = MixArchiveScanner(base_dir).get_mixes()
        dest = os.path.expanduser("~/Desktop/MP_Archive_Playlist.m3u") if (args.export_playlist in ("default", "") or not args.export_playlist) else args.export_playlist
        ok, res = export_playlist_m3u(mixes, dest)
        print(f"✔ Exported {len(mixes)} mixes to .m3u playlist: {res}" if ok else f"✖ Failed to export playlist: {res}")
        sys.exit(0 if ok else 1)

    if args.spek:
        tp = None
        if args.file and os.path.exists(args.file):
            tp = os.path.abspath(args.file)
        elif daemon_running:
            st = send_ipc_command("status")
            if st and "data" in st and st["data"].get("path"):
                tp = st["data"]["path"]
        if not tp:
            if is_music:
                scanner = MusicFolderPlaylistScanner(folder_target, playlist_path=args.playlist)
                mixes = scanner.get_mixes()
                if mixes: tp = mixes[0]["path"]
            else:
                latest = MixArchiveScanner(base_dir).get_latest_mix()
                if latest: tp = latest["path"]
        if not tp or not os.path.isfile(tp):
            print("✖ No audio file available for Spek generation", file=sys.stderr)
            sys.exit(1)
        existing = find_existing_spek(tp, mode=current_mode)
        if existing and os.path.isfile(existing):
            sz_kb = os.path.getsize(existing) // 1024
            print(f"✔ Spek already exists ({sz_kb} KB): {existing}")
            if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                open_image_viewer(existing)
            sys.exit(0)
        print(f"⚡ Generating Spek spectrogram for: {os.path.basename(tp)}...")
        ok, res = generate_track_spek(tp, mode=current_mode)
        if ok:
            sz_kb = os.path.getsize(res) // 1024
            print(f"✔ Spek generated successfully ({sz_kb} KB): {res}")
            if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                open_image_viewer(res)
            sys.exit(0)
        else:
            print(f"✖ Spek generation failed: {res}", file=sys.stderr)
            sys.exit(1)

    if args.new_window:
        ok = launch_player_window(mode=current_mode, folder_name=folder_target, playlist_path=args.playlist,
                                  theme=args.theme, style=args.style)
        sys.exit(0 if ok else 1)

    if args.cmd:
        res = send_ipc_command(args.cmd)
        if res: print(json.dumps(res)); sys.exit(0)
        sys.exit(1)

    if args.play_latest:
        latest = MixArchiveScanner(base_dir).get_latest_mix()
        if latest:
            res = send_ipc_command("play", file=latest["path"]) if daemon_running else None
            if not res:
                _spawn_player_daemon(latest["path"], auto_bluetooth=(not args.no_bluetooth_auto), mode=current_mode)
            sys.exit(0)
        sys.exit(1)

    if args.toggle:
        if daemon_running:
            res = send_ipc_command("toggle")
            if res: sys.exit(0)
        if args.only_if_running: sys.exit(0)
        latest = MixArchiveScanner(base_dir).get_latest_mix()
        if latest: _spawn_player_daemon(latest["path"], auto_bluetooth=(not args.no_bluetooth_auto), mode=current_mode)
        sys.exit(0)

    if args.pause or args.stop or args.next or args.prev:
        cmd = "pause" if args.pause else ("stop" if args.stop else ("next" if args.next else "prev"))
        if daemon_running: send_ipc_command(cmd)
        sys.exit(0)

    if args.shuffle:
        if daemon_running:
            res = send_ipc_command("shuffle")
            st_shuf = res.get("shuffle") if res else None
            if st_shuf is not None: print(f"✔ Shuffle mode: {'ON' if st_shuf else 'OFF'}")
            else: print("✔ Shuffle toggled")
        sys.exit(0)

    if args.repeat:
        if daemon_running:
            res = send_ipc_command("repeat")
            st_rep = res.get("repeat") if res else None
            if st_rep is not None: print(f"✔ Repeat mode: {st_rep.upper()}")
            else: print("✔ Repeat mode cycled")
        sys.exit(0)

    if args.record:
        if daemon_running:
            res = send_ipc_command("toggle_record")
            rec_on = res.get("recording", False) if res else False
            rec_file = res.get("recording_file", "") if res else ""
            if rec_on:
                print(f"✔ Live WAV Recording Started: {rec_file} (Max 3GB per WAV)")
            else:
                print("✔ Live WAV Recording Stopped & Saved to MP_AUDIOWAV_REC_OUTPUT")
        else:
            print("Player daemon not running.")
        sys.exit(0)

    if args.play is not None:
        ftp = os.path.abspath(args.play or (args.file or "")) if (args.play or args.file) else ""
        res = send_ipc_command("play", file=ftp or None) if daemon_running else None
        if not res:
            if not ftp:
                l = MixArchiveScanner(base_dir).get_latest_mix()
                ftp = l["path"] if l else ""
            if ftp:
                _spawn_player_daemon(ftp, auto_bluetooth=(not args.no_bluetooth_auto), mode=current_mode)
        sys.exit(0)

    if args.clear_queue:
        if daemon_running:
            res = send_ipc_command("clear_queue")
            cleared = res.get("cleared", 0) if res else 0
            print(f"✔ Cleared {cleared} mix(es) from playback queue.")
        else:
            print("Player daemon not running.")
        sys.exit(0)

    if args.queue is not None:
        q_target = os.path.abspath(args.queue or (args.file or "")) if (args.queue or args.file) else ""
        if not q_target:
            latest = MixArchiveScanner(base_dir).get_latest_mix()
            if latest: q_target = latest["path"]
        if q_target and os.path.exists(q_target):
            res = send_ipc_command("queue", file=q_target) if daemon_running else None
            if res:
                q_len = res.get("queue_len", "?")
                print(f"✔ Queued track (#{q_len} in queue): {os.path.basename(q_target)}")
            else:
                _spawn_player_daemon(q_target, auto_bluetooth=(not args.no_bluetooth_auto), mode=current_mode)
                print(f"✔ Started player daemon with mix: {os.path.basename(q_target)}")
            sys.exit(0)
        else:
            print(f"✖ File not found to queue: {q_target}", file=sys.stderr)
            sys.exit(1)

    if args.pitch is not None or args.pitch_up is not None or args.pitch_down is not None or args.pitch_reset:
        if daemon_running:
            if args.pitch is not None: send_ipc_command("set_pitch", percent=args.pitch)
            elif args.pitch_up is not None: send_ipc_command("pitch_up", step=args.pitch_up)
            elif args.pitch_down is not None: send_ipc_command("pitch_down", step=args.pitch_down)
            else: send_ipc_command("reset_pitch")
        sys.exit(0)

    if args.vol:
        if daemon_running:
            v = args.vol
            if v.startswith(("+", "-")): send_ipc_command("vol_up" if v[0] == "+" else "vol_down", step=abs(int(v)))
            else: send_ipc_command("set_volume", volume=int(v))
        sys.exit(0)

    if args.seek is not None:
        if daemon_running: send_ipc_command("seek", seconds=args.seek)
        sys.exit(0)

    if args.status or args.status_line:
        st = send_ipc_command("status") if daemon_running else None
        data = st.get("data") if st else None
        if args.status:
            print(json.dumps(data if data else {"running": False, "state": "stopped"}, indent=2))
        else:
            if data:
                icon = "▶" if data["state"] == "playing" else "⏸"
                pval = data.get("pitch_percent", 0)
                pstr = f"Pitch: {pval:+d}%" if pval != 0 else "Pitch: 0%"
                print(f"{icon} {data['title']} [{data['position_fmt']}/{data['duration_fmt']}] ({data['mini_eq']}) {pstr} Vol: {data['volume']}%")
            else: print("○ MP Audio Player: Stopped")
        sys.exit(0)

    if args.interactive or args.mini or args.micro or (not args.daemon and sys.stdin.isatty()):
        if is_music:
            scanner = MusicFolderPlaylistScanner(folder_name=folder_target, playlist_path=args.playlist)
        else:
            scanner = MixArchiveScanner(base_dir)
        mixes = scanner.get_mixes()

        tf = os.path.abspath(args.file) if args.file else None
        if daemon_running:
            st = send_ipc_command("status")
            if not st:
                daemon_running = False

        if not daemon_running:
            latest = scanner.get_latest_mix() if not is_music else (mixes[0] if mixes else None)
            init_file = tf or (latest["path"] if latest else (mixes[0]["path"] if mixes else None))
            _spawn_player_daemon(init_file, auto_bluetooth=(not args.no_bluetooth_auto),
                                 mode=current_mode, music_folder=folder_target, playlist_path=args.playlist)
            for _ in range(75):
                time.sleep(0.04)
                if (SOCKET_PATH.exists() or PORT_FILE.exists()) and is_player_daemon_running():
                    break
        else:
            if is_music:
                send_ipc_command("load_playlist", mode="MUSIC", folder_name=folder_target, playlist_path=args.playlist, play=True)
            if tf:
                send_ipc_command("play", file=tf)

        ui_mode = "MICRO" if getattr(args, "micro", False) else ("MINI" if getattr(args, "mini", False) else "NORMAL")
        TerminalPlayerUI(None, scanner, is_remote=True, default_style=args.style, default_theme=args.theme,
                         mode=current_mode, folder_name=folder_target, ui_size_mode=ui_mode).run()
        sys.exit(0)

    if args.daemon:
        try: PID_FILE.write_text(str(os.getpid()))
        except OSError: pass
        _install_windows_console_close()
        def _daemon_sig_handler(signum, frame):
            raise SystemExit(0)
        try:
            signal.signal(signal.SIGTERM, _daemon_sig_handler)
            signal.signal(signal.SIGINT, _daemon_sig_handler)
            if hasattr(signal, "SIGHUP"):
                signal.signal(signal.SIGHUP, _daemon_sig_handler)
        except Exception:
            pass

    if is_music:
        scanner = MusicFolderPlaylistScanner(folder_name=folder_target, playlist_path=args.playlist)
    else:
        scanner = MixArchiveScanner(base_dir)
    mixes = scanner.get_mixes()
    init_idx = 0
    if args.file:
        tp = os.path.abspath(args.file)
        for i, m in enumerate(mixes):
            if m["path"] == tp: init_idx = i; break
        else:
            if os.path.isfile(tp):
                mixes.insert(0, {"name": os.path.basename(tp), "path": tp, "size_mb": os.path.getsize(tp)/(1024*1024),
                                 "mtime": time.time(), "ext": os.path.splitext(tp)[1][1:].upper()})
                init_idx = 0

    engine = AudioEngine(mixes, auto_bluetooth=(not args.no_bluetooth_auto), mode=current_mode)
    PlayerIPCServer(engine).start()
    if mixes:
        engine.load_track(init_idx, True)

    try:
        while True:
            if engine.state == "playing": engine._ensure_stream()
            engine.check_track_end()
            time.sleep(0.5)
    except (KeyboardInterrupt, SystemExit): pass
    finally:
        engine.stop_playback()
        for p in (STATE_FILE, PID_FILE, SOCKET_PATH, PORT_FILE):
            try:
                if p == STATE_FILE: p.write_text(json.dumps({"running": False, "state": "stopped"}), encoding="utf-8")
                elif p.exists(): p.unlink()
            except OSError: pass
        sys.exit(0)

if __name__ == "__main__":
    main()