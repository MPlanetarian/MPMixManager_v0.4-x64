import unittest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from MP_Audio_Player import EqualizerVisualizer, TerminalPlayerUI, EqualizerManager, _display_width


class TestWideEqualizers(unittest.TestCase):
    def setUp(self):
        self.status = {
            "state": "playing",
            "levels": [0.5] * 24,
            "peaks": [0.6] * 24,
            "levels_left": [0.5] * 24,
            "levels_right": [0.5] * 24,
            "peaks_left": [0.6] * 24,
            "peaks_right": [0.6] * 24,
            "rms_level": 0.2,
            "peak_db": -3.0,
            "pitch_percent": 0,
            "waveform": [0.1 * i for i in range(50)],
        }

    def test_all_visualizer_styles_stretch_to_full_width_liquid_glass(self):
        """In MP Liquid Player (width=120, MP_LIQUID_GLASS=1), visualizers must stretch across full width."""
        os.environ["MP_LIQUID_GLASS"] = "1"
        try:
            for w in [80, 100, 120]:
                expected_line_w = w - 2
                for style in EqualizerVisualizer.STYLES:
                    vis = EqualizerVisualizer(default_style=style)
                    lines = vis.render(self.status, width=w, height=7)
                    self.assertGreater(len(lines), 0)
                    for idx, line in enumerate(lines):
                        lw = _display_width(line)
                        self.assertEqual(
                            lw,
                            expected_line_w,
                            f"Style {style} width mismatch at line {idx} for window width {w}: got {lw}, expected {expected_line_w}",
                        )
        finally:
            os.environ.pop("MP_LIQUID_GLASS", None)

    def test_equalizer_hud_stretches_to_full_width(self):
        """10-band Equalizer HUD must stretch cleanly to match inner width (iw=114 => line width=118)."""
        engine = MagicMock()
        engine.eq_manager = EqualizerManager()
        scanner = MagicMock()
        ui = TerminalPlayerUI(engine, scanner)

        hud_lines = ui._render_equalizer_hud(iw=114)
        self.assertGreater(len(hud_lines), 0)
        for idx, line in enumerate(hud_lines):
            lw = _display_width(line)
            self.assertEqual(
                lw,
                118,
                f"HUD width mismatch at line {idx}: got {lw}, expected 118",
            )


if __name__ == "__main__":
    unittest.main()
