#!/usr/bin/env python3
"""Pressing G in MP Audio Player opens an existing Spek, or generates one into SPEK_OUTPUTS and opens it."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import MP_Audio_Player


class _InlineThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class TestPlayerSpekGenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.audio = self.base / "Tone Mix.flac"
        self.audio.write_bytes(b"DUMMY_FLAC")
        self.spek_dir = self.base / "SPEK_OUTPUTS"
        self.scanner = MagicMock()
        self.scanner.get_mixes.return_value = [{"name": "Tone Mix", "path": str(self.audio)}]
        self.scanner.get_latest_mix.return_value = None
        self.ui = MP_Audio_Player.TerminalPlayerUI(None, self.scanner, is_remote=True)
        self.ui.selected_row = 0
        self.notes = []
        real_notify = self.ui._notify

        def _cap(msg, dur=3.0):
            self.notes.append(msg)
            real_notify(msg, dur)

        self.ui._notify = _cap

    def tearDown(self):
        self.tmp.cleanup()

    def test_g_opens_existing_spek_without_generating(self):
        existing = self.spek_dir / "Tone Mix_spectrogram.png"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"PNG")
        with patch.object(MP_Audio_Player, "find_existing_spek", return_value=str(existing)), \
             patch.object(MP_Audio_Player, "generate_track_spek") as gen, \
             patch.object(MP_Audio_Player, "open_image_viewer", return_value=True) as viewer:
            self.ui._process_key(b"G")
        gen.assert_not_called()
        viewer.assert_called_once_with(str(existing))
        self.assertTrue(any("Opening Spek" in n for n in self.notes))

    def test_g_generates_missing_spek_into_spek_outputs_then_opens_it(self):
        created = {}

        def fake_gen(audio_path, mode="MIX_ARCHIVE", output_dir=None, force=False):
            self.assertEqual(audio_path, str(self.audio))
            self.assertEqual(Path(output_dir), self.spek_dir)
            self.spek_dir.mkdir(parents=True, exist_ok=True)
            dest = self.spek_dir / "Tone Mix_spectrogram.png"
            dest.write_bytes(b"GENERATED_PNG")
            created["path"] = str(dest.resolve())
            return True, created["path"]

        with patch.object(MP_Audio_Player, "get_default_spek_dir", return_value=self.spek_dir), \
             patch.object(MP_Audio_Player, "find_existing_spek", return_value=None), \
             patch.object(MP_Audio_Player, "generate_track_spek", side_effect=fake_gen), \
             patch.object(MP_Audio_Player, "open_image_viewer", return_value=True) as viewer, \
             patch.object(MP_Audio_Player, "notify_desktop") as desk, \
             patch.object(MP_Audio_Player.threading, "Thread", _InlineThread):
            self.ui._process_key(b"g")

        self.assertTrue(any("MP Audio Player is generating a Spek for Tone Mix" in n for n in self.notes))
        self.assertTrue(any("finished the Spek" in n for n in self.notes))
        viewer.assert_called_once_with(created["path"])
        self.assertTrue(Path(created["path"]).is_file())
        self.assertEqual(Path(created["path"]).parent, self.spek_dir)
        desk.assert_any_call("MP Audio Player", "MP Audio Player is generating a Spek for Tone Mix")
        self.assertFalse(self.ui._spek_job_running)

    def test_generate_track_spek_writes_spectrogram_png_in_output_dir(self):
        out = self.base / "archive_spek"
        def fake_run(cmd, **kwargs):
            dest = Path(cmd[-1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"PNGDATA")
            return subprocess_result()

        with patch.object(MP_Audio_Player.subprocess, "run", side_effect=fake_run) as run:
            ok, res = MP_Audio_Player.generate_track_spek(str(self.audio), output_dir=out)
        self.assertTrue(ok)
        expected = (out / "Tone Mix_spectrogram.png").resolve()
        self.assertEqual(Path(res), expected)
        self.assertTrue(expected.is_file())
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], "ffmpeg")
        self.assertEqual(Path(argv[-1]).resolve(), expected)


def subprocess_result():
    class _R:
        returncode = 0
        stderr = ""
    return _R()


if __name__ == "__main__":
    unittest.main()
