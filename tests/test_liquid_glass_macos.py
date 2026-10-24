"""Tests for Liquid Glass macOS Metal renderer, Apple Silicon requirement, and Intel Mac refusal."""

import os
import platform
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import liquid_glass_metal
from liquid_glass_metal import (
    check_apple_silicon_support,
    get_dynamic_theme_state,
    is_apple_silicon,
    is_intel_mac,
    is_macos,
    theme_rgb,
)
from MP_Audio_Player_Liquid_Glass_macOS import (
    embed_check_argv,
    player_argv,
    player_panel_rects,
)


class TestAppleSiliconRequirement(unittest.TestCase):
    """Verifies strict Apple Silicon Metal enforcement and explicit Intel Mac refusal."""

    def test_apple_silicon_detected_on_darwin_arm64(self):
        with patch("sys.platform", "darwin"), patch("platform.machine", return_value="arm64"):
            self.assertTrue(is_macos())
            self.assertTrue(is_apple_silicon())
            self.assertFalse(is_intel_mac())
            # Should not raise
            check_apple_silicon_support()

    def test_apple_silicon_detected_on_darwin_aarch64(self):
        with patch("sys.platform", "darwin"), patch("platform.machine", return_value="aarch64"):
            self.assertTrue(is_macos())
            self.assertTrue(is_apple_silicon())
            self.assertFalse(is_intel_mac())
            # Should not raise
            check_apple_silicon_support()

    def test_intel_mac_refused_with_clear_error(self):
        with patch("sys.platform", "darwin"), patch("platform.machine", return_value="x86_64"):
            self.assertTrue(is_macos())
            self.assertFalse(is_apple_silicon())
            self.assertTrue(is_intel_mac())
            with self.assertRaises(RuntimeError) as ctx:
                check_apple_silicon_support()
            err_msg = str(ctx.exception)
            self.assertIn("Legacy Intel x86_64 Mac detected", err_msg)
            self.assertIn("Apple Silicon", err_msg)
            self.assertIn("M1/M2/M3/M4", err_msg)

    def test_non_darwin_platform_refused(self):
        with patch("sys.platform", "linux"), patch("platform.machine", return_value="x86_64"):
            self.assertFalse(is_macos())
            self.assertFalse(is_apple_silicon())
            with self.assertRaises(RuntimeError) as ctx:
                check_apple_silicon_support()
            self.assertIn("requires macOS with Apple Silicon", str(ctx.exception))


class TestMacOSPlayerHostConfiguration(unittest.TestCase):
    """Verifies command line arguments, window panels, and modes."""

    def test_embed_check_argv(self):
        argv = embed_check_argv()
        self.assertNotIn("--interactive", argv)
        self.assertFalse(any(arg.endswith("MP_Audio_Player.py") for arg in argv))

    def test_player_argv_modes(self):
        full_argv = player_argv(mode="full")
        self.assertEqual(full_argv[-2:], [str(ROOT / "MP_Audio_Player.py"), "--interactive"])

        mini_argv = player_argv(mode="mini")
        self.assertIn("--mini", mini_argv)

        micro_argv = player_argv(mode="micro")
        self.assertIn("--micro", micro_argv)

    def test_player_panel_rects(self):
        rects_full = player_panel_rects(130, 42, 8, 16, 0, 0, mode="NORMAL")
        self.assertEqual(len(rects_full), 2)
        self.assertGreater(rects_full[0][2], 0)
        self.assertGreater(rects_full[1][2], 0)

        rects_mini = player_panel_rects(80, 16, 8, 16, 0, 0, mode="MINI")
        self.assertEqual(len(rects_mini), 2)

        rects_micro = player_panel_rects(45, 6, 8, 16, 0, 0, mode="MICRO")
        self.assertEqual(len(rects_micro), 2)


class TestMetalShaderAndTheme(unittest.TestCase):
    """Verifies MSL shader source code, theme mappings, and dynamic rainbow breathing."""

    def test_metal_shader_exists_and_contains_entry_points(self):
        shader_file = ROOT / "shaders" / "liquid_glass_metal.metal"
        self.assertTrue(shader_file.is_file(), f"Missing {shader_file}")
        content = shader_file.read_text(encoding="utf-8")
        self.assertIn("liquid_glass_vertex", content)
        self.assertIn("liquid_glass_fragment", content)
        self.assertIn("GlassUniforms", content)
        self.assertIn("sdRoundRect", content)
        self.assertIn("hash21", content)

    def test_theme_rgb_includes_dreamworlds_and_dynamic_rainbow(self):
        rainbow = theme_rgb("dynamic_liquid_glass_rainbow")
        self.assertEqual(len(rainbow), 3)

        dream = theme_rgb("mp_dreamworlds_liquid_transparency")
        self.assertEqual(len(dream), 3)

    def test_dynamic_theme_state_breathing_alpha(self):
        # Base opacity 0.50 reflects 10% core transparency reduction
        colors, eff_at_0, factor_at_0 = get_dynamic_theme_state("dynamic_rainbow_liquid_glass", base_opacity=0.50, current_time=0.0)
        self.assertEqual(len(colors), 3)
        self.assertAlmostEqual(eff_at_0, 0.50, places=2)
        self.assertAlmostEqual(factor_at_0, 1.0, places=2)

        # At 1.5s (quarter cycle of 6s), factor = 1.0 + 0.09 = 1.09
        colors, eff_at_peak, factor_at_peak = get_dynamic_theme_state("dynamic_rainbow_liquid_glass", base_opacity=0.50, current_time=1.5)
        self.assertAlmostEqual(eff_at_peak, 0.50 * 1.09, places=2)
        self.assertAlmostEqual(factor_at_peak, 1.09, places=2)

        # At 4.5s (three-quarter cycle), factor = 1.0 - 0.09 = 0.91
        colors, eff_at_trough, factor_at_trough = get_dynamic_theme_state("dynamic_rainbow_liquid_glass", base_opacity=0.50, current_time=4.5)
        self.assertAlmostEqual(eff_at_trough, 0.50 * 0.91, places=2)
        self.assertAlmostEqual(factor_at_trough, 0.91, places=2)


class TestLauncherIntegrations(unittest.TestCase):
    """Verifies that launch scripts correctly detect Darwin arm64 and reject Intel Macs."""

    def test_launch_liquid_glass_script(self):
        content = (ROOT / "scripts" / "launch_liquid_glass.sh").read_text(encoding="utf-8")
        self.assertIn('uname -s)" = "Darwin"', content)
        self.assertIn('uname -m)" != "arm64"', content)
        self.assertIn("MP_Audio_Player_Liquid_Glass_macOS.py", content)
        self.assertIn("Intel Macs are not supported", content)

    def test_mix_archive_manager_script(self):
        content = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn('os_type" = "Darwin"', content)
        self.assertIn('arch_type" != "arm64"', content)
        self.assertIn("MP_Audio_Player_Liquid_Glass_macOS.py", content)
        self.assertIn("Metal (Apple Silicon)", content)
        self.assertIn("Intel Macs are not supported", content)

    def test_execution_on_linux_reports_apple_silicon_requirement(self):
        # When running the macOS player on Linux, it must gracefully exit 1 with an informative message
        result = subprocess.run(
            [sys.executable, str(ROOT / "MP_Audio_Player_Liquid_Glass_macOS.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(
            "Apple Silicon" in result.stdout or "Apple Silicon" in result.stderr
        )


if __name__ == "__main__":
    unittest.main()
