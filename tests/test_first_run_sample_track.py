#!/usr/bin/env python3
"""
Unit tests for the v0.4 release celebration track & first-run pre-load system.
Verifies that:
1. The sample track and cover art exist in MP_SAMPLES with valid metadata.
2. On first run, setup_first_run_sample_track loads the track ready at 0:00 (stopped state).
3. The first-run pre-load only occurs once and never overwrites user choices on subsequent runs.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.liquid_glass_reward import (
    ROOT,
    SAMPLE_DIR,
    SAMPLE_TRACK_NAME,
    SAMPLE_TRACK_FILE,
    SAMPLE_COVER_FILE,
    setup_first_run_sample_track,
)

class TestFirstRunSampleTrack(unittest.TestCase):
    def test_sample_files_exist_and_valid(self):
        self.assertTrue(SAMPLE_DIR.is_dir(), f"Directory {SAMPLE_DIR} should exist")
        self.assertTrue(SAMPLE_TRACK_FILE.is_file(), f"Sample track {SAMPLE_TRACK_FILE} should exist")
        self.assertTrue(SAMPLE_COVER_FILE.is_file(), f"Sample cover {SAMPLE_COVER_FILE} should exist")

        track_size = SAMPLE_TRACK_FILE.stat().st_size
        cover_size = SAMPLE_COVER_FILE.stat().st_size

        self.assertGreater(track_size, 50 * 1024 * 1024, "FLAC audio file should be high-res / substantial (>50MB)")
        self.assertGreater(cover_size, 100 * 1024, "PNG cover file should be high resolution (>100KB)")

    def test_first_run_preload_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_config = Path(tmp_dir) / "mix-manager"
            fake_config.mkdir(parents=True, exist_ok=True)

            flag_file = fake_config / ".first_run_sample_loaded"
            prevent_autoplay = fake_config / ".first_run_sample_prevent_autoplay"
            resume_file = fake_config / "playback_resume.json"
            state_file = fake_config / "mp_player_state.json"

            with patch("scripts.liquid_glass_reward.CONFIG_DIR", fake_config), \
                 patch("scripts.liquid_glass_reward.SAMPLE_FLAG_FILE", flag_file), \
                 patch("scripts.liquid_glass_reward.PREVENT_AUTOPLAY_FILE", prevent_autoplay):

                # 1. Initial run: clean environment
                self.assertFalse(flag_file.exists())
                success = setup_first_run_sample_track(force=False)
                self.assertTrue(success, "Initial setup should succeed")
                self.assertTrue(flag_file.exists(), "Flag file should be created")
                self.assertTrue(prevent_autoplay.exists(), "Autoplay prevention marker should be created")
                self.assertTrue(resume_file.is_file(), "playback_resume.json should be written")
                self.assertTrue(state_file.is_file(), "mp_player_state.json should be written")

                # Verify resume content
                res_data = json.loads(resume_file.read_text(encoding="utf-8"))
                self.assertEqual(res_data["position_sec"], 0.0)
                self.assertEqual(res_data["title"], SAMPLE_TRACK_NAME)
                self.assertIn("MPlanetarian - Ecology of the Earth", res_data["path"])

                # Verify state content
                st_data = json.loads(state_file.read_text(encoding="utf-8"))
                self.assertEqual(st_data["state"], "stopped")
                self.assertEqual(st_data["position_sec"], 0.0)
                self.assertEqual(st_data["position_fmt"], "00:00")
                self.assertEqual(st_data["duration_fmt"], "16:54")

                # 2. Simulate user switching to another mix
                custom_resume = {
                    "path": "/some/custom/user/mix.flac",
                    "position_sec": 420.0,
                    "duration_sec": 3600.0,
                    "title": "My Custom DJ Mix",
                }
                resume_file.write_text(json.dumps(custom_resume), encoding="utf-8")

                # 3. Subsequent run: must NOT overwrite user state
                subsequent = setup_first_run_sample_track(force=False)
                self.assertFalse(subsequent, "Subsequent run should return False (already loaded)")

                rechecked_resume = json.loads(resume_file.read_text(encoding="utf-8"))
                self.assertEqual(rechecked_resume["title"], "My Custom DJ Mix", "User resume state must NOT be overwritten")
                self.assertEqual(rechecked_resume["position_sec"], 420.0)

if __name__ == "__main__":
    unittest.main()
