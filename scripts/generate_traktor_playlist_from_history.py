#!/usr/bin/env python3
"""
scripts/generate_traktor_playlist_from_history.py - Traktor Playlist Generator

Builds a Traktor playlist from a Traktor Pro History (.nml) session and inserts
it into collection.nml under the default $ROOT playlist folder.

The same helpers are imported by MP_Fav_Playlist_Track_Exporter.py so the
Favorites exporter can create a playlist for the exact tracks it just copied.

Interactive use (Manager menu option 17 > 3):
    python3 scripts/generate_traktor_playlist_from_history.py

Headless use:
    python3 scripts/generate_traktor_playlist_from_history.py \
        --history-id history_2026y07m20d_08h01m28s.nml \
        --playlist-name "Favourites 2026-11-12"
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
CONFIG_CANDIDATES = (
    APP_DIR / "config.env",
    Path(__file__).resolve().parent / "config.env",
    Path.cwd() / "config.env",
    Path.home() / ".config" / "mix-manager" / "config.env",
)


# ------------------------------------------------------------------------------
# Configuration and Traktor discovery
# ------------------------------------------------------------------------------
def load_config() -> Dict[str, str]:
    """Read config.env values, then let real environment variables win."""
    cfg: Dict[str, str] = {}
    for candidate in CONFIG_CANDIDATES:
        if not candidate.is_file():
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


def _expand(value: Optional[str]) -> str:
    return os.path.expandvars(os.path.expanduser(str(value or "").strip().strip('"').strip("'")))


def _candidate_dirs(cfg: Dict[str, str]) -> List[str]:
    """Likely roots that hold a Traktor user folder or synced History folder."""
    candidates: List[str] = []
    for key in (
        "TRAKTOR_HISTORY_DIR",
        "TRAKTOR_AUDIO_ROOT",
        "MIX_ARCHIVE_DIR",
        "TRAKTOR_SMB_MOUNT",
        "TRAKTOR_NFS_MOUNT",
    ):
        value = _expand(cfg.get(key, ""))
        if value:
            candidates.append(value)
    candidates.extend(
        [
            str(Path.home() / "Documents" / "Native Instruments"),
            str(Path.home() / "Library" / "Application Support" / "Native Instruments"),
            str(Path.home() / "Music" / "Native Instruments"),
            str(APP_DIR / "MIX_ARCHIVE"),
            "/Volumes/MIX_ARCHIVE",
            "/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE",
        ]
    )
    unique: List[str] = []
    for value in candidates:
        if value and os.path.isdir(value) and value not in unique:
            unique.append(value)
    return unique


def find_collection_path(cfg: Optional[Dict[str, str]] = None) -> Optional[Path]:
    cfg = cfg or load_config()
    configured = _expand(cfg.get("TRAKTOR_COLLECTION_PATH", ""))
    if configured and os.path.isfile(configured):
        return Path(configured).resolve()

    patterns = [
        "Traktor*/collection.nml",
        "Native Instruments/Traktor*/collection.nml",
        "*/History/../collection.nml",
    ]
    found: List[Path] = []
    for root in _candidate_dirs(cfg):
        for pattern in patterns:
            for match in glob.glob(os.path.join(root, pattern)):
                if os.path.isfile(match):
                    found.append(Path(match).resolve())
    if not found:
        return None
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0]


def find_traktor_user_dir(cfg: Optional[Dict[str, str]] = None) -> Optional[Path]:
    collection = find_collection_path(cfg)
    if collection:
        return collection.parent
    dirs: List[Path] = []
    for root in _candidate_dirs(cfg or load_config()):
        for match in glob.glob(os.path.join(root, "Traktor*")):
            path = Path(match)
            if path.is_dir() and (path / "History").is_dir():
                dirs.append(path)
    if not dirs:
        return None
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dirs[0]


def find_history_dirs(
    cfg: Optional[Dict[str, str]] = None,
    extra: Optional[Iterable[str]] = None,
) -> List[Path]:
    cfg = cfg or load_config()
    candidates: List[str] = []
    configured = _expand(cfg.get("TRAKTOR_HISTORY_DIR", ""))
    if configured:
        candidates.append(configured)
    user_dir = find_traktor_user_dir(cfg)
    if user_dir:
        candidates.append(str(user_dir / "History"))
    for root in _candidate_dirs(cfg):
        candidates.extend(glob.glob(os.path.join(root, "Traktor*/History")))
        candidates.extend(glob.glob(os.path.join(root, "**", "Traktor*/History"), recursive=False))
    candidates.extend(_expand(value) for value in (extra or []))
    unique: List[Path] = []
    for value in candidates:
        if not value:
            continue
        path = Path(value)
        if path.is_dir():
            resolved = path.resolve()
            if resolved not in unique:
                unique.append(resolved)
    return unique


def _search_dirs(
    history_dirs: Optional[Iterable[str]], cfg: Optional[Dict[str, str]]
) -> List[Path]:
    """Explicit directories are authoritative; otherwise every known folder."""
    if history_dirs is not None:
        explicit: List[Path] = []
        for value in history_dirs:
            path = Path(_expand(str(value)))
            if path.is_dir() and path.resolve() not in explicit:
                explicit.append(path.resolve())
        return explicit
    return find_history_dirs(cfg)


def list_history_files(
    limit: int = 30,
    history_dirs: Optional[Iterable[str]] = None,
    cfg: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    cfg = cfg or load_config()
    files: List[Dict[str, Any]] = []
    for directory in _search_dirs(history_dirs, cfg):
        for path in sorted(Path(directory).glob("history_*.nml")):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            match = re.search(
                r"history_(\d{4})y(\d{2})m(\d{2})d_(\d{2})h(\d{2})m(\d{2})s", path.name
            )
            stamp = (
                f"{match.group(1)}-{match.group(2)}-{match.group(3)} "
                f"{match.group(4)}:{match.group(5)}:{match.group(6)}"
                if match
                else "Unknown Date"
            )
            files.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "id": path.stem,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "datetime": stamp,
                    "dir": str(Path(directory)),
                }
            )
    files.sort(key=lambda row: row["mtime"], reverse=True)
    return files[:limit]


def preferred_history_dirs(
    collection_path: Optional[Path], cfg: Optional[Dict[str, str]] = None
) -> List[str]:
    """History folders that belong to the Traktor collection being written.

    When the collection has a sibling History folder (a normal Traktor user
    folder, or the folder a synced history tree was copied into) that folder is
    authoritative. Otherwise every discovered History folder is used.
    """
    if collection_path:
        sibling = Path(collection_path).parent / "History"
        if sibling.is_dir():
            return [str(sibling)]
    return [str(path) for path in find_history_dirs(cfg)]


def resolve_history_file(
    history_id: Optional[str],
    history_dirs: Optional[Iterable[str]] = None,
    cfg: Optional[Dict[str, str]] = None,
) -> Optional[Path]:
    """Resolve a history file from an index, full path, ID or filename."""
    files = list_history_files(limit=500, history_dirs=history_dirs, cfg=cfg)
    if not files:
        return None
    raw = (history_id or "").strip().strip('"').strip("'")
    if not raw:
        return Path(files[0]["path"])
    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(files):
            return Path(files[index]["path"])
        return None
    expanded = Path(_expand(raw))
    if expanded.is_file():
        return expanded.resolve()
    lowered = raw.lower()
    basename = os.path.basename(lowered)
    for row in files:
        if row["name"].lower() == basename or row["id"].lower() == basename:
            return Path(row["path"])
    for row in files:
        if lowered in row["name"].lower() or lowered in row["id"].lower():
            return Path(row["path"])
    for directory in _search_dirs(history_dirs, cfg):
        candidate = Path(directory) / raw
        if candidate.is_file():
            return candidate.resolve()
        if not raw.endswith(".nml") and candidate.with_suffix(".nml").is_file():
            return candidate.with_suffix(".nml").resolve()
    return None


def is_traktor_running() -> bool:
    if not sys.platform.startswith(("darwin", "linux", "freebsd")):
        return False
    try:
        return bool(subprocess.check_output(["pgrep", "-x", "Traktor"], stderr=subprocess.DEVNULL).strip())
    except Exception:
        return False


def quit_traktor() -> bool:
    """Close Traktor cleanly so it flushes collection.nml before we write it."""
    if not is_traktor_running():
        return True
    if sys.platform == "darwin":
        try:
            subprocess.run(["osascript", "-e", 'tell application "Traktor" to quit'], check=False)
        except Exception:
            pass
        for _ in range(20):
            if not is_traktor_running():
                return True
            time.sleep(0.5)
    return not is_traktor_running()


# ------------------------------------------------------------------------------
# NML parsing
# ------------------------------------------------------------------------------
def _decode_name(value: str) -> str:
    try:
        return urllib.parse.unquote(str(value or ""))
    except Exception:
        return str(value or "")


def _make_track(entry: ET.Element) -> Dict[str, Any]:
    location = entry.find("LOCATION")
    volume = location.attrib.get("VOLUME", "") if location is not None else ""
    directory = location.attrib.get("DIR", "") if location is not None else ""
    filename = location.attrib.get("FILE", "") if location is not None else ""
    pkey = f"{volume}{directory}{filename}"
    info = entry.find("INFO")
    musical_key = entry.find("MUSICAL_KEY")
    tempo = entry.find("TEMPO")

    key_value = ""
    if info is not None:
        key_value = str(info.attrib.get("KEY", "") or "")
    musical_value = -1
    if musical_key is not None:
        try:
            musical_value = int(musical_key.attrib.get("VALUE", -1))
        except (TypeError, ValueError):
            musical_value = -1
    bpm = 0.0
    if tempo is not None:
        try:
            bpm = float(tempo.attrib.get("BPM", 0.0) or 0.0)
        except (TypeError, ValueError):
            bpm = 0.0
    duration = 0
    if info is not None:
        try:
            duration = int(float(info.attrib.get("PLAYTIME", 0) or 0))
        except (TypeError, ValueError):
            duration = 0
    return {
        "title": str(entry.attrib.get("TITLE", "") or "").strip(),
        "artist": str(entry.attrib.get("ARTIST", "") or "").strip(),
        "key": key_value,
        "mval": musical_value,
        "bpm": bpm,
        "duration": duration,
        "pkey": pkey,
        "entry_elem": entry,
        "file": _decode_name(filename),
        "basename": os.path.basename(_decode_name(filename)).casefold(),
    }


def _index_tracks(root: ET.Element) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_pkey: Dict[str, Dict[str, Any]] = {}
    by_basename: Dict[str, Dict[str, Any]] = {}
    collection = root.find("COLLECTION")
    scope = collection if collection is not None else root
    for entry in scope.findall("ENTRY"):
        track = _make_track(entry)
        if not track["pkey"]:
            continue
        by_pkey[track["pkey"]] = track
        if track["basename"] and track["basename"] not in by_basename:
            by_basename[track["basename"]] = track
    return by_pkey, by_basename


def parse_history_file(history_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Return the session tracks in play order plus the session lookup tables."""
    tree = ET.parse(history_path)
    root = tree.getroot()
    by_pkey, by_basename = _index_tracks(root)
    ordered: List[Dict[str, Any]] = []
    seen: set = set()
    playlist = root.find(".//PLAYLIST")
    if playlist is not None:
        for entry in playlist.findall("ENTRY"):
            primary = entry.find("PRIMARYKEY")
            if primary is None:
                continue
            key = primary.attrib.get("KEY", "")
            track = by_pkey.get(key)
            if track is None:
                decoded = _decode_name(key)
                basename = os.path.basename(decoded).casefold()
                track = by_basename.get(basename)
                if track is None:
                    track = {
                        "title": os.path.basename(decoded),
                        "artist": "",
                        "key": "",
                        "mval": -1,
                        "bpm": 0.0,
                        "duration": 0,
                        "pkey": key,
                        "entry_elem": None,
                        "file": basename,
                        "basename": basename,
                    }
            if track["pkey"] in seen:
                continue
            seen.add(track["pkey"])
            ordered.append(track)
    return ordered, by_basename


def load_collection_index(collection_path: str) -> Dict[str, Dict[str, Any]]:
    tree = ET.parse(collection_path)
    _, by_basename = _index_tracks(tree.getroot())
    return by_basename


def key_sort_rank(track: Dict[str, Any]) -> Tuple:
    """Key Field Ascending: Camelot/Open Key first, then musical key value."""
    key = str(track.get("key") or "").strip()
    match = re.match(r"^(\d{1,2})([a-zA-Z]?)$", key)
    if match:
        return (0, int(match.group(1)), match.group(2).lower(), track.get("title", ""))
    value = int(track.get("mval", -1) or -1)
    if value >= 0:
        return (1, value, "", track.get("title", ""))
    if key:
        return (2, key.lower(), "", track.get("title", ""))
    return (3, 999, "", track.get("title", ""))


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


# ------------------------------------------------------------------------------
# Collection writing
# ------------------------------------------------------------------------------
def insert_playlist_into_collection(
    collection_path: str,
    playlist_name: str,
    sorted_tracks: Sequence[Dict[str, Any]],
) -> Tuple[bool, str]:
    """Insert or replace a playlist in collection.nml and back up the original."""
    path = Path(collection_path)
    if not path.is_file():
        return False, f"collection.nml not found at {path}"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(path.name + f".bak_{stamp}")
    try:
        shutil.copy2(path, backup)
    except OSError as exc:
        return False, f"Could not back up collection.nml: {exc}"

    try:
        tree = ET.parse(path)
    except Exception as exc:
        return False, f"Could not parse collection.nml: {exc}"
    root = tree.getroot()

    playlists_node = root.find("PLAYLISTS")
    if playlists_node is None:
        playlists_node = ET.SubElement(root, "PLAYLISTS")
    root_folder = None
    for node in playlists_node.findall("NODE"):
        if node.attrib.get("TYPE") == "FOLDER" and node.attrib.get("NAME") == "$ROOT":
            root_folder = node
            break
    if root_folder is None:
        root_folder = ET.SubElement(playlists_node, "NODE", {"TYPE": "FOLDER", "NAME": "$ROOT"})
    subnodes = root_folder.find("SUBNODES")
    if subnodes is None:
        subnodes = ET.SubElement(root_folder, "SUBNODES")

    for node in list(subnodes.findall("NODE")):
        if node.attrib.get("TYPE") == "PLAYLIST" and node.attrib.get("NAME") == playlist_name:
            subnodes.remove(node)

    playlist_node = ET.SubElement(subnodes, "NODE", {"TYPE": "PLAYLIST", "NAME": playlist_name})
    playlist_content = ET.SubElement(
        playlist_node,
        "PLAYLIST",
        {"ENTRIES": str(len(sorted_tracks)), "TYPE": "LIST", "UUID": uuid.uuid4().hex},
    )

    collection_node = root.find("COLLECTION")
    existing_keys: set = set()
    if collection_node is not None:
        for entry in collection_node.findall("ENTRY"):
            location = entry.find("LOCATION")
            if location is not None:
                existing_keys.add(
                    f"{location.attrib.get('VOLUME', '')}"
                    f"{location.attrib.get('DIR', '')}"
                    f"{location.attrib.get('FILE', '')}"
                )

    added_to_collection = 0
    for track in sorted_tracks:
        entry = ET.SubElement(playlist_content, "ENTRY")
        ET.SubElement(entry, "PRIMARYKEY", {"TYPE": "TRACK", "KEY": track["pkey"]})
        if (
            collection_node is not None
            and track["pkey"] not in existing_keys
            and track.get("entry_elem") is not None
        ):
            collection_node.append(copy.deepcopy(track["entry_elem"]))
            existing_keys.add(track["pkey"])
            added_to_collection += 1

    if collection_node is not None:
        collection_node.attrib["ENTRIES"] = str(len(collection_node.findall("ENTRY")))
    if subnodes is not None:
        subnodes.attrib["COUNT"] = str(len(subnodes.findall("NODE")))

    temp = path.with_name(path.name + ".tmp")
    try:
        tree.write(temp, encoding="utf-8", xml_declaration=True)
        temp.replace(path)
    except Exception as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            shutil.copy2(backup, path)
        except OSError:
            pass
        return False, f"Could not write collection.nml: {exc}"

    return True, (
        f"Playlist '{playlist_name}' written with {len(sorted_tracks)} tracks "
        f"({added_to_collection} added to the collection). Backup: {backup.name}"
    )


def build_traktor_playlist(
    favorite_paths: Sequence[str],
    history_id: Optional[str] = None,
    playlist_name: Optional[str] = None,
    collection_path: Optional[str] = None,
    history_dirs: Optional[Iterable[str]] = None,
    cfg: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a Traktor playlist for the files that exist in Traktor.

    The history file is the session the user prepared before exporting, so its
    key/BPM metadata wins. Favorites that are not in that session are looked up
    in the full collection instead. Returns a result dictionary for CLI/UI use.
    """
    cfg = cfg or load_config()
    collection = Path(collection_path) if collection_path else find_collection_path(cfg)
    if not collection or not collection.is_file():
        return {
            "ok": False,
            "reason": "collection",
            "message": "collection.nml was not found. Run Traktor once and choose the collection path first.",
        }
    history = resolve_history_file(
        history_id,
        history_dirs=history_dirs or preferred_history_dirs(collection, cfg),
        cfg=cfg,
    )
    if not history or not history.is_file():
        return {
            "ok": False,
            "reason": "history",
            "message": "No Traktor History (.nml) files are available. Sync your Traktor history first.",
        }
    if is_traktor_running():
        return {
            "ok": False,
            "reason": "running",
            "message": "Traktor is running. Close Traktor cleanly, then create the playlist.",
        }

    try:
        _, history_index = parse_history_file(str(history))
        collection_index = load_collection_index(str(collection))
    except Exception as exc:
        return {"ok": False, "reason": "parse", "message": f"Could not parse Traktor data: {exc}"}

    matched: List[Dict[str, Any]] = []
    missing: List[str] = []
    seen: set = set()
    for file_path in favorite_paths:
        basename = os.path.basename(str(file_path)).casefold()
        track = history_index.get(basename) or collection_index.get(basename)
        if not track:
            missing.append(os.path.basename(str(file_path)))
            continue
        if track["pkey"] in seen:
            continue
        seen.add(track["pkey"])
        matched.append(track)

    if not matched:
        return {
            "ok": False,
            "reason": "no_match",
            "message": (
                f"None of the favorites were found in {history.name} or the Traktor collection. "
                "Choose a history file from the session where those tracks were imported."
            ),
            "missing": missing,
        }

    matched.sort(key=key_sort_rank)
    name = (playlist_name or "").strip() or f"MP Favorites {time.strftime('%Y-%m-%d')}"
    ok, message = insert_playlist_into_collection(str(collection), name, matched)
    return {
        "ok": ok,
        "reason": "written" if ok else "write",
        "message": message,
        "playlist": name,
        "history": history.name,
        "collection": str(collection),
        "matched": len(matched),
        "missing": missing,
        "tracks": matched,
    }


# ------------------------------------------------------------------------------
# Interactive generator (Manager menu option 17 > 3)
# ------------------------------------------------------------------------------
def _print_session(tracks: Sequence[Dict[str, Any]]) -> None:
    print(f" {BOLD}{'#':<4}{'KEY':<6}{'BPM':<8}{'TIME':<8}{'ARTIST':<30}{'TITLE':<40}{NC}")
    print(f"{BLUE}{'-' * 96}{NC}")
    for index, track in enumerate(tracks, 1):
        key = track.get("key") or (f"K{track['mval']}" if track.get("mval", -1) >= 0 else "-")
        bpm = f"{track['bpm']:.1f}" if track.get("bpm", 0) > 0 else "-"
        print(
            f" {index:<4}{key:<6}{bpm:<8}{format_duration(track.get('duration', 0)):<8}"
            f"{(track.get('artist') or '-')[:28]:<30}{(track.get('title') or '-')[:38]:<40}"
        )
    print(f"{BLUE}{'-' * 96}{NC}")


def interactive_main() -> int:
    cfg = load_config()
    collection = find_collection_path(cfg)
    history_dirs = find_history_dirs(cfg)
    history_files = list_history_files(30, [str(d) for d in history_dirs], cfg=cfg)

    os.system("clear 2>/dev/null || true")
    print(f"{BOLD}{MAGENTA}{'=' * 83}{NC}")
    print(f"{BOLD}{MAGENTA}     TRAKTOR PLAYLIST FROM HISTORY FILES - KEY SORTED / DECKS READY        {NC}")
    print(f"{BOLD}{MAGENTA}{'=' * 83}{NC}")
    print(f"  {BOLD}Collection:{NC}   {collection or 'Not found'}")
    for directory in history_dirs:
        print(f"  {BOLD}History:{NC}      {directory}")
    print(f"  {BOLD}History files:{NC} {len(history_files)}")
    print(f"{BLUE}{'-' * 83}{NC}\n")

    if not collection:
        print(f"{YELLOW}No collection.nml found. Set TRAKTOR_COLLECTION_PATH in config.env.{NC}")
        return 1
    if not history_files:
        print(f"{YELLOW}No Traktor History (.nml) files found. Sync the Traktor history first.{NC}")
        return 1

    for index, row in enumerate(history_files, 1):
        print(f"  {BOLD}{CYAN}{index:2d}){NC} {row['datetime']}  {DIM}{row['name']}{NC}")

    print(f"\n  {BOLD}[Q]{NC} Return")
    choice = input(f"Select a history file [1-{len(history_files)}, Q]: ").strip()
    if choice.lower() in ("q", "", "0"):
        return 0
    history = resolve_history_file(choice, [str(d) for d in history_dirs], cfg=cfg)
    if not history:
        print(f"{RED}Invalid history selection.{NC}")
        return 1

    try:
        session, _ = parse_history_file(str(history))
    except Exception as exc:
        print(f"{RED}Could not read {history.name}: {exc}{NC}")
        return 1
    if not session:
        print(f"{RED}No tracks found in {history.name}.{NC}")
        return 1

    sorted_session = sorted(session, key=key_sort_rank)
    os.system("clear 2>/dev/null || true")
    print(f"{BOLD}{CYAN}History: {history.name}  ({len(session)} tracks){NC}\n")
    _print_session(sorted_session)
    print(f"\n{BOLD}{YELLOW}First four tracks in Key Ascending order are ready for Decks A-D.{NC}")
    commit = input("Generate this playlist in Traktor now? [Y/n]: ").strip().lower()
    if commit not in ("", "y", "yes"):
        print(f"{YELLOW}Cancelled.{NC}")
        return 0
    default_name = f"SOF Mix {time.strftime('%Y-%m-%d')}"
    match = re.search(r"history_(\d{4})y(\d{2})m(\d{2})d_(\d{2})h(\d{2})m", history.name)
    if match:
        default_name = (
            f"SOF Mix {match.group(1)}-{match.group(2)}-{match.group(3)} "
            f"({match.group(4)}h{match.group(5)}m)"
        )
    name = input(f"Traktor playlist name [{default_name}]: ").strip() or default_name

    if is_traktor_running():
        print(f"{YELLOW}Traktor is running. It must be closed so collection.nml is not overwritten.{NC}")
        if input("Close Traktor now? [Y/n]: ").strip().lower() in ("", "y", "yes"):
            if not quit_traktor():
                print(f"{RED}Could not close Traktor. Close it manually and try again.{NC}")
                return 1
        else:
            return 1

    import copy as _copy

    ok, message = insert_playlist_into_collection(
        str(collection), name, [_copy.deepcopy(track) for track in sorted_session]
    )
    if ok:
        print(f"\n{BOLD}{GREEN}{message}{NC}")
        print(f"{GREEN}Open Traktor and the playlist will be in the default Playlists folder.{NC}")
        return 0
    print(f"\n{RED}{message}{NC}")
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Traktor playlist from a History .nml session.")
    parser.add_argument("--version-only", action="store_true", help="Print the detected Traktor version and exit")
    parser.add_argument("--list-history", action="store_true", help="List available history .nml files and exit")
    parser.add_argument("--json", action="store_true", help="Machine-readable output for --list-history")
    parser.add_argument("--history-id", "-H", help="History index, file name, ID or path")
    parser.add_argument("--playlist-name", "-n", help="Name of the Traktor playlist")
    parser.add_argument("--collection", help="Path to collection.nml")
    parser.add_argument("--history-dir", action="append", default=[], help="Extra History directory (repeatable)")
    parser.add_argument("--track", "-t", action="append", default=[], help="File to include (repeatable)")
    args = parser.parse_args(argv)

    if args.version_only:
        user_dir = find_traktor_user_dir()
        match = re.search(r"Traktor\s+([0-9][0-9.]*)", str(user_dir or ""))
        print(match.group(1) if match else "3")
        return 0

    if args.list_history:
        rows = list_history_files(500, args.history_dir)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for index, row in enumerate(rows, 1):
                print(f"{index:2d}) {row['datetime']}  {row['name']}  ({row['size'] // 1024} KB)")
        return 0 if rows else 1

    if args.track or args.playlist_name or args.history_id:
        if not args.track:
            history = resolve_history_file(args.history_id, args.history_dir)
            if not history:
                print(
                    "A Traktor History file is required. Pass --history-id or sync the history first.",
                    file=sys.stderr,
                )
                return 1
            try:
                session, _ = parse_history_file(str(history))
            except Exception as exc:
                print(f"Could not read {history.name}: {exc}", file=sys.stderr)
                return 1
            paths = [track.get("file") or track.get("basename") for track in session]
            paths = [value for value in paths if value]
        else:
            paths = list(args.track)
            history = resolve_history_file(args.history_id, args.history_dir)
            if args.history_id and not history:
                print(f"Traktor history '{args.history_id}' was not found.", file=sys.stderr)
                return 1

        result = build_traktor_playlist(
            paths,
            history_id=str(history) if history else args.history_id,
            playlist_name=args.playlist_name,
            collection_path=args.collection,
            history_dirs=args.history_dir,
        )
        if args.json:
            serializable = {key: value for key, value in result.items() if key != "tracks"}
            print(json.dumps(serializable, indent=2))
        else:
            print(result["message"])
        return 0 if result.get("ok") else 1

    try:
        return interactive_main()
    except (KeyboardInterrupt, EOFError):
        print("")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
