"""Drag and drop audio files onto the MP Liquid Player."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import liquid_audio_drop as drop
import MP_Audio_Player as player


class _Scanner:
    def __init__(self, mixes):
        self.mixes = list(mixes)

    def get_mixes(self, query=""):
        return self.mixes


class _InlineThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class DropCollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _touch(self, rel):
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"audio")
        return path

    def test_accepts_every_audio_type_and_rejects_other_files(self):
        accepted = []
        for ext in drop.AUDIO_DROP_EXTENSIONS:
            accepted.append(str(self._touch(f"track{ext}")))
        self._touch("clip.mp4")
        self._touch("photo.jpg")
        self._touch("notes.txt")
        self._touch("nested/.hidden.flac")
        self._touch("nested/visible.wav")
        paths, truncated = drop.collect_dropped_audio(
            [f"file://{quote(path)}" for path in accepted]
            + [str(self.dir / "clip.mp4"), str(self.dir / "photo.jpg"), str(self.dir / "notes.txt"), str(self.dir / "nested")]
        )
        self.assertNotIn(os.path.abspath(self.dir / "nested" / ".hidden.flac"), paths)
        self.assertIn(os.path.abspath(self.dir / "nested" / "visible.wav"), paths)
        self.assertFalse(truncated)
        self.assertEqual(paths[:len(accepted)], [os.path.abspath(path) for path in accepted])
        self.assertEqual(paths[len(accepted):], [os.path.abspath(self.dir / "nested" / "visible.wav")])

    def test_decodes_file_uris_directories_and_playlists(self):
        spaced = self._touch("My Mix.flac")
        nested = self._touch("Album/song.opus")
        self._touch("Album/cover.jpg")
        self._touch("Album/.skip.wav")
        later = self._touch("Album/zz.wav")
        playlist = self.dir / "set.m3u8"
        playlist.write_text("#EXTM3U\n#EXTINF:1,Song\nsong.opus\nnotes.txt\n", encoding="utf-8")
        (self.dir / "song.opus").write_bytes(b"audio")
        (self.dir / "notes.txt").write_bytes(b"nope")
        pls = self.dir / "set.pls"
        pls.write_text(f"[playlist]\nFile1={later}\nFile2=http://example.test/no.mp3\n", encoding="utf-8")
        paths, truncated = drop.collect_dropped_audio([
            f"file://{quote(str(spaced))}",
            f"'{self.dir / 'Album'}'",
            str(playlist),
            str(pls),
        ])
        self.assertFalse(truncated)
        self.assertEqual(paths[0], os.path.abspath(spaced))
        self.assertIn(os.path.abspath(nested), paths)
        self.assertIn(os.path.abspath(later), paths)
        self.assertIn(os.path.abspath(self.dir / "song.opus"), paths)
        self.assertTrue(all(path.endswith((".flac", ".opus", ".wav")) for path in paths))
        self.assertEqual(len(paths), len(set(paths)))

    def test_directory_scan_stops_at_the_file_cap(self):
        for index in range(5):
            self._touch(f"folder/track{index}.mp3")
        paths, truncated = drop.collect_dropped_audio([str(self.dir / "folder")], limit=2)
        self.assertTrue(truncated)
        self.assertEqual(len(paths), 2)

    def test_dialog_filters_name_every_audio_type(self):
        for builder in (drop.kdialog_audio_filter, drop.zenity_audio_filter, drop.windows_audio_filter):
            text = builder()
            self.assertIn("Audio Files (All types)", text)
            for ext in (".flac", ".wav", ".mp3", ".ogg", ".opus", ".m4a", ".aac", ".aiff", ".wma", ".dsf", ".ape"):
                self.assertIn(f"*{ext}", text)

    def test_only_the_audio_player_window_accepts_drops(self):
        self.assertTrue(drop.host_accepts_audio_drops(["python3", str(ROOT / "MP_Audio_Player.py"), "--interactive"]))
        self.assertTrue(drop.host_accepts_audio_drops([r"C:\MP\MP_Audio_Player.py"]))
        self.assertFalse(drop.host_accepts_audio_drops(["bash", str(ROOT / "Mix_Archive_Manager.sh")]))
        self.assertFalse(drop.host_accepts_audio_drops(["bash", str(ROOT / "scripts" / "view_tracklist_console.sh")]))

    def test_uncommon_audio_types_prefer_ffmpeg(self):
        self.assertFalse(drop.prefers_ffmpeg("mix.flac"))
        self.assertFalse(drop.prefers_ffmpeg("track.wav"))
        self.assertTrue(drop.prefers_ffmpeg("voice.opus"))
        self.assertTrue(drop.prefers_ffmpeg("album.dsf"))
        self.assertTrue(drop.prefers_ffmpeg("song.ape"))
        self.assertTrue(drop.prefers_ffmpeg("track.m4a"))


class DropDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.drop_dir = Path(self.tmp.name) / "drops"
        self.env = patch.dict(os.environ, {"MP_LIQUID_DROP_DIR": str(self.drop_dir)})
        self.env.start()
        self.audio = Path(self.tmp.name) / "Song.opus"
        self.audio.write_bytes(b"audio")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_manifest_round_trip_and_osc(self):
        path = drop.write_drop_manifest([str(self.audio)], truncated=True, rejected=False)
        self.assertTrue(drop.is_drop_manifest(path))
        outside = Path(self.tmp.name) / "evil.json"
        outside.write_text('{"paths": ["secret"]}', encoding="utf-8")
        self.assertFalse(drop.is_drop_manifest(outside))
        payload = drop.drop_osc(path)
        self.assertTrue(payload.startswith(drop.DROP_OSC_PREFIX))
        self.assertTrue(payload.endswith(b"\x07"))
        data = drop.read_drop_manifest(path)
        self.assertEqual(data["paths"], [str(self.audio)])
        self.assertTrue(data["truncated"])

    def test_bridge_feeds_the_terminal_after_the_player_is_ready(self):
        class Terminal:
            def __init__(self):
                self.fed = []

            def feed_child(self, data, length=None):
                self.fed.append(bytes(data))

        terminal = Terminal()
        bridge = drop.AudioDropBridge()
        bridge.terminal = terminal
        with patch.object(drop, "_schedule", side_effect=lambda fn: fn()):
            bridge._scan([f"file://{quote(str(self.audio))}", str(self.audio.with_suffix(".txt"))])
            self.assertEqual(terminal.fed, [])
            bridge.mark_ready()
        self.assertEqual(len(terminal.fed), 1)
        manifest = Path(terminal.fed[0][len(drop.DROP_OSC_PREFIX):-1].decode())
        self.assertEqual(drop.read_drop_manifest(manifest)["paths"], [os.path.abspath(self.audio)])
        manifest.unlink()

    def test_bridge_reports_a_drop_with_no_audio(self):
        class Terminal:
            def __init__(self):
                self.fed = []

            def feed_child(self, data, length=None):
                self.fed.append(bytes(data))

        terminal = Terminal()
        bridge = drop.AudioDropBridge()
        bridge.terminal = terminal
        bridge.ready = True
        with patch.object(drop, "_schedule", side_effect=lambda fn: fn()):
            bridge._scan([str(self.audio.with_suffix(".jpg"))])
        manifest = Path(terminal.fed[0][len(drop.DROP_OSC_PREFIX):-1].decode())
        data = drop.read_drop_manifest(manifest)
        self.assertEqual(data["paths"], [])
        self.assertTrue(data["rejected"])
        manifest.unlink()


class PlayerDropTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.drop_dir = Path(self.tmp.name) / "drops"
        self.env = patch.dict(os.environ, {"MP_LIQUID_DROP_DIR": str(self.drop_dir)})
        self.env.start()
        self.tracks = []
        for name in ("Mix_A.flac", "Mix_B.wav"):
            path = Path(self.tmp.name) / name
            path.write_bytes(b"RIFF" + b"\x00" * 16)
            self.tracks.append({"name": name, "path": str(path), "size_mb": 1.0, "ext": path.suffix[1:].upper()})
        self.opus = Path(self.tmp.name) / "Voice.opus"
        self.opus.write_bytes(b"opus")
        self.engine = player.AudioEngine(list(self.tracks), auto_bluetooth=False)
        self.engine.load_track = MagicMock(return_value=True)
        self.scanner = _Scanner(self.tracks)
        self.ui = player.TerminalPlayerUI(self.engine, self.scanner, is_remote=False)

    def tearDown(self):
        try:
            self.engine.stop_playback()
        except Exception:
            pass
        self.env.stop()
        self.tmp.cleanup()

    def _manifest(self, paths, **extra):
        return drop.write_drop_manifest(paths, **extra)

    def test_drop_puts_every_audio_file_first_and_plays_the_first(self):
        manifest = self._manifest([str(self.opus), self.tracks[1]["path"], str(Path(self.tmp.name) / "notes.txt")])
        self.ui.search_mode = True
        self.ui.search_query = "old"
        self.ui._playlist_clear_armed = True
        self.ui._consume_input(drop.drop_osc(manifest)[:12])
        self.assertEqual(self.scanner.mixes[0]["path"], self.tracks[0]["path"])
        self.ui._consume_input(drop.drop_osc(manifest)[12:])
        self.assertEqual([item["path"] for item in self.scanner.mixes], [os.path.abspath(self.opus), self.tracks[1]["path"], self.tracks[0]["path"]])
        self.assertEqual([item["path"] for item in self.engine.playlist], [item["path"] for item in self.scanner.mixes])
        self.engine.load_track.assert_called_with(0, True)
        self.assertEqual(self.ui.selected_row, 0)
        self.assertFalse(self.ui.search_mode)
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertIn("Playing 2 audio files", self.ui.notification_msg)
        self.assertIn("Voice.opus", self.ui.notification_msg)
        self.assertFalse(manifest.exists())

    def test_keys_mouse_and_escape_still_work_around_a_drop(self):
        self.ui._on_mouse_sgr = MagicMock()
        self.ui._consume_input(b"s\x1b[<0;4;5M")
        self.ui._on_mouse_sgr.assert_called_once()
        self.assertTrue(self.engine.shuffle)
        self.ui._process_key(b"D")
        self.ui._consume_input(b"\x1b")
        self.assertFalse(self.ui._playlist_clear_armed)
        self.assertIn("cancelled", self.ui.notification_msg)
        self.assertEqual(len(self.scanner.mixes), 2)

    def test_foreign_manifest_path_is_ignored(self):
        outside = Path(self.tmp.name) / "evil.json"
        outside.write_text('{"paths": ["%s"], "rejected": false}' % self.opus, encoding="utf-8")
        self.ui._consume_input(drop.DROP_OSC_PREFIX + str(outside).encode() + b"\x07")
        self.assertEqual([item["path"] for item in self.scanner.mixes], [item["path"] for item in self.tracks])
        self.assertTrue(outside.is_file())

    def test_rejected_drop_keeps_the_playlist(self):
        manifest = self._manifest([], rejected=True)
        self.ui._play_dropped_manifest(str(manifest))
        self.assertEqual(len(self.scanner.mixes), 2)
        self.assertIn("All audio types", self.ui.notification_msg)
        self.assertFalse(manifest.exists())

    def test_remote_ui_sends_the_manifest_to_the_engine(self):
        remote = player.TerminalPlayerUI(None, _Scanner(self.tracks), is_remote=True)
        manifest = self._manifest([str(self.opus)])
        seen = {}

        def fake_send(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["exists"] = Path(kwargs["manifest"]).is_file()
            seen["paths"] = drop.read_drop_manifest(kwargs["manifest"])["paths"]
            return {"status": "ok", "added": 1}

        with patch.object(player.threading, "Thread", _InlineThread), patch.object(player, "send_ipc_command", fake_send):
            remote._consume_input(drop.drop_osc(manifest))
        self.assertEqual(seen["cmd"], "drop_audio")
        self.assertTrue(seen["exists"])
        self.assertEqual(seen["paths"], [str(self.opus)])
        self.assertEqual(remote.scanner.mixes[0]["path"], os.path.abspath(self.opus))
        self.assertIn("Playing: Voice.opus", remote.notification_msg)
        self.assertFalse(manifest.exists())

    def test_engine_command_prepends_without_blocking_on_playback(self):
        manifest = self._manifest([str(self.opus), self.tracks[0]["path"]])
        with patch.object(player.threading, "Thread", _InlineThread):
            added = player.apply_drop_audio_command(self.engine, {"manifest": str(manifest)})
        self.assertEqual(added, 2)
        self.assertEqual(self.engine.playlist[0]["path"], os.path.abspath(self.opus))
        self.assertEqual(self.engine.playlist[1]["path"], self.tracks[0]["path"])
        self.engine.load_track.assert_called_with(0, True)


class LiquidHostWiringTests(unittest.TestCase):
    def test_both_liquid_players_install_audio_drops(self):
        for name in ("MP_Audio_Player_Liquid_Glass_OpenGL.py", "MP_Audio_Player_Liquid_Glass.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("def _install_audio_drop", text)
            self.assertIn("self._install_audio_drop(term)", text)
            self.assertIn("self.audio_drop.mark_ready()", text)
            self.assertIn("host_accepts_audio_drops", text)
