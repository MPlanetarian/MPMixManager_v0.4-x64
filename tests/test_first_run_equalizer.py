#!/usr/bin/env python3
"""
Unit tests to verify MP Mix Manager's MP Audio Player equalizer gets set to Flat on first load:
1. EqualizerManager initializes preset to Flat (0 dB on all bands) and creates .first_run_eq_initialized.
2. python MP_Audio_Player.py --reset-eq sets the active preset to Flat (0 dB) and updates both state files.
3. setup_first_run_equalizer() in scripts/liquid_glass_reward.py runs --reset-eq and respects the first-run flag.
4. Mix_Archive_Manager.sh includes ensure_first_run_equalizer and calls it at startup.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
from scripts.liquid_glass_reward import setup_first_run_equalizer


class TestFirstRunEqualizer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.preset_file = self.temp_path / "eq_preset"
        self.custom_file = self.temp_path / "custom_eq_presets.json"
        self.bands_file = self.temp_path / "eq_active_bands.json"
        self.flag_file = self.temp_path / ".first_run_eq_initialized"

        self.patches = [
            patch.object(MP_Audio_Player, "CONFIG_DIR", self.temp_path),
            patch.object(MP_Audio_Player, "EQ_PRESET_FILE", self.preset_file),
            patch.object(MP_Audio_Player, "EQ_CUSTOM_FILE", self.custom_file),
            patch.object(MP_Audio_Player, "EQ_ACTIVE_BANDS_FILE", self.bands_file),
            patch.object(MP_Audio_Player, "EQ_INIT_FLAG_FILE", self.flag_file),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp_dir.cleanup()

    def test_first_run_equalizer_manager_initializes_flat(self):
        """On fresh load without existing config, EqualizerManager enforces Flat preset."""
        self.assertFalse(self.flag_file.exists())
        self.assertFalse(self.preset_file.exists())
        self.assertFalse(self.bands_file.exists())

        mgr = MP_Audio_Player.EqualizerManager()
        self.assertEqual(mgr.active_preset, "Flat")
        self.assertTrue(mgr.is_flat())
        self.assertEqual(mgr.get_current_bands(), [0.0] * 10)

        # Verified files created on disk
        self.assertTrue(self.flag_file.exists(), ".first_run_eq_initialized flag should be created")
        self.assertTrue(self.preset_file.is_file(), "eq_preset should be created")
        self.assertEqual(self.preset_file.read_text(encoding="utf-8").strip(), "Flat")
        self.assertTrue(self.bands_file.is_file(), "eq_active_bands.json should be created")
        self.assertEqual(json.loads(self.bands_file.read_text(encoding="utf-8")), [0.0] * 10)

    def test_reset_eq_command_line_execution(self):
        """python MP_Audio_Player.py --reset-eq resets equalizer to Flat and creates flag."""
        with tempfile.TemporaryDirectory() as env_tmp:
            fake_config = Path(env_tmp) / ".config" / "mix-manager"
            fake_config.mkdir(parents=True, exist_ok=True)
            preset_f = fake_config / "eq_preset"
            bands_f = fake_config / "eq_active_bands.json"
            flag_f = fake_config / ".first_run_eq_initialized"

            # Pre-populate with a non-flat preset
            preset_f.write_text("Trance", encoding="utf-8")
            bands_f.write_text(json.dumps([4.0, 5.0, 2.0, -1.5, 0.0, 1.5, 2.5, 3.5, 4.0, 3.0]), encoding="utf-8")

            res = subprocess.run(
                [sys.executable, str(BASE_DIR / "MP_Audio_Player.py"), "--reset-eq"],
                env={**dict(subprocess.os.environ), "HOME": env_tmp},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("Equalizer reset to Flat (0 dB)", res.stdout)
            self.assertTrue(flag_f.exists(), "Flag should exist after running --reset-eq")
            self.assertEqual(preset_f.read_text(encoding="utf-8").strip(), "Flat")
            self.assertEqual(json.loads(bands_f.read_text(encoding="utf-8")), [0.0] * 10)

    def test_setup_first_run_equalizer_in_reward_script(self):
        """Verifies setup_first_run_equalizer helper in liquid_glass_reward.py."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_config = Path(tmp_dir) / "mix-manager"
            fake_config.mkdir(parents=True, exist_ok=True)
            flag_f = fake_config / ".first_run_eq_initialized"

            with patch("scripts.liquid_glass_reward.CONFIG_DIR", fake_config):
                # 1. First run should execute and return True
                self.assertFalse(flag_f.exists())
                success = setup_first_run_equalizer(force=False)
                self.assertTrue(success)
                self.assertTrue(flag_f.exists())

                # 2. Subsequent run without force should return False
                second = setup_first_run_equalizer(force=False)
                self.assertFalse(second)

                # 3. Forcing run should return True
                forced = setup_first_run_equalizer(force=True)
                self.assertTrue(forced)

    def test_mix_archive_manager_has_ensure_first_run_equalizer(self):
        """Verifies Mix_Archive_Manager.sh defines ensure_first_run_equalizer and calls it at startup."""
        mgr_sh = BASE_DIR / "Mix_Archive_Manager.sh"
        self.assertTrue(mgr_sh.is_file())
        content = mgr_sh.read_text(encoding="utf-8")

        self.assertIn("ensure_first_run_equalizer()", content)
        self.assertIn("--reset-eq", content)
        self.assertIn(".first_run_eq_initialized", content)
        self.assertIn("ensure_first_run_equalizer\nensure_first_run_sample_track", content)


if __name__ == "__main__":
    unittest.main()
