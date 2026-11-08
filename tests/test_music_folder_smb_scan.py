#!/usr/bin/env python3
"""SMB playlist scans must use rclone metadata and must not stat a wedged mount."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import music_folders_manager as mfm


def _folder():
    return {
        "type": "smb", "id": "DATAMAC1", "name": "DATAMAC1",
        "host": "192.168.1.138", "share": "DATAMAC1", "subpath": "", "user": "",
    }


def _config():
    return {
        "smb_user": "mplanetarian", "smb_password": "secret", "legacy_host": "",
        "mount_root": Path("/tmp/MUSIC_SMB"), "playlists_dir": Path("/tmp"),
        "base_dir": Path("/tmp"),
    }


class _Proc:
    def __init__(self, lines, errors="", rc=1):
        self.stdout = iter(lines)
        self.stderr = iter(errors.splitlines(True))
        self.rc = rc

    def wait(self):
        return self.rc


class TestSmbPlaylistScan(unittest.TestCase):
    def test_listing_uses_rclone_size_and_does_not_stat_the_mount(self):
        proc = _Proc([
            "Notes.txt|12|2026-11-04 12:46:42\n",
            "Album/Song.mp3|5000000|2026-11-04 12:46:42\n",
            "._shadow.mp3|10|2026-11-04 12:46:42\n",
        ], errors="ERROR : .Trashes: permission denied\n", rc=1)
        with patch.object(mfm, "connect_folder", return_value=(True, "ok")), \
             patch.object(mfm, "_scan_filesystem") as filesystem, \
             patch.object(mfm.shutil, "which", return_value="/usr/bin/rclone"), \
             patch.object(mfm.subprocess, "Popen", return_value=proc), \
             patch.object(mfm.os, "stat", side_effect=AssertionError("mount stat")):
            tracks = mfm.scan_folder_tracks(_folder(), _config(), interactive=False)
        filesystem.assert_not_called()
        self.assertEqual([t["name"] for t in tracks], ["Song.mp3"])
        self.assertEqual(tracks[0]["size_mb"], round(5000000 / (1024 * 1024), 2))
        self.assertTrue(tracks[0]["path"].endswith("Album/Song.mp3") or tracks[0]["path"].endswith("Album\\Song.mp3"))
        self.assertGreater(tracks[0]["mtime"], 0)

    def test_failed_listing_does_not_walk_the_mount(self):
        proc = _Proc([], errors="couldn't connect SMB: logon is invalid\n", rc=1)
        with patch.object(mfm, "connect_folder", return_value=(False, "not responding")), \
             patch.object(mfm, "_scan_filesystem") as filesystem, \
             patch.object(mfm.shutil, "which", return_value="/usr/bin/rclone"), \
             patch.object(mfm.subprocess, "Popen", return_value=proc), \
             patch.object(mfm.os, "stat", side_effect=AssertionError("mount stat")):
            notes = []
            tracks = mfm.scan_folder_tracks(_folder(), _config(), progress_cb=notes.append, interactive=False)
        filesystem.assert_not_called()
        self.assertIsNone(tracks)
        self.assertTrue(any("logon is invalid" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
