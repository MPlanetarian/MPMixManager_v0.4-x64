#!/usr/bin/env python3
"""
scripts/MP_Fav_Playlist_Track_Exporter.py - DJ Set Preparation: Favorites Exporter

Copies the MP Audio Player Favorites playlist to a folder on the local drive or
to an SMB share, writes a tracklist in the MP Mix Manager format, writes an
m3u8 playlist, and (optionally) creates a Traktor playlist from a History file.

Every copy is size-checked, and at least one copied track must decode as audio
before the export is reported as successful. SMB exports fetch one file back
from the share and probe that copy, so the verification covers the transfer.

Interactive:
    python3 scripts/MP_Fav_Playlist_Track_Exporter.py

Headless:
    python3 scripts/MP_Fav_Playlist_Track_Exporter.py \
        --destination "$HOME/Music/MP_Fav_Playlists" \
        --tracklist-name "Favourites 2026-11-12" --yes
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import urllib.parse
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
NC = "\033[0m"

APP_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"
DEFAULT_LOCAL_DIR = Path.home() / "Music" / "MP_Fav_Playlists"
RULE_HEAVY = "=" * 50
RULE_LIGHT = "-" * 50
PLAYLIST_ID_ALPHABET = string.ascii_uppercase + string.digits
PLAYLIST_ID_LENGTH = 12
try:
    from audio_formats import AUDIO_EXTENSIONS
except ImportError:  # imported as scripts.MP_Fav_Playlist_Track_Exporter
    from scripts.audio_formats import AUDIO_EXTENSIONS
AUDIO_EXTS = set(AUDIO_EXTENSIONS)


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
def _config_paths() -> List[Path]:
    return [
        Path(os.environ.get("MP_CONFIG_FILE", "")).expanduser() if os.environ.get("MP_CONFIG_FILE") else None,
        APP_DIR / "config.env",
        SCRIPT_DIR / "config.env",
        CONFIG_DIR / "config.env",
        Path.cwd() / "config.env",
    ]


def load_config() -> Dict[str, str]:
    cfg: Dict[str, str] = {}
    for candidate in _config_paths():
        if not candidate or not candidate.is_file():
            continue
        try:
            for raw in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                key, value = line.split("=", 1)
                cfg[key.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            continue
        break
    cfg.update({key: value for key, value in os.environ.items() if value})
    return cfg


def _expand(value: Any) -> str:
    return os.path.expandvars(os.path.expanduser(str(value or "").strip().strip('"').strip("'")))


def _sanitize_name(value: str, fallback: str = "MP_Fav_Set") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or fallback


def new_playlist_name(tracklist_name: Optional[str] = None) -> str:
    """Return the playlist/tracklist name: date plus a random 12-character ID."""
    if tracklist_name and str(tracklist_name).strip():
        return Path(_sanitize_name(tracklist_name)).stem
    date = time.strftime("%Y-%m-%d")
    ident = "".join(random.choice(PLAYLIST_ID_ALPHABET) for _ in range(PLAYLIST_ID_LENGTH))
    return f"MP_Fav_Set_{date}_{ident}"


# ------------------------------------------------------------------------------
# Favorites
# ------------------------------------------------------------------------------
def favorites_source_path() -> Path:
    return Path(os.environ.get("MP_FAVORITES_FILE") or FAVORITES_FILE)


def load_favorites(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    source = Path(path) if path else favorites_source_path()
    if not source.is_file():
        return []
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("tracks") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    tracks: List[Dict[str, Any]] = []
    seen: set = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        path_value = str(row.get("path") or "").strip()
        if not path_value:
            continue
        key = os.path.normcase(os.path.abspath(os.path.expanduser(path_value)))
        if key in seen:
            continue
        seen.add(key)
        tracks.append(
            {
                "name": str(row.get("name") or os.path.basename(path_value)),
                "path": os.path.expanduser(path_value),
                "ext": str(row.get("ext") or os.path.splitext(path_value)[1].lstrip(".")).upper(),
            }
        )
    return tracks


# ------------------------------------------------------------------------------
# Media metadata and verification
# ------------------------------------------------------------------------------
def _ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")


def probe_audio(path: Path) -> Dict[str, Any]:
    """Return {'playable': bool, 'artist', 'title', 'duration'} for a media file."""
    result: Dict[str, Any] = {"playable": False, "artist": "", "title": "", "duration": 0.0}
    if not path.is_file() or path.stat().st_size <= 0:
        return result
    tool = _ffprobe()
    if tool:
        try:
            completed = subprocess.run(
                [
                    tool,
                    "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=codec_type:format=duration:format_tags=artist,title",
                    "-of", "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if completed.returncode == 0:
                payload = json.loads(completed.stdout or "{}")
                streams = payload.get("streams") or []
                fmt = payload.get("format") or {}
                tags = {str(k).lower(): v for k, v in (fmt.get("tags") or {}).items()}
                result["playable"] = any(s.get("codec_type") == "audio" for s in streams)
                result["artist"] = str(tags.get("artist") or tags.get("album_artist") or "")
                result["title"] = str(tags.get("title") or "")
                try:
                    result["duration"] = float(fmt.get("duration") or 0.0)
                except (TypeError, ValueError):
                    result["duration"] = 0.0
                return result
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    # No ffprobe: accept a known audio container header with real payload.
    try:
        with path.open("rb") as handle:
            header = handle.read(16)
        known = (
            header.startswith(b"fLaC"),
            header.startswith(b"RIFF"),
            header.startswith(b"ID3"),
            header.startswith(b"OggS"),
            header[:4] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
            header.startswith(b"FORM"),
        )
        result["playable"] = path.stat().st_size > 1024 and any(known)
    except OSError:
        pass
    return result


def track_artist_title(track: Dict[str, Any], probed: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    probed = probed or {}
    artist = str(probed.get("artist") or "").strip()
    title = str(probed.get("title") or "").strip()
    if artist and title:
        return artist, title
    stem = Path(str(track.get("path") or track.get("name") or "")).stem
    match = re.match(r"^(.+?)\s+-\s+(.+)$", stem)
    if match:
        return artist or match.group(1).strip(), title or match.group(2).strip()
    if not title:
        title = re.sub(r"^\d{1,3}\s*[\.\-]\s+", "", stem).strip() or stem
    return artist, title


def clean_track_label(artist: str, title: str) -> str:
    artist, title = (artist or "").strip(), (title or "").strip()
    if artist and title:
        return f"{artist} - {title}"
    return title or artist or "Unknown Track"


# ------------------------------------------------------------------------------
# Destination handling (local folder or SMB share)
# ------------------------------------------------------------------------------
def smb_settings(cfg: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    cfg = cfg or load_config()
    host = _expand(cfg.get("FAV_EXPORT_SMB_HOST") or cfg.get("TRAKTOR_SMB_HOST") or cfg.get("MUSIC_SMB_HOST") or "")
    share = _expand(cfg.get("FAV_EXPORT_SMB_SHARE") or cfg.get("TRAKTOR_SMB_SHARE") or "")
    user = _expand(cfg.get("FAV_EXPORT_SMB_USER") or cfg.get("TRAKTOR_SMB_USER") or cfg.get("MUSIC_SMB_USER") or "")
    password = _expand(
        cfg.get("FAV_EXPORT_SMB_PASSWORD") or cfg.get("TRAKTOR_SMB_PASSWORD") or cfg.get("MUSIC_SMB_PASSWORD") or ""
    )
    subpath = _expand(cfg.get("FAV_EXPORT_SMB_PATH") or "")
    mount = _expand(cfg.get("FAV_EXPORT_SMB_MOUNT") or cfg.get("TRAKTOR_SMB_MOUNT") or "")
    return {
        "host": host,
        "share": share,
        "user": user,
        "password": password,
        "path": subpath,
        "mount": mount,
    }


def smb_configured(cfg: Optional[Dict[str, str]] = None) -> bool:
    settings = smb_settings(cfg)
    if settings["mount"] and os.path.isdir(settings["mount"]):
        return bool(settings["host"] and settings["share"])
    return bool(settings["host"] and settings["share"] and shutil.which("smbclient"))


def _smb_auth_file(settings: Dict[str, str]) -> str:
    handle = tempfile.NamedTemporaryFile("w", prefix="mp_fav_smb_", delete=False)
    try:
        handle.write(f"username={settings.get('user', '')}\npassword={settings.get('password', '')}\n")
        handle.flush()
    finally:
        handle.close()
    os.chmod(handle.name, 0o600)
    return handle.name


def _smb_run(settings: Dict[str, str], commands: str, timeout: int = 300) -> Tuple[int, str, str]:
    client = shutil.which("smbclient")
    if not client:
        return 127, "", "smbclient is not installed"
    auth = _smb_auth_file(settings)
    target = f"//{settings['host']}/{settings['share']}"
    try:
        completed = subprocess.run(
            [client, target, "-A", auth, "-t", "60", "-c", commands],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return completed.returncode, completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "SMB operation timed out"
    except OSError as exc:
        return 1, "", str(exc)
    finally:
        try:
            os.unlink(auth)
        except OSError:
            pass


def _smb_quote(value: str) -> str:
    return '"' + str(value).replace('"', "") + '"'


def _parse_smb_ls(output: str) -> Dict[str, int]:
    """Map remote file names to sizes from an smbclient ls listing."""
    rows: Dict[str, int] = {}
    for line in output.splitlines():
        match = re.match(
            r"\s*(.+?)\s+([A-Za-z]+)\s+(\d+)\s+\w{3}\s+\w{3}\s+\d+\s+\d{1,2}:\d{2}:\d{2}\s+\d{4}",
            line,
        )
        if match:
            try:
                rows[match.group(1).strip()] = int(match.group(3))
            except ValueError:
                continue
    return rows


def export_to_local(tracks: Sequence[Dict[str, Any]], destination: str,
                    folder_name: str) -> Dict[str, Any]:
    base = Path(_expand(destination) or DEFAULT_LOCAL_DIR).expanduser()
    target = base / folder_name
    result: Dict[str, Any] = {"kind": "local", "dest": str(target), "copied": [], "failed": [], "errors": []}
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result["errors"].append(f"Could not create {target}: {exc}")
        return result

    used: set = set()
    for track in tracks:
        source = Path(track["path"])
        if not source.is_file():
            result["failed"].append({"name": source.name, "reason": "source file is missing"})
            continue
        name = source.name
        stem, suffix = source.stem, source.suffix
        counter = 2
        while name.casefold() in used:
            name = f"{stem} ({counter}){suffix}"
            counter += 1
        used.add(name.casefold())
        destination_file = target / name
        temp_file = target / (name + ".part")
        try:
            shutil.copy2(source, temp_file)
            if temp_file.stat().st_size != source.stat().st_size:
                raise OSError("size differs after copy")
            temp_file.replace(destination_file)
        except OSError as exc:
            try:
                temp_file.unlink(missing_ok=True)
            except OSError:
                pass
            result["failed"].append({"name": source.name, "reason": str(exc)})
            continue
        result["copied"].append({"source": str(source), "dest": str(destination_file), "name": destination_file.name})
    return result


def export_to_smb(tracks: Sequence[Dict[str, Any]], folder_name: str,
                  settings: Dict[str, str]) -> Dict[str, Any]:
    remote_root = "/".join(
        part.strip("/") for part in (settings.get("path") or "") .split("/") if part.strip("/")
    )
    remote_dir = "/".join(part for part in (remote_root, folder_name) if part)
    result: Dict[str, Any] = {
        "kind": "smb",
        "dest": f"smb://{settings['host']}/{settings['share']}/{remote_dir}",
        "remote_dir": remote_dir,
        "copied": [],
        "failed": [],
        "errors": [],
    }

    if settings.get("mount") and os.path.isdir(settings["mount"]):
        mounted = Path(settings["mount"]) / remote_dir
        local = export_to_local(tracks, str(Path(settings["mount"])), remote_dir)
        local["kind"] = "smb"
        local["local_dest"] = local.get("dest", str(mounted))
        local["dest"] = result["dest"]
        local["remote_dir"] = remote_dir
        local["copied"] = [
            dict(row, dest=str(mounted / row["name"])) for row in local.get("copied", [])
        ]
        return local

    if not shutil.which("smbclient"):
        result["errors"].append("smbclient is not installed. Install samba-client or use a local folder.")
        return result

    mkdir_rc, _, mkdir_err = _smb_run(settings, f"mkdir {_smb_quote(remote_dir)}", timeout=90)
    # A pre-existing directory also returns non-zero on some servers; the put below is the real test.
    listing_rc, _, listing_err = _smb_run(settings, f"ls {_smb_quote(remote_dir)}", timeout=90)
    if listing_rc != 0:
        result["errors"].append(f"Could not open the SMB folder {remote_dir}: {listing_err.strip() or mkdir_err.strip()}")
        return result

    used: set = set()
    for track in tracks:
        source = Path(track["path"])
        if not source.is_file():
            result["failed"].append({"name": source.name, "reason": "source file is missing"})
            continue
        name = source.name
        stem, suffix = source.stem, source.suffix
        counter = 2
        while name.casefold() in used:
            name = f"{stem} ({counter}){suffix}"
            counter += 1
        used.add(name.casefold())
        remote_file = f"{remote_dir}/{name}"
        rc, _, err = _smb_run(
            settings,
            f'prompt OFF; put {_smb_quote(str(source))} {_smb_quote(remote_file)}',
            timeout=1800,
        )
        if rc != 0:
            result["failed"].append({"name": source.name, "reason": err.strip() or "smbclient put failed"})
            continue
        result["copied"].append({"source": str(source), "dest": remote_file, "name": name})
    return result


def verify_copies(result: Dict[str, Any], settings: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Confirm sizes, then probe at least one copied track (fetched back for SMB)."""
    settings = settings if settings is not None else smb_settings()
    playable = 0
    checked = 0
    errors: List[str] = list(result.get("errors") or [])
    copied = list(result.get("copied") or [])

    if result.get("kind") == "smb" and not (settings.get("mount") and os.path.isdir(settings["mount"])):
        remote_dir = result.get("remote_dir") or ""
        rc, out, err = _smb_run(settings, f"ls {_smb_quote(remote_dir)}", timeout=120)
        if rc != 0:
            errors.append(f"SMB verification listing failed: {err.strip()}")
        else:
            sizes = _parse_smb_ls(out)
            kept = []
            for row in copied:
                remote_size = sizes.get(row["name"])
                if remote_size is not None and remote_size != Path(row["source"]).stat().st_size:
                    result.setdefault("failed", []).append(
                        {"name": row["name"], "reason": "size differs on the SMB share"}
                    )
                    continue
                kept.append(row)
            copied = kept
        # Prove the transfer end-to-end: fetch the first file back and probe it.
        if copied:
            with tempfile.TemporaryDirectory(prefix="mp_fav_verify_") as tmp:
                probe_target = Path(tmp) / copied[0]["name"]
                fetch_rc, _, fetch_err = _smb_run(
                    settings,
                    f'prompt OFF; get {_smb_quote(smb_path(settings, copied[0]["dest"]))} {_smb_quote(str(probe_target))}',
                    timeout=600,
                )
                if fetch_rc == 0 and probe_target.is_file():
                    checked += 1
                    if probe_audio(probe_target)["playable"]:
                        playable += 1
                elif fetch_err:
                    errors.append(f"Could not read the copied file back: {fetch_err.strip()}")
    else:
        for row in copied:
            target = Path(row["dest"])
            source_size = Path(row["source"]).stat().st_size
            if not target.is_file() or target.stat().st_size != source_size:
                result.setdefault("failed", []).append(
                    {"name": row["name"], "reason": "copied file is missing or truncated"}
                )
                continue
            checked += 1
            if checked <= 25 and probe_audio(target)["playable"]:
                playable += 1

    result["copied"] = copied
    result["verified_files"] = checked
    result["playable_files"] = playable
    result["errors"] = errors
    return result


def smb_path(settings: Dict[str, str], value: str) -> str:
    """Normalise a stored remote path back to the form smbclient expects."""
    if value.startswith("smb://"):
        parsed = urllib.parse.urlparse(value)
        return parsed.path.lstrip("/")
    return str(value).lstrip("/")


# ------------------------------------------------------------------------------
# Tracklist and playlist files
# ------------------------------------------------------------------------------
def build_tracklist(tracks: Sequence[Dict[str, Any]], playlist_name: str,
                    destination: str, probed: Optional[Dict[str, Dict[str, Any]]] = None,
                    history_name: str = "") -> str:
    probed = probed or {}
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        RULE_HEAVY,
        "RELEASE INFO & SOURCE MANIFEST",
        RULE_HEAVY,
        "Artist:        MPlanetarian",
        "Album:         Stream of Frequency",
        f"Title:         {playlist_name}",
        f"Export Date:   {now}",
        "Source:        MP Audio Player Favorites Playlist",
    ]
    if history_name:
        lines.append(f"Traktor Source: {history_name}")
    lines.extend(
        [
            f"Total Tracks:  {len(tracks)}",
            f"Destination:   {destination}",
            RULE_LIGHT,
            RULE_HEAVY,
            "TRACKLIST",
            RULE_HEAVY,
        ]
    )
    width = 2 if len(tracks) < 100 else 3
    for index, track in enumerate(tracks, 1):
        label = track.get("label")
        if not label:
            probed_row = probed.get(str(track.get("path")))
            label = clean_track_label(*track_artist_title(track, probed_row))
        lines.append(f"{index:0{width}d}. {label}")
    lines.append("")
    return "\n".join(lines)


def write_tracklist(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
    return path


def write_m3u8(path: Path, playlist_name: str, entries: Sequence[Dict[str, Any]]) -> Path:
    lines = ["#EXTM3U", f"#PLAYLIST:{playlist_name}"]
    for row in entries:
        label = row.get("label") or Path(row.get("name") or row.get("dest") or "").stem
        lines.append(f"#EXTINF:-1,{label}")
        lines.append(str(row.get("dest") or ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------------------------
# Traktor bridge
# ------------------------------------------------------------------------------
def traktor_ready(cfg: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
    """True when Traktor collection + synced History files are available."""
    cfg = cfg or load_config()
    if str(cfg.get("TRAKTOR_ENABLED", "auto")).strip().lower() in ("false", "0", "no", "off", "disabled"):
        return False, "Traktor is disabled in config.env (TRAKTOR_ENABLED=false)."
    try:
        scripts = str(SCRIPT_DIR)
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import generate_traktor_playlist_from_history as traktor
    except Exception as exc:
        return False, f"Traktor helper is unavailable: {exc}"
    if not traktor.find_collection_path(cfg):
        return False, "collection.nml not found. Run Traktor once and set TRAKTOR_COLLECTION_PATH."
    collection = traktor.find_collection_path(cfg)
    history_dirs = traktor.preferred_history_dirs(collection, cfg)
    if not traktor.list_history_files(1, history_dirs, cfg=cfg):
        return False, "No Traktor History files were copied over yet. Sync the Traktor history first."
    return True, "Traktor history and collection are ready."


def create_traktor_playlist(favorite_paths: Sequence[str], playlist_name: str,
                            history_id: Optional[str] = None,
                            cfg: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    cfg = cfg or load_config()
    ready, reason = traktor_ready(cfg)
    if not ready:
        return {"ok": False, "reason": "not_ready", "message": reason}
    import generate_traktor_playlist_from_history as traktor

    collection = traktor.find_collection_path(cfg)
    history_dirs = traktor.preferred_history_dirs(collection, cfg)
    history = traktor.resolve_history_file(history_id, history_dirs, cfg=cfg)
    if not history:
        return {"ok": False, "reason": "history", "message": "No matching Traktor History file was found."}
    result = traktor.build_traktor_playlist(
        favorite_paths,
        history_id=str(history),
        playlist_name=playlist_name,
        collection_path=str(collection) if collection else None,
        history_dirs=history_dirs,
        cfg=cfg,
    )
    result["history_file"] = history.name
    return result


# ------------------------------------------------------------------------------
# Export orchestration
# ------------------------------------------------------------------------------
def _normalize_tracks(rows: Sequence[Any]) -> List[Dict[str, Any]]:
    """Accept dicts, strings or Path objects and return exporter track rows."""
    normalized: List[Dict[str, Any]] = []
    seen: set = set()
    for row in rows or []:
        if isinstance(row, dict):
            path_value = str(row.get("path") or row.get("name") or "").strip()
            name = str(row.get("name") or os.path.basename(path_value))
        else:
            path_value = str(row)
            name = os.path.basename(path_value)
        if not path_value:
            continue
        expanded = os.path.expanduser(path_value)
        key = os.path.normcase(os.path.abspath(expanded))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "name": name,
                "path": expanded,
                "ext": os.path.splitext(expanded)[1].lstrip(".").upper(),
            }
        )
    return normalized


def export_favorites(
    tracks: Optional[Sequence[Any]] = None,
    destination: Optional[str] = None,
    smb: Optional[Dict[str, str]] = None,
    tracklist_name: Optional[str] = None,
    playlist_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Copy favorites, verify the copies, and write the tracklist and m3u8.

    ``smb`` explicitly selects an SMB export; otherwise the local folder is used.
    """
    tracks = _normalize_tracks(list(tracks if tracks is not None else load_favorites()))
    result: Dict[str, Any] = {
        "ok": False,
        "playlist_name": "",
        "tracklist": "",
        "m3u8": "",
        "dest": "",
        "copied": [],
        "failed": [],
        "errors": [],
        "tracklist_name": "",
    }
    if not tracks:
        result["errors"].append(
            "The Favorites playlist is empty. Add at least one track with [H] before exporting."
        )
        return result

    name = playlist_name or new_playlist_name(tracklist_name)
    name = _sanitize_name(name, "MP_Fav_Set")
    result["playlist_name"] = name
    result["tracklist_name"] = _sanitize_name(tracklist_name or name, name)

    settings = smb
    if settings and (settings.get("host") or settings.get("mount")):
        copied_result = export_to_smb(tracks, name, settings)
    else:
        copied_result = export_to_local(tracks, destination or DEFAULT_LOCAL_DIR, name)

    result.update({key: copied_result.get(key, result.get(key)) for key in ("dest", "copied", "failed", "errors", "kind", "local_dest")})
    result["errors"] = list(dict.fromkeys(result.get("errors") or []))
    if copied_result.get("remote_dir"):
        result["remote_dir"] = copied_result["remote_dir"]

    verified = verify_copies(result, settings)
    result.update(
        {
            "copied": verified.get("copied", []),
            "failed": verified.get("failed", []),
            "errors": verified.get("errors", []),
            "verified_files": verified.get("verified_files", 0),
            "playable_files": verified.get("playable_files", 0),
        }
    )

    if not result["copied"]:
        result["errors"].append("No tracks were copied. Nothing was exported.")
        return result
    if not result.get("playable_files"):
        result["errors"].append(
            "None of the copied tracks could be opened as audio. The copy is treated as failed."
        )
        return result

    # Tracklist labels: prefer embedded tags, then Artist - Title from the file name.
    probed: Dict[str, Dict[str, Any]] = {}
    labels: List[Dict[str, Any]] = []
    for track in tracks:
        row = next((item for item in result["copied"] if item.get("source") == track.get("path")), None)
        if not row:
            continue
        target = Path(row["dest"]) if result.get("kind") != "smb" or os.path.isfile(row["dest"]) else None
        info = probe_audio(target) if target else {}
        probed[str(track.get("path"))] = info
        labels.append({**track, "label": clean_track_label(*track_artist_title(track, info))})

    tracklist_content = build_tracklist(labels, name, result["dest"], probed)
    tracklist_filename = f"{result['tracklist_name']}.txt"
    if result.get("kind") == "smb" and not (settings.get("mount") and os.path.isdir(settings["mount"])):
        with tempfile.TemporaryDirectory(prefix="mp_fav_tracklist_") as tmp:
            local_tracklist = write_tracklist(Path(tmp) / tracklist_filename, tracklist_content)
            rc, _, err = _smb_run(
                settings,
                f'prompt OFF; put {_smb_quote(str(local_tracklist))} '
                f'{_smb_quote(result["remote_dir"] + "/" + tracklist_filename)}',
                timeout=180,
            )
            if rc != 0:
                result["errors"].append(f"Could not upload the tracklist: {err.strip()}")
                return result
    else:
        folder = Path(result.get("local_dest") or result["dest"])
        saved = write_tracklist(folder / tracklist_filename, tracklist_content)
        result["tracklist"] = str(saved)

    entries = [
        {**row, "label": next(
            (item.get("label") for item in labels if item.get("path") == row.get("source")), row.get("name")
        )}
        for row in result["copied"]
    ]
    m3u_name = f"{name}.m3u8"
    if result.get("kind") == "smb" and not (settings.get("mount") and os.path.isdir(settings["mount"])):
        with tempfile.TemporaryDirectory(prefix="mp_fav_m3u_") as tmp:
            local_m3u = write_m3u8(Path(tmp) / m3u_name, name, entries)
            rc, _, err = _smb_run(
                settings,
                f'prompt OFF; put {_smb_quote(str(local_m3u))} '
                f'{_smb_quote(result["remote_dir"] + "/" + m3u_name)}',
                timeout=180,
            )
            if rc == 0:
                result["m3u8"] = result["dest"] + "/" + m3u_name
            elif err:
                result["errors"].append(f"Could not upload the m3u8 playlist: {err.strip()}")
    else:
        result["m3u8"] = str(
            write_m3u8(Path(result.get("local_dest") or result["dest"]) / m3u_name, name, entries)
        )

    result["ok"] = bool(result["playable_files"])
    return result


def summary_lines(result: Dict[str, Any]) -> List[str]:
    lines = [f"Playlist: {result.get('playlist_name', '')}", f"Folder: {result.get('dest', '')}"]
    lines.append(
        f"Copied {len(result.get('copied') or [])} of "
        f"{len(result.get('copied') or []) + len(result.get('failed') or [])} tracks"
    )
    lines.append(f"Verified playable: {result.get('playable_files', 0)}")
    if result.get("tracklist"):
        lines.append(f"Tracklist: {os.path.basename(result['tracklist'])}")
    if result.get("m3u8"):
        lines.append(f"Playlist file: {os.path.basename(result['m3u8'])}")
    traktor = result.get("traktor") or {}
    if traktor:
        lines.append(f"Traktor: {traktor.get('playlist') or traktor.get('message', '')}")
    for failure in (result.get("failed") or [])[:4]:
        lines.append(f"Failed: {failure.get('name')} — {failure.get('reason')}")
    for error in (result.get("errors") or [])[:4]:
        lines.append(f"Note: {error}")
    return lines


# ------------------------------------------------------------------------------
# Interactive CLI
# ------------------------------------------------------------------------------
def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        raise KeyboardInterrupt
    return answer or default


def _yes(prompt: str, default: bool = True) -> bool:
    answer = _ask(prompt, "Y" if default else "N").strip().lower()
    return answer in ("y", "yes")


def _print_header(title: str) -> None:
    os.system("clear 2>/dev/null || true")
    print(f"{BOLD}{MAGENTA}{'=' * 78}{NC}")
    print(f"{BOLD}{MAGENTA}{title.center(78)}{NC}")
    print(f"{BOLD}{MAGENTA}{'=' * 78}{NC}")


def interactive_main() -> int:
    cfg = load_config()
    tracks = load_favorites()
    _print_header("MP FAV PLAYLIST TRACK EXPORTER")
    print(f"  {BOLD}Favorites:{NC} {len(tracks)} track(s) in {favorites_source_path()}")
    if not tracks:
        print(f"\n{YELLOW}The Favorites playlist is empty.{NC}")
        print("Add at least one track in MP Audio Player with [H], then run this again.")
        return 1

    name = new_playlist_name()
    print(f"  {BOLD}Auto playlist name:{NC} {name}")
    custom_tracklist = _ask("Custom tracklist file name (Enter keeps the automatic name)", "")
    playlist_name = new_playlist_name(custom_tracklist)
    if custom_tracklist:
        print(f"  {BOLD}Using tracklist name:{NC} {playlist_name}")

    settings = smb_settings(cfg)
    print(f"\n  {BOLD}{CYAN}1){NC} Folder on this computer")
    smb_ready = smb_configured(cfg) and bool(settings["host"] or settings["mount"])
    print(f"  {BOLD}{CYAN}2){NC} SMB share" + ("  " + DIM + "(configured)" + NC if smb_ready else "  " + DIM + "(not configured)" + NC))
    print(f"  {BOLD}{CYAN}0){NC} Cancel")
    choice = _ask("Choose the export destination", "1")

    smb_options: Optional[Dict[str, str]] = None
    destination = ""
    if choice == "2":
        if not smb_configured(cfg):
            print(f"\n{YELLOW}The SMB share is not configured.{NC}")
            print("Set FAV_EXPORT_SMB_HOST, FAV_EXPORT_SMB_SHARE, FAV_EXPORT_SMB_USER and")
            print("FAV_EXPORT_SMB_PASSWORD (or the TRAKTOR_SMB_* values) in config.env.")
            return 1
        if settings["mount"]:
            print(f"  {BOLD}SMB mount:{NC} {settings['mount']}")
        else:
            print(f"  {BOLD}SMB target:{NC} //{settings['host']}/{settings['share']}")
        settings["path"] = _ask("Folder inside the share (Enter for the share root)", settings.get("path", ""))
        smb_options = {**settings, "kind": "smb"}
    elif choice in ("1", ""):
        destination = _ask("Folder on this drive", str(Path(_expand(cfg.get("FAV_EXPORT_LOCAL_DIR")) or DEFAULT_LOCAL_DIR)))
    else:
        return 0

    history_name = ""
    traktor_playlist = ""
    ready, reason = traktor_ready(cfg)
    if ready:
        print(f"\n{GREEN}Traktor history is ready.{NC}")
        if _yes("Create a Traktor playlist for these favorites too?", True):
            traktor_playlist = _ask("Traktor playlist name", playlist_name)
            history_id = _ask("Traktor history file ID (Enter uses the newest)", "")
            history_name = history_id
    else:
        print(f"\n{DIM}Traktor playlist skipped: {reason}{NC}")

    print(f"\n{CYAN}Exporting {len(tracks)} favorite track(s)...{NC}")
    result = export_favorites(
        tracks,
        destination=destination,
        smb=smb_options,
        tracklist_name=custom_tracklist or None,
        playlist_name=playlist_name,
    )
    if result.get("ok") and traktor_playlist:
        result["traktor"] = create_traktor_playlist(
            [row["path"] for row in tracks], traktor_playlist, history_name, cfg
        )

    print(f"\n{BOLD}{GREEN if result.get('ok') else RED}{'EXPORT COMPLETE' if result.get('ok') else 'EXPORT FAILED'}{NC}")
    for line in summary_lines(result):
        print(f"  {line}")
    if result.get("ok"):
        print(f"\n{BOLD}{GREEN}At least one copied track was verified as playable.{NC}")
    return 0 if result.get("ok") else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the MP Audio Player Favorites playlist for DJ set preparation."
    )
    parser.add_argument("--destination", "-d", help="Local folder for the export")
    parser.add_argument("--smb", action="store_true", help="Export to the configured SMB share")
    parser.add_argument("--smb-path", default=None, help="Folder inside the SMB share")
    parser.add_argument("--tracklist-name", "-n", help="Custom tracklist file name (without .txt)")
    parser.add_argument("--playlist-name", "-p", help="Custom playlist name (default: date + 12 characters)")
    parser.add_argument("--traktor-playlist", help="Also create this Traktor playlist")
    parser.add_argument("--history-id", help="Traktor history index, file name, ID or path")
    parser.add_argument("--yes", "-y", action="store_true", help="Do not prompt")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    parser.add_argument("--list-favorites", action="store_true", help="List the favorites and exit")
    args = parser.parse_args(argv)

    if args.list_favorites:
        tracks = load_favorites()
        if args.json:
            print(json.dumps(tracks, indent=2))
        else:
            for index, track in enumerate(tracks, 1):
                print(f"{index:2d}) {track['name']}  ({track['path']})")
        return 0 if tracks else 1

    if not args.yes and not args.destination and not args.smb:
        try:
            return interactive_main()
        except (KeyboardInterrupt, EOFError):
            print("")
            return 130

    tracks = load_favorites()
    smb_options: Optional[Dict[str, str]] = None
    if args.smb:
        settings = smb_settings()
        if not smb_configured():
            print("The SMB share is not configured in config.env.", file=sys.stderr)
            return 1
        settings["path"] = args.smb_path if args.smb_path is not None else settings.get("path", "")
        smb_options = {**settings, "kind": "smb"}

    result = export_favorites(
        tracks,
        destination=args.destination,
        smb=smb_options,
        tracklist_name=args.tracklist_name,
        playlist_name=args.playlist_name,
    )
    if result.get("ok") and args.traktor_playlist:
        result["traktor"] = create_traktor_playlist(
            [row["path"] for row in tracks],
            args.traktor_playlist,
            args.history_id,
        )
    if args.json:
        printable = {key: value for key, value in result.items() if key != "traktor"}
        if isinstance(printable.get("copied"), list):
            printable["copied"] = [
                {key: value for key, value in row.items() if key in ("source", "dest", "name")}
                for row in printable["copied"]
            ]
        traktor = result.get("traktor")
        if traktor:
            printable["traktor"] = {
                key: value for key, value in traktor.items() if key not in ("tracks",)
            }
        print(json.dumps(printable, indent=2, default=str))
    else:
        print(f"{'EXPORT COMPLETE' if result.get('ok') else 'EXPORT FAILED'}")
        for line in summary_lines(result):
            print(f"  {line}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
