#!/usr/bin/env python3
"""
Unit tests for 64-bit Windows MP Mix Archive Manager launcher:
- MP_Mix_Manager.exe exists and is a 64-bit Windows PE32+ executable
- manager.exe exists and is a 64-bit Windows PE32+ executable
- Executable contains standard PE headers and sections
- Executable source scripts/windows_launcher.c and resource scripts/windows_launcher.rc exist
"""

import unittest
import struct
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EXE_PATH = BASE_DIR / "MP_Mix_Manager.exe"
MGR_EXE_PATH = BASE_DIR / "manager.exe"
SRC_PATH = BASE_DIR / "scripts" / "windows_launcher.c"
RC_PATH = BASE_DIR / "scripts" / "windows_launcher.rc"


class TestWindowsLauncherExe(unittest.TestCase):
    def test_launcher_sources_exist(self):
        """Verifies that windows_launcher C source and RC resource exist."""
        self.assertTrue(SRC_PATH.is_file(), f"Missing {SRC_PATH}")
        self.assertTrue(RC_PATH.is_file(), f"Missing {RC_PATH}")

    def test_exe_files_exist_and_non_empty(self):
        """Verifies that MP_Mix_Manager.exe and manager.exe exist and have non-zero size."""
        self.assertTrue(EXE_PATH.is_file(), f"Missing {EXE_PATH}")
        self.assertGreater(EXE_PATH.stat().st_size, 1024)
        self.assertTrue(MGR_EXE_PATH.is_file(), f"Missing {MGR_EXE_PATH}")
        self.assertGreater(MGR_EXE_PATH.stat().st_size, 1024)

    def test_exe_is_pe32_plus_64bit(self):
        """Verifies that MP_Mix_Manager.exe has valid DOS and PE32+ (x86-64) headers."""
        data = EXE_PATH.read_bytes()

        # DOS Header check ("MZ")
        self.assertEqual(data[:2], b"MZ", "Missing DOS 'MZ' signature")

        # PE header offset at 0x3C
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        self.assertLess(pe_offset, len(data) - 24)

        # PE Signature ("PE\0\0")
        pe_sig = data[pe_offset:pe_offset + 4]
        self.assertEqual(pe_sig, b"PE\x00\x00", "Missing PE signature")

        # Machine type (0x8664 = x86-64)
        machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
        self.assertEqual(machine, 0x8664, f"Expected machine 0x8664 (x86-64), got 0x{machine:04X}")

        # Magic in Optional Header (0x020b = PE32+ / 64-bit)
        magic = struct.unpack_from("<H", data, pe_offset + 24)[0]
        self.assertEqual(magic, 0x020B, f"Expected PE32+ magic 0x020B, got 0x{magic:04X}")

    def test_manager_exe_is_identical_or_valid_pe32_plus(self):
        """Verifies that manager.exe is also valid PE32+ 64-bit."""
        data = MGR_EXE_PATH.read_bytes()
        self.assertEqual(data[:2], b"MZ")
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
        self.assertEqual(machine, 0x8664)


if __name__ == "__main__":
    unittest.main()
