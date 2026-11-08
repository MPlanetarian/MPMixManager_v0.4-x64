#!/usr/bin/env python3
"""Switch MP Audio Player between Mix Archive and Music playlists."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import MP_Audio_Player as player


def _ui(mode="MIX_ARCHIVE", remote=False):
    ui = player.TerminalPlayerUI.__new__(player.TerminalPlayerUI)
    ui.mode = mode
    ui.folder_name = "ALL"
    ui.keep_library = mode == "MUSIC"
    ui._user_library_mode = None
    ui.is_remote = remote
    ui.engine = None
    ui.scanner = MagicMock()
    ui.scanner.base_dir = Path("/tmp/mix-archive")
    ui.scanner.mixes = [{"name": "Current Mix", "path": "/mixes/current.flac"}]
    ui.export_mode = False
    ui.eq_naming_mode = False
    ui.search_mode = False
    ui.search_query = "stale"
    ui.selected_row = 3
    ui.scroll_offset = 1
    ui.cached_status = {"mode": mode, "title": "Current"}
    ui.notification_msg = ""
    ui.notification_time = 0.0
    ui.equalizer_hud_active = False
    ui.inspector_hud_active = False
    ui.ui_size_mode = "NORMAL"
    return ui


class MusicFolderPlaylistLoadTests(unittest.TestCase):
    def test_named_folder_does_not_load_the_combined_playlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            playlists = root / "PLAYLISTS_GENERATED"
            playlists.mkdir()
            (playlists / "DJ_Tracks_ALL_MUSIC_FOLDERS.json").write_text(
                '[{"name":"Only DATAMAC1.mp3","path":"/music/DATAMAC1/a.mp3","folder":"DATAMAC1"}]',
                encoding="utf-8",
            )
            (root / "DATAMAC3").mkdir()
            previous = os.getcwd()
            os.chdir(root)
            try:
                with patch.object(player, "get_base_dir", return_value=root):
                    missing = player.MusicFolderPlaylistScanner("DATAMAC3")
                    self.assertEqual(missing.mixes, [])
                    self.assertEqual(missing.folder_name, "DATAMAC3")
                    (playlists / "DJ_Tracks_DATAMAC3.json").write_text(
                        '[{"name":"Cabin Fever.mp3","path":"/music/DATAMAC3/cabin.mp3","folder":"DATAMAC3"}]',
                        encoding="utf-8",
                    )
                    loaded = player.MusicFolderPlaylistScanner("DATAMAC3")
            finally:
                os.chdir(previous)
            self.assertEqual([track["name"] for track in loaded.mixes], ["Cabin Fever.mp3"])
            self.assertEqual(loaded.folder_name, "DATAMAC3")


class LibraryModeSwitchTests(unittest.TestCase):
    def test_music_key_reloads_existing_playlist(self):
        ui = _ui()
        sent = []
        ui.is_remote = True
        ui._send_cmd = lambda cmd, **kwargs: sent.append((cmd, kwargs))
        with tempfile.NamedTemporaryFile(suffix=".json") as playlist:
            music = MagicMock()
            music.mixes = [
                {"name": "Track A", "path": "/music/a.flac"},
                {"name": "Track B", "path": "/music/b.flac"},
            ]
            music.playlist_path = Path(playlist.name)
            music.folder_name = "ALL"
            with patch.object(player, "MusicFolderPlaylistScanner", return_value=music):
                ui._process_key(b"2")
        self.assertEqual(ui.mode, "MUSIC")
        self.assertIs(ui.scanner, music)
        self.assertTrue(ui.keep_library)
        self.assertEqual(ui._user_library_mode, "MUSIC")
        self.assertEqual(ui.selected_row, 0)
        self.assertEqual(ui.search_query, "")
        self.assertEqual(sent, [("load_playlist", {
            "mode": "MUSIC",
            "play": False,
            "folder_name": "ALL",
            "playlist_path": playlist.name,
        })])
        self.assertIn("Loaded Music playlist — 2 tracks", ui.notification_msg)
        self.assertEqual(ui.cached_status["mode"], "MUSIC")

    def test_missing_music_playlist_names_menu_options(self):
        ui = _ui()
        music = MagicMock()
        music.mixes = []
        music.playlist_path = None
        with patch.object(player, "MusicFolderPlaylistScanner", return_value=music):
            ui._process_key(b"2")
        self.assertEqual(ui.mode, "MIX_ARCHIVE")
        self.assertIsNot(ui.scanner, music)
        self.assertIn("option 2", ui.notification_msg)
        self.assertIn("option 13", ui.notification_msg)

    def test_mix_archive_key_reloads_engine_playlist(self):
        ui = _ui(mode="MUSIC")
        ui.engine = MagicMock()
        ui.engine.current_track = {"path": "/mixes/second.flac"}
        archive = MagicMock()
        archive.mixes = [
            {"name": "First", "path": "/mixes/first.flac"},
            {"name": "Second", "path": "/mixes/second.flac"},
        ]
        archive.base_dir = Path("/tmp/mix-archive")
        with patch.object(player, "MixArchiveScanner", return_value=archive):
            ui._process_key(b"1")
        self.assertEqual(ui.mode, "MIX_ARCHIVE")
        self.assertIs(ui.scanner, archive)
        self.assertFalse(ui.keep_library)
        self.assertEqual(ui.engine.mode, "MIX_ARCHIVE")
        self.assertEqual(ui.engine.playlist, archive.mixes)
        self.assertEqual(ui.engine.current_index, 1)
        self.assertIn("Loaded Mix Archive playlist — 2 mixes", ui.notification_msg)

    def test_missing_mix_archive_playlist_names_menu_options(self):
        ui = _ui(mode="MUSIC")
        archive = MagicMock()
        archive.mixes = []
        with patch.object(player, "MixArchiveScanner", return_value=archive):
            ui._process_key(b"1")
        self.assertEqual(ui.mode, "MUSIC")
        self.assertIsNot(ui.scanner, archive)
        self.assertIn("option 13", ui.notification_msg)
        self.assertIn("option 2", ui.notification_msg)

    def test_user_choice_ignores_stale_daemon_mode(self):
        ui = _ui()
        with tempfile.NamedTemporaryFile(suffix=".json") as playlist:
            music = MagicMock(spec=player.MusicFolderPlaylistScanner)
            music.mixes = [{"name": "Track A", "path": "/music/a.flac"}]
            music.playlist_path = Path(playlist.name)
            music.folder_name = "ALL"
            with patch.object(player, "MusicFolderPlaylistScanner", return_value=music):
                ui._switch_library_mode("MUSIC")
            with patch.object(player, "MixArchiveScanner", return_value="should-not-load") as archive:
                ui._sync_mode_scanner("MIX_ARCHIVE")
            archive.assert_not_called()
        self.assertEqual(ui.mode, "MUSIC")
        self.assertIs(ui.scanner, music)

    def test_search_keeps_digit_keys(self):
        ui = _ui()
        ui.search_mode = True
        ui.search_query = ""
        with patch.object(player, "MusicFolderPlaylistScanner") as music:
            ui._process_key(b"2")
        music.assert_not_called()
        self.assertEqual(ui.search_query, "2")
        self.assertEqual(ui.mode, "MIX_ARCHIVE")


if __name__ == "__main__":
    unittest.main()
