#!/usr/bin/env python3
"""MP Gui must not leave cursor-shaped marks along the top of the playlist.

The macOS overlay used to prefer SFNSMono. That face draws › and ▶ and leaves
► ★ ✦ ≋ ◄ blank, so the visualizer's lower edge (the top of the playlist)
showed a row of chevrons. Menlo and Monaco draw the playlist mark instead.
"""

import os
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from MP_Audio_Player_Liquid_Glass_OpenGL_macOS import (  # noqa: E402
    OVERLAY_FONT_CANDIDATES,
    load_overlay_font,
)


def _ink(font, ch: str) -> int:
    img = Image.new("L", (32, 32), 255)
    ImageDraw.Draw(img).text((2, 2), ch, fill=0, font=font)
    return sum(1 for pixel in img.getdata() if pixel < 200)


class TestMacosPlaylistCursors(unittest.TestCase):
    def test_overlay_prefers_a_face_that_draws_the_playlist_mark(self):
        self.assertLess(
            OVERLAY_FONT_CANDIDATES.index("/System/Library/Fonts/Menlo.ttc"),
            OVERLAY_FONT_CANDIDATES.index("/System/Library/Fonts/SFNSMono.ttf"),
        )
        font = load_overlay_font(13)
        self.assertGreater(_ink(font, "\u25ba"), 8, "playlist mark ► did not draw")
        self.assertGreater(_ink(font, "\u2605"), 8, "favorite star did not draw")
        name = str(getattr(font, "path", "") or "")
        self.assertNotIn("SFNSMono", name)

    def test_stream_footer_has_no_cursor_arrows(self):
        os.environ["MP_LIQUID_GLASS"] = "1"
        from MP_Audio_Player import EqualizerVisualizer

        viz = EqualizerVisualizer(style="stream_of_frequency_eq")
        lines = viz.render_stream_of_frequency({"state": "stopped"}, width=120, height=7)
        footer = lines[-1]
        for cursor in ("\u25c4", "\u2794", "\u203a", "\u25b6", "\u276f"):
            self.assertNotIn(cursor, footer)

    def test_stream_particles_are_not_chevrons(self):
        os.environ["MP_LIQUID_GLASS"] = "1"
        from MP_Audio_Player import EqualizerVisualizer

        viz = EqualizerVisualizer(style="stream_of_frequency_eq")
        viz._sof_rng.choice = lambda seq: seq[-1]
        lines = viz.render_stream_of_frequency(
            {
                "state": "playing",
                "rms_level": 0.4,
                "peak_db": -3.0,
                "levels": [0.8] * 24,
                "levels_left": [0.8] * 24,
                "levels_right": [0.8] * 24,
            },
            width=120,
            height=7,
        )
        plain = "\n".join(lines)
        self.assertNotIn("\u203a", plain)
        self.assertNotIn("\u276f", plain)


if __name__ == "__main__":
    unittest.main()
