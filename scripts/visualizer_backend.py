"""Backend selection for the MP Visualizer.

The Liquid Glass *player* backend and the *visualizer* backend are separate
choices. ``LIQUID_GLASS_BACKEND`` picks the player host (OpenGL by default,
Vulkan when configured). The visualizer follows that same setting when it is
running as a window inside the player or MP Gui, because the drawing context
is the host's. When the visualizer runs standalone it picks for itself:

``VISUALIZER_BACKEND``
    ``auto`` (default), ``opengl``, or ``vulkan``.
    ``auto`` uses Vulkan when a working loader and at least one physical
    device are present, and OpenGL otherwise.

The user's configured Liquid Glass backend is honoured first: an explicit
``opengl`` there selects the OpenGL visualizer, and ``vulkan`` selects the
Vulkan one. An explicit ``VISUALIZER_BACKEND`` always wins.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG_ENV = Path.home() / ".config" / "mix-manager" / "config.env"

BACKEND_OPENGL = "opengl"
BACKEND_VULKAN = "vulkan"
BACKEND_AUTO = "auto"

_ALIASES = {
    "gl": BACKEND_OPENGL,
    "opengl": BACKEND_OPENGL,
    "ogl": BACKEND_OPENGL,
    "vk": BACKEND_VULKAN,
    "vulkan": BACKEND_VULKAN,
    "auto": BACKEND_AUTO,
    "": BACKEND_AUTO,
}


def _read_config_value(key: str, path: Optional[Path] = None) -> str:
    """Read ``KEY=value`` from config.env without importing the manager."""
    candidate = CONFIG_ENV if path is None else Path(path)
    try:
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    prefix = key + "="
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(prefix):
            continue
        value = line[len(prefix):].strip()
        return value.strip("\"'")
    return ""


def normalise(value: Optional[str]) -> str:
    """Map a backend name, including ``gl``/``vk`` aliases, to a canonical one."""
    return _ALIASES.get((value or "").strip().lower(), BACKEND_AUTO)


def configured_backend(path: Optional[Path] = None) -> str:
    """The Liquid Glass backend the user configured for the player."""
    for key in ("VISUALIZER_BACKEND", "LIQUID_GLASS_BACKEND"):
        value = os.environ.get(key, "").strip()
        if value:
            return normalise(value)
    for key in ("VISUALIZER_BACKEND", "LIQUID_GLASS_BACKEND"):
        value = _read_config_value(key, path)
        if value:
            return normalise(value)
    return BACKEND_AUTO


def vulkan_available() -> bool:
    """True when a Vulkan loader and at least one physical device are present.

    No window or surface is created. A GPU that advertises Vulkan but cannot
    present is still a Vulkan GPU, and the renderer reports a surface failure
    itself. A loader alone is not enough: Windows ships ``vulkan-1.dll`` with
    no ICD behind it, and Linux can have libvulkan installed with no driver.
    """
    try:
        from mp_liquid_visualizer_vulkan import load_vulkan_dll
    except ImportError:
        try:
            from scripts.mp_liquid_visualizer_vulkan import load_vulkan_dll
        except ImportError:
            return False
    try:
        loader = load_vulkan_dll()
    except Exception:
        return False
    if loader is None:
        return False
    return _device_count(loader) > 0


def _device_count(loader) -> int:
    """Enumerate physical devices with the smallest possible instance."""
    import ctypes
    from ctypes import POINTER, byref, c_char_p, c_int32, c_uint32, c_void_p

    VK_SUCCESS = 0

    def _proc(name):
        addr = loader.vkGetInstanceProcAddr
        addr.restype = c_void_p
        addr.argtypes = [c_void_p, c_char_p]
        return addr(None, name.encode())

    create_addr = _proc("vkCreateInstance")
    if not create_addr:
        return 0
    create = ctypes.CFUNCTYPE(c_int32, c_void_p, c_void_p, POINTER(c_void_p))(create_addr)

    class ApplicationInfo(ctypes.Structure):
        _fields_ = [
            ("sType", c_uint32), ("pNext", c_void_p), ("pApplicationName", c_char_p),
            ("applicationVersion", c_uint32), ("pEngineName", c_char_p),
            ("engineVersion", c_uint32), ("apiVersion", c_uint32),
        ]

    class InstanceInfo(ctypes.Structure):
        _fields_ = [
            ("sType", c_uint32), ("pNext", c_void_p), ("flags", c_uint32),
            ("pApplicationInfo", c_void_p), ("enabledLayerCount", c_uint32),
            ("ppEnabledLayerNames", c_void_p), ("enabledExtensionCount", c_uint32),
            ("ppEnabledExtensionNames", c_void_p),
        ]

    app = ApplicationInfo(0, None, b"MP Visualizer probe", 1, b"probe", 1, (1 << 22))
    info = InstanceInfo(1, None, 0, ctypes.cast(byref(app), c_void_p), 0, None, 0, None)
    instance = c_void_p()
    if create(ctypes.cast(byref(info), c_void_p), None, byref(instance)) != VK_SUCCESS or not instance:
        return 0
    try:
        enum_addr = _proc("vkEnumeratePhysicalDevices")
        if not enum_addr:
            return 0
        enum = ctypes.CFUNCTYPE(c_int32, c_void_p, POINTER(c_uint32), c_void_p)(enum_addr)
        count = c_uint32(0)
        if enum(instance, byref(count), None) != VK_SUCCESS:
            return 0
        return int(count.value)
    finally:
        destroy_addr = _proc("vkDestroyInstance")
        if destroy_addr:
            ctypes.CFUNCTYPE(None, c_void_p, c_void_p)(destroy_addr)(instance, None)


def resolve(force: Optional[str] = None, *, probe: bool = True,
            config_path: Optional[Path] = None) -> str:
    """Return ``opengl`` or ``vulkan`` for the standalone visualizer.

    ``force`` is the ``--backend`` command line value. It may be ``auto``.
    """
    requested = normalise(force if force else configured_backend(config_path))
    if requested in (BACKEND_OPENGL, BACKEND_VULKAN):
        return requested
    if not probe:
        return BACKEND_VULKAN
    return BACKEND_VULKAN if vulkan_available() else BACKEND_OPENGL


def renderer_class(backend: str):
    """The renderer class for a canonical backend name."""
    if normalise(backend) == BACKEND_OPENGL:
        try:
            from liquid_player_visualizer import LiquidVisualizerOpenGLRenderer as cls
        except ImportError:
            from scripts.liquid_player_visualizer import LiquidVisualizerOpenGLRenderer as cls
        return cls
    try:
        from mp_liquid_visualizer_vulkan import LiquidVisualizerVulkanRenderer as cls
    except ImportError:
        from scripts.mp_liquid_visualizer_vulkan import LiquidVisualizerVulkanRenderer as cls
    return cls
