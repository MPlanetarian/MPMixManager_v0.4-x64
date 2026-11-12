#!/usr/bin/env python3
"""Tests for the F10 / F11 multi-monitor MP Visualizer span.

Covers:
  1. F10 mirrors the current preset on every other monitor.
  2. F11 assigns a different random preset per spawned window.
  3. Monitor discovery returns name plus desktop rect per screen.
  4. Spawning skips the monitor in use and passes each child its own bounds.
  5. Pressing F10/F11 again closes the spawned windows and keeps the owner.
  6. A visualizer bonded behind the MP Liquid Player is never closed.
  7. Spawned windows go fullscreen after the two-second delay.
  8. Children exit when the owner's session disappears.
  9. CLI flags exist for the internal span options.
 10. Both renderer backends implement the shared span mixin.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import visualizer_monitor_span as span
import mp_liquid_visualizer_vulkan as vulkan_vis
import liquid_player_visualizer as gl_vis


class SpanSessionDirMixin(unittest.TestCase):
    """Point the span files at a temporary directory for every test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._patches = [
            patch.object(span, "SPAN_SESSION_FILE", self.dir / "visualizer_span.json"),
            patch.object(span, "SPAN_STOP_FILE", self.dir / "visualizer_span.stop"),
            patch.object(span, "SPAN_LOG_FILE", self.dir / "liquid_visualizer_span.log"),
            patch.object(span, "CONFIG_DIR", self.dir),
        ]
        for patcher in self._patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self._patches):
            patcher.stop()
        self._tmp.cleanup()


class TestSpanPresetPlan(unittest.TestCase):
    def test_f10_mirrors_the_current_preset(self) -> None:
        current = {"key": "cosmic_universe"}
        plan = span.span_preset_plan(current, 3, random_mode=False)
        self.assertEqual(plan, ["cosmic_universe"] * 3)

    def test_f11_assigns_distinct_random_presets(self) -> None:
        current = {"key": "cosmic_universe"}
        plan = span.span_preset_plan(current, 3, random_mode=True)
        self.assertEqual(len(plan), 3)
        self.assertNotIn("cosmic_universe", plan, "random mode must avoid the current preset")
        self.assertEqual(len(set(plan)), 3, "each spawned window should get a different preset")

    def test_f11_never_repeats_adjacent_presets_when_it_can_avoid_it(self) -> None:
        keys = [p["key"] for p in vulkan_vis.VISUALIZER_PRESETS]
        current = {"key": keys[0]}
        for _ in range(40):
            plan = span.span_preset_plan(current, 4, random_mode=True)
            for left, right in zip(plan, plan[1:]):
                self.assertNotEqual(left, right)

    def test_empty_monitor_list_yields_no_plan(self) -> None:
        self.assertEqual(span.span_preset_plan({"key": "cosmic_universe"}, 0, True), [])


class TestSpanParsing(unittest.TestCase):
    def test_bounds_parse(self) -> None:
        self.assertEqual(span.parse_span_bounds("1920,0,1920,1080"), (1920, 0, 1920, 1080))

    def test_bounds_reject_garbage(self) -> None:
        for bad in (None, "", "1,2,3", "a,b,c,d", "0,0,10,10"):
            self.assertIsNone(span.parse_span_bounds(bad), bad)

    def test_stop_request_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch.object(span, "SPAN_STOP_FILE", tmp_path / "stop.json"), \
                 patch.object(span, "CONFIG_DIR", tmp_path):
                self.assertFalse(span.stop_requested(1234))
                span.request_span_stop(1234)
                self.assertTrue(span.stop_requested(1234))
                self.assertFalse(span.stop_requested(9999))


class TestMonitorDiscovery(SpanSessionDirMixin):
    def _glfw(self):
        """Fake GLFW with two monitors side by side."""
        glfw = MagicMock()
        glfw.glfwGetMonitors.return_value = [101, 202]

        def pos(mon, px, py):
            px._obj.value = 0 if mon == 101 else 1920
            py._obj.value = 0

        def mode(mon):
            holder = MagicMock()
            holder.contents.width = 1920 if mon == 101 else 2560
            holder.contents.height = 1080 if mon == 101 else 1440
            return holder

        glfw.glfwGetMonitorPos.side_effect = pos
        glfw.glfwGetVideoMode.side_effect = mode
        glfw.glfwGetMonitorName.side_effect = lambda mon: b"Primary" if mon == 101 else b"Secondary"
        return glfw

    def test_rects_report_each_monitor(self) -> None:
        # glfwGetMonitors writes the count through a byref(c_int); emulate it.
        glfw = MagicMock()

        def get_monitors(count_ptr):
            count_ptr._obj.value = 2
            return [101, 202]

        glfw.glfwGetMonitors.side_effect = get_monitors
        glfw.glfwGetMonitorPos.side_effect = lambda mon, px, py: (
            setattr(px._obj, "value", 0 if mon == 101 else 1920),
            setattr(py._obj, "value", 0),
        )
        glfw.glfwGetVideoMode.side_effect = lambda mon: MagicMock(
            contents=MagicMock(width=1920 if mon == 101 else 2560,
                               height=1080 if mon == 101 else 1440))
        glfw.glfwGetMonitorName.side_effect = lambda mon: b"Primary" if mon == 101 else b"Secondary"
        rects = span.monitor_rects(glfw)
        self.assertEqual([r[1] for r in rects], [(0, 0, 1920, 1080), (1920, 0, 2560, 1440)])
        self.assertEqual([r[0] for r in rects], ["Primary", "Secondary"])

    def test_no_glfw_returns_nothing(self) -> None:
        self.assertEqual(span.monitor_rects(None), [])


class TestSpanLifecycle(SpanSessionDirMixin):
    def _renderer(self, rect=(0, 0, 1920, 1080)):
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer.preset = {"id": 8, "key": "cosmic_universe"}
        renderer.is_fullscreen = False
        renderer.should_close = False
        renderer._player_bonded = False
        renderer._glfw = None
        renderer._window = None
        renderer._init_span_state(None, "")
        renderer.monitor_rects = MagicMock(return_value=[
            ("Primary", (0, 0, 1920, 1080)),
            ("Left", (-1920, 0, 1920, 1080)),
            ("Right", (1920, 0, 1920, 1080)),
        ])
        renderer.monitor_bounds = MagicMock(return_value=rect)
        renderer.request_close = MagicMock()
        renderer.toggle_fullscreen = MagicMock()
        renderer.window_pos = MagicMock(return_value=(0, 0))
        return renderer

    def test_f10_skips_the_monitor_in_use(self) -> None:
        renderer = self._renderer(rect=(0, 0, 1920, 1080))
        with patch.object(span, "visualizer_entry_path", return_value=Path("/program/MP_Liquid_Visualizer.py")), \
             patch.object(span.subprocess, "Popen") as popen:
            popen.return_value = MagicMock(pid=4242, poll=MagicMock(return_value=None))
            children = renderer.start_monitor_span(random_mode=False)
        self.assertEqual(len(children), 2)
        spawned = [call.args[0] for call in popen.call_args_list]
        bounds = [cmd[cmd.index("--span-bounds") + 1] for cmd in spawned]
        self.assertEqual(bounds, ["-1920,0,1920,1080", "1920,0,1920,1080"])
        for cmd in spawned:
            self.assertIn("--span-role", cmd)
            self.assertEqual(cmd[cmd.index("--span-role") + 1], "spawned")
            self.assertEqual(cmd[cmd.index("--preset") + 1], "cosmic_universe")
        session = json.loads((self.dir / "visualizer_span.json").read_text())
        self.assertEqual(session["mode"], "mirror")
        self.assertEqual(len(session["children"]), 2)
        self.assertTrue(renderer._span_is_active())

    def test_f11_spawned_windows_use_random_presets(self) -> None:
        renderer = self._renderer()
        with patch.object(span, "visualizer_entry_path", return_value=Path("/program/MP_Liquid_Visualizer.py")), \
             patch.object(span.subprocess, "Popen") as popen:
            popen.return_value = MagicMock(pid=4242, poll=MagicMock(return_value=None))
            renderer.start_monitor_span(random_mode=True)
        presets = []
        for call in popen.call_args_list:
            cmd = call.args[0]
            presets.append(cmd[cmd.index("--preset") + 1])
        self.assertEqual(len(set(presets)), 2)
        self.assertNotIn("cosmic_universe", presets)
        session = json.loads((self.dir / "visualizer_span.json").read_text())
        self.assertEqual(session["mode"], "random")

    def test_second_f10_closes_the_spawned_windows(self) -> None:
        renderer = self._renderer()
        first, second = MagicMock(pid=11, poll=MagicMock(return_value=None)), MagicMock(pid=12, poll=MagicMock(return_value=None))
        with patch.object(span, "visualizer_entry_path", return_value=Path("/program/MP_Liquid_Visualizer.py")), \
             patch.object(span.subprocess, "Popen", side_effect=[first, second]):
            renderer.start_monitor_span(random_mode=False)
        self.assertFalse((self.dir / "visualizer_span.json").exists() is False)
        with patch.object(renderer, "_stop_span_child") as stop:
            renderer.handle_span_key(vulkan_vis.GLFW_KEY_F10)
        self.assertEqual(stop.call_count, 2)
        self.assertFalse(renderer._span_is_active())
        self.assertFalse((self.dir / "visualizer_span.json").exists())
        # The window the user is on is never asked to close.
        renderer.request_close.assert_not_called()

    def test_bonded_player_visualizer_is_never_closed(self) -> None:
        renderer = self._renderer()
        renderer._player_bonded = True
        child = MagicMock(pid=1, poll=MagicMock(return_value=None))
        with patch.object(span, "visualizer_entry_path", return_value=Path("/program/MP_Liquid_Visualizer.py")), \
             patch.object(span.subprocess, "Popen", return_value=child):
            renderer.start_monitor_span(random_mode=False)
        with patch.object(renderer, "_stop_span_child"):
            renderer.stop_monitor_span()
        renderer.request_close.assert_not_called()
        self.assertTrue(renderer._player_bonded)

    def test_single_monitor_does_nothing(self) -> None:
        renderer = self._renderer()
        renderer.monitor_rects = MagicMock(return_value=[("Primary", (0, 0, 1920, 1080))])
        with patch.object(span.subprocess, "Popen") as popen:
            self.assertEqual(renderer.start_monitor_span(False), [])
        popen.assert_not_called()
        self.assertFalse(renderer._span_is_active())

    def test_spawned_window_goes_fullscreen_after_the_delay(self) -> None:
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer.is_fullscreen = False
        renderer._player_bonded = False
        renderer.should_close = False
        renderer.toggle_fullscreen = MagicMock()
        renderer.request_close = MagicMock()
        renderer._init_span_state((1920, 0, 1920, 1080), "spawned", span_delay=0.05)
        with patch.object(span, "read_span_session", return_value={"owner_pid": os.getpid()}):
            renderer.poll_monitor_span()
            self.assertFalse(renderer.toggle_fullscreen.called, "must not go fullscreen before the delay")
            time.sleep(0.08)
            renderer._span_poll_at = 0.0
            renderer.poll_monitor_span()
        renderer.toggle_fullscreen.assert_called_once()
        renderer.request_close.assert_not_called()

    def test_spawned_window_closes_when_the_session_ends(self) -> None:
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer.is_fullscreen = True
        renderer._player_bonded = False
        renderer.should_close = False
        renderer.toggle_fullscreen = MagicMock()
        renderer.request_close = MagicMock()
        renderer._init_span_state((1920, 0, 1920, 1080), "spawned")
        with patch.object(span, "read_span_session", return_value=None):
            renderer.poll_monitor_span()
        renderer.request_close.assert_called_once()

    def test_owner_sees_a_spawned_stop_request(self) -> None:
        renderer = self._renderer()
        with patch.object(span, "visualizer_entry_path", return_value=Path("/program/MP_Liquid_Visualizer.py")), \
             patch.object(span.subprocess, "Popen", side_effect=[MagicMock(pid=7, poll=MagicMock(return_value=None))]):
            renderer.start_monitor_span(False)
        span.request_span_stop(os.getpid())
        with patch.object(renderer, "_stop_span_child") as stop:
            renderer._span_poll_at = 0.0
            renderer.poll_monitor_span()
        self.assertEqual(stop.call_count, 1)
        self.assertFalse(renderer._span_is_active())

    def test_spawned_window_delegates_the_toggle_to_the_owner(self) -> None:
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer.should_close = False
        renderer.request_close = MagicMock()
        renderer._init_span_state((1920, 0, 1920, 1080), "spawned")
        with patch.object(span, "read_span_session", return_value={"owner_pid": os.getpid()}):
            self.assertTrue(renderer.handle_span_key(vulkan_vis.GLFW_KEY_F11))
        self.assertTrue(span.stop_requested(os.getpid()))

    def test_span_monitor_falls_back_to_the_window_monitor(self) -> None:
        """A HiDPI coordinate mismatch must not leave a spanned window monitorless."""
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer._glfw = MagicMock()
        renderer._init_span_state((2880, 0, 2880, 1620), "spawned")
        renderer.monitor_rects = MagicMock(return_value=[("Left", (0, 0, 1920, 1080))])
        sentinel = object()
        renderer._window_monitor = MagicMock(return_value=(sentinel, (0, 0, 1920, 1080)))
        self.assertIs(renderer.span_monitor(), sentinel)

    def test_span_monitor_matches_the_assigned_rect_first(self) -> None:
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer._glfw = MagicMock()
        renderer._init_span_state((1920, 0, 2560, 1440), "spawned")
        renderer.monitor_rects = MagicMock(return_value=[("Right", (1920, 0, 2560, 1440))])
        handle = object()
        renderer._monitor_handle_for = MagicMock(return_value=handle)
        renderer._window_monitor = MagicMock(side_effect=AssertionError("must not be needed"))
        self.assertIs(renderer.span_monitor(), handle)

    def test_spawned_window_does_not_save_the_active_preset(self) -> None:
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer.preset = {"id": 0, "key": "owner_preset"}
        renderer._init_span_state(None, "spawned")
        renderer._device = 0
        renderer._pipeline = 0
        with patch.object(vulkan_vis, "save_active_preset") as save:
            renderer.switch_preset({"id": 3, "key": "spawned_preset"})
        save.assert_not_called()
        self.assertEqual(renderer.preset["key"], "spawned_preset")

    def test_owner_window_still_saves_the_active_preset(self) -> None:
        renderer = vulkan_vis.LiquidVisualizerVulkanRenderer.__new__(vulkan_vis.LiquidVisualizerVulkanRenderer)
        renderer.preset = {"id": 0, "key": "owner_preset"}
        renderer._init_span_state(None, "")
        renderer._device = 0
        renderer._pipeline = 0
        with patch.object(vulkan_vis, "save_active_preset") as save:
            renderer.switch_preset({"id": 3, "key": "next_preset"})
        save.assert_called_once_with("next_preset")


class TestSpanBackends(SpanSessionDirMixin):
    def test_both_renderers_share_the_mixin(self) -> None:
        self.assertTrue(issubclass(vulkan_vis.LiquidVisualizerVulkanRenderer, span.MonitorSpanMixin))
        self.assertTrue(issubclass(gl_vis.LiquidVisualizerOpenGLRenderer, span.MonitorSpanMixin))

    def test_vulkan_binds_f10_and_f11(self) -> None:
        self.assertEqual(vulkan_vis.GLFW_KEY_F10, 299)
        self.assertEqual(vulkan_vis.GLFW_KEY_F11, 300)

    def test_opengl_key_handler_calls_the_span_handler(self) -> None:
        renderer = gl_vis.LiquidVisualizerOpenGLRenderer.__new__(gl_vis.LiquidVisualizerOpenGLRenderer)
        renderer.screensaver = False
        renderer.should_close = False
        renderer.is_fullscreen = False
        renderer.preset = {"id": 0, "key": "cosmic_universe", "name": "Cosmic Universe"}
        renderer.handle_span_key = MagicMock(return_value=True)
        renderer._on_key(None, vulkan_vis.GLFW_KEY_F11, 0, 1, 0)
        renderer.handle_span_key.assert_called_once_with(vulkan_vis.GLFW_KEY_F11)

    def test_cli_hides_the_internal_span_flags(self) -> None:
        res = subprocess.run([sys.executable, str(ROOT_DIR / "MP_Liquid_Visualizer.py"), "--help"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0)
        # Internal flags work but stay out of the public help output.
        self.assertNotIn("--span-bounds", res.stdout)
        self.assertNotIn("--span-role", res.stdout)

    def test_span_flags_are_accepted(self) -> None:
        from unittest.mock import patch as _patch
        with _patch.object(vulkan_vis, "run_visualizer") as run:
            run.return_value = 0
            code = vulkan_vis.main(["--span-bounds", "1920,0,1920,1080", "--span-role", "spawned"])
        self.assertEqual(code, 0)
        _args, kwargs = run.call_args
        self.assertEqual(kwargs["span_bounds"], (1920, 0, 1920, 1080))
        self.assertEqual(kwargs["span_role"], "spawned")


if __name__ == "__main__":
    unittest.main()
