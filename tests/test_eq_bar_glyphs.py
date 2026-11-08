#!/usr/bin/env python3
"""Dual Stereo, Stardust, and Master Spectrum bar caps use console-safe glyphs.

Lucida Console and Consolas do not include eighth-block caps, the peak mark ▔,
or the stardust marks ✦ ✧ ⋆ ╵. On Windows those cells draw as the wrong symbol.
"""

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from MP_Audio_Player import EqualizerVisualizer

MISSING = ("✦", "◆", "✧", "⋆", "━", "▔", "▂", "▃", "▅", "▆", "▇", "▁", "╵", "⠄", "⠂", "⠁", "⠈", "⡀")


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


class TestEqualizerBarGlyphs(unittest.TestCase):
    def _plain(self, lines):
        return strip_ansi("\n".join(lines))

    def test_stereo_and_master_limited_caps(self):
        viz = EqualizerVisualizer()
        levels = np.full(24, 0.30)
        peaks = np.full(24, 0.85)
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=True):
            stereo = self._plain(viz.render_stereo_eq(levels, levels, peaks, width=80, height=7))
            master = self._plain(viz.render_master_spectrum(levels, peaks, height=7))
        for plain in (stereo, master):
            for missing in MISSING:
                self.assertNotIn(missing, plain)
            self.assertIn("▄", plain)
            self.assertIn("█", plain)
        self.assertIn("PEAK HOLD •", master)

    def test_stereo_and_master_full_caps(self):
        viz = EqualizerVisualizer()
        levels = np.full(24, 0.30)
        peaks = np.full(24, 0.85)
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=False):
            stereo = self._plain(viz.render_stereo_eq(levels, levels, peaks, width=80, height=7))
            master = self._plain(viz.render_master_spectrum(levels, peaks, height=7))
        self.assertIn("▁", stereo)
        self.assertIn("▔", stereo)
        self.assertIn("▁", master)
        self.assertIn("▔", master)
        self.assertIn("PEAK HOLD ✦", master)

    def test_stardust_limited_crest_and_peak(self):
        viz = EqualizerVisualizer(style="stardust_particles_eq")
        viz.dust_rng.seed(1)
        levels = np.full(16, 0.34)
        peaks = np.full(16, 0.90)
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=True):
            plain = self._plain(viz.render_stardust_particles_eq(
                levels, levels, peaks, peaks, width=80, height=7, rms=0.2, peak_db=-3.0
            ))
        for missing in MISSING:
            self.assertNotIn(missing, plain)
        self.assertIn("│", plain)
        self.assertIn("•", plain)

    def test_stardust_full_keeps_star_crest(self):
        viz = EqualizerVisualizer(style="stardust_particles_eq")
        viz.dust_rng.seed(1)
        levels = np.full(16, 0.34)
        peaks = np.full(16, 0.90)
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=False):
            plain = self._plain(viz.render_stardust_particles_eq(
                levels, levels, peaks, peaks, width=80, height=7, rms=0.05, peak_db=-20.0
            ))
        self.assertIn("✦", plain)
        self.assertIn("╵", plain)


if __name__ == "__main__":
    unittest.main()
