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
import os, re, sys, time, math, random, json, socket, select, shutil, argparse, threading, subprocess, unicodedata
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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

RED, GREEN, YELLOW = COLOR_TRAFFIC_RED, COLOR_TRAFFIC_GREEN, COLOR_TRAFFIC_AMBER
MAGENTA, CYAN = COLOR_HOT_PURPLE, COLOR_LILAC

CONFIG_DIR = Path.home() / ".config" / "mix-manager"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SOCKET_PATH, PORT_FILE = CONFIG_DIR / "mp_audio_player.sock", CONFIG_DIR / "mp_audio_player.port"
STATE_FILE, PID_FILE = CONFIG_DIR / "mp_player_state.json", CONFIG_DIR / "mp_player.pid"

AUDIO_EXTENSIONS = ('.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac', '.aiff', '.wma')
UNICODE_BLOCKS = [' ', ' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']

def get_base_dir() -> Path:
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "scripts" else p.parent

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

def _run_bg(cmd: List[str]) -> bool:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False

def open_in_file_manager(target_path: Union[str, Path, None]) -> bool:
    if not target_path: return False
    p = Path(target_path).expanduser().resolve()
    if not p.exists():
        p = p.parent if p.parent.exists() else None
        if not p: return False

    is_file = p.is_file()
    folder_dir, target_str = str(p.parent if is_file else p), str(p)

    if sys.platform == "darwin":
        return _run_bg(["open", "-R", target_str] if is_file else ["open", folder_dir])
    if sys.platform == "win32":
        return _run_bg(["explorer.exe", f"/select,{target_str}"] if is_file else ["explorer.exe", folder_dir])

    if Path("/proc/version").exists():
        try:
            if "microsoft" in Path("/proc/version").read_text(errors="ignore").lower():
                if shutil.which("wslpath") and shutil.which("explorer.exe"):
                    wp = subprocess.run(["wslpath", "-w", target_str if is_file else folder_dir], capture_output=True, text=True).stdout.strip()
                    if wp: return _run_bg(["explorer.exe", f"/select,{wp}"] if is_file else ["explorer.exe", wp])
                if shutil.which("wslview"): return _run_bg(["wslview", folder_dir])
        except Exception:
            pass

    for bin_name, args in [
        ("dolphin", ["--new-window"] + (["--select", target_str] if is_file else [folder_dir])),
        ("nautilus", ["--select", target_str] if is_file else ["--new-window", folder_dir]),
        ("nemo", ["--no-desktop", target_str] if is_file else [folder_dir]),
        ("thunar", [folder_dir]), ("pcmanfm-qt", [folder_dir]), ("pcmanfm", [folder_dir]),
        ("gio", ["open", folder_dir]), ("xdg-open", [folder_dir])
    ]:
        if shutil.which(bin_name) and _run_bg([bin_name] + args):
            return True
    return False

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

def open_tracklist_window(target_tracklist: Union[str, Path, None]) -> bool:
    if not target_tracklist: return False
    tl = Path(target_tracklist).expanduser().resolve()
    if not tl.is_file(): return False

    base = get_base_dir()
    v_sh = base / "scripts" / "view_tracklist_console.sh"
    if not v_sh.is_file(): v_sh = base / "view_tracklist_console.sh"
    t_str, v_str, title = str(tl), str(v_sh), "Mix Tracklist Viewer"

    cust = os.environ.get("TRACKLIST_VIEWER")
    if cust and cust not in ("console", "auto") and shutil.which(cust) and _run_bg([cust, t_str]):
        return True

    if sys.platform.startswith(("linux", "freebsd")):
        if shutil.which("konsole") and v_sh.is_file():
            if _run_bg(["konsole", "--hide-menubar", "--hide-tabbar", "--separate", "--qwindowtitle", title,
                        "-p", f"tabtitle={title}", "-p", "TerminalMargin=0", "--geometry", "95x35", "-e", "bash", v_str, t_str]):
                threading.Thread(target=lambda: (time.sleep(0.15), shutil.which("xprop") and subprocess.run(
                    ["xprop", "-name", title, "-f", "_MOTIF_WM_HINTS", "32c", "-set", "_MOTIF_WM_HINTS", "0x2, 0x0, 0x0, 0x0, 0x0"], capture_output=True)), daemon=True).start()
                return True
        for term, args in [
            ("gnome-terminal", [f"--title={title}", "--hide-menubar", "--", "bash", v_str, t_str]),
            ("xfce4-terminal", [f"--title={title}", "--hide-menubar", "--hide-borders", "-e", f"bash '{v_str}' '{t_str}'"]),
            ("alacritty", ["--title", title, "-e", "bash", v_str, t_str]),
            ("foot", ["-T", title, "bash", v_str, t_str]),
            ("xterm", ["-title", title, "-bd", "0", "-geometry", "95x35", "-e", "bash", v_str, t_str]),
            ("xdg-open", [t_str])
        ]:
            if shutil.which(term) and _run_bg([term] + args): return True
    elif sys.platform == "darwin":
        if v_sh.is_file():
            cmd = f'tell application "Terminal" to do script "bash \\"{v_str}\\" \\"{t_str}\\""'
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

        # Fallback audio discovery paths when user has not configured specific mix archives
        for fallback in (self.base_dir, Path.cwd(), Path.home() / "Music"):
            add(fallback)

        return dirs

    def _load_and_scan(self):
        seen, collected = set(), []
        for ad in self._get_archive_dirs():
            if not ad.is_dir(): continue
            for root, _, files in os.walk(ad):
                norm = root.replace("\\", "/")
                if "/." in norm or "__pycache__" in norm: continue
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
        if speed_ratio == 1.0 and self.in_pos == 0.0 and len(self.buffer) == 0:
            raw = read_func(out_frames)
            return np.zeros((0, 2), dtype=np.float32) if len(raw) == 0 else self._to_stereo(raw)

        t_out = self.in_pos + np.arange(out_frames, dtype=np.float64) * speed_ratio
        self.in_pos = t_out[-1] + speed_ratio
        needed = int(np.ceil(t_out[-1])) + 4

        while len(self.buffer) < needed:
            more = read_func(max(1024, needed - len(self.buffer)))
            if len(more) == 0: break
            stereo_more = self._to_stereo(more)
            self.buffer = np.vstack((self.buffer, stereo_more)) if len(self.buffer) else stereo_more

        if len(self.buffer) == 0: return np.zeros((0, 2), dtype=np.float32)
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

class AudioEngine:
    def __init__(self, playlist: List[Dict[str, Any]]):
        _ensure_audio_backends()
        self.playlist = playlist
        self.current_index = 0
        self.current_track = playlist[0] if playlist else None
        self.state, self.volume, self.muted, self.shuffle, self.repeat_mode = "stopped", 0.85, False, False, "all"
        self.position_sec, self.duration_sec, self.sample_rate, self.channels = 0.0, 0.0, 44100, 2

        self.pitch_percent, self.pitch_factor = 0, 1.0
        self.resampler = AudioResampler()
        self.sf_file, self.stream = None, None
        self.output_rate, self.output_device_name, self.stream_error = 44100, "", None
        self._sf_lock, self._sf_refs, self._sf_retired = threading.Lock(), 0, []
        self._next_stream_retry = 0.0

        self.num_bands = 16
        self.band_edges = np.logspace(np.log10(30), np.log10(18000), self.num_bands + 1)
        self.levels = np.zeros(self.num_bands, dtype=np.float32)
        self.levels_left = np.zeros(self.num_bands, dtype=np.float32)
        self.levels_right = np.zeros(self.num_bands, dtype=np.float32)
        self.smoothed_levels = np.zeros(self.num_bands, dtype=np.float32)
        self.peaks = np.zeros(self.num_bands, dtype=np.float32)
        self.peak_decay_timers = np.zeros(self.num_bands, dtype=np.float32)
        self.recent_mono_buffer = np.zeros(512, dtype=np.float32)
        self.rms_level, self.peak_db = 0.0, -60.0
        self.track_ended, self.pending_seek_sec = False, None
        self._ensure_stream()

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
                    blocksize=2048,
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

    def load_track(self, index: int, start_playing: bool = True) -> bool:
        if not self.playlist or not (0 <= index < len(self.playlist)): return False
        self.current_index = index
        self.current_track = self.playlist[index]
        try:
            new_sf = sf.SoundFile(self.current_track["path"])
            self.sample_rate = new_sf.samplerate
            self.channels = new_sf.channels
            self.duration_sec = float(new_sf.frames) / float(self.sample_rate)
            self.position_sec = 0.0
            self.resampler.reset()

            freqs = np.fft.rfftfreq(1024, 1.0 / self.sample_rate)
            self.band_indices = []
            for i in range(self.num_bands):
                idx = np.where((freqs >= self.band_edges[i]) & (freqs < self.band_edges[i + 1]))[0]
                if len(idx) == 0:
                    idx = np.array([min(len(freqs) - 1, max(0, int(self.band_edges[i] / (self.sample_rate / 2) * len(freqs))))])
                self.band_indices.append(idx)

            with self._sf_lock:
                old_sf, self.sf_file = self.sf_file, new_sf
            self._retire_sf(old_sf)
            self._ensure_stream()
            self.state = "playing" if start_playing else "paused"
            self._sync_state_file()
            return True
        except Exception:
            self.state = "stopped"
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
        sf_ref = self._acquire_sf()
        try:
            if sf_ref is None or self.state != "playing":
                outdata.fill(0)
                return

            if self.pending_seek_sec is not None:
                seek_val, self.pending_seek_sec = self.pending_seek_sec, None
                try:
                    sf_ref.seek(max(0, min(int(seek_val * self.sample_rate), max(0, sf_ref.frames - 1))))
                    self.position_sec = seek_val
                    self.resampler.reset()
                except Exception: pass

            out_rate = float(self.output_rate or 48000)
            data = self.resampler.process(lambda n: sf_ref.read(n, dtype='float32'), frames, (float(self.sample_rate) / out_rate) * self.pitch_factor)
            read_frames = len(data)

            try:
                told = int(sf_ref.tell())
                at_end = told >= int(sf_ref.frames)
                self.position_sec = min(self.duration_sec, float(told) / float(self.sample_rate))
            except Exception:
                at_end = False
                self.position_sec += float(max(read_frames, 0) * self.pitch_factor) / out_rate

            if read_frames <= 0:
                outdata.fill(0)
                if at_end: self.track_ended = True
                return

            eff_vol = 0.0 if self.muted else self.volume
            stereo_data = data if data.ndim > 1 and data.shape[1] >= 2 else (np.column_stack((data, data)) if data.ndim == 1 else np.column_stack((data[:, 0], data[:, 0])))
            stereo_data = stereo_data[:, :2]
            mono_data = np.mean(stereo_data, axis=1)

            if eff_vol != 1.0:
                stereo_data = np.ascontiguousarray(stereo_data * np.float32(eff_vol))

            ncopy = min(read_frames, frames, len(stereo_data))
            if at_end and np.all(stereo_data[:ncopy] == 0):
                outdata.fill(0)
                self.track_ended = True
                return

            outdata[:ncopy] = stereo_data[:ncopy]
            if ncopy < frames:
                outdata[ncopy:].fill(0)
                if at_end: self.track_ended = True

            self._compute_fft_spectrum(stereo_data[:ncopy], mono_data[:ncopy])
        finally:
            if sf_ref is not None: self._release_sf()

    def _compute_fft_spectrum(self, stereo_data: np.ndarray, mono_data: np.ndarray):
        try:
            fft_size = 1024
            m = np.pad(mono_data, (0, max(0, fft_size - len(mono_data))))[:fft_size]
            l = np.pad(stereo_data[:, 0], (0, max(0, fft_size - len(stereo_data))))[:fft_size]
            r = np.pad(stereo_data[:, 1], (0, max(0, fft_size - len(stereo_data))))[:fft_size]
            w = np.hanning(fft_size)

            scale = fft_size / 2
            m_fft, l_fft, r_fft = np.abs(np.fft.rfft(m * w)) / scale, np.abs(np.fft.rfft(l * w)) / scale, np.abs(np.fft.rfft(r * w)) / scale

            for b in range(self.num_bands):
                idx = self.band_indices[b]
                boost = (1.0 + (1.2 / (1.0 + b * 0.4))) * 4.5
                self.levels[b] = min(1.0, max(0.0, float(np.mean(m_fft[idx]) * boost)))
                self.levels_left[b] = min(1.0, max(0.0, float(np.mean(l_fft[idx]) * boost)))
                self.levels_right[b] = min(1.0, max(0.0, float(np.mean(r_fft[idx]) * boost)))

                if self.levels[b] > self.smoothed_levels[b]:
                    self.smoothed_levels[b] = self.levels[b]
                else:
                    self.smoothed_levels[b] = self.smoothed_levels[b] * 0.82 + self.levels[b] * 0.18

                if self.smoothed_levels[b] >= self.peaks[b]:
                    self.peaks[b], self.peak_decay_timers[b] = self.smoothed_levels[b], 0.0
                else:
                    self.peak_decay_timers[b] += 0.03
                    if self.peak_decay_timers[b] > 0.2:
                        self.peaks[b] = max(0.0, self.peaks[b] - 0.05)

            self.recent_mono_buffer = m[:512]
            self.rms_level = float(np.sqrt(np.mean(m ** 2)))
            self.peak_db = 20.0 * np.log10(max(1e-5, np.max(np.abs(m))))
        except Exception: pass

    def check_track_end(self):
        if self.track_ended:
            self.track_ended = False
            if self.repeat_mode == "one": self.seek(0)
            elif self.repeat_mode == "all" or self.current_index < len(self.playlist) - 1: self.next_track()
            else: self.stop_playback()

    def play(self):
        if not self.sf_file: self.load_track(self.current_index, True)
        else:
            self.state = "playing"
            self._ensure_stream()

    def pause(self): self.state = "paused"
    def toggle_play_pause(self): self.pause() if self.state == "playing" else self.play()
    def stop_playback(self):
        self.state, self.position_sec = "stopped", 0.0
        self.smoothed_levels.fill(0)
        self.peaks.fill(0)

    def _step_track(self, direction: int):
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
            self.pending_seek_sec = self.position_sec = max(0.0, min(self.duration_sec - 1.0, target_sec))

    def seek_relative(self, delta_sec: float): self.seek(self.position_sec + delta_sec)
    def set_volume(self, vol_pct: int): self.volume, self.muted = max(0.0, min(1.0, float(vol_pct) / 100.0)), False
    def change_volume(self, delta_pct: int): self.set_volume(int(self.volume * 100) + delta_pct)
    def toggle_mute(self): self.muted = not self.muted
    def toggle_shuffle(self): self.shuffle = not self.shuffle
    def cycle_repeat(self):
        modes = ["all", "one", "off"]
        self.repeat_mode = modes[(modes.index(self.repeat_mode) + 1) % len(modes)]

    def get_mini_visualizer(self) -> str:
        if self.state != "playing": return "·······"
        step = max(1, self.num_bands // 8)
        return "".join(UNICODE_BLOCKS[max(0, min(8, int(self.smoothed_levels[i] * 8)))] for i in range(0, self.num_bands, step)[:8])

    def get_status_dict(self) -> Dict[str, Any]:
        pct = round((self.position_sec / self.duration_sec * 100.0), 1) if self.duration_sec > 0 else 0.0
        return {
            "running": True, "state": str(self.state), "index": int(self.current_index),
            "total_tracks": len(self.playlist), "title": str(self.current_track["name"] if self.current_track else "No Track Loaded"),
            "path": str(self.current_track["path"] if self.current_track else ""), "position_sec": round(float(self.position_sec), 2),
            "duration_sec": round(float(self.duration_sec), 2), "position_fmt": format_seconds(self.position_sec),
            "duration_fmt": format_seconds(self.duration_sec), "progress_pct": float(pct), "volume": int(self.volume * 100),
            "pitch_percent": int(self.pitch_percent), "pitch_factor": round(float(self.pitch_factor), 3), "muted": bool(self.muted),
            "shuffle": bool(self.shuffle), "repeat": str(self.repeat_mode), "sample_rate": int(self.sample_rate),
            "output_rate": int(self.output_rate or 0), "output_device": str(self.output_device_name or ""),
            "audio_error": str(self.stream_error or ""), "channels": int(self.channels), "mini_eq": self.get_mini_visualizer(),
            "levels": [round(float(x), 3) for x in self.smoothed_levels], "peaks": [round(float(x), 3) for x in self.peaks],
            "levels_left": [round(float(x), 3) for x in self.levels_left], "levels_right": [round(float(x), 3) for x in self.levels_right],
            "peak_db": round(float(self.peak_db), 1), "pid": os.getpid()
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
                    for i, t in enumerate(self.engine.playlist):
                        if t["path"] == f or t["name"] == os.path.basename(f):
                            self.engine.load_track(i, True); break
                    else:
                        self.engine.playlist.insert(0, {"name": os.path.basename(f), "path": f, "size_mb": 0, "mtime": time.time(), "ext": os.path.splitext(f)[1][1:].upper()})
                        self.engine.load_track(0, True)
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
            elif cmd == "mute": self.engine.toggle_mute()
            elif cmd == "shuffle": self.engine.toggle_shuffle()
            elif cmd == "repeat": self.engine.cycle_repeat()
            elif cmd == "select_index": threading.Thread(target=self.engine.load_track, args=(int(req.get("index", 0)), True), daemon=True).start()
            elif cmd == "get_playlist": res["playlist"] = [{"index": i, "name": t["name"], "path": t["path"], "ext": t["ext"]} for i, t in enumerate(self.engine.playlist[:100])]
            elif cmd in ("open_file_manager", "reveal"):
                tf = req.get("file") or (self.engine.current_track.get("path") if self.engine.current_track else str(get_base_dir()))
                res["success"] = open_in_file_manager(tf)

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
            time.sleep(0.04)

def send_ipc_command(cmd: str, **kwargs) -> Optional[Dict[str, Any]]:
    has_unix = hasattr(socket, "AF_UNIX")
    if (has_unix and not SOCKET_PATH.exists()) or (not has_unix and not PORT_FILE.exists()): return None
    for _ in range(3):
        try:
            s = socket.socket(socket.AF_UNIX if has_unix else socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(str(SOCKET_PATH) if has_unix else ("127.0.0.1", int(PORT_FILE.read_text().strip())))
            payload = {"cmd": cmd, **kwargs}
            s.sendall(json.dumps(payload).encode('utf-8'))
            raw = s.recv(65536).decode('utf-8')
            s.close()
            if raw: return json.loads(raw)
        except Exception: time.sleep(0.05)
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
                return True
        except (OSError, ValueError): pass
        for p in (PID_FILE, SOCKET_PATH, PORT_FILE):
            try: p.unlink()
            except OSError: pass

    if hasattr(socket, "AF_UNIX") and SOCKET_PATH.exists():
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.1)
            s.connect(str(SOCKET_PATH))
            s.close()
            return True
        except Exception:
            try: SOCKET_PATH.unlink()
            except OSError: pass
    elif not hasattr(socket, "AF_UNIX") and PORT_FILE.exists():
        try:
            port = int(PORT_FILE.read_text().strip())
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except Exception:
            try: PORT_FILE.unlink()
            except OSError: pass
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
    STYLES = ["stereo_eq", "master_spectrum", "analog_vu", "oscilloscope"]
    THEMES = ["dreamworlds_ultra", "dreamworlds_neon", "retro_studio", "cyber_neon", "phosphor", "ice_cold"]

    def __init__(self):
        _ensure_numpy()
        self.style_idx = self.theme_idx = 0

    @property
    def style(self) -> str: return self.STYLES[self.style_idx]
    @property
    def theme(self) -> str: return self.THEMES[self.theme_idx]
    def cycle_style(self): self.style_idx = (self.style_idx + 1) % len(self.STYLES)
    def cycle_theme(self): self.theme_idx = (self.theme_idx + 1) % len(self.THEMES)

    def _get_bar_color(self, fraction: float) -> str:
        t = self.theme
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
                    ch = "█" if frac >= 1.0 else (UNICODE_BLOCKS[max(1, min(8, int(frac * 8)))] if frac > 0.0 else ("▔" if int(pk * height) == r else " "))
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
                ch = "█" if frac >= 1.0 else (UNICODE_BLOCKS[max(1, min(8, int(frac * 8)))] if frac > 0.0 else ("▔" if int(ip[c] * height) == r else " "))
                row_chars.append(f"{ch*2} ")
            lines.append(f"  │ {col}{''.join(row_chars)}{NC} │")

        lines.extend([f"  {DIM}{CYAN}│  32  63  125  250  500   1k   2k   4k   8k  12k  16k  18k    PEAK HOLD ✦ │{NC}",
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

    def render_oscilloscope(self, levels: np.ndarray, height: int = 5) -> List[str]:
        lines = [f"  {BOLD}{MAGENTA}╭── DYNAMIC OSCILLOSCOPE AUDIO WAVEFORM ───────────────────────────────────╮{NC}"]
        pts = [math.sin(i * 0.4) * (levels[i % len(levels)] if len(levels) else 0.0) for i in range(70)]
        hh = max(1, height // 2)
        for r in range(hh, -hh - 1, -1):
            row = ["  │  "] + [(f"{COLOR_ELECTRIC_CYAN}∿{NC}" if int(p * (hh + 0.5)) == r else (f"{DIM}─{NC}" if r == 0 else " ")) for p in pts] + ["  │"]
            lines.append("".join(row))
        lines.append(f"  {BOLD}{MAGENTA}╰──────────────────────────────────────────────────────────────────────────╯{NC}")
        return lines

    def render_vertical_pitch_fader(self, pitch_pct: int, total_lines: int = 10) -> List[str]:
        p = max(-20, min(20, int(pitch_pct)))
        frows = max(3, total_lines - 2)
        krow, crow = int(round((1.0 - (p + 20) / 40.0) * (frows - 1))), frows // 2
        lines = [f"{COLOR_HOT_PURPLE}╭── DJ PITCH ────────────╮{NC}"]

        for r in range(frows):
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
            elif r == frows - 1:
                lines.append(f"{COLOR_HOT_PURPLE}│{NC}    {COLOR_INDIGO_BLUE}▼{NC}     {DIM}-20% MIN{NC}      {COLOR_HOT_PURPLE}│{NC}")
            else:
                lines.append(f"{COLOR_HOT_PURPLE}│{NC}    {COLOR_INDIGO_BLUE}│{NC}{' ' * 19}{COLOR_HOT_PURPLE}│{NC}")
        lines.append(f"{COLOR_HOT_PURPLE}╰────────────────────────╯{NC}")
        return lines

    def render_horizontal_pitch_bar(self, pitch_pct: int, width: int = 36, max_cols: Optional[int] = None) -> str:
        p = max(-20, min(20, int(pitch_pct)))
        w = max(12, width)
        kpos, cpos = int(round(((p + 20) / 40.0) * (w - 1))), w // 2

        def _track(tw, kp, cp):
            chars = []
            for i in range(tw):
                if i == kp: chars.append(f"{BOLD}{COLOR_TRAFFIC_GREEN if p == 0 else (COLOR_TRAFFIC_AMBER if p > 0 else COLOR_INDIGO_BLUE)}●{NC}")
                elif i == cp: chars.append(f"{COLOR_TRAFFIC_GREEN}┼{NC}")
                elif i < cp: chars.append(f"{DIM}━{NC}" if (i < kp and p < 0) else (f"{COLOR_INDIGO_BLUE}━{NC}" if kp <= i < cp else f"{DIM}─{NC}"))
                else: chars.append(f"{COLOR_TRAFFIC_AMBER}━{NC}" if cp < i <= kp else f"{DIM}─{NC}")
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
                w = max(8, avail)
                kpos, cpos = int(round(((p + 20) / 40.0) * (w - 1))) if w > 1 else 0, w // 2

        return f"{pfx}{_track(w, kpos, cpos)}{sfx}"

    def render(self, status: Dict[str, Any], width: int = 80, height: int = 7) -> List[str]:
        levels = np.array(status.get("levels", [0.0]*16))
        peaks = np.array(status.get("peaks", [0.0]*16))
        ll, lr = np.array(status.get("levels_left", levels)), np.array(status.get("levels_right", levels))
        s = self.style
        if s == "master_spectrum": lines = self.render_master_spectrum(levels, peaks, height=height)
        elif s == "analog_vu": lines = self.render_analog_vu(status.get("peak_db", -60.0), ll, lr)
        elif s == "oscilloscope": lines = self.render_oscilloscope(levels, height=min(5, height))
        else: lines = self.render_stereo_eq(ll, lr, peaks, width=width, height=height)

        if width >= 122:
            faders = self.render_vertical_pitch_fader(int(status.get("pitch_percent", 0)), total_lines=len(lines))
            return [f"{el}{' ' * max(0, 91 - _display_width(el))}  {fl}" for el, fl in zip(lines, faders)]
        return lines

class TerminalPlayerUI:
    def __init__(self, engine: Optional[AudioEngine], scanner: MixArchiveScanner, is_remote: bool = False):
        self.engine, self.scanner, self.is_remote = engine, scanner, is_remote
        self.visualizer, self.running = EqualizerVisualizer(), True
        self.search_mode, self.search_query, self.export_mode, self.export_path = False, "", False, ""
        self.selected_row, self.scroll_offset, self.notification_msg, self.notification_time = 0, 0, "", 0.0
        self.cached_status = {"title": "Loading...", "path": "", "state": "stopped", "position_fmt": "00:00",
                              "duration_fmt": "00:00", "progress_pct": 0.0, "volume": 85, "muted": False,
                              "shuffle": False, "repeat": "all", "levels": [0.0]*16, "peaks": [0.0]*16}

    def _get_status(self) -> Dict[str, Any]:
        if self.is_remote:
            if STATE_FILE.exists():
                try: self.cached_status = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                except Exception: pass
            else:
                res = send_ipc_command("status")
                if res and "data" in res: self.cached_status = res["data"]
            return self.cached_status
        return self.engine.get_status_dict() if self.engine else self.cached_status

    def _sync_initial_selection(self, status: Dict[str, Any]):
        cp = status.get("path")
        if cp and cp != getattr(self, "_last_path", None):
            self._last_path = cp
            if not self.search_query:
                for i, m in enumerate(self.scanner.get_mixes()):
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
                "repeat": e.cycle_repeat, "stop": e.stop_playback
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
            elif cmd == "open_file_manager":
                tf = kwargs.get("file") or (e.current_track.get("path") if e.current_track else str(get_base_dir()))
                open_in_file_manager(tf)

    def _get_target_path(self) -> Tuple[Optional[str], Optional[str]]:
        mixes = self.scanner.get_mixes(self.search_query)
        if mixes and 0 <= self.selected_row < len(mixes):
            return mixes[self.selected_row].get("path"), mixes[self.selected_row].get("name")
        st = self._get_status()
        if st.get("path"): return st.get("path"), st.get("title")
        latest = self.scanner.get_latest_mix()
        return (latest["path"], latest["name"]) if latest else (None, None)

    def _open_selected_in_file_manager(self):
        tp, _ = self._get_target_path()
        target = tp or str(get_base_dir())
        ok = open_in_file_manager(target)
        name = os.path.basename(target)
        self.notification_msg = f"{'Opened in' if ok else 'Failed to open'} File Manager: {name}"
        self.notification_time = time.time() + 3.0

    def _view_selected_tracklist(self):
        tp, tn = self._get_target_path()
        if not tp:
            self.notification_msg = "No mix selected to view tracklist."
            self.notification_time = time.time() + 3.0
            return
        tl = find_tracklist_for_mix(tp)
        if tl and os.path.isfile(tl):
            ok = open_tracklist_window(tl)
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
        sys.stdout.write("\033[?1049h\033[?25l\033[?7l\033[2J\033[H")
        sys.stdout.flush()
        threading.Thread(target=self._input_loop, daemon=True).start()

        try:
            while self.running:
                if not self.is_remote and self.engine: self.engine.check_track_end()
                self._draw_frame()
                time.sleep(0.04)
        except (KeyboardInterrupt, SystemExit): pass
        finally:
            self.running = False
            if fd is not None and old_settings and termios:
                try: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except Exception: pass
            sys.stdout.write("\033[?7h\033[?25h\033[?1049l")
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
            filtered = self.scanner.get_mixes(self.search_query)
            if filtered: self.selected_row = len(filtered) - 1
        elif data in (b"\x1b[D", b"\x1bOD"):
            self._send_cmd("seek", seconds=-10.0)
        elif data in (b"\x1b[C", b"\x1bOC"):
            self._send_cmd("seek", seconds=10.0)
        elif data in (b"\r", b"\n"):
            mixes = self.scanner.get_mixes(self.search_query)
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
        elif data in (b"]", b"}", b"v"): self._send_cmd("vol_up", step=5)
        elif data in (b"[", b"{", b"V"): self._send_cmd("vol_down", step=5)
        elif data in (b"m", b"M"): self._send_cmd("mute")
        elif data in (b"s", b"S"): self._send_cmd("shuffle")
        elif data in (b"r", b"R"): self._send_cmd("repeat")
        elif data == b"e": self.visualizer.cycle_style()
        elif data in (b"c", b"C"): self.visualizer.cycle_theme()
        elif data in (b"o", b"O"): self._open_audio_file()
        elif data in (b"t", b"T"): self._view_selected_tracklist()
        elif data in (b"E", b"w", b"W"): self._export_playlist()
        elif data == b"/": self.search_mode, self.search_query = True, ""
        elif data in (b"f", b"F"): self._open_selected_in_file_manager()
        elif data in (b"x", b"X"): self._send_cmd("stop"); self.running = False
        elif data in (b"q", b"Q", b"b", b"B", b"\x1b", b"\x03"): self.running = False

    def _navigate_list(self, delta: int):
        m = self.scanner.get_mixes(self.search_query)
        if m: self.selected_row = max(0, min(len(m) - 1, self.selected_row + delta))

    def _draw_frame(self):
        w, h = _win_visible_size((80, 24))
        w, h = max(40, w), max(8, h)
        st = self._get_status()
        self._sync_initial_selection(st)
        lines = []

        iw = 115 if w >= 122 else max(20, w - 6)

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

        lines.append(f"  {badge}  {BOLD}{COLOR_NEON_PINK}♫  {tname}{NC}")
        lines.append(f"  {DIM}{CYAN}Format: {ext}{' Lossless' if w>=96 else ''}  │  Sample Rate: {sr/1000:.1f} kHz  │  Channels: {ch_str}  │  Archive: {'Configured' if w>=96 else 'OK'}{NC}")

        pct = float(st.get("progress_pct", 0.0))
        bw = max(20, min(54, iw - 42))
        fw = int((pct / 100.0) * bw)
        bstr = "━" * fw + "●" + "─" * max(0, bw - fw - 1)
        lines.extend([f"  {COLOR_ELECTRIC_CYAN}{st.get('position_fmt', '00:00')}{NC}  {COLOR_HOT_PURPLE}{bstr}{NC}  {COLOR_ELECTRIC_CYAN}{st.get('duration_fmt', '00:00')}{NC}  ({pct:.1f}%)",
                      self.visualizer.render_horizontal_pitch_bar(int(st.get("pitch_percent", 0)), width=bw, max_cols=max(20, w - 1)), ""])

        vis_h = 7 if h >= 34 else (5 if h >= 28 else 3)
        lines.extend(self.visualizer.render(st, width=w, height=vis_h) + [""])

        mixes = self.scanner.get_mixes(self.search_query)
        if self.export_mode: lines.append(f"  {BOLD}{COLOR_TRAFFIC_AMBER}Export Playlist (.m3u) Path: [{self.export_path}█]  (Enter: Save, Esc: Cancel){NC}")
        elif self.search_mode: lines.append(f"  {BOLD}{CYAN}Filter / Search: [{self.search_query}█]{NC}")
        elif self.search_query: lines.append(f"  {BOLD}Search Filter: '{self.search_query}' (Press '/' to search)")
        elif time.time() < self.notification_time and self.notification_msg: lines.append(f"  {BOLD}{COLOR_TRAFFIC_GREEN}📂 {self.notification_msg}{NC}")

        lines.append(_boxed_rule("┌", f"── MP MIX ARCHIVE PLAYLIST ({len(mixes)} Mixes Available) ", "┐", iw, f"{BOLD}{MAGENTA}"))
        vrows = max(0, h - len(lines) - 3)
        if vrows <= 0: self.scroll_offset = max(0, self.selected_row)
        elif self.selected_row < self.scroll_offset: self.scroll_offset = self.selected_row
        elif self.selected_row >= self.scroll_offset + vrows: self.scroll_offset = self.selected_row - vrows + 1

        b_col = f"{BOLD}{MAGENTA}"
        avail_name = max(4, iw - 23)
        if not mixes:
            empty_msg1 = "No audio mixes found in archive. (Mix archive folders not yet configured)"
            empty_msg2 = "Press [O] to open an audio file, [F] for File Manager, or Option 14 to configure archive."
            for em in (empty_msg1, empty_msg2):
                pad = " " * max(0, iw - _display_width(em) - 2)
                lines.append(f"  {b_col}│{NC} {COLOR_TRAFFIC_AMBER}{em}{NC}{pad}{b_col}│{NC}")
            for _ in range(max(0, vrows - 2)):
                lines.append(f"  {b_col}│{NC}{' ' * iw}{b_col}│{NC}")
        else:
            for i in range(self.scroll_offset, min(len(mixes), self.scroll_offset + vrows)):
                m = mixes[i]
                act, sel = (m["path"] == st.get("path")), (i == self.selected_row)
                raw_name = str(m.get("name", ""))
                if _display_width(raw_name) > avail_name:
                    mn = _clip_display(raw_name, max(1, avail_name - 3)) + "..." if avail_name > 3 else _clip_display(raw_name, avail_name)
                else:
                    mn = raw_name
                name_pad = " " * max(0, avail_name - _display_width(mn))
                pfx = "▶ " if act else "  "
                ext_str = f"{m.get('ext', ''):<4}"[:4]
                sz_str = f"{m.get('size_mb', 0):.0f}MB"
                inner_plain = f" {pfx}[{i+1:4d}] {mn}{name_pad} {ext_str} {sz_str:>6s} "
                curr_w = _display_width(inner_plain)
                if curr_w < iw:
                    inner_plain += " " * (iw - curr_w)
                elif curr_w > iw:
                    inner_plain = _clip_display(inner_plain, iw)

                if sel and act:
                    lstr = f"  {b_col}│{NC}\033[7m{BOLD}{GREEN}{inner_plain}\033[0m{b_col}│{NC}"
                elif sel:
                    lstr = f"  {b_col}│{NC}\033[7m{inner_plain}\033[0m{b_col}│{NC}"
                elif act:
                    lstr = f"  {b_col}│{NC}{BOLD}{GREEN}{inner_plain}{NC}{b_col}│{NC}"
                else:
                    lstr = f"  {b_col}│{NC}{inner_plain}{b_col}│{NC}"
                lines.append(lstr)

        lines.append(_boxed_rule("└", "── ↑/↓: Scroll  •  Enter: Play  •  O: Open  •  T: Tracklist  •  E: Export  •  F: Files  •  /: Search ", "┘", iw, f"{BOLD}{MAGENTA}"))

        shuf = f"{COLOR_TRAFFIC_GREEN}ON{NC}" if st.get("shuffle") else f"{DIM}OFF{NC}"
        rep = f"{COLOR_TRAFFIC_GREEN}{st.get('repeat', 'all').upper()}{NC}"
        vol = f"{st.get('volume', 85)}%" if not st.get("muted") else f"{COLOR_TRAFFIC_RED}MUTED{NC}"
        pval = int(st.get("pitch_percent", 0))
        pcol = COLOR_TRAFFIC_GREEN if pval == 0 else (COLOR_TRAFFIC_AMBER if pval > 0 else COLOR_INDIGO_BLUE)
        pbadge = f"{pcol}{pval:+d}% ({1.0 + pval/100:.2f}x){NC}"

        lines.append(_fit_text_line([
            f"  🔊 Vol: {BOLD}{COLOR_ELECTRIC_CYAN}{vol}{NC}  │  🎚 DJ Pitch: {BOLD}{pbadge}  │  🔀 Shuffle: {shuf}  │  🔁 Repeat: {rep}  │  🎨 Theme: {BOLD}{COLOR_HOT_PURPLE}Dreamworlds Ultra{NC}",
            f"  Vol: {BOLD}{COLOR_ELECTRIC_CYAN}{vol}{NC}  │  Pitch: {BOLD}{pbadge}  │  Shuffle: {shuf}  │  Repeat: {rep}",
            f"  Vol {vol}  Pitch {pbadge}  Shuf {shuf}  Rep {rep}"
        ], max(20, w - 1)))
        lines.append(_fit_text_line([
            f"  {DIM}[Space] Play/Pause  [+/-] Pitch ±1% (±20% max)  [0] Pitch Reset  [v/V] Vol  [n/p] Next/Prev  [O] Open  [T] Tracklist  [E] Export  [F] Files  [e] EQ  [b/q] Exit{NC}",
            f"  {DIM}Space Play  +/- Pitch  0 Reset  v/V Vol  n/p Skip  O Open  T List  E Export  F Files  e EQ  b/q Exit{NC}",
            f"  {DIM}Space Play  +/- Pitch  v/V Vol  n/p Skip  O Open  b/q Exit{NC}"
        ], max(20, w - 1)))

        _present_frame(lines, w, h)

def _spawn_player_daemon(file_path: Optional[str] = None):
    cmd = [sys.executable, str(Path(__file__).resolve()), "--daemon"]
    if file_path: cmd.append(str(file_path))
    proc = subprocess.Popen(cmd,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    try: PID_FILE.write_text(str(proc.pid))
    except OSError: pass

def _install_windows_console_close():
    if sys.platform != "win32": return
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    ht = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
    cb = ht(lambda c: (os._exit(0) if c in (2, 5, 6) else 0))
    k.SetConsoleCtrlHandler(cb, 1)

def main():
    parser = argparse.ArgumentParser(description="MP Audio Player - High Resolution Playback & Custom Animated Equalizer")
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
    parser.add_argument("--cmd", type=str, help="Send arbitrary IPC command")

    args, _ = parser.parse_known_args()
    base_dir = get_base_dir()

    if args.get_latest_mix:
        latest = MixArchiveScanner(base_dir).get_latest_mix()
        if latest: print(latest["path"]); sys.exit(0)
        sys.exit(1)

    if args.list_mixes:
        for m in MixArchiveScanner(base_dir).get_mixes():
            print(f"{m['path']}\t{m['size_mb']:.1f}MB\t{m['name']}")
        sys.exit(0)

    daemon_running = is_player_daemon_running()

    if args.open_file_manager or args.tracklist:
        tp = None
        if daemon_running:
            st = send_ipc_command("status")
            if st and "data" in st and st["data"].get("path"): tp = st["data"]["path"]
        if not tp or not os.path.exists(tp):
            latest = MixArchiveScanner(base_dir).get_latest_mix()
            if latest: tp = latest["path"]
        if args.open_file_manager:
            ok = open_in_file_manager(tp or str(base_dir))
            print(f"✔ Opened in file manager: {tp or base_dir}" if ok else "✖ Failed to open file manager")
            sys.exit(0 if ok else 1)
        else:
            tl = find_tracklist_for_mix(tp) if tp else None
            if tl and os.path.isfile(tl) and open_tracklist_window(tl):
                print(f"✔ Opened tracklist: {tl}"); sys.exit(0)
            print("✖ Tracklist not found" if tp else "✖ No mix available", file=sys.stderr)
            sys.exit(1)

    if args.export_playlist is not None:
        mixes = MixArchiveScanner(base_dir).get_mixes()
        dest = os.path.expanduser("~/Desktop/MP_Archive_Playlist.m3u") if (args.export_playlist in ("default", "") or not args.export_playlist) else args.export_playlist
        ok, res = export_playlist_m3u(mixes, dest)
        print(f"✔ Exported {len(mixes)} mixes to .m3u playlist: {res}" if ok else f"✖ Failed to export playlist: {res}")
        sys.exit(0 if ok else 1)

    if args.cmd:
        res = send_ipc_command(args.cmd)
        if res: print(json.dumps(res)); sys.exit(0)
        sys.exit(1)

    if args.play_latest:
        latest = MixArchiveScanner(base_dir).get_latest_mix()
        if latest:
            send_ipc_command("play", file=latest["path"]) if daemon_running else _spawn_player_daemon(latest["path"])
            sys.exit(0)
        sys.exit(1)

    if args.toggle:
        if daemon_running: sys.exit(0 if send_ipc_command("toggle") else 1)
        latest = MixArchiveScanner(base_dir).get_latest_mix()
        if latest: _spawn_player_daemon(latest["path"])
        sys.exit(0)

    if args.pause or args.stop or args.next or args.prev:
        cmd = "pause" if args.pause else ("stop" if args.stop else ("next" if args.next else "prev"))
        if daemon_running: send_ipc_command(cmd)
        sys.exit(0)

    if args.play is not None:
        ftp = args.play or (args.file or "")
        if daemon_running: send_ipc_command("play", file=ftp or None)
        else:
            if not ftp:
                l = MixArchiveScanner(base_dir).get_latest_mix()
                ftp = l["path"] if l else ""
            if ftp: _spawn_player_daemon(ftp)
        sys.exit(0)

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

    if args.interactive or (not args.daemon and sys.stdin.isatty()):
        scanner = MixArchiveScanner(base_dir)
        mixes = scanner.get_mixes()

        tf = os.path.abspath(args.file) if args.file else None
        if not daemon_running:
            latest = scanner.get_latest_mix()
            init_file = tf or (latest["path"] if latest else (mixes[0]["path"] if mixes else None))
            _spawn_player_daemon(init_file)
            for _ in range(50):
                time.sleep(0.04)
                if (SOCKET_PATH.exists() or PORT_FILE.exists()) and is_player_daemon_running():
                    break
        elif tf: send_ipc_command("play", file=tf)

        TerminalPlayerUI(None, scanner, is_remote=True).run()
        sys.exit(0)

    if args.daemon:
        try: PID_FILE.write_text(str(os.getpid()))
        except OSError: pass
        _install_windows_console_close()

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

    engine = AudioEngine(mixes)
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