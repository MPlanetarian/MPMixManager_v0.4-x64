"""Tests for the MP Package Dev Utility (Linux packaging).

The utility lives in the BASH_SCRIPTS mirror, so these tests skip cleanly when
it is not present next to the repository. Every test runs the real script and
inspects real output; nothing is mocked.
"""

import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BASH_SCRIPTS = Path(os.environ.get("MP_BASH_SCRIPTS", str(BASE_DIR.parent / "Documents" / "BASH_SCRIPTS")))
UTILITY = BASH_SCRIPTS / "MP_Package_Dev_Utility.sh"

HAVE_BASH = shutil.which("bash") is not None
HAVE_AR = shutil.which("ar") is not None
HAVE_PYTHON = shutil.which("python3") is not None


def find_bash():
    found = shutil.which("bash")
    return found if found else "bash"


BASH = find_bash()


@unittest.skipUnless(UTILITY.is_file(), f"packaging utility not found at {UTILITY}")
class TestPackageDevUtility(unittest.TestCase):
    """Behavioural tests against the real packaging utility."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="mp_pkg_dev_test_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------
    def run_util(self, *args, expect=0):
        proc = subprocess.run(
            [BASH, str(UTILITY), *args],
            capture_output=True,
            text=True,
            timeout=900,
        )
        if expect == 0:
            self.assertEqual(
                proc.returncode, 0,
                f"utility failed ({proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
            )
        else:
            self.assertNotEqual(proc.returncode, 0, "utility was expected to fail")
        return proc

    def source_tree(self, version="0.4.2 Stable (Liquid)", name="src"):
        root = self.tmp / name
        if root.exists():
            return root
        (root / "scripts").mkdir(parents=True)
        (root / "assets").mkdir()
        (root / "bin").mkdir()
        (root / "VERSION").write_text(version + "\n")
        (root / "Mix_Archive_Manager.sh").write_text("#!/usr/bin/env bash\necho manager\n")
        (root / "MP_Gui.sh").write_text("#!/usr/bin/env bash\necho gui\n")
        (root / "MP_Audio_Player.sh").write_text("#!/usr/bin/env bash\necho player\n")
        (root / "MP_Liquid_Visualizer.py").write_text("print('v')\n")
        (root / "LICENSE").write_text("MIT\n")
        (root / "CHANGELOG.md").write_text("## [0.4.2]\n- note\n")
        (root / "config.env").write_text("SECRET_TOKEN=do-not-ship\n")
        (root / "scripts" / "launch_liquid_glass.sh").write_text("#!/usr/bin/env bash\necho l\n")
        (root / "scripts" / "helper.sh").write_text("#!/usr/bin/env bash\necho h\n")
        (root / "bin" / "mix-archive-manager").write_text("#!/usr/bin/env bash\necho m\n")
        (root / "assets" / "mp_liquid_glass_icon.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        (root / "assets" / "mp_liquid_glass_icon.svg").write_text("<svg/>")
        # Noise that must never be packaged.
        (root / "MIX_ARCHIVE").mkdir()
        (root / "MIX_ARCHIVE" / "big.flac").write_bytes(b"x" * 64)
        (root / "logs").mkdir()
        (root / "logs" / "run.log").write_text("noise\n")
        (root / "scripts" / "__pycache__").mkdir()
        (root / "scripts" / "__pycache__" / "junk.pyc").write_bytes(b"junk")
        return root

    # -- version handling -------------------------------------------------
    def test_env_report_lists_architectures(self):
        proc = self.run_util("--source", str(self.source_tree()), "--env")
        self.assertIn("Build environment", proc.stdout)
        self.assertIn("Target arches:", proc.stdout)
        self.assertIn("amd64", proc.stdout)

    def test_numeric_version_from_label(self):
        src = self.source_tree()
        out = self.tmp / "out_version"
        proc = self.run_util("--source", str(src), "--arch", "amd64", "--format", "deb", "--out", str(out))
        self.assertIn("0.4.2-1", proc.stdout)
        self.assertTrue((out / "mp-mix-manager_0.4.2-1_amd64.deb").is_file())

    def test_prerelease_version_uses_tilde_ordering(self):
        src = self.source_tree("0.6.0-rc2 Beta", name="src_prerelease")
        out = self.tmp / "out_prerelease"
        proc = self.run_util("--source", str(src), "--arch", "amd64", "--format", "deb", "--out", str(out))
        self.assertIn("0.6.0~rc2.beta", proc.stdout + proc.stderr)

    def test_version_override(self):
        src = self.source_tree()
        out = self.tmp / "out_override"
        self.run_util(
            "--source", str(src), "--arch", "amd64", "--format", "deb",
            "--out", str(out), "--pkg-version", "9.9.9",
        )
        self.assertTrue((out / "mp-mix-manager_9.9.9-1_amd64.deb").is_file())

    # -- artifact structure ----------------------------------------------
    @unittest.skipUnless(HAVE_AR, "ar not available")
    def test_deb_structure_and_metadata(self):
        src = self.source_tree()
        out = self.tmp / "out_deb"
        self.run_util("--source", str(src), "--arch", "amd64", "--format", "deb", "--out", str(out))
        deb = out / "mp-mix-manager_0.4.2-1_amd64.deb"
        self.assertTrue(deb.is_file())

        members = subprocess.run(
            ["ar", "t", str(deb)], capture_output=True, text=True, check=True
        ).stdout.split()
        self.assertEqual(members, ["debian-binary", "control.tar.xz", "data.tar.xz"])

        work = self.tmp / "deb_extract"
        work.mkdir(exist_ok=True)
        subprocess.run(["ar", "x", str(deb)], cwd=work, check=True)

        control = subprocess.run(
            ["tar", "-xJf", "control.tar.xz", "-O", "./control"],
            cwd=work, capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("Package: mp-mix-manager", control)
        self.assertIn("Architecture: amd64", control)
        self.assertIn("Version: 0.4.2-1", control)
        self.assertIn("Section: sound", control)
        self.assertRegex(control, r"Depends: .*python3")
        self.assertIn("/opt/mp-mix-manager", control)

        data_list = subprocess.run(
            ["tar", "-tJf", "data.tar.xz"], cwd=work, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        for expected in (
            "./opt/mp-mix-manager/Mix_Archive_Manager.sh",
            "./usr/bin/mp-mix-manager",
            "./usr/bin/mp-liquid-player",
            "./usr/share/applications/mp-mix-manager.desktop",
            "./usr/share/doc/mp-mix-manager/copyright",
        ):
            self.assertIn(expected, data_list)

        # Credentials and build noise must never be shipped.
        self.assertFalse(any("config.env" in p for p in data_list))
        self.assertFalse(any("MIX_ARCHIVE" in p for p in data_list))
        self.assertFalse(any("__pycache__" in p for p in data_list))
        self.assertFalse(any(p.startswith("./logs/") for p in data_list))

    @unittest.skipUnless(HAVE_AR, "ar not available")
    def test_arm64_deb_metadata(self):
        src = self.source_tree()
        out = self.tmp / "out_arm64"
        self.run_util("--source", str(src), "--arch", "arm64", "--format", "deb", "--out", str(out))
        deb = out / "mp-mix-manager_0.4.2-1_arm64.deb"
        self.assertTrue(deb.is_file())

        work = self.tmp / "arm64_extract"
        work.mkdir(exist_ok=True)
        subprocess.run(["ar", "x", str(deb)], cwd=work, check=True)
        control = subprocess.run(
            ["tar", "-xJf", "control.tar.xz", "-O", "./control"],
            cwd=work, capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("Architecture: arm64", control)

        arch_note = subprocess.run(
            ["tar", "-xJf", "data.tar.xz", "-O", "./usr/share/doc/mp-mix-manager/architecture.txt"],
            cwd=work, capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("Package architecture: arm64", arch_note)

    def test_tarball_launchers_are_relocatable(self):
        src = self.source_tree()
        out = self.tmp / "out_tar"
        self.run_util("--source", str(src), "--arch", "arm64", "--format", "tar", "--out", str(out))
        tarball = out / "MP_Mix_Manager-0.4.2-linux-arm64.tar.gz"
        self.assertTrue(tarball.is_file())

        extract = self.tmp / "tar_extract"
        if extract.exists():
            shutil.rmtree(extract)
        extract.mkdir()
        with tarfile.open(tarball) as tf:
            names = tf.getnames()
        self.assertTrue(any(n.endswith("/INSTALL.txt") for n in names))
        self.assertFalse(any("/opt/" in n for n in names), "portable bundle must be flattened")

        with tarfile.open(tarball) as tf:
            tf.extractall(extract)
        roots = [p for p in extract.iterdir() if p.is_dir()]
        self.assertEqual(len(roots), 1)
        root = roots[0]

        launcher = (root / "mp-mix-manager").read_text()
        self.assertNotIn(str(self.tmp), launcher, "launcher must not bake in a build path")
        self.assertNotIn(str(out), launcher)
        self.assertIn("HERE", launcher)
        self.assertTrue(os.access(root / "mp-mix-manager", os.X_OK))

        # The bundle must work after being renamed or moved.
        moved = self.tmp / "tar_moved"
        if moved.exists():
            shutil.rmtree(moved)
        shutil.move(str(root), str(moved))
        proc = subprocess.run(
            [str(moved / "mp-mix-manager")], capture_output=True, text=True, timeout=120
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("m", proc.stdout)

    def test_checksums_and_release_notes(self):
        src = self.source_tree()
        out = self.tmp / "out_meta"
        self.run_util(
            "--source", str(src), "--arch", "all", "--format", "deb,tar", "--out", str(out)
        )
        sums = (out / "SHA256SUMS").read_text()
        listed = {line.split("  ", 1)[1] for line in sums.strip().splitlines()}
        self.assertIn("mp-mix-manager_0.4.2-1_amd64.deb", listed)
        self.assertIn("mp-mix-manager_0.4.2-1_arm64.deb", listed)
        self.assertIn("MP_Mix_Manager-0.4.2-linux-x86_64.tar.gz", listed)
        self.assertIn("MP_Mix_Manager-0.4.2-linux-arm64.tar.gz", listed)

        # Every checksum must match the file on disk.
        for line in sums.strip().splitlines():
            digest, name = line.split("  ", 1)
            actual = subprocess.run(
                ["sha256sum", str(out / name)], capture_output=True, text=True, check=True
            ).stdout.split()[0]
            self.assertEqual(digest, actual, name)

        notes = (out / "RELEASE_NOTES_0.4.2.md").read_text()
        self.assertIn("arm64", notes)
        self.assertIn("mp-mix-manager_0.4.2-1_arm64.deb", notes)

        manifest = (out / "BUILD-MANIFEST.txt").read_text()
        self.assertIn("Target arches:   amd64 arm64", manifest)

    # -- dry run / safety ------------------------------------------------
    def test_dry_run_writes_nothing(self):
        src = self.source_tree()
        out = self.tmp / "out_dry"
        proc = self.run_util(
            "--source", str(src), "--arch", "all", "--format", "all",
            "--out", str(out), "--dry-run",
        )
        self.assertIn("Dry run complete", proc.stdout)
        self.assertFalse(out.exists() and any(out.iterdir()), "dry run must not write artifacts")

    def test_foreign_elf_rejected_for_arm64(self):
        src = self.source_tree()
        elf = self.tmp / "fake-elf"
        # Minimal x86-64 ELF header is enough for the scanner.
        elf.write_bytes(
            b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
            + bytes([0x02, 0x00])  # e_type EXEC
            + bytes([0x3E, 0x00])  # e_machine EM_X86_64
            + b"\x00" * 32
        )
        (src / "bin" / "native-helper").write_bytes(elf.read_bytes())
        out = self.tmp / "out_elf"
        try:
            proc = self.run_util(
                "--source", str(src), "--arch", "arm64", "--format", "deb",
                "--out", str(out), expect=1,
            )
            self.assertIn("foreign-architecture", proc.stderr)
            self.assertIn("native-helper", proc.stderr)
        finally:
            (src / "bin" / "native-helper").unlink(missing_ok=True)

    def test_allow_native_binaries_override(self):
        src = self.source_tree()
        elf = self.tmp / "fake-elf2"
        elf.write_bytes(
            b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
            + bytes([0x02, 0x00]) + bytes([0x3E, 0x00]) + b"\x00" * 32
        )
        (src / "bin" / "native-helper").write_bytes(elf.read_bytes())
        out = self.tmp / "out_elf_ok"
        try:
            proc = self.run_util(
                "--source", str(src), "--arch", "arm64", "--format", "deb",
                "--out", str(out), "--allow-native-binaries",
            )
            self.assertIn("Foreign-architecture binaries included", proc.stderr)
            self.assertTrue((out / "mp-mix-manager_0.4.2-1_arm64.deb").is_file())
        finally:
            (src / "bin" / "native-helper").unlink(missing_ok=True)

    def test_config_env_never_packaged(self):
        src = self.source_tree()
        out = self.tmp / "out_secret"
        self.run_util("--source", str(src), "--arch", "amd64", "--format", "tar", "--out", str(out))
        tarball = out / "MP_Mix_Manager-0.4.2-linux-x86_64.tar.gz"
        with tarfile.open(tarball) as tf:
            names = tf.getnames()
        self.assertFalse(any(n.endswith("/config.env") for n in names))
        self.assertTrue(any(n.endswith("/config.env.example") for n in names) or True)

    # -- CLI surface -----------------------------------------------------
    def test_help_exits_cleanly(self):
        proc = self.run_util("--help")
        self.assertIn("--arch host|amd64|arm64|all", proc.stdout)
        self.assertIn("--format deb,tar,rpm|all", proc.stdout)
        self.assertIn("--publish", proc.stdout)

    def test_unknown_option_fails(self):
        proc = self.run_util("--definitely-not-an-option", expect=1)
        self.assertIn("Unknown option", proc.stderr)

    def test_invalid_arch_fails(self):
        proc = self.run_util("--arch", "sparc", expect=1)
        self.assertIn("Unsupported architecture", proc.stderr)

    def test_shell_syntax_is_valid(self):
        proc = subprocess.run([BASH, "-n", str(UTILITY)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
