#!/usr/bin/env python3
"""
Unit tests for MP Audio Player MICRO mode:
- EQ visualizers display in MICRO mode when height >= 9
- Pressing 'e' and 'E' in MICRO mode cycles the EQ style without triggering export playlist
- Micro dynamic meter reflects active EQ style (Neon Prism, Stardust, VU, Oscilloscope, etc.)
"""

import unittest
import sys
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", s)


class TestMicroPlayerEQ(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.config_patch = patch.object(MP_Audio_Player, "CONFIG_DIR", self.temp_path)
        self.config_patch.start()

        self.mock_scanner = MagicMock()
        self.mock_scanner.get_mixes.return_value = []
        self.ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=self.mock_scanner,
            ui_size_mode="MICRO",
            is_remote=True
        )
        self.st = {
            "title": "Trance Roots 2026.flac",
            "path": "/archive/Trance Roots 2026.flac",
            "state": "playing",
            "position_fmt": "02:15",
            "duration_fmt": "07:30",
            "progress_pct": 30.0,
            "volume": 85,
            "pitch_percent": 0,
            "levels": [0.5] * 24,
            "peaks": [0.7] * 24,
            "levels_left": [0.5] * 24,
            "levels_right": [0.5] * 24,
            "peaks_left": [0.7] * 24,
            "peaks_right": [0.7] * 24,
            "rms_level": 0.1,
            "peak_db": -3.0
        }

    def tearDown(self):
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def test_key_e_and_E_cycle_style_in_micro_mode(self):
        """Verifies that both lowercase 'e' and uppercase 'E' cycle EQ style in MICRO mode without export mode."""
        self.ui.visualizer.style_idx = 0
        initial_style = self.ui.visualizer.style

        # Test lowercase 'e'
        self.ui._process_key(b"e")
        self.assertNotEqual(self.ui.visualizer.style, initial_style)
        self.assertFalse(self.ui.export_mode, "Lowercase 'e' must not trigger export playlist")
        second_style = self.ui.visualizer.style

        # Test uppercase 'E'
        self.ui._process_key(b"E")
        self.assertNotEqual(self.ui.visualizer.style, second_style)
        self.assertFalse(self.ui.export_mode, "Uppercase 'E' in MICRO mode must cycle EQ and not trigger export playlist")

    def test_key_e_and_E_cycle_style_in_mini_mode(self):
        """Verifies that both 'e' and 'E' cycle EQ style in MINI mode without export mode."""
        self.ui.ui_size_mode = "MINI"
        self.ui.visualizer.style_idx = 0
        initial_style = self.ui.visualizer.style

        self.ui._process_key(b"e")
        self.assertNotEqual(self.ui.visualizer.style, initial_style)
        self.assertFalse(self.ui.export_mode)

        mid_style = self.ui.visualizer.style
        self.ui._process_key(b"E")
        self.assertNotEqual(self.ui.visualizer.style, mid_style)
        self.assertFalse(self.ui.export_mode)

    def test_micro_frame_displays_eq_visualizer(self):
        """Verifies that _draw_micro_frame renders the visualizer EQ lines when h >= 9."""
        captured_lines = []

        def mock_present(lines, w, h):
            captured_lines.extend(lines)

        with patch("MP_Audio_Player._present_frame", side_effect=mock_present):
            self.ui._draw_micro_frame(74, 14, self.st)

        text_dump = strip_ansi("\n".join(captured_lines))
        self.assertIn("MP MICRO AUDIO PLAYER", text_dump)
        self.assertIn("EQ", text_dump)

        # Check visualizer rendered header (e.g. LEFT CHANNEL or NEON PRISM or HIGH-RESOLUTION)
        has_eq_visualizer = any(
            ("LEFT" in line or "HIGH-RESOLUTION" in line or "ANALOG" in line or "OSCILLOSCOPE" in line or "STREAM" in line)
            for line in captured_lines
        )
        self.assertTrue(has_eq_visualizer, "MICRO mode must render the EQ visualizer lines")

    def test_all_eq_styles_render_in_micro_mode(self):
        """Verifies that every style in STYLES renders without error in MICRO mode."""
        for style in self.ui.visualizer.STYLES:
            self.ui.visualizer.style_idx = self.ui.visualizer.STYLES.index(style)
            captured_lines = []

            with patch("MP_Audio_Player._present_frame", side_effect=lambda l, w, h: captured_lines.extend(l)):
                self.ui._draw_micro_frame(74, 14, self.st)

            self.assertGreaterEqual(len(captured_lines), 9, f"Style {style} should output at least 9 lines in micro mode")
            text_dump = strip_ansi("\n".join(captured_lines))
            self.assertIn("MP MICRO AUDIO PLAYER", text_dump)
            self.assertIn("EQ", text_dump)


if __name__ == "__main__":
    unittest.main()
