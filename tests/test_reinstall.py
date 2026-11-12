#!/usr/bin/env python3
"""The reinstall flow wipes config, asks what to keep, and never deletes audio.

The helper script is exercised against a throwaway install tree, a throwaway
config directory, and a throwaway data directory, so no real user files are
touched. The installer and manager are checked for the wiring that exposes the
flow, including on Windows and macOS.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "scripts" / "reinstall_mp_manager.sh"
INSTALL = ROOT / "install.sh"
MANAGER = ROOT / "Mix_Archive_Manager.sh"
MANAGE_CONFIG = ROOT / "scripts" / "manage_installation_config.sh"
CLI = ROOT / "bin" / "mix-archive-manager"
HELP = ROOT / "scripts" / "show_help.sh"
CHANGELOG = ROOT / "CHANGELOG.md"


def bash_path() -> str:
    found = shutil.which("bash")
    return found or "bash"


class ReinstallHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mp_reinstall_test_"))
        self.root = self.tmp / "root"
        self.config = self.tmp / "config"
        self.data = self.tmp / "data"
        self.archive = self.tmp / "ARCHIVE"
        self.root.mkdir()
        (self.root / "Mix_Archive_Manager.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        shutil.copy2(ROOT / "config.env.example", self.root / "config.env.example")
        (self.root / "config.env").write_text(
            'MIX_ARCHIVE_CONFIGURED="true"\n'
            f'MIX_ARCHIVE_DIR="{self.archive}"\n'
            'EXTRA_MIX_ARCHIVE_DIRS=""\n'
            'OUTPUT_DIR="FLAC_CONVERTED_OUTPUTS"\n'
            'ARCHIVE_DIR="CONVERTED_WAV_FILES"\n'
            'MUSIC_SMB_USER="djuser"\n'
            'MUSIC_SMB_PASSWORD="djpass"\n'
            'SMTP_HOST="smtp.example.com"\n'
            'SMTP_USER="mail@example.com"\n'
            'LIQUID_GLASS_BACKEND="vulkan"\n',
            encoding="utf-8",
        )
        # Folders whose contents must always survive.
        self.audio = {
            "FLAC_CONVERTED_OUTPUTS": "mix1.flac",
            "MP3_CONVERTED_OUTPUTS": "mix1.mp3",
            "WAV_CONVERTED_OUTPUTS": "mix1.wav",
            "MP4_CONVERTED_OUTPUTS": "mix1.mp4",
            "CONVERTED_WAV_FILES": "source.wav",
            "COVERS": "Cover.png",
            "SPEK_OUTPUTS": "spec.png",
        }
        for folder, name in self.audio.items():
            target = self.root / folder
            target.mkdir()
            (target / name).write_bytes(b"audio-bytes")
        (self.archive / "FLAC_CONVERTED_OUTPUTS").mkdir(parents=True)
        (self.archive / "FLAC_CONVERTED_OUTPUTS" / "archive.flac").write_bytes(b"audio-bytes")
        (self.archive / "PLAYLISTS_GENERATED").mkdir(parents=True)
        (self.archive / "PLAYLISTS_GENERATED" / "archive.m3u8").write_text("#EXTM3U\n", encoding="utf-8")

        # Config and runtime state that a reset should clear.
        self.config.mkdir()
        (self.config / "theme").write_text("retro-linux-memories\n", encoding="utf-8")
        (self.config / "eq_preset").write_text("flat\n", encoding="utf-8")
        (self.config / "track_durations.json").write_text("{}\n", encoding="utf-8")
        (self.config / "user_activity.jsonl").write_text("{}\n", encoding="utf-8")
        (self.config / "liquid_glass.log").write_text("log\n", encoding="utf-8")
        (self.config / "music_folders.json").write_text('{"folders": []}\n', encoding="utf-8")
        (self.config / "favorites.json").write_text('{"tracks": []}\n', encoding="utf-8")
        (self.config / "playlists").mkdir()
        (self.config / "playlists" / "custom.m3u8").write_text("#EXTM3U\n", encoding="utf-8")
        (self.config / "mounts").mkdir()
        (self.config / "mounts" / "MUSIC001").write_text("mount\n", encoding="utf-8")
        (self.data / "python-env").mkdir(parents=True)
        (self.data / "python-env" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_helper(self, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.update({
            "MP_REINSTALL_SKIP_STOP": "1",
            "MP_REINSTALL_CONFIG_DIR": str(self.config),
            "MP_REINSTALL_DATA_DIR": str(self.data),
        })
        return subprocess.run(
            [bash_path(), str(HELPER), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

    def assert_audio_survived(self) -> None:
        for folder, name in self.audio.items():
            target = self.root / folder / name
            self.assertTrue(target.is_file(), f"{target} was deleted")
            self.assertEqual(target.read_bytes(), b"audio-bytes")
        archived = self.archive / "FLAC_CONVERTED_OUTPUTS" / "archive.flac"
        self.assertTrue(archived.is_file(), "converted audio in the archive was deleted")


class ReinstallHelperTests(ReinstallHarness):
    def test_fresh_reset_wipes_config_but_never_audio(self) -> None:
        result = self.run_helper("--fresh", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_audio_survived()

        # Config directory is reduced to a first-install (empty) state.
        self.assertFalse((self.config / "theme").exists())
        self.assertFalse((self.config / "eq_preset").exists())
        self.assertFalse((self.config / "user_activity.jsonl").exists())
        self.assertFalse((self.config / "music_folders.json").exists())
        self.assertFalse((self.config / "favorites.json").exists())
        self.assertFalse((self.config / "playlists").exists())
        self.assertFalse((self.config / "mounts").exists())

        # macOS generated environment is gone.
        self.assertFalse(self.data.exists())

        # config.env is a fresh copy of the template.
        fresh = (self.root / "config.env").read_text(encoding="utf-8")
        self.assertIn('MIX_ARCHIVE_CONFIGURED="false"', fresh)
        self.assertNotIn("SMTP_HOST=\"smtp.example.com\"", fresh)
        self.assertNotIn('MUSIC_SMB_USER="djuser"', fresh)
        self.assertNotIn('LIQUID_GLASS_BACKEND="vulkan"', fresh)

    def test_preserve_everything_keeps_the_three_choices(self) -> None:
        result = self.run_helper(
            "--yes",
            "--preserve-playlists",
            "--preserve-music-folders",
            "--preserve-archive-config",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_audio_survived()

        self.assertEqual((self.config / "favorites.json").read_text(encoding="utf-8"), '{"tracks": []}\n')
        self.assertTrue((self.config / "playlists" / "custom.m3u8").is_file())
        self.assertEqual((self.config / "music_folders.json").read_text(encoding="utf-8"), '{"folders": []}\n')
        self.assertTrue((self.config / "mounts" / "MUSIC001").is_file())

        # Theme and caches are still reset: only the chosen settings are kept.
        self.assertFalse((self.config / "theme").exists())
        self.assertFalse((self.config / "eq_preset").exists())

        fresh = (self.root / "config.env").read_text(encoding="utf-8")
        self.assertIn(f'MIX_ARCHIVE_DIR="{self.archive}"', fresh)
        self.assertIn('MUSIC_SMB_USER="djuser"', fresh)
        self.assertIn('MUSIC_SMB_PASSWORD="djpass"', fresh)
        # Settings the user did not choose to preserve come back at defaults.
        self.assertIn('LIQUID_GLASS_BACKEND="opengl"', fresh)
        self.assertNotIn('SMTP_HOST="smtp.example.com"', fresh)

    def test_preserving_only_playlists_leaves_music_and_archive_at_defaults(self) -> None:
        result = self.run_helper("--yes", "--preserve-playlists",
                                 "--no-preserve-music-folders",
                                 "--no-preserve-archive-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_audio_survived()
        self.assertTrue((self.config / "playlists" / "custom.m3u8").is_file())
        self.assertFalse((self.config / "music_folders.json").exists())
        fresh = (self.root / "config.env").read_text(encoding="utf-8")
        self.assertIn('MIX_ARCHIVE_CONFIGURED="false"', fresh)
        self.assertNotIn('MUSIC_SMB_USER="djuser"', fresh)

    def test_dry_run_changes_nothing(self) -> None:
        config_before = sorted(p.relative_to(self.config) for p in self.config.rglob("*"))
        result = self.run_helper("--fresh", "--yes", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN COMPLETE", result.stdout)
        config_after = sorted(p.relative_to(self.config) for p in self.config.rglob("*"))
        self.assertEqual(config_before, config_after)
        self.assertTrue((self.config / "theme").exists())
        self.assertTrue((self.root / "config.env").exists())
        self.assert_audio_survived()

    def test_aborted_confirmation_exits_10_and_changes_nothing(self) -> None:
        env = os.environ.copy()
        env.update({
            "MP_REINSTALL_SKIP_STOP": "1",
            "MP_REINSTALL_CONFIG_DIR": str(self.config),
            "MP_REINSTALL_DATA_DIR": str(self.data),
        })
        proc = subprocess.run(
            [bash_path(), str(HELPER), "--root", str(self.root), "--fresh"],
            capture_output=True,
            text=True,
            env=env,
            input="\n",
            timeout=60,
        )
        self.assertEqual(proc.returncode, 10)
        self.assertIn("cancelled", proc.stdout)
        self.assertTrue((self.config / "theme").exists())
        self.assertTrue((self.root / "config.env").exists())
        self.assert_audio_survived()

    def test_no_prompt_yes_defaults_to_preserving_all_three(self) -> None:
        result = self.run_helper("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_audio_survived()
        self.assertTrue((self.config / "playlists" / "custom.m3u8").is_file())
        self.assertTrue((self.config / "music_folders.json").is_file())
        fresh = (self.root / "config.env").read_text(encoding="utf-8")
        self.assertIn(f'MIX_ARCHIVE_DIR="{self.archive}"', fresh)

    def test_archive_playlists_generated_is_left_alone(self) -> None:
        result = self.run_helper("--fresh", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.archive / "PLAYLISTS_GENERATED" / "archive.m3u8").is_file())

    def test_install_tree_playlists_are_cleared_on_fresh(self) -> None:
        generated = self.root / "PLAYLISTS_GENERATED"
        generated.mkdir()
        (generated / "app.m3u8").write_text("#EXTM3U\n", encoding="utf-8")
        (generated / ".gitkeep").write_text("", encoding="utf-8")
        custom = self.root / "playlists"
        custom.mkdir()
        (custom / "mine.m3u8").write_text("#EXTM3U\n", encoding="utf-8")

        result = self.run_helper("--fresh", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((generated / "app.m3u8").exists())
        self.assertFalse((custom / "mine.m3u8").exists())
        self.assertTrue((generated / ".gitkeep").is_file())

    def test_report_lists_protected_folders(self) -> None:
        result = self.run_helper("--fresh", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Converted audio and artwork left untouched", result.stdout)
        self.assertIn("FLAC_CONVERTED_OUTPUTS", result.stdout)


class ReinstallWiringTests(unittest.TestCase):
    def test_helper_is_valid_shell(self) -> None:
        for script in (HELPER, INSTALL, MANAGER, MANAGE_CONFIG, CLI, HELP):
            result = subprocess.run(
                [bash_path(), "-n", str(script)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"{script}: {result.stderr}")

    def test_installer_accepts_the_reinstall_flag_on_every_host(self) -> None:
        text = INSTALL.read_text(encoding="utf-8")
        for flag in ("--reinstall", "--re-install", "--factory-reset", "--reset"):
            self.assertIn(flag, text)
        self.assertIn("reinstall_mp_manager.sh", text)
        self.assertIn("--root", text)
        # The reset runs before the permission, scaffold, symlink, and desktop
        # steps so the program is rebuilt around the fresh configuration.
        reinstall_at = text.index("reinstall_mp_manager.sh")
        chmod_at = text.index("Configuring Script & Binary Permissions")
        desktop_at = text.index("Installing Desktop Integration")
        self.assertLess(reinstall_at, chmod_at)
        self.assertLess(reinstall_at, desktop_at)

    def test_installer_help_lists_the_reinstall_options(self) -> None:
        result = subprocess.run(
            [bash_path(), str(INSTALL), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--reinstall", result.stdout)
        self.assertIn("--preserve-playlists", result.stdout)
        self.assertIn("--preserve-music-folders", result.stdout)
        self.assertIn("--preserve-archive-config", result.stdout)
        self.assertIn("--fresh", result.stdout)
        self.assertIn("never deleted", result.stdout)

    def test_manager_menu_exposes_the_reinstall(self) -> None:
        text = MANAGER.read_text(encoding="utf-8")
        self.assertIn("reinstall", text)
        self.assertIn("Reinstall", text)
        self.assertIn("manage_installation_config.sh", text)
        self.assertIn("reinstall_mp_manager.sh", text)

    def test_installation_config_menu_has_a_reinstall_row(self) -> None:
        text = MANAGE_CONFIG.read_text(encoding="utf-8")
        self.assertIn("reinstall_installation", text)
        self.assertIn("Reinstall MP Mix Manager", text)
        self.assertIn("--reinstall", text)
        self.assertIn("Converted audio files are never deleted", text)
        self.assertRegex(text, r"Enter choice \[1-7")

    def test_cli_has_a_reinstall_command(self) -> None:
        text = CLI.read_text(encoding="utf-8")
        self.assertIn("reinstall", text)
        self.assertIn("factory-reset", text)
        self.assertIn("reinstall_mp_manager.sh", text)

    def test_help_page_documents_the_reinstall(self) -> None:
        text = HELP.read_text(encoding="utf-8")
        self.assertIn("reinstall, --reinstall", text)
        self.assertIn("--fresh", text)
        self.assertIn("--dry-run", text)

    def test_changelog_mentions_the_reinstall(self) -> None:
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertIn("Reinstall / factory reset", text)

    def test_platform_specific_cleanup_is_present(self) -> None:
        text = HELPER.read_text(encoding="utf-8")
        # Every supported host is handled.
        for host in ('OS_TYPE" = "macos"', '"windows"', '"wsl"', '"freebsd"', '"linux"'):
            self.assertIn(host, text)
        self.assertIn("kill_all_mp_audio_players.sh", text)
        self.assertIn("mp_system_tray", text)
        self.assertIn("LaunchAgents", text)
        self.assertIn(".local/share/mp-mix-manager", text)
        self.assertIn("taskkill", text)
        self.assertIn("launchctl", text)

    def test_protected_audio_list_covers_every_output_folder(self) -> None:
        text = HELPER.read_text(encoding="utf-8")
        for folder in (
            "FLAC_CONVERTED_OUTPUTS",
            "MP3_CONVERTED_OUTPUTS",
            "WAV_CONVERTED_OUTPUTS",
            "MP4_CONVERTED_OUTPUTS",
            "CONVERTED_WAV_FILES",
            "MIX_ARCHIVE",
            "COVERS",
            "SPEK_OUTPUTS",
            "MP_AUDIOWAV_REC_OUTPUT",
        ):
            self.assertIn(folder, text)

    def test_config_example_is_never_removed(self) -> None:
        text = HELPER.read_text(encoding="utf-8")
        self.assertIn("config.env.example", text)
        # Only config.env itself is wiped, never the template.
        self.assertIn('wipe_path "$ROOT/config.env"', text)
        self.assertNotIn('wipe_path "$ROOT/config.env.example"', text)


if __name__ == "__main__":
    unittest.main()
