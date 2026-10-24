#!/usr/bin/env python3
"""
Unit tests for MP Audio Player 10-Band Graphic Equalizer:
- Built-in genre presets: Flat, Ambient, Trance, Techno, House, Progressive, Vapourwave
- Default is Flat (0 dB)
- EqualizerManager preset loading, resolution, and aliases
- Manual slider adjustment and clamping (-12 dB to +12 dB)
- Custom preset creation, saving, and deletion
- EqualizerFilter DSP frequency-domain processing
- Interactive UI Equalizer HUD controls, keys, and rendering
- IPC and CLI equalizer command handling
"""

import unittest
import sys
import os
import json
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player


class TestEqualizerPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        # Patch CONFIG_DIR to isolated temporary directory
        self.config_dir_patch = patch.object(MP_Audio_Player, "CONFIG_DIR", self.temp_path)
        self.preset_file_patch = patch.object(MP_Audio_Player, "EQ_PRESET_FILE", self.temp_path / "eq_preset")
        self.custom_file_patch = patch.object(MP_Audio_Player, "EQ_CUSTOM_FILE", self.temp_path / "custom_eq_presets.json")
        self.bands_file_patch = patch.object(MP_Audio_Player, "EQ_ACTIVE_BANDS_FILE", self.temp_path / "eq_active_bands.json")

        self.config_dir_patch.start()
        self.preset_file_patch.start()
        self.custom_file_patch.start()
        self.bands_file_patch.start()

    def tearDown(self):
        self.bands_file_patch.stop()
        self.custom_file_patch.stop()
        self.preset_file_patch.stop()
        self.config_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_default_presets_defined(self):
        """Verifies that all requested presets (Flat, Ambient, Trance, Techno, House, Progressive, Vapourwave) are defined."""
        presets = MP_Audio_Player.DEFAULT_EQ_PRESETS
        expected = ["Flat", "Ambient", "Trance", "Techno", "House", "Progressive", "Vapourwave"]
        for exp in expected:
            self.assertIn(exp, presets, f"Preset '{exp}' must be present in DEFAULT_EQ_PRESETS")
            self.assertEqual(len(presets[exp]), 10, f"Preset '{exp}' must have exactly 10 bands")

        # Flat must be 0 dB across all bands
        self.assertTrue(all(g == 0.0 for g in presets["Flat"]))

        # Non-flat presets must have characteristic curves
        self.assertGreater(presets["Techno"][0], 0.0)  # sub-bass boost in techno
        self.assertGreater(presets["Trance"][1], 0.0)  # bass punch in trance
        self.assertLess(presets["Vapourwave"][9], 0.0)  # lo-fi tape high-frequency roll-off

    def test_equalizer_manager_initial_flat_default(self):
        """Verifies that EqualizerManager defaults to Flat preset and is_flat returns True."""
        mgr = MP_Audio_Player.EqualizerManager()
        self.assertEqual(mgr.active_preset, "Flat")
        self.assertTrue(mgr.is_flat())
        self.assertEqual(mgr.get_current_bands(), [0.0] * 10)

    def test_equalizer_manager_apply_presets_and_aliases(self):
        """Verifies applying presets by name and alias (e.g. vaporwave -> Vapourwave)."""
        mgr = MP_Audio_Player.EqualizerManager()

        self.assertTrue(mgr.apply_preset("Ambient"))
        self.assertEqual(mgr.active_preset, "Ambient")
        self.assertFalse(mgr.is_flat())
        self.assertEqual(mgr.get_current_bands(), MP_Audio_Player.DEFAULT_EQ_PRESETS["Ambient"])

        # Test US spelling alias
        self.assertTrue(mgr.apply_preset("vaporwave"))
        self.assertEqual(mgr.active_preset, "Vapourwave")
        self.assertEqual(mgr.get_current_bands(), MP_Audio_Player.DEFAULT_EQ_PRESETS["Vapourwave"])

        # Test Progressive alias
        self.assertTrue(mgr.apply_preset("prog"))
        self.assertEqual(mgr.active_preset, "Progressive")

        # Reset to Flat
        self.assertTrue(mgr.apply_preset("Flat"))
        self.assertEqual(mgr.active_preset, "Flat")
        self.assertTrue(mgr.is_flat())

    def test_manual_slider_setting_and_clamping(self):
        """Verifies that setting a band manually updates gain, clamps to [-12, +12], and sets preset to Custom."""
        mgr = MP_Audio_Player.EqualizerManager()
        mgr.apply_preset("Trance")

        # Adjust band 0 (31Hz)
        mgr.set_band(0, 15.0)  # Above max
        self.assertEqual(mgr.current_bands[0], 12.0)
        self.assertEqual(mgr.active_preset, "Custom")

        mgr.set_band(0, -20.0)  # Below min
        self.assertEqual(mgr.current_bands[0], -12.0)

        # Step adjustment
        mgr.set_band(0, 0.0)
        mgr.set_band(0, 1.5, step=True)
        self.assertEqual(mgr.current_bands[0], 1.5)

    def test_save_and_delete_custom_preset(self):
        """Verifies user can save their current slider values as a custom preset and delete it."""
        mgr = MP_Audio_Player.EqualizerManager()
        custom_gains = [2.0, 3.0, 1.0, 0.0, -1.0, 0.0, 1.0, 2.0, 3.0, 1.5]
        mgr.set_bands(custom_gains)

        # Save custom preset
        self.assertTrue(mgr.save_custom_preset("Club Punch", custom_gains))
        self.assertEqual(mgr.active_preset, "Club Punch")
        self.assertIn("Club Punch", mgr.get_all_presets())
        self.assertIn("Club Punch", mgr.get_all_preset_names())

        # Test persistence: load a new EqualizerManager instance from disk
        mgr2 = MP_Audio_Player.EqualizerManager()
        self.assertIn("Club Punch", mgr2.get_all_presets())
        self.assertEqual(mgr2.active_preset, "Club Punch")
        self.assertEqual(mgr2.get_current_bands(), custom_gains)

        # Delete custom preset
        self.assertTrue(mgr2.delete_custom_preset("Club Punch"))
        self.assertNotIn("Club Punch", mgr2.get_all_presets())
        self.assertEqual(mgr2.active_preset, "Flat")

    def test_equalizer_filter_dsp_passthrough_when_flat(self):
        """Verifies EqualizerFilter is identity when Flat (is_flat == True)."""
        eq_filter = MP_Audio_Player.EqualizerFilter()
        eq_filter.set_gains([0.0] * 10, sr=44100)
        self.assertTrue(eq_filter.is_flat)

        chunk = np.random.randn(1024, 2).astype(np.float32)
        out = eq_filter.process(chunk)
        np.testing.assert_array_equal(out, chunk)

    def test_equalizer_filter_dsp_processes_non_flat_audio(self):
        """Verifies EqualizerFilter applies DSP filtering without NaN or clipping explosion."""
        eq_filter = MP_Audio_Player.EqualizerFilter()
        techno_gains = MP_Audio_Player.DEFAULT_EQ_PRESETS["Techno"]
        eq_filter.set_gains(techno_gains, sr=44100)
        self.assertFalse(eq_filter.is_flat)

        for _ in range(5):
            chunk = np.random.uniform(-0.5, 0.5, (1024, 2)).astype(np.float32)
            out = eq_filter.process(chunk)
            self.assertEqual(out.shape, (1024, 2))
            self.assertFalse(np.isnan(out).any())
            self.assertFalse(np.isinf(out).any())
            self.assertTrue(np.all(out >= -1.0) and np.all(out <= 1.0))

    def test_terminal_ui_key_E_toggles_equalizer_hud(self):
        """Verifies pressing 'E' in normal mode toggles Equalizer HUD."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True
        )
        self.assertFalse(ui.equalizer_hud_active)

        # Press 'E' to open HUD
        ui._process_key(b"E")
        self.assertTrue(ui.equalizer_hud_active)

        # Press 'E' to close HUD
        ui._process_key(b"E")
        self.assertFalse(ui.equalizer_hud_active)

    def test_terminal_ui_slider_navigation_and_presets(self):
        """Verifies Left/Right band navigation, Up/Down slider movement, and preset cycling in EQ HUD."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True
        )
        ui.equalizer_hud_active = True
        ui.eq_selected_band = 0

        # Move right
        ui._process_key(b"\x1b[C")  # Right arrow
        self.assertEqual(ui.eq_selected_band, 1)

        # Move up slider (+0.5 dB)
        initial_val = ui.eq_manager.current_bands[1]
        ui._process_key(b"\x1b[A")  # Up arrow
        self.assertEqual(ui.eq_manager.current_bands[1], round(initial_val + 0.5, 1))

        # Direct number preset jump: '3' for Trance
        ui._process_key(b"3")
        self.assertEqual(ui.eq_manager.active_preset, "Trance")

        # '1' for Flat
        ui._process_key(b"1")
        self.assertEqual(ui.eq_manager.active_preset, "Flat")
        self.assertTrue(ui.eq_manager.is_flat())

    def test_terminal_ui_custom_preset_naming(self):
        """Verifies pressing 'S' opens naming mode and Enter saves custom preset."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True
        )
        ui.equalizer_hud_active = True

        # Press 's' to save
        ui._process_key(b"s")
        self.assertTrue(ui.eq_naming_mode)

        # Type name 'MyBass'
        for ch in b"MyBass":
            ui._process_key(bytes([ch]))
        self.assertEqual(ui.eq_custom_name_input, "MyBass")

        # Press Enter to submit
        ui._process_key(b"\r")
        self.assertFalse(ui.eq_naming_mode)
        self.assertEqual(ui.eq_manager.active_preset, "MyBass")
        self.assertIn("MyBass", ui.eq_manager.custom_presets)

    def test_render_equalizer_hud_produces_valid_output(self):
        """Verifies _render_equalizer_hud outputs valid lines with sliders, scale, and presets."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True
        )
        ui.eq_manager.apply_preset("Ambient")
        lines = ui._render_equalizer_hud(st={"title": "Test"}, iw=90, h=28)
        rendered_text = "\n".join(lines)

        self.assertIn("10-BAND STEREO GRAPHIC EQUALIZER", rendered_text)
        self.assertIn("Ambient", rendered_text)
        self.assertIn("31Hz", rendered_text)
        self.assertIn("16kHz", rendered_text)
        self.assertIn("0 dB", rendered_text)


if __name__ == "__main__":
    unittest.main()
