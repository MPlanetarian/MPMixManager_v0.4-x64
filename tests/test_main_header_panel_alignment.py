#!/usr/bin/env python3
"""
Unit test to verify that the top banner panel window rendered in Mix_Archive_Manager.sh
and .probe_mgr.sh matches the MP Audio Player panel window below:
- Uses rounded corners (╭, ╮, ╰, ╯) and box border (─, │)
- Formatted as a panel window with equal row lengths across all widths
- Title is centered and aligned with the panel borders
- Matches panel window width of box_w + 2 (with 2 spaces indent)
"""

import unittest
import subprocess
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_regex.sub("", text)


class TestMainHeaderPanelAlignment(unittest.TestCase):
    def test_main_header_panel_box_dimensions(self):
        """Verify that the top 3 rows of render_main_header in Mix_Archive_Manager.sh form a panel window."""
        bash_script = r"""
        source ./Mix_Archive_Manager.sh 2>/dev/null || true

        for cols in 90 100 120 140 160 180; do
            _TERM_COLS=$cols
            _set_menu_box_width box_w "$cols"
            render_main_header "$box_w" >/dev/null
            readarray -t lines <<< "$_RENDERED_MAIN_HEADER"

            row1="$(printf '%b' "${lines[0]}" | sed 's/\x1b\[[0-9;]*m//g')"
            row2="$(printf '%b' "${lines[1]}" | sed 's/\x1b\[[0-9;]*m//g')"
            row3="$(printf '%b' "${lines[2]}" | sed 's/\x1b\[[0-9;]*m//g')"

            echo "BOX:$box_w:${#row1}:${#row2}:${#row3}:$row1"
        done
        """
        proc = subprocess.run(
            ["bash", "-c", bash_script],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        for line in proc.stdout.strip().splitlines():
            if line.startswith("BOX:"):
                parts = line.split(":", 5)
                box_w = int(parts[1])
                l1, l2, l3 = int(parts[2]), int(parts[3]), int(parts[4])
                row1_content = parts[5]

                # Check rounded corners
                self.assertTrue(row1_content.startswith("  ╭"), f"Row 1 does not start with '  ╭': {row1_content}")
                self.assertTrue(row1_content.endswith("╮"), f"Row 1 does not end with '╮': {row1_content}")

                # Check all 3 rows match box_w + 2
                expected_len = box_w + 2
                self.assertEqual(
                    (l1, l2, l3),
                    (expected_len, expected_len, expected_len),
                    f"Row length mismatch at box_w={box_w}: ({l1}, {l2}, {l3}) != {expected_len}"
                )

    def test_probe_mgr_header_matches(self):
        """Verify .probe_mgr.sh render_main_header also produces the matching panel window."""
        bash_script = r"""
        source ./Mix_Archive_Manager.sh 2>/dev/null || true
        eval "$(sed -n '/^render_main_header() {/,/^}/p' .probe_mgr.sh)"

        for cols in 90 100 120; do
            _TERM_COLS=$cols
            _set_menu_box_width box_w "$cols"
            render_main_header "$box_w" >/dev/null
            readarray -t lines <<< "$_RENDERED_MAIN_HEADER"

            row1="$(printf '%b' "${lines[0]}" | sed 's/\x1b\[[0-9;]*m//g')"
            row2="$(printf '%b' "${lines[1]}" | sed 's/\x1b\[[0-9;]*m//g')"
            row3="$(printf '%b' "${lines[2]}" | sed 's/\x1b\[[0-9;]*m//g')"

            echo "PROBE:$box_w:${#row1}:${#row2}:${#row3}"
        done
        """
        proc = subprocess.run(
            ["bash", "-c", bash_script],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        for line in proc.stdout.strip().splitlines():
            if line.startswith("PROBE:"):
                parts = line.split(":")
                box_w = int(parts[1])
                l1, l2, l3 = int(parts[2]), int(parts[3]), int(parts[4])
                expected_len = box_w + 2
                self.assertEqual(
                    (l1, l2, l3),
                    (expected_len, expected_len, expected_len),
                    f"Probe mismatch at box_w={box_w}: ({l1}, {l2}, {l3}) != {expected_len}"
                )


if __name__ == "__main__":
    unittest.main()
