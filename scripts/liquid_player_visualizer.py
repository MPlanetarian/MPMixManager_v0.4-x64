"""In-player MP Visualizer for the Liquid Glass window.

The player writes a small state file. The OpenGL host reads it and draws the
same preset shader the standalone MP Liquid Visualizer uses, behind the
terminal text. A text guard keeps that text readable.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
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


# The player window stays at its own size. The raymarch long edge is 768,
# so a 1094×734 window is drawn at 768×515 and scaled up. A full-window
# march of this shader is about 9 fps through MoltenVK. 768 is about three
# times the old 224-wide image on the long edge and still moves.
# MP_VISUALIZER_GL_LONG_EDGE still overrides the long edge.
# MP_VISUALIZER_GL_MARCH_STEPS clamps to 24..84.
MACOS_FULLSCREEN_SIZE = (1920, 1080)
_MACOS_LONG_EDGE = 768
_UNFOLDED_LONG_EDGE = 224
_FULL_MARCH_STEPS = 84
_MACOS_MARCH_STEPS = 64
_MARCH_LOOP = "for (int i = 0; i < 84; i++)"
_SOURCE_CACHE: Dict[str, str] = {}
_PRESET_SPIRV = ROOT / "shaders" / "presets"
_SPIRV_MAGIC = b"\x03\x02\x23\x07"

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


def macos_liquid_player_window_size(
    cols: int = 120, rows: int = 40, char_w: int = 9, char_h: int = 18, margin: int = 7
) -> tuple:
    """Point size of the macOS Liquid Player window.

    120×40 cells at 9×18 px, plus the 7 px bezel on each side: 1094×734.
    """
    return (
        int(cols) * int(char_w) + 2 * int(margin),
        int(rows) * int(char_h) + 2 * int(margin),
    )


_PLAYER_WINDOW_TITLE = "MP Audio Player (Liquid Glass"
_WINDOW_GEOM_RE = re.compile(r"(\d+)x(\d+)[+-]\d+[+-]\d+")


def linux_liquid_player_window_size(
    cols: int = 120, rows: int = 40, char_w: int = 9, char_h: int = 18, margin: int = 7, slider: int = 44
) -> tuple:
    """Pixel size of the Linux OpenGL Liquid Player before the font is measured.

    120×40 cells at 9×18 px, a 7 px bezel on each side, and the 44 px
    transparency slider: 1094×778. The host then refits to the real VTE cell.
    """
    return (
        int(cols) * int(char_w) + 2 * int(margin),
        int(rows) * int(char_h) + 2 * int(margin) + int(slider),
    )


def parse_liquid_player_window_size(tree_text: str) -> Optional[tuple]:
    """Largest mapped MP Liquid Player window in an xwininfo -root -tree listing."""
    best = None
    for line in (tree_text or "").splitlines():
        if _PLAYER_WINDOW_TITLE not in line:
            continue
        match = _WINDOW_GEOM_RE.search(line)
        if not match:
            continue
        size = (int(match.group(1)), int(match.group(2)))
        if size[0] < 64 or size[1] < 64:
            continue
        if best is None or size[0] * size[1] > best[0] * best[1]:
            best = size
    return best


def _read_xwininfo_tree() -> str:
    try:
        result = subprocess.run(
            ["xwininfo", "-root", "-tree"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def player_window_size_path() -> Path:
    override = (os.environ.get("MP_LIQUID_PLAYER_WINDOW_FILE") or "").strip()
    if override:
        return Path(override)
    return CONFIG_DIR / "liquid_player_window.json"


# (path, width, height, pid). Skips rewriting the same size every frame.
_PUBLISHED_CACHE: Optional[tuple] = None


def publish_liquid_player_window_size(width: int, height: int, pid: Optional[int] = None) -> None:
    """Record the Liquid Player's outer window so the visualizer can match it."""
    global _PUBLISHED_CACHE
    try:
        width_i = int(width)
        height_i = int(height)
        pid_i = int(os.getpid() if pid is None else pid)
    except (TypeError, ValueError):
        return
    if width_i < 64 or height_i < 64 or pid_i <= 0:
        return
    path = player_window_size_path()
    token = (str(path), width_i, height_i, pid_i)
    if token == _PUBLISHED_CACHE:
        return
    body = json.dumps({"width": width_i, "height": height_i, "pid": pid_i}) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return
    _PUBLISHED_CACHE = token


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def read_published_player_window_record() -> Optional[tuple]:
    """(width, height, mtime) for a player process that is still running."""
    path = player_window_size_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        mtime = path.stat().st_mtime
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    try:
        width = int(payload["width"])
        height = int(payload["height"])
        pid = int(payload.get("pid") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if width < 64 or height < 64 or not _pid_alive(pid):
        return None
    return width, height, float(mtime)


def read_published_player_window_size() -> Optional[tuple]:
    record = read_published_player_window_record()
    if not record:
        return None
    return int(record[0]), int(record[1])


def liquid_player_host_running() -> bool:
    """True when a Liquid Player host is up. The Manager GUI does not count."""
    root = Path("/proc")
    if not root.is_dir():
        return False
    marker = b"MP_Audio_Player_Liquid_Glass"
    try:
        entries = os.listdir(root)
    except OSError:
        return False
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            command = (root / entry / "cmdline").read_bytes()
        except OSError:
            continue
        if marker in command and b"--manager" not in command:
            return True
    return False


def wait_for_published_player_window_size(
    timeout: float = 5.0,
    idle_timeout: float = 0.45,
    stable_for: float = 0.3,
    *,
    require_mapped: bool = True,
    now=None,
    wall_now=None,
    sleep=None,
    host_running=None,
    read_tree=None,
) -> Optional[tuple]:
    """Fitted Liquid Player size, once the on-screen window matches it.

    The player opens at a 9×18 guess, then refits to the real VTE cell.
    A visualizer that reads the first size stays smaller. This waits until
    the published size has settled and, on the desktop, until the mapped
    window agrees. No player returns None after idle_timeout.
    """
    import time
    clock = time.monotonic if now is None else now
    wall = time.time if wall_now is None else wall_now
    pause = time.sleep if sleep is None else sleep
    running = liquid_player_host_running if host_running is None else host_running
    tree_of = _read_xwininfo_tree if read_tree is None else read_tree
    start = clock()
    seen = None
    seen_at = start
    while True:
        record = read_published_player_window_record()
        current = clock()
        size = None
        settled = False
        if record:
            size = (int(record[0]), int(record[1]))
            if size != seen:
                seen = size
                seen_at = current
            age = wall() - float(record[2])
            settled = age >= float(stable_for) or (current - seen_at) >= float(stable_for)
        mapped_ok = True
        if settled and size and require_mapped:
            mapped = parse_liquid_player_window_size(tree_of() or "")
            mapped_ok = mapped == size
        if settled and size and mapped_ok:
            return size
        elapsed = current - start
        host_up = bool(running())
        if host_up and elapsed >= float(timeout):
            return seen
        if not host_up and elapsed >= float(idle_timeout):
            return seen
        pause(0.05)


def linux_visualizer_window_size(tree_text: Optional[str] = None) -> tuple:
    """Linux MP Visualizer size: the fitted Liquid Player, or that player's formula.

    An explicit window-tree listing is parsed as given. The live lookup
    prefers the size the player published after measuring its font.
    """
    if tree_text is None:
        published = read_published_player_window_size()
        if published:
            return published
        tree_text = _read_xwininfo_tree()
    found = parse_liquid_player_window_size(tree_text or "")
    if found:
        return found
    return linux_liquid_player_window_size()


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


def _scale_long_edge(rw: int, rh: int, cap: int) -> tuple:
    """Scale down so the long edge is at most cap. A smaller image stays as it is."""
    rw, rh = max(2, int(rw)), max(2, int(rh))
    cap = max(2, int(cap))
    longest = max(rw, rh)
    if longest <= cap:
        return rw, rh
    scale = cap / float(longest)
    return max(2, int(round(rw * scale))), max(2, int(round(rh * scale)))


def march_target_size(width: int, height: int, long_edge: Optional[int] = None) -> tuple:
    """Raymarch pixels for a window of this size.

    On macOS the long edge defaults to 768. A 1094×734 window therefore
    marches at 768×515 and is scaled onto the window. Other platforms keep
    the 224 cap unless an override is set.
    """
    if long_edge is not None or bool((os.environ.get("MP_VISUALIZER_GL_LONG_EDGE") or "").strip()):
        cap = macos_visualizer_long_edge() if long_edge is None else max(160, int(long_edge))
    elif sys.platform == "darwin":
        cap = macos_visualizer_long_edge()
    else:
        cap = _UNFOLDED_LONG_EDGE
    return _scale_long_edge(width, height, cap)


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

    On macOS the long edge stops at 768, and that image is scaled onto the
    window. A 1094×734 window marches at 768×515. A larger framebuffer uses
    the same cap. Other platforms use the framebuffer as it is.
    ``fullscreen`` does not raise the cap.
    MP_VISUALIZER_GL_LONG_EDGE still overrides the long edge.
    """
    del fullscreen
    fw_i = max(2, int(fw))
    fh_i = max(2, int(fh))
    if macos is None:
        macos = sys.platform == "darwin"
    if not macos:
        return fw_i, fh_i
    if long_edge is not None or bool((os.environ.get("MP_VISUALIZER_GL_LONG_EDGE") or "").strip()):
        if ww is None or wh is None:
            rw, rh = fw_i, fh_i
        else:
            rw = min(fw_i, max(2, int(ww)))
            rh = min(fh_i, max(2, int(wh)))
        cap = macos_visualizer_long_edge() if long_edge is None else max(160, int(long_edge))
        return _scale_long_edge(rw, rh, cap)
    return _scale_long_edge(fw_i, fh_i, macos_visualizer_long_edge())


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


def specialize_vulkan_source(source: str, preset_id: int, march_steps: Optional[int] = None) -> str:
    """Fold ``u.preset.x`` so MoltenVK drops the other scenes from the march."""
    preset = f"({float(int(preset_id)):.1f})"
    specialized = source.replace("u.preset.x", preset)
    steps = _FULL_MARCH_STEPS if march_steps is None else int(march_steps)
    if steps != _FULL_MARCH_STEPS and _MARCH_LOOP in specialized:
        specialized = specialized.replace(_MARCH_LOOP, f"for (int i = 0; i < {steps}; i++)", 1)
    return specialized


def _tool_path(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    for cand in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"):
        if os.access(cand, os.X_OK):
            return cand
    return None


def _visualizer_source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _read_preset_manifest() -> Dict[str, Any]:
    try:
        raw = json.loads((_PRESET_SPIRV / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _compile_folded_spirv(source: str, preset_id: int, steps: int, dest: Path) -> Optional[Path]:
    compiler = _tool_path("glslangValidator")
    if not compiler:
        return None
    folded = specialize_vulkan_source(source, preset_id, steps)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_path = dest.with_suffix(".frag")
    tmp_spv = dest.with_suffix(".tmp.spv")
    src_path.write_text(folded, encoding="utf-8")
    try:
        result = subprocess.run(
            [compiler, "-V", "--target-env", "vulkan1.0", "-o", str(tmp_spv), str(src_path)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        if result.returncode != 0 or not tmp_spv.is_file():
            return None
        optimizer = _tool_path("spirv-opt")
        if optimizer:
            optimized = dest.with_suffix(".opt.spv")
            opt = subprocess.run(
                [optimizer, "-O", str(tmp_spv), "-o", str(optimized)],
                capture_output=True, timeout=60, check=False,
            )
            if opt.returncode == 0 and optimized.is_file():
                optimized.replace(tmp_spv)
        data = tmp_spv.read_bytes()
        if not data.startswith(_SPIRV_MAGIC):
            return None
        tmp_spv.replace(dest)
        return dest
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        src_path.unlink(missing_ok=True)
        if tmp_spv.exists() and tmp_spv != dest:
            tmp_spv.unlink(missing_ok=True)


def vulkan_preset_spirv(preset_id: int, march_steps: Optional[int] = None) -> Optional[Path]:
    """SPIR-V for one preset, with the other scenes folded out.

    The shipped modules match the shader at a 64-step march. A newer shader
    is compiled into the user cache when glslangValidator is installed.
    """
    steps = macos_visualizer_march_steps() if march_steps is None else int(march_steps)
    preset_id = int(preset_id)
    try:
        source = (ROOT / "shaders" / "mp_liquid_visualizer.frag").read_text(encoding="utf-8")
    except OSError:
        return None
    digest = _visualizer_source_digest(source)
    cache = CONFIG_DIR / "visualizer-spirv" / f"p{preset_id}-s{steps}-{digest}.spv"
    if cache.is_file() and cache.stat().st_size > 16:
        return cache
    shipped = _PRESET_SPIRV / f"p{preset_id}.frag.spv"
    meta = _read_preset_manifest()
    shipped_ok = (
        shipped.is_file()
        and steps == _MACOS_MARCH_STEPS
        and meta.get("source") == digest
        and int(meta.get("steps", -1)) == steps
    )
    if shipped_ok:
        return shipped
    compiled = _compile_folded_spirv(source, preset_id, steps, cache)
    if compiled:
        return compiled
    if shipped.is_file() and steps == _MACOS_MARCH_STEPS:
        return shipped
    return None


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
