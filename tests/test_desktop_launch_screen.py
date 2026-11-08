"""Main-screen placement skips the Hisense TV at the desktop origin."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from desktop_launch_screen import (  # noqa: E402
    main_desktop_origin,
    parse_kscreen,
    parse_xrandr_monitors,
    select_main,
)


HISENSE_AT_ORIGIN = """
Output: 1 HDMI-A-1 aaaa
	enabled
	connected
	priority 2
	Geometry: 0,0 2648x1490
Output: 2 DP-3 bbbb
	enabled
	connected
	priority 1
	Geometry: 2649,0 1920x1200
Output: 3 DP-1 cccc
	enabled
	connected
	priority 3
	Geometry: 4569,0 1920x1200
"""

HISENSE_IS_PRIORITY = """
Output: 1 HDMI-A-1 aaaa
	enabled
	connected
	priority 1
	Geometry: 0,0 2648x1490
Output: 2 DP-3 bbbb
	enabled
	connected
	priority 2
	Geometry: 4569,0 1920x1200
"""

CURRENT_DESKTOP = """
Output: 1 DP-3 aaaa
	enabled
	connected
	priority 1
	Geometry: 1920,0 1920x1200
Output: 2 DP-1 bbbb
	enabled
	connected
	priority 2
	Geometry: 0,0 1920x1200
Output: 3 DP-2 cccc
	enabled
	connected
	priority 3
	Geometry: 3840,0 1920x1200
"""


class TestDesktopLaunchScreen(unittest.TestCase):
    def test_hisense_at_origin_uses_priority_desktop(self):
        outputs = parse_kscreen(HISENSE_AT_ORIGIN)
        self.assertEqual(select_main(outputs)["name"], "DP-3")
        self.assertEqual(main_desktop_origin(72, 64, outputs), (2721, 64))

    def test_hisense_primary_still_uses_a_desktop_monitor(self):
        outputs = parse_kscreen(HISENSE_IS_PRIORITY)
        self.assertEqual(select_main(outputs)["name"], "DP-3")
        self.assertEqual(main_desktop_origin(160, 80, outputs), (4729, 80))

    def test_live_three_monitor_layout_uses_center_screen(self):
        outputs = parse_kscreen(CURRENT_DESKTOP)
        self.assertEqual(main_desktop_origin(72, 64, outputs), (1992, 64))

    def test_colored_kscreen_output_parses(self):
        colored = "\x1b[01;32mOutput: \x1b[0;0m1 DP-3 uuid\n\t\x1b[01;32menabled\x1b[0;0m\n\t\x1b[01;32mconnected\x1b[0;0m\n\t\x1b[01;32mpriority 1\x1b[0;0m\n\x1b[01;33m\tGeometry: \x1b[0;0m1920,0 1920x1200\n"
        outputs = parse_kscreen(colored)
        self.assertEqual(outputs[0]["name"], "DP-3")
        self.assertEqual(outputs[0]["geo"], (1920, 0, 1920, 1200))
        self.assertTrue(outputs[0]["enabled"])

    def test_xrandr_primary_skips_hisense(self):
        text = "\n".join([
            "Monitors: 2",
            " 0: +*HDMI-A-1 3840/1200x2160/680+0+0  HDMI-A-1",
            " 1: +DP-3 1920/546x1200/352+2649+0  DP-3",
        ])
        monitors = parse_xrandr_monitors(text)
        self.assertEqual(monitors[0]["name"], "HDMI-A-1")
        self.assertTrue(monitors[0]["primary"])
        self.assertEqual(monitors[1]["geo"][:2], (2649, 0))


if __name__ == "__main__":
    unittest.main()
