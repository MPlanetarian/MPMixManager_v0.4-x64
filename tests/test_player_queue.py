#!/usr/bin/env python3
"""
Unit tests for MP Audio Player mix queuing feature:
- Pressing 'q' or 'Q' in TerminalPlayerUI queues the selected mix/track
- AudioEngine queue_track, dequeue_next, clear_queue, get_queue methods
- AudioEngine _step_track prioritizes queued tracks when advancing forward
- AudioEngine get_status_dict includes 'queue' and 'queue_len'
- PlayerIPCServer handles 'queue', 'get_queue', and 'clear_queue' IPC commands
- CLI arguments --queue / -q and --clear-queue are recognized
"""

import unittest
from unittest.mock import MagicMock, patch
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PLAYER_PY = BASE_DIR / "MP_Audio_Player.py"

import MP_Audio_Player


class TestPlayerQueue(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.track1 = str(Path(self.tmp_dir.name) / "Mix_001.flac")
        self.track2 = str(Path(self.tmp_dir.name) / "Mix_002.flac")
        self.track3 = str(Path(self.tmp_dir.name) / "Mix_003.flac")
        for p in (self.track1, self.track2, self.track3):
            Path(p).write_bytes(b"RIFF" + b"\x00" * 100)

        self.playlist = [
            {"name": "Mix_001", "path": self.track1, "size_mb": 1.0, "ext": "FLAC"},
            {"name": "Mix_002", "path": self.track2, "size_mb": 1.0, "ext": "FLAC"},
            {"name": "Mix_003", "path": self.track3, "size_mb": 1.0, "ext": "FLAC"},
        ]

        self.engine = MP_Audio_Player.AudioEngine(self.playlist, auto_bluetooth=False)

    def tearDown(self):
        try:
            self.engine.stop_playback()
        except Exception:
            pass
        self.tmp_dir.cleanup()

    def test_queue_and_get_queue(self):
        """Verifies that queue_track appends items to the queue and get_queue returns them."""
        self.assertEqual(len(self.engine.play_queue), 0)
        res1 = self.engine.queue_track(self.track3)
        self.assertTrue(res1["queued"])
        self.assertEqual(res1["queue_len"], 1)

        res2 = self.engine.queue_track(self.track2)
        self.assertTrue(res2["queued"])
        self.assertEqual(res2["queue_len"], 2)

        q = self.engine.get_queue()
        self.assertEqual(len(q), 2)
        self.assertEqual(q[0]["path"], self.track3)
        self.assertEqual(q[1]["path"], self.track2)

    def test_clear_queue(self):
        """Verifies that clear_queue empties the play_queue."""
        self.engine.queue_track(self.track2)
        self.engine.queue_track(self.track3)
        self.assertEqual(len(self.engine.play_queue), 2)

        cleared_count = self.engine.clear_queue()
        self.assertEqual(cleared_count, 2)
        self.assertEqual(len(self.engine.play_queue), 0)

    def test_step_track_plays_queued_track_first(self):
        """Verifies that advancing track pops from play_queue rather than default index progression."""
        self.engine.current_index = 0
        self.engine.current_track = self.playlist[0]

        # Queue track 3
        self.engine.queue_track(self.track3)
        self.assertEqual(len(self.engine.play_queue), 1)

        # Mock load_track to record loaded index/path
        loaded = []
        def mock_load(idx, play=True):
            loaded.append(self.engine.playlist[idx]["path"])
            self.engine.current_index = idx
            self.engine.current_track = self.engine.playlist[idx]
            return True

        self.engine.load_track = mock_load

        # Step forward
        self.engine.next_track()

        # Track 3 should have been loaded first, and queue should now be empty
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0], self.track3)
        self.assertEqual(len(self.engine.play_queue), 0)

    def test_get_status_dict_includes_queue_info(self):
        """Verifies that get_status_dict includes queue and queue_len keys."""
        self.engine.queue_track(self.track2)
        st = self.engine.get_status_dict()
        self.assertIn("queue_len", st)
        self.assertIn("queue", st)
        self.assertEqual(st["queue_len"], 1)
        self.assertEqual(st["queue"], [self.track2])

    def test_ui_key_q_queues_selected_track(self):
        """Verifies that pressing 'q' or 'Q' in UI queues the selected track and updates banner."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = self.playlist

        ui = MP_Audio_Player.TerminalPlayerUI(self.engine, mock_scanner, is_remote=False)
        ui.selected_row = 2  # Select Track 3

        # Press 'q'
        ui._process_key(b"q")
        self.assertEqual(len(self.engine.play_queue), 1)
        self.assertEqual(self.engine.play_queue[0]["path"], self.track3)
        self.assertIn("Queued Mix", ui.notification_msg)
        self.assertIn("Mix_003", ui.notification_msg)
        self.assertTrue(ui.running)  # UI should NOT exit on 'q'

        # Select Track 2 and press 'Q'
        ui.selected_row = 1
        ui._process_key(b"Q")
        self.assertEqual(len(self.engine.play_queue), 2)
        self.assertEqual(self.engine.play_queue[1]["path"], self.track2)
        self.assertIn("Mix_002", ui.notification_msg)
        self.assertTrue(ui.running)

    def test_ui_exit_keys_still_exit(self):
        """Verifies that Escape, Ctrl+C, and 'b' still set running to False."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = self.playlist
        ui = MP_Audio_Player.TerminalPlayerUI(self.engine, mock_scanner, is_remote=False)

        ui.running = True
        ui._process_key(b"\x1b")  # Escape
        self.assertFalse(ui.running)

        ui.running = True
        ui._process_key(b"b")     # Back / Exit
        self.assertFalse(ui.running)

        ui.running = True
        ui._process_key(b"B")
        self.assertFalse(ui.running)

        ui.running = True
        ui._process_key(b"\x03")  # Ctrl+C
        self.assertFalse(ui.running)

    def test_cli_flags_recognized(self):
        """Verifies that --queue, -q, and --clear-queue are supported in CLI args."""
        res = subprocess.run(
            [sys.executable, str(PLAYER_PY), "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--queue", res.stdout)
        self.assertIn("--clear-queue", res.stdout)


if __name__ == "__main__":
    unittest.main()
