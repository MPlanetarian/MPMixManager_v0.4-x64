"""OpenGL liquid-glass window supporting wide GPU hardware (AMD Radeon, Intel, NVIDIA, older GPUs).

The glass is rendered with OpenGL (Core 3.3+ with compatibility fallback) on any available GPU.
GLFW supplies the X11 window and OpenGL context. The clear pane is achieved via KWin's
blur-behind and window opacity over the light frosted glass drawn by the GLSL shader.
"""

from __future__ import annotations

import os

# Ensure PyOpenGL uses the GLX platform when running on X11
os.environ.setdefault("PYOPENGL_PLATFORM", "glx")

import colorsys
import ctypes
import math
import sys
import time
from ctypes import (
    CFUNCTYPE,
    POINTER,
    byref,
    c_char,
    c_char_p,
    c_double,
    c_float,
    c_int,
    c_size_t,
    c_uint,
    c_uint32,
    c_uint64,
    c_void_p,
)
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHADER_DIR = ROOT / "shaders"

THEME_COLORS = {
    "dreamworlds_ultra": ((166, 77, 255), (247, 37, 133), (0, 229, 255)),
    "dynamic_rainbow_liquid_glass": ((176, 88, 255), (255, 45, 142), (0, 242, 254)),
    "dreamworlds_liquid": ((0, 245, 255), (199, 125, 255), (72, 149, 239)),
    "cosmic_supernova": ((224, 86, 253), (0, 245, 212), (76, 201, 240)),
    "dreamworlds_neon": ((0, 229, 255), (247, 37, 133), (102, 102, 255)),
    "retro_studio": ((241, 196, 15), (230, 126, 34), (243, 156, 18)),
    "cyber_neon": ((76, 201, 240), (255, 0, 85), (153, 153, 255)),
    "phosphor": ((57, 255, 20), (166, 255, 0), (0, 255, 102)),
    "ice_cold": ((0, 229, 255), (136, 192, 208), (129, 161, 193)),
    "retro_terminal": ((230, 230, 230), (180, 180, 180), (255, 255, 255)),
}
THEME_ALIASES = {
    "dreamworlds": "dreamworlds_ultra",
    "default": "dreamworlds_ultra",
    "mplanetarian": "dreamworlds_ultra",
    "dynamic_rainbow_liquid_glass": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_rainbow": "dynamic_rainbow_liquid_glass",
    "dynamic_rainbow": "dynamic_rainbow_liquid_glass",
    "rainbow_liquid_glass": "dynamic_rainbow_liquid_glass",
    "rainbow": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_[rainbow_colours]_(new)": "dynamic_rainbow_liquid_glass",
    "dynamic_liquid_glass_[rainbow_colours]": "dynamic_rainbow_liquid_glass",
    "dynamic liquid glass [rainbow colours] (new)": "dynamic_rainbow_liquid_glass",
    "dynamic liquid glass [rainbow colours]": "dynamic_rainbow_liquid_glass",
    "mp_dreamworlds_liquid_transparency": "dreamworlds_liquid",
    "dreamworlds_liquid_transparency": "dreamworlds_liquid",
    "liquid_transparency": "dreamworlds_liquid",
    "liquid": "dreamworlds_liquid",
    "glass": "dreamworlds_liquid",
    "liquid_glass": "dreamworlds_liquid",
    "cosmic": "cosmic_supernova",
    "supernova": "cosmic_supernova",
    "cyberpunk": "cyber_neon",
    "cyber": "cyber_neon",
    "matrix": "phosphor",
    "nord": "ice_cold",
    "dracula": "dreamworlds_neon",
    "gruvbox": "retro_studio",
    "unix_terminal": "retro_terminal",
    "terminal": "retro_terminal",
    "classic": "retro_terminal",
}

# GLFW Constants
GLFW_RESIZABLE = 0x00020003
GLFW_VISIBLE = 0x00020004
GLFW_DECORATED = 0x00020005
GLFW_FOCUSED = 0x00020001
GLFW_TRANSPARENT = 0x0002000A
GLFW_FOCUS_ON_SHOW = 0x0002000C
GLFW_CLIENT_API = 0x00022001
GLFW_OPENGL_API = 0x00030001
GLFW_CONTEXT_VERSION_MAJOR = 0x00022002
GLFW_CONTEXT_VERSION_MINOR = 0x00022003
GLFW_OPENGL_FORWARD_COMPAT = 0x00022006
GLFW_OPENGL_PROFILE = 0x00022008
GLFW_OPENGL_CORE_PROFILE = 0x00032001
GLFW_PLATFORM = 0x00050003
GLFW_PLATFORM_X11 = 0x00060004
GLFW_PRESS = 1
GLFW_RELEASE = 0


def theme_rgb(name):
    key = THEME_ALIASES.get(str(name or "").strip().lower(), str(name or "").strip().lower())
    return THEME_COLORS.get(key, THEME_COLORS["dreamworlds_ultra"])


def get_dynamic_theme_state(theme_name, base_opacity=1.0, current_time=None):
    """
    For 'dynamic_rainbow_liquid_glass':
    - Dynamically cycles liquid glass through all rainbow colors slowly over time.
    - Oscillates transparency between -9% and +9% over a 6-second period.
    Returns (colors_tuple, effective_opacity, transparency_factor).
    """
    key = THEME_ALIASES.get(str(theme_name or "").strip().lower(), str(theme_name or "").strip().lower())
    if key == "dynamic_rainbow_liquid_glass":
        t = time.time() if current_time is None else current_time
        # 1. Dynamic rainbow colors: smooth 18-second sweep through all rainbow hues
        h0 = (t / 18.0) % 1.0
        hA = h0
        hB = (h0 + 0.16) % 1.0
        hC = (h0 + 0.40) % 1.0
        rA, gA, bA = [int(round(c * 255)) for c in colorsys.hsv_to_rgb(hA, 0.88, 1.0)]
        rB, gB, bB = [int(round(c * 255)) for c in colorsys.hsv_to_rgb(hB, 0.94, 0.98)]
        rC, gC, bC = [int(round(c * 255)) for c in colorsys.hsv_to_rgb(hC, 0.92, 1.0)]
        colors = ((rA, gA, bA), (rB, gB, bB), (rC, gC, bC))

        # 2. Dynamic transparency oscillation: alternating between -9% and +9% over a 6-second period
        omega = 2.0 * math.pi / 6.0
        transparency_factor = 1.0 + 0.09 * math.sin(omega * t)
        effective_opacity = max(0.01, min(1.20, float(base_opacity) * transparency_factor))
        return colors, effective_opacity, transparency_factor

    colors = theme_rgb(theme_name)
    return colors, float(base_opacity), 1.0


def read_player_theme(config_dir=None):
    path = Path(config_dir) if config_dir else Path.home() / ".config" / "mix-manager"
    theme_file = path / "theme"
    try:
        name = theme_file.read_text(encoding="utf-8").strip().lower()
    except OSError:
        name = "dreamworlds_ultra"
    return name or "dreamworlds_ultra"


def _rgb01(rgb):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


FALLBACK_VERT_SRC = """#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;
out vec2 vUv;
void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

FALLBACK_FRAG_SRC = """#version 330 core
in vec2 vUv;
out vec4 outColor;

uniform vec4 u_res;
uniform vec4 u_themeA;
uniform vec4 u_themeB;
uniform vec4 u_themeC;
uniform vec4 u_bezel;
uniform vec4 u_panel0;
uniform vec4 u_panel1;

struct GlassUBO_t {
    vec4 res;
    vec4 themeA;
    vec4 themeB;
    vec4 themeC;
    vec4 bezel;
    vec4 panel0;
    vec4 panel1;
};

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p = p * 2.03 + vec2(1.7, 9.2);
        a *= 0.5;
    }
    return v;
}

float sdRoundRect(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float panelMask(vec2 frag, vec4 r) {
    if (r.z < 4.0 || r.w < 4.0) {
        return 0.0;
    }
    vec2 halfSize = 0.5 * r.zw;
    float rad = clamp(min(halfSize.x, halfSize.y) * 0.18, 8.0, 22.0);
    float d = sdRoundRect(frag - (r.xy + halfSize), halfSize, rad);
    float body = 1.0 - smoothstep(-0.5, 1.5, d);
    return body;
}

void main() {
    GlassUBO_t u = GlassUBO_t(u_res, u_themeA, u_themeB, u_themeC, u_bezel, u_panel0, u_panel1);

    vec2 frag = vUv * u.res.xy;
    vec2 center = 0.5 * u.res.xy;
    vec2 p = frag - center;
    float rad = u.bezel.y;

    vec2 halfSize = center - vec2(1.0);
    float outer = sdRoundRect(p, halfSize, rad);
    if (outer > 0.6) {
        outColor = vec4(0.0);
        return;
    }

    vec3 hi = u.themeA.rgb;
    vec3 accent = u.themeB.rgb;
    vec3 refl = u.themeC.rgb;
    vec3 theme = mix(hi, accent, 0.42);
    theme = mix(theme, refl, 0.20);

    vec2 uv = frag / u.res.xy;
    float n = fbm(uv * 4.6);
    float n2 = fbm(uv * 9.5 + vec2(3.1, 8.4));
    float caust = smoothstep(0.58, 0.86, n);
    float caustFine = smoothstep(0.74, 0.92, n2);

    vec3 water = vec3(0.76, 0.80, 0.87);
    water = mix(water, theme, 0.22);
    water += theme * (caust * 0.16 + caustFine * 0.08);
    water += vec3(0.95, 0.97, 1.0) * caustFine * 0.04;

    float title = panelMask(frag, u.panel0);
    float library = panelMask(frag, u.panel1);
    float panel = max(title, library);
    vec3 panelCol = mix(vec3(0.34, 0.36, 0.44), theme, 0.34);
    water = mix(water, panelCol, panel * 0.82);
    float panelLip = 0.0;
    if (u.panel0.z > 4.0) {
        vec2 h0 = 0.5 * u.panel0.zw;
        float d0 = sdRoundRect(frag - (u.panel0.xy + h0), h0, 14.0);
        panelLip = max(panelLip, exp(-pow((abs(d0) - 1.5) / 2.2, 2.0)));
    }
    if (u.panel1.z > 4.0) {
        vec2 h1 = 0.5 * u.panel1.zw;
        float d1 = sdRoundRect(frag - (u.panel1.xy + h1), h1, 16.0);
        panelLip = max(panelLip, exp(-pow((abs(d1) - 1.5) / 2.4, 2.0)));
    }
    water += mix(vec3(1.0), theme, 0.45) * panelLip * 0.22;

    float edge = max(-outer, 0.0);
    float large = exp(-pow((edge - 6.5) / 5.0, 2.0));
    float shoulder = exp(-pow((edge - 16.0) / 4.2, 2.0));
    float echo = exp(-pow((edge - 46.0) / 9.0, 2.0));
    float echoFar = exp(-pow((edge - 84.0) / 7.0, 2.0));
    float hair = 1.0 - smoothstep(0.15, 2.0, edge);
    float toe = smoothstep(20.0, 28.0, edge) * (1.0 - smoothstep(28.0, 36.0, edge));

    vec2 beadCell = floor(frag / 6.5);
    float bead = step(0.84, hash(beadCell)) * step(edge, 24.0) * step(2.0, edge);
    float glint = step(0.94, hash(floor(frag / 3.0) + vec2(4.0, 1.0))) * step(edge, 12.0) * step(1.0, edge);

    vec3 col = water;
    col = mix(col, mix(vec3(1.0), theme, 0.28), large * 0.80);
    col = mix(col, mix(theme, vec3(1.0), 0.25), shoulder * 0.55);
    col += mix(theme, vec3(1.0), 0.35) * echo * 0.16;
    col += theme * echoFar * 0.08;
    col = mix(col, col * vec3(0.72, 0.76, 0.84), toe * 0.65);
    col = mix(col, vec3(1.0), hair);
    col = mix(col, mix(vec3(1.0), theme, 0.15), bead * 0.9);
    col += vec3(1.0) * glint * 0.75;

    vec2 m = vec2(u.themeA.w, u.themeB.w);
    vec2 lp = (m - uv) * vec2(max(u.res.w, 0.5), 1.0);
    float spec = pow(max(0.0, 1.0 - length(lp) * 1.8), 8.0);
    col += vec3(1.0) * spec * 0.28 * large;

    if (u.bezel.w > 0.5) {
        float margin = max(u.bezel.x, 8.0);
        vec2 cpos = vec2(u.res.x - margin * 0.72, margin * 0.62);
        float cd = length(frag - cpos);
        float cr = margin * 0.30;
        float disc = smoothstep(cr + 0.8, cr - 1.2, cd);
        vec3 discCol = mix(vec3(0.98, 0.985, 1.0), theme, 0.06);
        col = mix(col, discCol, disc);
        float ring = (1.0 - smoothstep(0.15, 1.6, abs(cd - (cr - 1.0)))) * disc;
        col = mix(col, vec3(1.0), ring);
        float xmark = min(
            smoothstep(4.2, 1.3, abs((frag.x - cpos.x) - (frag.y - cpos.y))),
            smoothstep(4.2, 1.3, abs((frag.x - cpos.x) + (frag.y - cpos.y)))
        );
        xmark *= smoothstep(cr * 0.58, cr * 0.20, cd);
        col = mix(col, vec3(0.02, 0.02, 0.025), xmark);
    }

    float alpha = 0.50 * (1.0 - panel * 0.25);
    if (u.themeC.w > 0.0) {
        alpha *= u.themeC.w;
    }
    alpha *= smoothstep(0.8, -0.4, outer);
    vec3 rgb = clamp(col, 0.0, 1.0);
    if (u.bezel.z > 0.5) {
        outColor = vec4(rgb * alpha, alpha);
    } else {
        outColor = vec4(rgb, 1.0);
    }
}
"""


class LiquidGlassRendererOpenGL:
    """A borderless X11 window rendered via OpenGL supporting AMD, Intel, NVIDIA, and legacy GPUs."""

    bezel_px = 52
    radius_px = 36
    clear_opacity = 0.70

    def __init__(self, width=1280, height=820, title="MP Audio Player (Liquid Glass - OpenGL)"):
        self.width = int(width)
        self.height = int(height)
        self.title = title
        self.vendor_name = "Unknown"
        self.renderer_name = "OpenGL Generic"
        self.gl_version = "Unknown"
        self.cursor = (0.0, 0.0)
        self.panels = ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))
        self.mouse_down = False
        self.presses = []
        self.should_close = False
        self.shaped = False
        self._shape_size = (0, 0)
        self._cur_pos = (72, 64)
        self._alive = False
        self._window = None
        self._vao = 0
        self._vbo = 0
        self._prog = 0
        self._u_locs = {}

    @property
    def summary(self):
        return (
            f"OpenGL device: {self.renderer_name} "
            f"(vendor: {self.vendor_name}, version: {self.gl_version})"
        )

    def open(self):
        self._step = "x11 threads"
        self._x11 = ctypes.CDLL("libX11.so.6")
        self._x11.XInitThreads.restype = c_int
        self._x11.XInitThreads()
        self._bind_x11()
        self._install_x_error_handler()
        self._bind_xext()

        self._step = "glfw"
        self._glfw = ctypes.CDLL("libglfw.so.3")
        self._bind_glfw()
        self._glfw.glfwInitHint(GLFW_PLATFORM, GLFW_PLATFORM_X11)
        if not self._glfw.glfwInit():
            raise RuntimeError("glfwInit failed")

        self._step = "window"
        self._window = self._create_window()
        self._bind_input()
        self._glfw.glfwMakeContextCurrent(self._window)
        try:
            self._glfw.glfwSwapInterval(1)
        except Exception:
            pass

        self._step = "opengl init"
        self._init_gl()
        self._create_pipeline()
        self._apply_shape()
        self._alive = True
        print(self.summary, flush=True)
        return self

    def close(self):
        if not self._alive:
            self._destroy_window()
            return
        try:
            from OpenGL import GL
            if self._prog:
                GL.glDeleteProgram(self._prog)
            if self._vao:
                GL.glDeleteVertexArrays(1, [self._vao])
            if self._vbo:
                GL.glDeleteBuffers(1, [self._vbo])
        except Exception:
            pass
        self._alive = False
        self._destroy_window()

    def request_close(self):
        self.should_close = True
        if self._window:
            self._glfw.glfwSetWindowShouldClose(self._window, 1)

    def set_panels(self, panels):
        rects = []
        for rect in list(panels)[:2]:
            x, y, w, h = rect
            rects.append((float(x), float(y), float(w), float(h)))
        while len(rects) < 2:
            rects.append((0.0, 0.0, 0.0, 0.0))
        self.panels = tuple(rects)

    def window_size(self):
        w, h = c_int(), c_int()
        self._glfw.glfwGetWindowSize(self._window, byref(w), byref(h))
        return int(w.value), int(h.value)

    def framebuffer_size(self):
        w, h = c_int(), c_int()
        self._glfw.glfwGetFramebufferSize(self._window, byref(w), byref(h))
        return max(1, int(w.value)), max(1, int(h.value))

    def window_pos(self):
        if getattr(self, "_cur_pos", None) is not None:
            return self._cur_pos
        x, y = c_int(), c_int()
        self._glfw.glfwGetWindowPos(self._window, byref(x), byref(y))
        pos = (int(x.value), int(y.value))
        self._cur_pos = pos
        return pos

    def set_window_pos(self, x, y):
        pos = (int(x), int(y))
        self._cur_pos = pos
        self._glfw.glfwSetWindowPos(self._window, pos[0], pos[1])

    def set_window_size(self, w, h):
        self._glfw.glfwSetWindowSize(self._window, int(w), int(h))
        self._resize = True

    def get_workarea(self):
        """Monitor workarea (x, y, width, height) where this window is located."""
        if not self._window:
            return 0, 0, 1920, 1080
        wx, wy = self.window_pos()
        self._glfw.glfwGetPrimaryMonitor.restype = c_void_p
        mon = self._glfw.glfwGetPrimaryMonitor()
        count = c_int()
        self._glfw.glfwGetMonitors.restype = POINTER(c_void_p)
        self._glfw.glfwGetMonitors.argtypes = [POINTER(c_int)]
        if hasattr(self._glfw, "glfwGetMonitorWorkarea"):
            self._glfw.glfwGetMonitorWorkarea.argtypes = [
                c_void_p,
                POINTER(c_int),
                POINTER(c_int),
                POINTER(c_int),
                POINTER(c_int),
            ]
            mons = self._glfw.glfwGetMonitors(byref(count))
            if mons and count.value > 0:
                for i in range(count.value):
                    m = mons[i]
                    mx, my, mw, mh = c_int(), c_int(), c_int(), c_int()
                    self._glfw.glfwGetMonitorWorkarea(m, byref(mx), byref(my), byref(mw), byref(mh))
                    if mx.value <= wx < mx.value + mw.value and my.value <= wy < my.value + mh.value:
                        return int(mx.value), int(my.value), int(mw.value), int(mh.value)
                # Fallback to primary monitor workarea
                mx, my, mw, mh = c_int(), c_int(), c_int(), c_int()
                self._glfw.glfwGetMonitorWorkarea(mon, byref(mx), byref(my), byref(mw), byref(mh))
                if mw.value > 0 and mh.value > 0:
                    return int(mx.value), int(my.value), int(mw.value), int(mh.value)
        disp = self.x11_display()
        if disp and getattr(self, "_x11", None):
            try:
                screen = self._x11.XDefaultScreen(disp)
                rw = self._x11.XDisplayWidth(disp, screen)
                rh = self._x11.XDisplayHeight(disp, screen)
                return 0, 0, int(rw), int(rh)
            except Exception:
                pass
        return 0, 0, 1920, 1080

    def x11_window(self):
        return int(self._glfw.glfwGetX11Window(self._window))

    def x11_display(self):
        return self._glfw.glfwGetX11Display(self._window)

    def poll(self):
        self._glfw.glfwPollEvents()
        if self._glfw.glfwWindowShouldClose(self._window):
            self.should_close = True
        return not self.should_close

    def draw(self, theme_name, opacity=1.0, capture=False):
        if not self.poll():
            return None
        fw, fh = self.framebuffer_size()
        if fw < 2 or fh < 2:
            return None
        if self.window_size() != self._shape_size:
            self._apply_shape()

        from OpenGL import GL

        GL.glViewport(0, 0, fw, fh)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glUseProgram(self._prog)

        colors, effective_opacity, factor = get_dynamic_theme_state(theme_name, opacity)
        win = self.x11_window() if hasattr(self, "x11_window") else None
        if factor != 1.0 and win:
            target_op = int(self.clear_opacity * factor * 1000)
            if getattr(self, "_last_dyn_opacity", None) != target_op:
                self._last_dyn_opacity = target_op
                self._set_opacity(win, self.clear_opacity * factor)

        a = _rgb01(colors[0])
        b = _rgb01(colors[1])
        c = _rgb01(colors[2])
        aspect = float(fw) / max(1.0, float(fh))

        u = self._u_locs
        GL.glUniform4f(u["u_res"], float(fw), float(fh), float(time.monotonic() - getattr(self, "_start", 0)), aspect)
        GL.glUniform4f(u["u_themeA"], a[0], a[1], a[2], float(self.cursor[0]) / max(1.0, float(fw)))
        GL.glUniform4f(u["u_themeB"], b[0], b[1], b[2], float(self.cursor[1]) / max(1.0, float(fh)))
        GL.glUniform4f(u["u_themeC"], c[0], c[1], c[2], float(effective_opacity))
        GL.glUniform4f(u["u_bezel"], float(self.bezel_px), float(self.radius_px), 0.0, 1.0)

        p0 = self.panels[0]
        p1 = self.panels[1]
        GL.glUniform4f(u["u_panel0"], float(p0[0]), float(p0[1]), float(p0[2]), float(p0[3]))
        GL.glUniform4f(u["u_panel1"], float(p1[0]), float(p1[1]), float(p1[2]), float(p1[3]))

        GL.glBindVertexArray(self._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)

        pixels = None
        if capture:
            raw = GL.glReadPixels(0, 0, fw, fh, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            pixels = self._format_capture(fw, fh, raw)

        self._glfw.glfwSwapBuffers(self._window)
        return pixels

    def _format_capture(self, w, h, raw):
        import numpy as np
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
        arr_flipped = np.flipud(arr)
        bgra = np.empty_like(arr_flipped)
        bgra[:, :, 0] = arr_flipped[:, :, 2]
        bgra[:, :, 1] = arr_flipped[:, :, 1]
        bgra[:, :, 2] = arr_flipped[:, :, 0]
        bgra[:, :, 3] = arr_flipped[:, :, 3]
        return w, h, bytes(bgra.flatten())

    def _bind_x11(self):
        x = self._x11
        x.XOpenDisplay.restype = c_void_p
        x.XOpenDisplay.argtypes = [c_char_p]
        x.XReparentWindow.argtypes = [c_void_p, c_uint64, c_uint64, c_int, c_int]
        x.XMoveResizeWindow.argtypes = [c_void_p, c_uint64, c_int, c_int, c_uint32, c_uint32]
        x.XMapWindow.argtypes = [c_void_p, c_uint64]
        x.XFlush.argtypes = [c_void_p]
        x.XSync.argtypes = [c_void_p, c_int]
        x.XQueryTree.argtypes = [
            c_void_p, c_uint64, POINTER(c_uint64), POINTER(c_uint64),
            POINTER(POINTER(c_uint64)), POINTER(c_uint32),
        ]
        x.XQueryTree.restype = c_int
        x.XFree.argtypes = [c_void_p]
        x.XCloseDisplay.argtypes = [c_void_p]
        x.XCreatePixmap.argtypes = [c_void_p, c_uint64, c_uint32, c_uint32, c_uint32]
        x.XCreatePixmap.restype = c_uint64
        x.XFreePixmap.argtypes = [c_void_p, c_uint64]
        x.XCreateGC.argtypes = [c_void_p, c_uint64, c_uint64, c_void_p]
        x.XCreateGC.restype = c_void_p
        x.XFreeGC.argtypes = [c_void_p, c_void_p]
        x.XSetForeground.argtypes = [c_void_p, c_void_p, c_uint64]
        x.XFillRectangle.argtypes = [c_void_p, c_uint64, c_void_p, c_int, c_int, c_uint32, c_uint32]
        x.XFillArc.argtypes = [
            c_void_p, c_uint64, c_void_p, c_int, c_int, c_uint32, c_uint32, c_int, c_int,
        ]
        x.XSetInputFocus.argtypes = [c_void_p, c_uint64, c_int, c_uint64]
        x.XSetErrorHandler.argtypes = [c_void_p]
        x.XSetErrorHandler.restype = c_void_p
        x.XSync.restype = c_int
        x.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]
        x.XInternAtom.restype = c_uint64
        x.XChangeProperty.argtypes = [
            c_void_p, c_uint64, c_uint64, c_uint64, c_int, c_int, c_void_p, c_int,
        ]
        x.XChangeProperty.restype = c_int
        x.XRaiseWindow.argtypes = [c_void_p, c_uint64]
        x.XSetTransientForHint.argtypes = [c_void_p, c_uint64, c_uint64]
        x.XSetTransientForHint.restype = c_int
        x.XGetGeometry.argtypes = [
            c_void_p, c_uint64, POINTER(c_uint64), POINTER(c_int), POINTER(c_int),
            POINTER(c_uint32), POINTER(c_uint32), POINTER(c_uint32), POINTER(c_uint32),
        ]
        x.XGetGeometry.restype = c_int
        x.XTranslateCoordinates.argtypes = [
            c_void_p, c_uint64, c_uint64, c_int, c_int,
            POINTER(c_int), POINTER(c_int), POINTER(c_uint64),
        ]
        x.XTranslateCoordinates.restype = c_int
        x.XDefaultRootWindow.argtypes = [c_void_p]
        x.XDefaultRootWindow.restype = c_uint64
        x.XGetInputFocus.argtypes = [c_void_p, POINTER(c_uint64), POINTER(c_int)]
        x.XQueryPointer.argtypes = [
            c_void_p, c_uint64,
            POINTER(c_uint64), POINTER(c_uint64),
            POINTER(c_int), POINTER(c_int),
            POINTER(c_int), POINTER(c_int),
            POINTER(c_uint32),
        ]
        x.XQueryPointer.restype = c_int

    def root_pointer(self):
        """Absolute screen coordinates of the mouse pointer from the X11 root window."""
        display = self.x11_display()
        if not display:
            return 0, 0
        root = self._x11.XDefaultRootWindow(display)
        root_ret = c_uint64()
        child_ret = c_uint64()
        root_x = c_int()
        root_y = c_int()
        win_x = c_int()
        win_y = c_int()
        mask = c_uint32()
        ok = self._x11.XQueryPointer(
            display,
            root,
            byref(root_ret),
            byref(child_ret),
            byref(root_x),
            byref(root_y),
            byref(win_x),
            byref(win_y),
            byref(mask),
        )
        if not ok:
            return 0, 0
        return int(root_x.value), int(root_y.value)

    def _install_x_error_handler(self):
        @ctypes.CFUNCTYPE(c_int, c_void_p, c_void_p)
        def handler(_display, _event):
            return 0

        self._x_error_handler = handler
        self._x11.XSetErrorHandler(ctypes.cast(handler, c_void_p))

    def _bind_xext(self):
        try:
            ext = ctypes.CDLL("libXext.so.6")
        except OSError:
            self._xext = None
            return
        ext.XShapeCombineMask.argtypes = [c_void_p, c_uint64, c_int, c_int, c_int, c_uint64, c_int]
        ext.XShapeQueryExtents.argtypes = [
            c_void_p, c_uint64,
            POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_uint32), POINTER(c_uint32),
            POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_uint32), POINTER(c_uint32),
        ]
        ext.XShapeQueryExtents.restype = c_int
        self._xext = ext

    def _apply_shape(self):
        self._shape_size = self.window_size()
        self.shaped = False
        self._apply_desktop_glass()
        if not getattr(self, "_xext", None):
            return
        display = self.x11_display()
        window = self.x11_window()
        width, height = self._shape_size
        if not display or not window or width < 8 or height < 8:
            return
        radius = max(8, min(int(self.radius_px), width // 2 - 1, height // 2 - 1))
        x11 = self._x11
        mask = x11.XCreatePixmap(display, window, width, height, 1)
        if not mask:
            return
        gc = x11.XCreateGC(display, mask, 0, None)
        if not gc:
            x11.XFreePixmap(display, mask)
            return
        diameter = radius * 2
        x11.XSetForeground(display, gc, 0)
        x11.XFillRectangle(display, mask, gc, 0, 0, width, height)
        x11.XSetForeground(display, gc, 1)
        x11.XFillRectangle(display, mask, gc, radius, 0, width - diameter, height)
        x11.XFillRectangle(display, mask, gc, 0, radius, width, height - diameter)
        x11.XFillArc(display, mask, gc, 0, 0, diameter, diameter, 90 * 64, 90 * 64)
        x11.XFillArc(display, mask, gc, width - diameter, 0, diameter, diameter, 0, 90 * 64)
        x11.XFillArc(display, mask, gc, 0, height - diameter, diameter, diameter, 180 * 64, 90 * 64)
        x11.XFillArc(display, mask, gc, width - diameter, height - diameter, diameter, diameter, 270 * 64, 90 * 64)
        self._xext.XShapeCombineMask(display, window, 0, 0, 0, mask, 0)
        x11.XFreeGC(display, gc)
        x11.XFreePixmap(display, mask)
        x11.XFlush(display)
        self.shaped = self._window_is_shaped()

    def _window_is_shaped(self):
        if not getattr(self, "_xext", None):
            return False
        bounding = c_int()
        clip = c_int()
        bx, by = c_int(), c_int()
        cx, cy = c_int(), c_int()
        bw, bh = c_uint32(), c_uint32()
        cw, ch = c_uint32(), c_uint32()
        ok = self._xext.XShapeQueryExtents(
            self.x11_display(), self.x11_window(),
            byref(bounding), byref(bx), byref(by), byref(bw), byref(bh),
            byref(clip), byref(cx), byref(cy), byref(cw), byref(ch),
        )
        return bool(ok and bounding.value)

    def _x_atom(self, name):
        atoms = getattr(self, "_x_atoms", None)
        if atoms is None:
            atoms = {}
            self._x_atoms = atoms
        if name not in atoms:
            atoms[name] = int(self._x11.XInternAtom(self.x11_display(), name.encode("ascii"), 0))
        return atoms[name]

    def _change_cardinal(self, window, prop, values):
        data = (c_uint32 * len(values))(*[int(value) & 0xFFFFFFFF for value in values])
        self._prop_keep = data
        self._x11.XChangeProperty(
            self.x11_display(),
            int(window),
            int(prop),
            self._x_atom("CARDINAL"),
            32,
            0,
            ctypes.cast(data, c_void_p),
            len(values),
        )

    def _set_opacity(self, window, opacity):
        value = int(max(0.0, min(1.0, float(opacity))) * 0xFFFFFFFF)
        self._change_cardinal(window, self._x_atom("_NET_WM_WINDOW_OPACITY"), [value])

    def _apply_desktop_glass(self):
        window = self.x11_window()
        if not self.x11_display() or not window:
            return
        width, height = self.window_size()
        self._set_opacity(window, self.clear_opacity)
        self._change_cardinal(
            window,
            self._x_atom("_KDE_NET_WM_BLUR_BEHIND_REGION"),
            [0, 0, max(int(width), 1), max(int(height), 1)],
        )
        self._x11.XFlush(self.x11_display())

    def reparent_window(self, child, x, y, width, height):
        display = self.x11_display()
        self._x11.XReparentWindow(display, int(child), self.x11_window(), int(x), int(y))
        self._x11.XMoveResizeWindow(display, int(child), int(x), int(y), int(width), int(height))
        self._x11.XMapWindow(display, int(child))
        self._set_opacity(int(child), 1.0)
        self._x11.XSetInputFocus(display, int(child), 2, 0)
        self._x11.XFlush(display)

    def focus_window(self, window):
        self._x11.XSetInputFocus(self.x11_display(), int(window), 2, 0)
        self._x11.XFlush(self.x11_display())

    def focused_window(self):
        window = c_uint64()
        revert = c_int()
        self._x11.XGetInputFocus(self.x11_display(), byref(window), byref(revert))
        return int(window.value)

    def window_rect(self, window):
        display = self.x11_display()
        root = c_uint64()
        x, y = c_int(), c_int()
        width, height = c_uint32(), c_uint32()
        border, depth = c_uint32(), c_uint32()
        ok = self._x11.XGetGeometry(
            display, int(window), byref(root), byref(x), byref(y),
            byref(width), byref(height), byref(border), byref(depth),
        )
        if not ok:
            return 0, 0, 0, 0
        origin_x, origin_y = c_int(), c_int()
        child = c_uint64()
        self._x11.XTranslateCoordinates(
            display, int(window), self._x11.XDefaultRootWindow(display),
            0, 0, byref(origin_x), byref(origin_y), byref(child),
        )
        return int(origin_x.value), int(origin_y.value), int(width.value), int(height.value)

    def place_terminal(self, child, x, y, width, height):
        del x, y, width, height
        display = self.x11_display()
        child = int(child)
        self._x11.XSetTransientForHint(display, child, self.x11_window())
        self._set_opacity(child, 1.0)
        focused = self.focused_window()
        glass = self.x11_window()
        if focused in (glass, child, self.window_parent(glass), self.window_parent(child)):
            self._x11.XRaiseWindow(display, child)
        self._x11.XFlush(display)

    def window_parent(self, child):
        root = c_uint64()
        parent = c_uint64()
        children = POINTER(c_uint64)()
        count = c_uint32()
        ok = self._x11.XQueryTree(
            self.x11_display(), int(child), byref(root), byref(parent), byref(children), byref(count),
        )
        if children:
            self._x11.XFree(children)
        if not ok:
            return 0
        return int(parent.value)

    def _bind_glfw(self):
        g = self._glfw
        g.glfwInit.restype = c_int
        g.glfwInitHint.argtypes = [c_int, c_int]
        g.glfwWindowHint.argtypes = [c_int, c_int]
        g.glfwDefaultWindowHints.argtypes = []
        g.glfwCreateWindow.restype = c_void_p
        g.glfwCreateWindow.argtypes = [c_int, c_int, c_char_p, c_void_p, c_void_p]
        g.glfwDestroyWindow.argtypes = [c_void_p]
        g.glfwMakeContextCurrent.argtypes = [c_void_p]
        g.glfwSwapInterval.argtypes = [c_int]
        g.glfwSwapBuffers.argtypes = [c_void_p]
        g.glfwPollEvents.argtypes = []
        g.glfwWindowShouldClose.argtypes = [c_void_p]
        g.glfwWindowShouldClose.restype = c_int
        g.glfwSetWindowShouldClose.argtypes = [c_void_p, c_int]
        g.glfwGetWindowSize.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetFramebufferSize.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwGetWindowPos.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
        g.glfwSetWindowPos.argtypes = [c_void_p, c_int, c_int]
        g.glfwSetWindowSize.argtypes = [c_void_p, c_int, c_int]
        g.glfwGetX11Window.argtypes = [c_void_p]
        g.glfwGetX11Window.restype = c_uint64
        g.glfwGetX11Display.argtypes = [c_void_p]
        g.glfwGetX11Display.restype = c_void_p
        g.glfwSetMouseButtonCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetMouseButtonCallback.restype = c_void_p
        g.glfwSetCursorPosCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetCursorPosCallback.restype = c_void_p
        g.glfwSetFramebufferSizeCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetFramebufferSizeCallback.restype = c_void_p
        g.glfwSetWindowPosCallback.argtypes = [c_void_p, c_void_p]
        g.glfwSetWindowPosCallback.restype = c_void_p

    def _create_window(self):
        g = self._glfw
        g.glfwDefaultWindowHints()
        g.glfwWindowHint(GLFW_CLIENT_API, GLFW_OPENGL_API)
        g.glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3)
        g.glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3)
        g.glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE)
        g.glfwWindowHint(GLFW_RESIZABLE, 1)
        g.glfwWindowHint(GLFW_DECORATED, 0)
        g.glfwWindowHint(GLFW_FOCUS_ON_SHOW, 1)
        g.glfwWindowHint(GLFW_VISIBLE, 1)
        g.glfwWindowHint(GLFW_FOCUSED, 1)
        g.glfwWindowHint(GLFW_TRANSPARENT, 1)

        title = self.title.encode("utf-8")
        window = g.glfwCreateWindow(self.width, self.height, title, None, None)
        if not window:
            # Fallback for older legacy hardware/drivers that may not support Core 3.3 profile:
            g.glfwDefaultWindowHints()
            g.glfwWindowHint(GLFW_RESIZABLE, 1)
            g.glfwWindowHint(GLFW_DECORATED, 0)
            g.glfwWindowHint(GLFW_VISIBLE, 1)
            g.glfwWindowHint(GLFW_TRANSPARENT, 1)
            window = g.glfwCreateWindow(self.width, self.height, title, None, None)
        if not window:
            raise RuntimeError("GLFW could not open an X11 window with OpenGL support")

        g.glfwSetWindowPos(window, 72, 64)
        self._cur_pos = (72, 64)
        self._resize = False
        return window

    def _bind_input(self):
        self._on_mouse = CFUNCTYPE(None, c_void_p, c_int, c_int, c_int)(self._mouse_button)
        self._on_cursor = CFUNCTYPE(None, c_void_p, c_double, c_double)(self._cursor)
        self._on_fb = CFUNCTYPE(None, c_void_p, c_int, c_int)(self._framebuffer)
        self._on_pos = CFUNCTYPE(None, c_void_p, c_int, c_int)(self._pos_callback)
        self._glfw.glfwSetMouseButtonCallback(self._window, ctypes.cast(self._on_mouse, c_void_p))
        self._glfw.glfwSetCursorPosCallback(self._window, ctypes.cast(self._on_cursor, c_void_p))
        self._glfw.glfwSetFramebufferSizeCallback(self._window, ctypes.cast(self._on_fb, c_void_p))
        self._glfw.glfwSetWindowPosCallback(self._window, ctypes.cast(self._on_pos, c_void_p))

    def _pos_callback(self, _window, x, y):
        self._cur_pos = (int(x), int(y))

    def _mouse_button(self, _window, button, action, _mods):
        if button == 0:
            self.mouse_down = action == GLFW_PRESS
            if action == GLFW_PRESS:
                self.presses.append(self.cursor)

    def _cursor(self, _window, x, y):
        self.cursor = (float(x), float(y))

    def _framebuffer(self, _window, _w, _h):
        self._resize = True

    def _init_gl(self):
        from OpenGL import GL

        vendor_b = GL.glGetString(GL.GL_VENDOR)
        renderer_b = GL.glGetString(GL.GL_RENDERER)
        version_b = GL.glGetString(GL.GL_VERSION)
        self.vendor_name = vendor_b.decode("utf-8", errors="replace") if vendor_b else "Unknown"
        self.renderer_name = renderer_b.decode("utf-8", errors="replace") if renderer_b else "OpenGL Generic"
        self.gl_version = version_b.decode("utf-8", errors="replace") if version_b else "Unknown"

    def _create_pipeline(self):
        from OpenGL import GL
        import numpy as np

        vert_path = SHADER_DIR / "liquid_glass_gl.vert"
        frag_path = SHADER_DIR / "liquid_glass_gl.frag"

        vert_src = vert_path.read_text(encoding="utf-8") if vert_path.is_file() else FALLBACK_VERT_SRC
        frag_src = frag_path.read_text(encoding="utf-8") if frag_path.is_file() else FALLBACK_FRAG_SRC

        vs = GL.glCreateShader(GL.GL_VERTEX_SHADER)
        GL.glShaderSource(vs, vert_src)
        GL.glCompileShader(vs)
        if not GL.glGetShaderiv(vs, GL.GL_COMPILE_STATUS):
            err = GL.glGetShaderInfoLog(vs).decode("utf-8", errors="replace")
            raise RuntimeError(f"Vertex shader compilation failed: {err}")

        fs = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
        GL.glShaderSource(fs, frag_src)
        GL.glCompileShader(fs)
        if not GL.glGetShaderiv(fs, GL.GL_COMPILE_STATUS):
            err = GL.glGetShaderInfoLog(fs).decode("utf-8", errors="replace")
            raise RuntimeError(f"Fragment shader compilation failed: {err}")

        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            err = GL.glGetProgramInfoLog(prog).decode("utf-8", errors="replace")
            raise RuntimeError(f"Shader program link failed: {err}")

        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        self._prog = prog

        # Cache uniform locations
        for u_name in [
            "u_res", "u_themeA", "u_themeB", "u_themeC",
            "u_bezel", "u_panel0", "u_panel1"
        ]:
            loc = GL.glGetUniformLocation(prog, u_name)
            self._u_locs[u_name] = loc

        # Full-screen quad geometry
        quad = np.array([
            -1.0,  1.0, 0.0, 0.0,
            -1.0, -1.0, 0.0, 1.0,
             1.0, -1.0, 1.0, 1.0,
            -1.0,  1.0, 0.0, 0.0,
             1.0, -1.0, 1.0, 1.0,
             1.0,  1.0, 1.0, 0.0,
        ], dtype=np.float32)

        self._vao = GL.glGenVertexArrays(1)
        self._vbo = GL.glGenBuffers(1)

        GL.glBindVertexArray(self._vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, quad.nbytes, quad, GL.GL_STATIC_DRAW)

        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 4 * 4, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, 4 * 4, ctypes.c_void_p(2 * 4))
        GL.glBindVertexArray(0)

    def _destroy_window(self):
        if self._window and getattr(self, "_glfw", None):
            self._glfw.glfwDestroyWindow(self._window)
            self._window = None
            self._glfw.glfwTerminate()


def save_png(path, width, height, bgra, swap_rb=False):
    from PIL import Image
    raw = bytearray(bgra)
    if swap_rb:
        for i in range(0, len(raw), 4):
            raw[i], raw[i + 2] = raw[i + 2], raw[i]
    image = Image.frombytes("RGBA", (width, height), bytes(raw))
    image.save(path)
    return image


def glass_metrics(width, height, bgra):
    """Return simple colour stats used to confirm the shader actually drew."""
    def px(x, y):
        i = (y * width + x) * 4
        b, g, r, a = bgra[i:i + 4]
        return r, g, b, a

    rim = px(width // 2, min(6, height - 1))
    clear = px(width // 2, min(145, height - 1))
    panel = px(width // 2, height // 2)
    corner = px(min(2, width - 1), min(2, height - 1))
    return {"rim": rim, "clear": clear, "panel": panel, "corner": corner}


def run_self_test(png_path=None):
    renderer = LiquidGlassRendererOpenGL(720, 440, "MP Liquid Glass self-test (OpenGL)")
    try:
        renderer.open()
        renderer.set_panels(((60.0, 58.0, 600.0, 52.0), (60.0, 180.0, 600.0, 200.0)))
        pixels = None
        for i in range(6):
            pixels = renderer.draw("dreamworlds_ultra", capture=(i == 5))
        if not pixels:
            raise RuntimeError("OpenGL swapchain did not produce a readable frame")
        width, height, bgra = pixels
        if png_path:
            save_png(png_path, width, height, bgra, swap_rb=False)
        stats = glass_metrics(width, height, bgra)
        rim = stats["rim"]
        clear = stats["clear"]
        panel = stats["panel"]
        corner = stats["corner"]
        if max(rim[0], rim[1], rim[2]) < 180:
            raise RuntimeError(f"sloped rim is not catching light: {rim}")
        if min(clear[0], clear[1], clear[2]) < 140:
            raise RuntimeError(f"the water is not clear glass: {clear}")
        if clear[2] < clear[1] + 8:
            raise RuntimeError(f"the still water is missing the dreamworlds theme colour: {clear}")
        clear_luma = clear[0] + clear[1] + clear[2]
        panel_luma = panel[0] + panel[1] + panel[2]
        if panel_luma >= clear_luma:
            raise RuntimeError(f"glass panel is not darker than the water ({panel} vs {clear})")
        if panel_luma < 120:
            raise RuntimeError(f"glass panel is a solid well, not shaded glass: {panel}")
        if max(corner[0], corner[1], corner[2]) > 24:
            raise RuntimeError(f"corner outside the rounded glass is not clear: {corner}")
        if not renderer.shaped:
            raise RuntimeError("the X11 window was not clipped to the rounded glass shape")
        print(
            f"LIQUID_GLASS_OK {renderer.summary} "
            f"frame={width}x{height} rim={rim} water={clear} panel={panel} corner={corner}",
            flush=True,
        )
        return renderer.summary
    finally:
        renderer.close()


if __name__ == "__main__":
    try:
        run_self_test()
    except Exception as exc:
        print(f"Liquid Glass (OpenGL): {exc}", file=sys.stderr)
        raise SystemExit(1)
