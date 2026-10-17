#!/usr/bin/env python3
"""
music_folders_manager.py - DJ Tracks Database & SMB Music Folders Suite
Part of MP_Mix_Manager_v0.3 (Dreamworlds Productions)

Manages remote SMB Music Folders (/MUSIC001, /MUSIC002) at 192.168.1.138:
  - Supports automatic FUSE mounting via rclone CIFS/SMB interop
  - Scrapes and pre-generates playlists (.m3u8 and .json cache) in advance
  - Provides instant loading for MP Audio Player in MUSIC Mode (DJ Tracks Database)
  - Completely separate from MIX_ARCHIVE folders
"""

from __future__ import annotations
import os
import sys
import re
import time
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# ANSI TrueColor Palette
BOLD, DIM, ITALIC, NC = "\033[1m", "\033[2m", "\033[3m", "\033[0m"
COLOR_HOT_PURPLE = "\033[38;2;166;77;255m"
COLOR_INDIGO_BLUE = "\033[38;2;102;102;255m"
COLOR_LILAC = "\033[38;2;153;153;255m"
COLOR_TRAFFIC_GREEN = "\033[38;2;0;255;0m"
COLOR_TRAFFIC_AMBER = "\033[38;2;255;153;51m"
COLOR_TRAFFIC_RED = "\033[38;2;255;0;0m"
COLOR_NEON_PINK = "\033[38;2;247;37;133m"
COLOR_ELECTRIC_CYAN = "\033[38;2;0;229;255m"
WHITE = "\033[1;37m"

RED, GREEN, YELLOW = COLOR_TRAFFIC_RED, COLOR_TRAFFIC_GREEN, COLOR_TRAFFIC_AMBER
MAGENTA, CYAN = COLOR_HOT_PURPLE, COLOR_LILAC

AUDIO_EXTENSIONS = ('.flac', '.wav', '.mp3', '.ogg', '.m4a', '.aac', '.aiff', '.wma')

def get_base_dir() -> Path:
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "scripts" else p.parent

def parse_env_file(path: Path) -> Dict[str, str]:
    data = {}
    if not path.is_file():
        return data
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return data

def load_music_config() -> Dict[str, Any]:
    base_dir = get_base_dir()
    cfg_files = [
        base_dir / "config.env",
        Path.home() / ".config" / "mix-manager" / "config.env"
    ]
    merged = {}
    for cf in cfg_files:
        merged.update(parse_env_file(cf))

    host = os.environ.get("MUSIC_SMB_HOST") or merged.get("MUSIC_SMB_HOST", "192.168.1.138")
    user = os.environ.get("MUSIC_SMB_USER") or merged.get("MUSIC_SMB_USER", "mplanetarian")
    password = os.environ.get("MUSIC_SMB_PASSWORD") or merged.get("MUSIC_SMB_PASSWORD", "Wizard04")
    shares_raw = os.environ.get("MUSIC_SMB_SHARES") or merged.get("MUSIC_SMB_SHARES", "MUSIC001,MUSIC002")
    mount_root = os.environ.get("MUSIC_SMB_MOUNT_ROOT") or merged.get("MUSIC_SMB_MOUNT_ROOT", "/var/home/mplanetarian/MUSIC_SMB")

    shares = [s.strip().strip('/') for s in re.split(r'[,;:]', shares_raw) if s.strip()]
    if not shares:
        shares = ["MUSIC001", "MUSIC002"]

    playlists_dir = base_dir / "PLAYLISTS_GENERATED"
    playlists_dir.mkdir(parents=True, exist_ok=True)

    # Rclone obscured password
    rclone_pass = "Bl5Ejf6SBQivAUu_JvImDn__AKLASZcq"
    if password != "Wizard04":
        try:
            res = subprocess.run(["rclone", "obscure", password], capture_output=True, text=True, check=True)
            rclone_pass = res.stdout.strip()
        except Exception:
            pass

    return {
        "host": host,
        "user": user,
        "password": password,
        "rclone_pass": rclone_pass,
        "shares": shares,
        "mount_root": Path(mount_root),
        "playlists_dir": playlists_dir,
        "base_dir": base_dir
    }

def get_mount_path_for_share(share: str, config: Dict[str, Any]) -> Path:
    return config["mount_root"] / share

def is_share_mounted(share: str, config: Dict[str, Any]) -> bool:
    target_path = str(get_mount_path_for_share(share, config).resolve())
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == target_path:
                    return True
    except Exception:
        pass
    p = Path(target_path)
    try:
        return p.is_dir() and any(p.iterdir())
    except Exception:
        return False

def mount_smb_share(share: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    mount_dir = get_mount_path_for_share(share, config)
    mount_dir.mkdir(parents=True, exist_ok=True)

    if is_share_mounted(share, config):
        return True, f"Share {share} is already mounted at {mount_dir}"

    rclone_remote = f':smb,host="{config["host"]}",user="{config["user"]}",pass="{config["rclone_pass"]}":{share}/'
    cmd = [
        "nohup", "rclone", "mount",
        rclone_remote,
        str(mount_dir),
        "--read-only",
        "--dir-cache-time", "24h",
        "--vfs-cache-mode", "full",
        "--vfs-cache-max-size", "15G",
        "--vfs-cache-max-age", "24h",
        "--vfs-read-chunk-size", "4M",
        "--vfs-read-chunk-size-limit", "64M",
        "--buffer-size", "16M",
        "--no-modtime",
        "--attr-timeout", "1h"
    ]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as exc:
        return False, f"Failed to execute rclone mount for {share}: {exc}"

    # Wait up to 3.5 seconds for mount to appear in /proc/mounts
    for _ in range(35):
        time.sleep(0.1)
        if is_share_mounted(share, config):
            return True, f"Successfully mounted {share} to {mount_dir}"

    return False, f"Timed out waiting for {share} to mount at {mount_dir}"

def unmount_smb_share(share: str, config: Dict[str, Any]) -> Tuple[bool, str]:
    mount_dir = get_mount_path_for_share(share, config)
    if not is_share_mounted(share, config):
        return True, f"{share} is not mounted."
    try:
        res = subprocess.run(["fusermount3", "-u", str(mount_dir)], capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Unmounted {share}"
        res = subprocess.run(["fusermount", "-u", str(mount_dir)], capture_output=True, text=True)
        return (res.returncode == 0), (f"Unmounted {share}" if res.returncode == 0 else res.stderr.strip())
    except Exception as exc:
        return False, f"Unmount failed for {share}: {exc}"

def ensure_all_shares_mounted(config: Optional[Dict[str, Any]] = None) -> List[Tuple[str, bool, str]]:
    if config is None:
        config = load_music_config()
    results = []
    for s in config["shares"]:
        if is_share_mounted(s, config):
            results.append((s, True, "Already mounted"))
        else:
            ok, msg = mount_smb_share(s, config)
            results.append((s, ok, msg))
    return results

def get_playlist_m3u_path(target: str, config: Dict[str, Any]) -> Path:
    if target.upper() == "ALL":
        return config["playlists_dir"] / "DJ_Tracks_ALL_MUSIC_FOLDERS.m3u8"
    return config["playlists_dir"] / f"DJ_Tracks_{target.upper()}.m3u8"

def get_playlist_json_path(target: str, config: Dict[str, Any]) -> Path:
    if target.upper() == "ALL":
        return config["playlists_dir"] / "DJ_Tracks_ALL_MUSIC_FOLDERS.json"
    return config["playlists_dir"] / f"DJ_Tracks_{target.upper()}.json"

def check_playlist_status(target: str, config: Dict[str, Any]) -> Dict[str, Any]:
    m3u_path = get_playlist_m3u_path(target, config)
    json_path = get_playlist_json_path(target, config)
    exists = m3u_path.is_file() and json_path.is_file()
    track_count = 0
    mtime = 0.0
    if exists:
        try:
            mtime = m3u_path.stat().st_mtime
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    track_count = len(data)
        except Exception:
            pass
    return {
        "exists": exists,
        "track_count": track_count,
        "m3u_path": m3u_path,
        "json_path": json_path,
        "mtime": mtime,
        "mtime_fmt": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)) if mtime > 0 else "Never"
    }

def scrape_share_audio_tracks(share: str, config: Dict[str, Any], progress_cb=None) -> List[Dict[str, Any]]:
    """Scrapes all valid audio files from an SMB share via rclone lsf."""
    if progress_cb:
        progress_cb(f"Connecting to SMB share smb://{config['host']}/{share}...")

    rclone_remote = f':smb,host="{config["host"]}",user="{config["user"]}",pass="{config["rclone_pass"]}":{share}/'
    cmd = [
        "rclone", "lsf",
        rclone_remote,
        "--recursive",
        "--files-only"
    ]

    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    except Exception as exc:
        if progress_cb:
            progress_cb(f"Error launching rclone: {exc}")
        return []

    tracks = []
    mount_dir = get_mount_path_for_share(share, config)
    count = 0

    if p.stdout:
        for line in p.stdout:
            line = line.strip()
            if not line:
                continue
            base = os.path.basename(line)
            # Filter out AppleDouble, dot-files, recycle bins
            if base.startswith("._") or "/." in ("/" + line) or "$RECYCLE.BIN" in line:
                continue
            ext = os.path.splitext(base)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                count += 1
                fp = str(mount_dir / line)
                title_guess = os.path.splitext(base)[0]
                tracks.append({
                    "name": base,
                    "title": title_guess,
                    "path": fp,
                    "folder": share,
                    "subpath": line,
                    "ext": ext[1:].upper(),
                    "size_mb": 0.0,
                    "duration_fmt": "00:00",
                    "mtime": time.time()
                })
                if progress_cb and count % 2000 == 0:
                    progress_cb(f"Indexed {count:,} audio tracks in /{share}...")

    p.wait()
    if progress_cb:
        progress_cb(f"Completed scan of /{share}: {len(tracks):,} audio tracks found.")
    return tracks

def save_playlist_files(tracks: List[Dict[str, Any]], target: str, config: Dict[str, Any]) -> Tuple[Path, Path]:
    """Saves both .m3u8 playlist and structured .json cache for lightning-fast loading."""
    m3u_path = get_playlist_m3u_path(target, config)
    json_path = get_playlist_json_path(target, config)

    # 1. Write M3U8
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#PLAYLIST:MP DJ Tracks Database - {target.upper()}\n")
        for t in tracks:
            d_sec = int(t.get("duration_sec", -1)) if t.get("duration_sec") else -1
            f.write(f"#EXTINF:{d_sec},{t.get('title', t['name'])}\n")
            f.write(f"{t['path']}\n")

    # 2. Write JSON Cache
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=2, ensure_ascii=False)

    return m3u_path, json_path

def generate_advance_playlists(target: str = "ALL", config: Optional[Dict[str, Any]] = None,
                               interactive: bool = True) -> Dict[str, Any]:
    """Generates playlists for MUSIC folders in advance and saves them."""
    if config is None:
        config = load_music_config()

    shares_to_process = config["shares"] if target.upper() == "ALL" else [target.upper()]
    results = {}
    total_all_tracks = []

    print(f"\n{BOLD}{COLOR_HOT_PURPLE}======================================================================{NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}    GENERATING PLAYLISTS FOR MUSIC FOLDERS IN ADVANCE                 {NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}======================================================================{NC}")
    print(f"  {BOLD}SMB Host:{NC} {CYAN}{config['host']}{NC}  │  {BOLD}Mount Root:{NC} {CYAN}{config['mount_root']}{NC}")
    print(f"  {BOLD}Target Folders:{NC} {WHITE}{', '.join(shares_to_process)}{NC}\n")
    print(f"  {DIM}Connecting to SMB shares and pre-caching audio files to eliminate player loading delays...{NC}\n")

    t_start = time.time()

    for s in shares_to_process:
        print(f"  {BOLD}{CYAN}▶ Scraping audio tracks from /{s}...{NC}")
        def log_cb(msg):
            print(f"    {DIM}{msg}{NC}")
        s_tracks = scrape_share_audio_tracks(s, config, progress_cb=log_cb)
        total_all_tracks.extend(s_tracks)

        m3u_p, json_p = save_playlist_files(s_tracks, s, config)
        results[s] = {
            "count": len(s_tracks),
            "m3u": str(m3u_p),
            "json": str(json_p)
        }
        print(f"  {BOLD}{GREEN}✓ Saved /{s} Playlist:{NC} {len(s_tracks):,} tracks ➔ {m3u_p.name}\n")

    # If target is ALL, also save combined playlist
    if target.upper() == "ALL" or len(shares_to_process) > 1:
        m3u_all, json_all = save_playlist_files(total_all_tracks, "ALL", config)
        results["ALL"] = {
            "count": len(total_all_tracks),
            "m3u": str(m3u_all),
            "json": str(json_all)
        }
        print(f"  {BOLD}{GREEN}✓ Saved Combined ALL Music Folders Playlist:{NC} {len(total_all_tracks):,} tracks ➔ {m3u_all.name}")

    elapsed = time.time() - t_start
    print(f"\n{BOLD}{COLOR_TRAFFIC_GREEN}✔ Playlist Generation Complete!{NC}")
    print(f"  Total Indexed Tracks : {BOLD}{WHITE}{len(total_all_tracks):,}{NC}")
    print(f"  Time Elapsed         : {BOLD}{CYAN}{elapsed:.2f}s{NC}")
    print(f"  Storage Directory    : {DIM}{config['playlists_dir']}{NC}\n")

    return results

def launch_mp_audio_player_music_mode(target: str = "ALL", config: Optional[Dict[str, Any]] = None):
    """Launches MP Audio Player in MUSIC Mode with the generated playlist."""
    if config is None:
        config = load_music_config()

    st = check_playlist_status(target, config)
    if not st["exists"] or st["track_count"] == 0:
        print(f"\n{BOLD}{YELLOW}Notice: Playlist for '{target}' has not been generated yet!{NC}")
        print(f"{DIM}Generating playlist in advance to guarantee zero-latency loading...{NC}\n")
        generate_advance_playlists(target, config=config, interactive=True)
        st = check_playlist_status(target, config)

    # Ensure SMB mount is active
    print(f"{DIM}Verifying SMB shares mount status...{NC}")
    ensure_all_shares_mounted(config)

    playlist_path = st["json_path"] if st["json_path"].is_file() else st["m3u_path"]
    player_py = config["base_dir"] / "MP_Audio_Player.py"
    if not player_py.is_file():
        player_py = config["base_dir"] / "scripts" / "MP_Audio_Player.py"

    cmd = [
        sys.executable,
        str(player_py),
        "--interactive",
        "--music-mode",
        "--music-folder", target.upper(),
        "--playlist", str(playlist_path)
    ]

    print(f"{BOLD}{GREEN}Launching MP Audio Player in MUSIC Mode ({st['track_count']:,} tracks)...{NC}")
    time.sleep(0.5)
    subprocess.run(cmd)

def run_music_folders_menu():
    """Interactive TUI menu for managing MUSIC folders."""
    config = load_music_config()

    while True:
        os.system("clear")
        all_st = check_playlist_status("ALL", config)
        m1_st = check_playlist_status("MUSIC001", config)
        m2_st = check_playlist_status("MUSIC002", config)

        m1_mounted = is_share_mounted("MUSIC001", config)
        m2_mounted = is_share_mounted("MUSIC002", config)

        m1_m_badge = f"{GREEN}[MOUNTED]{NC}" if m1_mounted else f"{YELLOW}[NOT MOUNTED]{NC}"
        m2_m_badge = f"{GREEN}[MOUNTED]{NC}" if m2_mounted else f"{YELLOW}[NOT MOUNTED]{NC}"

        all_pl_badge = f"{GREEN}{all_st['track_count']:,} Tracks (Ready){NC}" if all_st["exists"] else f"{RED}Not Generated{NC}"
        m1_pl_badge = f"{GREEN}{m1_st['track_count']:,} Tracks (Ready){NC}" if m1_st["exists"] else f"{RED}Not Generated{NC}"
        m2_pl_badge = f"{GREEN}{m2_st['track_count']:,} Tracks (Ready){NC}" if m2_st["exists"] else f"{RED}Not Generated{NC}"

        print(f"{BOLD}{COLOR_HOT_PURPLE}======================================================================{NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE}  Play Tracks from MUSIC Folders using MP Audio Player                {NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE}                   (Music Library • SMB Shares Suite)                 {NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE}======================================================================{NC}")
        print(f"  {BOLD}SMB Host Network  :{NC} {CYAN}smb://{config['host']}{NC}  {DIM}(Credentials: {config['user']}){NC}")
        print(f"  {BOLD}Configured Shares :{NC} {WHITE}/MUSIC001{NC} {m1_m_badge}  •  {WHITE}/MUSIC002{NC} {m2_m_badge}")
        print(f"  {BOLD}Mount Point Root  :{NC} {DIM}{config['mount_root']}{NC}")
        print(f"  --------------------------------------------------------------------")
        print(f"  {BOLD}Pre-Generated Playlists Status:{NC}")
        print(f"    • ALL Music Folders : {all_pl_badge}")
        print(f"    • /MUSIC001 Share   : {m1_pl_badge}")
        print(f"    • /MUSIC002 Share   : {m2_pl_badge}")
        print(f"  --------------------------------------------------------------------\n")

        print(f"{BOLD}Select an Option:{NC}")
        print(f"  {BOLD}{CYAN}1){NC} Play ALL Music Folders in MP Audio Player ({BOLD}{COLOR_ELECTRIC_CYAN}MUSIC Mode{NC})")
        print(f"  {BOLD}{CYAN}2){NC} Play Specific Music Folder: {WHITE}/MUSIC001{NC} in MP Audio Player")
        print(f"  {BOLD}{CYAN}3){NC} Play Specific Music Folder: {WHITE}/MUSIC002{NC} in MP Audio Player")
        print(f"  {BOLD}{CYAN}4){NC} Generate / Refresh Playlists in Advance (Pre-cache for Instant Loading)")
        print(f"  {BOLD}{CYAN}5){NC} Mount / Re-Mount All SMB Music Shares (rclone CIFS/SMB FUSE)")
        print(f"  {BOLD}{CYAN}6){NC} Unmount All SMB Music Shares")
        print(f"  {BOLD}{CYAN}7){NC} View Track Audio Inspector & Player Shortcuts Guide")
        print(f"  {BOLD}{CYAN}0){NC} Return to Main Menu\n")

        raw_choice = input("Enter choice [0-7]: ")
        choice = raw_choice.strip()

        if choice in ("m", "M"):
            base_dir = get_base_dir()
            player_py = base_dir / "MP_Audio_Player.py"
            if not player_py.is_file():
                player_py = base_dir / "scripts" / "MP_Audio_Player.py"
            if player_py.is_file():
                subprocess.Popen([sys.executable, str(player_py), "--new-window"])
            continue

        if raw_choice == " " or choice.lower() == "space":
            base_dir = get_base_dir()
            player_py = base_dir / "MP_Audio_Player.py"
            if not player_py.is_file():
                player_py = base_dir / "scripts" / "MP_Audio_Player.py"
            if player_py.is_file():
                subprocess.Popen([sys.executable, str(player_py), "--toggle", "--only-if-running"])
            continue

        if choice in ("1", "all", "ALL"):
            if not all_st["exists"]:
                print(f"\n{BOLD}{YELLOW}Playlist for ALL Music Folders must be generated in advance first!{NC}")
                generate_advance_playlists("ALL", config=config, interactive=True)
                input(f"\n{BOLD}Press Enter to launch MP Audio Player...{NC}")
            launch_mp_audio_player_music_mode("ALL", config)

        elif choice in ("2", "m1", "MUSIC001", "music001"):
            if not m1_st["exists"]:
                print(f"\n{BOLD}{YELLOW}Playlist for /MUSIC001 must be generated in advance first!{NC}")
                generate_advance_playlists("MUSIC001", config=config, interactive=True)
                input(f"\n{BOLD}Press Enter to launch MP Audio Player...{NC}")
            launch_mp_audio_player_music_mode("MUSIC001", config)

        elif choice in ("3", "m2", "MUSIC002", "music002"):
            if not m2_st["exists"]:
                print(f"\n{BOLD}{YELLOW}Playlist for /MUSIC002 must be generated in advance first!{NC}")
                generate_advance_playlists("MUSIC002", config=config, interactive=True)
                input(f"\n{BOLD}Press Enter to launch MP Audio Player...{NC}")
            launch_mp_audio_player_music_mode("MUSIC002", config)

        elif choice == "4":
            print(f"\n{BOLD}Select target for playlist generation:{NC}")
            print(f"  1) ALL Music Folders (MUSIC001 + MUSIC002)")
            print(f"  2) /MUSIC001 Only")
            print(f"  3) /MUSIC002 Only")
            print(f"  0) Cancel")
            g_opt = input("Enter choice [0-3]: ").strip()
            if g_opt == "1":
                generate_advance_playlists("ALL", config=config, interactive=True)
            elif g_opt == "2":
                generate_advance_playlists("MUSIC001", config=config, interactive=True)
            elif g_opt == "3":
                generate_advance_playlists("MUSIC002", config=config, interactive=True)
            input(f"\n{BOLD}Press Enter to continue...{NC}")

        elif choice == "5":
            print(f"\n{BOLD}Mounting SMB Music Shares...{NC}")
            res = ensure_all_shares_mounted(config)
            for s, ok, msg in res:
                print(f"  /{s}: {'✔ ' + GREEN if ok else '✖ ' + RED}{msg}{NC}")
            input(f"\n{BOLD}Press Enter to continue...{NC}")

        elif choice == "6":
            print(f"\n{BOLD}Unmounting SMB Music Shares...{NC}")
            for s in config["shares"]:
                ok, msg = unmount_smb_share(s, config)
                print(f"  /{s}: {'✔ ' + GREEN if ok else '✖ ' + RED}{msg}{NC}")
            input(f"\n{BOLD}Press Enter to continue...{NC}")

        elif choice == "7":
            print(f"\n{BOLD}{COLOR_HOT_PURPLE}======================================================================{NC}")
            print(f"{BOLD}{COLOR_HOT_PURPLE}     TRACK AUDIO INSPECTOR & PLAYER SHORTCUTS GUIDE (MUSIC MODE)      {NC}")
            print(f"{BOLD}{COLOR_HOT_PURPLE}======================================================================{NC}\n")
            print(f"  {BOLD}{CYAN}1. Track Audio Inspector HUD (Key I){NC}")
            print(f"     • Real-time modal HUD displaying full audio specs, format, sample rate,")
            print(f"       channels, time position, hardware audio output, and SMB network path.")
            print(f"     • Press [I], [Esc], or [Enter] to toggle or close overlay.")
            print(f"\n  {BOLD}{CYAN}2. Instant Search & Filtering (Key /){NC}")
            print(f"     • Press [/] anywhere to filter 31,000+ tracks instantly by typing.")
            print(f"     • Use Up/Down arrows to navigate search matches and Enter to play.")
            print(f"\n  {BOLD}{CYAN}3. Playback Controls & Navigation{NC}")
            print(f"     • [Space] Play / Pause toggle.")
            print(f"     • [n] / [p] Next / Previous track in playlist.")
            print(f"     • [+/-] Fine pitch adjust (±1%), [0] Pitch reset.")
            print(f"     • [v] / [V] Volume adjust (±5%), [m] Mute toggle.")
            print(f"\n  {BOLD}{CYAN}4. Equalizer Visualizer & Themes{NC}")
            print(f"     • [e] Cycle through 10+ animated Equalizer visualizer styles.")
            print(f"     • [c] Cycle through 12+ vibrant color themes.")
            print(f"     • [a] Route audio to connected Bluetooth headphones/speakers.")
            input(f"\n{BOLD}Press Enter to return to menu...{NC}")

        elif choice in ("0", "q", "Q", "exit", "ESC"):
            break

def main():
    parser = argparse.ArgumentParser(description="SMB Music Folders & MP Audio Player Suite")
    parser.add_argument("--menu", action="store_true", help="Launch interactive Music Folders menu")
    parser.add_argument("--mount", action="store_true", help="Mount all SMB Music shares")
    parser.add_argument("--unmount", action="store_true", help="Unmount all SMB Music shares")
    parser.add_argument("--status", action="store_true", help="Check SMB shares & playlists status")
    parser.add_argument("--generate", nargs="?", const="ALL", help="Generate playlists in advance (ALL, MUSIC001, MUSIC002)")
    parser.add_argument("--play", nargs="?", const="ALL", help="Launch MP Audio Player in MUSIC mode (ALL, MUSIC001, MUSIC002)")
    args = parser.parse_args()

    config = load_music_config()

    if args.mount:
        res = ensure_all_shares_mounted(config)
        for s, ok, msg in res:
            print(f"{s}: {'OK' if ok else 'FAIL'} - {msg}")
        sys.exit(0)

    if args.unmount:
        for s in config["shares"]:
            ok, msg = unmount_smb_share(s, config)
            print(f"{s}: {'OK' if ok else 'FAIL'} - {msg}")
        sys.exit(0)

    if args.status:
        print(json.dumps({
            "host": config["host"],
            "shares": config["shares"],
            "mount_root": str(config["mount_root"]),
            "mounted": {s: is_share_mounted(s, config) for s in config["shares"]},
            "playlists": {s: check_playlist_status(s, config) for s in ["ALL"] + config["shares"]}
        }, indent=2, default=str))
        sys.exit(0)

    if args.generate:
        generate_advance_playlists(args.generate, config=config, interactive=True)
        sys.exit(0)

    if args.play:
        launch_mp_audio_player_music_mode(args.play, config=config)
        sys.exit(0)

    # Default to menu
    run_music_folders_menu()

if __name__ == "__main__":
    main()
