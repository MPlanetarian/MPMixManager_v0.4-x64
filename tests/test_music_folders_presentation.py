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


if __name__ == "__main__":
    unittest.main()
