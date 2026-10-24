#!/usr/bin/env python3
"""
Unit tests for MP Audio Player Playlist theme highlighting:
- EqualizerVisualizer.get_theme_palette() provides theme-matched highlight, active, border, and accent colors.
- Playlist row selection and active playing indicator dynamically match the active theme.
- Traffic light green is not hardcoded into playlist row selection in dreamworlds_ultra and other themes.
"""

import unittest
import sys
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
from MP_Audio_Player import (
    EqualizerVisualizer,
    TerminalPlayerUI,
    COLOR_HOT_PURPLE,
    COLOR_NEON_PINK,
    COLOR_ELECTRIC_CYAN,
    COLOR_TRAFFIC_GREEN,
)


class TestPlaylistThemeHighlight(unittest.TestCase):
    def test_theme_palette_mapping(self):
        """Verifies that get_theme_palette returns correct theme-specific palettes."""
        viz = EqualizerVisualizer(theme="dreamworlds_ultra")
        pal = viz.get_theme_palette()
        self.assertEqual(pal["highlight"], COLOR_HOT_PURPLE)
        self.assertEqual(pal["active"], COLOR_NEON_PINK)
        self.assertEqual(pal["border"], COLOR_HOT_PURPLE)

        # cosmic_supernova
        viz.theme = "cosmic_supernova"
        pal_cosmic = viz.get_theme_palette()
        self.assertIn("224;86;253", pal_cosmic["highlight"])
        self.assertIn("0;245;212", pal_cosmic["active"])

        # retro_studio
        viz.theme = "retro_studio"
        pal_retro = viz.get_theme_palette()
        self.assertIn("241;196;15", pal_retro["highlight"])

        # cyber_neon
        viz.theme = "cyber_neon"
        pal_cyber = viz.get_theme_palette()
        self.assertIn("76;201;240", pal_cyber["highlight"])

        # ice_cold
        viz.theme = "ice_cold"
        pal_ice = viz.get_theme_palette()
        self.assertIn("0;229;255", pal_ice["highlight"])

    def test_theme_aliases_resolution(self):
        """Verifies that theme aliases from Mix Archive Manager resolve properly."""
        viz_nord = EqualizerVisualizer(theme="nord")
        self.assertEqual(viz_nord.theme, "ice_cold")

        viz_dracula = EqualizerVisualizer(theme="dracula")
        self.assertEqual(viz_dracula.theme, "dreamworlds_neon")

        viz_cyberpunk = EqualizerVisualizer(theme="cyberpunk")
        self.assertEqual(viz_cyberpunk.theme, "cyber_neon")

        viz_matrix = EqualizerVisualizer(theme="matrix")
        self.assertEqual(viz_matrix.theme, "phosphor")

        viz_default = EqualizerVisualizer(theme="dreamworlds")
        self.assertEqual(viz_default.theme, "dreamworlds_ultra")

    def test_playlist_rendering_uses_theme_colors(self):
        """Verifies that playlist selection row does not use hardcoded traffic green in dreamworlds_ultra."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Mix 01 - Astral Projection", "path": "/path/to/mix1.mp3", "folder": "Chill"},
            {"name": "Mix 02 - Solar Eclipse", "path": "/path/to/mix2.mp3", "folder": "Trance"},
        ]
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="STANDARD",
            is_remote=True
        )
        ui.visualizer.theme = "dreamworlds_ultra"
        ui.selected_row = 0

        st = {
            "title": "Mix 01 - Astral Projection",
            "path": "/path/to/mix1.mp3",
            "state": "playing",
            "index": 0,
            "position_sec": 120,
            "duration_sec": 3600,
            "position_fmt": "02:00",
            "duration_fmt": "60:00",
            "progress_pct": 3.3,
            "volume": 80,
            "pitch_percent": 0,
            "levels": [0.5] * 24,
            "peaks": [0.7] * 24,
            "levels_left": [0.5] * 24,
            "levels_right": [0.5] * 24,
            "peaks_left": [0.7] * 24,
            "peaks_right": [0.7] * 24,
            "rms_level": 0.1,
            "peak_db": -3.0
        }

        captured_lines = []
        with patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured_lines.extend(lines)), \
             patch("MP_Audio_Player._win_visible_size", return_value=(100, 35)):
            ui._get_status = MagicMock(return_value=st)
            ui._draw_frame()

        selected_lines = [l for l in captured_lines if "│" in l and "Mix 01 - Astral Projection" in l]
        self.assertTrue(len(selected_lines) > 0, "Selected playlist row not found in rendered frame")
        sel_line = selected_lines[0]

        # The selected row highlight must contain COLOR_HOT_PURPLE
        self.assertIn(COLOR_HOT_PURPLE, sel_line)
        # The selected row highlight must NOT contain COLOR_TRAFFIC_GREEN
        self.assertNotIn(COLOR_TRAFFIC_GREEN, sel_line)

    def test_active_track_separate_cursor(self):
        """Verifies that when cursor is on track 0 and playing track is track 1, active track uses theme active color."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Mix 01 - Astral Projection", "path": "/path/to/mix1.mp3", "folder": "Chill"},
            {"name": "Mix 02 - Solar Eclipse", "path": "/path/to/mix2.mp3", "folder": "Trance"},
        ]
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="STANDARD",
            is_remote=True
        )
        ui.visualizer.theme = "dreamworlds_ultra"
        ui._last_path = "/path/to/mix2.mp3"
        ui.selected_row = 0  # Cursor on track 0

        st = {
            "title": "Mix 02 - Solar Eclipse",
            "path": "/path/to/mix2.mp3",
            "state": "playing",
            "index": 1,  # Playing track is track 1
            "position_sec": 120,
            "duration_sec": 3600,
            "position_fmt": "02:00",
            "duration_fmt": "60:00",
            "progress_pct": 3.3,
            "volume": 80,
            "pitch_percent": 0,
            "levels": [0.5] * 24,
            "peaks": [0.7] * 24,
            "levels_left": [0.5] * 24,
            "levels_right": [0.5] * 24,
            "peaks_left": [0.7] * 24,
            "peaks_right": [0.7] * 24,
            "rms_level": 0.1,
            "peak_db": -3.0
        }

        captured_lines = []
        with patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured_lines.extend(lines)), \
             patch("MP_Audio_Player._win_visible_size", return_value=(100, 35)):
            ui._get_status = MagicMock(return_value=st)
            ui._draw_frame()

        active_lines = [l for l in captured_lines if "│" in l and "Mix 02 - Solar Eclipse" in l]
        self.assertTrue(len(active_lines) > 0, "Active playlist row not found in rendered frame")
        act_line = active_lines[0]

        # Active playing track should use COLOR_NEON_PINK in dreamworlds_ultra
        self.assertIn(COLOR_NEON_PINK, act_line)
        self.assertNotIn(COLOR_TRAFFIC_GREEN, act_line)

    def test_dreamworlds_liquid_theme_and_aliases(self):
        """Verifies dreamworlds_liquid theme, aliases, and palette."""
        for alias in ("dreamworlds_liquid", "mp_dreamworlds_liquid_transparency", "liquid_transparency", "liquid", "glass"):
            viz = EqualizerVisualizer(theme=alias)
            self.assertEqual(viz.theme, "dreamworlds_liquid", f"Alias {alias} failed to resolve to dreamworlds_liquid")

        viz = EqualizerVisualizer(theme="dreamworlds_liquid")
        pal = viz.get_theme_palette()
        self.assertIn("0;245;255", pal["highlight"])
        self.assertIn("199;125;255", pal["active"])
        self.assertIn("72;149;239", pal["border"])
        self.assertIn("0;245;212", pal["accent"])
        self.assertEqual(viz.b_col, f"\033[1m{pal['border']}")

    def test_top_panels_and_playlist_border_color_matching(self):
        """Verifies top title banner box, visualizer box, and playlist box borders all match theme border."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Mix 01 - Astral Projection", "path": "/path/to/mix1.mp3", "folder": "Chill"},
        ]
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="STANDARD",
            is_remote=True
        )

        st = {
            "title": "Mix 01 - Astral Projection",
            "path": "/path/to/mix1.mp3",
            "state": "playing",
            "index": 0,
            "position_sec": 120,
            "duration_sec": 3600,
            "position_fmt": "02:00",
            "duration_fmt": "60:00",
            "progress_pct": 3.3,
            "volume": 80,
            "pitch_percent": 0,
            "levels": [0.5] * 24,
            "peaks": [0.7] * 24,
            "levels_left": [0.5] * 24,
            "levels_right": [0.5] * 24,
            "peaks_left": [0.7] * 24,
            "peaks_right": [0.7] * 24,
            "rms_level": 0.1,
            "peak_db": -3.0
        }

        for test_theme in ("dreamworlds_liquid", "cosmic_supernova", "dracula", "ice_cold"):
            ui.visualizer.theme = test_theme
            b_col = ui.visualizer.b_col
            captured_lines = []
            with patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured_lines.extend(lines)), \
                 patch("MP_Audio_Player._win_visible_size", return_value=(100, 35)):
                ui._get_status = MagicMock(return_value=st)
                ui._draw_frame()

            # 1. Top banner header box top line (starts with ╭)
            banner_top = [l for l in captured_lines if "╭" in l and "MP AUDIO PLAYER" not in l and "LEFT" not in l]
            self.assertTrue(len(banner_top) > 0, "Top title banner box top line not found")
            self.assertIn(b_col, banner_top[0], f"Banner top border does not use theme b_col for theme {test_theme}")

            # 2. Visualizer box top line (starts with ╭── LEFT or ╭── HIGH-RESOLUTION)
            vis_top = [l for l in captured_lines if "╭" in l and ("LEFT" in l or "HIGH-RESOLUTION" in l or "SPECTRUM" in l)]
            self.assertTrue(len(vis_top) > 0, "Visualizer box top line not found")
            self.assertIn(b_col, vis_top[0], f"Visualizer box top line does not use theme b_col for theme {test_theme}")

            # 3. Playlist box top line (starts with ┌── MP MIX ARCHIVE)
            pl_top = [l for l in captured_lines if "┌" in l and "MP MIX ARCHIVE" in l]
            self.assertTrue(len(pl_top) > 0, "Playlist box top line not found")
            self.assertIn(b_col, pl_top[0], f"Playlist box top line does not use theme b_col for theme {test_theme}")


if __name__ == "__main__":
    unittest.main()
