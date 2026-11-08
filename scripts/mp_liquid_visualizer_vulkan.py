#!/usr/bin/env python3
"""MP_Liquid_Visualizer — Native Vulkan 3D Audio-Reactive Visualizer Engine."""
from __future__ import annotations
import argparse, ctypes, json, math, os, platform, random, socket, subprocess, sys, time
from ctypes import (CFUNCTYPE, POINTER, Structure, addressof, byref, c_char, c_char_p, c_double,
                    c_float, c_int, c_int32, c_size_t, c_uint8, c_uint32, c_uint64, c_void_p, cast, memmove, sizeof, string_at)
from ctypes.util import find_library
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "shaders").is_dir() and (Path(__file__).resolve().parent / "shaders").is_dir():
    ROOT = Path(__file__).resolve().parent

SHADER_DIR, ASSETS_DIR, COVERS_DIR = ROOT / "shaders", ROOT / "assets", ROOT / "COVERS"
CONFIG_DIR = Path.home() / ".config" / "mix-manager"
WINDOW_WIDTH = WINDOW_HEIGHT = 1400
RENDER_1080P_WIDTH, RENDER_1080P_HEIGHT = 1920, 1080
FOUR_K_MIN_WIDTH, FOUR_K_MIN_HEIGHT = 3840, 2160

_BC = "https://mplanetarian.bandcamp.com"
_DEF = Path("/run/media/mplanetarian/EXT_004_P1_1TB/defasten")
_GAMES = Path("/run/media/mplanetarian/GAMES1/DATA_DRIVE_MOVED/MPlanetarian Bandcamp Covers")
_WDB = Path("/run/media/mplanetarian/WD BLACK B/MPlanetarian Bandcamp Covers")
_HOME = Path("/home/mplanetarian")

def _mk_preset(pid: int, key: str, name: str, album: str, c_asset: str, c_cov: str, extra: Optional[Path] = None,
               vid: Optional[str] = None, url: str = _BC, aliases: Tuple[str, ...] = ()) -> Dict[str, Any]:
    p: Dict[str, Any] = {
        "id": pid, "key": key, "name": name, "album": album, "bandcamp_url": url,
        "cover_paths": [ASSETS_DIR / c_asset, COVERS_DIR / c_cov] + ([extra] if extra else []),
        "_aliases": aliases,
    }
    if vid:
        p["video_path"], p["defasten_video"] = _DEF / vid, vid
    return p

VISUALIZER_PRESETS: List[Dict[str, Any]] = [
    _mk_preset(0, "cosmic_dreamworlds_liquid", "Cosmic Dreamworlds (Liquid)", "MPlanetarian - Cosmic Dreamworlds [Deluxe Edition]",
               "cosmic_dreamworlds_cover.jpg", "Cosmic_Dreamworlds_Liquid_Preset.png", url=f"{_BC}/album/mplanetarian-cosmic-dreamworlds-deluxe-edition"),
    _mk_preset(1, "orbital_void_reflux", "Orbital Void Reflux", "MPlanetarian - Orbital Void Reflux",
               "orbital_void_reflux_cover.png", "Orbital_Void_Reflux_Preset.png", _HOME / "Desktop/Cover_WMI_V2.png"),
    _mk_preset(2, "dreamworlds_ultra_defasten", "Dreamworlds Ultra (Defasten Biomech)", "MPlanetarian - Dreamworlds Ultra (Defasten Edition)",
               "dreamworlds_ultra_defasten_cover.png", "Dreamworlds_Ultra_Defasten_Preset.png", _HOME / "Documents/Dreamworlds_Ultra_7.2.11_Theme/Start_Menu_Icon.png"),
    _mk_preset(3, "infinite_complexity", "Infinite Complexity", "MPlanetarian - Infinite Complexity",
               "infinite_complexity_cover.png", "Infinite_Complexity_Preset.png", _GAMES / "Cover_v4.png"),
    _mk_preset(4, "sensorium_interface", "Sensorium Interface", "MPlanetarian - Sensorium Interface",
               "sensorium_interface_cover.png", "Sensorium_Interface_Preset.png", _GAMES / "Sensorium_Interface.jpeg",
               aliases=("sensorium", "sensorium interface", "sensorium_interface", "earth_flipper", "earth flipper", "flipper", "yaporigami", "defasten earth flipper")),
    _mk_preset(5, "stream_of_frequency", "Stream of Frequency", "MPlanetarian - Stream of Frequency",
               "stream_of_frequency_cover.jpg", "Stream_of_Frequency_Preset.png", _HOME / "Documents/Stream_of_Frequency.jpg",
               vid="20221004 - NEXTWORLD： Layer 1 (Ambient State) [VPe8PRUVVkU].mkv",
               aliases=("stream of frequency", "stream_of_frequency", "stream", "frequency", "sof", "stream of frequency preset")),
    _mk_preset(6, "beyond_dimensions", "Beyond Dimensions", "MPlanetarian - Beyond Dimensions",
               "beyond_dimensions_cover.png", "Beyond_Dimensions_Preset.png", _WDB / "Cotangent Dimensions (In Progress) [album].png",
               vid="20231129 - BEYOND BASEL 2023： DEFASTEN [IoEpQ09v2l4].mkv",
               aliases=("beyond dimensions", "beyond_dimensions", "beyond", "dimensions", "cotangent", "cotangent dimensions", "beyond basel", "beyond_basel")),
    _mk_preset(7, "particle_accelerator", "Particle Accelerator", "MPlanetarian - Particle Accelerator",
               "particle_accelerator_cover.png", "Particle_Accelerator_Preset.png", _WDB / "Vortex Sync (Mateh's Version) [track].png",
               vid="20191112 - TOROID (feat. Yaporigami) [_2vtEhBzPsE].mkv",
               aliases=("particle accelerator", "particle_accelerator", "particle", "accelerator", "toroid", "vortex sync", "vortex_sync", "collider")),
    _mk_preset(8, "cosmic_universe", "Cosmic Universe", "MPlanetarian - Cosmic Universe",
               "cosmic_universe_cover.png", "Cosmic_Universe_Preset.png", _WDB / "The Cosmological Horizon (2026 Remaster) [track].png",
               vid="20120811 - Constellation (2012) [ISIu20AePHw].mkv",
               aliases=("cosmic universe", "cosmic_universe", "cosmic", "universe", "constellation", "the cosmological horizon", "cosmological horizon", "horizon")),
    _mk_preset(9, "resonant_fluid_dynamics", "Resonant Fluid Dynamics", "MPlanetarian - Resonant Fluid Dynamics",
               "resonant_fluid_dynamics_cover.png", "Resonant_Fluid_Dynamics_Preset.png", _HOME / "Documents/Resonant Fluid Dynamics.png",
               vid="20230607 - Yaporigami - Earth Flipper (2022) [KE8zIfDsloA].mkv",
               aliases=("resonant fluid dynamics", "resonant_fluid_dynamics", "resonant", "fluid dynamics", "fluid_dynamics", "earth flipper", "earth_flipper", "10", "yaporigami", "defasten earth flipper")),
]

_SYS = platform.system().lower()
_IS_WIN = sys.platform == "win32" or _SYS == "windows"
_IS_MAC = sys.platform == "darwin" or _SYS == "darwin"
_IS_ARM = _IS_MAC and platform.machine().lower() in ("arm64", "aarch64")

def is_windows() -> bool: return _IS_WIN
def is_windows_10_or_11() -> bool: return _IS_WIN and getattr(sys.getwindowsversion(), "major", 10) >= 10 if hasattr(sys, "getwindowsversion") else _IS_WIN
def is_macos() -> bool: return _IS_MAC
def is_apple_silicon() -> bool: return _IS_ARM

def _load_cdll(cands: List[str], names: Tuple[str, ...], bad: Tuple[str, ...], err: str, fb: Optional[str] = None):
    try:
        for n in names:
            f = find_library(n)
            if f and not any(x in f for x in bad) and f not in cands: cands.insert(0, f)
    except Exception: pass
    for c in cands:
        try: return ctypes.CDLL(c)
        except OSError: continue
    if fb: return ctypes.CDLL(fb)
    raise RuntimeError(err)

def load_glfw_dll():
    if _IS_WIN:
        return _load_cdll(["glfw3.dll", "glfw.dll", os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "glfw", "lib", "glfw3.dll"),
                           os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "glfw", "glfw3.dll")],
                          ("glfw3", "glfw"), (".so", ".dylib"), "Could not load GLFW on Windows. Ensure glfw3.dll is in PATH.")
    if _IS_MAC:
        return _load_cdll(["/opt/homebrew/lib/libglfw.3.dylib", "/opt/homebrew/lib/libglfw.dylib", "/usr/local/lib/libglfw.3.dylib",
                           "/usr/local/lib/libglfw.dylib", "libglfw.3.dylib", "libglfw.dylib"],
                          ("glfw3", "glfw"), (".so", ".dll"), "Could not load GLFW on macOS. Please install GLFW (e.g. 'brew install glfw') or ensure libglfw is available.")
    return _load_cdll(["libglfw.so.3", "libglfw.so", "/usr/lib64/libglfw.so.3", "/usr/lib/x86_64-linux-gnu/libglfw.so.3"],
                      ("glfw3", "glfw"), (".dll", ".dylib"), "", fb="libglfw.so.3")

def load_vulkan_dll():
    sdk = os.environ.get("VULKAN_SDK")
    if _IS_WIN:
        sr = os.environ.get("SystemRoot", "C:\\Windows")
        return _load_cdll(([os.path.join(sdk, "Bin", "vulkan-1.dll")] if sdk else []) + ["vulkan-1.dll", os.path.join(sr, "System32", "vulkan-1.dll"), os.path.join(sr, "SysWOW64", "vulkan-1.dll")],
                          ("vulkan-1", "vulkan"), (".so", ".dylib"), "Could not load Vulkan loader on Windows. Ensure vulkan-1.dll is installed.")
    if _IS_MAC:
        return _load_cdll(([os.path.join(sdk, "lib", x) for x in ("libMoltenVK.dylib", "libvulkan.1.dylib", "libvulkan.dylib")] if sdk else []) +
                          ["/opt/homebrew/lib/libvulkan.1.dylib", "/opt/homebrew/lib/libvulkan.dylib", "/opt/homebrew/lib/libMoltenVK.dylib",
                           "/usr/local/lib/libvulkan.1.dylib", "/usr/local/lib/libvulkan.dylib", "/usr/local/lib/libMoltenVK.dylib",
                           "libvulkan.1.dylib", "libvulkan.dylib", "libMoltenVK.dylib"],
                          ("vulkan", "MoltenVK"), (".so", ".dll"), "Could not load Vulkan loader or MoltenVK on macOS. Please install MoltenVK or the Vulkan SDK (e.g. 'brew install molten-vk' or LunarG Vulkan SDK).")
    return _load_cdll(["libvulkan.so.1", "libvulkan.so", "/usr/lib64/libvulkan.so.1", "/usr/lib/x86_64-linux-gnu/libvulkan.so.1"],
                      ("vulkan-1", "vulkan"), (".dll", ".dylib"), "", fb="libvulkan.so.1")

_RAND_KEYS = {"random", "rand", "rnd", "-1", "any", "shuffle"}

def get_active_preset(preset_arg: Optional[str] = None) -> Dict[str, Any]:
    t = str(preset_arg or "").strip().lower()
    if t in _RAND_KEYS: return random.choice(VISUALIZER_PRESETS)
    if not t:
        try:
            t = (CONFIG_DIR / "visualizer_preset").read_text(encoding="utf-8").strip().lower()
            if t in _RAND_KEYS: return random.choice(VISUALIZER_PRESETS)
        except OSError: pass
    if not t:
        try:
            th = (CONFIG_DIR / "theme").read_text(encoding="utf-8").strip().lower()
            if th in ("sensorium", "sensorium_interface", "sensorium interface", "earth_flipper", "earth flipper"): t = "sensorium_interface"
            elif th in ("stream_of_frequency", "stream", "frequency", "sof", "frequency_stream"): t = "stream_of_frequency"
        except OSError: pass
    if t:
        for p in VISUALIZER_PRESETS:
            kl = p["key"].lower()
            if t in (str(p["id"] + 1), str(p["id"]), kl, p["name"].lower(), kl.replace("_", "-"), kl.replace("_", " ")) or t in p.get("_aliases", ()): return p
        for p in VISUALIZER_PRESETS:
            if t in p["key"].lower() or t in p["name"].lower(): return p
    return VISUALIZER_PRESETS[0]

def save_active_preset(preset_key_or_name: str) -> Dict[str, Any]:
    p = get_active_preset(preset_key_or_name)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (CONFIG_DIR / "visualizer_preset").write_text(p["key"], encoding="utf-8")
    except OSError: pass
    return p

def load_preset_cover_rgba(preset: Dict[str, Any], tex_size: int = 1024) -> Tuple[int, int, bytes]:
    from PIL import Image
    for cp in preset.get("cover_paths", []):
        p = Path(cp)
        if p.is_file():
            with Image.open(p) as im:
                return tex_size, tex_size, im.convert("RGBA").resize((tex_size, tex_size), Image.Resampling.LANCZOS).tobytes()
    raise FileNotFoundError(f"Cover art file not found for preset '{preset.get('name')}'")


class AudioTelemetryBridge:
    __slots__ = (
        "config_dir", "state_file", "socket_path", "port_file", "_state_str", "_sock_str", "is_playing", "accum_time", "dynamic_time",
        "bass_phase", "mid_phase", "high_phase", "beat_pulse", "_prev_bass", "_last_poll", "_last_state_mtime_ns",
        "_cached_status", "bands16", "sub_bass", "bass", "low_mid", "mid", "high_mid", "treble", "air", "rms_energy", "pitch_factor"
    )

    def __init__(self, config_dir: Optional[Path] = None):
        c = Path(config_dir) if config_dir else CONFIG_DIR
        self.config_dir, self.state_file, self.socket_path, self.port_file = c, c / "mp_player_state.json", c / "mp_audio_player.sock", c / "mp_audio_player.port"
        self._state_str, self._sock_str = str(self.state_file), str(self.socket_path)
        self.is_playing = False
        self.accum_time = self.dynamic_time = self.bass_phase = self.mid_phase = self.high_phase = self.beat_pulse = self._prev_bass = self._last_poll = 0.0
        self._last_state_mtime_ns = 0
        self._cached_status: Dict[str, Any] = {}
        self.bands16: List[float] = [0.0] * 16
        self.sub_bass = self.bass = self.low_mid = self.mid = self.high_mid = self.treble = self.air = self.rms_energy = 0.0
        self.pitch_factor = 1.0

    def _query_player_state(self) -> Dict[str, Any]:
        now = time.monotonic()
        changed, st_stat = False, None
        try:
            st_stat = os.stat(self._state_str)
            if st_stat.st_mtime_ns != self._last_state_mtime_ns:
                changed, self._last_state_mtime_ns = True, st_stat.st_mtime_ns
        except OSError: pass

        if not changed and (now - self._last_poll < 0.025) and self._cached_status:
            return self._cached_status
        self._last_poll = now

        if st_stat is not None and (time.time() - st_stat.st_mtime < 3.0):
            try:
                with open(self._state_str, "rb") as f:
                    data = json.loads(f.read())
                if isinstance(data, dict):
                    self._cached_status = data
                    return data
            except Exception: pass

        use_unix = hasattr(socket, "AF_UNIX") and os.path.exists(self._sock_str)
        if use_unix or self.port_file.exists():
            try:
                with socket.socket(socket.AF_UNIX if use_unix else socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.05)
                    s.connect(self._sock_str if use_unix else ("127.0.0.1", int(self.port_file.read_text().strip())))
                    s.sendall(b'{"cmd": "status"}')
                    raw = s.recv(16384)
                if raw:
                    resp = json.loads(raw)
                    if isinstance(resp.get("data"), dict):
                        self._cached_status = resp["data"]
                        return self._cached_status
            except Exception: pass

        self._cached_status = {"running": False, "state": "stopped"}
        return self._cached_status

    def update(self, dt: float, force_playing: Optional[bool] = None, synthetic_audio: bool = False, _sin=math.sin, _cos=math.cos):
        dt = 0.0 if dt < 0.0 else (0.1 if dt > 0.1 else dt)
        if synthetic_audio:
            self.is_playing = True if force_playing is None else bool(force_playing)
            if self.is_playing:
                self.accum_time += dt
                t = self.accum_time
                self.dynamic_time += dt * (1.0 + 0.55 * _sin(t * 0.09) * _cos(t * 0.045) + 0.25 * _sin(t * 0.18))
                self._apply_bands([0.55 + 0.40 * _sin(t * 3.2 + i * 0.45) ** 2 for i in range(16)], 0.62, 1.0, dt)
            return

        st = self._query_player_state()
        playing = bool(st.get("running", True)) and str(st.get("state", "stopped")).lower() == "playing" and not bool(st.get("muted", False))
        self.is_playing = playing if force_playing is None else bool(force_playing)
        if not self.is_playing: return

        p = float(st.get("pitch_factor", 1.0) or 1.0)
        self.pitch_factor = p = 0.5 if p < 0.5 else (1.5 if p > 1.5 else p)
        self.accum_time += dt * p
        t = self.accum_time
        rms = float(st.get("rms_level", 0.0) or 0.0)
        rc = 0.0 if rms < 0.0 else (1.0 if rms > 0.5 else rms * 2.0)
        self.dynamic_time += dt * (1.0 + 0.65 * _sin(t * 0.082) * _cos(t * 0.041) + 0.35 * _sin(t * 0.173)) * (0.85 + 0.30 * rc) * p

        lv = st.get("levels")
        if isinstance(lv, list) and len(lv) >= 8:
            n = len(lv) - 1
            raw16 = [0.0] * 16
            for i in range(16):
                f = (i / 15.0) * n
                i0 = int(f)
                v = float(lv[i0]) * (1.0 - (f - i0)) + float(lv[i0 + 1 if i0 < n else n]) * (f - i0)
                raw16[i] = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
        else:
            pos = float(st.get("position_sec", t) or t)
            raw16 = [0.25 + 0.20 * _sin(pos * (2.5 + i * 0.3) + i) ** 2 for i in range(16)]
            if rms < 0.28: rms = 0.28
        self._apply_bands(raw16, rms, p, dt)

    def _apply_bands(self, raw16: List[float], rms: float, pitch: float, dt: float):
        b = self.bands16
        for i in range(16):
            tg, c = raw16[i], b[i]
            b[i] = c + (tg - c) * (0.68 if tg > c else 0.22)

        self.sub_bass = (b[0] + b[1]) * 0.5
        self.bass = (b[1] + b[2] + b[3]) * 0.3333333333333333
        self.low_mid = (b[4] + b[5] + b[6]) * 0.3333333333333333
        self.mid = (b[6] + b[7] + b[8] + b[9]) * 0.25
        self.high_mid = (b[10] + b[11] + b[12]) * 0.3333333333333333
        self.treble = (b[12] + b[13] + b[14]) * 0.3333333333333333
        self.air = b[15]
        e = rms * 2.2 + self.bass * 0.35
        self.rms_energy = 0.0 if e < 0.0 else (1.0 if e > 1.0 else e)

        bd = self.bass - self._prev_bass
        self._prev_bass = self.bass
        bp = (self.beat_pulse + bd * 3.2) if bd > 0.065 else (self.beat_pulse - dt * 2.8)
        self.beat_pulse = 0.0 if bp < 0.0 else (1.0 if bp > 1.0 else bp)

        self.bass_phase += dt * (1.2 + self.sub_bass * 4.2 + self.beat_pulse * 2.0) * pitch
        self.mid_phase += dt * (1.0 + self.mid * 3.6) * pitch
        self.high_phase += dt * (0.9 + self.treble * 4.0) * pitch


NVIDIA_VENDOR_ID, DISCRETE_GPU = 0x10DE, 2
(ST_APPLICATION_INFO, ST_INSTANCE_CREATE_INFO, ST_DEVICE_QUEUE_CREATE_INFO, ST_DEVICE_CREATE_INFO, ST_SUBMIT_INFO,
 ST_MEMORY_ALLOCATE_INFO, ST_FENCE_CREATE_INFO, ST_SEMAPHORE_CREATE_INFO, ST_BUFFER_CREATE_INFO, ST_IMAGE_CREATE_INFO,
 ST_IMAGE_VIEW_CREATE_INFO, ST_SHADER_MODULE_CREATE_INFO, ST_PIPELINE_SHADER_STAGE, ST_PIPELINE_VERTEX_INPUT,
 ST_PIPELINE_INPUT_ASSEMBLY, ST_PIPELINE_VIEWPORT, ST_PIPELINE_RASTER, ST_PIPELINE_MULTISAMPLE, ST_PIPELINE_COLOR_BLEND,
 ST_PIPELINE_DYNAMIC, ST_GRAPHICS_PIPELINE, ST_PIPELINE_LAYOUT, ST_SAMPLER_CREATE_INFO, ST_DESCRIPTOR_SET_LAYOUT,
 ST_DESCRIPTOR_POOL, ST_DESCRIPTOR_SET_ALLOCATE, ST_WRITE_DESCRIPTOR_SET, ST_FRAMEBUFFER, ST_RENDER_PASS,
 ST_COMMAND_POOL, ST_COMMAND_BUFFER_ALLOCATE, ST_COMMAND_BUFFER_BEGIN, ST_RENDER_PASS_BEGIN, ST_BUFFER_MEMORY_BARRIER,
 ST_IMAGE_MEMORY_BARRIER, ST_SWAPCHAIN_CREATE, ST_PRESENT_INFO) = (
    0, 1, 2, 3, 4, 5, 8, 9, 12, 14, 15, 16, 18, 19, 20, 22, 23, 24, 26, 27, 28, 30, 31, 32, 33, 34, 35, 37, 38, 39, 40, 42, 43, 44, 45, 1000001000, 1000001001
)

QUEUE_GRAPHICS = IMAGE_USAGE_TRANSFER_SRC = BUFFER_USAGE_TRANSFER_SRC = COMPOSITE_OPAQUE = VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR = TRANSFORM_IDENTITY = IMAGE_TYPE_2D = IMAGE_VIEW_2D = IMAGE_ASPECT_COLOR = SAMPLE_1 = LOAD_CLEAR = STORE_DONT = STAGE_TOP = STAGE_VERTEX_BIT = CMD_ONE_TIME = FENCE_SIGNALED = DYNAMIC_SCISSOR = DESCRIPTOR_COMBINED_IMAGE_SAMPLER = SHADER_VERTEX = MEMORY_DEVICE_LOCAL = FILTER_LINEAR = SAMPLER_MIPMAP_LINEAR = GLFW_TRUE = GLFW_PRESS = 1
IMAGE_USAGE_TRANSFER_DST = BUFFER_USAGE_TRANSFER_DST = COMPOSITE_PRE_MULTIPLIED = PRESENT_FIFO = LOAD_DONT = LAYOUT_COLOR = CMD_POOL_RESET = MEMORY_HOST_VISIBLE = 2
SHARING_EXCLUSIVE = TILING_OPTIMAL = STORE_STORE = LAYOUT_UNDEFINED = DYNAMIC_VIEWPORT = SUCCESS = SAMPLER_ADDRESS_REPEAT = GLFW_NO_API = GLFW_FALSE = 0
IMAGE_USAGE_SAMPLED = COMPOSITE_POST_MULTIPLIED = MEMORY_HOST_COHERENT = 4
COMPOSITE_INHERIT = ACCESS_UNIFORM = 8
IMAGE_USAGE_COLOR = BUFFER_USAGE_UNIFORM = STAGE_FRAGMENT_BIT = SHADER_FRAGMENT = 0x10
FORMAT_R8G8B8A8_UNORM, FORMAT_B8G8R8A8_UNORM, FORMAT_B8G8R8A8_SRGB = 37, 44, 50
LAYOUT_SHADER_READ_ONLY, LAYOUT_TRANSFER_SRC, LAYOUT_TRANSFER_DST, LAYOUT_PRESENT = 5, 6, 7, 1000001002
SUBPASS_EXTERNAL = QUEUE_FAMILY_IGNORED = 0xFFFFFFFF
STAGE_FRAGMENT, STAGE_COLOR_OUT, STAGE_TRANSFER, STAGE_BOTTOM, STAGE_HOST = 0x80, 0x400, 0x1000, 0x2000, 0x4000
ACCESS_SHADER_READ, ACCESS_COLOR_WRITE, ACCESS_TRANSFER_READ, ACCESS_TRANSFER_WRITE, ACCESS_HOST_WRITE, ACCESS_MEMORY_READ = 0x20, 0x100, 0x800, 0x1000, 0x4000, 0x8000
TOPOLOGY_TRIANGLE_LIST, COLOR_WRITE_ALL, DESCRIPTOR_UNIFORM = 3, 0xF, 6
SUBOPTIMAL, OUT_OF_DATE = 1000001003, -1000001004

GLFW_CLIENT_API, GLFW_RESIZABLE, GLFW_VISIBLE, GLFW_DECORATED = 0x00022001, 0x00020003, 0x00020004, 0x00020005
GLFW_FOCUSED, GLFW_AUTO_ICONIFY, GLFW_FLOATING, GLFW_ICONIFIED = 0x00020001, 0x00020006, 0x00020007, 0x00020002
GLFW_FOCUS_ON_SHOW, GLFW_PLATFORM, GLFW_PLATFORM_X11, GLFW_DONT_CARE = 0x0002000C, 0x00050003, 0x00060004, -1
GLFW_KEY_ESCAPE, GLFW_KEY_Q, GLFW_KEY_Z, GLFW_KEY_SPACE = 256, 81, 90, 32
GLFW_KEY_1, GLFW_KEY_2, GLFW_KEY_3, GLFW_KEY_4, GLFW_KEY_5, GLFW_KEY_6, GLFW_KEY_7, GLFW_KEY_8, GLFW_KEY_9 = range(49, 58)

U32, I32, U64, F32, VP, CP = c_uint32, c_int32, c_uint64, c_float, c_void_p, c_char_p
def _S(n: str, *f: Tuple[str, Any]): return type(n, (Structure,), {"_fields_": list(f)})

GLFWvidmode = _S("GLFWvidmode", ("width", c_int), ("height", c_int), ("redBits", c_int), ("greenBits", c_int), ("blueBits", c_int), ("refreshRate", c_int))
VkApplicationInfo = _S("VkApplicationInfo", ("sType", U32), ("pNext", VP), ("pApplicationName", CP), ("applicationVersion", U32), ("pEngineName", CP), ("engineVersion", U32), ("apiVersion", U32))
VkInstanceCreateInfo = _S("VkInstanceCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("pApplicationInfo", VP), ("enabledLayerCount", U32), ("ppEnabledLayerNames", VP), ("enabledExtensionCount", U32), ("ppEnabledExtensionNames", VP))
VkDeviceQueueCreateInfo = _S("VkDeviceQueueCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("queueFamilyIndex", U32), ("queueCount", U32), ("pQueuePriorities", VP))
VkDeviceCreateInfo = _S("VkDeviceCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("queueCreateInfoCount", U32), ("pQueueCreateInfos", VP), ("enabledLayerCount", U32), ("ppEnabledLayerNames", VP), ("enabledExtensionCount", U32), ("ppEnabledExtensionNames", VP), ("pEnabledFeatures", VP))
VkExtent2D = _S("VkExtent2D", ("width", U32), ("height", U32))
VkExtent3D = _S("VkExtent3D", ("width", U32), ("height", U32), ("depth", U32))
VkOffset2D = _S("VkOffset2D", ("x", I32), ("y", I32))
VkOffset3D = _S("VkOffset3D", ("x", I32), ("y", I32), ("z", I32))
VkRect2D = _S("VkRect2D", ("offset", VkOffset2D), ("extent", VkExtent2D))
VkSurfaceCapabilitiesKHR = _S("VkSurfaceCapabilitiesKHR", ("minImageCount", U32), ("maxImageCount", U32), ("currentExtent", VkExtent2D), ("minImageExtent", VkExtent2D), ("maxImageExtent", VkExtent2D), ("maxImageArrayLayers", U32), ("supportedTransforms", U32), ("currentTransform", U32), ("supportedCompositeAlpha", U32), ("supportedUsageFlags", U32))
VkSurfaceFormatKHR = _S("VkSurfaceFormatKHR", ("format", U32), ("colorSpace", U32))
VkSwapchainCreateInfoKHR = _S("VkSwapchainCreateInfoKHR", ("sType", U32), ("pNext", VP), ("flags", U32), ("surface", U64), ("minImageCount", U32), ("imageFormat", U32), ("imageColorSpace", U32), ("imageExtent", VkExtent2D), ("imageArrayLayers", U32), ("imageUsage", U32), ("imageSharingMode", U32), ("queueFamilyIndexCount", U32), ("pQueueFamilyIndices", VP), ("preTransform", U32), ("compositeAlpha", U32), ("presentMode", U32), ("clipped", U32), ("oldSwapchain", U64))
VkImageCreateInfo = _S("VkImageCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("imageType", U32), ("format", U32), ("extent", VkExtent3D), ("mipLevels", U32), ("arrayLayers", U32), ("samples", U32), ("tiling", U32), ("usage", U32), ("sharingMode", U32), ("queueFamilyIndexCount", U32), ("pQueueFamilyIndices", VP), ("initialLayout", U32))
VkImageViewCreateInfo = _S("VkImageViewCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("image", U64), ("viewType", U32), ("format", U32), ("r", U32), ("g", U32), ("b", U32), ("a", U32), ("aspectMask", U32), ("baseMipLevel", U32), ("levelCount", U32), ("baseArrayLayer", U32), ("layerCount", U32))
VkSamplerCreateInfo = _S("VkSamplerCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("magFilter", U32), ("minFilter", U32), ("mipmapMode", U32), ("addressModeU", U32), ("addressModeV", U32), ("addressModeW", U32), ("mipLodBias", F32), ("anisotropyEnable", U32), ("maxAnisotropy", F32), ("compareEnable", U32), ("compareOp", U32), ("minLod", F32), ("maxLod", F32), ("borderColor", U32), ("unnormalizedCoordinates", U32))
VkAttachmentDescription = _S("VkAttachmentDescription", ("flags", U32), ("format", U32), ("samples", U32), ("loadOp", U32), ("storeOp", U32), ("stencilLoadOp", U32), ("stencilStoreOp", U32), ("initialLayout", U32), ("finalLayout", U32))
VkAttachmentReference = _S("VkAttachmentReference", ("attachment", U32), ("layout", U32))
VkSubpassDescription = _S("VkSubpassDescription", ("flags", U32), ("pipelineBindPoint", U32), ("inputAttachmentCount", U32), ("pInputAttachments", VP), ("colorAttachmentCount", U32), ("pColorAttachments", VP), ("pResolveAttachments", VP), ("pDepthStencilAttachment", VP), ("preserveAttachmentCount", U32), ("pPreserveAttachments", VP))
VkSubpassDependency = _S("VkSubpassDependency", ("srcSubpass", U32), ("dstSubpass", U32), ("srcStageMask", U32), ("dstStageMask", U32), ("srcAccessMask", U32), ("dstAccessMask", U32), ("dependencyFlags", U32))
VkRenderPassCreateInfo = _S("VkRenderPassCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("attachmentCount", U32), ("pAttachments", VP), ("subpassCount", U32), ("pSubpasses", VP), ("dependencyCount", U32), ("pDependencies", VP))
VkFramebufferCreateInfo = _S("VkFramebufferCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("renderPass", U64), ("attachmentCount", U32), ("pAttachments", VP), ("width", U32), ("height", U32), ("layers", U32))
VkShaderModuleCreateInfo = _S("VkShaderModuleCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("codeSize", c_size_t), ("pCode", VP))
VkPipelineShaderStageCreateInfo = _S("VkPipelineShaderStageCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("stage", U32), ("module", U64), ("pName", CP), ("pSpecializationInfo", VP))
VkPipelineVertexInputStateCreateInfo = _S("VkPipelineVertexInputStateCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("vertexBindingDescriptionCount", U32), ("pVertexBindingDescriptions", VP), ("vertexAttributeDescriptionCount", U32), ("pVertexAttributeDescriptions", VP))
VkPipelineInputAssemblyStateCreateInfo = _S("VkPipelineInputAssemblyStateCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("topology", U32), ("primitiveRestartEnable", U32))
VkPipelineViewportStateCreateInfo = _S("VkPipelineViewportStateCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("viewportCount", U32), ("pViewports", VP), ("scissorCount", U32), ("pScissors", VP))
VkPipelineRasterizationStateCreateInfo = _S("VkPipelineRasterizationStateCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("depthClampEnable", U32), ("rasterizerDiscardEnable", U32), ("polygonMode", U32), ("cullMode", U32), ("frontFace", U32), ("depthBiasEnable", U32), ("depthBiasConstantFactor", F32), ("depthBiasClamp", F32), ("depthBiasSlopeFactor", F32), ("lineWidth", F32))
VkPipelineMultisampleStateCreateInfo = _S("VkPipelineMultisampleStateCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("rasterizationSamples", U32), ("sampleShadingEnable", U32), ("minSampleShading", F32), ("pSampleMask", VP), ("alphaToCoverageEnable", U32), ("alphaToOneEnable", U32))
VkPipelineColorBlendAttachmentState = _S("VkPipelineColorBlendAttachmentState", ("blendEnable", U32), ("srcColorBlendFactor", U32), ("dstColorBlendFactor", U32), ("colorBlendOp", U32), ("srcAlphaBlendFactor", U32), ("dstAlphaBlendFactor", U32), ("alphaBlendOp", U32), ("colorWriteMask", U32))
VkPipelineColorBlendStateCreateInfo = _S("VkPipelineColorBlendStateCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("logicOpEnable", U32), ("logicOp", U32), ("attachmentCount", U32), ("pAttachments", VP), ("blendConstants", F32 * 4))
VkPipelineDynamicStateCreateInfo = _S("VkPipelineDynamicStateCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("dynamicStateCount", U32), ("pDynamicStates", VP))
VkPipelineLayoutCreateInfo = _S("VkPipelineLayoutCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("setLayoutCount", U32), ("pSetLayouts", VP), ("pushConstantRangeCount", U32), ("pPushConstantRanges", VP))
VkGraphicsPipelineCreateInfo = _S("VkGraphicsPipelineCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("stageCount", U32), ("pStages", VP), ("pVertexInputState", VP), ("pInputAssemblyState", VP), ("pTessellationState", VP), ("pViewportState", VP), ("pRasterizationState", VP), ("pMultisampleState", VP), ("pDepthStencilState", VP), ("pColorBlendState", VP), ("pDynamicState", VP), ("layout", U64), ("renderPass", U64), ("subpass", U32), ("basePipelineHandle", U64), ("basePipelineIndex", I32))
VkDescriptorSetLayoutBinding = _S("VkDescriptorSetLayoutBinding", ("binding", U32), ("descriptorType", U32), ("descriptorCount", U32), ("stageFlags", U32), ("pImmutableSamplers", VP))
VkDescriptorSetLayoutCreateInfo = _S("VkDescriptorSetLayoutCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("bindingCount", U32), ("pBindings", VP))
VkDescriptorPoolSize = _S("VkDescriptorPoolSize", ("type", U32), ("descriptorCount", U32))
VkDescriptorPoolCreateInfo = _S("VkDescriptorPoolCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("maxSets", U32), ("poolSizeCount", U32), ("pPoolSizes", VP))
VkDescriptorSetAllocateInfo = _S("VkDescriptorSetAllocateInfo", ("sType", U32), ("pNext", VP), ("descriptorPool", U64), ("descriptorSetCount", U32), ("pSetLayouts", VP))
VkDescriptorBufferInfo = _S("VkDescriptorBufferInfo", ("buffer", U64), ("offset", U64), ("range", U64))
VkDescriptorImageInfo = _S("VkDescriptorImageInfo", ("sampler", U64), ("imageView", U64), ("imageLayout", U32))
VkWriteDescriptorSet = _S("VkWriteDescriptorSet", ("sType", U32), ("pNext", VP), ("dstSet", U64), ("dstBinding", U32), ("dstArrayElement", U32), ("descriptorCount", U32), ("descriptorType", U32), ("pImageInfo", VP), ("pBufferInfo", VP), ("pTexelBufferView", VP))
VkBufferCreateInfo = _S("VkBufferCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("size", U64), ("usage", U32), ("sharingMode", U32), ("queueFamilyIndexCount", U32), ("pQueueFamilyIndices", VP))
VkMemoryAllocateInfo = _S("VkMemoryAllocateInfo", ("sType", U32), ("pNext", VP), ("allocationSize", U64), ("memoryTypeIndex", U32))
VkMemoryRequirements = _S("VkMemoryRequirements", ("size", U64), ("alignment", U64), ("memoryTypeBits", U32))
VkMemoryType = _S("VkMemoryType", ("propertyFlags", U32), ("heapIndex", U32))
VkMemoryHeap = _S("VkMemoryHeap", ("size", U64), ("flags", U32), ("_pad", U32))
VkPhysicalDeviceMemoryProperties = _S("VkPhysicalDeviceMemoryProperties", ("memoryTypeCount", U32), ("memoryTypes", VkMemoryType * 32), ("memoryHeapCount", U32), ("memoryHeaps", VkMemoryHeap * 16))
VkQueueFamilyProperties = _S("VkQueueFamilyProperties", ("queueFlags", U32), ("queueCount", U32), ("timestampValidBits", U32), ("minImageTransferGranularity", VkExtent3D))
VkCommandPoolCreateInfo = _S("VkCommandPoolCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("queueFamilyIndex", U32))
VkCommandBufferAllocateInfo = _S("VkCommandBufferAllocateInfo", ("sType", U32), ("pNext", VP), ("commandPool", U64), ("level", U32), ("commandBufferCount", U32))
VkCommandBufferBeginInfo = _S("VkCommandBufferBeginInfo", ("sType", U32), ("pNext", VP), ("flags", U32), ("pInheritanceInfo", VP))
VkClearValue = _S("VkClearValue", ("color", F32 * 4))
VkRenderPassBeginInfo = _S("VkRenderPassBeginInfo", ("sType", U32), ("pNext", VP), ("renderPass", U64), ("framebuffer", U64), ("renderArea", VkRect2D), ("clearValueCount", U32), ("pClearValues", VP))
VkViewport = _S("VkViewport", ("x", F32), ("y", F32), ("width", F32), ("height", F32), ("minDepth", F32), ("maxDepth", F32))
VkSubmitInfo = _S("VkSubmitInfo", ("sType", U32), ("pNext", VP), ("waitSemaphoreCount", U32), ("pWaitSemaphores", VP), ("pWaitDstStageMask", VP), ("commandBufferCount", U32), ("pCommandBuffers", VP), ("signalSemaphoreCount", U32), ("pSignalSemaphores", VP))
VkPresentInfoKHR = _S("VkPresentInfoKHR", ("sType", U32), ("pNext", VP), ("waitSemaphoreCount", U32), ("pWaitSemaphores", VP), ("swapchainCount", U32), ("pSwapchains", VP), ("pImageIndices", VP), ("pResults", VP))
VkBufferMemoryBarrier = _S("VkBufferMemoryBarrier", ("sType", U32), ("pNext", VP), ("srcAccessMask", U32), ("dstAccessMask", U32), ("srcQueueFamilyIndex", U32), ("dstQueueFamilyIndex", U32), ("buffer", U64), ("offset", U64), ("size", U64))
VkImageSubresourceRange = _S("VkImageSubresourceRange", ("aspectMask", U32), ("baseMipLevel", U32), ("levelCount", U32), ("baseArrayLayer", U32), ("layerCount", U32))
VkImageMemoryBarrier = _S("VkImageMemoryBarrier", ("sType", U32), ("pNext", VP), ("srcAccessMask", U32), ("dstAccessMask", U32), ("oldLayout", U32), ("newLayout", U32), ("srcQueueFamilyIndex", U32), ("dstQueueFamilyIndex", U32), ("image", U64), ("subresourceRange", VkImageSubresourceRange))
VkImageSubresourceLayers = _S("VkImageSubresourceLayers", ("aspectMask", U32), ("mipLevel", U32), ("baseArrayLayer", U32), ("layerCount", U32))
VkBufferImageCopy = _S("VkBufferImageCopy", ("bufferOffset", U64), ("bufferRowLength", U32), ("bufferImageHeight", U32), ("imageSubresource", VkImageSubresourceLayers), ("imageOffset", VkOffset3D), ("imageExtent", VkExtent3D))
VkFenceCreateInfo = _S("VkFenceCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32))
VkSemaphoreCreateInfo = _S("VkSemaphoreCreateInfo", ("sType", U32), ("pNext", VP), ("flags", U32))
VisualizerUBO = _S("VisualizerUBO", ("res", F32 * 4), ("audio0", F32 * 4), ("audio1", F32 * 4), ("audio2", F32 * 4), ("bands0", F32 * 4), ("bands1", F32 * 4), ("bands2", F32 * 4), ("bands3", F32 * 4), ("preset", F32 * 4))
_VkExtProp = _S("_VkExtProp", ("extensionName", c_char * 256), ("specVersion", U32))
_WinPOINT = _S("_WinPOINT", ("x", c_int), ("y", c_int))

def _api_version(major, minor, patch=0): return (major << 22) | (minor << 12) | patch
def _check(result, what):
    if result != SUCCESS: raise RuntimeError(f"{what} failed with Vulkan result {result}")
    return result
def _addr(obj): return cast(byref(obj), VP)
def _load(getter, owner, name, restype, argtypes):
    raw = getter(owner, name.encode())
    if not raw: raise RuntimeError(f"Vulkan entry point {name} is missing")
    return CFUNCTYPE(restype, *argtypes)(raw)

def select_vulkan_device(devices: List[Dict[str, Any]]) -> int:
    nvidia = [i for i, d in enumerate(devices) if int(d["vendor_id"]) == NVIDIA_VENDOR_ID]
    if nvidia:
        disc = [i for i in nvidia if int(devices[i].get("device_type", -1)) == DISCRETE_GPU]
        return (disc or nvidia)[0]
    disc = [i for i, d in enumerate(devices) if int(d.get("device_type", -1)) == DISCRETE_GPU]
    if disc: return disc[0]
    if devices: return 0
    raise RuntimeError("MP_Liquid_Visualizer requires a Vulkan-capable GPU.")


class LiquidVisualizerVulkanRenderer:
    width = WINDOW_WIDTH
    height = WINDOW_HEIGHT

    def __init__(self, preset_name: Optional[str] = None, fullscreen: bool = False, target_4k: bool = False):
        self.preset = get_active_preset(preset_name)
        self.title = "MP Liquid Visualizer"
        self.target_4k = target_4k
        self.fullscreen_on_start = fullscreen or target_4k
        self._user_toggled_windowed = self.should_close = self.mouse_down = self._drag_active = self.is_fullscreen = self._resize = self._alive = self._is_4k_cached = False
        self._last_monitor = self._readback_ptr = None
        self.device_name = ""
        self.vendor_id = self._frame = self._swapchain = self._tex_image = self._tex_memory = self._tex_view = self._tex_sampler = self._readback_buffer = self._readback_memory = self._readback_bytes = 0
        self.device_type = -1
        self.format = FORMAT_B8G8R8A8_UNORM
        self.cursor = (0.0, 0.0)
        self._drag_origin = self._drag_press_screen = (0, 0)
        self._cur_pos = self._saved_window_pos = (160, 80)
        self._images, self._views, self._framebuffers, self._image_available, self._render_finished, self._fences, self._cmd = [], [], [], [], [], [], []
        self._extent = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self._ubo_flat = (F32 * 36)()
        self._ubo_flat_ptr = byref(self._ubo_flat)

    @property
    def summary(self) -> str:
        return f"MP_Liquid_Visualizer Vulkan device: {self.device_name} (vendor 0x{self.vendor_id:04x}, {'discrete' if self.device_type == DISCRETE_GPU else 'gpu'}) | Preset: {self.preset['name']} | Window: {self.width}x{self.height} Fixed Borderless"

    def open(self):
        self._silence_overlays()
        self._x11 = None
        if not _IS_WIN and not _IS_MAC:
            try:
                self._x11 = ctypes.CDLL("libX11.so.6")
                self._x11.XInitThreads.restype = c_int
                self._x11.XInitThreads()
                self._bind_x11()
            except Exception:
                self._x11 = None

        self._glfw = load_glfw_dll()
        self._bind_glfw()
        if self._x11 is not None and hasattr(self._glfw, "glfwInitHint"):
            try: self._glfw.glfwInitHint(GLFW_PLATFORM, GLFW_PLATFORM_X11)
            except Exception: pass

        if not self._glfw.glfwInit(): raise RuntimeError("glfwInit failed")
        if not self._glfw.glfwVulkanSupported(): raise RuntimeError("GLFW reports Vulkan is unavailable")

        self._window = self._create_window()
        self._bind_input()
        self._vulkan = load_vulkan_dll()
        self._bind_loader()
        self._create_instance()
        self._load_instance()

        surface = U64()
        _check(self._glfw.glfwCreateWindowSurface(self._instance, self._window, None, byref(surface)), "glfwCreateWindowSurface")
        self._surface = surface.value

        self._pick_device()
        self._create_device()
        self._load_device()
        self._create_swapchain()
        self._create_commands()
        self._create_cover_texture()
        self._create_pipeline()
        self._create_descriptors()
        self._init_hotloop_structs()
        self._alive = True

        if getattr(self, "fullscreen_on_start", False):
            self.toggle_fullscreen()
        return self

    def _silence_overlays(self):
        os.environ.update({
            "DISABLE_MANGOHUD": "1", "MANGOHUD": "0", "DISABLE_VKBASALT": "1", "GALLIUM_HUD": "", "DXVK_HUD": "0",
            "VK_LOADER_LAYERS_DISABLE": "VK_LAYER_MANGOHUD_overlay_x86_64,VK_LAYER_MANGOHUD_overlay_x86,VK_LAYER_VKBASALT_post_processing,VK_LAYER_OBS_vkcapture_64,VK_LAYER_VALVE_steam_overlay_64,VK_LAYER_VALVE_steam_fossilize_64,VK_LAYER_MESA_overlay"
        })

    def _bind_x11(self):
        self._x11.XDefaultRootWindow.argtypes, self._x11.XDefaultRootWindow.restype = [VP], U64
        self._x11.XQueryPointer.argtypes = [VP, U64, POINTER(U64), POINTER(U64), POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(U32)]
        self._x11.XQueryPointer.restype = c_int

    def _bind_glfw(self):
        g, CI, PI = self._glfw, c_int, POINTER(c_int)
        for name, res, args in (
            ("glfwInit", CI, []), ("glfwInitHint", None, [CI, CI]), ("glfwWindowHint", None, [CI, CI]),
            ("glfwVulkanSupported", CI, []), ("glfwCreateWindow", VP, [CI, CI, CP, VP, VP]), ("glfwDestroyWindow", None, [VP]),
            ("glfwTerminate", None, []), ("glfwPollEvents", None, []), ("glfwWindowShouldClose", CI, [VP]),
            ("glfwSetWindowShouldClose", None, [VP, CI]), ("glfwSetWindowPos", None, [VP, CI, CI]),
            ("glfwSetWindowSize", None, [VP, CI, CI]), ("glfwSetWindowSizeLimits", None, [VP, CI, CI, CI, CI]),
            ("glfwGetWindowSize", None, [VP, PI, PI]), ("glfwGetWindowPos", None, [VP, PI, PI]),
            ("glfwGetFramebufferSize", None, [VP, PI, PI]), ("glfwGetPrimaryMonitor", VP, []),
            ("glfwGetMonitors", POINTER(VP), [PI]), ("glfwGetMonitorPos", None, [VP, PI, PI]),
            ("glfwGetVideoMode", POINTER(GLFWvidmode), [VP]), ("glfwGetMonitorName", CP, [VP]),
            ("glfwSetWindowMonitor", None, [VP, VP, CI, CI, CI, CI, CI]),
            ("glfwGetRequiredInstanceExtensions", POINTER(CP), [POINTER(U32)]),
            ("glfwCreateWindowSurface", CI, [VP, VP, VP, POINTER(U64)]),
            ("glfwSetKeyCallback", VP, [VP, VP]), ("glfwSetMouseButtonCallback", VP, [VP, VP]),
            ("glfwSetCursorPosCallback", VP, [VP, VP]), ("glfwSetFramebufferSizeCallback", VP, [VP, VP]),
            ("glfwSetWindowPosCallback", VP, [VP, VP]), ("glfwSetWindowAttrib", None, [VP, CI, CI]),
            ("glfwGetWindowAttrib", CI, [VP, CI]), ("glfwRestoreWindow", None, [VP]), ("glfwFocusWindow", None, [VP]),
            ("glfwSetWindowIconifyCallback", VP, [VP, VP]), ("glfwWindowHintString", None, [CI, CP]),
            ("glfwGetWin32Window", VP, [VP]), ("glfwGetCocoaWindow", VP, [VP]),
            ("glfwGetX11Display", VP, [VP]), ("glfwGetX11Window", U64, [VP]),
        ):
            if hasattr(g, name):
                try:
                    fn = getattr(g, name)
                    fn.restype, fn.argtypes = res, args
                except Exception: pass

    def win32_window(self): return self._glfw.glfwGetWin32Window(self._window) if _IS_WIN and hasattr(self._glfw, "glfwGetWin32Window") and self._window else 0
    def cocoa_window(self): return self._glfw.glfwGetCocoaWindow(self._window) if _IS_MAC and hasattr(self._glfw, "glfwGetCocoaWindow") and self._window else 0
    def x11_window(self):
        if not _IS_WIN and not _IS_MAC and hasattr(self._glfw, "glfwGetX11Window") and self._window:
            try: return self._glfw.glfwGetX11Window(self._window)
            except Exception: pass
        return 0
    def x11_display(self):
        if not _IS_WIN and not _IS_MAC and hasattr(self._glfw, "glfwGetX11Display") and self._window:
            try: return self._glfw.glfwGetX11Display(self._window)
            except Exception: pass
        return None

    def _create_window(self):
        g = self._glfw
        for k, v in ((GLFW_CLIENT_API, GLFW_NO_API), (GLFW_RESIZABLE, GLFW_FALSE), (GLFW_DECORATED, GLFW_FALSE),
                     (GLFW_FOCUS_ON_SHOW, GLFW_TRUE), (GLFW_VISIBLE, GLFW_TRUE), (GLFW_FOCUSED, GLFW_TRUE), (GLFW_AUTO_ICONIFY, GLFW_FALSE)):
            g.glfwWindowHint(k, v)
        if hasattr(g, "glfwWindowHintString"):
            try:
                g.glfwWindowHintString(0x00024001, b"MP_Visualizer")
                g.glfwWindowHintString(0x00024002, b"mp_visualizer")
            except Exception: pass

        w = g.glfwCreateWindow(WINDOW_WIDTH, WINDOW_HEIGHT, self.title.encode("utf-8"), None, None)
        if not w: raise RuntimeError("GLFW could not open a 1400x1400 borderless window for Vulkan")
        if hasattr(g, "glfwSetWindowAttrib"):
            try: g.glfwSetWindowAttrib(w, GLFW_AUTO_ICONIFY, GLFW_FALSE)
            except Exception: pass
        try: g.glfwSetWindowSizeLimits(w, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT)
        except Exception: pass

        ix, iy = 160, 80
        if getattr(self, "target_4k", False):
            m4k = self._find_4k_monitor()
            if m4k:
                mx, my = c_int(), c_int()
                g.glfwGetMonitorPos(m4k, byref(mx), byref(my))
                ix, iy = mx.value, my.value
        g.glfwSetWindowPos(w, ix, iy)
        self._cur_pos = (ix, iy)
        return w

    def _bind_input(self):
        self._on_key_cb = CFUNCTYPE(None, VP, c_int, c_int, c_int, c_int)(self._on_key)
        self._on_mouse_cb = CFUNCTYPE(None, VP, c_int, c_int, c_int)(self._on_mouse)
        self._on_cursor_cb = CFUNCTYPE(None, VP, c_double, c_double)(self._on_cursor)
        self._on_fb_cb = CFUNCTYPE(None, VP, c_int, c_int)(self._on_fb)
        self._on_pos_cb = CFUNCTYPE(None, VP, c_int, c_int)(self._on_pos)
        self._on_iconify_cb = CFUNCTYPE(None, VP, c_int)(self._on_iconify)

        g, w = self._glfw, self._window
        g.glfwSetKeyCallback(w, cast(self._on_key_cb, VP))
        g.glfwSetMouseButtonCallback(w, cast(self._on_mouse_cb, VP))
        g.glfwSetCursorPosCallback(w, cast(self._on_cursor_cb, VP))
        g.glfwSetFramebufferSizeCallback(w, cast(self._on_fb_cb, VP))
        g.glfwSetWindowPosCallback(w, cast(self._on_pos_cb, VP))
        if hasattr(g, "glfwSetWindowIconifyCallback"):
            g.glfwSetWindowIconifyCallback(w, cast(self._on_iconify_cb, VP))
        self._is_4k_cached = self.is_4k_display()

    def _on_iconify(self, _w, iconified):
        if iconified and self.is_fullscreen and hasattr(self._glfw, "glfwRestoreWindow"):
            try: self._glfw.glfwRestoreWindow(self._window)
            except Exception: pass

    def _on_key(self, _w, key, _sc, action, _mods):
        if action != GLFW_PRESS: return
        if key in (GLFW_KEY_ESCAPE, GLFW_KEY_Q): self.request_close()
        elif key == GLFW_KEY_Z: self.toggle_fullscreen()
        elif key == 75 and (_mods & 1):
            if _IS_WIN:
                subprocess.run('taskkill /F /FI "WINDOWTITLE eq MP Audio Player*" >nul 2>&1', shell=True)
                subprocess.run('powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like \'*MP_Audio_Player*\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1', shell=True)
            else:
                subprocess.run('pkill -9 -f "MP_Audio_Player"', shell=True)
        elif GLFW_KEY_1 <= key <= GLFW_KEY_9:
            idx = key - GLFW_KEY_1
            if 0 <= idx < len(VISUALIZER_PRESETS): self.switch_preset(VISUALIZER_PRESETS[idx])

    def is_4k_display(self, mon=None) -> bool:
        g = getattr(self, "_glfw", None)
        if not g: return False
        mon = mon or self._current_monitor()
        if not mon: return False
        try:
            mp = g.glfwGetVideoMode(mon)
            if mp and (mp.contents.width >= FOUR_K_MIN_WIDTH or mp.contents.height >= FOUR_K_MIN_HEIGHT): return True
            if hasattr(g, "glfwGetMonitorName"):
                nb = g.glfwGetMonitorName(mon)
                if nb and any(k in nb.decode("utf-8", errors="ignore").lower() for k in ("4k", "uhd", "hisense")): return True
        except Exception: pass
        return False

    def _find_4k_monitor(self):
        g = getattr(self, "_glfw", None)
        if not g: return None
        try:
            c = c_int()
            mons = g.glfwGetMonitors(byref(c))
            if mons and c.value > 0:
                for i in range(c.value):
                    if self.is_4k_display(mons[i]): return mons[i]
        except Exception: pass
        return None

    def _current_monitor(self):
        if not getattr(self, "_window", None) or not getattr(self, "_glfw", None): return None
        g = self._glfw
        mon = g.glfwGetPrimaryMonitor()
        try:
            wx, wy = self._cur_pos
            ww, wh = self.width, self.height
            c = c_int()
            mons = g.glfwGetMonitors(byref(c))
            if mons and c.value > 0:
                ba, bm, mx, my = -1, None, c_int(), c_int()
                for i in range(c.value):
                    m = mons[i]
                    g.glfwGetMonitorPos(m, byref(mx), byref(my))
                    mp = g.glfwGetVideoMode(m)
                    if mp:
                        md = mp.contents
                        area = max(0, min(wx + ww, mx.value + md.width) - max(wx, mx.value)) * max(0, min(wy + wh, my.value + md.height) - max(wy, my.value))
                        if area > ba: ba, bm = area, m
                if bm and ba > 0: return bm
        except Exception: pass
        return mon

    def toggle_fullscreen(self) -> bool:
        if not getattr(self, "_window", None) or not getattr(self, "_glfw", None):
            self.is_fullscreen = not self.is_fullscreen
            self.width, self.height = (RENDER_1080P_WIDTH, RENDER_1080P_HEIGHT) if self.is_fullscreen else (WINDOW_WIDTH, WINDOW_HEIGHT)
            return self.is_fullscreen

        g, w = self._glfw, self._window
        self._drag_active = False
        if not self.is_fullscreen:
            self._saved_window_pos = self.window_pos()
            mon = self._current_monitor()
            fw, fh, ref = RENDER_1080P_WIDTH, RENDER_1080P_HEIGHT, 60
            if mon:
                mp = g.glfwGetVideoMode(mon)
                if mp:
                    md = mp.contents
                    if not (self.is_4k_display(mon) or md.width >= FOUR_K_MIN_WIDTH or md.height >= FOUR_K_MIN_HEIGHT) and md.width > 0 and md.height > 0:
                        fw, fh = int(md.width), int(md.height)
                    if md.refreshRate > 0: ref = int(md.refreshRate)
            self.is_fullscreen, self._user_toggled_windowed = True, False
            self.width, self.height = fw, fh
            try: g.glfwSetWindowSizeLimits(w, GLFW_DONT_CARE, GLFW_DONT_CARE, GLFW_DONT_CARE, GLFW_DONT_CARE)
            except Exception: pass
            if mon: g.glfwSetWindowMonitor(w, mon, 0, 0, fw, fh, ref)
            else:
                g.glfwSetWindowPos(w, 0, 0)
                g.glfwSetWindowSize(w, fw, fh)
            if hasattr(g, "glfwSetWindowAttrib"):
                try:
                    g.glfwSetWindowAttrib(w, GLFW_AUTO_ICONIFY, GLFW_FALSE)
                    g.glfwSetWindowAttrib(w, GLFW_FLOATING, GLFW_TRUE)
                except Exception: pass
            self._resize = True
        else:
            rx, ry = getattr(self, "_saved_window_pos", (160, 80))
            self.is_fullscreen, self._user_toggled_windowed = False, True
            self.width, self.height = WINDOW_WIDTH, WINDOW_HEIGHT
            if hasattr(g, "glfwSetWindowAttrib"):
                try: g.glfwSetWindowAttrib(w, GLFW_FLOATING, GLFW_FALSE)
                except Exception: pass
            g.glfwSetWindowMonitor(w, None, int(rx), int(ry), WINDOW_WIDTH, WINDOW_HEIGHT, 0)
            try: g.glfwSetWindowSizeLimits(w, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT)
            except Exception: pass
            g.glfwSetWindowSize(w, WINDOW_WIDTH, WINDOW_HEIGHT)
            g.glfwSetWindowPos(w, int(rx), int(ry))
            self._cur_pos = (int(rx), int(ry))
            self._resize = True
            try: g.glfwPollEvents()
            except Exception: pass
        self._is_4k_cached = self.is_4k_display()
        return self.is_fullscreen

    def _on_mouse(self, _w, button, action, _mods):
        if button == 0:
            self.mouse_down = action == GLFW_PRESS
            if self.mouse_down and not self.is_fullscreen:
                self._drag_active = True
                self._drag_origin = self.window_pos()
                rx, ry = self.root_pointer()
                self._drag_press_screen = (rx, ry) if (rx or ry) else (int(self._drag_origin[0] + self.cursor[0]), int(self._drag_origin[1] + self.cursor[1]))
            else:
                self._drag_active = False

    def _on_cursor(self, _w, x, y):
        self.cursor = (float(x), float(y))
        if self._drag_active and self.mouse_down and not self.is_fullscreen:
            rx, ry = self.root_pointer()
            if rx or ry:
                self.set_window_pos(int(self._drag_origin[0] + (rx - self._drag_press_screen[0])), int(self._drag_origin[1] + (ry - self._drag_press_screen[1])))

    def _on_fb(self, _w, _fw, _fh): self._resize = True

    def _on_pos(self, _w, x, y):
        self._cur_pos = (int(x), int(y))
        cm = self._current_monitor()
        if cm != getattr(self, "_last_monitor", None):
            self._last_monitor = cm
            self._is_4k_cached = self.is_4k_display(cm)
            if self._is_4k_cached: self._user_toggled_windowed = False

    def root_pointer(self) -> Tuple[int, int]:
        if _IS_WIN:
            try:
                pt = _WinPOINT()
                if ctypes.windll.user32.GetCursorPos(byref(pt)): return int(pt.x), int(pt.y)
            except Exception: pass
            return self.window_pos()
        if not _IS_MAC:
            d = self.x11_display()
            if d and getattr(self, "_x11", None):
                try:
                    r, c, rx, ry, wx, wy, m = U64(), U64(), c_int(), c_int(), c_int(), c_int(), U32()
                    if self._x11.XQueryPointer(d, self._x11.XDefaultRootWindow(d), byref(r), byref(c), byref(rx), byref(ry), byref(wx), byref(wy), byref(m)):
                        return int(rx.value), int(ry.value)
                except Exception: pass
        try:
            wx, wy = self.window_pos()
            return int(wx + self.cursor[0]), int(wy + self.cursor[1])
        except Exception:
            return self.window_pos()

    def window_size(self) -> Tuple[int, int]:
        w, h = c_int(), c_int()
        self._glfw.glfwGetWindowSize(self._window, byref(w), byref(h))
        if not self.is_fullscreen: return WINDOW_WIDTH, WINDOW_HEIGHT
        if self._is_4k_cached or w.value >= FOUR_K_MIN_WIDTH or h.value >= FOUR_K_MIN_HEIGHT:
            return RENDER_1080P_WIDTH, RENDER_1080P_HEIGHT
        return int(w.value), int(h.value)

    def framebuffer_size(self) -> Tuple[int, int]:
        w, h = c_int(), c_int()
        self._glfw.glfwGetFramebufferSize(self._window, byref(w), byref(h))
        if not self.is_fullscreen: return max(1, int(w.value)), max(1, int(h.value))
        if self._is_4k_cached or w.value >= FOUR_K_MIN_WIDTH or h.value >= FOUR_K_MIN_HEIGHT:
            return RENDER_1080P_WIDTH, RENDER_1080P_HEIGHT
        return max(1, int(w.value)), max(1, int(h.value))

    def window_pos(self) -> Tuple[int, int]:
        if getattr(self, "_window", None) and getattr(self, "_glfw", None):
            try:
                x, y = c_int(), c_int()
                self._glfw.glfwGetWindowPos(self._window, byref(x), byref(y))
                self._cur_pos = (int(x.value), int(y.value))
            except Exception: pass
        return self._cur_pos

    def set_window_pos(self, x: int, y: int):
        self._cur_pos = (int(x), int(y))
        self._glfw.glfwSetWindowPos(self._window, int(x), int(y))

    def request_close(self):
        self.should_close = True
        if getattr(self, "_window", None): self._glfw.glfwSetWindowShouldClose(self._window, 1)

    def poll(self) -> bool:
        g, w = self._glfw, self._window
        g.glfwPollEvents()
        if g.glfwWindowShouldClose(w): self.should_close = True
        if not self.is_fullscreen:
            if self._is_4k_cached and not getattr(self, "_user_toggled_windowed", False):
                self.toggle_fullscreen()
            else:
                ww, wh = c_int(), c_int()
                g.glfwGetWindowSize(w, byref(ww), byref(wh))
                if (ww.value, wh.value) != (WINDOW_WIDTH, WINDOW_HEIGHT):
                    g.glfwSetWindowSize(w, WINDOW_WIDTH, WINDOW_HEIGHT)
                    self._resize = True
                self.width, self.height = WINDOW_WIDTH, WINDOW_HEIGHT
        else:
            if hasattr(g, "glfwGetWindowAttrib") and hasattr(g, "glfwRestoreWindow"):
                try:
                    if g.glfwGetWindowAttrib(w, GLFW_ICONIFIED): g.glfwRestoreWindow(w)
                except Exception: pass
            ww, wh = self.window_size()
            if ww > 0 and wh > 0:
                self.width, self.height = (RENDER_1080P_WIDTH, RENDER_1080P_HEIGHT) if (self._is_4k_cached or ww >= FOUR_K_MIN_WIDTH or wh >= FOUR_K_MIN_HEIGHT) else (ww, wh)
        return not self.should_close

    def _bind_loader(self):
        v = self._vulkan
        v.vkGetInstanceProcAddr.restype, v.vkGetInstanceProcAddr.argtypes = VP, [VP, CP]
        v.vkGetDeviceProcAddr.restype, v.vkGetDeviceProcAddr.argtypes = VP, [VP, CP]
        v.vkCreateInstance.restype, v.vkCreateInstance.argtypes = I32, [VP, VP, POINTER(VP)]
        if hasattr(v, "vkEnumerateInstanceExtensionProperties"):
            v.vkEnumerateInstanceExtensionProperties.restype, v.vkEnumerateInstanceExtensionProperties.argtypes = I32, [CP, POINTER(U32), VP]

    def _create_instance(self):
        c = U32()
        ptr = self._glfw.glfwGetRequiredInstanceExtensions(byref(c))
        names = [ptr[i] for i in range(c.value)]

        avail = set()
        if hasattr(self._vulkan, "vkEnumerateInstanceExtensionProperties"):
            ec = U32(0)
            self._vulkan.vkEnumerateInstanceExtensionProperties(None, byref(ec), None)
            if ec.value > 0:
                ap = (_VkExtProp * ec.value)()
                self._vulkan.vkEnumerateInstanceExtensionProperties(None, byref(ec), ap)
                avail = {p.extensionName.split(b"\x00")[0] for p in ap}

        flags = 0
        if b"VK_KHR_portability_enumeration" in avail or _IS_MAC:
            if b"VK_KHR_portability_enumeration" not in names: names.append(b"VK_KHR_portability_enumeration")
            flags |= VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR
        if b"VK_KHR_get_physical_device_properties2" in avail and b"VK_KHR_get_physical_device_properties2" not in names:
            names.append(b"VK_KHR_get_physical_device_properties2")

        self._ext_names = names
        self._ext_arr = arr = (CP * len(names))(*names)
        self._app = app = VkApplicationInfo(ST_APPLICATION_INFO, None, b"MP Liquid Visualizer", _api_version(0, 4, 0), b"mp-liquid-visualizer-vulkan", 1, _api_version(1, 2, 0))
        self._instance_info = info = VkInstanceCreateInfo(ST_INSTANCE_CREATE_INFO, None, flags, _addr(app), 0, None, len(names), cast(arr, VP))
        inst = VP()
        _check(self._vulkan.vkCreateInstance(_addr(info), None, byref(inst)), "vkCreateInstance")
        self._instance = inst

    def _load_instance(self):
        g, inst, PU32 = self._vulkan.vkGetInstanceProcAddr, self._instance, POINTER(U32)
        self._i = type("I", (), {})()
        for attr, name, res, args in (
            ("DestroyInstance", "vkDestroyInstance", None, [VP, VP]),
            ("DestroySurfaceKHR", "vkDestroySurfaceKHR", None, [VP, U64, VP]),
            ("EnumeratePhysicalDevices", "vkEnumeratePhysicalDevices", I32, [VP, PU32, POINTER(VP)]),
            ("GetPhysicalDeviceProperties", "vkGetPhysicalDeviceProperties", None, [VP, VP]),
            ("GetPhysicalDeviceQueueFamilyProperties", "vkGetPhysicalDeviceQueueFamilyProperties", None, [VP, PU32, VP]),
            ("GetPhysicalDeviceMemoryProperties", "vkGetPhysicalDeviceMemoryProperties", None, [VP, VP]),
            ("GetSurfaceSupport", "vkGetPhysicalDeviceSurfaceSupportKHR", I32, [VP, U32, U64, PU32]),
            ("GetSurfaceCaps", "vkGetPhysicalDeviceSurfaceCapabilitiesKHR", I32, [VP, U64, VP]),
            ("GetSurfaceFormats", "vkGetPhysicalDeviceSurfaceFormatsKHR", I32, [VP, U64, PU32, VP]),
            ("GetSurfaceModes", "vkGetPhysicalDeviceSurfacePresentModesKHR", I32, [VP, U64, PU32, VP]),
            ("CreateDevice", "vkCreateDevice", I32, [VP, VP, VP, POINTER(VP)]),
            ("EnumerateDeviceExtensionProperties", "vkEnumerateDeviceExtensionProperties", I32, [VP, CP, PU32, VP]),
        ):
            setattr(self._i, attr, _load(g, inst, name, res, args))

    def _device_header(self, phys) -> Dict[str, Any]:
        buf = (c_uint8 * 16384)()
        self._i.GetPhysicalDeviceProperties(phys, buf)
        api, drv, ven, dev, dt = cast(buf, POINTER(U32 * 5)).contents
        return {"api": int(api), "driver": int(drv), "vendor_id": int(ven), "device_id": int(dev), "device_type": int(dt),
                "name": string_at(addressof(buf) + 20, 256).split(b"\0", 1)[0].decode("utf-8", "replace")}

    def _pick_device(self):
        c = U32()
        _check(self._i.EnumeratePhysicalDevices(self._instance, byref(c), None), "enumerate devices")
        if c.value == 0: raise RuntimeError("Vulkan reported no physical devices")
        raw = (VP * c.value)()
        _check(self._i.EnumeratePhysicalDevices(self._instance, byref(c), raw), "enumerate devices")
        hdrs = [self._device_header(raw[i]) for i in range(c.value)]
        idx = select_vulkan_device(hdrs)
        self._physical, ch = raw[idx], hdrs[idx]
        self.device_name, self.vendor_id, self.device_type = ch["name"], ch["vendor_id"], ch["device_type"]
        self._queue_family = self._present_family(self._physical)

    def _present_family(self, phys) -> int:
        c, sup = U32(), U32()
        self._i.GetPhysicalDeviceQueueFamilyProperties(phys, byref(c), None)
        props = (VkQueueFamilyProperties * c.value)()
        self._i.GetPhysicalDeviceQueueFamilyProperties(phys, byref(c), props)
        for i in range(c.value):
            if props[i].queueFlags & QUEUE_GRAPHICS:
                _check(self._i.GetSurfaceSupport(phys, i, self._surface, byref(sup)), "surface support")
                if sup.value: return i
        raise RuntimeError(f"{self.device_name} has no Vulkan graphics queue that can present")

    def _create_device(self):
        self._priority = prio = (F32 * 1)(1.0)
        self._queue_info = q = VkDeviceQueueCreateInfo(ST_DEVICE_QUEUE_CREATE_INFO, None, 0, self._queue_family, 1, cast(prio, VP))
        exts = [b"VK_KHR_swapchain"]
        if hasattr(self._i, "EnumerateDeviceExtensionProperties"):
            ec = U32(0)
            self._i.EnumerateDeviceExtensionProperties(self._physical, None, byref(ec), None)
            if ec.value > 0:
                ap = (_VkExtProp * ec.value)()
                self._i.EnumerateDeviceExtensionProperties(self._physical, None, byref(ec), ap)
                if b"VK_KHR_portability_subset" in {p.extensionName.split(b"\x00")[0] for p in ap}:
                    exts.append(b"VK_KHR_portability_subset")

        self._dev_ext = ext = (CP * len(exts))(*exts)
        self._device_info = info = VkDeviceCreateInfo(ST_DEVICE_CREATE_INFO, None, 0, 1, _addr(q), 0, None, len(exts), cast(ext, VP), None)
        dev = VP()
        _check(self._i.CreateDevice(self._physical, _addr(info), None, byref(dev)), "vkCreateDevice")
        self._device = dev

    def _load_device(self):
        g, dev, P, H, PH, PU32 = self._vulkan.vkGetDeviceProcAddr, self._device, VP, U64, POINTER(U64), POINTER(U32)
        self._vk = vk = type("D", (), {})()
        for attr, res, args in (
            ("GetDeviceQueue", None, [P, U32, U32, POINTER(P)]), ("DeviceWaitIdle", I32, [P]), ("DestroyDevice", None, [P, P]),
            ("CreateSwapchainKHR", I32, [P, P, P, PH]), ("DestroySwapchainKHR", None, [P, H, P]),
            ("GetSwapchainImagesKHR", I32, [P, H, PU32, PH]), ("CreateImage", I32, [P, P, P, PH]), ("DestroyImage", None, [P, H, P]),
            ("GetImageMemoryRequirements", None, [P, H, P]), ("BindImageMemory", I32, [P, H, H, U64]),
            ("CreateImageView", I32, [P, P, P, PH]), ("DestroyImageView", None, [P, H, P]),
            ("CreateSampler", I32, [P, P, P, PH]), ("DestroySampler", None, [P, H, P]),
            ("CreateRenderPass", I32, [P, P, P, PH]), ("DestroyRenderPass", None, [P, H, P]),
            ("CreateFramebuffer", I32, [P, P, P, PH]), ("DestroyFramebuffer", None, [P, H, P]),
            ("CreateShaderModule", I32, [P, P, P, PH]), ("DestroyShaderModule", None, [P, H, P]),
            ("CreatePipelineLayout", I32, [P, P, P, PH]), ("DestroyPipelineLayout", None, [P, H, P]),
            ("CreateGraphicsPipelines", I32, [P, H, U32, P, P, PH]), ("DestroyPipeline", None, [P, H, P]),
            ("CreateDescriptorSetLayout", I32, [P, P, P, PH]), ("DestroyDescriptorSetLayout", None, [P, H, P]),
            ("CreateDescriptorPool", I32, [P, P, P, PH]), ("DestroyDescriptorPool", None, [P, H, P]),
            ("AllocateDescriptorSets", I32, [P, P, PH]), ("UpdateDescriptorSets", None, [P, U32, P, U32, P]),
            ("CreateBuffer", I32, [P, P, P, PH]), ("DestroyBuffer", None, [P, H, P]),
            ("GetBufferMemoryRequirements", None, [P, H, P]), ("AllocateMemory", I32, [P, P, P, PH]),
            ("FreeMemory", None, [P, H, P]), ("BindBufferMemory", I32, [P, H, H, U64]),
            ("MapMemory", I32, [P, H, U64, U64, U32, POINTER(P)]), ("UnmapMemory", None, [P, H]),
            ("CreateCommandPool", I32, [P, P, P, PH]), ("DestroyCommandPool", None, [P, H, P]),
            ("AllocateCommandBuffers", I32, [P, P, POINTER(P)]), ("BeginCommandBuffer", I32, [P, P]),
            ("EndCommandBuffer", I32, [P]), ("ResetCommandBuffer", I32, [P, U32]),
            ("CmdBeginRenderPass", None, [P, P, U32]), ("CmdEndRenderPass", None, [P]),
            ("CmdBindPipeline", None, [P, U32, H]), ("CmdBindDescriptorSets", None, [P, U32, H, U32, U32, P, U32, P]),
            ("CmdDraw", None, [P, U32, U32, U32, U32]), ("CmdSetViewport", None, [P, U32, U32, P]),
            ("CmdSetScissor", None, [P, U32, U32, P]), ("CmdPipelineBarrier", None, [P, U32, U32, U32, U32, P, U32, P, U32, P]),
            ("CmdCopyBufferToImage", None, [P, H, H, U32, U32, P]), ("CmdCopyImageToBuffer", None, [P, H, U32, H, U32, P]),
            ("CreateSemaphore", I32, [P, P, P, PH]), ("DestroySemaphore", None, [P, H, P]),
            ("CreateFence", I32, [P, P, P, PH]), ("DestroyFence", None, [P, H, P]),
            ("WaitForFences", I32, [P, U32, P, U32, U64]), ("ResetFences", I32, [P, U32, P]),
            ("AcquireNextImageKHR", I32, [P, H, U64, H, H, PU32]), ("QueueSubmit", I32, [P, U32, P, H]),
            ("QueuePresentKHR", I32, [P, P]), ("QueueWaitIdle", I32, [P]),
        ):
            setattr(vk, attr, _load(g, dev, f"vk{attr}", res, args))
        q = VP()
        vk.GetDeviceQueue(self._device, self._queue_family, 0, byref(q))
        self._queue = q

    def _surface_choices(self):
        caps = VkSurfaceCapabilitiesKHR()
        _check(self._i.GetSurfaceCaps(self._physical, self._surface, _addr(caps)), "surface caps")
        c = U32()
        _check(self._i.GetSurfaceFormats(self._physical, self._surface, byref(c), None), "surface formats")
        fmts = (VkSurfaceFormatKHR * c.value)()
        _check(self._i.GetSurfaceFormats(self._physical, self._surface, byref(c), fmts), "surface formats")
        chosen = fmts[0]
        for w in (FORMAT_B8G8R8A8_UNORM, FORMAT_R8G8B8A8_UNORM, FORMAT_B8G8R8A8_SRGB):
            for f in fmts:
                if f.format == w: chosen = f; break
            else: continue
            break
        mn = U32()
        _check(self._i.GetSurfaceModes(self._physical, self._surface, byref(mn), None), "present modes")
        modes = (U32 * mn.value)()
        _check(self._i.GetSurfaceModes(self._physical, self._surface, byref(mn), modes), "present modes")
        return caps, chosen, PRESENT_FIFO if any(modes[i] == PRESENT_FIFO for i in range(mn.value)) else modes[0]

    def _create_swapchain(self, old=0):
        caps, fmt, present = self._surface_choices()
        self.format, self._colorspace = int(fmt.format), int(fmt.colorSpace)
        fw, fh = self.framebuffer_size()
        if caps.currentExtent.width != 0xFFFFFFFF and caps.currentExtent.width > 0:
            ext = (int(caps.currentExtent.width), int(caps.currentExtent.height))
        else:
            efw = min(fw, RENDER_1080P_WIDTH) if (self.is_fullscreen and self._is_4k_cached) else fw
            efh = min(fh, RENDER_1080P_HEIGHT) if (self.is_fullscreen and self._is_4k_cached) else fh
            ext = (min(max(efw, caps.minImageExtent.width), caps.maxImageExtent.width),
                   min(max(efh, caps.minImageExtent.height), caps.maxImageExtent.height))
        if ext[0] == 0 or ext[1] == 0: ext = (fw, fh)

        ic = max(caps.minImageCount, 3)
        if caps.maxImageCount: ic = min(ic, caps.maxImageCount)

        self._can_readback = bool(caps.supportedUsageFlags & IMAGE_USAGE_TRANSFER_SRC)
        usage = IMAGE_USAGE_COLOR | (IMAGE_USAGE_TRANSFER_SRC if self._can_readback else 0)

        ca = COMPOSITE_OPAQUE
        if not (caps.supportedCompositeAlpha & COMPOSITE_OPAQUE):
            for cand in (COMPOSITE_PRE_MULTIPLIED, COMPOSITE_POST_MULTIPLIED, COMPOSITE_INHERIT):
                if caps.supportedCompositeAlpha & cand: ca = cand; break

        self._swap_info = info = VkSwapchainCreateInfoKHR(
            ST_SWAPCHAIN_CREATE, None, 0, self._surface, ic, self.format, self._colorspace,
            VkExtent2D(ext[0], ext[1]), 1, usage, SHARING_EXCLUSIVE, 0, None,
            caps.currentTransform or TRANSFORM_IDENTITY, ca, present, 1, old
        )
        swap = U64()
        _check(self._vk.CreateSwapchainKHR(self._device, _addr(info), None, byref(swap)), "vkCreateSwapchainKHR")
        if old: self._vk.DestroySwapchainKHR(self._device, old, None)
        self._swapchain, self._extent = swap.value, ext

        c = U32()
        _check(self._vk.GetSwapchainImagesKHR(self._device, self._swapchain, byref(c), None), "swapchain images")
        imgs = (U64 * c.value)()
        _check(self._vk.GetSwapchainImagesKHR(self._device, self._swapchain, byref(c), imgs), "swapchain images")
        self._images = [int(imgs[i]) for i in range(c.value)]
        self._views, self._framebuffers = [], []

        for img in self._images:
            vi = VkImageViewCreateInfo(ST_IMAGE_VIEW_CREATE_INFO, None, 0, img, IMAGE_VIEW_2D, self.format, 0, 0, 0, 0, IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
            v = U64()
            _check(self._vk.CreateImageView(self._device, _addr(vi), None, byref(v)), "image view")
            self._views.append(v.value)

        if not getattr(self, "_render_pass", 0): self._create_render_pass()
        self._create_framebuffers()

    def _create_render_pass(self):
        att = VkAttachmentDescription(0, self.format, SAMPLE_1, LOAD_CLEAR, STORE_STORE, LOAD_DONT, STORE_DONT, LAYOUT_UNDEFINED, LAYOUT_PRESENT)
        ref = VkAttachmentReference(0, LAYOUT_COLOR)
        sub = VkSubpassDescription(0, 0, 0, None, 1, _addr(ref), None, None, 0, None)
        deps = (VkSubpassDependency * 2)(
            VkSubpassDependency(SUBPASS_EXTERNAL, 0, STAGE_COLOR_OUT, STAGE_COLOR_OUT, 0, ACCESS_COLOR_WRITE, 0),
            VkSubpassDependency(0, SUBPASS_EXTERNAL, STAGE_COLOR_OUT, STAGE_BOTTOM, ACCESS_COLOR_WRITE, 0, 0),
        )
        info = VkRenderPassCreateInfo(ST_RENDER_PASS, None, 0, 1, _addr(att), 1, _addr(sub), 2, cast(deps, VP))
        self._rp_keep = (att, ref, sub, deps, info)
        rp = U64()
        _check(self._vk.CreateRenderPass(self._device, _addr(info), None, byref(rp)), "render pass")
        self._render_pass = rp.value

    def _create_framebuffers(self):
        self._fb_keeps = []
        for view in self._views:
            vs = (U64 * 1)(view)
            info = VkFramebufferCreateInfo(ST_FRAMEBUFFER, None, 0, self._render_pass, 1, cast(vs, VP), self._extent[0], self._extent[1], 1)
            fb = U64()
            self._fb_keeps.append((vs, info))
            _check(self._vk.CreateFramebuffer(self._device, _addr(info), None, byref(fb)), "framebuffer")
            self._framebuffers.append(fb.value)

    def _destroy_swapchain_views(self):
        for fb in self._framebuffers: self._vk.DestroyFramebuffer(self._device, fb, None)
        for v in self._views: self._vk.DestroyImageView(self._device, v, None)
        self._framebuffers, self._views = [], []

    def _recreate_swapchain(self):
        self._vk.DeviceWaitIdle(self._device)
        self._destroy_swapchain_views()
        self._create_swapchain(self._swapchain)
        self._resize = False
        self._destroy_readback()
        if hasattr(self, "_hot_rp"): self._sync_hotloop_extent()

    def _memory_type(self, bits: int, flags: int) -> int:
        props = VkPhysicalDeviceMemoryProperties()
        self._i.GetPhysicalDeviceMemoryProperties(self._physical, _addr(props))
        for i in range(props.memoryTypeCount):
            if bits & (1 << i) and (props.memoryTypes[i].propertyFlags & flags) == flags: return i
        raise RuntimeError("No compatible Vulkan memory type found on device")

    def _create_buffer(self, size: int, usage: int, mem_flags: int = MEMORY_HOST_VISIBLE | MEMORY_HOST_COHERENT):
        info = VkBufferCreateInfo(ST_BUFFER_CREATE_INFO, None, 0, size, usage, SHARING_EXCLUSIVE, 0, None)
        buf, mem, req = U64(), U64(), VkMemoryRequirements()
        _check(self._vk.CreateBuffer(self._device, _addr(info), None, byref(buf)), "buffer")
        self._vk.GetBufferMemoryRequirements(self._device, buf.value, _addr(req))
        alloc = VkMemoryAllocateInfo(ST_MEMORY_ALLOCATE_INFO, None, req.size, self._memory_type(req.memoryTypeBits, mem_flags))
        _check(self._vk.AllocateMemory(self._device, _addr(alloc), None, byref(mem)), "memory")
        _check(self._vk.BindBufferMemory(self._device, buf.value, mem.value, 0), "bind memory")
        return buf.value, mem.value, int(req.size)

    def _create_commands(self):
        pi = VkCommandPoolCreateInfo(ST_COMMAND_POOL, None, CMD_POOL_RESET, self._queue_family)
        pool = U64()
        _check(self._vk.CreateCommandPool(self._device, _addr(pi), None, byref(pool)), "command pool")
        self._pool = pool.value

        self._cmd_alloc = alloc = VkCommandBufferAllocateInfo(ST_COMMAND_BUFFER_ALLOCATE, None, self._pool, 0, 2)
        self._cmd_keep = cmds = (VP * 2)()
        _check(self._vk.AllocateCommandBuffers(self._device, _addr(alloc), cmds), "command buffers")
        self._cmd = [cmds[0], cmds[1]]

        si, fi = VkSemaphoreCreateInfo(ST_SEMAPHORE_CREATE_INFO, None, 0), VkFenceCreateInfo(ST_FENCE_CREATE_INFO, None, FENCE_SIGNALED)
        self._sync_info = (si, fi)
        for _ in range(2):
            s1, s2, f = U64(), U64(), U64()
            _check(self._vk.CreateSemaphore(self._device, _addr(si), None, byref(s1)), "semaphore")
            _check(self._vk.CreateSemaphore(self._device, _addr(si), None, byref(s2)), "semaphore")
            _check(self._vk.CreateFence(self._device, _addr(fi), None, byref(f)), "fence")
            self._image_available.append(s1.value)
            self._render_finished.append(s2.value)
            self._fences.append(f.value)
        self._frame = 0

    def _submit_one_time_cmd(self, record_fn):
        vk = self._vk
        alloc = VkCommandBufferAllocateInfo(ST_COMMAND_BUFFER_ALLOCATE, None, self._pool, 0, 1)
        cmd = VP()
        _check(vk.AllocateCommandBuffers(self._device, _addr(alloc), byref(cmd)), "alloc one-time cmd")
        begin = VkCommandBufferBeginInfo(ST_COMMAND_BUFFER_BEGIN, None, CMD_ONE_TIME, None)
        _check(vk.BeginCommandBuffer(cmd, _addr(begin)), "begin one-time cmd")
        keep = record_fn(cmd)
        _check(vk.EndCommandBuffer(cmd), "end one-time cmd")
        sub = VkSubmitInfo(ST_SUBMIT_INFO, None, 0, None, None, 1, cast(byref(cmd), VP), 0, None)
        _check(vk.QueueSubmit(self._queue, 1, _addr(sub), 0), "submit one-time cmd")
        _check(vk.QueueWaitIdle(self._queue), "wait one-time cmd")
        return keep

    def _upload_cover_image(self):
        tw, th, rgba = load_preset_cover_rgba(self.preset, tex_size=1024)
        blen = len(rgba)
        sbuf, smem, _ = self._create_buffer(blen, BUFFER_USAGE_TRANSFER_SRC)
        ptr = VP()
        _check(self._vk.MapMemory(self._device, smem, 0, blen, 0, byref(ptr)), "map staging")
        memmove(ptr, rgba, blen)
        self._vk.UnmapMemory(self._device, smem)

        ii = VkImageCreateInfo(ST_IMAGE_CREATE_INFO, None, 0, IMAGE_TYPE_2D, FORMAT_R8G8B8A8_UNORM, VkExtent3D(tw, th, 1),
                               1, 1, SAMPLE_1, TILING_OPTIMAL, IMAGE_USAGE_TRANSFER_DST | IMAGE_USAGE_SAMPLED, SHARING_EXCLUSIVE, 0, None, LAYOUT_UNDEFINED)
        timg, tmem, req = U64(), U64(), VkMemoryRequirements()
        _check(self._vk.CreateImage(self._device, _addr(ii), None, byref(timg)), "create cover image")
        self._tex_image = timg.value

        self._vk.GetImageMemoryRequirements(self._device, self._tex_image, _addr(req))
        try: mt = self._memory_type(req.memoryTypeBits, MEMORY_DEVICE_LOCAL)
        except Exception: mt = self._memory_type(req.memoryTypeBits, 0)
        alloc = VkMemoryAllocateInfo(ST_MEMORY_ALLOCATE_INFO, None, req.size, mt)
        _check(self._vk.AllocateMemory(self._device, _addr(alloc), None, byref(tmem)), "alloc cover mem")
        self._tex_memory = tmem.value
        _check(self._vk.BindImageMemory(self._device, self._tex_image, self._tex_memory, 0), "bind cover mem")

        sr = VkImageSubresourceRange(IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
        def _rec(cmd):
            b1 = VkImageMemoryBarrier(ST_IMAGE_MEMORY_BARRIER, None, 0, ACCESS_TRANSFER_WRITE, LAYOUT_UNDEFINED, LAYOUT_TRANSFER_DST, QUEUE_FAMILY_IGNORED, QUEUE_FAMILY_IGNORED, self._tex_image, sr)
            self._vk.CmdPipelineBarrier(cmd, STAGE_TOP, STAGE_TRANSFER, 0, 0, None, 0, None, 1, _addr(b1))
            reg = VkBufferImageCopy(0, 0, 0, VkImageSubresourceLayers(IMAGE_ASPECT_COLOR, 0, 0, 1), VkOffset3D(0, 0, 0), VkExtent3D(tw, th, 1))
            self._vk.CmdCopyBufferToImage(cmd, sbuf, self._tex_image, LAYOUT_TRANSFER_DST, 1, _addr(reg))
            b2 = VkImageMemoryBarrier(ST_IMAGE_MEMORY_BARRIER, None, ACCESS_TRANSFER_WRITE, ACCESS_SHADER_READ, LAYOUT_TRANSFER_DST, LAYOUT_SHADER_READ_ONLY, QUEUE_FAMILY_IGNORED, QUEUE_FAMILY_IGNORED, self._tex_image, sr)
            self._vk.CmdPipelineBarrier(cmd, STAGE_TRANSFER, STAGE_FRAGMENT, 0, 0, None, 0, None, 1, _addr(b2))
            return (b1, reg, b2)

        self._submit_one_time_cmd(_rec)
        self._vk.DestroyBuffer(self._device, sbuf, None)
        self._vk.FreeMemory(self._device, smem, None)

        vi = VkImageViewCreateInfo(ST_IMAGE_VIEW_CREATE_INFO, None, 0, self._tex_image, IMAGE_VIEW_2D, FORMAT_R8G8B8A8_UNORM, 0, 0, 0, 0, IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
        tv = U64()
        _check(self._vk.CreateImageView(self._device, _addr(vi), None, byref(tv)), "cover image view")
        self._tex_view = tv.value

    def _create_cover_texture(self):
        self._upload_cover_image()
        si = VkSamplerCreateInfo(ST_SAMPLER_CREATE_INFO, None, 0, FILTER_LINEAR, FILTER_LINEAR, SAMPLER_MIPMAP_LINEAR,
                                 SAMPLER_ADDRESS_REPEAT, SAMPLER_ADDRESS_REPEAT, SAMPLER_ADDRESS_REPEAT, 0.0, 0, 1.0, 0, 0, 0.0, 1.0, 0, 0)
        samp = U64()
        _check(self._vk.CreateSampler(self._device, _addr(si), None, byref(samp)), "cover sampler")
        self._tex_sampler = samp.value

    def switch_preset(self, preset: Dict[str, Any]):
        if preset.get("id") == self.preset.get("id"): return
        self.preset = preset
        save_active_preset(self.preset["key"])
        if hasattr(self, "_device") and self._device and getattr(self, "_tex_sampler", 0):
            try:
                self._vk.QueueWaitIdle(self._queue)
                if getattr(self, "_tex_view", None): self._vk.DestroyImageView(self._device, self._tex_view, None); self._tex_view = None
                if getattr(self, "_tex_image", None): self._vk.DestroyImage(self._device, self._tex_image, None); self._tex_image = None
                if getattr(self, "_tex_memory", None): self._vk.FreeMemory(self._device, self._tex_memory, None); self._tex_memory = None
                self._upload_cover_image()
                ii = VkDescriptorImageInfo(self._tex_sampler, self._tex_view, LAYOUT_SHADER_READ_ONLY)
                w = VkWriteDescriptorSet(ST_WRITE_DESCRIPTOR_SET, None, self._dset, 1, 0, 1, DESCRIPTOR_COMBINED_IMAGE_SAMPLER, _addr(ii), None, None)
                self._desc_switch_keep = (ii, w)
                self._vk.UpdateDescriptorSets(self._device, 1, _addr(w), 0, None)
            except Exception as e:
                print(f"[LiquidVisualizer] Warning: failed to switch cover texture: {e}", file=sys.stderr)

    def _shader_module(self, path: Path) -> int:
        data = Path(path).read_bytes()
        if len(data) % 4: raise RuntimeError(f"{path} is not aligned SPIR-V")
        buf = (c_uint8 * len(data)).from_buffer_copy(data)
        info = VkShaderModuleCreateInfo(ST_SHADER_MODULE_CREATE_INFO, None, 0, len(data), cast(buf, VP))
        mod = U64()
        self._shader_keep = getattr(self, "_shader_keep", [])
        self._shader_keep.append((buf, info))
        _check(self._vk.CreateShaderModule(self._device, _addr(info), None, byref(mod)), f"shader {path.name}")
        return mod.value

    def _create_pipeline(self):
        vert = self._shader_module(SHADER_DIR / "mp_liquid_visualizer.vert.spv")
        frag = self._shader_module(SHADER_DIR / "mp_liquid_visualizer.frag.spv")
        self._modules = [vert, frag]

        stages = (VkPipelineShaderStageCreateInfo * 2)(
            VkPipelineShaderStageCreateInfo(ST_PIPELINE_SHADER_STAGE, None, 0, SHADER_VERTEX, vert, b"main", None),
            VkPipelineShaderStageCreateInfo(ST_PIPELINE_SHADER_STAGE, None, 0, SHADER_FRAGMENT, frag, b"main", None),
        )
        vertex = VkPipelineVertexInputStateCreateInfo(ST_PIPELINE_VERTEX_INPUT, None, 0, 0, None, 0, None)
        assembly = VkPipelineInputAssemblyStateCreateInfo(ST_PIPELINE_INPUT_ASSEMBLY, None, 0, TOPOLOGY_TRIANGLE_LIST, 0)
        vp = VkViewport(0, 0, float(self._extent[0]), float(self._extent[1]), 0.0, 1.0)
        sc = VkRect2D(VkOffset2D(0, 0), VkExtent2D(self._extent[0], self._extent[1]))
        viewport = VkPipelineViewportStateCreateInfo(ST_PIPELINE_VIEWPORT, None, 0, 1, _addr(vp), 1, _addr(sc))
        raster = VkPipelineRasterizationStateCreateInfo(ST_PIPELINE_RASTER, None, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 1.0)
        multi = VkPipelineMultisampleStateCreateInfo(ST_PIPELINE_MULTISAMPLE, None, 0, SAMPLE_1, 0, 0.0, None, 0, 0)
        blend_att = VkPipelineColorBlendAttachmentState(0, 0, 0, 0, 0, 0, 0, COLOR_WRITE_ALL)
        blend = VkPipelineColorBlendStateCreateInfo(ST_PIPELINE_COLOR_BLEND, None, 0, 0, 0, 1, _addr(blend_att), (F32 * 4)(0, 0, 0, 0))
        dynamics = (U32 * 2)(DYNAMIC_VIEWPORT, DYNAMIC_SCISSOR)
        dynamic = VkPipelineDynamicStateCreateInfo(ST_PIPELINE_DYNAMIC, None, 0, 2, cast(dynamics, VP))

        bindings = (VkDescriptorSetLayoutBinding * 2)(
            VkDescriptorSetLayoutBinding(0, DESCRIPTOR_UNIFORM, 1, STAGE_VERTEX_BIT | STAGE_FRAGMENT_BIT, None),
            VkDescriptorSetLayoutBinding(1, DESCRIPTOR_COMBINED_IMAGE_SAMPLER, 1, STAGE_FRAGMENT_BIT, None),
        )
        set_info = VkDescriptorSetLayoutCreateInfo(ST_DESCRIPTOR_SET_LAYOUT, None, 0, 2, cast(bindings, VP))
        dl, layout, pipeline = U64(), U64(), U64()
        _check(self._vk.CreateDescriptorSetLayout(self._device, _addr(set_info), None, byref(dl)), "descriptor layout")
        self._desc_layout = dl.value

        layouts = (U64 * 1)(self._desc_layout)
        pli = VkPipelineLayoutCreateInfo(ST_PIPELINE_LAYOUT, None, 0, 1, cast(layouts, VP), 0, None)
        _check(self._vk.CreatePipelineLayout(self._device, _addr(pli), None, byref(layout)), "pipeline layout")
        self._layout = layout.value

        gp = VkGraphicsPipelineCreateInfo(
            ST_GRAPHICS_PIPELINE, None, 0, 2, cast(stages, VP), _addr(vertex), _addr(assembly), None,
            _addr(viewport), _addr(raster), _addr(multi), None, _addr(blend), _addr(dynamic),
            self._layout, self._render_pass, 0, 0, -1
        )
        self._pipe_keep = (stages, vertex, assembly, vp, sc, viewport, raster, multi, blend_att, blend, dynamics, dynamic, bindings, set_info, layouts, pli, gp)
        _check(self._vk.CreateGraphicsPipelines(self._device, 0, 1, _addr(gp), None, byref(pipeline)), "graphics pipeline")
        self._pipeline = pipeline.value

    def _create_descriptors(self):
        us = sizeof(VisualizerUBO)
        self._ubo, self._ubo_memory, _ = self._create_buffer(us, BUFFER_USAGE_UNIFORM)
        ptr = VP()
        _check(self._vk.MapMemory(self._device, self._ubo_memory, 0, us, 0, byref(ptr)), "map ubo")
        self._ubo_ptr = ptr

        ps = (VkDescriptorPoolSize * 2)(VkDescriptorPoolSize(DESCRIPTOR_UNIFORM, 1), VkDescriptorPoolSize(DESCRIPTOR_COMBINED_IMAGE_SAMPLER, 1))
        pi = VkDescriptorPoolCreateInfo(ST_DESCRIPTOR_POOL, None, 0, 1, 2, cast(ps, VP))
        pool, dset = U64(), U64()
        _check(self._vk.CreateDescriptorPool(self._device, _addr(pi), None, byref(pool)), "descriptor pool")
        self._desc_pool = pool.value

        layouts = (U64 * 1)(self._desc_layout)
        ai = VkDescriptorSetAllocateInfo(ST_DESCRIPTOR_SET_ALLOCATE, None, self._desc_pool, 1, cast(layouts, VP))
        self._desc_keep = (ps, pi, layouts, ai)
        _check(self._vk.AllocateDescriptorSets(self._device, _addr(ai), byref(dset)), "descriptor set")
        self._dset = dset.value

        bi = VkDescriptorBufferInfo(self._ubo, 0, us)
        ii = VkDescriptorImageInfo(self._tex_sampler, self._tex_view, LAYOUT_SHADER_READ_ONLY)
        writes = (VkWriteDescriptorSet * 2)(
            VkWriteDescriptorSet(ST_WRITE_DESCRIPTOR_SET, None, self._dset, 0, 0, 1, DESCRIPTOR_UNIFORM, None, _addr(bi), None),
            VkWriteDescriptorSet(ST_WRITE_DESCRIPTOR_SET, None, self._dset, 1, 0, 1, DESCRIPTOR_COMBINED_IMAGE_SAMPLER, _addr(ii), None, None),
        )
        self._write_keep = (bi, ii, writes)
        self._vk.UpdateDescriptorSets(self._device, 2, cast(writes, VP), 0, None)

    def _init_hotloop_structs(self):
        self._ubo_size = sizeof(VisualizerUBO)
        self._hot_begin = VkCommandBufferBeginInfo(ST_COMMAND_BUFFER_BEGIN, None, CMD_ONE_TIME, None)
        self._hot_begin_ptr = _addr(self._hot_begin)

        self._hot_barrier = VkBufferMemoryBarrier(ST_BUFFER_MEMORY_BARRIER, None, ACCESS_HOST_WRITE, ACCESS_UNIFORM, QUEUE_FAMILY_IGNORED, QUEUE_FAMILY_IGNORED, self._ubo, 0, self._ubo_size)
        self._hot_barrier_ptr = _addr(self._hot_barrier)

        self._hot_clear = VkClearValue((F32 * 4)(0.0, 0.0, 0.0, 1.0))
        self._hot_rp = VkRenderPassBeginInfo(ST_RENDER_PASS_BEGIN, None, self._render_pass, 0, VkRect2D(VkOffset2D(0, 0), VkExtent2D(*self._extent)), 1, _addr(self._hot_clear))
        self._hot_rp_ptr = _addr(self._hot_rp)

        self._hot_view = VkViewport(0.0, 0.0, float(self._extent[0]), float(self._extent[1]), 0.0, 1.0)
        self._hot_view_ptr = VP(addressof(self._hot_view))
        self._hot_scissor = VkRect2D(VkOffset2D(0, 0), VkExtent2D(*self._extent))
        self._hot_scissor_ptr = VP(addressof(self._hot_scissor))

        self._hot_dset = U64(self._dset)
        self._hot_dset_ptr = cast(byref(self._hot_dset), VP)

        self._hot_fences = [U64(f) for f in self._fences]
        self._hot_fence_ptrs = [byref(f) for f in self._hot_fences]
        self._hot_wait_sems = [U64(s) for s in self._image_available]
        self._hot_sig_sems = [U64(s) for s in self._render_finished]
        self._hot_wait_stage = U32(STAGE_COLOR_OUT)
        self._hot_cmd_keeps = [VP(c) for c in self._cmd]

        self._hot_submits, self._hot_submit_ptrs = [], []
        self._hot_index = U32()
        self._hot_index_ptr = byref(self._hot_index)
        self._hot_swap = U64(self._swapchain)
        self._hot_presents, self._hot_present_ptrs = [], []
        for i in range(2):
            sub = VkSubmitInfo(ST_SUBMIT_INFO, None, 1, cast(byref(self._hot_wait_sems[i]), VP), cast(byref(self._hot_wait_stage), VP), 1, cast(byref(self._hot_cmd_keeps[i]), VP), 1, cast(byref(self._hot_sig_sems[i]), VP))
            self._hot_submits.append(sub)
            self._hot_submit_ptrs.append(_addr(sub))
            pr = VkPresentInfoKHR(ST_PRESENT_INFO, None, 1, cast(byref(self._hot_sig_sems[i]), VP), 1, cast(byref(self._hot_swap), VP), cast(self._hot_index_ptr, VP), None)
            self._hot_presents.append(pr)
            self._hot_present_ptrs.append(_addr(pr))

        vk = self._vk
        self._fn_wait_fences, self._fn_acquire, self._fn_reset_fences = vk.WaitForFences, vk.AcquireNextImageKHR, vk.ResetFences
        self._fn_reset_cmd, self._fn_begin_cmd, self._fn_end_cmd = vk.ResetCommandBuffer, vk.BeginCommandBuffer, vk.EndCommandBuffer
        self._fn_barrier, self._fn_begin_rp, self._fn_end_rp = vk.CmdPipelineBarrier, vk.CmdBeginRenderPass, vk.CmdEndRenderPass
        self._fn_bind_pipe, self._fn_set_vp, self._fn_set_sc = vk.CmdBindPipeline, vk.CmdSetViewport, vk.CmdSetScissor
        self._fn_bind_ds, self._fn_draw, self._fn_submit, self._fn_present = vk.CmdBindDescriptorSets, vk.CmdDraw, vk.QueueSubmit, vk.QueuePresentKHR

    def _sync_hotloop_extent(self):
        ew, eh = self._extent
        self._hot_rp.renderArea.extent.width, self._hot_rp.renderArea.extent.height = ew, eh
        self._hot_view.width, self._hot_view.height = float(ew), float(eh)
        self._hot_scissor.extent.width, self._hot_scissor.extent.height = ew, eh
        self._hot_swap.value = self._swapchain

    def _write_ubo(self, bridge: AudioTelemetryBridge, _mm=memmove):
        fw, fh = self._extent
        if self._is_4k_cached or fw >= FOUR_K_MIN_WIDTH or fh >= FOUR_K_MIN_HEIGHT:
            rw, rh = float(min(fw, RENDER_1080P_WIDTH)), float(min(fh, RENDER_1080P_HEIGHT))
        else:
            rw, rh = float(fw), float(fh)
        u = self._ubo_flat
        u[0], u[1], u[2], u[3] = rw, rh, bridge.accum_time, 1.0 if bridge.is_playing else 0.0
        u[4], u[5], u[6], u[7] = bridge.sub_bass, bridge.bass, bridge.low_mid, bridge.mid
        u[8], u[9], u[10], u[11] = bridge.high_mid, bridge.treble, bridge.air, bridge.rms_energy
        u[12], u[13], u[14], u[15] = bridge.beat_pulse, bridge.bass_phase, bridge.mid_phase, bridge.high_phase
        u[16:32] = bridge.bands16
        u[32], u[33], u[34], u[35] = float(self.preset["id"]), bridge.pitch_factor, 1.0, getattr(bridge, "dynamic_time", bridge.accum_time)
        _mm(self._ubo_ptr, self._ubo_flat_ptr, self._ubo_size)

    def draw(self, bridge: AudioTelemetryBridge, capture: bool = False):
        if not self.poll(): return None
        fw, fh = self.framebuffer_size()
        if fw < 2 or fh < 2: return None
        if self._resize or (fw, fh) != self._extent: self._recreate_swapchain()
        self._write_ubo(bridge)
        return self._render(capture)

    def _render(self, capture: bool):
        dev, frame = self._device, self._frame
        fence, fence_ptr = self._fences[frame], self._hot_fence_ptrs[frame]
        _check(self._fn_wait_fences(dev, 1, fence_ptr, 1, 2_000_000_000), "wait fence")

        acq = self._fn_acquire(dev, self._swapchain, 2_000_000_000, self._image_available[frame], 0, self._hot_index_ptr)
        if acq == OUT_OF_DATE:
            self._recreate_swapchain()
            return None
        if acq not in (SUCCESS, SUBOPTIMAL): _check(acq, "acquire")
        if acq == SUBOPTIMAL: self._resize = True

        _check(self._fn_reset_fences(dev, 1, fence_ptr), "reset fence")
        cmd = self._cmd[frame]
        _check(self._fn_reset_cmd(cmd, 0), "reset command")
        _check(self._fn_begin_cmd(cmd, self._hot_begin_ptr), "begin command")

        self._fn_barrier(cmd, STAGE_HOST, STAGE_FRAGMENT, 0, 0, None, 1, self._hot_barrier_ptr, 0, None)
        idx = self._hot_index.value
        self._hot_rp.framebuffer = self._framebuffers[idx]
        self._fn_begin_rp(cmd, self._hot_rp_ptr, 0)
        self._fn_bind_pipe(cmd, 0, self._pipeline)
        self._fn_set_vp(cmd, 0, 1, self._hot_view_ptr)
        self._fn_set_sc(cmd, 0, 1, self._hot_scissor_ptr)
        self._fn_bind_ds(cmd, 0, self._layout, 0, 1, self._hot_dset_ptr, 0, None)
        self._fn_draw(cmd, 3, 1, 0, 0)
        self._fn_end_rp(cmd)
        _check(self._fn_end_cmd(cmd), "end command")

        _check(self._fn_submit(self._queue, 1, self._hot_submit_ptrs[frame], fence), "queue submit")

        pixels = None
        if capture and self._can_readback:
            _check(self._fn_wait_fences(dev, 1, fence_ptr, 1, 2_000_000_000), "wait draw")
            pixels = self._read_image(self._images[idx])

        pres = self._fn_present(self._queue, self._hot_present_ptrs[frame])
        if pres in (OUT_OF_DATE, SUBOPTIMAL): self._resize = True
        elif pres != SUCCESS: _check(pres, "present")

        self._frame = (frame + 1) & 1
        return pixels

    def _ensure_readback(self):
        bc = self._extent[0] * self._extent[1] * 4
        if self._readback_buffer and self._readback_bytes >= bc: return
        self._destroy_readback()
        buf, mem, size = self._create_buffer(bc, BUFFER_USAGE_TRANSFER_DST)
        ptr = VP()
        _check(self._vk.MapMemory(self._device, mem, 0, size, 0, byref(ptr)), "map readback")
        self._readback_buffer, self._readback_memory, self._readback_ptr, self._readback_bytes = buf, mem, ptr, bc

    def _destroy_readback(self):
        if self._readback_memory:
            self._vk.UnmapMemory(self._device, self._readback_memory)
            self._vk.DestroyBuffer(self._device, self._readback_buffer, None)
            self._vk.FreeMemory(self._device, self._readback_memory, None)
        self._readback_buffer = self._readback_memory = self._readback_bytes = 0
        self._readback_ptr = None

    def _read_image(self, image: int):
        self._ensure_readback()
        sr = VkImageSubresourceRange(IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
        def _rec(cmd):
            b1 = VkImageMemoryBarrier(ST_IMAGE_MEMORY_BARRIER, None, ACCESS_MEMORY_READ, ACCESS_TRANSFER_READ, LAYOUT_PRESENT, LAYOUT_TRANSFER_SRC, QUEUE_FAMILY_IGNORED, QUEUE_FAMILY_IGNORED, image, sr)
            self._vk.CmdPipelineBarrier(cmd, STAGE_BOTTOM, STAGE_TRANSFER, 0, 0, None, 0, None, 1, _addr(b1))
            reg = VkBufferImageCopy(0, 0, 0, VkImageSubresourceLayers(IMAGE_ASPECT_COLOR, 0, 0, 1), VkOffset3D(0, 0, 0), VkExtent3D(self._extent[0], self._extent[1], 1))
            self._vk.CmdCopyImageToBuffer(cmd, image, LAYOUT_TRANSFER_SRC, self._readback_buffer, 1, _addr(reg))
            b2 = VkImageMemoryBarrier(ST_IMAGE_MEMORY_BARRIER, None, ACCESS_TRANSFER_READ, ACCESS_MEMORY_READ, LAYOUT_TRANSFER_SRC, LAYOUT_PRESENT, QUEUE_FAMILY_IGNORED, QUEUE_FAMILY_IGNORED, image, sr)
            self._vk.CmdPipelineBarrier(cmd, STAGE_TRANSFER, STAGE_BOTTOM, 0, 0, None, 0, None, 1, _addr(b2))
            return (b1, reg, b2)

        self._read_keep = self._submit_one_time_cmd(_rec)
        return self._extent[0], self._extent[1], string_at(self._readback_ptr, self._extent[0] * self._extent[1] * 4)

    def close(self):
        if not self._alive:
            self._destroy_window()
            return
        vk, dev = self._vk, self._device
        try: vk.DeviceWaitIdle(dev)
        except Exception: pass
        self._destroy_readback()
        if self._tex_sampler: vk.DestroySampler(dev, self._tex_sampler, None)
        if self._tex_view: vk.DestroyImageView(dev, self._tex_view, None)
        if self._tex_image: vk.DestroyImage(dev, self._tex_image, None)
        if self._tex_memory: vk.FreeMemory(dev, self._tex_memory, None)
        for f in self._fences: vk.DestroyFence(dev, f, None)
        for s in self._image_available + self._render_finished: vk.DestroySemaphore(dev, s, None)
        if getattr(self, "_pool", 0): vk.DestroyCommandPool(dev, self._pool, None)
        self._destroy_swapchain_views()
        if getattr(self, "_pipeline", 0): vk.DestroyPipeline(dev, self._pipeline, None)
        if getattr(self, "_layout", 0): vk.DestroyPipelineLayout(dev, self._layout, None)
        if getattr(self, "_render_pass", 0): vk.DestroyRenderPass(dev, self._render_pass, None)
        if getattr(self, "_desc_pool", 0): vk.DestroyDescriptorPool(dev, self._desc_pool, None)
        if getattr(self, "_desc_layout", 0): vk.DestroyDescriptorSetLayout(dev, self._desc_layout, None)
        if getattr(self, "_ubo", 0):
            vk.UnmapMemory(dev, self._ubo_memory)
            vk.DestroyBuffer(dev, self._ubo, None)
        if getattr(self, "_ubo_memory", 0): vk.FreeMemory(dev, self._ubo_memory, None)
        for mod in getattr(self, "_modules", []): vk.DestroyShaderModule(dev, mod, None)
        if self._swapchain: vk.DestroySwapchainKHR(dev, self._swapchain, None)
        vk.DestroyDevice(dev, None)
        self._i.DestroySurfaceKHR(self._instance, self._surface, None)
        self._i.DestroyInstance(self._instance, None)
        self._alive = False
        self._destroy_window()

    def _destroy_window(self):
        if getattr(self, "_window", None) and getattr(self, "_glfw", None):
            self._glfw.glfwDestroyWindow(self._window)
            self._window = None
            self._glfw.glfwTerminate()


def save_png(path: Union[str, Path], width: int, height: int, bgra: bytes, swap_rb: bool = True):
    from PIL import Image
    if swap_rb:
        raw = bytearray(bgra)
        raw[0::4], raw[2::4] = raw[2::4], raw[0::4]
        bgra = bytes(raw)
    img = Image.frombytes("RGBA", (width, height), bgra)
    img.save(path)
    return img


def run_self_test(png_path: Optional[Union[str, Path]] = None, preset_name: Optional[str] = None) -> str:
    renderer = LiquidVisualizerVulkanRenderer(preset_name or get_active_preset()["name"])
    bridge = AudioTelemetryBridge()
    try:
        renderer.open()
        ww, wh = renderer.window_size()
        if (ww, wh) != (1400, 1400): raise RuntimeError(f"Expected fixed 1400x1400 window, got {ww}x{wh}")

        for _ in range(5):
            bridge.update(0.12, force_playing=True, synthetic_audio=True)
            renderer.draw(bridge, capture=False)
        t_playing = bridge.accum_time
        if t_playing <= 0.0: raise RuntimeError("accum_time did not advance while playing")

        bridge.update(0.50, force_playing=False, synthetic_audio=True)
        if bridge.accum_time != t_playing: raise RuntimeError("accum_time advanced while music was stopped/paused")

        bridge.update(0.15, force_playing=True, synthetic_audio=True)
        pixels = renderer.draw(bridge, capture=True)
        if not pixels: raise RuntimeError("Vulkan swapchain did not produce a readable 1400x1400 frame")
        w, h, bgra = pixels
        if (w, h) != (1400, 1400): raise RuntimeError(f"Expected 1400x1400 framebuffer, got {w}x{h}")

        if png_path:
            save_png(png_path, w, h, bgra, swap_rb=(renderer.format != FORMAT_R8G8B8A8_UNORM))

        print(f"MP_LIQUID_VISUALIZER_OK {renderer.summary}", flush=True)
        return renderer.summary
    finally:
        renderer.close()


def run_visualizer(preset_name: Optional[str] = None, max_seconds: Optional[float] = None, fullscreen: bool = False, target_4k: bool = False) -> int:
    renderer = LiquidVisualizerVulkanRenderer(preset_name, fullscreen=fullscreen, target_4k=target_4k)
    bridge = AudioTelemetryBridge()
    renderer.open()
    monotonic, sleep = time.monotonic, time.sleep
    last_t = start_t = monotonic()
    update, draw = bridge.update, renderer.draw
    try:
        while not renderer.should_close:
            now = monotonic()
            dt = now - last_t
            last_t = now
            if max_seconds is not None and (now - start_t) >= max_seconds: break
            update(dt)
            draw(bridge, False)
            sleep(0.008)
    except KeyboardInterrupt: pass
    finally: renderer.close()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="MP_Liquid_Visualizer", description="MP Liquid Visualizer — Native Vulkan 1400x1400 Borderless 3D Audio-Reactive Visualizer")
    p.add_argument("--preset", type=str, default=None, help="Select visualizer preset by name, key, or ID")
    p.add_argument("--random", "--random-preset", dest="random_preset", action="store_true", help="Launch with a random visualizer preset")
    p.add_argument("--set-preset", type=str, default=None, help="Persist active preset and exit")
    p.add_argument("--list-presets", action="store_true", help="List available visualizer presets and exit")
    p.add_argument("--fullscreen", "-fs", action="store_true", help="Launch visualizer in fullscreen mode (rendered at 1920x1080 on 4K)")
    p.add_argument("--4k", "--screen-4k", dest="target_4k", action="store_true", help="Launch visualizer on 4K display in fullscreen (rendered at 1920x1080)")
    p.add_argument("--screen", type=str, default=None, help="Target screen or monitor (e.g. '4k', 'hdmi', 'primary')")
    p.add_argument("--self-test", action="store_true", help="Run Vulkan 1400x1400 render & pause/play verification")
    p.add_argument("--png", type=str, default=None, help="Output PNG path when running --self-test")
    p.add_argument("--max-seconds", type=float, default=None, help="Optional maximum runtime in seconds")
    args = p.parse_args(argv)

    if args.random_preset: args.preset = "random"
    if args.list_presets:
        active = get_active_preset()
        for pr in VISUALIZER_PRESETS:
            print(f"[{'*' if pr['key'] == active['key'] else ' '}] {pr['id'] + 1}. {pr['name']} ({pr['key']}) — Cover: {pr['album']}")
        return 0
    if args.set_preset is not None:
        saved = save_active_preset(args.set_preset)
        print(f"Active Preset set to: {saved['name']} ({saved['key']})")
        return 0
    if args.preset is not None and args.preset.lower() not in _RAND_KEYS:
        save_active_preset(args.preset)
    if args.self_test:
        run_self_test(args.png)
        return 0

    target_4k = bool(args.target_4k) or bool(args.screen and any(k in args.screen.lower() for k in ("4k", "hdmi", "uhd", "hisense")))
    return run_visualizer(preset_name=args.preset, max_seconds=args.max_seconds, fullscreen=bool(args.fullscreen), target_4k=target_4k)

if __name__ == "__main__":
    raise SystemExit(main())