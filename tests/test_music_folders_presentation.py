#!/usr/bin/env python3
"""
Option 1 — Music Folders are chosen by the user.

Local drive paths and SMB shares can be added and removed.
The program does not ship with a fixed host or share list.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import music_folders_manager as mfm
from music_folders_manager import (
    add_folder,
    check_playlist_status,
    find_folder,
    folder_key,
    load_folders,
    parse_folder_path,
    rebuild_all_playlist,
    remove_folder,
    save_playlist_files,
    scan_folder_tracks,
    unc_path,
    _migrate_legacy_folders,
)


class TestMusicFolderConfiguration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folders_file = self.root / "music_folders.json"
        self.config = {
            "playlists_dir": self.root / "playlists",
            "mount_root": self.root / "mnt",
            "smb_user": "",
            "smb_password": "",
            "base_dir": self.root,
            "legacy_host": "",
            "legacy_shares": "",
        }
        self.config["playlists_dir"].mkdir()
        self._patch = patch.object(mfm, "FOLDERS_FILE", self.folders_file)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.cleanup()

    def test_user_smb_shares_parse(self):
        first = parse_folder_path(r"\\192.168.1.138\music001")
        second = parse_folder_path("smb://192.168.1.138/music002/House")
        self.assertEqual(first["type"], "smb")
        self.assertEqual(first["host"], "192.168.1.138")
        self.assertEqual(first["share"], "music001")
        self.assertEqual(unc_path(first), r"\\192.168.1.138\music001")
        self.assertEqual(second["share"], "music002")
        self.assertEqual(second["subpath"], "House")
        self.assertEqual(unc_path(second), r"\\192.168.1.138\music002\House")
        self.assertEqual(
            folder_key(parse_folder_path(r"\\192.168.1.138\music001")),
            folder_key(parse_folder_path("smb://192.168.1.138/MUSIC001")),
        )

    def test_only_local_drives_and_smb_are_accepted(self):
        with patch.object(mfm, "_windows_remote_unc", return_value=None):
            local = parse_folder_path(r"D:\Music")
            bash_style = parse_folder_path("/d/DJ")
        self.assertEqual(local["type"], "local")
        self.assertEqual(local["path"], r"D:\Music")
        self.assertEqual(bash_style["path"], r"D:\DJ")
        for rejected in ("ftp://nas/music", "nfs://nas/music", "https://example.com/a.flac", "music", r"\\192.168.1.138"):
            with self.assertRaises(ValueError):
                parse_folder_path(rejected)

    def test_mapped_smb_drive_is_stored_as_a_share(self):
        with patch.object(mfm, "_windows_remote_unc", return_value=r"\\192.168.1.138\music001\House"):
            parsed = parse_folder_path(r"Z:\House")
        self.assertEqual(parsed["type"], "smb")
        self.assertEqual(parsed["share"], "music001")
        self.assertEqual(parsed["subpath"], "House")

    def test_add_list_and_remove_folders(self):
        folders = []
        add_folder(r"\\192.168.1.138\music001", folders, name="MUSIC001")
        add_folder(r"\\192.168.1.138\music002", folders, name="MUSIC002")
        with self.assertRaises(ValueError):
            add_folder("smb://192.168.1.138/music001", folders)
        loaded = load_folders(self.config)
        self.assertEqual([f["id"] for f in loaded], ["MUSIC001", "MUSIC002"])
        self.assertEqual(find_folder("2", loaded)["share"], "music002")
        self.assertEqual(find_folder(r"\\192.168.1.138\MUSIC001", loaded)["id"], "MUSIC001")
        remove_folder(loaded[0], loaded, self.config)
        self.assertEqual([f["id"] for f in load_folders(self.config)], ["MUSIC002"])

    def test_local_folder_scan_and_playlist_rebuild(self):
        music = self.root / "Desk"
        music.mkdir()
        (music / "track.flac").write_bytes(b"")
        (music / "notes.txt").write_bytes(b"")
        (music / ".hidden.mp3").write_bytes(b"")
        skipped = music / "$recycle.bin"
        skipped.mkdir()
        (skipped / "junk.mp3").write_bytes(b"")
        folders = []
        added = add_folder(str(music), folders, name="Desk")
        tracks = scan_folder_tracks(added, self.config, interactive=False)
        self.assertEqual([t["name"] for t in tracks], ["track.flac"])
        save_playlist_files(tracks, added["id"], self.config, title="Desk")
        self.assertEqual(rebuild_all_playlist(folders, self.config), 1)
        status = check_playlist_status(added["id"], self.config)
        self.assertTrue(status["exists"])
        self.assertEqual(status["track_count"], 1)
        remove_folder(added, folders, self.config)
        self.assertFalse(check_playlist_status(added["id"], self.config)["exists"])
        self.assertFalse(check_playlist_status("ALL", self.config)["exists"])

    def test_a_file_cannot_be_added_as_a_folder(self):
        audio = self.root / "one.flac"
        audio.write_bytes(b"")
        with self.assertRaises(ValueError):
            add_folder(str(audio), [])

    def test_legacy_env_seed_is_optional(self):
        seeded = _migrate_legacy_folders({"legacy_host": "192.168.1.138", "legacy_shares": "music001, music002"})
        self.assertEqual([f["id"] for f in seeded], ["MUSIC001", "MUSIC002"])
        self.assertEqual(_migrate_legacy_folders({"legacy_host": "", "legacy_shares": ""}), [])

    def test_option1_menu_exposes_add_and_remove(self):
        src = Path(mfm.__file__).read_text(encoding="utf-8")
        self.assertIn("Add Music Folder", src)
        self.assertIn("Remove Music Folder", src)
        self.assertNotIn("Connect / Mount SMB Music Shares", src)
        self.assertNotIn("Disconnect / Unmount SMB Music Shares", src)
        self.assertIn("6){NC} View Track Audio Inspector & Player Shortcuts Guide", src)
        shell = (PROJECT_ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8", errors="replace")
        self.assertIn("Local Drives & SMB Shares • Add / Remove Folders", shell)
        self.assertNotIn("SMB /MUSIC001 & /MUSIC002", shell)


class TestMusicPlayerPresentation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        playlist = Path(self.tmp.name) / "DJ_Tracks_MUSIC001.json"
        self.track_path = r"\\192.168.1.138\music001\Cosmic Voyager.flac"
        playlist.write_text(json.dumps([{
            "name": "Cosmic Voyager.flac",
            "title": "Cosmic Voyager",
            "path": self.track_path,
            "folder": "MUSIC001",
            "ext": "FLAC",
            "duration_fmt": "00:00",
        }]), encoding="utf-8")
        self.playlist = playlist

    def tearDown(self):
        self.tmp.cleanup()

    def test_music_mode_duration_field_presentation(self):
        from MP_Audio_Player import MusicFolderPlaylistScanner, TerminalPlayerUI, _display_width

        scanner = MusicFolderPlaylistScanner("MUSIC001", playlist_path=self.playlist)
        mixes = scanner.get_mixes()
        self.assertEqual(len(mixes), 1)
        self.assertEqual(mixes[0]["duration_fmt"], "00:00")

        ui = TerminalPlayerUI(None, scanner, is_remote=True, mode="MUSIC", folder_name="MUSIC001")
        self.assertEqual(ui.mode, "MUSIC")

        iw = 115
        avail_name = max(4, iw - 23)
        m = mixes[0]
        raw_name = str(m.get("name", ""))
        mn = raw_name[:avail_name]
        name_pad = " " * max(0, avail_name - _display_width(mn))
        ext_str = f"{m.get('ext', ''):<4}"[:4]
        field_str = f"{m.get('duration_fmt', '00:00'):>6s}"
        inner_plain = f"   [   1] {mn}{name_pad} {ext_str} {field_str} "

        self.assertEqual(_display_width(inner_plain), iw)
        self.assertIn("00:00", inner_plain)
        self.assertNotIn("0MB", inner_plain)

    def test_player_label_uses_the_configured_folder(self):
        from MP_Audio_Player import music_library_label
        self.assertEqual(music_library_label("ALL"), "All Music Folders")
        self.assertEqual(music_library_label("MUSIC001"), "MUSIC001")

    def test_dj_features_removed_and_clean_audio_player(self):
        import MP_Audio_Player

        self.assertFalse(hasattr(MP_Audio_Player, "CAMELOT_WHEEL"))
        self.assertFalse(hasattr(MP_Audio_Player, "extract_track_camelot_key"))
        self.assertFalse(hasattr(MP_Audio_Player, "get_compatible_camelot_keys"))
        self.assertFalse(hasattr(MP_Audio_Player, "HotCueManager"))

        scanner = MP_Audio_Player.MusicFolderPlaylistScanner("MUSIC001", playlist_path=self.playlist)
        ui = MP_Audio_Player.TerminalPlayerUI(None, scanner, is_remote=True, mode="MUSIC", folder_name="MUSIC001")
        self.assertFalse(hasattr(ui, "cue_mgr"))
        self.assertFalse(hasattr(ui, "bpm_tap_times"))
        self.assertFalse(hasattr(ui, "tapped_bpm"))
        self.assertFalse(hasattr(ui, "harmonic_filter_active"))
        self.assertFalse(hasattr(ui, "drop_audition_step"))

    def test_track_inspector_hud_shows_the_real_source(self):
        from MP_Audio_Player import MusicFolderPlaylistScanner, TerminalPlayerUI

        scanner = MusicFolderPlaylistScanner("MUSIC001", playlist_path=self.playlist)
        ui = TerminalPlayerUI(None, scanner, is_remote=True, mode="MUSIC", folder_name="MUSIC001")
        self.assertFalse(ui.inspector_hud_active)
        ui.inspector_hud_active = True

        status = {
            "title": "Cosmic Voyager (Deep Mix)",
            "path": self.track_path,
            "sample_rate": 96000,
            "channels": 2,
            "position_fmt": "04:20",
            "duration_fmt": "08:45",
            "progress_pct": 49.5,
            "volume": 90,
            "pitch_percent": 0,
            "output_rate": 96000,
            "output_device": "Speakers",
        }
        hud_text = "\n".join(ui._render_inspector_hud(status, iw=115))
        self.assertIn("TRACK AUDIO INSPECTOR", hud_text)
        self.assertIn("Folder / Src", hud_text)
        self.assertIn("SMB Share [MUSIC001]", hud_text)
        self.assertIn(r"\\192.168.1.138\music001", hud_text)
        self.assertIn("Network Path", hud_text)
        self.assertNotIn("SMB Network /MUSIC001 (192.168.1.138)", hud_text)
        self.assertNotIn("Camelot", hud_text)
        self.assertNotIn("DJ Cues", hud_text)

        local = dict(status, path=r"D:\Music\Cosmic Voyager.flac")
        local_text = "\n".join(ui._render_inspector_hud(local, iw=115))
        self.assertIn("Local Drive", local_text)
        self.assertIn("File Path", local_text)

    def test_mix_archive_manager_slash_search_match(self):
        import os
        import shutil
        import subprocess

        bash = None
        for cand in (
            os.path.join(os.environ.get("ProgramFiles", ""), "Git", "bin", "bash.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Git", "bin", "bash.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "bin", "bash.exe"),
            r"C:\msys64\usr\bin\bash.exe",
        ):
            if cand and os.path.isfile(cand):
                bash = cand
                break
        if bash is None:
            found = shutil.which("bash")
            if found and "WindowsApps" not in found.replace("/", "\\"):
                bash = found
        if bash is None:
            self.skipTest("Git Bash is not installed")

        bash_test_script = r"""
        total_opts=4
        _opts_ref=(
            "SECTION|SECTION 1: WORKFLOW|"
            "1|Play Tracks from MUSIC Folders using MP Audio Player|(Music Library • Local Drives & SMB Shares • Add / Remove Folders)"
            "2|Run Mix Conversion|(FLAC, MP3, WAV, or YouTube MP4)"
            "19|Spectrogram Generation & Audio Frequency Analysis|(Single & Multiple Spek, SoX)"
        )
        cur_idx=0
        _find_menu_search_match() {
            local q="${1,,}" start="${2:-0}" dir="${3:-1}"
            [ -z "$q" ] && return 0
            local step=0 idx="$start"
            while [ "$step" -lt "$total_opts" ]; do
                local ok="" ol="" oe=""
                IFS='|' read -r ok ol oe <<< "${_opts_ref[$idx]}"
                if [ "$ok" != "SECTION" ] && [ "$ok" != "SEP" ]; then
                    local haystack="${ok} ${ol} ${oe}"
                    haystack="${haystack,,}"
                    if [[ "$haystack" == *"$q"* ]]; then
                        cur_idx=$idx
                        return 0
                    fi
                fi
                idx=$(( (idx + dir + total_opts) % total_opts ))
                ((step++))
            done
            return 1
        }

        _find_menu_search_match "music" 0 1 || exit 10
        [ "$cur_idx" -eq 1 ] || exit 11
        _find_menu_search_match "smb" 0 1 || exit 12
        [ "$cur_idx" -eq 1 ] || exit 13
        _find_menu_search_match "conversion" 0 1 || exit 20
        [ "$cur_idx" -eq 2 ] || exit 21
        _find_menu_search_match "spek" 0 1 || exit 30
        [ "$cur_idx" -eq 3 ] || exit 31
        if _find_menu_search_match "zzznonexistent" 0 1; then exit 40; fi
        echo "BASH_SEARCH_TESTS_PASS"
        """

        result = subprocess.run([bash, "-c", bash_test_script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Bash search match tests failed: {result.stderr}")
        self.assertIn("BASH_SEARCH_TESTS_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
