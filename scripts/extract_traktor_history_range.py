#!/usr/bin/env python3
"""
Extract Tracklist from Traktor History Files by Range
Allows extracting a contiguous slice of played tracks (e.g. tracks 95 to 118)
from Traktor Pro history (.nml) files and saving permanently to a mix tracklist file.
"""

import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Colors
NC = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


def find_traktor_history_dirs():
    """Locate all candidate Traktor History directories across platforms and storage."""
    candidates = []

    # Config env value if present
    env_hist = os.environ.get("TRAKTOR_HISTORY_DIR")
    if env_hist and os.path.isdir(env_hist):
        candidates.append(os.path.abspath(env_hist))

    # Known archive / external paths
    for base in [
        "/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE",
        "/Volumes/WD BLACK B/MIX_ARCHIVE",
        "/Volumes/MIX_ARCHIVE",
        os.path.expanduser("~/MIX_ARCHIVE"),
    ]:
        if os.path.isdir(base):
            for p in glob.glob(os.path.join(base, "Traktor*", "History")):
                if os.path.isdir(p):
                    candidates.append(p)

    # Standard user home directories (Linux, macOS, Windows)
    home = Path.home()
    for doc_root in [
        home / "Documents" / "Native Instruments",
        home / "Library" / "Application Support" / "Native Instruments",
        Path("/c/Users") / os.environ.get("USERNAME", "") / "Documents" / "Native Instruments",
    ]:
        if doc_root.is_dir():
            for p in doc_root.glob("Traktor*/History"):
                if p.is_dir():
                    candidates.append(str(p))

    seen = set()
    unique = []
    for c in candidates:
        norm = os.path.normpath(c)
        if norm not in seen and os.path.isdir(norm):
            seen.add(norm)
            unique.append(norm)
    return unique


def list_history_files(limit=30):
    """Return sorted list of Traktor history .nml files (newest first)."""
    hdirs = find_traktor_history_dirs()
    all_files = []
    for d in hdirs:
        for f in glob.glob(os.path.join(d, "history_*.nml")):
            if os.path.isfile(f):
                try:
                    st = os.stat(f)
                    all_files.append({
                        "path": f,
                        "name": os.path.basename(f),
                        "mtime": st.st_mtime,
                        "size": st.st_size,
                    })
                except OSError:
                    continue

    all_files.sort(key=lambda x: x["mtime"], reverse=True)
    return all_files[:limit]


def parse_history_entries(history_file):
    """
    Parse a Traktor history (.nml) file and return a list of tracks in session order.
    Prefers the <PLAYLIST TYPE="PROTOCOL"> node; falls back to <COLLECTION>.
    Each entry: {"artist": str, "title": str, "duration_sec": float, "deck": str}
    """
    if not os.path.isfile(history_file):
        raise FileNotFoundError(f"History file not found: {history_file}")

    tree = ET.parse(history_file)
    root = tree.getroot()

    # Build collection lookup map: key -> (artist, title)
    coll_map = {}
    collection = root.find("COLLECTION")
    if collection is not None:
        for e in collection.findall("ENTRY"):
            loc = e.find("LOCATION")
            art = (e.get("ARTIST") or "").strip()
            tit = (e.get("TITLE") or "").strip()
            if loc is not None:
                v = loc.get("VOLUME") or ""
                d = loc.get("DIR") or ""
                fn = loc.get("FILE") or ""
                key = v + d + fn
                coll_map[key] = (art, tit, fn)

    tracks = []
    pl = root.find(".//PLAYLIST")
    if pl is not None and len(pl.findall("ENTRY")) > 0:
        for pe in pl.findall("ENTRY"):
            pk = pe.find("PRIMARYKEY")
            key = pk.get("KEY", "") if pk is not None else ""
            ext = pe.find("EXTENDEDDATA")
            dur = 0.0
            deck = ""
            if ext is not None:
                try:
                    dur = float(ext.get("DURATION", 0.0))
                except (ValueError, TypeError):
                    dur = 0.0
                deck = ext.get("DECK", "")

            art, tit, fn = coll_map.get(key, ("", "", ""))
            if not tit and not art and fn:
                # Fallback to cleaning filename
                clean = re.sub(r"^\d+[\.\-\s]+", "", os.path.splitext(fn)[0]).strip()
                if " - " in clean:
                    art, tit = clean.split(" - ", 1)
                else:
                    tit = clean

            tracks.append({
                "artist": art.strip(),
                "title": tit.strip(),
                "duration_sec": dur,
                "deck": deck,
                "key": key,
            })
    elif collection is not None:
        for e in collection.findall("ENTRY"):
            art = (e.get("ARTIST") or "").strip()
            tit = (e.get("TITLE") or "").strip()
            tracks.append({
                "artist": art,
                "title": tit,
                "duration_sec": 0.0,
                "deck": "",
                "key": "",
            })

    return tracks


def clean_track_entry(artist, title):
    """Clean up and normalize track artist and title strings."""
    art = (artist or "").strip()
    tit = (title or "").strip()

    # If title begins with "01. " or "01 - " track numbering, clean it (preserve titles like "40 Miles")
    tit = re.sub(r"^\d{1,3}\s*[\.\-]\s+", "", tit)

    # If artist is empty but title has "Artist - Title"
    if not art and " - " in tit:
        parts = tit.split(" - ", 1)
        art = parts[0].strip()
        tit = parts[1].strip()

    # Strip redundant quotes
    art = art.strip("\"'")
    tit = tit.strip("\"'")

    if art and tit:
        return f"{art} - {tit}"
    elif tit:
        return tit
    elif art:
        return art
    return "Unknown Track"


def build_tracklist_content(tracks, start_idx, end_idx, history_file, mix_file=None, mix_title=None):
    """
    Format the complete tracklist text file with release info header and numbered tracks.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    h_bname = os.path.basename(history_file)
    mix_name = mix_title or (os.path.basename(mix_file) if mix_file else "DJ Mix")
    mix_name_clean = os.path.splitext(mix_name)[0]

    slice_tracks = tracks[start_idx - 1 : end_idx]
    count = len(slice_tracks)

    lines = [
        "==================================================",
        "RELEASE INFO & SOURCE MANIFEST",
        "==================================================",
        "Artist:        MPlanetarian",
        "Album:         Stream of Frequency",
        f"Title:         {mix_name_clean}",
        f"Extracted:     {now_str}",
        f"Traktor Source: {h_bname} (Tracks {start_idx} to {end_idx})",
        f"Total Tracks:  {count}",
        "--------------------------------------------------",
    ]
    if mix_file:
        lines.append(f"Associated Mix: {os.path.basename(mix_file)}")
    lines.extend([
        "==================================================",
        "TRACKLIST",
        "==================================================",
    ])

    pad_width = 2 if count < 100 else 3
    for i, t in enumerate(slice_tracks, start=1):
        formatted = clean_track_entry(t.get("artist"), t.get("title"))
        lines.append(f"{i:0{pad_width}d}. {formatted}")

    lines.append("")  # Trailing newline
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract tracklist from Traktor history .nml by range")
    parser.add_argument("--history", "-H", help="Path or full filename of Traktor .nml history file")
    parser.add_argument("--start", "-s", type=int, help="Start track number (1-based, inclusive)")
    parser.add_argument("--end", "-e", type=int, help="End track number (1-based, inclusive)")
    parser.add_argument("--output", "-o", help="Target .txt tracklist output path to save/overwrite permanently")
    parser.add_argument("--mix-file", "-m", help="Path to selected mix audio file")
    parser.add_argument("--mix-title", help="Mix title for tracklist header")
    parser.add_argument("--list-history", action="store_true", help="List recent Traktor history files and exit")
    parser.add_argument("--count", help="Print total track count in a history file and exit")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if args.list_history:
        files = list_history_files()
        if args.json:
            print(json.dumps(files, indent=2))
        else:
            if not files:
                print(f"{YELLOW}No Traktor History (.nml) files found in standard locations.{NC}")
                sys.exit(1)
            print(f"\n{BOLD}{CYAN}Recent Traktor History Files ({len(files)} found):{NC}\n")
            for i, f in enumerate(files, start=1):
                dt = datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
                sz_kb = f["size"] // 1024
                print(f"  {BOLD}{CYAN}[{i:2d}]{NC} {f['name']}  {DIM}({dt}, {sz_kb} KB){NC}")
            print()
        sys.exit(0)

    if args.count:
        h_path = args.count
        if not os.path.isfile(h_path):
            # check candidates
            for d in find_traktor_history_dirs():
                cand = os.path.join(d, h_path)
                if os.path.isfile(cand):
                    h_path = cand
                    break
                if not cand.endswith(".nml") and os.path.isfile(cand + ".nml"):
                    h_path = cand + ".nml"
                    break
        try:
            entries = parse_history_entries(h_path)
            if args.json:
                print(json.dumps({"file": h_path, "count": len(entries)}))
            else:
                print(len(entries))
            sys.exit(0)
        except Exception as exc:
            print(f"{RED}Error reading {h_path}: {exc}{NC}", file=sys.stderr)
            sys.exit(1)

    if not args.history or args.start is None or args.end is None:
        parser.print_help()
        sys.exit(1)

    # Resolve history file with strict validation
    hist_input = args.history.strip()
    h_file = None
    if os.path.isfile(hist_input):
        h_file = os.path.abspath(hist_input)
    else:
        for d in find_traktor_history_dirs():
            cand = os.path.join(d, hist_input)
            if os.path.isfile(cand):
                h_file = cand
                break
            if not cand.endswith(".nml") and os.path.isfile(cand + ".nml"):
                h_file = cand + ".nml"
                break

    if not h_file or not os.path.isfile(h_file):
        print(f"{BOLD}{RED}❌ Error: History file '{hist_input}' not found.{NC}", file=sys.stderr)
        print(f"{YELLOW}You must enter the full exact name of the history file (e.g. history_2026y07m20d_08h01m28s.nml).{NC}", file=sys.stderr)
        sys.exit(1)

    # Parse entries
    try:
        entries = parse_history_entries(h_file)
    except Exception as exc:
        print(f"{BOLD}{RED}❌ Failed to parse Traktor history file: {exc}{NC}", file=sys.stderr)
        sys.exit(1)

    total = len(entries)
    if total == 0:
        print(f"{BOLD}{RED}❌ History file contains 0 tracks.{NC}", file=sys.stderr)
        sys.exit(1)

    start = args.start
    end = args.end
    if start < 1:
        print(f"{BOLD}{RED}❌ Start track must be >= 1 (got {start}).{NC}", file=sys.stderr)
        sys.exit(1)
    if start > end:
        print(f"{BOLD}{RED}❌ Start track ({start}) cannot be greater than end track ({end}).{NC}", file=sys.stderr)
        sys.exit(1)
    if end > total:
        print(f"{BOLD}{YELLOW}⚠️ Note: End track ({end}) exceeds total history tracks ({total}). Clamping to {total}.{NC}")
        end = total

    content = build_tracklist_content(entries, start, end, h_file, mix_file=args.mix_file, mix_title=args.mix_title)

    if args.output:
        out_p = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(out_p), exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"{BOLD}{GREEN}✔ Successfully extracted {end - start + 1} tracks to:{NC} {out_p}")
    else:
        print(content)


if __name__ == "__main__":
    main()
