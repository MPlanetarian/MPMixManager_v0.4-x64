#!/usr/bin/env python3
"""Neon Chroma Prism bar caps and the highlighted playlist mark use console-safe glyphs.

Git Bash on Windows draws with Lucida Console or Consolas. Those fonts do not
include eighth-block caps, the prism peak marks, or U+25B6 ▶. Missing glyphs
show up as the wrong symbol at the top of each bar and beside the highlighted mix.
"""

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
from MP_Audio_Player import EqualizerVisualizer, TerminalPlayerUI, PLAYLIST_ACTIVE_MARK


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


class TestNeonPrismPlaylistGlyphs(unittest.TestCase):
    def test_limited_console_bar_caps_and_peaks(self):
        viz = EqualizerVisualizer(style="neon_prism_eq")
        levels = np.full(16, 0.30)
        peaks = np.full(16, 0.91)
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=True):
            lines = viz.render_neon_prism_eq(levels, levels, peaks, peaks, width=80, height=7)
        plain = strip_ansi("\n".join(lines))
        for missing in ("✦", "◆", "━", "▂", "▃", "▅", "▆", "▇", "▁"):
            self.assertNotIn(missing, plain)
        self.assertIn("▄", plain)
        self.assertIn("█", plain)
        self.assertIn("▲", plain)

    def test_full_console_keeps_eighth_caps(self):
        viz = EqualizerVisualizer(style="neon_prism_eq")
        levels = np.full(16, 0.30)
        peaks = np.full(16, 0.91)
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=False):
            lines = viz.render_neon_prism_eq(levels, levels, peaks, peaks, width=80, height=7)
        plain = strip_ansi("\n".join(lines))
        self.assertIn("▁", plain)
        self.assertTrue(("✦" in plain) or ("◆" in plain))

    def test_highlighted_playlist_mark_is_console_pointer(self):
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Mix 01 - Astral Projection", "path": "/path/to/mix1.mp3", "folder": "Chill", "ext": "MP3", "size_mb": 12},
            {"name": "Mix 02 - Solar Eclipse", "path": "/path/to/mix2.mp3", "folder": "Trance", "ext": "MP3", "size_mb": 18},
        ]
        ui = TerminalPlayerUI(engine=None, scanner=mock_scanner, ui_size_mode="STANDARD", is_remote=True)
        ui.selected_row = 0
        st = {
            "title": "Mix 01 - Astral Projection",
            "path": "/path/to/mix1.mp3",
            "state": "playing",
            "index": 0,
            "position_fmt": "02:00",
            "duration_fmt": "60:00",
            "progress_pct": 3.3,
            "volume": 80,
            "pitch_percent": 0,
            "levels": [0.5] * 24,
            "peaks": [0.7] * 24,
            "levels_left": [0.5] * 24,
            "levels_right": [0.5] * 24,
            "peaks_left": [0.7] * 24,
            "peaks_right": [0.7] * 24,
            "rms_level": 0.1,
            "peak_db": -3.0,
        }
        captured = []
        with patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured.extend(lines)), \
             patch("MP_Audio_Player._win_visible_size", return_value=(100, 35)):
            ui._get_status = MagicMock(return_value=st)
            ui._draw_frame()
        rows = [line for line in captured if "│" in line and "Mix 01 - Astral Projection" in line]
        self.assertTrue(rows, "Highlighted playlist row was not drawn")
        row = rows[0]
        self.assertIn(PLAYLIST_ACTIVE_MARK, row)
        self.assertNotIn("▶", row)
        self.assertEqual(PLAYLIST_ACTIVE_MARK, "\u25ba")


if __name__ == "__main__":
    unittest.main()
