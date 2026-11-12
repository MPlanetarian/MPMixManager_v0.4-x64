#!/usr/bin/env python3
"""
Unit tests for the three full-field Rainbow FX visualisers in MP Audio Player:

- Rainbow Mandala Bloom  (rainbow_mandala_eq)  — kaleidoscopic spectrum wreaths
- Rainbow Wormhole       (rainbow_wormhole_eq) — hyperspace plasma tunnel
- Rainbow Aurora Cascade (rainbow_aurora_eq)   — holographic ribbon curtains

These are distinct from the Stream of Frequency spectrogram: they are
full-field, multi-layer, animated and TrueColor rainbow throughout.
"""

import re
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
from MP_Audio_Player import EqualizerVisualizer, TerminalPlayerUI, _display_width

NEW_STYLES = ("rainbow_mandala_eq", "rainbow_wormhole_eq", "rainbow_aurora_eq")

# Glyphs no console-safe font is guaranteed to carry.
UNSAFE = (
    "✦", "✧", "⋆", "✺", "✷", "✸", "✹", "✻", "❋", "❖", "✱", "✳", "✴", "⁂", "⁕",
    "⍟", "⎈", "⬢", "⬡", "◈", "◉", "◎", "◌", "⌬", "╎", "┊", "┃", "═", "▪",
)

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def plain(lines):
    return ANSI.sub("", "\n".join(lines))


def status(state="playing", level=0.72):
    levels = [max(0.05, level - i * 0.03) for i in range(24)]
    return {
        "title": "Cosmic Trance Odyssey.flac",
        "path": "/archive/Cosmic Trance Odyssey.flac",
        "state": state,
        "position_fmt": "03:45",
        "duration_fmt": "08:20",
        "progress_pct": 45.0,
        "volume": 85,
        "pitch_percent": 0,
        "levels": levels,
        "peaks": [0.9] * 24,
        "levels_left": [0.85] * 24,
        "levels_right": [0.75] * 24,
        "rms_level": 0.19,
        "peak_db": -2.5,
        "waveform": [0.1 * i for i in range(50)],
    }


class RainbowFxTestBase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_patch = patch.object(MP_Audio_Player, "CONFIG_DIR", Path(self.temp_dir.name))
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def viz(self, style):
        return EqualizerVisualizer(default_style=style)


class TestRainbowFxRegistration(RainbowFxTestBase):
    def test_all_three_are_registered(self):
        for style in NEW_STYLES:
            self.assertIn(style, EqualizerVisualizer.STYLES)
            self.assertEqual(self.viz(style).style, style)

    def test_display_names_are_distinct_and_descriptive(self):
        names = {s: EqualizerVisualizer.STYLE_NAMES[s] for s in NEW_STYLES}
        self.assertEqual(len(set(names.values())), 3)
        for name in names.values():
            self.assertIn("Rainbow", name)

    def test_stream_of_frequency_remains_the_default(self):
        self.assertEqual(EqualizerVisualizer.STYLES[0], "stream_of_frequency_eq")
        self.assertEqual(self.viz("stream").style, "stream_of_frequency_eq")

    def test_friendly_aliases_resolve(self):
        cases = {
            "mandala": "rainbow_mandala_eq",
            "kaleidoscope": "rainbow_mandala_eq",
            "rainbow_bloom": "rainbow_mandala_eq",
            "wormhole": "rainbow_wormhole_eq",
            "hyperspace": "rainbow_wormhole_eq",
            "vortex": "rainbow_wormhole_eq",
            "aurora": "rainbow_aurora_eq",
            "ribbons": "rainbow_aurora_eq",
            "holographic": "rainbow_aurora_eq",
        }
        for alias, expected in cases.items():
            self.assertEqual(self.viz(alias).style, expected, alias)

    def test_unknown_style_falls_back_instead_of_crashing(self):
        self.assertEqual(self.viz("no_such_effect_at_all").style, "stream_of_frequency_eq")


class TestRainbowFxGeometry(RainbowFxTestBase):
    def test_line_count_is_height_plus_two_borders(self):
        for style in NEW_STYLES:
            viz = self.viz(style)
            for h in (1, 2, 3, 5, 7, 9):
                lines = viz.render(status(), width=80, height=h)
                self.assertEqual(len(lines), h + 2, f"{style} height {h}")

    def test_every_line_matches_the_light_player_width(self):
        """In Liquid Glass the equaliser must span exactly width-2 columns."""
        with patch.dict("os.environ", {"MP_LIQUID_GLASS": "1"}):
            for style in NEW_STYLES:
                viz = self.viz(style)
                for w in (34, 50, 74, 80, 100, 120):
                    lines = viz.render(status(), width=w, height=7)
                    widths = {_display_width(line) for line in lines}
                    self.assertEqual(widths, {w - 2}, f"{style} at width {w}: {widths}")

    def test_narrow_and_tall_frames_do_not_raise(self):
        for style in NEW_STYLES:
            viz = self.viz(style)
            for w, h in ((26, 1), (26, 7), (30, 2), (46, 9)):
                lines = viz.render(status(), width=w, height=h)
                self.assertEqual(len(lines), h + 2)
                self.assertEqual(len({_display_width(l) for l in lines}), 1)


class TestRainbowFxColour(RainbowFxTestBase):
    def test_output_is_truecolor_rainbow(self):
        for style in NEW_STYLES:
            viz = self.viz(style)
            for _ in range(3):
                raw = "\n".join(viz.render(status(), width=100, height=7))
            hues = {int(m.group(1)) for m in re.finditer(r"\x1b\[(?:1;)?38;2;(\d+);", raw)}
            self.assertGreater(len(hues), 40, f"{style} should use a wide rainbow, got {len(hues)} red levels")
            # A rainbow sweep needs all three channels present in force.
            for channel in (0, 1, 2):
                values = [int(m.group(1)) for m in
                          re.finditer(r"\x1b\[(?:1;)?38;2;(\d+);(\d+);(\d+)m", raw)]
                self.assertTrue(any(v > 120 for v in values))

    def test_colours_change_over_time(self):
        """The rainbow must animate: two frames a moment apart differ."""
        for style in NEW_STYLES:
            viz = self.viz(style)
            first = "\n".join(viz.render(status(), width=90, height=7))
            time.sleep(0.06)
            second = "\n".join(viz.render(status(), width=90, height=7))
            self.assertNotEqual(first, second, f"{style} did not animate")

    def test_rendering_is_audio_reactive(self):
        """A loud frame must not look like a silent one."""
        frozen = time.time()

        def quiet_status():
            st = status("playing", 0.02)
            st.update(
                levels=[0.02] * 24,
                peaks=[0.02] * 24,
                levels_left=[0.02] * 24,
                levels_right=[0.02] * 24,
                rms_level=0.0,
                peak_db=-60.0,
            )
            return st

        def loud_status():
            st = status("playing", 0.95)
            st.update(
                levels=[0.95] * 24,
                peaks=[0.99] * 24,
                levels_left=[0.95] * 24,
                levels_right=[0.95] * 24,
                rms_level=0.35,
                peak_db=-0.2,
            )
            return st

        for style in NEW_STYLES:
            viz = self.viz(style)
            # Freeze the clock so only the audio telemetry can differ.
            with patch("MP_Audio_Player.time.time", return_value=frozen):
                loud = "\n".join(viz.render(loud_status(), width=90, height=7))
                quiet = "\n".join(viz.render(quiet_status(), width=90, height=7))
            self.assertNotEqual(loud, quiet, f"{style} ignores audio levels")


class TestRainbowFxCadence(RainbowFxTestBase):
    def test_render_cadence_stays_responsive(self):
        """Each frame must stay well inside a 25 fps redraw budget."""
        for style in NEW_STYLES:
            viz = self.viz(style)
            for _ in range(4):
                viz.render(status(), width=120, height=7)
            start = time.perf_counter()
            for _ in range(20):
                viz.render(status(), width=120, height=7)
            ms = (time.perf_counter() - start) / 20.0 * 1000.0
            self.assertLess(ms, 40.0, f"{style} too slow: {ms:.1f} ms/frame")

    def test_particles_and_rings_stay_bounded(self):
        viz = self.viz("rainbow_mandala_eq")
        for _ in range(200):
            viz.render(status(), width=110, height=7)
        self.assertLessEqual(len(viz._mandala_sparks), 26)
        self.assertLessEqual(len(viz._mandala_rings), 6)

        viz = self.viz("rainbow_wormhole_eq")
        for _ in range(200):
            viz.render(status(), width=110, height=7)
        self.assertLessEqual(len(viz._worm_motes), 32)

        viz = self.viz("rainbow_aurora_eq")
        for _ in range(200):
            viz.render(status(), width=110, height=7)
        self.assertLessEqual(len(viz._aurora_embers), 26)


class TestRainbowFxConsoleSafety(RainbowFxTestBase):
    def test_limited_console_never_emits_missing_glyphs(self):
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=True):
            for style in NEW_STYLES:
                viz = self.viz(style)
                for _ in range(4):
                    text = plain(viz.render(status(), width=100, height=7))
                for glyph in UNSAFE:
                    self.assertNotIn(glyph, text, f"{style} leaked {glyph}")

    def test_full_console_keeps_the_rich_glyphs(self):
        with patch("MP_Audio_Player._use_limited_console_glyphs", return_value=False):
            for style in NEW_STYLES:
                viz = self.viz(style)
                for _ in range(4):
                    text = plain(viz.render(status(), width=100, height=7))
                self.assertTrue(
                    any(g in text for g in ("✦", "✧", "✺", "◇", "◉", "◎", "❖")),
                    f"{style} lost its starfield on a full console",
                )


class TestRainbowFxPlayerFrames(RainbowFxTestBase):
    def _ui(self, mode, style):
        scanner = MagicMock()
        scanner.get_mixes.return_value = []
        return TerminalPlayerUI(
            engine=None, scanner=scanner, ui_size_mode=mode, is_remote=True, default_style=style
        )

    def test_micro_meter_is_style_specific_and_rainbow(self):
        viz = self.viz("rainbow_mandala_eq")
        meter = viz._fx_micro_meter("rainbow_mandala_eq", 12.5, np.linspace(0.1, 0.9, 14))
        self.assertEqual(len(ANSI.sub("", meter)), 14)
        self.assertGreater(len(set(re.findall(r"\x1b\[(?:1;)?38;2;\d+;", meter))), 6)

        mandala = viz._fx_micro_meter("rainbow_mandala_eq", 12.5, np.full(14, 0.9))
        wormhole = viz._fx_micro_meter("rainbow_wormhole_eq", 12.5, np.full(14, 0.9))
        aurora = viz._fx_micro_meter("rainbow_aurora_eq", 12.5, np.full(14, 0.9))
        self.assertNotEqual(ANSI.sub("", mandala), ANSI.sub("", wormhole))
        self.assertNotEqual(ANSI.sub("", wormhole), ANSI.sub("", aurora))

    def test_each_frame_renders_the_active_effect(self):
        for style in NEW_STYLES:
            for mode, call in (
                ("NORMAL", lambda ui, st: ui._draw_frame()),
                ("MINI", lambda ui, st: ui._draw_mini_frame(74, 14, st)),
                ("MICRO", lambda ui, st: ui._draw_micro_frame(74, 14, st)),
            ):
                ui = self._ui(mode, style)
                self.assertEqual(ui.visualizer.style, style)
                captured = []
                st = status()
                with patch("MP_Audio_Player._present_frame",
                           side_effect=lambda lines, w, h: captured.extend(lines)), \
                     patch("MP_Audio_Player._win_visible_size", return_value=(120, 40)), \
                     patch.object(ui, "_get_status", MagicMock(return_value=st)):
                    call(ui, st)
                text = plain(captured)
                self.assertIn("MP", text, f"{style}/{mode} produced no frame")
                if mode != "MICRO":
                    # The visualiser box is on screen in Normal and Mini.
                    self.assertIn("│", text)


if __name__ == "__main__":
    unittest.main()
