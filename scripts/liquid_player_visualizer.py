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

if sys.platform == "darwin":
    # Must be set before the first OpenGL import. See the macOS host.
    os.environ.setdefault("PYOPENGL_ERROR_CHECKING", "0")

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


# The player window stays at its own size. The raymarch is a separate target
# that fits inside 1920x1080, then the result is scaled to the window.
# MP_VISUALIZER_GL_LONG_EDGE still scales the long edge when it is set.
# MP_VISUALIZER_GL_MARCH_STEPS clamps to 24..84.
MACOS_FULLSCREEN_SIZE = (1920, 1080)
_MACOS_LONG_EDGE = 512
_FULL_MARCH_STEPS = 84
_MACOS_MARCH_STEPS = 64
_MARCH_LOOP = "for (int i = 0; i < 84; i++)"
_SOURCE_CACHE: Dict[str, str] = {}

_UPSCALE_FRAG = """#version 330 core
in vec2 vUv;
out vec4 outColor;
uniform sampler2D uTex;
void main() {
    outColor = vec4(texture(uTex, vUv).rgb, 1.0);
}
"""


def _env_int(name: str, default: int, low: int, high: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(low, min(high, value))


def macos_visualizer_long_edge() -> int:
    return _env_int("MP_VISUALIZER_GL_LONG_EDGE", _MACOS_LONG_EDGE, 160, 4096)


def macos_visualizer_march_steps() -> int:
    return _env_int("MP_VISUALIZER_GL_MARCH_STEPS", _MACOS_MARCH_STEPS, 24, _FULL_MARCH_STEPS)


def macos_player_grid(width: int, height: int, char_w: int = 9, char_h: int = 18, margin: int = 7) -> tuple:
    """Character cells that fill a macOS player window of this pixel size."""
    cols = max(20, (int(width) - 2 * int(margin)) // int(char_w))
    rows = max(8, (int(height) - 2 * int(margin)) // int(char_h))
    return cols, rows


def macos_fullscreen_size(work_w: int, work_h: int) -> tuple:
    """Fullscreen pixels. 1920x1080 is the highest, and a smaller screen stays smaller."""
    cap_w, cap_h = MACOS_FULLSCREEN_SIZE
    return min(max(2, int(work_w)), cap_w), min(max(2, int(work_h)), cap_h)


def _renderer_is_fullscreen(renderer) -> bool:
    host = getattr(renderer, "host_ref", None)
    if host is not None and getattr(host, "is_maximized", False):
        return True
    return bool(getattr(renderer, "is_fullscreen", False))


def _fit_box(rw: int, rh: int, cap_w: int, cap_h: int) -> tuple:
    """Largest size with this aspect that fits inside the cap. Scales up or down."""
    rw = max(2, int(rw))
    rh = max(2, int(rh))
    cap_w = max(2, int(cap_w))
    cap_h = max(2, int(cap_h))
    scale = min(cap_w / float(rw), cap_h / float(rh))
    return min(cap_w, max(2, int(rw * scale))), min(cap_h, max(2, int(rh * scale)))


def visualizer_internal_size(
    fw: int,
    fh: int,
    ww: Optional[int] = None,
    wh: Optional[int] = None,
    *,
    macos: Optional[bool] = None,
    long_edge: Optional[int] = None,
    fullscreen: bool = False,
) -> tuple:
    """Pixel size of the raymarch.

    On macOS the march fits inside 1920x1080 and keeps the framebuffer's aspect.
    A smaller framebuffer is scaled up to that cap. The player window is not
    resized to match. Other platforms use the framebuffer.
    ``fullscreen`` is accepted so callers can pass it. The cap is the same
    either way. MP_VISUALIZER_GL_LONG_EDGE still scales the long edge down.
    """
    del fullscreen
    fw_i = max(2, int(fw))
    fh_i = max(2, int(fh))
    if macos is None:
        macos = sys.platform == "darwin"
    if not macos:
        return fw_i, fh_i
    if ww is None or wh is None:
        rw, rh = fw_i, fh_i
    else:
        rw = min(fw_i, max(2, int(ww)))
        rh = min(fh_i, max(2, int(wh)))
    use_long_edge = long_edge is not None or bool((os.environ.get("MP_VISUALIZER_GL_LONG_EDGE") or "").strip())
    if use_long_edge:
        cap = macos_visualizer_long_edge() if long_edge is None else max(160, int(long_edge))
        longest = max(rw, rh)
        if longest > cap:
            scale = cap / float(longest)
            rw = max(2, int(round(rw * scale)))
            rh = max(2, int(round(rh * scale)))
        return rw, rh
    cap_w, cap_h = MACOS_FULLSCREEN_SIZE
    return _fit_box(fw_i, fh_i, cap_w, cap_h)


def opengl_visualizer_source() -> str:
    """GLSL 330 port of shaders/mp_liquid_visualizer.frag, with a text guard."""
    cached = _SOURCE_CACHE.get("generic")
    if cached is not None:
        return cached
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
    source = _GL_HEADER + body
    _SOURCE_CACHE["generic"] = source
    return source


def specialize_visualizer_source(source: str, preset_id: int, march_steps: Optional[int] = None) -> str:
    """Fold the preset id to a constant so the other scenes drop out of the program.

    The fragment shader carries every preset. Apple's compiler keeps the whole
    program live when the id is a uniform, and that register pressure is what
    makes the march slow. Pitch and dynamic time stay in u_preset.
    """
    preset = f"({float(int(preset_id)):.1f})"
    specialized = source.replace("u_preset.x", preset)
    steps = _FULL_MARCH_STEPS if march_steps is None else int(march_steps)
    if steps != _FULL_MARCH_STEPS and _MARCH_LOOP in specialized:
        specialized = specialized.replace(_MARCH_LOOP, f"for (int i = 0; i < {steps}; i++)", 1)
    return specialized


def _window_points(renderer) -> Optional[tuple]:
    getter = getattr(renderer, "window_size", None)
    if not callable(getter):
        return None
    try:
        ww, wh = getter()
        ww_i, wh_i = int(ww), int(wh)
    except (TypeError, ValueError):
        return None
    if ww_i < 2 or wh_i < 2:
        return None
    return ww_i, wh_i


def _loc(locs: Dict[str, int], name: str) -> int:
    try:
        value = int(locs.get(name, -1))
    except (TypeError, ValueError):
        return -1
    return value


class PlayerVisualizerLayer:
    """Draws the MP Visualizer preset into the liquid-glass framebuffer."""

    def __init__(self) -> None:
        self._prog = 0
        self._locs: Dict[str, int] = {}
        self._programs: Dict[int, tuple] = {}
        self._tex = 0
        self._tex_key = ""
        self._bridge = None
        self._last = 0.0
        self._error = ""
        self._fbo = 0
        self._color = 0
        self._target_size: tuple = (0, 0)
        self._upscale = 0
        self._upscale_tex = -1
        self._failed: set = set()

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

        preset_id = int(state.get("preset_id") or 0)
        if not self._compile(GL, renderer, preset_id):
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

        fw_i, fh_i = max(2, int(fw)), max(2, int(fh))
        points = _window_points(renderer)
        fullscreen = _renderer_is_fullscreen(renderer)
        if points is None:
            rw, rh = visualizer_internal_size(fw_i, fh_i, fullscreen=fullscreen)
        else:
            rw, rh = visualizer_internal_size(fw_i, fh_i, points[0], points[1], fullscreen=fullscreen)
        if (rw, rh) != (fw_i, fh_i) and self._ensure_target(GL, rw, rh) and self._ensure_upscale(GL):
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
            GL.glViewport(0, 0, rw, rh)
            try:
                self._draw_scene(GL, renderer, rw, rh, bridge)
            finally:
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
                GL.glViewport(0, 0, fw_i, fh_i)
            self._draw_upscale(GL, renderer)
            return True
        self._draw_scene(GL, renderer, fw_i, fh_i, bridge)
        return True

    def _draw_scene(self, GL, renderer, rw: int, rh: int, bridge) -> None:
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glUseProgram(self._prog)
        locs = self._locs
        bands = list(bridge.bands16) + [0.0] * 16
        playing = 1.0 if bridge.is_playing else 0.0
        self._uniform4(GL, _loc(locs, "u_res"), float(rw), float(rh), float(bridge.accum_time), playing)
        self._uniform4(GL, _loc(locs, "u_audio0"), bridge.sub_bass, bridge.bass, bridge.low_mid, bridge.mid)
        self._uniform4(GL, _loc(locs, "u_audio1"), bridge.high_mid, bridge.treble, bridge.air, bridge.rms_energy)
        self._uniform4(GL, _loc(locs, "u_audio2"), bridge.beat_pulse, bridge.bass_phase, bridge.mid_phase, bridge.high_phase)
        self._uniform4(GL, _loc(locs, "u_bands0"), bands[0], bands[1], bands[2], bands[3])
        self._uniform4(GL, _loc(locs, "u_bands1"), bands[4], bands[5], bands[6], bands[7])
        self._uniform4(GL, _loc(locs, "u_bands2"), bands[8], bands[9], bands[10], bands[11])
        self._uniform4(GL, _loc(locs, "u_bands3"), bands[12], bands[13], bands[14], bands[15])
        self._uniform4(GL, _loc(locs, "u_preset"), 0.0, float(bridge.pitch_factor), 1.0, float(bridge.dynamic_time))
        cover = _loc(locs, "uCoverTex")
        if cover >= 0:
            GL.glUniform1i(cover, 0)
        guard = _loc(locs, "uTextGuard")
        if guard >= 0:
            GL.glUniform1f(guard, 1.0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
        GL.glBindVertexArray(renderer._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)

    def _uniform4(self, GL, loc: int, x, y, z, w) -> None:
        if loc < 0:
            return
        GL.glUniform4f(loc, float(x), float(y), float(z), float(w))

    def _compile(self, GL, renderer=None, preset_id: int = 0) -> bool:
        preset_id = int(preset_id)
        if preset_id in self._failed:
            return False
        cached = self._programs.get(preset_id)
        if cached is None:
            try:
                vert_src = (ROOT / "shaders" / "liquid_glass_gl.vert").read_text(encoding="utf-8")
                steps = macos_visualizer_march_steps() if sys.platform == "darwin" else None
                frag_src = specialize_visualizer_source(opengl_visualizer_source(), preset_id, steps)
                prog, locs = self._link_program(GL, vert_src, frag_src, _UNIFORM_NAMES)
                if _loc(locs, "u_res") < 0:
                    raise RuntimeError("MP Visualizer shader uniforms did not link")
                cached = (prog, locs)
                self._programs[preset_id] = cached
            except Exception:
                # A failed compile used to run again on the next frame. Apple's
                # compiler spends a long time rejecting this shader.
                self._failed.add(preset_id)
                raise
        self._prog, self._locs = cached
        if not self._tex:
            self._tex = int(GL.glGenTextures(1))
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_MIRRORED_REPEAT)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_MIRRORED_REPEAT)
            self._upload_solid(GL, 12, 40, 96)
        return True

    def _link_program(self, GL, vert_src: str, frag_src: str, names) -> tuple:
        vs = GL.glCreateShader(GL.GL_VERTEX_SHADER)
        GL.glShaderSource(vs, vert_src)
        GL.glCompileShader(vs)
        if not GL.glGetShaderiv(vs, GL.GL_COMPILE_STATUS):
            raise RuntimeError(self._shader_log(GL, vs))
        fs = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
        GL.glShaderSource(fs, frag_src)
        GL.glCompileShader(fs)
        if not GL.glGetShaderiv(fs, GL.GL_COMPILE_STATUS):
            raise RuntimeError(self._shader_log(GL, fs))
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            log = GL.glGetProgramInfoLog(prog)
            if isinstance(log, bytes):
                log = log.decode("utf-8", errors="replace")
            raise RuntimeError(str(log))
        locs = {name: int(GL.glGetUniformLocation(prog, name)) for name in names}
        return int(prog), locs

    def _shader_log(self, GL, shader) -> str:
        log = GL.glGetShaderInfoLog(shader)
        if isinstance(log, bytes):
            log = log.decode("utf-8", errors="replace")
        return str(log)

    def _ensure_target(self, GL, rw: int, rh: int) -> bool:
        if self._fbo and self._target_size == (rw, rh):
            return True
        if not self._fbo:
            self._fbo = int(GL.glGenFramebuffers(1))
            self._color = int(GL.glGenTextures(1))
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._color)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._color)
        internal = getattr(GL, "GL_RGBA8", GL.GL_RGBA)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, internal, int(rw), int(rh), 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
        GL.glFramebufferTexture2D(
            GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, self._color, 0
        )
        GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
        complete = int(GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)) == int(GL.GL_FRAMEBUFFER_COMPLETE)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        if not complete:
            return False
        self._target_size = (int(rw), int(rh))
        return True

    def _ensure_upscale(self, GL) -> bool:
        if self._upscale:
            return True
        vert_src = (ROOT / "shaders" / "liquid_glass_gl.vert").read_text(encoding="utf-8")
        prog, locs = self._link_program(GL, vert_src, _UPSCALE_FRAG, ("uTex",))
        self._upscale = prog
        self._upscale_tex = _loc(locs, "uTex")
        return True

    def _draw_upscale(self, GL, renderer) -> None:
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glUseProgram(self._upscale)
        if self._upscale_tex >= 0:
            GL.glUniform1i(self._upscale_tex, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._color)
        GL.glBindVertexArray(renderer._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)

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
