#!/usr/bin/env python3
"""
Tests for the 0.4 end-of-life upgrade in update_manager.sh.

0.4 was the final 0.4 release. `./Mix_Archive_Manager.sh update` must hand a
0.4 install over to MP Mix Manager 0.5:

  * A 0.4 tree clones the published 0.5 repository into a sibling directory.
  * The user's config.env, playlists, covers, themes and reports are copied.
  * Files that already exist in 0.5 are never overwritten.
  * The 0.4 tree itself is never modified.
  * An unpublished / unreachable 0.5 repository falls back to a normal 0.4 pull.
  * A 0.5 tree keeps the ordinary git-pull behaviour and never re-upgrades.

Every test builds throwaway git repositories under a temporary directory, so
nothing here touches the network or the real installation.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPDATER = REPO_ROOT / "update_manager.sh"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(*args, cwd):
    env = dict(os.environ)
    env.update(GIT_ENV)
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class UpgradeTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.src = self.base / "src"
        self.src.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    # ---------------------------------------------------------------- fixtures
    def make_successor_repo(self, name, version="0.5.0 Stable (Sensorium)"):
        """A stand-in for github.com/MPlanetarian/MPMixManager_v0.5-x64."""
        repo = self.src / name
        (repo / "bin").mkdir(parents=True)
        (repo / "scripts" / "lib").mkdir(parents=True)
        (repo / "PLAYLISTS_GENERATED").mkdir(parents=True)
        (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
        (repo / "Mix_Archive_Manager.sh").write_text("#!/usr/bin/env bash\necho 0.5\n", encoding="utf-8")
        (repo / "bin" / "mix-archive-manager").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        (repo / "scripts" / "lib" / "mp_install_dir.sh").write_text(
            "mp_find_install_dir() { :; }\n", encoding="utf-8"
        )
        (repo / "config.env.example").write_text('MIX_ARCHIVE_DIR=""\n', encoding="utf-8")
        (repo / "PLAYLISTS_GENERATED" / "TRACKED.txt").write_text("tracked-0.5\n", encoding="utf-8")
        # A real 0.5 updater so the successor's own update path can be exercised.
        updater_text = UPDATER.read_text(encoding="utf-8")
        updater_text = updater_text.replace(
            'echo "0.4.2 Stable (Liquid)"', 'echo "0.5.0 Stable (Sensorium)"'
        )
        (repo / "update_manager.sh").write_text(updater_text, encoding="utf-8")
        (repo / "scripts" / "update_manager.sh").write_text(updater_text, encoding="utf-8")
        (repo / "install.sh").write_text(
            "#!/usr/bin/env bash\n"
            'echo "STUB INSTALLER in $(pwd)"\n'
            'mkdir -p "$HOME/.config/mix-manager/lib" "$HOME/.local/bin"\n'
            'printf "%s\\n" "$(pwd)" > "$HOME/.config/mix-manager/install_dir"\n'
            'ln -sfn "$(pwd)/bin/mix-archive-manager" "$HOME/.local/bin/mix-archive-manager"\n'
            'ln -sfn "$(pwd)/Mix_Archive_Manager.sh" "$HOME/.local/bin/manager"\n'
            '[ "${STUB_INSTALL_FAIL:-0}" = "1" ] && exit 3\n'
            "exit 0\n",
            encoding="utf-8",
        )
        for f in ("Mix_Archive_Manager.sh", "bin/mix-archive-manager", "install.sh",
                  "update_manager.sh", "scripts/update_manager.sh"):
            (repo / f).chmod(0o755)
        _git("init", "-q", ".", cwd=repo)
        _git("add", "-A", cwd=repo)
        _git("commit", "-qm", "0.5 release", cwd=repo)
        return repo

    def make_04_tree(self, files=None):
        """A stand-in for an existing ~/MPMixManager_v0.4-x64 install."""
        tree = self.home / "MPMixManager_v0.4-x64"
        (tree / "scripts").mkdir(parents=True)
        (tree / "PLAYLISTS_GENERATED").mkdir()
        (tree / "COVERS").mkdir()
        (tree / "themes").mkdir()
        shutil.copy2(UPDATER, tree / "update_manager.sh")
        shutil.copy2(UPDATER, tree / "scripts" / "update_manager.sh")
        (tree / "VERSION").write_text("0.4.2 Stable (Liquid)\n", encoding="utf-8")
        (tree / "Mix_Archive_Manager.sh").write_text("#!/usr/bin/env bash\necho 0.4\n", encoding="utf-8")
        (tree / "config.env").write_text('KEEP_ME="yes"\n', encoding="utf-8")
        (tree / "PLAYLISTS_GENERATED" / "Custom.m3u").write_text("user playlist\n", encoding="utf-8")
        (tree / "COVERS" / "MyMix.png").write_text("user cover\n", encoding="utf-8")
        (tree / "themes" / "My.theme").write_text("user theme\n", encoding="utf-8")
        for extra, body in (files or {}).items():
            path = tree / extra
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        _git("init", "-q", ".", cwd=tree)
        _git("add", "-A", cwd=tree)
        _git("commit", "-qm", "0.4 end of life", cwd=tree)
        return tree

    # ------------------------------------------------------------------ runner
    def run_update(self, tree, repo_url, *args, extra_env=None):
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["MP_UPGRADE_REPO_URL"] = str(repo_url)
        env.update(extra_env or {})
        return subprocess.run(
            ["bash", "update_manager.sh", "update", *args],
            cwd=str(tree),
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )


class TestEndOfLifeUpgrade(UpgradeTestBase):
    def test_check_reports_available_without_installing(self):
        repo = self.make_successor_repo("v05")
        tree = self.make_04_tree()

        res = self.run_update(tree, repo, "--check")

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("MP Mix Manager 0.5 is available", res.stdout)
        self.assertFalse((self.home / "MPMixManager_v0.5-x64").exists())

    def test_check_reports_unpublished_repository(self):
        bare = self.src / "empty"
        bare.mkdir()
        _git("init", "-q", "--bare", ".", cwd=bare)
        tree = self.make_04_tree()

        res = self.run_update(tree, bare, "--check")

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("not published yet", res.stdout)
        self.assertFalse((self.home / "MPMixManager_v0.5-x64").exists())

    def test_update_clones_and_carries_user_data(self):
        repo = self.make_successor_repo("v05")
        tree = self.make_04_tree({
            "MIX_ARCHIVE/FLAC_CONVERTED_OUTPUTS/mix.flac": "audio\n",
            # Same path that 0.5 also ships: the 0.5 copy must win.
            "PLAYLISTS_GENERATED/TRACKED.txt": "stale-0.4-content\n",
        })

        res = self.run_update(tree, repo)

        self.assertEqual(res.returncode, 0, res.stderr)
        new = self.home / "MPMixManager_v0.5-x64"
        self.assertTrue((new / "Mix_Archive_Manager.sh").is_file())
        self.assertEqual((new / "VERSION").read_text().strip(), "0.5.0 Stable (Sensorium)")

        # User configuration and data.
        self.assertEqual((new / "config.env").read_text(), 'KEEP_ME="yes"\n')
        self.assertEqual((new / "PLAYLISTS_GENERATED" / "Custom.m3u").read_text(), "user playlist\n")
        self.assertEqual((new / "COVERS" / "MyMix.png").read_text(), "user cover\n")
        self.assertEqual((new / "themes" / "My.theme").read_text(), "user theme\n")
        self.assertEqual(
            (new / "MIX_ARCHIVE" / "FLAC_CONVERTED_OUTPUTS" / "mix.flac").read_text(), "audio\n"
        )

        # Files shipped by 0.5 are never overwritten.
        self.assertEqual((new / "PLAYLISTS_GENERATED" / "TRACKED.txt").read_text(), "tracked-0.5\n")

        # Launchers and the recorded install directory point at 0.5.
        self.assertEqual((self.home / ".config" / "mix-manager" / "install_dir").read_text().strip(),
                         str(new))
        self.assertTrue((self.home / ".local" / "bin" / "manager").is_symlink())
        self.assertEqual(os.path.realpath(self.home / ".local" / "bin" / "manager"),
                         os.path.realpath(new / "Mix_Archive_Manager.sh"))

        # The 0.4 tree is left exactly as it was.
        self.assertEqual((tree / "config.env").read_text(), 'KEEP_ME="yes"\n')
        self.assertEqual((tree / "VERSION").read_text().strip(), "0.4.2 Stable (Liquid)")
        self.assertFalse((tree / "MPMixManager_v0.5-x64").exists())

    def test_unpublished_repository_falls_back_to_04_update(self):
        bare = self.src / "empty"
        bare.mkdir()
        _git("init", "-q", "--bare", ".", cwd=bare)
        tree = self.make_04_tree()

        res = self.run_update(tree, bare)

        self.assertIn("Continuing with the normal 0.4 update", res.stdout)
        self.assertFalse((self.home / "MPMixManager_v0.5-x64").exists())

    def test_foreign_target_directory_is_preserved(self):
        repo = self.make_successor_repo("v05")
        tree = self.make_04_tree()
        foreign = self.home / "MPMixManager_v0.5-x64"
        foreign.mkdir()
        (foreign / "notes.txt").write_text("someone's work\n", encoding="utf-8")

        res = self.run_update(tree, repo)

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("already exists and is not an MP Mix Manager 0.5 install", res.stdout)
        self.assertEqual((foreign / "notes.txt").read_text(), "someone's work\n")
        self.assertEqual((tree / "VERSION").read_text().strip(), "0.4.2 Stable (Liquid)")

    def test_wrong_published_version_is_rejected(self):
        repo = self.make_successor_repo("v04", version="0.4.9 Wrong")
        tree = self.make_04_tree()

        res = self.run_update(tree, repo)

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not 0.5 or newer", res.stdout)
        self.assertFalse((self.home / "MPMixManager_v0.5-x64").exists())

    def test_installer_failure_still_leaves_usable_install(self):
        repo = self.make_successor_repo("v05")
        tree = self.make_04_tree()

        res = self.run_update(tree, repo, extra_env={"STUB_INSTALL_FAIL": "1"})

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("reported an error", res.stdout)
        new = self.home / "MPMixManager_v0.5-x64"
        self.assertTrue((new / "Mix_Archive_Manager.sh").is_file())
        self.assertEqual(os.path.realpath(self.home / ".local" / "bin" / "manager"),
                         os.path.realpath(new / "Mix_Archive_Manager.sh"))

    def test_second_run_is_idempotent(self):
        repo = self.make_successor_repo("v05")
        tree = self.make_04_tree()
        self.assertEqual(self.run_update(tree, repo).returncode, 0)

        playlist = self.home / "MPMixManager_v0.5-x64" / "PLAYLISTS_GENERATED" / "Custom.m3u"
        before = playlist.read_text()

        res = self.run_update(tree, repo)

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("already installed at", res.stdout)
        self.assertEqual(playlist.read_text(), before)

        forced = self.run_update(tree, repo, "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertEqual(playlist.read_text(), before)


class TestSuccessorKeepsNormalUpdates(UpgradeTestBase):
    def test_05_tree_does_not_offer_the_upgrade_again(self):
        repo = self.make_successor_repo("v05")
        self.make_04_tree()
        tree = self.home / "MPMixManager_v0.5-x64"
        _git("clone", "-q", str(repo), str(tree), cwd=self.base)

        res = self.run_update(tree, repo, "--check")

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("0.4 is the final 0.4 release", res.stdout)
        self.assertNotIn("MP Mix Manager 0.5 is available", res.stdout)
        self.assertTrue(
            "latest version" in res.stdout or "new version of MP Mix" in res.stdout,
            res.stdout,
        )

    def test_version_and_help_still_work_on_04(self):
        tree = self.make_04_tree()
        env = dict(os.environ, HOME=str(self.home))

        version = subprocess.run(
            ["bash", "update_manager.sh", "--version"],
            cwd=str(tree), env=env, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertIn("v0.4.2 Stable", version.stdout)

        help_out = subprocess.run(
            ["bash", "update_manager.sh", "--help"],
            cwd=str(tree), env=env, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(help_out.returncode, 0, help_out.stderr)
        self.assertIn("end of life", help_out.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
