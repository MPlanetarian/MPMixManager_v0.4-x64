"""MP Mix Manager GUI: Charcoal Vault theme, menu option 36, and shutdown."""

import os
import signal
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import liquid_visualizer_session as vis_session
from liquid_glass_metal import theme_rgb as metal_theme_rgb
from liquid_glass_opengl import theme_rgb as opengl_theme_rgb
from liquid_glass_vulkan import theme_rgb as vulkan_theme_rgb

CHARCOAL = ((45, 45, 45), (21, 83, 158), (26, 30, 33))
MANAGER_THEMES = (
    "stream_of_frequency",
    "dreamworlds",
    "cosmic_dreamworlds",
    "cosmic_dreamworlds_radioactive",
    "orbital_void_reflux",
    "dynamic_rainbow_liquid_glass",
    "dreamworlds_liquid",
    "dreamworlds_ultra",
    "cosmic_supernova",
    "retro_linux_memories",
    "retro_terminal",
    "dracula",
    "nord",
    "matrix",
    "solarized",
    "tokyo",
    "monokai",
    "gruvbox",
    "emerald",
    "classic",
    "cyberpunk",
    "charcoal_vault",
)


class TestCharcoalVaultTheme(unittest.TestCase):
    def test_glass_palettes_match_the_veracrypt_screenshot(self):
        for theme_rgb in (opengl_theme_rgb, vulkan_theme_rgb, metal_theme_rgb):
            self.assertEqual(theme_rgb("charcoal_vault"), CHARCOAL)
            self.assertEqual(theme_rgb("veracrypt_dark"), CHARCOAL)
            self.assertEqual(theme_rgb("Charcoal Vault (VeraCrypt Dark)"), CHARCOAL)
            self.assertEqual(theme_rgb("veracrypt"), theme_rgb("retro_linux_memories"))
            self.assertNotEqual(theme_rgb("veracrypt"), CHARCOAL)

    def test_builtin_manager_themes_resolve_to_their_own_glass(self):
        ultra = opengl_theme_rgb("dreamworlds_ultra")
        for name in MANAGER_THEMES:
            colors = opengl_theme_rgb(name)
            self.assertEqual(len(colors), 3)
            self.assertTrue(all(len(rgb) == 3 for rgb in colors))
            if name not in ("dreamworlds", "dreamworlds_ultra", "default"):
                self.assertNotEqual(colors, ultra, name)


class TestManagerMenu(unittest.TestCase):
    def test_option_36_launches_the_gui_without_moving_exit(self):
        text = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn(
            "36|MP Mix Manager GUI|(Liquid Glass window • MP Liquid Player interface • Charcoal Vault and built-in themes)",
            text,
        )
        self.assertIn('36|mp-gui|gui|MP_Gui|"MP Mix Manager GUI"*) launch_mp_gui_from_menu', text)
        self.assertIn("launch_mp_gui_from_menu", text)
        self.assertIn('CURRENT_THEME="charcoal_vault"', text)
        self.assertIn("23|Charcoal Vault (VeraCrypt Dark)", text)
        self.assertIn("MP_GUI_SESSION", text)
        self.assertIn("37|77|", text)
        self.assertNotIn("36|77|", text)
        self.assertIn("between 0 and 37", text)

    def test_shell_parses(self):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / "Mix_Archive_Manager.sh")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestGuiLauncher(unittest.TestCase):
    def test_mp_gui_starts_the_manager_host(self):
        path = ROOT / "MP_Gui.sh"
        self.assertTrue(path.is_file())
        mode = path.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)
        text = path.read_text(encoding="utf-8")
        self.assertIn("--manager", text)
        self.assertIn("charcoal_vault", text)
        self.assertIn("--keep-theme", text)
        self.assertIn('MP Mix Manager (Liquid Glass', text)
        result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hosts_stop_playback_and_the_visualizer_for_the_manager(self):
        for name in (
            "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "MP_Audio_Player_Liquid_Glass.py",
            "MP_Audio_Player_Liquid_Glass_macOS.py",
            "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
        ):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn('os.environ["MP_GUI_SESSION"] = "1"', text)
            self.assertIn("stop_companion_playback()", text)
            self.assertIn("stop_companion_visualizer(force=True)", text)
            self.assertIn("stop_companion_visualizer()", text)


class TestGuiShutdown(unittest.TestCase):
    @patch("liquid_visualizer_session._signal_visualizer")
    @patch("liquid_visualizer_session._alive", return_value=False)
    @patch("liquid_visualizer_session.visualizer_pids", return_value=[4242])
    @patch("liquid_visualizer_session.other_liquid_player_running", return_value=True)
    def test_forced_close_stops_the_visualizer_while_another_host_is_open(self, _other, _pids, _alive, signal_vis):
        vis_session.stop_companion_visualizer(force=True)
        signal_vis.assert_called_once_with(4242, signal.SIGTERM)

    @patch("liquid_visualizer_session._signal_visualizer")
    @patch("liquid_visualizer_session._playback_engine_pids", return_value=[5150])
    @patch("liquid_visualizer_session._send_player_stop")
    @patch("liquid_visualizer_session._alive", return_value=False)
    def test_gui_close_stops_playback_engines(self, _alive, send_stop, _pids, signal_vis):
        vis_session.stop_companion_playback()
        send_stop.assert_called_once_with()
        signal_vis.assert_called_once_with(5150, signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
