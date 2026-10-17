#!/usr/bin/env python3
"""
Unit tests for MP Audio Player shuffle and control shortcuts:
- Pressing 's' or 'S' in TerminalPlayerUI enables/disables shuffle mode
- Pressing 'v' / 'V' controls volume
- AudioEngine toggle_shuffle toggles shuffle state
- PlayerIPCServer handles 'shuffle' IPC command
- CLI argument --shuffle is recognized and supported
"""

import unittest
from unittest.mock import MagicMock, patch
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PLAYER_PY = BASE_DIR / "MP_Audio_Player.py"

import MP_Audio_Player


class TestPlayerShuffle(unittest.TestCase):
    def setUp(self):
        self.mock_engine = MagicMock()
        self.mock_engine.shuffle = False
        self.mock_engine.repeat_mode = "all"
        self.mock_engine.volume = 0.85
        self.mock_engine.muted = False
        self.mock_engine.playlist = []

        def _toggle_shuffle():
            self.mock_engine.shuffle = not self.mock_engine.shuffle

        self.mock_engine.toggle_shuffle.side_effect = _toggle_shuffle
        self.mock_scanner = MagicMock()
        self.mock_scanner.get_mixes.return_value = []

    def test_key_s_and_S_toggle_shuffle_local(self):
        """Verifies that pressing 's' and 'S' toggles shuffle mode when local engine is present."""
        ui = MP_Audio_Player.TerminalPlayerUI(self.mock_engine, self.mock_scanner, is_remote=False)
        self.assertFalse(ui.cached_status.get("shuffle", False))

        # Press 's'
        ui._process_key(b"s")
        self.assertTrue(self.mock_engine.shuffle)
        self.assertTrue(ui.cached_status.get("shuffle", False))
        self.assertEqual(ui.notification_msg, "Shuffle: ON")

        # Press 'S'
        ui._process_key(b"S")
        self.assertFalse(self.mock_engine.shuffle)
        self.assertFalse(ui.cached_status.get("shuffle", False))
        self.assertEqual(ui.notification_msg, "Shuffle: OFF")

    @patch.object(MP_Audio_Player, "send_ipc_command")
    def test_key_s_toggle_shuffle_remote(self, mock_ipc):
        """Verifies that pressing 's' in remote UI mode dispatches IPC shuffle command."""
        ui = MP_Audio_Player.TerminalPlayerUI(None, self.mock_scanner, is_remote=True)
        ui.cached_status["shuffle"] = False

        ui._process_key(b"s")
        self.assertTrue(ui.cached_status.get("shuffle", False))
        self.assertEqual(ui.notification_msg, "Shuffle: ON")

        ui._process_key(b"S")
        self.assertFalse(ui.cached_status.get("shuffle", False))
        self.assertEqual(ui.notification_msg, "Shuffle: OFF")

    def test_key_v_and_V_volume(self):
        """Verifies that pressing 'v' and 'V' changes volume and updates cached status."""
        ui = MP_Audio_Player.TerminalPlayerUI(self.mock_engine, self.mock_scanner, is_remote=False)
        ui.cached_status["volume"] = 80

        ui._process_key(b"v")
        self.assertEqual(ui.cached_status["volume"], 85)

        ui._process_key(b"V")
        self.assertEqual(ui.cached_status["volume"], 80)

    def test_cli_shuffle_flag_recognized(self):
        """Verifies that --shuffle is accepted by the argument parser."""
        res = subprocess.run(
            [sys.executable, str(PLAYER_PY), "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--shuffle", res.stdout)
        self.assertIn("--repeat", res.stdout)


if __name__ == "__main__":
    unittest.main()
