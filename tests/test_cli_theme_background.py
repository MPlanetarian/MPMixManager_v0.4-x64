#!/usr/bin/env python3
"""The CLI manager paints a different console background for every theme.

Windows Terminal, Linux VTE/Konsole/xterm, and iTerm take OSC 11. Terminal.app
and the classic Windows console are handled beside that sequence. MP Gui and
the liquid-glass hosts keep their own pane, so they must not receive OSC 11.
"""

import subprocess
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MGR_SH = BASE_DIR / "Mix_Archive_Manager.sh"

THEMES = (
    "stream_of_frequency",
    "dreamworlds",
    "dreamworlds_ultra",
    "dynamic_rainbow_liquid_glass",
    "cosmic_supernova",
    "dreamworlds_liquid",
    "dreamworlds_neon",
    "retro_studio",
    "cyber_neon",
    "phosphor",
    "ice_cold",
    "retro_terminal",
    "cosmic_dreamworlds_radioactive",
    "cosmic_dreamworlds",
    "orbital_void_reflux",
    "sensorium_interface",
    "retro_linux_memories",
    "cyberpunk",
    "dracula",
    "nord",
    "matrix",
    "solarized",
    "tokyo",
    "monokai",
    "gruvbox",
    "emerald",
    "classic",
)


def _bash(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
    )


class TestCliThemeBackground(unittest.TestCase):
    def test_each_theme_has_its_own_dark_background(self):
        themes = " ".join(THEMES)
        script = f"""
        set -e
        eval "$(awk '/^set_theme_colors\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
        for theme in {themes}; do
            set_theme_colors "$theme"
            printf '%s\\t%s\\t%s\\t%s\\n' "$theme" "$THEME_BG_R" "$THEME_BG_G" "$THEME_BG_B"
        done
        """
        res = _bash(script)
        self.assertEqual(res.returncode, 0, res.stderr)
        seen = {}
        for raw in res.stdout.splitlines():
            theme, r, g, b = raw.split("\t")
            seen[theme] = (int(r), int(g), int(b))
        self.assertEqual(set(seen), set(THEMES))
        # MPlanetarian Dreamworlds is black. The white-on-black retro
        # terminal uses the same pane, so that one pair is shared.
        self.assertEqual(seen["dreamworlds"], (0, 0, 0))
        alias = _bash(
            f"""
            set -e
            eval "$(awk '/^set_theme_colors\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
            for theme in default mplanetarian mplanetarian_dreamworlds; do
                set_theme_colors "$theme"
                printf '%s\\t%s\\t%s\\t%s\\n' "$theme" "$THEME_BG_R" "$THEME_BG_G" "$THEME_BG_B"
            done
            """
        )
        self.assertEqual(alias.returncode, 0, alias.stderr)
        for raw in alias.stdout.splitlines():
            theme, r, g, b = raw.split("\t")
            self.assertEqual((int(r), int(g), int(b)), (0, 0, 0), theme)
        colours = [rgb for theme, rgb in seen.items() if theme != "dreamworlds"]
        self.assertEqual(len(colours), len(set(colours)))
        for theme, (r, g, b) in seen.items():
            for channel in (r, g, b):
                self.assertGreaterEqual(channel, 0, theme)
                self.assertLessEqual(channel, 255, theme)
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            self.assertLess(luma, 90, f"{theme} background is too light for the menu text")
        # Neighbouring themes in the C-key cycle must be visibly different.
        cycle = [
            "stream_of_frequency",
            "dreamworlds_ultra",
            "dynamic_rainbow_liquid_glass",
            "cosmic_supernova",
            "dreamworlds_liquid",
            "dreamworlds_neon",
            "retro_studio",
            "cyber_neon",
            "phosphor",
            "ice_cold",
            "retro_terminal",
            "cosmic_dreamworlds_radioactive",
            "cosmic_dreamworlds",
            "orbital_void_reflux",
            "sensorium_interface",
            "retro_linux_memories",
        ]
        for left, right in zip(cycle, cycle[1:] + cycle[:1]):
            ar, ag, ab = seen[left]
            br, bg, bb = seen[right]
            dist = ((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2) ** 0.5
            self.assertGreaterEqual(dist, 18, f"{left} and {right} backgrounds are too alike")

    def test_theme_switch_emits_osc11_for_windows_mac_and_linux(self):
        script = f"""
        set -e
        eval "$(awk '/^set_theme_colors\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
        eval "$(awk '/^_apply_cli_theme_background\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
        export MP_CLI_THEME_BG_FORCE=1
        unset MP_LIQUID_GLASS MP_GUI_SESSION
        set_theme_colors dreamworlds_ultra
        _apply_cli_theme_background
        printf '\\n--\\n'
        set_theme_colors retro_linux_memories
        _apply_cli_theme_background
        """
        res = _bash(script)
        self.assertEqual(res.returncode, 0, res.stderr)
        chunks = res.stdout.split("\n--\n")
        self.assertEqual(len(chunks), 2)
        # BEL form and ST form, so Windows Terminal, Terminal-class Linux, and Konsole all take it.
        self.assertIn("\033]11;#16062e\007", chunks[0])
        self.assertIn("\033]11;#16062e\033\\", chunks[0])
        self.assertIn("\033]11;#1a1e21\007", chunks[1])
        self.assertIn("\033]11;#1a1e21\033\\", chunks[1])

    def test_glass_hosts_do_not_take_a_console_background(self):
        script = f"""
        set -e
        eval "$(awk '/^set_theme_colors\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
        eval "$(awk '/^_apply_cli_theme_background\\(\\)/{{f=1}} f{{print}} f&&/^}}/{{exit}}' "{MGR_SH}")"
        export MP_CLI_THEME_BG_FORCE=1
        set_theme_colors matrix
        MP_LIQUID_GLASS=1 _apply_cli_theme_background
        unset MP_LIQUID_GLASS
        _CLI_THEME_BG_HEX=""
        MP_GUI_SESSION=1 _apply_cli_theme_background
        """
        res = _bash(script)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("]11;", res.stdout)

    def test_platform_hooks_and_restore_are_wired(self):
        text = MGR_SH.read_text(encoding="utf-8")
        self.assertIn("SetConsoleScreenBufferInfoEx", text)
        self.assertIn('set background color of t to wanted', text)
        self.assertIn("_apply_cli_theme_background", text)
        self.assertIn("_restore_cli_theme_background", text)
        # Konsole's scheme reset must run before the theme pane is painted.
        load = text.split("load_theme() {", 1)[1].split("\n_ensure_konsole_default_scheme()", 1)[0]
        self.assertLess(load.find("_ensure_konsole_default_scheme"), load.find("_apply_cli_theme_background"))
        self.assertIn('_sync_btop_theme "$new_theme"; _apply_cli_theme_background', text)


if __name__ == "__main__":
    unittest.main()
