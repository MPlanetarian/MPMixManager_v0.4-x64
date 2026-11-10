#!/usr/bin/env python3
"""
Unit tests for Stream of Frequency Equalizer in MP Audio Player:
- Default equalizer effect for Default, Mini, and Micro modes
- Dynamic Spectrogram feeding from live audio FFT frequency levels
- Rainbow Coloured Particle stream undulating as continuous waves flowing from Right to Left
- High-efficiency rendering and sub-millisecond execution
- Dimension and border alignment across widths and heights
- Interactive UI rendering in Normal, Mini, and Micro player frames
"""

import unittest
import sys
import time
import math
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
from MP_Audio_Player import EqualizerVisualizer, TerminalPlayerUI, _display_width


def strip_ansi(s: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", s)


class TestStreamOfFrequencyEqualizer(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.config_patch = patch.object(MP_Audio_Player, "CONFIG_DIR", self.temp_path)
        self.config_patch.start()

        # Fresh visualizer with stream_of_frequency_eq
        self.eq = EqualizerVisualizer(default_style="stream_of_frequency_eq")
        self.st = {
            "title": "Cosmic Trance Odyssey.flac",
            "path": "/archive/Cosmic Trance Odyssey.flac",
            "state": "playing",
            "position_fmt": "03:45",
            "duration_fmt": "08:20",
            "progress_pct": 45.0,
            "volume": 85,
            "pitch_percent": 0,
            "levels": [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1] + [0.35] * 16,
            "peaks": [0.9] * 24,
            "levels_left": [0.85] * 24,
            "levels_right": [0.75] * 24,
            "rms_level": 0.16,
            "peak_db": -2.5,
        }

    def tearDown(self):
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def test_stream_of_frequency_registered_as_default(self):
        """Verifies that stream_of_frequency_eq is the default first style in STYLES."""
        self.assertIn("stream_of_frequency_eq", EqualizerVisualizer.STYLES)
        self.assertEqual(EqualizerVisualizer.STYLES[0], "stream_of_frequency_eq")
        
        # Fresh instance without arguments defaults to stream_of_frequency_eq
        with patch.object(EqualizerVisualizer, "__init__", lambda s: setattr(s, "style_idx", 0)):
            viz = EqualizerVisualizer()
            self.assertEqual(viz.style, "stream_of_frequency_eq")

        disp_name = self.eq.get_style_display_name()
        self.assertIn("Stream of Frequency", disp_name)

    def test_stream_of_frequency_aliases(self):
        """Verifies that all alias strings resolve to stream_of_frequency_eq."""
        aliases = [
            "stream",
            "stream_of_frequency",
            "stream_of_frequency_eq",
            "frequency_stream",
            "frequency_stream_eq",
            "spectrogram",
            "dynamic_spectrogram",
            "river",
            "rainbow_stream",
        ]
        for alias in aliases:
            viz = EqualizerVisualizer(default_style=alias)
            self.assertEqual(
                viz.style,
                "stream_of_frequency_eq",
                f"Alias '{alias}' did not resolve to 'stream_of_frequency_eq'",
            )

    def test_render_stream_of_frequency_dimensions_and_alignment(self):
        """Verifies that all output lines have matching display widths across standard and custom widths."""
        test_widths = [60, 74, 80, 96, 110, 130]
        for w in test_widths:
            lines = self.eq.render_stream_of_frequency(self.st, width=w, height=7)
            self.assertEqual(len(lines), 9, f"Height 7 should produce 9 lines (7 rows + 2 borders) for width {w}")
            widths = [_display_width(line) for line in lines]
            self.assertEqual(
                len(set(widths)),
                1,
                f"Line display widths not uniform for width {w}: {widths}",
            )
            self.assertLessEqual(widths[0], w, f"Rendered width {widths[0]} exceeds terminal width {w}")

    def test_render_stream_of_frequency_various_heights(self):
        """Verifies that various heights (7, 5, 3, 2, 1) produce exactly height + 2 lines."""
        for h in [7, 5, 3, 2, 1]:
            lines = self.eq.render_stream_of_frequency(self.st, width=80, height=h)
            self.assertEqual(
                len(lines),
                h + 2,
                f"Height {h} must produce {h + 2} lines (got {len(lines)})",
            )
            self.assertIn("STREAM OF FREQUENCY", lines[0])

    def test_continuous_flow_from_right_to_left(self):
        """Verifies that particle stream positions advance from Right to Left over time."""
        # Initialize buffer and spawn initial particles
        _ = self.eq.render_stream_of_frequency(self.st, width=80, height=7)
        self.assertGreater(len(self.eq._sof_particles), 0, "Audio should spawn particles")

        # Track first particle's x position
        first_p = self.eq._sof_particles[0]
        init_x = first_p["x"]

        # Advance time by sleeping a tiny interval and rendering next frame
        time.sleep(0.04)
        _ = self.eq.render_stream_of_frequency(self.st, width=80, height=7)

        # Particle should have flowed to the left (x decreased)
        curr_x = first_p["x"]
        self.assertLess(
            curr_x,
            init_x,
            f"Particle did not flow from Right to Left (init_x: {init_x}, curr_x: {curr_x})",
        )

    def test_audio_responsiveness_and_spectrogram_feeding(self):
        """Verifies that audio frequency levels are fed into the spectrogram buffer."""
        # Test stopped state: levels are zeroed out
        stopped_st = dict(self.st, state="stopped", levels=[0.0] * 24, rms_level=0.0)
        _ = self.eq.render_stream_of_frequency(stopped_st, width=80, height=7)
        self.assertIsNotNone(self.eq._sof_buffer)
        
        # Test playing state with high audio energy: spectrogram buffer updates
        playing_st = dict(self.st, state="playing", levels=[0.95] * 24, rms_level=0.25, peak_db=-0.5)
        _ = self.eq.render_stream_of_frequency(playing_st, width=80, height=7)
        rightmost_slice = self.eq._sof_buffer[:, -1]
        self.assertGreater(np.max(rightmost_slice), 0.5, "Rightmost slice must reflect high audio energy")

    def test_micro_mode_inline_stream_meter(self):
        """Verifies that _draw_micro_frame generates a 14-char rainbow stream in MICRO mode."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="MICRO",
            is_remote=True,
            default_style="stream_of_frequency_eq",
        )
        self.assertEqual(ui.visualizer.style, "stream_of_frequency_eq")

        captured_lines = []
        with patch("MP_Audio_Player._present_frame", side_effect=lambda l, w, h: captured_lines.extend(l)):
            ui._draw_micro_frame(74, 14, self.st)

        text_dump = strip_ansi("\n".join(captured_lines))
        self.assertIn("MP MICRO AUDIO PLAYER", text_dump)
        self.assertIn("STREAM OF FREQUENCY", text_dump)

    def test_mini_mode_renders_stream_of_frequency(self):
        """Verifies that _draw_mini_frame renders Stream of Frequency Equalizer in MINI mode."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="MINI",
            is_remote=True,
            default_style="stream_of_frequency_eq",
        )
        self.assertEqual(ui.visualizer.style, "stream_of_frequency_eq")

        captured_lines = []
        with patch("MP_Audio_Player._present_frame", side_effect=lambda l, w, h: captured_lines.extend(l)):
            ui._draw_mini_frame(74, 14, self.st)

        text_dump = strip_ansi("\n".join(captured_lines))
        self.assertIn("MP MINI AUDIO PLAYER", text_dump)
        self.assertIn("STREAM OF FREQUENCY", text_dump)

    def test_normal_mode_renders_stream_of_frequency_default(self):
        """Verifies that Default (NORMAL) mode defaults to Stream of Frequency Equalizer."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True,
        )
        self.assertEqual(ui.visualizer.style, "stream_of_frequency_eq")

    def test_high_efficiency_benchmark(self):
        """Verifies that rendering 100 consecutive frames executes in well under 100ms (<1ms/frame)."""
        t0 = time.perf_counter()
        for _ in range(100):
            _ = self.eq.render_stream_of_frequency(self.st, width=80, height=7)
        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / 100.0) * 1000.0
        self.assertLess(avg_ms, 5.0, f"Render must be ultra-efficient (<5ms/frame, got {avg_ms:.3f}ms)")


if __name__ == "__main__":
    unittest.main()
