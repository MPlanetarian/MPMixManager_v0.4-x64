#!/usr/bin/env python3
"""
MP_Video_Image_Dir_WAN2GP_Output_Monitor.py
Version: 0.0.4
Pinky-Purple Image & Video Output Monitor for WAN2GP (FLUX / LTX / WAN2GP)

Monitors WAN2GP output directory for new media files.
Features:
- Live summary table (images/videos count, total size, latest files)
- 10-second refresh ticker
- Logging of new files (path, mtime, size)
- Last 10 images/videos lists with launch to XnView MP / VLC
- Batch rename for Images (FLUX / Other) and Videos (LTX / Other)
- Live process monitoring for wan2gp_flux_batch, wan2gp_ltx_batch, and wan2gp_tts_batch
- Drive free-space monitoring with ≤20% red alert
- Session new-data-written metric
- Configurable output directory via CLI, environment, config.env, and interactive [D] command
- Multi-platform XnView MP launch (Flatpak com.xnview.XnViewMP, native binaries, and fallbacks)
- Continuous monitoring
"""

import os
import time
import subprocess
import sys
import select
import re
import shutil
import argparse
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
    print("Error: 'rich' library required. Install with: pip install rich")
    sys.exit(1)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

VERSION = "0.0.4"
APP_NAME = "MP Video Image Directory Output Monitor (FLUX / LTX / WAN2GP)"
LOG_FILE = Path("WAN2GP_Monitor_Log.txt")

# Batch scripts to monitor
TARGET_SCRIPTS = [
    "wan2gp_flux_batch",
    "wan2gp_ltx_batch",
    "wan2gp_tts_batch",
]
TARGET_SCRIPT_PATHS = [
    "/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_flux_batch.py",
    "/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_ltx_batch.py",
    "/var/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_tts_batch.py",
    "/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_flux_batch.py",
    "/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_ltx_batch.py",
    "/home/mplanetarian/MP_Mix_Manager_v0.3/scripts/wan2gp_tts_batch.py",
]

IMAGE_EXTS = {".jpeg", ".jpg", ".png"}
VIDEO_EXTS = {".mp4", ".webm", ".mpeg", ".avi", ".mkv"}
ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS

# Pinky-purple theme
STYLE_TITLE = "bold magenta"
STYLE_HEADER = "bold bright_magenta"
STYLE_IMAGE = "bold hot_pink"
STYLE_VIDEO = "bold medium_purple"
STYLE_METRIC = "bold orchid"
STYLE_OK = "bold spring_green1"
STYLE_WARN = "bold yellow"
STYLE_TICKER = "bold deep_pink1"
STYLE_ALERT = "bold red on black"

console = Console()


def resolve_default_watch_dir() -> Path:
    """Resolve the default directory to watch using env, config.env, and fallbacks."""
    # 1. Active environment variable
    env_dir = os.environ.get("WAN2GP_OUTPUTS")
    if env_dir:
        p = Path(env_dir).expanduser()
        if p.exists():
            return p

    # 2. Check config.env in project or home directories
    search_dirs = [
        Path.cwd(),
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.home() / "MP_Mix_Manager_v0.3",
        Path("/var/home/mplanetarian/MP_Mix_Manager_v0.3"),
    ]
    for base in search_dirs:
        cfg = base / "config.env"
        if cfg.is_file():
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("WAN2GP_OUTPUTS="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                p = Path(val).expanduser()
                                if p.exists():
                                    return p
            except Exception:
                pass

    # 3. Known fallback locations
    fallbacks = [
        Path("/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/WAN2GP_OUTPUTS"),
        Path.home() / "Documents/WAN2GP_OUTPUTS",
        Path.home() / "WAN2GP_OUTPUTS",
        Path("/var/home/mplanetarian/Documents/WAN2GP_OUTPUTS"),
    ]
    for fb in fallbacks:
        if fb.exists():
            return fb

    return Path.home() / "Documents/WAN2GP_OUTPUTS"


class Monitor:
    def __init__(self, watch_dir: Path | str | None = None):
        if watch_dir:
            self.watch_dir = Path(watch_dir).expanduser().resolve()
        else:
            self.watch_dir = resolve_default_watch_dir().resolve()

        self.known_files = set()
        self.images = []
        self.videos = []
        self.total_size = 0
        self.latest_image = None
        self.latest_video = None
        self.start_time = datetime.now()
        self.last_scan = None
        self.new_count = 0
        self.log_initialized = False
        self.session_bytes_written = 0  # cumulative size of new media detected this session
        self.disk_alert_threshold = 20.0  # percent

    def human_size(self, size_bytes):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def get_file_info(self, path: Path):
        try:
            stat = path.stat()
            return {
                "path": path,
                "name": path.name,
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime),
                "ext": path.suffix.lower()
            }
        except Exception:
            return None

    def get_disk_info(self):
        """Return disk usage for the filesystem containing watch_dir."""
        try:
            target = self.watch_dir if self.watch_dir.exists() else self.watch_dir.parent
            usage = shutil.disk_usage(target)
            free_percent = (usage.free / usage.total * 100) if usage.total else 0
            mount_point = str(target)
            if PSUTIL_AVAILABLE:
                try:
                    for part in psutil.disk_partitions(all=False):
                        if target.resolve().is_relative_to(Path(part.mountpoint)):
                            mount_point = part.mountpoint
                            break
                except Exception:
                    pass
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "free_percent": free_percent,
                "mount": mount_point,
                "low": free_percent <= self.disk_alert_threshold,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_running_batch_processes(self):
        """Return list of dicts with stats for matching FLUX/LTX/TTS batch processes."""
        if not PSUTIL_AVAILABLE:
            return []
        found = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "status", "create_time", "cpu_percent", "memory_info", "username"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                cmd_str = " ".join(cmdline)
                name = proc.info.get("name") or ""
                matched = False
                for target in TARGET_SCRIPTS + TARGET_SCRIPT_PATHS:
                    if target in cmd_str or target in name:
                        matched = True
                        break
                if matched:
                    mem = proc.info.get("memory_info")
                    found.append({
                        "pid": proc.info["pid"],
                        "name": name,
                        "cmdline": cmd_str[:120] + ("..." if len(cmd_str) > 120 else ""),
                        "status": proc.info.get("status", "?"),
                        "cpu": proc.info.get("cpu_percent", 0.0),
                        "mem_mb": (mem.rss / 1024 / 1024) if mem else 0,
                        "create_time": datetime.fromtimestamp(proc.info["create_time"]) if proc.info.get("create_time") else None,
                        "username": proc.info.get("username", "?"),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return found

    def scan_directory(self):
        if not self.watch_dir.exists():
            return False

        current_files = set()
        new_images = []
        new_videos = []
        total = 0
        newly_added_size = 0

        for root, dirs, files in os.walk(self.watch_dir):
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() not in ALL_EXTS:
                    continue
                current_files.add(str(fpath))
                info = self.get_file_info(fpath)
                if not info:
                    continue
                total += info["size"]
                if info["ext"] in IMAGE_EXTS:
                    new_images.append(info)
                else:
                    new_videos.append(info)

        # Detect new files and accumulate session bytes
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
        new_images.sort(key=lambda x: x["mtime"], reverse=True)
        new_videos.sort(key=lambda x: x["mtime"], reverse=True)

        self.images = new_images
        self.videos = new_videos
        self.total_size = total

        self.latest_image = new_images[0] if new_images else None
        self.latest_video = new_videos[0] if new_videos else None

        self.last_scan = datetime.now()
        return True

    def change_watch_dir(self, new_dir: Path | str) -> bool:
        """Dynamically switch to a new watched directory."""
        path = Path(new_dir).expanduser()
        if not path.exists():
            console.print(f"[yellow]Directory does not exist:[/] {path}")
            if Confirm.ask("[magenta]Would you like to create it?[/]", default=True):
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    console.print(f"[spring_green1]✓ Created directory:[/] {path}")
                except Exception as e:
                    console.print(f"[red]Error creating directory: {e}[/]")
                    time.sleep(1.5)
                    return False
            else:
                time.sleep(1)
                return False

        self.watch_dir = path.resolve()
        self.known_files.clear()
        self.images.clear()
        self.videos.clear()
        self.latest_image = None
        self.latest_video = None
        self.scan_directory()

        try:
            with open(LOG_FILE, "a") as f:
                f.write(f"\n[SWITCH DIR {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Monitored Directory changed to: {self.watch_dir}\n")
        except Exception:
            pass

        console.print(f"[bold spring_green1]✓ Monitored Directory updated to:[/] [hot_pink]{self.watch_dir}[/]")
        time.sleep(1.2)
        return True

    def log_new_file(self, info):
        if not self.log_initialized:
            try:
                with open(LOG_FILE, "a") as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"Monitor Session Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Watching: {self.watch_dir}\n")
                    f.write(f"{'='*80}\n")
                self.log_initialized = True
            except Exception:
                return

        line = (
            f"[{info['mtime'].strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{info['size']:>12} bytes | "
            f"{info['path']}\n"
        )
        try:
            with open(LOG_FILE, "a") as f:
                f.write(line)
        except Exception:
            pass

    def log_rename(self, old_path: Path, new_path: Path):
        try:
            with open(LOG_FILE, "a") as f:
                f.write(f"[RENAME {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {old_path} -> {new_path}\n")
        except Exception:
            pass

    def build_summary_table(self):
        table = Table(
            title=f"[bold magenta]{APP_NAME}[/]  |  [deep_pink1]v{VERSION}[/]",
            box=box.DOUBLE_EDGE,
            border_style="magenta",
            header_style="bold bright_magenta",
            title_style="bold magenta"
        )
        table.add_column("Metric", style="bold orchid", no_wrap=True)
        table.add_column("Value", style="bold hot_pink")

        table.add_row("Images Generated", f"[bold hot_pink]{len(self.images)}[/]")
        table.add_row("Videos Generated", f"[bold medium_purple]{len(self.videos)}[/]")
        table.add_row("Total Media Files", f"{len(self.images) + len(self.videos)}")
        table.add_row("Total Size (All)", f"[bold spring_green1]{self.human_size(self.total_size)}[/]")
        table.add_row("New Files This Session", f"[bold yellow]{self.new_count}[/]")
        table.add_row("New Data Written (Session)", f"[bold spring_green1]{self.human_size(self.session_bytes_written)}[/]")

        if self.latest_image:
            table.add_row("Latest Image", f"[hot_pink]{self.latest_image['name']}[/]")
            table.add_row("  └ Size / Time", f"{self.human_size(self.latest_image['size'])}  @  {self.latest_image['mtime'].strftime('%H:%M:%S')}")
        else:
            table.add_row("Latest Image", "[dim]None[/]")

        if self.latest_video:
            table.add_row("Latest Video", f"[medium_purple]{self.latest_video['name']}[/]")
            table.add_row("  └ Size / Time", f"{self.human_size(self.latest_video['size'])}  @  {self.latest_video['mtime'].strftime('%H:%M:%S')}")
        else:
            table.add_row("Latest Video", "[dim]None[/]")

        table.add_row("Last Scan", self.last_scan.strftime("%Y-%m-%d %H:%M:%S") if self.last_scan else "Never")
        table.add_row("Uptime", str(datetime.now() - self.start_time).split(".")[0])

        return table

    def build_disk_panel(self):
        info = self.get_disk_info()
        if "error" in info:
            return Panel(f"[red]Disk info error: {info['error']}[/]", title="Drive Space", border_style="red")

        free_style = STYLE_ALERT if info["low"] else "bold spring_green1"
        alert_msg = "\n[bold red]⚠ LOW DISK SPACE ALERT (≤ 20%) ⚠[/]" if info["low"] else ""

        content = (
            f"[bold orchid]Mount Point:[/] [hot_pink]{info['mount']}[/]\n"
            f"[bold orchid]Output Path:[/] [hot_pink]{self.watch_dir}[/]\n"
            f"[bold orchid]Total:[/]  {self.human_size(info['total'])}\n"
            f"[bold orchid]Used:[/]   {self.human_size(info['used'])}\n"
            f"[bold orchid]Free:[/]   [{free_style}]{self.human_size(info['free'])}[/]  "
            f"([{free_style}]{info['free_percent']:.1f}% free[/])"
            f"{alert_msg}"
        )
        border = "red" if info["low"] else "magenta"
        return Panel(content, title="[bold magenta]Drive Free Space[/]", border_style=border)

    def build_process_panel(self, procs):
        if not PSUTIL_AVAILABLE:
            return Panel("[yellow]psutil not installed — process details limited.\nInstall with: pip install psutil[/]",
                         title="Batch Processes", border_style="yellow")
        if not procs:
            return Panel("[dim]No wan2gp_flux_batch, wan2gp_ltx_batch, or wan2gp_tts_batch processes running.[/]",
                         title="[bold magenta]Batch Process Monitor[/]", border_style="magenta")

        table = Table(box=box.SIMPLE, border_style="hot_pink", show_header=True, header_style="bold bright_magenta")
        table.add_column("PID", style="bold magenta")
        table.add_column("CPU %", style="orchid")
        table.add_column("MEM MB", style="hot_pink")
        table.add_column("Status", style="spring_green1")
        table.add_column("Started", style="medium_purple")
        table.add_column("Command (truncated)", style="dim")

        for p in procs:
            started = p["create_time"].strftime("%H:%M:%S") if p["create_time"] else "?"
            table.add_row(
                str(p["pid"]),
                f"{p['cpu']:.1f}",
                f"{p['mem_mb']:.1f}",
                p["status"],
                started,
                p["cmdline"]
            )
        return Panel(table, title=f"[bold magenta]Live Batch Processes ({len(procs)} running)[/]", border_style="magenta")

    def build_ticker(self):
        ticker = Text()
        ticker.append("● LIVE ", style="bold deep_pink1")
        ticker.append("Monitoring ", style="magenta")
        ticker.append(str(self.watch_dir), style="bold hot_pink")
        ticker.append("  |  Refresh every 10s  |  ", style="medium_purple")
        ticker.append(f"Log: {LOG_FILE.name}", style="orchid")
        ticker.append("  |  [I] Images  [V] Videos  [RI] Rename Images  [RV] Rename Videos  [D] Change Dir  [Q] Quit", style="bold magenta")
        return Panel(ticker, border_style="magenta", style="on black")

    def show_list(self, items, kind):
        if not items:
            console.print(f"[bold yellow]No {kind} found.[/]")
            return

        last10 = items[:10]
        table = Table(title=f"Last 10 {kind}s", box=box.ROUNDED, border_style="hot_pink")
        table.add_column("#", style="bold magenta", width=4)
        table.add_column("Filename", style="bold hot_pink")
        table.add_column("Size", style="orchid")
        table.add_column("Modified", style="medium_purple")

        for i, item in enumerate(last10, 1):
            table.add_row(
                str(i),
                item["name"],
                self.human_size(item["size"]),
                item["mtime"].strftime("%Y-%m-%d %H:%M:%S")
            )
        console.print(table)

        try:
            choice = IntPrompt.ask(
                f"[bold magenta]Select number to open in {'XnView MP' if kind=='Image' else 'VLC'} (0 to cancel)[/]",
                default=0
            )
            if 1 <= choice <= len(last10):
                target = last10[choice - 1]["path"]
                self.launch_viewer(target, kind)
        except Exception:
            pass

    def get_image_viewer_cmd(self, path: Path):
        """Locate XnView MP executable via environment, Flatpak, PATH, or known paths."""
        target_str = str(path)

        # 1. Environment variable override
        custom = os.environ.get("XNVIEW_BIN") or os.environ.get("XNVIEW_PATH")
        if custom:
            return [custom, target_str]

        # 2. Flatpak com.xnview.XnViewMP (standard on Bazzite / Fedora Atomic / SteamOS)
        flatpak_bin = shutil.which("flatpak")
        if flatpak_bin:
            try:
                res = subprocess.run([flatpak_bin, "info", "com.xnview.XnViewMP"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    return [flatpak_bin, "run", "com.xnview.XnViewMP", target_str]
            except Exception:
                pass

        # 3. Known exported paths and desktop scripts
        known_paths = [
            Path.home() / ".local/share/flatpak/exports/bin/com.xnview.XnViewMP",
            Path("/var/lib/flatpak/exports/bin/com.xnview.XnViewMP"),
            Path.home() / "KDE_CONNECT_CMDS/kc_launch_xnviewmp.sh",
            Path("/opt/XnView/xnview.sh"),
            Path("/opt/xnviewmp/xnviewmp"),
            Path("/usr/bin/xnview"),
            Path("/usr/local/bin/xnview"),
            Path("C:/Program Files/XnViewMP/xnviewmp.exe"),
            Path("C:/Program Files (x86)/XnViewMP/xnviewmp.exe"),
            Path("/Applications/XnViewMP.app/Contents/MacOS/XnViewMP"),
        ]
        for kp in known_paths:
            if kp.is_file() and (os.access(str(kp), os.X_OK) or sys.platform == "win32"):
                return [str(kp), target_str]

        # 4. Binary names in standard PATH
        for bin_name in ["com.xnview.XnViewMP", "xnviewmp", "xnview", "XnViewMP"]:
            if shutil.which(bin_name):
                return [bin_name, target_str]

        return None

    def launch_viewer(self, path: Path, kind):
        # Prepare graphical environment variables
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        if "WAYLAND_DISPLAY" not in env:
            env["WAYLAND_DISPLAY"] = "wayland-0"
        if "XDG_RUNTIME_DIR" not in env and hasattr(os, "getuid"):
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"

        if kind == "Image":
            cmd = self.get_image_viewer_cmd(path)
            if cmd:
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    console.print(f"[bold spring_green1]✓ Opened image in XnView MP: {path.name}[/]")
                    return
                except Exception as e:
                    console.print(f"[yellow]Failed to launch XnView MP ({e}), attempting system viewer...[/]")

            # Fallback to system default viewer
            fallback = shutil.which("xdg-open") or shutil.which("open")
            if fallback:
                try:
                    subprocess.Popen([fallback, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    console.print(f"[bold spring_green1]✓ Opened image with system viewer: {path.name}[/]")
                    return
                except Exception:
                    pass

            console.print("[bold yellow]XnView MP not found. Please install Flatpak com.xnview.XnViewMP or add xnviewmp to PATH.[/]")

        else:
            # Video viewer
            vlc_cmd = None
            if shutil.which("vlc"):
                vlc_cmd = ["vlc", str(path)]
            elif shutil.which("flatpak"):
                try:
                    res = subprocess.run(["flatpak", "info", "org.videolan.VLC"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        vlc_cmd = ["flatpak", "run", "org.videolan.VLC", str(path)]
                except Exception:
                    pass

            if not vlc_cmd:
                fallback = shutil.which("xdg-open") or shutil.which("open")
                if fallback:
                    vlc_cmd = [fallback, str(path)]

            if vlc_cmd:
                try:
                    subprocess.Popen(vlc_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                    console.print(f"[bold spring_green1]✓ Opened video in player: {path.name}[/]")
                    return
                except Exception as e:
                    console.print(f"[bold yellow]Failed to launch video player ({e}).[/]")
            else:
                console.print("[bold yellow]VLC player not found in PATH.[/]")

    def batch_rename(self, media_type: str, category: str):
        console.clear()
        console.print(Panel.fit(
            f"[bold magenta]Batch Rename {media_type.title()}s[/]\n"
            f"Category filter: [hot_pink]{category}[/]",
            border_style="magenta"
        ))

        candidates = []
        pattern = re.compile(r"_(?P<num>\d+)(?P<ext>\.[^.]+)$", re.IGNORECASE)

        items = self.images if media_type == "image" else self.videos
        for info in items:
            name = info["name"]
            if category == "FLUX" and "FLUX" not in name.upper():
                continue
            if category == "LTX" and "LTX" not in name.upper():
                continue
            if category == "Other":
                if media_type == "image" and "FLUX" in name.upper():
                    continue
                if media_type == "video" and "LTX" in name.upper():
                    continue

            m = pattern.search(name)
            if m:
                candidates.append((info["path"], m))

        if not candidates:
            console.print("[bold yellow]No matching files with numeric suffix (_01, _02, ...) found.[/]")
            Prompt.ask("[dim]Press Enter to return[/]")
            return

        console.print(f"[bold spring_green1]Found {len(candidates)} candidate file(s) to rename.[/]\n")

        table = Table(title="Preview (first 8)", box=box.SIMPLE, border_style="hot_pink")
        table.add_column("Current Name", style="hot_pink")
        table.add_column("Current #", style="orchid")
        for path, m in candidates[:8]:
            table.add_row(path.name, m.group("num"))
        console.print(table)
        if len(candidates) > 8:
            console.print(f"[dim]... and {len(candidates)-8} more[/]")

        try:
            new_num_str = Prompt.ask(
                "[bold magenta]Enter new number (e.g. 2 → _02, 15 → _15)[/]",
                default="2"
            )
            new_num = int(new_num_str)
            if new_num < 0:
                raise ValueError
            new_suffix = f"_{new_num:02d}"
        except Exception:
            console.print("[bold red]Invalid number. Aborting.[/]")
            Prompt.ask("[dim]Press Enter to return[/]")
            return

        console.print(f"\n[bold yellow]This will rename files so that _XX becomes {new_suffix}[/]")
        if not Confirm.ask("[bold magenta]Proceed with rename?[/]", default=False):
            console.print("[yellow]Cancelled.[/]")
            Prompt.ask("[dim]Press Enter to return[/]")
            return

        renamed = 0
        errors = 0
        for path, m in candidates:
            old_num = m.group("num")
            ext = m.group("ext")
            stem = path.name[: m.start()]
            new_name = f"{stem}{new_suffix}{ext}"
            new_path = path.with_name(new_name)

            if new_path == path:
                continue
            if new_path.exists():
                console.print(f"[yellow]Skip (exists): {new_path.name}[/]")
                errors += 1
                continue

            try:
                path.rename(new_path)
                self.log_rename(path, new_path)
                console.print(f"[spring_green1]✓[/] {path.name} → [hot_pink]{new_name}[/]")
                renamed += 1
            except Exception as e:
                console.print(f"[red]Error renaming {path.name}: {e}[/]")
                errors += 1

        console.print(f"\n[bold spring_green1]Done. Renamed: {renamed} | Skipped/Errors: {errors}[/]")
        self.known_files.clear()
        Prompt.ask("[dim]Press Enter to return to monitor[/]")

    def run(self):
        console.clear()
        console.print(Panel.fit(
            f"[bold magenta]{APP_NAME}[/]\n[deep_pink1]v{VERSION} - Pinky Purple Edition[/]\n"
            f"Watching: [hot_pink]{self.watch_dir}[/]",
            border_style="magenta",
            title="Starting Monitor"
        ))

        if not self.watch_dir.exists():
            console.print(f"[bold yellow]Notice:[/] Monitored directory does not currently exist:\n{self.watch_dir}")
            if Confirm.ask("[magenta]Would you like to create it now?[/]", default=True):
                try:
                    self.watch_dir.mkdir(parents=True, exist_ok=True)
                    console.print(f"[bold spring_green1]✓ Created directory:[/] {self.watch_dir}")
                except Exception as e:
                    console.print(f"[bold red]ERROR:[/] Could not create directory: {e}")
                    return
            else:
                console.print("[yellow]Please specify a valid directory using --dir or press [D] in monitor.[/]")
                return

        if not PSUTIL_AVAILABLE:
            console.print("[yellow]Note: psutil not found. Process monitoring will be limited. Install with: pip install psutil[/]")

        console.print("[bold spring_green1]Scanning directory...[/]")
        self.scan_directory()
        console.print(f"[bold spring_green1]Found {len(self.images)} images and {len(self.videos)} videos.[/]")
        console.print(f"[orchid]Log file: {LOG_FILE.absolute()}[/]")
        time.sleep(1.2)

        try:
            while True:
                self.scan_directory()
                procs = self.get_running_batch_processes()

                console.clear()
                console.print(self.build_ticker())
                console.print(self.build_summary_table())
                console.print(self.build_disk_panel())
                console.print(self.build_process_panel(procs))
                console.print(
                    "\n[bold magenta]Actions:[/]\n"
                    "  [hot_pink][I][/] View last 10 Images (XnView MP)\n"
                    "  [medium_purple][V][/] View last 10 Videos (VLC)\n"
                    "  [bold orchid][RI][/] Rename Images (FLUX / Other)\n"
                    "  [bold medium_purple][RV][/] Rename Videos (LTX / Other)\n"
                    "  [bold yellow][D][/] Change Monitored Directory\n"
                    "  [yellow][Q][/] Quit\n"
                )

                start = time.time()
                action = None
                while time.time() - start < 10:
                    if sys.stdin in select.select([sys.stdin], [], [], 0.5)[0]:
                        key = sys.stdin.read(1).lower()
                        if key == "i":
                            action = "images"
                            break
                        elif key == "v":
                            action = "videos"
                            break
                        elif key == "d":
                            action = "change_dir"
                            break
                        elif key == "q":
                            action = "quit"
                            break
                        elif key == "r":
                            if sys.stdin in select.select([sys.stdin], [], [], 0.8)[0]:
                                second = sys.stdin.read(1).lower()
                                if second == "i":
                                    action = "rename_images"
                                    break
                                elif second == "v":
                                    action = "rename_videos"
                                    break
                    time.sleep(0.1)

                if action == "images":
                    console.clear()
                    self.show_list(self.images, "Image")
                    Prompt.ask("[dim]Press Enter to return to monitor[/]")
                elif action == "videos":
                    console.clear()
                    self.show_list(self.videos, "Video")
                    Prompt.ask("[dim]Press Enter to return to monitor[/]")
                elif action == "change_dir":
                    console.clear()
                    console.print(Panel.fit("[bold magenta]Change Monitored Directory[/]", border_style="magenta"))
                    console.print(f"Current directory: [hot_pink]{self.watch_dir}[/]\n")
                    try:
                        new_path_str = Prompt.ask("[bold magenta]Enter new directory path to monitor[/]", default=str(self.watch_dir))
                        if new_path_str and new_path_str.strip() != str(self.watch_dir):
                            self.change_watch_dir(new_path_str.strip())
                    except Exception as e:
                        console.print(f"[red]Error: {e}[/]")
                        time.sleep(1)
                elif action == "rename_images":
                    console.clear()
                    console.print("[bold magenta]Rename Images[/]\n")
                    console.print("  [1] FLUX only")
                    console.print("  [2] Other (non-FLUX)")
                    console.print("  [3] All images")
                    console.print("  [0] Cancel")
                    try:
                        choice = IntPrompt.ask("[bold magenta]Select[/]", default=0)
                        if choice == 1:
                            self.batch_rename("image", "FLUX")
                        elif choice == 2:
                            self.batch_rename("image", "Other")
                        elif choice == 3:
                            self.batch_rename("image", "All")
                    except Exception:
                        pass
                elif action == "rename_videos":
                    console.clear()
                    console.print("[bold magenta]Rename Videos[/]\n")
                    console.print("  [1] LTX only")
                    console.print("  [2] Other (non-LTX)")
                    console.print("  [3] All videos")
                    console.print("  [0] Cancel")
                    try:
                        choice = IntPrompt.ask("[bold magenta]Select[/]", default=0)
                        if choice == 1:
                            self.batch_rename("video", "LTX")
                        elif choice == 2:
                            self.batch_rename("video", "Other")
                        elif choice == 3:
                            self.batch_rename("video", "All")
                    except Exception:
                        pass
                elif action == "quit":
                    break

        except KeyboardInterrupt:
            pass

        console.print("\n[bold magenta]Monitor stopped.[/]")
        console.print(f"[orchid]Full log available at: {LOG_FILE.absolute()}[/]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MP Video Image Directory Output Monitor (FLUX / LTX / WAN2GP)")
    parser.add_argument("dir", nargs="?", default=None, help="Directory to monitor (optional)")
    parser.add_argument("--dir", "--output-dir", "-d", dest="output_dir", default=None, help="Directory to monitor")
    args = parser.parse_args()

    target_dir = args.output_dir or args.dir
    monitor = Monitor(target_dir)
    monitor.run()
