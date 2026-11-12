"""Tests for the Web Companion library mode, mini playlist, theming and autoplay.

These cover the behaviour added on top of the streaming base:

  * a five-track mini playlist that also reports the full library count
  * a Mix / Music library switch mirroring the MP Audio Player [1]/[2] modes
  * a Theme button backed by /api/themes and /api/set_theme
  * autoplay that arms the stream at startup without opening a local device
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import mix_web_companion as companion


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _touch_audio(path: Path, payload: bytes = b"\x00" * 64) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class CompanionTestBase(unittest.TestCase):
    """Redirect every persisted path into a temporary home."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.config = self.home / ".config" / "mix-manager"

        self._patches = [
            patch.object(companion, "CONFIG_DIR", self.config),
            patch.object(companion, "WEB_MODE_FILE", self.config / "web_companion_mode"),
            patch.object(companion, "WEB_THEME_FILE", self.config / "web_companion_theme"),
            patch.object(companion, "MUSIC_FOLDERS_FILE", self.config / "music_folders.json"),
            patch.object(companion, "PLAYLIST_DIR", self.config / "playlists"),
            patch.object(companion, "VOLUME_FILE", self.config / "web_companion_stream.json"),
            patch.object(companion, "RESUME_FILE", self.config / "playback_resume.json"),
            patch.object(companion, "FAVORITES_FILE", self.config / "favorites.json"),
        ]
        for p in self._patches:
            p.start()
        companion.invalidate_queue_cache()
        companion._queue_source_state.update({"fallback": False, "detail": ""})
        self._reset_autoplay()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        companion.invalidate_queue_cache()
        self._tmp.cleanup()

    def _reset_autoplay(self):
        companion._autoplay_done.clear()
        companion._autoplay_result.clear()
        companion._autoplay_result.update({"status": "pending", "detail": ""})

    def use_archive(self, files):
        """Point the mix archive at the given file list."""
        self._archive_files = [str(Path(f)) for f in files]
        self._archive_patch = patch.object(
            companion, "scan_archive_files", side_effect=lambda: list(self._archive_files)
        )
        self._archive_patch.start()
        self.addCleanup(self._archive_patch.stop)
        companion.invalidate_queue_cache()

    def use_music(self, files):
        self._music_files = [str(Path(f)) for f in files]
        self._music_patch = patch.object(
            companion, "scan_music_files", side_effect=lambda: list(self._music_files)
        )
        self._music_patch.start()
        self.addCleanup(self._music_patch.stop)
        companion.invalidate_queue_cache()

    def use_favorites(self, files):
        """Write a favorites.json the way the MP Audio Player stores it."""
        tracks = [{"name": Path(f).name, "path": str(Path(f)), "added": 1.0} for f in files]
        _write(
            self.config / "favorites.json",
            json.dumps({"version": 1, "name": "Favorites", "tracks": tracks}),
        )
        companion.invalidate_queue_cache()


class TestLibraryMode(CompanionTestBase):
    def test_default_mode_is_mix_archive(self):
        self.assertEqual(companion.get_library_mode(), companion.LIBRARY_MODE_MIX)

    def test_mode_persists_to_disk(self):
        chosen = companion.set_library_mode("MUSIC")
        self.assertEqual(chosen, companion.LIBRARY_MODE_MUSIC)
        self.assertEqual(
            (self.config / "web_companion_mode").read_text(encoding="utf-8").strip(),
            companion.LIBRARY_MODE_MUSIC,
        )
        self.assertEqual(companion.get_library_mode(), companion.LIBRARY_MODE_MUSIC)

    def test_mode_accepts_short_aliases(self):
        self.assertEqual(companion.set_library_mode("mix"), companion.LIBRARY_MODE_MIX)
        self.assertEqual(companion.set_library_mode("tracks"), companion.LIBRARY_MODE_MUSIC)
        self.assertEqual(companion.set_library_mode("faves"), companion.LIBRARY_MODE_FAVORITES)
        self.assertEqual(companion.set_library_mode("favourite"), companion.LIBRARY_MODE_FAVORITES)

    def test_all_three_modes_are_advertised(self):
        self.assertEqual(
            list(companion.MODE_LABELS),
            ["MIX_ARCHIVE", "MUSIC", "FAVORITES"],
        )
        self.assertIn("Favorites", companion.MODE_LABELS.values())

    def test_favorites_mode_streams_the_saved_playlist(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        fav = _touch_audio(self.home / "MUSIC" / "fav_song.mp3")
        self.use_archive([mix])
        self.use_music([])
        self.use_favorites([fav])
        companion.set_library_mode("FAVORITES")
        self.assertEqual(companion.build_stream_queue(), [str(fav)])

    def test_favorites_keep_the_order_the_player_saved(self):
        first = _touch_audio(self.home / "MUSIC" / "first.mp3")
        second = _touch_audio(self.home / "MUSIC" / "second.mp3")
        self.use_archive([])
        self.use_favorites([second, first])
        companion.set_library_mode("FAVORITES")
        self.assertEqual(companion.build_stream_queue(), [str(second), str(first)])

    def test_favorites_deduplicate_paths(self):
        fav = _touch_audio(self.home / "MUSIC" / "fav.mp3")
        _write(
            self.config / "favorites.json",
            json.dumps({"tracks": [{"path": str(fav)}, {"path": str(fav)}]}),
        )
        companion.invalidate_queue_cache()
        self.assertEqual(companion.scan_favorite_files(), [str(fav)])

    def test_favorites_skip_files_that_no_longer_exist(self):
        live = _touch_audio(self.home / "MUSIC" / "live.mp3")
        _write(
            self.config / "favorites.json",
            json.dumps({"tracks": [
                {"path": str(self.home / "MUSIC" / "gone.mp3")},
                {"path": str(live)},
            ]}),
        )
        companion.invalidate_queue_cache()
        self.assertEqual(companion.scan_favorite_files(), [str(live)])

    def test_favorites_fall_back_to_the_m3u8_mirror(self):
        """favorites.m3u8 is written beside favorites.json by the player."""
        fav = _touch_audio(self.home / "MUSIC" / "fav.mp3")
        _write(
            self.config / "favorites.m3u8",
            "#EXTM3U\n#PLAYLIST:MP Favorites\n#EXTINF:-1,fav.mp3\n" + str(fav) + "\n",
        )
        companion.invalidate_queue_cache()
        self.assertEqual(companion.scan_favorite_files(), [str(fav)])

    def test_empty_favorites_is_empty_not_borrowed_from_the_archive(self):
        """An empty Favorites is a normal state; it must not stream the archive."""
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        self.use_archive([mix])
        self.use_music([])
        self.use_favorites([])
        companion.set_library_mode("FAVORITES")

        self.assertEqual(companion.build_stream_queue(), [])
        data = companion.get_mini_playlist()
        self.assertEqual(data["items"], [])
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["mode"], "FAVORITES")
        self.assertFalse(data["library_fallback"])
        self.assertIn("favorites", data["library_detail"].lower())

    def test_favorites_mode_reports_its_label(self):
        fav = _touch_audio(self.home / "MUSIC" / "fav.mp3")
        self.use_archive([])
        self.use_favorites([fav])
        companion.set_library_mode("FAVORITES")
        data = companion.get_mini_playlist()
        self.assertEqual(data["mode_label"], "Favorites")
        self.assertEqual(len(data["items"]), 1)

    def test_unknown_mode_is_rejected(self):
        self.assertIsNone(companion.set_library_mode("bogus"))

    def test_mix_mode_streams_the_archive(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        self.use_archive([mix])
        self.use_music([])
        companion.set_library_mode("MIX_ARCHIVE")
        self.assertEqual(companion.build_stream_queue(), [str(mix)])

    def test_music_mode_streams_the_music_library(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        track = _touch_audio(self.home / "MUSIC" / "song.mp3")
        self.use_archive([mix])
        self.use_music([track])
        companion.set_library_mode("MUSIC")
        self.assertEqual(companion.build_stream_queue(), [str(track)])

    def test_offline_music_library_falls_back_to_archive_and_reports_it(self):
        """An unmounted SMB share must not leave the phone with nothing to play."""
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        self.use_archive([mix])
        self.use_music([])
        companion.set_library_mode("MUSIC")

        queue = companion.build_stream_queue()
        self.assertEqual(queue, [str(mix)])
        self.assertTrue(companion._queue_source_state["fallback"])
        self.assertIn("offline", companion._queue_source_state["detail"])
        self.assertTrue(companion.get_mini_playlist()["library_fallback"])

    def test_switching_library_resets_to_first_track(self):
        first = _touch_audio(self.home / "MIX_ARCHIVE" / "a.flac")
        second = _touch_audio(self.home / "MIX_ARCHIVE" / "b.flac")
        track = _touch_audio(self.home / "MUSIC" / "song.mp3")
        self.use_archive([first, second])
        self.use_music([track])

        companion.set_library_mode("MIX_ARCHIVE")
        companion.control_player("select_index", {"index": ["1"]})
        self.assertEqual(companion.load_stream_session()["index"], 1)

        companion.set_library_mode("MUSIC")
        state = companion.load_stream_session()
        self.assertEqual(state["index"], 0)
        self.assertEqual(state["position_sec"], 0.0)


class TestMiniPlaylist(CompanionTestBase):
    def test_returns_five_items_and_full_count(self):
        files = [_touch_audio(self.home / "MIX_ARCHIVE" / f"mix_{i}.flac") for i in range(9)]
        self.use_archive(files)
        companion.set_library_mode("MIX_ARCHIVE")

        data = companion.get_mini_playlist(limit=companion.MINI_PLAYLIST_SIZE)
        self.assertEqual(companion.MINI_PLAYLIST_SIZE, 5)
        self.assertEqual(len(data["items"]), 5)
        self.assertEqual(data["show"], 5)
        self.assertEqual(data["total"], 9)
        self.assertEqual(data["mode"], "MIX_ARCHIVE")

    def test_default_window_is_scrollable_past_the_visible_rows(self):
        files = [_touch_audio(self.home / "MIX_ARCHIVE" / f"mix_{i}.flac") for i in range(40)]
        self.use_archive(files)
        data = companion.get_mini_playlist()
        self.assertGreater(len(data["items"]), data["show"])
        self.assertEqual(len(data["items"]), companion.MINI_PLAYLIST_WINDOW)
        # Indices are contiguous, so the list can scroll without repeats.
        self.assertEqual([i["index"] for i in data["items"]],
                         list(range(len(data["items"]))))

    def test_window_stops_at_the_end_of_the_queue(self):
        files = [_touch_audio(self.home / "MIX_ARCHIVE" / f"mix_{i}.flac") for i in range(7)]
        self.use_archive(files)
        data = companion.get_mini_playlist()
        self.assertEqual(len(data["items"]), 7)
        self.assertEqual(data["items"][-1]["index"], 6)

    def test_first_item_is_marked_current(self):
        files = [_touch_audio(self.home / "MIX_ARCHIVE" / f"mix_{i}.flac") for i in range(4)]
        self.use_archive(files)
        data = companion.get_mini_playlist()
        self.assertTrue(data["items"][0]["current"])
        self.assertFalse(data["items"][1]["current"])

    def test_empty_library_reports_zero(self):
        self.use_archive([])
        data = companion.get_mini_playlist()
        self.assertEqual(data["items"], [])
        self.assertEqual(data["total"], 0)
        self.assertIn("modes", data)

    def test_exposes_every_mode_for_the_switch(self):
        self.use_archive([])
        modes = [m["id"] for m in companion.get_mini_playlist()["modes"]]
        self.assertEqual(modes, ["MIX_ARCHIVE", "MUSIC", "FAVORITES"])


class TestModeSwitchResponsiveness(CompanionTestBase):
    """The Mix/Music buttons must visibly switch, not appear dead."""

    def test_reselecting_the_active_mode_does_not_rewind(self):
        first = _touch_audio(self.home / "MIX_ARCHIVE" / "a.flac")
        second = _touch_audio(self.home / "MIX_ARCHIVE" / "b.flac")
        self.use_archive([first, second])
        companion.set_library_mode("MIX_ARCHIVE")
        companion.control_player("select_index", {"index": ["1"]})
        self.assertEqual(companion.load_stream_session()["index"], 1)

        self.assertEqual(companion.set_library_mode("MIX"), companion.LIBRARY_MODE_MIX)
        self.assertEqual(companion.load_stream_session()["index"], 1)

    def test_switching_library_returns_the_new_queue_length(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        track = _touch_audio(self.home / "MUSIC" / "song.mp3")
        self.use_archive([mix])
        self.use_music([track])
        companion.set_library_mode("MIX_ARCHIVE")
        self.assertEqual(len(companion.build_stream_queue()), 1)

        companion.set_library_mode("MUSIC")
        queue = companion.build_stream_queue()
        self.assertEqual(queue, [str(track)])
        self.assertEqual(len(companion.get_mini_playlist()["items"]), 1)

    def test_music_playlist_is_parsed_only_once(self):
        """Re-parsing a 30 MB playlist on every tap made the buttons feel dead."""
        playlist = self.home / "PLAYLISTS_GENERATED" / "DJ_Tracks_ALL_MUSIC_FOLDERS.json"
        track = _touch_audio(self.home / "MUSIC" / "song.mp3")
        _write(playlist, json.dumps([{"path": str(track)}]))
        companion.invalidate_queue_cache()

        calls = []
        real_read = companion._read_playlist_file

        def counting_read(path):
            calls.append(path)
            return real_read(path)

        with patch.object(companion, "music_playlist_candidates", return_value=[playlist]), \
             patch.object(companion, "_read_playlist_file", side_effect=counting_read):
            companion.scan_music_files()
            companion.scan_music_files()
            companion.scan_music_files()

        self.assertEqual(len(calls), 1)

        # The cache is keyed to the playlist file, so a rewrite re-reads it.
        with patch.object(companion, "music_playlist_candidates", return_value=[playlist]), \
             patch.object(companion, "_read_playlist_file", side_effect=counting_read):
            _write(playlist, json.dumps([{"path": str(track)}, {"path": str(track)}]))
            self.assertEqual(len(companion.scan_music_files()), 2)
        self.assertEqual(len(calls), 2)

    def test_page_marks_the_busy_mode_switch(self):
        page = companion.render_html_page(companion.THEMES["cosmic_supernova"])
        self.assertIn("setModeBusy", page)
        self.assertIn("Switching to", page)
        self.assertIn("button.pending:disabled", page)

    def test_offline_notice_is_outside_the_scroll_list(self):
        """Five rows must stay visible even when the library is offline."""
        page = companion.render_html_page(companion.THEMES["cosmic_supernova"])
        self.assertIn('id="miniPlNote"', page)
        note_pos = page.index('id="miniPlNote"')
        list_pos = page.index('id="miniPlItems"')
        self.assertLess(note_pos, list_pos)



class TestThemeButton(CompanionTestBase):
    def test_themes_endpoint_lists_every_palette(self):
        themes = companion.available_themes()
        self.assertGreater(len(themes), 1)
        self.assertTrue(all("id" in t and "name" in t for t in themes))
        self.assertEqual({t["id"] for t in themes}, set(companion.THEMES))

    def test_setting_a_theme_persists_it(self):
        target = next(iter(companion.THEMES))
        self.assertEqual(companion.set_web_theme(target), target)
        self.assertEqual(companion.get_current_theme_id(), target)

    def test_unknown_theme_is_rejected(self):
        self.assertIsNone(companion.set_web_theme("not_a_real_theme"))

    def test_page_has_a_theme_button_not_a_select(self):
        page = companion.render_html_page(companion.THEMES["cosmic_supernova"])
        self.assertIn('id="themeBtn"', page)
        self.assertIn("Theme", page)
        self.assertNotIn('id="themeSelect"', page)
        self.assertNotIn("theme-select", page)

    def test_page_exposes_mode_switch_and_track_count(self):
        page = companion.render_html_page(companion.THEMES["cosmic_supernova"])
        self.assertIn('id="modeSwitch"', page)
        self.assertIn('data-mode="MIX_ARCHIVE"', page)
        self.assertIn('data-mode="MUSIC"', page)
        self.assertIn('data-mode="FAVORITES"', page)
        self.assertIn(">Mix</button>", page)
        self.assertIn(">Music</button>", page)
        self.assertIn(">Favourites</button>", page)
        self.assertIn('id="miniPlCount"', page)

    def test_page_is_branded_as_the_liquid_player(self):
        page = companion.render_html_page(companion.THEMES["cosmic_supernova"])
        self.assertIn("MP LIQUID PLAYER (WEB)", page)
        self.assertIn("<title>MP Liquid Player (Web)", page)
        self.assertNotIn("MP MIX MANAGER <span", page)

    def test_playlist_scrolls_and_shows_five_rows(self):
        page = companion.render_html_page(companion.THEMES["cosmic_supernova"])
        self.assertIn("overflow-y: auto", page)
        self.assertIn("#miniPlItems", page)
        self.assertIn("264px", page)


class TestAutoplay(CompanionTestBase):
    def test_startup_arms_the_stream(self):
        """The service must report a playing stream so the phone auto-starts."""
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        self.use_archive([mix])
        companion.set_library_mode("MIX_ARCHIVE")

        state = companion.autoplay_once()
        self.assertEqual(state["status"], "ready")
        session = companion.load_stream_session()
        self.assertTrue(session["playing"])
        self.assertEqual(session["path"], str(mix))
        self.assertEqual(companion.get_playback_status()["state"], "playing")

    def test_autoplay_can_be_disabled(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        self.use_archive([mix])
        with patch.dict(os.environ, {"WEB_COMPANION_AUTOPLAY": "false"}):
            state = companion.autoplay_once()
        self.assertEqual(state["status"], "disabled")
        self.assertFalse(companion.load_stream_session()["playing"])

    def test_empty_library_reports_empty_playlist(self):
        self.use_archive([])
        self.assertEqual(companion.autoplay_once()["status"], "empty_playlist")

    def test_autoplay_never_opens_a_local_audio_device(self):
        """Streaming only: no player IPC, no player process, no sound output."""
        source = Path(companion.__file__).read_text(encoding="utf-8")
        for banned in ("query_mp_player_socket", "SOCKET_PATH", "mp_audio_player.sock"):
            self.assertNotIn(banned, source)

    def test_resume_position_is_restored(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        self.use_archive([mix])
        _write(
            self.config / "playback_resume.json",
            json.dumps({"path": str(mix), "position_sec": 42.5}),
        )
        with patch.object(companion, "probe_duration", return_value=300.0):
            state = companion.autoplay_once()
        self.assertAlmostEqual(state["position"], 42.5, places=1)


class TestQueueCache(CompanionTestBase):
    def test_repeated_calls_hit_the_cache(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        with patch.object(companion, "scan_archive_files", return_value=[str(mix)]) as scan:
            companion.build_stream_queue()
            companion.build_stream_queue()
            companion.build_stream_queue()
        self.assertEqual(scan.call_count, 1)

    def test_switching_mode_invalidates_the_cache(self):
        mix = _touch_audio(self.home / "MIX_ARCHIVE" / "mix_one.flac")
        track = _touch_audio(self.home / "MUSIC" / "song.mp3")
        self.use_archive([mix])
        self.use_music([track])
        companion.set_library_mode("MIX_ARCHIVE")
        self.assertEqual(companion.build_stream_queue(), [str(mix)])
        companion.set_library_mode("MUSIC")
        self.assertEqual(companion.build_stream_queue(), [str(track)])


if __name__ == "__main__":
    unittest.main()
