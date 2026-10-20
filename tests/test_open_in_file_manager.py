#!/usr/bin/env python3
"""Files (F) reveals the playing audio file instead of a default folder."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import MP_Audio_Player as player


class TestRevealPath(unittest.TestCase):
    def test_playing_file_wins_over_the_highlighted_row(self):
        with tempfile.TemporaryDirectory() as folder:
            playing = os.path.join(folder, "now playing.flac")
            selected = os.path.join(folder, "other.flac")
            open(playing, "wb").close()
            open(selected, "wb").close()
            chosen = player.choose_file_manager_target(playing, selected)
            self.assertEqual(os.path.normcase(chosen), os.path.normcase(playing))

    def test_highlighted_row_is_used_when_nothing_is_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            selected = os.path.join(folder, "highlighted.flac")
            open(selected, "wb").close()
            chosen = player.choose_file_manager_target("", selected)
            self.assertEqual(os.path.normcase(chosen), os.path.normcase(selected))

    def test_missing_paths_do_not_invent_a_folder(self):
        self.assertIsNone(player.choose_file_manager_target("", r"Z:\no\such\mix.flac"))

    def test_file_uri_and_git_bash_drive_path(self):
        with tempfile.TemporaryDirectory() as folder:
            track = os.path.join(folder, "mix.flac")
            open(track, "wb").close()
            uri = Path(track).as_uri()
            self.assertEqual(
                os.path.normcase(player.choose_file_manager_target(uri)),
                os.path.normcase(track),
            )
        if os.name == "nt":
            normalized = player._normalize_reveal_path("/x/Music/mix.flac")
            self.assertEqual(normalized, r"X:\Music\mix.flac")


class TestRevealCommands(unittest.TestCase):
    def test_windows_quotes_only_the_file_path(self):
        cmd = player.windows_explorer_select_command(r"C:\Music\My Mix.flac")
        self.assertEqual(cmd, 'explorer.exe /select,"C:\\Music\\My Mix.flac"')
        self.assertNotIn('"/select,', cmd)

    def test_windows_plan_selects_the_file(self):
        plan = player.reveal_launch_plan(r"C:\Music\My Mix.flac", "win32", is_file=True)
        self.assertEqual(plan, [("bg", 'explorer.exe /select,"C:\\Music\\My Mix.flac"')])

    def test_macos_reveals_the_file_in_finder(self):
        plan = player.reveal_launch_plan("/Users/dj/Music/My Mix.flac", "darwin", is_file=True)
        self.assertEqual(plan, [("bg", ["open", "-R", "/Users/dj/Music/My Mix.flac"])])

    def test_linux_and_freebsd_select_the_file(self):
        path = "/home/dj/Music/My Mix.flac"
        uri = "file:///home/dj/Music/My%20Mix.flac"
        for platform in ("linux", "freebsd"):
            plan = player.reveal_launch_plan(path, platform, is_file=True)
            commands = [item[1] for item in plan]
            self.assertIn(
                [
                    "dbus-send", "--session", "--type=method_call",
                    "--dest=org.freedesktop.FileManager1",
                    "/org/freedesktop/FileManager1",
                    "org.freedesktop.FileManager1.ShowItems",
                    f"array:string:{uri}", "string:",
                ],
                commands,
            )
            self.assertIn(["dolphin", "--select", path], commands)
            self.assertIn(["nautilus", "--select", path], commands)
            self.assertIn(["nemo", path], commands)
            self.assertIn(["caja", path], commands)
            self.assertTrue(any(cmd[-1] == "/home/dj/Music" for cmd in commands if isinstance(cmd, list)))

    def test_open_uses_shell_select_before_explorer(self):
        with tempfile.TemporaryDirectory(prefix="mix file ") as folder:
            track = os.path.join(folder, "now playing.flac")
            open(track, "wb").close()
            with patch.object(player, "_windows_shell_select", return_value=True) as shell, \
                 patch.object(player, "_run_bg") as run, \
                 patch.object(player.sys, "platform", "win32"):
                self.assertTrue(player.open_in_file_manager(track))
            shell.assert_called_once()
            run.assert_not_called()

    def test_open_falls_back_to_quoted_explorer_command(self):
        with tempfile.TemporaryDirectory(prefix="mix file ") as folder:
            track = os.path.join(folder, "now playing.flac")
            open(track, "wb").close()
            with patch.object(player, "_windows_shell_select", return_value=False), \
                 patch.object(player, "_run_bg", return_value=True) as run, \
                 patch.object(player.sys, "platform", "win32"):
                self.assertTrue(player.open_in_file_manager(track))
            launched = run.call_args.args[0]
            self.assertIsInstance(launched, str)
            self.assertIn('/select,"', launched)
            self.assertIn("now playing.flac", launched)
            self.assertNotIn('"/select,', launched)


if __name__ == "__main__":
    unittest.main()
