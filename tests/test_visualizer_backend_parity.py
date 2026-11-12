#!/usr/bin/env python3
"""Tests for MP Visualizer backend parity.

Two guarantees are covered:

1. The in-window MP Visualizer background exists on both the OpenGL and the
   Vulkan player host, so the picture behind the terminal does not depend on
   which backend the user configured.
2. The standalone MP Visualizer runs its whole preset library on either
   backend, and the backend is chosen from the user's configuration.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import liquid_glass_opengl
import liquid_glass_vulkan
import liquid_player_visualizer
import mp_liquid_visualizer_vulkan
import visualizer_backend


class TestVisualizerBackendSelection(unittest.TestCase):
    """``visualizer_backend`` resolves auto/opengl/vulkan from config."""

    def test_normalise_aliases(self):
        self.assertEqual(visualizer_backend.normalise("GL"), "opengl")
        self.assertEqual(visualizer_backend.normalise("vk"), "vulkan")
        self.assertEqual(visualizer_backend.normalise(""), "auto")
        self.assertEqual(visualizer_backend.normalise("bogus"), "auto")

    def test_explicit_backend_is_never_probed(self):
        with patch.object(visualizer_backend, "vulkan_available") as available:
            available.return_value = False
            self.assertEqual(visualizer_backend.resolve("vulkan"), "vulkan")
            self.assertEqual(visualizer_backend.resolve("opengl"), "opengl")

    def test_auto_prefers_vulkan_when_a_driver_exists(self):
        with patch.object(visualizer_backend, "configured_backend", return_value="auto"), \
             patch.object(visualizer_backend, "vulkan_available", return_value=True):
            self.assertEqual(visualizer_backend.resolve(), "vulkan")

    def test_auto_falls_back_to_opengl_without_a_driver(self):
        with patch.object(visualizer_backend, "configured_backend", return_value="auto"), \
             patch.object(visualizer_backend, "vulkan_available", return_value=False):
            self.assertEqual(visualizer_backend.resolve(), "opengl")

    def test_configured_player_backend_is_honoured(self):
        with patch.object(visualizer_backend, "configured_backend", return_value="opengl"), \
             patch.object(visualizer_backend, "vulkan_available", return_value=True):
            self.assertEqual(visualizer_backend.resolve(), "opengl")

    def test_renderer_class_mapping(self):
        self.assertIs(
            visualizer_backend.renderer_class("opengl"),
            liquid_player_visualizer.LiquidVisualizerOpenGLRenderer,
        )
        self.assertIs(
            visualizer_backend.renderer_class("vulkan"),
            mp_liquid_visualizer_vulkan.LiquidVisualizerVulkanRenderer,
        )

    def test_config_env_is_read_without_importing_the_manager(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.env"
            path.write_text('LIQUID_GLASS_BACKEND="vulkan"\n', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("LIQUID_GLASS_BACKEND", None)
                os.environ.pop("VISUALIZER_BACKEND", None)
                self.assertEqual(visualizer_backend.configured_backend(path), "vulkan")


class TestInWindowVisualizerOnBothBackends(unittest.TestCase):
    """The player-window background is implemented by both renderers."""

    def test_opengl_host_has_the_background_hooks(self):
        renderer = liquid_glass_opengl.LiquidGlassRendererOpenGL
        self.assertTrue(hasattr(renderer, "draw_player_visualizer_background"))
        self.assertTrue(hasattr(renderer, "sync_player_visualizer_opacity"))

    def test_vulkan_host_has_the_background_hooks(self):
        renderer = liquid_glass_vulkan.LiquidGlassRenderer
        self.assertTrue(hasattr(renderer, "draw_player_visualizer_background"))
        self.assertTrue(hasattr(renderer, "sync_player_visualizer_opacity"))

    def test_vulkan_renderer_defaults_to_glass_only(self):
        """A host that never opts in must not draw the visualizer."""
        renderer = object.__new__(liquid_glass_vulkan.LiquidGlassRenderer)
        renderer.allow_player_visualizer = False
        self.assertFalse(renderer.draw_player_visualizer_background(640, 480))

    def test_vulkan_video_layer_class_exists(self):
        self.assertTrue(callable(liquid_glass_vulkan.VisualizerBackground))

    def test_vulkan_draw_uses_the_visualizer_pipeline_when_active(self):
        """An active visualizer replaces the glass pass, not adds to it."""
        renderer = object.__new__(liquid_glass_vulkan.LiquidGlassRenderer)
        renderer._vk = MagicMock()
        renderer._device = 1
        renderer._fences = [10, 11]
        renderer._frame = 0
        renderer._image_available = [20, 21]
        renderer._render_finished = [30, 31]
        renderer._cmd = [40, 41]
        renderer._swapchain = 50
        renderer._images = [60, 61]
        renderer._framebuffers = [70, 71]
        renderer._extent = (640, 480)
        renderer._can_readback = False
        renderer._queue = 80
        renderer._render_pass = 90
        renderer._shape_size = (640, 480)
        renderer._pipeline = 999
        renderer._ubo = 555
        for name in ("WaitForFences", "ResetFences", "ResetCommandBuffer", "BeginCommandBuffer",
                     "EndCommandBuffer", "QueueSubmit", "QueuePresentKHR"):
            getattr(renderer._vk, name).return_value = 0
        renderer._vk.AcquireNextImageKHR.return_value = 0

        calls = []

        def fake_layer_draw(layer, host, state):
            calls.append(state)
            host._vk.CmdBeginRenderPass(host._draw_cmd, None, 0)
            host._vk.CmdDraw(host._draw_cmd, 3, 1, 0, 0)
            host._vk.CmdEndRenderPass(host._draw_cmd)
            return True

        renderer._vis_layer = MagicMock()
        renderer._vis_layer.draw.side_effect = lambda host, state: fake_layer_draw(
            renderer._vis_layer, host, state
        )
        renderer.poll = lambda: True
        renderer.framebuffer_size = lambda: (640, 480)
        renderer.window_size = lambda: (640, 480)
        renderer._visualizer_state = lambda: {"active": True, "preset_id": 3}
        renderer.sync_player_visualizer_opacity = MagicMock()

        liquid_glass_vulkan.LiquidGlassRenderer.draw(renderer, "dreamworlds_ultra")

        self.assertEqual(len(calls), 1, "the visualizer must draw once")
        bound = [call.args[2] for call in renderer._vk.CmdBindPipeline.call_args_list]
        self.assertNotIn(999, bound, "the glass pipeline must not draw over the visualizer")
        renderer.sync_player_visualizer_opacity.assert_called_once_with(True)

    def test_vulkan_player_host_opts_into_the_background(self):
        source = (ROOT / "MP_Audio_Player_Liquid_Glass.py").read_text(encoding="utf-8")
        self.assertIn("allow_player_visualizer", source)
        self.assertIn("allow_visualizer", source)

    def test_opengl_player_host_still_opts_into_the_background(self):
        source = (ROOT / "MP_Audio_Player_Liquid_Glass_OpenGL.py").read_text(encoding="utf-8")
        self.assertIn("allow_player_visualizer", source)


class TestOpenGLLayerSupportsEveryPreset(unittest.TestCase):
    """The OpenGL port covers the whole preset library, not just preset 1."""

    def test_generic_source_is_a_single_shader_for_all_presets(self):
        source = liquid_player_visualizer.opengl_visualizer_source()
        # One program carries every scene; the preset id selects inside it.
        self.assertIn("uniform vec4 u_preset", source)
        self.assertIn("u_preset.x", source)

    def test_every_preset_specialises_to_a_distinct_program(self):
        base = liquid_player_visualizer.opengl_visualizer_source()
        seen = set()
        for preset in mp_liquid_visualizer_vulkan.VISUALIZER_PRESETS:
            folded = liquid_player_visualizer.specialize_visualizer_source(
                base, int(preset["id"]), 64
            )
            self.assertNotIn("u_preset.x", folded, preset["key"])
            self.assertIn(f"({float(int(preset['id'])):.1f})", folded, preset["key"])
            seen.add(folded)
        self.assertEqual(len(seen), len(mp_liquid_visualizer_vulkan.VISUALIZER_PRESETS))

    def test_every_preset_has_shipped_spirv_for_vulkan(self):
        for preset in mp_liquid_visualizer_vulkan.VISUALIZER_PRESETS:
            path = liquid_player_visualizer.vulkan_preset_spirv(int(preset["id"]), march_steps=64)
            self.assertIsNotNone(path, preset["key"])
            self.assertTrue(Path(path).read_bytes().startswith(liquid_player_visualizer._SPIRV_MAGIC))

    def test_preset_count_matches_the_number_key_slots_plus_extras(self):
        presets = mp_liquid_visualizer_vulkan.VISUALIZER_PRESETS
        slots = mp_liquid_visualizer_vulkan.presets_by_slot()
        self.assertEqual(len(slots), 9)
        self.assertGreaterEqual(len(presets), len(slots))
        # Extra presets must still be reachable by cycling.
        current = presets[-1]
        nxt = mp_liquid_visualizer_vulkan.cycle_preset(current, 1)
        self.assertIs(nxt, presets[0])


class TestStandaloneVisualizerAcceptsBackend(unittest.TestCase):
    """The standalone entry point can be pinned to either backend."""

    def test_renderer_factory_honours_an_explicit_backend(self):
        with patch.object(visualizer_backend, "resolve", return_value="opengl"):
            made = mp_liquid_visualizer_vulkan._make_renderer("cosmic_dreamworlds_liquid")
        self.assertIsInstance(made, liquid_player_visualizer.LiquidVisualizerOpenGLRenderer)

    def test_cli_exposes_a_backend_flag(self):
        argv = ["--backend", "opengl", "--list-presets"]
        with patch("sys.stdout"):
            self.assertEqual(mp_liquid_visualizer_vulkan.main(argv), 0)

    def test_self_test_routes_to_the_selected_backend(self):
        with patch.object(visualizer_backend, "resolve", return_value="opengl"), \
             patch.object(mp_liquid_visualizer_vulkan, "_run_opengl_self_test",
                          return_value="ok") as opengl_test:
            result = mp_liquid_visualizer_vulkan.run_self_test(backend="opengl")
        self.assertEqual(result, "ok")
        opengl_test.assert_called_once()


class TestLaunchScriptsForwardTheBackend(unittest.TestCase):
    """Every launcher tells the visualizer which backend the host chose."""

    def test_player_and_gui_launchers_pass_backend(self):
        for name in ("scripts/launch_liquid_glass.sh", "scripts/launch-liquid-glass", "MP_Gui.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("--backend", text, name)

    def test_player_hosts_pass_their_own_backend(self):
        expectations = {
            "MP_Audio_Player_Liquid_Glass.py": '"vulkan"',
            "MP_Audio_Player_Liquid_Glass_OpenGL.py": '"opengl"',
        }
        for name, value in expectations.items():
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("--backend", text, name)
            self.assertIn(value, text, name)


if __name__ == "__main__":
    unittest.main()
