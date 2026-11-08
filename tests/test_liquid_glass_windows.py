"""Tests for Liquid Glass Audio Player Windows 10 & 11 support across OpenGL and Vulkan."""

import os
import platform
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import liquid_glass_opengl
import liquid_glass_vulkan
import MP_Audio_Player
import MP_Audio_Player_Liquid_Glass
import MP_Audio_Player_Liquid_Glass_OpenGL


class TestWindowsPlatformDetection(unittest.TestCase):
    """Verifies Windows 10 and 11 platform detection logic."""

    def test_is_windows_detected(self):
        with patch("sys.platform", "win32"):
            self.assertTrue(liquid_glass_opengl.is_windows())
            self.assertTrue(liquid_glass_vulkan.is_windows())

    def test_is_not_windows_on_linux(self):
        with patch("sys.platform", "linux"), patch("platform.system", return_value="Linux"):
            self.assertFalse(liquid_glass_opengl.is_windows())
            self.assertFalse(liquid_glass_vulkan.is_windows())

    def test_windows_10_and_11_versions(self):
        # Windows 10 build 19045
        mock_win10 = MagicMock()
        mock_win10.major = 10
        mock_win10.minor = 0
        mock_win10.build = 19045

        # Windows 11 build 22631
        mock_win11 = MagicMock()
        mock_win11.major = 10
        mock_win11.minor = 0
        mock_win11.build = 22631

        # Windows 7 build 7601 (unsupported legacy)
        mock_win7 = MagicMock()
        mock_win7.major = 6
        mock_win7.minor = 1
        mock_win7.build = 7601

        with patch("sys.platform", "win32"):
            with patch("sys.getwindowsversion", return_value=mock_win10, create=True):
                self.assertTrue(liquid_glass_opengl.is_windows_10_or_11())
                self.assertTrue(liquid_glass_vulkan.is_windows_10_or_11())

            with patch("sys.getwindowsversion", return_value=mock_win11, create=True):
                self.assertTrue(liquid_glass_opengl.is_windows_10_or_11())
                self.assertTrue(liquid_glass_vulkan.is_windows_10_or_11())

            with patch("sys.getwindowsversion", return_value=mock_win7, create=True):
                self.assertFalse(liquid_glass_opengl.is_windows_10_or_11())
                self.assertFalse(liquid_glass_vulkan.is_windows_10_or_11())


class TestWindowsOpenGLRenderer(unittest.TestCase):
    """Verifies Windows-specific DLL loading and Win32 adaptations for OpenGL."""

    def test_glfw_dll_candidates_on_windows(self):
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            with patch("ctypes.CDLL") as mock_cdll:
                mock_cdll.return_value = MagicMock()
                dll = liquid_glass_opengl.load_glfw_dll()
                self.assertIsNotNone(dll)
                # First attempt should load glfw3.dll or resolved path
                called_arg = mock_cdll.call_args[0][0]
                self.assertTrue("glfw" in str(called_arg).lower())

    def test_win32_window_and_pointer_methods(self):
        renderer = liquid_glass_opengl.LiquidGlassRendererOpenGL(800, 600)
        renderer._window = 0x12345
        renderer._glfw = MagicMock()
        renderer._glfw.glfwGetWin32Window.return_value = 0xABCDE

        with patch("sys.platform", "win32"):
            hwnd = renderer.win32_window()
            self.assertEqual(hwnd, 0xABCDE)
            # x11_window returns 0 on win32
            self.assertEqual(renderer.x11_window(), 0)
            self.assertIsNone(renderer.x11_display())

    def test_root_pointer_win32_fallback(self):
        renderer = liquid_glass_opengl.LiquidGlassRendererOpenGL(800, 600)
        renderer._cur_pos = (120, 140)
        with patch("sys.platform", "win32"):
            # When ctypes.windll.user32.GetCursorPos is unavailable or fails, returns window_pos
            pos = renderer.root_pointer()
            self.assertEqual(pos, (120, 140))


class TestWindowsVulkanRenderer(unittest.TestCase):
    """Verifies Windows-specific DLL loading, GPU selection, and Win32 adaptations for Vulkan."""

    def test_vulkan_dll_loading_on_windows(self):
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            with patch("ctypes.CDLL") as mock_cdll:
                mock_cdll.return_value = MagicMock()
                dll = liquid_glass_vulkan.load_vulkan_dll()
                self.assertIsNotNone(dll)
                called_arg = mock_cdll.call_args[0][0]
                self.assertTrue("vulkan" in str(called_arg).lower())

    def test_select_gpu_on_windows_supports_all_vendors(self):
        devices = [
            {"name": "AMD Radeon RX 7900 XTX", "vendor_id": 0x1002, "device_type": 2},
            {"name": "Intel Arc A770", "vendor_id": 0x8086, "device_type": 2},
        ]
        with patch("sys.platform", "win32"):
            chosen = liquid_glass_vulkan.select_nvidia_device(devices)
            self.assertEqual(chosen, 0)

        # But with NVIDIA present, it prioritizes NVIDIA:
        devices_with_nvidia = [
            {"name": "AMD Radeon Graphics", "vendor_id": 0x1002, "device_type": 1},
            {"name": "NVIDIA GeForce RTX 4080", "vendor_id": 0x10DE, "device_type": 2},
        ]
        with patch("sys.platform", "win32"):
            chosen_nv = liquid_glass_vulkan.select_nvidia_device(devices_with_nvidia)
            self.assertEqual(chosen_nv, 1)

    def test_vulkan_summary_shows_correct_vendor_on_windows(self):
        renderer = liquid_glass_vulkan.LiquidGlassRenderer(800, 600)
        renderer.device_name = "AMD Radeon RX 6800 XT"
        renderer.vendor_id = 0x1002
        renderer.device_type = 2
        self.assertIn("AMD", renderer.summary)
        self.assertIn("RX 6800 XT", renderer.summary)


class TestWindowsPlayerHosts(unittest.TestCase):
    """Verifies that OpenGL and Vulkan player hosts gracefully adapt to Windows (no GTK/VTE required)."""

    def test_opengl_gtk_import_returns_none_on_windows(self):
        with patch("sys.platform", "win32"):
            glib, gtk, vte = MP_Audio_Player_Liquid_Glass_OpenGL._import_gtk()
            self.assertIsNone(glib)
            self.assertIsNone(gtk)
            self.assertIsNone(vte)

    def test_vulkan_gtk_import_returns_none_on_windows(self):
        with patch("sys.platform", "win32"):
            glib, gtk, vte = MP_Audio_Player_Liquid_Glass._import_gtk()
            self.assertIsNone(glib)
            self.assertIsNone(gtk)
            self.assertIsNone(vte)

    def test_glass_host_handles_none_terminal_on_windows(self):
        # On Windows, self.terminal is None (hosted via console HWND), so toggle_maximize and set_mode must not crash
        host_gl = MP_Audio_Player_Liquid_Glass_OpenGL.GlassHost(["test"], mode="NORMAL")
        host_gl.renderer = MagicMock()
        host_gl.renderer.bezel_px = 7
        host_gl.renderer.window_pos.return_value = (100, 100)
        host_gl.renderer.window_size.return_value = (1280, 820)
        host_gl.renderer.get_workarea.return_value = (0, 0, 1920, 1080)

        # Should toggle maximize without raising AttributeError or returning False
        host_gl.toggle_maximize()
        self.assertTrue(host_gl.is_maximized)
        host_gl.toggle_maximize()
        self.assertFalse(host_gl.is_maximized)

        # Mode switching without terminal
        host_gl.set_mode("MINI")
        self.assertEqual(host_gl.mode, "MINI")
        host_gl.set_mode("MICRO")
        self.assertEqual(host_gl.mode, "MICRO")
        host_gl.set_mode("NORMAL")
        self.assertEqual(host_gl.mode, "NORMAL")


class TestAudioPlayerWindowsIntegration(unittest.TestCase):
    """Verifies MP_Audio_Player.py and launcher scripts support Windows 10 & 11."""

    def test_launch_liquid_glass_player_on_windows(self):
        with patch("sys.platform", "win32"):
            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.pid = 98765
                mock_popen.return_value = mock_proc

                # Test OpenGL default on Windows
                with patch.dict(os.environ, {"LIQUID_GLASS_BACKEND": "opengl"}):
                    ok = MP_Audio_Player.launch_liquid_glass_player(base_dir=ROOT)
                    self.assertTrue(ok)
                    called_args = mock_popen.call_args[0][0]
                    self.assertTrue(any("OpenGL" in str(arg) for arg in called_args))
                    # creationflags should include DETACHED_PROCESS (0x8)
                    flags = mock_popen.call_args[1].get("creationflags", 0)
                    self.assertTrue(flags & 0x00000008)

                # Test Vulkan option on Windows
                with patch.dict(os.environ, {"LIQUID_GLASS_BACKEND": "vulkan"}):
                    ok_vk = MP_Audio_Player.launch_liquid_glass_player(base_dir=ROOT)
                    self.assertTrue(ok_vk)
                    called_args_vk = mock_popen.call_args[0][0]
                    self.assertTrue(any(str(arg).endswith("MP_Audio_Player_Liquid_Glass.py") for arg in called_args_vk))

    def test_windows_launch_bat_exists_and_defaults_to_opengl(self):
        bat = ROOT / "scripts" / "launch_liquid_glass.bat"
        self.assertTrue(bat.is_file(), f"Missing {bat}")
        content = bat.read_text(encoding="utf-8")
        self.assertIn("MP Liquid Glass Audio Player", content)
        self.assertIn("Windows 10 & 11", content)
        self.assertIn('set "BACKEND=opengl"', content)
        self.assertIn("MP_Audio_Player_Liquid_Glass_OpenGL.py", content)
        self.assertIn("MP_Audio_Player_Liquid_Glass.py", content)

    def test_root_launch_bat_exists(self):
        root_bat = ROOT / "launch_liquid_glass.bat"
        self.assertTrue(root_bat.is_file(), f"Missing {root_bat}")
        content = root_bat.read_text(encoding="utf-8")
        self.assertIn("scripts\\launch_liquid_glass.bat", content)


if __name__ == "__main__":
    unittest.main()
