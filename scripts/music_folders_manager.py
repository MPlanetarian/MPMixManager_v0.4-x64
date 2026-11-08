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
import atexit
import argparse
import getpass
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
SKIP_DIR_NAMES = {
    "$recycle.bin", "system volume information", "@eadir", "#recycle", 
    "#snapshot", ".trashes", ".spotlight-v100", ".fseventsd", "logic pro library.bundle"
}

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
                    data[k.strip()] = _unquote_env_value(v)
    except Exception:
        pass
    return data

def _unquote_env_value(raw: str) -> str:
    """Read one config.env value. Single quotes stay literal, including $ and quotes."""
    v = raw.strip()
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("'\"'\"'", "'")
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    return v.strip('"').strip("'")

def _quote_env_value(value: str) -> str:
    if any(ch in value for ch in "\n\r\x00"):
        raise ValueError("Username and password cannot contain line breaks.")
    return "'" + value.replace("'", "'\"'\"'") + "'"

def set_env_values(path: Path, updates: Dict[str, str]) -> None:
    """Replace or append keys in one env file. Other lines stay as they are."""
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.is_file() else []
    seen = set()
    out: List[str] = []
    for line in original:
        stripped = line.strip()
        key = None
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
        if key in updates:
            if key not in seen:
                out.append(f"{key}={_quote_env_value(updates[key])}")
                seen.add(key)
            continue
        out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={_quote_env_value(value)}")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

def save_smb_login(user: str, password: str, path: Optional[Path] = None) -> None:
    """Store the SMB login in the user config. The password is not written to the repo."""
    target = path or (CONFIG_DIR / "config.env")
    set_env_values(target, {"MUSIC_SMB_USER": user, "MUSIC_SMB_PASSWORD": password})

def _smb_login_badge(config: Dict[str, Any]) -> str:
    user = (config.get("smb_user") or "").strip()
    saved = bool(config.get("smb_password"))
    if not user and not saved:
        return f"{YELLOW}not set{NC}"
    who = user if user else "(username on each folder)"
    pw = f"{GREEN}saved{NC}" if saved else f"{RED}not set{NC}"
    return f"{CYAN}{who}{NC}  password {pw}"

def configure_smb_login(config: Dict[str, Any]) -> None:
    """Ask for the SMB username and password used by playlist refresh and mounting."""
    print(f"\n{BOLD}{COLOR_HOT_PURPLE}=== CONFIGURE SMB LOGIN ==={NC}\n")
    print(f"  Playlist refresh and mounting use this login for every SMB music folder.")
    print(f"  A folder that already has its own username keeps that username.")
    print(f"  Current login: {_smb_login_badge(config)}")
    print(f"  {DIM}Press Enter to keep the current value. The password is not shown.{NC}\n")
    current_user = (config.get("smb_user") or "").strip()
    current_password = config.get("smb_password") or ""
    typed_user = ask(f"SMB username [{current_user or 'not set'}]: ").strip()
    user = typed_user or current_user
    try:
        typed_password = getpass.getpass("SMB password (hidden, Enter keeps the saved password): ")
    except (EOFError, KeyboardInterrupt):
        print()
        return
    password = current_password if typed_password == "" else typed_password
    if not user:
        print(f"{RED}✖ A username is required.{NC}")
        pause()
        return
    if not password:
        print(f"{RED}✖ A password is required.{NC}")
        pause()
        return
    try:
        save_smb_login(user, password)
    except ValueError as exc:
        print(f"{RED}✖ {exc}{NC}")
        pause()
        return
    config["smb_user"] = user
    config["smb_password"] = password
    print(f"\n{GREEN}✔ SMB login saved for {user}. The password is stored and will not be shown.{NC}")
    pause()

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
    host = f.get("host") or load_music_config().get("legacy_host", "nas")
    share = f.get("share") or f.get("id", "")
    p = "\\\\" + host + "\\" + share
    if f.get("subpath"):
        p += "\\" + f["subpath"].replace("/", "\\")
    return p

def display_path(f: Dict[str, Any]) -> str:
    return unc_path(f) if f.get("type") == "smb" or f.get("path", "").startswith(str(load_music_config()["mount_root"])) else f.get("path", "")

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
    if f.get("type") == "smb":
        return f["subpath"].rsplit("/", 1)[-1] if f.get("subpath") else f["share"]
    return os.path.basename(f.get("path", "").rstrip("\\/")) or f.get("id", "FOLDER")

# ---------------------------------------------------------------------------
# Folder list persistence & Migration
# ---------------------------------------------------------------------------

def save_folders(folders: List[Dict[str, Any]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FOLDERS_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "folders": folders}, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, FOLDERS_FILE)

def _migrate_legacy_folders(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    host, shares_raw = config.get("legacy_host", ""), config.get("legacy_shares", "")
    if not host or not shares_raw:
        return []
    folders: List[Dict[str, Any]] = []
    for share in [s.strip().strip("/\\") for s in re.split(r'[,;]', shares_raw) if s.strip()]:
        f = {"type": "smb", "host": host, "share": share, "subpath": "", "user": ""}
        f["name"] = share
        f["id"] = make_folder_id(share, folders)
        f["path"] = str(config["mount_root"] / f["id"])
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
    if not IS_WINDOWS:
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
    def _probe():
        try:
            return os.path.isdir(path)
        except Exception:
            return False
    return _run_with_timeout(_probe, timeout, None)

def _listing_responds(path: str, timeout: float = 4.0) -> bool:
    """True when a directory listing returns. A wedged rclone mount makes os.listdir hang."""
    try:
        res = subprocess.run(
            ["ls", "-A", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return res.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False

def _kill_rclone_mount(md: Path) -> None:
    target = str(md)
    pids = []
    for entry in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            cmd = entry.read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except OSError:
            continue
        if "rclone" in cmd and " mount " in cmd and target in cmd:
            pids.append(int(entry.parent.name))
    for pid in pids:
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    if not pids:
        return
    time.sleep(0.4)
    for pid in pids:
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        try:
            os.kill(pid, 9)
        except OSError:
            pass

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
    sub = f.get("subpath", "")
    share = f.get("share", f.get("id", ""))
    host = f.get("host", "")
    cands: List[str] = []
    if IS_MAC:
        cands.append(os.path.join("/Volumes", share, sub))
    else:
        uid = os.getuid() if hasattr(os, "getuid") else 0
        for s in dict.fromkeys((share, share.lower())):
            cands.append(os.path.join(f"/run/user/{uid}/gvfs", f"smb-share:server={host.lower()},share={s}", sub))
    return cands

def access_path(f: Dict[str, Any], config: Dict[str, Any], timeout: float = 12.0) -> Tuple[Optional[str], str]:
    mount_root_str = str(config["mount_root"])
    path_str = f.get("path", "")
    is_under_mount_root = path_str.startswith(mount_root_str) or f.get("type") == "smb"

    if f["type"] == "local" and not is_under_mount_root:
        ok = _isdir_timeout(path_str, timeout)
        return (path_str, "ONLINE") if ok else (None, "TIMEOUT" if ok is None else "MISSING")

    if IS_WINDOWS:
        p = unc_path(f) if f.get("type") == "smb" else path_str
        ok = _isdir_timeout(p, timeout)
        return (p, "ONLINE") if ok else (None, "TIMEOUT" if ok is None else "OFFLINE")

    md = smb_mount_dir(f, config)
    mounted = _is_mountpoint(md)
    if not mounted:
        for p in _posix_existing_smb_paths(f):
            if _is_mountpoint(Path(p)):
                mounted = True
                break

    if not mounted:
        return None, "OFFLINE"

    p = os.path.join(str(md), f.get("subpath", "")) if f.get("type") == "smb" or path_str.startswith(mount_root_str) else path_str
    # isdir is true for a mountpoint even when the SMB connection never answers.
    return (p, "ONLINE") if _listing_responds(p, timeout) else (None, "OFFLINE")

def _smb_credentials(f: Dict[str, Any], config: Dict[str, Any]) -> Tuple[str, str]:
    return (f.get("user") or config.get("smb_user", "")), config.get("smb_password", "")

def _rclone_remote(f: Dict[str, Any], config: Dict[str, Any], with_subpath: bool = False) -> Optional[str]:
    if not shutil.which("rclone"):
        return None
    user, password = _smb_credentials(f, config)
    host = f.get("host") or config.get("legacy_host")
    share = f.get("share") or f.get("id")
    if not host or not share:
        return None
    opts = [f'host="{host}"']
    if user:
        opts.append(f'user="{user}"')
    if password:
        try:
            res = subprocess.run(["rclone", "obscure", password], capture_output=True, text=True, check=True)
            opts.append(f'pass="{res.stdout.strip()}"')
        except Exception:
            pass
    path = share + "/" + (f.get("subpath", "") + "/" if with_subpath and f.get("subpath") else "")
    return f":smb,{','.join(opts)}:{path}"

def connect_folder(f: Dict[str, Any], config: Dict[str, Any], interactive: bool = True) -> Tuple[bool, str]:
    p, label = access_path(f, config)
    if p:
        return True, f"{label} ({p})"
    if f["type"] == "local" and not f.get("path", "").startswith(str(config["mount_root"])):
        return False, f"Local folder not found: {f['path']}"

    if IS_WINDOWS:
        share_unc = unc_path(f)
        user, password = _smb_credentials(f, config)
        cmd = ["net", "use", share_unc]
        if password and user:
            cmd += [password, f"/user:{user}"]
        elif user:
            cmd += ["*", f"/user:{user}"]
        try:
            res = subprocess.run(cmd, stdin=None if interactive else subprocess.DEVNULL)
        except Exception as exc:
            return False, f"net use failed: {exc}"
        p, label = access_path(f, config)
        return (True, f"Connected ({p})") if p else (False, f"Could not connect to {share_unc}.")

    remote = _rclone_remote(f, config)
    if not remote:
        return False, "rclone is not installed or SMB host is not configured in config.env."
    md = smb_mount_dir(f, config)
    target = os.path.join(str(md), f.get("subpath", ""))
    if _is_mountpoint(md):
        disconnect_folder(f, config)
        for _ in range(30):
            if not _is_mountpoint(md):
                break
            time.sleep(0.1)
        if _is_mountpoint(md):
            return False, f"{display_path(f)} is mounted but not responding, and it could not be remounted."
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
            break
    else:
        return False, f"Timed out waiting for {display_path(f)} to mount at {md}"
    if _listing_responds(target, 8):
        return True, f"Mounted {display_path(f)} at {md}"
    return False, f"Mounted {display_path(f)} but the share did not respond. Check the SMB login in option 8."

def disconnect_folder(f: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
    if IS_WINDOWS:
        share_unc = unc_path(f)
        res = subprocess.run(["net", "use", share_unc, "/delete", "/y"], capture_output=True, text=True)
        return True, ("Disconnected" if res.returncode == 0 else "No active UNC session")
    md = smb_mount_dir(f, config)
    if _is_mountpoint(md):
        commands = []
        if shutil.which("fusermount3"):
            commands.append(["fusermount3", "-uz", str(md)])
        if shutil.which("fusermount"):
            commands.append(["fusermount", "-uz", str(md)])
        commands.append(["umount", "-l", str(md)])
        for cmd in commands:
            # A wedged FUSE mount can leave fusermount blocked. Give up and kill rclone.
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            except subprocess.TimeoutExpired:
                pass
            if not _is_mountpoint(md):
                break
    _kill_rclone_mount(md)
    if not _is_mountpoint(md):
        return True, f"Unmounted {md}"
    return False, f"Could not unmount {md}"

def ensure_folders_connected(folders: List[Dict[str, Any]], config: Dict[str, Any],
                             interactive: bool = True) -> List[Tuple[Dict[str, Any], bool, str]]:
    return [(f, *connect_folder(f, config, interactive=interactive)) for f in folders]

def folder_statuses(folders: List[Dict[str, Any]], config: Dict[str, Any], timeout: float = 8.0) -> Dict[str, str]:
    results: Dict[str, str] = {}
    threads = []
    for f in folders:
        def _check(fx=f):
            results[fx["id"]] = access_path(fx, config, timeout)[1]
        t = threading.Thread(target=lambda: _check(), daemon=True)
        t.start()
        threads.append(t)
    deadline = time.time() + timeout + 0.5
    for t in threads:
        t.join(max(0.0, deadline - time.time()))
    return {f["id"]: results.get(f["id"], "OFFLINE") for f in folders}

# ---------------------------------------------------------------------------
# Playlists & Scanning Suite
# ---------------------------------------------------------------------------

def get_playlist_paths(target: str, config: Dict[str, Any]) -> Tuple[Path, Path]:
    stem = ALL_PLAYLIST_STEM if target.upper() == ALL_TARGET else f"DJ_Tracks_{target.upper()}"
    return config["playlists_dir"] / f"{stem}.m3u8", config["playlists_dir"] / f"{stem}.json"

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
    seen_paths = set()
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
                
                real_path = os.path.abspath(e.path)
                if real_path in seen_paths:
                    continue
                seen_paths.add(real_path)

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
            except Exception:
                pass
    return tracks

def _parse_rclone_mtime(text: str) -> float:
    raw = (text or "").strip().split(".")[0].replace("T", " ").replace("Z", "")
    try:
        return time.mktime(time.strptime(raw[:19], "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return time.time()

def _scan_rclone(f: Dict[str, Any], config: Dict[str, Any], progress_cb=None) -> Optional[List[Dict[str, Any]]]:
    """List an SMB share with rclone. Size and time come from rclone, not the FUSE mount.

    A mount that was started without the SMB login accepts the mountpoint and then
    hangs forever on stat. Reading stderr on another thread keeps a noisy share
    from filling the pipe and stalling the listing.
    """
    remote = _rclone_remote(f, config, with_subpath=True)
    if not remote:
        return None
    cmd = [
        "rclone", "lsf", remote, "--recursive", "--files-only",
        "--format", "pst", "--separator", "|",
        "--contimeout", "20s", "--timeout", "10m", "--retries", "2", "--low-level-retries", "2",
        "--exclude", ".Trashes/**", "--exclude", ".TemporaryItems/**",
        "--exclude", ".DocumentRevisions-V100/**", "--exclude", ".Spotlight-V100/**",
        "--exclude", ".fseventsd/**", "--exclude", ".DS_Store", "--exclude", "._*",
        "--exclude", "@eaDir/**", "--exclude", "#recycle/**", "--exclude", "#snapshot/**",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    except Exception as exc:
        if progress_cb:
            progress_cb(f"Error launching rclone: {exc}")
        return None
    err_tail: List[str] = []

    def _drain_err():
        if not proc.stderr:
            return
        for err_line in proc.stderr:
            err_line = err_line.strip()
            if not err_line:
                continue
            err_tail.append(err_line)
            if len(err_tail) > 6:
                del err_tail[0]

    drain = threading.Thread(target=_drain_err, daemon=True)
    drain.start()
    root = os.path.join(str(smb_mount_dir(f, config)), f.get("subpath", ""))
    tracks: List[Dict[str, Any]] = []
    seen_paths = set()
    if progress_cb:
        progress_cb(f"Listing {display_path(f)}...")
    for line in (proc.stdout or []):
        line = line.strip()
        if not line:
            continue
        if line.count("|") >= 2:
            rel, size_s, mtime_s = line.rsplit("|", 2)
        else:
            rel, size_s, mtime_s = line, "0", ""
        lower_line = rel.lower()
        if ".logicx/" in lower_line or ".band/" in lower_line:
            continue
        base = os.path.basename(rel)
        if base.startswith(".") or base.startswith("._"):
            continue
        if os.path.splitext(base)[1].lower() not in AUDIO_EXTENSIONS:
            continue
        full_path = os.path.join(root, rel.replace("/", os.sep))
        if full_path in seen_paths:
            continue
        seen_paths.add(full_path)
        try:
            size = int(size_s)
        except ValueError:
            size = 0
        tracks.append(_track_entry(full_path, rel.replace("\\", "/"), f["id"], size, _parse_rclone_mtime(mtime_s)))
        if progress_cb and (len(tracks) == 1 or len(tracks) % 500 == 0):
            progress_cb(f"Indexed {len(tracks):,} audio tracks...")
    rc = proc.wait()
    drain.join(timeout=2)
    if tracks:
        return tracks
    if progress_cb:
        detail = err_tail[-1] if err_tail else f"rclone exited {rc}"
        progress_cb(f"No audio tracks listed. {detail}")
    return [] if rc == 0 else None

def scan_folder_tracks(f: Dict[str, Any], config: Dict[str, Any], progress_cb=None,
                       interactive: bool = True) -> Optional[List[Dict[str, Any]]]:
    # SMB listings go through rclone with the saved login. Do not mount first:
    # a wedged FUSE mount hangs on connect, and the folders after it never get
    # a playlist. Playback mounts the share later, when a track is opened.
    if f.get("type") == "smb" and not IS_WINDOWS and shutil.which("rclone"):
        tracks = _scan_rclone(f, config, progress_cb)
        if tracks is None:
            return None
        tracks.sort(key=lambda t: t["subpath"].lower())
        return tracks

    if progress_cb:
        progress_cb(f"Connecting to {display_path(f)}...")
    root, _ = access_path(f, config)
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
    m3u_path, json_path = get_playlist_paths(target, config)
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#PLAYLIST:MP DJ Tracks Database - {title or target.upper()}\n")
        for t in tracks:
            f.write(f"#EXTINF:-1,{t.get('title', t['name'])}\n")
            f.write(f"{t['path']}\n")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=2, ensure_ascii=False)
    return m3u_path, json_path

def rebuild_all_playlist(folders: List[Dict[str, Any]], config: Dict[str, Any]) -> int:
    combined: List[Dict[str, Any]] = []
    seen_paths = set()
    
    for f in folders:
        jp = get_playlist_paths(f["id"], config)[1]
        if jp.is_file():
            try:
                with open(jp, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    for track in data:
                        p = track.get("path")
                        if p and p not in seen_paths:
                            seen_paths.add(p)
                            combined.append(track)
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
    config = config or load_music_config()
    folders = folders if folders is not None else load_folders(config)
    to_process = list(folders) if target.upper() == ALL_TARGET else [find_folder(target, folders)]
    to_process = [f for f in to_process if f]
    if not to_process:
        print(f"\n{YELLOW}No music folders configured.{NC}")
        return {}

    print(f"\n{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}    GENERATING PLAYLISTS FOR MUSIC FOLDERS IN ADVANCE                 {NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
    t_start = time.time()
    for f in to_process:
        print(f"  {BOLD}{CYAN}▶ Scanning [{f['id']}] {display_path(f)}...{NC}", flush=True)
        tracks = scan_folder_tracks(f, config, progress_cb=lambda m: print(f"    {DIM}{m}{NC}", flush=True), interactive=interactive)
        if not tracks:
            print(f"  {BOLD}{RED}✖ Could not list {f['name']}. Its playlist was left unchanged.{NC}\n", flush=True)
            continue
        save_playlist_files(tracks, f["id"], config, title=f["name"])
        # Keep the combined playlist current if a later folder stalls or fails.
        total = rebuild_all_playlist(folders, config)
        print(f"  {BOLD}{GREEN}✓ Saved {f['name']} Playlist:{NC} {len(tracks):,} tracks\n", flush=True)
    total = rebuild_all_playlist(folders, config)
    print(f"  {BOLD}{GREEN}✔ Playlist Generation Complete ({total:,} total tracks in ALL){NC}")
    print(f"  Time Elapsed : {BOLD}{CYAN}{time.time() - t_start:.2f}s{NC}\n")
    return {}

def launch_mp_audio_player_music_mode(target: str = ALL_TARGET, config: Optional[Dict[str, Any]] = None,
                                      folders: Optional[List[Dict[str, Any]]] = None):
    config = config or load_music_config()
    folders = folders if folders is not None else load_folders(config)
    involved, target_id = (folders, ALL_TARGET) if target.upper() == ALL_TARGET else ([find_folder(target, folders)], target)
    if not involved or not involved[0]:
        print(f"\n{YELLOW}Folder not found.{NC}")
        return

    st = check_playlist_status(target_id, config)
    if not st["exists"] or st["track_count"] == 0:
        generate_advance_playlists(target_id, config=config, interactive=True, folders=folders)
        st = check_playlist_status(target_id, config)

    print(f"{DIM}Verifying music folder connections...{NC}", flush=True)
    for f, _, _ in ensure_folders_connected(involved, config, interactive=True):
        pass

    playlist_path = st["json_path"] if st["json_path"].is_file() else st["m3u_path"]
    player_py = config["base_dir"] / "MP_Audio_Player.py"
    if not player_py.is_file():
        player_py = config["base_dir"] / "scripts" / "MP_Audio_Player.py"
    print(f"{BOLD}{GREEN}Launching MP Audio Player in MUSIC Mode ({st['track_count']:,} tracks)...{NC}", flush=True)
    time.sleep(0.5)
    subprocess.run([sys.executable, str(player_py), "--interactive", "--music-mode",
                    "--music-folder", target_id, "--playlist", str(playlist_path)])

# ---------------------------------------------------------------------------
# Interactive Menu & Guides
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
    return text if len(text) <= width else text[:width - 3] + "..."

def _status_badge(label: str) -> str:
    return f"{GREEN}● {label}{NC}" if label == "ONLINE" else f"{RED}○ {label}{NC}"

def _playlist_badge(st: Dict[str, Any]) -> str:
    return f"{GREEN}{st['track_count']:,} Tracks{NC}" if st["exists"] else f"{RED}Not Generated{NC}"

def pick_folder(folders: List[Dict[str, Any]], title: str, allow_all: bool = False) -> Optional[Union[str, Dict[str, Any]]]:
    if not folders:
        print(f"\n{YELLOW}No music folders configured.{NC}")
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
    return find_folder(c, folders)

def show_shortcuts_guide():
    print(f"\n{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}     TRACK AUDIO INSPECTOR & PLAYER SHORTCUTS GUIDE (MUSIC MODE)      {NC}")
    print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}\n")
    print(f"  {BOLD}{CYAN}1. Track Audio Inspector HUD (Key I){NC}")
    print(f"     • Real-time modal HUD displaying full audio specs, sample rate, channels, time position, source path.")
    print(f"  {BOLD}{CYAN}2. Instant Search & Filtering (Key /){NC}")
    print(f"     • Press [/] anywhere to filter tracks instantly by typing.")
    print(f"  {BOLD}{CYAN}3. Playback Controls{NC}")
    print(f"     • [Space] Play/Pause, [n]/[p] Next/Previous, [+/-] Pitch, [v]/[V] Volume, [u] Mute.")
    print(f"  {BOLD}{CYAN}4. Library Mode{NC}")
    print(f"     • [1] Mix Archive playlist, [2] Music playlist. Each key reloads that playlist.")
    print(f"     • If a playlist is missing, configure Mix Archive with main menu option 13 and Music folders with option 2.")
    print(f"  {BOLD}{CYAN}5. Clear Playlist (Key D or Delete){NC}")
    print(f"     • Press [D] or [Del], then press it again, to empty the open playlist and its queue.")
    print(f"     • Audio files stay on disk. [Esc] cancels. [1] or [2] reloads that library.")
    print(f"  {BOLD}{CYAN}6. Favorites (Key H and Key 3){NC}")
    print(f"     • [H] marks the selected mix or music track, or removes it if it is already a favorite.")
    print(f"     • Marked items are saved in the Favorites playlist.")
    print(f"     • [3] opens that playlist. In the Liquid Player, click the gold FAVORITES button too.")
    pause("Press Enter to return to menu...")

def run_music_folders_menu():
    config = load_music_config()
    while True:
        folders = load_folders(config)
        clear_screen()
        print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE} Play Tracks from MUSIC Folders using MP Audio Player                {NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE} (Music Library • Local Drives & SMB Shares)              {NC}")
        print(f"{BOLD}{COLOR_HOT_PURPLE}{BANNER}{NC}")
        print(f"  {BOLD}Configured Music Folders:{NC} {DIM}({FOLDERS_FILE}){NC}")
        if folders:
            statuses = folder_statuses(folders, config)
            for i, f in enumerate(folders, 1):
                kind = "SMB  " if f.get("type") == "smb" else "LOCAL"
                print(f"    {BOLD}{CYAN}[{i}]{NC} {WHITE}{_clip(f['name'], 16)}{NC} {DIM}{kind}{NC} {_clip(display_path(f), 40)} "
                      f"{_status_badge(statuses[f['id']])}  {_playlist_badge(check_playlist_status(f['id'], config))}")
            print(f"    {BOLD}ALL Music Folders playlist:{NC} {_playlist_badge(check_playlist_status(ALL_TARGET, config))}")
        else:
            print(f"    {YELLOW}No music folders configured yet - choose option 4 to add a folder.{NC}")
        print(f"  {BOLD}SMB Login:{NC} {_smb_login_badge(config)}")
        print(LINE + "\n")

        print(f"{BOLD}Select an Option:{NC}")
        print(f"  {BOLD}{CYAN}1){NC} Play ALL Music Folders in MP Audio Player ({BOLD}{COLOR_ELECTRIC_CYAN}MUSIC Mode{NC})")
        print(f"  {BOLD}{CYAN}2){NC} Play a Specific Music Folder in MP Audio Player")
        print(f"  {BOLD}{CYAN}3){NC} Generate / Refresh Playlists in Advance (Pre-cache for Instant Loading)")
        print(f"  {BOLD}{CYAN}4){NC} Add Music Folder {DIM}(Local Drive Path or SMB Share){NC}")
        print(f"  {BOLD}{CYAN}5){NC} Remove Music Folder")
        print(f"  {BOLD}{CYAN}6){NC} View Track Audio Inspector & Player Shortcuts Guide")
        print(f"  {BOLD}{CYAN}7){NC} Mount All Configured SMB / Library Folders")
        print(f"  {BOLD}{CYAN}8){NC} Configure SMB Login {DIM}(Username & Password){NC}")
        print(f"  {BOLD}{CYAN}r){NC} Refresh Status")
        print(f"  {BOLD}{CYAN}0){NC} Return to Main Menu\n")

        try:
            choice = ask("Enter choice [0-8]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "1":
            if not folders:
                print(f"\n{YELLOW}Add a music folder first (option 4).{NC}")
                pause()
                continue
            launch_mp_audio_player_music_mode(ALL_TARGET, config, folders)
        elif choice == "2":
            f = pick_folder(folders, "Select music folder to play:")
            if isinstance(f, dict):
                launch_mp_audio_player_music_mode(f["id"], config, folders)
        elif choice == "3":
            t = pick_folder(folders, "Select target for playlist generation:", allow_all=True)
            if t:
                generate_advance_playlists(t if isinstance(t, str) else t["id"], config=config, folders=folders)
                pause()
        elif choice == "4":
            print(f"\n{BOLD}{COLOR_HOT_PURPLE}=== ADD MUSIC FOLDER ==={NC}\n")
            raw = ask("Music folder path: ").strip()
            if raw:
                try:
                    f = add_folder(raw, folders)
                    print(f"\n{GREEN}✔ Added [{f['id']}] {f['name']} ➔ {display_path(f)}{NC}")
                    if ask("Generate playlist now? [Y/n]: ").strip().lower() not in ("n", "no"):
                        generate_advance_playlists(f["id"], config=config, folders=load_folders(config))
                except ValueError as e:
                    print(f"{RED}✖ {e}{NC}")
                pause()
        elif choice == "5":
            f = pick_folder(folders, "Select music folder to remove:")
            if isinstance(f, dict):
                if ask(f"{YELLOW}Remove [{f['id']}] {f['name']}? [y/N]: {NC}").strip().lower() in ("y", "yes"):
                    remove_folder(f, folders, config)
                    print(f"{GREEN}✔ Removed {f['name']}.{NC}")
                    pause()
        elif choice == "6":
            show_shortcuts_guide()
        elif choice == "7":
            print(f"\n{BOLD}{CYAN}Attempting to mount all configured library shares...{NC}\n", flush=True)
            for f, ok, msg in ensure_folders_connected(folders, config, interactive=True):
                print(f"  {GREEN if ok else RED}➔ [{f['id']}] {f['name']}: {msg}{NC}")
            pause()
        elif choice == "8":
            configure_smb_login(config)
        elif choice.lower() in ("r", ""):
            continue
        elif choice in ("0", "q", "Q"):
            break

# ---------------------------------------------------------------------------
# CLI Argument Parser Suite
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Music Folders & MP Audio Player Suite")
    parser.add_argument("--menu", action="store_true", help="Launch interactive menu")
    parser.add_argument("--list", action="store_true", help="List configured music folders")
    parser.add_argument("--add", metavar="PATH", help="Add a music folder")
    parser.add_argument("--name", default="", help="Display name for --add")
    parser.add_argument("--user", default="", help="SMB username for --add")
    parser.add_argument("--remove", metavar="ID", help="Remove music folder by ID or name")
    parser.add_argument("--mount", "--connect", dest="mount", action="store_true", help="Mount all SMB shares")
    parser.add_argument("--unmount", "--disconnect", dest="unmount", action="store_true", help="Unmount all SMB shares")
    parser.add_argument("--status", action="store_true", help="Show status as JSON")
    parser.add_argument("--generate", nargs="?", const=ALL_TARGET, help="Generate playlists")
    parser.add_argument("--play", nargs="?", const=ALL_TARGET, help="Launch player in MUSIC mode")
    args = parser.parse_args()

    config = load_music_config()
    folders = load_folders(config)

    if args.list:
        for i, f in enumerate(folders, 1):
            print(f"[{i}] {f['id']:<16} {f.get('type'):<5} {display_path(f)} ({f['name']})")
        sys.exit(0)
    if args.add:
        try:
            f = add_folder(args.add, folders, name=args.name, user=args.user)
            print(f"Added [{f['id']}] {f['name']} -> {display_path(f)}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        sys.exit(0)
    if args.remove:
        f = find_folder(args.remove, folders)
        if not f:
            print(f"Error: folder not found '{args.remove}'")
            sys.exit(1)
        remove_folder(f, folders, config)
        print(f"Removed [{f['id']}] {f['name']}")
        sys.exit(0)
    if args.mount:
        for f, ok, msg in ensure_folders_connected(folders, config, interactive=False):
            print(f"{f['id']}: {'OK' if ok else 'FAIL'} - {msg}")
        sys.exit(0)
    if args.unmount:
        for f in folders:
            ok, msg = disconnect_folder(f, config)
            print(f"{f['id']}: {'OK' if ok else 'FAIL'} - {msg}")
        sys.exit(0)
    if args.status:
        statuses = folder_statuses(folders, config)
        print(json.dumps({"folders": [dict(f, status=statuses[f["id"]]) for f in folders]}, indent=2, default=str))
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