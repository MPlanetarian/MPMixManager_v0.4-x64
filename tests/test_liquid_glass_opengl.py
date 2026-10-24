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
    LiquidGlassRendererOpenGL,
    glass_metrics,
    theme_rgb,
)
from MP_Audio_Player_Liquid_Glass_OpenGL import embed_check_argv, player_argv  # noqa: E402


class TestOpenGLTheme(unittest.TestCase):
    def test_theme_aliases_and_palettes(self):
        self.assertEqual(theme_rgb("dreamworlds"), theme_rgb("dreamworlds_ultra"))
        self.assertEqual(theme_rgb("matrix"), theme_rgb("phosphor"))
        self.assertEqual(theme_rgb("cyber"), theme_rgb("cyber_neon"))
        self.assertEqual(theme_rgb("dreamworlds_ultra")[0], (166, 77, 255))


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
            init_pos = renderer.window_pos()
            self.assertEqual(init_pos, (72, 64))
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
