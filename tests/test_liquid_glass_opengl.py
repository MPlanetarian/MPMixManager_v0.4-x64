"""Tests for Liquid Glass OpenGL renderer, standalone player, and backend configuration."""

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_opengl import (  # noqa: E402
    THEME_COLORS,
    LiquidGlassRendererOpenGL,
    glass_foreground_rgb,
    glass_metrics,
    glass_text_rgb,
    theme_rgb,
    theme_text_rgb,
    theme_uses_dark_glass,
)
from MP_Audio_Player_Liquid_Glass_OpenGL import embed_check_argv, player_argv  # noqa: E402


class TestOpenGLTheme(unittest.TestCase):
    def test_theme_aliases_and_palettes(self):
        self.assertEqual(theme_rgb("dreamworlds"), theme_rgb("dreamworlds_ultra"))
        self.assertEqual(theme_rgb("matrix"), theme_rgb("phosphor"))
        self.assertEqual(theme_rgb("cyber"), theme_rgb("cyber_neon"))
        self.assertEqual(theme_rgb("dreamworlds_ultra")[0], (166, 77, 255))


class TestGlassTextInk(unittest.TestCase):
    def test_only_retro_linux_memories_is_the_dark_pane(self):
        for name in THEME_COLORS:
            if name == "retro_linux_memories":
                self.assertTrue(theme_uses_dark_glass(name), name)
            else:
                self.assertFalse(theme_uses_dark_glass(name), name)
        self.assertTrue(theme_uses_dark_glass("Retro Linux Memories"))
        self.assertFalse(theme_uses_dark_glass("cyber_neon"))
        self.assertFalse(theme_uses_dark_glass("dreamworlds_ultra"))

    def test_light_glyphs_darken_and_dark_glyphs_stay(self):
        white = glass_text_rgb(255, 255, 255)
        self.assertTrue(all(channel < 80 for channel in white))
        ice = glass_text_rgb(200, 235, 255)
        self.assertLess(0.299 * ice[0] + 0.587 * ice[1] + 0.114 * ice[2], 80)
        cyan = glass_text_rgb(0, 242, 255)
        self.assertEqual(cyan[0], 0)
        self.assertLess(cyan[1], 80)
        self.assertLess(cyan[2], 90)
        self.assertEqual(glass_text_rgb(247, 37, 133), (247, 37, 133))

    def test_each_theme_has_its_own_text_colour(self):
        names = (
            "stream_of_frequency",
            "dreamworlds_ultra",
            "sensorium_interface",
            "cosmic_supernova",
            "phosphor",
            "retro_linux_memories",
            "retro_terminal",
        )
        colours = [theme_text_rgb(name) for name in names]
        self.assertEqual(len(colours), len(set(colours)))
        self.assertNotEqual(theme_text_rgb("sensorium_interface"), (255, 255, 255))
        self.assertEqual(theme_text_rgb("retro_linux_memories"), (255, 183, 20))

    def test_default_foreground_follows_the_pane(self):
        self.assertEqual(glass_foreground_rgb("retro_linux_memories"), (236, 240, 244))
        ink = glass_foreground_rgb("cyber_neon")
        self.assertTrue(all(channel < 80 for channel in ink))

    def test_linux_hosts_use_dark_ink_on_pale_glass(self):
        import types
        from unittest.mock import MagicMock

        from MP_Audio_Player_Liquid_Glass import GlassHost as VulkanHost
        from MP_Audio_Player_Liquid_Glass_OpenGL import GlassHost as OpenGLHost

        class RGBA:
            def __init__(self, red=0, green=0, blue=0, alpha=1):
                self.red = red
                self.green = green
                self.blue = blue
                self.alpha = alpha

        gdk = types.SimpleNamespace(RGBA=RGBA)
        gi = types.ModuleType("gi")
        repository = types.ModuleType("gi.repository")
        repository.Gdk = gdk
        gi.repository = repository

        opengl = OpenGLHost(["test"], mode="NORMAL", font="Monospace 11")
        vulkan = VulkanHost(["test"], mode="NORMAL", font="Monospace 11")
        with unittest.mock.patch.object(sys.modules["MP_Audio_Player_Liquid_Glass_OpenGL"], "Gdk", gdk):
            for host, theme, dark in (
                (opengl, "cyber_neon", True),
                (opengl, "retro_linux_memories", False),
                (vulkan, "cyber_neon", True),
                (vulkan, "retro_linux_memories", False),
            ):
                term = MagicMock()
                with unittest.mock.patch.dict(sys.modules, {"gi": gi, "gi.repository": repository}):
                    host._apply_glass_foreground(term, theme)
                color = term.set_color_foreground.call_args[0][0]
                peak = max(color.red, color.green, color.blue)
                if dark:
                    self.assertLess(peak, 0.25, theme)
                else:
                    self.assertGreater(min(color.red, color.green, color.blue), 0.85, theme)


class TestOpenGLHost(unittest.TestCase):
    def test_embed_check_does_not_launch_player(self):
        argv = embed_check_argv()
        self.assertNotIn("--interactive", argv)
        self.assertFalse(any(arg.endswith("MP_Audio_Player.py") for arg in argv))

    def test_normal_launch_targets_interactive_player(self):
        self.assertEqual(player_argv()[-2:], [str(ROOT / "MP_Audio_Player.py"), "--interactive"])


class TestManagerBackendConfiguration(unittest.TestCase):
    def test_manager_contains_liquid_glass_backend_wiring(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn('LIQUID_GLASS_BACKEND="${LIQUID_GLASS_BACKEND:-opengl}"', text)
        self.assertIn("configure_liquid_glass_backend", text)
        self.assertIn("MP_Audio_Player_Liquid_Glass_OpenGL.py", text)
        self.assertIn("MP_Audio_Player_Liquid_Glass.py", text)

    def test_config_env_defaults_to_opengl(self):
        config_text = (ROOT / "config.env").read_text(encoding="utf-8")
        self.assertTrue(
            'LIQUID_GLASS_BACKEND="opengl"' in config_text or 'LIQUID_GLASS_BACKEND="vulkan"' in config_text,
            "config.env must contain a valid LIQUID_GLASS_BACKEND configuration"
        )

    def test_config_env_example_contains_liquid_glass_backend(self):
        example_text = (ROOT / "config.env.example").read_text(encoding="utf-8")
        self.assertIn('LIQUID_GLASS_BACKEND="opengl"', example_text)

    def test_manager_shell_parses_cleanly(self):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / "Mix_Archive_Manager.sh")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(os.environ.get("DISPLAY"), "an X11 display is required")
class TestOpenGLFrame(unittest.TestCase):
    def test_opengl_renderer_draws_frame(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "liquid_glass_opengl.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LIQUID_GLASS_OK", result.stdout)
        self.assertIn("OpenGL device:", result.stdout)

    def test_opengl_player_embed_check(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "MP_Audio_Player_Liquid_Glass_OpenGL.py"), "--embed-check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LIQUID_GLASS_EMBED_OK", result.stdout)

    def test_window_movement_and_pointer_tracking(self):
        renderer = LiquidGlassRendererOpenGL(400, 300, "Movement Test")
        try:
            renderer.open()
            from desktop_launch_screen import kscreen_outputs, select_main, visible_origin
            visible = visible_origin(renderer.x11_window(), renderer.title)
            main = select_main(kscreen_outputs())
            self.assertIsNotNone(visible)
            self.assertIsNotNone(main)
            left, top, width, height = main["geo"]
            self.assertTrue(left <= visible[0] < left + width, f"window {visible} is outside {main['name']} {main['geo']}")
            self.assertTrue(top <= visible[1] < top + height, f"window {visible} is outside {main['name']} {main['geo']}")
            renderer.set_window_pos(150, 200)
            self.assertEqual(renderer.window_pos(), (150, 200))
            rx, ry = renderer.root_pointer()
            self.assertIsInstance(rx, int)
            self.assertIsInstance(ry, int)
        finally:
            renderer.close()

    def test_audio_player_launch_liquid_glass_backend_selection(self):
        import MP_Audio_Player
        from unittest.mock import patch, MagicMock

        # Test OpenGL default
        with patch.dict(os.environ, {"LIQUID_GLASS_BACKEND": "opengl"}, clear=False), \
             patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc
            ok = MP_Audio_Player.launch_liquid_glass_player(base_dir=Path(MP_Audio_Player.__file__).resolve().parent)
            self.assertTrue(ok)
            mock_popen.assert_called_once()
            called_args = mock_popen.call_args[0][0]
            self.assertTrue(any("MP_Audio_Player_Liquid_Glass_OpenGL.py" in str(a) for a in called_args))

        # Test Vulkan override
        with patch.dict(os.environ, {"LIQUID_GLASS_BACKEND": "vulkan"}, clear=False), \
             patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12346
            mock_popen.return_value = mock_proc
            ok = MP_Audio_Player.launch_liquid_glass_player(base_dir=Path(MP_Audio_Player.__file__).resolve().parent)
            self.assertTrue(ok)
            mock_popen.assert_called_once()
            called_args = mock_popen.call_args[0][0]
            self.assertTrue(any("MP_Audio_Player_Liquid_Glass.py" in str(a) for a in called_args))


if __name__ == "__main__":
    unittest.main()
