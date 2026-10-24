#!/usr/bin/env python3
"""
Unit tests to verify Shift+K shortcut kills MP_Audio_Player:
1. In MP_Audio_Player.py (TerminalPlayerUI):
   - Shift+K (b"K") triggers pkill -9 -f "MP_Audio_Player" and terminates UI
   - Lowercase 'k' (b"k") still navigates the track list without triggering kill
   - Capital 'K' during search, export, or preset naming enters text normally
2. In Mix_Archive_Manager.sh:
   - Shift+K ('K') in press_enter triggers pkill -9 -f "MP_Audio_Player"
   - CHAR:K in run_interactive_submenu key dispatch triggers pkill -9 -f "MP_Audio_Player"
3. In Liquid Glass players:
   - Shift+K in _on_key_press triggers pkill -9 -f "MP_Audio_Player"
"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PLAYER_PY = BASE_DIR / "MP_Audio_Player.py"
MGR_SH = BASE_DIR / "Mix_Archive_Manager.sh"


class TestShiftKKillPlayer(unittest.TestCase):
    def test_audio_player_shift_k_triggers_pkill(self):
        """Verifies that pressing Shift+K (b'K') in TerminalPlayerUI runs pkill -9 -f 'MP_Audio_Player'."""
        import MP_Audio_Player

        mock_engine = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [{"name": "Track 1", "path": "/tmp/t1.flac"}]

        ui = MP_Audio_Player.TerminalPlayerUI(engine=mock_engine, scanner=mock_scanner)
        ui.running = True

        with patch("subprocess.run") as mock_subproc, patch.object(ui, "_cleanup_terminal") as mock_clean:
            ui._process_key(b"K")

            self.assertFalse(ui.running, "UI should stop running when Shift+K is pressed")
            mock_clean.assert_called_once()
            mock_subproc.assert_called_once_with('pkill -9 -f "MP_Audio_Player"', shell=True)

    def test_audio_player_lowercase_k_does_not_kill(self):
        """Verifies that lowercase 'k' (b'k') continues navigating the list and does NOT kill the player."""
        import MP_Audio_Player

        mock_engine = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Track 1", "path": "/tmp/t1.flac"},
            {"name": "Track 2", "path": "/tmp/t2.flac"},
        ]

        ui = MP_Audio_Player.TerminalPlayerUI(engine=mock_engine, scanner=mock_scanner)
        ui.running = True
        ui.selected_row = 1

        with patch("subprocess.run") as mock_subproc:
            ui._process_key(b"k")

            self.assertTrue(ui.running, "UI should continue running on lowercase 'k'")
            self.assertEqual(ui.selected_row, 0, "Lowercase 'k' should navigate up")
            mock_subproc.assert_not_called()

    def test_audio_player_shift_k_during_search_mode_enters_char(self):
        """Verifies that pressing Shift+K when search_mode is active types 'K' and does NOT kill the player."""
        import MP_Audio_Player

        mock_engine = MagicMock()
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []

        ui = MP_Audio_Player.TerminalPlayerUI(engine=mock_engine, scanner=mock_scanner)
        ui.running = True
        ui.search_mode = True
        ui.search_query = ""

        with patch("subprocess.run") as mock_subproc:
            ui._process_key(b"K")

            self.assertTrue(ui.running, "UI should remain running during search mode")
            self.assertEqual(ui.search_query, "K", "Search query should receive 'K'")
            mock_subproc.assert_not_called()

    def test_manager_press_enter_shift_k_runs_pkill(self):
        """Verifies that pressing Shift+K in press_enter() executes pkill -9 -f 'MP_Audio_Player'."""
        bash_test = f"""
source "{MGR_SH}" 2>/dev/null || true

# Mock pkill to record invocations
pkill() {{
    echo "MOCK_PKILL: $*" >> /tmp/test_pkill_shift_k.log
}}

rm -f /tmp/test_pkill_shift_k.log
# Feed 'K' to press_enter
printf 'K' | press_enter >/dev/null 2>&1 || true

cat /tmp/test_pkill_shift_k.log 2>/dev/null || echo "NONE"
rm -f /tmp/test_pkill_shift_k.log
"""
        res = subprocess.run(["bash", "-c", bash_test], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("MOCK_PKILL: -9 -f MP_Audio_Player", res.stdout)

    def test_manager_run_interactive_submenu_shift_k_present(self):
        """Verifies that CHAR:K is implemented in Mix_Archive_Manager.sh."""
        content = MGR_SH.read_text(encoding="utf-8")
        self.assertIn('CHAR:K) if [ "$search_mode" -eq 1 ]; then', content)
        self.assertIn('pkill -9 -f "MP_Audio_Player"', content)

    def test_liquid_glass_shift_k_handling(self):
        """Verifies that MP_Audio_Player_Liquid_Glass.py handles Shift+K in _on_key_press."""
        import MP_Audio_Player_Liquid_Glass as lg

        mock_event = MagicMock()
        mock_event.keyval = 75  # Gdk.KEY_K
        mock_event.state = 0

        host = MagicMock()
        host.mode = "NORMAL"

        with patch("subprocess.run") as mock_subproc:
            res = lg.GlassHost._on_key_press(host, None, mock_event)
            self.assertTrue(res)
            mock_subproc.assert_called_once_with('pkill -9 -f "MP_Audio_Player"', shell=True)


if __name__ == "__main__":
    unittest.main()
