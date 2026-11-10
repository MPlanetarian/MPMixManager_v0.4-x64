"""Linux TTY Desktop Switcher and MP Mix Manager TTY Audio Mode."""

import os
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _manager_text():
    return (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")


def _tty_block():
    text = _manager_text()
    start = text.index("# MP_TTY_AUDIO_MODE_BEGIN")
    end = text.index("# MP_TTY_AUDIO_MODE_END")
    return text[start:end]


class TestMenuWiring(unittest.TestCase):
    def test_option_37_is_linux_only_and_exit_is_38(self):
        text = _manager_text()
        self.assertIn(
            'if [ "${OS_TYPE:-}" = "linux" ]; then main_opts+=("37|Linux TTY Desktop Switcher (MP Mix Manager TTY Audio Mode)|(Text console • enables MP Mix Manager TTY Audio Mode)"); fi; main_opts+=("38|Exit Manager|(or q / exit)")',
            text,
        )
        self.assertNotIn('"37|Exit Manager|(or q / exit)"', text)
        self.assertIn(
            '37|tty|tty-mode|tty-audio|desktop-cli|"Linux TTY Desktop Switcher (MP Mix Manager TTY Audio Mode)"*) manage_linux_tty_desktop_switch',
            text,
        )
        self.assertIn("38|77|[qQ]|[eE][xX][iI][tT]) exit_mix_manager", text)
        self.assertNotIn("37|77|", text)
        self.assertIn("between 0 and 38", text)
        self.assertIn("mp_tty_audio_mode_load", text)
        self.assertIn("MP Mix Manager TTY Audio Mode", text)
        self.assertIn('player="mp_audio_player"', text)
        help_text = (ROOT / "scripts" / "show_help.sh").read_text(encoding="utf-8")
        self.assertIn("Linux TTY Desktop Switcher (MP Mix Manager TTY Audio Mode)", help_text)
        self.assertIn("Linux only. This row is hidden", help_text)
        self.assertLess(
            help_text.index("Linux TTY Desktop Switcher"),
            help_text.index("Exit Manager"),
        )

    def test_linux_menu_hides_the_row_on_other_systems(self):
        text = _manager_text()
        start = text.index('if [ "${OS_TYPE:-}" = "linux" ]; then main_opts+=("37|')
        end = text.index('if [ -n "$CLI_INITIAL_ACTION" ]', start)
        snippet = text[start:end]
        script = textwrap.dedent(
            f"""
            build() {{
                OS_TYPE="$1"
                main_opts=()
                {snippet}
                printf '%s\\n' "${{main_opts[@]}}"
            }}
            echo '---linux---'
            build linux
            echo '---darwin---'
            build darwin
            echo '---windows---'
            build windows
            """
        )
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        linux, other = result.stdout.split("---darwin---", 1)
        self.assertIn("37|Linux TTY Desktop Switcher (MP Mix Manager TTY Audio Mode)|", linux)
        self.assertIn("38|Exit Manager|", linux)
        self.assertNotIn("37|Linux TTY Desktop Switcher", other)
        self.assertEqual(other.count("38|Exit Manager|"), 2)

    def test_switch_script_parses(self):
        script = ROOT / "scripts" / "MP_Desktop_CLI_Switch.sh"
        self.assertTrue(script.is_file())
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestTtyAudioMode(unittest.TestCase):
    def _run(self, body, home):
        script = _tty_block() + "\n" + textwrap.dedent(body)
        env = os.environ.copy()
        env["HOME"] = str(home)
        env.pop("MP_MIX_MANAGER_TTY_MODE", None)
        return subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_flag_enables_and_disables_the_mode(self):
        import tempfile

        with tempfile.TemporaryDirectory() as home:
            body = """
            press_enter() { :; }
            BOLD= CYAN= NC= YELLOW= GREEN= RED= DIM=
            mp_tty_audio_mode_enable
            mp_tty_audio_mode_active && echo ACTIVE || echo INACTIVE
            printf 'env:%s\\n' "$MP_MIX_MANAGER_TTY_MODE"
            mp_tty_skip_desktop "MP Gui" >/dev/null && echo SKIP || echo ALLOW
            mp_tty_audio_mode_disable
            mp_tty_audio_mode_active && echo STILL || echo CLEARED
            printf 'env:%s\\n' "$MP_MIX_MANAGER_TTY_MODE"
            """
            result = self._run(body, home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ACTIVE", result.stdout)
            self.assertIn("env:1", result.stdout)
            self.assertIn("SKIP", result.stdout)
            self.assertIn("CLEARED", result.stdout)
            self.assertIn("env:0", result.stdout)
            self.assertTrue((Path(home) / ".config" / "mix-manager" / "tty_audio_mode").exists() is False)

    def test_switch_target_follows_the_session(self):
        import tempfile

        with tempfile.TemporaryDirectory() as home:
            body = """
            press_enter() { :; }
            BOLD= CYAN= NC= YELLOW= GREEN= RED= DIM=
            systemctl() { printf '%s\\n' "${FAKE_DEFAULT:-graphical.target}"; }
            unset DISPLAY WAYLAND_DISPLAY
            FAKE_DEFAULT=graphical.target
            _mp_tty_switch_target
            DISPLAY=:0
            _mp_tty_switch_target
            unset DISPLAY WAYLAND_DISPLAY
            FAKE_DEFAULT=multi-user.target
            _mp_tty_switch_target
            """
            result = self._run(body, home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["here", "tty", "desktop"])

    def test_desktop_confirmation_enables_the_mode_and_runs_the_switch(self):
        import tempfile

        with tempfile.TemporaryDirectory() as home:
            switch = Path(home) / "scripts"
            switch.mkdir()
            fake = switch / "MP_Desktop_CLI_Switch.sh"
            fake.write_text("#!/bin/bash\nprintf '%s\\n' SWITCHED\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            body = f"""
            press_enter() {{ echo PRESSED; }}
            BOLD= CYAN= NC= YELLOW= GREEN= RED= DIM=
            systemctl() {{ printf '%s\\n' graphical.target; }}
            OS_TYPE=linux
            SCRIPT_DIR={str(Path(home))}
            DISPLAY=:0
            manage_linux_tty_desktop_switch <<< 'n'
            echo AFTER_NO
            test -f "$HOME/.config/mix-manager/tty_audio_mode" && echo FLAG || echo NOFLAG
            manage_linux_tty_desktop_switch <<< 'y'
            echo AFTER_YES
            test -f "$HOME/.config/mix-manager/tty_audio_mode" && echo FLAG || echo NOFLAG
            printf 'env:%s\\n' "$MP_MIX_MANAGER_TTY_MODE"
            """
            result = self._run(body, home)
            self.assertEqual(result.returncode, 0, result.stderr)
            no, rest = result.stdout.split("AFTER_NO", 1)
            yes, _after = rest.split("AFTER_YES", 1)
            self.assertNotIn("SWITCHED", no)
            self.assertIn("NOFLAG", yes)
            self.assertIn("SWITCHED", yes)
            self.assertIn("FLAG", _after)
            self.assertIn("env:1", _after)
            self.assertIn("MP Mix Manager TTY Audio Mode is on.", yes)

    def test_tty_confirmation_returns_to_the_desktop_and_clears_the_mode(self):
        import tempfile

        with tempfile.TemporaryDirectory() as home:
            switch = Path(home) / "scripts"
            switch.mkdir()
            fake = switch / "MP_Desktop_CLI_Switch.sh"
            fake.write_text("#!/bin/bash\nprintf '%s\\n' SWITCHED\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            body = f"""
            press_enter() {{ :; }}
            BOLD= CYAN= NC= YELLOW= GREEN= RED= DIM=
            systemctl() {{ printf '%s\\n' multi-user.target; }}
            OS_TYPE=linux
            SCRIPT_DIR={str(Path(home))}
            unset DISPLAY WAYLAND_DISPLAY
            mp_tty_audio_mode_enable
            manage_linux_tty_desktop_switch <<< 'y'
            test -f "$HOME/.config/mix-manager/tty_audio_mode" && echo FLAG || echo CLEARED
            printf 'env:%s\\n' "$MP_MIX_MANAGER_TTY_MODE"
            """
            result = self._run(body, home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SWITCHED", result.stdout)
            self.assertIn("CLEARED", result.stdout)
            self.assertIn("env:0", result.stdout)

    def test_other_systems_do_not_enable_the_mode(self):
        import tempfile

        with tempfile.TemporaryDirectory() as home:
            body = """
            press_enter() { echo PRESSED; }
            BOLD= CYAN= NC= YELLOW= GREEN= RED= DIM=
            OS_TYPE=macos
            SCRIPT_DIR=/none
            DISPLAY=:0
            manage_linux_tty_desktop_switch
            test -f "$HOME/.config/mix-manager/tty_audio_mode" && echo FLAG || echo NOFLAG
            """
            result = self._run(body, home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("available on Linux only", result.stdout)
            self.assertIn("NOFLAG", result.stdout)
            self.assertIn("PRESSED", result.stdout)

    def test_a_text_console_enables_the_mode_without_the_switch_script(self):
        import tempfile

        with tempfile.TemporaryDirectory() as home:
            switch = Path(home) / "scripts"
            switch.mkdir()
            fake = switch / "MP_Desktop_CLI_Switch.sh"
            fake.write_text("#!/bin/bash\nprintf '%s\\n' SWITCHED\nexit 9\n", encoding="utf-8")
            fake.chmod(0o755)
            body = f"""
            press_enter() {{ :; }}
            BOLD= CYAN= NC= YELLOW= GREEN= RED= DIM=
            systemctl() {{ printf '%s\\n' graphical.target; }}
            OS_TYPE=linux
            SCRIPT_DIR={str(Path(home))}
            unset DISPLAY WAYLAND_DISPLAY
            manage_linux_tty_desktop_switch <<< 'y'
            test -f "$HOME/.config/mix-manager/tty_audio_mode" && echo FLAG || echo NOFLAG
            """
            result = self._run(body, home)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SWITCHED", result.stdout)
            self.assertIn("FLAG", result.stdout)
            self.assertIn("MP Mix Manager TTY Audio Mode is on.", result.stdout)
