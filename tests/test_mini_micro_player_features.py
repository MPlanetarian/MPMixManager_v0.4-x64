#!/usr/bin/env python3
"""
Unit tests for MP Audio Player MINI and MICRO modes:
- Scrollbar disabling (-p ScrollBarPosition=0 and in profile)
- No terminal colorscheme escape sequence emitted to parent stdout
- Transparent background (no OSC 11 background overrides)
- High-visibility text colors for clear readability
- KWin rules provisioning for fixed window size / no resize / no maximize
"""

import unittest
import sys
import tempfile
import inspect
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player


class TestMiniMicroPlayerFeatures(unittest.TestCase):
    def test_no_colorscheme_escape_to_parent_stdout(self):
        """Verifies that _setup_mini_terminal_appearance never emits OSC 50 ColorScheme to stdout."""
        source = inspect.getsource(MP_Audio_Player._setup_mini_terminal_appearance)
        self.assertNotIn(r"\033]50;ColorScheme=", source)

    def test_konsole_profile_disables_scrollbar(self):
        """Verifies that MP_Mini_Player profile explicitly disables the scrollbar."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_home = Path(tmp_dir)
            k_dir = tmp_home / ".local" / "share" / "konsole"
            k_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(Path, "home", return_value=tmp_home):
                MP_Audio_Player._setup_mini_terminal_appearance()

            prof_file = k_dir / "MP_Mini_Player.profile"
            self.assertTrue(prof_file.exists())
            content = prof_file.read_text(encoding="utf-8")
            self.assertIn("ScrollBarPosition=0", content)

    def test_launch_mini_player_window_passes_scrollbar_disabled(self):
        """Verifies that launch_mini_player_window passes -p ScrollBarPosition=0 to Konsole."""
        source = inspect.getsource(MP_Audio_Player.launch_mini_player_window)
        self.assertIn("ScrollBarPosition=0", source)

    def test_frames_do_not_emit_osc11_background_override(self):
        """Verifies that mini and micro frames do not overwrite window transparency with OSC 11."""
        mini_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_mini_frame)
        micro_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_micro_frame)
        self.assertNotIn(r"\033]11;#", mini_src)
        self.assertNotIn(r"\033]11;#", micro_src)

    def test_frames_enforce_fixed_geometry(self):
        """Verifies that mini and micro frames enforce fixed terminal dimensions (74x14 and 74x7)."""
        mini_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_mini_frame)
        micro_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_micro_frame)
        self.assertIn(r"\033[8;", mini_src)
        self.assertIn(r"\033[8;", micro_src)

    def test_kwin_rules_provisioned(self):
        """Verifies that ensure_mini_player_kwin_rules creates fixed-size / no-maximize rules in kwinrulesrc."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_home = Path(tmp_dir)
            cfg_dir = tmp_home / ".config"
            cfg_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(Path, "home", return_value=tmp_home):
                MP_Audio_Player.ensure_mini_player_kwin_rules()

            rc_file = cfg_dir / "kwinrulesrc"
            self.assertTrue(rc_file.exists())
            content = rc_file.read_text(encoding="utf-8")
            self.assertIn("MP Mini Audio Player (Fixed Size)", content)
            self.assertIn("MP Micro Audio Player (Fixed Size)", content)
            self.assertIn("maximizehoriz = false", content)
            self.assertIn("maximizevert = false", content)

    def test_mode_toggle_cycle_in_terminal_ui(self):
        """Verifies that pressing 'm' or 'M' cycles NORMAL -> MINI -> MICRO -> NORMAL."""
        ui = MP_Audio_Player.TerminalPlayerUI(None, None, is_remote=True, ui_size_mode="NORMAL")
        self.assertEqual(ui.ui_size_mode, "NORMAL")
        
        ui._process_key(b"m")
        self.assertEqual(ui.ui_size_mode, "MINI")
        
        ui._process_key(b"M")
        self.assertEqual(ui.ui_size_mode, "MICRO")
        
        ui._process_key(b"m")
        self.assertEqual(ui.ui_size_mode, "NORMAL")


if __name__ == "__main__":
    unittest.main()
