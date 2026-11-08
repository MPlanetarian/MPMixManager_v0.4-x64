#!/usr/bin/env python3
"""Clear the open MP Audio Player playlist from the keyboard."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import MP_Audio_Player as player


class ClearPlaylistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tracks = []
        for name in ("Mix_A.flac", "Mix_B.flac", "Mix_C.flac"):
            path = Path(self.tmp.name) / name
            path.write_bytes(b"RIFF" + b"\x00" * 32)
            self.tracks.append({"name": name, "path": str(path), "size_mb": 1.0, "ext": "FLAC"})
        self.engine = player.AudioEngine(list(self.tracks), auto_bluetooth=False)
        self.engine.queue_track(self.tracks[2]["path"])
        self.scanner = MagicMock()
        self.scanner.mixes = list(self.tracks)
        self.ui = player.TerminalPlayerUI(self.engine, self.scanner, is_remote=False)

    def tearDown(self):
        try:
            self.engine.stop_playback()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_engine_clear_playlist_empties_list_queue_and_stops(self):
        self.engine.current_track = self.tracks[0]
        self.engine.state = "playing"
        removed = self.engine.clear_playlist()
        self.assertEqual(removed, 3)
        self.assertEqual(self.engine.playlist, [])
        self.assertEqual(self.engine.play_queue, [])
        self.assertIsNone(self.engine.current_track)
        self.assertEqual(self.engine.state, "stopped")
        self.assertTrue(Path(self.tracks[0]["path"]).is_file())

    def test_d_then_d_clears_visible_playlist_and_queue(self):
        self.ui._process_key(b"d")
        self.assertTrue(self.ui._playlist_clear_armed)
        self.assertEqual(len(self.scanner.mixes), 3)
        self.assertIn("Press D or Del again", self.ui.notification_msg)

        self.ui._process_key(b"D")
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertEqual(self.scanner.mixes, [])
        self.assertEqual(self.engine.playlist, [])
        self.assertEqual(self.engine.play_queue, [])
        self.assertIsNone(self.engine.current_track)
        self.assertEqual(self.engine.state, "stopped")
        self.assertIn("Playlist cleared", self.ui.notification_msg)
        self.assertIn("not deleted", self.ui.notification_msg)
        self.assertTrue(self.ui.running)
        self.assertTrue(Path(self.tracks[1]["path"]).is_file())

    def test_delete_key_confirms_clear(self):
        self.ui._process_key(b"\x1b[3~")
        self.ui._process_key(b"\x1b[3~")
        self.assertEqual(self.scanner.mixes, [])
        self.assertEqual(self.engine.playlist, [])

    def test_escape_cancels_without_leaving_the_player(self):
        self.ui._process_key(b"D")
        self.ui._process_key(b"\x1b")
        self.assertTrue(self.ui.running)
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertEqual(len(self.scanner.mixes), 3)
        self.assertEqual(len(self.engine.playlist), 3)
        self.assertIn("cancelled", self.ui.notification_msg)

    def test_other_key_cancels_and_still_runs(self):
        self.ui._process_key(b"D")
        self.ui._process_key(b"s")
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertEqual(len(self.engine.playlist), 3)
        self.assertTrue(self.engine.shuffle)

    def test_empty_playlist_does_not_arm(self):
        self.scanner.mixes = []
        self.engine.clear_playlist()
        self.ui._process_key(b"d")
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertIn("already empty", self.ui.notification_msg)

    def test_equalizer_d_does_not_clear_the_playlist(self):
        self.ui.equalizer_hud_active = True
        self.ui._process_key(b"d")
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertEqual(len(self.scanner.mixes), 3)
        self.assertEqual(len(self.engine.playlist), 3)

    def test_inspector_d_does_not_clear_the_playlist(self):
        self.ui.inspector_hud_active = True
        self.ui._process_key(b"D")
        self.assertFalse(getattr(self.ui, "_playlist_clear_armed", False))
        self.assertEqual(len(self.scanner.mixes), 3)

    def test_search_d_types_instead_of_clearing(self):
        self.ui.search_mode = True
        self.ui._process_key(b"d")
        self.assertEqual(self.ui.search_query, "d")
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertEqual(len(self.scanner.mixes), 3)

    def test_remote_clear_sends_ipc_and_empties_local_list(self):
        sent = []
        self.ui.is_remote = True
        self.ui._send_cmd = lambda cmd, **kwargs: sent.append(cmd)
        self.ui._process_key(b"d")
        self.ui._process_key(b"d")
        self.assertEqual(sent, ["clear_playlist"])
        self.assertEqual(self.scanner.mixes, [])
        self.assertEqual(self.ui.cached_status["queue"], [])
        self.assertEqual(self.ui.cached_status["state"], "stopped")
        self.assertEqual(self.ui.cached_status["title"], "No Track Loaded")

    def test_clear_does_not_rewrite_music_playlist_file(self):
        playlist = Path(self.tmp.name) / "DJ_Tracks_ALL.json"
        payload = [{"name": "Track A", "path": "/music/a.flac", "ext": "FLAC"}]
        playlist.write_text(json.dumps(payload), encoding="utf-8")
        scanner = player.MusicFolderPlaylistScanner("ALL", playlist)
        engine = player.AudioEngine(list(scanner.mixes), auto_bluetooth=False)
        ui = player.TerminalPlayerUI(engine, scanner, mode="MUSIC")
        ui._process_key(b"d")
        ui._process_key(b"d")
        self.assertEqual(scanner.mixes, [])
        self.assertEqual(engine.playlist, [])
        self.assertEqual(json.loads(playlist.read_text(encoding="utf-8")), payload)
        engine.stop_playback()


if __name__ == "__main__":
    unittest.main()
