#!/usr/bin/env python3
"""G in the MP Liquid Player opens MP Gui and the shortcut row lists it."""

import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import MP_Audio_Player as player

ANSI = re.compile(r"\033\[[0-9;]*m")


def _visible(line: str, width: int) -> str:
    return ANSI.sub("", line)[: max(1, width - 1)]


def _ui():
    scanner = MagicMock()
    scanner.get_mixes.return_value = []
    scanner.base_dir = ROOT
    return player.TerminalPlayerUI(engine=None, scanner=scanner, ui_size_mode="NORMAL", is_remote=True)


def _status():
    return {
        "title": "Tone",
        "path": "/tmp/tone.flac",
        "state": "stopped",
        "index": 0,
        "position_fmt": "00:00",
        "duration_fmt": "00:00",
        "progress_pct": 0,
        "volume": 85,
        "pitch_percent": 0,
        "levels": [0.0] * 24,
        "peaks": [0.0] * 24,
        "levels_left": [0.0] * 24,
        "levels_right": [0.0] * 24,
        "peaks_left": [0.0] * 24,
        "peaks_right": [0.0] * 24,
        "shuffle": False,
        "repeat": "all",
        "muted": False,
    }


class TestLiquidPlayerMpGuiShortcut(unittest.TestCase):
    def test_g_opens_mp_gui_only_inside_liquid_player(self):
        ui = _ui()
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch.object(player, "launch_mp_gui", return_value=True) as launch, \
             patch.object(ui, "_generate_selected_spek") as spek:
            ui._process_key(b"g")
            ui._process_key(b"G")
        self.assertEqual(launch.call_count, 2)
        launch.assert_called_with(base_dir=ROOT)
        spek.assert_not_called()
        self.assertIn("Opened MP Gui", ui.notification_msg)

        ui.notification_msg = ""
        with patch.dict(os.environ, {}, clear=False), \
             patch.object(player, "launch_mp_gui") as launch, \
             patch.object(ui, "_generate_selected_spek") as spek:
            os.environ.pop("MP_LIQUID_GLASS", None)
            ui._process_key(b"g")
        launch.assert_not_called()
        spek.assert_called_once()

    def test_search_and_inspector_do_not_open_mp_gui(self):
        ui = _ui()
        ui.search_mode = True
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch.object(player, "launch_mp_gui") as launch:
            ui._process_key(b"g")
        launch.assert_not_called()
        self.assertEqual(ui.search_query, "g")

        ui = _ui()
        ui.inspector_hud_active = True
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch.object(player, "launch_mp_gui") as launch, \
             patch.object(ui, "_generate_selected_spek", return_value=None) as spek:
            ui._process_key(b"g")
        launch.assert_not_called()
        spek.assert_called_once()

    def test_shortcut_row_lists_mp_gui_beside_other_keys(self):
        ui = _ui()
        ui._get_status = lambda: _status()
        cases = (
            ("NORMAL", "MIX_ARCHIVE", 120, 40, "G MP Gui"),
            ("NORMAL", "MUSIC", 120, 40, "[G] MP Gui"),
            ("MINI", "MIX_ARCHIVE", 74, 14, "[G] MP Gui"),
            ("MICRO", "MIX_ARCHIVE", 74, 7, "[G] MP Gui"),
        )
        for size, library, width, height, label in cases:
            captured = []
            ui.ui_size_mode = size
            ui.mode = library
            with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
                 patch.object(player, "_present_frame", side_effect=lambda lines, w, h: captured.extend(lines)), \
                 patch.object(player, "_win_visible_size", return_value=(width, height)):
                ui._draw_frame()
            visible = [_visible(line, width) for line in captured[:height]]
            self.assertTrue(
                any(label in line for line in visible),
                f"{size} {library} did not show {label!r} on a visible row: {visible[-4:]}",
            )

        captured = []
        ui.ui_size_mode = "NORMAL"
        ui.mode = "MIX_ARCHIVE"
        with patch.dict(os.environ, {}, clear=False), \
             patch.object(player, "_present_frame", side_effect=lambda lines, w, h: captured.extend(lines)), \
             patch.object(player, "_win_visible_size", return_value=(120, 40)):
            os.environ.pop("MP_LIQUID_GLASS", None)
            ui._draw_frame()
        bottom = _visible(captured[-1], 120)
        self.assertIn("G Spek", bottom)
        self.assertNotIn("MP Gui", bottom)

    def test_launch_mp_gui_focuses_an_open_window(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return MagicMock(returncode=0)

        with patch.object(player.subprocess, "run", side_effect=fake_run), \
             patch.object(player.subprocess, "Popen") as popen, \
             patch.object(player.shutil, "which", return_value="/usr/bin/wmctrl"):
            self.assertTrue(player.launch_mp_gui(base_dir=ROOT))
        popen.assert_not_called()
        self.assertEqual(calls[0][0], "pgrep")
        self.assertEqual(calls[1][:2], ["/usr/bin/wmctrl", "-a"])
        self.assertIn("MP Mix Manager (Liquid Glass", calls[1][2])

    def test_launch_mp_gui_starts_when_only_the_metal_host_is_running(self):
        def fake_run(cmd, **kwargs):
            cmd = list(cmd)
            if cmd[:2] == ["pgrep", "-fl"]:
                return MagicMock(
                    returncode=0,
                    stdout="24253 python MP_Audio_Player_Liquid_Glass_macOS.py --manager\n",
                )
            return MagicMock(returncode=0, stdout="")

        with patch.object(player.subprocess, "run", side_effect=fake_run), \
             patch.object(player.subprocess, "Popen", return_value=MagicMock(pid=4321)) as popen, \
             patch.object(player.shutil, "which", return_value=None):
            self.assertTrue(player.launch_mp_gui(base_dir=ROOT))
        popen.assert_called_once()
        cmd = popen.call_args.args[0]
        self.assertTrue(str(cmd[1]).endswith("MP_Gui.sh"))

    def test_launch_mp_gui_does_not_stack_a_windowed_host_without_wmctrl(self):
        def fake_run(cmd, **kwargs):
            cmd = list(cmd)
            if cmd[:2] == ["pgrep", "-fl"]:
                return MagicMock(
                    returncode=0,
                    stdout="77 python MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py --manager\n",
                )
            return MagicMock(returncode=0, stdout="")

        with patch.object(player.subprocess, "run", side_effect=fake_run), \
             patch.object(player.subprocess, "Popen") as popen, \
             patch.object(player.shutil, "which", return_value=None):
            self.assertTrue(player.launch_mp_gui(base_dir=ROOT))
        popen.assert_not_called()

    def test_launch_mp_gui_starts_mp_gui_sh_without_changing_theme(self):
        with patch.object(player.subprocess, "run", return_value=MagicMock(returncode=1)), \
             patch.object(player.subprocess, "Popen", return_value=MagicMock(pid=4321)) as popen:
            self.assertTrue(player.launch_mp_gui(base_dir=ROOT))
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[0], "bash")
        self.assertTrue(str(cmd[1]).endswith("MP_Gui.sh"))
        self.assertEqual(cmd[2], "--keep-theme")
        self.assertTrue(popen.call_args.kwargs.get("start_new_session"))

    def test_launch_mp_gui_finds_the_script_beside_the_player(self):
        with patch.object(player.subprocess, "run", return_value=MagicMock(returncode=1)), \
             patch.object(player.subprocess, "Popen", return_value=MagicMock(pid=4321)) as popen:
            self.assertTrue(player.launch_mp_gui(base_dir=Path("/tmp/not-the-repo")))
        cmd = popen.call_args.args[0]
        self.assertEqual(Path(cmd[1]).resolve(), (ROOT / "MP_Gui.sh").resolve())

    def test_launch_mp_gui_reports_a_missing_launcher(self):
        with patch.object(Path, "is_file", return_value=False), \
             patch.object(player.subprocess, "run", return_value=MagicMock(returncode=1)), \
             patch.object(player.subprocess, "Popen") as popen:
            self.assertFalse(player.launch_mp_gui(base_dir=ROOT))
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
