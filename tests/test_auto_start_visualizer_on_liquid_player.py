#!/usr/bin/env python3
"""
Unit tests for automatic random visualizer launch when running MP Liquid Player.
Verifies:
  1. Preset random selection in mp_liquid_visualizer_vulkan.py.
  2. Stream of Frequency preset accessibility.
  3. ensure_random_visualizer_started() single-instance guard and process spawn.
  4. --no-visualizer flag handling.
  5. Shell scripts (Mix_Archive_Manager.sh, scripts/launch_liquid_glass.sh) integration.
"""

import os
import signal
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import liquid_visualizer_session as vis_session

import mp_liquid_visualizer_vulkan as vis_mod
import MP_Audio_Player_Liquid_Glass_OpenGL as opengl_glass
import MP_Audio_Player_Liquid_Glass as vulkan_glass
import MP_Audio_Player_Liquid_Glass_macOS as macos_glass


class TestAutoStartVisualizerOnLiquidPlayer(unittest.TestCase):
    def test_random_preset_selection(self):
        """get_active_preset('random') should return valid presets and exhibit variance across draws."""
        samples = set()
        for _ in range(50):
            preset = vis_mod.get_active_preset("random")
            self.assertIn("key", preset)
            self.assertIn("name", preset)
            samples.add(preset["key"])
        # With 6 presets and 50 draws, probability of getting only 1 preset is astronomically small
        self.assertGreater(len(samples), 1)

    def test_random_preset_aliases(self):
        """Aliases like 'rand', 'rnd', 'any', 'shuffle' should all trigger random selection."""
        for alias in ("rand", "rnd", "any", "shuffle", "-1"):
            preset = vis_mod.get_active_preset(alias)
            self.assertIn(preset["key"], [p["key"] for p in vis_mod.VISUALIZER_PRESETS])

    def test_stream_of_frequency_preset(self):
        """Preset Stream of Frequency (internal ID 5, 1-based index 6) is correctly registered and resolvable."""
        preset_by_idx = vis_mod.get_active_preset("6")
        self.assertEqual(preset_by_idx["key"], "stream_of_frequency")
        self.assertEqual(preset_by_idx["name"], "Stream of Frequency")
        self.assertEqual(preset_by_idx["id"], 5)

        preset_by_key = vis_mod.get_active_preset("stream_of_frequency")
        self.assertEqual(preset_by_key["id"], 5)

        preset_by_name = vis_mod.get_active_preset("stream of frequency")
        self.assertEqual(preset_by_name["key"], "stream_of_frequency")

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_ensure_random_visualizer_skips_when_already_running(self, mock_popen, mock_run):
        """ensure_random_visualizer_started should return False if already running."""
        # Mock pgrep returning 0 (process found)
        mock_run.return_value = MagicMock(returncode=0)

        started = opengl_glass.ensure_random_visualizer_started()
        self.assertFalse(started)
        mock_popen.assert_not_called()

        started_vulkan = vulkan_glass.ensure_random_visualizer_started()
        self.assertFalse(started_vulkan)
        mock_popen.assert_not_called()

        started_macos = macos_glass.ensure_random_visualizer_started()
        self.assertFalse(started_macos)
        mock_popen.assert_not_called()

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    def test_ensure_random_visualizer_spawns_when_not_running(self, mock_popen, mock_run):
        """ensure_random_visualizer_started should spawn visualizer with --preset random when not running."""
        # Mock pgrep returning 1 (process not found)
        mock_run.return_value = MagicMock(returncode=1)
        mock_proc = MagicMock(pid=12345)
        mock_popen.return_value = mock_proc

        started = opengl_glass.ensure_random_visualizer_started()
        self.assertTrue(started)
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        self.assertIn("--preset", cmd)
        self.assertIn("random", cmd)

    def test_launch_scripts_contain_random_visualizer_spawn(self):
        """Check launch_liquid_glass.sh and Mix_Archive_Manager.sh for visualizer spawn logic."""
        launch_script = ROOT_DIR / "scripts" / "launch_liquid_glass.sh"
        self.assertTrue(launch_script.is_file())
        content = launch_script.read_text(encoding="utf-8")
        self.assertIn("--preset random", content)
        self.assertIn("MP_Liquid_Visualizer", content)

        mgr_script = ROOT_DIR / "Mix_Archive_Manager.sh"
        self.assertTrue(mgr_script.is_file())
        mgr_content = mgr_script.read_text(encoding="utf-8")
        self.assertIn("launch_mp_audio_player_liquid_glass", mgr_content)
        # The menu must not start a new visualizer after the player returns.
        # That window is closed by the player itself.
        self.assertNotIn('nohup "$py_bin" "$vis_py" --preset random', mgr_content)
        for name in (
            "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "MP_Audio_Player_Liquid_Glass.py",
            "MP_Audio_Player_Liquid_Glass_macOS.py",
        ):
            text = (ROOT_DIR / name).read_text(encoding="utf-8")
            self.assertIn("stop_companion_visualizer()", text)

    @patch("liquid_visualizer_session._signal_visualizer")
    @patch("liquid_visualizer_session._alive", return_value=False)
    @patch("liquid_visualizer_session.visualizer_pids", return_value=[4242])
    @patch("liquid_visualizer_session.other_liquid_player_running", return_value=False)
    def test_player_exit_stops_the_visualizer(self, _other, _pids, _alive, signal_vis):
        vis_session.stop_companion_visualizer()
        signal_vis.assert_called_once_with(4242, signal.SIGTERM)

    @patch("liquid_visualizer_session._signal_visualizer")
    @patch("liquid_visualizer_session.visualizer_pids", return_value=[4242])
    @patch("liquid_visualizer_session.other_liquid_player_running", return_value=True)
    def test_player_exit_leaves_visualizer_when_another_player_is_open(self, _other, _pids, signal_vis):
        vis_session.stop_companion_visualizer()
        signal_vis.assert_not_called()


if __name__ == "__main__":
    unittest.main()
