#!/usr/bin/env python3
"""Cross-platform unit tests for MP Liquid Visualizer on Windows 10/11 and macOS (Darwin/MoltenVK)."""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import MP_Liquid_Visualizer as vis_entry
import MP_Audio_Player
from scripts import mp_liquid_visualizer_vulkan as vis


class TestPlatformDetection(unittest.TestCase):
    """Verifies Windows 10/11 and macOS platform detection helpers."""

    def test_windows_platform_detection(self):
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            self.assertTrue(vis.is_windows())
            self.assertTrue(vis_entry.is_windows())
            self.assertFalse(vis.is_macos())
            self.assertFalse(vis_entry.is_macos())

    def test_windows_10_and_11_detection(self):
        # Windows 10 build 19045
        win10 = MagicMock()
        win10.major = 10
        win10.minor = 0
        win10.build = 19045

        # Windows 11 build 22631
        win11 = MagicMock()
        win11.major = 10
        win11.minor = 0
        win11.build = 22631

        # Windows 7 build 7601 (unsupported)
        win7 = MagicMock()
        win7.major = 6
        win7.minor = 1
        win7.build = 7601

        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            with patch("sys.getwindowsversion", return_value=win10, create=True):
                self.assertTrue(vis.is_windows_10_or_11())
                self.assertTrue(vis_entry.is_windows_10_or_11())

            with patch("sys.getwindowsversion", return_value=win11, create=True):
                self.assertTrue(vis.is_windows_10_or_11())
                self.assertTrue(vis_entry.is_windows_10_or_11())

            with patch("sys.getwindowsversion", return_value=win7, create=True):
                self.assertFalse(vis.is_windows_10_or_11())
                self.assertFalse(vis_entry.is_windows_10_or_11())

    def test_macos_platform_detection(self):
        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            self.assertTrue(vis.is_macos())
            self.assertTrue(vis_entry.is_macos())
            self.assertFalse(vis.is_windows())
            self.assertFalse(vis.is_windows_10_or_11())

    def test_apple_silicon_detection(self):
        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                self.assertTrue(vis.is_apple_silicon())
                self.assertTrue(vis_entry.is_apple_silicon())

            with patch("platform.machine", return_value="aarch64"):
                self.assertTrue(vis.is_apple_silicon())

            with patch("platform.machine", return_value="x86_64"):
                self.assertFalse(vis.is_apple_silicon())


class TestLibraryLoading(unittest.TestCase):
    """Verifies GLFW and Vulkan DLL loading candidate paths across Windows, macOS, and Linux."""

    def test_glfw_loading_candidates_on_windows(self):
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            with patch("ctypes.CDLL") as mock_cdll:
                mock_cdll.return_value = MagicMock()
                dll = vis.load_glfw_dll()
                self.assertIsNotNone(dll)
                called_path = str(mock_cdll.call_args[0][0]).lower()
                self.assertIn("glfw", called_path)

    def test_glfw_loading_candidates_on_macos(self):
        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            with patch("ctypes.CDLL") as mock_cdll:
                mock_cdll.return_value = MagicMock()
                dll = vis.load_glfw_dll()
                self.assertIsNotNone(dll)
                called_path = str(mock_cdll.call_args[0][0])
                self.assertTrue("glfw" in called_path and (".dylib" in called_path or "opt" in called_path))

    def test_vulkan_loading_candidates_on_windows(self):
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            with patch("ctypes.CDLL") as mock_cdll:
                mock_cdll.return_value = MagicMock()
                dll = vis.load_vulkan_dll()
                self.assertIsNotNone(dll)
                called_path = str(mock_cdll.call_args[0][0]).lower()
                self.assertIn("vulkan", called_path)

    def test_vulkan_loading_candidates_on_macos(self):
        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            with patch("ctypes.CDLL") as mock_cdll:
                mock_cdll.return_value = MagicMock()
                dll = vis.load_vulkan_dll()
                self.assertIsNotNone(dll)
                called_path = str(mock_cdll.call_args[0][0])
                self.assertTrue("vulkan" in called_path or "MoltenVK" in called_path)


class TestRendererWindowHandlesAndPointer(unittest.TestCase):
    """Verifies native window handles and mouse query adaptations on Windows and macOS."""

    def test_win32_window_handle(self):
        renderer = vis.LiquidVisualizerVulkanRenderer()
        renderer._window = 0x54321
        renderer._glfw = MagicMock()
        renderer._glfw.glfwGetWin32Window.return_value = 0x99999

        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            self.assertEqual(renderer.win32_window(), 0x99999)
            self.assertEqual(renderer.cocoa_window(), 0)
            self.assertEqual(renderer.x11_window(), 0)
            self.assertIsNone(renderer.x11_display())

    def test_cocoa_window_handle(self):
        renderer = vis.LiquidVisualizerVulkanRenderer()
        renderer._window = 0x54321
        renderer._glfw = MagicMock()
        renderer._glfw.glfwGetCocoaWindow.return_value = 0x77777

        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            self.assertEqual(renderer.cocoa_window(), 0x77777)
            self.assertEqual(renderer.win32_window(), 0)
            self.assertEqual(renderer.x11_window(), 0)
            self.assertIsNone(renderer.x11_display())

    def test_root_pointer_win32_fallback(self):
        renderer = vis.LiquidVisualizerVulkanRenderer()
        renderer._cur_pos = (200, 300)
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            pos = renderer.root_pointer()
            self.assertEqual(pos, (200, 300))

    def test_root_pointer_macos_fallback(self):
        renderer = vis.LiquidVisualizerVulkanRenderer()
        renderer._cur_pos = (150, 250)
        renderer.cursor = (50.0, 75.0)
        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            pos = renderer.root_pointer()
            self.assertEqual(pos, (200, 325))

    def test_open_skips_x11_on_macos_and_windows(self):
        """Renderer.open() must not load libX11.so on Windows or macOS."""
        renderer = vis.LiquidVisualizerVulkanRenderer()

        # On Windows
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            with patch("scripts.mp_liquid_visualizer_vulkan.load_glfw_dll") as mock_lg:
                mock_lg.return_value = MagicMock()
                mock_lg.return_value.glfwInit.return_value = 0  # Fail early after init
                with self.assertRaises(RuntimeError):
                    renderer.open()
                self.assertIsNone(renderer._x11)

        # On macOS
        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            with patch("scripts.mp_liquid_visualizer_vulkan.load_glfw_dll") as mock_lg:
                mock_lg.return_value = MagicMock()
                mock_lg.return_value.glfwInit.return_value = 0  # Fail early after init
                with self.assertRaises(RuntimeError):
                    renderer.open()
                self.assertIsNone(renderer._x11)


class TestMoltenVKAndPortabilitySupport(unittest.TestCase):
    """Verifies MoltenVK portability flags and extensions on macOS."""

    def test_moltenvk_portability_instance_flag_on_macos(self):
        renderer = vis.LiquidVisualizerVulkanRenderer()
        renderer._glfw = MagicMock()
        renderer._vulkan = MagicMock()
        renderer._vulkan.vkCreateInstance.return_value = 0

        # Simulate GLFW required instance extensions
        req_exts = [b"VK_KHR_surface"]
        count = ctypes.c_uint32(len(req_exts))
        arr = (ctypes.c_char_p * len(req_exts))(*req_exts)
        renderer._glfw.glfwGetRequiredInstanceExtensions.return_value = arr

        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            renderer._create_instance()
            info = renderer._instance_info
            # Flag VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR = 0x00000001 must be set
            self.assertTrue(bool(info.flags & vis.VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR))
            self.assertIn(b"VK_KHR_portability_enumeration", renderer._ext_names)


class TestCrossPlatformKeyHandlingAndLaunchers(unittest.TestCase):
    """Verifies cross-platform keybindings, player termination, and launcher scripts."""

    def test_shift_k_kill_command_cross_platform(self):
        renderer = vis.LiquidVisualizerVulkanRenderer()

        # On Windows: uses taskkill and PowerShell
        with patch("sys.platform", "win32"), patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                renderer._on_key(None, 75, 0, vis.GLFW_PRESS, 1)  # Shift+K
                self.assertEqual(mock_run.call_count, 2)
                first_call = str(mock_run.call_args_list[0])
                self.assertIn("taskkill", first_call)

        # On macOS / Linux: uses pkill
        with patch("sys.platform", "darwin"), patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                renderer._on_key(None, 75, 0, vis.GLFW_PRESS, 1)  # Shift+K
                self.assertEqual(mock_run.call_count, 1)
                call_str = str(mock_run.call_args_list[0])
                self.assertIn("pkill", call_str)

    def test_windows_launch_liquid_visualizer_bat_exists(self):
        root_bat = ROOT / "launch_liquid_visualizer.bat"
        scripts_bat = ROOT / "scripts" / "launch_liquid_visualizer.bat"
        self.assertTrue(root_bat.is_file(), "launch_liquid_visualizer.bat must exist in root")
        self.assertTrue(scripts_bat.is_file(), "launch_liquid_visualizer.bat must exist in scripts")

        content = scripts_bat.read_text(encoding="utf-8")
        self.assertIn("MP Liquid Visualizer", content)
        self.assertIn("MP_Liquid_Visualizer.py", content)

    def test_launch_liquid_visualizer_sh_cross_platform(self):
        sh_script = ROOT / "scripts" / "launch_liquid_visualizer.sh"
        self.assertTrue(sh_script.is_file())
        self.assertTrue(os.access(sh_script, os.X_OK))

        content = sh_script.read_text(encoding="utf-8")
        self.assertIn("/opt/homebrew/bin", content)
        self.assertIn("MP_Liquid_Visualizer.py", content)

    def test_mix_archive_manager_visualizer_cli_command(self):
        mam_sh = ROOT / "Mix_Archive_Manager.sh"
        content = mam_sh.read_text(encoding="utf-8")
        self.assertIn("visualizer|--visualizer|vis|--vis", content)
        self.assertIn("launch_mp_liquid_visualizer", content)

        bin_script = ROOT / "bin" / "mix-archive-manager"
        bin_content = bin_script.read_text(encoding="utf-8")
        self.assertIn('"visualizer"', bin_content)
        self.assertIn("MP_Liquid_Visualizer.py", bin_content)


if __name__ == "__main__":
    unittest.main()
