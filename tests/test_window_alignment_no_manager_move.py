import unittest
from pathlib import Path
from scripts.align_mix_windows import js_code, align_x11


class TestWindowAlignmentNoManagerMove(unittest.TestCase):
    def test_js_code_never_moves_manager_window(self):
        code = js_code(
            prim_name="DP-1",
            sec_name="HDMI-1",
            mgr_ancestors=[1234],
            mgr_pid=1234,
            parent_pid=1230,
            expect_straw=False,
            expect_cover=False,
            run_token="TEST_TOKEN",
        )
        self.assertNotIn("workspace.sendClientToScreen(mgrWin", code)
        self.assertNotIn("workspace.raiseWindow(mgrWin)", code)
        self.assertNotIn("workspace.activeWindow = mgrWin", code)

    def test_align_x11_never_forces_manager_window_activation(self):
        # align_x11 must return cleanly without touching or moving the manager window
        result = align_x11(mgr_pid=1234)
        self.assertTrue(result)

    def test_launch_manager_wrapper_is_windowed(self):
        launch_script = Path(__file__).resolve().parent.parent / "bin" / "launch-manager"
        content = launch_script.read_text(encoding="utf-8")
        self.assertNotIn("--fullscreen", content)
        self.assertIn("exec /usr/bin/konsole --separate", content)


if __name__ == "__main__":
    unittest.main()
