#!/usr/bin/env python3
"""
mp_tracklist_analyzer.py - Master Tracklist HTML & Multi-Folder Analytics Engine
Part of MP_Mix_Manager_v0.3

Extracts, parses, and performs deep analytics on master_tracklists.html,
analyzing mixes across archive folders, tracks played per day, top artists,
durations, and storage footprints.
"""

import os
import sys
import re
import html
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from collections import defaultdict, Counter

SCRIPT_DIR = Path(__file__).resolve().parent.parent

try:
    from scripts.mp_logging import log_error as mp_log_error
except ImportError:
    try:
        from mp_logging import log_error as mp_log_error
    except ImportError:
        def mp_log_error(c, m, e=None, d=None):
            pass

def find_master_tracklist_html() -> Optional[Path]:
    """Locate master_tracklists.html in workspace or parent paths."""
    candidates = [
        SCRIPT_DIR / "master_tracklists.html",
        SCRIPT_DIR.parent / "master_tracklists.html",
        Path.home() / "master_tracklists.html"
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 100:
            return c
    return None

def parse_duration_to_seconds(dur_str: str) -> float:
    """Convert HH:MM:SS or MM:SS to seconds."""
    parts = dur_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:
            return float(parts[0])
    except Exception:
        pass
    return 0.0

def parse_size_to_gb(size_str: str) -> float:
    """Convert '2.14 GB' or '500 MB' or bytes string to float GB."""
    s = size_str.upper().strip()
    try:
        if "GB" in s:
            return float(s.replace("GB", "").strip())
        elif "MB" in s:
            return float(s.replace("MB", "").strip()) / 1024.0
        elif "TB" in s:
            return float(s.replace("TB", "").strip()) * 1024.0
        elif "BYTES" in s:
            return float(s.replace("BYTES", "").strip()) / (1024.0 ** 3)
        return float(s)
    except Exception:
        return 0.0

def parse_artist_and_title(raw_track: str) -> Tuple[str, str]:
    """Parse track string into (artist, title)."""
    clean = html.unescape(raw_track).strip()
    # Strip leading track numbers like '01.', '1 -', etc.
    clean = re.sub(r'^\d+[\.\-\s]+', '', clean).strip()
    if " - " in clean:
        parts = clean.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    elif " — " in clean:
        parts = clean.split(" — ", 1)
        return parts[0].strip(), parts[1].strip()
    elif ":" in clean:
        parts = clean.split(":", 1)
        return parts[0].strip(), parts[1].strip()
    return "Unknown Artist", clean

class MasterTracklistAnalyzer:
    def __init__(self, html_path: Optional[Path] = None):
        self.html_path = html_path or find_master_tracklist_html()
        self.raw_stats: Dict[str, str] = {}
        self.mixes: List[Dict[str, Any]] = []
        self.folder_stats: Dict[str, Dict[str, Any]] = {}
        self.artist_counts: Counter = Counter()
        self.daily_track_counts: Dict[str, int] = defaultdict(int)
        self.daily_mix_counts: Dict[str, int] = defaultdict(int)
        self.tracks_list: List[str] = []
        self._parsed = False

    def parse(self) -> bool:
        if not self.html_path or not self.html_path.exists():
            mp_log_error("TracklistAnalyzer", "master_tracklists.html not found.")
            return False

        try:
            with open(self.html_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # 1. Parse stats box
            stat_items = re.findall(
                r'<div class=\"stat-val\">(.*?)</div>\s*<div class=\"stat-lbl\">(.*?)</div>',
                content
            )
            for val, lbl in stat_items:
                self.raw_stats[lbl.strip()] = val.strip()

            # 2. Parse mix cards
            cards = re.findall(
                r'<div class=\"mix-card\">(.*?)</div>\s*(?=<div class=\"mix-card\"|</div>\s*</body>)',
                content,
                re.DOTALL
            )

            folder_data = defaultdict(lambda: {"mix_count": 0, "size_gb": 0.0, "duration_sec": 0.0, "track_count": 0, "path": ""})

            for card in cards:
                # Heading & size
                heading_match = re.search(r'<div class=\"mix-heading\">(.*?)</div>', card, re.DOTALL)
                heading_raw = heading_match.group(1).strip() if heading_match else ""
                
                # Extract archive badge
                badge_match = re.search(r'<span class=\"badge-arch\">(.*?)</span>', heading_raw)
                archive_name = badge_match.group(1).strip() if badge_match else "Primary Archive"
                title_line = re.sub(r'<span class=\"badge-arch\">.*?</span>', '', heading_raw).strip()

                # Extract size from title_line e.g. "(2.14 GB)"
                size_match = re.search(r'\(([\d\.]+\s*(?:GB|MB|bytes))\)', title_line)
                size_gb = parse_size_to_gb(size_match.group(1)) if size_match else 0.0

                # Meta lines: Storage Archive, Recording Date, Duration, Local Filename
                meta_dict = {}
                for lbl, val in re.findall(r'<div class=\"meta-line\"><span class=\"meta-label\">(.*?):</span>\s*(.*?)</div>', card):
                    clean_val = re.sub(r'<[^>]+>', '', val).strip()
                    meta_dict[lbl.strip()] = clean_val
                    if lbl.strip() == "Storage Archive" and "(" in clean_val:
                        path_match = re.search(r'\((.*?)\)', clean_val)
                        if path_match:
                            folder_data[archive_name]["path"] = path_match.group(1).strip()

                date_val = meta_dict.get("Recording Date", "Unknown")
                dur_str = meta_dict.get("Duration", "00:00:00")
                dur_sec = parse_duration_to_seconds(dur_str)

                # Tracklist
                tracks = [html.unescape(t.strip()) for t in re.findall(r'<li class=\"track-item\">(.*?)</li>', card)]

                for trk in tracks:
                    self.tracks_list.append(trk)
                    art, tit = parse_artist_and_title(trk)
                    if art and art != "Unknown Artist":
                        self.artist_counts[art] += 1

                # Update daily maps if date is recognized
                if date_val != "Unknown" and re.match(r'^\d{4}-\d{2}-\d{2}$', date_val):
                    self.daily_track_counts[date_val] += len(tracks)
                    self.daily_mix_counts[date_val] += 1

                # Update folder stats
                folder_data[archive_name]["mix_count"] += 1
                folder_data[archive_name]["size_gb"] += size_gb
                folder_data[archive_name]["duration_sec"] += dur_sec
                folder_data[archive_name]["track_count"] += len(tracks)

                self.mixes.append({
                    "title": title_line,
                    "archive_name": archive_name,
                    "size_gb": round(size_gb, 2),
                    "duration_sec": dur_sec,
                    "date": date_val,
                    "track_count": len(tracks),
                    "tracks": tracks
                })

            # Finalize folder stats
            total_gb = sum(d["size_gb"] for d in folder_data.values()) or 1.0
            for k, v in folder_data.items():
                v["size_gb"] = round(v["size_gb"], 2)
                v["duration_hours"] = round(v["duration_sec"] / 3600.0, 1)
                v["percentage"] = round((v["size_gb"] / total_gb) * 100.0, 1)
                self.folder_stats[k] = dict(v)

            self._parsed = True
            return True

        except Exception as e:
            mp_log_error("TracklistAnalyzer", f"Error parsing HTML: {e}", e)
            return False

    def get_summary_report(self) -> Dict[str, Any]:
        """Produce comprehensive analytics dictionary."""
        if not self._parsed:
            self.parse()

        total_mixes = len(self.mixes) or int(self.raw_stats.get("Total Mixes", 0))
        total_tracks = len(self.tracks_list) or int(self.raw_stats.get("Total Tracks Played", 0))
        total_size_gb = sum(d["size_gb"] for d in self.folder_stats.values()) if self.folder_stats else parse_size_to_gb(self.raw_stats.get("Combined Size", "0 GB"))
        total_sec = sum(m["duration_sec"] for m in self.mixes) if self.mixes else 0.0

        top_artists = self.artist_counts.most_common(20)

        # Mix duration stats
        durations = [m["duration_sec"] / 3600.0 for m in self.mixes if m["duration_sec"] > 0]
        avg_duration_h = round(sum(durations) / len(durations), 2) if durations else 0.0
        max_duration_h = round(max(durations), 2) if durations else 0.0
        min_duration_h = round(min(durations), 2) if durations else 0.0

        # Tracks per mix stats
        track_counts = [m["track_count"] for m in self.mixes if m["track_count"] > 0]
        avg_tracks_per_mix = round(sum(track_counts) / len(track_counts), 1) if track_counts else 0.0

        # Recent daily tracks played
        sorted_dates = sorted(self.daily_track_counts.keys(), reverse=True)
        recent_daily_plays = [{"date": d, "tracks": self.daily_track_counts[d], "mixes": self.daily_mix_counts[d]} for d in sorted_dates[:14]]

        return {
            "html_source": str(self.html_path),
            "total_mixes": total_mixes,
            "total_tracks_played": total_tracks,
            "verified_tracklists": self.raw_stats.get("Verified Tracklists", "N/A"),
            "combined_size_gb": round(total_size_gb, 2),
            "total_duration_hours": round(total_sec / 3600.0, 1),
            "total_duration_str": self.raw_stats.get("Total Mixing Duration", f"{round(total_sec/3600.0, 1)}h"),
            "avg_mix_duration_hours": avg_duration_h,
            "max_mix_duration_hours": max_duration_h,
            "min_mix_duration_hours": min_duration_h,
            "avg_tracks_per_mix": avg_tracks_per_mix,
            "unique_artists_count": len(self.artist_counts),
            "top_artists": top_artists,
            "folder_stats": self.folder_stats,
            "recent_daily_plays": recent_daily_plays
        }

if __name__ == "__main__":
    analyzer = MasterTracklistAnalyzer()
    if analyzer.parse():
        s = analyzer.get_summary_report()
        print("=== Master Tracklist HTML Analytics ===")
        print(f"Total Mixes:          {s['total_mixes']}")
        print(f"Total Tracks Played:  {s['total_tracks_played']}")
        print(f"Combined Size:        {s['combined_size_gb']} GB")
        print(f"Total Duration:       {s['total_duration_str']}")
        print(f"Unique Artists:       {s['unique_artists_count']}")
        print("\nStorage Archive Folders:")
        for name, data in s['folder_stats'].items():
            print(f"  • {name}: {data['mix_count']} mixes, {data['size_gb']} GB ({data['percentage']}%), {data['track_count']} tracks")
        print("\nTop 5 Artists Played:")
        for art, cnt in s['top_artists'][:5]:
            print(f"  • {art}: {cnt} tracks")
    else:
        print("Failed to parse master_tracklists.html")
