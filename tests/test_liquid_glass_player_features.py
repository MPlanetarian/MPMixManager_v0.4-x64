#!/usr/bin/env python3
"""
Unit tests for Liquid Glass Player Features:
1. Double-click top bezel to toggle maximize / restore to default size.
2. Mode transitions between NORMAL, MINI, and MICRO in Liquid Glass (both Vulkan and OpenGL hosts).
3. In-process 'm'/'M' key handling when MP_LIQUID_GLASS=1.
4. Correct panel geometry computation for NORMAL, MINI, and MICRO modes.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
import MP_Audio_Player_Liquid_Glass as lg_vulkan
import MP_Audio_Player_Liquid_Glass_OpenGL as lg_opengl


class TestLiquidGlassPlayerFeatures(unittest.TestCase):
    def test_player_panel_rects_modes(self):
        """Verifies player_panel_rects produces appropriate rects for NORMAL, MINI, and MICRO."""
        for mod in (lg_vulkan, lg_opengl):
            r_norm = mod.player_panel_rects(80, 24, 9, 18, 14, 14, mode="NORMAL")
            self.assertEqual(len(r_norm), 2, f"{mod.__name__} NORMAL should return 2 panel rects")
            self.assertGreater(r_norm[0][2], 0)
            self.assertGreater(r_norm[1][2], 0)

            r_mini = mod.player_panel_rects(74, 14, 9, 18, 14, 14, mode="MINI")
            self.assertEqual(len(r_mini), 2, f"{mod.__name__} MINI should return 2 panel rects")

            r_micro = mod.player_panel_rects(74, 7, 9, 18, 14, 14, mode="MICRO")
            self.assertEqual(len(r_micro), 2, f"{mod.__name__} MICRO should return 2 panel rects (second empty)")
            self.assertEqual(r_micro[1], (0.0, 0.0, 0.0, 0.0))

    def test_on_top_bezel_detection(self):
        """Verifies _on_top_bezel accurately identifies clicks within the top window bezel."""
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost.__new__(mod.GlassHost)
            host.renderer = MagicMock()
            host.renderer.bezel_px = 14

            # Within top bezel
            self.assertTrue(host._on_top_bezel(100, 5, 800, 600))
            self.assertTrue(host._on_top_bezel(400, 13, 800, 600))

            # Close button area is excluded from top bezel drag
            self.assertFalse(host._on_top_bezel(800 - int(14 * 0.72), int(14 * 0.62), 800, 600))

            # Outside top bezel (lower in client area)
            self.assertFalse(host._on_top_bezel(100, 100, 800, 600))

    def test_toggle_maximize_restore(self):
        """Verifies toggle_maximize maximizes to monitor workarea and restores to original dimensions."""
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost.__new__(mod.GlassHost)
            host.is_maximized = False
            host.mode = "NORMAL"
            host._saved_rect = None
            host.terminal = MagicMock()
            host.terminal.get_char_width.return_value = 9
            host.terminal.get_char_height.return_value = 18

            host.renderer = MagicMock()
            host.renderer.bezel_px = 14
            host.renderer.window_pos.return_value = (100, 100)
            host.renderer.window_size.return_value = (900, 600)
            host.renderer.get_workarea.return_value = (0, 0, 1920, 1080)
            host._place_terminal = MagicMock()

            # 1. First toggle: should maximize
            host.toggle_maximize()
            self.assertTrue(host.is_maximized)
            self.assertEqual(host._saved_rect, ((100, 100), (900, 600)))
            host.renderer.set_window_pos.assert_called_with(0, 0)
            host.renderer.set_window_size.assert_called_with(1920, 1080)

            # 2. Second toggle: should restore
            host.toggle_maximize()
            self.assertFalse(host.is_maximized)
            host.renderer.set_window_pos.assert_called_with(100, 100)

    def test_set_mode_resizing(self):
        """Verifies set_mode updates mode and resizes window / terminal for NORMAL, MINI, and MICRO."""
        for mod in (lg_vulkan, lg_opengl):
            host = mod.GlassHost.__new__(mod.GlassHost)
            host.mode = "NORMAL"
            host.is_maximized = False
            host.terminal = MagicMock()
            host.terminal.get_char_width.return_value = 9
            host.terminal.get_char_height.return_value = 18

            host.renderer = MagicMock()
            host.renderer.bezel_px = 14
            host.renderer.set_panels = MagicMock()
            host.renderer.set_window_size = MagicMock()
            host._place_terminal = MagicMock()

            # Switch to MINI
            host.set_mode("MINI")
            self.assertEqual(host.mode, "MINI")
            host.terminal.set_size.assert_called_with(74, 14)

            # Switch to MICRO
            host.set_mode("MICRO")
            self.assertEqual(host.mode, "MICRO")
            host.terminal.set_size.assert_called_with(74, 7)

            # Switch back to NORMAL
            host.set_mode("NORMAL")
            self.assertEqual(host.mode, "NORMAL")
            host.terminal.set_size.assert_called_with(mod.COLS, mod.ROWS)

    def test_audio_player_m_key_inside_liquid_glass(self):
        """Verifies pressing 'm'/'M' inside Liquid Glass cycles mode in-place without spawning external window."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = []
        ui = MP_Audio_Player.TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="NORMAL",
            is_remote=True
        )

        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch("MP_Audio_Player.launch_mini_player_window") as mock_launch:
            # Press 'm': NORMAL -> MINI
            ui._process_key(b"m")
            self.assertEqual(ui.ui_size_mode, "MINI")
            mock_launch.assert_not_called()

            # Press 'm': MINI -> MICRO
            ui._process_key(b"m")
            self.assertEqual(ui.ui_size_mode, "MICRO")
            mock_launch.assert_not_called()

            # Press 'm': MICRO -> NORMAL
            ui._process_key(b"m")
            self.assertEqual(ui.ui_size_mode, "NORMAL")
            mock_launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
