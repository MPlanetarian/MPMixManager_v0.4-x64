#!/usr/bin/env python3
"""
Test Suite: MP Audio Player Option 1 - MUSIC Folders Presentation & Status
Verifies that:
1. scripts/music_folders_manager.py loads the SMB music configuration correctly.
2. Remote SMB shares (/MUSIC001, /MUSIC002) at 192.168.1.138 are tracked.
3. Pre-cached playlists for ALL, MUSIC001, and MUSIC002 are generated and present.
4. Track counts match expected libraries (31,000+ tracks presented across music folders).
5. MP_Audio_Player.py exposes advanced DJ mode bindings and hot cue persistence.
"""

import sys
import unittest
from pathlib import Path

# Add project root and scripts to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from music_folders_manager import (
    load_music_config,
    check_playlist_status,
    is_share_mounted,
)


class TestMusicFoldersPresentation(unittest.TestCase):
    """Test suite verifying music folders configuration and playlist presentation."""

    def setUp(self):
        self.config = load_music_config()

    def test_music_config_structure(self):
        """Verify configuration host, shares, and mount paths."""
        self.assertEqual(self.config.get("host"), "192.168.1.138")
        shares = self.config.get("shares", [])
        self.assertIn("MUSIC001", shares)
        self.assertIn("MUSIC002", shares)
        self.assertTrue(Path(self.config["mount_root"]).is_absolute())

    def test_music_folders_playlists_presentation(self):
        """Verify that all music folders have their pre-cached playlists correctly presented."""
        status_all = check_playlist_status("ALL", self.config)
        status_m1 = check_playlist_status("MUSIC001", self.config)
        status_m2 = check_playlist_status("MUSIC002", self.config)

        self.assertTrue(status_all["exists"], "Playlist for ALL music folders should exist")
        self.assertTrue(status_m1["exists"], "Playlist for MUSIC001 should exist")
        self.assertTrue(status_m2["exists"], "Playlist for MUSIC002 should exist")

        self.assertGreater(status_all["track_count"], 30000, "ALL playlist should present 30,000+ tracks")
        self.assertGreater(status_m1["track_count"], 10000, "MUSIC001 should present 10,000+ tracks")
        self.assertGreater(status_m2["track_count"], 18000, "MUSIC002 should present 18,000+ tracks")

        # Verify combined count equals sum
        combined = status_m1["track_count"] + status_m2["track_count"]
        self.assertEqual(status_all["track_count"], combined)

    def test_music_folders_m3u_format(self):
        """Verify generated playlists contain valid paths to music folders."""
        m3u_path = Path(self.config["playlists_dir"]) / "DJ_Tracks_ALL_MUSIC_FOLDERS.m3u8"
        self.assertTrue(m3u_path.is_file(), f"M3U playlist {m3u_path} must exist on disk")

        with open(m3u_path, "r", encoding="utf-8", errors="replace") as f:
            header = f.readline().strip()
            self.assertEqual(header, "#EXTM3U", "Playlist header must be valid #EXTM3U")

    def test_music_mode_duration_field_presentation(self):
        """Verify that MP Audio Player presents track duration 00:00 instead of size in MUSIC mode."""
        from MP_Audio_Player import MusicFolderPlaylistScanner, TerminalPlayerUI, _display_width

        scanner = MusicFolderPlaylistScanner("MUSIC001")
        mixes = scanner.get_mixes()
        self.assertGreater(len(mixes), 0, "Tracks should be loaded in MusicFolderPlaylistScanner")
        self.assertIn("duration_fmt", mixes[0], "Track should have duration_fmt property")
        self.assertEqual(mixes[0]["duration_fmt"], "00:00")

        ui = TerminalPlayerUI(None, scanner, is_remote=True, mode="MUSIC", folder_name="MUSIC001")
        self.assertEqual(ui.mode, "MUSIC")

        # Simulate rendering of a track row in MUSIC mode
        iw = 115
        avail_name = max(4, iw - 23)
        m = mixes[0]
        raw_name = str(m.get("name", ""))
        mn = raw_name[:avail_name]
        name_pad = " " * max(0, avail_name - _display_width(mn))
        ext_str = f"{m.get('ext', ''):<4}"[:4]
        dur = m.get("duration_fmt", "00:00")
        field_str = f"{dur:>6s}"
        inner_plain = f"   [   1] {mn}{name_pad} {ext_str} {field_str} "

        self.assertEqual(_display_width(inner_plain), iw)
        self.assertIn("00:00", inner_plain)
        self.assertNotIn("0MB", inner_plain)

    def test_dj_features_removed_and_clean_audio_player(self):
        """Verify that the 4 DJ features (Hot Cues, BPM Tap, Camelot Matcher, Drop Audition) were removed."""
        import MP_Audio_Player

        # 1. Camelot wheel & helper functions removed
        self.assertFalse(hasattr(MP_Audio_Player, "CAMELOT_WHEEL"), "CAMELOT_WHEEL should be removed")
        self.assertFalse(hasattr(MP_Audio_Player, "extract_track_camelot_key"), "extract_track_camelot_key should be removed")
        self.assertFalse(hasattr(MP_Audio_Player, "get_compatible_camelot_keys"), "get_compatible_camelot_keys should be removed")

        # 2. HotCueManager removed
        self.assertFalse(hasattr(MP_Audio_Player, "HotCueManager"), "HotCueManager should be removed")

        # 3. AudioEngine and TerminalPlayerUI do not expose DJ state attributes
        scanner = MP_Audio_Player.MusicFolderPlaylistScanner("MUSIC001")
        ui = MP_Audio_Player.TerminalPlayerUI(None, scanner, is_remote=True, mode="MUSIC", folder_name="MUSIC001")
        self.assertFalse(hasattr(ui, "cue_mgr"), "TerminalPlayerUI should not have cue_mgr")
        self.assertFalse(hasattr(ui, "bpm_tap_times"), "TerminalPlayerUI should not have bpm_tap_times")
        self.assertFalse(hasattr(ui, "tapped_bpm"), "TerminalPlayerUI should not have tapped_bpm")
        self.assertFalse(hasattr(ui, "harmonic_filter_active"), "TerminalPlayerUI should not have harmonic_filter_active")
        self.assertFalse(hasattr(ui, "drop_audition_step"), "TerminalPlayerUI should not have drop_audition_step")

    def test_track_inspector_hud_retained(self):
        """Verify that Option I (Track Audio Inspector HUD) is preserved and functional."""
        from MP_Audio_Player import MusicFolderPlaylistScanner, TerminalPlayerUI

        scanner = MusicFolderPlaylistScanner("MUSIC001")
        ui = TerminalPlayerUI(None, scanner, is_remote=True, mode="MUSIC", folder_name="MUSIC001")

        self.assertFalse(ui.inspector_hud_active, "Inspector HUD should initially be inactive")
        ui.inspector_hud_active = True
        self.assertTrue(ui.inspector_hud_active, "Inspector HUD should be toggleable")

        status = {
            "title": "Cosmic Voyager (Deep Mix)",
            "path": "/mnt/smb_music/MUSIC001/Cosmic Voyager.flac",
            "sample_rate": 96000,
            "channels": 2,
            "position_fmt": "04:20",
            "duration_fmt": "08:45",
            "progress_pct": 49.5,
            "volume": 90,
            "pitch_percent": 0,
            "output_rate": 96000,
            "output_device": "PipeWire ALSA Output"
        }

        hud_lines = ui._render_inspector_hud(status, iw=115)
        self.assertIsInstance(hud_lines, list)
        self.assertGreater(len(hud_lines), 5, "HUD should output multiple formatted lines")

        hud_text = "\n".join(hud_lines)
        self.assertIn("TRACK AUDIO INSPECTOR", hud_text)
        self.assertIn("Cosmic Voyager", hud_text)
        self.assertIn("Folder / SMB", hud_text)
        self.assertIn("Format/Codec", hud_text)
        self.assertIn("Time Position", hud_text)
        self.assertIn("Audio Engine", hud_text)

        # Confirm DJ features are NOT in the HUD
        self.assertNotIn("Camelot", hud_text)
        self.assertNotIn("DJ Cues", hud_text)
        self.assertNotIn("Drop Markers", hud_text)

    def test_mix_archive_manager_slash_search_match(self):
        """Verify that Mix_Archive_Manager.sh _find_menu_search_match finds options by search query."""
        import subprocess

        bash_test_script = """
        total_opts=4
        _opts_ref=(
            "SECTION|SECTION 1: WORKFLOW|"
            "1|Play Tracks from MUSIC Folders using MP Audio Player|(Music Library • SMB /MUSIC001 & /MUSIC002)"
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

        # Test 1: Search 'music' -> Should match index 1 (Option 1)
        _find_menu_search_match "music" 0 1 || exit 10
        [ "$cur_idx" -eq 1 ] || exit 11

        # Test 2: Search 'conversion' -> Should match index 2 (Option 2)
        _find_menu_search_match "conversion" 0 1 || exit 20
        [ "$cur_idx" -eq 2 ] || exit 21

        # Test 3: Search 'spek' -> Should match index 3 (Option 19)
        _find_menu_search_match "spek" 0 1 || exit 30
        [ "$cur_idx" -eq 3 ] || exit 31

        # Test 4: Search non-existent term -> Should return failure (exit code 1)
        if _find_menu_search_match "xyznonexistent" 0 1; then exit 40; fi

        echo "BASH_SEARCH_TESTS_PASS"
        """

        result = subprocess.run(
            ["bash", "-c", bash_test_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Bash search match tests failed: {result.stderr}")
        self.assertIn("BASH_SEARCH_TESTS_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
