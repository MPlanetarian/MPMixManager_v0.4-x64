"""The MP Liquid window stays draggable on Windows after the console covers it."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import MP_Audio_Player_Liquid_Glass as vulkan_host
import MP_Audio_Player_Liquid_Glass_OpenGL as opengl_host
from windows_glass_drag import (
    HEADER_DRAG_PX,
    HTCAPTION,
    HTCLIENT,
    WM_NCLBUTTONDOWN,
    WM_NCHITTEST,
    WM_SYSCOMMAND,
    WM_WINDOWPOSCHANGED,
    GlassWindowDrag,
    console_should_pass_clicks,
    glass_hit,
    moved_origin,
    pack_point,
    release_stuck_mouse,
    unpack_point,
)


def _host():
    host = opengl_host.GlassHost(["player"])
    host.renderer = MagicMock()
    host.renderer.bezel_px = 7
    host.renderer.window_pos.return_value = (100, 200)
    host.renderer.window_size.return_value = (800, 600)
    host.renderer._cur_pos = (100, 200)
    host.toggle_maximize = MagicMock()
    host._place_terminal = MagicMock()
    host.child_xid = 0
    host.is_maximized = False
    return host


def _drag(host=None):
    host = host or _host()
    drag = GlassWindowDrag(host)
    drag._alt_down = lambda: False
    drag._call_old = MagicMock(return_value=0)
    drag._start_system_move = MagicMock()
    return drag


class TestDragGeometry(unittest.TestCase):
    def test_header_is_a_drag_and_the_console_lets_it_through(self):
        self.assertEqual(
            glass_hit(400, 20, 800, 600, on_close=False, on_slider=False, on_outer=False, alt_down=False, maximized=False),
            HTCAPTION,
        )
        self.assertTrue(console_should_pass_clicks(20, alt_down=False))
        self.assertLessEqual(HEADER_DRAG_PX, 90)

    def test_body_is_not_a_drag(self):
        self.assertEqual(
            glass_hit(400, 300, 800, 600, on_close=False, on_slider=False, on_outer=False, alt_down=False, maximized=False),
            HTCLIENT,
        )
        self.assertFalse(console_should_pass_clicks(300, alt_down=False))

    def test_close_and_slider_stay_clicks(self):
        self.assertEqual(
            glass_hit(794, 5, 800, 600, on_close=True, on_slider=False, on_outer=True, alt_down=False, maximized=False),
            HTCLIENT,
        )
        self.assertEqual(
            glass_hit(400, 570, 800, 600, on_close=False, on_slider=True, on_outer=False, alt_down=False, maximized=False),
            HTCLIENT,
        )

    def test_alt_drags_from_the_body(self):
        self.assertEqual(
            glass_hit(400, 300, 800, 600, on_close=False, on_slider=False, on_outer=False, alt_down=True, maximized=False),
            HTCAPTION,
        )
        self.assertTrue(console_should_pass_clicks(300, alt_down=True))

    def test_screen_delta_moves_the_window_origin(self):
        self.assertEqual(moved_origin((100, 200), (500, 220), (540, 260)), (140, 240))

    def test_signed_points_round_trip(self):
        self.assertEqual(unpack_point(pack_point(-20, -5)), (-20, -5))
        self.assertEqual(unpack_point(pack_point(500, 220)), (500, 220))


class TestGlassMessages(unittest.TestCase):
    def test_header_hit_is_caption_and_body_hit_is_client(self):
        drag = _drag()
        self.assertEqual(drag._dispatch(1, WM_NCHITTEST, 0, pack_point(500, 220)), HTCAPTION)
        self.assertEqual(drag._dispatch(1, WM_NCHITTEST, 0, pack_point(500, 500)), HTCLIENT)

    def test_close_button_and_slider_are_client_hits(self):
        drag = _drag()
        self.assertTrue(drag.host._on_close(794, 5, 800, 600))
        self.assertEqual(drag._dispatch(1, WM_NCHITTEST, 0, pack_point(894, 205)), HTCLIENT)
        self.assertEqual(drag._dispatch(1, WM_NCHITTEST, 0, pack_point(500, 770)), HTCLIENT)

    def test_outer_bezel_and_alt_drag(self):
        drag = _drag()
        self.assertEqual(drag._dispatch(1, WM_NCHITTEST, 0, pack_point(102, 500)), HTCAPTION)
        drag._alt_down = lambda: True
        self.assertEqual(drag._dispatch(1, WM_NCHITTEST, 0, pack_point(500, 500)), HTCAPTION)

    def test_caption_press_moves_and_the_second_press_maximizes(self):
        drag = _drag()
        point = pack_point(500, 220)
        self.assertEqual(drag._dispatch(1, WM_NCLBUTTONDOWN, HTCAPTION, point), 0)
        drag._start_system_move.assert_called_once_with(1)
        self.assertEqual(drag._dispatch(1, WM_NCLBUTTONDOWN, HTCAPTION, point), 0)
        drag._start_system_move.assert_called_once()
        drag.host.toggle_maximize.assert_called_once()

    def test_maximized_caption_does_not_move_until_the_second_press_restores(self):
        drag = _drag()
        drag.host.is_maximized = True
        point = pack_point(500, 220)
        drag._dispatch(1, WM_NCLBUTTONDOWN, HTCAPTION, point)
        drag._start_system_move.assert_not_called()
        drag._dispatch(1, WM_NCLBUTTONDOWN, HTCAPTION, point)
        drag.host.toggle_maximize.assert_called_once()
        drag._start_system_move.assert_not_called()

    def test_system_move_is_refused_while_maximized(self):
        drag = _drag()
        drag.host.is_maximized = True
        self.assertEqual(drag._dispatch(1, WM_SYSCOMMAND, 0xF012, 0), 0)
        drag._call_old.assert_not_called()
        drag.host.is_maximized = False
        drag._call_old.return_value = 9
        self.assertEqual(drag._dispatch(1, WM_SYSCOMMAND, 0xF012, 0), 9)

    def test_window_move_repositions_the_console(self):
        drag = _drag()
        drag._follow = MagicMock()
        drag._call_old.return_value = 41
        self.assertEqual(drag._dispatch(1, WM_WINDOWPOSCHANGED, 0, 0), 41)
        drag._follow.assert_called_once()


class TestConsoleFallbackDrag(unittest.TestCase):
    def test_header_drag_follows_the_pointer_and_a_second_press_maximizes(self):
        drag = _drag()
        drag.glass_hwnd = 0
        self.assertEqual(drag.poll_pointer(True, 500, 220, True), "drag")
        self.assertTrue(drag.host._os_dragging)
        self.assertEqual(drag.poll_pointer(True, 540, 260, True), "drag")
        drag.host.renderer.set_window_pos.assert_called_with(140, 240)
        self.assertEqual(drag.poll_pointer(False, 540, 260, True), "drop")
        self.assertFalse(drag.host._os_dragging)
        self.assertEqual(drag.poll_pointer(True, 500, 220, True), "toggle")
        drag.host.toggle_maximize.assert_called_once()

    def test_body_click_does_not_move_the_window(self):
        drag = _drag()
        drag.glass_hwnd = 0
        self.assertEqual(drag.poll_pointer(True, 500, 500, True), "pass")
        drag.host.renderer.set_window_pos.assert_not_called()
        self.assertFalse(getattr(drag.host, "_os_dragging", False))

    def test_press_outside_the_console_does_not_drag_when_the_pointer_enters_it(self):
        drag = _drag()
        drag.glass_hwnd = 0
        self.assertEqual(drag.poll_pointer(True, 500, 220, False), "pass")
        self.assertEqual(drag.poll_pointer(True, 500, 220, True), "pass")
        drag.host.renderer.set_window_pos.assert_not_called()

    def test_update_passes_header_clicks_through_and_polls_when_that_fails(self):
        drag = _drag()
        drag.glass_hwnd = 1
        drag.console_hwnd = 2
        drag._subclassed = True
        drag._window_rect = lambda _hwnd: (100, 200, 800, 600)
        drag._cursor_pos = lambda: (500, 220)
        passed = []
        drag._set_click_through = lambda enabled: passed.append(enabled) or True
        drag.poll_pointer = MagicMock(return_value="pass")
        drag.update()
        self.assertEqual(passed, [True])
        drag.poll_pointer.assert_not_called()

        passed.clear()
        drag._cursor_pos = lambda: (500, 500)
        drag.update()
        self.assertEqual(passed, [False])

        drag._set_click_through = lambda enabled: False
        drag._button_down = lambda: False
        drag._cursor_on_console = lambda _sx, _sy: True
        drag.update()
        drag.poll_pointer.assert_called()


class TestStuckMouseAndHostWiring(unittest.TestCase):
    def test_release_over_the_console_clears_a_stuck_glfw_button(self):
        renderer = MagicMock()
        renderer.mouse_down = True
        with patch("windows_glass_drag.left_button_held", return_value=False):
            release_stuck_mouse(renderer)
        self.assertFalse(renderer.mouse_down)
        renderer.mouse_down = True
        with patch("windows_glass_drag.left_button_held", return_value=True):
            release_stuck_mouse(renderer)
        self.assertTrue(renderer.mouse_down)

    def test_os_drag_does_not_let_the_glass_loop_pin_the_window(self):
        for module in (opengl_host, vulkan_host):
            host = module.GlassHost(["player"])
            host.renderer = MagicMock()
            host.renderer.bezel_px = 7
            host.renderer.mouse_down = True
            host.renderer.cursor = (100, 10)
            host.renderer.window_size.return_value = (800, 600)
            host.renderer.window_pos.return_value = (50, 50)
            host.renderer.root_pointer.return_value = (150, 60)
            host._os_dragging = True
            _down, dragging, *_rest = host._track_drag(False, False, (50, 50), (0, 0))
            self.assertFalse(dragging, module.__name__)
            host.renderer.set_window_pos.assert_not_called()

    def test_sync_attaches_the_glass_and_the_console(self):
        host = opengl_host.GlassHost(["player"])
        host.renderer = MagicMock()
        host.renderer.win32_window.return_value = 55
        host.child_xid = 77
        with patch("windows_glass_drag.GlassWindowDrag._subclass"):
            host._sync_windows_drag()
        self.assertEqual(host._glass_drag.glass_hwnd, 55)
        self.assertEqual(host._glass_drag.console_hwnd, 77)

    def test_pump_updates_drag_and_close_releases_it(self):
        host = opengl_host.GlassHost(["player"])
        host.renderer = MagicMock()
        host.renderer.mouse_down = False
        drag = MagicMock()
        host._glass_drag = drag
        host._pump_windows_drag()
        drag.update.assert_called_once()
        host.close()
        drag.close.assert_called_once()
        self.assertIsNone(host._glass_drag)

    def test_windows_run_loop_keeps_the_drag_alive(self):
        for name in ("MP_Audio_Player_Liquid_Glass_OpenGL.py", "MP_Audio_Player_Liquid_Glass.py"):
            source = (ROOT / name).read_text(encoding="utf-8")
            run = source.split("def _run_windows", 1)[1].split("\n    def ", 1)[0]
            close = source.split("def close(", 1)[1].split("\n    def ", 1)[0]
            self.assertIn("_sync_windows_drag()", run, name)
            self.assertIn("_pump_windows_drag()", run, name)
            self.assertIn("_release_windows_drag()", close, name)


if __name__ == "__main__":
    unittest.main()
