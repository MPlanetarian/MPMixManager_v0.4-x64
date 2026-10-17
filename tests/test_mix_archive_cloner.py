#!/usr/bin/env python3
"""
Unit tests for MP_Mix_Archive_Cloner (scripts/MP_Mix_Archive_Cloner.sh):
- Validates that destination path must be a full (absolute) path
- Clones an entire Mix Archive folder (with FLACs, WAVs, tracklists, Spek, etc.) to a new destination
- Supports interactive mode (prompting user for full destination path) and CLI flags (--source, --dest, --all)
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestMPMixArchiveCloner(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp_dir.name)
        self.cloner_sh = REPO_ROOT / "scripts" / "MP_Mix_Archive_Cloner.sh"

        # Create a sample Mix Archive folder structure
        self.src_archive = self.base / "MIX_ARCHIVE_SOURCE"
        (self.src_archive / "FLAC_CONVERTED_OUTPUTS").mkdir(parents=True, exist_ok=True)
        (self.src_archive / "CONVERTED_WAV_FILES").mkdir(parents=True, exist_ok=True)
        (self.src_archive / "SPEK_OUTPUTS").mkdir(parents=True, exist_ok=True)

        (self.src_archive / "FLAC_CONVERTED_OUTPUTS" / "Mix_Ep01.flac").write_bytes(b"FLAC_DATA_01")
        (self.src_archive / "FLAC_CONVERTED_OUTPUTS" / "Mix_Ep01.txt").write_text("01. Track 1\n", encoding="utf-8")
        (self.src_archive / "CONVERTED_WAV_FILES" / "Mix_Ep01.wav").write_bytes(b"WAV_DATA_01")
        (self.src_archive / "SPEK_OUTPUTS" / "Mix_Ep01_spectrogram.png").write_bytes(b"PNG_DATA_01")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_rejects_relative_destination_path(self):
        res = subprocess.run(
            ["bash", str(self.cloner_sh), "--source", str(self.src_archive), "--dest", "relative/backup/folder"],
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("full (absolute) destination path", res.stderr)

    def test_clones_entire_archive_folder_cli(self):
        dest_root = self.base / "BACKUP_DESTINATION"
        res = subprocess.run(
            ["bash", str(self.cloner_sh), "--source", str(self.src_archive), "--dest", str(dest_root)],
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(res.returncode, 0, msg=f"stderr: {res.stderr}\nstdout: {res.stdout}")
        cloned_root = dest_root / "MIX_ARCHIVE_SOURCE"
        self.assertTrue((cloned_root / "FLAC_CONVERTED_OUTPUTS" / "Mix_Ep01.flac").is_file())
        self.assertEqual((cloned_root / "FLAC_CONVERTED_OUTPUTS" / "Mix_Ep01.flac").read_bytes(), b"FLAC_DATA_01")
        self.assertTrue((cloned_root / "FLAC_CONVERTED_OUTPUTS" / "Mix_Ep01.txt").is_file())
        self.assertTrue((cloned_root / "CONVERTED_WAV_FILES" / "Mix_Ep01.wav").is_file())
        self.assertTrue((cloned_root / "SPEK_OUTPUTS" / "Mix_Ep01_spectrogram.png").is_file())

    def test_interactive_mode_prompts_and_clones_to_full_path(self):
        dest_root = self.base / "INTERACTIVE_CLONE_DEST"
        env = os.environ.copy()
        env["MIX_ARCHIVE_DIR"] = str(self.src_archive)
        env["EXTRA_MIX_ARCHIVE_DIRS"] = ""
        env["MP_CLONER_SKIP_REPO_DEFAULT"] = "1"

        # Choose option 1 (first discovered archive) and provide full destination path
        user_input = f"1\n{dest_root}\n"
        res = subprocess.run(
            ["bash", str(self.cloner_sh)],
            input=user_input,
            text=True,
            capture_output=True,
            env=env,
            timeout=15,
        )
        self.assertEqual(res.returncode, 0, msg=f"stderr: {res.stderr}\nstdout: {res.stdout}")
        cloned_root = dest_root / "MIX_ARCHIVE_SOURCE"
        self.assertTrue((cloned_root / "FLAC_CONVERTED_OUTPUTS" / "Mix_Ep01.flac").is_file())
        self.assertIn("MIX ARCHIVE CLONE & BACKUP COMPLETED SUCCESSFULLY", res.stdout)


if __name__ == "__main__":
    unittest.main()
