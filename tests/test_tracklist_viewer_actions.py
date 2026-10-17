#!/usr/bin/env python3
"""
Unit tests for Tracklist Viewer (scripts/view_tracklist_console.sh & MP_Audio_Player.py):
- Pressing E edits tracklist in VI and reloads from disk
- Pressing G opens existing Spek immediately if it already exists, or generates and opens Spek if not
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import MP_Audio_Player as mp_player


class TestTracklistViewerActions(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp_dir.name)
        self.bin_dir = self.base / "bin"
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.viewer_sh = REPO_ROOT / "scripts" / "view_tracklist_console.sh"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _make_executable(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def test_footer_shows_e_vi_and_g_spek(self):
        tl = self.base / "Mix_001.txt"
        tl.write_text("01. Artist One - Track One\n", encoding="utf-8")

        res = subprocess.run(
            ["bash", str(self.viewer_sh), str(tl)],
            input="q",
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("[E]", res.stdout)
        self.assertIn("Edit Tracklist in VI", res.stdout)
        self.assertIn("[G]", res.stdout)
        self.assertIn("Generate & Open Spek", res.stdout)
        self.assertIn("[D]", res.stdout)
        self.assertIn("Extract & Copy Mix Audio", res.stdout)

    def test_press_d_extracts_and_copies_mix_audio(self):
        mix_dir = self.base / "MIX_ARCHIVE_COPY"
        flac_dir = mix_dir / "FLAC_CONVERTED_OUTPUTS"
        flac_dir.mkdir(parents=True, exist_ok=True)

        audio_file = flac_dir / "Stream_of_Frequency_101.flac"
        audio_content = b"FLAC_AUDIO_STREAM_PAYLOAD_101"
        audio_file.write_bytes(audio_content)

        tl_file = flac_dir / "Stream_of_Frequency_101.txt"
        tl_file.write_text("01. DJ Test - Frequency 101\n", encoding="utf-8")

        dest_dir = self.base / "Extracted_Mixes"

        env = os.environ.copy()
        env["MIX_ARCHIVE_DIR"] = str(mix_dir)

        res = subprocess.run(
            ["bash", str(self.viewer_sh), str(tl_file)],
            input=f"d{dest_dir}\nq",
            text=True,
            capture_output=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        copied_file = dest_dir / "Stream_of_Frequency_101.flac"
        self.assertTrue(copied_file.is_file(), "Mix audio file should be copied to destination directory")
        self.assertEqual(copied_file.read_bytes(), audio_content)
        self.assertIn("Mix audio file extracted and copied to:", res.stdout)

    def test_press_e_edits_tracklist_in_vi(self):
        tl = self.base / "Mix_002.txt"
        tl.write_text("01. Old Artist - Old Title\n", encoding="utf-8")
        vi_log = self.base / "vi_called.txt"

        self._make_executable(
            self.bin_dir / "vi",
            f'#!/bin/bash\necho "$1" > "{vi_log}"\necho "02. Added By VI - New Track" >> "$1"\nexit 0\n',
        )

        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        res = subprocess.run(
            ["bash", str(self.viewer_sh), str(tl)],
            input="eq",
            text=True,
            capture_output=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(vi_log.is_file(), "vi should have been invoked when pressing E")
        self.assertEqual(vi_log.read_text(encoding="utf-8").strip(), str(tl))
        self.assertIn("Added By VI", tl.read_text(encoding="utf-8"))
        self.assertIn("Tracklist edited in VI and reloaded from disk", res.stdout)

    def test_press_g_opens_existing_spek_immediately(self):
        mix_dir = self.base / "MIX_ARCHIVE"
        flac_dir = mix_dir / "FLAC_CONVERTED_OUTPUTS"
        spek_dir = mix_dir / "SPEK_OUTPUTS"
        flac_dir.mkdir(parents=True, exist_ok=True)
        spek_dir.mkdir(parents=True, exist_ok=True)

        audio_file = flac_dir / "Stream_of_Frequency_099.flac"
        audio_file.write_bytes(b"RIFF_DUMMY_AUDIO")
        tl_file = flac_dir / "Stream_of_Frequency_099.txt"
        tl_file.write_text("01. DJ Test - Frequency 099\n", encoding="utf-8")

        existing_spek = spek_dir / "Stream_of_Frequency_099_spectrogram.png"
        existing_spek.write_bytes(b"\x89PNG\r\n\x1a\nEXISTING_SPEK_DATA")

        viewer_log = self.base / "viewer_opened.txt"
        ffmpeg_log = self.base / "ffmpeg_called.txt"

        self._make_executable(
            self.bin_dir / "gwenview",
            f'#!/bin/bash\necho "$1" > "{viewer_log}"\nexit 0\n',
        )
        self._make_executable(
            self.bin_dir / "ffmpeg",
            f'#!/bin/bash\necho "CALLED" > "{ffmpeg_log}"\nexit 0\n',
        )

        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        env["MIX_ARCHIVE_DIR"] = str(mix_dir)

        res = subprocess.run(
            ["bash", str(self.viewer_sh), str(tl_file), str(audio_file)],
            input="gq",
            text=True,
            capture_output=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Spek already exists! Opened:", res.stdout)
        self.assertFalse(ffmpeg_log.exists(), "ffmpeg should not run when Spek already exists")
        for _ in range(20):
            if viewer_log.is_file():
                break
            import time
            time.sleep(0.05)
        self.assertTrue(viewer_log.is_file(), "Image viewer should be launched for existing Spek")
        self.assertEqual(Path(viewer_log.read_text(encoding="utf-8").strip()).resolve(), existing_spek.resolve())

    def test_press_g_generates_and_opens_spek_when_missing(self):
        mix_dir = self.base / "MIX_ARCHIVE_GEN"
        flac_dir = mix_dir / "FLAC_CONVERTED_OUTPUTS"
        spek_dir = mix_dir / "SPEK_OUTPUTS"
        flac_dir.mkdir(parents=True, exist_ok=True)

        audio_file = flac_dir / "Stream_of_Frequency_100.flac"
        audio_file.write_bytes(b"RIFF_DUMMY_AUDIO")
        tl_file = flac_dir / "Stream_of_Frequency_100.txt"
        tl_file.write_text("01. DJ Test - Frequency 100\n", encoding="utf-8")

        viewer_log = self.base / "viewer_gen_opened.txt"
        self._make_executable(
            self.bin_dir / "gwenview",
            f'#!/bin/bash\necho "$1" > "{viewer_log}"\nexit 0\n',
        )
        self._make_executable(
            self.bin_dir / "ffmpeg",
            '#!/bin/bash\n'
            'out="${@: -1}"\n'
            'mkdir -p "$(dirname "$out")"\n'
            'printf "GENERATED_PNG_DATA" > "$out"\n'
            'exit 0\n',
        )

        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        env["MIX_ARCHIVE_DIR"] = str(mix_dir)

        res = subprocess.run(
            ["bash", str(self.viewer_sh), str(tl_file)],
            input="gq",
            text=True,
            capture_output=True,
            env=env,
            timeout=15,
        )
        self.assertEqual(res.returncode, 0)
        expected_spek = spek_dir / "Stream_of_Frequency_100_spectrogram.png"
        self.assertTrue(expected_spek.is_file(), "Spek spectrogram should be generated in SPEK_OUTPUTS")
        self.assertIn("Spek generated and opened:", res.stdout)
        for _ in range(20):
            if viewer_log.is_file():
                break
            import time
            time.sleep(0.05)
        self.assertTrue(viewer_log.is_file(), "Image viewer should be launched for newly generated Spek")
        self.assertEqual(Path(viewer_log.read_text(encoding="utf-8").strip()).resolve(), expected_spek.resolve())

    def test_mp_audio_player_reuses_existing_spek(self):
        audio_file = self.base / "Test_Mix_Ep55.flac"
        audio_file.write_bytes(b"DUMMY_FLAC")
        spek_dir = self.base / "SPEK_OUTPUTS"
        spek_dir.mkdir(parents=True, exist_ok=True)
        existing_spek = spek_dir / "Test_Mix_Ep55_spectrogram.png"
        existing_spek.write_bytes(b"EXISTING_PNG")

        found = mp_player.find_existing_spek(str(audio_file), output_dir=spek_dir)
        self.assertEqual(found, str(existing_spek.resolve()))

        with patch("MP_Audio_Player.subprocess.run") as mock_run:
            ok, res = mp_player.generate_track_spek(str(audio_file), output_dir=spek_dir)
            self.assertTrue(ok)
            self.assertEqual(res, str(existing_spek.resolve()))
            ffmpeg_calls = [c for c in mock_run.call_args_list if c.args and c.args[0] and c.args[0][0] == "ffmpeg"]
            self.assertEqual(len(ffmpeg_calls), 0)


if __name__ == "__main__":
    unittest.main()
