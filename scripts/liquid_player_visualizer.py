"""In-player MP Visualizer for the Liquid Glass window.

The player writes a small state file. The OpenGL host reads it and draws the
same preset shader the standalone MP Liquid Visualizer uses, behind the
terminal text. A text guard keeps that text readable.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

CONFIG_DIR = Path.home() / ".config" / "mix-manager"
_DEFAULT_STATE = CONFIG_DIR / "liquid_player_visualizer.json"
_CACHE: Dict[str, Any] = {"path": "", "mtime": None, "state": None}

_TEXT_GUARD = """
    if (uTextGuard > 0.5) {
        float luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
        col *= mix(0.92, 0.42, smoothstep(0.18, 0.84, luma));
        col = mix(vec3(0.015, 0.020, 0.034), col, 0.80);
        float well = smoothstep(0.0, 0.07, vUv.x) * smoothstep(1.0, 0.93, vUv.x)
                   * smoothstep(0.0, 0.05, vUv.y) * smoothstep(1.0, 0.94, vUv.y);
        col = mix(col, col * 0.70 + vec3(0.008, 0.010, 0.018), well * 0.50);
    }
"""

_GL_HEADER = """#version 330 core
in vec2 vUv;
out vec4 outColor;
uniform vec4 u_res;
uniform vec4 u_audio0;
uniform vec4 u_audio1;
uniform vec4 u_audio2;
uniform vec4 u_bands0;
uniform vec4 u_bands1;
uniform vec4 u_bands2;
uniform vec4 u_bands3;
uniform vec4 u_preset;
uniform sampler2D uCoverTex;
uniform float uTextGuard;
"""

_UNIFORM_NAMES = (
    "u_res", "u_audio0", "u_audio1", "u_audio2",
    "u_bands0", "u_bands1", "u_bands2", "u_bands3",
    "u_preset", "uCoverTex", "uTextGuard",
)


def state_path() -> Path:
    override = (os.environ.get("MP_LIQUID_VISUALIZER_STATE") or "").strip()
    return Path(override).expanduser() if override else _DEFAULT_STATE


def _inactive(preset_id: int = 0) -> Dict[str, Any]:
    return {
        "active": False,
        "preset_id": int(preset_id),
        "preset_key": "cosmic_dreamworlds_liquid",
        "preset_name": "Cosmic Dreamworlds (Liquid)",
    }


def visualizer_presets() -> List[Dict[str, Any]]:
    from mp_liquid_visualizer_vulkan import VISUALIZER_PRESETS
    return list(VISUALIZER_PRESETS)


def preset_by_id(preset_id: int) -> Optional[Dict[str, Any]]:
    want = int(preset_id)
    for preset in visualizer_presets():
        if int(preset.get("id", -1)) == want:
            return preset
    return None


def read_player_visualizer_state() -> Dict[str, Any]:
    path = state_path()
    key = str(path)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        state = _inactive()
        _CACHE.update(path=key, mtime=None, state=state)
        return dict(state)
    if _CACHE.get("path") == key and _CACHE.get("mtime") == mtime and isinstance(_CACHE.get("state"), dict):
        return dict(_CACHE["state"])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    state = _inactive(int(raw.get("preset_id") or 0))
    state["active"] = bool(raw.get("active"))
    if raw.get("preset_key"):
        state["preset_key"] = str(raw.get("preset_key"))
    if raw.get("preset_name"):
        state["preset_name"] = str(raw.get("preset_name"))
    _CACHE.update(path=key, mtime=mtime, state=state)
    return dict(state)


def write_player_visualizer_state(active: bool, preset: Dict[str, Any]) -> Dict[str, Any]:
    state = {
        "active": bool(active),
        "preset_id": int(preset.get("id", 0)),
        "preset_key": str(preset.get("key") or "cosmic_dreamworlds_liquid"),
        "preset_name": str(preset.get("name") or "Cosmic Dreamworlds (Liquid)"),
    }
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, path)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        mtime = None
    _CACHE.update(path=str(path), mtime=mtime, state=dict(state))
    # Keep the standalone visualizer on the same theme. A test that points
    # MP_LIQUID_VISUALIZER_STATE at a temp file must not rewrite the user's preset.
    if active and path == _DEFAULT_STATE:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            (CONFIG_DIR / "visualizer_preset").write_text(state["preset_key"] + "\n", encoding="utf-8")
        except OSError:
            pass
    return dict(state)


def opengl_visualizer_source() -> str:
    """GLSL 330 port of shaders/mp_liquid_visualizer.frag, with a text guard."""
    raw = (ROOT / "shaders" / "mp_liquid_visualizer.frag").read_text(encoding="utf-8")
    start = raw.find("const float PI")
    if start < 0:
        raise RuntimeError("MP Visualizer shader is missing its prelude")
    body = raw[start:]
    for src, dst in (
        ("u.bands0", "u_bands0"),
        ("u.bands1", "u_bands1"),
        ("u.bands2", "u_bands2"),
        ("u.bands3", "u_bands3"),
        ("u.audio0", "u_audio0"),
        ("u.audio1", "u_audio1"),
        ("u.audio2", "u_audio2"),
        ("u.preset", "u_preset"),
        ("u.res", "u_res"),
    ):
        body = body.replace(src, dst)
    needle = "outColor = vec4(col, 1.0);"
    if needle not in body:
        raise RuntimeError("MP Visualizer shader is missing its output")
    body = body.replace(needle, _TEXT_GUARD + "\n    " + needle, 1)
    return _GL_HEADER + body


class PlayerVisualizerLayer:
    """Draws the MP Visualizer preset into the liquid-glass framebuffer."""

    def __init__(self) -> None:
        self._prog = 0
        self._locs: Dict[str, int] = {}
        self._tex = 0
        self._tex_key = ""
        self._bridge = None
        self._last = 0.0
        self._error = ""

    def draw(self, renderer, fw: int, fh: int) -> bool:
        state = read_player_visualizer_state()
        if not state.get("active"):
            return False
        try:
            return self._draw(renderer, fw, fh, state)
        except Exception as exc:
            if not self._error:
                self._error = str(exc)
                print(f"MP Visualizer background unavailable: {exc}", file=sys.stderr)
            return False

    def _draw(self, renderer, fw: int, fh: int, state: Dict[str, Any]) -> bool:
        import time
        from OpenGL import GL

        if not self._prog and not self._compile(GL, renderer):
            return False
        self._ensure_cover(GL, state)
        bridge = self._ensure_bridge()
        now = time.monotonic()
        dt = 0.016 if self._last <= 0.0 else max(0.0, min(0.05, now - self._last))
        self._last = now
        bridge.update(dt)
        if not bridge.is_playing:
            bridge.accum_time += dt * 0.45
            bridge.dynamic_time += dt * 0.45

        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glUseProgram(self._prog)
        locs = self._locs
        preset_id = float(state.get("preset_id") or 0)
        bands = list(bridge.bands16) + [0.0] * 16
        GL.glUniform4f(locs["u_res"], float(fw), float(fh), float(bridge.accum_time), 1.0 if bridge.is_playing else 0.0)
        GL.glUniform4f(locs["u_audio0"], bridge.sub_bass, bridge.bass, bridge.low_mid, bridge.mid)
        GL.glUniform4f(locs["u_audio1"], bridge.high_mid, bridge.treble, bridge.air, bridge.rms_energy)
        GL.glUniform4f(locs["u_audio2"], bridge.beat_pulse, bridge.bass_phase, bridge.mid_phase, bridge.high_phase)
        GL.glUniform4f(locs["u_bands0"], bands[0], bands[1], bands[2], bands[3])
        GL.glUniform4f(locs["u_bands1"], bands[4], bands[5], bands[6], bands[7])
        GL.glUniform4f(locs["u_bands2"], bands[8], bands[9], bands[10], bands[11])
        GL.glUniform4f(locs["u_bands3"], bands[12], bands[13], bands[14], bands[15])
        GL.glUniform4f(locs["u_preset"], preset_id, float(bridge.pitch_factor), 1.0, float(bridge.dynamic_time))
        GL.glUniform1i(locs["uCoverTex"], 0)
        GL.glUniform1f(locs["uTextGuard"], 1.0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
        GL.glBindVertexArray(renderer._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        return True

    def _compile(self, GL, renderer) -> bool:
        vert_path = ROOT / "shaders" / "liquid_glass_gl.vert"
        vert_src = vert_path.read_text(encoding="utf-8")
        frag_src = opengl_visualizer_source()
        vs = GL.glCreateShader(GL.GL_VERTEX_SHADER)
        GL.glShaderSource(vs, vert_src)
        GL.glCompileShader(vs)
        if not GL.glGetShaderiv(vs, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(vs).decode("utf-8", errors="replace"))
        fs = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
        GL.glShaderSource(fs, frag_src)
        GL.glCompileShader(fs)
        if not GL.glGetShaderiv(fs, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(fs).decode("utf-8", errors="replace"))
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(prog).decode("utf-8", errors="replace"))
        locs = {name: int(GL.glGetUniformLocation(prog, name)) for name in _UNIFORM_NAMES}
        if locs.get("u_res", -1) < 0 or locs.get("u_preset", -1) < 0:
            raise RuntimeError("MP Visualizer shader uniforms did not link")
        self._prog = prog
        self._locs = locs
        self._tex = int(GL.glGenTextures(1))
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_MIRRORED_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
        self._upload_solid(GL, 12, 40, 96)
        return True

    def _ensure_bridge(self):
        if self._bridge is None:
            from mp_liquid_visualizer_vulkan import AudioTelemetryBridge
            self._bridge = AudioTelemetryBridge()
        return self._bridge

    def _ensure_cover(self, GL, state: Dict[str, Any]) -> None:
        key = f"{state.get('preset_id')}:{state.get('preset_key')}"
        if key == self._tex_key and self._tex:
            return
        preset = preset_by_id(int(state.get("preset_id") or 0)) or {
            "id": state.get("preset_id") or 0,
            "key": state.get("preset_key"),
            "name": state.get("preset_name"),
            "cover_paths": [],
        }
        width, height, pixels = 64, 64, b""
        try:
            from mp_liquid_visualizer_vulkan import load_preset_cover_rgba
            width, height, pixels = load_preset_cover_rgba(preset, tex_size=512)
        except Exception:
            pixels = b""
        if not pixels:
            self._upload_solid(GL, 18, 72, 140)
        else:
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, width, height, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels)
        self._tex_key = key

    def _upload_solid(self, GL, r: int, g: int, b: int) -> None:
        pixel = bytes((r, g, b, 255)) * 4
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, 2, 2, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixel)
