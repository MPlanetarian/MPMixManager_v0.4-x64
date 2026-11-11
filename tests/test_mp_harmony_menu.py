"""Main-menu MP Harmony row, Ollama gate, and Shift+A."""

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "scripts" / "launch_mp_harmony.sh"
MANAGER = ROOT / "Mix_Archive_Manager.sh"


def _run_launcher(env_extra):
    env = os.environ.copy()
    env.update(env_extra)
    env["MP_HARMONY_NO_PAUSE"] = "1"
    return subprocess.run(
        ["bash", str(LAUNCHER)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestHarmonyMenu(unittest.TestCase):
    def test_ai_is_the_first_selectable_row(self):
        text = MANAGER.read_text(encoding="utf-8")
        ai = text.index(
            '"AI|Load MP Mix Manager AI Assistant (MP Harmony) (New)|'
            '(Shift+A • starts Ollama if needed • loads gpt-oss-pinned:latest)"'
        )
        mp = text.index('"MP|MP GUI Mix Manager (New)|(Press G • Liquid Glass window • runs MP Gui)"')
        zero = text.index('"0|Run Any Desktop Shortcuts|')
        self.assertLess(ai, mp)
        self.assertLess(mp, zero)
        self.assertIn(
            'AI|ai|"Load MP Mix Manager AI Assistant (MP Harmony) (New)"*) launch_mp_harmony_from_menu',
            text,
        )
        self.assertIn("CHAR:A)", text)
        self.assertIn("launch_mp_harmony_from_menu", text)
        self.assertIn("[Shift+A] MP Harmony", text)
        self.assertIn("exit 42", text)
        self.assertIn('bind -x \'"A": _mp_manager_bash_key A\'', text)

    def test_shell_parses(self):
        for path in (MANAGER, LAUNCHER):
            result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_launcher_can_start_ollama_when_it_is_down(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("harmony_offer_start_ollama", text)
        self.assertIn("systemctl --user start", text)
        self.assertIn("distrobox enter --no-workdir -T", text)
        self.assertIn("ollama serve", text)
        self.assertIn("Start Ollama now?", text)
        self.assertIn("Container name:", text)
        self.assertIn("gpt-oss-pinned:latest", text)

    def test_declining_the_start_prompt_returns_immediately(self):
        result = _run_launcher(
            {
                "MP_HARMONY_FORCE_DOWN": "1",
                "MP_HARMONY_ASSUME_NO": "1",
                "MP_HARMONY_NO_PROMPT": "1",
            }
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        out = result.stdout
        self.assertIn("Ollama is not running", out)
        self.assertIn("Returning to MP Mix Manager", out)
        self.assertNotIn("Press Enter to return to MP Mix Manager.", out)
        self.assertNotIn("You would be installing", out)

    def test_a_missing_container_name_is_reported(self):
        result = _run_launcher(
            {
                "MP_HARMONY_FORCE_DOWN": "1",
                "MP_HARMONY_ASSUME_YES": "1",
                "OLLAMA_CONTAINER": "no-such-container-for-this-test",
                "OLLAMA_START_TIMEOUT": "1",
                "OLLAMA_API_URL": "http://127.0.0.1:1",
                "PATH": os.environ.get("PATH", "") + ":/nonexistent",
            }
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("No podman container named", result.stdout)


class TestHarmonyShiftA(unittest.TestCase):
    def test_empty_shift_a_returns_from_the_agent_prompt(self):
        agent = Path("/var/home/mplanetarian/OpenAI/MP_Harmony_Agent/MP_Harmony_Agent.py")
        if not agent.is_file():
            self.skipTest("MP Harmony agent is not installed on this machine")
        source = agent.read_text(encoding="utf-8")
        self.assertIn('os.environ.get("MP_MIX_MANAGER_SHIFT_A") == "1"', source)
        self.assertIn("MP_SHIFT_A_RETURN", source)
        self.assertIn('@kb.add("A", eager=True)', source)

        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.output import DummyOutput
        from prompt_toolkit import PromptSession

        sentinel = "\x1eMP_SHIFT_A_RETURN"
        kb = KeyBindings()

        @kb.add("A", eager=True)
        def _(event):
            if not event.current_buffer.text.strip():
                event.app.exit(result=sentinel)
            else:
                event.current_buffer.insert_text("A")

        with create_pipe_input() as pipe:
            session = PromptSession(input=pipe, output=DummyOutput(), key_bindings=kb)
            pipe.send_text("A")
            pipe.close()
            self.assertEqual(session.prompt(), sentinel)

        with create_pipe_input() as pipe:
            session = PromptSession(input=pipe, output=DummyOutput(), key_bindings=kb)
            pipe.send_text("xA\r")
            self.assertEqual(session.prompt(), "xA")


class TestHarmonyGate(unittest.TestCase):
    def test_refuses_when_ollama_is_down(self):
        result = _run_launcher({"MP_HARMONY_FORCE_DOWN": "1"})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Ollama is not running", result.stdout)
        self.assertNotIn("You would be installing", result.stdout)
        self.assertNotIn("Agent launch skipped", result.stdout)

    def test_asks_before_installing_a_missing_model(self):
        result = _run_launcher(
            {
                "MP_HARMONY_FORCE_UP": "1",
                "MP_HARMONY_FORCE_MODEL": "0",
                "MP_HARMONY_ASSUME_NO": "1",
            }
        )
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        out = result.stdout
        self.assertIn("gpt-oss-pinned:latest", out)
        self.assertIn("gpt-oss-20b", out)
        self.assertIn("20.9 billion", out)
        self.assertIn("Apache License 2.0", out)
        self.assertIn("Harmony format", out)
        self.assertIn("mix archive", out)
        self.assertIn("MP Audio Player", out)
        self.assertIn("was not installed", out)
        self.assertNotIn("Pulling", out)

    def test_loads_an_installed_model_without_asking(self):
        result = _run_launcher(
            {
                "MP_HARMONY_FORCE_UP": "1",
                "MP_HARMONY_FORCE_MODEL": "1",
                "MP_HARMONY_SKIP_LOAD": "1",
                "MP_HARMONY_SKIP_AGENT": "1",
            }
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("is installed", result.stdout)
        self.assertIn("Load skipped", result.stdout)
        self.assertIn("Agent launch skipped", result.stdout)
        self.assertNotIn("You would be installing", result.stdout)

    def test_live_ollama_sees_the_pinned_model(self):
        probe = subprocess.run(
            ["curl", "-sf", "--connect-timeout", "2", "--max-time", "4", "http://127.0.0.1:11434/"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0 or "Ollama is running" not in probe.stdout:
            self.skipTest("Ollama is not answering on port 11434")
        result = _run_launcher(
            {
                "MP_HARMONY_SKIP_LOAD": "1",
                "MP_HARMONY_SKIP_AGENT": "1",
            }
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Ollama is running", result.stdout)
        self.assertIn("gpt-oss-pinned:latest is installed", result.stdout)


if __name__ == "__main__":
    unittest.main()
