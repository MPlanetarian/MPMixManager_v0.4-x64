#!/usr/bin/env python3
"""Unit tests for the R-key random preset mode in the MP Visualizer.

Covers:
  1. R toggles random mode on and off, and the second press stops rotation.
  2. A new random preset is chosen only after the one-minute interval.
  3. The pick is never the preset already on screen.
  4. F10/F11 spawned copies and screensaver windows never rotate on their own.
  5. Both the Vulkan and the OpenGL renderer bind R and inherit the mixin.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import liquid_player_visualizer as gl_vis
import mp_liquid_visualizer_vulkan as vis
import visualizer_random_mode as random_mode


class _FakeRenderer(random_mode.RandomPresetMixin):
    """Minimal host: the mixin only needs ``preset`` and ``switch_preset``."""

    screensaver = False
    _span_role = ""

    def __init__(self, preset):
        self.preset = preset
        self.switched = []
        self.init_random_mode()

    def switch_preset(self, preset):
        self.preset = preset
        self.switched.append(preset["key"])


class TestRandomModeToggle(unittest.TestCase):
    def test_r_starts_disabled(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        self.assertFalse(r.random_mode)
        self.assertEqual(r._random_switch_at, 0.0)

    def test_first_press_enables_and_starts_the_minute(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        with patch.object(random_mode.time, "monotonic", return_value=1000.0):
            self.assertTrue(r.toggle_random_mode())
        self.assertTrue(r.random_mode)
        self.assertEqual(r._random_switch_at, 1000.0 + random_mode.RANDOM_PRESET_INTERVAL)

    def test_second_press_disables_and_cancels_the_clock(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        r.toggle_random_mode()
        self.assertFalse(r.toggle_random_mode())
        self.assertFalse(r.random_mode)
        self.assertEqual(r._random_switch_at, 0.0)

    def test_nothing_switches_before_the_minute_is_up(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        with patch.object(random_mode.time, "monotonic", return_value=1000.0):
            r.toggle_random_mode()
        self.assertFalse(r.poll_random_mode(now=1000.0 + 59.9))
        self.assertEqual(r.switched, [])

    def test_switches_once_the_minute_has_passed(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        with patch.object(random_mode.time, "monotonic", return_value=1000.0):
            r.toggle_random_mode()
        self.assertTrue(r.poll_random_mode(now=1000.0 + random_mode.RANDOM_PRESET_INTERVAL))
        self.assertEqual(len(r.switched), 1)
        # The clock restarts from the switch, so the next pick is a full minute later.
        self.assertEqual(
            r._random_switch_at,
            1000.0 + random_mode.RANDOM_PRESET_INTERVAL * 2,
        )
        self.assertFalse(r.poll_random_mode(now=1000.0 + random_mode.RANDOM_PRESET_INTERVAL + 30))
        self.assertEqual(len(r.switched), 1)

    def test_disabling_stops_rotation(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        with patch.object(random_mode.time, "monotonic", return_value=1000.0):
            r.toggle_random_mode()
        r.toggle_random_mode()  # off again
        self.assertFalse(r.poll_random_mode(now=9999.0))
        self.assertEqual(r.switched, [])


class TestRandomPick(unittest.TestCase):
    def test_never_picks_the_preset_already_showing(self):
        current = vis.VISUALIZER_PRESETS[0]
        for _ in range(200):
            nxt = random_mode.pick_random_preset(current)
            self.assertIsNotNone(nxt)
            self.assertNotEqual(nxt["key"], current["key"])

    def test_picks_only_real_presets(self):
        keys = {p["key"] for p in vis.VISUALIZER_PRESETS}
        for _ in range(200):
            self.assertIn(random_mode.pick_random_preset(None)["key"], keys)

    def test_single_preset_library_still_returns_it(self):
        only = vis.VISUALIZER_PRESETS[0]
        with patch.object(vis, "VISUALIZER_PRESETS", [only]):
            self.assertEqual(random_mode.pick_random_preset(only)["key"], only["key"])


class TestViewerWindowsNeverRotate(unittest.TestCase):
    def test_screensaver_does_not_rotate(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        r.screensaver = True
        r.toggle_random_mode()
        self.assertFalse(r.poll_random_mode(now=99999.0))
        self.assertEqual(r.switched, [])

    def test_spawned_span_window_does_not_rotate(self):
        r = _FakeRenderer(vis.VISUALIZER_PRESETS[0])
        r._span_role = "spawned"
        r.toggle_random_mode()
        self.assertFalse(r.poll_random_mode(now=99999.0))
        self.assertEqual(r.switched, [])


class TestRandomBindings(unittest.TestCase):
    def test_interval_is_one_minute(self):
        self.assertEqual(random_mode.RANDOM_PRESET_INTERVAL, 60.0)

    def test_glfw_r_keycode(self):
        self.assertEqual(vis.GLFW_KEY_R, 82)

    def test_both_renderers_are_random_mixin_hosts(self):
        self.assertTrue(issubclass(vis.LiquidVisualizerVulkanRenderer, random_mode.RandomPresetMixin))
        self.assertTrue(
            issubclass(gl_vis.LiquidVisualizerOpenGLRenderer, random_mode.RandomPresetMixin)
        )

    def test_vulkan_key_handler_toggles_random_mode(self):
        r = vis.LiquidVisualizerVulkanRenderer.__new__(vis.LiquidVisualizerVulkanRenderer)
        r.screensaver = False
        r.should_close = False
        r._player_bonded = False
        r.preset = dict(vis.VISUALIZER_PRESETS[0])
        r.init_random_mode()
        r.switch_preset = MagicMock()
        r._on_key(None, vis.GLFW_KEY_R, 0, vis.GLFW_PRESS, 0)
        self.assertTrue(r.random_mode)
        r._on_key(None, vis.GLFW_KEY_R, 0, vis.GLFW_PRESS, 0)
        self.assertFalse(r.random_mode)

    def test_opengl_key_handler_toggles_random_mode(self):
        r = gl_vis.LiquidVisualizerOpenGLRenderer.__new__(gl_vis.LiquidVisualizerOpenGLRenderer)
        r.screensaver = False
        r.should_close = False
        r.preset = dict(vis.VISUALIZER_PRESETS[0])
        r.init_random_mode()
        r.switch_preset = MagicMock()
        r._on_key(None, 82, 0, 1, 0)
        self.assertTrue(r.random_mode)
        r._on_key(None, 82, 0, 1, 0)
        self.assertFalse(r.random_mode)

    def test_key_release_is_ignored(self):
        renderer = vis.LiquidVisualizerVulkanRenderer.__new__(vis.LiquidVisualizerVulkanRenderer)
        renderer.screensaver = False
        renderer.preset = dict(vis.VISUALIZER_PRESETS[0])
        renderer.toggle_random_mode = MagicMock()
        renderer._on_key(None, vis.GLFW_KEY_R, 0, 0, 0)  # GLFW_RELEASE
        renderer.toggle_random_mode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
