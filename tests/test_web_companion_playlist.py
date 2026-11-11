"""Tests for the Web Companion library mode, mini playlist, theming and autoplay.

These cover the behaviour added on top of the streaming base:

  * a three-track mini playlist that also reports the full library count
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
    def test_returns_three_items_and_full_count(self):
        files = [_touch_audio(self.home / "MIX_ARCHIVE" / f"mix_{i}.flac") for i in range(9)]
        self.use_archive(files)
        companion.set_library_mode("MIX_ARCHIVE")

        data = companion.get_mini_playlist()
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["total"], 9)
        self.assertEqual(data["mode"], "MIX_ARCHIVE")

    def test_first_item_is_marked_current(self):
        files = [_touch_audio(self.home / "MIX_ARCHIVE" / f"mix_{i}.flac") for i in range(4)]
        self.use_archive(files)
        data = companion.get_mini_playlist()
        self.assertTrue(data["items"][0]["current"])
        self.assertFalse(data["items"][1]["current"])

    def test_items_wrap_past_the_end_of_the_queue(self):
        files = [_touch_audio(self.home / "MIX_ARCHIVE" / f"mix_{i}.flac") for i in range(2)]
        self.use_archive(files)
        data = companion.get_mini_playlist(limit=3)
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["items"][2]["index"], 0)

    def test_empty_library_reports_zero(self):
        self.use_archive([])
        data = companion.get_mini_playlist()
        self.assertEqual(data["items"], [])
        self.assertEqual(data["total"], 0)
        self.assertIn("modes", data)

    def test_exposes_both_modes_for_the_switch(self):
        self.use_archive([])
        modes = [m["id"] for m in companion.get_mini_playlist()["modes"]]
        self.assertEqual(modes, ["MIX_ARCHIVE", "MUSIC"])


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
        self.assertIn('id="miniPlCount"', page)


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
