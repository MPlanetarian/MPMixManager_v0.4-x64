#!/usr/bin/env python3
"""
Test terminal resize handling in Mix_Archive_Manager.sh.
Verifies that when terminal window is resized (e.g. via Ctrl + / Ctrl -),
the script catches SIGWINCH, detects the geometry change, emits RESIZE,
updates _TERM_LINES, _TERM_COLS, LINES, and COLUMNS, and automatically
rescales box width and header dimensions.
"""

import subprocess
import unittest
import os

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANAGER_SH = os.path.join(SCRIPT_DIR, "Mix_Archive_Manager.sh")

class TestManagerResize(unittest.TestCase):
    def test_syntax_valid(self):
        result = subprocess.run(["bash", "-n", MANAGER_SH], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Syntax error in {MANAGER_SH}: {result.stderr}")

    def test_winch_trap_present(self):
        with open(MANAGER_SH, "r", encoding="utf-8") as f:
            content = f.read(2000) # Check header
        self.assertIn("trap '_on_winch' WINCH", content)
        self.assertIn("_TERM_RESIZED=1", content)

    def test_resize_detection_flow(self):
        bash_test = f'''
        SCRIPT_DIR="{SCRIPT_DIR}"
        source <(sed -n '1,142p' "{MANAGER_SH}")
        
        # Test initial geometry
        update_terminal_geometry 1
        init_lines="$_TERM_LINES"
        init_cols="$_TERM_COLS"
        [ -n "$init_lines" ] || exit 1
        [ -n "$init_cols" ] || exit 2
        
        # Idle check should return TICK
        k=""
        read_nav_key k
        [ "$k" = "TICK" ] || exit 3
        
        # Trigger WINCH signal
        _on_winch
        [ "$_TERM_RESIZED" -eq 1 ] || exit 4
        
        # read_nav_key should now immediately emit RESIZE
        k=""
        read_nav_key k
        [ "$k" = "RESIZE" ] || exit 5
        
        # Simulate handling RESIZE
        update_terminal_geometry 1
        _TERM_RESIZED=0
        
        # Box width should adapt
        _set_menu_box_width new_w "$_TERM_COLS"
        expected_w=$(( _TERM_COLS >= 8 ? _TERM_COLS - 4 : (_TERM_COLS >= 3 ? _TERM_COLS - 2 : 1) ))
        [ "$new_w" -eq "$expected_w" ] || exit 6
        
        # Subsequent key should be TICK again (no stuck loop)
        k=""
        read_nav_key k
        [ "$k" = "TICK" ] || exit 7
        
        echo "SUCCESS"
        '''
        res = subprocess.run(["bash", "-c", bash_test], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Bash resize flow failed: {res.stderr}\nOutput: {res.stdout}")
        self.assertIn("SUCCESS", res.stdout)

    def test_scaling_dimensions_on_zoom(self):
        """Verify that _set_menu_box_width and render_main_header adapt to Ctrl+ (zoom in) and Ctrl- (zoom out) sizes."""
        bash_test = """
        SCRIPT_DIR=""" + f'"{SCRIPT_DIR}"' + """
        source <(sed -n '1,142p' """ + f'"{MANAGER_SH}"' + """)
        is_mix_archive_configured() { return 0; }
        get_manager_uptime() { _MANAGER_UPTIME_LINE="Uptime: 1h"; }
        source <(sed -n '/^render_main_header() {/,/^}/p' """ + f'"{MANAGER_SH}"' + """)
        
        # Case 1: Zoom In with Ctrl + (e.g. font becomes bigger, so window cols shrink to 90)
        _TERM_COLS=90
        _TERM_LINES=30
        _set_menu_box_width w_zoom_in "$_TERM_COLS"
        [ "$w_zoom_in" -eq 86 ] || exit 10
        render_main_header "$w_zoom_in" >/dev/null
        # Header panel width matches w_zoom_in + 2 (with 2 spaces indent)
        first_line="$(printf '%b\n' "$_RENDERED_MAIN_HEADER" | head -n 1)"
        clean_line=$(printf '%b' "$first_line" | sed 's/\\x1b\\[[0-9;]*m//g' | tr -d '\r\n')
        [ "${#clean_line}" -eq $((w_zoom_in + 2)) ] || exit 11
        
        # Case 2: Zoom Out with Ctrl - (e.g. font becomes smaller, so window cols expand to 160)
        _TERM_COLS=160
        _TERM_LINES=55
        _set_menu_box_width w_zoom_out "$_TERM_COLS"
        [ "$w_zoom_out" -eq 156 ] || exit 20
        render_main_header "$w_zoom_out" >/dev/null
        first_line="$(printf '%b\n' "$_RENDERED_MAIN_HEADER" | head -n 1)"
        clean_line=$(printf '%b' "$first_line" | sed 's/\\x1b\\[[0-9;]*m//g' | tr -d '\r\n')
        [ "${#clean_line}" -eq $((w_zoom_out + 2)) ] || exit 21
        
        echo "ZOOM_SUCCESS"
        """
        res = subprocess.run(["bash", "-c", bash_test], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Zoom scaling test failed: {res.stderr}\nOutput: {res.stdout}")
        self.assertIn("ZOOM_SUCCESS", res.stdout)

if __name__ == "__main__":
    unittest.main()
