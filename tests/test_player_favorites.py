#!/usr/bin/env python3
"""Favorites playlist: mark a mix or track, then open it from the key or the button."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import MP_Audio_Player as player


def _track(name, path):
    return {"name": name, "path": path, "ext": "FLAC", "size_mb": 1.0}


class _ListScanner:
    def __init__(self, mixes):
        self.mixes = list(mixes)
        self.base_dir = Path("/tmp/mix-archive")

    def get_mixes(self, query=""):
        if not query:
            return self.mixes
        q = query.lower()
        return [track for track in self.mixes if q in track["name"].lower() or q in track["path"].lower()]

    def get_latest_mix(self):
        return self.mixes[0] if self.mixes else None


def _ui(tracks=None, mode="MIX_ARCHIVE"):
    ui = player.TerminalPlayerUI.__new__(player.TerminalPlayerUI)
    ui.mode = mode
    ui.folder_name = "ALL"
    ui.keep_library = False
    ui._user_library_mode = None
    ui.is_remote = False
    ui.engine = MagicMock()
    ui.engine.current_track = None
    ui.engine.playlist = []
    ui.engine.current_index = 0
    ui.engine.get_status_dict.return_value = {"path": "", "title": "", "mode": mode, "state": "stopped"}
    ui.scanner = _ListScanner(tracks or [_track("Mix A.flac", "/mixes/a.flac"), _track("Track B.flac", "/music/b.flac")])
    ui.export_mode = False
    ui.eq_naming_mode = False
    ui.search_mode = False
    ui.search_query = ""
    ui.selected_row = 0
    ui.scroll_offset = 0
    ui.cached_status = {"mode": mode, "title": "Mix A", "path": ""}
    ui.notification_msg = ""
    ui.notification_time = 0.0
    ui.equalizer_hud_active = False
    ui.inspector_hud_active = False
    ui.ui_size_mode = "NORMAL"
    ui._playlist_clear_armed = False
    ui._inbuf = b""
    ui._reset_click_targets()
    return ui


class FavoritesStoreTests(unittest.TestCase):
    def test_toggle_saves_and_removes_without_touching_the_audio_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "favorites.json"
            audio = Path(tmp) / "Mix A.flac"
            audio.write_bytes(b"RIFF")
            store = player.FavoritesStore(path)
            added = store.toggle(_track("Mix A.flac", str(audio)))
            self.assertTrue(added)
            self.assertTrue(store.is_favorite(str(audio)))
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["tracks"][0]["name"], "Mix A.flac")
            self.assertIn("#PLAYLIST:MP Favorites", path.with_suffix(".m3u8").read_text(encoding="utf-8"))
            self.assertTrue(audio.is_file())
            self.assertFalse(store.toggle(_track("Mix A.flac", str(audio))))
            self.assertEqual(store.tracks(), [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["tracks"], [])

    def test_duplicate_paths_load_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "favorites.json"
            path.write_text(
                json.dumps({"tracks": [
                    {"name": "Mix A.flac", "path": "/mixes/a.flac"},
                    {"name": "Mix A copy", "path": "/mixes/a.flac"},
                ]}),
                encoding="utf-8",
            )
            store = player.FavoritesStore(path)
            self.assertEqual([track["name"] for track in store.tracks()], ["Mix A.flac"])


class FavoritesPlayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = player.FavoritesStore(Path(self.tmp.name) / "favorites.json")
        self.ui = _ui()
        self.ui.favorites = self.store

    def tearDown(self):
        self.tmp.cleanup()

    def test_h_marks_the_selected_mix_and_h_again_removes_it(self):
        self.ui._process_key(b"h")
        self.assertTrue(self.store.is_favorite("/mixes/a.flac"))
        self.assertIn("Added to Favorites", self.ui.notification_msg)
        self.assertEqual(self.ui.mode, "MIX_ARCHIVE")
        self.ui._process_key(b"H")
        self.assertFalse(self.store.is_favorite("/mixes/a.flac"))
        self.assertIn("Removed from Favorites", self.ui.notification_msg)

    def test_h_marks_a_music_track(self):
        self.ui.mode = "MUSIC"
        self.ui.selected_row = 1
        self.ui._process_key(b"h")
        saved = self.store.tracks()
        self.assertEqual(saved[0]["path"], "/music/b.flac")
        self.assertEqual(saved[0]["source"], "MUSIC")

    def test_3_loads_the_favorites_playlist(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.store.toggle(_track("Track B.flac", "/music/b.flac"))
        self.ui.engine.current_track = {"path": "/mixes/a.flac"}
        self.ui._process_key(b"3")
        self.assertEqual(self.ui.mode, "FAVORITES")
        self.assertEqual(self.ui._user_library_mode, "FAVORITES")
        self.assertIsInstance(self.ui.scanner, player.FavoritesScanner)
        self.assertEqual([track["path"] for track in self.ui.engine.playlist], ["/mixes/a.flac", "/music/b.flac"])
        self.assertEqual(self.ui.engine.mode, "FAVORITES")
        self.assertEqual(self.ui.engine.current_index, 0)
        self.assertIn("Loaded Favorites playlist — 2 saved", self.ui.notification_msg)

    def test_empty_favorites_still_opens_the_playlist(self):
        self.ui._process_key(b"3")
        self.assertEqual(self.ui.mode, "FAVORITES")
        self.assertEqual(self.ui.scanner.mixes, [])
        self.assertIn("empty", self.ui.notification_msg)

    def test_remote_load_asks_the_daemon_to_read_the_playlist(self):
        sent = []
        self.ui.is_remote = True
        self.ui._send_cmd = lambda cmd, **kwargs: sent.append((cmd, kwargs))
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui._process_key(b"3")
        self.assertEqual(sent, [("load_playlist", {"mode": "FAVORITES", "play": False})])
        self.assertEqual(self.ui.cached_status["mode"], "FAVORITES")

    def test_clicking_the_favorites_button_loads_the_playlist(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.ui._favorites_button_row = 12
        self.ui._favorites_button_span = (3, 18)
        self.ui._favorites_button_whole_row = True
        self.ui._process_key(b"\x1b[<0;40;12M")
        self.assertEqual(self.ui.mode, "FAVORITES")
        self.assertEqual(len(self.ui.engine.playlist), 1)

    def test_clicking_the_star_marks_that_row(self):
        self.ui._playlist_star_rows = {20: 1}
        self.ui._playlist_star_col = 14
        self.ui._process_key(b"\x1b[<0;14;20M")
        self.assertEqual(self.ui.selected_row, 1)
        self.assertTrue(self.store.is_favorite("/music/b.flac"))

    def test_search_keeps_the_favorites_keys(self):
        self.ui.search_mode = True
        self.ui._process_key(b"3")
        self.ui._process_key(b"h")
        self.assertEqual(self.ui.search_query, "3h")
        self.assertEqual(self.store.tracks(), [])
        self.assertEqual(self.ui.mode, "MIX_ARCHIVE")

    def test_equalizer_keys_do_not_change_favorites(self):
        self.ui.equalizer_hud_active = True
        self.ui.eq_manager = MagicMock()
        self.ui.eq_manager.current_bands = [0.0] * 10
        self.ui.eq_selected_band = 3
        self.ui.eq_manager.cycle_preset.return_value = "Trance"
        self.ui._process_key(b"3")
        self.ui._process_key(b"h")
        self.assertEqual(self.store.tracks(), [])
        self.assertEqual(self.ui.mode, "MIX_ARCHIVE")
        self.assertEqual(self.ui.eq_selected_band, 2)

    def test_removing_a_favorite_updates_the_open_playlist(self):
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        self.store.toggle(_track("Track B.flac", "/music/b.flac"))
        self.ui._process_key(b"3")
        self.ui.selected_row = 0
        self.ui._process_key(b"h")
        self.assertEqual([track["path"] for track in self.ui.scanner.mixes], ["/music/b.flac"])
        self.assertEqual([track["path"] for track in self.ui.engine.playlist], ["/music/b.flac"])

    def test_button_line_is_a_visible_favorites_control(self):
        lines = []
        self.ui._append_favorites_button(lines, 100, whole_row=True)
        self.assertEqual(self.ui._favorites_button_row, 1)
        self.assertTrue(self.ui._favorites_button_whole_row)
        visible = lines[0]
        self.assertIn("FAVORITES", visible)
        self.assertIn("[3]", visible)
        self.assertIn("[H]", visible)
        self.assertIn("38;2;255;196;0", visible)
        self.assertNotIn("48;2;", visible)

    def test_full_frame_draws_the_favorites_button(self):
        engine = player.AudioEngine([], auto_bluetooth=False)
        scanner = _ListScanner([_track("Mix A.flac", "/mixes/a.flac")])
        ui = player.TerminalPlayerUI(engine, scanner, is_remote=False)
        ui.favorites = self.store
        self.store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            ui._draw_frame()
        drawn = buf.getvalue()
        self.assertIn("FAVORITES", drawn)
        self.assertIn("[3]", drawn)
        self.assertIn("[H]", drawn)
        self.assertGreater(ui._favorites_button_row, 4)
        engine.stop_playback()


class FavoritesDaemonTests(unittest.TestCase):
    def test_daemon_loads_the_saved_favorites_playlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "favorites.json"
            store = player.FavoritesStore(path)
            store.toggle(_track("Mix A.flac", "/mixes/a.flac"))
            engine = MagicMock()
            engine.current_track = {"path": "/mixes/a.flac"}
            engine.playlist = []
            with patch.object(player, "FAVORITES_FILE", path):
                loaded = player.load_engine_playlist(engine, mode="FAVORITES", play=False)
            self.assertEqual(loaded, 1)
            self.assertEqual(engine.mode, "FAVORITES")
            self.assertEqual(engine.playlist[0]["path"], "/mixes/a.flac")
            self.assertEqual(engine.current_index, 0)


if __name__ == "__main__":
    unittest.main()
