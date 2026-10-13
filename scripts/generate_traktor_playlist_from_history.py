import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

# Colors and formatting
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
NC = "\033[0m"

def is_traktor_running():
    # Check if Traktor is running (platform-specific code needed)
    pass

def quit_traktor():
    # Quit Traktor (platform-specific code needed)
    pass

def launch_traktor_and_load_decks(traktor_dir, playlist_name, tracks):
    # Launch Traktor and load decks (platform-specific code needed)
    pass

def parse_history_file(file_path):
    tracks = []
    with open(file_path, "r", errors="ignore") as f:
        content = f.read()
        root = ET.fromstring(content)
        for entry in root.findall(".//TRACK"):
            key = entry.find("KEY").text if entry.find("KEY") is not None else "Unknown"
            bpm = entry.find("BPM").text if entry.find("BPM") is not None else "Unknown"
            title = entry.find("TITLE").text if entry.find("TITLE") is not None else "Unknown"
            artist = entry.find("ARTIST").text if entry.find("ARTIST") is not None else "Unknown"
            tracks.append({"key": key, "bpm": bpm, "title": title, "artist": artist})
    return tracks

def insert_playlist_into_collection(collection_nml, playlist_name, tracks):
    # Insert playlist into collection (implementation needed)
    pass

def update_traktor_settings_tsi(traktor_dir, playlist_name):
    # Update Traktor settings (implementation needed)
    pass

def main():
    traktor_dir = os.path.expanduser("~/Library/Application Support/Native Instruments/Traktor")
    history_dir = os.path.join(traktor_dir, "History")
    collection_nml = os.path.join(traktor_dir, "Collection.nml")
    traktor_ver = "2.11"

    hfiles = sorted(glob(os.path.join(history_dir, "history_*.nml")), key=os.path.getmtime, reverse=True)
    if not hfiles:
        print(f"{YELLOW}No Traktor History (.nml) files found in {history_dir}.{NC}")
        input("Press [Enter] to return...")
        return

    while True:
        os.system("clear 2>/dev/null || true")
        print(f"{BOLD}{MAGENTA}==================================================================================={NC}")
        print(f"{BOLD}{MAGENTA}       TRAKTOR {traktor_ver}: GENERATE PLAYLIST FROM HISTORY DATABASE               {NC}")
        print(f"{BOLD}{MAGENTA}==================================================================================={NC}")
        print(f"  {BOLD}Traktor Directory:{NC} {traktor_dir}")
        print(f"  {BOLD}Total History Files:{NC} {len(hfiles)}")
        print(f"{BLUE}───────────────────────────────────────────────────────────────────────────────────{NC}\n")

        start_idx = 0
        end_idx = len(hfiles)

        for i in range(start_idx, end_idx):
            hf = hfiles[i]
            fname = os.path.basename(hf)
            m = re.search(r"history_(\d{4})y(\d{2})m(\d{2})d_(\d{2})h(\d{2})m(\d{2})s", fname)
            dt_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}" if m else "Unknown Date"
            print(f"  {BOLD}{CYAN}{i + 1:2d}){NC} {dt_str}  {DIM}{fname}{NC}")

        print(f"\n{BLUE}───────────────────────────────────────────────────────────────────────────────────{NC}")
        print(f"  Options: {BOLD}[Q]{NC}uit / Return")
        print(f"{BLUE}───────────────────────────────────────────────────────────────────────────────────{NC}")

        choice = input(f"Enter choice [1-{len(hfiles)}, Q]: ").strip()

        if choice.lower() == 'q' or choice == '0':
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(hfiles):
            print(f"{RED}Invalid selection.{NC}")
            time.sleep(1)
            continue

        chosen_idx = int(choice) - 1
        chosen_hf = hfiles[chosen_idx]
        chosen_name = os.path.basename(chosen_hf)

        print(f"\n{CYAN}Reading tracks from {chosen_name}...{NC}")
        history_tracks = parse_history_file(chosen_hf)

        if not history_tracks:
            print(f"{RED}No tracks found in {chosen_name}!{NC}")
            input("Press [Enter] to continue...")
            continue

        sorted_tracks = sorted(history_tracks, key=lambda x: x['key'])

        while True:
            os.system("clear 2>/dev/null || true")
            print(f"{BOLD}{MAGENTA}==================================================================================={NC}")
            print(f"{BOLD}{CYAN}  SELECTED HISTORY FILE: {chosen_name}{NC}")
            print(f"  Tracks in session: {BOLD}{len(history_tracks)}{NC}")
            print(f"{BOLD}{MAGENTA}==================================================================================={NC}\n")
            print(f"  {BOLD}{CYAN}1){NC} {BOLD}View Tracklist in Console{NC}")
            print(f"  {BOLD}{CYAN}2){NC} {BOLD}{GREEN}Commit & Generate Traktor Playlist in Key Field Ascending Order{NC}")
            print(f"  {BOLD}{CYAN}3){NC} Select a Different History File")
            print(f"  {BOLD}{CYAN}0){NC} Return to Main Menu\n")

            sub_choice = input("Enter choice [1-3, 0 to cancel]: ").strip()

            if sub_choice == '1':
                for track in sorted_tracks:
                    print(f"  {track['key']:<10} {track['bpm']:<10} {track['title']} - {track['artist']}")
                commit_choice = input("Commit to generating Traktor Playlist from this History? [Y/n]: ").strip()
                if commit_choice.lower() in ['', 'y', 'yes']:
                    sub_choice = '2'
                else:
                    continue

            if sub_choice == '2':
                m = re.search(r"history_(\d{4})y(\d{2})m(\d{2})d_(\d{2})h(\d{2})m(\d{2})s", chosen_name)
                default_pl_name = f"SOF Mix {m.group(1)}-{m.group(2)}-{m.group(3)} ({m.group(4)}h{m.group(5)}m)" if m else f"History Playlist {time.strftime('%Y-%m-%d')}"

                user_pl_name = input(f"Enter Traktor Playlist Name [Default: '{default_pl_name}']: ").strip()
                final_pl_name = user_pl_name if user_pl_name else default_pl_name

                if is_traktor_running():
                    print(f"\n{BOLD}{YELLOW}⚠️  Traktor Pro is currently running!{NC}")
                    close_ask = input("Close Traktor cleanly now so the playlist can be written? [Y/n]: ").strip()
                    if close_ask.lower() in ['', 'y', 'yes']:
                        print(f"{CYAN}Closing Traktor...{NC}")
                        if not quit_traktor():
                            print(f"{RED}Could not close Traktor automatically. Please close Traktor manually and try again.{NC}")
                            input("Press [Enter] to continue...")
                            break
                        print(f"{GREEN}✓ Traktor closed safely.{NC}")
                    else:
                        print(f"{YELLOW}Operation cancelled to avoid database conflicts.{NC}")
                        input("Press [Enter] to continue...")
                        break

                print(f"\n{CYAN}Generating playlist '{final_pl_name}' with {len(sorted_tracks)} tracks in Key Ascending order...{NC}")
                success = insert_playlist_into_collection(collection_nml, final_pl_name, sorted_tracks)

                if success:
                    update_traktor_settings_tsi(traktor_dir, final_pl_name)
                    print(f"\n{BOLD}{GREEN}======================================================================{NC}")
                    print(f"{BOLD}{GREEN}✓ Playlist '{final_pl_name}' is Ready in Traktor's Default Root Playlists!{NC}")
                    print(f"  • Total Tracks: {len(sorted_tracks)}")
                    print(f"  • Sorting: Key Field Ascending Order")
                    print(f"{BOLD}{GREEN}======================================================================{NC}\n")

                    launch_ask = input(f"{BOLD}Do you want to open the playlist in Traktor now ready to make a mix? [Y/n]: {NC}").strip()
                    if launch_ask.lower() in ['', 'y', 'yes']:
                        launch_traktor_and_load_decks(traktor_dir, playlist_name, tracks)

                input("Press [Enter] to continue...")
                break

            if sub_choice == '3':
                break

            if sub_choice == '0':
                return

if __name__ == "__main__":
    main() # 633 to 178