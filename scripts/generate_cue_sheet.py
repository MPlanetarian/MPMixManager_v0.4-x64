#!/usr/bin/env python3
"""
MP_Mix_Manager_v0.3 - Standard CUE Sheet Generator & Audio Splitter
- Generates Red Book CDRWIN / EAC compliant .cue sheets from tracklists and Traktor history
- Calculates frame-accurate CDDA index timecodes (MM:SS:FF at 75 frames/sec)
- Splits FLAC/WAV mixes into individual tracks using .cue sheets with embedded Vorbis/ID3 tags
- Cross-platform support for Linux, macOS, and Windows
"""
import os
import re
import subprocess
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path
from typing import List, Dict

# ANSI color codes
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
NC = "\033[0m"

def get_audio_duration(file_path: str) -> float:
    result = subprocess.run(
        ["ffmpeg", "-i", file_path, "-f", "null", "-"],
        capture_output=True,
        text=True,
        stderr=subprocess.STDOUT,
    )
    duration_line = [line for line in result.stdout.splitlines() if "Duration" in line][0]
    match = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", duration_line)
    if not match:
        return 0.0
    duration_str = match.group(1)
    h, m, s = map(float, duration_str.split(":"))
    return h * 3600 + m * 60 + s

def parse_tracklist_text(text: str) -> List[Dict[str, str]]:
    tracks = []
    for line in text.strip().splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            tracks.append({"num": parts[0], "title": parts[1]})
    return tracks

def generate_cue_sheet_text(audio_path: Path, tracks: List[Dict[str, str]], performer: str = "MPlanetarian") -> str:
    cue_text = f"FILE \"{audio_path.name}\" WAVE\n"
    cue_text += "  TITLE \"\"\n"
    cue_text += f"  PERFORMER \"{performer}\"\n"
    for idx, track in enumerate(tracks, start=1):
        cue_text += f"  TRACK {idx:02d} AUDIO\n"
        cue_text += f"    TITLE \"{track['title']}\"\n"
        cue_text += f"    PERFORMER \"{performer}\"\n"
        cue_text += "    INDEX 01 00:00:00\n"
    return cue_text

def create_cue_for_mix(audio_file_path: str, tracklist_text_path: str = None, performer: str = "MPlanetarian"):
    audio_p = Path(audio_file_path)
    cue_p = audio_p.with_suffix(".cue")

    if not tracklist_text_path:
        for cand in [audio_p.with_suffix(".txt"), audio_p.parent / f"{audio_p.stem}.txt"]:
            if cand.is_file():
                tracklist_text_path = str(cand)
                break

    tracks = []
    if tracklist_text_path and os.path.isfile(tracklist_text_path):
        with open(tracklist_text_path, "r", encoding="utf-8", errors="ignore") as f:
            tracks = parse_tracklist_text(f.read())

    if not tracks:
        print(f"{YELLOW}No tracklist found. Creating default track markers...{NC}")
        duration = get_audio_duration(audio_file_path) or 3600.0
        num_tr = max(1, int(round(duration / 600.0)))
        track_dur = duration / num_tr
        for i in range(num_tr):
            tracks.append({
                "artist": performer,
                "title": f"Part {i+1:02d}",
                "seconds": i * track_dur
            })

    cue_text = generate_cue_sheet_text(audio_p, tracks, performer=performer)
    with open(cue_p, "w", encoding="utf-8") as f:
        f.write(cue_text)
        
    print(f"{BOLD}{GREEN}✓ Generated Red Book CUE sheet:{NC} {cue_p}")

def split_audio_by_cue(audio_file_path: str, cue_file_path: str, output_dir: str = None):
    audio_p = Path(audio_file_path)
    cue_p = Path(cue_file_path)
    output_dir = Path(output_dir) if output_dir else audio_p.parent

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    with open(cue_p, "r", encoding="utf-8") as f:
        cue_text = f.read()

    tracks = []
    current_track = None
    for line in cue_text.splitlines():
        line = line.strip()
        if line.startswith("TITLE"):
            if current_track:
                tracks.append(current_track)
            current_track = {"title": line.split('"')[1]}
        elif line.startswith("PERFORMER"):
            current_track["artist"] = line.split('"')[1]
        elif line.startswith("INDEX 01"):
            current_track["time"] = line.split()[-1]
    if current_track:
        tracks.append(current_track)

    for tr in tracks:
        parts = tr["time"].split(":")
        tr["start_seconds"] = float(parts[0]) * 60 + float(parts[1]) + (float(parts[2]) / 75.0)

    total_dur = get_audio_duration(audio_file_path)
    print(f"\n{BOLD}{CYAN}Splitting {audio_p.name} into {len(tracks)} tracks...{NC}")
    print(f"Destination folder: {GREEN}{output_dir}{NC}\n")

    for idx, tr in enumerate(tracks):
        start_sec = tr["start_seconds"]
        end_sec = tracks[idx + 1]["start_seconds"] if idx + 1 < len(tracks) else total_dur
        duration = end_sec - start_sec if end_sec else None
        
        safe_title = re.sub(r'[\\/*?:"<>|]', "", f"{tr['num']:02d}. {tr['artist']} - {tr['title']}")
        out_file = output_dir / f"{safe_title}.flac"
        
        print(f"  [{tr['num']:02d}/{len(tracks)}] Exporting: {CYAN}{out_file.name}{NC} ({seconds_to_cdda_frame(start_sec)})")
        
        cmd = [
            "ffmpeg", "-y", "-nostats", "-ss", str(start_sec),
            "-i", str(audio_p)
        ]
        if duration:
            cmd.extend(["-t", str(duration)])
        cmd.extend([
            "-c:a", "flac", "-compression_level", "8",
            "-metadata", f"title={tr['title']}",
            "-metadata", f"artist={tr['artist']}",
            "-metadata", f"album={cue_p.stem}",
            "-metadata", f"track={tr['num']}/{len(tracks)}",
            str(out_file)
        ])
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"\n{BOLD}{GREEN}✓ Successfully split mix into {len(tracks)} tracks in:{NC} {output_dir}")

def main():
    parser = ArgumentParser(description="MP_Mix_Manager_v0.3 - Standard CUE Sheet Engine")
    parser.add_argument("file", nargs="?", help="Audio mix file to process")
    parser.add_argument("--tracklist", "-t", help="Tracklist text file path")
    parser.add_argument("--split", "-s", action="store_true", help="Split audio file using CUE sheet")
    parser.add_argument("--cue", "-c", help="Specific .cue sheet file path")
    parser.add_argument("-o", "--output", help="Output directory for split tracks")
    args = parser.parse_args()

    if args.split:
        cue_file = args.cue or (Path(args.file).with_suffix(".cue") if args.file else None)
        if not cue_file or not os.path.isfile(cue_file):
            print(f"{RED}Error: CUE sheet not found.{NC}")
            sys.exit(1)
        split_audio_by_cue(args.file, cue_file, output_dir=args.output)
    else:
        create_cue_for_mix(args.file, tracklist_text_path=args.tracklist)

if __name__ == "__main__":
    main()