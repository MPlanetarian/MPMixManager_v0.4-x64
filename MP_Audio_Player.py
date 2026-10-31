#!/usr/bin/env python3
from __future__ import annotations
import os, re, sys, time, datetime, math, random, json, socket, select, shutil, argparse, threading, subprocess, unicodedata, queue, collections, signal, functools, colorsys, re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try: _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass

def _get_app_version() -> str:
    if v := os.environ.get("VERSION"): return v.strip()
    s_dir = Path(__file__).resolve().parent
    for c in (s_dir / "VERSION", s_dir.parent / "VERSION"):
        if c.is_file():
            try: return c.read_text(encoding="utf-8").strip()
            except Exception: pass
    return "0.4.0 Stable"

VERSION = _get_app_version()

try:
    from mp_activity_tracker import record_activity
    from mp_logging import log_error as mp_log_error
except ImportError:
    try:
        from scripts.mp_activity_tracker import record_activity
        from scripts.mp_logging import log_error as mp_log_error
    except ImportError:
        def record_activity(*a, **k): pass
        def mp_log_error(*a, **k): pass

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

try: import termios, tty
except ImportError: termios = tty = None

BOLD, DIM, ITALIC, NC = "\033[1m", "\033[2m", "\033[3m", "\033[0m"
COLOR_HOT_PURPLE, COLOR_INDIGO_BLUE, COLOR_LILAC = "\033[38;2;166;77;255m", "\033[38;2;102;102;255m", "\033[38;2;153;153;255m"
COLOR_TRAFFIC_GREEN, COLOR_TRAFFIC_AMBER, COLOR_TRAFFIC_RED = "\033[38;2;0;255;0m", "\033[38;2;255;153;51m", "\033[38;2;255;0;0m"
COLOR_MAIN_FG, COLOR_NEON_PINK, COLOR_ELECTRIC_CYAN, WHITE = "\033[38;2;209;209;224m", "\033[38;2;247;37;133m", "\033[38;2;0;229;255m", "\033[1;38;2;255;255;255m"
RED, GREEN, YELLOW, MAGENTA, CYAN = COLOR_TRAFFIC_RED, COLOR_TRAFFIC_GREEN, COLOR_TRAFFIC_AMBER, COLOR_HOT_PURPLE, COLOR_LILAC

CONFIG_DIR = Path.home() / ".config" / "mix-manager"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SOCKET_PATH, PORT_FILE = CONFIG_DIR / "mp_audio_player.sock", CONFIG_DIR / "mp_audio_player.port"
STATE_FILE, PID_FILE, DURATION_CACHE_FILE = CONFIG_DIR / "mp_player_state.json", CONFIG_DIR / "mp_player.pid", CONFIG_DIR / "track_durations.json"
DAEMON_LOCK_FILE = CONFIG_DIR / "mp_player.lock"
RESUME_STATE_FILE = CONFIG_DIR / "playback_resume.json"
_DAEMON_LOCK_FH = None

AUDIO_EXTENSIONS = ('.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac', '.aiff', '.wma')
UNICODE_BLOCKS = [' ', ' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
_PRISM_LEVELS_FULL = (" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")
_PRISM_LEVELS_LIMITED = (" ", "▄", "▄", "▄", "▄", "█", "█", "█", "█")
PLAYLIST_ACTIVE_MARK = "\u25ba"
REC_MAX_FILE_BYTES = 3 * 1024 * 1024 * 1024

_LIMITED_GLYPHS = os.name == "nt" or sys.platform in ("win32", "cygwin") or bool(os.environ.get("MSYSTEM"))
def _use_limited_console_glyphs() -> bool: return _LIMITED_GLYPHS
def prism_level_glyph(eighth: int) -> str: return (_PRISM_LEVELS_LIMITED if _use_limited_console_glyphs() else _PRISM_LEVELS_FULL)[max(0, min(8, int(eighth)))]
def prism_peak_glyph(hot: bool, column: int = 0) -> str:
    return ("\u25b2" if hot else "\u2500") if _use_limited_console_glyphs() else (("\u2726" if column % 2 == 0 else "\u25c6") if hot else "\u2501")
def meter_peak_glyph() -> str: return "\u2500" if _use_limited_console_glyphs() else "\u2594"
def meter_level_char(frac: float, peak_here: bool) -> str:
    return "█" if frac >= 1.0 else (prism_level_glyph(max(1, min(8, int(frac * 8)))) if frac > 0.0 else (meter_peak_glyph() if peak_here else " "))

_STARDUST_SAFE = {"✦": "•", "✧": "°", "⋆": "·", "◆": "•", "╵": "│", "▔": "─", "⠄": "·", "⠂": ".", "⠁": ".", "⠈": "'", "⡀": ".", "≈": "~", "≋": "~", "∿": "~", "∽": "~", "›": ">", "»": ">"}
def console_symbol(ch: str) -> str: return _STARDUST_SAFE.get(ch, ch) if _use_limited_console_glyphs() else ch

# Precomputed high-efficiency rainbow color tables for Stream of Frequency visualizer (360 degrees of hue)
_RAINBOW_RGB_TABLE = tuple(tuple(int(c * 255) for c in colorsys.hsv_to_rgb(deg / 360.0, 1.0, 1.0)) for deg in range(360))
_RAINBOW_ANSI_BOLD = tuple(f"\033[1;38;2;{r};{g};{b}m" for r, g, b in _RAINBOW_RGB_TABLE)
_RAINBOW_ANSI_NORMAL = tuple(f"\033[38;2;{r};{g};{b}m" for r, g, b in _RAINBOW_RGB_TABLE)
_RAINBOW_ANSI_DIM = tuple(f"\033[38;2;{r//2};{g//2};{b//2}m" for r, g, b in _RAINBOW_RGB_TABLE)
_RAINBOW_ANSI_FAINT = tuple(f"\033[38;2;{max(20, int(r*0.35))};{max(20, int(g*0.35))};{max(20, int(b*0.35))}m" for r, g, b in _RAINBOW_RGB_TABLE)

_DUST_CHOICES_LIM = {"hot": ["•", "°", "·", "˙", "+"], "mid": ["•", "°", "·", "˙", ".", "*"], "low": ["·", "˙", ".", "*", "'", ","]}
_DUST_CHOICES_FULL = {"hot": ["✦", "✧", "⋆", "•", "°"], "mid": ["•", "°", "·", "˙", "⠄", "⠂"], "low": ["·", "˙", "⠄", "⠂", "⠁", "⠈", "⡀"]}
def stardust_dust_choices(tier: str) -> List[str]: return (_DUST_CHOICES_LIM if _use_limited_console_glyphs() else _DUST_CHOICES_FULL)[tier]

def music_library_label(folder_name: str) -> str:
    n = str(folder_name or "ALL").strip() or "ALL"
    return "All Music Folders" if n.upper() in ("ALL", "ALL_MUSIC_FOLDERS") else n

def is_cloud_or_remote_path(p: Union[str, Path, None]) -> bool:
    if not p: return False
    s = str(p)
    return s.startswith(("\\\\", "//", "smb://")) or any(k in s for k in ("GoogleDrive", "google3:", "MUSIC_SMB", "/run/media/", "/mnt/", "/media/", "/gvfs/smb-share:"))

@functools.lru_cache(maxsize=1)
def get_base_dir() -> Path:
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "scripts" else p.parent

try:
    _sd_dir = str(get_base_dir() / "scripts")
    if _sd_dir not in sys.path: sys.path.insert(0, _sd_dir)
    from monitor_bluetooth_audio import BluetoothAudioRouter, get_bluetooth_audio_status
except Exception:
    BluetoothAudioRouter = get_bluetooth_audio_status = None

def parse_env_file(filepath: Path) -> Dict[str, str]:
    env = {}
    if filepath.is_file():
        try:
            for l in filepath.read_text(encoding="utf-8", errors="ignore").splitlines():
                l = l.strip()
                if l and not l.startswith("#") and "=" in l:
                    k, v = l.split("=", 1)
                    env[k.strip()] = v.strip().strip('"\'')
        except Exception: pass
    return env

def format_seconds(seconds: float) -> str:
    if seconds < 0 or math.isnan(seconds): return "00:00"
    s = int(seconds)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}" if h > 0 else f"{m:02d}:{sec:02d}"

def _run_bg(cmd: Union[List[str], str]) -> bool:
    try:
        subprocess.Popen(
            cmd,
            cwd=str(get_base_dir()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True
        )
        return True
    except Exception: return False

def _run_checked(cmd: List[str], timeout: float = 2.0) -> bool:
    try: return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=timeout).returncode == 0
    except Exception: return False

def _normalize_reveal_path(target_path: Union[str, Path, None]) -> Optional[str]:
    if target_path is None: return None
    raw = str(target_path).strip().strip('"')
    if not raw: return None
    if raw.lower().startswith("file:"):
        from urllib.parse import unquote, urlparse
        raw = unquote(urlparse(raw).path or "")
        if os.name == "nt" and len(raw) >= 3 and raw[0] == "/" and raw[2] == ":": raw = raw[1:]
    raw = os.path.expanduser(raw)
    if os.name == "nt":
        if (m := re.match(r"^/([a-zA-Z])/(.*)$", raw.replace("\\", "/"))) and not os.path.exists(raw):
            raw = f"{m.group(1).upper()}:\\{m.group(2).replace('/', '\\')}"
        return os.path.normpath(raw)
    return os.path.abspath(raw)

def choose_file_manager_target(current_path: Union[str, Path, None], selected_path: Union[str, Path, None] = None) -> Optional[str]:
    for c in (current_path, selected_path):
        if (n := _normalize_reveal_path(c)) and os.path.exists(n): return n
    return None

def windows_explorer_select_command(path: str) -> str:
    s = path.replace('"', "")
    return f'explorer.exe /select,"{os.path.normpath(s) if os.name == "nt" else s}"'

def _windows_shell_select(path: str) -> bool:
    if os.name != "nt": return False
    try:
        import ctypes
        sh, ole = ctypes.windll.shell32, ctypes.windll.ole32
        ole.CoInitialize(None)
        sh.ILCreateFromPathW.argtypes, sh.ILCreateFromPathW.restype = [ctypes.c_wchar_p], ctypes.c_void_p
        sh.ILFree.argtypes, sh.ILFree.restype = [ctypes.c_void_p], None
        sh.SHOpenFolderAndSelectItems.argtypes, sh.SHOpenFolderAndSelectItems.restype = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_ulong], ctypes.c_long
        if not (pidl := sh.ILCreateFromPathW(os.path.normpath(path))): return False
        try: return int(sh.SHOpenFolderAndSelectItems(pidl, 0, None, 0)) == 0
        finally: sh.ILFree(pidl)
    except Exception: return False

def _file_uri(path: str) -> str:
    from urllib.parse import quote
    t = str(path).replace("\\", "/")
    return ("file:///" if re.match(r"^[a-zA-Z]:/", t) else "file://") + quote(t if t.startswith("/") or re.match(r"^[a-zA-Z]:/", t) else "/" + t, safe="/:")

def _reveal_folder(path: str, is_file: bool) -> str:
    if not is_file: return path
    t = str(path).rstrip("\\/")
    c = max(t.rfind("/"), t.rfind("\\"))
    return t[:c] if c > 0 else t

def reveal_launch_plan(path: str, platform: str, is_file: Optional[bool] = None) -> List[Tuple[str, Union[List[str], str]]]:
    k = platform.lower()
    target = str(path) if k in ("linux", "freebsd", "darwin") else (_normalize_reveal_path(path) or str(path))
    ft = os.path.isfile(target) if is_file is None else bool(is_file)
    folder = _reveal_folder(target, ft)
    if k == "darwin": return [("bg", ["open", "-R", target] if ft else ["open", folder])]
    if k == "win32": return [("bg", windows_explorer_select_command(target) if ft else ["explorer.exe", folder])]
    if k == "wsl": return [("wsl", target if ft else folder), ("bg", ["wslview", folder])]
    plan: List[Tuple[str, Union[List[str], str]]] = []
    if ft:
        uri, name = _file_uri(target), target[len(folder) + 1:] if folder and target.startswith(folder) else os.path.basename(target)
        plan.extend([
            ("checked", ["dbus-send", "--session", "--type=method_call", "--dest=org.freedesktop.FileManager1", "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1.ShowItems", f"array:string:{uri}", "string:"]),
            ("checked", ["gdbus", "call", "--session", "--dest", "org.freedesktop.FileManager1", "--object-path", "/org/freedesktop/FileManager1", "--method", "org.freedesktop.FileManager1.ShowItems", f"['{uri}']", ""]),
            ("checked", ["dbus-send", "--session", "--type=method_call", "--dest=org.xfce.FileManager", "/org/xfce/FileManager", "org.xfce.FileManager.DisplayFolderAndSelect", f"string:{folder}", f"string:{name}", "string:"]),
            ("bg", ["dolphin", "--select", target]), ("bg", ["nautilus", "--select", target]), ("bg", ["nemo", target]), ("bg", ["caja", target])
        ])
    plan.extend([("bg", [p, folder]) for p in ("thunar", "pcmanfm-qt", "pcmanfm")] + [("bg", ["gio", "open", folder]), ("bg", ["xdg-open", folder])])
    return plan

def _execute_reveal_plan(plan: List[Tuple[str, Union[List[str], str]]], which=None) -> bool:
    finder = which or shutil.which
    for mode, cmd in plan:
        if mode == "wsl":
            if not (finder("wslpath") and finder("explorer.exe")): continue
            try: conv = subprocess.run(["wslpath", "-w", str(cmd)], capture_output=True, text=True, timeout=2).stdout.strip()
            except Exception: conv = ""
            if conv and _run_bg(["cmd.exe", "/c", windows_explorer_select_command(conv) if os.path.isfile(str(cmd)) else f'explorer.exe "{conv}"']): return True
        elif isinstance(cmd, str):
            if mode == "bg" and _run_bg(cmd): return True
        elif finder(cmd[0]) and (_run_checked(cmd) if mode == "checked" else _run_bg(cmd)):
            return True
    return False

def open_in_file_manager(target_path: Union[str, Path, None]) -> bool:
    if not (norm := _normalize_reveal_path(target_path)) or not os.path.exists(norm): return False
    if sys.platform == "win32" and os.path.isfile(norm) and _windows_shell_select(norm): return True
    if sys.platform in ("darwin", "win32"): plat = sys.platform
    elif Path("/proc/version").exists() and "microsoft" in Path("/proc/version").read_text(errors="ignore").lower(): plat = "wsl"
    else: plat = "freebsd" if sys.platform.startswith("freebsd") else "linux"
    return _execute_reveal_plan(reveal_launch_plan(norm, plat))

def find_tracklist_for_mix(mix_file: Union[str, Path, None]) -> Optional[str]:
    if not mix_file or not (p := Path(mix_file).expanduser().resolve()).exists(): return None
    if (exact := p.parent / f"{p.stem}.txt").is_file(): return str(exact)
    base = get_base_dir()
    c_dirs = [d for d in {p.parent, p.parent / "FLAC_CONVERTED_OUTPUTS", p.parent.parent / "FLAC_CONVERTED_OUTPUTS", base / "FLAC_CONVERTED_OUTPUTS", base, p.parent.parent} if d.is_dir()]
    for d in c_dirs:
        if (c := d / f"{p.stem}.txt").is_file(): return str(c)
    tokens = [m.group(1) for m in (re.search(r'[_\ -](\d{2,3})([_\ -]|$)', p.stem), re.search(r'(\d{4}-\d{2}-\d{2})', p.stem)) if m]
    words = [w.lower() for w in re.sub(r'[_\ -]+', ' ', re.sub(r'MPlanetarian|Stream|of|Frequency|Part|WMI|Mix', '', p.stem, flags=re.I)).split() if len(w) >= 4]
    for d in c_dirs:
        try:
            for f in d.iterdir():
                if f.is_file() and f.suffix.lower() == ".txt":
                    fn = f.name.lower()
                    if any(t in fn for t in tokens) or any(w in fn for w in words): return str(f)
        except Exception: pass
    if (sh := base / "Mix_Archive_Manager.sh").is_file():
        try:
            out = subprocess.run(["bash", "-c", f'source "{sh}" 2>/dev/null; find_mix_tracklist "{p}" 2>/dev/null'], capture_output=True, text=True, timeout=1.5).stdout.strip()
            if out and os.path.isfile(out): return out
        except Exception: pass
    return None

def launch_liquid_glass_tracklist(
    tracklist_path: Union[str, Path],
    audio_path: Optional[Union[str, Path]] = None,
    theme: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> bool:
    if sys.platform not in ("linux", "darwin", "win32") and not sys.platform.startswith("freebsd"):
        return False
    if not tracklist_path or not (tl := Path(tracklist_path).expanduser().resolve()).is_file():
        return False
    base = base_dir or get_base_dir()

    if sys.platform == "darwin":
        candidates = [
            base / "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
            base / "scripts" / "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
            Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
            base / "MP_Audio_Player_Liquid_Glass_macOS.py",
            base / "scripts" / "MP_Audio_Player_Liquid_Glass_macOS.py",
            Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_macOS.py",
        ]
    else:
        backend = os.environ.get("MP_LIQUID_GLASS_BACKEND", "").strip().lower() or os.environ.get("LIQUID_GLASS_BACKEND", "").strip().lower()
        if not backend:
            for cfg in (base / "config.env", CONFIG_DIR / "config.env", Path(__file__).resolve().parent / "config.env"):
                if cfg.is_file():
                    if val := parse_env_file(cfg).get("LIQUID_GLASS_BACKEND"):
                        backend = val.strip().lower()
                        break
        if not backend:
            backend = "opengl"

        if backend == "vulkan":
            candidates = [
                base / "MP_Audio_Player_Liquid_Glass.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass.py",
                base / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            ]
        else:
            candidates = [
                base / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                base / "MP_Audio_Player_Liquid_Glass.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass.py",
            ]

    script_path = None
    for cand in candidates:
        if cand.is_file():
            script_path = cand
            break

    if not script_path:
        return False

    cmd = [sys.executable, str(script_path), "--tracklist", str(tl)]
    if audio_path and os.path.exists(str(audio_path)):
        cmd.extend(["--audio", str(Path(audio_path).expanduser().resolve())])
    if theme:
        cmd.extend(["--theme", str(theme)])

    log_dir = Path.home() / ".config" / "mix-manager"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    log_file = log_dir / "liquid_glass_tracklist.log"

    extra_kwargs = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        extra_kwargs["start_new_session"] = True

    try:
        with open(log_file, "a") as log_fd:
            proc = subprocess.Popen(
                cmd,
                cwd=str(base),
                stdin=subprocess.DEVNULL,
                stdout=log_fd,
                stderr=log_fd,
                close_fds=True,
                **extra_kwargs,
            )
            return proc.pid > 0
    except Exception:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(base),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                **extra_kwargs,
            )
            return proc.pid > 0
        except Exception as exc:
            try:
                mp_log_error("MP_Audio_Player", f"Failed launching Liquid Glass tracklist viewer: {exc}", exc)
            except Exception:
                pass
            return False


def open_tracklist_window(target_tracklist: Union[str, Path, None], audio_path: Optional[Union[str, Path]] = None, theme: Optional[str] = None) -> bool:
    if not target_tracklist or not (tl := Path(target_tracklist).expanduser().resolve()).is_file(): return False
    base = get_base_dir()
    v_sh = base / "scripts" / "view_tracklist_console.sh"
    if not v_sh.is_file(): v_sh = base / "view_tracklist_console.sh"
    t_str, v_str, title = str(tl), str(v_sh), "Mix Tracklist Viewer"
    a_str = str(Path(audio_path).expanduser().resolve()) if audio_path and os.path.exists(str(audio_path)) else ""
    if a_str: os.environ["MP_TRACKLIST_AUDIO_FILE"] = a_str
    active_theme = (theme or "").strip()
    if not active_theme:
        try:
            th_file = CONFIG_DIR / "theme"
            if th_file.is_file(): active_theme = th_file.read_text(encoding="utf-8").strip()
        except Exception: pass
    if not active_theme:
        active_theme = os.environ.get("MP_TRACKLIST_THEME") or os.environ.get("CURRENT_THEME") or ""
    if active_theme:
        os.environ["MP_TRACKLIST_THEME"] = active_theme
        os.environ["CURRENT_THEME"] = active_theme

    if os.environ.get("MP_LIQUID_GLASS") == "1" or os.environ.get("TRACKLIST_VIEWER") in ("liquid_glass", "glass"):
        if launch_liquid_glass_tracklist(tl, audio_path=a_str, theme=active_theme, base_dir=base):
            return True
    sh_args = [v_str] + (["--theme", active_theme] if active_theme else []) + [t_str] + ([a_str] if a_str else [])
    if (cust := os.environ.get("TRACKLIST_VIEWER")) and cust not in ("console", "auto") and shutil.which(cust) and _run_bg([cust, t_str]): return True
    if sys.platform.startswith(("linux", "freebsd")):
        if shutil.which("konsole") and v_sh.is_file() and _run_bg(["konsole", "--hide-menubar", "--hide-tabbar", "--separate", "--qwindowtitle", title, "-p", f"tabtitle={title}", "-p", "TerminalMargin=0", "-p", "TerminalColumns=95", "-p", "TerminalRows=35", "-e", "bash"] + sh_args):
            threading.Thread(target=lambda: (time.sleep(0.15), shutil.which("xprop") and subprocess.run(["xprop", "-name", title, "-f", "_MOTIF_WM_HINTS", "32c", "-set", "_MOTIF_WM_HINTS", "0x2, 0x0, 0x0, 0x0, 0x0"], capture_output=True)), daemon=True).start()
            return True
        xfce_cmd = f"bash '{v_str}'" + (f" --theme '{active_theme}'" if active_theme else "") + f" '{t_str}'" + (f" '{a_str}'" if a_str else "")
        for term, args in [("gnome-terminal", [f"--title={title}", "--hide-menubar", "--", "bash"] + sh_args), ("xfce4-terminal", [f"--title={title}", "--hide-menubar", "--hide-borders", "-e", xfce_cmd]), ("alacritty", ["--title", title, "-e", "bash"] + sh_args), ("foot", ["-T", title, "bash"] + sh_args), ("xterm", ["-title", title, "-bd", "0", "-geometry", "95x35", "-e", "bash"] + sh_args), ("xdg-open", [t_str])]:
            if shutil.which(term) and _run_bg([term] + args): return True
    elif sys.platform == "darwin":
        if v_sh.is_file():
            mac_args = f'\\"{v_str}\\"' + (f' --theme \\"{active_theme}\\"' if active_theme else "") + f' \\"{t_str}\\"' + (f' \\"{a_str}\\"' if a_str else "")
            if _run_bg(["osascript", "-e", f'tell application "Terminal" to do script "bash {mac_args}"']): return True
        return _run_bg(["open", t_str])
    elif sys.platform == "win32":
        try: os.startfile(t_str); return True
        except Exception: pass
    return False

def export_playlist_m3u(mixes: List[Dict[str, Any]], target_path: Union[str, Path, None]) -> Tuple[bool, str]:
    if not target_path: return False, "Destination path cannot be empty"
    try:
        tp = Path(str(target_path).strip()).expanduser()
        if tp.suffix.lower() != ".m3u": tp = tp.with_suffix(".m3u")
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text("#EXTM3U\n" + "".join(f"#EXTINF:-1,{m.get('name', Path(m.get('path', '')).stem)}\n{m.get('path')}\n" for m in mixes), encoding="utf-8")
        return True, str(tp.resolve())
    except Exception as e: return False, str(e)

def open_image_viewer(image_path: Union[str, Path]) -> bool:
    if not (ip := Path(image_path).expanduser().resolve()).is_file(): return False
    t_str = str(ip)
    if sys.platform.startswith(("linux", "freebsd")):
        return any(shutil.which(v) and _run_bg([v, t_str]) for v in ("gwenview", "loupe", "eog", "feh", "xdg-open"))
    if sys.platform == "darwin": return _run_bg(["open", "-a", "Preview", t_str]) or _run_bg(["open", t_str])
    if sys.platform == "win32":
        try: os.startfile(t_str); return True
        except Exception: pass
    return False

def notify_desktop(title: str, message: str) -> None:
    title, message = str(title or "MP Audio Player"), str(message or "")
    if not message: return
    try:
        if sys.platform.startswith(("linux", "freebsd")) and shutil.which("notify-send"):
            _run_bg(["notify-send", "-a", "MP Audio Player", title, message])
        elif sys.platform == "darwin":
            esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
            _run_bg(["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}"'])
    except Exception:
        pass

def _resolve_sub_dir(sub_name: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or get_base_dir()
    mix_arc = os.environ.get("MIX_ARCHIVE_DIR")
    if not mix_arc:
        for cfg in (base / "config.env", CONFIG_DIR / "config.env"):
            if val := parse_env_file(cfg).get("MIX_ARCHIVE_DIR"):
                if os.path.isdir(val): mix_arc = val; break
    for d in ([Path(mix_arc) / sub_name] if mix_arc and os.path.isdir(mix_arc) else []) + [base / sub_name, CONFIG_DIR / sub_name]:
        try: d.mkdir(parents=True, exist_ok=True); return d.resolve()
        except Exception: pass
    fb = base / sub_name
    fb.mkdir(parents=True, exist_ok=True)
    return fb.resolve()

def get_default_spek_dir(base_dir: Optional[Path] = None, mode: str = "MIX_ARCHIVE", audio_path: Optional[str] = None) -> Path:
    return _resolve_sub_dir("SPEK_OUTPUTS", base_dir)

def get_recording_output_dir(base_dir: Optional[Path] = None) -> Path:
    return _resolve_sub_dir("MP_AUDIOWAV_REC_OUTPUT", base_dir)

def find_existing_spek(audio_path: Optional[Union[str, Path]], mode: str = "MIX_ARCHIVE", output_dir: Optional[Union[str, Path]] = None) -> Optional[str]:
    if not audio_path: return None
    p = Path(audio_path).expanduser()
    stem, clean = p.stem, re.sub(r'[\/\\:\*\?"<>\|]', '_', p.stem)
    base = get_base_dir()
    c_dirs = ([Path(output_dir)] if output_dir else []) + [get_default_spek_dir(base, mode, str(audio_path))]
    if p.parent.is_dir():
        c_dirs.extend([p.parent / "SPEK_OUTPUTS", p.parent])
        if p.parent.parent.is_dir(): c_dirs.append(p.parent.parent / "SPEK_OUTPUTS")
    c_dirs.append(base / "SPEK_OUTPUTS")
    names = list(dict.fromkeys(f"{s}{ext}" for s in (clean, stem) for ext in ("_spectrogram.png", ".spek.png", ".spek", "_spectrogram.jpg")))
    seen = set()
    for d in c_dirs:
        rd = str(d.resolve()) if d.exists() else str(d)
        if rd in seen or not d.is_dir(): continue
        seen.add(rd)
        for n in names:
            c = d / n
            try:
                if c.is_file() and c.stat().st_size > 0: return str(c.resolve())
            except Exception: pass
    return None

def generate_track_spek(audio_path: str, mode: str = "MIX_ARCHIVE", output_dir: Optional[Union[str, Path]] = None, force: bool = False) -> Tuple[bool, str]:
    if not audio_path or not os.path.isfile(audio_path): return False, "Audio file not found"
    if not force and (ex := find_existing_spek(audio_path, mode, output_dir)): return True, ex
    out_dir = Path(output_dir) if output_dir else get_default_spek_dir(get_base_dir(), mode, audio_path)
    try: out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e: return False, f"Failed to create SPEK output directory: {e}"
    clean_stem = re.sub(r'[\\/:\*\?"<>\|]', '_', Path(audio_path).stem)
    spek_file = out_dir / f"{clean_stem}_spectrogram.png"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(audio_path),
             "-lavfi", "showspectrumpic=s=1920x1080:mode=combined:color=intensity:scale=log:legend=1:saturation=1.2",
             "-frames:v", "1", str(spek_file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        if proc.returncode == 0 and spek_file.is_file() and spek_file.stat().st_size > 0:
            return True, str(spek_file.resolve())
        err = (proc.stderr or "").strip().splitlines()
        return False, (err[-1][:180] if err else "FFmpeg failed to produce spectrogram image")
    except Exception as exc: return False, f"Spectrogram generation error: {exc}"

def choose_export_m3u_gui() -> Optional[str]:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")): return None
    dt = os.path.join(os.path.expanduser("~/Desktop" if os.path.isdir(os.path.expanduser("~/Desktop")) else "~"), "MP_Archive_Playlist.m3u")
    for cmd in (["kdialog", "--title", "Export MP Mix Archive Playlist (.m3u)", "--getsavefilename", dt, "*.m3u | M3U Playlist (*.m3u)"], ["zenity", "--file-selection", "--save", "--confirm-overwrite", f"--filename={dt}", "--file-filter=M3U Playlist (*.m3u) | *.m3u"]):
        if shutil.which(cmd[0]):
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else ""
            except Exception: pass
    return None

def choose_audio_file_gui() -> Optional[str]:
    if sys.platform == "win32":
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "[System.Reflection.Assembly]::LoadWithPartialName('System.windows.forms')|Out-Null;$f=New-Object System.Windows.Forms.OpenFileDialog;$f.Filter='Audio Files (*.flac;*.wav;*.mp3;*.ogg;*.aac;*.m4a)|*.flac;*.wav;*.mp3;*.ogg;*.aac;*.m4a|All Files (*.*)|*.*';$f.Title='Open Audio File in MP Audio Player';if($f.ShowDialog() -eq 'OK'){Write-Host $f.FileName}"], capture_output=True, text=True, timeout=120).stdout.strip()
            return out if out and os.path.isfile(out) else ("" if out == "" else None)
        except Exception: pass
    elif sys.platform == "darwin":
        try:
            if res := subprocess.run(["osascript", "-e", 'choose file of type {"public.audio", "wav", "flac", "mp3", "ogg", "aac", "m4a"} with prompt "Open Audio File in MP Audio Player"'], capture_output=True, text=True, timeout=120).stdout.strip():
                p = subprocess.run(["osascript", "-e", f'POSIX path of "{res}"'], capture_output=True, text=True, timeout=10).stdout.strip()
                if p and os.path.isfile(p): return p
            return ""
        except Exception: pass
    elif os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        h = os.path.expanduser("~")
        for cmd in (["kdialog", "--title", "Open Audio File in MP Audio Player", "--getopenfilename", h, "*.flac *.wav *.mp3 *.ogg *.aac *.m4a *.aiff | Audio Files (*.flac *.wav *.mp3 *.ogg *.aac *.m4a *.aiff)"], ["zenity", "--file-selection", "--title=Open Audio File in MP Audio Player", f"--filename={h}/", "--file-filter=Audio Files (*.flac, *.wav, *.mp3, *.ogg, *.aac, *.m4a) | *.flac *.wav *.mp3 *.ogg *.aac *.m4a *.FLAC *.WAV *.MP3"]):
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
                if p.is_dir() and str(p) not in seen: seen.add(str(p)); dirs.append(p)
            except Exception: pass
        def parse(ex):
            if ex:
                for pt in re.split(r'[;\n,]|(?<!^[a-zA-Z]):(?![\\/])', ex): add(pt)
        add(os.environ.get("MIX_ARCHIVE_DIR"))
        parse(os.environ.get("EXTRA_MIX_ARCHIVE_DIRS") or os.environ.get("MIX_ARCHIVE_DIRS"))
        efs = [self.base_dir / "config.env", CONFIG_DIR / "config.env", Path(__file__).resolve().parent / "config.env"]
        if sys.platform == "win32": efs.append(Path("B:/MIX_ARCHIVE/config.env"))
        for ef in efs:
            cfg = parse_env_file(ef)
            add(cfg.get("MIX_ARCHIVE_DIR"))
            parse(cfg.get("EXTRA_MIX_ARCHIVE_DIRS") or cfg.get("MIX_ARCHIVE_DIRS"))
        for n in ("MIX_ARCHIVE", "MP_SAMPLES", "FLAC_CONVERTED_OUTPUTS", "MP3_CONVERTED_OUTPUTS", "WAV_CONVERTED_OUTPUTS"): add(self.base_dir / n)
        if sys.platform == "win32":
            for d in ("B:/MIX_ARCHIVE", "B:/MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS", "X:/MIX_ARCHIVE"): add(d)
            for l in "BDEFGNVXZ": add(f"{l}:/MIX_ARCHIVE")
        else:
            for p in ("/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE", "/run/media/mplanetarian/DATA/MIX_ARCHIVE2/FLAC_CONVERTED_OUTPUTS", os.path.expanduser("~/GoogleDrive/MIX_ARCHIVE")): add(p)
        if not dirs:
            for fb in (self.base_dir / "MIX_ARCHIVE", self.base_dir / "FLAC_CONVERTED_OUTPUTS", self.base_dir, Path.home() / "Music"):
                if fb not in (Path.home(), Path("/")): add(fb)
        return dirs

    def _load_and_scan(self):
        seen, collected, home_p, skip = set(), [], Path.home(), {'__pycache__', 'node_modules', '.git', 'venv', '.venv'}
        for ad in self._get_archive_dirs():
            if not ad.is_dir() or ad in (home_p, Path("/")): continue
            for root, subdirs, files in os.walk(ad):
                subdirs[:] = [d for d in subdirs if not d.startswith('.') and d not in skip]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in AUDIO_EXTENSIONS and (fp := os.path.join(root, f)) not in seen:
                        seen.add(fp)
                        try:
                            st = os.stat(fp)
                            collected.append({"name": f, "path": fp, "size_mb": st.st_size / 1048576.0, "mtime": st.st_mtime, "ext": ext[1:].upper()})
                        except OSError: pass
        self.mixes = sorted(collected, key=lambda x: x["mtime"], reverse=True)

    def get_mixes(self, query: str = "") -> List[Dict[str, Any]]:
            if not (q := query.lower().strip()): 
                return self.mixes
            tokens = q.split()

            # Cache the processed search strings on the tracks themselves if it hasn't been done yet
            if not hasattr(self, '_search_cache_initialized') or self._search_cache_initialized != id(self.mixes):
                self._cached_search_data = []
                for m in self.mixes:
                    raw_text = " ".join(str(v) for v in m.values()).lower()
                    clean_text = re.sub(r'[^a-z0-9\s]', ' ', raw_text)
                    self._cached_search_data.append((m, raw_text, clean_text))
                self._search_cache_initialized = id(self.mixes)

            results = []
            for m, raw_text, clean_text in self._cached_search_data:
                if all(t in raw_text or t in clean_text for t in tokens):
                    results.append(m)

            return results
    def get_latest_mix(self) -> Optional[Dict[str, Any]]: return self.mixes[0] if self.mixes else None

class MusicFolderPlaylistScanner:
    def __init__(self, folder_name: Union[str, Path, None] = "ALL", playlist_path: Union[str, Path, None] = None):
        if folder_name and (str(folder_name).endswith((".json", ".m3u", ".m3u8")) or os.path.exists(str(folder_name))):
            playlist_path, folder_name = folder_name, "ALL"
            if (m := re.match(r'^DJ_Tracks_(.+)\.(?:json|m3u8?)$', os.path.basename(str(playlist_path)), re.I)) and m.group(1).upper() != "ALL_MUSIC_FOLDERS":
                folder_name = m.group(1)
        self.folder_name = str(folder_name or "ALL").upper()
        self.base_dir = get_base_dir()
        self.mixes: List[Dict[str, Any]] = []
        self.playlist_path = Path(playlist_path) if playlist_path else None
        self._load_playlist()

    def _load_playlist(self):
        pl_dir = self.base_dir / "PLAYLISTS_GENERATED"
        if not self.playlist_path or not self.playlist_path.is_file():
            for c in (pl_dir / f"DJ_Tracks_{self.folder_name}.json", pl_dir / f"DJ_Tracks_{self.folder_name}.m3u8", pl_dir / "DJ_Tracks_ALL_MUSIC_FOLDERS.json", pl_dir / "DJ_Tracks_ALL_MUSIC_FOLDERS.m3u8"):
                if c.is_file(): self.playlist_path = c; break
        if not self.playlist_path or not self.playlist_path.is_file(): return
        if str(self.playlist_path).endswith(".json"):
            try:
                data = json.loads(self.playlist_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for m in data: m.setdefault("duration_fmt", "00:00")
                    self.mixes = data
                    return
            except Exception: pass
        try:
            cur_t, cur_d, now = "", "00:00", time.time()
            for line in self.playlist_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not (line := line.strip()): continue
                if line.startswith("#EXTINF:"):
                    p = line[8:]
                    if "," in p:
                        dp, cur_t = p.split(",", 1)
                        try: cur_d = format_seconds(float(dp.strip())) if float(dp.strip()) > 0 else "00:00"
                        except ValueError: cur_d = "00:00"
                    else: cur_t, cur_d = p, "00:00"
                elif not line.startswith("#"):
                    ext, bname = os.path.splitext(line)[1].lower(), os.path.basename(line)
                    self.mixes.append({"name": bname, "title": cur_t or os.path.splitext(bname)[0], "path": line, "ext": ext[1:].upper() if ext else "AUDIO", "size_mb": 0.0, "duration_fmt": cur_d, "mtime": now, "folder": self.folder_name})
                    cur_t, cur_d = "", "00:00"
        except Exception: pass

    def get_mixes(self, query: str = "") -> List[Dict[str, Any]]:
            if not (q := query.lower().strip()): 
                return self.mixes
            tokens = q.split()

            # Cache the processed search strings on the tracks themselves if it hasn't been done yet
            if not hasattr(self, '_search_cache_initialized') or self._search_cache_initialized != id(self.mixes):
                self._cached_search_data = []
                for m in self.mixes:
                    raw_text = " ".join(str(v) for v in m.values()).lower()
                    clean_text = re.sub(r'[^a-z0-9\s]', ' ', raw_text)
                    self._cached_search_data.append((m, raw_text, clean_text))
                self._search_cache_initialized = id(self.mixes)

            results = []
            for m, raw_text, clean_text in self._cached_search_data:
                if all(t in raw_text or t in clean_text for t in tokens):
                    results.append(m)
            return results
    def get_latest_mix(self) -> Optional[Dict[str, Any]]: return self.mixes[0] if self.mixes else None

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
            return np.column_stack((c, c)).astype(np.float32, copy=False)
        return arr[:, :2].astype(np.float32, copy=False)

    def process(self, read_func, out_frames: int, speed_ratio: float) -> np.ndarray:
        if abs(speed_ratio - 1.0) < 1e-4 and self.in_pos == 0.0 and len(self.buffer) == 0:
            raw = read_func(out_frames)
            return np.zeros((0, 2), dtype=np.float32) if len(raw) == 0 else self._to_stereo(raw)
        t_out = self.in_pos + np.arange(out_frames, dtype=np.float64) * speed_ratio
        needed = int(math.ceil(t_out[-1])) + 4
        while len(self.buffer) < needed:
            more = read_func(max(1024, needed - len(self.buffer)))
            if len(more) == 0: break
            sm = self._to_stereo(more)
            self.buffer = np.vstack((self.buffer, sm)) if len(self.buffer) else sm
        if len(self.buffer) == 0: return np.zeros((0, 2), dtype=np.float32)
        self.in_pos = t_out[-1] + speed_ratio
        if len(self.buffer) <= int(math.ceil(t_out[-1])):
            self.buffer = np.vstack((self.buffer, np.zeros((int(math.ceil(t_out[-1])) + 4 - len(self.buffer), 2), dtype=np.float32)))
        t_in = np.arange(len(self.buffer), dtype=np.float64)
        out = np.column_stack((np.interp(t_out, t_in, self.buffer[:, 0]), np.interp(t_out, t_in, self.buffer[:, 1]))).astype(np.float32)
        if (discard := int(math.floor(self.in_pos))) > 0:
            self.buffer = self.buffer[discard:]
            self.in_pos -= discard
        return out

class AudioSource:
    def read(self, frames: int) -> np.ndarray: raise NotImplementedError
    def seek(self, frame: int): raise NotImplementedError
    def tell(self) -> int: raise NotImplementedError
    def total_frames(self) -> int: raise NotImplementedError
    def close(self): raise NotImplementedError

class SoundFileAudioSource(AudioSource):
    def __init__(self, path: str, initial_sf: Optional[Any] = None):
        _ensure_audio_backends()
        self.path, self.sf, self._current_frame = str(path), initial_sf, 0
        if self.sf is None: self._open_with_retry(4)
        self.samplerate, self.channels, self.frames = int(self.sf.samplerate), int(self.sf.channels), int(getattr(self.sf, "frames", 0))

    def _open_with_retry(self, max_retries: int = 4, target_frame: int = 0):
        _ensure_audio_backends()
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                self.close()
                self.sf = sf.SoundFile(self.path)
                if target_frame > 0:
                    try: self.sf.seek(target_frame)
                    except Exception: pass
                try: self._current_frame = int(self.sf.tell())
                except Exception: self._current_frame = target_frame
                return
            except Exception as e:
                last_exc = e
                if attempt < max_retries: time.sleep(0.25 * attempt)
        if last_exc: raise last_exc

    def read(self, frames: int) -> np.ndarray:
        for attempt in range(1, 4):
            try:
                if self.sf is None: self._open_with_retry(3, self._current_frame)
                data = self.sf.read(frames, dtype='float32')
                self._current_frame += len(data)
                return data
            except Exception as e:
                try: mp_log_error("MP_Audio_Player", f"SoundFile read glitch: {self.path}", e)
                except Exception: pass
                try: self._open_with_retry(3, self._current_frame)
                except Exception: pass
                if attempt < 3: time.sleep(0.15 * attempt)
        return np.zeros((0, self.channels), dtype=np.float32)

    def seek(self, frame: int):
        target = max(0, min(frame, max(0, self.frames - 1) if self.frames > 0 else frame))
        for attempt in range(1, 4):
            try:
                if self.sf is None: self._open_with_retry(2, target); return
                self.sf.seek(target)
                try: self._current_frame = int(self.sf.tell())
                except Exception: self._current_frame = target
                return
            except Exception:
                try: self._open_with_retry(2, target); return
                except Exception:
                    if attempt == 3: self._current_frame = target

    def tell(self) -> int:
        try:
            if self.sf: self._current_frame = int(self.sf.tell())
        except Exception: pass
        return self._current_frame

    def total_frames(self) -> int: return self.frames
    def close(self):
        if self.sf:
            try: self.sf.close()
            except Exception: pass
            self.sf = None

class FFmpegAudioSource(AudioSource):
    def __init__(self, path: str, target_samplerate: int = 44100):
        _ensure_audio_backends()
        self.path, self.samplerate, self.channels, self._current_frame, self.proc = str(path), target_samplerate, 2, 0, None
        self.frames = self._probe_frames()
        self._start_ffmpeg(0.0)

    def _probe_frames(self) -> int:
        try:
            out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate:format=duration", "-of", "default=noprint_wrappers=1:nokey=1", self.path], stderr=subprocess.DEVNULL, timeout=6).decode().splitlines()
            if len(out) >= 2 and out[0].strip().isdigit(): self.samplerate = int(out[0].strip())
            dur = float(out[-1].strip()) if out else 0.0
            return int(dur * self.samplerate)
        except Exception: return 0

    def _start_ffmpeg(self, start_sec: float = 0.0):
        self.close()
        cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start_sec:.3f}"] if start_sec > 0 else []) + ["-i", self.path, "-vn", "-f", "f32le", "-ac", "2", "-ar", str(self.samplerate), "pipe:1"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=131072)
            self._current_frame = int(start_sec * self.samplerate)
        except Exception as e:
            try: mp_log_error("MP_Audio_Player", f"Failed starting FFmpeg reader: {self.path}", e)
            except Exception: pass

    def read(self, frames: int) -> np.ndarray:
        if not self.proc or not self.proc.stdout: return np.zeros((0, 2), dtype=np.float32)
        try:
            if not (raw := self.proc.stdout.read(frames * 8)): return np.zeros((0, 2), dtype=np.float32)
            arr = np.frombuffer(raw, dtype=np.float32)
            nf = len(arr) // 2
            self._current_frame += nf
            return arr[:nf * 2].reshape((nf, 2))
        except Exception: return np.zeros((0, 2), dtype=np.float32)

    def seek(self, frame: int): self._start_ffmpeg(float(frame) / float(self.samplerate) if self.samplerate > 0 else 0.0)
    def tell(self) -> int: return self._current_frame
    def total_frames(self) -> int: return self.frames
    def close(self):
        if self.proc:
            try: self.proc.terminate(); self.proc.wait(timeout=0.3)
            except Exception:
                try: self.proc.kill()
                except Exception: pass
            self.proc = None

def open_audio_source(path: str) -> AudioSource:
    ext = os.path.splitext(str(path))[1].lower()
    for cls in ([FFmpegAudioSource, SoundFileAudioSource] if ext in ('.m4a', '.aac', '.wma', '.alac') else [SoundFileAudioSource, FFmpegAudioSource]):
        try: return cls(path)
        except Exception as e: last_exc = e
    raise last_exc

class AudioPrefetchBuffer:
    def __init__(self, sample_rate: int, buffer_sec: float = 12.0):
        self.sample_rate, self.max_frames = sample_rate, int(buffer_sec * sample_rate)
        self.chunks, self.chunk_offset, self.available_frames, self.eof = collections.deque(), 0, 0, False
        self.lock = threading.Lock()
        self.not_empty, self.not_full = threading.Condition(self.lock), threading.Condition(self.lock)

    def clear(self):
        with self.lock:
            self.chunks.clear()
            self.chunk_offset = self.available_frames = 0
            self.eof = False
            self.not_full.notify_all()

    def set_eof(self):
        with self.lock: self.eof = True; self.not_empty.notify_all()
    def is_empty(self) -> bool:
        with self.lock: return self.available_frames == 0
    def health_sec(self) -> float:
        with self.lock: return float(self.available_frames) / float(self.sample_rate) if self.sample_rate > 0 else 0.0

    def _to_stereo(self, arr: np.ndarray) -> np.ndarray:
        if arr.ndim == 1: return np.column_stack((arr, arr)).astype(np.float32, copy=False)
        if arr.shape[1] == 1: return np.column_stack((arr[:, 0], arr[:, 0])).astype(np.float32, copy=False)
        return arr[:, :2].astype(np.float32, copy=False)

    def write(self, data: np.ndarray, timeout: float = 0.5) -> bool:
        if len(data) == 0: return True
        ds = self._to_stereo(data)
        n = len(ds)
        with self.lock:
            while self.available_frames + n > self.max_frames:
                if not self.not_full.wait(timeout=timeout): return False
            self.chunks.append(ds)
            self.available_frames += n
            self.not_empty.notify_all()
            return True

    def read(self, frames: int) -> np.ndarray:
        with self.lock:
            if self.available_frames == 0: return np.zeros((0, 2), dtype=np.float32)
            n, parts, col = min(frames, self.available_frames), [], 0
            while col < n and self.chunks:
                front = self.chunks[0]
                avail, needed = len(front) - self.chunk_offset, n - col
                if avail <= needed:
                    parts.append(front[self.chunk_offset:])
                    col += avail
                    self.chunks.popleft()
                    self.chunk_offset = 0
                else:
                    parts.append(front[self.chunk_offset:self.chunk_offset + needed])
                    self.chunk_offset += needed
                    col += needed
                    break
            self.available_frames -= col
            self.not_full.notify_all()
            return parts[0] if len(parts) == 1 else (np.vstack(parts) if parts else np.zeros((0, 2), dtype=np.float32))

class AudioFeederThread(threading.Thread):
    def __init__(self, source: AudioSource, audio_buffer: AudioPrefetchBuffer, engine: Any, chunk_frames: int = 16384):
        super().__init__(name="AudioFeederThread", daemon=True)
        self.source, self.audio_buffer, self.engine, self.chunk_frames = source, audio_buffer, engine, chunk_frames
        self._running, self._seek_target, self.current_frame = True, None, 0
        self._seek_lock, self._wake_cond = threading.Lock(), threading.Condition(threading.Lock())

    def request_seek(self, frame: int):
        with self._seek_lock: self._seek_target = frame
        with self._wake_cond: self._wake_cond.notify_all()
        with self.audio_buffer.lock: self.audio_buffer.not_full.notify_all()

    def stop(self):
        self._running = False
        with self._wake_cond: self._wake_cond.notify_all()
        with self.audio_buffer.lock:
            self.audio_buffer.not_full.notify_all()
            self.audio_buffer.not_empty.notify_all()

    def run(self):
        cs = self.chunk_frames
        while self._running:
            with self._seek_lock:
                st, self._seek_target = self._seek_target, None
            if st is not None:
                try: self.source.seek(st); self.current_frame = st; self.audio_buffer.clear()
                except Exception as e:
                    try: mp_log_error("MP_Audio_Player", f"Feeder seek error: {e}", e)
                    except Exception: pass
            if self.audio_buffer.available_frames >= self.audio_buffer.max_frames:
                with self._wake_cond: self._wake_cond.wait(timeout=0.08)
                continue
            try: chunk = self.source.read(cs)
            except Exception: time.sleep(0.2); continue
            if len(chunk) > 0:
                self.current_frame = self.source.tell()
                while self._running and self._seek_target is None and not self.audio_buffer.write(chunk, timeout=0.1): pass
            else:
                cur_pos, tot = self.source.tell(), self.source.total_frames()
                if tot > 0 and cur_pos < (tot - cs * 2): time.sleep(0.15); continue
                got = False
                for _ in range(4):
                    time.sleep(0.1)
                    try:
                        if len(vc := self.source.read(cs)) > 0:
                            self.audio_buffer.write(vc); self.current_frame = self.source.tell(); got = True; break
                    except Exception: pass
                if got: continue
                if tot <= 0 or cur_pos >= (tot - cs * 2):
                    self.audio_buffer.set_eof()
                    while self._running and self._seek_target is None:
                        with self._wake_cond: self._wake_cond.wait(timeout=0.2)

EQ_BAND_FREQS: List[float] = [31.25, 62.5, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0]
EQ_BAND_LABELS: List[str] = ["31Hz", "62Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]
EQ_PRESET_FILE = CONFIG_DIR / "eq_preset"
EQ_CUSTOM_FILE = CONFIG_DIR / "custom_eq_presets.json"
EQ_ACTIVE_BANDS_FILE = CONFIG_DIR / "eq_active_bands.json"

DEFAULT_EQ_PRESETS: Dict[str, List[float]] = {
    "Flat": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "Ambient": [3.0, 2.5, 1.5, 0.0, -1.0, -1.5, -0.5, 1.0, 2.0, 2.5],
    "Trance": [4.0, 5.0, 2.0, -1.5, 0.0, 1.5, 2.5, 3.5, 4.0, 3.0],
    "Techno": [5.0, 4.5, 2.0, -2.5, -2.0, -0.5, 1.0, 2.5, 3.0, 1.5],
    "House": [3.5, 4.0, 3.0, -1.0, -1.0, 0.0, 1.5, 2.0, 3.0, 2.0],
    "Progressive": [3.0, 4.0, 2.5, -1.0, -1.0, 0.0, 1.5, 2.0, 2.5, 3.0],
    "Vapourwave": [-2.0, 1.0, 2.5, 3.5, 1.5, 0.0, -1.0, -2.5, -4.0, -6.0],
    "Sensorium Interface": [4.5, 4.0, 1.5, -1.0, 0.5, 1.5, 2.5, 3.5, 4.0, 3.0],
}

EQ_PRESET_ALIASES: Dict[str, str] = {
    "vaporwave": "Vapourwave",
    "vapor": "Vapourwave",
    "vapour": "Vapourwave",
    "progressive house": "Progressive",
    "prog": "Progressive",
    "default": "Flat",
    "sensorium": "Sensorium Interface",
    "sensorium interface": "Sensorium Interface",
    "sensorium_interface": "Sensorium Interface",
    "earth flipper": "Sensorium Interface",
    "earth_flipper": "Sensorium Interface",
}


class EqualizerFilter:
    def __init__(self, num_bands: int = 10, filter_len: int = 256):
        _ensure_numpy()
        self.band_freqs = np.array(EQ_BAND_FREQS, dtype=np.float32)
        self.filter_len = filter_len
        self.fft_len = 1024 + filter_len
        self.fft_n = int(2 ** np.ceil(np.log2(self.fft_len)))
        self.overlap = np.zeros((filter_len - 1, 2), dtype=np.float32)
        self.H = None
        self.is_flat = True
        self.current_sr = 44100
        self._lock = threading.Lock()

    def set_gains(self, gains_db: Sequence[float], sr: int = 44100):
        with self._lock:
            g = np.array(gains_db, dtype=np.float32)
            if np.all(np.abs(g) < 0.05):
                self.is_flat = True
                self.H = None
                return
            self.is_flat = False
            self.current_sr = int(sr if sr and sr > 0 else 44100)
            fft_freqs = np.fft.rfftfreq(self.filter_len, 1.0 / self.current_sr)
            log_bands = np.log10(self.band_freqs)
            log_fft = np.log10(np.maximum(10.0, fft_freqs))
            gains_interp_db = np.interp(log_fft, log_bands, g)
            lin_gain = 10.0 ** (gains_interp_db / 20.0)
            fir = np.fft.irfft(lin_gain, n=self.filter_len)
            fir = np.fft.fftshift(fir) * np.hanning(self.filter_len)
            fir_sum = np.sum(fir)
            if abs(fir_sum) > 1e-4:
                fir = fir / fir_sum
            self.H = np.fft.rfft(fir, n=self.fft_n).astype(np.complex64)[:, None]

    def process(self, chunk: np.ndarray) -> np.ndarray:
        with self._lock:
            if self.is_flat or self.H is None:
                return chunk
            n = len(chunk)
            if n == 0:
                return chunk
            if len(self.overlap) != self.filter_len - 1:
                self.overlap = np.zeros((self.filter_len - 1, 2), dtype=np.float32)
            ext = np.vstack([self.overlap, chunk])
            conv = np.fft.irfft(np.fft.rfft(ext, n=self.fft_n, axis=0) * self.H, n=self.fft_n, axis=0)
            self.overlap = chunk[-(self.filter_len - 1):].copy()
            delay = (self.filter_len - 1) // 2
            return np.clip(conv[delay : delay + n], -1.0, 1.0)


class EqualizerManager:
    def __init__(self):
        self.num_bands = 10
        self.band_freqs = list(EQ_BAND_FREQS)
        self.band_labels = list(EQ_BAND_LABELS)
        self.custom_presets: Dict[str, List[float]] = {}
        self.active_preset: str = "Flat"
        self.current_bands: List[float] = [0.0] * 10
        self._load()

    def _load(self):
        if EQ_CUSTOM_FILE.is_file():
            try:
                data = json.loads(EQ_CUSTOM_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, (list, tuple)) and len(v) == self.num_bands:
                            self.custom_presets[str(k)] = [max(-12.0, min(12.0, float(x))) for x in v]
            except Exception: pass

        preset_name = "Flat"
        if EQ_PRESET_FILE.is_file():
            try:
                saved = EQ_PRESET_FILE.read_text(encoding="utf-8").strip()
                if saved: preset_name = saved
            except Exception: pass

        self.apply_preset(preset_name, save=False)
        if self.active_preset == "Custom" and EQ_ACTIVE_BANDS_FILE.is_file():
            try:
                ab = json.loads(EQ_ACTIVE_BANDS_FILE.read_text(encoding="utf-8"))
                if isinstance(ab, (list, tuple)) and len(ab) == self.num_bands:
                    self.current_bands = [max(-12.0, min(12.0, float(x))) for x in ab]
            except Exception: pass

    def get_all_presets(self) -> Dict[str, List[float]]:
        p = dict(DEFAULT_EQ_PRESETS)
        p.update(self.custom_presets)
        return p

    def get_all_preset_names(self) -> List[str]:
        names = [k for k in DEFAULT_EQ_PRESETS.keys()]
        for c in sorted(self.custom_presets.keys()):
            if c not in names:
                names.append(c)
        return names

    def resolve_preset_name(self, name: str) -> Optional[str]:
        if not name: return None
        nl = name.strip().lower()
        if nl in EQ_PRESET_ALIASES:
            return EQ_PRESET_ALIASES[nl]
        for k in self.get_all_presets().keys():
            if k.lower() == nl:
                return k
        return None

    def apply_preset(self, name: str, save: bool = True) -> bool:
        resolved = self.resolve_preset_name(name)
        if resolved and resolved in self.get_all_presets():
            self.active_preset = resolved
            self.current_bands = list(self.get_all_presets()[resolved])
            if save:
                try: EQ_PRESET_FILE.write_text(self.active_preset, encoding="utf-8")
                except Exception: pass
            return True
        if name.strip().lower() == "custom":
            self.active_preset = "Custom"
            return True
        self.active_preset = "Flat"
        self.current_bands = list(DEFAULT_EQ_PRESETS["Flat"])
        if save:
            try: EQ_PRESET_FILE.write_text("Flat", encoding="utf-8")
            except Exception: pass
        return False

    def cycle_preset(self, direction: int = 1) -> str:
        names = self.get_all_preset_names()
        cur = self.active_preset
        if cur in names:
            idx = (names.index(cur) + direction) % len(names)
        else:
            idx = 0
        self.apply_preset(names[idx])
        return self.active_preset

    def set_band(self, index: int, gain_db: float, step: bool = False) -> bool:
        if not (0 <= index < self.num_bands): return False
        new_val = (self.current_bands[index] + gain_db) if step else gain_db
        new_val = round(max(-12.0, min(12.0, float(new_val))), 1)
        self.current_bands[index] = new_val
        self._check_if_preset_matched()
        try: EQ_ACTIVE_BANDS_FILE.write_text(json.dumps(self.current_bands), encoding="utf-8")
        except Exception: pass
        return True

    def set_bands(self, gains: Sequence[float]) -> bool:
        if len(gains) != self.num_bands: return False
        self.current_bands = [round(max(-12.0, min(12.0, float(x))), 1) for x in gains]
        self._check_if_preset_matched()
        try: EQ_ACTIVE_BANDS_FILE.write_text(json.dumps(self.current_bands), encoding="utf-8")
        except Exception: pass
        return True

    def _check_if_preset_matched(self):
        for name, preset_gains in self.get_all_presets().items():
            if all(abs(a - b) < 0.1 for a, b in zip(self.current_bands, preset_gains)):
                self.active_preset = name
                try: EQ_PRESET_FILE.write_text(self.active_preset, encoding="utf-8")
                except Exception: pass
                return
        self.active_preset = "Custom"
        try: EQ_PRESET_FILE.write_text("Custom", encoding="utf-8")
        except Exception: pass

    def save_custom_preset(self, name: str, gains: Optional[Sequence[float]] = None) -> bool:
        name = str(name).strip()
        if not name: name = "Custom 1"
        if name.lower() in ("flat", "ambient", "trance", "techno", "house", "progressive", "vapourwave", "vaporwave"):
            name = f"{name} (User)"
        band_vals = [round(max(-12.0, min(12.0, float(x))), 1) for x in (gains if gains is not None else self.current_bands)]
        self.custom_presets[name] = band_vals
        self.active_preset = name
        self.current_bands = list(band_vals)
        try:
            EQ_CUSTOM_FILE.write_text(json.dumps(self.custom_presets, indent=2), encoding="utf-8")
            EQ_PRESET_FILE.write_text(self.active_preset, encoding="utf-8")
            EQ_ACTIVE_BANDS_FILE.write_text(json.dumps(self.current_bands), encoding="utf-8")
        except Exception: pass
        return True

    def delete_custom_preset(self, name: str) -> bool:
        if name in self.custom_presets:
            del self.custom_presets[name]
            try: EQ_CUSTOM_FILE.write_text(json.dumps(self.custom_presets, indent=2), encoding="utf-8")
            except Exception: pass
            if self.active_preset == name:
                self.apply_preset("Flat")
            return True
        return False

    def is_flat(self) -> bool:
        return all(abs(x) < 0.05 for x in self.current_bands)

    def get_current_bands(self) -> List[float]:
        return list(self.current_bands)

class AudioEngine:
    def __init__(self, playlist: List[Dict[str, Any]], auto_bluetooth: bool = True, mode: str = "MIX_ARCHIVE"):
        _ensure_audio_backends()
        self.mode, self.playlist, self.play_queue, self._queue_lock = str(mode or "MIX_ARCHIVE").upper(), playlist, [], threading.Lock()
        self.current_index, self.current_track = 0, playlist[0] if playlist else None
        self.state, self.volume, self.muted, self.shuffle, self.repeat_mode = "stopped", 1.0, False, False, "all"
        self.position_sec, self.duration_sec, self.sample_rate, self.channels = 0.0, 0.0, 44100, 2
        self.pitch_percent, self.pitch_factor, self.resampler = 0, 1.0, AudioResampler()
        self.sf_file = self.stream = self.audio_source = self.audio_buffer = self.feeder = self.stream_error = self.pending_seek_sec = None
        self.output_rate, self.output_device_name, self._next_stream_retry, self.track_ended = 44100, "", 0.0, False
        self._sf_lock, self._sf_refs, self._sf_retired = threading.Lock(), 0, []

        self.num_bands = 24
        self.band_edges = np.logspace(np.log10(28), np.log10(18500), self.num_bands + 1)
        self.band_boosts = ((1.0 + (1.2 / (1.0 + np.arange(self.num_bands, dtype=np.float32) * 0.28))) * 4.6)
        for attr in ("levels", "levels_left", "levels_right", "smoothed_levels", "smoothed_levels_left", "smoothed_levels_right", "peaks", "peaks_left", "peaks_right", "peak_decay_timers", "peak_decay_timers_left", "peak_decay_timers_right"):
            setattr(self, attr, np.zeros(self.num_bands, dtype=np.float32))
        self.recent_mono_buffer = np.zeros(512, dtype=np.float32)
        self.rms_level, self.peak_db = 0.0, -60.0
        self.hanning_window, self.fft_scale = np.hanning(1024).astype(np.float32), 512.0
        self._setup_fft_bins(44100)
        self._cached_bt_info, self._last_bt_query = {}, 0.0
        self.is_recording, self.recording_current_path, self.recording_bytes_written, self.recording_duration_sec = False, "", 0, 0.0
        self._rec_queue = self._rec_worker_thread = self._rec_dir = None
        self._rec_lock, self._rec_part_index, self._rec_base_stem, self._rec_samplerate = threading.Lock(), 1, "", 48000
        self._ensure_stream()
        self.eq_manager = EqualizerManager()
        self.eq_filter = EqualizerFilter()
        self.eq_filter.set_gains(self.eq_manager.get_current_bands(), self.sample_rate)
        self.auto_bluetooth, self.bt_router = auto_bluetooth, None
        if BluetoothAudioRouter is not None:
            try:
                self.bt_router = BluetoothAudioRouter(target_pid=os.getpid(), on_route_change=self._on_bt_route_change, auto_switch=self.auto_bluetooth)
                self.bt_router.start()
            except Exception: pass

    def _setup_fft_bins(self, sr: int):
        freqs = np.fft.rfftfreq(1024, 1.0 / sr)
        self.band_indices = []
        for i in range(self.num_bands):
            idx = np.where((freqs >= self.band_edges[i]) & (freqs < self.band_edges[i + 1]))[0]
            if len(idx) == 0: idx = np.array([min(len(freqs) - 1, max(0, int(self.band_edges[i] / (sr / 2) * len(freqs))))])
            self.band_indices.append(idx)
        self._flat_idx = np.concatenate(self.band_indices)
        self._reduce_offsets = np.cumsum([0] + [len(x) for x in self.band_indices[:-1]])
        self._band_counts = np.array([len(x) for x in self.band_indices], dtype=np.float32)

    def _on_bt_route_change(self, device_name: str, is_bluetooth: bool, action: str, codec: Optional[str] = None):
        self._ensure_stream()
        if self.bt_router:
            try:
                self._cached_bt_info = self.bt_router.get_status(force_probe=True)
                self._last_bt_query = time.time()
                if is_bluetooth and self._cached_bt_info.get("bluetooth_codec"): codec = self._cached_bt_info["bluetooth_codec"]
            except Exception: pass
        c_sfx = f" {codec}" if codec else ""
        self.output_device_name = f"{device_name} [Bluetooth{c_sfx}]" if is_bluetooth else device_name
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
            if r > 0 and k not in seen: seen.add(k); attempts.append((d, int(r), e))
        if sd is None: return attempts

        # Windows WASAPI specific handling
        if sys.platform == "win32":
            try:
                for h in sd.query_hostapis():
                    if "WASAPI" in str(h.get("name", "")).upper() and (dev := h.get("default_output_device", -1)) is not None and int(dev) >= 0:
                        ex, nat = sd.WasapiSettings(exclusive=False, auto_convert=True), int(sd.query_devices(int(dev)).get("default_samplerate") or 48000)
                        for r in (nat, 48000, 44100): add(int(dev), r, ex)
            except Exception: pass

        # Safe macOS / cross-platform native rate query
        try:
            default_out = getattr(sd.default, 'device', None)
            default_out_idx = None
            if isinstance(default_out, (list, tuple)) and len(default_out) > 1:
                default_out_idx = default_out[1]
            elif isinstance(default_out, int):
                default_out_idx = default_out

            dev_info = sd.query_devices(default_out_idx, 'output') if default_out_idx is not None else sd.query_devices(kind='output')
            native_rate = int(dev_info.get("default_samplerate") or 48000)
            dev_idx = int(default_out_idx) if default_out_idx is not None and default_out_idx >= 0 else None
            for r in (native_rate, 44100, 48000, 96000, 88200):
                add(dev_idx, r, None)
        except Exception: pass

        try: 
            gen_out = sd.query_devices(kind="output")
            add(None, int(gen_out.get("default_samplerate") or 48000), None)
        except Exception: pass

        for r in (44100, 48000, 96000, 88200): 
            add(None, r, None)

        return attempts

    def _open_output_stream(self) -> bool:
        if sd is None: self.stream_error = "sounddevice is not installed"; return False
        errors = []
        for dev, rate, extra in self._stream_attempts():
            s = None
            try:
                kw = dict(samplerate=rate, channels=2, dtype="float32", callback=self._audio_callback, blocksize=1024, latency="high")
                if extra: kw["extra_settings"] = extra
                if dev is not None: kw["device"] = dev
                s = sd.OutputStream(**kw); s.start()
                nr = int(round(float(s.samplerate)))
                if nr != self.output_rate: self.resampler.reset()
                self.output_rate, self.stream, self.stream_error = nr or rate, s, None
                try: self.output_device_name = str(sd.query_devices(s.device[-1] if isinstance(s.device, (list, tuple)) else s.device)["name"])
                except Exception: self.output_device_name = "default"
                if self.bt_router:
                    try: threading.Thread(target=self.bt_router.check_and_route, daemon=True).start()
                    except Exception: pass
                return True
            except Exception as exc:
                errors.append(f"{dev}@{rate}: {exc}")
                if s:
                    try: s.close()
                    except Exception: pass
        self.stream, self.stream_error = None, "; ".join(errors)[-400:] if errors else "no output device"
        return False

    def _ensure_stream(self) -> bool:
        if self._stream_alive(): return True
        if time.time() < self._next_stream_retry: return False
        self._close_stream()
        if not (ok := self._open_output_stream()): self._next_stream_retry = time.time() + 1.5
        return ok

    def _acquire_sf(self):
        with self._sf_lock:
            if self.sf_file: self._sf_refs += 1
            return self.sf_file

    def _release_sf(self):
        with self._sf_lock:
            if self._sf_refs > 0: self._sf_refs -= 1
            closing, self._sf_retired = (self._sf_retired, []) if self._sf_refs == 0 and self._sf_retired else ([], self._sf_retired)
        for old in closing:
            try: old.close()
            except Exception: pass

    def _retire_sf(self, old_sf):
        if not old_sf: return
        with self._sf_lock:
            if self._sf_refs == 0: closing = [old_sf]
            else: self._sf_retired.append(old_sf); closing = []
        for old in closing:
            try: old.close()
            except Exception: pass

    def _stop_feeder(self):
        if f := self.feeder:
            self.feeder = None
            try: f.stop()
            except Exception: pass
        if b := self.audio_buffer:
            try: b.clear()
            except Exception: pass
        if s := self.audio_source:
            self.audio_source = None
            try: s.close()
            except Exception: pass

    def load_track(self, index: int, start_playing: bool = True, start_position: float = 0.0) -> bool:
        if not self.playlist or not (0 <= index < len(self.playlist)): return False
        self.current_index, self.current_track = index, self.playlist[index]
        self._stop_feeder()
        try:
            src = open_audio_source(self.current_track["path"])
            self.audio_source, self.sample_rate, self.channels = src, src.samplerate, src.channels
            self.duration_sec = float(src.total_frames()) / float(self.sample_rate) if self.sample_rate > 0 else 0.0
            self.current_track.update(duration_sec=self.duration_sec, duration_fmt=format_seconds(self.duration_sec))
            self.position_sec = 0.0
            self.resampler.reset()
            self._setup_fft_bins(self.sample_rate)
            self.eq_filter.set_gains(self.eq_manager.get_current_bands(), self.sample_rate)
            with self._sf_lock: old_sf, self.sf_file = self.sf_file, getattr(src, "sf", src)
            self._retire_sf(old_sf)
            self.audio_buffer = AudioPrefetchBuffer(self.sample_rate, 12.0)
            self.feeder = AudioFeederThread(self.audio_source, self.audio_buffer, self)
            self.feeder.start()
            if start_position > 0.0:
                self.seek(start_position)
            min_pre, t0 = int(0.5 * self.sample_rate), time.time()
            while (time.time() - t0 < 1.0) and (self.audio_buffer.available_frames < min_pre) and not self.audio_buffer.eof:
                time.sleep(0.04)
            self._ensure_stream()
            self.state = "playing" if start_playing else "paused"
            self._sync_state_file()
            if start_playing:
                try: record_activity("Play Mix / Audio File", category="playback", details={"track_name": self.current_track.get("name"), "track_path": self.current_track.get("path"), "duration_sec": round(self.duration_sec, 2), "sample_rate": self.sample_rate}, status="success")
                except Exception: pass
            return True
        except Exception as exc:
            self.state = "stopped"
            try: mp_log_error("MP_Audio_Player", f"Failed loading track: {self.current_track.get('path', '')}", exc)
            except Exception: pass
            return False

    def _sync_state_file(self):
        try:
            tmp = STATE_FILE.with_name(f".{STATE_FILE.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(self.get_status_dict(), default=float), encoding="utf-8")
            tmp.replace(STATE_FILE)
            if self.current_track and self.current_track.get("path") and self.duration_sec > 0:
                pos = round(float(self.position_sec), 2)
                if pos <= 0.0 and RESUME_STATE_FILE.is_file():
                    try:
                        prev = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
                        if prev.get("path") == str(self.current_track.get("path")):
                            prev_pos = float(prev.get("position_sec", 0.0))
                            if prev_pos > 0.0:
                                pos = prev_pos
                    except Exception: pass
                res_tmp = RESUME_STATE_FILE.with_suffix(".tmp")
                res_tmp.write_text(json.dumps({
                    "path": str(self.current_track.get("path")),
                    "position_sec": pos,
                    "duration_sec": round(float(self.duration_sec), 2),
                    "title": str(self.current_track.get("name", "")),
                    "mode": str(self.mode),
                    "player": "mp_audio_player",
                    "timestamp": time.time()
                }), encoding="utf-8")
                res_tmp.replace(RESUME_STATE_FILE)
        except Exception: pass

    def _audio_callback(self, outdata, frames, time_info, status):
        try: self._render_audio(outdata, frames)
        except Exception as exc: self.stream_error = str(exc); outdata.fill(0)

    def _render_audio(self, outdata, frames):
        buf = self.audio_buffer
        if buf is None or self.state != "playing": outdata.fill(0); return
        out_rate = float(self.output_rate or 48000)
        data = self.resampler.process(buf.read, frames, (float(self.sample_rate) / out_rate) * self.pitch_factor)
        rf = len(data)
        if self.feeder and self.sample_rate > 0:
            self.position_sec = min(self.duration_sec, float(max(0, self.feeder.current_frame - buf.available_frames)) / float(self.sample_rate))
        else:
            self.position_sec += float(max(rf, 0) * self.pitch_factor) / out_rate
        if rf <= 0:
            outdata.fill(0)
            if buf.eof and buf.is_empty(): self.track_ended = True
            return
        eff_vol = 0.0 if self.muted else self.volume
        sd_arr = (data if data.ndim > 1 and data.shape[1] >= 2 else np.column_stack((data, data) if data.ndim == 1 else (data[:, 0], data[:, 0])))[:, :2]
        if not self.eq_filter.is_flat:
            sd_arr = self.eq_filter.process(sd_arr)
        mono = (sd_arr[:, 0] + sd_arr[:, 1]) * 0.5
        if eff_vol != 1.0: sd_arr = np.ascontiguousarray(sd_arr * np.float32(eff_vol))
        ncopy = min(rf, frames, len(sd_arr))
        if buf.eof and buf.is_empty() and np.all(sd_arr[:ncopy] == 0):
            outdata.fill(0); self.track_ended = True; return
        outdata[:ncopy] = sd_arr[:ncopy]
        if ncopy < frames:
            outdata[ncopy:].fill(0)
            if buf.eof and buf.is_empty(): self.track_ended = True
        if self.is_recording and self._rec_queue is not None and ncopy > 0:
            try: self._rec_queue.put_nowait(sd_arr[:ncopy].copy())
            except Exception: pass
        self._compute_fft_spectrum(sd_arr[:ncopy], mono[:ncopy])

    def _compute_fft_spectrum(self, stereo_data: np.ndarray, mono_data: np.ndarray):
        try:
            n = len(mono_data)
            if n >= 1024:
                m, l, r = mono_data[:1024], stereo_data[:1024, 0], stereo_data[:1024, 1]
            else:
                pad = (0, 1024 - n)
                m, l, r = np.pad(mono_data, pad), np.pad(stereo_data[:, 0], pad), np.pad(stereo_data[:, 1], pad)
            w, sc, fi, ro, bc, bst = self.hanning_window, self.fft_scale, self._flat_idx, self._reduce_offsets, self._band_counts, self.band_boosts
            m_fft, l_fft, r_fft = np.abs(np.fft.rfft(m * w)) / sc, np.abs(np.fft.rfft(l * w)) / sc, np.abs(np.fft.rfft(r * w)) / sc

            for lv, sm, pk, tm, fft_arr in (
                (self.levels, self.smoothed_levels, self.peaks, self.peak_decay_timers, m_fft),
                (self.levels_left, self.smoothed_levels_left, self.peaks_left, self.peak_decay_timers_left, l_fft),
                (self.levels_right, self.smoothed_levels_right, self.peaks_right, self.peak_decay_timers_right, r_fft),
            ):
                np.clip((np.add.reduceat(fft_arr[fi], ro) / bc) * bst, 0.0, 1.0, out=lv)
                rise = lv > sm
                sm[:] = np.where(rise, sm * 0.15 + lv * 0.85, sm * 0.80 + lv * 0.20)
                hit = sm >= pk
                pk[:] = np.where(hit, sm, pk)
                tm[:] = np.where(hit, 0.0, tm + 0.025)
                dec = (~hit) & (tm > 0.15)
                pk[:] = np.where(dec, np.maximum(0.0, pk - (0.035 + (tm - 0.15) * 0.08)), pk)

            self.recent_mono_buffer = m[:512]
            self.rms_level = float(np.sqrt(np.mean(m * m)))
            self.peak_db = 20.0 * math.log10(max(1e-5, float(np.max(np.abs(m)))))
        except Exception: pass

    def check_track_end(self):
        if self.track_ended:
            self.track_ended = False
            if self.repeat_mode == "one": self.seek(0)
            elif self.repeat_mode == "all" or bool(self.play_queue) or self.current_index < len(self.playlist) - 1: self.next_track()
            else: self.stop_playback(reset_position=True)

    def play(self):
        if self.audio_source is None or self.feeder is None or self.state == "stopped": self.load_track(self.current_index, True)
        else:
            self.state = "playing"; self._ensure_stream()
            if self.bt_router and hasattr(self.bt_router, "running") and not self.bt_router.running:
                try: self.bt_router.start()
                except Exception: pass
            self._sync_state_file()

    def pause(self): self.state = "paused"; self._sync_state_file()
    def toggle_play_pause(self): self.pause() if self.state == "playing" else self.play()

    def stop_playback(self, reset_position: bool = False):
        self.state = "stopped"
        if reset_position: self.position_sec = 0.0
        self._stop_feeder()
        with self._sf_lock: old_sf, self.sf_file = self.sf_file, None
        self._retire_sf(old_sf)
        for a in (self.smoothed_levels, self.smoothed_levels_left, self.smoothed_levels_right, self.peaks, self.peaks_left, self.peaks_right): a.fill(0)
        self._sync_state_file()

    def queue_track(self, track_or_path: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        with self._queue_lock:
            td = dict(track_or_path) if isinstance(track_or_path, dict) else None
            if td is None and isinstance(track_or_path, str) and track_or_path:
                tp = str(track_or_path)
                td = next((dict(t) for t in self.playlist if t.get("path") == tp or t.get("name") == os.path.basename(tp)), None)
                if td is None:
                    td = {"name": os.path.basename(tp), "path": tp, "size_mb": os.path.getsize(tp) / 1048576.0 if os.path.isfile(tp) else 0.0, "mtime": time.time(), "ext": os.path.splitext(tp)[1].lstrip(".").upper()}
            if td:
                self.play_queue.append(td); self._sync_state_file()
                return {"queued": True, "track": td, "queue_len": len(self.play_queue)}
            return {"queued": False, "queue_len": len(self.play_queue)}

    def dequeue_next(self) -> Optional[Dict[str, Any]]:
        with self._queue_lock:
            if self.play_queue:
                t = self.play_queue.pop(0); self._sync_state_file(); return t
        return None

    def clear_queue(self) -> int:
        with self._queue_lock:
            n = len(self.play_queue); self.play_queue.clear(); self._sync_state_file(); return n

    def get_queue(self) -> List[Dict[str, Any]]:
        with self._queue_lock: return list(self.play_queue)

    def _step_track(self, direction: int):
        if direction > 0 and (qi := self.dequeue_next()):
            qp = qi.get("path")
            for i, t in enumerate(self.playlist):
                if t.get("path") == qp:
                    if self.load_track(i, True): return
                    break
            else:
                self.playlist.insert(0, qi)
                if self.load_track(0, True): return
        if not (n := len(self.playlist)): return
        for s in range(1, min(10, n) + 1):
            idx = random.choice([i for i in range(n) if i != self.current_index]) if (self.shuffle and n > 1) else (self.current_index + s * direction) % n
            if self.load_track(idx, True): return

    def next_track(self): self._step_track(1)
    def prev_track(self): self.seek(0) if self.position_sec > 5.0 else self._step_track(-1)

    def seek(self, target_sec: float):
        if self.duration_sec > 0:
            self.position_sec = target = max(0.0, min(self.duration_sec - 1.0, float(target_sec)))
            if self.feeder and self.sample_rate > 0: self.feeder.request_seek(int(target * self.sample_rate))
            self.resampler.reset()

    def seek_relative(self, delta_sec: float): self.seek(self.position_sec + delta_sec)
    def set_volume(self, vol_pct: int): self.volume, self.muted = max(0.0, min(1.0, float(vol_pct) / 100.0)), False; self._sync_state_file()
    def change_volume(self, delta_pct: int): self.set_volume(int(self.volume * 100) + delta_pct)
    def toggle_mute(self): self.muted = not self.muted; self._sync_state_file()
    def toggle_shuffle(self): self.shuffle = not self.shuffle; self._sync_state_file()
    def cycle_repeat(self):
        m = ["all", "one", "off"]
        self.repeat_mode = m[(m.index(self.repeat_mode) + 1) % 3]
        self._sync_state_file()

    def start_recording(self) -> str:
        with self._rec_lock:
            if self.is_recording: return self.recording_current_path
            self._rec_dir = get_recording_output_dir()
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            ct = str(self.current_track.get("name") or self.current_track.get("title", "")) if isinstance(self.current_track, dict) else ""
            cl = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', os.path.splitext(ct)[0])[:32].strip("_") if ct else ""
            cl_sfx = f"_{cl}" if cl else ""
            self._rec_base_stem, self._rec_part_index = f"MP_REC_{ts}{cl_sfx}", 1
            self.recording_current_path = str(self._rec_dir / f"{self._rec_base_stem}_pt01.wav")
            self.recording_bytes_written, self.recording_duration_sec = 0, 0.0
            self._rec_samplerate = int(self.output_rate or self.sample_rate or 48000)
            self.is_recording, self._rec_queue = True, queue.Queue(maxsize=1200)
            self._rec_worker_thread = threading.Thread(target=self._recording_worker, daemon=True)
            self._rec_worker_thread.start()
            self._sync_state_file()
            return self.recording_current_path

    def stop_recording(self) -> Tuple[bool, str]:
        with self._rec_lock:
            if not self.is_recording: return False, ""
            self.is_recording, last, self.recording_current_path = False, self.recording_current_path, ""
            if self._rec_queue is not None:
                try: self._rec_queue.put_nowait(None)
                except Exception: pass
            self._sync_state_file()
            return True, last

    def toggle_recording(self) -> Tuple[bool, str]:
        return (False, self.stop_recording()[1]) if self.is_recording else (True, self.start_recording())

    def _recording_worker(self):
        sr, max_b = getattr(self, "_rec_samplerate", 48000), getattr(self, "_rec_max_bytes", None) or REC_MAX_FILE_BYTES
        def _open_w(fp: str):
            _ensure_audio_backends()
            if sf is not None: return sf.SoundFile(str(fp), mode="w", samplerate=sr, channels=2, subtype="PCM_16", format="WAV")
            import wave
            wf = wave.open(str(fp), "wb"); wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr); return wf
        try: cf, cb = _open_w(self.recording_current_path), 0
        except Exception: self.is_recording = False; return
        while True:
            try: chunk = self._rec_queue.get(timeout=0.2)
            except Exception:
                if not self.is_recording and (self._rec_queue is None or self._rec_queue.empty()): break
                continue
            if chunk is None: break
            if (cl := len(chunk)) <= 0: continue
            ch_b = cl * 4
            if cb + ch_b >= max_b:
                try: cf.close()
                except Exception: pass
                with self._rec_lock:
                    self._rec_part_index += 1
                    self.recording_current_path = str(self._rec_dir / f"{self._rec_base_stem}_pt{self._rec_part_index:02d}.wav")
                try: cf, cb = _open_w(self.recording_current_path), 0
                except Exception: break
            try:
                if sf is not None and isinstance(cf, sf.SoundFile): cf.write(chunk)
                else: cf.writeframes(np.clip(chunk * 32767.0, -32768, 32767).astype(np.int16).tobytes())
                cb += ch_b; self.recording_bytes_written += ch_b; self.recording_duration_sec += cl / float(sr)
            except Exception: pass
        if cf:
            try: cf.close()
            except Exception: pass
        self._sync_state_file()

    def get_mini_visualizer(self) -> str:
        if self.state != "playing": return "·······"
        step = max(1, self.num_bands // 8)
        return "".join(prism_level_glyph(int(self.smoothed_levels[i] * 8)) for i in range(0, self.num_bands, step)[:8])

    def get_status_dict(self) -> Dict[str, Any]:
        pct = round((self.position_sec / self.duration_sec * 100.0), 1) if self.duration_sec > 0 else 0.0
        now = time.time()
        if self.bt_router and (not self._cached_bt_info or now - self._last_bt_query > 1.0):
            try: self._cached_bt_info, self._last_bt_query = self.bt_router.get_status(), now
            except Exception: pass
        bt = self._cached_bt_info if self.bt_router else {}
        is_bt, bt_dev, bt_c = bool(bt.get("bluetooth_connected", False)), str(bt.get("bluetooth_device", "")), str(bt.get("bluetooth_codec", ""))
        bt_c_sfx = f" {bt_c}" if bt_c else ""
        cur_out = f"{bt_dev} [Bluetooth{bt_c_sfx}]" if (is_bt and bt_dev) else str(self.output_device_name or "")
        return {
            "running": True, "state": str(self.state), "mode": str(self.mode), "index": int(self.current_index),
            "total_tracks": len(self.playlist), "title": str(self.current_track["name"] if self.current_track else "No Track Loaded"),
            "path": str(self.current_track["path"] if self.current_track else ""), "position_sec": round(float(self.position_sec), 2),
            "duration_sec": round(float(self.duration_sec), 2), "position_fmt": format_seconds(self.position_sec),
            "duration_fmt": format_seconds(self.duration_sec), "progress_pct": float(pct), "volume": int(self.volume * 100),
            "pitch_percent": int(self.pitch_percent), "pitch_factor": round(float(self.pitch_factor), 3), "muted": bool(self.muted),
            "shuffle": bool(self.shuffle), "repeat": str(self.repeat_mode), "sample_rate": int(self.sample_rate),
            "recording": bool(self.is_recording), "recording_file": str(self.recording_current_path),
            "recording_bytes": int(self.recording_bytes_written), "recording_duration": round(float(self.recording_duration_sec), 2),
            "queue_len": len(self.play_queue), "queue": [t.get("path") for t in self.play_queue if isinstance(t, dict)],
            "output_rate": int(self.output_rate or 0), "output_device": cur_out,
            "bluetooth_connected": is_bt, "bluetooth_device": bt_dev, "bluetooth_codec": bt_c,
            "bluetooth_auto_route": bool(getattr(self, "auto_bluetooth", True)), "audio_error": str(self.stream_error or ""),
            "channels": int(self.channels), "mini_eq": self.get_mini_visualizer(),
            "levels": np.round(self.smoothed_levels, 3).tolist(), "peaks": np.round(self.peaks, 3).tolist(),
            "levels_left": np.round(self.smoothed_levels_left, 3).tolist(), "levels_right": np.round(self.smoothed_levels_right, 3).tolist(),
            "peaks_left": np.round(self.peaks_left, 3).tolist(), "peaks_right": np.round(self.peaks_right, 3).tolist(),
            "waveform": np.round(self.recent_mono_buffer[::7][:80], 3).tolist(),
            "rms_level": round(float(self.rms_level), 4), "peak_db": round(float(self.peak_db), 1), "pid": os.getpid(),
            "eq_preset": str(self.eq_manager.active_preset),
            "eq_bands": [round(float(x), 1) for x in self.eq_manager.get_current_bands()],
            "eq_is_flat": bool(self.eq_manager.is_flat()),
            "eq_presets": self.eq_manager.get_all_preset_names(),
        }

    def set_eq_preset(self, name: str) -> bool:
        ok = self.eq_manager.apply_preset(name)
        self.eq_filter.set_gains(self.eq_manager.get_current_bands(), self.sample_rate)
        self._sync_state_file()
        return ok

    def set_eq_band(self, index: int, gain_db: float, step: bool = False) -> bool:
        ok = self.eq_manager.set_band(index, gain_db, step=step)
        self.eq_filter.set_gains(self.eq_manager.get_current_bands(), self.sample_rate)
        self._sync_state_file()
        return ok

    def set_eq_bands(self, gains: Sequence[float]) -> bool:
        ok = self.eq_manager.set_bands(gains)
        self.eq_filter.set_gains(self.eq_manager.get_current_bands(), self.sample_rate)
        self._sync_state_file()
        return ok

    def save_eq_preset(self, name: str, gains: Optional[Sequence[float]] = None) -> bool:
        ok = self.eq_manager.save_custom_preset(name, gains)
        self.eq_filter.set_gains(self.eq_manager.get_current_bands(), self.sample_rate)
        self._sync_state_file()
        return ok

    def delete_eq_preset(self, name: str) -> bool:
        ok = self.eq_manager.delete_custom_preset(name)
        self.eq_filter.set_gains(self.eq_manager.get_current_bands(), self.sample_rate)
        self._sync_state_file()
        return ok

class PlayerIPCServer:
    def __init__(self, engine: AudioEngine): self.engine, self.running, self.sock = engine, True, None

    def start(self):
        if hasattr(socket, "AF_UNIX"):
            SOCKET_PATH.unlink(missing_ok=True)
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.bind(str(SOCKET_PATH))
        else:
            PORT_FILE.unlink(missing_ok=True)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.bind(("127.0.0.1", 0))
            PORT_FILE.write_text(str(self.sock.getsockname()[1]))
        self.sock.listen(10); self.sock.setblocking(False)
        PID_FILE.write_text(str(os.getpid()))
        threading.Thread(target=self._server_loop, daemon=True).start()
        threading.Thread(target=self._state_sync_loop, daemon=True).start()

    def _server_loop(self):
        while self.running:
            try:
                if select.select([self.sock], [], [], 0.2)[0]:
                    conn, _ = self.sock.accept()
                    threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception: pass

    def _handle_client(self, conn: socket.socket):
        try:
            conn.settimeout(2.0)
            if not (data := conn.recv(4096).decode('utf-8')): return
            req, e, res = json.loads(data), self.engine, {"status": "ok"}
            cmd = req.get("cmd")
            if cmd == "status": res["data"] = e.get_status_dict()
            elif cmd == "play":
                pos = float(req.get("position", 0.0) or 0.0)
                if f := req.get("file"):
                    def _l(tf, p):
                        for i, t in enumerate(e.playlist):
                            if t["path"] == tf or t["name"] == os.path.basename(tf):
                                e.load_track(i, True, start_position=p)
                                return
                        e.playlist.insert(0, {"name": os.path.basename(tf), "path": tf, "size_mb": 0, "mtime": time.time(), "ext": os.path.splitext(tf)[1][1:].upper()})
                        e.load_track(0, True, start_position=p)
                    threading.Thread(target=_l, args=(f, pos), daemon=True).start()
                else:
                    if pos > 0: e.seek(pos)
                    e.play()
            elif cmd == "pause": e.pause()
            elif cmd in ("toggle", "play_pause"): e.toggle_play_pause(); res["state"] = e.state
            elif cmd in ("stop", "quit"):
                try:
                    if e.current_track and e.current_track.get("path"):
                        saved_pos = round(float(e.position_sec), 2)
                        if saved_pos <= 0.0 and RESUME_STATE_FILE.is_file():
                            try:
                                prev = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
                                if prev.get("path") == str(e.current_track.get("path")):
                                    prev_pos = float(prev.get("position_sec", 0.0))
                                    if prev_pos > 0.0:
                                        saved_pos = prev_pos
                            except Exception: pass
                        res_tmp = RESUME_STATE_FILE.with_suffix(".tmp")
                        res_tmp.write_text(json.dumps({
                            "path": str(e.current_track.get("path")),
                            "position_sec": saved_pos,
                            "duration_sec": round(float(e.duration_sec), 2),
                            "title": str(e.current_track.get("name", "")),
                            "mode": str(e.mode),
                            "player": "mp_audio_player",
                            "timestamp": time.time()
                        }), encoding="utf-8")
                        res_tmp.replace(RESUME_STATE_FILE)
                except Exception: pass
                e.stop_playback(reset_position=False); self.running = False
                for p in (STATE_FILE, SOCKET_PATH, PORT_FILE, PID_FILE): p.unlink(missing_ok=True)
                conn.sendall(json.dumps(res).encode('utf-8')); conn.close(); os._exit(0)
            elif cmd == "next": threading.Thread(target=e.next_track, daemon=True).start()
            elif cmd == "prev": threading.Thread(target=e.prev_track, daemon=True).start()
            elif cmd == "seek": e.seek_relative(float(req.get("seconds", 10.0)))
            elif cmd == "seek_to": e.seek(float(req.get("position", 0.0)))
            elif cmd == "set_volume": e.set_volume(int(req.get("volume", 85)))
            elif cmd == "vol_up": e.change_volume(int(req.get("step", 5)))
            elif cmd == "vol_down": e.change_volume(-int(req.get("step", 5)))
            elif cmd in ("pitch_up", "pitch_down", "set_pitch", "reset_pitch"):
                if cmd == "pitch_up": e.change_pitch(int(req.get("step", 1)))
                elif cmd == "pitch_down": e.change_pitch(-int(req.get("step", 1)))
                elif cmd == "set_pitch": e.set_pitch(int(req.get("percent", 0)))
                else: e.reset_pitch()
                res.update(pitch_percent=e.pitch_percent, pitch_factor=e.pitch_factor)
            elif cmd == "mute": e.toggle_mute(); res["muted"] = e.muted
            elif cmd == "shuffle": e.toggle_shuffle(); res["shuffle"] = e.shuffle
            elif cmd == "repeat": e.cycle_repeat(); res["repeat"] = e.repeat_mode
            elif cmd in ("record", "toggle_record"):
                ir, rf = e.toggle_recording(); res.update(recording=ir, recording_file=rf)
            elif cmd == "start_record": res.update(recording=True, recording_file=e.start_recording())
            elif cmd == "stop_record": res.update(recording=False, recording_file=e.stop_recording()[1])
            elif cmd == "select_index": threading.Thread(target=e.load_track, args=(int(req.get("index", 0)), True), daemon=True).start()
            elif cmd == "queue":
                f = req.get("file") or req.get("track")
                res.update(e.queue_track(f) if f else {"queued": False, "queue_len": len(e.play_queue)})
            elif cmd == "get_queue": res["queue"] = q = e.get_queue(); res["queue_len"] = len(q)
            elif cmd == "clear_queue": res["cleared"] = e.clear_queue()
            elif cmd == "get_playlist": res["playlist"] = [{"index": i, "name": t["name"], "path": t["path"], "ext": t["ext"]} for i, t in enumerate(e.playlist[:100])]
            elif cmd in ("open_file_manager", "reveal"):
                t = choose_file_manager_target(req.get("file") or (e.current_track.get("path") if e.current_track else ""))
                res["success"] = bool(t) and open_in_file_manager(t)
            elif cmd in ("route_bluetooth", "switch_bluetooth"):
                if e.bt_router: res.update(routed=e.bt_router.route_to_bluetooth(), bluetooth=e.bt_router.get_status())
                else: res.update(status="error", message="Bluetooth router not available")
            elif cmd in ("revert_audio", "fallback_audio"):
                if e.bt_router: res.update(reverted=e.bt_router.route_to_fallback(), bluetooth=e.bt_router.get_status())
                else: res.update(status="error", message="Bluetooth router not available")
            elif cmd == "bluetooth_status": res["bluetooth"] = e.bt_router.get_status() if e.bt_router else {"bluetooth_connected": False}
            elif cmd == "toggle_bluetooth_auto":
                if e.bt_router: e.auto_bluetooth = e.bt_router.auto_switch = not getattr(e, "auto_bluetooth", True); res["auto_switch"] = e.auto_bluetooth
                else: res["status"] = "error"
            elif cmd == "set_mode": e.mode = res["mode"] = str(req.get("mode", "MIX_ARCHIVE")).upper()
            elif cmd == "get_eq":
                res.update(preset=e.eq_manager.active_preset, bands=e.eq_manager.get_current_bands(), presets=e.eq_manager.get_all_preset_names(), is_flat=e.eq_manager.is_flat())
            elif cmd == "set_eq_preset":
                ok = e.set_eq_preset(req.get("preset", "Flat"))
                res.update(success=ok, preset=e.eq_manager.active_preset, bands=e.eq_manager.get_current_bands())
            elif cmd == "set_eq_band":
                idx, gain = int(req.get("band", 0)), float(req.get("gain", 0.0))
                ok = e.set_eq_band(idx, gain, step=bool(req.get("step", False)))
                res.update(success=ok, preset=e.eq_manager.active_preset, bands=e.eq_manager.get_current_bands())
            elif cmd == "set_eq_bands":
                ok = e.set_eq_bands(req.get("bands", []))
                res.update(success=ok, preset=e.eq_manager.active_preset, bands=e.eq_manager.get_current_bands())
            elif cmd == "save_eq_preset":
                ok = e.save_eq_preset(req.get("name", "Custom"), req.get("bands"))
                res.update(success=ok, preset=e.eq_manager.active_preset, presets=e.eq_manager.get_all_preset_names())
            elif cmd == "delete_eq_preset":
                ok = e.delete_eq_preset(req.get("name", ""))
                res.update(success=ok, presets=e.eq_manager.get_all_preset_names())
            elif cmd == "reset_eq":
                e.set_eq_preset("Flat")
                res.update(success=True, preset="Flat", bands=e.eq_manager.get_current_bands())
            elif cmd == "load_playlist":
                pl, mode, pl_p, fn = req.get("playlist", []), str(req.get("mode", "MUSIC")).upper(), req.get("playlist_path"), req.get("folder_name")
                if not pl:
                    if mode == "MUSIC" or pl_p or fn: pl, mode = MusicFolderPlaylistScanner(fn or "ALL", pl_p or "").get_mixes(), "MUSIC"
                    else: pl, mode = MixArchiveScanner(get_base_dir()).get_mixes(), "MIX_ARCHIVE"
                e.playlist, e.mode = pl, mode
                if pl and req.get("play", False): e.load_track(0, True)
                res.update(loaded=len(pl), mode=e.mode)
            elif cmd in ("generate_spek", "spek"):
                tf = req.get("file") or (e.current_track.get("path") if e.current_track else (e.playlist[0].get("path") if e.playlist else None))
                if tf:
                    ok, sr = generate_track_spek(tf, mode=e.mode)
                    res.update(success=ok, spek_path=sr if ok else "")
                    if not ok: res.update(status="error", message=sr)
                else: res.update(status="error", message="No track available for Spek generation")
            conn.sendall(json.dumps(res, default=float).encode('utf-8'))
        except Exception as err:
            try: conn.sendall(json.dumps({"status": "error", "message": str(err)}).encode('utf-8'))
            except Exception: pass
        finally:
            try: conn.close()
            except Exception: pass

    def _state_sync_loop(self):
        while self.running:
            self.engine._sync_state_file()
            time.sleep(0.04 if self.engine.state == "playing" else 0.25)

def _cleanup_stale_daemon_files():
    for p in (PID_FILE, SOCKET_PATH, PORT_FILE): p.unlink(missing_ok=True)
    try: STATE_FILE.write_text(json.dumps({"running": False, "state": "stopped"}), encoding="utf-8")
    except OSError: pass

def send_ipc_command(cmd: str, **kwargs) -> Optional[Dict[str, Any]]:
    use_unix = hasattr(socket, "AF_UNIX") and SOCKET_PATH.exists()
    if not use_unix and not PORT_FILE.exists(): return None
    for _ in range(4):
        try:
            s = socket.socket(socket.AF_UNIX if use_unix else socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.5)
            s.connect(str(SOCKET_PATH) if use_unix else ("127.0.0.1", int(PORT_FILE.read_text().strip())))
            s.sendall(json.dumps({"cmd": cmd, **kwargs}).encode('utf-8'))
            raw = s.recv(65536).decode('utf-8'); s.close()
            if raw: return json.loads(raw)
        except (ConnectionRefusedError, FileNotFoundError): break
        except Exception: time.sleep(0.08)
    return None

def is_player_daemon_running() -> bool:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if sys.platform == "win32":
                import ctypes
                k = ctypes.WinDLL("kernel32", use_last_error=True)
                if h := k.OpenProcess(0x1000, False, pid):
                    ec = ctypes.c_ulong(); ok = k.GetExitCodeProcess(h, ctypes.byref(ec)); k.CloseHandle(h)
                    if ok and ec.value == 259: return True
            else:
                os.kill(pid, 0)
                cp = Path(f"/proc/{pid}/cmdline")
                if not cp.exists() or any(x in cp.read_text(errors="ignore") for x in ("MP_Audio_Player", "python")): return True
        except (OSError, ValueError): pass
    if hasattr(socket, "AF_UNIX") and SOCKET_PATH.exists():
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(0.8); s.connect(str(SOCKET_PATH)); s.close(); return True
        except (ConnectionRefusedError, FileNotFoundError): SOCKET_PATH.unlink(missing_ok=True)
        except Exception: return True
    elif not hasattr(socket, "AF_UNIX") and PORT_FILE.exists():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(0.8); s.connect(("127.0.0.1", int(PORT_FILE.read_text().strip()))); s.close(); return True
        except (ConnectionRefusedError, OSError): PORT_FILE.unlink(missing_ok=True)
        except Exception: return True
    return False

def _existing_audio_path(raw: Optional[str]) -> str:
    """Return the first real file named by a player argument.

    A broken launcher can stuff several paths into one argument, separated by
    newlines. Playing that whole string misses the playlist and starts a
    second mix at index 0.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    lines = [ln.strip().strip("'\"") for ln in text.replace("\r", "\n").split("\n")]
    ordered = lines + ([] if text in lines else [text])
    seen = set()
    for cand in ordered:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return ""

def _acquire_daemon_lock() -> bool:
    """Keep a single playback daemon. A second daemon would overwrite the shared status file and the playlist would flicker."""
    global _DAEMON_LOCK_FH
    try:
        fh = open(DAEMON_LOCK_FILE, "a+", encoding="utf-8")
    except OSError:
        return True
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False
    try:
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
    except OSError:
        pass
    _DAEMON_LOCK_FH = fh
    return True

def _release_daemon_lock() -> None:
    global _DAEMON_LOCK_FH
    fh, _DAEMON_LOCK_FH = _DAEMON_LOCK_FH, None
    if not fh:
        return
    try:
        fh.close()
    except OSError:
        pass

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False

def _audio_player_daemon_pids() -> List[int]:
    me = os.getpid()
    found: List[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == me:
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except OSError:
            continue
        if "MP_Audio_Player" in cmd and "--daemon" in cmd:
            found.append(pid)
    return found

def _choose_daemon_owner(pids: List[int], prefer_pid: Optional[int] = None, pid_file_pid: Optional[int] = None, ipc_pid: Optional[int] = None) -> Optional[int]:
    alive = [int(p) for p in pids if _pid_alive(p)]
    if not alive:
        return None
    for cand in (prefer_pid, pid_file_pid, ipc_pid):
        try:
            if cand is not None and int(cand) in alive:
                return int(cand)
        except (TypeError, ValueError):
            continue
    return min(alive)

def _retire_extra_player_daemons(prefer_pid: Optional[int] = None) -> None:
    """Stop every playback daemon except the one the visible player is using.

    Each daemon rewrites mp_player_state.json. The playlist follows that file,
    so two daemons make the highlight and the now-playing row swap every frame.
    SIGKILL skips the daemon's exit handler, which would otherwise delete the
    socket and pid file still used by the daemon we keep.
    """
    pids = _audio_player_daemon_pids()
    if prefer_pid and int(prefer_pid) == os.getpid():
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        return
    if len(pids) <= 1:
        return
    pid_file_pid = None
    if PID_FILE.is_file():
        try:
            pid_file_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid_file_pid = None
    ipc_pid = None
    status = send_ipc_command("status")
    if status and isinstance(status.get("data"), dict):
        try:
            ipc_pid = int(status["data"].get("pid") or 0) or None
        except (TypeError, ValueError):
            ipc_pid = None
    owner = _choose_daemon_owner(pids, prefer_pid, pid_file_pid, ipc_pid)
    for pid in pids:
        if pid != owner:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_WIN_CONSOLE = None

@functools.lru_cache(maxsize=4096)
def _char_display_width(ch: str) -> int:
    return 0 if (ch in ("\ufe0e", "\ufe0f") or unicodedata.combining(ch)) else (2 if ord(ch) >= 0x1F000 or unicodedata.east_asian_width(ch) in ("W", "F") else 1)

@functools.lru_cache(maxsize=2048)
def _display_width(text: str) -> int:
    return sum(_char_display_width(c) for c in _ANSI_RE.sub("", text))

def _clip_display(text: str, max_cols: int) -> str:
    if max_cols <= 0: return ""
    if _display_width(text) <= max_cols: return text
    out, cols, i, n = [], 0, 0, len(text)
    while i < n:
        if text[i] == "\033" and (m := _ANSI_RE.match(text, i)):
            out.append(m.group(0)); i = m.end(); continue
        w = _char_display_width(text[i])
        if cols + w > max_cols: break
        out.append(text[i]); cols += w; i += 1
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
        h, k, m = msvcrt.get_osfhandle(sys.stdout.fileno()), ctypes.WinDLL("kernel32", use_last_error=True), ctypes.c_uint32()
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

def _strip_bold_ansi(s: str) -> str:
    def repl(m):
        codes = [c for c in m.group(1).split(";") if c != "1"]
        return f"\033[{';'.join(codes)}m" if codes else ""
    return re.sub(r"\033\[([0-9;]*)m", repl, s)

def _present_frame(lines: List[str], width: int, height: int):
    usable = max(1, width - 1)
    if os.environ.get("MP_LIQUID_GLASS"):
        lines = [_strip_bold_ansi(l) for l in lines]
    clipped = [_clip_display(l, usable) + "\033[K" for l in lines[:height]]
    clipped.extend(["\033[K"] * (height - len(clipped)))
    body = "\n".join(clipped)
    sys.stdout.write(f"\033[?2026h\033[?7l\033[H{body}\033[?2026l")
    sys.stdout.flush()

_THEME_PALETTES = {
    "stream_of_frequency": {"highlight": "\033[38;2;0;242;255m", "active": "\033[38;2;76;217;123m", "border": "\033[38;2;48;49;131m", "accent": "\033[38;2;245;237;106m"},
    "dynamic_rainbow_liquid_glass": {"highlight": "\033[38;2;176;88;255m", "active": "\033[38;2;255;45;142m", "border": "\033[38;2;176;88;255m", "accent": "\033[38;2;0;242;254m"},
    "dreamworlds_liquid": {"highlight": "\033[38;2;0;245;255m", "active": "\033[38;2;199;125;255m", "border": "\033[38;2;72;149;239m", "accent": "\033[38;2;0;245;212m"},
    "cosmic_supernova": {"highlight": "\033[38;2;224;86;253m", "active": "\033[38;2;0;245;212m", "border": "\033[38;2;224;86;253m", "accent": "\033[38;2;76;201;240m"},
    "dreamworlds_neon": {"highlight": COLOR_ELECTRIC_CYAN, "active": COLOR_NEON_PINK, "border": COLOR_NEON_PINK, "accent": COLOR_ELECTRIC_CYAN},
    "retro_studio": {"highlight": "\033[38;2;241;196;15m", "active": "\033[38;2;230;126;34m", "border": "\033[38;2;241;196;15m", "accent": "\033[38;2;243;156;18m"},
    "cyber_neon": {"highlight": "\033[38;2;76;201;240m", "active": "\033[38;2;255;0;85m", "border": "\033[38;2;76;201;240m", "accent": "\033[38;2;255;0;85m"},
    "phosphor": {"highlight": "\033[38;2;57;255;20m", "active": "\033[38;2;166;255;0m", "border": "\033[38;2;57;255;20m", "accent": "\033[38;2;0;255;102m"},
    "ice_cold": {"highlight": "\033[38;2;0;229;255m", "active": "\033[38;2;136;192;208m", "border": "\033[38;2;0;229;255m", "accent": "\033[38;2;129;161;193m"},
    "retro_terminal": {"highlight": "\033[1;37m", "active": "\033[1;37m", "border": "\033[1;37m", "accent": "\033[1;37m"},
    "cosmic_dreamworlds_radioactive": {"highlight": "\033[38;2;57;255;20m", "active": "\033[38;2;0;245;212m", "border": "\033[38;2;57;255;20m", "accent": "\033[38;2;166;77;255m"},
    "cosmic_dreamworlds": {"highlight": "\033[38;2;232;13;104m", "active": "\033[38;2;0;245;212m", "border": "\033[38;2;232;13;104m", "accent": "\033[38;2;176;88;255m"},
    "orbital_void_reflux": {"highlight": "\033[38;2;0;240;255m", "active": "\033[38;2;255;0;127m", "border": "\033[38;2;0;240;255m", "accent": "\033[38;2;157;78;221m"},
    "sensorium_interface": {"highlight": "\033[38;2;0;245;255m", "active": "\033[38;2;240;168;216m", "border": "\033[38;2;0;245;255m", "accent": "\033[38;2;184;72;196m"},
}
_DEFAULT_PALETTE = {"highlight": COLOR_HOT_PURPLE, "active": COLOR_NEON_PINK, "border": COLOR_HOT_PURPLE, "accent": COLOR_ELECTRIC_CYAN}

_THEME_ALIASES = {
    "stream_of_frequency": "stream_of_frequency",
    "stream_of_frequency_theme": "stream_of_frequency",
    "stream of frequency": "stream_of_frequency",
    "stream-of-frequency": "stream_of_frequency",
    "stream": "stream_of_frequency",
    "frequency": "stream_of_frequency",
    "sof": "stream_of_frequency",
    "frequency_stream": "stream_of_frequency",
    "unix_terminal": "retro_terminal", "retro_unix": "retro_terminal", "white_on_black": "retro_terminal", "old_style_unix": "retro_terminal", "terminal": "retro_terminal", "classic": "retro_terminal",
    "cosmic": "cosmic_supernova", "supernova": "cosmic_supernova",
    "cyberpunk": "cyber_neon", "cyber": "cyber_neon",
    "matrix": "phosphor", "nord": "ice_cold", "dracula": "dreamworlds_neon", "gruvbox": "retro_studio",
    "dreamworlds": "dreamworlds_ultra", "default": "dreamworlds_ultra", "mplanetarian": "dreamworlds_ultra",
    "dynamic_rainbow_liquid_glass": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_rainbow": "dynamic_rainbow_liquid_glass",
    "dynamic_rainbow": "dynamic_rainbow_liquid_glass",
    "rainbow_liquid_glass": "dynamic_rainbow_liquid_glass",
    "rainbow": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_[rainbow_colours]_(new)": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_[rainbow_colours]": "dynamic_rainbow_liquid_glass",
    "dynamic liquid glass [rainbow colours] (new)": "dynamic_rainbow_liquid_glass",
    "dynamic liquid glass [rainbow colours]": "dynamic_rainbow_liquid_glass",
    "mp_dreamworlds_liquid_transparency": "dreamworlds_liquid", "dreamworlds_liquid_transparency": "dreamworlds_liquid",
    "liquid_transparency": "dreamworlds_liquid", "liquid": "dreamworlds_liquid", "glass": "dreamworlds_liquid",
    "liquid_glass": "dreamworlds_liquid", "mp_liquid": "dreamworlds_liquid"
}

class EqualizerVisualizer:
    STYLES = [
        "stream_of_frequency_eq",
        "stereo_eq",
        "neon_prism_eq",
        "stardust_particles_eq",
        "master_spectrum",
        "analog_vu",
        "oscilloscope",
    ]
    STYLE_NAMES = {
        "stream_of_frequency_eq": "Stream of Frequency (Dynamic Spectrogram)",
        "stereo_eq": "Dual Stereo (12-Band)",
        "neon_prism_eq": "Neon Chroma Prism (Thin Hi-Res)",
        "stardust_particles_eq": "Stardust Chroma (Thin Lines & Falling Dust)",
        "master_spectrum": "Master Spectrum (24-Band)",
        "analog_vu": "Analog Studio VU",
        "oscilloscope": "Oscilloscope Waveform",
    }
    THEMES = [
        "stream_of_frequency",
        "dreamworlds_ultra",
        "dynamic_rainbow_liquid_glass",
        "cosmic_supernova",
        "dreamworlds_liquid",
        "dreamworlds_neon",
        "retro_studio",
        "cyber_neon",
        "phosphor",
        "ice_cold",
        "retro_terminal",
        "cosmic_dreamworlds_radioactive",
        "cosmic_dreamworlds",
        "orbital_void_reflux",
        "sensorium_interface",
    ]
    THEME_NAMES = {
        "stream_of_frequency": "Stream of Frequency [Special Edition]",
        "dreamworlds_ultra": "Dreamworlds Ultra",
        "dynamic_rainbow_liquid_glass": "Dynamic Liquid Glass [Rainbow Colours] (New)",
        "cosmic_supernova": "Cosmic Supernova",
        "dreamworlds_liquid": "MP Dreamworlds Liquid Transparency",
        "dreamworlds_neon": "Dreamworlds Neon",
        "retro_studio": "Retro Studio",
        "cyber_neon": "Cyber Neon",
        "phosphor": "Phosphor",
        "ice_cold": "Ice Cold",
        "retro_terminal": "Retro Terminal",
        "cosmic_dreamworlds_radioactive": "Cosmic Dreamworlds Radioactive (Liquid Glass Skin)",
        "cosmic_dreamworlds": "Cosmic Dreamworlds (Liquid Glass Skin)",
        "orbital_void_reflux": "Orbital Void Reflux (Liquid Glass Skin)",
        "sensorium_interface": "Sensorium Interface (Liquid Glass Skin)",
    }

    def __init__(self, default_style: Optional[str] = None, default_theme: Optional[str] = None, theme: Optional[str] = None, style: Optional[str] = None):
        _ensure_numpy()
        self.style_idx = self.theme_idx = 0
        self.dust_particles, self.last_dust_update, self.dust_rng = [], time.time(), random.Random()
        self._sof_buffer, self._sof_particles, self._sof_last_time, self._sof_rng = None, [], time.time(), random.Random()
        try:
            th_file = CONFIG_DIR / "theme"
            if saved := (theme or default_theme or (th_file.read_text(encoding="utf-8").strip().lower() if th_file.is_file() else None)):
                self.set_theme(saved)
        except Exception: pass
        try:
            eq_file = CONFIG_DIR / "eq_style"
            ts = style or default_style
            if ts and ts in self.STYLES: self.style_idx = self.STYLES.index(ts)
            elif ts and str(ts).lower() in ("stream", "stream_of_frequency", "stream_of_frequency_eq", "frequency_stream", "frequency_stream_eq", "spectrogram", "dynamic_spectrogram", "river", "rainbow_stream"):
                self.style_idx = self.STYLES.index("stream_of_frequency_eq")
            elif eq_file.is_file():
                seq = eq_file.read_text(encoding="utf-8").strip().lower()
                if seq in self.STYLES: self.style_idx = self.STYLES.index(seq)
                elif seq in ("stream", "stream_of_frequency", "stream_of_frequency_eq", "frequency_stream", "frequency_stream_eq", "spectrogram", "dynamic_spectrogram", "river", "rainbow_stream"):
                    self.style_idx = self.STYLES.index("stream_of_frequency_eq")
                elif seq in ("neon", "prism", "chroma", "neon_prism"): self.style_idx = self.STYLES.index("neon_prism_eq")
                elif seq in ("stardust", "particles", "dust", "falling_dust", "stardust_eq", "chroma_dust"): self.style_idx = self.STYLES.index("stardust_particles_eq")
        except Exception: pass

    @property
    def style(self) -> str: return self.STYLES[self.style_idx]
    @property
    def theme(self) -> str: return self.THEMES[self.theme_idx]
    @theme.setter
    def theme(self, name: str): self.set_theme(name)

    @property
    def b_col(self) -> str:
        return f"{BOLD}{self.get_theme_palette().get('border', COLOR_HOT_PURPLE)}"

    def set_theme(self, name: str):
        c = _THEME_ALIASES.get(str(name).strip().lower(), str(name).strip().lower())
        if c in self.THEMES:
            self.theme_idx = self.THEMES.index(c)
            if c == "stream_of_frequency":
                self.style_idx = self.STYLES.index("stream_of_frequency_eq")

    def cycle_style(self):
        self.style_idx = (self.style_idx + 1) % len(self.STYLES)
        try: (CONFIG_DIR / "eq_style").write_text(self.style, encoding="utf-8")
        except Exception: pass

    def cycle_theme(self):
        self.theme_idx = (self.theme_idx + 1) % len(self.THEMES)
        try: (CONFIG_DIR / "theme").write_text(self.theme, encoding="utf-8")
        except Exception: pass

    def get_style_display_name(self) -> str: return self.STYLE_NAMES.get(self.style, self.style.replace("_", " ").title())
    def get_theme_display_name(self) -> str: return self.THEME_NAMES.get(self.theme, self.theme.replace("_", " ").title())
    def get_theme_palette(self) -> Dict[str, str]: return _THEME_PALETTES.get(self.theme, _DEFAULT_PALETTE)

    def _base_theme_rgb(self, c_frac: float, ultra_floor: float = 0.10) -> Tuple[float, float, float]:
        t = self.theme
        if t in ("stream_of_frequency", "stream", "frequency"):
            if c_frac < 0.25:
                s = c_frac / 0.25
                return 0.19 * (1.0 - s), 0.19 + 0.76 * s, 0.51 + 0.49 * s
            if c_frac < 0.50:
                s = (c_frac - 0.25) / 0.25
                return 0.0 + 0.30 * s, 0.95 - 0.10 * s, 1.0 - 0.52 * s
            if c_frac < 0.75:
                s = (c_frac - 0.50) / 0.25
                return 0.30 + 0.66 * s, 0.85 + 0.08 * s, 0.48 - 0.07 * s
            s = (c_frac - 0.75) / 0.25
            return 0.96 - 0.02 * s, 0.93 - 0.80 * s, 0.41 - 0.28 * s
        if t in ("sensorium_interface", "sensorium", "sensorium interface"):
            if c_frac < 0.33:
                s = c_frac / 0.33
                return 0.0 + 0.94 * s, 0.96 - 0.30 * s, 1.0 - 0.15 * s
            if c_frac < 0.66:
                s = (c_frac - 0.33) / 0.33
                return 0.94 - 0.22 * s, 0.66 - 0.38 * s, 0.85 - 0.08 * s
            s = (c_frac - 0.66) / 0.34
            return 0.72 - 0.26 * s, 0.28 + 0.30 * s, 0.77 - 0.33 * s
        if t in ("orbital_void_reflux", "orbital_void", "void_reflux", "orbital"):
            if c_frac < 0.50:
                s = c_frac / 0.50
                return 0.61 * s, 0.94 - 0.63 * s, 1.0 - 0.13 * s
            s = (c_frac - 0.50) / 0.50
            return 0.61 + 0.39 * s, 0.31 * (1.0 - s), 0.87 - 0.37 * s
        if t in ("cosmic_dreamworlds", "cosmic_dream", "cosmic_dreamworld"):
            if c_frac < 0.33:
                s = c_frac / 0.33
                return 0.0 + 0.69 * s, 0.96 - 0.61 * s, 0.83 + 0.17 * s
            if c_frac < 0.66:
                s = (c_frac - 0.33) / 0.33
                return 0.69 + 0.22 * s, 0.35 - 0.30 * s, 1.0 - 0.59 * s
            s = (c_frac - 0.66) / 0.34
            return 0.91 + 0.09 * s, 0.05 + 0.84 * s, 0.41 - 0.16 * s
        if t in ("cosmic_dreamworlds_radioactive", "radioactive", "cosmic_radioactive"):
            if c_frac < 0.40:
                s = c_frac / 0.40
                return 0.22 * (1.0 - s), 1.0 - 0.04 * s, 0.08 + 0.75 * s
            s = (c_frac - 0.40) / 0.60
            return 0.65 * s, 0.96 - 0.66 * s, 0.83 + 0.17 * s
        if t == "cosmic_supernova":
            if c_frac < 0.25: s = c_frac / 0.25; return 0.0, 0.96 - 0.17 * s, 0.83 + 0.11 * s
            if c_frac < 0.55: s = (c_frac - 0.25) / 0.30; return 0.30 + 0.58 * s, 0.79 - 0.45 * s, 0.94 + 0.05 * s
            if c_frac < 0.80: s = (c_frac - 0.55) / 0.25; return 0.88 + 0.12 * s, 0.34 - 0.14 * s, 0.99 - 0.59 * s
            s = (c_frac - 0.80) / 0.20; return 1.0, 0.20 - 0.10 * s, 0.40 - 0.25 * s
        if t in ("dreamworlds_liquid", "liquid_transparency", "mp_dreamworlds_liquid_transparency"):
            if c_frac < 0.33: s = c_frac / 0.33; return 0.0, 0.96 - 0.16 * s, 1.0
            if c_frac < 0.66: s = (c_frac - 0.33) / 0.33; return 0.28 * s, 0.80 - 0.31 * s, 1.0 - 0.06 * s
            s = (c_frac - 0.66) / 0.34; return 0.28 + 0.50 * s, 0.49 * (1.0 - s), 0.94 + 0.06 * s
        if t in ("dreamworlds_ultra", "dreamworlds"):
            h6 = ((c_frac * 0.88 + 0.82) % 1.0) * 6.0
            i, f = int(h6), h6 - int(h6)
            q, u = 1.0 - f, ultra_floor
            return ((1.0, f, u), (q, 1.0, u), (u, 1.0, f), (u, q, 1.0), (f, u, 1.0), (1.0, u, q))[i % 6]
        if t in ("dynamic_rainbow_liquid_glass", "dynamic_liquid_glass_rainbow", "dynamic_rainbow", "rainbow"):
            h6 = ((c_frac * 0.88 + 0.85) % 1.0) * 6.0
            i, f = int(h6), h6 - int(h6)
            q, u = 1.0 - f, ultra_floor
            return ((1.0, f, u), (q, 1.0, u), (u, 1.0, f), (u, q, 1.0), (f, u, 1.0), (1.0, u, q))[i % 6]
        if t == "dreamworlds_neon":
            if c_frac < 0.33: s = c_frac / 0.33; return 0.0, 0.90 - 0.50 * s, 1.0
            if c_frac < 0.66: s = (c_frac - 0.33) / 0.33; return 0.70 * s + 0.20, 0.10, 1.0 - 0.20 * s
            s = (c_frac - 0.66) / 0.34; return 1.0, 0.15 + 0.40 * s, 0.50 - 0.50 * s
        if t == "retro_studio":
            if c_frac < 0.5: s = c_frac / 0.5; return 0.10 + 0.70 * s, 0.85 + 0.15 * s, 0.20 - 0.15 * s
            s = (c_frac - 0.5) / 0.5; return 0.90 + 0.10 * s, 0.85 - 0.60 * s, 0.10
        if t == "cyber_neon": return 0.45 + 0.50 * math.sin(c_frac * math.pi), 0.10 + 0.70 * c_frac, 0.95 - 0.20 * c_frac
        if t == "phosphor": return 0.10 * (1.0 - c_frac), 0.95, 0.20
        if t == "retro_terminal": return 1.0, 1.0, 1.0
        return 0.10 + 0.75 * (c_frac ** 1.5), 0.50 + 0.45 * c_frac, 1.0

    def _get_neon_prism_color(self, c_frac: float, r_frac: float, is_peak: bool = False, is_cap: bool = False) -> str:
        if is_peak:
            return "\033[38;2;255;255;255m\033[1m" if r_frac > 0.85 else ("\033[38;2;255;235;120m\033[1m" if r_frac > 0.5 else "\033[38;2;0;255;255m\033[1m")
        r, g, b = self._base_theme_rgb(c_frac, 0.10)
        if is_cap and r_frac > 0.70:
            r, g, b = min(1.0, r * 1.25 + 0.15), min(1.0, g * 1.25 + 0.15), min(1.0, b * 1.25 + 0.15)
        else:
            v = 0.62 + 0.38 * r_frac
            r, g, b = r * v, g * v, b * v
        return f"\033[38;2;{int(r*255)};{int(g*255)};{int(b*255)}m"

    def _get_stardust_rgb(self, c_frac: float, r_frac: float, is_peak: bool = False, is_sparkle: bool = False) -> Tuple[int, int, int]:
        if is_sparkle: return (255, 255, 255) if r_frac > 0.75 else (255, 235, 140)
        if is_peak: return (255, 255, 255) if r_frac > 0.85 else ((255, 235, 120) if r_frac > 0.50 else (0, 255, 255))
        r, g, b = (0.10 + 0.75 * (c_frac ** 1.5), 0.50 + 0.45 * c_frac, 1.0) if self.theme == "retro_terminal" else self._base_theme_rgb(c_frac, 0.08)
        v = (0.58 + 0.42 * r_frac) * 255.0
        return int(min(255, max(0, r * v))), int(min(255, max(0, g * v))), int(min(255, max(0, b * v)))

    def _get_stardust_color(self, c_frac: float, r_frac: float, is_peak: bool = False, is_sparkle: bool = False) -> str:
        r, g, b = self._get_stardust_rgb(c_frac, r_frac, is_peak, is_sparkle)
        return f"\033[38;2;{r};{g};{b}m"

    def _resample_bands(self, ll: np.ndarray, lr: np.ndarray, pl: np.ndarray, pr: np.ndarray, n: int):
        if len(ll) <= 1: z = np.zeros(n); return z, z, z, z
        xi, xo = np.linspace(0.0, 1.0, len(ll)), np.linspace(0.0, 1.0, n)
        bl, br = np.interp(xo, xi, ll), np.interp(xo, xi, lr)
        return bl, br, (np.interp(xo, xi, pl) if len(pl) > 1 else bl), (np.interp(xo, xi, pr) if len(pr) > 1 else br)

    def _format_freq_labels(self, ch_w: int) -> str:
        freqs_wide = ["30", "60", "125", "250", "500", "1k", "2k", "4k", "8k", "12k", "16k", "18k"]
        freqs_narrow = ["32", "64", "125", "250", "500", "1k", "4k", "16k"]
        freqs = freqs_wide if ch_w >= 40 else freqs_narrow
        tot = sum(len(f) for f in freqs)
        if ch_w <= tot + len(freqs):
            s = " ".join(freqs)
            return f"{s:<{ch_w}s}"[:ch_w]
        rem = ch_w - tot
        gaps = len(freqs) + 1
        base = rem // gaps
        extra = rem % gaps
        parts = []
        for i, f in enumerate(freqs):
            pad = base + (1 if i < extra else 0)
            parts.append(" " * pad + f)
        rem_end = ch_w - sum(len(p) for p in parts)
        res = "".join(parts) + " " * rem_end
        return f"{res:<{ch_w}s}"[:ch_w]

    def _stereo_footer(self, ch_w_l: Union[int, bool] = 36, ch_w_r: Optional[int] = None) -> List[str]:
        if isinstance(ch_w_l, bool):
            is_wide = ch_w_l
            ch_w_l = 43 if is_wide else 36
            ch_w_r = 43 if is_wide else 36
        elif ch_w_r is None:
            ch_w_r = ch_w_l
        lbl = f"│{self._format_freq_labels(ch_w_l)}│{self._format_freq_labels(ch_w_r)}│"
        bot = f"╰{'─' * ch_w_l}┴{'─' * ch_w_r}╯"
        return [f"  {self.b_col}{lbl}{NC}", f"  {self.b_col}{bot}{NC}"]

    def render_neon_prism_eq(self, levels_l: np.ndarray, levels_r: np.ndarray, peaks_l: np.ndarray, peaks_r: np.ndarray, width: int = 80, height: int = 7, rms: float = 0.0, peak_db: float = -60.0) -> List[str]:
        target_iw = max(20, width - 6 if width >= 26 else width - 4)
        ch_w_l = (target_iw - 1) // 2
        ch_w_r = target_iw - 1 - ch_w_l
        n = max(16, (ch_w_l - 2) // 2)
        bl, br, pl, pr = self._resample_bands(levels_l, levels_r, peaks_l, peaks_r, n)
        is_beat = rms > 0.13 or peak_db > -5.0
        bolt = "\033[1;38;2;255;255;255m" if is_beat else ("\033[1;38;2;255;215;0m" if rms > 0.07 else COLOR_HOT_PURPLE)
        div = "\033[1;38;2;247;37;133m" if is_beat else self.b_col
        lh = f"── {bolt}⚡{NC}{self.b_col} LEFT ({n}-BAND NEON PRISM) "
        rh = f"── {bolt}⚡{NC}{self.b_col} RIGHT ({n}-BAND NEON PRISM) "
        hdr = f"╭{lh}{'─' * max(0, ch_w_l - _display_width(lh))}┬{rh}{'─' * max(0, ch_w_r - _display_width(rh))}╮"
        lines = [f"  {self.b_col}{hdr}{NC}"]
        for r in range(height - 1, -1, -1):
            rf = (r + 1) / float(height)
            def _side(bands, pks, ch_w):
                rem = max(0, ch_w - n * 2)
                l_pad = rem // 2
                r_pad = rem - l_pad
                pts = []
                for c in range(n):
                    frac, cf, pk = bands[c] * height - r, c / float(max(1, n - 1)), pks[c] if c < len(pks) else 0.0
                    if frac >= 1.0: col, ch = self._get_neon_prism_color(cf, rf, is_cap=(frac < 2.0)), "█"
                    elif frac > 0.0: col, ch = self._get_neon_prism_color(cf, rf, is_cap=True), prism_level_glyph(max(1, min(8, int(frac * 8))))
                    elif int(round(pk * height)) == r:
                        col = "\033[38;2;255;255;255m\033[1m" if pk >= 0.90 else self._get_neon_prism_color(cf, rf, is_peak=True)
                        ch = prism_peak_glyph(pk >= 0.90, c)
                    else: ch = " "
                    pts.append(f"{col}{ch}{NC} " if ch != " " else "  ")
                return (" " * l_pad) + "".join(pts) + (" " * r_pad)
            lines.append(f"  {self.b_col}│{NC}{_side(bl, pl, ch_w_l)}{div}│{NC}{_side(br, pr, ch_w_r)}{self.b_col}│{NC}")
        return lines + self._stereo_footer(ch_w_l, ch_w_r)

    def render_stardust_particles_eq(self, levels_l: np.ndarray, levels_r: np.ndarray, peaks_l: np.ndarray, peaks_r: np.ndarray, width: int = 80, height: int = 7, rms: float = 0.0, peak_db: float = -60.0) -> List[str]:
        target_iw = max(20, width - 6 if width >= 26 else width - 4)
        ch_w_l = (target_iw - 1) // 2
        ch_w_r = target_iw - 1 - ch_w_l
        min_w = min(ch_w_l, ch_w_r)
        n = max(16, (min_w - 2) // 2)
        bl, br, pl, pr = self._resample_bands(levels_l, levels_r, peaks_l, peaks_r, n)
        now, is_beat = time.time(), (rms > 0.13 or peak_db > -5.0)
        scol = "\033[1;38;2;255;255;255m" if is_beat else ("\033[1;38;2;255;215;0m" if rms > 0.07 else COLOR_HOT_PURPLE)
        div = "\033[1;38;2;247;37;133m" if is_beat else self.b_col
        spark = console_symbol("✦")
        m_l = max(0, (ch_w_l - (2 * n - 1)) // 2)
        m_r = max(0, (ch_w_r - (2 * n - 1)) // 2)
        col_map_l = [min(ch_w_l - 1, m_l + b * 2) for b in range(n)]
        col_map_r = [min(ch_w_r - 1, m_r + b * 2) for b in range(n)]
        lt = f"LEFT ({n}-BAND CHROMA STARDUST)"
        rt = f"RIGHT ({n}-BAND CHROMA STARDUST)"
        lh = f"── {scol}{spark}{NC}{self.b_col} {lt} "; lh += "─" * max(0, ch_w_l - _display_width(lh))
        rh = f"── {scol}{spark}{NC}{self.b_col} {rt} "; rh += "─" * max(0, ch_w_r - _display_width(rh))
        lines = [f"  {self.b_col}╭{lh}┬{rh}╮{NC}"]

        for ch_idx, (bands, pks, ch_w, col_map) in enumerate(((bl, pl, ch_w_l, col_map_l), (br, pr, ch_w_r, col_map_r))):
            for b in range(n):
                val, pk = float(bands[b]), float(pks[b]) if b < len(pks) else float(bands[b])
                if val > 0.15 and self.dust_rng.random() < val * 0.40:
                    sym = self.dust_rng.choice(stardust_dust_choices("hot" if (val > 0.70 or pk > 0.85) else ("mid" if val > 0.35 else "low")))
                    self.dust_particles.append({
                        "ch": ch_idx, "x": float(col_map[b]) + self.dust_rng.uniform(-0.4, 0.4), "y": float(min(height - 1, val * height)) + self.dust_rng.uniform(0.1, 0.8),
                        "vx": self.dust_rng.uniform(-0.5, 0.5), "vy": self.dust_rng.uniform(0.7, 1.8), "symbol": sym,
                        "color_rgb": self._get_stardust_rgb(b / float(n - 1), min(1.0, val), is_sparkle=(val > 0.75)),
                        "life": self.dust_rng.uniform(1.8, 3.8), "max_life": 3.8, "sway_freq": self.dust_rng.uniform(1.8, 3.6),
                        "sway_amp": self.dust_rng.uniform(0.3, 0.8), "twinkle_phase": self.dust_rng.uniform(0.0, 6.28), "twinkle_speed": self.dust_rng.uniform(3.0, 9.0)
                    })

        if is_beat and len(self.dust_particles) < 70:
            for _ in range(self.dust_rng.randint(2, 4)):
                rb = self.dust_rng.randint(0, n - 1)
                rf, cf = min(1.0, max(0.2, float(bl[rb]))), rb / float(n - 1)
                tch = self.dust_rng.choice([0, 1])
                tcm = col_map_l if tch == 0 else col_map_r
                self.dust_particles.append({
                    "ch": tch, "x": float(tcm[rb]) + self.dust_rng.uniform(-0.6, 0.6),
                    "y": float(min(height - 1, bl[rb] * height + self.dust_rng.uniform(0.5, 1.5))), "vx": self.dust_rng.uniform(-0.8, 0.8), "vy": self.dust_rng.uniform(0.6, 1.5),
                    "symbol": self.dust_rng.choice(stardust_dust_choices("hot")),
                    "color_rgb": (255, 255, 255) if self.dust_rng.random() < 0.4 else self._get_stardust_rgb(cf, rf, is_sparkle=True),
                    "life": self.dust_rng.uniform(2.0, 4.0), "max_life": 4.0, "sway_freq": self.dust_rng.uniform(2.0, 4.0),
                    "sway_amp": self.dust_rng.uniform(0.5, 1.1), "twinkle_phase": self.dust_rng.uniform(0.0, 6.28), "twinkle_speed": self.dust_rng.uniform(5.0, 12.0)
                })

        if len(self.dust_particles) > 75: self.dust_particles = self.dust_particles[-75:]
        dt, self.last_dust_update, alive = max(0.005, min(0.10, now - self.last_dust_update)), now, []
        for p in self.dust_particles:
            p["life"] -= dt
            if p["life"] > 0.0:
                p_cw = ch_w_l if p.get("ch", 0) == 0 else ch_w_r
                p["x"] = max(0.0, min(float(p_cw - 1), p["x"] + (p["vx"] + math.sin(now * p["sway_freq"] + p["twinkle_phase"]) * p["sway_amp"]) * dt))
                p["y"] -= p["vy"] * dt
                if p["y"] >= 0.0: alive.append(p)
        self.dust_particles = alive

        c_grids = []
        for ch_idx, (bands, pks, ch_w, col_map) in enumerate(((bl, pl, ch_w_l, col_map_l), (br, pr, ch_w_r, col_map_r))):
            gc, gcol = [[" "] * ch_w for _ in range(height)], [[""] * ch_w for _ in range(height)]
            for b in range(n):
                col, cf, val = col_map[b], b / float(n - 1), float(bands[b])
                hv, pk_val = val * height, float(pks[b]) if b < len(pks) else val
                cr, rem = int(hv), hv - int(hv)
                pk_r = min(height - 1, max(0, int(round(pk_val * height)))) if pk_val > 0.08 else -1
                for r in range(height):
                    rf = (r + 1) / float(height)
                    if r < cr: gc[r][col], gcol[r][col] = "│", self._get_stardust_color(cf, rf)
                    elif r == cr and rem > 0.05:
                        gc[r][col], gcol[r][col] = ("│" if rem > 0.65 else (console_symbol("╵") if rem > 0.25 else "·")), self._get_stardust_color(cf, rf)
                    elif r == pk_r:
                        gc[r][col] = console_symbol("✦") if pk_val >= 0.85 else (console_symbol("✧") if pk_val >= 0.50 else "·")
                        gcol[r][col] = "\033[1;38;2;255;255;255m" if pk_val >= 0.85 else self._get_stardust_color(cf, rf, is_peak=True)

            for p in self.dust_particles:
                if p["ch"] != ch_idx: continue
                pr_i, pc_i = int(round(p["y"])), int(round(p["x"]))
                if not (0 <= pr_i < height and 0 <= pc_i < ch_w): continue
                lr_rat, tw = max(0.0, min(1.0, p["life"] / p["max_life"])), math.sin(now * p["twinkle_speed"] + p["twinkle_phase"])
                if tw > 0.78 and lr_rat > 0.25:
                    p_col = "\033[1;38;2;255;255;255m"
                    p_sym = (p["symbol"] if p["symbol"] in ("•", "°", "·", "˙", "+") else "•") if _use_limited_console_glyphs() else (p["symbol"] if p["symbol"] in ("✦", "✧", "⋆", "•") else "✦")
                else:
                    rc, gc_v, bc = p["color_rgb"]
                    fade = lr_rat * (0.60 + 0.40 * max(0.0, tw)) * (0.6 if pr_i == 0 else 1.0)
                    p_col = f"\033[38;2;{max(20, min(255, int(rc * fade)))};{max(20, min(255, int(gc_v * fade)))};{max(20, min(255, int(bc * fade)))}m"
                    p_sym = console_symbol(p["symbol"])
                    if lr_rat < 0.20 and p_sym in ("✦", "✧", "•", "°"): p_sym = "·"
                if gc[pr_i][pc_i] == " " or (p_sym in ("✦", "✧", "⋆") and tw > 0.78): gc[pr_i][pc_i], gcol[pr_i][pc_i] = p_sym, p_col
                else:
                    for off in (1, -1):
                        if 0 <= pc_i + off < ch_w and gc[pr_i][pc_i + off] == " ": gc[pr_i][pc_i + off], gcol[pr_i][pc_i + off] = p_sym, p_col; break
            c_grids.append((gc, gcol))

        (gl_c, gl_col), (gr_c, gr_col) = c_grids
        for r in range(height - 1, -1, -1):
            ls = "".join(f"{gl_col[r][c]}{gl_c[r][c]}{NC}" if gl_c[r][c] != " " else " " for c in range(ch_w_l))
            rs = "".join(f"{gr_col[r][c]}{gr_c[r][c]}{NC}" if gr_c[r][c] != " " else " " for c in range(ch_w_r))
            lines.append(f"  {self.b_col}│{NC}{ls}{div}│{NC}{rs}{self.b_col}│{NC}")
        return lines + self._stereo_footer(ch_w_l, ch_w_r)

    def _get_bar_color(self, fraction: float) -> str:
        t = self.theme
        if t in ("stream_of_frequency", "stream", "frequency"):
            return "\033[38;2;0;242;255m" if fraction < 0.30 else ("\033[38;2;76;217;123m" if fraction < 0.60 else ("\033[38;2;245;237;106m" if fraction < 0.85 else "\033[38;2;240;32;24m"))
        if t == "cosmic_supernova":
            return "\033[38;2;0;245;212m" if fraction < 0.35 else ("\033[38;2;76;201;240m" if fraction < 0.65 else ("\033[38;2;224;86;253m" if fraction < 0.85 else "\033[38;2;255;51;102m"))
        if t in ("dreamworlds_liquid", "liquid_transparency", "mp_dreamworlds_liquid_transparency"):
            return "\033[38;2;0;245;255m" if fraction < 0.45 else ("\033[38;2;0;245;212m" if fraction < 0.75 else "\033[38;2;199;125;255m")
        if t in ("dynamic_rainbow_liquid_glass", "dynamic_liquid_glass_rainbow", "dynamic_rainbow", "rainbow"):
            return "\033[38;2;0;242;254m" if fraction < 0.40 else ("\033[38;2;255;215;0m" if fraction < 0.70 else ("\033[38;2;255;45;142m" if fraction < 0.90 else "\033[38;2;176;88;255m"))
        if t in ("dreamworlds_ultra", "dreamworlds"): return COLOR_TRAFFIC_GREEN if fraction < 0.60 else (COLOR_TRAFFIC_AMBER if fraction < 0.85 else COLOR_TRAFFIC_RED)
        if t == "dreamworlds_neon": return "\033[38;2;0;229;255m" if fraction < 0.4 else ("\033[38;2;247;37;133m" if fraction < 0.75 else "\033[38;2;255;140;0m")
        if t == "retro_studio": return "\033[38;2;46;204;113m" if fraction < 0.6 else ("\033[38;2;241;196;15m" if fraction < 0.85 else "\033[38;2;231;76;60m")
        if t == "cyber_neon": return "\033[38;2;114;9;183m" if fraction < 0.5 else "\033[38;2;76;201;240m"
        if t == "phosphor": return "\033[38;2;57;255;20m"
        return "\033[38;2;30;144;255m" if fraction < 0.5 else "\033[38;2;224;255;255m"

    def render_stereo_eq(self, levels_l: np.ndarray, levels_r: np.ndarray, peaks: np.ndarray, width: int = 80, height: int = 7) -> List[str]:
        target_iw = max(20, width - 6 if width >= 26 else width - 4)
        ch_w_l = (target_iw - 1) // 2
        ch_w_r = target_iw - 1 - ch_w_l
        min_w = min(ch_w_l, ch_w_r)
        if min_w >= 50: n = 16
        elif min_w >= 38: n = 12
        else: n = 8
        bl, br, pl, pr = self._resample_bands(levels_l, levels_r, peaks, peaks, n)

        def _calc_widths(ch_w: int) -> List[int]:
            base_bw = ch_w // n
            rem = ch_w % n
            return [base_bw + (1 if i < rem else 0) for i in range(n)]

        widths_l = _calc_widths(ch_w_l)
        widths_r = _calc_widths(ch_w_r)

        lt = f"LEFT CHANNEL ({n}-BAND)"
        rt = f"RIGHT CHANNEL ({n}-BAND)"
        lh = f"── {lt} "; lh += "─" * max(0, ch_w_l - _display_width(lh))
        rh = f"── {rt} "; rh += "─" * max(0, ch_w_r - _display_width(rh))
        hdr = f"╭{lh}┬{rh}╮"
        lines = [f"  {self.b_col}{hdr}{NC}"]

        def _render_channel_row(bands, pks, widths, r):
            pts = []
            for c in range(n):
                w_c = widths[c]
                pk = pks[c % len(pks)] if len(pks) > 0 else 0.0
                ch = meter_level_char(bands[c] * height - r, int(pk * height) == r)
                if w_c <= 2:
                    pts.append(f"{ch} " if w_c == 2 else ch)
                elif w_c == 3:
                    pts.append(f" {ch} ")
                else:
                    bar_w = 2
                    pad_tot = w_c - bar_w
                    pl = pad_tot // 2
                    pr = pad_tot - pl
                    pts.append((" " * pl) + (ch * bar_w) + (" " * pr))
            return "".join(pts)

        for r in range(height - 1, -1, -1):
            col = self._get_bar_color(r / float(height))
            ls = _render_channel_row(bl, pl, widths_l, r)
            rs = _render_channel_row(br, pr, widths_r, r)
            lines.append(f"  {self.b_col}│{NC}{col}{ls}{NC}{self.b_col}│{NC}{col}{rs}{NC}{self.b_col}│{NC}")
        return lines + self._stereo_footer(ch_w_l, ch_w_r)

    def render_master_spectrum(self, levels: np.ndarray, peaks: np.ndarray, width: int = 80, height: int = 7) -> List[str]:
        target_iw = max(20, width - 6 if width >= 26 else width - 4)
        num_bars = max(16, (target_iw - 2) // 3)
        hdr = "── HIGH-RESOLUTION MASTER FREQUENCY SPECTRUM (30Hz - 18kHz) "
        top_line = f"  {self.b_col}╭{hdr}{'─' * max(0, target_iw - _display_width(hdr))}╮{NC}"
        bot_line = f"  {self.b_col}╰{'─' * target_iw}╯{NC}"
        lines = [top_line]
        if len(levels) > 1:
            xo, xn = np.linspace(0, 1, len(levels)), np.linspace(0, 1, num_bars)
            il = np.interp(xn, xo, levels)
            ip = np.interp(xn, xo, peaks) if len(peaks) > 1 else np.zeros(num_bars)
        else:
            il = ip = np.zeros(num_bars)
        avail = target_iw - 2
        bar_span = num_bars * 3
        pad_tot = max(0, avail - bar_span)
        pad_l = 1 + pad_tot // 2
        pad_r = target_iw - pad_l - bar_span

        for r in range(height - 1, -1, -1):
            col = self._get_bar_color(r / float(height))
            rc = [f"{meter_level_char(val * height - r, int(ip[c] * height) == r)*2} " for c, val in enumerate(il)]
            lines.append(f"  {self.b_col}│{NC}{' ' * pad_l}{col}{''.join(rc)}{NC}{' ' * pad_r}{self.b_col}│{NC}")

        peak_str = f"PEAK HOLD {console_symbol('✦')}"
        rem_w = max(10, target_iw - _display_width(peak_str) - 4)
        fl = self._format_freq_labels(rem_w)
        ftr_mid = f"  {fl}  {peak_str}"
        ftr_pad = max(0, target_iw - _display_width(ftr_mid))
        lines.append(f"  {self.b_col}│{NC}{DIM}{CYAN}{ftr_mid}{' ' * ftr_pad}{NC}{self.b_col}│{NC}")
        lines.append(bot_line)
        return lines

    def render_analog_vu(self, peak_db: float, levels_l: np.ndarray, levels_r: np.ndarray, width: int = 80) -> List[str]:
        target_iw = max(20, width - 6 if width >= 26 else width - 4)
        hdr = "── DUAL ANALOG STUDIO VU METERS (PEAK & RMS BALLISTICS) "
        top_line = f"  {self.b_col}╭{hdr}{'─' * max(0, target_iw - _display_width(hdr))}╮{NC}"
        bot_line = f"  {self.b_col}╰{'─' * target_iw}╯{NC}"
        lines = [top_line]

        blen = max(10, target_iw - 28)
        scale_raw = "-40   -30   -20   -10   -7   -5   -3   -1    0  +1  +2  +3 dB"
        scale_pfx = "  "
        scale_str = scale_pfx + scale_raw
        if _display_width(scale_str) > target_iw:
            scale_str = _clip_display(scale_str, target_iw)
        scale_pad = max(0, target_iw - _display_width(scale_str))
        lines.append(f"  {self.b_col}│{NC}{scale_str}{' ' * scale_pad}{self.b_col}│{NC}")

        for name, val in (("LEFT  CHANNEL", np.mean(levels_l) if len(levels_l) else 0.0), ("RIGHT CHANNEL", np.mean(levels_r) if len(levels_r) else 0.0)):
            filled = int(val * blen)
            meter = "".join(f"{self._get_bar_color(i / blen)}█{NC}" if i < filled else f"{DIM}░{NC}" for i in range(blen))
            clip_s = f"{BOLD}{RED}[CLIP]{NC}" if filled >= blen - 1 else f"{DIM}[SAFE]{NC}"
            row_content = f"  {BOLD}{CYAN}{name}{NC} [{meter}] {clip_s}"
            row_pad = max(0, target_iw - _display_width(row_content))
            lines.append(f"  {self.b_col}│{NC}{row_content}{' ' * row_pad}{self.b_col}│{NC}")

        info_str = f"  Peak Audio Level: {BOLD}{YELLOW}{peak_db:+6.1f} dBFS{NC}  │  Master Headroom: {BOLD}{GREEN}{max(0.0, -peak_db):5.1f} dB{NC}"
        if _display_width(info_str) > target_iw:
            info_str = _clip_display(info_str, target_iw)
        info_pad = max(0, target_iw - _display_width(info_str))
        lines.append(f"  {self.b_col}│{NC}{info_str}{' ' * info_pad}{self.b_col}│{NC}")
        lines.append(bot_line)
        return lines

    def render_oscilloscope(self, levels: np.ndarray, status: Optional[Dict[str, Any]] = None, width: int = 80, height: int = 5) -> List[str]:
        st = status or {}
        target_iw = max(20, width - 6 if width >= 26 else width - 4)
        iw = max(16, target_iw - 4)
        hdr = "── DYNAMIC OSCILLOSCOPE AUDIO WAVEFORM "
        top_l = f"  {self.b_col}╭{hdr}{'─' * max(0, target_iw - _display_width(hdr))}╮{NC}"
        bot_l = f"  {self.b_col}╰{'─' * target_iw}╯{NC}"

        hh, state, rms, pm = max(1, height // 2), st.get("state", "stopped"), float(st.get("rms_level", 0.0)), max(0.5, min(2.0, 1.0 + int(st.get("pitch_percent", 0)) / 100.0))
        now, wf_arr, xd = time.time(), np.array(st.get("waveform", []), dtype=float), np.linspace(0.0, 1.0, iw)
        if state == "playing":
            b_v = float(np.mean(levels[:4])) if len(levels) >= 4 else max(0.15, rms)
            m_v = float(np.mean(levels[4:14])) if len(levels) >= 14 else rms * 0.7
            t_v = float(np.mean(levels[14:])) if len(levels) >= 15 else rms * 0.4
            da = max(0.25, min(1.0, rms * 2.2 + (float(np.max(levels)) * 0.8 if len(levels) else 0.0)))
            sp = np.clip((np.sin(xd * (2.0 * math.pi) - now * 3.5 * pm) * 0.60 * max(0.2, b_v) + np.sin(xd * (4.0 * math.pi) + now * 6.0 * pm) * 0.28 * max(0.1, m_v) + np.sin(xd * (6.0 * math.pi) - now * 10.0 * pm) * 0.14 * max(0.05, t_v)) * da * 1.5, -0.98, 0.98)
            if len(wf_arr) >= 16 and float(np.max(np.abs(wf_arr))) > 0.01:
                pi = np.interp(xd, np.linspace(0.0, 1.0, len(wf_arr)), wf_arr)
                pts = np.clip(0.65 * ((pi / max(0.15, float(np.max(np.abs(pi))))) * min(1.0, max(0.25, rms * 2.0))) + 0.35 * sp, -0.98, 0.98)
            else: pts = sp
        elif state == "paused": pts = np.sin(xd * (2.0 * math.pi) + now * 1.2) * 0.18
        else: pts = np.zeros(iw)
        y_f = [float(p) * hh for p in pts]
        y_i = [max(-hh, min(hh, int(round(yf)))) for yf in y_f]
        lines, cx = [top_l], iw // 2
        pad_l = (target_iw - iw) // 2
        pad_r = target_iw - iw - pad_l
        for r in range(hh, -hh - 1, -1):
            rc = []
            for i in range(iw):
                py, cy = y_i[i - 1] if i > 0 else y_i[i], y_i[i]
                rmn, rmx = min(py, cy), max(py, cy)
                if rmn <= r <= rmx:
                    col = self._get_neon_prism_color(i / float(max(1, iw - 1)), min(1.0, abs(y_f[i]) / float(hh) * 0.85 + rms * 0.35), is_peak=(abs(cy) == hh and abs(y_f[i]) >= hh * 0.75))
                    ch = "━" if rmn == rmx else (("╱" if r in (rmn, rmx) else "│") if cy > py else ("╲" if r in (rmn, rmx) else "│"))
                    rc.append(f"{col}{BOLD}{ch}{NC}")
                else:
                    tk = (i - cx) % 10 == 0
                    rc.append(f"{DIM}{'┼' if tk else '·'}{NC}" if r == 0 else (f"{DIM}·{NC}" if tk else " "))
            lines.append(f"  {self.b_col}│{NC}{' ' * pad_l}{''.join(rc)}{' ' * pad_r}{self.b_col}│{NC}")
        return lines + [bot_l]

    def render_stream_of_frequency(self, status: Optional[Dict[str, Any]] = None, width: int = 80, height: int = 7) -> List[str]:
        st = status or {}
        inner_w = max(20, width - 6 if width >= 26 else width - 4)
        cw = max(16, inner_w - 2)
        hdr_text = "── 🌊 STREAM OF FREQUENCY (DYNAMIC SPECTROGRAM) " if inner_w >= 50 else ("── 🌊 STREAM OF FREQUENCY " if inner_w >= 32 else "── 🌊 STREAM ")
        if inner_w >= 70:
            ftr_text = "── ◄ FLOW (RIGHT ➔ LEFT) ◄ ──── 32Hz  125Hz  500Hz  2kHz  8kHz  16kHz ────"
        elif inner_w >= 36:
            ftr_text = "── ◄ FLOW (R ➔ L) ◄ ────"
        else:
            ftr_text = "── ◄ FLOW ◄ "

        top_l = f"  {self.b_col}╭{hdr_text}{'─' * max(0, inner_w - _display_width(hdr_text))}╮{NC}"
        bot_l = f"  {self.b_col}╰{ftr_text}{'─' * max(0, inner_w - _display_width(ftr_text))}╯{NC}"

        H = max(1, height)
        now = time.time()
        dt = max(0.005, min(0.08, now - getattr(self, "_sof_last_time", now)))
        self._sof_last_time = now

        state = st.get("state", "stopped")
        rms = float(st.get("rms_level", 0.0))
        peak_db = float(st.get("peak_db", -60.0))
        pitch_pct = int(st.get("pitch_percent", 0))
        speed_mult = max(0.5, min(2.0, 1.0 + pitch_pct / 100.0))

        # Audio levels
        lv = np.array(st.get("levels", [0.0] * 24), dtype=float)
        ll = np.array(st.get("levels_left", lv), dtype=float)
        lr = np.array(st.get("levels_right", lv), dtype=float)
        mono = 0.5 * (ll + lr) if len(ll) == len(lr) and len(ll) > 0 else lv
        if len(mono) < 24: mono = np.pad(mono, (0, max(0, 24 - len(mono))))

        buf_cols = max(140, cw + 40)
        if getattr(self, "_sof_buffer", None) is None or self._sof_buffer.shape[1] < buf_cols:
            self._sof_buffer = np.zeros((16, buf_cols), dtype=float)

        if state == "playing":
            interp_x = np.linspace(0.0, 1.0, 16)
            levels_x = np.linspace(0.0, 1.0, len(mono))
            slice_col = np.clip(np.interp(interp_x, levels_x, mono), 0.0, 1.0)
            if rms > 0.12 or peak_db > -4.5:
                slice_col = np.clip(slice_col * 1.25 + 0.15, 0.0, 1.0)
        elif state == "paused":
            slice_col = np.array([0.07 + 0.04 * math.sin(now * 2.2 + r * 0.4) for r in range(16)], dtype=float)
        else:
            slice_col = np.zeros(16, dtype=float)

        shift_cols = max(1, min(3, int(round(dt * 24.0 * speed_mult))))
        for _ in range(shift_cols):
            self._sof_buffer[:, :-1] = self._sof_buffer[:, 1:]
            self._sof_buffer[:, -1] = slice_col

        if getattr(self, "_sof_particles", None) is None:
            self._sof_particles = []

        if state == "playing":
            for r in range(H):
                buf_r = min(15, int(r * (16.0 / max(1, H))))
                val = float(slice_col[buf_r])
                if val > 0.05:
                    prob = min(0.85, val * 0.65 + (0.25 if (rms > 0.12 or peak_db > -4.5) else 0.0))
                    if self._sof_rng.random() < prob:
                        if r >= max(1, H - 2):
                            sym = self._sof_rng.choice(["✦", "✧", "⋆", "•", "°", "·"])
                        elif r >= max(1, H // 2):
                            sym = self._sof_rng.choice(["≈", "≋", "~", "∿", "∽", "›"])
                        else:
                            sym = self._sof_rng.choice(["≋", "≈", "█", "▓", "▒", "░", "◆"])
                        self._sof_particles.append({
                            "x": float(cw - 1) + self._sof_rng.uniform(-0.2, 0.2),
                            "base_y": float(r),
                            "y": float(r),
                            "vx": self._sof_rng.uniform(-20.0, -36.0) * speed_mult,
                            "wave_amp": self._sof_rng.uniform(0.15, 0.55),
                            "wave_freq": self._sof_rng.uniform(3.0, 7.5),
                            "wave_phase": self._sof_rng.uniform(0.0, 6.283),
                            "life": self._sof_rng.uniform(2.5, 4.5),
                            "max_life": 4.5,
                            "symbol": sym,
                            "hue_offset": self._sof_rng.uniform(0.0, 1.0),
                            "is_sparkle": (val > 0.70 or rms > 0.14)
                        })

            if (rms > 0.13 or peak_db > -4.5) and len(self._sof_particles) < 70:
                for _ in range(self._sof_rng.randint(2, 4)):
                    br = self._sof_rng.randint(0, H - 1)
                    self._sof_particles.append({
                        "x": float(cw - 1) + self._sof_rng.uniform(-0.5, 0.5),
                        "base_y": float(br),
                        "y": float(br),
                        "vx": self._sof_rng.uniform(-26.0, -42.0) * speed_mult,
                        "wave_amp": self._sof_rng.uniform(0.25, 0.70),
                        "wave_freq": self._sof_rng.uniform(4.0, 9.0),
                        "wave_phase": self._sof_rng.uniform(0.0, 6.283),
                        "life": self._sof_rng.uniform(2.8, 4.8),
                        "max_life": 4.8,
                        "symbol": "✦" if br >= H // 2 else "≋",
                        "hue_offset": self._sof_rng.uniform(0.0, 1.0),
                        "is_sparkle": True
                    })

        if len(self._sof_particles) > 75:
            self._sof_particles = self._sof_particles[-75:]

        alive = []
        for p in self._sof_particles:
            p["life"] -= dt
            if p["life"] > 0:
                p["x"] += p["vx"] * dt
                if p["x"] >= -0.8:
                    w_disp = math.sin(now * p["wave_freq"] + p["wave_phase"] - 0.22 * p["x"]) * p["wave_amp"]
                    p["y"] = max(0.0, min(float(H - 1), p["base_y"] + w_disp))
                    alive.append(p)
        self._sof_particles = alive

        # 2D Grid buffers
        grid_c = [[" "] * cw for _ in range(H)]
        grid_col = [[""] * cw for _ in range(H)]

        buf_offset = self._sof_buffer.shape[1] - cw
        for r in range(H):
            buf_r = min(15, int(r * (16.0 / max(1, H))))
            for c in range(cw):
                energy = float(self._sof_buffer[buf_r, buf_offset + c])
                if energy > 0.05:
                    h_idx = int(((now * 0.40 + (cw - 1 - c) * 0.038 + r * 0.08) % 1.0) * 360) % 360
                    if energy > 0.75:
                        col = _RAINBOW_ANSI_BOLD[h_idx]
                        glyph = "█" if energy > 0.90 else "▓"
                    elif energy > 0.45:
                        col = _RAINBOW_ANSI_BOLD[h_idx]
                        glyph = "≋" if r < max(1, H // 2) else "≈"
                    elif energy > 0.20:
                        col = _RAINBOW_ANSI_NORMAL[h_idx]
                        glyph = "≈" if r < max(1, H // 2) else "~"
                    elif energy > 0.10:
                        col = _RAINBOW_ANSI_DIM[h_idx]
                        glyph = "∿" if r < max(1, H // 2) else "∽"
                    else:
                        col = _RAINBOW_ANSI_FAINT[h_idx]
                        glyph = "·"
                    grid_c[r][c] = glyph
                    grid_col[r][c] = col

        # Overlay particles
        for p in self._sof_particles:
            pr = max(0, min(H - 1, int(round(p["y"]))))
            pc = int(round(p["x"]))
            if 0 <= pc < cw:
                p_hue = (now * 0.45 + (cw - 1 - pc) * 0.038 + p["hue_offset"]) % 1.0
                p_h_idx = int(p_hue * 360) % 360
                if p["is_sparkle"]:
                    p_col = "\033[1;38;2;255;255;255m" if self._sof_rng.random() < 0.35 else _RAINBOW_ANSI_BOLD[p_h_idx]
                else:
                    p_col = _RAINBOW_ANSI_BOLD[p_h_idx]
                grid_c[pr][pc] = console_symbol(p["symbol"])
                grid_col[pr][pc] = p_col

        # Build output lines (from top row H-1 down to bottom row 0)
        lines = [top_l]
        pad_tot = inner_w - cw
        pad_l = pad_tot // 2
        pad_r = inner_w - cw - pad_l
        for r in range(H - 1, -1, -1):
            row_str = "".join(f"{grid_col[r][c]}{grid_c[r][c]}{NC}" if grid_c[r][c] != " " else " " for c in range(cw))
            lines.append(f"  {self.b_col}│{NC}{' ' * pad_l}{row_str}{' ' * pad_r}{self.b_col}│{NC}")
        lines.append(bot_l)
        return lines

    def render_vertical_pitch_fader(self, pitch_pct: int, total_lines: int = 10) -> List[str]:
        p, frows = max(-20, min(20, int(pitch_pct))), max(3, total_lines - 2)
        has_hint = frows % 2 == 0
        tr = frows - 1 if has_hint else frows
        cr = tr // 2
        kr = cr if p == 0 else (cr - int(round((p / 20.0) * cr)) if p > 0 else cr + int(round((-p / 20.0) * (tr - 1 - cr))))
        lines = [f"{self.b_col}╭── DJ PITCH ────────────╮{NC}"]
        for r in range(tr):
            if r == kr == cr: lines.append(f"{self.b_col}│{NC} {COLOR_TRAFFIC_GREEN}[▓█0█▓]{NC} {BOLD}{COLOR_TRAFFIC_GREEN}◄ 0.0% [CENTER]{NC}{self.b_col}│{NC}")
            elif r == kr:
                kc, ts = (COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE), f"◄ {p:+d}% ({1.0 + p/100:.2f}x)"
                lines.append(f"{self.b_col}│{NC} {kc}[▓███▓]{NC} {BOLD}{kc}{ts:<14}{NC} {self.b_col}│{NC}")
            elif r == cr: lines.append(f"{self.b_col}│{NC} {COLOR_INDIGO_BLUE}─── 0 ───{NC} {DIM}{COLOR_LILAC}CENTER (0%){NC}  {self.b_col}│{NC}")
            elif r == 0: lines.append(f"{self.b_col}│{NC}    {COLOR_TRAFFIC_AMBER}▲{NC}     {DIM}+20% MAX{NC}      {self.b_col}│{NC}")
            elif r == tr - 1: lines.append(f"{self.b_col}│{NC}    {COLOR_INDIGO_BLUE}▼{NC}     {DIM}-20% MIN{NC}      {self.b_col}│{NC}")
            else: lines.append(f"{self.b_col}│{NC}    {COLOR_INDIGO_BLUE}│{NC}{' ' * 19}{self.b_col}│{NC}")
        if has_hint: lines.append(f"{self.b_col}│{NC}  {DIM}[+/-: 1% • 0: Reset]{NC}  {self.b_col}│{NC}")
        return lines + [f"{self.b_col}╰────────────────────────╯{NC}"]

    def render_horizontal_pitch_bar(self, pitch_pct: int, width: int = 36, max_cols: Optional[int] = None) -> str:
        is_lg = bool(os.environ.get("MP_LIQUID_GLASS"))
        bold_s = "" if is_lg else BOLD
        p, w = max(-20, min(20, int(pitch_pct))), max(11, width)
        if w % 2 == 0: w -= 1
        cp = w // 2
        kp = cp if p == 0 else max(0, min(w - 1, cp + int(round((p / 20.0) * cp))))
        def _trk(tw, k, c):
            return "".join(f"{bold_s}{COLOR_TRAFFIC_GREEN if p == 0 else (COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE)}●{NC}" if i == k else (f"{COLOR_TRAFFIC_GREEN}┼{NC}" if i == c else ((f"{DIM}━{NC}" if (i < k and p < 0) else (f"{COLOR_INDIGO_BLUE}━{NC}" if k <= i < c else f"{DIM}─{NC}")) if i < c else (f"{COLOR_TRAFFIC_AMBER}━{NC}" if c < i <= k else f"{DIM}─{NC}"))) for i in range(tw))
        stag = f"{bold_s}{COLOR_TRAFFIC_GREEN}0.0% [CENTER DETENT]{NC}" if p == 0 else f"{bold_s}{COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE}{p:+d}% ({1.0 + p/100:.2f}x){NC}"
        pfx, sfx = f"  {bold_s}{COLOR_HOT_PURPLE}🎚 DJ PITCH:{NC} {DIM}-20%{NC} [", f"] {DIM}+20%{NC}  {stag}  {DIM}[+/-: 1% • 0: Reset]{NC}"
        if max_cols and (_display_width(pfx) + w + _display_width(sfx) > max_cols):
            sfx = f"] {DIM}+20%{NC}  {stag}"
            if _display_width(pfx) + w + _display_width(sfx) > max_cols:
                sfx = f"] {DIM}+20%{NC}  {bold_s}{COLOR_TRAFFIC_GREEN if p == 0 else (COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE)}{p:+d}%{NC}"
            if (avail := max_cols - _display_width(pfx) - _display_width(sfx)) < w:
                w = max(7, avail)
                if w % 2 == 0: w -= 1
                cp = w // 2
                kp = cp if p == 0 else max(0, min(w - 1, cp + int(round((p / 20.0) * cp))))
        return f"{pfx}{_trk(w, kp, cp)}{sfx}"

    def render(self, status: Dict[str, Any], width: int = 80, height: int = 7) -> List[str]:
        lv, pk = np.array(status.get("levels", [0.0]*24)), np.array(status.get("peaks", [0.0]*24))
        ll, lr = np.array(status.get("levels_left", lv)), np.array(status.get("levels_right", lv))
        pl, pr = np.array(status.get("peaks_left", pk)), np.array(status.get("peaks_right", pk))
        rms, pdb, s = float(status.get("rms_level", 0.0)), float(status.get("peak_db", -60.0)), self.style
        if s == "stream_of_frequency_eq": lines = self.render_stream_of_frequency(status, width, height)
        elif s == "neon_prism_eq": lines = self.render_neon_prism_eq(ll, lr, pl, pr, width, height, rms, pdb)
        elif s == "stardust_particles_eq": lines = self.render_stardust_particles_eq(ll, lr, pl, pr, width, height, rms, pdb)
        elif s == "master_spectrum": lines = self.render_master_spectrum(lv, pk, width=width, height=height)
        elif s == "analog_vu": lines = self.render_analog_vu(pdb, ll, lr, width=width)
        elif s == "oscilloscope": lines = self.render_oscilloscope(lv, status, width, height)
        else: lines = self.render_stereo_eq(ll, lr, pk, width, height)
        is_lg = bool(os.environ.get("MP_LIQUID_GLASS"))
        if width >= 122 and not is_lg:
            faders = self.render_vertical_pitch_fader(int(status.get("pitch_percent", 0)), len(lines))
            pad_to = max(91, (width - 6) - 26)
            return [f"{el}{' ' * max(2, pad_to - _display_width(el))}{fl}" for el, fl in zip(lines, faders)]
        return lines

def _get_dynamic_gradient(step: float) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    return (
        (int(180 + 75 * math.sin(step * 0.6180339887 + 0.3)), int(180 + 75 * math.sin(step * 0.8408964152 + 2.1)), int(180 + 75 * math.sin(step * 0.7071067811 + 4.2))),
        (int(180 + 75 * math.sin(step * 0.6180339887 + 3.14159)), int(180 + 75 * math.sin(step * 0.8408964152 + 5.28318)), int(180 + 75 * math.sin(step * 0.7071067811 + 1.04719))),
        (int(60 + 52 * math.sin(step * 0.41 + 0.5)), int(48 + 42 * math.sin(step * 0.53 + 2.4)), int(78 + 58 * math.sin(step * 0.47 + 4.1)))
    )

def ensure_mini_player_kwin_rules():
    if not sys.platform.startswith(("linux", "freebsd")):
        return
    rc_path = Path.home() / ".config" / "kwinrulesrc"
    try:
        import configparser, uuid
        cp = configparser.ConfigParser()
        if rc_path.exists():
            cp.read(str(rc_path))
        else:
            rc_path.parent.mkdir(parents=True, exist_ok=True)
            cp.add_section("General")
            cp.set("General", "count", "0")
            cp.set("General", "rules", "")

        rules_defs = [
            ("MP Mini Audio Player (Fixed Size)", "MP Mini Audio Player"),
            ("MP Micro Audio Player (Fixed Size)", "MP Micro Audio Player")
        ]
        modified = False
        for desc, title in rules_defs:
            found_sec = None
            for sec in cp.sections():
                if cp.has_option(sec, "description") and cp.get(sec, "description") == desc:
                    found_sec = sec
                    break
            if not found_sec:
                found_sec = str(uuid.uuid4())
                cp.add_section(found_sec)
                cp.set(found_sec, "description", desc)
                cp.set(found_sec, "wmclass", "konsole")
                cp.set(found_sec, "wmclassmatch", "1")
                cp.set(found_sec, "title", title)
                cp.set(found_sec, "titlematch", "2")
                cp.set(found_sec, "types", "1")
                cp.set(found_sec, "maximizehoriz", "false")
                cp.set(found_sec, "maximizehorizrule", "2")
                cp.set(found_sec, "maximizevert", "false")
                cp.set(found_sec, "maximizevertrule", "2")
                if not cp.has_section("General"):
                    cp.add_section("General")
                count = int(cp.get("General", "count", fallback="0")) + 1
                cp.set("General", "count", str(count))
                existing = [r.strip() for r in cp.get("General", "rules", fallback="").split(",") if r.strip()]
                existing.append(found_sec)
                cp.set("General", "rules", ",".join(existing))
                modified = True
        if modified:
            with open(str(rc_path), "w", encoding="utf-8") as f:
                cp.write(f)
            if shutil.which("qdbus"):
                subprocess.run(["qdbus", "org.kde.KWin", "/KWin", "reconfigure"], capture_output=True)
            elif shutil.which("qdbus-qt6"):
                subprocess.run(["qdbus-qt6", "org.kde.KWin", "/KWin", "reconfigure"], capture_output=True)
    except Exception:
        pass

def _setup_mini_terminal_appearance():
    if sys.platform.startswith(("linux", "freebsd")):
        if (k_dir := Path.home() / ".local" / "share" / "konsole").is_dir():
            try:
                (k_dir / "MP_Mini_Player.colorscheme").write_text(
                    "[General]\nDescription=MP Mini Player\nOpacity=0.30\nBlur=true\nColorRandomization=false\nWallpaperOpacity=1\n\n"
                    "[Background]\nColor=12,14,24\nOpacity=0.30\n\n"
                    "[BackgroundFaint]\nColor=14,16,28\nOpacity=0.30\n\n"
                    "[Foreground]\nColor=240,245,255\n\n"
                    "[ForegroundFaint]\nColor=180,190,210\n\n"
                    "[ForegroundIntense]\nColor=255,255,255\n\n"
                    "[Color0]\nColor=12,14,24\n[Color1]\nColor=255,51,102\n[Color2]\nColor=0,255,180\n"
                    "[Color3]\nColor=255,200,50\n[Color4]\nColor=102,153,255\n[Color5]\nColor=190,100,255\n"
                    "[Color6]\nColor=0,229,255\n[Color7]\nColor=240,245,255\n\n"
                    "[Color0Intense]\nColor=40,45,65\n[Color1Intense]\nColor=255,80,130\n[Color2Intense]\nColor=50,255,200\n"
                    "[Color3Intense]\nColor=255,220,90\n[Color4Intense]\nColor=130,175,255\n[Color5Intense]\nColor=210,130,255\n"
                    "[Color6Intense]\nColor=80,240,255\n[Color7Intense]\nColor=255,255,255\n",
                    encoding="utf-8"
                )
                prof = k_dir / "MP_Mini_Player.profile"
                prof.write_text(
                    "[Appearance]\nColorScheme=MP_Mini_Player\nFont=Monospace,11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1,,0,0\n\n"
                    "[General]\nEnvironment=TERM=xterm-256color,COLORTERM=truecolor\nInheritContainerContext=true\nName=MP_Mini_Player\nParent=FALLBACK/\nTerminalColumns=74\nTerminalRows=14\n\n"
                    "[Scrolling]\nScrollBarPosition=0\nHistoryMode=0\n\n"
                    "[Terminal Features]\nBlinkingCursorEnabled=true\n",
                    encoding="utf-8"
                )
            except Exception: pass
        ensure_mini_player_kwin_rules()

def _build_window_cmd(mini: bool, mode: str, folder_name: str, playlist_path: str, theme: Optional[str], style: Optional[str], micro: bool = False) -> List[str]:
    cmd = [sys.executable or "python3", str(Path(__file__).resolve()), "--interactive"]
    if micro:
        cmd.append("--micro")
    elif mini:
        cmd.append("--mini")
    if mode == "MUSIC":
        cmd.append("--music-mode")
        if folder_name and folder_name != "ALL": cmd.extend(["--music-folder", str(folder_name)])
        if playlist_path: cmd.extend(["--playlist", str(playlist_path)])
    if theme: cmd.extend(["--theme", str(theme)])
    if style: cmd.extend(["--style", str(style)])
    return cmd

def _konsole_bus_call(args: List[str]) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=1.0, stdin=subprocess.DEVNULL)
        return proc.stdout or ""
    except Exception:
        return ""

def _konsole_main_window(service: str) -> str:
    for line in _konsole_bus_call(["qdbus", service]).splitlines():
        line = line.strip()
        if line.endswith("MainWindow_1") or (line.count("/") == 2 and "MainWindow" in line):
            return line
    return "/konsole/MainWindow_1"

def _konsole_pixel_size(service: str, window: str) -> Optional[Tuple[int, int]]:
    out = _konsole_bus_call(["busctl", "--user", "get-property", service, window, "org.qtproject.Qt.QWidget", "size"])
    if m := re.search(r"\(ii\)\s+(\d+)\s+(\d+)", out):
        return int(m.group(1)), int(m.group(2))
    return None

def _set_konsole_pixel_size(service: str, window: str, width: int, height: int) -> None:
    subprocess.run(
        ["busctl", "--user", "set-property", service, window, "org.qtproject.Qt.QWidget", "size", "(ii)", str(int(width)), str(int(height))],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=1.0,
    )

def resize_host_terminal(columns: int, rows: int, title: str) -> None:
    """Resize the current terminal to columns by rows and set its title.

    Wayland Konsole reports the CSI 8 size without changing the window, so the
    Micro Player was drawn in the Mini Player's 14-row frame. Measure the real
    size first, resize the Konsole window over DBus, then emit CSI 8 for other terminals.
    """
    try:
        term_c, term_r = (int(n) for n in shutil.get_terminal_size((80, 24)))
    except Exception:
        term_c, term_r = 80, 24
    service = os.environ.get("KONSOLE_DBUS_SERVICE", "")
    if service and shutil.which("qdbus") and shutil.which("busctl") and not (term_c == columns and term_r == rows):
        try:
            session = os.environ.get("KONSOLE_DBUS_SESSION", "")
            if session:
                for role in ("0", "1"):
                    subprocess.run(["qdbus", service, session, "org.kde.konsole.Session.setTitle", role, title], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=1.0)
            window = _konsole_main_window(service)
            subprocess.run(["qdbus", service, window, "org.qtproject.Qt.QWidget.setWindowTitle", title], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=1.0)
            size = _konsole_pixel_size(service, window)
            if size:
                pix_w, pix_h = size
                probe_h = max(80, pix_h + (36 if rows > term_r else -36))
                _set_konsole_pixel_size(service, window, pix_w, probe_h)
                time.sleep(0.06)
                probed = _konsole_pixel_size(service, window) or (pix_w, probe_h)
                probed_r = int(shutil.get_terminal_size((80, 24)).lines)
                if probed_r != term_r and probed[1] != pix_h:
                    cell_h = max(8, int(round((probed[1] - pix_h) / (probed_r - term_r))))
                else:
                    cell_h = 19
                chrome_h = pix_h - cell_h * term_r
                _set_konsole_pixel_size(service, window, pix_w, max(80, chrome_h + cell_h * rows))
                time.sleep(0.06)
                now_c, now_r = (int(n) for n in shutil.get_terminal_size((80, 24)))
                if now_r != rows or now_c != columns:
                    cur = _konsole_pixel_size(service, window)
                    if cur:
                        fix_h = cur[1] + (rows - now_r) * cell_h
                        fix_w = cur[0] if now_c == columns else cur[0] + (columns - now_c) * max(6, int(round(cur[0] / max(now_c, 1))))
                        _set_konsole_pixel_size(service, window, max(120, fix_w), max(80, fix_h))
        except Exception:
            pass
    try:
        if os.environ.get("KONSOLE_DBUS_SERVICE"):
            sys.stdout.write(f"\033]0;{title}\007")
        else:
            sys.stdout.write(f"\033[8;{int(rows)};{int(columns)}t\033]0;{title}\007")
        sys.stdout.flush()
    except Exception:
        pass

def launch_mini_player_window(mode: str = "MIX_ARCHIVE", folder_name: str = "ALL", playlist_path: str = "", theme: Optional[str] = None, style: Optional[str] = None, micro: bool = False) -> bool:
    title = "MP Micro Audio Player" if micro else "MP Mini Audio Player"
    t_rows = "7" if micro else "14"
    cmd = _build_window_cmd(not micro, mode, folder_name, playlist_path, theme, style, micro=micro)
    base_dir = str(get_base_dir())
    if sys.platform.startswith(("linux", "freebsd")):
        _setup_mini_terminal_appearance()
        cmd_str = " ".join(f'"{c}"' for c in cmd)
        if shutil.which("konsole") and _run_bg([
            "konsole",
            "--profile", "MP_Mini_Player",
            "--hide-menubar",
            "--hide-tabbar",
            "--separate",
            "--workdir", base_dir,
            "--qwindowtitle", title,
            "-p", f"tabtitle={title}",
            "-p", "TerminalColumns=74",
            "-p", f"TerminalRows={t_rows}",
            "-p", "ScrollBarPosition=0",
            "-e", "bash", "-c", cmd_str
        ]):
            if shutil.which("xprop"):
                def _set_hints():
                    time.sleep(0.3)
                    subprocess.run(["xprop", "-name", title, "-f", "_NET_WM_WINDOW_OPACITY", "32c", "-set", "_NET_WM_WINDOW_OPACITY", "0x4d000000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                threading.Thread(target=_set_hints, daemon=True).start()
            return True
        for term, targs in [
            ("gnome-terminal", [f"--title={title}", f"--geometry=74x{t_rows}", "--", "bash", "-c", cmd_str]),
            ("xfce4-terminal", [f"--title={title}", f"--geometry=74x{t_rows}", "--hide-menubar", "--hide-borders", "-e", f"bash -c '{cmd_str}'"]),
            ("alacritty", ["--title", title, "-o", "window.opacity=0.30", "-o", "window.dimensions.columns=74", "-o", f"window.dimensions.lines={t_rows}", "-e", "bash", "-c", cmd_str]),
            ("foot", ["-T", title, "-w", f"74x{t_rows}", "-a", "0.30", "bash", "-c", cmd_str]),
            ("xterm", ["-title", title, "-geometry", f"74x{t_rows}", "-e", "bash", "-c", cmd_str]),
            ("xdg-terminal-exec", ["bash", "-c", cmd_str])
        ]:
            if shutil.which(term) and _run_bg([term] + targs): return True
    elif sys.platform == "darwin":
        c_str = " ".join(f'\\"{a}\\"' for a in cmd)
        return _run_bg(["osascript", "-e", f'tell application "Terminal" to do script "{c_str}"'])
    elif sys.platform == "win32":
        if shutil.which("wt.exe") and _run_bg(["wt.exe", "-w", "new", "--title", title, "-p", "Command Prompt", "--size", f"74,{t_rows}"] + cmd): return True
        c_str = " ".join(f'"{a}"' for a in cmd)
        try: subprocess.Popen(f'start "{title}" {c_str}', shell=True); return True
        except Exception: pass
    return False

def launch_player_window(mode: str = "MIX_ARCHIVE", folder_name: str = "ALL", playlist_path: str = "", theme: Optional[str] = None, style: Optional[str] = None) -> bool:
    title, cmd = "MP Audio Player", _build_window_cmd(False, mode, folder_name, playlist_path, theme, style)
    if sys.platform.startswith(("linux", "freebsd")):
        if shutil.which("konsole") and _run_bg(["konsole", "--separate", "--workdir", str(Path.cwd()), "--qwindowtitle", title, "-p", f"tabtitle={title}", "-e"] + cmd): return True
        for term, targs in [("xdg-terminal-exec", cmd), ("gnome-terminal", [f"--title={title}", "--"] + cmd), ("xfce4-terminal", [f"--title={title}", "-e", " ".join(f'"{a}"' for a in cmd)]), ("alacritty", ["--title", title, "-e"] + cmd), ("foot", ["-T", title] + cmd), ("xterm", ["-title", title, "-e"] + cmd)]:
            if shutil.which(term) and _run_bg([term] + targs): return True
    elif sys.platform == "darwin":
        c_str = " ".join(f'\\"{a}\\"' for a in cmd)
        return _run_bg(["osascript", "-e", f'tell application "Terminal" to do script "{c_str}"'])
    elif sys.platform == "win32":
        if shutil.which("wt.exe") and _run_bg(["wt.exe", "-w", "new", "--title", title, "-p", "Command Prompt"] + cmd): return True
        c_str = " ".join(f'"{a}"' for a in cmd)
        try: subprocess.Popen(f'start "{title}" {c_str}', shell=True); return True
        except Exception: pass
    return False

def launch_liquid_glass_player(
    base_dir: Optional[Path] = None,
    mode: Optional[str] = None,
    folder_name: Optional[str] = None,
    playlist_path: Optional[str] = None,
    theme: Optional[str] = None,
    style: Optional[str] = None,
    mini: bool = False,
    micro: bool = False,
    no_visualizer: bool = False,
) -> bool:
    if sys.platform not in ("linux", "darwin", "win32") and not sys.platform.startswith("freebsd"):
        return False
    base = base_dir or get_base_dir()

    if sys.platform == "darwin":
        candidates = [
            base / "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
            base / "scripts" / "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
            Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
            base / "MP_Audio_Player_Liquid_Glass_macOS.py",
            base / "scripts" / "MP_Audio_Player_Liquid_Glass_macOS.py",
            Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_macOS.py",
        ]
    else:
        backend = os.environ.get("LIQUID_GLASS_BACKEND", "").strip().lower()
        if not backend:
            for cfg in (base / "config.env", CONFIG_DIR / "config.env", Path(__file__).resolve().parent / "config.env"):
                if cfg.is_file():
                    if val := parse_env_file(cfg).get("LIQUID_GLASS_BACKEND"):
                        backend = val.strip().lower()
                        break
        if not backend:
            backend = "opengl"

        if backend == "vulkan":
            candidates = [
                base / "MP_Audio_Player_Liquid_Glass.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass.py",
                base / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            ]
        else:
            candidates = [
                base / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass_OpenGL.py",
                base / "MP_Audio_Player_Liquid_Glass.py",
                base / "scripts" / "MP_Audio_Player_Liquid_Glass.py",
                Path(__file__).resolve().parent / "MP_Audio_Player_Liquid_Glass.py",
            ]

    script_path = None
    for cand in candidates:
        if cand.is_file():
            script_path = cand
            break

    if not script_path:
        return False

    cmd = [sys.executable, str(script_path)]
    if no_visualizer:
        cmd.append("--no-visualizer")
    if micro:
        cmd.append("--micro")
    elif mini:
        cmd.append("--mini")
    if str(mode or "").upper() == "MUSIC":
        cmd.append("--music-mode")
        if folder_name and str(folder_name).upper() != "ALL":
            cmd.extend(["--music-folder", str(folder_name)])
        if playlist_path:
            cmd.extend(["--playlist", str(playlist_path)])
    elif str(mode or "").upper() == "MIX_ARCHIVE":
        cmd.append("--mix-archive-mode")
    if theme:
        cmd.extend(["--theme", str(theme)])
    if style:
        cmd.extend(["--style", str(style)])

    log_dir = Path.home() / ".config" / "mix-manager"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    log_file = log_dir / "liquid_glass.log"

    extra_kwargs = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        extra_kwargs["start_new_session"] = True

    try:
        with open(log_file, "a") as log_fd:
            proc = subprocess.Popen(
                cmd,
                cwd=str(base),
                stdin=subprocess.DEVNULL,
                stdout=log_fd,
                stderr=log_fd,
                close_fds=True,
                **extra_kwargs,
            )
            return proc.pid > 0
    except Exception:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(base),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                **extra_kwargs,
            )
            return proc.pid > 0
        except Exception as exc:
            try:
                mp_log_error("MP_Audio_Player", f"Failed launching Liquid Glass player: {exc}", exc)
            except Exception:
                pass
            return False


def launch_liquid_visualizer(
    base_dir: Optional[Path] = None,
    preset: Optional[str] = None,
) -> bool:
    """Launch MP_Liquid_Visualizer in its native 1400x1400 borderless Vulkan window."""
    if sys.platform not in ("linux", "darwin", "win32") and not sys.platform.startswith("freebsd"):
        return False
    base = base_dir or get_base_dir()
    candidates = [
        base / "MP_Liquid_Visualizer.py",
        base / "scripts" / "mp_liquid_visualizer_vulkan.py",
        Path(__file__).resolve().parent / "MP_Liquid_Visualizer.py",
        Path(__file__).resolve().parent / "scripts" / "mp_liquid_visualizer_vulkan.py",
    ]
    script_path = None
    for cand in candidates:
        if cand.is_file():
            script_path = cand
            break
    if not script_path:
        return False

    cmd = [sys.executable, str(script_path)]
    if preset:
        cmd.extend(["--preset", str(preset)])

    log_dir = Path.home() / ".config" / "mix-manager"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    log_file = log_dir / "liquid_visualizer.log"

    extra_kwargs = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        extra_kwargs["start_new_session"] = True

    try:
        with open(log_file, "a") as log_fd:
            proc = subprocess.Popen(
                cmd,
                cwd=str(base),
                stdin=subprocess.DEVNULL,
                stdout=log_fd,
                stderr=log_fd,
                close_fds=True,
                **extra_kwargs,
            )
            return proc.pid > 0
    except Exception:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(base),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                **extra_kwargs,
            )
            return proc.pid > 0
        except Exception as exc:
            try:
                mp_log_error("MP_Audio_Player", f"Failed launching MP_Liquid_Visualizer: {exc}", exc)
            except Exception:
                pass
            return False

class TerminalPlayerUI:
    def __init__(self, engine: Optional[AudioEngine], scanner: Union[MixArchiveScanner, MusicFolderPlaylistScanner], is_remote: bool = False, default_style: Optional[str] = None, default_theme: Optional[str] = None, mode: str = "MIX_ARCHIVE", folder_name: str = "ALL", ui_size_mode: str = "NORMAL"):
        self.engine, self.scanner, self.is_remote = engine, scanner, is_remote
        self.mode, self.folder_name, self.ui_size_mode = str(mode or "MIX_ARCHIVE").upper(), str(folder_name or "ALL").upper(), str(ui_size_mode or "NORMAL").upper()
        self.visualizer = EqualizerVisualizer(default_style=default_style, default_theme=default_theme)
        self.eq_manager = getattr(engine, "eq_manager", None) or EqualizerManager()
        self.equalizer_hud_active = False
        self.eq_selected_band = 0
        self.eq_naming_mode = False
        self.eq_custom_name_input = ""
        self.running, self.inspector_hud_active = True, False
        self.search_mode, self.search_query, self.export_mode, self.export_path = False, "", False, ""
        self.selected_row, self.scroll_offset, self.notification_msg, self.notification_time = 0, 0, "", 0.0
        self._spek_job_running = False
        self._last_seen_bt_device = self._last_seen_bt_state = self._duration_queue = None
        self._duration_cache: Dict[str, str] = {}
        if DURATION_CACHE_FILE.exists():
            try:
                if isinstance(ld := json.loads(DURATION_CACHE_FILE.read_text(encoding="utf-8")), dict): self._duration_cache.update(ld)
            except Exception: pass
        self._duration_in_queue, self._duration_worker_started = set(self._duration_cache.keys()), False
        self.cached_status = {
            "title": "Loading...", "path": "", "state": "stopped", "position_fmt": "00:00", "duration_fmt": "00:00",
            "progress_pct": 0.0, "volume": 85, "muted": False, "shuffle": False, "repeat": "all", "mode": self.mode,
            "recording": False, "recording_file": "", "recording_bytes": 0, "recording_duration": 0.0,
            "levels": [0.0]*24, "peaks": [0.0]*24, "levels_left": [0.0]*24, "levels_right": [0.0]*24,
            "peaks_left": [0.0]*24, "peaks_right": [0.0]*24, "waveform": [0.0]*80, "rms_level": 0.0, "peak_db": -60.0
        }
        try:
            script_reward_path = Path(__file__).resolve().parent / "scripts"
            if str(script_reward_path) not in sys.path:
                sys.path.insert(0, str(script_reward_path))
            from liquid_glass_reward import is_welcomed, ensure_first_run_reward
            if not is_welcomed():
                ensure_first_run_reward(interactive=False)
                self.notification_msg = "✦ Special Reward from MPlanetarian: Liquid Glass Icon Unlocked on Desktop!"
                self.notification_time = time.time() + 6.0
        except Exception:
            pass

    def _save_duration_cache(self):
        try:
            tmp = DURATION_CACHE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._duration_cache), encoding="utf-8")
            tmp.replace(DURATION_CACHE_FILE)
        except Exception: pass

    def _start_duration_worker(self):
        if self._duration_worker_started: return
        self._duration_worker_started, self._duration_queue = True, queue.Queue()
        def _worker():
            _ensure_audio_backends()
            last_save = time.time()
            while self.running:
                try:
                    if not self._duration_queue: break
                    path, m_ref = self._duration_queue.get(timeout=0.4)
                except Exception: continue
                if path in self._duration_cache: continue
                if self.engine and getattr(self.engine, "state", "") == "playing" and is_cloud_or_remote_path(path): time.sleep(0.08)
                try:
                    if sf is not None and os.path.isfile(path):
                        if is_cloud_or_remote_path(path): time.sleep(0.12)
                        info = sf.info(path)
                        dfmt = format_seconds(info.duration)
                        self._duration_cache[path] = dfmt
                        if isinstance(m_ref, dict): m_ref.update(duration_fmt=dfmt, duration_sec=info.duration)
                        if time.time() - last_save > 5.0: self._save_duration_cache(); last_save = time.time()
                    else: self._duration_cache[path] = "00:00"
                except Exception: self._duration_cache[path] = "00:00"
                finally:
                    if self._duration_queue: self._duration_queue.task_done()
            self._save_duration_cache()
        threading.Thread(target=_worker, daemon=True).start()

    def _request_duration(self, m: Dict[str, Any]):
        if not (p := m.get("path")) or p in self._duration_cache or p in self._duration_in_queue: return
        if not self._duration_worker_started: self._start_duration_worker()
        self._duration_in_queue.add(p)
        if self._duration_queue: self._duration_queue.put((p, m))

    def _sync_mode_scanner(self, new_mode: Optional[str]):
        if not new_mode:
            return
        nm = str(new_mode).upper()
        if nm != self.mode:
            self.mode = nm
        if self.mode == "MUSIC" and isinstance(self.scanner, MixArchiveScanner):
            self.scanner = MusicFolderPlaylistScanner(folder_name=self.folder_name)
        elif self.mode == "MIX_ARCHIVE" and isinstance(self.scanner, MusicFolderPlaylistScanner):
            self.scanner = MixArchiveScanner(getattr(self.scanner, "base_dir", None) or get_base_dir())

    def _get_status(self) -> Dict[str, Any]:
        if self.is_remote:
            if STATE_FILE.exists():
                try:
                    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and data.get("title") and data.get("title") != "Loading...": self.cached_status = data
                except Exception: pass
            elif not self.cached_status.get("title") or self.cached_status.get("title") == "Loading...":
                if (res := send_ipc_command("status")) and isinstance(res.get("data"), dict): self.cached_status = res["data"]
            if self.cached_status.get("mode"): self._sync_mode_scanner(self.cached_status.get("mode"))
            if not self.equalizer_hud_active:
                if self.cached_status.get("eq_preset"): self.eq_manager.active_preset = str(self.cached_status["eq_preset"])
                if isinstance(self.cached_status.get("eq_bands"), list) and len(self.cached_status["eq_bands"]) == 10:
                    self.eq_manager.current_bands = [float(x) for x in self.cached_status["eq_bands"]]
            return self.cached_status
        st = self.engine.get_status_dict() if self.engine else self.cached_status
        if st.get("mode"): self._sync_mode_scanner(st.get("mode"))
        return st

    def _sync_initial_selection(self, status: Dict[str, Any]):
        if (cp := status.get("path")) and cp != getattr(self, "_last_path", None):
            self._last_path = cp
            if not self.search_query:
                for i, m in enumerate(self._get_active_tracks()):
                    if m["path"] == cp: self.selected_row = i; break

    def _send_cmd(self, cmd: str, **kwargs):
        if self.is_remote:
            threading.Thread(target=send_ipc_command, args=(cmd,), kwargs=kwargs, daemon=True).start()
        elif self.engine:
            e = self.engine
            mapping = {"toggle": e.toggle_play_pause, "pause": e.pause, "next": e.next_track, "prev": e.prev_track, "reset_pitch": e.reset_pitch, "mute": e.toggle_mute, "shuffle": e.toggle_shuffle, "repeat": e.cycle_repeat, "stop": e.stop_playback, "record": e.toggle_recording, "toggle_record": e.toggle_recording, "start_record": e.start_recording, "stop_record": e.stop_recording}
            if cmd in mapping: mapping[cmd]()
            elif cmd == "play":
                if f := kwargs.get("file"):
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
                if f := (kwargs.get("file") or kwargs.get("track")): e.queue_track(f)
            elif cmd == "clear_queue": e.clear_queue()
            elif cmd == "open_file_manager":
                if target := choose_file_manager_target(kwargs.get("file") or (e.current_track.get("path") if e.current_track else "")):
                    open_in_file_manager(target)

    def _get_active_tracks(self) -> List[Dict[str, Any]]: return self.scanner.get_mixes(self.search_query)

    def _render_inspector_hud(self, st: Optional[Dict[str, Any]] = None, iw: Optional[int] = None) -> List[str]:
        if st is None: st = self._get_status()
        if iw is None:
            w, _ = _win_visible_size((80, 24))
            iw = max(20, w - 6)
        tp = st.get("path", "")
        tname = st.get("title", os.path.basename(tp))
        folder = next((m.get("folder") for m in getattr(self.scanner, "mixes", []) if m.get("path") == tp and m.get("folder")), None) or self.folder_name
        is_net = tp.startswith(("\\\\", "//")) or is_cloud_or_remote_path(tp)
        msl = max(20, iw - 22)
        dt = (tname[:msl-3] + "...") if len(tname) > msl else tname
        ds = (tp[:msl-3] + "...") if len(tp) > msl else tp
        ext, sr, ch = os.path.splitext(tp)[1][1:].upper() or "FLAC", st.get("sample_rate", 44100), st.get("channels", 2)
        ch_s = "Stereo" if ch == 2 else ("Mono" if ch == 1 else f"{ch} Channels")
        b_col = f"{BOLD}{self.visualizer.get_theme_palette().get('border', COLOR_HOT_PURPLE)}"
        lines = [
            _boxed_rule("╭", "── ✦ TRACK AUDIO INSPECTOR (METADATA & HARDWARE HUD) ", "╮", iw, b_col),
        ]
        info_items = [
            (f" {BOLD}{WHITE}Track Title{NC}", dt),
            (f" {BOLD}{CYAN}Folder / Src{NC}", f"{'SMB Share' if is_net else 'Local Drive'} [{folder}] • Music Library"),
            (f" {BOLD}{CYAN}Format/Codec{NC}", f"{ext} Lossless • {sr/1000:.1f} kHz • {ch_s}"),
            (f" {BOLD}{CYAN}Time Position{NC}", f"{st.get('position_fmt','00:00')} / {st.get('duration_fmt','00:00')} ({st.get('progress_pct',0):.1f}%)"),
            (f" {BOLD}{CYAN}Volume/Pitch{NC}", f"Volume: {st.get('volume', 85)}%  │  Pitch: {st.get('pitch_percent', 0):+d}%"),
            (f" {BOLD}{CYAN}Audio Engine{NC}", f"Output Rate: {st.get('output_rate', 44100)/1000:.1f} kHz • Device: {st.get('output_device', 'Default Audio Device')}"),
            (f" {BOLD}{CYAN}{'Network Path' if is_net else 'File Path   '}{NC}", ds),
        ]
        for label, val in info_items:
            row_str = f"{label}  : {val}"
            pad = max(0, iw - _display_width(row_str))
            lines.append(f"  {b_col}│{NC}{row_str}{' ' * pad}{b_col}│{NC}")
        lines.append(_boxed_rule("╰", "── [G] Generate Spek • Press [I], [Esc], or [Enter] to Close ", "╯", iw, b_col))
        return lines

    def _render_equalizer_hud(self, st: Optional[Dict[str, Any]] = None, iw: Optional[int] = None, h: int = 24) -> List[str]:
        if st is None: st = self._get_status()
        if iw is None:
            w, _ = _win_visible_size((80, 24))
            iw = max(20, w - 6)

        cur_p = self.eq_manager.active_preset
        gains = self.eq_manager.current_bands
        sel_idx = self.eq_selected_band
        presets = self.eq_manager.get_all_preset_names()

        pal = self.visualizer.get_theme_palette()
        hl_col = pal.get("highlight", COLOR_HOT_PURPLE)
        act_col = pal.get("active", COLOR_NEON_PINK)
        b_col = f"{BOLD}{pal.get('border', COLOR_HOT_PURPLE)}"

        lines = []
        lines.append(_boxed_rule("╭", "── ✦ 10-BAND STEREO GRAPHIC EQUALIZER & PRESETS ──", "╮", iw, b_col))

        p_badge = f"{BOLD}{COLOR_TRAFFIC_GREEN}[{cur_p}]{NC}" if cur_p != "Flat" else f"{BOLD}{COLOR_ELECTRIC_CYAN}[Flat (Default)]{NC}"
        sel_freq = EQ_BAND_LABELS[sel_idx]
        sel_gain = gains[sel_idx]
        status_info = f" Active: {p_badge}  •  Selected Band: {BOLD}{COLOR_NEON_PINK}{sel_idx+1}/10 ({sel_freq}: {sel_gain:+4.1f} dB){NC}  •  Scale: -12.0 to +12.0 dB"
        sh_info = status_info if _display_width(status_info) <= iw else _clip_display(status_info, iw)
        pad = max(0, iw - _display_width(sh_info))
        lines.append(f"  {b_col}│{NC}{sh_info}{' ' * pad}{b_col}│{NC}")

        pill_parts = []
        for i, pname in enumerate(presets[:9]):
            pnum = f"{i+1}:" if i < 7 else ""
            if pname == cur_p:
                pill_parts.append(f"\033[7m{BOLD}{COLOR_NEON_PINK} {pnum}{pname} \033[0m")
            else:
                pill_parts.append(f"{COLOR_ELECTRIC_CYAN}[{pnum}{pname}]{NC}")
        preset_row = f" Presets: " + " ".join(pill_parts)
        sh_preset = preset_row if _display_width(preset_row) <= iw else _clip_display(preset_row, iw)
        pad = max(0, iw - _display_width(sh_preset))
        lines.append(f"  {b_col}│{NC}{sh_preset}{' ' * pad}{b_col}│{NC}")
        lines.append(_boxed_rule("├", "─" * 16, "┤", iw, b_col))

        if h >= 32:
            scale_dbs = [12, 10, 8, 6, 4, 2, 0, -2, -4, -6, -8, -10, -12]
        elif h >= 26:
            scale_dbs = [12, 9, 6, 3, 0, -3, -6, -9, -12]
        else:
            scale_dbs = [12, 8, 4, 0, -4, -8, -12]

        def gain_to_row(g):
            clamped = max(-12.0, min(12.0, float(g)))
            frac = (12.0 - clamped) / 24.0
            return int(round(frac * (len(scale_dbs) - 1)))

        thumb_rows = [gain_to_row(g) for g in gains]
        avail_w = max(60, iw - 10)
        base_bw = avail_w // 10
        rem = avail_w % 10
        band_widths = [base_bw + (1 if i < rem else 0) for i in range(10)]

        for r_idx, db in enumerate(scale_dbs):
            is_zero = (db == 0)
            prefix = f"  {BOLD}{COLOR_ELECTRIC_CYAN}0 dB ├─{NC}" if is_zero else f" {DIM}{CYAN}{db:+3d} dB │{NC}"

            cells = []
            for c_idx, tr in enumerate(thumb_rows):
                is_sel = (c_idx == sel_idx)
                bw = band_widths[c_idx]
                if tr == r_idx:
                    g_val = gains[c_idx]
                    t_col = COLOR_TRAFFIC_GREEN if g_val > 0 else (COLOR_TRAFFIC_AMBER if g_val < 0 else COLOR_ELECTRIC_CYAN)
                    thumb = f"\033[7m{BOLD}{COLOR_NEON_PINK}[█]{NC}\033[0m" if is_sel else f"{BOLD}{t_col}█{NC}"
                    tw = 3 if is_sel else 1
                    pad_tot = bw - tw
                    pl = pad_tot // 2
                    pr = pad_tot - pl
                    cell = (("─" * pl) + thumb + ("─" * pr)) if is_zero else ((" " * pl) + thumb + (" " * pr))
                else:
                    pad_tot = bw - 1
                    pl = pad_tot // 2
                    pr = pad_tot - pl
                    if is_zero:
                        cell = ("─" * pl) + f"{COLOR_ELECTRIC_CYAN}┼{NC}" + ("─" * pr)
                    else:
                        tr_ch = f"{COLOR_NEON_PINK}┆{NC}" if is_sel else f"{DIM}│{NC}"
                        cell = (" " * pl) + tr_ch + (" " * pr)
                cells.append(cell)

            sep = f"{COLOR_ELECTRIC_CYAN}┤{NC}" if is_zero else f"{DIM}│{NC}"
            row_content = prefix + "".join(cells) + sep
            pad = max(0, iw - _display_width(row_content))
            lines.append(f"  {b_col}│{NC}{row_content}{' ' * pad}{b_col}│{NC}")

        f_prefix = f"  {DIM}Freq: │{NC}"
        freq_cells = []
        for i, fl in enumerate(EQ_BAND_LABELS):
            bw = band_widths[i]
            fl_padded = f"{fl:^{bw}s}"
            freq_cells.append(f"\033[7m{BOLD}{COLOR_NEON_PINK}{fl_padded}\033[0m" if i == sel_idx else f"{BOLD}{COLOR_LILAC}{fl_padded}{NC}")
        f_row = f_prefix + "".join(freq_cells) + f"{DIM}│{NC}"
        pad = max(0, iw - _display_width(f_row))
        lines.append(f"  {b_col}│{NC}{f_row}{' ' * pad}{b_col}│{NC}")

        g_prefix = f"  {DIM}Gain: │{NC}"
        gain_cells = []
        for i, g in enumerate(gains):
            bw = band_widths[i]
            g_str = f"{g:+4.1f}"
            g_padded = f"{g_str:^{bw}s}"
            if i == sel_idx:
                gain_cells.append(f"\033[7m{BOLD}{COLOR_ELECTRIC_CYAN}{g_padded}\033[0m")
            elif abs(g) > 0.05:
                gain_cells.append(f"{COLOR_TRAFFIC_GREEN if g > 0 else COLOR_TRAFFIC_AMBER}{g_padded}{NC}")
            else:
                gain_cells.append(f"{DIM}{g_padded}{NC}")
        g_row = g_prefix + "".join(gain_cells) + f"{DIM}│{NC}"
        pad = max(0, iw - _display_width(g_row))
        lines.append(f"  {b_col}│{NC}{g_row}{' ' * pad}{b_col}│{NC}")

        c_prefix = "        │"
        cursor_cells = []
        for i in range(10):
            bw = band_widths[i]
            if i == sel_idx:
                cur_padded = f"{'▲':^{bw}s}"
                cursor_cells.append(f"{BOLD}{COLOR_NEON_PINK}{cur_padded}{NC}")
            else:
                cursor_cells.append(" " * bw)
        c_row = c_prefix + "".join(cursor_cells) + f"{DIM}│{NC}"
        pad = max(0, iw - _display_width(c_row))
        lines.append(f"  {b_col}│{NC}{c_row}{' ' * pad}{b_col}│{NC}")

        if self.eq_naming_mode:
            save_prompt = f" {BOLD}{COLOR_TRAFFIC_AMBER}💾 Name Custom Preset: [{self.eq_custom_name_input}█]  (Enter: Save, Esc: Cancel){NC}"
            sh_save = save_prompt if _display_width(save_prompt) <= iw else _clip_display(save_prompt, iw)
            pad = max(0, iw - _display_width(sh_save))
            lines.append(f"  {b_col}│{NC}{sh_save}{' ' * pad}{b_col}│{NC}")
        lines.append(_boxed_rule("╰", "── [←/→] Band • [↑/↓] Slider (±0.5dB) • [P/Tab] Preset • [1-7] Preset • [S] Save • [R] Flat • [E/Esc] Close ", "╯", iw, b_col))
        return lines

    def _get_target_path(self) -> Tuple[Optional[str], Optional[str]]:
        mixes = self._get_active_tracks()
        if mixes and 0 <= self.selected_row < len(mixes): return mixes[self.selected_row].get("path"), mixes[self.selected_row].get("name")
        st = self._get_status()
        if st.get("path"): return st.get("path"), st.get("title")
        latest = self.scanner.get_latest_mix()
        return (latest["path"], latest["name"]) if latest else (None, None)

    def _notify(self, msg: str, dur: float = 3.0):
        self.notification_msg, self.notification_time = msg, time.time() + dur

    def _generate_selected_spek(self):
        tp, tn = self._get_target_path()
        label = tn or (os.path.basename(tp) if tp else "this track")
        if not tp or not os.path.isfile(tp): return self._notify("No audio track available for Spek generation.", 3.0)
        if (ex := find_existing_spek(tp, mode=self.mode)) and os.path.isfile(ex) and os.path.getsize(ex) > 0:
            self._notify(f"Opening Spek: {os.path.basename(ex)}", 4.0)
            if not open_image_viewer(ex):
                self._notify(f"Spek found but the image viewer did not open: {os.path.basename(ex)}", 5.0)
            return
        if self._spek_job_running:
            return self._notify("MP Audio Player is already generating a Spek.", 4.0)
        out_dir = get_default_spek_dir(mode=self.mode, audio_path=tp)
        self._spek_job_running = True
        self._notify(f"MP Audio Player is generating a Spek for {label}. It will open when finished.", 86400.0)
        notify_desktop("MP Audio Player", f"MP Audio Player is generating a Spek for {label}")
        def _w():
            try:
                ok, res = generate_track_spek(tp, mode=self.mode, output_dir=out_dir)
                if ok and res and os.path.isfile(res):
                    self._notify(f"MP Audio Player finished the Spek. Opening {os.path.basename(res)}", 6.0)
                    notify_desktop("MP Audio Player", f"Spek ready: {os.path.basename(res)}")
                    if not open_image_viewer(res):
                        self._notify(f"Spek saved to {out_dir.name} but the image viewer did not open.", 6.0)
                else:
                    self._notify(f"Spek generation failed: {str(res)[:80]}", 6.0)
            finally:
                self._spek_job_running = False
        threading.Thread(target=_w, daemon=True).start()

    def _open_selected_in_file_manager(self):
        st, mixes = self._get_status(), self._get_active_tracks()
        sel = mixes[self.selected_row].get("path") or "" if (mixes and 0 <= self.selected_row < len(mixes)) else ""
        if not (target := choose_file_manager_target(st.get("path") or "", sel)):
            return self._notify("No audio file to show in File Manager.", 3.0)
        ok = open_in_file_manager(target)
        self._notify(f"{'Opened in' if ok else 'Failed to open'} File Manager: {os.path.basename(target)}", 3.0)

    def _toggle_recording(self):
        if self.is_remote:
            res = send_ipc_command("toggle_record") or {}
            is_rec, rec_file = bool(res.get("recording", False)), str(res.get("recording_file", ""))
        elif self.engine: is_rec, rec_file = self.engine.toggle_recording()
        else: return
        self.cached_status.update(recording=is_rec, recording_file=rec_file)
        self._notify(f"● RECORDING TO WAV STARTED: {os.path.basename(rec_file)} (3GB Max / File)" if is_rec else "■ RECORDING STOPPED & SAVED TO MP_AUDIOWAV_REC_OUTPUT", 4.0)

    def _view_selected_tracklist(self):
        tp, tn = self._get_target_path()
        if not tp: return self._notify("No mix selected to view tracklist.", 3.0)
        if (tl := find_tracklist_for_mix(tp)) and os.path.isfile(tl):
            self._notify(f"{'Opened' if open_tracklist_window(tl, tp, theme=self.visualizer.theme) else 'Failed to open'} Tracklist: {os.path.basename(tl)}", 3.5)
        else: self._notify(f"No tracklist found for: {tn or os.path.basename(tp)}", 3.5)

    def _open_audio_file(self):
        chosen = choose_audio_file_gui()
        if chosen == "": return self._notify("Open file cancelled.", 2.5)
        if chosen and os.path.isfile(chosen):
            self._send_cmd("play", file=chosen)
            item = {"name": os.path.basename(chosen), "path": chosen, "size_mb": os.path.getsize(chosen) / 1048576.0, "mtime": time.time(), "ext": os.path.splitext(chosen)[1].lower()[1:].upper()}
            if not any(m["path"] == chosen for m in self.scanner.mixes): self.scanner.mixes.insert(0, item)
            self.selected_row = 0
            return self._notify(f"Playing: {os.path.basename(chosen)}", 3.5)
        self._notify("No audio file selected. Press [F] for File Manager.", 3.0)

    def _export_playlist(self):
        if not (mixes := self.scanner.get_mixes(self.search_query)): return self._notify("No mixes in playlist to export.", 3.0)
        chosen = choose_export_m3u_gui()
        if chosen == "": return self._notify("Export cancelled.", 2.5)
        if chosen:
            ok, res = export_playlist_m3u(mixes, chosen)
            return self._notify(f"Exported {len(mixes)} mixes to: {os.path.basename(res)}" if ok else f"Export failed: {res}", 4.0)
        self.export_mode = True
        self.export_path = os.path.join(os.path.expanduser("~/Desktop" if os.path.isdir(os.path.expanduser("~/Desktop")) else "~"), "MP_Archive_Playlist.m3u")

    def _queue_selected(self):
        tp, tn = self._get_target_path()
        if not tp: return self._notify("No mix selected to queue.", 2.5)
        self._send_cmd("queue", file=tp)
        if not self.is_remote and self.engine: q_len = len(self.engine.play_queue)
        else:
            cur_q = list(self.cached_status.get("queue", []))
            if tp not in cur_q: cur_q.append(tp)
            self.cached_status.update(queue=cur_q, queue_len=len(cur_q))
            q_len = len(cur_q)
        self._notify(f"✔ Queued Mix: {tn or os.path.basename(tp)} (#{q_len} in Queue)", 3.5)

    def _cleanup_terminal(self):
        fd = getattr(self, "_orig_fd", None)
        old_settings = getattr(self, "_orig_termios", None)
        if fd is not None and old_settings and termios:
            try: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception: pass
        try:
            sys.stdout.write("\033]111\007\033[49m\033[?7h\033[?25h\033[?1049l\033]0;MP Audio Player\007\n")
            sys.stdout.flush()
        except Exception: pass
        if hasattr(self, "_win_cstate"):
            _win_console_end(self._win_cstate)

    def run(self):
        fd = sys.stdin.fileno() if sys.stdin.isatty() else None
        old_settings = None
        if fd is not None and termios and tty:
            try:
                old_settings = termios.tcgetattr(fd)
                tty.setcbreak(fd)
                new = termios.tcgetattr(fd); new[1] |= termios.OPOST
                termios.tcsetattr(fd, termios.TCSADRAIN, new)
            except Exception: pass
        cstate = _win_console_begin()
        self._orig_fd = fd
        self._orig_termios = old_settings
        self._win_cstate = cstate
        if self.ui_size_mode in ("MINI", "MICRO"):
            _setup_mini_terminal_appearance()
            t_rows = 7 if self.ui_size_mode == "MICRO" else 14
            # Konsole on Wayland applies CSI 8 to the reported size only. The real
            # window size is set at launch (-p TerminalRows) or by resize_host_terminal.
            if not os.environ.get("KONSOLE_DBUS_SERVICE"):
                sys.stdout.write(f"\033[8;{t_rows};74t")
            sys.stdout.write(f"\033]0;MP {'Mini' if self.ui_size_mode == 'MINI' else 'Micro'} Audio Player\007")
        else: sys.stdout.write("\033]0;MP Audio Player\007")
        sys.stdout.write("\033[?1049h\033[?25l\033[?7l\033[2J\033[H"); sys.stdout.flush()
        threading.Thread(target=self._input_loop, daemon=True).start()
        try:
            while self.running:
                if not self.is_remote and self.engine: self.engine.check_track_end()
                try:
                    self._draw_frame()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as exc:
                    mp_log_error("TerminalPlayerUI", f"Error drawing frame: {exc}", exc)
                time.sleep(0.02)
        except (KeyboardInterrupt, SystemExit): pass
        finally:
            self.running = False
            if self.engine and not self.is_remote:
                try: self.engine.stop_recording()
                except Exception: pass
            self._cleanup_terminal()

    def _input_loop(self):
        if not sys.stdin.isatty(): return
        if sys.platform == "win32":
            import msvcrt
            km = {b"H": b"\x1b[A", b"P": b"\x1b[B", b"M": b"\x1b[C", b"K": b"\x1b[D", b"G": b"\x1b[H", b"O": b"\x1b[F", b"I": b"\x1b[5~", b"Q": b"\x1b[6~"}
            while self.running:
                try:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        self._process_key(km.get(msvcrt.getch(), b"") if ch in (b"\x00", b"\xe0") else ch)
                    else: time.sleep(0.02)
                except Exception: time.sleep(0.02)
            return
        fd = sys.stdin.fileno()
        while self.running:
            try:
                if select.select([fd], [], [], 0.05)[0] and self.running:
                    d = os.read(fd, 32)
                    if d == b"\x1b" and select.select([fd], [], [], 0.03)[0]: d += os.read(fd, 31)
                    self._process_key(d)
            except Exception: pass

    def _process_key(self, data: bytes):
        if not data: return
        if self.equalizer_hud_active and self.eq_naming_mode:
            if data in (b"\r", b"\n"):
                self.eq_naming_mode = False
                p_name = self.eq_custom_name_input.strip() or "Custom 1"
                cb = list(self.eq_manager.current_bands)
                if self.is_remote: self._send_cmd("save_eq_preset", name=p_name, bands=cb)
                elif self.engine: self.engine.save_eq_preset(p_name, cb)
                self.eq_manager.save_custom_preset(p_name, cb)
                self._notify(f"Equalizer preset saved: {p_name}", 3.0)
                return
            elif data == b"\x1b":
                self.eq_naming_mode = False
                self._notify("Preset save cancelled", 2.0)
                return
            elif data in (b"\x7f", b"\x08"):
                self.eq_custom_name_input = self.eq_custom_name_input[:-1]
                return
            else:
                try:
                    c = data.decode("utf-8", "ignore")
                    if c.isprintable(): self.eq_custom_name_input += c
                except Exception: pass
                return
        if self.export_mode:
            if data in (b"\r", b"\n"):
                self.export_mode = False
                mixes = self.scanner.get_mixes(self.search_query)
                ok, res = export_playlist_m3u(mixes, self.export_path.strip() or os.path.expanduser("~/Desktop/MP_Archive_Playlist.m3u"))
                self._notify(f"Exported {len(mixes)} mixes to: {os.path.basename(res)}" if ok else f"Export failed: {res}", 4.0)
            elif data == b"\x1b": self.export_mode = False; self._notify("Export cancelled", 2.5)
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
                    if (c := data.decode("utf-8", "ignore")).isprintable(): self.search_query, self.selected_row = self.search_query + c, 0
                except Exception: pass
            return

        if data == b"K":
            self._cleanup_terminal()
            try:
                subprocess.run('pkill -9 -f "MP_Audio_Player"', shell=True)
            except Exception:
                pass
            self.running = False
            return

        if self.equalizer_hud_active:
            if data in (b"\x1b[D", b"\x1bOD", b"h", b"H"):
                self.eq_selected_band = max(0, self.eq_selected_band - 1)
                return
            elif data in (b"\x1b[C", b"\x1bOC", b"l", b"L"):
                self.eq_selected_band = min(9, self.eq_selected_band + 1)
                return
            elif data in (b"\x1b[A", b"\x1bOA", b"k", b"+", b"="):
                new_gain = round(min(12.0, self.eq_manager.current_bands[self.eq_selected_band] + 0.5), 1)
                self.eq_manager.set_band(self.eq_selected_band, new_gain)
                if self.is_remote: self._send_cmd("set_eq_band", band=self.eq_selected_band, gain=new_gain)
                elif self.engine: self.engine.set_eq_band(self.eq_selected_band, new_gain)
                return
            elif data in (b"\x1b[B", b"\x1bOB", b"j", b"J", b"-", b"_"):
                new_gain = round(max(-12.0, self.eq_manager.current_bands[self.eq_selected_band] - 0.5), 1)
                self.eq_manager.set_band(self.eq_selected_band, new_gain)
                if self.is_remote: self._send_cmd("set_eq_band", band=self.eq_selected_band, gain=new_gain)
                elif self.engine: self.engine.set_eq_band(self.eq_selected_band, new_gain)
                return
            elif data in (b"p", b"P", b"\t"):
                np_name = self.eq_manager.cycle_preset(1)
                if self.is_remote: self._send_cmd("set_eq_preset", preset=np_name)
                elif self.engine: self.engine.set_eq_preset(np_name)
                self._notify(f"Equalizer Preset: {np_name}", 2.0)
                return
            elif data in (b"1", b"2", b"3", b"4", b"5", b"6", b"7"):
                p_list = ["Flat", "Ambient", "Trance", "Techno", "House", "Progressive", "Vapourwave"]
                idx = int(data.decode("ascii")) - 1
                if 0 <= idx < len(p_list):
                    t_name = p_list[idx]
                    self.eq_manager.apply_preset(t_name)
                    if self.is_remote: self._send_cmd("set_eq_preset", preset=t_name)
                    elif self.engine: self.engine.set_eq_preset(t_name)
                    self._notify(f"Equalizer Preset: {t_name}", 2.0)
                return
            elif data in (b"s", b"S"):
                self.eq_naming_mode = True
                self.eq_custom_name_input = ""
                return
            elif data in (b"r", b"R", b"0"):
                self.eq_manager.apply_preset("Flat")
                if self.is_remote: self._send_cmd("set_eq_preset", preset="Flat")
                elif self.engine: self.engine.set_eq_preset("Flat")
                self._notify("Equalizer Reset to Flat (0 dB)", 2.0)
                return
            elif data in (b"d", b"D"):
                cur = self.eq_manager.active_preset
                if cur in self.eq_manager.custom_presets:
                    self.eq_manager.delete_custom_preset(cur)
                    if self.is_remote: self._send_cmd("delete_eq_preset", name=cur)
                    elif self.engine: self.engine.delete_eq_preset(cur)
                    self._notify(f"Deleted custom preset: {cur}", 2.5)
                return
            elif data in (b" ",):
                self._send_cmd("toggle")
                return
            elif data in (b"\x1b", b"E", b"\r", b"\n", b"q", b"Q", b"b", b"B"):
                self.equalizer_hud_active = False
                return
        if self.inspector_hud_active:
            if data in (b"g", b"G"): return self._generate_selected_spek()
            if data in (b"\x1b", b"i", b"I", b"\r", b"\n", b"q", b"Q", b" "): self.inspector_hud_active = False; return
        if data in (b"i", b"I"): self.inspector_hud_active = not self.inspector_hud_active; return
        if data in (b"E",) and self.ui_size_mode not in ("MINI", "MICRO"):
            self.equalizer_hud_active = not self.equalizer_hud_active
            if self.equalizer_hud_active: self.inspector_hud_active = False
            return
        if data in (b"\x1b[A", b"\x1bOA", b"k"): self._navigate_list(-1)
        elif data in (b"\x1b[B", b"\x1bOB", b"j", b"J"): self._navigate_list(1)
        elif data == b"\x1b[5~": self._navigate_list(-5)
        elif data == b"\x1b[6~": self._navigate_list(5)
        elif data in (b"\x1b[H", b"\x1b[1~", b"\x1b[7~", b"\x1bOH"): self.selected_row = 0
        elif data in (b"\x1b[F", b"\x1b[4~", b"\x1b[8~", b"\x1bOF"):
            if flt := self._get_active_tracks(): self.selected_row = len(flt) - 1
        elif data in (b"\x1b[D", b"\x1bOD"): self._send_cmd("seek", seconds=-10.0)
        elif data in (b"\x1b[C", b"\x1bOC"): self._send_cmd("seek", seconds=10.0)
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
            self.cached_status.update(volume=min(100, int(self.cached_status.get("volume", 85)) + 5), muted=False)
        elif data in (b"[", b"{", b"V"):
            self._send_cmd("vol_down", step=5)
            self.cached_status.update(volume=max(0, int(self.cached_status.get("volume", 85)) - 5), muted=False)
        elif data in (b"u", b"U"):
            self._send_cmd("mute")
            im = self.engine.muted if (self.engine and not self.is_remote) else not self.cached_status.get("muted", False)
            self.cached_status["muted"] = im
            self._notify(f"Audio: {'MUTED' if im else 'UNMUTED'}", 2.0)
        elif data in (b"s", b"S"):
            self._send_cmd("shuffle")
            so = self.engine.shuffle if (self.engine and not self.is_remote) else not self.cached_status.get("shuffle", False)
            self.cached_status["shuffle"] = so
            self._notify(f"Shuffle: {'ON' if so else 'OFF'}", 2.5)
        elif data in (b"m", b"M"):
            if os.environ.get("MP_LIQUID_GLASS") == "1":
                if self.ui_size_mode == "NORMAL":
                    self.ui_size_mode = "MINI"
                elif self.ui_size_mode == "MINI":
                    self.ui_size_mode = "MICRO"
                else:
                    self.ui_size_mode = "NORMAL"
                self._notify(f"Liquid Glass Mode: {self.ui_size_mode}", 2.0)
            elif self.ui_size_mode in ("MINI", "MICRO"):
                self.ui_size_mode = "MICRO" if self.ui_size_mode == "MINI" else "MINI"
                t_rows = 7 if self.ui_size_mode == "MICRO" else 14
                title = f"MP {'Micro' if self.ui_size_mode == 'MICRO' else 'Mini'} Audio Player"
                resize_host_terminal(74, t_rows, title)
            else:
                ok = launch_mini_player_window(
                    self.mode,
                    self.folder_name,
                    getattr(self.scanner, "playlist_path", "") or "",
                    self.visualizer.theme,
                    self.visualizer.style,
                )
                self._notify("✦ Launched MP Mini Audio Player in new window" if ok else "Failed to open Mini Player window", 3.0)
        elif data in (b"r", b"R"): self._toggle_recording()
        elif data in (b"l", b"L"):
            ok = launch_liquid_glass_player(
                base_dir=getattr(self.scanner, "base_dir", None),
                mode=self.mode,
                folder_name=self.folder_name,
                playlist_path=str(getattr(self.scanner, "playlist_path", "") or ""),
                theme=self.visualizer.theme,
                style=self.visualizer.style,
                mini=(self.ui_size_mode == "MINI"),
                micro=(self.ui_size_mode == "MICRO"),
            )
            self._notify("✦ Launched MP Audio Player (Liquid Glass)" if ok else "Failed to open Liquid Glass Player window", 3.0)
        elif data in (b"z", b"Z"):
            ok = launch_liquid_visualizer(base_dir=getattr(self.scanner, "base_dir", None))
            self._notify("✦ Launched MP Liquid Visualizer [Cosmic Dreamworlds (Liquid)] — 1400x1400 Vulkan" if ok else "Failed to launch MP Liquid Visualizer", 3.5)
        elif data in (b"y", b"Y"):
            self._send_cmd("repeat")
            modes = ["all", "one", "off"]
            cr = self.engine.repeat_mode if (self.engine and not self.is_remote) else self.cached_status.get("repeat", "all")
            nr = modes[(modes.index(cr) + 1) % 3] if cr in modes else "all"
            self.cached_status["repeat"] = nr
            self._notify(f"Repeat: {nr.upper()}", 2.5)
        elif (data in (b"e", b"E") if self.ui_size_mode in ("MINI", "MICRO") else data == b"e"):
            self.visualizer.cycle_style()
            self._notify(f"Visualizer: {self.visualizer.get_style_display_name()}", 2.5)
        elif data in (b"c", b"C"):
            self.visualizer.cycle_theme()
            self._notify(f"Color Theme: {self.visualizer.get_theme_display_name()}", 2.5)
        elif data in (b"b", b"B", b"\x1b", b"\x03"): self.running = False
        elif data in (b"a", b"A"):
            if self.is_remote:
                bi = (send_ipc_command("route_bluetooth") or {}).get("bluetooth", {})
                c_str = f" ({bi.get('bluetooth_codec')})" if bi.get("bluetooth_codec") else ""
                self._notify(f"🎧 Bluetooth Audio Routed: {bi.get('bluetooth_device')}{c_str}" if bi.get("bluetooth_connected") else "No Bluetooth audio device connected. (Checked)", 3.5)
            elif self.engine and self.engine.bt_router:
                self.engine.bt_router.route_to_bluetooth()
                bi = self.engine.bt_router.get_status()
                c_str = f" ({bi.get('bluetooth_codec')})" if bi.get("bluetooth_codec") else ""
                self._notify(f"🎧 Bluetooth Audio Routed: {bi.get('bluetooth_device')}{c_str}" if bi.get("bluetooth_connected") else "No Bluetooth audio device connected.", 3.5)
        elif data in (b"o", b"O"): self._open_audio_file()
        elif data in (b"t", b"T"): self._view_selected_tracklist()
        elif data in (b"w", b"W"): self._export_playlist()
        elif data == b"/": self.search_mode, self.search_query = True, ""
        elif data in (b"f", b"F"): self._open_selected_in_file_manager()
        elif data in (b"g", b"G"): self._generate_selected_spek()
        elif data in (b"q", b"Q"): self._queue_selected()
        elif data in (b"x", b"X"): self._send_cmd("stop"); self.running = False

    def _navigate_list(self, delta: int):
        if m := self._get_active_tracks(): self.selected_row = max(0, min(len(m) - 1, self.selected_row + delta))

    def _draw_frame(self):
        w, h = _win_visible_size((80, 24))
        w, h, st = max(40, w), max(5, h), self._get_status()
        if self.ui_size_mode == "MINI": return self._draw_mini_frame(w, h, st)
        if self.ui_size_mode == "MICRO": return self._draw_micro_frame(w, h, st)
        self._sync_initial_selection(st)
        lines = []
        is_bt, bt_dev = bool(st.get("bluetooth_connected", False)), st.get("bluetooth_device", "")
        if self._last_seen_bt_state is not None:
            if is_bt and not self._last_seen_bt_state:
                c = st.get("bluetooth_codec", "")
                c_sfx = f" ({c})" if c else ""
                self._notify(f"🎧 Auto-switched to Bluetooth: {bt_dev}{c_sfx}", 4.0)
            elif not is_bt and self._last_seen_bt_state: self._notify("🔊 Bluetooth disconnected — Reverted to System Audio", 4.0)
        self._last_seen_bt_state, self._last_seen_bt_device = is_bt, bt_dev
        iw = max(20, w - 6)
        pal = self.visualizer.get_theme_palette()
        is_lg = bool(os.environ.get("MP_LIQUID_GLASS"))
        bold_s = "" if is_lg else BOLD
        hl_col, act_col = pal.get("highlight", COLOR_HOT_PURPLE), pal.get("active", COLOR_NEON_PINK)
        b_col = pal.get("border", COLOR_HOT_PURPLE) if is_lg else f"{BOLD}{pal.get('border', COLOR_HOT_PURPLE)}"
        accent_col = pal.get("accent", COLOR_LILAC)
        if is_lg:
            btitle = ("✦ MP AUDIO PLAYER (LIQUID GLASS) — MUSIC LIBRARY ✦" if self.mode == "MUSIC" else "✦ MP AUDIO PLAYER (LIQUID GLASS) — LIQUID AUDIO MODE ✦")[:max(0, iw - 1)]
            bsub = (f"Liquid Glass Music Library  •  {music_library_label(self.folder_name)}" if self.mode == "MUSIC" else "Liquid Glass Translucent Surface  •  Fluid Audio Navigation")[:max(0, iw - 1)]
        else:
            btitle = ("✦ MP AUDIO PLAYER — MUSIC MODE (TRACKS LIBRARY) ✦" if self.mode == "MUSIC" else "✦ MP AUDIO PLAYER — DREAMWORLDS ULTRA AUDIO MODE ✦")[:max(0, iw - 1)]
            bsub = (f"Music Library  •  {music_library_label(self.folder_name)}  •  Local Drives & SMB Shares" if self.mode == "MUSIC" else "Dreamworlds Productions  •  Hot Purple & Traffic Light Edition")[:max(0, iw - 1)]
        lines.extend([f"  {b_col}╭{'─'*iw}╮{NC}", f"  {b_col}│{btitle.center(iw)}│{NC}", f"  {bold_s}{accent_col}│{bsub.center(iw)}│{NC}", f"  {b_col}╰{'─'*iw}╯{NC}"])

        dim_s = DIM
        tname, maxlen = st.get("title", "Unknown Mix"), max(58, iw - 20)
        if len(tname) > maxlen: tname = tname[:maxlen - 3] + "..."
        ch_str, sr, ext = ("Stereo" if st.get("channels", 2) == 2 else "Mono"), st.get("sample_rate", 44100), os.path.splitext(st.get("path", ""))[1][1:].upper() or "FLAC"
        badge = f"{bold_s}{GREEN}▶ PLAYING{NC}" if st.get("state") == "playing" else (f"{bold_s}{YELLOW}⏸ PAUSED{NC}" if st.get("state") == "paused" else f"{bold_s}{RED}⏹ STOPPED{NC}")
        mode_b = f" {bold_s}{COLOR_TRAFFIC_GREEN}[MUSIC MODE]{NC}" if self.mode == "MUSIC" else f" {dim_s}{COLOR_HOT_PURPLE}[MIX ARCHIVE]{NC}"
        is_rec, flash = bool(st.get("recording", False)), (int(time.time() * 1.5) % 2 == 0)
        rec_b = f"  {bold_s}{COLOR_TRAFFIC_RED}● REC{NC}" if (is_rec and flash) else (f"  {dim_s}{RED}○ REC{NC}" if is_rec else "")
        lines.append(f"  {badge}{mode_b}{rec_b}  {bold_s}{COLOR_NEON_PINK}♫  {tname}{NC}")
        if is_rec:
            rf, rmb, rdur = os.path.basename(st.get("recording_file", "")), float(st.get("recording_bytes", 0)) / 1048576.0, format_seconds(float(st.get("recording_duration", 0.0)))
            rdot = f"{bold_s}{COLOR_TRAFFIC_RED}●{NC}" if flash else f"{dim_s}{RED}○{NC}"
            lines.append(f"  {rdot} {bold_s}{COLOR_TRAFFIC_RED}RECORDING TO WAV:{NC} {bold_s}{COLOR_ELECTRIC_CYAN}{rf}{NC} {dim_s}[{rmb:.1f} MB  •  {rdur}  •  Max 3GB/WAV]{NC}")
        out_n = bt_dev or st.get("output_device", "Speakers")
        bt_b = f"{bold_s}{COLOR_NEON_PINK}🎧 Output: {out_n}{NC}" if (is_bt or "bluetooth" in str(out_n).lower()) else f"{dim_s}{CYAN}🔊 Output: {out_n}{NC}"
        s4_b = f"  │  {bold_s}\033[38;2;0;255;127m🎛️ S4 MIDI [hw:0,0]{NC}" if (CONFIG_DIR / "traktor_s4_midi.pid").exists() else ""
        lines.append(f"  {dim_s}{CYAN}Format: {ext}{' Lossless' if w>=116 else ''}  │  Sample Rate: {sr/1000:.1f} kHz  │  Channels: {ch_str}  │  {bt_b}{s4_b}{NC}" if w >= 106 else f"  {dim_s}{CYAN}Format: {ext}  │  {sr/1000:.1f} kHz  │  {bt_b}{NC}")

        pct, bw = float(st.get("progress_pct", 0.0)), max(20, min(max(54, iw - 42), iw - 28))
        fw = int((pct / 100.0) * bw)
        lines.extend([
            f"  {bold_s}{COLOR_ELECTRIC_CYAN}{st.get('position_fmt', '00:00')}{NC}  {b_col}{'━' * fw + '●' + '─' * max(0, bw - fw - 1)}{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}{st.get('duration_fmt', '00:00')}{NC}  {WHITE if is_lg else ''}({pct:.1f}%){NC if is_lg else ''}",
            self.visualizer.render_horizontal_pitch_bar(int(st.get("pitch_percent", 0)), width=bw, max_cols=max(20, w - 1)), ""
        ])
        lines.extend(self.visualizer.render(st, width=w, height=(7 if h >= 34 else (5 if h >= 28 else 3))) + [""])

        active_tracks = self._get_active_tracks()
        if self.export_mode: lines.append(f"  {bold_s}{COLOR_TRAFFIC_AMBER}Export Playlist (.m3u) Path: [{self.export_path}█]  (Enter: Save, Esc: Cancel){NC}")
        elif self.search_mode: lines.append(f"  {bold_s}{CYAN}Filter / Search: [{self.search_query}█]{NC}")
        elif self.search_query: lines.append(f"  {bold_s}Search Filter: '{self.search_query}' (Press '/' to search)")
        elif time.time() < self.notification_time and self.notification_msg: lines.append(f"  {bold_s}{COLOR_TRAFFIC_GREEN}📂 {self.notification_msg}{NC}")

        if self.inspector_hud_active: lines.extend(self._render_inspector_hud(st, iw))
        elif self.equalizer_hud_active: lines.extend(self._render_equalizer_hud(st, iw, h))
        else:
            q_len, q_paths = int(st.get("queue_len", 0)), list(st.get("queue", []))
            qb = f" • Queue: {q_len}" if q_len > 0 else ""
            lines.append(_boxed_rule("┌", f"── MUSIC LIBRARY: {music_library_label(self.folder_name)} ({len(active_tracks)} Tracks{qb}) " if self.mode == "MUSIC" else f"── MP MIX ARCHIVE PLAYLIST ({len(active_tracks)} Mixes Available{qb}) ", "┐", iw, b_col))
            vrows = max(0, h - len(lines) - 4)
            if vrows <= 0: self.scroll_offset = max(0, self.selected_row)
            elif self.selected_row < self.scroll_offset: self.scroll_offset = self.selected_row
            elif self.selected_row >= self.scroll_offset + vrows: self.scroll_offset = self.selected_row - vrows + 1
            avail_name = max(4, iw - 23)
            if not active_tracks:
                em1 = "No audio tracks found in playlist." if self.mode == "MUSIC" else "No audio mixes found in archive. (Mix archive folders not yet configured)"
                em2 = "Option 1: add a local drive or SMB folder, then generate its playlist." if self.mode == "MUSIC" else "Press [O] to open an audio file, [F] for File Manager, or Option 14 to configure archive."
                for em in (em1, em2): lines.append(f"  {b_col}│{NC} {bold_s}{COLOR_TRAFFIC_AMBER}{em}{NC}{' ' * max(0, iw - _display_width(em) - 2)}{b_col}│{NC}")
                for _ in range(max(0, vrows - 2)): lines.append(f"  {b_col}│{NC}{' ' * iw}{b_col}│{NC}")
            else:
                for i in range(self.scroll_offset, min(len(active_tracks), self.scroll_offset + vrows)):
                    m = active_tracks[i]
                    act, sel, in_q, rn = (m["path"] == st.get("path")), (i == self.selected_row), (m["path"] in q_paths), str(m.get("name", ""))
                    mn = (_clip_display(rn, max(1, avail_name - 3)) + "..." if avail_name > 3 else _clip_display(rn, avail_name)) if _display_width(rn) > avail_name else rn
                    npad = " " * max(0, avail_name - _display_width(mn))
                    pfx = f"{PLAYLIST_ACTIVE_MARK} " if act else ((f"Q{q_paths.index(m['path']) + 1}" if q_paths.index(m["path"]) < 9 else "Q*") if in_q else "  ")
                    ext_s = f"{m.get('ext', ''):<4}"[:4]
                    if self.mode == "MUSIC":
                        dur = m.get("duration_fmt")
                        if not dur or dur == "00:00":
                            if act and st.get("duration_fmt"): dur = m["duration_fmt"] = self._duration_cache[m["path"]] = st["duration_fmt"]
                            elif m.get("duration_sec"): dur = m["duration_fmt"] = self._duration_cache[m["path"]] = format_seconds(m["duration_sec"])
                            elif m.get("path") in self._duration_cache: dur = m["duration_fmt"] = self._duration_cache[m["path"]]
                            else: dur = "00:00"; self._request_duration(m)
                        f_str = f"{dur:>6s}"
                    else: f_str = f"{m.get('size_mb', 0):.0f}MB".rjust(6)
                    if len(f_str) > 6:
                        ex_l = len(f_str) - 6
                        npad = npad[:-ex_l] if len(npad) >= ex_l else ""
                    ip = f" {pfx}[{i+1:4d}] {mn}{npad} {ext_s} {f_str} "
                    cw = _display_width(ip)
                    ip = ip + " " * (iw - cw) if cw < iw else (_clip_display(ip, iw) if cw > iw else ip)
                    if sel: lines.append(f"  {b_col}│{NC}\033[7m{bold_s}{hl_col}{ip}\033[0m{b_col}│{NC}")
                    elif act: lines.append(f"  {b_col}│{NC}{bold_s}{act_col}{ip}{NC}{b_col}│{NC}")
                    elif in_q: lines.append(f"  {b_col}│{NC}{bold_s}{COLOR_ELECTRIC_CYAN}{ip}{NC}{b_col}│{NC}")
                    else: lines.append(f"  {b_col}│{NC}{WHITE}{ip}{NC}{b_col}│{NC}")
            lines.append(_boxed_rule("└", "── ↑/↓: Scroll • Enter: Play • Q: Queue • Space: Pause • G: Spek • I: Inspector • E: Equalizer • /: Search • b/Esc: Exit " if self.mode == "MUSIC" else "── ↑/↓: Scroll  •  Enter: Play  •  Q: Queue  •  G: Spek  •  O: Open  •  T: Tracklist  •  E: Equalizer  •  w: Export  •  F: Files  •  /: Search ", "┘", iw, b_col))

        hint_col = WHITE if is_lg else DIM
        shuf = f"{bold_s}{COLOR_TRAFFIC_GREEN}ON{NC}" if st.get("shuffle") else f"{hint_col}OFF{NC}"
        rep = f"{bold_s}{COLOR_TRAFFIC_GREEN}{st.get('repeat', 'all').upper()}{NC}"
        vol = (f"{bold_s}{COLOR_ELECTRIC_CYAN}{st.get('volume', 85)}%{NC}" if not st.get("muted") else f"{bold_s}{COLOR_TRAFFIC_RED}MUTED{NC}")
        pval = int(st.get("pitch_percent", 0))
        pcol = COLOR_TRAFFIC_GREEN if pval == 0 else (COLOR_TRAFFIC_AMBER if pval > 0 else COLOR_INDIGO_BLUE)
        pbadge = f"{bold_s}{pcol}{pval:+d}% ({1.0 + pval/100:.2f}x){NC}"
        eq_n = self.visualizer.get_style_display_name()
        th_n = self.visualizer.get_theme_display_name()
        eq_p = self.eq_manager.active_preset
        eq_p_col = COLOR_TRAFFIC_GREEN if eq_p != "Flat" else COLOR_ELECTRIC_CYAN
        lines.append(_fit_text_line([
            f"  🔊 Vol: {vol}  │  🎚 Pitch: {pbadge}  │  🎛 EQ: {bold_s}{eq_p_col}{eq_p}{NC}  │  📊 Vis: {bold_s}{COLOR_NEON_PINK}{eq_n}{NC}  │  🔀 Shuf: {shuf}  │  🔁 Rep: {rep}  │  🎨 {bold_s}{COLOR_HOT_PURPLE}{th_n}{NC}",
            f"  Vol: {vol}  │  Pitch: {pbadge}  │  EQ: {bold_s}{eq_p_col}{eq_p}{NC}  │  Vis: {bold_s}{COLOR_NEON_PINK}{eq_n}{NC}  │  Shuf: {shuf}  │  Rep: {rep}",
            f"  Vol {vol}  Pitch {pbadge}  EQ {eq_p}  Vis {eq_n}  Shuf {shuf}  Rep {rep}"
        ], max(20, w - 1)))
        if self.mode == "MUSIC":
            lines.extend([
                _fit_text_line([
                    f"  {bold_s}{COLOR_TRAFFIC_GREEN}TRACK CONTROLS:{NC} {bold_s}{COLOR_ELECTRIC_CYAN}[Space]{NC} {bold_s}Play/Pause{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[R]{NC} {bold_s}Record WAV{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[M]{NC} {bold_s}Mini Mode{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[L]{NC} {bold_s}Liquid Glass{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[Z]{NC} {bold_s}MP Liquid Visualizer{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[Q]{NC} {bold_s}Queue{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[G]{NC} {bold_s}Spek{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[I]{NC} {bold_s}Track Inspector{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[E]{NC} {bold_s}Equalizer HUD{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[/]{NC} {bold_s}Search{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[n/p]{NC} {bold_s}Skip{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[+/-]{NC} {bold_s}Pitch{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[v/V]{NC} {bold_s}Vol{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[u]{NC} {bold_s}Mute{NC}  {bold_s}{COLOR_ELECTRIC_CYAN}[b/Esc]{NC} {bold_s}Exit{NC}",
                    f"  {bold_s}{COLOR_TRAFFIC_GREEN}CONTROLS:{NC} {bold_s}[Space] Play{NC}  {bold_s}[R] Rec WAV{NC}  {bold_s}[M] Mini{NC}  {bold_s}[L] Liquid{NC}  {bold_s}[Z] Liquid Vis{NC}  {bold_s}[Q] Queue{NC}  {bold_s}[G] Spek{NC}  {bold_s}[I] Inspector{NC}  {bold_s}[E] Equalizer{NC}  {bold_s}[/] Search{NC}  {bold_s}[n/p] Skip{NC}  {bold_s}[+/-] Pitch{NC}  {bold_s}[v/V] Vol{NC}  {bold_s}[u] Mute{NC}  {bold_s}[b/Esc] Exit{NC}",
                    f"  {bold_s}Space Play  [R] Rec  [M] Mini  [L] Liquid  [Z] Liquid Vis  [Q] Queue  [G] Spek  [I] Inspector  [E] EQ  [/] Search  n/p Skip  [u] Mute  b/Esc Exit{NC}"
                ], max(20, w - 1)),
                _fit_text_line([
                    f"  {hint_col}[0] Pitch Reset  [u] Mute  [s] Shuffle  [y] Repeat  [L] Liquid Glass  [Z] MP Liquid Visualizer  [E] Equalizer HUD  [e] Vis Style  [c] Color Theme  [a] Audio/BT  [O] Open  [F] Files{NC}",
                    f"  {hint_col}0 Reset  u Mute  s Shuf  y Rep  L Glass  Z Liquid Vis  E Equalizer  e Vis  c Theme  a BT  O Open  F Files{NC}",
                    f"  {hint_col}0 Reset  u Mute  s Shuf  y Rep  L Glass  Z Liquid Vis  E Equalizer  e Vis  c Theme  b/Esc Exit{NC}"
                ], max(20, w - 1))
            ])
        else:
            lines.append(_fit_text_line([
                f"  {hint_col}[Space] Play/Pause  [R] Record WAV  [M] Mini Mode  [L] Liquid Glass  [Z] MP Liquid Visualizer  [Q] Queue  [G] Spek  [+/-] Pitch ±1% (±20% max)  [0] Pitch Reset  [v/V] Vol  [u] Mute  [s] Shuffle  [y] Repeat  [n/p] Next/Prev  [a] Audio/BT  [O] Open  [T] Tracklist  [w] Export  [F] Files  [E] Equalizer HUD  [e] Vis  [b/Esc] Exit{NC}",
                f"  {hint_col}Space Play  R Rec  M Mini  L Glass  Z Liquid Vis  Q Queue  G Spek  +/- Pitch  0 Reset  v/V Vol  u Mute  s Shuf  y Rep  n/p Skip  a BT  O Open  T List  w Export  F Files  E EQ  e Vis  b/Esc Exit{NC}",
                f"  {hint_col}Space Play  R Rec  M Mini  L Glass  Z Liquid Vis  Q Queue  G Spek  +/- Pitch  v/V Vol  u Mute  s Shuf  y Rep  n/p Skip  a BT  O Open  E EQ  e Vis  b/Esc Exit{NC}"
            ], max(20, w - 1)))
        if is_lg:
            lines = [_strip_bold_ansi(l) for l in lines]
        _present_frame(lines, w, h)

    def _draw_mini_frame(self, w: int, h: int, st: Dict[str, Any]):
        self._sync_initial_selection(st)
        t_now = time.time()
        g1, g2, _ = _get_dynamic_gradient(t_now)
        c1, c2 = f"\033[38;2;{g1[0]};{g1[1]};{g1[2]}m", f"\033[38;2;{g2[0]};{g2[1]};{g2[2]}m"
        target_rows, target_cols = 14, 74
        if (w != target_cols or h != target_rows) and sys.platform.startswith(("linux", "freebsd")) and not os.environ.get("KONSOLE_DBUS_SERVICE") and not os.environ.get("MP_LIQUID_GLASS"):
            sys.stdout.write(f"\033[8;{target_rows};{target_cols}t")
        sys.stdout.write("\033]0;MP Mini Audio Player\007")
        iw = max(24, min(w - 4, 74))
        is_lg = bool(os.environ.get("MP_LIQUID_GLASS"))
        bold_s = "" if is_lg else BOLD
        header_title = '✦ MP MINI AUDIO PLAYER (LIQUID GLASS) ✦' if is_lg else '✦ MP MINI AUDIO PLAYER ✦'
        lines = [f"  {c1}╭{'─'*iw}╮{NC}", f"  {c1}│{c2}{header_title.center(iw)}{c1}│{NC}", f"  {c1}╰{'─'*iw}╯{NC}"] if is_lg else [f"  {BOLD}{c1}╭{'─'*iw}╮{NC}", f"  {BOLD}{c1}│{BOLD}{c2}{header_title.center(iw)}{c1}│{NC}", f"  {BOLD}{c1}╰{'─'*iw}╯{NC}"]
        tname, av = st.get("title", "Unknown Track"), max(18, iw - 18)
        if _display_width(tname) > av: tname = _clip_display(tname, av - 3) + "..."
        state = st.get("state", "stopped")
        badge = f"{bold_s}\033[38;2;0;255;127m▶ PLAY{NC}" if state == "playing" else (f"{bold_s}\033[38;2;255;191;0m⏸ PAUSE{NC}" if state == "paused" else f"{bold_s}\033[38;2;255;64;64m⏹ STOP{NC}")
        is_rec, flash = bool(st.get("recording", False)), (int(t_now * 1.5) % 2 == 0)
        rec_b = f" {bold_s}\033[38;2;255;64;64m● REC{NC}" if (is_rec and flash) else (f" \033[38;2;255;100;100m○ REC{NC}" if is_rec else "")
        mode_str = 'MUSIC' if self.mode == 'MUSIC' else 'MIX'
        lines.append(f"  {badge} {bold_s}\033[38;2;0;229;255m[{mode_str}]{NC}{rec_b} \033[38;2;255;255;255m♫ {tname}{NC}")
        ext, sr, ch_s = os.path.splitext(st.get("path", ""))[1][1:].upper() or "FLAC", st.get("sample_rate", 44100), ("Stereo" if st.get("channels", 2) == 2 else "Mono")
        dev_s = f"{'🎧' if st.get('bluetooth_connected') else '🔊'} {st.get('output_device', 'Speakers')}"
        if _display_width(dev_s) > 22: dev_s = dev_s[:19] + "..."
        lines.append(f"  \033[38;2;120;215;255m{ext} • {sr/1000:.1f}kHz • {ch_s}{NC}  │  \033[38;2;235;240;255m{dev_s}{NC}")
        pct, bw = float(st.get("progress_pct", 0.0)), max(16, min(34, iw - 30))
        fw = int((pct / 100.0) * bw)
        bar_fill = f"\033[38;2;0;229;255m{'━' * fw}\033[38;2;255;255;255m●{NC}"
        bar_empty = f"\033[38;2;90;105;135m{'─' * max(0, bw - fw - 1)}{NC}"
        lines.append(f"  \033[38;2;0;229;255m{st.get('position_fmt', '00:00')}{NC} {bar_fill}{bar_empty} \033[38;2;0;229;255m{st.get('duration_fmt', '00:00')}{NC} \033[38;2;255;215;0m({pct:.1f}%){NC}")
        vol, pval = (f"{st.get('volume', 85)}%" if not st.get("muted") else "\033[38;2;255;64;64mMUTED\033[0m"), int(st.get("pitch_percent", 0))
        p_str = "\033[38;2;0;255;127m0%\033[0m" if pval == 0 else f"\033[38;2;255;191;0m{pval:+d}%\033[0m"
        lines.append(f"  🔊 \033[38;2;0;229;255m{vol}{NC} │ 🎚 {p_str} │ 🎛 {bold_s}{c2}{self.visualizer.get_style_display_name()[:16]}{NC} │ 🎨 {c1}{self.visualizer.get_theme_display_name()[:14]}{NC}")
        lines.extend(self.visualizer.render(st, width=iw + 4, height=(3 if h >= 14 else 2)))
        if t_now < self.notification_time and self.notification_msg:
            lines.append(f"  {bold_s}\033[38;2;0;255;127m📂 {self.notification_msg}{NC}")
        else:
            lines.append(f"  \033[38;2;0;229;255m[Space]{NC} \033[38;2;235;240;255mPlay{NC}  \033[38;2;0;229;255m[Q]{NC} \033[38;2;235;240;255mQueue{NC}  \033[38;2;0;229;255m[R]{NC} \033[38;2;235;240;255mRec{NC}  \033[38;2;0;229;255m[G]{NC} \033[38;2;235;240;255mSpek{NC}  \033[38;2;0;229;255m[n/p]{NC} \033[38;2;235;240;255mSkip{NC}  \033[38;2;0;229;255m[v/V]{NC} \033[38;2;235;240;255mVol{NC}  \033[38;2;0;229;255m[s]{NC} \033[38;2;235;240;255mShuf{NC}  \033[38;2;0;229;255m[y]{NC} \033[38;2;235;240;255mRep{NC}  \033[38;2;0;229;255m[L]{NC} \033[38;2;235;240;255mGlass{NC}  \033[38;2;0;229;255m[e]{NC} \033[38;2;235;240;255mEQ{NC}  \033[38;2;0;229;255m[c]{NC} \033[38;2;235;240;255mTheme{NC}  \033[38;2;255;215;0m[M]{NC} \033[38;2;235;240;255mMicro{NC}  \033[38;2;255;64;64m[b]{NC} \033[38;2;235;240;255mClose{NC}")
        if is_lg:
            lines = [_strip_bold_ansi(l) for l in lines]
        _present_frame(lines, w, h)

    def _draw_micro_frame(self, w: int, h: int, st: Dict[str, Any]):
        self._sync_initial_selection(st)
        t_now = time.time()
        g1, g2, _ = _get_dynamic_gradient(t_now)
        c1, c2 = f"\033[38;2;{g1[0]};{g1[1]};{g1[2]}m", f"\033[38;2;{g2[0]};{g2[1]};{g2[2]}m"
        target_rows, target_cols = 7, 74
        if (w != target_cols or h != target_rows) and sys.platform.startswith(("linux", "freebsd")) and not os.environ.get("KONSOLE_DBUS_SERVICE") and not os.environ.get("MP_LIQUID_GLASS"):
            sys.stdout.write(f"\033[8;{target_rows};{target_cols}t")
        sys.stdout.write("\033]0;MP Micro Audio Player\007")
        iw, tname = max(24, min(w - 4, 70)), st.get("title", "Unknown Track")
        avail = max(10, iw - 43)
        if _display_width(tname) > avail: tname = _clip_display(tname, avail - 2) + ".."
        is_lg = bool(os.environ.get("MP_LIQUID_GLASS"))
        bold_s = "" if is_lg else BOLD
        state = st.get("state", "stopped")
        badge = f"{bold_s}\033[38;2;0;255;127m▶{NC}" if state == "playing" else (f"{bold_s}\033[38;2;255;191;0m⏸{NC}" if state == "paused" else f"{bold_s}\033[38;2;255;64;64m⏹{NC}")
        cs, lv = self.visualizer.style, np.array(st.get("levels", [0.0] * 24))
        if cs == "stream_of_frequency_eq":
            p_chars = []
            for i in range(14):
                v = float(lv[i % len(lv)]) if len(lv) else 0.0
                h_idx = int(((t_now * 0.65 + (13 - i) * 0.075 + v * 0.25) % 1.0) * 360) % 360
                col = _RAINBOW_ANSI_BOLD[h_idx] if v > 0.4 else _RAINBOW_ANSI_NORMAL[h_idx]
                if v > 0.70: g = "✦" if (int(t_now * 5.0) + i) % 2 == 0 else "≋"
                elif v > 0.35: g = "≈" if (int(t_now * 4.0) + i) % 2 == 0 else "∿"
                elif v > 0.10: g = "~"
                else: g = "·" if (int(t_now * 2.5) + i) % 3 == 0 else " "
                p_chars.append(f"{col}{console_symbol(g)}{NC}")
            m_str = "".join(p_chars)
        elif cs == "oscilloscope":
            wc = ("─", "∿", "~", "≈", "∽", "∿")
            m_str = "".join(f"{c2}{wc[max(0, min(5, int(abs(math.sin(i * 0.7 + t_now * 8.0) * (lv[i % len(lv)] if len(lv) else 0.0)) * 5)))] if (lv[i % len(lv)] if len(lv) else 0.0) > 0.05 else '─'}{NC}" for i in range(14))
        elif cs == "analog_vu":
            lb, rb = int(min(5, round((np.mean(st.get("levels_left", lv)) if len(lv) else 0.0) * 5))), int(min(5, round((np.mean(st.get("levels_right", lv)) if len(lv) else 0.0) * 5)))
            m_str = f"{c1}L{NC}{c2}{'█'*lb}\033[38;2;90;105;135m{'░'*(5-lb)}{NC} {c1}R{NC}{c2}{'█'*rb}\033[38;2;90;105;135m{'░'*(5-rb)}{NC}"
        elif cs == "stardust_particles_eq":
            dc = [console_symbol(ch) for ch in (" ", "·", "˙", ":", "⋆", "✦", "◆", "█")]
            m_str = "".join(f"{c2}{dc[min(len(dc) - 1, int(val * len(dc)))]}{NC}" for val in lv[:14])
        elif cs == "neon_prism_eq":
            m_str = "".join(f"{self.visualizer._get_neon_prism_color(i / 13.0, val)}{prism_level_glyph(min(8, int(val * 9)))}{NC}" for i, val in enumerate(lv[:14]))
        else: m_str = "".join(f"{c2}{prism_level_glyph(min(8, int(val * 9)))}{NC}" for val in lv[:14])

        is_rec, flash = bool(st.get("recording", False)), (int(t_now * 1.5) % 2 == 0)
        rec_d = f" {bold_s}\033[38;2;255;64;64m●{NC}" if (is_rec and flash) else (f" \033[38;2;255;100;100m○{NC}" if is_rec else "")
        pval = int(st.get("pitch_percent", 0))
        p_txt = f"{pval:+d}%" if pval != 0 else "0%"
        vol_str = f"{st.get('volume', 85)}%" if not st.get("muted") else "\033[38;2;255;64;64mMUTED\033[0m"
        r1 = f" {badge}{rec_d} \033[38;2;255;255;255m{tname}{NC} │ \033[38;2;0;229;255m{st.get('position_fmt', '00:00')}/{st.get('duration_fmt', '00:00')}{NC} │ Vol: \033[38;2;0;229;255m{vol_str}{NC} │ \033[38;2;255;215;0mPitch: {p_txt}{NC} "
        next_mode_lbl = "Full" if is_lg else "Mini"
        r2 = f" 🎛 [{m_str}] │ EQ: {bold_s}{c2}{self.visualizer.get_style_display_name()[:14]}{NC} │ 🎨 {c1}{self.visualizer.get_theme_display_name()[:10]}{NC} │ \033[38;2;255;215;0m[M] {next_mode_lbl}{NC} "
        micro_hdr = "✦ MP MICRO AUDIO PLAYER (LIQUID GLASS) ✦" if is_lg else "✦ MP MICRO AUDIO PLAYER ✦"
        if is_lg:
            lines = [
                f"  {c1}╭─ {micro_hdr} {'─' * max(0, iw - _display_width(micro_hdr) - 4)}╮{NC}",
                f"  {c1}│{NC}{r1}{' ' * max(0, iw - _display_width(r1))}{c1}│{NC}",
                f"  {c1}│{NC}{r2}{' ' * max(0, iw - _display_width(r2))}{c1}│{NC}",
                f"  {c1}╰{'─' * iw}╯{NC}"
            ]
        else:
            lines = [
                f"  {BOLD}{c1}╭─ ✦ MP MICRO AUDIO PLAYER ✦ {'─' * max(0, iw - 28)}╮{NC}",
                f"  {BOLD}{c1}│{NC}{r1}{' ' * max(0, iw - _display_width(r1))}{BOLD}{c1}│{NC}",
                f"  {BOLD}{c1}│{NC}{r2}{' ' * max(0, iw - _display_width(r2))}{BOLD}{c1}│{NC}",
                f"  {BOLD}{c1}╰{'─' * iw}╯{NC}"
            ]
        if h >= 9: lines.extend(self.visualizer.render(st, width=iw + 4, height=(2 if h >= 12 else 1)))
        if t_now < self.notification_time and self.notification_msg: lines.append(f"  {bold_s}\033[38;2;0;255;127m📂 {self.notification_msg}{NC}")
        else:
            m_hint = "[M] Full" if is_lg else "[M] Mini"
            m_hint_short = "M Full" if is_lg else "M Mini"
            lines.append(_fit_text_line([
                f"  \033[1;38;2;0;229;255m[Space]{NC} \033[38;2;235;240;255mPlay{NC}  \033[1;38;2;0;229;255m[Q]{NC} \033[38;2;235;240;255mQue{NC}  \033[1;38;2;0;229;255m[R]{NC} \033[38;2;235;240;255mRec{NC}  \033[1;38;2;0;229;255m[G]{NC} \033[38;2;235;240;255mSpek{NC}  \033[1;38;2;0;229;255m[n/p]{NC} \033[38;2;235;240;255mSkip{NC}  \033[1;38;2;0;229;255m[v/V]{NC} \033[38;2;235;240;255mVol{NC}  \033[1;38;2;0;229;255m[s]{NC} \033[38;2;235;240;255mShuf{NC}  \033[1;38;2;0;229;255m[e]{NC} \033[38;2;235;240;255mEQ{NC}  \033[1;38;2;0;229;255m[c]{NC} \033[38;2;235;240;255mTheme{NC}  \033[1;38;2;255;215;0m{m_hint}{NC}  \033[1;38;2;255;64;64m[b]{NC} \033[38;2;235;240;255mClose{NC}",
                f"  \033[1;38;2;0;229;255m[Space]{NC} \033[38;2;235;240;255mPlay{NC}  \033[1;38;2;0;229;255m[Q]{NC} \033[38;2;235;240;255mQue{NC}  \033[1;38;2;0;229;255m[R]{NC} \033[38;2;235;240;255mRec{NC}  \033[1;38;2;0;229;255m[n/p]{NC} \033[38;2;235;240;255mSkip{NC}  \033[1;38;2;0;229;255m[v/V]{NC} \033[38;2;235;240;255mVol{NC}  \033[1;38;2;0;229;255m[s]{NC} \033[38;2;235;240;255mShuf{NC}  \033[1;38;2;0;229;255m[e]{NC} \033[38;2;235;240;255mEQ{NC}  \033[1;38;2;0;229;255m[c]{NC} \033[38;2;235;240;255mTheme{NC}  \033[1;38;2;255;215;0m{m_hint}{NC}  \033[1;38;2;255;64;64m[b]{NC} \033[38;2;235;240;255mClose{NC}",
                f"  \033[1;38;2;0;229;255mSpace{NC} \033[38;2;235;240;255mPlay{NC}  \033[1;38;2;0;229;255mQ{NC} \033[38;2;235;240;255mQue{NC}  \033[1;38;2;0;229;255mR{NC} \033[38;2;235;240;255mRec{NC}  \033[1;38;2;0;229;255mn/p{NC} \033[38;2;235;240;255mSkip{NC}  \033[1;38;2;0;229;255mv/V{NC} \033[38;2;235;240;255mVol{NC}  \033[1;38;2;0;229;255ms{NC} \033[38;2;235;240;255mShuf{NC}  \033[1;38;2;0;229;255me{NC} \033[38;2;235;240;255mEQ{NC}  \033[1;38;2;0;229;255mc{NC} \033[38;2;235;240;255mTheme{NC}  \033[1;38;2;255;215;0m{m_hint_short}{NC}  \033[1;38;2;255;64;64mb{NC} \033[38;2;235;240;255mClose{NC}"
            ], max(20, w - 1)))
        if is_lg:
            lines = [_strip_bold_ansi(l) for l in lines]
        _present_frame(lines, w, h)

def _spawn_player_daemon(file_path: Optional[str] = None, auto_bluetooth: bool = True, mode: str = "MIX_ARCHIVE", music_folder: Optional[str] = None, playlist_path: Optional[str] = None, seek_to: Optional[float] = None) -> Optional[int]:
    if is_player_daemon_running():
        return None
    _cleanup_stale_daemon_files()
    cmd = [sys.executable, str(Path(__file__).resolve()), "--daemon"] + ([] if auto_bluetooth else ["--no-bluetooth-auto"])
    if mode == "MUSIC":
        cmd.append("--music-mode")
        if music_folder: cmd.extend(["--music-folder", str(music_folder)])
        if playlist_path: cmd.extend(["--playlist", str(playlist_path)])
    if seek_to is not None and float(seek_to) > 0:
        cmd.extend(["--seek-to", str(seek_to)])
    cleaned = _existing_audio_path(file_path) if file_path else ""
    if cleaned:
        cmd.append(cleaned)
    try:
        proc = subprocess.Popen(cmd, cwd=str(get_base_dir()), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        # Auto-start Traktor S4 MIDI controller service if configured
        try:
            s4_script = Path(__file__).resolve().parent / "scripts" / "traktor_s4_midi.py"
            if not s4_script.is_file(): s4_script = Path(__file__).resolve().parent / "traktor_s4_midi.py"
            if s4_script.is_file() and os.environ.get("MIDI_CONTROL_ENABLED", "true").lower() != "false":
                subprocess.Popen([sys.executable, str(s4_script), "--start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass
        return proc.pid
    except Exception as exc:
        try: mp_log_error("MP_Audio_Player", f"Failed spawning player daemon: {exc}", exc)
        except Exception: pass
        return None

def _install_windows_console_close():
    if sys.platform != "win32": return
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    cb = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)(lambda c: (os._exit(0) if c in (2, 5, 6) else 0))
    k.SetConsoleCtrlHandler(cb, 1)

def main():
    p = argparse.ArgumentParser(description=f"MP Audio Player (MP Mix Manager v{VERSION}) - High Resolution Playback & Custom Animated Equalizer")
    p.add_argument("--version", "-v", action="version", version=f"MP Audio Player (MP Mix Manager v{VERSION})")
    p.add_argument("file", nargs="?", help="Audio file path to play immediately")
    for flags, kw in [
        (("--daemon",), dict(action="store_true")), (("--interactive", "-i"), dict(action="store_true")),
        (("--play",), dict(nargs="?", const="")), (("--pause",), dict(action="store_true")),
        (("--toggle",), dict(action="store_true")), (("--stop",), dict(action="store_true")),
        (("--next",), dict(action="store_true")), (("--prev",), dict(action="store_true")),
        (("--pitch",), dict(type=int)), (("--pitch-up",), dict(type=int, nargs="?", const=1)),
        (("--pitch-down",), dict(type=int, nargs="?", const=1)), (("--pitch-reset",), dict(action="store_true")),
        (("--vol",), dict(type=str)), (("--seek",), dict(type=float)),
        (("--seek-to", "--position"), dict(type=float, default=None)),
        (("--resume",), dict(action="store_true")),
        (("--status",), dict(action="store_true")), (("--status-line",), dict(action="store_true")),
        (("--play-latest",), dict(action="store_true")), (("--get-latest-mix",), dict(action="store_true")),
        (("--list-mixes",), dict(action="store_true")), (("--open-file-manager", "-f"), dict(action="store_true")),
        (("--tracklist", "-t"), dict(action="store_true")), (("--export-playlist", "-e"), dict(nargs="?", const="default")),
        (("--style", "--eq"), dict(type=str, choices=EqualizerVisualizer.STYLES)), (("--theme",), dict(type=str, choices=EqualizerVisualizer.THEMES)),
        (("--cmd",), dict(type=str)), (("--music-mode",), dict(action="store_true")), (("--mix-archive-mode",), dict(action="store_true")),
        (("--music-folder",), dict(type=str, default="ALL")), (("--playlist",), dict(type=str, default="")),
        (("--no-bluetooth-auto",), dict(action="store_true")), (("--bluetooth-status",), dict(action="store_true")),
        (("--bluetooth-route",), dict(action="store_true")), (("--mini",), dict(action="store_true")),
        (("--micro",), dict(action="store_true")), (("--spek", "--generate-spek", "-g"), dict(action="store_true")),
        (("--new-window", "--window", "-w"), dict(action="store_true")), (("--only-if-running",), dict(action="store_true")),
        (("--shuffle",), dict(action="store_true")), (("--repeat",), dict(action="store_true")),
        (("--liquid", "--liquid-glass", "--glass"), dict(action="store_true", help="Launch MP Audio Player in Liquid Glass mode")),
        (("--visualizer", "--liquid-visualizer"), dict(action="store_true", help="Launch MP Liquid Visualizer (1400x1400 fixed borderless Vulkan 3D)")),
        (("--visualizer-preset",), dict(type=str, default=None, help="Select MP Liquid Visualizer preset (e.g. 'Cosmic Dreamworlds (Liquid)')")),
        (("--list-visualizer-presets",), dict(action="store_true", help="List available MP Liquid Visualizer presets")),
        (("--queue", "-q"), dict(type=str, nargs="?", const="")), (("--clear-queue",), dict(action="store_true")),
        (("--record", "--toggle-record", "-r"), dict(action="store_true")),
        (("--eq-preset",), dict(type=str, help="Set active equalizer preset (Flat, Ambient, Trance, Techno, House, Progressive, Vapourwave, or custom)")),
        (("--list-eq-presets",), dict(action="store_true", help="List all available equalizer presets and their dB curves")),
        (("--eq-bands",), dict(type=str, help="Set 10-band equalizer gains in dB (e.g. '3.0,2.5,1.5,0,-1,-1.5,-0.5,1,2,2.5')")),
        (("--reset-eq",), dict(action="store_true", help="Reset equalizer to Flat preset (0 dB on all bands)"))
    ]: p.add_argument(*flags, **kw)

    args, _ = p.parse_known_args()
    base_dir = get_base_dir()
    is_music = bool(args.music_mode or args.playlist or (args.music_folder and args.music_folder != "ALL"))
    current_mode, folder_target, auto_bt = ("MUSIC" if is_music else "MIX_ARCHIVE"), (args.music_folder if is_music else "ALL"), not args.no_bluetooth_auto

    if args.get_latest_mix:
        if latest := MixArchiveScanner(base_dir).get_latest_mix(): print(latest["path"]); sys.exit(0)
        sys.exit(1)

    if args.list_mixes:
        scanner = MusicFolderPlaylistScanner(folder_target, playlist_path=args.playlist) if is_music else MixArchiveScanner(base_dir)
        for m in scanner.get_mixes():
            info_col = m.get("duration_fmt", "00:00") if is_music else f"{m['size_mb']:.1f}MB"
            print(f"{m['path']}\t{info_col}\t{m['name']}")
        sys.exit(0)

    daemon_running = is_player_daemon_running()

    if args.bluetooth_status:
        if daemon_running: print(json.dumps((send_ipc_command("bluetooth_status") or {}).get("bluetooth", {}), indent=2))
        elif get_bluetooth_audio_status: print(json.dumps(get_bluetooth_audio_status(), indent=2))
        else: print(json.dumps({"bluetooth_connected": False, "error": "Router unavailable"}, indent=2))
        sys.exit(0)

    if args.bluetooth_route:
        if daemon_running:
            res = send_ipc_command("route_bluetooth")
            print("✔ Sent route command to player daemon:" if (res and res.get("routed")) else "✖ Failed to route to Bluetooth:")
            print(json.dumps(res or {}, indent=2))
        elif BluetoothAudioRouter:
            print("✔ Routed system audio to Bluetooth" if BluetoothAudioRouter().route_to_bluetooth() else "✖ Failed to route to Bluetooth")
        sys.exit(0)

    if args.open_file_manager or args.tracklist:
        tp = (st.get("data", {}).get("path") if (daemon_running and (st := send_ipc_command("status"))) else None)
        if not tp or not os.path.exists(tp):
            if latest := MixArchiveScanner(base_dir).get_latest_mix(): tp = latest["path"]
        if args.open_file_manager:
            target = choose_file_manager_target(tp)
            ok = bool(target) and open_in_file_manager(target)
            print(f"✔ Opened in file manager: {target}" if ok else "✖ Failed to open file manager")
            sys.exit(0 if ok else 1)
        tl = find_tracklist_for_mix(tp) if tp else None
        if tl and os.path.isfile(tl) and open_tracklist_window(tl, tp, theme=args.theme): print(f"✔ Opened tracklist: {tl}"); sys.exit(0)
        print("✖ Tracklist not found" if tp else "✖ No mix available", file=sys.stderr); sys.exit(1)

    if args.export_playlist is not None:
        mixes = MixArchiveScanner(base_dir).get_mixes()
        dest = os.path.expanduser("~/Desktop/MP_Archive_Playlist.m3u") if (args.export_playlist in ("default", "") or not args.export_playlist) else args.export_playlist
        ok, res = export_playlist_m3u(mixes, dest)
        print(f"✔ Exported {len(mixes)} mixes to .m3u playlist: {res}" if ok else f"✖ Failed to export playlist: {res}")
        sys.exit(0 if ok else 1)

    if args.spek:
        tp = os.path.abspath(args.file) if (args.file and os.path.exists(args.file)) else ((st.get("data", {}).get("path") if (daemon_running and (st := send_ipc_command("status"))) else None))
        if not tp:
            if is_music:
                if mixes := MusicFolderPlaylistScanner(folder_target, playlist_path=args.playlist).get_mixes(): tp = mixes[0]["path"]
            elif latest := MixArchiveScanner(base_dir).get_latest_mix(): tp = latest["path"]
        if not tp or not os.path.isfile(tp): print("✖ No audio file available for Spek generation", file=sys.stderr); sys.exit(1)
        if (ex := find_existing_spek(tp, mode=current_mode)) and os.path.isfile(ex):
            print(f"✔ Spek already exists ({os.path.getsize(ex) // 1024} KB): {ex}")
            open_image_viewer(ex)
            sys.exit(0)
        print(f"MP Audio Player is generating a Spek for {os.path.basename(tp)}. It will open when finished.")
        notify_desktop("MP Audio Player", f"MP Audio Player is generating a Spek for {os.path.basename(tp)}")
        ok, res = generate_track_spek(tp, mode=current_mode)
        if ok:
            print(f"✔ Spek generated successfully ({os.path.getsize(res) // 1024} KB): {res}")
            open_image_viewer(res)
            sys.exit(0)
        print(f"✖ Spek generation failed: {res}", file=sys.stderr); sys.exit(1)

    if args.list_visualizer_presets:
        vis_script = base_dir / "MP_Liquid_Visualizer.py"
        if not vis_script.is_file():
            vis_script = base_dir / "scripts" / "mp_liquid_visualizer_vulkan.py"
        sys.exit(subprocess.call([sys.executable, str(vis_script), "--list-presets"]))

    if args.visualizer_preset and not args.visualizer:
        vis_script = base_dir / "MP_Liquid_Visualizer.py"
        if not vis_script.is_file():
            vis_script = base_dir / "scripts" / "mp_liquid_visualizer_vulkan.py"
        sys.exit(subprocess.call([sys.executable, str(vis_script), "--set-preset", str(args.visualizer_preset)]))

    if args.visualizer:
        ok = launch_liquid_visualizer(base_dir, preset=args.visualizer_preset)
        if ok:
            p_label = args.visualizer_preset or "Active Preset"
            print(f"✔ Launched MP Liquid Visualizer [{p_label}] — 1400x1400 Fixed Borderless Vulkan")
            sys.exit(0)
        print("✖ Failed to launch MP Liquid Visualizer", file=sys.stderr)
        sys.exit(1)

    if args.liquid:
        sys.exit(
            0
            if launch_liquid_glass_player(
                base_dir,
                mode=("MUSIC" if args.music_mode else ("MIX_ARCHIVE" if args.mix_archive_mode else None)),
                folder_name=(args.music_folder if is_music else None),
                playlist_path=(args.playlist or None),
                theme=args.theme,
                style=args.style,
                mini=bool(args.mini),
                micro=bool(args.micro),
            )
            else 1
        )

    if args.new_window:
        if daemon_running:
            try:
                st = send_ipc_command("status")
                if st and isinstance(st.get("data"), dict):
                    d_data = st["data"]
                    if d_mode := d_data.get("mode"):
                        if not args.music_mode and not args.mix_archive_mode:
                            current_mode = d_mode
                            is_music = (current_mode == "MUSIC")
            except Exception: pass
        if args.mini or args.micro:
            sys.exit(0 if launch_mini_player_window(current_mode, folder_target, args.playlist, args.theme, args.style, micro=bool(args.micro)) else 1)
        sys.exit(0 if launch_player_window(current_mode, folder_target, args.playlist, args.theme, args.style) else 1)

    if args.cmd:
        if res := send_ipc_command(args.cmd): print(json.dumps(res)); sys.exit(0)
        sys.exit(1)

    if args.play_latest:
        if latest := MixArchiveScanner(base_dir).get_latest_mix():
            if not (daemon_running and send_ipc_command("play", file=latest["path"])):
                _spawn_player_daemon(latest["path"], auto_bluetooth=auto_bt, mode=current_mode)
            sys.exit(0)
        sys.exit(1)

    if args.toggle:
        if daemon_running and send_ipc_command("toggle"): sys.exit(0)
        res_data = None
        if RESUME_STATE_FILE.is_file():
            try: res_data = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
            except Exception: pass
        if res_data and res_data.get("path") and os.path.isfile(res_data["path"]):
            target_file = res_data["path"]
            target_pos = float(res_data.get("position_sec", 0.0) or 0.0)
            if daemon_running and send_ipc_command("play", file=target_file, position=target_pos):
                sys.exit(0)
            if not args.only_if_running:
                _spawn_player_daemon(target_file, auto_bluetooth=auto_bt, mode=res_data.get("mode", current_mode), seek_to=target_pos)
                sys.exit(0)
        if not args.only_if_running and (latest := MixArchiveScanner(base_dir).get_latest_mix()):
            _spawn_player_daemon(latest["path"], auto_bluetooth=auto_bt, mode=current_mode)
        sys.exit(0)

    if args.pause or args.stop or args.next or args.prev:
        if daemon_running: send_ipc_command("pause" if args.pause else ("stop" if args.stop else ("next" if args.next else "prev")))
        sys.exit(0)

    if args.shuffle:
        if daemon_running:
            res = send_ipc_command("shuffle") or {}
            print(f"✔ Shuffle mode: {'ON' if res['shuffle'] else 'OFF'}" if "shuffle" in res else "✔ Shuffle toggled")
        sys.exit(0)

    if args.repeat:
        if daemon_running:
            res = send_ipc_command("repeat") or {}
            print(f"✔ Repeat mode: {res['repeat'].upper()}" if "repeat" in res else "✔ Repeat mode cycled")
        sys.exit(0)

    if args.record:
        if daemon_running:
            res = send_ipc_command("toggle_record") or {}
            print(f"✔ Live WAV Recording Started: {res.get('recording_file', '')} (Max 3GB per WAV)" if res.get("recording") else "✔ Live WAV Recording Stopped & Saved to MP_AUDIOWAV_REC_OUTPUT")
        else: print("Player daemon not running.")
        sys.exit(0)

    if args.resume:
        res_data = None
        if RESUME_STATE_FILE.is_file():
            try: res_data = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
            except Exception: pass
        if res_data and res_data.get("path") and os.path.isfile(res_data["path"]):
            target_file = res_data["path"]
            target_pos = float(res_data.get("position_sec", 0.0) or 0.0)
            if daemon_running and send_ipc_command("play", file=target_file, position=target_pos):
                print(f"✔ Resumed playback: {os.path.basename(target_file)} at {format_seconds(target_pos)}")
                sys.exit(0)
            _spawn_player_daemon(target_file, auto_bluetooth=auto_bt, mode=res_data.get("mode", current_mode), seek_to=target_pos)
            print(f"✔ Started player daemon and resumed: {os.path.basename(target_file)} at {format_seconds(target_pos)}")
            sys.exit(0)
        else:
            print("✖ No previous mix available to resume.", file=sys.stderr)
            sys.exit(1)

    # Liquid Glass always embeds this script with --interactive. A startup resume
    # also passes --play and --seek-to. Those flags must load the mix inside the
    # window. Exiting here makes the embedded terminal quit and the glass window closes.
    ui_session = bool(args.interactive or args.mini or args.micro)

    if args.play is not None and not ui_session:
        ftp = _existing_audio_path(args.play or (args.file or "")) if (args.play or args.file) else ""
        pos = float(args.seek_to) if args.seek_to is not None else None
        res_data = None
        if RESUME_STATE_FILE.is_file():
            try: res_data = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
            except Exception: pass
        if not ftp and res_data and res_data.get("path") and os.path.isfile(res_data["path"]):
            ftp = res_data["path"]
            if pos is None:
                pos = float(res_data.get("position_sec", 0.0) or 0.0)
            if not args.music_mode and not args.mix_archive_mode:
                if res_data.get("mode") == "MUSIC":
                    current_mode = "MUSIC"
        elif ftp and pos is None and res_data and res_data.get("path") == ftp:
            pos = float(res_data.get("position_sec", 0.0) or 0.0)
        if pos is None:
            pos = 0.0
        if not (daemon_running and send_ipc_command("play", file=ftp or None, position=pos)):
            if not ftp and (l := MixArchiveScanner(base_dir).get_latest_mix()): ftp = l["path"]
            if ftp: _spawn_player_daemon(ftp, auto_bluetooth=auto_bt, mode=current_mode, seek_to=pos)
        sys.exit(0)

    if args.clear_queue:
        print(f"✔ Cleared {(send_ipc_command('clear_queue') or {}).get('cleared', 0)} mix(es) from playback queue." if daemon_running else "Player daemon not running.")
        sys.exit(0)

    if args.queue is not None:
        qt = os.path.abspath(args.queue or (args.file or "")) if (args.queue or args.file) else ""
        if not qt and (latest := MixArchiveScanner(base_dir).get_latest_mix()): qt = latest["path"]
        if qt and os.path.exists(qt):
            if daemon_running and (res := send_ipc_command("queue", file=qt)):
                print(f"✔ Queued track (#{res.get('queue_len', '?')} in queue): {os.path.basename(qt)}")
            else:
                _spawn_player_daemon(qt, auto_bluetooth=auto_bt, mode=current_mode)
                print(f"✔ Started player daemon with mix: {os.path.basename(qt)}")
            sys.exit(0)
        print(f"✖ File not found to queue: {qt}", file=sys.stderr); sys.exit(1)

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
            send_ipc_command("vol_up" if v[0] == "+" else "vol_down", step=abs(int(v))) if v.startswith(("+", "-")) else send_ipc_command("set_volume", volume=int(v))
        sys.exit(0)

    if args.seek is not None:
        if daemon_running: send_ipc_command("seek", seconds=args.seek)
        sys.exit(0)

    if args.seek_to is not None and args.play is None and not args.daemon and not ui_session:
        if daemon_running: send_ipc_command("seek_to", position=args.seek_to)
        sys.exit(0)

    if args.status or args.status_line:
        data = (send_ipc_command("status") or {}).get("data") if daemon_running else None
        if args.status: print(json.dumps(data or {"running": False, "state": "stopped"}, indent=2))
        elif data:
            pval = data.get("pitch_percent", 0)
            p_str = f"Pitch: {pval:+d}%" if pval != 0 else "Pitch: 0%"
            eq_s = f"EQ: {data.get('eq_preset', 'Flat')}"
            print(f"{'▶' if data['state'] == 'playing' else '⏸'} {data['title']} [{data['position_fmt']}/{data['duration_fmt']}] ({data['mini_eq']}) {p_str} {eq_s} Vol: {data['volume']}%")
        else: print("○ MP Audio Player: Stopped")
        sys.exit(0)

    if args.list_eq_presets:
        mgr = EqualizerManager()
        presets = mgr.get_all_presets()
        print("MP Audio Player 10-Band Equalizer Presets:")
        print("  Frequencies:  " + "  ".join(f"{f:>6s}" for f in EQ_BAND_LABELS))
        for name in mgr.get_all_preset_names():
            gains = presets.get(name, [])
            g_str = "  ".join(f"{g:+6.1f}" for g in gains)
            d_mark = " (Default)" if name == "Flat" else ""
            print(f"  • {name:<14s}{d_mark}: {g_str} dB")
        sys.exit(0)

    if args.eq_preset:
        target_preset = args.eq_preset
        if daemon_running:
            res = send_ipc_command("set_eq_preset", preset=target_preset) or {}
            if res.get("success"):
                print(f"✔ Equalizer preset set to: {res.get('preset')}")
                sys.exit(0)
            else:
                print(f"✖ Failed to set equalizer preset: {target_preset}", file=sys.stderr)
                sys.exit(1)
        else:
            mgr = EqualizerManager()
            if mgr.apply_preset(target_preset):
                print(f"✔ Equalizer preset saved as default: {mgr.active_preset}")
                sys.exit(0)
            else:
                print(f"✖ Unknown equalizer preset: {target_preset}", file=sys.stderr)
                sys.exit(1)

    if args.reset_eq:
        if daemon_running:
            send_ipc_command("reset_eq")
            print("✔ Equalizer reset to Flat (0 dB)")
            sys.exit(0)
        else:
            mgr = EqualizerManager()
            mgr.apply_preset("Flat")
            print("✔ Equalizer reset to Flat (0 dB)")
            sys.exit(0)

    if args.eq_bands:
        try:
            parts = [float(x.strip()) for x in args.eq_bands.split(",")]
            if len(parts) != 10:
                print("✖ Exactly 10 band gains (dB) required separated by commas.", file=sys.stderr)
                sys.exit(1)
            if daemon_running:
                res = send_ipc_command("set_eq_bands", bands=parts) or {}
                print(f"✔ Equalizer bands updated (Preset: {res.get('preset', 'Custom')})")
                sys.exit(0)
            else:
                mgr = EqualizerManager()
                mgr.set_bands(parts)
                print("✔ Equalizer custom bands saved.")
                sys.exit(0)
        except Exception as exc:
            print(f"✖ Invalid band values: {exc}", file=sys.stderr)
            sys.exit(1)

    if args.interactive or args.mini or args.micro or (not args.daemon and sys.stdin.isatty()):
        d_status = send_ipc_command("status") if daemon_running else None
        if daemon_running and not d_status:
            daemon_running = False
        elif daemon_running and d_status and isinstance(d_status.get("data"), dict):
            d_data = d_status["data"]
            if d_mode := d_data.get("mode"):
                if not args.music_mode and not args.mix_archive_mode:
                    current_mode = d_mode
                    is_music = (current_mode == "MUSIC")

        scanner = MusicFolderPlaylistScanner(folder_name=folder_target, playlist_path=args.playlist) if is_music else MixArchiveScanner(base_dir)
        mixes = scanner.get_mixes()
        requested = (args.play or args.file or "") if args.play is not None else (args.file or "")
        tf = (_existing_audio_path(requested) or None) if requested else None

        if not daemon_running:
            resume_f, resume_pos = None, 0.0
            if not tf and RESUME_STATE_FILE.is_file():
                try:
                    res_data = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
                    if res_data and res_data.get("path") and os.path.isfile(res_data["path"]):
                        resume_f = res_data["path"]
                        resume_pos = float(res_data.get("position_sec", 0.0) or 0.0)
                        if not args.music_mode and not args.mix_archive_mode:
                            if res_data.get("mode") == "MUSIC":
                                current_mode = "MUSIC"
                                is_music = True
                                scanner = MusicFolderPlaylistScanner(folder_name=folder_target, playlist_path=args.playlist)
                                mixes = scanner.get_mixes()
                except Exception: pass
            elif not tf and not (CONFIG_DIR / ".first_run_sample_loaded").exists():
                sample_track = base_dir / "MP_SAMPLES" / "MPlanetarian - Ecology of the Earth (Cosmic Dreamworlds Remake).flac"
                if sample_track.is_file():
                    resume_f = str(sample_track.resolve())
                    resume_pos = 0.0
                    try:
                        (CONFIG_DIR / ".first_run_sample_loaded").touch(exist_ok=True)
                        RESUME_STATE_FILE.write_text(json.dumps({
                            "path": resume_f,
                            "position_sec": 0.0,
                            "duration_sec": 1014.42,
                            "title": "MPlanetarian - Ecology of the Earth (Cosmic Dreamworlds Remake)",
                            "mode": "MIX_ARCHIVE",
                            "player": "mp_audio_player",
                            "timestamp": time.time()
                        }, indent=2), encoding="utf-8")
                    except Exception: pass
            latest = scanner.get_latest_mix() if not is_music else (mixes[0] if mixes else None)
            init_f = tf or resume_f or (latest["path"] if latest else (mixes[0]["path"] if mixes else None))
            if tf and args.seek_to is not None:
                init_pos = float(args.seek_to)
            elif not tf and resume_f:
                init_pos = resume_pos
            else:
                init_pos = 0.0
            spawned_pid = _spawn_player_daemon(init_f, auto_bluetooth=auto_bt, mode=current_mode, music_folder=folder_target, playlist_path=args.playlist, seek_to=init_pos)
            for _ in range(75):
                time.sleep(0.04)
                if (SOCKET_PATH.exists() or PORT_FILE.exists()) and is_player_daemon_running(): break
        else:
            spawned_pid = None
            d_data = d_status.get("data", {}) if d_status else {}
            d_state = d_data.get("state", "stopped")
            if tf:
                play_kw = {"file": tf}
                if args.seek_to is not None:
                    play_kw["position"] = float(args.seek_to)
                send_ipc_command("play", **play_kw)
            elif d_state == "stopped" or not d_data.get("path"):
                resume_f, resume_pos = None, 0.0
                if RESUME_STATE_FILE.is_file():
                    try:
                        res_data = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
                        if res_data and res_data.get("path") and os.path.isfile(res_data["path"]):
                            resume_f = res_data["path"]
                            resume_pos = float(res_data.get("position_sec", 0.0) or 0.0)
                    except Exception: pass
                if resume_f:
                    send_ipc_command("play", file=resume_f, position=resume_pos)
                elif is_music:
                    send_ipc_command("load_playlist", mode="MUSIC", folder_name=folder_target, playlist_path=args.playlist, play=True)
                elif latest := scanner.get_latest_mix():
                    send_ipc_command("play", file=latest["path"])
        _retire_extra_player_daemons(prefer_pid=spawned_pid)

        ui_mode = "MICRO" if args.micro else ("MINI" if args.mini else "NORMAL")
        def _term_sig(s, f):
            try:
                sys.stdout.write("\033[?25h\033[?1049l\033[0m")
                sys.stdout.flush()
            except Exception: pass
            os._exit(0)
        for sig in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", None)):
            if sig:
                try: signal.signal(sig, _term_sig)
                except Exception: pass
        TerminalPlayerUI(None, scanner, is_remote=True, default_style=args.style, default_theme=args.theme, mode=current_mode, folder_name=folder_target, ui_size_mode=ui_mode).run()
        sys.exit(0)

    if args.daemon:
        if not _acquire_daemon_lock():
            sys.exit(0)
        try: PID_FILE.write_text(str(os.getpid()))
        except OSError: pass
        _retire_extra_player_daemons(prefer_pid=os.getpid())
        _install_windows_console_close()
        def _sig(s, f):
            try:
                for p in (STATE_FILE, SOCKET_PATH, PORT_FILE, PID_FILE): p.unlink(missing_ok=True)
            except Exception: pass
            os._exit(0)
        for sig in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", None)):
            if sig:
                try: signal.signal(sig, _sig)
                except Exception: pass

    scanner = MusicFolderPlaylistScanner(folder_name=folder_target, playlist_path=args.playlist) if is_music else MixArchiveScanner(base_dir)
    mixes, init_idx, explicit_missing = scanner.get_mixes(), 0, False
    if args.file:
        tp = _existing_audio_path(args.file)
        if not tp:
            explicit_missing = True
        else:
            for i, m in enumerate(mixes):
                if m["path"] == tp: init_idx = i; break
            else:
                mixes.insert(0, {"name": os.path.basename(tp), "path": tp, "size_mb": os.path.getsize(tp) / 1048576.0, "mtime": time.time(), "ext": os.path.splitext(tp)[1][1:].upper()})
                init_idx = 0

    init_pos = float(args.seek_to) if args.seek_to is not None else 0.0
    engine = AudioEngine(mixes, auto_bluetooth=auto_bt, mode=current_mode)
    PlayerIPCServer(engine).start()
    if mixes and not explicit_missing: engine.load_track(init_idx, True, start_position=init_pos)

    try:
        while True:
            if engine.state == "playing": engine._ensure_stream()
            engine.check_track_end()
            time.sleep(0.5)
    except (KeyboardInterrupt, SystemExit): pass
    finally:
        try:
            if engine.current_track and engine.current_track.get("path"):
                saved_pos = round(float(engine.position_sec), 2)
                if saved_pos <= 0.0 and RESUME_STATE_FILE.is_file():
                    try:
                        prev = json.loads(RESUME_STATE_FILE.read_text(encoding="utf-8"))
                        if prev.get("path") == str(engine.current_track.get("path")):
                            prev_pos = float(prev.get("position_sec", 0.0))
                            if prev_pos > 0.0:
                                saved_pos = prev_pos
                    except Exception: pass
                res_tmp = RESUME_STATE_FILE.with_suffix(".tmp")
                res_tmp.write_text(json.dumps({
                    "path": str(engine.current_track.get("path")),
                    "position_sec": saved_pos,
                    "duration_sec": round(float(engine.duration_sec), 2),
                    "title": str(engine.current_track.get("name", "")),
                    "mode": str(engine.mode),
                    "player": "mp_audio_player",
                    "timestamp": time.time()
                }), encoding="utf-8")
                res_tmp.replace(RESUME_STATE_FILE)
        except Exception: pass
        engine.stop_playback(reset_position=False)
        for p in (PID_FILE, SOCKET_PATH, PORT_FILE): p.unlink(missing_ok=True)
        try: STATE_FILE.write_text(json.dumps({"running": False, "state": "stopped"}), encoding="utf-8")
        except OSError: pass
        sys.exit(0)

if __name__ == "__main__":
    main()