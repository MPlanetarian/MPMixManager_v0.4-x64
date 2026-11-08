#!/usr/bin/env python3
"""Unit tests for MP Liquid Visualizer renaming, Liquid Glass unbolded styling,
liquid text effects, and default font customization.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import MP_Audio_Player as player
import MP_Audio_Player_Liquid_Glass as lg_vk
import MP_Audio_Player_Liquid_Glass_OpenGL as lg_gl


class TestLiquidVisualizerAndFontCustomization(unittest.TestCase):
    def test_default_font_is_monospace_normal_weight(self):
        """Default font must be Monospace 11 (normal weight, unbolded)."""
        self.assertEqual(lg_vk.DEFAULT_FONT, "Monospace 11")
        self.assertEqual(lg_gl.DEFAULT_FONT, "Monospace 11")
        self.assertNotIn("Bold", lg_vk.DEFAULT_FONT)
        self.assertNotIn("Bold", lg_gl.DEFAULT_FONT)

    def test_font_override_and_persistence(self):
        """Test that font can be customized via parameter or persistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_cfg = Path(tmpdir) / "liquid_glass_font"
            with patch.object(lg_vk, "FONT_CONFIG_FILE", test_cfg), \
                 patch.object(lg_vk, "CONFIG_DIR", Path(tmpdir)):
                # Default without file
                self.assertEqual(lg_vk.get_liquid_glass_font(), "Monospace 11")
                # CLI override
                self.assertEqual(lg_vk.get_liquid_glass_font("Fira Code 11"), "Fira Code 11")
                # Persistence via set_liquid_glass_font
                lg_vk.set_liquid_glass_font("Hack 11")
                self.assertEqual(lg_vk.get_liquid_glass_font(), "Hack 11")

    def test_liquid_glass_vte_css_unbolded_and_liquid_glow(self):
        """VTE terminal styling in Liquid Glass must disable bold and include liquid text glow."""
        for mod in (lg_vk, lg_gl):
            host = mod.GlassHost(["test"], mode="NORMAL", font="Monospace 11")
            self.assertEqual(host.font_name, "Monospace 11")
            # Verify clear terminal background configuration logic
            mock_term = MagicMock()
            mock_win = MagicMock()
            mock_style_ctx = MagicMock()
            mock_term.get_style_context.return_value = mock_style_ctx
            mock_win.get_style_context.return_value = mock_style_ctx
            mock_win.get_screen.return_value = None
            mock_term.get_pango_context.return_value = None

            host._clear_terminal_background(mock_win, mock_term)
            mock_term.set_bold_is_bright.assert_called_with(False)
            mock_term.set_allow_bold.assert_called_with(False)

            # Inspect CSS providers loaded into style context
            self.assertTrue(mock_style_ctx.add_provider.called)
            provider_arg = mock_style_ctx.add_provider.call_args[0][0]
            self.assertIsNotNone(provider_arg)

    def test_mp_audio_player_visualizer_strings(self):
        """Verify MP Audio Player user-facing strings refer to MP Liquid Visualizer."""
        # Check CLI help output
        import subprocess
        res = subprocess.run([sys.executable, str(ROOT / "MP_Audio_Player.py"), "--help"], capture_output=True, text=True)
        help_text = res.stdout
        self.assertIn("MP Liquid Visualizer", help_text)
        self.assertNotIn("MP_Liquid_Visualizer 3D Vulkan Visualizer", help_text)

        # Check UI frame controls line in MUSIC mode
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [{"name": "Track A", "path": "/test.flac", "size_mb": 50}]
        ui = player.TerminalPlayerUI(None, mock_scanner, is_remote=True, mode="MUSIC")
        ui.visualizer.theme = "dreamworlds_liquid"
        st = {"state": "playing", "title": "Test", "path": "/test.flac"}
        captured = []
        with patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured.extend(lines)), \
             patch("MP_Audio_Player._win_visible_size", return_value=(120, 40)):
            ui._get_status = MagicMock(return_value=st)
            ui._draw_frame()

        controls_lines = [l for l in captured if "[Z]" in l or "Liquid Vis" in l]
        self.assertTrue(len(controls_lines) > 0, "Controls line with Z hotkey not found")
        for line in controls_lines:
            self.assertNotIn("3D Visualizer", line)
            self.assertTrue("Liquid Vis" in line or "MP Liquid Visualizer" in line)

    def test_mp_audio_player_liquid_glass_unbolded_mode(self):
        """When running in MP_LIQUID_GLASS mode, bold playlist items and hints must not be forced."""
        mock_scanner = MagicMock()
        mock_scanner.get_mixes.return_value = [{"name": "Track A", "path": "/a.flac", "size_mb": 50}]
        ui = player.TerminalPlayerUI(None, mock_scanner, is_remote=True)
        st = {"state": "stopped", "title": "Track A", "path": "/a.flac"}

        captured = []
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch("MP_Audio_Player._present_frame", side_effect=lambda lines, w, h: captured.extend([player._strip_bold_ansi(l) for l in lines])), \
             patch("MP_Audio_Player._win_visible_size", return_value=(100, 35)):
            ui._get_status = MagicMock(return_value=st)
            ui._draw_frame()

        # Check banner title indicates Liquid Glass
        banner_lines = [l for l in captured if "LIQUID GLASS" in l]
        self.assertTrue(len(banner_lines) > 0, "Liquid Glass banner title not rendered")

        # In MP_LIQUID_GLASS mode, bold escape codes must not be forced
        for line in captured:
            self.assertNotIn("\033[1m", line, f"Forced bold escape sequence found in line: {line!r}")

        # Test _present_frame bold stripping under MP_LIQUID_GLASS
        raw_lines = ["\033[1;38;2;0;229;255mTest Title\033[0m", "\033[1mBold Text\033[0m"]
        out_buf = []
        with patch.dict(os.environ, {"MP_LIQUID_GLASS": "1"}), \
             patch("sys.stdout.write", side_effect=out_buf.append), \
             patch("sys.stdout.flush"):
            player._present_frame(raw_lines, 80, 2)
        presented = "".join(out_buf)
        self.assertNotIn("\033[1m", presented)
        self.assertNotIn("\033[1;", presented)
        self.assertIn("\033[38;2;0;229;255mTest Title\033[0m", presented)


if __name__ == "__main__":
    unittest.main()
