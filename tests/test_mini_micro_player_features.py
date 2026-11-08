#!/usr/bin/env python3
"""
Unit tests for MP Audio Player MINI and MICRO modes:
- Scrollbar disabling (-p ScrollBarPosition=0 and in profile)
- No terminal colorscheme escape sequence emitted to parent stdout
- Transparent background (no OSC 11 background overrides)
- High-visibility text colors for clear readability
- KWin rules provisioning for fixed window size / no resize / no maximize
"""

import unittest
import sys
import tempfile
import inspect
from pathlib import Path
from unittest import mock
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player


class TestMiniMicroPlayerFeatures(unittest.TestCase):
    def test_no_colorscheme_escape_to_parent_stdout(self):
        """Verifies that _setup_mini_terminal_appearance never emits OSC 50 ColorScheme to stdout."""
        source = inspect.getsource(MP_Audio_Player._setup_mini_terminal_appearance)
        self.assertNotIn(r"\033]50;ColorScheme=", source)

    def test_konsole_profile_disables_scrollbar(self):
        """Verifies that MP_Mini_Player profile explicitly disables the scrollbar."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_home = Path(tmp_dir)
            k_dir = tmp_home / ".local" / "share" / "konsole"
            k_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(Path, "home", return_value=tmp_home):
                MP_Audio_Player._setup_mini_terminal_appearance()

            prof_file = k_dir / "MP_Mini_Player.profile"
            self.assertTrue(prof_file.exists())
            content = prof_file.read_text(encoding="utf-8")
            self.assertIn("ScrollBarPosition=0", content)

    def test_launch_mini_player_window_passes_scrollbar_disabled(self):
        """Verifies that launch_mini_player_window passes -p ScrollBarPosition=0 to Konsole."""
        source = inspect.getsource(MP_Audio_Player.launch_mini_player_window)
        self.assertIn("ScrollBarPosition=0", source)

    def test_frames_do_not_emit_osc11_background_override(self):
        """Verifies that mini and micro frames do not overwrite window transparency with OSC 11."""
        mini_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_mini_frame)
        micro_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_micro_frame)
        self.assertNotIn(r"\033]11;#", mini_src)
        self.assertNotIn(r"\033]11;#", micro_src)

    def test_frames_enforce_fixed_geometry(self):
        """Verifies that mini and micro frames enforce fixed terminal dimensions (74x14 and 74x7)."""
        mini_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_mini_frame)
        micro_src = inspect.getsource(MP_Audio_Player.TerminalPlayerUI._draw_micro_frame)
        self.assertIn(r"\033[8;", mini_src)
        self.assertIn(r"\033[8;", micro_src)

    def test_kwin_rules_provisioned(self):
        """Verifies that ensure_mini_player_kwin_rules creates fixed-size / no-maximize rules in kwinrulesrc."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_home = Path(tmp_dir)
            cfg_dir = tmp_home / ".config"
            cfg_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(Path, "home", return_value=tmp_home):
                MP_Audio_Player.ensure_mini_player_kwin_rules()

            rc_file = cfg_dir / "kwinrulesrc"
            self.assertTrue(rc_file.exists())
            content = rc_file.read_text(encoding="utf-8")
            self.assertIn("MP Mini Audio Player (Fixed Size)", content)
            self.assertIn("MP Micro Audio Player (Fixed Size)", content)
            self.assertIn("maximizehoriz = false", content)
            self.assertIn("maximizevert = false", content)

    def test_m_from_normal_opens_mini_player_in_new_window(self):
        """Pressing m or M in the full player opens the Mini Player in a new console window."""
        ui = MP_Audio_Player.TerminalPlayerUI(None, None, is_remote=True, ui_size_mode="NORMAL")
        self.assertEqual(ui.ui_size_mode, "NORMAL")
        with mock.patch("MP_Audio_Player.launch_mini_player_window", return_value=True) as launch:
            ui._process_key(b"m")
            launch.assert_called_once()
            self.assertEqual(ui.ui_size_mode, "NORMAL")
            args = launch.call_args[0]
            self.assertEqual(args[0], "MIX_ARCHIVE")
            self.assertFalse(launch.call_args.kwargs.get("micro", False))
            ui._process_key(b"M")
            self.assertEqual(launch.call_count, 2)
            self.assertEqual(ui.ui_size_mode, "NORMAL")
            self.assertIn("new window", ui.notification_msg)

    def test_m_toggles_mini_and_micro_inside_compact_window(self):
        """Inside an already-open Mini or Micro window, M switches between those sizes and resizes the terminal."""
        ui = MP_Audio_Player.TerminalPlayerUI(None, None, is_remote=True, ui_size_mode="MINI")
        with mock.patch("MP_Audio_Player.launch_mini_player_window") as launch, \
             mock.patch("MP_Audio_Player.resize_host_terminal") as resize:
            ui._process_key(b"m")
            launch.assert_not_called()
            self.assertEqual(ui.ui_size_mode, "MICRO")
            resize.assert_called_with(74, 7, "MP Micro Audio Player")
            ui._process_key(b"M")
            launch.assert_not_called()
            self.assertEqual(ui.ui_size_mode, "MINI")
            resize.assert_called_with(74, 14, "MP Mini Audio Player")

    @mock.patch.object(sys, "argv", ["MP_Audio_Player.py", "--mini"])
    @mock.patch("MP_Audio_Player.is_player_daemon_running", return_value=True)
    @mock.patch("MP_Audio_Player.send_ipc_command")
    @mock.patch("MP_Audio_Player.TerminalPlayerUI.run", return_value=None)
    def test_mini_player_attach_does_not_restart_track_or_playlist_in_music_mode(self, mock_ui_run, mock_ipc, mock_daemon_run):
        """When Mini Player attaches to an active daemon in MUSIC mode, it must NOT send load_playlist(play=True) or disrupt playback."""
        mock_ipc.side_effect = lambda cmd, **kwargs: {
            "status": "ok",
            "data": {
                "running": True,
                "state": "playing",
                "mode": "MUSIC",
                "path": "/music/song1.flac",
                "title": "song1.flac",
                "position_sec": 42.0,
                "duration_sec": 240.0
            }
        } if cmd == "status" else {"status": "ok"}
        
        with self.assertRaises(SystemExit) as cm:
            MP_Audio_Player.main()
        self.assertEqual(cm.exception.code, 0)
        
        # Verify that send_ipc_command was never called with load_playlist or play
        for call in mock_ipc.call_args_list:
            cmd = call[0][0] if call[0] else call[1].get("cmd")
            self.assertNotEqual(cmd, "load_playlist", "Connecting Mini Player must NOT send load_playlist")
            self.assertNotEqual(cmd, "play", "Connecting Mini Player must NOT send play when track is already playing")

    @mock.patch.object(sys, "argv", ["MP_Audio_Player.py", "--mini"])
    @mock.patch("MP_Audio_Player.is_player_daemon_running", return_value=True)
    @mock.patch("MP_Audio_Player.send_ipc_command")
    @mock.patch("MP_Audio_Player.TerminalPlayerUI.run", return_value=None)
    def test_mini_player_attach_does_not_restart_track_or_playlist_in_mix_mode(self, mock_ui_run, mock_ipc, mock_daemon_run):
        """When Mini Player attaches to an active daemon in MIX_ARCHIVE mode, it must NOT restart track or playlist."""
        mock_ipc.side_effect = lambda cmd, **kwargs: {
            "status": "ok",
            "data": {
                "running": True,
                "state": "playing",
                "mode": "MIX_ARCHIVE",
                "path": "/mixes/episode_01.flac",
                "title": "episode_01.flac",
                "position_sec": 512.0,
                "duration_sec": 7200.0
            }
        } if cmd == "status" else {"status": "ok"}
        
        with self.assertRaises(SystemExit) as cm:
            MP_Audio_Player.main()
        self.assertEqual(cm.exception.code, 0)
        
        for call in mock_ipc.call_args_list:
            cmd = call[0][0] if call[0] else call[1].get("cmd")
            self.assertNotEqual(cmd, "load_playlist", "Connecting Mini Player must NOT send load_playlist")
            self.assertNotEqual(cmd, "play", "Connecting Mini Player must NOT send play when track is already playing")

    @mock.patch.object(sys, "argv", ["MP_Audio_Player.py", "--mini", "--new-window"])
    @mock.patch("MP_Audio_Player.is_player_daemon_running", return_value=True)
    @mock.patch("MP_Audio_Player.send_ipc_command")
    @mock.patch("MP_Audio_Player.launch_mini_player_window", return_value=True)
    def test_new_window_inherits_daemon_music_mode(self, mock_launch_mini, mock_ipc, mock_daemon_run):
        """--new-window should inspect the running daemon and pass the active mode to launch_mini_player_window."""
        mock_ipc.return_value = {
            "status": "ok",
            "data": {
                "running": True,
                "state": "playing",
                "mode": "MUSIC",
                "path": "/music/song.flac"
            }
        }
        with self.assertRaises(SystemExit) as cm:
            MP_Audio_Player.main()
        self.assertEqual(cm.exception.code, 0)
        mock_launch_mini.assert_called_once()
        self.assertEqual(mock_launch_mini.call_args[0][0], "MUSIC")


if __name__ == "__main__":
    unittest.main()
