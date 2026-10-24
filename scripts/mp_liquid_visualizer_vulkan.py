#!/usr/bin/env python3
"""MP_Liquid_Visualizer — Native Vulkan 3D Audio-Reactive Visualizer Engine.

Built from the ground up in Vulkan for MP Mix Manager & MP Liquid Glass Audio Player.
First Preset: "Cosmic Dreamworlds (Liquid)"
Exclusively inspired by MPlanetarian - Cosmic Dreamworlds [Deluxe Edition] cover art
(https://mplanetarian.bandcamp.com/album/mplanetarian-cosmic-dreamworlds-deluxe-edition)
and procedural 3D architectural / liquid motion principles.

Window specifications:
- Fixed 1400x1400 dimensions (non-resizable)
- Borderless, no scrollbars
- Pure visualizer: zero text overlay ever displayed
- Continually generates 3D that connects and moves to currently playing music
- When music is paused or stopped, 3D generation freezes in-place and waits for Play
- User cannot alter how the visualizer looks; only preset selection is supported
- Pressing Escape or 'q' / 'Q' closes the window immediately
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import platform
import socket
import sys
import time
from ctypes import (
    CFUNCTYPE,
    POINTER,
    byref,
    c_char_p,
    c_double,
    c_float,
    c_int,
    c_int32,
    c_size_t,
    c_uint8,
    c_uint32,
    c_uint64,
    c_void_p,
)
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "shaders").is_dir() and (Path(__file__).resolve().parent / "shaders").is_dir():
    ROOT = Path(__file__).resolve().parent

SHADER_DIR = ROOT / "shaders"
ASSETS_DIR = ROOT / "assets"
COVERS_DIR = ROOT / "COVERS"
CONFIG_DIR = Path.home() / ".config" / "mix-manager"

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 1400

# Preset Registry (Each preset uses strictly ONE Bandcamp cover)
# Eventually ~5 presets; Preset 0 is the first one: Cosmic Dreamworlds (Liquid).
VISUALIZER_PRESETS: List[Dict[str, Any]] = [
    {
        "id": 0,
        "key": "cosmic_dreamworlds_liquid",
        "name": "Cosmic Dreamworlds (Liquid)",
        "album": "MPlanetarian - Cosmic Dreamworlds [Deluxe Edition]",
        "bandcamp_url": "https://mplanetarian.bandcamp.com/album/mplanetarian-cosmic-dreamworlds-deluxe-edition",
        "cover_paths": [
            ASSETS_DIR / "cosmic_dreamworlds_cover.jpg",
            COVERS_DIR / "Cosmic_Dreamworlds_Liquid_Preset.png",
        ],
    }
]


def is_windows() -> bool:
    return sys.platform == "win32" or platform.system().lower() == "windows"


def load_glfw_dll():
    if is_windows():
        candidates = ["glfw3.dll", "glfw.dll"]
        try:
            from ctypes.util import find_library
            for name in ("glfw3", "glfw"):
                f = find_library(name)
                if f and f not in candidates:
                    candidates.insert(0, f)
        except Exception:
            pass
        for cand in candidates:
            try:
                return ctypes.CDLL(cand)
            except OSError:
                continue
        raise RuntimeError("Could not load GLFW on Windows. Ensure glfw3.dll is in PATH.")
    return ctypes.CDLL("libglfw.so.3")


def load_vulkan_dll():
    if is_windows():
        candidates = ["vulkan-1.dll"]
        try:
            from ctypes.util import find_library
            for name in ("vulkan-1", "vulkan"):
                f = find_library(name)
                if f and f not in candidates:
                    candidates.insert(0, f)
        except Exception:
            pass
        for cand in candidates:
            try:
                return ctypes.CDLL(cand)
            except OSError:
                continue
        raise RuntimeError("Could not load Vulkan loader on Windows. Ensure vulkan-1.dll is installed.")
    return ctypes.CDLL("libvulkan.so.1")


def get_active_preset(preset_arg: Optional[str] = None) -> Dict[str, Any]:
    """Return the active visualizer preset dictionary."""
    target = str(preset_arg or "").strip().lower()
    if not target:
        preset_file = CONFIG_DIR / "visualizer_preset"
        if preset_file.is_file():
            try:
                target = preset_file.read_text(encoding="utf-8").strip().lower()
            except OSError:
                pass
    for p in VISUALIZER_PRESETS:
        if target in (str(p["id"]), p["key"].lower(), p["name"].lower()):
            return p
    return VISUALIZER_PRESETS[0]


def save_active_preset(preset_key_or_name: str) -> Dict[str, Any]:
    preset = get_active_preset(preset_key_or_name)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (CONFIG_DIR / "visualizer_preset").write_text(preset["key"], encoding="utf-8")
    except OSError:
        pass
    return preset


def load_preset_cover_rgba(preset: Dict[str, Any], tex_size: int = 1024) -> Tuple[int, int, bytes]:
    """Load the single Bandcamp cover image for the preset as RGBA8 bytes."""
    from PIL import Image

    for cpath in preset.get("cover_paths", []):
        p = Path(cpath)
        if p.is_file():
            with Image.open(p) as im:
                rgba = im.convert("RGBA").resize((tex_size, tex_size), Image.Resampling.LANCZOS)
                return tex_size, tex_size, rgba.tobytes()
    raise FileNotFoundError(f"Cover art file not found for preset '{preset.get('name')}'")


class AudioTelemetryBridge:
    """Real-time audio telemetry reader connected to MP Audio Player & Liquid Glass Player."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = Path(config_dir) if config_dir else CONFIG_DIR
        self.state_file = self.config_dir / "mp_player_state.json"
        self.socket_path = self.config_dir / "mp_audio_player.sock"
        self.port_file = self.config_dir / "mp_audio_player.port"

        self.is_playing: bool = False
        self.accum_time: float = 0.0
        self.bass_phase: float = 0.0
        self.mid_phase: float = 0.0
        self.high_phase: float = 0.0
        self.beat_pulse: float = 0.0
        self._prev_bass: float = 0.0
        self._last_poll: float = 0.0
        self._last_state_mtime_ns: int = 0
        self._cached_status: Dict[str, Any] = {}

        # Smoothed 16 spectrum bands
        self.bands16: List[float] = [0.0] * 16
        self.sub_bass: float = 0.0
        self.bass: float = 0.0
        self.low_mid: float = 0.0
        self.mid: float = 0.0
        self.high_mid: float = 0.0
        self.treble: float = 0.0
        self.air: float = 0.0
        self.rms_energy: float = 0.0
        self.pitch_factor: float = 1.0

    def _query_player_state(self) -> Dict[str, Any]:
        now = time.monotonic()
        state_changed = False
        if self.state_file.is_file():
            try:
                st_stat = self.state_file.stat()
                if st_stat.st_mtime_ns != self._last_state_mtime_ns:
                    state_changed = True
                    self._last_state_mtime_ns = st_stat.st_mtime_ns
            except OSError:
                pass

        if not state_changed and (now - self._last_poll < 0.025) and self._cached_status:
            return self._cached_status
        self._last_poll = now

        # Fast path: read atomic state file updated at 25Hz+ by MP_Audio_Player daemon
        if self.state_file.is_file():
            try:
                mtime = self.state_file.stat().st_mtime
                if time.time() - mtime < 3.0:
                    data = json.loads(self.state_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        self._cached_status = data
                        return data
            except Exception:
                pass

        # Fallback: direct non-blocking IPC socket query
        use_unix = hasattr(socket, "AF_UNIX") and self.socket_path.exists()
        if use_unix or self.port_file.exists():
            try:
                s = socket.socket(socket.AF_UNIX if use_unix else socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.05)
                if use_unix:
                    s.connect(str(self.socket_path))
                else:
                    s.connect(("127.0.0.1", int(self.port_file.read_text().strip())))
                s.sendall(b'{"cmd": "status"}')
                raw = s.recv(16384).decode("utf-8")
                s.close()
                if raw:
                    resp = json.loads(raw)
                    if isinstance(resp.get("data"), dict):
                        self._cached_status = resp["data"]
                        return self._cached_status
            except Exception:
                pass

        self._cached_status = {"running": False, "state": "stopped"}
        return self._cached_status

    def update(self, dt: float, force_playing: Optional[bool] = None, synthetic_audio: bool = False):
        """Advance audio-reactive state. Freezes completely if music is not playing."""
        dt = max(0.0, min(dt, 0.1))

        if synthetic_audio:
            self.is_playing = True if force_playing is None else bool(force_playing)
            if self.is_playing:
                self.accum_time += dt
                t = self.accum_time
                raw_bands = [
                    0.55 + 0.40 * math.sin(t * 3.2 + i * 0.45) ** 2 for i in range(16)
                ]
                self._apply_bands(raw_bands, rms=0.62, pitch=1.0, dt=dt)
            return

        st = self._query_player_state()
        playing = (
            bool(st.get("running", True))
            and str(st.get("state", "stopped")).lower() == "playing"
            and not bool(st.get("muted", False))
        )
        if force_playing is not None:
            playing = bool(force_playing)

        self.is_playing = playing
        if not self.is_playing:
            # Music is paused or stopped: freeze 3D generation in-place and wait for Play
            return

        # Music is actively playing: advance 3D generation clock and audio phases
        pitch = float(st.get("pitch_factor", 1.0) or 1.0)
        self.pitch_factor = max(0.5, min(1.5, pitch))
        self.accum_time += dt * self.pitch_factor

        levels = st.get("levels") or []
        rms = float(st.get("rms_level", 0.0) or 0.0)

        # Convert 24 player bands (or fallback waveform) into 16 normalized visualizer bands
        raw16 = [0.0] * 16
        if isinstance(levels, list) and len(levels) >= 8:
            n_lv = len(levels)
            for i in range(16):
                idx_f = (i / 15.0) * (n_lv - 1)
                i0 = int(math.floor(idx_f))
                i1 = min(n_lv - 1, i0 + 1)
                frac = idx_f - i0
                val = float(levels[i0]) * (1.0 - frac) + float(levels[i1]) * frac
                raw16[i] = max(0.0, min(1.0, val))
        else:
            # If track is playing but FFT array is momentarily flat, derive gentle groove from position
            pos = float(st.get("position_sec", self.accum_time) or self.accum_time)
            for i in range(16):
                raw16[i] = 0.25 + 0.20 * math.sin(pos * (2.5 + i * 0.3) + i) ** 2
            rms = max(rms, 0.28)

        self._apply_bands(raw16, rms=rms, pitch=self.pitch_factor, dt=dt)

    def _apply_bands(self, raw16: List[float], rms: float, pitch: float, dt: float):
        # Smooth attack / release per band
        for i in range(16):
            target = raw16[i]
            cur = self.bands16[i]
            coeff = 0.68 if target > cur else 0.22
            self.bands16[i] = cur + (target - cur) * coeff

        self.sub_bass = (self.bands16[0] + self.bands16[1]) * 0.5
        self.bass = (self.bands16[1] + self.bands16[2] + self.bands16[3]) / 3.0
        self.low_mid = (self.bands16[4] + self.bands16[5] + self.bands16[6]) / 3.0
        self.mid = (self.bands16[6] + self.bands16[7] + self.bands16[8] + self.bands16[9]) * 0.25
        self.high_mid = (self.bands16[10] + self.bands16[11] + self.bands16[12]) / 3.0
        self.treble = (self.bands16[12] + self.bands16[13] + self.bands16[14]) / 3.0
        self.air = self.bands16[15]
        self.rms_energy = max(0.0, min(1.0, rms * 2.2 + self.bass * 0.35))

        # Beat onset detection on bass derivative
        bass_delta = max(0.0, self.bass - self._prev_bass)
        self._prev_bass = self.bass
        if bass_delta > 0.065:
            self.beat_pulse = min(1.0, self.beat_pulse + bass_delta * 3.2)
        else:
            self.beat_pulse = max(0.0, self.beat_pulse - dt * 2.8)

        # Continuous phase accumulators that drive 3D structural articulation
        self.bass_phase += dt * (1.2 + self.sub_bass * 4.2 + self.beat_pulse * 2.0) * pitch
        self.mid_phase += dt * (1.0 + self.mid * 3.6) * pitch
        self.high_phase += dt * (0.9 + self.treble * 4.0) * pitch


# ==============================================================================
# Vulkan Constants & Ctypes Structures
# ==============================================================================
NVIDIA_VENDOR_ID = 0x10DE
DISCRETE_GPU = 2

ST_APPLICATION_INFO = 0
ST_INSTANCE_CREATE_INFO = 1
ST_DEVICE_QUEUE_CREATE_INFO = 2
ST_DEVICE_CREATE_INFO = 3
ST_SUBMIT_INFO = 4
ST_MEMORY_ALLOCATE_INFO = 5
ST_FENCE_CREATE_INFO = 8
ST_SEMAPHORE_CREATE_INFO = 9
ST_BUFFER_CREATE_INFO = 12
ST_IMAGE_CREATE_INFO = 14
ST_IMAGE_VIEW_CREATE_INFO = 15
ST_SHADER_MODULE_CREATE_INFO = 16
ST_PIPELINE_SHADER_STAGE = 18
ST_PIPELINE_VERTEX_INPUT = 19
ST_PIPELINE_INPUT_ASSEMBLY = 20
ST_PIPELINE_VIEWPORT = 22
ST_PIPELINE_RASTER = 23
ST_PIPELINE_MULTISAMPLE = 24
ST_PIPELINE_COLOR_BLEND = 26
ST_PIPELINE_DYNAMIC = 27
ST_GRAPHICS_PIPELINE = 28
ST_PIPELINE_LAYOUT = 30
ST_SAMPLER_CREATE_INFO = 31
ST_DESCRIPTOR_SET_LAYOUT = 32
ST_DESCRIPTOR_POOL = 33
ST_DESCRIPTOR_SET_ALLOCATE = 34
ST_WRITE_DESCRIPTOR_SET = 35
ST_FRAMEBUFFER = 37
ST_RENDER_PASS = 38
ST_COMMAND_POOL = 39
ST_COMMAND_BUFFER_ALLOCATE = 40
ST_COMMAND_BUFFER_BEGIN = 42
ST_RENDER_PASS_BEGIN = 43
ST_BUFFER_MEMORY_BARRIER = 44
ST_IMAGE_MEMORY_BARRIER = 45
ST_SWAPCHAIN_CREATE = 1000001000
ST_PRESENT_INFO = 1000001001

QUEUE_GRAPHICS = 0x1
IMAGE_USAGE_TRANSFER_SRC = 0x1
IMAGE_USAGE_TRANSFER_DST = 0x2
IMAGE_USAGE_SAMPLED = 0x4
IMAGE_USAGE_COLOR = 0x10
BUFFER_USAGE_TRANSFER_SRC = 0x1
BUFFER_USAGE_TRANSFER_DST = 0x2
BUFFER_USAGE_UNIFORM = 0x10

SHARING_EXCLUSIVE = 0
COMPOSITE_OPAQUE = 0x1
PRESENT_FIFO = 2
TRANSFORM_IDENTITY = 0x1
FORMAT_R8G8B8A8_UNORM = 37
FORMAT_B8G8R8A8_UNORM = 44
FORMAT_B8G8R8A8_SRGB = 50
IMAGE_TYPE_2D = 1
IMAGE_VIEW_2D = 1
IMAGE_ASPECT_COLOR = 0x1
SAMPLE_1 = 0x1
TILING_OPTIMAL = 0
LOAD_CLEAR = 1
STORE_STORE = 0
STORE_DONT = 1
LOAD_DONT = 2

LAYOUT_UNDEFINED = 0
LAYOUT_COLOR = 2
LAYOUT_SHADER_READ_ONLY = 5
LAYOUT_TRANSFER_SRC = 6
LAYOUT_TRANSFER_DST = 7
LAYOUT_PRESENT = 1000001002

SUBPASS_EXTERNAL = 0xFFFFFFFF
STAGE_TOP = 0x1
STAGE_VERTEX_BIT = 0x00000001
STAGE_FRAGMENT_BIT = 0x00000010
STAGE_FRAGMENT = 0x80
STAGE_COLOR_OUT = 0x400
STAGE_TRANSFER = 0x1000
STAGE_BOTTOM = 0x2000
STAGE_HOST = 0x4000

ACCESS_UNIFORM = 0x8
ACCESS_SHADER_READ = 0x20
ACCESS_COLOR_WRITE = 0x100
ACCESS_TRANSFER_READ = 0x800
ACCESS_TRANSFER_WRITE = 0x1000
ACCESS_HOST_WRITE = 0x4000
ACCESS_MEMORY_READ = 0x8000

CMD_POOL_RESET = 0x2
CMD_ONE_TIME = 0x1
FENCE_SIGNALED = 0x1
TOPOLOGY_TRIANGLE_LIST = 3
COLOR_WRITE_ALL = 0xF
DYNAMIC_VIEWPORT = 0
DYNAMIC_SCISSOR = 1
DESCRIPTOR_COMBINED_IMAGE_SAMPLER = 1
DESCRIPTOR_UNIFORM = 6
SHADER_VERTEX = 0x1
SHADER_FRAGMENT = 0x10
MEMORY_DEVICE_LOCAL = 0x1
MEMORY_HOST_VISIBLE = 0x2
MEMORY_HOST_COHERENT = 0x4
QUEUE_FAMILY_IGNORED = 0xFFFFFFFF
SUBOPTIMAL = 1000001003
OUT_OF_DATE = -1000001004
SUCCESS = 0

FILTER_LINEAR = 1
SAMPLER_MIPMAP_LINEAR = 1
SAMPLER_ADDRESS_REPEAT = 0

GLFW_CLIENT_API = 0x00022001
GLFW_NO_API = 0
GLFW_RESIZABLE = 0x00020003
GLFW_VISIBLE = 0x00020004
GLFW_DECORATED = 0x00020005
GLFW_FOCUSED = 0x00020001
GLFW_FOCUS_ON_SHOW = 0x0002000C
GLFW_PLATFORM = 0x00050003
GLFW_PLATFORM_X11 = 0x00060004
GLFW_TRUE = 1
GLFW_FALSE = 0
GLFW_PRESS = 1
GLFW_KEY_ESCAPE = 256
GLFW_KEY_Q = 81
GLFW_KEY_SPACE = 32
GLFW_KEY_1 = 49
GLFW_KEY_2 = 50
GLFW_KEY_3 = 51
GLFW_KEY_4 = 52
GLFW_KEY_5 = 53


class VkApplicationInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("pApplicationName", c_char_p),
        ("applicationVersion", c_uint32), ("pEngineName", c_char_p),
        ("engineVersion", c_uint32), ("apiVersion", c_uint32),
    ]


class VkInstanceCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("pApplicationInfo", c_void_p), ("enabledLayerCount", c_uint32),
        ("ppEnabledLayerNames", c_void_p), ("enabledExtensionCount", c_uint32),
        ("ppEnabledExtensionNames", c_void_p),
    ]


class VkDeviceQueueCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("queueFamilyIndex", c_uint32), ("queueCount", c_uint32),
        ("pQueuePriorities", c_void_p),
    ]


class VkDeviceCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("queueCreateInfoCount", c_uint32), ("pQueueCreateInfos", c_void_p),
        ("enabledLayerCount", c_uint32), ("ppEnabledLayerNames", c_void_p),
        ("enabledExtensionCount", c_uint32), ("ppEnabledExtensionNames", c_void_p),
        ("pEnabledFeatures", c_void_p),
    ]


class VkExtent2D(ctypes.Structure):
    _fields_ = [("width", c_uint32), ("height", c_uint32)]


class VkExtent3D(ctypes.Structure):
    _fields_ = [("width", c_uint32), ("height", c_uint32), ("depth", c_uint32)]


class VkOffset2D(ctypes.Structure):
    _fields_ = [("x", c_int32), ("y", c_int32)]


class VkOffset3D(ctypes.Structure):
    _fields_ = [("x", c_int32), ("y", c_int32), ("z", c_int32)]


class VkRect2D(ctypes.Structure):
    _fields_ = [("offset", VkOffset2D), ("extent", VkExtent2D)]


class VkSurfaceCapabilitiesKHR(ctypes.Structure):
    _fields_ = [
        ("minImageCount", c_uint32), ("maxImageCount", c_uint32),
        ("currentExtent", VkExtent2D), ("minImageExtent", VkExtent2D),
        ("maxImageExtent", VkExtent2D), ("maxImageArrayLayers", c_uint32),
        ("supportedTransforms", c_uint32), ("currentTransform", c_uint32),
        ("supportedCompositeAlpha", c_uint32), ("supportedUsageFlags", c_uint32),
    ]


class VkSurfaceFormatKHR(ctypes.Structure):
    _fields_ = [("format", c_uint32), ("colorSpace", c_uint32)]


class VkSwapchainCreateInfoKHR(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("surface", c_uint64), ("minImageCount", c_uint32), ("imageFormat", c_uint32),
        ("imageColorSpace", c_uint32), ("imageExtent", VkExtent2D),
        ("imageArrayLayers", c_uint32), ("imageUsage", c_uint32),
        ("imageSharingMode", c_uint32), ("queueFamilyIndexCount", c_uint32),
        ("pQueueFamilyIndices", c_void_p), ("preTransform", c_uint32),
        ("compositeAlpha", c_uint32), ("presentMode", c_uint32),
        ("clipped", c_uint32), ("oldSwapchain", c_uint64),
    ]


class VkImageCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("imageType", c_uint32), ("format", c_uint32), ("extent", VkExtent3D),
        ("mipLevels", c_uint32), ("arrayLayers", c_uint32), ("samples", c_uint32),
        ("tiling", c_uint32), ("usage", c_uint32), ("sharingMode", c_uint32),
        ("queueFamilyIndexCount", c_uint32), ("pQueueFamilyIndices", c_void_p),
        ("initialLayout", c_uint32),
    ]


class VkImageViewCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("image", c_uint64), ("viewType", c_uint32), ("format", c_uint32),
        ("r", c_uint32), ("g", c_uint32), ("b", c_uint32), ("a", c_uint32),
        ("aspectMask", c_uint32), ("baseMipLevel", c_uint32), ("levelCount", c_uint32),
        ("baseArrayLayer", c_uint32), ("layerCount", c_uint32),
    ]


class VkSamplerCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("magFilter", c_uint32), ("minFilter", c_uint32), ("mipmapMode", c_uint32),
        ("addressModeU", c_uint32), ("addressModeV", c_uint32), ("addressModeW", c_uint32),
        ("mipLodBias", c_float), ("anisotropyEnable", c_uint32), ("maxAnisotropy", c_float),
        ("compareEnable", c_uint32), ("compareOp", c_uint32),
        ("minLod", c_float), ("maxLod", c_float), ("borderColor", c_uint32),
        ("unnormalizedCoordinates", c_uint32),
    ]


class VkAttachmentDescription(ctypes.Structure):
    _fields_ = [
        ("flags", c_uint32), ("format", c_uint32), ("samples", c_uint32),
        ("loadOp", c_uint32), ("storeOp", c_uint32),
        ("stencilLoadOp", c_uint32), ("stencilStoreOp", c_uint32),
        ("initialLayout", c_uint32), ("finalLayout", c_uint32),
    ]


class VkAttachmentReference(ctypes.Structure):
    _fields_ = [("attachment", c_uint32), ("layout", c_uint32)]


class VkSubpassDescription(ctypes.Structure):
    _fields_ = [
        ("flags", c_uint32), ("pipelineBindPoint", c_uint32),
        ("inputAttachmentCount", c_uint32), ("pInputAttachments", c_void_p),
        ("colorAttachmentCount", c_uint32), ("pColorAttachments", c_void_p),
        ("pResolveAttachments", c_void_p), ("pDepthStencilAttachment", c_void_p),
        ("preserveAttachmentCount", c_uint32), ("pPreserveAttachments", c_void_p),
    ]


class VkSubpassDependency(ctypes.Structure):
    _fields_ = [
        ("srcSubpass", c_uint32), ("dstSubpass", c_uint32),
        ("srcStageMask", c_uint32), ("dstStageMask", c_uint32),
        ("srcAccessMask", c_uint32), ("dstAccessMask", c_uint32),
        ("dependencyFlags", c_uint32),
    ]


class VkRenderPassCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("attachmentCount", c_uint32), ("pAttachments", c_void_p),
        ("subpassCount", c_uint32), ("pSubpasses", c_void_p),
        ("dependencyCount", c_uint32), ("pDependencies", c_void_p),
    ]


class VkFramebufferCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("renderPass", c_uint64), ("attachmentCount", c_uint32),
        ("pAttachments", c_void_p), ("width", c_uint32), ("height", c_uint32),
        ("layers", c_uint32),
    ]


class VkShaderModuleCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("codeSize", c_size_t), ("pCode", c_void_p),
    ]


class VkPipelineShaderStageCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("stage", c_uint32), ("module", c_uint64), ("pName", c_char_p),
        ("pSpecializationInfo", c_void_p),
    ]


class VkPipelineVertexInputStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("vertexBindingDescriptionCount", c_uint32), ("pVertexBindingDescriptions", c_void_p),
        ("vertexAttributeDescriptionCount", c_uint32), ("pVertexAttributeDescriptions", c_void_p),
    ]


class VkPipelineInputAssemblyStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("topology", c_uint32), ("primitiveRestartEnable", c_uint32),
    ]


class VkPipelineViewportStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("viewportCount", c_uint32), ("pViewports", c_void_p),
        ("scissorCount", c_uint32), ("pScissors", c_void_p),
    ]


class VkPipelineRasterizationStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("depthClampEnable", c_uint32), ("rasterizerDiscardEnable", c_uint32),
        ("polygonMode", c_uint32), ("cullMode", c_uint32), ("frontFace", c_uint32),
        ("depthBiasEnable", c_uint32), ("depthBiasConstantFactor", c_float),
        ("depthBiasClamp", c_float), ("depthBiasSlopeFactor", c_float),
        ("lineWidth", c_float),
    ]


class VkPipelineMultisampleStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("rasterizationSamples", c_uint32), ("sampleShadingEnable", c_uint32),
        ("minSampleShading", c_float), ("pSampleMask", c_void_p),
        ("alphaToCoverageEnable", c_uint32), ("alphaToOneEnable", c_uint32),
    ]


class VkPipelineColorBlendAttachmentState(ctypes.Structure):
    _fields_ = [
        ("blendEnable", c_uint32), ("srcColorBlendFactor", c_uint32),
        ("dstColorBlendFactor", c_uint32), ("colorBlendOp", c_uint32),
        ("srcAlphaBlendFactor", c_uint32), ("dstAlphaBlendFactor", c_uint32),
        ("alphaBlendOp", c_uint32), ("colorWriteMask", c_uint32),
    ]


class VkPipelineColorBlendStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("logicOpEnable", c_uint32), ("logicOp", c_uint32),
        ("attachmentCount", c_uint32), ("pAttachments", c_void_p),
        ("blendConstants", c_float * 4),
    ]


class VkPipelineDynamicStateCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("dynamicStateCount", c_uint32), ("pDynamicStates", c_void_p),
    ]


class VkPipelineLayoutCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("setLayoutCount", c_uint32), ("pSetLayouts", c_void_p),
        ("pushConstantRangeCount", c_uint32), ("pPushConstantRanges", c_void_p),
    ]


class VkGraphicsPipelineCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("stageCount", c_uint32), ("pStages", c_void_p),
        ("pVertexInputState", c_void_p), ("pInputAssemblyState", c_void_p),
        ("pTessellationState", c_void_p), ("pViewportState", c_void_p),
        ("pRasterizationState", c_void_p), ("pMultisampleState", c_void_p),
        ("pDepthStencilState", c_void_p), ("pColorBlendState", c_void_p),
        ("pDynamicState", c_void_p), ("layout", c_uint64), ("renderPass", c_uint64),
        ("subpass", c_uint32), ("basePipelineHandle", c_uint64),
        ("basePipelineIndex", c_int32),
    ]


class VkDescriptorSetLayoutBinding(ctypes.Structure):
    _fields_ = [
        ("binding", c_uint32), ("descriptorType", c_uint32),
        ("descriptorCount", c_uint32), ("stageFlags", c_uint32),
        ("pImmutableSamplers", c_void_p),
    ]


class VkDescriptorSetLayoutCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("bindingCount", c_uint32), ("pBindings", c_void_p),
    ]


class VkDescriptorPoolSize(ctypes.Structure):
    _fields_ = [("type", c_uint32), ("descriptorCount", c_uint32)]


class VkDescriptorPoolCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("maxSets", c_uint32), ("poolSizeCount", c_uint32), ("pPoolSizes", c_void_p),
    ]


class VkDescriptorSetAllocateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("descriptorPool", c_uint64),
        ("descriptorSetCount", c_uint32), ("pSetLayouts", c_void_p),
    ]


class VkDescriptorBufferInfo(ctypes.Structure):
    _fields_ = [("buffer", c_uint64), ("offset", c_uint64), ("range", c_uint64)]


class VkDescriptorImageInfo(ctypes.Structure):
    _fields_ = [("sampler", c_uint64), ("imageView", c_uint64), ("imageLayout", c_uint32)]


class VkWriteDescriptorSet(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("dstSet", c_uint64),
        ("dstBinding", c_uint32), ("dstArrayElement", c_uint32),
        ("descriptorCount", c_uint32), ("descriptorType", c_uint32),
        ("pImageInfo", c_void_p), ("pBufferInfo", c_void_p),
        ("pTexelBufferView", c_void_p),
    ]


class VkBufferCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("size", c_uint64), ("usage", c_uint32), ("sharingMode", c_uint32),
        ("queueFamilyIndexCount", c_uint32), ("pQueueFamilyIndices", c_void_p),
    ]


class VkMemoryAllocateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("allocationSize", c_uint64), ("memoryTypeIndex", c_uint32),
    ]


class VkMemoryRequirements(ctypes.Structure):
    _fields_ = [
        ("size", c_uint64), ("alignment", c_uint64), ("memoryTypeBits", c_uint32),
    ]


class VkMemoryType(ctypes.Structure):
    _fields_ = [("propertyFlags", c_uint32), ("heapIndex", c_uint32)]


class VkMemoryHeap(ctypes.Structure):
    _fields_ = [("size", c_uint64), ("flags", c_uint32), ("_pad", c_uint32)]


class VkPhysicalDeviceMemoryProperties(ctypes.Structure):
    _fields_ = [
        ("memoryTypeCount", c_uint32),
        ("memoryTypes", VkMemoryType * 32),
        ("memoryHeapCount", c_uint32),
        ("memoryHeaps", VkMemoryHeap * 16),
    ]


class VkQueueFamilyProperties(ctypes.Structure):
    _fields_ = [
        ("queueFlags", c_uint32), ("queueCount", c_uint32),
        ("timestampValidBits", c_uint32), ("minImageTransferGranularity", VkExtent3D),
    ]


class VkCommandPoolCreateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("queueFamilyIndex", c_uint32),
    ]


class VkCommandBufferAllocateInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("commandPool", c_uint64),
        ("level", c_uint32), ("commandBufferCount", c_uint32),
    ]


class VkCommandBufferBeginInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
        ("pInheritanceInfo", c_void_p),
    ]


class VkClearValue(ctypes.Structure):
    _fields_ = [("color", c_float * 4)]


class VkRenderPassBeginInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p), ("renderPass", c_uint64),
        ("framebuffer", c_uint64), ("renderArea", VkRect2D),
        ("clearValueCount", c_uint32), ("pClearValues", c_void_p),
    ]


class VkViewport(ctypes.Structure):
    _fields_ = [
        ("x", c_float), ("y", c_float), ("width", c_float), ("height", c_float),
        ("minDepth", c_float), ("maxDepth", c_float),
    ]


class VkSubmitInfo(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("waitSemaphoreCount", c_uint32), ("pWaitSemaphores", c_void_p),
        ("pWaitDstStageMask", c_void_p), ("commandBufferCount", c_uint32),
        ("pCommandBuffers", c_void_p), ("signalSemaphoreCount", c_uint32),
        ("pSignalSemaphores", c_void_p),
    ]


class VkPresentInfoKHR(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("waitSemaphoreCount", c_uint32), ("pWaitSemaphores", c_void_p),
        ("swapchainCount", c_uint32), ("pSwapchains", c_void_p),
        ("pImageIndices", c_void_p), ("pResults", c_void_p),
    ]


class VkBufferMemoryBarrier(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("srcAccessMask", c_uint32), ("dstAccessMask", c_uint32),
        ("srcQueueFamilyIndex", c_uint32), ("dstQueueFamilyIndex", c_uint32),
        ("buffer", c_uint64), ("offset", c_uint64), ("size", c_uint64),
    ]


class VkImageSubresourceRange(ctypes.Structure):
    _fields_ = [
        ("aspectMask", c_uint32), ("baseMipLevel", c_uint32), ("levelCount", c_uint32),
        ("baseArrayLayer", c_uint32), ("layerCount", c_uint32),
    ]


class VkImageMemoryBarrier(ctypes.Structure):
    _fields_ = [
        ("sType", c_uint32), ("pNext", c_void_p),
        ("srcAccessMask", c_uint32), ("dstAccessMask", c_uint32),
        ("oldLayout", c_uint32), ("newLayout", c_uint32),
        ("srcQueueFamilyIndex", c_uint32), ("dstQueueFamilyIndex", c_uint32),
        ("image", c_uint64), ("subresourceRange", VkImageSubresourceRange),
    ]


class VkImageSubresourceLayers(ctypes.Structure):
    _fields_ = [
        ("aspectMask", c_uint32), ("mipLevel", c_uint32),
        ("baseArrayLayer", c_uint32), ("layerCount", c_uint32),
    ]


class VkBufferImageCopy(ctypes.Structure):
    _fields_ = [
        ("bufferOffset", c_uint64), ("bufferRowLength", c_uint32),
        ("bufferImageHeight", c_uint32), ("imageSubresource", VkImageSubresourceLayers),
        ("imageOffset", VkOffset3D), ("imageExtent", VkExtent3D),
    ]


class VkFenceCreateInfo(ctypes.Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]


class VkSemaphoreCreateInfo(ctypes.Structure):
    _fields_ = [("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32)]


class VisualizerUBO(ctypes.Structure):
    _fields_ = [
        ("res", c_float * 4),     # width, height, accum_time, is_playing
        ("audio0", c_float * 4),  # sub_bass, bass, low_mid, mid
        ("audio1", c_float * 4),  # high_mid, treble, air, rms_energy
        ("audio2", c_float * 4),  # beat_pulse, bass_phase, mid_phase, high_phase
        ("bands0", c_float * 4),  # spectrum bands 0..3
        ("bands1", c_float * 4),  # spectrum bands 4..7
        ("bands2", c_float * 4),  # spectrum bands 8..11
        ("bands3", c_float * 4),  # spectrum bands 12..15
        ("preset", c_float * 4),  # preset_id, pitch_factor, dyn_range, seed
    ]


def _api_version(major, minor, patch=0):
    return (major << 22) | (minor << 12) | patch


def _check(result, what):
    if result != SUCCESS:
        raise RuntimeError(f"{what} failed with Vulkan result {result}")
    return result


def _addr(obj):
    return ctypes.cast(byref(obj), c_void_p)


def _load(getter, owner, name, restype, argtypes):
    raw = getter(owner, name.encode())
    if not raw:
        raise RuntimeError(f"Vulkan entry point {name} is missing")
    return CFUNCTYPE(restype, *argtypes)(raw)


def select_vulkan_device(devices: List[Dict[str, Any]]) -> int:
    """Select preferred discrete Vulkan GPU (prioritizing NVIDIA discrete GPU)."""
    nvidia = [i for i, dev in enumerate(devices) if int(dev["vendor_id"]) == NVIDIA_VENDOR_ID]
    if nvidia:
        discrete = [i for i in nvidia if int(devices[i].get("device_type", -1)) == DISCRETE_GPU]
        return (discrete or nvidia)[0]
    discrete = [i for i, dev in enumerate(devices) if int(dev.get("device_type", -1)) == DISCRETE_GPU]
    if discrete:
        return discrete[0]
    if devices:
        return 0
    raise RuntimeError("MP_Liquid_Visualizer requires a Vulkan-capable GPU.")


class LiquidVisualizerVulkanRenderer:
    """Borderless fixed 1400x1400 Vulkan 3D Visualizer Window with zero text overlay."""

    width = WINDOW_WIDTH
    height = WINDOW_HEIGHT

    def __init__(self, preset_name: Optional[str] = None):
        self.preset = get_active_preset(preset_name)
        self.title = "MP_Liquid_Visualizer"
        self.device_name = ""
        self.vendor_id = 0
        self.device_type = -1
        self.format = FORMAT_B8G8R8A8_UNORM
        self.should_close = False
        self.mouse_down = False
        self.cursor = (0.0, 0.0)
        self._drag_active = False
        self._drag_origin = (0, 0)
        self._drag_press_screen = (0, 0)
        self._cur_pos = (160, 80)

        self._frame = 0
        self._swapchain = 0
        self._images = []
        self._views = []
        self._framebuffers = []
        self._image_available = []
        self._render_finished = []
        self._fences = []
        self._cmd = []
        self._extent = (WINDOW_WIDTH, WINDOW_HEIGHT)

        self._tex_image = 0
        self._tex_memory = 0
        self._tex_view = 0
        self._tex_sampler = 0

        self._readback_buffer = 0
        self._readback_memory = 0
        self._readback_ptr = None
        self._readback_bytes = 0
        self._alive = False

    @property
    def summary(self) -> str:
        kind = "discrete" if self.device_type == DISCRETE_GPU else "gpu"
        return (
            f"MP_Liquid_Visualizer Vulkan device: {self.device_name} "
            f"(vendor 0x{self.vendor_id:04x}, {kind}) | "
            f"Preset: {self.preset['name']} | Window: {self.width}x{self.height} Fixed Borderless"
        )

    def open(self):
        self._silence_overlays()
        if is_windows():
            self._glfw = load_glfw_dll()
            self._bind_glfw()
            self._x11 = None
        else:
            self._x11 = ctypes.CDLL("libX11.so.6")
            self._x11.XInitThreads.restype = c_int
            self._x11.XInitThreads()
            self._bind_x11()
            self._glfw = load_glfw_dll()
            self._bind_glfw()
            self._glfw.glfwInitHint(GLFW_PLATFORM, GLFW_PLATFORM_X11)

        if not self._glfw.glfwInit():
            raise RuntimeError("glfwInit failed")
        if not self._glfw.glfwVulkanSupported():
            raise RuntimeError("GLFW reports Vulkan is unavailable")

        self._window = self._create_window()
        self._bind_input()
        self._vulkan = load_vulkan_dll()
        self._bind_loader()
        self._create_instance()
        self._load_instance()

        surface = c_uint64()
        _check(
            self._glfw.glfwCreateWindowSurface(self._instance, self._window, None, byref(surface)),
            "glfwCreateWindowSurface",
        )
        self._surface = surface.value

        self._pick_device()
        self._create_device()
        self._load_device()
        self._create_swapchain()
        self._create_commands()
        self._create_cover_texture()
        self._create_pipeline()
        self._create_descriptors()
        self._alive = True
        return self

    def _silence_overlays(self):
        # Strictly disable all FPS/HUD overlays so there is NEVER any text overlay displayed
        os.environ["DISABLE_MANGOHUD"] = "1"
        os.environ["MANGOHUD"] = "0"
        os.environ["DISABLE_VKBASALT"] = "1"
        os.environ["GALLIUM_HUD"] = ""
        os.environ["DXVK_HUD"] = "0"
        os.environ["VK_LOADER_LAYERS_DISABLE"] = (
            "VK_LAYER_MANGOHUD_overlay_x86_64,VK_LAYER_MANGOHUD_overlay_x86,"
            "VK_LAYER_VKBASALT_post_processing,VK_LAYER_OBS_vkcapture_64,"
            "VK_LAYER_VALVE_steam_overlay_64,VK_LAYER_VALVE_steam_fossilize_64,"
            "VK_LAYER_MESA_overlay"
        )

    def _bind_x11(self):
        x = self._x11
        x.XDefaultRootWindow.argtypes = [c_void_p]
        x.XDefaultRootWindow.restype = c_uint64
        x.XQueryPointer.argtypes = [
            c_void_p, c_uint64,
            POINTER(c_uint64), POINTER(c_uint64),
            POINTER(c_int), POINTER(c_int),
            POINTER(c_int), POINTER(c_int),
            POINTER(c_uint32),
        ]
        x.XQueryPointer.restype = c_int

    def _bind_glfw(self):
        g = self._glfw
        g.glfwInit.restype = c_int
        g.glfwInitHint.argtypes = [c_int, c_int]
        g.glfwWindowHint.argtypes = [c_int, c_int]
        g.glfwVulkanSupported.restype = c_int
        g.glfwCreateWindow.argtypes = [c_int, c_int, c_char_p, c_void_p, c_void_p]
        g.glfwCreateWindow.restype = c_void_p
        g.glfwDestroyWindow.argtypes = [c_void_p]
        g.glfwTerminate.argtypes = []
        g.glfwPollEvents.argtypes = []
        g.glfwWindowShouldClose.argtypes = [c_void_p]
        g.glfwWindowShouldClose.restype = c_int
        g.glfwSetWindowShouldClose.argtypes = [c_void_p, c_int]
        g.glfwSetWindowPos.argtypes = [c_void_p, c_int, c_int]
        g.glfwSetWindowSize.argtypes = [c_void_p, c_int, c_int]
        g.glfwSetWindowSizeLimits.argtypes = [c_void_p, c_int, c_int, c_int, c_int]
        g.glfwGetWindowSize.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetWindowPos.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetFramebufferSize.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetRequiredInstanceExtensions.argtypes = [POINTER(c_uint32)]
        g.glfwGetRequiredInstanceExtensions.restype = POINTER(c_char_p)
        g.glfwCreateWindowSurface.argtypes = [c_void_p, c_void_p, c_void_p, POINTER(c_uint64)]
        g.glfwCreateWindowSurface.restype = c_int
        g.glfwSetKeyCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetKeyCallback.restype = c_void_p
        g.glfwSetMouseButtonCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetMouseButtonCallback.restype = c_void_p
        g.glfwSetCursorPosCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetCursorPosCallback.restype = c_void_p
        g.glfwSetWindowPosCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetWindowPosCallback.restype = c_void_p
        if not is_windows() and hasattr(g, "glfwGetX11Display"):
            g.glfwGetX11Display.argtypes = [c_void_p]
            g.glfwGetX11Display.restype = c_void_p

    def _create_window(self):
        g = self._glfw
        g.glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API)
        # Fixed 1400x1400 non-resizable, borderless window
        g.glfwWindowHint(GLFW_RESIZABLE, GLFW_FALSE)
        g.glfwWindowHint(GLFW_DECORATED, GLFW_FALSE)
        g.glfwWindowHint(GLFW_FOCUS_ON_SHOW, GLFW_TRUE)
        g.glfwWindowHint(GLFW_VISIBLE, GLFW_TRUE)
        g.glfwWindowHint(GLFW_FOCUSED, GLFW_TRUE)

        title = self.title.encode("utf-8")
        window = g.glfwCreateWindow(WINDOW_WIDTH, WINDOW_HEIGHT, title, None, None)
        if not window:
            raise RuntimeError("GLFW could not open a 1400x1400 borderless window for Vulkan")

        # Enforce strict 1400x1400 size limits
        try:
            g.glfwSetWindowSizeLimits(window, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT)
        except Exception:
            pass
        g.glfwSetWindowPos(window, 160, 80)
        self._cur_pos = (160, 80)
        return window

    def _bind_input(self):
        KEY_CB = CFUNCTYPE(None, c_void_p, c_int, c_int, c_int, c_int)
        MOUSE_CB = CFUNCTYPE(None, c_void_p, c_int, c_int, c_int)
        CURSOR_CB = CFUNCTYPE(None, c_void_p, c_double, c_double)
        POS_CB = CFUNCTYPE(None, c_void_p, c_int, c_int)

        self._on_key_cb = KEY_CB(self._on_key)
        self._on_mouse_cb = MOUSE_CB(self._on_mouse)
        self._on_cursor_cb = CURSOR_CB(self._on_cursor)
        self._on_pos_cb = POS_CB(self._on_pos)

        self._glfw.glfwSetKeyCallback(self._window, ctypes.cast(self._on_key_cb, c_void_p))
        self._glfw.glfwSetMouseButtonCallback(self._window, ctypes.cast(self._on_mouse_cb, c_void_p))
        self._glfw.glfwSetCursorPosCallback(self._window, ctypes.cast(self._on_cursor_cb, c_void_p))
        self._glfw.glfwSetWindowPosCallback(self._window, ctypes.cast(self._on_pos_cb, c_void_p))

    def _on_key(self, _window, key, _scancode, action, _mods):
        if action != GLFW_PRESS:
            return
        # Pressing Escape or 'q'/'Q' immediately closes the visualizer
        if key in (GLFW_KEY_ESCAPE, GLFW_KEY_Q):
            self.request_close()
        elif key in (GLFW_KEY_1, GLFW_KEY_2, GLFW_KEY_3, GLFW_KEY_4, GLFW_KEY_5):
            idx = key - GLFW_KEY_1
            if 0 <= idx < len(VISUALIZER_PRESETS):
                self.preset = VISUALIZER_PRESETS[idx]
                save_active_preset(self.preset["key"])

    def _on_mouse(self, _window, button, action, _mods):
        if button == 0:
            self.mouse_down = action == GLFW_PRESS
            if self.mouse_down:
                self._drag_active = True
                self._drag_origin = self.window_pos()
                rx, ry = self.root_pointer()
                self._drag_press_screen = (rx, ry) if (rx or ry) else (
                    int(self._drag_origin[0] + self.cursor[0]),
                    int(self._drag_origin[1] + self.cursor[1]),
                )
            else:
                self._drag_active = False

    def _on_cursor(self, _window, x, y):
        self.cursor = (float(x), float(y))
        if self._drag_active and self.mouse_down:
            rx, ry = self.root_pointer()
            if rx or ry:
                nx = int(self._drag_origin[0] + (rx - self._drag_press_screen[0]))
                ny = int(self._drag_origin[1] + (ry - self._drag_press_screen[1]))
                self.set_window_pos(nx, ny)

    def _on_pos(self, _window, x, y):
        self._cur_pos = (int(x), int(y))

    def root_pointer(self) -> Tuple[int, int]:
        if is_windows():
            try:
                class POINT(ctypes.Structure):
                    _fields_ = [("x", c_int), ("y", c_int)]
                pt = POINT()
                if ctypes.windll.user32.GetCursorPos(byref(pt)):
                    return int(pt.x), int(pt.y)
            except Exception:
                pass
            return 0, 0
        if not getattr(self, "_x11", None) or not hasattr(self._glfw, "glfwGetX11Display"):
            return 0, 0
        display = self._glfw.glfwGetX11Display(self._window)
        if not display:
            return 0, 0
        root = self._x11.XDefaultRootWindow(display)
        root_ret, child_ret = c_uint64(), c_uint64()
        rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
        mask = c_uint32()
        if self._x11.XQueryPointer(
            display, root, byref(root_ret), byref(child_ret),
            byref(rx), byref(ry), byref(wx), byref(wy), byref(mask),
        ):
            return int(rx.value), int(ry.value)
        return 0, 0

    def window_size(self) -> Tuple[int, int]:
        w, h = c_int(), c_int()
        self._glfw.glfwGetWindowSize(self._window, byref(w), byref(h))
        return int(w.value), int(h.value)

    def framebuffer_size(self) -> Tuple[int, int]:
        w, h = c_int(), c_int()
        self._glfw.glfwGetFramebufferSize(self._window, byref(w), byref(h))
        return max(1, int(w.value)), max(1, int(h.value))

    def window_pos(self) -> Tuple[int, int]:
        return self._cur_pos

    def set_window_pos(self, x: int, y: int):
        self._cur_pos = (int(x), int(y))
        self._glfw.glfwSetWindowPos(self._window, int(x), int(y))

    def request_close(self):
        self.should_close = True
        if getattr(self, "_window", None):
            self._glfw.glfwSetWindowShouldClose(self._window, 1)

    def poll(self) -> bool:
        self._glfw.glfwPollEvents()
        if self._glfw.glfwWindowShouldClose(self._window):
            self.should_close = True
        # Ensure window dimensions remain strictly 1400x1400
        w, h = self.window_size()
        if (w, h) != (WINDOW_WIDTH, WINDOW_HEIGHT):
            self._glfw.glfwSetWindowSize(self._window, WINDOW_WIDTH, WINDOW_HEIGHT)
        return not self.should_close

    def _bind_loader(self):
        v = self._vulkan
        v.vkGetInstanceProcAddr.restype = c_void_p
        v.vkGetInstanceProcAddr.argtypes = [c_void_p, c_char_p]
        v.vkGetDeviceProcAddr.restype = c_void_p
        v.vkGetDeviceProcAddr.argtypes = [c_void_p, c_char_p]
        v.vkCreateInstance.restype = c_int32
        v.vkCreateInstance.argtypes = [c_void_p, c_void_p, POINTER(c_void_p)]

    def _create_instance(self):
        count = c_uint32()
        ptr = self._glfw.glfwGetRequiredInstanceExtensions(byref(count))
        names = [ptr[i] for i in range(count.value)]
        self._ext_names = names
        arr = (c_char_p * len(names))(*names)
        self._ext_arr = arr
        app = VkApplicationInfo()
        app.sType = ST_APPLICATION_INFO
        app.pApplicationName = b"MP_Liquid_Visualizer"
        app.applicationVersion = _api_version(0, 4, 0)
        app.pEngineName = b"mp-liquid-visualizer-vulkan"
        app.engineVersion = 1
        app.apiVersion = _api_version(1, 2, 0)
        self._app = app
        info = VkInstanceCreateInfo()
        info.sType = ST_INSTANCE_CREATE_INFO
        info.pApplicationInfo = _addr(app)
        info.enabledExtensionCount = len(names)
        info.ppEnabledExtensionNames = ctypes.cast(arr, c_void_p)
        self._instance_info = info
        instance = c_void_p()
        _check(self._vulkan.vkCreateInstance(_addr(info), None, byref(instance)), "vkCreateInstance")
        self._instance = instance

    def _load_instance(self):
        g = self._vulkan.vkGetInstanceProcAddr
        inst = self._instance

        def load(name, restype, argtypes):
            return _load(g, inst, name, restype, argtypes)

        U32 = c_uint32
        self._i = type("I", (), {})()
        self._i.DestroyInstance = load("vkDestroyInstance", None, [c_void_p, c_void_p])
        self._i.DestroySurfaceKHR = load("vkDestroySurfaceKHR", None, [c_void_p, c_uint64, c_void_p])
        self._i.EnumeratePhysicalDevices = load(
            "vkEnumeratePhysicalDevices", c_int32, [c_void_p, POINTER(U32), POINTER(c_void_p)]
        )
        self._i.GetPhysicalDeviceProperties = load(
            "vkGetPhysicalDeviceProperties", None, [c_void_p, c_void_p]
        )
        self._i.GetPhysicalDeviceQueueFamilyProperties = load(
            "vkGetPhysicalDeviceQueueFamilyProperties", None, [c_void_p, POINTER(U32), c_void_p]
        )
        self._i.GetPhysicalDeviceMemoryProperties = load(
            "vkGetPhysicalDeviceMemoryProperties", None, [c_void_p, c_void_p]
        )
        self._i.GetSurfaceSupport = load(
            "vkGetPhysicalDeviceSurfaceSupportKHR", c_int32, [c_void_p, U32, c_uint64, POINTER(U32)]
        )
        self._i.GetSurfaceCaps = load(
            "vkGetPhysicalDeviceSurfaceCapabilitiesKHR", c_int32, [c_void_p, c_uint64, c_void_p]
        )
        self._i.GetSurfaceFormats = load(
            "vkGetPhysicalDeviceSurfaceFormatsKHR", c_int32, [c_void_p, c_uint64, POINTER(U32), c_void_p]
        )
        self._i.GetSurfaceModes = load(
            "vkGetPhysicalDeviceSurfacePresentModesKHR", c_int32, [c_void_p, c_uint64, POINTER(U32), c_void_p]
        )
        self._i.CreateDevice = load(
            "vkCreateDevice", c_int32, [c_void_p, c_void_p, c_void_p, POINTER(c_void_p)]
        )

    def _device_header(self, phys) -> Dict[str, Any]:
        buf = (c_uint8 * 16384)()
        self._i.GetPhysicalDeviceProperties(phys, buf)
        api, driver, vendor, device, dtype = ctypes.cast(buf, POINTER(c_uint32 * 5)).contents
        name = ctypes.string_at(ctypes.addressof(buf) + 20, 256).split(b"\0", 1)[0].decode("utf-8", "replace")
        return {
            "api": int(api),
            "driver": int(driver),
            "vendor_id": int(vendor),
            "device_id": int(device),
            "device_type": int(dtype),
            "name": name,
        }

    def _pick_device(self):
        count = c_uint32()
        _check(self._i.EnumeratePhysicalDevices(self._instance, byref(count), None), "enumerate devices")
        if count.value == 0:
            raise RuntimeError("Vulkan reported no physical devices")
        raw = (c_void_p * count.value)()
        _check(self._i.EnumeratePhysicalDevices(self._instance, byref(count), raw), "enumerate devices")
        headers = [self._device_header(raw[i]) for i in range(count.value)]
        idx = select_vulkan_device(headers)
        self._physical = raw[idx]
        chosen = headers[idx]
        self.device_name = chosen["name"]
        self.vendor_id = chosen["vendor_id"]
        self.device_type = chosen["device_type"]
        self._queue_family = self._present_family(self._physical)

    def _present_family(self, phys) -> int:
        count = c_uint32()
        self._i.GetPhysicalDeviceQueueFamilyProperties(phys, byref(count), None)
        props = (VkQueueFamilyProperties * count.value)()
        self._i.GetPhysicalDeviceQueueFamilyProperties(phys, byref(count), props)
        for i in range(count.value):
            if not (props[i].queueFlags & QUEUE_GRAPHICS):
                continue
            support = c_uint32()
            _check(self._i.GetSurfaceSupport(phys, i, self._surface, byref(support)), "surface support")
            if support.value:
                return i
        raise RuntimeError(f"{self.device_name} has no Vulkan graphics queue that can present")

    def _create_device(self):
        priority = (c_float * 1)(1.0)
        self._priority = priority
        q = VkDeviceQueueCreateInfo()
        q.sType = ST_DEVICE_QUEUE_CREATE_INFO
        q.queueFamilyIndex = self._queue_family
        q.queueCount = 1
        q.pQueuePriorities = ctypes.cast(priority, c_void_p)
        self._queue_info = q
        ext = (c_char_p * 1)(b"VK_KHR_swapchain")
        self._dev_ext = ext
        info = VkDeviceCreateInfo()
        info.sType = ST_DEVICE_CREATE_INFO
        info.queueCreateInfoCount = 1
        info.pQueueCreateInfos = _addr(q)
        info.enabledExtensionCount = 1
        info.ppEnabledExtensionNames = ctypes.cast(ext, c_void_p)
        self._device_info = info
        device = c_void_p()
        _check(self._i.CreateDevice(self._physical, _addr(info), None, byref(device)), "vkCreateDevice")
        self._device = device

    def _load_device(self):
        g = self._vulkan.vkGetDeviceProcAddr
        dev = self._device

        def load(name, restype, argtypes):
            return _load(g, dev, name, restype, argtypes)

        U32 = c_uint32
        P = c_void_p
        H = c_uint64
        self._vk = type("D", (), {})()
        vk = self._vk
        vk.GetDeviceQueue = load("vkGetDeviceQueue", None, [P, U32, U32, POINTER(P)])
        vk.DeviceWaitIdle = load("vkDeviceWaitIdle", c_int32, [P])
        vk.DestroyDevice = load("vkDestroyDevice", None, [P, P])
        vk.CreateSwapchainKHR = load("vkCreateSwapchainKHR", c_int32, [P, P, P, POINTER(H)])
        vk.DestroySwapchainKHR = load("vkDestroySwapchainKHR", None, [P, H, P])
        vk.GetSwapchainImagesKHR = load("vkGetSwapchainImagesKHR", c_int32, [P, H, POINTER(U32), POINTER(H)])
        vk.CreateImage = load("vkCreateImage", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyImage = load("vkDestroyImage", None, [P, H, P])
        vk.GetImageMemoryRequirements = load("vkGetImageMemoryRequirements", None, [P, H, P])
        vk.BindImageMemory = load("vkBindImageMemory", c_int32, [P, H, H, c_uint64])
        vk.CreateImageView = load("vkCreateImageView", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyImageView = load("vkDestroyImageView", None, [P, H, P])
        vk.CreateSampler = load("vkCreateSampler", c_int32, [P, P, P, POINTER(H)])
        vk.DestroySampler = load("vkDestroySampler", None, [P, H, P])
        vk.CreateRenderPass = load("vkCreateRenderPass", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyRenderPass = load("vkDestroyRenderPass", None, [P, H, P])
        vk.CreateFramebuffer = load("vkCreateFramebuffer", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyFramebuffer = load("vkDestroyFramebuffer", None, [P, H, P])
        vk.CreateShaderModule = load("vkCreateShaderModule", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyShaderModule = load("vkDestroyShaderModule", None, [P, H, P])
        vk.CreatePipelineLayout = load("vkCreatePipelineLayout", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyPipelineLayout = load("vkDestroyPipelineLayout", None, [P, H, P])
        vk.CreateGraphicsPipelines = load("vkCreateGraphicsPipelines", c_int32, [P, H, U32, P, P, POINTER(H)])
        vk.DestroyPipeline = load("vkDestroyPipeline", None, [P, H, P])
        vk.CreateDescriptorSetLayout = load("vkCreateDescriptorSetLayout", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyDescriptorSetLayout = load("vkDestroyDescriptorSetLayout", None, [P, H, P])
        vk.CreateDescriptorPool = load("vkCreateDescriptorPool", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyDescriptorPool = load("vkDestroyDescriptorPool", None, [P, H, P])
        vk.AllocateDescriptorSets = load("vkAllocateDescriptorSets", c_int32, [P, P, POINTER(H)])
        vk.UpdateDescriptorSets = load("vkUpdateDescriptorSets", None, [P, U32, P, U32, P])
        vk.CreateBuffer = load("vkCreateBuffer", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyBuffer = load("vkDestroyBuffer", None, [P, H, P])
        vk.GetBufferMemoryRequirements = load("vkGetBufferMemoryRequirements", None, [P, H, P])
        vk.AllocateMemory = load("vkAllocateMemory", c_int32, [P, P, P, POINTER(H)])
        vk.FreeMemory = load("vkFreeMemory", None, [P, H, P])
        vk.BindBufferMemory = load("vkBindBufferMemory", c_int32, [P, H, H, c_uint64])
        vk.MapMemory = load("vkMapMemory", c_int32, [P, H, c_uint64, c_uint64, U32, POINTER(P)])
        vk.UnmapMemory = load("vkUnmapMemory", None, [P, H])
        vk.CreateCommandPool = load("vkCreateCommandPool", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyCommandPool = load("vkDestroyCommandPool", None, [P, H, P])
        vk.AllocateCommandBuffers = load("vkAllocateCommandBuffers", c_int32, [P, P, POINTER(P)])
        vk.BeginCommandBuffer = load("vkBeginCommandBuffer", c_int32, [P, P])
        vk.EndCommandBuffer = load("vkEndCommandBuffer", c_int32, [P])
        vk.ResetCommandBuffer = load("vkResetCommandBuffer", c_int32, [P, U32])
        vk.CmdBeginRenderPass = load("vkCmdBeginRenderPass", None, [P, P, U32])
        vk.CmdEndRenderPass = load("vkCmdEndRenderPass", None, [P])
        vk.CmdBindPipeline = load("vkCmdBindPipeline", None, [P, U32, H])
        vk.CmdBindDescriptorSets = load("vkCmdBindDescriptorSets", None, [P, U32, H, U32, U32, P, U32, P])
        vk.CmdDraw = load("vkCmdDraw", None, [P, U32, U32, U32, U32])
        vk.CmdSetViewport = load("vkCmdSetViewport", None, [P, U32, U32, P])
        vk.CmdSetScissor = load("vkCmdSetScissor", None, [P, U32, U32, P])
        vk.CmdPipelineBarrier = load("vkCmdPipelineBarrier", None, [P, U32, U32, U32, U32, P, U32, P, U32, P])
        vk.CmdCopyBufferToImage = load("vkCmdCopyBufferToImage", None, [P, H, H, U32, U32, P])
        vk.CmdCopyImageToBuffer = load("vkCmdCopyImageToBuffer", None, [P, H, U32, H, U32, P])
        vk.CreateSemaphore = load("vkCreateSemaphore", c_int32, [P, P, P, POINTER(H)])
        vk.DestroySemaphore = load("vkDestroySemaphore", None, [P, H, P])
        vk.CreateFence = load("vkCreateFence", c_int32, [P, P, P, POINTER(H)])
        vk.DestroyFence = load("vkDestroyFence", None, [P, H, P])
        vk.WaitForFences = load("vkWaitForFences", c_int32, [P, U32, P, U32, c_uint64])
        vk.ResetFences = load("vkResetFences", c_int32, [P, U32, P])
        vk.AcquireNextImageKHR = load("vkAcquireNextImageKHR", c_int32, [P, H, c_uint64, H, H, POINTER(U32)])
        vk.QueueSubmit = load("vkQueueSubmit", c_int32, [P, U32, P, H])
        vk.QueuePresentKHR = load("vkQueuePresentKHR", c_int32, [P, P])
        vk.QueueWaitIdle = load("vkQueueWaitIdle", c_int32, [P])

        queue = c_void_p()
        vk.GetDeviceQueue(self._device, self._queue_family, 0, byref(queue))
        self._queue = queue

    def _surface_choices(self):
        caps = VkSurfaceCapabilitiesKHR()
        _check(self._i.GetSurfaceCaps(self._physical, self._surface, _addr(caps)), "surface caps")
        count = c_uint32()
        _check(self._i.GetSurfaceFormats(self._physical, self._surface, byref(count), None), "surface formats")
        formats = (VkSurfaceFormatKHR * count.value)()
        _check(self._i.GetSurfaceFormats(self._physical, self._surface, byref(count), formats), "surface formats")
        preferred = (FORMAT_B8G8R8A8_UNORM, FORMAT_R8G8B8A8_UNORM, FORMAT_B8G8R8A8_SRGB)
        chosen = formats[0]
        for want in preferred:
            for fmt in formats:
                if fmt.format == want:
                    chosen = fmt
                    break
            else:
                continue
            break
        modes_n = c_uint32()
        _check(self._i.GetSurfaceModes(self._physical, self._surface, byref(modes_n), None), "present modes")
        modes = (c_uint32 * modes_n.value)()
        _check(self._i.GetSurfaceModes(self._physical, self._surface, byref(modes_n), modes), "present modes")
        present = PRESENT_FIFO if any(modes[i] == PRESENT_FIFO for i in range(modes_n.value)) else modes[0]
        return caps, chosen, present

    def _create_swapchain(self, old=0):
        caps, fmt, present = self._surface_choices()
        self.format = int(fmt.format)
        self._colorspace = int(fmt.colorSpace)
        extent = (WINDOW_WIDTH, WINDOW_HEIGHT)
        if caps.currentExtent.width != 0xFFFFFFFF and caps.currentExtent.width > 0:
            extent = (int(caps.currentExtent.width), int(caps.currentExtent.height))

        image_count = max(caps.minImageCount, 3)
        if caps.maxImageCount:
            image_count = min(image_count, caps.maxImageCount)

        usage = IMAGE_USAGE_COLOR
        if caps.supportedUsageFlags & IMAGE_USAGE_TRANSFER_SRC:
            usage |= IMAGE_USAGE_TRANSFER_SRC
            self._can_readback = True
        else:
            self._can_readback = False

        info = VkSwapchainCreateInfoKHR()
        info.sType = ST_SWAPCHAIN_CREATE
        info.surface = self._surface
        info.minImageCount = image_count
        info.imageFormat = self.format
        info.imageColorSpace = self._colorspace
        info.imageExtent = VkExtent2D(extent[0], extent[1])
        info.imageArrayLayers = 1
        info.imageUsage = usage
        info.imageSharingMode = SHARING_EXCLUSIVE
        info.preTransform = caps.currentTransform or TRANSFORM_IDENTITY
        info.compositeAlpha = COMPOSITE_OPAQUE
        info.presentMode = present
        info.clipped = 1
        info.oldSwapchain = old
        self._swap_info = info

        swap = c_uint64()
        _check(self._vk.CreateSwapchainKHR(self._device, _addr(info), None, byref(swap)), "vkCreateSwapchainKHR")
        if old:
            self._vk.DestroySwapchainKHR(self._device, old, None)
        self._swapchain = swap.value
        self._extent = extent

        count = c_uint32()
        _check(self._vk.GetSwapchainImagesKHR(self._device, self._swapchain, byref(count), None), "swapchain images")
        images = (c_uint64 * count.value)()
        _check(self._vk.GetSwapchainImagesKHR(self._device, self._swapchain, byref(count), images), "swapchain images")
        self._images = [int(images[i]) for i in range(count.value)]
        self._views = []
        self._framebuffers = []

        for image in self._images:
            view_info = VkImageViewCreateInfo()
            view_info.sType = ST_IMAGE_VIEW_CREATE_INFO
            view_info.image = image
            view_info.viewType = IMAGE_VIEW_2D
            view_info.format = self.format
            view_info.aspectMask = IMAGE_ASPECT_COLOR
            view_info.levelCount = 1
            view_info.layerCount = 1
            view = c_uint64()
            _check(self._vk.CreateImageView(self._device, _addr(view_info), None, byref(view)), "image view")
            self._views.append(view.value)

        if not getattr(self, "_render_pass", 0):
            self._create_render_pass()
        self._create_framebuffers()

    def _create_render_pass(self):
        attachment = VkAttachmentDescription()
        attachment.format = self.format
        attachment.samples = SAMPLE_1
        attachment.loadOp = LOAD_CLEAR
        attachment.storeOp = STORE_STORE
        attachment.stencilLoadOp = LOAD_DONT
        attachment.stencilStoreOp = STORE_DONT
        attachment.initialLayout = LAYOUT_UNDEFINED
        attachment.finalLayout = LAYOUT_PRESENT
        ref = VkAttachmentReference(0, LAYOUT_COLOR)
        sub = VkSubpassDescription()
        sub.pipelineBindPoint = 0
        sub.colorAttachmentCount = 1
        sub.pColorAttachments = _addr(ref)
        deps = (VkSubpassDependency * 2)()
        deps[0].srcSubpass = SUBPASS_EXTERNAL
        deps[0].dstSubpass = 0
        deps[0].srcStageMask = STAGE_COLOR_OUT
        deps[0].dstStageMask = STAGE_COLOR_OUT
        deps[0].dstAccessMask = ACCESS_COLOR_WRITE
        deps[1].srcSubpass = 0
        deps[1].dstSubpass = SUBPASS_EXTERNAL
        deps[1].srcStageMask = STAGE_COLOR_OUT
        deps[1].dstStageMask = STAGE_BOTTOM
        deps[1].srcAccessMask = ACCESS_COLOR_WRITE
        info = VkRenderPassCreateInfo()
        info.sType = ST_RENDER_PASS
        info.attachmentCount = 1
        info.pAttachments = _addr(attachment)
        info.subpassCount = 1
        info.pSubpasses = _addr(sub)
        info.dependencyCount = 2
        info.pDependencies = ctypes.cast(deps, c_void_p)
        self._rp_keep = (attachment, ref, sub, deps, info)
        rp = c_uint64()
        _check(self._vk.CreateRenderPass(self._device, _addr(info), None, byref(rp)), "render pass")
        self._render_pass = rp.value

    def _create_framebuffers(self):
        self._fb_keeps = []
        for view in self._views:
            views = (c_uint64 * 1)(view)
            info = VkFramebufferCreateInfo()
            info.sType = ST_FRAMEBUFFER
            info.renderPass = self._render_pass
            info.attachmentCount = 1
            info.pAttachments = ctypes.cast(views, c_void_p)
            info.width, info.height = self._extent
            info.layers = 1
            fb = c_uint64()
            self._fb_keeps.append((views, info))
            _check(self._vk.CreateFramebuffer(self._device, _addr(info), None, byref(fb)), "framebuffer")
            self._framebuffers.append(fb.value)

    def _memory_type(self, bits: int, flags: int) -> int:
        props = VkPhysicalDeviceMemoryProperties()
        self._i.GetPhysicalDeviceMemoryProperties(self._physical, _addr(props))
        for i in range(props.memoryTypeCount):
            if bits & (1 << i) and (props.memoryTypes[i].propertyFlags & flags) == flags:
                return i
        raise RuntimeError("No compatible Vulkan memory type found on device")

    def _create_buffer(self, size: int, usage: int, mem_flags: int = MEMORY_HOST_VISIBLE | MEMORY_HOST_COHERENT):
        info = VkBufferCreateInfo()
        info.sType = ST_BUFFER_CREATE_INFO
        info.size = size
        info.usage = usage
        info.sharingMode = SHARING_EXCLUSIVE
        buf = c_uint64()
        _check(self._vk.CreateBuffer(self._device, _addr(info), None, byref(buf)), "buffer")
        req = VkMemoryRequirements()
        self._vk.GetBufferMemoryRequirements(self._device, buf.value, _addr(req))
        alloc = VkMemoryAllocateInfo()
        alloc.sType = ST_MEMORY_ALLOCATE_INFO
        alloc.allocationSize = req.size
        alloc.memoryTypeIndex = self._memory_type(req.memoryTypeBits, mem_flags)
        mem = c_uint64()
        _check(self._vk.AllocateMemory(self._device, _addr(alloc), None, byref(mem)), "memory")
        _check(self._vk.BindBufferMemory(self._device, buf.value, mem.value, 0), "bind memory")
        return buf.value, mem.value, int(req.size)

    def _create_commands(self):
        pool_info = VkCommandPoolCreateInfo()
        pool_info.sType = ST_COMMAND_POOL
        pool_info.flags = CMD_POOL_RESET
        pool_info.queueFamilyIndex = self._queue_family
        pool = c_uint64()
        _check(self._vk.CreateCommandPool(self._device, _addr(pool_info), None, byref(pool)), "command pool")
        self._pool = pool.value

        frames = 2
        alloc = VkCommandBufferAllocateInfo()
        alloc.sType = ST_COMMAND_BUFFER_ALLOCATE
        alloc.commandPool = self._pool
        alloc.level = 0
        alloc.commandBufferCount = frames
        cmds = (c_void_p * frames)()
        self._cmd_alloc = alloc
        _check(self._vk.AllocateCommandBuffers(self._device, _addr(alloc), cmds), "command buffers")
        self._cmd = [cmds[i] for i in range(frames)]
        self._cmd_keep = cmds

        sem_info = VkSemaphoreCreateInfo()
        sem_info.sType = ST_SEMAPHORE_CREATE_INFO
        fence_info = VkFenceCreateInfo()
        fence_info.sType = ST_FENCE_CREATE_INFO
        fence_info.flags = FENCE_SIGNALED
        self._sync_info = (sem_info, fence_info)

        for _ in range(frames):
            sem = c_uint64()
            _check(self._vk.CreateSemaphore(self._device, _addr(sem_info), None, byref(sem)), "semaphore")
            self._image_available.append(sem.value)
            sem2 = c_uint64()
            _check(self._vk.CreateSemaphore(self._device, _addr(sem_info), None, byref(sem2)), "semaphore")
            self._render_finished.append(sem2.value)
            fence = c_uint64()
            _check(self._vk.CreateFence(self._device, _addr(fence_info), None, byref(fence)), "fence")
            self._fences.append(fence.value)
        self._frame = 0

    def _create_cover_texture(self):
        """Upload the single Bandcamp cover for Cosmic Dreamworlds (Liquid) into a Vulkan 2D Texture."""
        tw, th, rgba_bytes = load_preset_cover_rgba(self.preset, tex_size=1024)
        byte_len = len(rgba_bytes)

        staging_buf, staging_mem, _ = self._create_buffer(byte_len, BUFFER_USAGE_TRANSFER_SRC)
        ptr = c_void_p()
        _check(self._vk.MapMemory(self._device, staging_mem, 0, byte_len, 0, byref(ptr)), "map staging")
        ctypes.memmove(ptr, rgba_bytes, byte_len)
        self._vk.UnmapMemory(self._device, staging_mem)

        img_info = VkImageCreateInfo()
        img_info.sType = ST_IMAGE_CREATE_INFO
        img_info.imageType = IMAGE_TYPE_2D
        img_info.format = FORMAT_R8G8B8A8_UNORM
        img_info.extent = VkExtent3D(tw, th, 1)
        img_info.mipLevels = 1
        img_info.arrayLayers = 1
        img_info.samples = SAMPLE_1
        img_info.tiling = TILING_OPTIMAL
        img_info.usage = IMAGE_USAGE_TRANSFER_DST | IMAGE_USAGE_SAMPLED
        img_info.sharingMode = SHARING_EXCLUSIVE
        img_info.initialLayout = LAYOUT_UNDEFINED

        tex_img = c_uint64()
        _check(self._vk.CreateImage(self._device, _addr(img_info), None, byref(tex_img)), "create cover image")
        self._tex_image = tex_img.value

        req = VkMemoryRequirements()
        self._vk.GetImageMemoryRequirements(self._device, self._tex_image, _addr(req))
        alloc = VkMemoryAllocateInfo()
        alloc.sType = ST_MEMORY_ALLOCATE_INFO
        alloc.allocationSize = req.size
        try:
            alloc.memoryTypeIndex = self._memory_type(req.memoryTypeBits, MEMORY_DEVICE_LOCAL)
        except Exception:
            alloc.memoryTypeIndex = self._memory_type(req.memoryTypeBits, 0)
        tex_mem = c_uint64()
        _check(self._vk.AllocateMemory(self._device, _addr(alloc), None, byref(tex_mem)), "alloc cover mem")
        self._tex_memory = tex_mem.value
        _check(self._vk.BindImageMemory(self._device, self._tex_image, self._tex_memory, 0), "bind cover mem")

        # Transition image layout and copy staging buffer -> device image
        cmd_alloc = VkCommandBufferAllocateInfo()
        cmd_alloc.sType = ST_COMMAND_BUFFER_ALLOCATE
        cmd_alloc.commandPool = self._pool
        cmd_alloc.commandBufferCount = 1
        cmd = c_void_p()
        _check(self._vk.AllocateCommandBuffers(self._device, _addr(cmd_alloc), byref(cmd)), "tex cmd")

        begin = VkCommandBufferBeginInfo()
        begin.sType = ST_COMMAND_BUFFER_BEGIN
        begin.flags = CMD_ONE_TIME
        _check(self._vk.BeginCommandBuffer(cmd, _addr(begin)), "begin tex cmd")

        b1 = VkImageMemoryBarrier()
        b1.sType = ST_IMAGE_MEMORY_BARRIER
        b1.srcAccessMask = 0
        b1.dstAccessMask = ACCESS_TRANSFER_WRITE
        b1.oldLayout = LAYOUT_UNDEFINED
        b1.newLayout = LAYOUT_TRANSFER_DST
        b1.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        b1.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        b1.image = self._tex_image
        b1.subresourceRange = VkImageSubresourceRange(IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
        self._vk.CmdPipelineBarrier(cmd, STAGE_TOP, STAGE_TRANSFER, 0, 0, None, 0, None, 1, _addr(b1))

        region = VkBufferImageCopy()
        region.bufferOffset = 0
        region.bufferRowLength = 0
        region.bufferImageHeight = 0
        region.imageSubresource = VkImageSubresourceLayers(IMAGE_ASPECT_COLOR, 0, 0, 1)
        region.imageOffset = VkOffset3D(0, 0, 0)
        region.imageExtent = VkExtent3D(tw, th, 1)
        self._vk.CmdCopyBufferToImage(cmd, staging_buf, self._tex_image, LAYOUT_TRANSFER_DST, 1, _addr(region))

        b2 = VkImageMemoryBarrier()
        b2.sType = ST_IMAGE_MEMORY_BARRIER
        b2.srcAccessMask = ACCESS_TRANSFER_WRITE
        b2.dstAccessMask = ACCESS_SHADER_READ
        b2.oldLayout = LAYOUT_TRANSFER_DST
        b2.newLayout = LAYOUT_SHADER_READ_ONLY
        b2.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        b2.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        b2.image = self._tex_image
        b2.subresourceRange = VkImageSubresourceRange(IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
        self._vk.CmdPipelineBarrier(cmd, STAGE_TRANSFER, STAGE_FRAGMENT, 0, 0, None, 0, None, 1, _addr(b2))

        _check(self._vk.EndCommandBuffer(cmd), "end tex cmd")
        submit = VkSubmitInfo()
        submit.sType = ST_SUBMIT_INFO
        submit.commandBufferCount = 1
        submit.pCommandBuffers = ctypes.cast(byref(cmd), c_void_p)
        _check(self._vk.QueueSubmit(self._queue, 1, _addr(submit), 0), "submit tex cmd")
        _check(self._vk.QueueWaitIdle(self._queue), "wait tex upload")

        self._vk.DestroyBuffer(self._device, staging_buf, None)
        self._vk.FreeMemory(self._device, staging_mem, None)

        view_info = VkImageViewCreateInfo()
        view_info.sType = ST_IMAGE_VIEW_CREATE_INFO
        view_info.image = self._tex_image
        view_info.viewType = IMAGE_VIEW_2D
        view_info.format = FORMAT_R8G8B8A8_UNORM
        view_info.aspectMask = IMAGE_ASPECT_COLOR
        view_info.levelCount = 1
        view_info.layerCount = 1
        tview = c_uint64()
        _check(self._vk.CreateImageView(self._device, _addr(view_info), None, byref(tview)), "cover image view")
        self._tex_view = tview.value

        samp_info = VkSamplerCreateInfo()
        samp_info.sType = ST_SAMPLER_CREATE_INFO
        samp_info.magFilter = FILTER_LINEAR
        samp_info.minFilter = FILTER_LINEAR
        samp_info.mipmapMode = SAMPLER_MIPMAP_LINEAR
        samp_info.addressModeU = SAMPLER_ADDRESS_REPEAT
        samp_info.addressModeV = SAMPLER_ADDRESS_REPEAT
        samp_info.addressModeW = SAMPLER_ADDRESS_REPEAT
        samp_info.maxAnisotropy = 1.0
        samp_info.maxLod = 1.0
        sampler = c_uint64()
        _check(self._vk.CreateSampler(self._device, _addr(samp_info), None, byref(sampler)), "cover sampler")
        self._tex_sampler = sampler.value

    def _shader_module(self, path: Path) -> int:
        data = Path(path).read_bytes()
        if len(data) % 4:
            raise RuntimeError(f"{path} is not aligned SPIR-V")
        buf = (c_uint8 * len(data)).from_buffer_copy(data)
        info = VkShaderModuleCreateInfo()
        info.sType = ST_SHADER_MODULE_CREATE_INFO
        info.codeSize = len(data)
        info.pCode = ctypes.cast(buf, c_void_p)
        mod = c_uint64()
        self._shader_keep = getattr(self, "_shader_keep", [])
        self._shader_keep.append((buf, info))
        _check(self._vk.CreateShaderModule(self._device, _addr(info), None, byref(mod)), f"shader {path.name}")
        return mod.value

    def _create_pipeline(self):
        vert = self._shader_module(SHADER_DIR / "mp_liquid_visualizer.vert.spv")
        frag = self._shader_module(SHADER_DIR / "mp_liquid_visualizer.frag.spv")
        self._modules = [vert, frag]

        stages = (VkPipelineShaderStageCreateInfo * 2)()
        for stage, mod, bit in ((0, vert, SHADER_VERTEX), (1, frag, SHADER_FRAGMENT)):
            stages[stage].sType = ST_PIPELINE_SHADER_STAGE
            stages[stage].stage = bit
            stages[stage].module = mod
            stages[stage].pName = b"main"

        vertex = VkPipelineVertexInputStateCreateInfo()
        vertex.sType = ST_PIPELINE_VERTEX_INPUT
        assembly = VkPipelineInputAssemblyStateCreateInfo()
        assembly.sType = ST_PIPELINE_INPUT_ASSEMBLY
        assembly.topology = TOPOLOGY_TRIANGLE_LIST

        vp = VkViewport(0, 0, float(self._extent[0]), float(self._extent[1]), 0.0, 1.0)
        sc = VkRect2D(VkOffset2D(0, 0), VkExtent2D(self._extent[0], self._extent[1]))
        viewport = VkPipelineViewportStateCreateInfo()
        viewport.sType = ST_PIPELINE_VIEWPORT
        viewport.viewportCount = 1
        viewport.pViewports = _addr(vp)
        viewport.scissorCount = 1
        viewport.pScissors = _addr(sc)

        raster = VkPipelineRasterizationStateCreateInfo()
        raster.sType = ST_PIPELINE_RASTER
        raster.polygonMode = 0
        raster.lineWidth = 1.0

        multi = VkPipelineMultisampleStateCreateInfo()
        multi.sType = ST_PIPELINE_MULTISAMPLE
        multi.rasterizationSamples = SAMPLE_1

        blend_att = VkPipelineColorBlendAttachmentState()
        blend_att.colorWriteMask = COLOR_WRITE_ALL
        blend_att.blendEnable = 0
        blend = VkPipelineColorBlendStateCreateInfo()
        blend.sType = ST_PIPELINE_COLOR_BLEND
        blend.attachmentCount = 1
        blend.pAttachments = _addr(blend_att)

        dynamics = (c_uint32 * 2)(DYNAMIC_VIEWPORT, DYNAMIC_SCISSOR)
        dynamic = VkPipelineDynamicStateCreateInfo()
        dynamic.sType = ST_PIPELINE_DYNAMIC
        dynamic.dynamicStateCount = 2
        dynamic.pDynamicStates = ctypes.cast(dynamics, c_void_p)

        bindings = (VkDescriptorSetLayoutBinding * 2)()
        bindings[0].binding = 0
        bindings[0].descriptorType = DESCRIPTOR_UNIFORM
        bindings[0].descriptorCount = 1
        bindings[0].stageFlags = STAGE_VERTEX_BIT | STAGE_FRAGMENT_BIT

        bindings[1].binding = 1
        bindings[1].descriptorType = DESCRIPTOR_COMBINED_IMAGE_SAMPLER
        bindings[1].descriptorCount = 1
        bindings[1].stageFlags = STAGE_FRAGMENT_BIT

        set_info = VkDescriptorSetLayoutCreateInfo()
        set_info.sType = ST_DESCRIPTOR_SET_LAYOUT
        set_info.bindingCount = 2
        set_info.pBindings = ctypes.cast(bindings, c_void_p)
        desc_layout = c_uint64()
        _check(
            self._vk.CreateDescriptorSetLayout(self._device, _addr(set_info), None, byref(desc_layout)),
            "descriptor layout",
        )
        self._desc_layout = desc_layout.value

        layouts = (c_uint64 * 1)(self._desc_layout)
        pipe_layout_info = VkPipelineLayoutCreateInfo()
        pipe_layout_info.sType = ST_PIPELINE_LAYOUT
        pipe_layout_info.setLayoutCount = 1
        pipe_layout_info.pSetLayouts = ctypes.cast(layouts, c_void_p)
        layout = c_uint64()
        _check(
            self._vk.CreatePipelineLayout(self._device, _addr(pipe_layout_info), None, byref(layout)),
            "pipeline layout",
        )
        self._layout = layout.value

        gp = VkGraphicsPipelineCreateInfo()
        gp.sType = ST_GRAPHICS_PIPELINE
        gp.stageCount = 2
        gp.pStages = ctypes.cast(stages, c_void_p)
        gp.pVertexInputState = _addr(vertex)
        gp.pInputAssemblyState = _addr(assembly)
        gp.pViewportState = _addr(viewport)
        gp.pRasterizationState = _addr(raster)
        gp.pMultisampleState = _addr(multi)
        gp.pColorBlendState = _addr(blend)
        gp.pDynamicState = _addr(dynamic)
        gp.layout = self._layout
        gp.renderPass = self._render_pass
        gp.basePipelineIndex = -1
        self._pipe_keep = (
            stages, vertex, assembly, vp, sc, viewport, raster, multi,
            blend_att, blend, dynamics, dynamic, bindings, set_info, layouts,
            pipe_layout_info, gp,
        )
        pipeline = c_uint64()
        _check(
            self._vk.CreateGraphicsPipelines(self._device, 0, 1, _addr(gp), None, byref(pipeline)),
            "graphics pipeline",
        )
        self._pipeline = pipeline.value

    def _create_descriptors(self):
        ubo_size = ctypes.sizeof(VisualizerUBO)
        self._ubo, self._ubo_memory, _ = self._create_buffer(ubo_size, BUFFER_USAGE_UNIFORM)
        ptr = c_void_p()
        _check(self._vk.MapMemory(self._device, self._ubo_memory, 0, ubo_size, 0, byref(ptr)), "map ubo")
        self._ubo_ptr = ptr

        pool_sizes = (VkDescriptorPoolSize * 2)()
        pool_sizes[0] = VkDescriptorPoolSize(DESCRIPTOR_UNIFORM, 1)
        pool_sizes[1] = VkDescriptorPoolSize(DESCRIPTOR_COMBINED_IMAGE_SAMPLER, 1)

        pool_info = VkDescriptorPoolCreateInfo()
        pool_info.sType = ST_DESCRIPTOR_POOL
        pool_info.maxSets = 1
        pool_info.poolSizeCount = 2
        pool_info.pPoolSizes = ctypes.cast(pool_sizes, c_void_p)
        pool = c_uint64()
        _check(self._vk.CreateDescriptorPool(self._device, _addr(pool_info), None, byref(pool)), "descriptor pool")
        self._desc_pool = pool.value

        layouts = (c_uint64 * 1)(self._desc_layout)
        alloc_info = VkDescriptorSetAllocateInfo()
        alloc_info.sType = ST_DESCRIPTOR_SET_ALLOCATE
        alloc_info.descriptorPool = self._desc_pool
        alloc_info.descriptorSetCount = 1
        alloc_info.pSetLayouts = ctypes.cast(layouts, c_void_p)
        dset = c_uint64()
        self._desc_keep = (pool_sizes, pool_info, layouts, alloc_info)
        _check(self._vk.AllocateDescriptorSets(self._device, _addr(alloc_info), byref(dset)), "descriptor set")
        self._dset = dset.value

        buffer_info = VkDescriptorBufferInfo(self._ubo, 0, ubo_size)
        image_info = VkDescriptorImageInfo(self._tex_sampler, self._tex_view, LAYOUT_SHADER_READ_ONLY)

        writes = (VkWriteDescriptorSet * 2)()
        writes[0].sType = ST_WRITE_DESCRIPTOR_SET
        writes[0].dstSet = self._dset
        writes[0].dstBinding = 0
        writes[0].descriptorCount = 1
        writes[0].descriptorType = DESCRIPTOR_UNIFORM
        writes[0].pBufferInfo = _addr(buffer_info)

        writes[1].sType = ST_WRITE_DESCRIPTOR_SET
        writes[1].dstSet = self._dset
        writes[1].dstBinding = 1
        writes[1].descriptorCount = 1
        writes[1].descriptorType = DESCRIPTOR_COMBINED_IMAGE_SAMPLER
        writes[1].pImageInfo = _addr(image_info)

        self._write_keep = (buffer_info, image_info, writes)
        self._vk.UpdateDescriptorSets(self._device, 2, ctypes.cast(writes, c_void_p), 0, None)

    def _write_ubo(self, bridge: AudioTelemetryBridge):
        fw, fh = self._extent
        ubo = VisualizerUBO()
        ubo.res[:] = (
            float(fw),
            float(fh),
            float(bridge.accum_time),
            1.0 if bridge.is_playing else 0.0,
        )
        ubo.audio0[:] = (
            float(bridge.sub_bass),
            float(bridge.bass),
            float(bridge.low_mid),
            float(bridge.mid),
        )
        ubo.audio1[:] = (
            float(bridge.high_mid),
            float(bridge.treble),
            float(bridge.air),
            float(bridge.rms_energy),
        )
        ubo.audio2[:] = (
            float(bridge.beat_pulse),
            float(bridge.bass_phase),
            float(bridge.mid_phase),
            float(bridge.high_phase),
        )
        b = bridge.bands16
        ubo.bands0[:] = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        ubo.bands1[:] = (float(b[4]), float(b[5]), float(b[6]), float(b[7]))
        ubo.bands2[:] = (float(b[8]), float(b[9]), float(b[10]), float(b[11]))
        ubo.bands3[:] = (float(b[12]), float(b[13]), float(b[14]), float(b[15]))
        ubo.preset[:] = (
            float(self.preset["id"]),
            float(bridge.pitch_factor),
            1.0,
            0.0,
        )
        ctypes.memmove(self._ubo_ptr, byref(ubo), ctypes.sizeof(ubo))

    def draw(self, bridge: AudioTelemetryBridge, capture: bool = False):
        if not self.poll():
            return None
        self._write_ubo(bridge)
        return self._render(capture)

    def _render(self, capture: bool):
        vk = self._vk
        frame = self._frame
        fence = self._fences[frame]
        _check(vk.WaitForFences(self._device, 1, byref(c_uint64(fence)), 1, 2_000_000_000), "wait fence")
        index = c_uint32()
        acquired = vk.AcquireNextImageKHR(
            self._device, self._swapchain, 2_000_000_000,
            self._image_available[frame], 0, byref(index),
        )
        if acquired in (OUT_OF_DATE, SUBOPTIMAL):
            return None
        _check(acquired, "acquire")
        _check(vk.ResetFences(self._device, 1, byref(c_uint64(fence))), "reset fence")
        cmd = self._cmd[frame]
        _check(vk.ResetCommandBuffer(cmd, 0), "reset command")

        begin = VkCommandBufferBeginInfo()
        begin.sType = ST_COMMAND_BUFFER_BEGIN
        begin.flags = CMD_ONE_TIME
        _check(vk.BeginCommandBuffer(cmd, _addr(begin)), "begin command")

        barrier = VkBufferMemoryBarrier()
        barrier.sType = ST_BUFFER_MEMORY_BARRIER
        barrier.srcAccessMask = ACCESS_HOST_WRITE
        barrier.dstAccessMask = ACCESS_UNIFORM
        barrier.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.buffer = self._ubo
        barrier.size = ctypes.sizeof(VisualizerUBO)
        vk.CmdPipelineBarrier(cmd, STAGE_HOST, STAGE_FRAGMENT, 0, 0, None, 1, _addr(barrier), 0, None)

        clear = VkClearValue()
        clear.color[:] = (0.0, 0.0, 0.0, 1.0)
        rp = VkRenderPassBeginInfo()
        rp.sType = ST_RENDER_PASS_BEGIN
        rp.renderPass = self._render_pass
        rp.framebuffer = self._framebuffers[index.value]
        rp.renderArea.extent = VkExtent2D(*self._extent)
        rp.clearValueCount = 1
        rp.pClearValues = _addr(clear)
        vk.CmdBeginRenderPass(cmd, _addr(rp), 0)
        vk.CmdBindPipeline(cmd, 0, self._pipeline)

        view = VkViewport(0.0, 0.0, float(self._extent[0]), float(self._extent[1]), 0.0, 1.0)
        scissor = VkRect2D(VkOffset2D(0, 0), VkExtent2D(self._extent[0], self._extent[1]))
        vk.CmdSetViewport(cmd, 0, 1, c_void_p(ctypes.addressof(view)))
        vk.CmdSetScissor(cmd, 0, 1, c_void_p(ctypes.addressof(scissor)))
        self._vbind_keep = (view, scissor)

        dset = c_uint64(self._dset)
        vk.CmdBindDescriptorSets(cmd, 0, self._layout, 0, 1, ctypes.cast(byref(dset), c_void_p), 0, None)
        vk.CmdDraw(cmd, 3, 1, 0, 0)
        vk.CmdEndRenderPass(cmd)
        _check(vk.EndCommandBuffer(cmd), "end command")

        wait_sem = c_uint64(self._image_available[frame])
        signal_sem = c_uint64(self._render_finished[frame])
        wait_stage = c_uint32(STAGE_COLOR_OUT)
        cmd_keep = c_void_p(cmd)
        submit = VkSubmitInfo()
        submit.sType = ST_SUBMIT_INFO
        submit.waitSemaphoreCount = 1
        submit.pWaitSemaphores = ctypes.cast(byref(wait_sem), c_void_p)
        submit.pWaitDstStageMask = ctypes.cast(byref(wait_stage), c_void_p)
        submit.commandBufferCount = 1
        submit.pCommandBuffers = ctypes.cast(byref(cmd_keep), c_void_p)
        submit.signalSemaphoreCount = 1
        submit.pSignalSemaphores = ctypes.cast(byref(signal_sem), c_void_p)
        _check(vk.QueueSubmit(self._queue, 1, _addr(submit), fence), "queue submit")

        pixels = None
        if capture and self._can_readback:
            _check(vk.WaitForFences(self._device, 1, byref(c_uint64(fence)), 1, 2_000_000_000), "wait draw")
            pixels = self._read_image(self._images[index.value])

        swap = c_uint64(self._swapchain)
        present = VkPresentInfoKHR()
        present.sType = ST_PRESENT_INFO
        present.waitSemaphoreCount = 1
        present.pWaitSemaphores = ctypes.cast(byref(signal_sem), c_void_p)
        present.swapchainCount = 1
        present.pSwapchains = ctypes.cast(byref(swap), c_void_p)
        present.pImageIndices = ctypes.cast(byref(index), c_void_p)
        presented = vk.QueuePresentKHR(self._queue, _addr(present))
        if presented not in (SUCCESS, OUT_OF_DATE, SUBOPTIMAL):
            _check(presented, "present")

        self._frame = (frame + 1) % 2
        self._frame_keep = (begin, barrier, clear, rp, wait_sem, signal_sem, wait_stage, cmd_keep, submit, swap, present, index)
        return pixels

    def _ensure_readback(self):
        byte_count = self._extent[0] * self._extent[1] * 4
        if self._readback_buffer and self._readback_bytes >= byte_count:
            return
        self._destroy_readback()
        buf, mem, size = self._create_buffer(byte_count, BUFFER_USAGE_TRANSFER_DST)
        ptr = c_void_p()
        _check(self._vk.MapMemory(self._device, mem, 0, size, 0, byref(ptr)), "map readback")
        self._readback_buffer = buf
        self._readback_memory = mem
        self._readback_ptr = ptr
        self._readback_bytes = byte_count

    def _destroy_readback(self):
        if self._readback_memory:
            self._vk.UnmapMemory(self._device, self._readback_memory)
            self._vk.DestroyBuffer(self._device, self._readback_buffer, None)
            self._vk.FreeMemory(self._device, self._readback_memory, None)
        self._readback_buffer = 0
        self._readback_memory = 0
        self._readback_ptr = None
        self._readback_bytes = 0

    def _read_image(self, image: int):
        self._ensure_readback()
        vk = self._vk
        alloc = VkCommandBufferAllocateInfo()
        alloc.sType = ST_COMMAND_BUFFER_ALLOCATE
        alloc.commandPool = self._pool
        alloc.commandBufferCount = 1
        cmd = c_void_p()
        _check(vk.AllocateCommandBuffers(self._device, _addr(alloc), byref(cmd)), "readback command")
        begin = VkCommandBufferBeginInfo()
        begin.sType = ST_COMMAND_BUFFER_BEGIN
        begin.flags = CMD_ONE_TIME
        _check(vk.BeginCommandBuffer(cmd, _addr(begin)), "begin readback")

        barrier = VkImageMemoryBarrier()
        barrier.sType = ST_IMAGE_MEMORY_BARRIER
        barrier.srcAccessMask = ACCESS_MEMORY_READ
        barrier.dstAccessMask = ACCESS_TRANSFER_READ
        barrier.oldLayout = LAYOUT_PRESENT
        barrier.newLayout = LAYOUT_TRANSFER_SRC
        barrier.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        barrier.image = image
        barrier.subresourceRange = VkImageSubresourceRange(IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
        vk.CmdPipelineBarrier(cmd, STAGE_BOTTOM, STAGE_TRANSFER, 0, 0, None, 0, None, 1, _addr(barrier))

        region = VkBufferImageCopy()
        region.imageSubresource = VkImageSubresourceLayers(IMAGE_ASPECT_COLOR, 0, 0, 1)
        region.imageExtent = VkExtent3D(self._extent[0], self._extent[1], 1)
        vk.CmdCopyImageToBuffer(cmd, image, LAYOUT_TRANSFER_SRC, self._readback_buffer, 1, _addr(region))

        back = VkImageMemoryBarrier()
        back.sType = ST_IMAGE_MEMORY_BARRIER
        back.srcAccessMask = ACCESS_TRANSFER_READ
        back.dstAccessMask = ACCESS_MEMORY_READ
        back.oldLayout = LAYOUT_TRANSFER_SRC
        back.newLayout = LAYOUT_PRESENT
        back.srcQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        back.dstQueueFamilyIndex = QUEUE_FAMILY_IGNORED
        back.image = image
        back.subresourceRange = VkImageSubresourceRange(IMAGE_ASPECT_COLOR, 0, 1, 0, 1)
        vk.CmdPipelineBarrier(cmd, STAGE_TRANSFER, STAGE_BOTTOM, 0, 0, None, 0, None, 1, _addr(back))

        _check(vk.EndCommandBuffer(cmd), "end readback")
        submit = VkSubmitInfo()
        submit.sType = ST_SUBMIT_INFO
        submit.commandBufferCount = 1
        submit.pCommandBuffers = ctypes.cast(byref(cmd), c_void_p)
        _check(vk.QueueSubmit(self._queue, 1, _addr(submit), 0), "submit readback")
        _check(vk.QueueWaitIdle(self._queue), "readback idle")
        byte_count = self._extent[0] * self._extent[1] * 4
        raw = ctypes.string_at(self._readback_ptr, byte_count)
        self._read_keep = (alloc, begin, barrier, region, back, submit)
        return self._extent[0], self._extent[1], raw

    def close(self):
        if not self._alive:
            self._destroy_window()
            return
        try:
            self._vk.DeviceWaitIdle(self._device)
        except Exception:
            pass
        self._destroy_readback()
        if self._tex_sampler:
            self._vk.DestroySampler(self._device, self._tex_sampler, None)
        if self._tex_view:
            self._vk.DestroyImageView(self._device, self._tex_view, None)
        if self._tex_image:
            self._vk.DestroyImage(self._device, self._tex_image, None)
        if self._tex_memory:
            self._vk.FreeMemory(self._device, self._tex_memory, None)
        for fence in self._fences:
            self._vk.DestroyFence(self._device, fence, None)
        for sem in self._image_available + self._render_finished:
            self._vk.DestroySemaphore(self._device, sem, None)
        if getattr(self, "_pool", 0):
            self._vk.DestroyCommandPool(self._device, self._pool, None)
        for fb in self._framebuffers:
            self._vk.DestroyFramebuffer(self._device, fb, None)
        for view in self._views:
            self._vk.DestroyImageView(self._device, view, None)
        if getattr(self, "_pipeline", 0):
            self._vk.DestroyPipeline(self._device, self._pipeline, None)
        if getattr(self, "_layout", 0):
            self._vk.DestroyPipelineLayout(self._device, self._layout, None)
        if getattr(self, "_render_pass", 0):
            self._vk.DestroyRenderPass(self._device, self._render_pass, None)
        if getattr(self, "_desc_pool", 0):
            self._vk.DestroyDescriptorPool(self._device, self._desc_pool, None)
        if getattr(self, "_desc_layout", 0):
            self._vk.DestroyDescriptorSetLayout(self._device, self._desc_layout, None)
        if getattr(self, "_ubo", 0):
            self._vk.UnmapMemory(self._device, self._ubo_memory)
            self._vk.DestroyBuffer(self._device, self._ubo, None)
        if getattr(self, "_ubo_memory", 0):
            self._vk.FreeMemory(self._device, self._ubo_memory, None)
        for mod in getattr(self, "_modules", []):
            self._vk.DestroyShaderModule(self._device, mod, None)
        if self._swapchain:
            self._vk.DestroySwapchainKHR(self._device, self._swapchain, None)
        self._vk.DestroyDevice(self._device, None)
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
    raw = bytearray(bgra)
    if swap_rb:
        for i in range(0, len(raw), 4):
            raw[i], raw[i + 2] = raw[i + 2], raw[i]
    image = Image.frombytes("RGBA", (width, height), bytes(raw))
    image.save(path)
    return image


def run_self_test(png_path: Optional[Union[str, Path]] = None) -> str:
    """Verify 1400x1400 borderless Vulkan rendering, cover texture binding, and pause/play freeze behavior."""
    renderer = LiquidVisualizerVulkanRenderer("Cosmic Dreamworlds (Liquid)")
    bridge = AudioTelemetryBridge()
    try:
        renderer.open()
        ww, wh = renderer.window_size()
        if (ww, wh) != (1400, 1400):
            raise RuntimeError(f"Expected fixed 1400x1400 window, got {ww}x{wh}")

        # 1. Verify active playing state advances 3D generation
        for _ in range(5):
            bridge.update(0.12, force_playing=True, synthetic_audio=True)
            renderer.draw(bridge, capture=False)
        t_playing = bridge.accum_time
        if t_playing <= 0.0:
            raise RuntimeError("accum_time did not advance while playing")

        # 2. Verify paused/stopped state freezes 3D generation in-place
        bridge.update(0.50, force_playing=False, synthetic_audio=True)
        if bridge.accum_time != t_playing:
            raise RuntimeError("accum_time advanced while music was stopped/paused")

        # 3. Capture rendered 1400x1400 frame
        bridge.update(0.15, force_playing=True, synthetic_audio=True)
        pixels = renderer.draw(bridge, capture=True)
        if not pixels:
            raise RuntimeError("Vulkan swapchain did not produce a readable 1400x1400 frame")
        width, height, bgra = pixels
        if (width, height) != (1400, 1400):
            raise RuntimeError(f"Expected 1400x1400 framebuffer, got {width}x{height}")

        if png_path:
            save_png(png_path, width, height, bgra, swap_rb=(renderer.format != FORMAT_R8G8B8A8_UNORM))

        print(f"MP_LIQUID_VISUALIZER_OK {renderer.summary}", flush=True)
        return renderer.summary
    finally:
        renderer.close()


def run_visualizer(preset_name: Optional[str] = None, max_seconds: Optional[float] = None) -> int:
    renderer = LiquidVisualizerVulkanRenderer(preset_name)
    bridge = AudioTelemetryBridge()
    renderer.open()
    last_t = time.monotonic()
    start_t = last_t
    try:
        while not renderer.should_close:
            now = time.monotonic()
            dt = now - last_t
            last_t = now
            if max_seconds is not None and (now - start_t) >= max_seconds:
                break
            bridge.update(dt)
            renderer.draw(bridge, capture=False)
            time.sleep(0.008)
    except KeyboardInterrupt:
        pass
    finally:
        renderer.close()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="MP_Liquid_Visualizer",
        description="MP_Liquid_Visualizer — Native Vulkan 1400x1400 Borderless 3D Audio-Reactive Visualizer",
    )
    parser.add_argument("--preset", type=str, default=None, help="Select visualizer preset by name, key, or ID")
    parser.add_argument("--set-preset", type=str, default=None, help="Persist active preset and exit")
    parser.add_argument("--list-presets", action="store_true", help="List available visualizer presets and exit")
    parser.add_argument("--self-test", action="store_true", help="Run Vulkan 1400x1400 render & pause/play verification")
    parser.add_argument("--png", type=str, default=None, help="Output PNG path when running --self-test")
    parser.add_argument("--max-seconds", type=float, default=None, help="Optional maximum runtime in seconds")
    args = parser.parse_args(argv)

    if args.list_presets:
        active = get_active_preset()
        for p in VISUALIZER_PRESETS:
            marker = "*" if p["key"] == active["key"] else " "
            print(f"[{marker}] {p['id'] + 1}. {p['name']} ({p['key']}) — Cover: {p['album']}")
        return 0

    if args.set_preset is not None:
        saved = save_active_preset(args.set_preset)
        print(f"Active Preset set to: {saved['name']} ({saved['key']})")
        return 0

    if args.preset is not None:
        save_active_preset(args.preset)

    if args.self_test:
        run_self_test(args.png)
        return 0

    return run_visualizer(preset_name=args.preset, max_seconds=args.max_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
