#!/usr/bin/env python3
"""
Unit tests for MP Audio Player MINI Mode:
- 30% transparent / opaque background setting (Opacity=0.30)
- Dynamic color changing ambient background tint
"""

import unittest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player


class TestMiniPlayerTransparency(unittest.TestCase):
    def test_dynamic_gradient_background_changes_color(self):
        """Verifies that _get_dynamic_gradient produces changing, vibrant background colors across steps."""
        colors = []
        for t in [0.0, 5.0, 10.0, 15.0, 20.0, 30.0]:
            _, _, gbg = MP_Audio_Player._get_dynamic_gradient(t)
            self.assertEqual(len(gbg), 3)
            for ch in gbg:
                self.assertGreaterEqual(ch, 0)
                self.assertLessEqual(ch, 255)
            colors.append(gbg)

        # Ensure background colors are not static
        unique_colors = set(colors)
        self.assertGreater(len(unique_colors), 1, "Background color must dynamically change over time")

        # Verify that background colors are visibly distinct (not clamped to near-zero/black)
        max_channel = max(max(c) for c in colors)
        self.assertGreaterEqual(max_channel, 80, "Background color peaks must be clearly perceptible at 30% opacity")

    def test_setup_mini_terminal_appearance_writes_30_percent_opacity(self):
        """Verifies that _setup_mini_terminal_appearance configures Konsole colorscheme with Opacity=0.30."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_home = Path(tmp_dir)
            k_dir = tmp_home / ".local" / "share" / "konsole"
            k_dir.mkdir(parents=True, exist_ok=True)

            # Pre-create an old colorscheme with 0.80 opacity to ensure it gets updated to 0.30
            cs_file = k_dir / "MP_Mini_Player.colorscheme"
            cs_file.write_text("[Background]\nColor=16,18,28\nOpacity=0.80\n", encoding="utf-8")

            with patch.object(Path, "home", return_value=tmp_home):
                MP_Audio_Player._setup_mini_terminal_appearance()

            self.assertTrue(cs_file.exists())
            content = cs_file.read_text(encoding="utf-8")
            self.assertIn("Opacity=0.30", content)
            self.assertNotIn("Opacity=0.80", content)

    def test_launch_mini_player_window_uses_30_percent_opacity(self):
        """Verifies that launch_mini_player_window specifies 0.30 opacity for terminal configurations."""
        import inspect
        source = inspect.getsource(MP_Audio_Player.launch_mini_player_window)
        self.assertIn("window.opacity=0.30", source)
        self.assertIn("-a", source)
        self.assertIn("0.30", source)
        self.assertIn("0x4d000000", source)


if __name__ == "__main__":
    unittest.main()
