#!/usr/bin/env python3
"""
Unit tests for Main Menu selector breathing animation and macOS Traktor auto-launch:
- highlight_menu_line supports breath_factor parameter (100 down to 15)
- highlight_menu_line scales background RGB and pointer RGB smoothly
- Mix_Archive_Manager.sh contains the 10-second idle breathing trigger logic
- run_deferred_startup contains macOS Traktor detection and console tab launch
"""

import unittest
import subprocess
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MGR_SH = BASE_DIR / "Mix_Archive_Manager.sh"


class TestMenuBreathingAndTraktor(unittest.TestCase):
    def test_highlight_menu_line_breathing_scaling(self):
        """Verifies that highlight_menu_line produces scaled RGB escape codes when breath_factor is changed."""
        bash_cmd = f"""
        eval "$(sed -n '/^highlight_menu_line() {{/,/^}}/p' "{MGR_SH}")"
        out_100=""
        out_50=""
        out_20=""
        highlight_menu_line "1" "Test Option" "Extra" 0 out_100 70 100
        highlight_menu_line "1" "Test Option" "Extra" 0 out_50 70 50
        highlight_menu_line "1" "Test Option" "Extra" 0 out_20 70 20
        echo "100:$out_100"
        echo "50:$out_50"
        echo "20:$out_20"
        """
        res = subprocess.run(["bash", "-c", bash_cmd], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

        lines = res.stdout.strip().split("\n")
        line_100 = next(l for l in lines if l.startswith("100:"))
        line_50 = next(l for l in lines if l.startswith("50:"))
        line_20 = next(l for l in lines if l.startswith("20:"))

        # Check that 100 contains full color 247;37;133
        self.assertIn("247;37;133", line_100)

        # Check that 50 contains halved color ~123;18;66
        self.assertIn("123;18;66", line_50)

        # Check that 20 contains dimmed color ~49;7;26
        self.assertIn("49;7;26", line_20)

        # Verify that bracketed extra text is never rendered during fading/breathing
        self.assertNotIn("Extra", line_100)
        self.assertNotIn("Extra", line_50)
        self.assertNotIn("Extra", line_20)

    def test_idle_10_seconds_breathing_trigger_present(self):
        """Verifies that Mix_Archive_Manager.sh contains the 10-second idle breathing logic."""
        content = MGR_SH.read_text(encoding="utf-8", errors="replace")
        self.assertIn("_LAST_NAV_TIME", content)
        self.assertIn("_BREATH_FACTORS", content)
        self.assertIn("_IS_BREATHING", content)
        self.assertIn("_idle_time", content)
        # Check condition: idle time >= 10
        self.assertTrue(re.search(r'\[\s*"\$_idle_time"\s*-ge\s*10\s*\]', content))

    def test_macos_traktor_startup_tab_launch_present(self):
        """Startup opens the Traktor monitor tab only when the Traktor app is running."""
        content = MGR_SH.read_text(encoding="utf-8", errors="replace")
        self.assertIn("traktor_app_is_running", content)
        self.assertIn('launch_in_terminal "Traktor Live Monitor"', content)
        self.assertIn('"tab"', content)
        self.assertNotIn('grep -qi "true"', content)

    def test_traktor_app_is_running_ignores_closed_app_and_helper_scripts(self):
        """AppleScript 'false' and traktor_*.py processes are not the Traktor app."""
        script = r"""
        set -e
        eval "$(sed -n '/^traktor_app_is_running() {/,/^}/p' Mix_Archive_Manager.sh)"
        check() {
            if traktor_app_is_running; then echo "$1:YES"; else echo "$1:NO"; fi
        }
        pgrep() { return 1; }
        osascript() { printf '%s\n' "false"; }
        check closed
        osascript() { printf '%s\n' "true"; }
        check open
        osascript() { printf '%s\n' "false"; }
        pgrep() {
            # Helper scripts contain the word Traktor, but they are not the app.
            if [ "$1" = "-f" ]; then return 0; fi
            return 1
        }
        check helper
        pgrep() {
            if [ "$1" = "-x" ] && [ "$2" = "Traktor" ]; then return 0; fi
            return 1
        }
        check process
        """
        res = subprocess.run(
            ["bash", "-c", script],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("closed:NO", res.stdout)
        self.assertIn("open:YES", res.stdout)
        self.assertIn("helper:NO", res.stdout)
        self.assertIn("process:YES", res.stdout)


if __name__ == "__main__":
    unittest.main()
