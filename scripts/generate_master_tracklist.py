"""
This script scans a set of directories for audio mix archives, processes the contents, and generates a comprehensive HTML index page listing all tracks with associated metadata. The script also provides statistics about the total mixes, verified tracklists, combined size, total tracks played, and total mixing duration. Additionally, it attempts to automatically open the generated HTML file in a web browser for easy viewing.
"""

import os
import sys
import re
import html
import logging
from datetime import datetime
from functools import partial
from collections import defaultdict
from subprocess import run, PIPE, STDOUT

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.info

# Constants
FLAC_SIZE_PATTERN = re.compile(r'(\d+)\s+bytes')
DURATION_PATTERN = re.compile(r'(\d+):(\d+):(\d+)')
SHOW_ID_PATTERN = re.compile(r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})')
DATE_PATTERN = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
MIX_PATTERN = re.compile(r'SoF-(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})')

def rclone_mounts():
    """Retrieve a list of mounted rclone filesystems."""
    result = run(['rclone', 'listremotes'], check=True, capture_output=True, text=True)
    return [line.strip().split(':')[0] for line in result.stdout.splitlines()]

def rclone_location(path, mounts):
    """Determine if a path is a mounted rclone filesystem."""
    for mount in mounts:
        if path.startswith(mount):
            return (mount, path[len(mount):])
    return None

def process_archive(arch_label, dir_path, mounts):
    """Process the contents of an archive directory."""
    entries = []
    located = rclone_location(dir_path, mounts)
    kind = f"rclone:{located[0]}" if located else "local disk"
    log(f"Processing {arch_label} at {dir_path} [{kind}]...")

    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.flac'):
                flac_path = os.path.join(root, file)
                try:
                    flac_size_bytes = os.path.getsize(flac_path)
                    flac_size_readable = get_readable_size(flac_size_bytes)
                    duration_seconds = get_duration(flac_path)
                    duration_readable = format_duration(duration_seconds)
                    show_id = get_show_id(flac_path)
                    rec_date = get_rec_date(flac_path)
                    tracks = get_tracks(flac_path)
                    entries.append({
                        "archive_label": arch_label,
                        "dir_path": dir_path,
                        "show_id": show_id,
                        "flac_name": file,
                        "flac_size_bytes": flac_size_bytes,
                        "flac_size_readable": flac_size_readable,
                        "duration_seconds": duration_seconds,
                        "duration_readable": duration_readable,
                        "rec_date": rec_date,
                        "tracks": tracks
                    })
                except Exception as exc:
                    log(f"Error processing {flac_path}: {exc}")
    return entries

def remember_entry(mix_entries, seen_mix_bases, entry):
    """Add an entry to the mix entries list if it hasn't been seen before."""
    base = entry["show_id"]
    if base not in seen_mix_bases:
        seen_mix_bases[base] = entry
        mix_entries.append(entry)

def get_readable_size(size_bytes):
    """Convert bytes to a human-readable size."""
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PiB"

def format_total_duration(seconds):
    """Format total duration in seconds to a human-readable string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def get_duration(flac_path):
    """Get the duration of an audio file using ffprobe."""
    result = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', flac_path], check=True, capture_output=True, text=True)
    return int(float(result.stdout.strip()))

def get_show_id(flac_path):
    """Extract the show ID from the file name."""
    match = SHOW_ID_PATTERN.search(flac_path)
    return match.group(0) if match else "Unknown"

def get_rec_date(flac_path):
    """Extract the recording date from the file name."""
    match = DATE_PATTERN.search(flac_path)
    return match.group(0) if match else "Unknown"

def get_tracks(flac_path):
    """Extract tracklist from the file name or return an empty list if not found."""
    match = MIX_PATTERN.search(flac_path)
    if match:
        tracklist = match.group(0).split('-')[4:]
        return [re.sub(r"^\d+[\.\-]\s*", "", track) for track in tracklist]
    return []

def main():
    """Main function to execute the script."""
    scan_dirs = [
        ("archive1", "/path/to/archive1"),
        ("archive2", "/path/to/archive2"),
        # Add more directories as needed
    ]

    if not scan_dirs:
        log("Error: You must specify one or more archive output directories to scan.")
        return 1

    mounts = rclone_mounts()
    log(f"Scanning {len(scan_dirs)} archive storage location(s)...")
    for label, path in scan_dirs:
        located = rclone_location(path, mounts)
        kind = f"rclone:{located[0]}" if located else "local disk"
        log(f"  • {label}: {path} [{kind}]")

    mix_entries = []
    seen_mix_bases = {}
    for arch_label, dir_path in scan_dirs:
        for entry in process_archive(arch_label, dir_path, mounts):
            remember_entry(mix_entries, seen_mix_bases, entry)

    mix_entries.sort(key=lambda entry: (0, int(entry["show_id"])) if entry["show_id"].isdigit() else (1, entry["show_id"]))

    total_mixes = len(mix_entries)
    total_with_tracklists = sum(1 for mix in mix_entries if mix["tracks"])
    total_size_bytes = sum(mix["flac_size_bytes"] for mix in mix_entries)
    total_tracks_played = sum(len(mix["tracks"]) for mix in mix_entries)
    total_duration_seconds = sum(mix["duration_seconds"] for mix in mix_entries)
    total_size_readable = get_readable_size(total_size_bytes)
    total_duration_readable = format_total_duration(total_duration_seconds)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MPlanetarian - Stream of Frequency Tracklistings</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #e0e0e0; line-height: 1.6; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #ff007f; border-bottom: 2px solid #ff007f; padding-bottom: 15px; margin-bottom: 30px; }}
        .stats-box {{ background: linear-gradient(135deg, #1f1c2c, #928dab); border-radius: 8px; padding: 20px; margin-bottom: 40px; border: 1px solid #444; box-shadow: 0 4px 10px rgba(0,0,0,0.5); display: flex; justify-content: space-around; flex-wrap: wrap; }}
        .stat-item {{ text-align: center; padding: 10px 15px; min-width: 140px; }}
        .stat-val {{ font-size: 1.6em; font-weight: bold; color: #00e5ff; margin-bottom: 5px; }}
        .stat-lbl {{ font-size: 0.85em; color: #cfd8dc; text-transform: uppercase; letter-spacing: 1px; }}
        .mix-card {{ background-color: #1e1e1e; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #444; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }}
        .mix-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .mix-title {{ color: #ff007f; font-size: 1.2em; font-weight: bold; }}
        .mix-date {{ color: #cfd8dc; font-size: 0.9em; }}
        .track-list {{ list-style-type: none; padding: 0; }}
        .track-item {{ margin-bottom: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>MPlanetarian - Stream of Frequency Tracklistings</h1>
        <div class="stats-box">
            <div class="stat-item">
                <div class="stat-val">{total_mixes}</div>
                <div class="stat-lbl">Total Mixes</div>
            </div>
            <div class="stat-item">
                <div class="stat-val">{total_with_tracklists}</div>
                <div class="stat-lbl">Verified Tracklists</div>
            </div>
            <div class="stat-item">
                <div class="stat-val">{total_size_readable}</div>
                <div class="stat-lbl">Combined Size</div>
            </div>
            <div class="stat-item">
                <div class="stat-val">{total_tracks_played}</div>
                <div class="stat-lbl">Total Tracks Played</div>
            </div>
            <div class="stat-item">
                <div class="stat-val">{total_duration_readable}</div>
                <div class="stat-lbl">Total Mixing Duration</div>
            </div>
        </div>
        {''.join(f'''
            <div class="mix-card">
                <div class="mix-header">
                    <div class="mix-title">{mix['show_id']}</div>
                    <div class="mix-date">{mix['rec_date']}</div>
                </div>
                <div class="track-list">
                    {''.join(f'<li class="track-item">{track}</li>' for track in mix['tracks'])}
                </div>
            </div>
        ''' for mix in mix_entries)}
    </div>
</body>
</html>
"""

    html_path = "tracklistings.html"
    with open(html_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_content)
    log(f"Generated HTML file: {html_path}")

    try:
        run(['xdg-open', html_path], check=False)
    except Exception as exc:
        log(f"Failed to open HTML file: {exc}")

    return 0

if __name__ == "__main__":
    sys.exit(main())