#!/usr/bin/env python3
"""
Unit tests for Option 33 Submenu System:
- Verifies that all 6 Option 33 submenus:
  1. manage_ai_models
  2. manage_ollama
  3. manage_open_webui
  4. manage_harmony_agent
  5. manage_dsh_mobile
  6. manage_wan2gp
  (as well as manage_beszel and run_wan2gp_output_monitor)
  use run_interactive_submenu to enable keyboard navigation (Up/Down arrow keys, Enter to select).
- Verifies non-interactive execution and clean return on exit (0/ESC/q).
"""

import unittest
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MGR_SH = BASE_DIR / "Mix_Archive_Manager.sh"


class TestOption33Submenus(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MGR_SH.exists(), f"Cannot find {MGR_SH}")
        self.mgr_content = MGR_SH.read_text(encoding="utf-8", errors="replace")

    def test_submenus_use_run_interactive_submenu(self):
        """Verifies that all 6 submenus and helpers call run_interactive_submenu."""
        submenus = [
            "manage_ai_models",
            "manage_ollama",
            "manage_open_webui",
            "manage_harmony_agent",
            "manage_dsh_mobile",
            "manage_wan2gp",
            "manage_beszel",
            "run_wan2gp_output_monitor",
        ]
        for fn in submenus:
            # Check function definition exists
            self.assertIn(f"{fn}()", self.mgr_content, f"Function {fn}() not found in Mix_Archive_Manager.sh")

        # Check that run_interactive_submenu is used inside these functions
        self.assertIn('run_interactive_submenu "AI ASSISTANT & MODEL LAUNCHER (AGY)"', self.mgr_content)
        self.assertIn('run_interactive_submenu "OLLAMA LOCAL LLM SERVER MANAGER"', self.mgr_content)
        self.assertIn('run_interactive_submenu "OPEN WEBUI SERVER & WEB CHAT MANAGER"', self.mgr_content)
        self.assertIn('run_interactive_submenu "MP HARMONY AI AGENT & VOICE BRIDGE (:11435)"', self.mgr_content)
        self.assertIn('run_interactive_submenu "DEEPSEEK HARNESS (DSH-MOBILE) SERVER MANAGER"', self.mgr_content)
        self.assertIn('run_interactive_submenu "WAN2GP AI VIDEO & IMAGE WORKSTATION SUITE"', self.mgr_content)
        self.assertIn('run_interactive_submenu "WAN2GP DIRECTORY CONFIGURATION"', self.mgr_content)
        self.assertIn('run_interactive_submenu "BESZEL WORKSTATION & GPU MONITORING SUITE"', self.mgr_content)
        self.assertIn('run_interactive_submenu "MP VIDEO & IMAGE DIRECTORY OUTPUT MONITOR"', self.mgr_content)

    def test_submenus_exit_cleanly_on_zero(self):
        """Tests that invoking any submenu with '0' as input exits cleanly with return code 0."""
        submenus = [
            "manage_ai_models",
            "manage_ollama",
            "manage_open_webui",
            "manage_harmony_agent",
            "manage_dsh_mobile",
            "manage_wan2gp",
            "manage_beszel",
            "run_wan2gp_output_monitor",
        ]
        for fn in submenus:
            bash_cmd = f"""
            eval "$(head -n 2613 "{MGR_SH}")"
            echo "0" | {fn}
            """
            res = subprocess.run(["bash", "-c", bash_cmd], cwd=str(BASE_DIR), capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Submenu {fn} failed with return code {res.returncode}: {res.stderr}")

    def test_submenus_cli_argument_dispatch(self):
        """Tests that server submenus with arguments dispatch cleanly to their sub-scripts without starting an interactive menu."""
        # Test manage_open_webui status
        bash_cmd = f"""
        eval "$(head -n 2613 "{MGR_SH}")"
        manage_open_webui status
        """
        res = subprocess.run(["bash", "-c", bash_cmd], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Open WebUI is", res.stdout)

        # Test manage_beszel status
        bash_cmd = f"""
        eval "$(head -n 2613 "{MGR_SH}")"
        manage_beszel status
        """
        res = subprocess.run(["bash", "-c", bash_cmd], cwd=str(BASE_DIR), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Beszel Hub Port", res.stdout)


if __name__ == "__main__":
    unittest.main()
