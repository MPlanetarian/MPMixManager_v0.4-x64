#!/usr/bin/env python3
"""Unit tests for the MP Visualizer screensaver and preset cycling.

Covers:
  1. +/- preset cycling across the whole library, both directions, with wrap.
  2. The +/- keys are bound only inside the MP Visualizer window.
  3. Number keys 1-9 still map to stable slots.
  4. Screensaver mode wakes and closes on any key or mouse input.
  5. CLI flag surface for --screensaver.
  6. The idle saver script's status/stop plumbing.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import mp_liquid_visualizer_vulkan as vis


class TestPresetCycling(unittest.TestCase):
    def test_forward_cycle_visits_every_preset_and_wraps(self):
        """+ must step through the entire library once and return to the start."""
        start = vis.VISUALIZER_PRESETS[0]
        seen = []
        cur = start
        for _ in range(len(vis.VISUALIZER_PRESETS)):
            cur = vis.cycle_preset(cur, 1)
            seen.append(cur["key"])
        self.assertEqual(len(seen), len(vis.VISUALIZER_PRESETS))
        self.assertEqual(len(set(seen)), len(vis.VISUALIZER_PRESETS), "cycle must not repeat early")
        # After a full lap we are back on the first preset
        self.assertEqual(cur["key"], start["key"])

    def test_backward_cycle_wraps_to_last(self):
        """- from the first preset must jump to the last one."""
        last = vis.VISUALIZER_PRESETS[-1]
        self.assertEqual(vis.cycle_preset(vis.VISUALIZER_PRESETS[0], -1)["key"], last["key"])

    def test_cycle_reaches_every_slot_and_extra(self):
        """Cycling must reach presets that are not on a number key."""
        reachable = set()
        cur = vis.VISUALIZER_PRESETS[0]
        for _ in range(len(vis.VISUALIZER_PRESETS)):
            cur = vis.cycle_preset(cur, 1)
            reachable.add(cur["key"])
        for preset in vis.VISUALIZER_PRESETS:
            self.assertIn(preset["key"], reachable)

    def test_number_keys_still_use_slots(self):
        """Number keys 1-9 must keep resolving to the numbered slot list."""
        slots = vis.presets_by_slot()
        self.assertEqual(len(slots), 9)
        for i, preset in enumerate(slots, start=1):
            self.assertEqual(vis.get_active_preset(str(i))["key"], preset["key"])


class TestCycleKeysOnlyInVisualizer(unittest.TestCase):
    def test_visualizer_binds_plus_minus(self):
        """The visualizer key handler must handle the +/- keys and keypad variants."""
        src = Path(vis.__file__).read_text(encoding="utf-8")
        self.assertIn("GLFW_KEY_EQUAL", src)
        self.assertIn("GLFW_KEY_MINUS", src)
        self.assertIn("GLFW_KEY_KP_ADD", src)
        self.assertIn("GLFW_KEY_KP_SUBTRACT", src)
        self.assertIn("cycle_preset", src)

    def test_liquid_player_does_not_bind_plus_minus_to_presets(self):
        """The MP Liquid Player must not gain +/- preset cycling."""
        for name in (
            "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "MP_Audio_Player_Liquid_Glass.py",
            "MP_Audio_Player_Liquid_Glass_macOS.py",
        ):
            path = ROOT_DIR / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("cycle_preset", text, f"{name} must not use preset cycling")
            self.assertNotIn("GLFW_KEY_EQUAL", text, f"{name} must not own the + key")


class TestScreensaverMode(unittest.TestCase):
    def _renderer(self):
        r = vis.LiquidVisualizerVulkanRenderer.__new__(vis.LiquidVisualizerVulkanRenderer)
        r.screensaver = True
        r._wake_event = False
        r.should_close = False
        r._player_bonded = False
        r.mouse_down = False
        r._drag_active = False
        r.is_fullscreen = True
        r.cursor = (0.0, 0.0)
        r._window = 0
        r.request_close = lambda: setattr(r, "should_close", True)
        return r

    def test_any_key_wakes_and_closes(self):
        r = self._renderer()
        r._on_key(0, 65, 0, vis.GLFW_PRESS, 0)  # 'a'
        self.assertTrue(r.should_close)
        self.assertTrue(r._wake_event)

    def test_mouse_press_wakes_and_closes(self):
        r = self._renderer()
        r._on_mouse(0, 0, vis.GLFW_PRESS, 0)
        self.assertTrue(r.should_close)
        self.assertTrue(r._wake_event)

    def test_first_cursor_event_only_primes(self):
        """The cursor sample reported when the window appears must not close it."""
        r = self._renderer()
        r._saver_cursor_primed = False
        r._on_cursor(0, 10.0, 10.0)
        self.assertFalse(r.should_close, "initial cursor sample must not wake the saver")
        r._on_cursor(0, 40.0, 40.0)
        self.assertTrue(r.should_close, "genuine mouse movement must wake the saver")

    def test_mouse_release_does_not_wake(self):
        r = self._renderer()
        r._on_mouse(0, 0, 0, 0)  # GLFW_RELEASE is 0
        self.assertFalse(r.should_close)

    def test_cli_exposes_screensaver_flags(self):
        res = subprocess.run(
            [sys.executable, str(ROOT_DIR / "MP_Liquid_Visualizer.py"), "--help"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(res.returncode, 0)
        for flag in ("--screensaver", "--saver-dwell", "--saver-preset", "--saver-windowed"):
            self.assertIn(flag, res.stdout)


class TestSaverResolutionPolicy(unittest.TestCase):
    """The screensaver fills every screen but caps its render resolution."""

    def test_1920x1200_panel_uses_1920x1200(self):
        self.assertEqual(vis.saver_target_resolution(1920, 1200), (1920, 1200))

    def test_16_9_panel_falls_back_to_1920x1080(self):
        self.assertEqual(vis.saver_target_resolution(1920, 1080), (1920, 1080))

    def test_4k_panel_is_capped_not_native(self):
        self.assertEqual(vis.saver_target_resolution(3840, 2160), (1920, 1200))

    def test_1440p_panel_capped_to_1920x1200(self):
        self.assertEqual(vis.saver_target_resolution(2560, 1440), (1920, 1200))

    def test_smaller_panel_is_not_upscaled(self):
        self.assertEqual(vis.saver_target_resolution(1600, 900), (1600, 900))
        self.assertEqual(vis.saver_target_resolution(1280, 1024), (1280, 1024))

    def test_cap_never_exceeds_max(self):
        for w, h in ((3840, 2160), (5120, 2880), (2560, 1600)):
            rw, rh = vis.saver_target_resolution(w, h)
            self.assertLessEqual(rw, vis.SAVER_MAX_WIDTH)
            self.assertLessEqual(rh, vis.SAVER_MAX_HEIGHT)

    def test_screen_plan_covers_every_monitor(self):
        monitors = [
            ("DP-1", (0, 0, 1920, 1200)),
            ("DP-2", (1920, 0, 1920, 1200)),
            ("HDMI-A-1", (0, 1200, 3840, 2160)),
        ]
        plan = vis.saver_screen_plan(monitors)
        self.assertEqual(len(plan), 3)
        self.assertEqual([e["name"] for e in plan], ["DP-1", "DP-2", "HDMI-A-1"])
        for entry in plan:
            self.assertEqual(len(entry["bounds"]), 4)
            self.assertEqual(len(entry["render"]), 2)
        # The 16:10 panels keep 1920x1200, the 4K one is capped to it too.
        self.assertEqual(plan[0]["render"], [1920, 1200])
        self.assertEqual(plan[2]["render"], [1920, 1200])

    def test_screen_plan_skips_degenerate_monitors(self):
        plan = vis.saver_screen_plan([("bad", (0, 0, 0, 0)), ("ok", (0, 0, 1920, 1200))])
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["name"], "ok")

    def test_render_pair_parser(self):
        self.assertEqual(vis._parse_pair("1920,1200"), (1920, 1200))
        self.assertIsNone(vis._parse_pair(""))
        self.assertIsNone(vis._parse_pair("nope"))
        self.assertIsNone(vis._parse_pair("1,1"))


class TestIdleSaverScript(unittest.TestCase):
    def test_script_exists_and_reports_status(self):
        script = ROOT_DIR / "scripts" / "mp_visualizer_idle_saver.py"
        self.assertTrue(script.is_file())
        res = subprocess.run([sys.executable, str(script), "--status"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0)
        self.assertIn("MP Visualizer idle saver", res.stdout)

    def test_script_exposes_expected_flags(self):
        res = subprocess.run([sys.executable, str(ROOT_DIR / "scripts" / "mp_visualizer_idle_saver.py"), "--help"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0)
        for flag in ("--idle", "--dwell", "--cooldown", "--stop", "--status"):
            self.assertIn(flag, res.stdout)

    def test_idle_seconds_is_a_number(self):
        self.assertIsInstance(float(vis.idle_seconds()), float)


if __name__ == "__main__":
    unittest.main()
