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
        self.assertGreaterEqual(len(vis.VISUALIZER_PRESETS), 1)
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
            self.assertGreater(bridge.bass_phase, 0.0)
            self.assertGreater(bridge.mid_phase, 0.0)
            self.assertGreater(bridge.high_phase, 0.0)

            frozen_time = bridge.accum_time
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

        with tempfile.TemporaryDirectory() as td:
            out_png = Path(td) / "self_test_1400.png"
            summary = vis.run_self_test(out_png)
            self.assertIn("MP_Liquid_Visualizer Vulkan device:", summary)
            self.assertIn("1400x1400 Fixed Borderless", summary)
            self.assertTrue(out_png.is_file() and out_png.stat().st_size > 50000)


if __name__ == "__main__":
    unittest.main()
