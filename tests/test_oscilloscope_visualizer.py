import unittest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import numpy as np
import time
from MP_Audio_Player import EqualizerVisualizer, _display_width


class TestOscilloscopeVisualizer(unittest.TestCase):
    def setUp(self):
        self.eq = EqualizerVisualizer(default_style="oscilloscope")

    def test_oscilloscope_style_registered(self):
        self.assertIn("oscilloscope", EqualizerVisualizer.STYLES)
        self.assertEqual(self.eq.style, "oscilloscope")

    def test_oscilloscope_animation_over_time(self):
        """Verify that the oscilloscope changes its waveform output over time (animating, not frozen)."""
        levels = np.array([0.5, 0.4, 0.3, 0.2] + [0.1] * 20)
        status = {
            "state": "playing",
            "levels": levels.tolist(),
            "rms_level": 0.25,
            "peak_db": -6.0,
            "pitch_percent": 0,
        }

        lines_t0 = self.eq.render_oscilloscope(levels, status=status, width=80, height=5)
        time.sleep(0.08)
        lines_t1 = self.eq.render_oscilloscope(levels, status=status, width=80, height=5)

        # Ensure lines are generated and match expected count (hh=2 => 5 rows + 2 borders = 7)
        self.assertEqual(len(lines_t0), 7)
        self.assertEqual(len(lines_t1), 7)

        # The inner waveform content must change over time (animation is active)
        inner_t0 = "\n".join(lines_t0[1:-1])
        inner_t1 = "\n".join(lines_t1[1:-1])
        self.assertNotEqual(inner_t0, inner_t1, "Oscilloscope did not animate between time intervals!")

    def test_oscilloscope_with_live_pcm_waveform(self):
        """Verify oscilloscope handles live PCM buffer input."""
        levels = np.array([0.3] * 24)
        pcm_wave = [float(np.sin(i * 0.2)) for i in range(80)]
        status = {
            "state": "playing",
            "levels": levels.tolist(),
            "waveform": pcm_wave,
            "rms_level": 0.3,
            "peak_db": -3.0,
            "pitch_percent": 5,
        }

        lines = self.eq.render_oscilloscope(levels, status=status, width=80, height=5)
        self.assertEqual(len(lines), 7)
        for line in lines:
            self.assertEqual(_display_width(line), 78)

    def test_oscilloscope_various_heights(self):
        """Test rendering at heights 7, 5, and 3."""
        status = {"state": "playing", "levels": [0.4] * 24, "rms_level": 0.2}
        levels = np.array(status["levels"])

        # Height 7: hh=3 => 7 inner rows + 2 borders = 9 lines
        res_h7 = self.eq.render_oscilloscope(levels, status=status, width=80, height=7)
        self.assertEqual(len(res_h7), 9)

        # Height 5: hh=2 => 5 inner rows + 2 borders = 7 lines
        res_h5 = self.eq.render_oscilloscope(levels, status=status, width=80, height=5)
        self.assertEqual(len(res_h5), 7)

        # Height 3: hh=1 => 3 inner rows + 2 borders = 5 lines
        res_h3 = self.eq.render_oscilloscope(levels, status=status, width=80, height=3)
        self.assertEqual(len(res_h3), 5)

    def test_oscilloscope_narrow_terminal_width(self):
        """Test rendering in narrower terminals (e.g. mini mode width=60)."""
        status = {"state": "playing", "levels": [0.3] * 24, "rms_level": 0.2}
        levels = np.array(status["levels"])

        res_w60 = self.eq.render_oscilloscope(levels, status=status, width=60, height=5)
        self.assertEqual(len(res_w60), 7)
        expected_w = _display_width(res_w60[0])
        self.assertLessEqual(expected_w, 60)
        for line in res_w60:
            self.assertEqual(_display_width(line), expected_w)

    def test_equalizer_visualizer_render_dispatch(self):
        """Test that EqualizerVisualizer.render dispatches to oscilloscope seamlessly."""
        status = {
            "state": "playing",
            "levels": [0.5] * 24,
            "peaks": [0.5] * 24,
            "levels_left": [0.5] * 24,
            "levels_right": [0.5] * 24,
            "rms_level": 0.3,
            "peak_db": -4.0,
            "pitch_percent": 0,
        }
        res = self.eq.render(status, width=80, height=5)
        self.assertEqual(len(res), 7)
        self.assertIn("OSCILLOSCOPE", res[0])


if __name__ == "__main__":
    unittest.main()
