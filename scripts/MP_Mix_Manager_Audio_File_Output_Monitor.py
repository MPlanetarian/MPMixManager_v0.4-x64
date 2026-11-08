#!/usr/bin/env python3
"""
MP_Mix_Manager_Audio_File_Output_Monitor.py
Version: 1.0.0
Live Real-Time Audio & Video Output Monitor for MP Mix Archive Manager

Features:
- Monitors Audio Conversion outputs (FLAC, MP3, WAV, OGG, AAC) and YouTube Video outputs (.MP4, .MKV)
- Live process monitoring for active MP Mix Archive Manager conversion & video creation scripts
- Real-time conversion velocity & throughput tracking (MB/min, session writes, active jobs)
- Multi-instance intelligence: detects multiple manager instances and transcoding pipelines
- Structured JSONL + TXT logging (MP_Mix_Manager_Conversion_Log.jsonl / .txt)
- Audio playback via MP Audio Player, Audacious, Strawberry, VLC, or system default
- Video playback via VLC, Haruna, MPV, or system default
- Dynamic directory switching between archive output folders and custom directories
- Drive capacity forecasting (estimated mix headroom remaining before disk full)
"""

import os
import sys
import time
import json
import select
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from collections import deque

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich.layout import Layout
    from rich.prompt import Prompt, IntPrompt, Confirm
    from rich import box
except ImportError:
    print("Error: 'rich' library is required. Install with: pip install rich")
    sys.exit(1)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

VERSION = "1.0.0"
APP_NAME = "MP Mix Manager Audio & Video Output Monitor"
LOG_JSONL_NAME = "MP_Mix_Manager_Conversion_Log.jsonl"
LOG_TXT_NAME = "MP_Mix_Manager_Conversion_Log.txt"

# Target scripts & executables that perform audio/video operations
TARGET_SCRIPTS = [
    "Make_SOF_FLAC_CONVERSION.sh",
    "convert_audio_format.sh",
    "generate_youtube_video.sh",
    "generate_youtube_short_promo",
    "Make_SOF_Episode_From_PNG_FLAC_Output_MP4_1080p_Video.sh",
    "Make_SOF_Episode_From_PNG_FLAC_Output_MP4_4K_Video.sh",
    "Make_SOF_Episode_From_PNG_FLAC_Output_MP4_720p_Video.sh",
    "Make_SOF_Episode_From_MP4_Audio_Output_MP4_1080p_Video.sh",
    "Split_FLAC_File.sh",
    "Split_Video_File.sh",
    "Cut_Video.sh",
    "master_audio_loudness",
    "verify_audio_mastering",
    "MOVE_NOT_CONVERTED_WAVS.sh",
]

ENCODER_BINARIES = {"ffmpeg", "flac", "lame", "sox", "spek"}

AUDIO_EXTS = {".flac", ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".aiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov"}
ALL_EXTS = AUDIO_EXTS | VIDEO_EXTS

# Palette: Cyan / Purple / Neon Green
STYLE_TITLE = "bold magenta"
STYLE_HEADER = "bold bright_cyan"
STYLE_AUDIO = "bold spring_green1"
STYLE_VIDEO = "bold medium_purple"
STYLE_METRIC = "bold orchid"
STYLE_WARN = "bold yellow"
STYLE_ALERT = "bold red on black"

console = Console()


def find_project_root() -> Path:
    """Find the root directory of MP_Mix_Manager_v0.3."""
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.home() / "MP_Mix_Manager_v0.3",
        Path("/var/home/mplanetarian/MP_Mix_Manager_v0.3"),
    ]
    for c in candidates:
        if (c / "Mix_Archive_Manager.sh").is_file() or (c / "config.env").is_file():
            return c
    return Path.cwd()


def load_config_env() -> dict:
    """Load configuration from config.env."""
    root = find_project_root()
    cfg_file = root / "config.env"
    config = {}
    if cfg_file.is_file():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    config[k] = v
        except Exception:
            pass
    return config


class AudioVideoMonitor:
    def __init__(self, target_dirs: list[Path] | None = None):
        self.project_root = find_project_root()
        self.config = load_config_env()

        self.log_jsonl = self.project_root / LOG_JSONL_NAME
        self.log_txt = self.project_root / LOG_TXT_NAME

        if target_dirs:
            self.watch_dirs = [Path(d).expanduser().resolve() for d in target_dirs]
        else:
            self.watch_dirs = self.detect_default_watch_dirs()

        self.known_files = set()
        self.audio_files = []
        self.video_files = []
        self.total_audio_size = 0
        self.total_video_size = 0

        self.latest_audio = None
        self.latest_video = None
        self.start_time = datetime.now()
        self.last_scan = None
        self.new_count = 0
        self.session_bytes_written = 0

        # Velocity tracking: samples of (timestamp, cumulative_bytes)
        self.velocity_samples = deque(maxlen=60)
        self.velocity_samples.append((time.time(), 0))

        self.disk_alert_threshold = 20.0

    def detect_default_watch_dirs(self) -> list[Path]:
        """Auto-detect all audio and video conversion folders."""
        dirs = []
        mix_archive = self.config.get("MIX_ARCHIVE_DIR")
        archive_root = Path(mix_archive).expanduser() if mix_archive else self.project_root

        # Standard output folder names
        folder_names = [
            self.config.get("OUTPUT_DIR", "FLAC_CONVERTED_OUTPUTS"),
            "MP3_CONVERTED_OUTPUTS",
            "WAV_CONVERTED_OUTPUTS",
            "MP4_CONVERTED_OUTPUTS",
            "YOUTUBE_VIDEOS",
            "YOUTUBE_SHORTS",
            "SPEK_OUTPUTS",
        ]

        for fname in folder_names:
            p_archive = archive_root / fname
            if p_archive.exists() and p_archive not in dirs:
                dirs.append(p_archive.resolve())
            p_root = self.project_root / fname
            if p_root.exists() and p_root not in dirs:
                dirs.append(p_root.resolve())

        # If none exist yet, monitor project root or archive root
        if not dirs:
            dirs.append(archive_root if archive_root.exists() else self.project_root)

        return dirs

    def human_size(self, size_bytes: float) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def get_file_info(self, path: Path) -> dict | None:
        try:
            stat = path.stat()
            ext = path.suffix.lower()
            kind = "audio" if ext in AUDIO_EXTS else "video"
            return {
                "path": path,
                "name": path.name,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime),
                "ext": ext,
                "kind": kind,
                "parent_name": path.parent.name,
            }
        except Exception:
            return None

    def get_disk_info(self) -> dict:
        """Return usage for the primary archive filesystem."""
        try:
            target = self.watch_dirs[0] if self.watch_dirs else self.project_root
            usage = shutil.disk_usage(target)
            free_percent = (usage.free / usage.total * 100) if usage.total else 0
            mount = str(target)
            if PSUTIL_AVAILABLE:
                try:
                    for part in psutil.disk_partitions(all=False):
                        if target.resolve().is_relative_to(Path(part.mountpoint)):
                            mount = part.mountpoint
                            break
                except Exception:
                    pass

            # Estimate headroom: average 2-hour 24-bit FLAC mix is ~800MB
            est_mixes_left = int(usage.free / (800 * 1024 * 1024))

            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "free_percent": free_percent,
                "mount": mount,
                "low": free_percent <= self.disk_alert_threshold,
                "est_mixes": max(0, est_mixes_left),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_running_conversion_processes(self) -> list[dict]:
        """Detect running conversion scripts, youtube generators, and audio encoders."""
        if not PSUTIL_AVAILABLE:
            return []
        found = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "status", "create_time", "cpu_percent", "memory_info", "username"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                cmd_str = " ".join(cmdline)
                name = proc.info.get("name") or ""
                matched_category = None

                # 1. Check conversion scripts
                for target in TARGET_SCRIPTS:
                    if target in cmd_str or target in name:
                        if "FLAC_CONVERSION" in target or "convert_audio" in target:
                            matched_category = "Audio Conversion"
                        elif "Episode" in target or "youtube" in target.lower():
                            matched_category = "YouTube Video Creation"
                        elif "Split" in target:
                            matched_category = "Audio/Video Split"
                        elif "master" in target:
                            matched_category = "Audio Loudness Mastering"
                        else:
                            matched_category = "Mix Archive Processing"
                        break

                # 2. Check active encoders spawned during conversions
                if not matched_category and name in ENCODER_BINARIES:
                    if "libmp3lame" in cmd_str or "flac" in cmd_str or "pcm_s24le" in cmd_str:
                        matched_category = f"Active Encoder ({name})"
                    elif "showspectrumpic" in cmd_str:
                        matched_category = "Spectrogram Analysis (Spek)"
                    elif "h264" in cmd_str or "1920:1080" in cmd_str:
                        matched_category = "YouTube Video Encoding (ffmpeg)"
                    else:
                        matched_category = f"Media Processing ({name})"

                if matched_category:
                    mem = proc.info.get("memory_info")
                    found.append({
                        "pid": proc.info["pid"],
                        "name": name,
                        "category": matched_category,
                        "cmdline": cmd_str[:110] + ("..." if len(cmd_str) > 110 else ""),
                        "status": proc.info.get("status", "?"),
                        "cpu": proc.info.get("cpu_percent", 0.0),
                        "mem_mb": (mem.rss / 1024 / 1024) if mem else 0,
                        "create_time": datetime.fromtimestamp(proc.info["create_time"]) if proc.info.get("create_time") else None,
                        "username": proc.info.get("username", "?"),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort by PID ascending
        found.sort(key=lambda x: x["pid"])
        return found

    def count_manager_instances(self) -> int:
        """Count running Mix Archive Manager sessions."""
        if not PSUTIL_AVAILABLE:
            return 1
        count = 0
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                cmd_str = " ".join(proc.info.get("cmdline") or [])
                if "Mix_Archive_Manager.sh" in cmd_str or "manager.sh" in cmd_str:
                    count += 1
            except Exception:
                continue
        return max(1, count)

    def scan_directories(self) -> bool:
        current_files = set()
        new_audios = []
        new_videos = []
        audio_tot = 0
        video_tot = 0
        newly_added_size = 0

        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                continue
            for root, dirs, files in os.walk(watch_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    if fpath.suffix.lower() not in ALL_EXTS:
                        continue
                    current_files.add(str(fpath))
                    info = self.get_file_info(fpath)
                    if not info:
                        continue
                    if info["kind"] == "audio":
                        audio_tot += info["size"]
                        new_audios.append(info)
                    else:
                        video_tot += info["size"]
                        new_videos.append(info)

        # Detect new media
        newly_added = current_files - self.known_files
        for fstr in newly_added:
            fpath = Path(fstr)
            info = self.get_file_info(fpath)
            if info:
                newly_added_size += info["size"]
                self.log_new_file(info)
                self.new_count += 1

        self.session_bytes_written += newly_added_size
        self.known_files = current_files

        # Sort by mtime descending
        new_audios.sort(key=lambda x: x["mtime"], reverse=True)
        new_videos.sort(key=lambda x: x["mtime"], reverse=True)

        self.audio_files = new_audios
        self.video_files = new_videos
        self.total_audio_size = audio_tot
        self.total_video_size = video_tot

        self.latest_audio = new_audios[0] if new_audios else None
        self.latest_video = new_videos[0] if new_videos else None

        self.last_scan = datetime.now()

        # Update velocity tracking
        now = time.time()
        self.velocity_samples.append((now, self.session_bytes_written))
        return True

    def calculate_velocity_mb_min(self) -> float:
        """Calculate recent write rate in MB/minute."""
        if len(self.velocity_samples) < 2:
            return 0.0
        old_time, old_bytes = self.velocity_samples[0]
        cur_time, cur_bytes = self.velocity_samples[-1]
        dt = cur_time - old_time
        if dt <= 0:
            return 0.0
        db = cur_bytes - old_bytes
        mb_per_sec = (db / (1024 * 1024)) / dt
        return mb_per_sec * 60.0

    def log_new_file(self, info: dict):
        """Append to both JSONL intelligence log and TXT log."""
        ts_iso = datetime.now().isoformat()
        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = {
            "timestamp": ts_iso,
            "event": "CONVERSION_OUTPUT_DETECTED",
            "media_type": info["kind"],
            "format": info["ext"].replace(".", "").upper(),
            "filename": info["name"],
            "filepath": str(info["path"]),
            "size_bytes": info["size"],
            "human_size": self.human_size(info["size"]),
            "folder": info["parent_name"],
            "mtime": info["mtime"].isoformat(),
            "session_files_count": self.new_count + 1,
            "session_bytes_written": self.session_bytes_written + info["size"],
        }

        # Write to JSONL
        try:
            with open(self.log_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

        # Write human-readable text line
        try:
            txt_line = (
                f"[{ts_str}] [{info['kind'].upper():5}] [{info['ext'].upper()[1:]:4}] "
                f"{self.human_size(info['size']):>10} | {info['name']}\n"
            )
            with open(self.log_txt, "a", encoding="utf-8") as f:
                f.write(txt_line)
        except Exception:
            pass

    def build_summary_table(self):
        table = Table(
            title=f"[bold magenta]{APP_NAME}[/] [deep_pink1]v{VERSION}[/]",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            header_style="bold bright_cyan",
            title_style="bold magenta",
        )
        table.add_column("Telemetry Metric", style="bold orchid", no_wrap=True)
        table.add_column("Value / Status", style="bold bright_cyan")

        # Counts by format
        flac_cnt = sum(1 for a in self.audio_files if a["ext"] == ".flac")
        mp3_cnt = sum(1 for a in self.audio_files if a["ext"] == ".mp3")
        wav_cnt = sum(1 for a in self.audio_files if a["ext"] == ".wav")
        other_aud = len(self.audio_files) - (flac_cnt + mp3_cnt + wav_cnt)

        table.add_row("Audio Files Converted",
                      f"[bold spring_green1]{len(self.audio_files)}[/] "
                      f"([cyan]{flac_cnt}[/] FLAC, [yellow]{mp3_cnt}[/] MP3, [magenta]{wav_cnt}[/] WAV"
                      + (f", [dim]{other_aud} other[/]" if other_aud > 0 else "") + ")")
        table.add_row("YouTube Videos Rendered", f"[bold medium_purple]{len(self.video_files)}[/] MP4 Videos")
        table.add_row("Total Output Size (All)",
                      f"[bold spring_green1]{self.human_size(self.total_audio_size + self.total_video_size)}[/] "
                      f"([spring_green1]Audio:[/] {self.human_size(self.total_audio_size)} | [medium_purple]Video:[/] {self.human_size(self.total_video_size)})")

        table.add_row("New Outputs This Session", f"[bold yellow]{self.new_count}[/] files")
        table.add_row("New Data Written (Session)", f"[bold spring_green1]{self.human_size(self.session_bytes_written)}[/]")

        vel = self.calculate_velocity_mb_min()
        table.add_row("Conversion Velocity", f"[bold hot_pink]{vel:.2f} MB/min[/] [dim]({vel*60/1024:.2f} GB/hr)[/]")

        mgr_instances = self.count_manager_instances()
        mgr_badge = f"[bold green]{mgr_instances} Active[/]" if mgr_instances == 1 else f"[bold yellow]{mgr_instances} Instances Active (Multi-Instance)[/]"
        table.add_row("MP Manager Instances", mgr_badge)

        if self.latest_audio:
            table.add_row("Latest Converted Audio", f"[spring_green1]{self.latest_audio['name']}[/]")
            table.add_row("  └ Size / Time / Folder",
                          f"{self.human_size(self.latest_audio['size'])}  @  {self.latest_audio['mtime'].strftime('%H:%M:%S')}  [{self.latest_audio['parent_name']}]")
        else:
            table.add_row("Latest Converted Audio", "[dim]None yet detected[/]")

        if self.latest_video:
            table.add_row("Latest YouTube Video", f"[medium_purple]{self.latest_video['name']}[/]")
            table.add_row("  └ Size / Time / Folder",
                          f"{self.human_size(self.latest_video['size'])}  @  {self.latest_video['mtime'].strftime('%H:%M:%S')}  [{self.latest_video['parent_name']}]")
        else:
            table.add_row("Latest YouTube Video", "[dim]None yet detected[/]")

        table.add_row("Last Scan Time", self.last_scan.strftime("%Y-%m-%d %H:%M:%S") if self.last_scan else "Never")
        table.add_row("Monitor Uptime", str(datetime.now() - self.start_time).split(".")[0])

        return table

    def build_disk_panel(self):
        info = self.get_disk_info()
        if "error" in info:
            return Panel(f"[red]Disk info error: {info['error']}[/]", title="Drive Space", border_style="red")

        free_style = STYLE_ALERT if info["low"] else "bold spring_green1"
        alert_msg = "\n[bold red]⚠ LOW DISK SPACE ALERT (≤ 20%) — ARCHIVE DRIVE FILLING FAST ⚠[/]" if info["low"] else ""

        watched_str = " | ".join(f"[hot_pink]{p.name}[/]" for p in self.watch_dirs[:4])
        if len(self.watch_dirs) > 4:
            watched_str += f" [dim](+{len(self.watch_dirs)-4} more)[/]"

        content = (
            f"[bold orchid]Target Mount:[/]    [cyan]{info['mount']}[/]\n"
            f"[bold orchid]Monitored Dirs:[/]  {watched_str}\n"
            f"[bold orchid]Total Storage:[/]   {self.human_size(info['total'])}\n"
            f"[bold orchid]Free Space:[/]      [{free_style}]{self.human_size(info['free'])}[/]  "
            f"([{free_style}]{info['free_percent']:.1f}% free[/])  |  "
            f"[bold green]~{info['est_mixes']} mixes headroom left[/]"
            f"{alert_msg}"
        )
        border = "red" if info["low"] else "cyan"
        return Panel(content, title="[bold bright_cyan]Archive Drive Capacity & Headroom[/]", border_style=border)

    def build_process_panel(self, procs: list[dict]):
        if not PSUTIL_AVAILABLE:
            return Panel("[yellow]psutil not installed — live process detection limited.[/]",
                         title="Active Processes", border_style="yellow")

        if not procs:
            return Panel("[dim]○ No MP Mix Archive Manager conversion or video rendering jobs active right now.[/]",
                         title="[bold cyan]Active Conversion & Video Creation Pipelines[/]", border_style="cyan")

        table = Table(box=box.SIMPLE, border_style="cyan", show_header=True, header_style="bold bright_cyan")
        table.add_column("PID", style="bold magenta", width=8)
        table.add_column("Task Category", style="bold hot_pink")
        table.add_column("Status", style="spring_green1")
        table.add_column("CPU %", style="orchid")
        table.add_column("RAM MB", style="cyan")
        table.add_column("Started", style="medium_purple")
        table.add_column("Command Preview", style="dim")

        for p in procs:
            started = p["create_time"].strftime("%H:%M:%S") if p["create_time"] else "?"
            table.add_row(
                str(p["pid"]),
                p["category"],
                p["status"],
                f"{p['cpu']:.1f}%",
                f"{p['mem_mb']:.1f}",
                started,
                p["cmdline"],
            )
        return Panel(table, title=f"[bold bright_cyan]Active Conversion & Video Creation Pipelines ({len(procs)} Jobs Running)[/]", border_style="cyan")

    def build_ticker(self):
        ticker = Text()
        ticker.append("● LIVE MONITOR ", style="bold bright_cyan")
        ticker.append(f"Watching {len(self.watch_dirs)} Output Folder(s) ", style="orchid")
        ticker.append(" | Refresh 10s | ", style="magenta")
        ticker.append(f"Log: {self.log_jsonl.name}", style="yellow")
        ticker.append("\n[A] Audio Mixes  [Y/V] YouTube Videos  [D] Change Dirs  [P] Process List  [L] View Log  [Q] Quit", style="bold spring_green1")
        return Panel(ticker, border_style="bright_cyan", style="on black")

    def show_list(self, items: list[dict], kind: str):
        if not items:
            console.print(f"[bold yellow]No {kind} found in monitored directories.[/]")
            return

        last10 = items[:10]
        table = Table(title=f"Last 10 {kind.title()} Files Generated", box=box.ROUNDED, border_style="cyan")
        table.add_column("#", style="bold magenta", width=4)
        table.add_column("Filename", style="bold bright_cyan")
        table.add_column("Folder", style="orchid")
        table.add_column("Size", style="spring_green1")
        table.add_column("Timestamp", style="medium_purple")

        for i, item in enumerate(last10, 1):
            table.add_row(
                str(i),
                item["name"],
                item["parent_name"],
                self.human_size(item["size"]),
                item["mtime"].strftime("%Y-%m-%d %H:%M:%S")
            )
        console.print(table)

        player_hint = "MP Audio Player / Player" if kind == "Audio" else "VLC Video Player"
        try:
            choice = IntPrompt.ask(
                f"[bold cyan]Select number [1-{len(last10)}] to launch and play in {player_hint} (0 to cancel)[/]",
                default=0
            )
            if 1 <= choice <= len(last10):
                target = last10[choice - 1]["path"]
                self.launch_player(target, kind)
        except Exception:
            pass

    def launch_player(self, path: Path, kind: str):
        target_str = str(path)
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        if "WAYLAND_DISPLAY" not in env:
            env["WAYLAND_DISPLAY"] = "wayland-0"
        if "XDG_RUNTIME_DIR" not in env and hasattr(os, "getuid"):
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"

        if kind == "Audio":
            # Check configured player
            default_p = self.config.get("DEFAULT_AUDIO_PLAYER", "mp_audio_player")
            player_cmd = None
            if default_p == "mp_audio_player":
                # Check MP_Audio_Player.py in project
                for p_script in [self.project_root / "MP_Audio_Player.py", self.project_root / "scripts/MP_Audio_Player.py"]:
                    if p_script.is_file():
                        player_cmd = ["python3", str(p_script), target_str]
                        break
            if not player_cmd and shutil.which(default_p):
                player_cmd = [default_p, target_str]

            # Fallback list
            if not player_cmd:
                for candidate in ["audacious", "strawberry", "vlc", "mpv", "xdg-open", "open"]:
                    if shutil.which(candidate):
                        player_cmd = [candidate, target_str]
                        break

            if player_cmd:
                try:
                    subprocess.Popen(player_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    console.print(f"[bold spring_green1]✓ Launched audio in {player_cmd[0]}: {path.name}[/]")
                    return
                except Exception as e:
                    console.print(f"[yellow]Could not launch audio player ({e}).[/]")
            console.print("[bold yellow]No supported audio player found on system.[/]")

        else:
            # Video player
            default_v = self.config.get("DEFAULT_VIDEO_PLAYER", "vlc")
            video_cmd = None
            if shutil.which(default_v):
                video_cmd = [default_v, target_str]
            elif shutil.which("flatpak"):
                try:
                    res = subprocess.run(["flatpak", "info", "org.videolan.VLC"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        video_cmd = ["flatpak", "run", "org.videolan.VLC", target_str]
                except Exception:
                    pass

            if not video_cmd:
                for v_cand in ["vlc", "mpv", "haruna", "kodi", "xdg-open", "open"]:
                    if shutil.which(v_cand):
                        video_cmd = [v_cand, target_str]
                        break

            if video_cmd:
                try:
                    subprocess.Popen(video_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    console.print(f"[bold spring_green1]✓ Launched video in {video_cmd[0]}: {path.name}[/]")
                    return
                except Exception as e:
                    console.print(f"[yellow]Could not launch video player ({e}).[/]")
            console.print("[bold yellow]No supported video player found on system.[/]")

    def view_recent_logs(self):
        console.clear()
        console.print(Panel.fit("[bold bright_cyan]Recent Conversion Log Entries[/]", border_style="cyan"))
        if not self.log_jsonl.exists():
            console.print("[yellow]Log file does not exist yet. It will be created when files are converted.[/]")
            Prompt.ask("[dim]Press Enter to return[/]")
            return

        lines = []
        try:
            with open(self.log_jsonl, "r", encoding="utf-8") as f:
                for l in f:
                    if l.strip():
                        lines.append(l.strip())
        except Exception as e:
            console.print(f"[red]Error reading log: {e}[/]")
            Prompt.ask("[dim]Press Enter to return[/]")
            return

        table = Table(box=box.SIMPLE, border_style="cyan", show_header=True)
        table.add_column("Timestamp", style="magenta", width=19)
        table.add_column("Type", style="bold cyan", width=6)
        table.add_column("Fmt", style="bold yellow", width=5)
        table.add_column("Size", style="spring_green1", width=10)
        table.add_column("Filename", style="bright_cyan")

        for line_str in lines[-15:]:
            try:
                data = json.loads(line_str)
                table.add_row(
                    data.get("timestamp", "")[:19].replace("T", " "),
                    data.get("media_type", "").upper(),
                    data.get("format", ""),
                    data.get("human_size", ""),
                    data.get("filename", "")
                )
            except Exception:
                continue

        console.print(table)
        console.print(f"\n[dim]Log file path: {self.log_jsonl}[/]")
        Prompt.ask("[dim]Press Enter to return to monitor[/]")

    def change_directories(self):
        console.clear()
        console.print(Panel.fit("[bold bright_cyan]Configure Monitored Output Directories[/]", border_style="cyan"))
        console.print("Currently Monitored Directory Paths:")
        for idx, d in enumerate(self.watch_dirs, 1):
            console.print(f"  [{idx}] [hot_pink]{d}[/]")

        console.print("\n[bold cyan]Options:[/]")
        console.print("  [1] Reset to All Standard Mix Archive Output Folders (FLAC, MP3, WAV, MP4, SPEK)")
        console.print("  [2] Monitor Single Custom Directory")
        console.print("  [3] Add Another Directory to Monitored List")
        console.print("  [0] Keep Current and Return")

        try:
            choice = IntPrompt.ask("[bold bright_cyan]Select[/]", default=0)
            if choice == 1:
                self.watch_dirs = self.detect_default_watch_dirs()
                self.known_files.clear()
                self.scan_directories()
                console.print("[spring_green1]✓ Reset to all standard output folders.[/]")
                time.sleep(1)
            elif choice == 2:
                new_path = Prompt.ask("[bold bright_cyan]Enter directory path[/]")
                p = Path(new_path).expanduser().resolve()
                if p.exists() and p.is_dir():
                    self.watch_dirs = [p]
                    self.known_files.clear()
                    self.scan_directories()
                    console.print(f"[spring_green1]✓ Now monitoring solely: {p}[/]")
                    time.sleep(1)
                else:
                    console.print("[red]Directory not found.[/]")
                    time.sleep(1.5)
            elif choice == 3:
                new_path = Prompt.ask("[bold bright_cyan]Enter directory to add[/]")
                p = Path(new_path).expanduser().resolve()
                if p.exists() and p.is_dir() and p not in self.watch_dirs:
                    self.watch_dirs.append(p)
                    self.scan_directories()
                    console.print(f"[spring_green1]✓ Added directory: {p}[/]")
                    time.sleep(1)
                else:
                    console.print("[yellow]Invalid directory or already monitored.[/]")
                    time.sleep(1.5)
        except Exception:
            pass

    def run(self):
        console.clear()
        console.print(Panel.fit(
            f"[bold magenta]{APP_NAME}[/]\n[bright_cyan]v{VERSION}[/]\n"
            f"Watching [hot_pink]{len(self.watch_dirs)}[/] conversion output folder(s)",
            border_style="cyan",
            title="Starting Conversion Output Monitor"
        ))

        console.print("[bold spring_green1]Performing initial scan of audio and video folders...[/]")
        self.scan_directories()
        console.print(f"[bold spring_green1]Found {len(self.audio_files)} audio mixes and {len(self.video_files)} YouTube videos.[/]")
        console.print(f"[orchid]Intelligence Log: {self.log_jsonl}[/]")
        time.sleep(1.2)

        try:
            while True:
                self.scan_directories()
                procs = self.get_running_conversion_processes()

                console.clear()
                console.print(self.build_ticker())
                console.print(self.build_summary_table())
                console.print(self.build_disk_panel())
                console.print(self.build_process_panel(procs))
                console.print(
                    "\n[bold bright_cyan]Actions:[/]\n"
                    "  [bold spring_green1][A][/] View Last 10 Converted Audio Mixes (FLAC / MP3 / WAV)\n"
                    "  [bold medium_purple][Y][/] View Last 10 Rendered YouTube Videos (.MP4)\n"
                    "  [bold hot_pink][D][/] Configure / Switch Monitored Folders\n"
                    "  [bold orchid][L][/] View Recent Conversion JSONL Logs\n"
                    "  [yellow][Q][/] Quit\n"
                )

                start = time.time()
                action = None
                while time.time() - start < 10:
                    if sys.stdin in select.select([sys.stdin], [], [], 0.5)[0]:
                        key = sys.stdin.read(1).lower()
                        if key == "a":
                            action = "audio"
                            break
                        elif key in ("y", "v"):
                            action = "video"
                            break
                        elif key == "d":
                            action = "change_dirs"
                            break
                        elif key == "l":
                            action = "logs"
                            break
                        elif key == "q":
                            action = "quit"
                            break
                    time.sleep(0.1)

                if action == "audio":
                    console.clear()
                    self.show_list(self.audio_files, "Audio")
                    Prompt.ask("[dim]Press Enter to return to monitor[/]")
                elif action == "video":
                    console.clear()
                    self.show_list(self.video_files, "Video")
                    Prompt.ask("[dim]Press Enter to return to monitor[/]")
                elif action == "change_dirs":
                    self.change_directories()
                elif action == "logs":
                    self.view_recent_logs()
                elif action == "quit":
                    break

        except KeyboardInterrupt:
            pass

        console.print("\n[bold magenta]Conversion Output Monitor stopped.[/]")
        console.print(f"[orchid]Full intelligence log: {self.log_jsonl}[/]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MP Mix Manager Audio & Video Output Monitor")
    parser.add_argument("dirs", nargs="*", default=None, help="Specific directories to monitor (optional)")
    parser.add_argument("--dir", "-d", dest="single_dir", default=None, help="Directory to monitor")
    args = parser.parse_args()

    target_paths = []
    if args.single_dir:
        target_paths.append(Path(args.single_dir))
    if args.dirs:
        for d in args.dirs:
            target_paths.append(Path(d))

    monitor = AudioVideoMonitor(target_paths if target_paths else None)
    monitor.run()
