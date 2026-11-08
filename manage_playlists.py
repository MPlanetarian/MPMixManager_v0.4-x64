#!/usr/bin/env python3
import os, sys, subprocess, shutil, argparse, re, time
from pathlib import Path

AUDIO_EXTS = ['.flac', '.wav', '.mp3', '.m4a', '.aif', '.ogg']

def get_base_dir():
    return Path(__file__).resolve().parent

def get_playlists_dir():
    p_dir = get_base_dir() / "playlists"
    p_dir.mkdir(parents=True, exist_ok=True)
    return p_dir

def list_archive_mixes():
    base_dir = get_base_dir()
    env_dir = os.environ.get("MIX_ARCHIVE_DIR")
    arch_dir = Path(env_dir) if env_dir and Path(env_dir).is_dir() else (base_dir / "MIX_ARCHIVE")
    scan_paths = [arch_dir / "FLAC_CONVERTED_OUTPUTS", arch_dir, base_dir / "MIX_ARCHIVE" / "FLAC_CONVERTED_OUTPUTS", base_dir / "FLAC_CONVERTED_OUTPUTS", base_dir]
    extra_env = os.environ.get("EXTRA_MIX_ARCHIVE_DIRS")
    if not extra_env:
        cfg = base_dir / "config.env"
        if cfg.is_file():
            try:
                with open(cfg, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("EXTRA_MIX_ARCHIVE_DIRS="):
                            extra_env = line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
    if extra_env:
        raw_extra = extra_env.strip()
        for sep in ('\n', ';', ','):
            if sep in raw_extra:
                extras = [x.strip().strip('"').strip("'") for x in raw_extra.split(sep) if x.strip().strip('"').strip("'")]
                break
        else:
            if re.search(r':[a-zA-Z]:', raw_extra):
                _fixed = re.sub(r':([a-zA-Z]:)', r';\1', raw_extra)
                extras = [x.strip().strip('"').strip("'") for x in _fixed.split(';') if x.strip().strip('"').strip("'")]
            elif ':' in raw_extra and not re.match(r'^[a-zA-Z]:', raw_extra):
                extras = [x.strip().strip('"').strip("'") for x in raw_extra.split(':') if x.strip().strip('"').strip("'")]
            elif raw_extra:
                extras = [raw_extra.strip('"').strip("'")]
        for ed in extras:
            p = Path(ed)
            if (p / "FLAC_CONVERTED_OUTPUTS").is_dir():
                scan_paths.append(p / "FLAC_CONVERTED_OUTPUTS")
            if p.is_dir():
                scan_paths.append(p)
    seen = set()
    mixes = []
    for sdir in scan_paths:
        if not sdir.is_dir():
            continue
        try:
            for entry in os.scandir(str(sdir)):
                if entry.is_file():
                    lower = entry.name.lower()
                    if any(lower.endswith(ext) for ext in AUDIO_EXTS):
                        if entry.name not in seen and entry.stat().st_size >= 20 * 1024 * 1024:
                            seen.add(entry.name)
                            mixes.append({"filename": entry.name, "path": entry.path, "size": entry.stat().st_size})
        except Exception:
            pass
    mixes.sort(key=lambda x: x["filename"].lower())
    return mixes

def get_generated_playlists_dir():
    g_dir = get_base_dir() / "PLAYLISTS_GENERATED"
    g_dir.mkdir(parents=True, exist_ok=True)
    return g_dir

def list_playlists():
    p_dir = get_playlists_dir()
    g_dir = get_generated_playlists_dir()
    playlists = []
    seen_names = set()
    for d in (g_dir, p_dir):
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in ('.m3u', '.m3u8', '.xspf'):
                    if f.name not in seen_names:
                        seen_names.add(f.name)
                        playlists.append(f)
    playlists.sort(key=lambda x: x.name.lower())
    return playlists

def parse_m3u(file_path):
    p = Path(file_path)
    tracks = []
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            if p.suffix.lower() == '.xspf':
                import urllib.parse
                for line in f:
                    line = line.strip()
                    if line.startswith("<location>") and line.endswith("</location>"):
                        loc = line[10:-11]
                        if loc.startswith("file://"):
                            loc = urllib.parse.unquote(loc[7:])
                        tracks.append(loc)
            else:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        tracks.append(line)
    except Exception:
        pass
    return tracks

def write_m3u(file_path, track_paths):
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for t in track_paths:
            title = Path(t).stem
            f.write(f"#EXTINF:-1,{title}\n{t}\n")

def launch_playlist_in_player(playlist_path, player="cliamp"):
    playlist_path = Path(playlist_path).resolve()
    print(f"\nLaunching {player} with playlist: {playlist_path.name}...")
    if player == "cliamp":
        cliamp_bin = shutil.which("cliamp") or (get_base_dir() / "bin" / "cliamp")
        if os.name == 'posix' and shutil.which("konsole"):
            subprocess.Popen(["konsole", "--hold", "-e", str(cliamp_bin), str(playlist_path)])
        elif os.name == 'posix' and shutil.which("ptyxis"):
            subprocess.Popen(["ptyxis", "--", str(cliamp_bin), str(playlist_path)])
        else:
            subprocess.Popen([str(cliamp_bin), str(playlist_path)])
    elif player == "strawberry":
        subprocess.Popen(["strawberry", str(playlist_path)])
    elif player == "vlc":
        if shutil.which("vlc"):
            subprocess.Popen(["vlc", str(playlist_path)])
        elif shutil.which("flatpak"):
            subprocess.Popen(["flatpak", "run", "org.videolan.VLC", str(playlist_path)])
    elif player == "mpv":
        if shutil.which("mpv"):
            subprocess.Popen(["mpv", f"--playlist={playlist_path}"])
    elif player == "kodi":
        if shutil.which("kodi"):
            subprocess.Popen(["kodi", str(playlist_path)])
        elif shutil.which("flatpak"):
            subprocess.Popen(["flatpak", "run", "tv.kodi.Kodi", str(playlist_path)])
    else:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(playlist_path)])
        elif sys.platform == "win32":
            subprocess.Popen(["cmd.exe", "/c", "start", "", str(playlist_path)])
        else:
            subprocess.Popen(["xdg-open", str(playlist_path)])

def create_playlist_wizard():
    print("\n--- Create New Custom Playlist ---")
    name = input("Enter Playlist Name (e.g. Best_Of_SOF): ").strip()
    if not name:
        return
    if not name.lower().endswith(('.m3u', '.m3u8')):
        name += ".m3u8"
    p_file = get_playlists_dir() / name
    all_mixes = list_archive_mixes()
    selected_paths = []
    while True:
        print(f"Creating Playlist: {name}")
        print(f"Selected Tracks: {len(selected_paths)} mixes in playlist")
        print("\nOptions: Enter numbers (e.g. 1,3,5), '/<query>' to filter, 'save' to finish, 'cancel' to exit")
        cmd = input("Select: ").strip()
        if cmd.lower() == 'cancel':
            return
        elif cmd.lower() == 'save':
            if selected_paths:
                write_m3u(p_file, selected_paths)
                alt_file = p_file.with_suffix('.m3u8') if p_file.suffix.lower() == '.m3u' else p_file.with_suffix('.m3u')
                write_m3u(alt_file, selected_paths)
                print(f"\n✓ Playlist successfully created with {len(selected_paths)} tracks (.m3u & .m3u8): {p_file.name}, {alt_file.name}")
                input("Press Enter to continue...")
            return
        elif cmd.startswith('/'):
            filter_q = cmd[1:].strip()
            filtered = [m for m in all_mixes if filter_q.lower() in m["filename"].lower()]
        else:
            filtered = all_mixes
            filter_q = ""
        print("Available Tracks:")
        for idx, m in enumerate(filtered[:25], start=1):
            print(f"  {idx}) {m['filename']}")
        print("\nOptions: Enter numbers (e.g. 1,3,5), '/<query>' to filter, 'save' to finish, 'cancel' to exit")
        cmd = input("Select: ").strip()
        if cmd.lower() == 'cancel':
            return
        elif cmd.lower() == 'save':
            if selected_paths:
                write_m3u(p_file, selected_paths)
                alt_file = p_file.with_suffix('.m3u8') if p_file.suffix.lower() == '.m3u' else p_file.with_suffix('.m3u')
                write_m3u(alt_file, selected_paths)
                print(f"\n✓ Playlist successfully created with {len(selected_paths)} tracks (.m3u & .m3u8): {p_file.name}, {alt_file.name}")
                input("Press Enter to continue...")
            return
        elif cmd.startswith('/'):
            filter_q = cmd[1:].strip()
        else:
            try:
                for part in cmd.split(','):
                    part = part.strip()
                    if part.isdigit():
                        i = int(part)
                        if 1 <= i <= len(filtered):
                            p = filtered[i - 1]["path"]
                            if p not in selected_paths:
                                selected_paths.append(p)
                            else:
                                selected_paths.remove(p)
            except Exception:
                pass

def edit_playlist_wizard(p_file):
    tracks = parse_m3u(p_file)
    while True:
        print(f"Editing Playlist: {p_file.name}")
        print(f"Total Tracks: {len(tracks)}")
        print("\nOptions: 'r <index>' to remove track, 'add' to append tracks, 'save' to finish, '0' to cancel")
        cmd = input("Select: ").strip()
        if cmd in ('0', 'cancel'):
            return
        elif cmd == 'save':
            write_m3u(p_file, tracks)
            alt_file = p_file.with_suffix('.m3u8') if p_file.suffix.lower() == '.m3u' else p_file.with_suffix('.m3u')
            if alt_file.is_file():
                write_m3u(alt_file, tracks)
            print("✓ Playlist updated (.m3u / .m3u8).")
            time.sleep(1)
            return
        elif cmd.startswith('r '):
            idx_str = cmd[2:].strip()
            if idx_str.isdigit() and 1 <= int(idx_str) <= len(tracks):
                tracks.pop(int(idx_str) - 1)
        elif cmd == 'add':
            mixes = list_archive_mixes()
            print("\nSelect mix to append:")
            for i, m in enumerate(mixes[:15], start=1):
                print(f"  {i}) {m['filename']}")
            asel = input(f"Select [1-{min(15, len(mixes))}]: ").strip()
            if asel.isdigit() and 1 <= int(asel) <= min(15, len(mixes)):
                tracks.append(mixes[int(asel) - 1]["path"])

def main():
    parser = argparse.ArgumentParser(description="Custom Playlists Creator & Launcher")
    parser.add_argument("--list", action="store_true", help="List all playlists")
    parser.add_argument("--generate-archive-playlists", action="store_true", help="Generate playlists for all configured mix archive folders")
    parser.add_argument("--launch", help="Playlist path or name to launch")
    parser.add_argument("--player", default="cliamp", help="Audio player to launch")
    args = parser.parse_args()
    if args.generate_archive_playlists:
        gen_script = get_base_dir() / "scripts" / "generate_archive_folder_playlists.py"
        if not gen_script.is_file():
            gen_script = get_base_dir() / "generate_archive_folder_playlists.py"
        if gen_script.is_file():
            subprocess.run([sys.executable, str(gen_script), "--all"])
    elif args.list:
        for p in list_playlists():
            print(f"{p.name} ({len(parse_m3u(p))} tracks)")
    elif args.launch:
        launch_playlist_in_player(args.launch, args.player)
    else:
        while True:
            playlists = list_playlists()
            print("Custom Playlists Creator & Audio Player Launcher")
            print(f"Playlist Directory: {get_playlists_dir()}")
            print(f"Saved Playlists: {len(playlists)}")
            if playlists:
                for idx, p in enumerate(playlists, start=1):
                    tracks = parse_m3u(p)
                    print(f"  {idx}) {p.name} ({len(tracks)} mix tracks)")
            else:
                print("  No playlists created yet.")
            print("\nPlaylist Operations:")
            print("  C) Create New Custom Playlist")
            print("  G) Generate Mix Archive Folder Playlists (from Configured Storage Folders)")
            print("  L) Launch a Playlist in Audio Player")
            print("  E) Edit / Re-order Tracks in Existing Playlist")
            print("  D) Delete a Playlist")
            if sys.platform == "darwin":
                print("  T) Generate Traktor Playlist from History Files (macOS)")
            print("\n  0) Return to Main Menu (or 'q')")
            cmd = input("Enter choice: ").strip()
            if cmd in ('0', 'q', 'exit', 'quit'):
                break
            if cmd.lower() == 'c':
                create_playlist_wizard()
            elif cmd.lower() == 'g':
                gen_script = get_base_dir() / "scripts" / "generate_archive_folder_playlists.py"
                if not gen_script.is_file():
                    gen_script = get_base_dir() / "generate_archive_folder_playlists.py"
                if gen_script.is_file():
                    subprocess.run([sys.executable, str(gen_script)])
                else:
                    print("Error: generate_archive_folder_playlists.py not found!")
                    time.sleep(1)
            elif cmd.lower() == 't' and sys.platform == "darwin":
                traktor_script = get_base_dir() / "generate_traktor_playlist_from_history.py"
                if traktor_script.is_file():
                    subprocess.run([sys.executable, str(traktor_script)])
                else:
                    print("Error: generate_traktor_playlist_from_history.py not found!")
                    time.sleep(1)
            elif cmd.lower() == 'l':
                if not playlists:
                    print("No playlists available.")
                    time.sleep(1)
                    continue
                sel = input(f"Select playlist to launch [1-{len(playlists)}]: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(playlists):
                    p_file = playlists[int(sel) - 1]
                    print("\nSelect Audio Player:")
                    print("  1) cliamp (Terminal Player)")
                    print("  2) Strawberry Music Player")
                    print("  3) VLC Media Player")
                    print("  4) MPV Player")
                    print("  5) Kodi Media Center")
                    p_sel = input("Select player [1-5, default 1]: ").strip() or "1"
                    p_map = {"1": "cliamp", "2": "strawberry", "3": "vlc", "4": "mpv", "5": "kodi"}
                    player_name = p_map.get(p_sel, "cliamp")
                    launch_playlist_in_player(p_file, player_name)
                    time.sleep(1)
            elif cmd.lower() == 'e':
                if not playlists:
                    continue
                sel = input(f"Select playlist to edit [1-{len(playlists)}]: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(playlists):
                    edit_playlist_wizard(playlists[int(sel) - 1])
            elif cmd.lower() == 'd':
                if not playlists:
                    continue
                sel = input(f"Select playlist to delete [1-{len(playlists)}]: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(playlists):
                    to_del = playlists[int(sel) - 1]
                    conf = input(f"Delete {to_del.name}? [y/N]: ").strip().lower()
                    if conf in ('y', 'yes'):
                        to_del.unlink()
                        print("✓ Playlist deleted.")
                        time.sleep(0.8)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        sys.exit(0)