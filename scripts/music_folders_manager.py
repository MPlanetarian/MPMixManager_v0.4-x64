#!/usr/bin/env python3
"""
music_folders_manager.py - DJ Tracks Database & Music Folders Suite
Part of MP_Mix_Manager_v0.3 (Dreamworlds Productions)

Manages user-configured Music Folders (local drive paths and SMB shares only):
  - Folders are configured per machine in ~/.config/mix-manager/music_folders.json
  - Add / remove folders from the interactive menu or the CLI (--add / --remove / --list)
  - SMB shares are accessed directly via UNC paths on Windows (\\\\host\\share), and via
    existing gvfs / Finder mounts or an on-demand rclone FUSE mount on Linux / macOS
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
import threading
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

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
SKIP_DIR_NAMES = {"$recycle.bin", "system volume information", "@eadir", "#recycle", "#snapshot", ".trashes", ".spotlight-v100", ".fseventsd"}

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
FOLDERS_FILE = CONFIG_DIR / "music_folders.json"
ALL_TARGET = "ALL"
ALL_PLAYLIST_STEM = "DJ_Tracks_ALL_MUSIC_FOLDERS"
LINE = "  --------------------------------------------------------------------"
BANNER = "======================================================================"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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
    """Loads global settings (credentials / mount root). No hard-coded hosts or shares."""
    base_dir = get_base_dir()
    merged: Dict[str, str] = {}
    for cf in (base_dir / "config.env", CONFIG_DIR / "config.env"):
        merged.update(parse_env_file(cf))

    def _get(key: str, default: str = "") -> str:
        return os.environ.get(key) or merged.get(key, default)

    playlists_dir = base_dir / "PLAYLISTS_GENERATED"
    playlists_dir.mkdir(parents=True, exist_ok=True)
    return {
        "smb_user": _get("MUSIC_SMB_USER"),
        "smb_password": _get("MUSIC_SMB_PASSWORD"),
        "mount_root": Path(os.path.expanduser(_get("MUSIC_SMB_MOUNT_ROOT", str(Path.home() / "MUSIC_SMB")))),
        "legacy_host": _get("MUSIC_SMB_HOST"),
        "legacy_shares": _get("MUSIC_SMB_SHARES"),
        "playlists_dir": playlists_dir,
        "base_dir": base_dir,
    }

# ---------------------------------------------------------------------------
# Folder path parsing
# ---------------------------------------------------------------------------

_SMB_RE = re.compile(r'^(?:smb:)?(?:\\\\|//)([^\\/]+)[\\/]+([^\\/]+)(?:[\\/]+(.*))?$', re.I)
_ONLY_LOCAL_OR_SMB = (
    "Only a local drive path or an SMB share is allowed "
    "(for example D:\\Music, \\\\192.168.1.138\\music001, or smb://host/share)."
)

def _normalize_extended_path(s: str) -> str:
    """Turns \\\\?\\UNC\\server\\share and \\\\?\\C:\\... into ordinary paths."""
    t = s.replace("/", "\\")
    upper = t.upper()
    if upper.startswith("\\\\?\\UNC\\"):
        return "\\\\" + t[8:]
    if upper.startswith("\\\\?\\"):
        return t[4:]
    return s

def _looks_like_windows_local(s: str) -> bool:
    if re.match(r'^[a-zA-Z]:[\\/]', s):
        return True
    if s == "~" or s.startswith("~/") or s.startswith("~\\"):
        return True
    if re.match(r'^/(?:cygdrive/)?[a-zA-Z](?:/|$)', s):
        return True
    return bool(re.match(r'^%[A-Za-z0-9_]+%([\\/]|$)', s))

def _windows_remote_unc(path: str) -> Optional[str]:
    """If a Windows drive letter is mapped to an SMB share, return that UNC path."""
    if not IS_WINDOWS:
        return None
    drive, rest = os.path.splitdrive(path)
    if len(drive) != 2 or not drive[0].isalpha():
        return None
    try:
        import ctypes
        from ctypes import wintypes
        if int(ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")) != 4:
            return None
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        rc = int(ctypes.windll.mpr.WNetGetConnectionW(drive, buf, ctypes.byref(size)))
    except Exception:
        return None
    remote = buf.value if rc == 0 else ""
    if not remote.startswith("\\\\"):
        return None
    tail = rest.replace("/", "\\").lstrip("\\")
    return remote.rstrip("\\") + (("\\" + tail) if tail else "")

def parse_folder_path(raw: str) -> Dict[str, Any]:
    """Parses a local drive path or SMB share. Raises ValueError for anything else."""
    s = (raw or "").strip().strip('"').strip("'").strip()
    if not s:
        raise ValueError("No path entered.")
    s = _normalize_extended_path(s)
    m = _SMB_RE.match(s)
    if m:
        host, share, sub = m.group(1), m.group(2), (m.group(3) or "")
        user = ""
        if "@" in host:
            user, host = host.rsplit("@", 1)
            user = user.split(":", 1)[0]
        sub = sub.replace("\\", "/").strip("/")
        if not host or not share or host in ("?", "."):
            raise ValueError("SMB paths must include both a host and a share, e.g. \\\\192.168.1.138\\music001")
        return {"type": "smb", "host": host, "share": share, "subpath": sub, "user": user}
    if re.match(r'^[a-z][a-z0-9+.\-]*://', s, re.I):
        raise ValueError(_ONLY_LOCAL_OR_SMB)
    if s.startswith(("\\\\", "//")):
        raise ValueError("SMB paths must include both a host and a share, e.g. \\\\192.168.1.138\\music001")
    if IS_WINDOWS:
        if not _looks_like_windows_local(s):
            raise ValueError(_ONLY_LOCAL_OR_SMB)
    elif not (s.startswith("~") or s.startswith("/")):
        raise ValueError(_ONLY_LOCAL_OR_SMB)
    p = os.path.expandvars(os.path.expanduser(s))
    if IS_WINDOWS:
        # Accept Git Bash / MSYS / Cygwin style paths: /x/Music, /cygdrive/x/Music
        mm = re.match(r'^/(?:cygdrive/)?([a-zA-Z])(?:/(.*))?$', p)
        if mm:
            p = mm.group(1).upper() + ":\\" + (mm.group(2) or "").replace("/", "\\")
    p = os.path.normpath(os.path.abspath(p))
    mapped = _windows_remote_unc(p)
    if mapped:
        return parse_folder_path(mapped)
    if IS_WINDOWS:
        drive, _ = os.path.splitdrive(p)
        if not drive:
            raise ValueError("Enter a local drive path such as D:\\Music.")
    return {"type": "local", "path": p}

def unc_path(f: Dict[str, Any]) -> str:
    p = "\\\\" + f["host"] + "\\" + f["share"]
    if f.get("subpath"):
        p += "\\" + f["subpath"].replace("/", "\\")
    return p

def display_path(f: Dict[str, Any]) -> str:
    return unc_path(f) if f.get("type") == "smb" else f.get("path", "")

def folder_key(f: Dict[str, Any]) -> Tuple[str, ...]:
    if f.get("type") == "smb":
        return ("smb", f["host"].lower(), f["share"].lower(), f.get("subpath", "").lower().strip("/"))
    return ("local", os.path.normcase(os.path.normpath(f.get("path", ""))))

def make_folder_id(name: str, existing: List[Dict[str, Any]]) -> str:
    base = re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_') or "FOLDER"
    if base == ALL_TARGET or base.startswith("ALL_MUSIC_FOLDERS"):
        base += "_DIR"
    taken = {str(f.get("id", "")).upper() for f in existing}
    fid, n = base, 2
    while fid in taken:
        fid, n = f"{base}_{n}", n + 1
    return fid

def default_folder_name(f: Dict[str, Any]) -> str:
    if f["type"] == "smb":
        return f["subpath"].rsplit("/", 1)[-1] if f.get("subpath") else f["share"]
    return os.path.basename(f["path"].rstrip("\\/")) or f["path"]

# ---------------------------------------------------------------------------
# Folder list persistence
# ---------------------------------------------------------------------------

def save_folders(folders: List[Dict[str, Any]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FOLDERS_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "folders": folders}, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, FOLDERS_FILE)

def _migrate_legacy_folders(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Seeds the folder list from explicit legacy MUSIC_SMB_HOST / MUSIC_SMB_SHARES settings, if present."""
    host, shares_raw = config.get("legacy_host", ""), config.get("legacy_shares", "")
    if not host or not shares_raw:
        return []
    folders: List[Dict[str, Any]] = []
    for share in [s.strip().strip("/\\") for s in re.split(r'[,;]', shares_raw) if s.strip()]:
        f = {"type": "smb", "host": host, "share": share, "subpath": "", "user": ""}
        f["name"] = share
        f["id"] = make_folder_id(share, folders)
        f["path"] = display_path(f)
        folders.append(f)
    return folders

def load_folders(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if FOLDERS_FILE.is_file():
        try:
            with open(FOLDERS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            items = data.get("folders", []) if isinstance(data, dict) else data
            return [f for f in items if isinstance(f, dict) and f.get("id") and f.get("type") in ("smb", "local")]
        except Exception as exc:
            print(f"{RED}Warning: could not read {FOLDERS_FILE}: {exc}{NC}")
            return []
    folders = _migrate_legacy_folders(config or load_music_config())
    if folders:
        save_folders(folders)
    return folders

def find_folder(key: str, folders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    k = (key or "").strip()
    if not k:
        return None
    if k.isdigit() and 1 <= int(k) <= len(folders):
        return folders[int(k) - 1]
    for f in folders:
        if f["id"].upper() == k.upper() or f.get("name", "").lower() == k.lower():
            return f
    try:
        pk = folder_key(parse_folder_path(k))
        for f in folders:
            if folder_key(f) == pk:
                return f
    except ValueError:
        pass
    return None

def add_folder(raw_path: str, folders: List[Dict[str, Any]], name: str = "", user: str = "") -> Dict[str, Any]:
    f = parse_folder_path(raw_path)
    if user and f["type"] == "smb":
        f["user"] = user
    for existing in folders:
        if folder_key(existing) == folder_key(f):
            raise ValueError(f"That folder is already configured as [{existing['id']}] {existing.get('name', '')}.")
    f["name"] = (name or "").strip() or default_folder_name(f)
    f["id"] = make_folder_id(f["name"], folders)
    f["path"] = display_path(f)
    if f["type"] == "local" and os.path.isfile(f["path"]):
        raise ValueError(f"That path is a file, not a folder: {f['path']}")
    folders.append(f)
    save_folders(folders)
    return f

def remove_folder(f: Dict[str, Any], folders: List[Dict[str, Any]], config: Dict[str, Any]) -> None:
    if f["type"] == "smb" and not IS_WINDOWS:
        disconnect_folder(f, config)
    folders[:] = [x for x in folders if x["id"] != f["id"]]
    save_folders(folders)
    for p in get_playlist_paths(f["id"], config):
        try:
            p.unlink()
        except OSError:
            pass
    rebuild_all_playlist(folders, config)

# ---------------------------------------------------------------------------
# Access / connection (cross-platform)
# ---------------------------------------------------------------------------

def _run_with_timeout(fn, timeout: float, default=None):
    box: Dict[str, Any] = {}
    t = threading.Thread(target=lambda: box.__setitem__("v", fn()), daemon=True)
    t.start()
    t.join(timeout)
    return box.get("v", default) if not t.is_alive() else default

def _isdir_timeout(path: str, timeout: float = 6.0) -> Optional[bool]:
    """os.path.isdir that cannot hang the menu on an unreachable SMB host. None = timed out."""
    def _probe():
        try:
            return os.path.isdir(path)
        except Exception:
            return False
    return _run_with_timeout(_probe, timeout, None)

def smb_mount_dir(f: Dict[str, Any], config: Dict[str, Any]) -> Path:
    return config["mount_root"] / f["id"]

def _is_mountpoint(p: Path) -> bool:
    target = str(p)
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[1].replace("\\040", " ") == target:
                    return True
    except Exception:
        pass
    try:
        return os.path.ismount(target)
    except Exception:
        return False

def _posix_existing_smb_paths(f: Dict[str, Any]) -> List[str]:
    """Shares already mounted by the desktop (gvfs on Linux, Finder on macOS)."""
    sub = f.get("subpath", "")
    cands: List[str] = []
    if IS_MAC:
        cands.append(os.path.join("/Volumes", f["share"], sub))
    else:
        uid = os.getuid() if hasattr(os, "getuid") else 0
        for share in dict.fromkeys((f["share"], f["share"].lower())):
            cands.append(os.path.join(f"/run/user/{uid}/gvfs", f"smb-share:server={f['host'].lower()},share={share}", sub))
    return cands

def access_path(f: Dict[str, Any], config: Dict[str, Any], timeout: float = 6.0) -> Tuple[Optional[str], str]:
    """Returns (filesystem path usable for scanning/playback or None, status label)."""
    if f["type"] == "local":
        ok = _isdir_timeout(f["path"], timeout)
        return (f["path"], "ONLINE") if ok else (None, "TIMEOUT" if ok is None else "MISSING")
    if IS_WINDOWS:
        p = unc_path(f)
        ok = _isdir_timeout(p, timeout)
        return (p, "ONLINE") if ok else (None, "TIMEOUT" if ok is None else "OFFLINE")
    md = smb_mount_dir(f, config)
    if _is_mountpoint(md):
        p = os.path.join(str(md), f.get("subpath", ""))
        if _isdir_timeout(p, timeout):
            return p, "MOUNTED"
    for p in _posix_existing_smb_paths(f):
        if _isdir_timeout(p, timeout):
            return p, "MOUNTED"
    return None, "NOT MOUNTED"

def _smb_credentials(f: Dict[str, Any], config: Dict[str, Any]) -> Tuple[str, str]:
    return (f.get("user") or config.get("smb_user", "")), config.get("smb_password", "")

def _rclone_remote(f: Dict[str, Any], config: Dict[str, Any], with_subpath: bool = False) -> Optional[str]:
    if not shutil.which("rclone"):
        return None
    user, password = _smb_credentials(f, config)
    opts = [f'host="{f["host"]}"']
    if user:
        opts.append(f'user="{user}"')
    if password:
        try:
            res = subprocess.run(["rclone", "obscure", password], capture_output=True, text=True, check=True)
            opts.append(f'pass="{res.stdout.strip()}"')
        except Exception:
            pass
    path = f["share"] + "/" + (f.get("subpath", "") + "/" if with_subpath and f.get("subpath") else "")
    return f":smb,{','.join(opts)}:{path}"

def connect_folder(f: Dict[str, Any], config: Dict[str, Any], interactive: bool = True) -> Tuple[bool, str]:
    """Makes a folder accessible: verifies local paths, connects/mounts SMB shares."""
    p, label = access_path(f, config)
    if p:
        return True, f"{label} ({p})"
    if f["type"] == "local":
        return False, f"Local folder not found: {f['path']}"

    if IS_WINDOWS:
        share_unc = "\\\\" + f["host"] + "\\" + f["share"]
        user, password = _smb_credentials(f, config)
        cmd = ["net", "use", share_unc]
        if password and user:
            cmd += [password, f"/user:{user}"]
        elif user:
            cmd += ["*", f"/user:{user}"]
        if not interactive and not password:
            return False, f"{share_unc} is not reachable (connect from the menu to enter credentials)."
        if interactive:
            print(f"  {DIM}Connecting to {share_unc} (Windows may prompt for credentials)...{NC}", flush=True)
        try:
            res = subprocess.run(cmd, stdin=None if interactive else subprocess.DEVNULL)
        except Exception as exc:
            return False, f"net use failed: {exc}"
        p, label = access_path(f, config)
        return (True, f"Connected ({p})") if p else (False, f"Could not connect to {unc_path(f)} (net use exit {res.returncode}).")

    remote = _rclone_remote(f, config)
    if not remote:
        return False, "rclone is not installed. Install rclone or mount the share with your file manager (gvfs / Finder)."
    md = smb_mount_dir(f, config)
    md.mkdir(parents=True, exist_ok=True)
    cmd = ["rclone", "mount", remote, str(md), "--read-only",
           "--dir-cache-time", "24h", "--vfs-cache-mode", "full", "--vfs-cache-max-size", "15G",
           "--vfs-cache-max-age", "24h", "--vfs-read-chunk-size", "4M", "--vfs-read-chunk-size-limit", "64M",
           "--buffer-size", "16M", "--no-modtime", "--attr-timeout", "1h"]
    if shutil.which("nohup"):
        cmd.insert(0, "nohup")
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:
        return False, f"Failed to execute rclone mount: {exc}"
    for _ in range(50):
        time.sleep(0.1)
        if _is_mountpoint(md):
            return True, f"Mounted {display_path(f)} at {md}"
    return False, f"Timed out waiting for {display_path(f)} to mount at {md}"

def disconnect_folder(f: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
    if f["type"] != "smb":
        return True, "Local folder (nothing to disconnect)."
    if IS_WINDOWS:
        share_unc = "\\\\" + f["host"] + "\\" + f["share"]
        res = subprocess.run(["net", "use", share_unc, "/delete", "/y"], capture_output=True, text=True)
        return True, ("Disconnected" if res.returncode == 0 else "No active UNC session (mapped drive letters are left untouched)")
    md = smb_mount_dir(f, config)
    if not _is_mountpoint(md):
        return True, "Not mounted by MP Mix Manager."
    for cmd in (["fusermount3", "-u", str(md)], ["fusermount", "-u", str(md)], ["umount", str(md)]):
        if shutil.which(cmd[0]):
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return True, f"Unmounted {md}"
    return False, f"Could not unmount {md}"

def ensure_folders_connected(folders: List[Dict[str, Any]], config: Dict[str, Any],
                             interactive: bool = True) -> List[Tuple[Dict[str, Any], bool, str]]:
    return [(f, *connect_folder(f, config, interactive=interactive)) for f in folders]

def folder_statuses(folders: List[Dict[str, Any]], config: Dict[str, Any], timeout: float = 3.0) -> Dict[str, str]:
    """Checks all folders in parallel so offline SMB hosts don't stall the menu."""
    results: Dict[str, str] = {}
    threads = []
    for f in folders:
        def _check(fx=f):
            results[fx["id"]] = access_path(fx, config, timeout)[1]
        t = threading.Thread(target=_check, daemon=True)
        t.start()
        threads.append(t)
    deadline = time.time() + timeout + 0.5
    for t in threads:
        t.join(max(0.0, deadline - time.time()))
    return {f["id"]: results.get(f["id"], "TIMEOUT") for f in folders}

# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

def get_playlist_paths(target: str, config: Dict[str, Any]) -> Tuple[Path, Path]:
    stem = ALL_PLAYLIST_STEM if target.upper() == ALL_TARGET else f"DJ_Tracks_{target.upper()}"
    return config["playlists_dir"] / f"{stem}.m3u8", config["playlists_dir"] / f"{stem}.json"

def get_playlist_m3u_path(target: str, config: Dict[str, Any]) -> Path:
    return get_playlist_paths(target, config)[0]

def get_playlist_json_path(target: str, config: Dict[str, Any]) -> Path:
    return get_playlist_paths(target, config)[1]

def check_playlist_status(target: str, config: Dict[str, Any]) -> Dict[str, Any]:
    m3u_path, json_path = get_playlist_paths(target, config)
    exists = m3u_path.is_file() and json_path.is_file()
    track_count, mtime = 0, 0.0
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
        "exists": exists, "track_count": track_count, "m3u_path": m3u_path, "json_path": json_path,
        "mtime": mtime,
        "mtime_fmt": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)) if mtime > 0 else "Never",
    }

def _track_entry(full_path: str, rel: str, folder_id: str, size: int = 0, mtime: float = 0.0) -> Dict[str, Any]:
    base = os.path.basename(full_path)
    stem, ext = os.path.splitext(base)
    return {
        "name": base, "title": stem, "path": full_path, "folder": folder_id, "subpath": rel,
        "ext": ext[1:].upper(), "size_mb": round(size / (1024 * 1024), 2) if size else 0.0,
        "duration_fmt": "00:00", "mtime": mtime or time.time(),
    }

def _scan_filesystem(root: str, folder_id: str, progress_cb=None) -> List[Dict[str, Any]]:
    tracks: List[Dict[str, Any]] = []
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                entries = list(it)
        except OSError as exc:
            if progress_cb:
                progress_cb(f"Skipped unreadable folder: {cur} ({exc.strerror or exc})")
            continue
        for e in entries:
            n = e.name
            if n.startswith(".") or n.startswith("._"):
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    if n.lower() not in SKIP_DIR_NAMES:
                        stack.append(e.path)
                    continue
                if os.path.splitext(n)[1].lower() not in AUDIO_EXTENSIONS:
                    continue
                size, mtime = 0, 0.0
                try:
                    st = e.stat()
                    size, mtime = st.st_size, st.st_mtime
                except OSError:
                    pass
                rel = os.path.relpath(e.path, root).replace("\\", "/")
                tracks.append(_track_entry(e.path, rel, folder_id, size, mtime))
                if progress_cb and len(tracks) % 2000 == 0:
                    progress_cb(f"Indexed {len(tracks):,} audio tracks...")
            except OSError:
                continue
    return tracks

def _scan_rclone(f: Dict[str, Any], config: Dict[str, Any], progress_cb=None) -> Optional[List[Dict[str, Any]]]:
    remote = _rclone_remote(f, config, with_subpath=True)
    if not remote:
        return None
    try:
        p = subprocess.Popen(["rclone", "lsf", remote, "--recursive", "--files-only"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    except Exception as exc:
        if progress_cb:
            progress_cb(f"Error launching rclone: {exc}")
        return None
    root = os.path.join(str(smb_mount_dir(f, config)), f.get("subpath", ""))
    tracks: List[Dict[str, Any]] = []
    for line in (p.stdout or []):
        line = line.strip()
        if not line:
            continue
        base = os.path.basename(line)
        if base.startswith("._") or "/." in ("/" + line) or "$RECYCLE.BIN" in line:
            continue
        if os.path.splitext(base)[1].lower() in AUDIO_EXTENSIONS:
            tracks.append(_track_entry(os.path.join(root, line), line, f["id"]))
            if progress_cb and len(tracks) % 2000 == 0:
                progress_cb(f"Indexed {len(tracks):,} audio tracks...")
    p.wait()
    if p.returncode != 0 and not tracks:
        if progress_cb:
            err = (p.stderr.read() if p.stderr else "").strip().splitlines()
            progress_cb(f"rclone could not list {display_path(f)}: {err[-1] if err else 'exit ' + str(p.returncode)}")
        return None
    return tracks

def scan_folder_tracks(f: Dict[str, Any], config: Dict[str, Any], progress_cb=None,
                       interactive: bool = True) -> Optional[List[Dict[str, Any]]]:
    """Returns the folder's audio tracks, or None if the folder could not be reached."""
    if progress_cb:
        progress_cb(f"Connecting to {display_path(f)}...")
    root, _ = access_path(f, config)
    if not root and f["type"] == "smb" and not IS_WINDOWS:
        # Fast path on Linux/macOS: list the share via rclone, tracks resolve to the rclone mount at play time.
        tracks = _scan_rclone(f, config, progress_cb)
        if tracks is not None:
            tracks.sort(key=lambda t: t["subpath"].lower())
            return tracks
    if not root:
        ok, msg = connect_folder(f, config, interactive=interactive)
        if progress_cb:
            progress_cb(msg)
        root = access_path(f, config)[0] if ok else None
    if not root:
        return None
    tracks = _scan_filesystem(root, f["id"], progress_cb)
    tracks.sort(key=lambda t: t["subpath"].lower())
    return tracks

def save_playlist_files(tracks: List[Dict[str, Any]], target: str, config: Dict[str, Any],
                        title: str = "") -> Tuple[Path, Path]:
    """Saves both .m3u8 playlist and structured .json cache for lightning-fast loading."""
    m3u_path, json_path = get_playlist_paths(target, config)
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#PLAYLIST:MP DJ Tracks Database - {title or target.upper()}\n")
        for t in tracks:
            d_sec = int(t.get("duration_sec", -1)) if t.get("duration_sec") else -1
            f.write(f"#EXTINF:{d_sec},{t.get('title', t['name'])}\n")
            f.write(f"{t['path']}\n")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=2, ensure_ascii=False)
    return m3u_path, json_path

def rebuild_all_playlist(folders: List[Dict[str, Any]], config: Dict[str, Any]) -> int:
    """Rebuilds the combined ALL playlist from the per-folder caches (no rescan needed)."""
    combined: List[Dict[str, Any]] = []
    for f in folders:
        jp = get_playlist_json_path(f["id"], config)
        if jp.is_file():
            try:
                with open(jp, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    combined.extend(data)
            except Exception:
                pass
    if not folders:
        for p in get_playlist_paths(ALL_TARGET, config):
            try:
                p.unlink()
            except OSError:
                pass
        return 0
    save_playlist_files(combined, ALL_TARGET, config, title="ALL MUSIC FOLDERS")
    return len(combined)

def generate_advance_playlists(target: str = ALL_TARGET, config: Optional[Dict[str, Any]] = None,
                               interactive: bool = True, folders: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Generates playlists for MUSIC folders in advance and saves them."""
    config = config or load_music_config()
    folders = folders if folders is not None else load_folders(config)
    if target.upper() == ALL_TARGET:
        to_process = list(folders)
    else:
        f = find_folder(target, folders)
        if not f:
            print(f"{RED}Unknown music folder: {target}{NC}")
            return {}
        to_process = [f]
    if not to_process:
        print(f"\n{YELLOW}No music folders configured. Add a local drive folder or SMB share first.{NC}")
        return {}

    print(f"\n{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}    GENERATING PLAYLISTS FOR MUSIC FOLDERS IN ADVANCE                 {NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
    print(f"  {BOLD}Target Folders:{NC} {WHITE}{', '.join(f['name'] for f in to_process)}{NC}\n")
    print(f"  {DIM}Scanning folders and pre-caching audio files to eliminate player loading delays...{NC}\n", flush=True)

    t_start = time.time()
    results: Dict[str, Any] = {}
    for f in to_process:
        print(f"  {BOLD}{CYAN}▶ Scanning [{f['id']}] {display_path(f)}...{NC}", flush=True)
        tracks = scan_folder_tracks(f, config, progress_cb=lambda m: print(f"    {DIM}{m}{NC}", flush=True),
                                    interactive=interactive)
        if tracks is None:
            print(f"  {BOLD}{RED}✖ Could not reach {display_path(f)} - existing playlist kept unchanged.{NC}\n")
            results[f["id"]] = {"count": None, "error": "unreachable"}
            continue
        m3u_p, json_p = save_playlist_files(tracks, f["id"], config, title=f["name"])
        results[f["id"]] = {"count": len(tracks), "m3u": str(m3u_p), "json": str(json_p)}
        print(f"  {BOLD}{GREEN}✓ Saved {f['name']} Playlist:{NC} {len(tracks):,} tracks ➔ {m3u_p.name}\n", flush=True)

    total = rebuild_all_playlist(folders, config)
    results[ALL_TARGET] = {"count": total}
    print(f"  {BOLD}{GREEN}✓ Updated Combined ALL Music Folders Playlist:{NC} {total:,} tracks")
    print(f"\n{BOLD}{COLOR_TRAFFIC_GREEN}✔ Playlist Generation Complete!{NC}")
    print(f"  Time Elapsed         : {BOLD}{CYAN}{time.time() - t_start:.2f}s{NC}")
    print(f"  Storage Directory    : {DIM}{config['playlists_dir']}{NC}\n")
    return results

def launch_mp_audio_player_music_mode(target: str = ALL_TARGET, config: Optional[Dict[str, Any]] = None,
                                      folders: Optional[List[Dict[str, Any]]] = None):
    """Launches MP Audio Player in MUSIC Mode with the generated playlist."""
    config = config or load_music_config()
    folders = folders if folders is not None else load_folders(config)
    if target.upper() == ALL_TARGET:
        involved, target_id = folders, ALL_TARGET
    else:
        f = find_folder(target, folders)
        if not f:
            print(f"{RED}Unknown music folder: {target}{NC}")
            return
        involved, target_id = [f], f["id"]
    if not involved:
        print(f"\n{YELLOW}No music folders configured. Add a local drive folder or SMB share first.{NC}")
        return

    st = check_playlist_status(target_id, config)
    if not st["exists"] or st["track_count"] == 0:
        print(f"\n{BOLD}{YELLOW}Notice: Playlist for '{target_id}' has not been generated yet!{NC}")
        print(f"{DIM}Generating playlist in advance to guarantee zero-latency loading...{NC}\n")
        generate_advance_playlists(target_id, config=config, interactive=True, folders=folders)
        st = check_playlist_status(target_id, config)
    if st["track_count"] == 0:
        print(f"{RED}No audio tracks available for '{target_id}'. Check the folder path and connection.{NC}")
        return

    print(f"{DIM}Verifying music folder connections...{NC}", flush=True)
    for f, ok, msg in ensure_folders_connected(involved, config, interactive=True):
        if not ok:
            print(f"  {YELLOW}⚠ {f['name']}: {msg}{NC}")

    playlist_path = st["json_path"] if st["json_path"].is_file() else st["m3u_path"]
    player_py = config["base_dir"] / "MP_Audio_Player.py"
    if not player_py.is_file():
        player_py = config["base_dir"] / "scripts" / "MP_Audio_Player.py"
    cmd = [sys.executable, str(player_py), "--interactive", "--music-mode",
           "--music-folder", target_id, "--playlist", str(playlist_path)]
    print(f"{BOLD}{GREEN}Launching MP Audio Player in MUSIC Mode ({st['track_count']:,} tracks)...{NC}", flush=True)
    time.sleep(0.5)
    subprocess.run(cmd)

# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

def clear_screen():
    sys.stdout.write("\033[2J\033[3J\033[H")
    sys.stdout.flush()

def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return ""

def pause(msg: str = "Press Enter to continue..."):
    ask(f"\n{BOLD}{msg}{NC}")

def _clip(text: str, width: int) -> str:
    text = str(text or "")
    if len(text) <= width:
        return text.ljust(width)
    if width <= 3:
        return text[:width]
    return text[:width - 3] + "..."

def _status_badge(label: str) -> str:
    if label in ("ONLINE", "MOUNTED"):
        return f"{GREEN}● {label}{NC}"
    if label == "NOT MOUNTED":
        return f"{YELLOW}○ {label}{NC}"
    return f"{RED}✖ {label}{NC}"

def _playlist_badge(st: Dict[str, Any]) -> str:
    return f"{GREEN}{st['track_count']:,} Tracks{NC}" if st["exists"] else f"{RED}Not Generated{NC}"

def pick_folder(folders: List[Dict[str, Any]], title: str, allow_all: bool = False) -> Optional[Union[str, Dict[str, Any]]]:
    if not folders:
        print(f"\n{YELLOW}No music folders configured yet.{NC}")
        pause()
        return None
    print(f"\n{BOLD}{title}{NC}")
    if allow_all:
        print(f"  {BOLD}{CYAN}A){NC} ALL Music Folders")
    for i, f in enumerate(folders, 1):
        print(f"  {BOLD}{CYAN}{i}){NC} {f['name']}  {DIM}{display_path(f)}{NC}")
    print(f"  {BOLD}{CYAN}0){NC} Cancel")
    c = ask("Enter choice: ").strip()
    if allow_all and c.lower() in ("a", "all"):
        return ALL_TARGET
    if c in ("", "0", "q", "Q"):
        return None
    f = find_folder(c, folders)
    if not f:
        print(f"{RED}Invalid choice.{NC}")
        pause()
    return f

def add_folder_interactive(folders: List[Dict[str, Any]], config: Dict[str, Any]):
    print(f"\n{BOLD}{COLOR_HOT_PURPLE}=== ADD MUSIC FOLDER (Local Drive or SMB Share) ==={NC}\n")
    print(f"  {BOLD}Examples:{NC}")
    if IS_WINDOWS:
        print(f"    Local drive : {CYAN}D:\\Music{NC}   or   {CYAN}/d/Music{NC}")
    else:
        print(f"    Local drive : {CYAN}{Path.home() / 'Music'}{NC}   or   {CYAN}/run/media/{os.environ.get('USER', 'user')}/USB/Music{NC}")
    print(f"    SMB share   : {CYAN}\\\\192.168.1.138\\music001{NC}   or   {CYAN}smb://nas/share/Subfolder{NC}")
    print(f"  {DIM}Only local drives and SMB shares can be added. ftp, nfs, http, and cloud URLs are rejected.{NC}")
    print(f"  {DIM}Leave blank to cancel.{NC}\n")
    raw = ask("Music folder path: ").strip()
    if not raw:
        return
    try:
        parsed = parse_folder_path(raw)
    except ValueError as exc:
        print(f"{RED}✖ {exc}{NC}")
        pause()
        return
    for existing in folders:
        if folder_key(existing) == folder_key(parsed):
            print(f"{YELLOW}That folder is already configured as [{existing['id']}] {existing['name']}.{NC}")
            pause()
            return

    probe = dict(parsed, id="__probe__", path=display_path(parsed))
    print(f"  {DIM}Checking {display_path(parsed)}...{NC}", flush=True)
    reachable, label = access_path(probe, config, timeout=8.0)
    user = ""
    if not reachable and parsed["type"] == "smb":
        print(f"  {YELLOW}Share is not currently reachable ({label}).{NC}")
        user = ask("SMB username (blank = current Windows / guest credentials): ").strip()
        if IS_WINDOWS or ask("Try to connect now? [Y/n]: ").strip().lower() not in ("n", "no"):
            ok, msg = connect_folder(dict(probe, user=user or parsed.get("user", "")), config, interactive=True)
            print(f"  {GREEN if ok else YELLOW}{msg}{NC}")
            reachable = ok
    if not reachable:
        if ask(f"{YELLOW}Folder could not be verified. Add it anyway? [y/N]: {NC}").strip().lower() not in ("y", "yes"):
            return
    else:
        print(f"  {GREEN}✔ Folder is accessible.{NC}")

    name = ask(f"Display name [{default_folder_name(parsed)}]: ").strip()
    try:
        f = add_folder(raw, folders, name=name, user=user)
    except ValueError as exc:
        print(f"{RED}✖ {exc}{NC}")
        pause()
        return
    print(f"\n{GREEN}✔ Added [{f['id']}] {f['name']} ➔ {display_path(f)}{NC}")
    if reachable and ask("Generate this folder's playlist now? [Y/n]: ").strip().lower() not in ("n", "no"):
        generate_advance_playlists(f["id"], config=config, interactive=True, folders=folders)
    pause()

def remove_folder_interactive(folders: List[Dict[str, Any]], config: Dict[str, Any]):
    f = pick_folder(folders, "Select the music folder to REMOVE:")
    if not isinstance(f, dict):
        return
    if ask(f"{YELLOW}Remove [{f['id']}] {f['name']} ({display_path(f)}) and its cached playlist? [y/N]: {NC}").strip().lower() not in ("y", "yes"):
        return
    remove_folder(f, folders, config)
    print(f"{GREEN}✔ Removed {f['name']}. Your music files were not touched.{NC}")
    pause()

def show_shortcuts_guide():
    print(f"\n{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}     TRACK AUDIO INSPECTOR & PLAYER SHORTCUTS GUIDE (MUSIC MODE)      {NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}\n")
    print(f"  {BOLD}{CYAN}1. Track Audio Inspector HUD (Key I){NC}")
    print(f"     • Real-time modal HUD displaying full audio specs, format, sample rate,")
    print(f"       channels, time position, hardware audio output, and source path.")
    print(f"     • Press [I], [Esc], or [Enter] to toggle or close overlay.")
    print(f"\n  {BOLD}{CYAN}2. Instant Search & Filtering (Key /){NC}")
    print(f"     • Press [/] anywhere to filter tracks instantly by typing.")
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
    pause("Press Enter to return to menu...")

def _player_py() -> Optional[Path]:
    base_dir = get_base_dir()
    for p in (base_dir / "MP_Audio_Player.py", base_dir / "scripts" / "MP_Audio_Player.py"):
        if p.is_file():
            return p
    return None

def run_music_folders_menu():
    """Interactive TUI menu for managing MUSIC folders."""
    config = load_music_config()
    while True:
        folders = load_folders(config)
        clear_screen()
        print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE}  Play Tracks from MUSIC Folders using MP Audio Player                {NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE}             (Music Library • Local Drives & SMB Shares)              {NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
        print(f"  {BOLD}Configured Music Folders:{NC} {DIM}({FOLDERS_FILE}){NC}")
        if folders:
            print(f"  {DIM}Checking folder status...{NC}", end="\r", flush=True)
            statuses = folder_statuses(folders, config)
            for i, f in enumerate(folders, 1):
                kind = "SMB  " if f["type"] == "smb" else "LOCAL"
                print(f"    {BOLD}{CYAN}[{i}]{NC} {WHITE}{_clip(f['name'], 16)}{NC} {DIM}{kind}{NC} {_clip(display_path(f), 40)} "
                      f"{_status_badge(statuses[f['id']])}  {_playlist_badge(check_playlist_status(f['id'], config))}")
            print(f"    {BOLD}ALL Music Folders playlist:{NC} {_playlist_badge(check_playlist_status(ALL_TARGET, config))}")
        else:
            print(f"    {YELLOW}No music folders configured yet - choose option 4 to add a local drive folder or SMB share.{NC}")
        print(LINE + "\n")

        print(f"{BOLD}Select an Option:{NC}")
        print(f"  {BOLD}{CYAN}1){NC} Play ALL Music Folders in MP Audio Player ({BOLD}{COLOR_ELECTRIC_CYAN}MUSIC Mode{NC})")
        print(f"  {BOLD}{CYAN}2){NC} Play a Specific Music Folder in MP Audio Player")
        print(f"  {BOLD}{CYAN}3){NC} Generate / Refresh Playlists in Advance (Pre-cache for Instant Loading)")
        print(f"  {BOLD}{CYAN}4){NC} Add Music Folder {DIM}(Local Drive Path or SMB Share){NC}")
        print(f"  {BOLD}{CYAN}5){NC} Remove Music Folder")
        print(f"  {BOLD}{CYAN}6){NC} View Track Audio Inspector & Player Shortcuts Guide")
        print(f"  {BOLD}{CYAN}r){NC} Refresh Status")
        print(f"  {BOLD}{CYAN}0){NC} Return to Main Menu\n")

        try:
            raw_choice = input("Enter choice [0-6]: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        choice = raw_choice.strip()

        if choice in ("m", "M"):
            pp = _player_py()
            if pp:
                subprocess.Popen([sys.executable, str(pp), "--new-window"])
            continue
        if raw_choice == " " or choice.lower() == "space":
            pp = _player_py()
            if pp:
                subprocess.Popen([sys.executable, str(pp), "--toggle", "--only-if-running"])
            continue

        if choice in ("1", "all", "ALL"):
            if not folders:
                print(f"\n{YELLOW}Add a music folder first (option 4).{NC}")
                pause()
                continue
            launch_mp_audio_player_music_mode(ALL_TARGET, config, folders)
        elif choice == "2":
            f = pick_folder(folders, "Select the music folder to play:")
            if isinstance(f, dict):
                launch_mp_audio_player_music_mode(f["id"], config, folders)
        elif choice == "3":
            t = pick_folder(folders, "Select target for playlist generation:", allow_all=True)
            if t:
                generate_advance_playlists(t if isinstance(t, str) else t["id"], config=config,
                                           interactive=True, folders=folders)
                pause()
        elif choice == "4":
            add_folder_interactive(folders, config)
        elif choice == "5":
            remove_folder_interactive(folders, config)
        elif choice == "6":
            show_shortcuts_guide()
        elif choice.lower() in ("r", ""):
            continue
        elif choice in ("0", "q", "Q", "exit", "ESC"):
            break

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Music Folders (Local Drives & SMB Shares) & MP Audio Player Suite")
    parser.add_argument("--menu", action="store_true", help="Launch interactive Music Folders menu")
    parser.add_argument("--list", action="store_true", help="List configured music folders")
    parser.add_argument("--add", metavar="PATH", help="Add a music folder (local path, \\\\host\\share or smb://host/share)")
    parser.add_argument("--name", default="", help="Display name for --add")
    parser.add_argument("--user", default="", help="SMB username for --add (optional)")
    parser.add_argument("--remove", metavar="ID", help="Remove a music folder by ID, number, name or path")
    parser.add_argument("--mount", "--connect", dest="mount", action="store_true", help="Connect / mount all SMB music shares")
    parser.add_argument("--unmount", "--disconnect", dest="unmount", action="store_true", help="Disconnect / unmount all SMB music shares")
    parser.add_argument("--status", action="store_true", help="Show music folders & playlists status as JSON")
    parser.add_argument("--generate", nargs="?", const=ALL_TARGET, help="Generate playlists in advance (ALL or folder ID)")
    parser.add_argument("--play", nargs="?", const=ALL_TARGET, help="Launch MP Audio Player in MUSIC mode (ALL or folder ID)")
    args = parser.parse_args()

    config = load_music_config()
    folders = load_folders(config)

    if args.list:
        if not folders:
            print("No music folders configured.")
        for i, f in enumerate(folders, 1):
            print(f"[{i}] {f['id']:<16} {f['type']:<5} {display_path(f)}  ({f['name']})")
        sys.exit(0)
    if args.add:
        try:
            f = add_folder(args.add, folders, name=args.name, user=args.user)
        except ValueError as exc:
            print(f"Error: {exc}")
            sys.exit(1)
        label = access_path(f, config)[1]
        print(f"Added [{f['id']}] {f['name']} -> {display_path(f)} ({label})")
        sys.exit(0)
    if args.remove:
        f = find_folder(args.remove, folders)
        if not f:
            print(f"Error: no music folder matches '{args.remove}'")
            sys.exit(1)
        remove_folder(f, folders, config)
        print(f"Removed [{f['id']}] {f['name']}")
        sys.exit(0)
    if args.mount:
        for f, ok, msg in ensure_folders_connected([x for x in folders if x["type"] == "smb"], config, interactive=False):
            print(f"{f['id']}: {'OK' if ok else 'FAIL'} - {msg}")
        sys.exit(0)
    if args.unmount:
        for f in [x for x in folders if x["type"] == "smb"]:
            ok, msg = disconnect_folder(f, config)
            print(f"{f['id']}: {'OK' if ok else 'FAIL'} - {msg}")
        sys.exit(0)
    if args.status:
        statuses = folder_statuses(folders, config)
        print(json.dumps({
            "config_file": str(FOLDERS_FILE),
            "folders": [dict(f, status=statuses[f["id"]]) for f in folders],
            "playlists": {t: check_playlist_status(t, config) for t in [ALL_TARGET] + [f["id"] for f in folders]},
        }, indent=2, default=str))
        sys.exit(0)
    if args.generate:
        generate_advance_playlists(args.generate, config=config, interactive=sys.stdin.isatty(), folders=folders)
        sys.exit(0)
    if args.play:
        launch_mp_audio_player_music_mode(args.play, config=config, folders=folders)
        sys.exit(0)
    run_music_folders_menu()

if __name__ == "__main__":
    main()
