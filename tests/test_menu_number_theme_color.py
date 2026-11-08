#!/usr/bin/env python3
"""Menu item numbers and their brackets follow the active theme accent."""

import subprocess
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MGR_SH = BASE_DIR / "Mix_Archive_Manager.sh"

# One truecolor hue per theme. These replace the shared light-blue menu-number cyan.
EXPECTED = {
    "stream_of_frequency": "255;237;20",
    "dreamworlds": "255;20;129",
    "dreamworlds_ultra": "165;20;255",
    "dynamic_rainbow_liquid_glass": "255;20;237",
    "cosmic_supernova": "255;129;20",
    "dreamworlds_liquid": "20;255;147",
    "dreamworlds_neon": "219;20;255",
    "retro_studio": "180;140;20",
    "cyber_neon": "255;20;20",
    "phosphor": "165;255;20",
    "ice_cold": "20;147;255",
    "retro_terminal": "255;255;255",
    "cosmic_dreamworlds_radioactive": "111;255;20",
    "cosmic_dreamworlds": "255;20;183",
    "orbital_void_reflux": "56;20;255",
    "sensorium_interface": "111;20;255",
    "retro_linux_memories": "255;183;20",
    "cyberpunk": "200;0;180",
    "dracula": "255;20;75",
    "nord": "70;140;90",
    "matrix": "20;255;38",
    "solarized": "219;255;20",
    "tokyo": "255;75;20",
    "monokai": "56;255;20",
    "gruvbox": "180;70;20",
    "emerald": "20;255;93",
    "classic": "230;200;80",
}

LIGHT_BLUE = (
    "38;2;0;193;228",
    "38;2;0;242;255",
    "38;2;0;245;255",
    "38;2;0;245;212",
    "38;2;0;240;255",
    "38;2;76;201;240",
    "38;2;91;134;187",
    "38;2;153;153;255",
    "38;5;117",
    "38;5;51",
)


class TestMenuNumberThemeColor(unittest.TestCase):
    def test_bracketed_numbers_use_each_theme_accent(self):
        themes = " ".join(EXPECTED)
        script = f"""
        set -e
        eval "$(awk '/^set_theme_colors\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
        eval "$(sed -n '/^_menu_line_plain() {{/,/^}}/p' "{MGR_SH}")"
        declare -a opts=('4|Play Mix|')
        declare -n _opts_ref=opts
        for theme in {themes}; do
            set_theme_colors "$theme"
            line=""
            _menu_line_plain 0 line
            printf '%s\\t%s\\n' "$theme" "$line"
        done
        """
        res = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        seen = {}
        for raw in res.stdout.splitlines():
            theme, line = raw.split("\t", 1)
            seen[theme] = line
        self.assertEqual(set(seen), set(EXPECTED))
        accents = []
        for theme, accent in EXPECTED.items():
            line = seen[theme]
            self.assertIn(accent, line, theme)
            self.assertIn("[ 4]", line, theme)
            # The colour applies to the brackets and the digits together.
            self.assertLess(line.find(accent), line.find("[ 4]"), theme)
            if theme != "dreamworlds":
                for blue in LIGHT_BLUE:
                    self.assertNotIn(blue, line, f"{theme} still uses {blue}")
            accents.append(accent)
        self.assertEqual(len(accents), len(set(accents)))
        # Ice Cold is the only light-blue menu-number hue.
        blues = [name for name, accent in EXPECTED.items() if _is_light_blue(accent)]
        self.assertEqual(blues, ["ice_cold"])

    def test_selection_bar_uses_that_same_hue(self):
        themes = " ".join(EXPECTED)
        script = f"""
        set -e
        eval "$(awk '/^set_theme_colors\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
        eval "$(sed -n '/^highlight_menu_line() {{/,/^}}/p' "{MGR_SH}")"
        for theme in {themes}; do
            set_theme_colors "$theme"
            line=""
            highlight_menu_line "0" "Play Mix" "" 0 line 74 100
            printf '%s\\t%s\\n' "$theme" "$line"
        done
        """
        res = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        bars = []
        for raw in res.stdout.splitlines():
            theme, line = raw.split("\t", 1)
            accent = EXPECTED[theme]
            self.assertIn(f"48;2;{accent}", line, theme)
            self.assertNotIn("0;229;255", line, theme)
            bars.append(accent)
        self.assertEqual(len(bars), len(set(bars)))


def _is_light_blue(accent: str) -> bool:
    parts = [int(p) for p in accent.split(";")]
    if len(parts) != 3:
        return False
    r, g, b = [c / 255 for c in parts]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == 0 or mx - mn < 0.35 or mx < 0.45:
        return False
    d = mx - mn
    if mx == b and b >= r and b >= g:
        hue = (60 * ((r - g) / d) + 240) % 360
        return 175 <= hue <= 215
    return False


if __name__ == "__main__":
    unittest.main()
