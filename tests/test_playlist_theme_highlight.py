#!/usr/bin/env python3
"""
Unit tests for MP Audio Player Playlist theme highlighting:
- EqualizerVisualizer.get_theme_palette() provides theme-matched highlight, active, border, and accent colors.
- Playlist row selection and active playing indicator dynamically match the active theme.
- Traffic light green is not hardcoded into playlist row selection in dreamworlds_ultra and other themes.
"""

import unittest
import sys
import os
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

            # 2. Visualizer box top line (starts with ╭── LEFT or ╭── HIGH-RESOLUTION or ╭── 🌊 STREAM)
            vis_top = [l for l in captured_lines if "╭" in l and ("LEFT" in l or "HIGH-RESOLUTION" in l or "SPECTRUM" in l or "STREAM" in l)]
            self.assertTrue(len(vis_top) > 0, "Visualizer box top line not found")
            self.assertIn(b_col, vis_top[0], f"Visualizer box top line does not use theme b_col for theme {test_theme}")

            # 3. Playlist box top line (starts with ┌── MP MIX ARCHIVE)
            pl_top = [l for l in captured_lines if "┌" in l and "MP MIX ARCHIVE" in l]
            self.assertTrue(len(pl_top) > 0, "Playlist box top line not found")
            self.assertIn(b_col, pl_top[0], f"Playlist box top line does not use theme b_col for theme {test_theme}")

    def test_liquid_header_side_bars_match_panel_edge(self):
        """Header left and right bars use the border colour on every row, including the subtitle."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Mix 01 - Astral Projection", "path": "/path/to/mix1.mp3", "folder": "Chill"},
        ]
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="STANDARD",
            is_remote=True,
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
            "peak_db": -3.0,
        }
        ansi = re.compile(r"\x1b\[[0-9;]*m")

        def colors_at(line, glyphs):
            active = ""
            found = []
            i = 0
            while i < len(line):
                match = ansi.match(line, i)
                if match:
                    code = match.group(0)
                    active = "" if code == "\x1b[0m" else active + code
                    i = match.end()
                    continue
                if line[i] in glyphs:
                    found.append((line[i], active))
                i += 1
            return found

        for test_theme in ("retro_linux_memories", "dreamworlds_liquid", "retro_studio"):
            ui.visualizer.theme = test_theme
            pal = ui.visualizer.get_theme_palette()
            border = pal["border"]
            accent = pal["accent"]
            captured_lines = []
            with patch.dict("os.environ", {"MP_LIQUID_GLASS": "1"}), \
                 patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured_lines.extend(lines)), \
                 patch("MP_Audio_Player._win_visible_size", return_value=(100, 35)):
                ui._get_status = MagicMock(return_value=st)
                ui._draw_frame()

            sub_idx = next(i for i, line in enumerate(captured_lines) if "Fluid Audio Navigation" in line)
            header = captured_lines[sub_idx - 2:sub_idx + 2]
            self.assertEqual(len(header), 4, f"Header panel was not four rows for {test_theme}")
            edge_colors = []
            for line in header:
                edge_colors.extend(color for glyph, color in colors_at(line, "│╭╮╰╯─"))
            self.assertGreaterEqual(len(edge_colors), 6, f"Header edge glyphs missing for {test_theme}")
            for color in edge_colors:
                self.assertEqual(color, border, f"Header edge {color!r} is not border {border!r} for {test_theme}")
                if accent != border:
                    self.assertNotIn(accent, color)
            self.assertIn(accent, header[2], f"Subtitle text lost the accent colour for {test_theme}")
            side_bars = [color for glyph, color in colors_at(header[2], "│")]
            self.assertEqual(side_bars, [border, border], f"Subtitle side bars differ for {test_theme}")

    def test_liquid_playlist_edge_matches_panel_colour(self):
        """The playlist box, including the clipped bottom-right corner, uses the theme border."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": f"Mix {i:02d} - Astral Projection", "path": f"/path/to/mix{i}.mp3", "folder": "Chill", "ext": "FLAC", "size_mb": 80 + i}
            for i in range(12)
        ]
        ui = TerminalPlayerUI(
            engine=None,
            scanner=mock_scanner,
            ui_size_mode="STANDARD",
            is_remote=True,
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
            "peak_db": -3.0,
        }
        ansi = re.compile(r"\x1b\[[0-9;]*m")

        def glyph_colors(line):
            active = ""
            found = []
            i = 0
            while i < len(line):
                match = ansi.match(line, i)
                if match:
                    code = match.group(0)
                    active = "" if code == "\033[0m" else active + code
                    i = match.end()
                    continue
                found.append((line[i], active))
                i += 1
            return found

        border = "\033[38;2;84;84;83m"
        clipped = MP_Audio_Player._boxed_rule("└", "── " + ("Scroll • " * 20), "┘", 24, border)
        self.assertEqual(glyph_colors(clipped)[-1], ("┘", border))

        for test_theme in ("retro_linux_memories", "dreamworlds_liquid", "retro_studio"):
            ui.visualizer.theme = test_theme
            border = ui.visualizer.get_theme_palette()["border"]
            captured_lines = []
            with patch.dict("os.environ", {"MP_LIQUID_GLASS": "1"}), \
                 patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured_lines.extend(lines)), \
                 patch("MP_Audio_Player._win_visible_size", return_value=(120, 40)):
                ui._get_status = MagicMock(return_value=st)
                ui._draw_frame()

            top = next(i for i, line in enumerate(captured_lines) if "┌" in line and "PLAYLIST" in line)
            bottom = next(i for i, line in enumerate(captured_lines) if i > top and "┘" in MP_Audio_Player._ANSI_RE.sub("", line))
            panel = captured_lines[top:bottom + 1]
            self.assertGreaterEqual(len(panel), 3, f"Playlist panel was too short for {test_theme}")
            for line in (panel[0], panel[-1]):
                edges = [(glyph, color) for glyph, color in glyph_colors(line) if glyph in "┌┐└┘─│"]
                self.assertGreaterEqual(len(edges), 3, f"Playlist rule lost its edge for {test_theme}")
                for glyph, color in edges:
                    self.assertEqual(color, border, f"Playlist {glyph} is {color!r}, not {border!r}, for {test_theme}")
            self.assertEqual(glyph_colors(panel[-1])[-1], ("┘", border), f"Bottom-right corner differs for {test_theme}")
            for line in panel[1:-1]:
                bars = [color for glyph, color in glyph_colors(line) if glyph == "│"]
                self.assertEqual(bars, [border, border], f"Playlist side bars differ for {test_theme}")

    def test_selected_playlist_row_uses_theme_colour(self):
        """The navigation bar on the selected row follows the active theme.

        It used to be a fixed grey in the console and reverse video in Liquid
        Glass, so the bar looked identical in every theme. Each theme's highlight
        hue has to reach the fill, and the text has to stay legible on it.
        """
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [
            {"name": "Mix 01 - Astral Projection", "path": "/path/to/mix1.mp3", "folder": "Chill"},
            {"name": "Mix 02 - Solar Eclipse", "path": "/path/to/mix2.mp3", "folder": "Trance"},
        ]
        ui = TerminalPlayerUI(engine=None, scanner=mock_scanner, ui_size_mode="STANDARD", is_remote=True)
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
            "peak_db": -3.0,
            "queue_len": 0,
            "queue": [],
        }

        seen = {}
        for light in ("1", ""):
            with patch.dict("os.environ", {"MP_LIQUID_GLASS": light} if light else {}, clear=False):
                if not light:
                    os.environ.pop("MP_LIQUID_GLASS", None)
                for test_theme in ("dreamworlds_ultra", "sensorium_interface", "cosmic_supernova",
                                   "retro_terminal", "stream_of_frequency"):
                    ui.visualizer.theme = test_theme
                    captured_lines = []
                    with patch("MP_Audio_Player._present_frame",
                               side_effect=lambda lines, w, h: captured_lines.extend(lines)), \
                         patch("MP_Audio_Player._win_visible_size", return_value=(120, 40)):
                        ui._get_status = MagicMock(return_value=st)
                        ui._draw_frame()
                    rows = [l for l in captured_lines if "│" in l and "Mix 01 - Astral Projection" in l]
                    self.assertTrue(rows, f"Selected playlist row missing for {test_theme}")
                    row = rows[0]
                    expected_bg, expected_fg = MP_Audio_Player._selection_bar_ansi(test_theme)
                    self.assertIn(expected_bg, row,
                                  f"Selected row is not filled with the {test_theme} theme colour")
                    # Liquid Glass strips the bold attribute, the console keeps it,
                    # so only the colour channels are compared.
                    fg_colour = expected_fg.split("[1;", 1)[-1]
                    self.assertIn(fg_colour, row, f"Selected row text is unreadable on {test_theme}")
                    # The old hardcoded values must be gone in both hosts.
                    self.assertNotIn("48;2;70;70;70", row, f"Console host still paints a grey bar for {test_theme}")
                    self.assertNotIn("\033[7m", row, f"Liquid Glass host still uses reverse video for {test_theme}")
                    hue = MP_Audio_Player._rgb_from_ansi(expected_bg)
                    self.assertIsNotNone(hue, f"{test_theme} selection bar is not a 24-bit colour")
                    seen.setdefault(test_theme, set()).add(hue)
        self.assertEqual(len(seen), 5)
        for test_theme, hues in seen.items():
            self.assertEqual(len(hues), 1, f"{test_theme} changed hue between the console and Liquid Glass hosts")


if __name__ == "__main__":
    unittest.main()
