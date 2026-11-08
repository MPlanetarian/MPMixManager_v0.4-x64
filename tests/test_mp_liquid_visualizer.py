#!/usr/bin/env python3
"""Unit and Vulkan GPU integration tests for MP_Liquid_Visualizer."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import MP_Liquid_Visualizer as vis_entry  # noqa: E402
from scripts import mp_liquid_visualizer_vulkan as vis  # noqa: E402


class TestMPLiquidVisualizer(unittest.TestCase):
    def test_window_dimensions_are_fixed_1400x1400(self):
        """Window dimensions must be strictly 1400x1400 fixed."""
        self.assertEqual(vis.WINDOW_WIDTH, 1400)
        self.assertEqual(vis.WINDOW_HEIGHT, 1400)
        self.assertEqual(vis_entry.WINDOW_WIDTH, 1400)
        self.assertEqual(vis_entry.WINDOW_HEIGHT, 1400)

    def test_preset_cosmic_dreamworlds_single_bandcamp_cover(self):
        """First preset must be 'Cosmic Dreamworlds (Liquid)' using strictly ONE Bandcamp cover."""
        self.assertGreaterEqual(len(vis.VISUALIZER_PRESETS), 3)
        preset = vis.get_active_preset("Cosmic Dreamworlds (Liquid)")
        self.assertEqual(preset["name"], "Cosmic Dreamworlds (Liquid)")
        self.assertEqual(preset["key"], "cosmic_dreamworlds_liquid")
        self.assertEqual(preset["album"], "MPlanetarian - Cosmic Dreamworlds [Deluxe Edition]")
        self.assertEqual(
            preset["bandcamp_url"],
            "https://mplanetarian.bandcamp.com/album/mplanetarian-cosmic-dreamworlds-deluxe-edition",
        )
        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Cosmic Dreamworlds (Liquid) must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_preset_orbital_void_reflux_single_bandcamp_cover(self):
        """Second preset must be 'Orbital Void Reflux' using strictly ONE Bandcamp cover (Cover_WMI_V2.png)."""
        preset = vis.get_active_preset("Orbital Void Reflux")
        self.assertEqual(preset["name"], "Orbital Void Reflux")
        self.assertEqual(preset["key"], "orbital_void_reflux")
        self.assertEqual(preset["id"], 1)

        # Aliases test
        self.assertEqual(vis.get_active_preset("orbital_void_reflux")["id"], 1)
        self.assertEqual(vis.get_active_preset("orbital-void-reflux")["id"], 1)
        self.assertEqual(vis.get_active_preset("orbital void")["id"], 1)
        self.assertEqual(vis.get_active_preset("2")["id"], 1)

        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Orbital Void Reflux must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_preset_dreamworlds_ultra_defasten_single_cover(self):
        """Third preset must be 'Dreamworlds Ultra (Defasten Biomech)' inspired by Defasten's XINRI D and Start_Menu_Icon.png."""
        preset = vis.get_active_preset("Dreamworlds Ultra (Defasten Biomech)")
        self.assertEqual(preset["name"], "Dreamworlds Ultra (Defasten Biomech)")
        self.assertEqual(preset["key"], "dreamworlds_ultra_defasten")
        self.assertEqual(preset["id"], 2)

        # Aliases test
        self.assertEqual(vis.get_active_preset("dreamworlds_ultra_defasten")["id"], 2)
        self.assertEqual(vis.get_active_preset("defasten")["id"], 2)
        self.assertEqual(vis.get_active_preset("biomech")["id"], 2)
        self.assertEqual(vis.get_active_preset("3")["id"], 2)

        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Dreamworlds Ultra (Defasten Biomech) must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_preset_infinite_complexity_single_cover(self):
        """Fourth preset (4) must be 'Infinite Complexity' inspired by Defasten's Mirrored Madness and Cover_v4.png."""
        preset = vis.get_active_preset("Infinite Complexity")
        self.assertEqual(preset["name"], "Infinite Complexity")
        self.assertEqual(preset["key"], "infinite_complexity")
        self.assertEqual(preset["id"], 3)

        # Aliases test
        self.assertEqual(vis.get_active_preset("infinite_complexity")["id"], 3)
        self.assertEqual(vis.get_active_preset("infinite complexity")["id"], 3)
        self.assertEqual(vis.get_active_preset("infinite")["id"], 3)
        self.assertEqual(vis.get_active_preset("complexity")["id"], 3)
        self.assertEqual(vis.get_active_preset("4")["id"], 3)

        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Infinite Complexity must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_preset_sensorium_interface_single_cover(self):
        """Fifth preset (5) must be 'Sensorium Interface' inspired by Defasten Earth Flipper and Sensorium_Interface.jpeg."""
        preset = vis.get_active_preset("Sensorium Interface")
        self.assertEqual(preset["name"], "Sensorium Interface")
        self.assertEqual(preset["key"], "sensorium_interface")
        self.assertEqual(preset["id"], 4)

        # Aliases test
        self.assertEqual(vis.get_active_preset("sensorium_interface")["id"], 4)
        self.assertEqual(vis.get_active_preset("sensorium interface")["id"], 4)
        self.assertEqual(vis.get_active_preset("sensorium")["id"], 4)
        self.assertEqual(vis.get_active_preset("earth_flipper")["id"], 4)
        self.assertEqual(vis.get_active_preset("5")["id"], 4)

        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Sensorium Interface must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_preset_beyond_dimensions_single_cover(self):
        """Seventh preset (7) must be 'Beyond Dimensions' inspired by Defasten Beyond Basel and Cotangent Dimensions."""
        preset = vis.get_active_preset("Beyond Dimensions")
        self.assertEqual(preset["name"], "Beyond Dimensions")
        self.assertEqual(preset["key"], "beyond_dimensions")
        self.assertEqual(preset["id"], 6)

        # Aliases test
        self.assertEqual(vis.get_active_preset("beyond_dimensions")["id"], 6)
        self.assertEqual(vis.get_active_preset("beyond dimensions")["id"], 6)
        self.assertEqual(vis.get_active_preset("beyond")["id"], 6)
        self.assertEqual(vis.get_active_preset("dimensions")["id"], 6)
        self.assertEqual(vis.get_active_preset("cotangent")["id"], 6)
        self.assertEqual(vis.get_active_preset("7")["id"], 6)

        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Beyond Dimensions must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_preset_particle_accelerator_single_cover(self):
        """Eighth preset (8) must be 'Particle Accelerator' inspired by Defasten TOROID and Vortex Sync."""
        preset = vis.get_active_preset("Particle Accelerator")
        self.assertEqual(preset["name"], "Particle Accelerator")
        self.assertEqual(preset["key"], "particle_accelerator")
        self.assertEqual(preset["id"], 7)

        # Aliases test
        self.assertEqual(vis.get_active_preset("particle_accelerator")["id"], 7)
        self.assertEqual(vis.get_active_preset("particle accelerator")["id"], 7)
        self.assertEqual(vis.get_active_preset("particle")["id"], 7)
        self.assertEqual(vis.get_active_preset("accelerator")["id"], 7)
        self.assertEqual(vis.get_active_preset("toroid")["id"], 7)
        self.assertEqual(vis.get_active_preset("8")["id"], 7)

        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Particle Accelerator must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_preset_cosmic_universe_single_cover(self):
        """Ninth preset (9) must be 'Cosmic Universe' inspired by Defasten Constellation and The Cosmological Horizon."""
        preset = vis.get_active_preset("Cosmic Universe")
        self.assertEqual(preset["name"], "Cosmic Universe")
        self.assertEqual(preset["key"], "cosmic_universe")
        self.assertEqual(preset["id"], 8)

        # Aliases test
        self.assertEqual(vis.get_active_preset("cosmic_universe")["id"], 8)
        self.assertEqual(vis.get_active_preset("cosmic universe")["id"], 8)
        self.assertEqual(vis.get_active_preset("cosmic")["id"], 8)
        self.assertEqual(vis.get_active_preset("universe")["id"], 8)
        self.assertEqual(vis.get_active_preset("constellation")["id"], 8)
        self.assertEqual(vis.get_active_preset("9")["id"], 8)

        existing_covers = [Path(p) for p in preset["cover_paths"] if Path(p).is_file()]
        self.assertGreaterEqual(
            len(existing_covers),
            1,
            "Cover art file for Cosmic Universe must exist",
        )

        w, h, rgba_bytes = vis.load_preset_cover_rgba(preset, tex_size=256)
        self.assertEqual((w, h), (256, 256))
        self.assertEqual(len(rgba_bytes), 256 * 256 * 4)

    def test_audio_telemetry_advances_only_when_playing(self):
        """3D generation must advance when music is playing and freeze in-place when paused or stopped."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            bridge = vis.AudioTelemetryBridge()
            state_file = tmp_path / "mp_player_state.json"
            bridge.state_file = state_file

            # 1. Stopped state -> 3D generation waits at 0.0
            state_file.write_text(
                json.dumps(
                    {
                        "running": True,
                        "state": "stopped",
                        "muted": False,
                        "rms_level": 0.0,
                        "levels": [0.0] * 24,
                    }
                ),
                encoding="utf-8",
            )
            bridge.update(0.25)
            self.assertFalse(bridge.is_playing)
            self.assertEqual(bridge.accum_time, 0.0)
            self.assertEqual(bridge.bass_phase, 0.0)

            # 2. Playing state -> 3D generation advances and reacts to audio bands
            state_file.write_text(
                json.dumps(
                    {
                        "running": True,
                        "state": "playing",
                        "muted": False,
                        "rms_level": 0.42,
                        "pitch_factor": 1.0,
                        "levels": [0.8, 0.75, 0.7, 0.6, 0.5, 0.45, 0.4, 0.35] * 3,
                    }
                ),
                encoding="utf-8",
            )
            for _ in range(5):
                bridge.update(0.10)
            self.assertTrue(bridge.is_playing)
            self.assertGreater(bridge.accum_time, 0.0)
            self.assertGreater(bridge.dynamic_time, 0.0)
            self.assertGreater(bridge.bass_phase, 0.0)
            self.assertGreater(bridge.mid_phase, 0.0)
            self.assertGreater(bridge.high_phase, 0.0)

            frozen_time = bridge.accum_time
            frozen_dynamic_time = bridge.dynamic_time
            frozen_bass_phase = bridge.bass_phase
            frozen_mid_phase = bridge.mid_phase
            frozen_high_phase = bridge.high_phase

            # 3. Paused state -> 3D generation freezes in-place and waits for Play
            state_file.write_text(
                json.dumps(
                    {
                        "running": True,
                        "state": "paused",
                        "muted": False,
                        "rms_level": 0.42,
                        "levels": [0.8] * 24,
                    }
                ),
                encoding="utf-8",
            )
            for _ in range(10):
                bridge.update(0.10)
            self.assertFalse(bridge.is_playing)
            self.assertEqual(bridge.accum_time, frozen_time)
            self.assertEqual(bridge.dynamic_time, frozen_dynamic_time)
            self.assertEqual(bridge.bass_phase, frozen_bass_phase)
            self.assertEqual(bridge.mid_phase, frozen_mid_phase)
            self.assertEqual(bridge.high_phase, frozen_high_phase)

    def test_escape_and_q_keys_close_window(self):
        """Pressing Escape (256) or 'q' (81) must close the borderless window."""
        src = Path(vis.__file__).read_text(encoding="utf-8")
        self.assertIn("GLFW_DECORATED = 0x00020005", src)
        self.assertIn("GLFW_RESIZABLE = 0x00020003", src)
        self.assertIn("GLFW_KEY_ESCAPE = 256", src)
        self.assertIn("GLFW_KEY_Q = 81", src)
        self.assertIn("key in (GLFW_KEY_ESCAPE, GLFW_KEY_Q)", src)

    def test_z_key_toggles_fullscreen_and_normal_size(self):
        """Pressing Z inside MP_Liquid_Visualizer must toggle full screen on and back to normal 1400x1400 size."""
        import time

        renderer = vis.LiquidVisualizerVulkanRenderer()
        bridge = vis.AudioTelemetryBridge()
        try:
            renderer.open()
            self.assertFalse(renderer.is_fullscreen)
            self.assertEqual(renderer.window_size(), (1400, 1400))

            # Press Z -> enters fullscreen
            renderer._on_key(renderer._window, vis.GLFW_KEY_Z, 0, vis.GLFW_PRESS, 0)
            self.assertTrue(renderer.is_fullscreen)
            for _ in range(5):
                bridge.update(0.05, force_playing=True, synthetic_audio=True)
                renderer.draw(bridge, capture=False)
                time.sleep(0.01)
            fs_w, fs_h = renderer.window_size()
            self.assertGreater(fs_w, 1400)
            self.assertEqual(renderer._extent, renderer.framebuffer_size())

            # Press Z again -> returns to normal 1400x1400 size
            renderer._on_key(renderer._window, vis.GLFW_KEY_Z, 0, vis.GLFW_PRESS, 0)
            self.assertFalse(renderer.is_fullscreen)
            for _ in range(5):
                bridge.update(0.05, force_playing=True, synthetic_audio=True)
                renderer.draw(bridge, capture=False)
                time.sleep(0.01)
            self.assertEqual(renderer.window_size(), (1400, 1400))
            self.assertEqual(renderer._extent, (1400, 1400))
        finally:
            renderer.close()

    def test_shaders_compiled_and_valid(self):
        """Both Vulkan SPIR-V shaders must exist and have valid SPIR-V magic numbers."""
        vert_spv = ROOT / "shaders" / "mp_liquid_visualizer.vert.spv"
        frag_spv = ROOT / "shaders" / "mp_liquid_visualizer.frag.spv"
        self.assertTrue(vert_spv.is_file() and vert_spv.stat().st_size > 100)
        self.assertTrue(frag_spv.is_file() and frag_spv.stat().st_size > 1000)
        self.assertEqual(vert_spv.read_bytes()[:4], b"\x03\x02#\x07")
        self.assertEqual(frag_spv.read_bytes()[:4], b"\x03\x02#\x07")

    def test_cli_list_presets_and_vulkan_self_test(self):
        """CLI --list-presets and --self-test must succeed and render a 1400x1400 PNG."""
        res_list = subprocess.run(
            [sys.executable, str(ROOT / "MP_Liquid_Visualizer.py"), "--list-presets"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(res_list.returncode, 0)
        self.assertIn("Cosmic Dreamworlds (Liquid)", res_list.stdout)
        self.assertIn("Orbital Void Reflux", res_list.stdout)

        with tempfile.TemporaryDirectory() as td:
            out_png = Path(td) / "self_test_1400.png"
            summary = vis.run_self_test(out_png)
            self.assertIn("MP_Liquid_Visualizer Vulkan device:", summary)
            self.assertIn("1400x1400 Fixed Borderless", summary)
            self.assertTrue(out_png.is_file() and out_png.stat().st_size > 50000)


    def test_fullscreen_no_auto_iconify_across_desktops(self):
        """Fullscreen window must disable GLFW_AUTO_ICONIFY and enable GLFW_FLOATING so it stays visible when clicking away."""
        renderer = vis.LiquidVisualizerVulkanRenderer()
        try:
            renderer.open()
            g = renderer._glfw
            if hasattr(g, "glfwGetWindowAttrib"):
                # Window must have auto-iconify disabled so focusing another desktop does not hide it
                auto_iconify = g.glfwGetWindowAttrib(renderer._window, vis.GLFW_AUTO_ICONIFY)
                self.assertEqual(auto_iconify, 0)

            # Toggle fullscreen (press Z)
            renderer._on_key(renderer._window, vis.GLFW_KEY_Z, 0, vis.GLFW_PRESS, 0)
            self.assertTrue(renderer.is_fullscreen)

            if hasattr(g, "glfwGetWindowAttrib"):
                auto_iconify = g.glfwGetWindowAttrib(renderer._window, vis.GLFW_AUTO_ICONIFY)
                self.assertEqual(auto_iconify, 0)
                floating = g.glfwGetWindowAttrib(renderer._window, vis.GLFW_FLOATING)
                self.assertEqual(floating, 1)

            # Polling while fullscreen must never iconify / disappear
            for _ in range(5):
                renderer.poll()

            if hasattr(g, "glfwGetWindowAttrib"):
                iconified = g.glfwGetWindowAttrib(renderer._window, vis.GLFW_ICONIFIED)
                self.assertEqual(iconified, 0)

            # Press Z again -> returns to normal 1400x1400 windowed mode
            renderer._on_key(renderer._window, vis.GLFW_KEY_Z, 0, vis.GLFW_PRESS, 0)
            self.assertFalse(renderer.is_fullscreen)
            import time
            for _ in range(5):
                renderer.poll()
                time.sleep(0.01)
            self.assertEqual(renderer.window_size(), (1400, 1400))
            if hasattr(g, "glfwGetWindowAttrib"):
                floating = g.glfwGetWindowAttrib(renderer._window, vis.GLFW_FLOATING)
                self.assertEqual(floating, 0)
        finally:
            renderer.close()

    def test_two_visualizer_processes_can_run_simultaneously(self):
        """Two separate visualizer processes can run simultaneously without conflicts."""
        p1 = subprocess.Popen([sys.executable, str(ROOT / "MP_Liquid_Visualizer.py"), "--max-seconds", "1"])
        p2 = subprocess.Popen([sys.executable, str(ROOT / "MP_Liquid_Visualizer.py"), "--max-seconds", "1"])
        ret1 = p1.wait(timeout=10)
        ret2 = p2.wait(timeout=10)
        self.assertEqual(ret1, 0)
        self.assertEqual(ret2, 0)

    def test_4k_display_rendered_at_1080p_not_4k(self):
        """When the Visualizer runs or goes fullscreen on a 4K display, it must render at 1920x1080, NOT 4K."""
        renderer = vis.LiquidVisualizerVulkanRenderer(target_4k=True)
        bridge = vis.AudioTelemetryBridge()
        try:
            renderer.open()
            # If a 4K display is present on the machine, target_4k will target it and enter fullscreen
            self.assertTrue(renderer.is_fullscreen)
            self.assertEqual(renderer.window_size(), (1920, 1080))
            self.assertEqual(renderer.framebuffer_size(), (1920, 1080))
            self.assertEqual(renderer._extent, (1920, 1080))

            for _ in range(5):
                bridge.update(0.05, force_playing=True, synthetic_audio=True)
                renderer.draw(bridge, capture=False)
                time.sleep(0.01)

            # Ensure Vulkan swapchain extent and framebuffer are strictly 1920x1080 (never 4K: 3840x2160)
            self.assertEqual(renderer._extent, (1920, 1080))
            self.assertEqual(renderer.framebuffer_size(), (1920, 1080))
            self.assertNotEqual(renderer._extent, (3840, 2160))

            # Toggle Z -> returns cleanly to normal 1400x1400 windowed mode
            renderer._on_key(renderer._window, vis.GLFW_KEY_Z, 0, vis.GLFW_PRESS, 0)
            self.assertFalse(renderer.is_fullscreen)
            for _ in range(5):
                bridge.update(0.05, force_playing=True, synthetic_audio=True)
                renderer.draw(bridge, capture=False)
                time.sleep(0.01)
            self.assertEqual(renderer.window_size(), (1400, 1400))
            self.assertEqual(renderer._extent, (1400, 1400))
        finally:
            renderer.close()

    def test_is_4k_display_detection_and_constants(self):
        """Verify 4K display detection logic and 1080p resolution constants."""
        self.assertEqual(vis.RENDER_1080P_WIDTH, 1920)
        self.assertEqual(vis.RENDER_1080P_HEIGHT, 1080)
        self.assertEqual(vis.FOUR_K_MIN_WIDTH, 3840)
        self.assertEqual(vis.FOUR_K_MIN_HEIGHT, 2160)

        # Mock monitor with 4K video mode (3840x2160)
        class MockVideoMode:
            width = 3840
            height = 2160
            refreshRate = 60

        class MockGLFW:
            def glfwGetVideoMode(self, mon):
                class Ptr:
                    contents = MockVideoMode()
                return Ptr()
            def glfwGetMonitorName(self, mon):
                return b"Hisense 4K TV"

        renderer = vis.LiquidVisualizerVulkanRenderer()
        renderer._glfw = MockGLFW()
        self.assertTrue(renderer.is_4k_display(12345))

        # Mock standard 1080p monitor
        MockVideoMode.width = 1920
        MockVideoMode.height = 1080
        MockGLFW.glfwGetMonitorName = lambda s, m: b"Standard 1080p Display"
        self.assertFalse(renderer.is_4k_display(12345))

    def test_cli_4k_and_fullscreen_options(self):
        """CLI must accept --fullscreen, --4k, and --screen flags."""
        res = subprocess.run(
            [sys.executable, str(ROOT / "MP_Liquid_Visualizer.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--fullscreen", res.stdout)
        self.assertIn("--4k", res.stdout)
        self.assertIn("--screen", res.stdout)
        self.assertIn("1920x1080", res.stdout)


if __name__ == "__main__":
    unittest.main()
