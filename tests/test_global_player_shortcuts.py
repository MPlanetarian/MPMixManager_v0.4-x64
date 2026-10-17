#!/usr/bin/env python3
"""
Unit tests for global MP Audio Player shortcuts and options:
- Space toggle playback (only if running)
- M open player in a new window
- micro mode toggle in player
"""

import unittest
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PLAYER_PY = BASE_DIR / "MP_Audio_Player.py"

class TestGlobalPlayerShortcuts(unittest.TestCase):
    def test_toggle_only_if_running_flag_logic(self):
        """Verifies that with only_if_running=True and daemon_running=False, no process or daemon is started."""
        # Test directly via subprocess with dummy port/pid env to ensure no daemon runs
        res = subprocess.run(
            [sys.executable, "-c", """
import sys
from unittest.mock import patch
import MP_Audio_Player

# Mock daemon_running as False and verify _spawn_player_daemon is never called
with patch.object(MP_Audio_Player, "is_player_daemon_running", return_value=False), \
     patch.object(MP_Audio_Player, "_spawn_player_daemon") as mock_spawn:
    test_args = ["MP_Audio_Player.py", "--toggle", "--only-if-running"]
    with patch.object(sys, "argv", test_args):
        try:
            MP_Audio_Player.main()
        except SystemExit as e:
            assert e.code == 0
    assert not mock_spawn.called, "Should not spawn daemon when only_if_running is set"
print("SUCCESS")
"""],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        self.assertIn("SUCCESS", res.stdout)

    def test_new_window_arg_recognized(self):
        """Verifies that --new-window is accepted by argument parser."""
        res = subprocess.run(
            [sys.executable, str(PLAYER_PY), "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--new-window", res.stdout)
        self.assertIn("--only-if-running", res.stdout)

if __name__ == "__main__":
    unittest.main()
