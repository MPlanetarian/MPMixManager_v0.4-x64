#!/usr/bin/env python3
from __future__ import annotations
import ctypes
import ctypes.util
import os
import sys
import time
from pathlib import Path

# --- Platform & CTypes compatibility setup ---
os.environ["PYOPENGL_PLATFORM"] = "darwin"
_orig_cfunctype = ctypes.CFUNCTYPE
_type_proxy_cache: dict = {}

def _is_valid_ctype(tp):
    if tp is None: return True
    if isinstance(tp, type):
        try:
            return issubclass(tp, (ctypes._SimpleCData, ctypes.Structure, ctypes.Union, ctypes._Pointer, ctypes.Array, ctypes._CFuncPtr))
        except TypeError: return False
    return False

def _sanitize_ctype(tp):
    if _is_valid_ctype(tp): return tp
    if tp in _type_proxy_cache: return _type_proxy_cache[tp]
    orig_from_param = getattr(tp, "from_param", None)
    class _PyOpenGLTypeProxy(ctypes.c_void_p):
        @classmethod
        def from_param(cls, value):
            if value is None: return None
            if orig_from_param is not None:
                try:
                    res = orig_from_param(value)
                    if isinstance(res, ctypes._CData) or hasattr(res, "_as_parameter_"): return res
                except Exception: pass
            if isinstance(value, (bytes, bytearray)): return ctypes.c_char_p(bytes(value))
            if isinstance(value, str): return ctypes.c_char_p(value.encode("utf-8"))
            if isinstance(value, int): return ctypes.c_void_p(value)
            if isinstance(value, ctypes._CData): return ctypes.byref(value) if not isinstance(value, (ctypes._Pointer, ctypes.Array, ctypes.c_void_p, ctypes.c_char_p)) else value
            if hasattr(value, "ctypes"): return value.ctypes.data_as(ctypes.c_void_p)
            return ctypes.c_void_p.from_param(value)
    _PyOpenGLTypeProxy.__name__ = f"Proxy_{getattr(tp, '__name__', 'Param')}"
    _type_proxy_cache[tp] = _PyOpenGLTypeProxy
    return _PyOpenGLTypeProxy

def _py315_safe_cfunctype(restype, *argtypes, **kwargs):
    try: return _orig_cfunctype(restype, *argtypes, **kwargs)
    except (TypeError, ValueError):
        return _orig_cfunctype(_sanitize_ctype(restype), *tuple(_sanitize_ctype(a) for a in argtypes), **kwargs)

ctypes.CFUNCTYPE = _py315_safe_cfunctype

ROOT = Path(__file__).resolve().parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from liquid_glass_opengl import (
    LiquidGlassRendererOpenGL,
    read_player_theme,
    get_dynamic_theme_state,
    _rgb01,
    THEME_ALIASES,
)
from MP_Audio_Player import (
    AudioEngine,
    MixArchiveScanner,
    PlayerIPCServer,
    EqualizerVisualizer,
    _spawn_player_daemon,
    is_player_daemon_running,
    CONFIG_DIR,
    STATE_FILE,
)

COLS = 120
ROWS = 40
CHAR_W = 9
CHAR_H = 18


def player_panel_rects(cols=COLS, rows=ROWS, char_w=CHAR_W, char_h=CHAR_H, origin_x=0, origin_y=0, mode="NORMAL"):
    def box(col, row, box_cols, box_rows):
        return (
            float(origin_x + col * char_w),
            float(origin_y + row * char_h),
            float(box_cols * char_w),
            float(box_rows * char_h),
        )
    return box(2, 0, max(20, cols - 2), 4), box(2, 6, max(20, cols - 2), max(1, rows - 7))


class HeadlessTerminalOverlay:
    """Renders player status directly into an OpenGL texture with zero external terminal windows."""

    def __init__(self, scanner, cols=COLS, rows=ROWS, char_w=CHAR_W, char_h=CHAR_H):
        self.scanner = scanner
        self.cols = cols
        self.rows = rows
        self.char_w = char_w
        self.char_h = char_h
        self.visualizer = EqualizerVisualizer()
        self.texture_id = 0
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self._initialized_gl = False
        self.font = None
        self.image = None
        self.img_w = self.cols * self.char_w
        self.img_h = self.rows * self.char_h

        try:
            from PIL import Image, ImageFont
            for font_path in [
                "/System/Library/Fonts/SFNSMono.ttf",
                "/System/Library/Fonts/Monaco.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Courier New.ttf",
            ]:
                if os.path.exists(font_path):
                    self.font = ImageFont.truetype(font_path, 13)
                    break
            if not self.font:
                self.font = ImageFont.load_default()
            self.image = Image.new("RGBA", (self.img_w, self.img_h), (0, 0, 0, 0))
        except Exception:
            pass

    def init_gl(self):
        if self._initialized_gl:
            return
        try:
            from OpenGL.GL import (
                glCreateShader, glShaderSource, glCompileShader, glCreateProgram,
                glAttachShader, glLinkProgram, glGenVertexArrays, glBindVertexArray,
                glGenBuffers, glBindBuffer, glBufferData, glVertexAttribPointer,
                glEnableVertexAttribArray, GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
                GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW, GL_FLOAT, GL_FALSE,
                glGenTextures, glBindTexture, glTexParameteri, glTexImage2D,
                GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
                GL_NEAREST, GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
                GL_RGBA, GL_UNSIGNED_BYTE
            )
            import numpy as np

            vs_src = b"""
            #version 410 core
            layout(location = 0) in vec2 a_position;
            layout(location = 1) in vec2 a_uv;
            out vec2 v_uv;
            void main() {
                gl_Position = vec4(a_position, 0.0, 1.0);
                v_uv = a_uv;
            }
            """
            vs = glCreateShader(GL_VERTEX_SHADER)
            glShaderSource(vs, vs_src)
            glCompileShader(vs)

            fs_src = b"""
            #version 410 core
            in vec2 v_uv;
            uniform sampler2D u_textTex;
            out vec4 fragColor;
            void main() {
                vec4 texColor = texture(u_textTex, v_uv);
                if (texColor.a < 0.05) discard;
                fragColor = texColor;
            }
            """
            fs = glCreateShader(GL_FRAGMENT_SHADER)
            glShaderSource(fs, fs_src)
            glCompileShader(fs)

            self.shader_program = glCreateProgram()
            glAttachShader(self.shader_program, vs)
            glAttachShader(self.shader_program, fs)
            glLinkProgram(self.shader_program)

            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)

            glBindVertexArray(self.vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferData(GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL_DYNAMIC_DRAW)

            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(2 * 4))
            glEnableVertexAttribArray(1)
            glBindVertexArray(0)

            self.texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.img_w, self.img_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
            glBindTexture(GL_TEXTURE_2D, 0)

            self._initialized_gl = True
        except Exception as e:
            print(f"Overlay GL init error: {e}", flush=True)

    def render_status(self, status: dict, fw: int, fh: int):
        if not self._initialized_gl:
            self.init_gl()
        if not self._initialized_gl or not self.shader_program or not self.image:
            return

        try:
            from OpenGL.GL import (
                glUseProgram, glBindVertexArray, glDrawArrays, glBindBuffer,
                glBufferData, glDisable, glEnable, glBlendFunc, GL_DEPTH_TEST,
                GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_TRIANGLES,
                GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW, glBindTexture, GL_TEXTURE_2D,
                glTexImage2D, GL_RGBA, GL_UNSIGNED_BYTE
            )
            import numpy as np
            from PIL import ImageDraw

            self.image.paste((0, 0, 0, 0), [0, 0, self.img_w, self.img_h])
            draw = ImageDraw.Draw(self.image)

            # Build UI text lines matching MP_Audio_Player aesthetic
            lines = []
            title = status.get("title", "No Track Loaded")
            state = status.get("state", "stopped")
            pos_fmt = status.get("position_fmt", "00:00")
            dur_fmt = status.get("duration_fmt", "00:00")
            pct = status.get("progress_pct", 0.0)
            vol = status.get("volume", 85)

            lines.append(f"  MP AUDIO PLAYER (UNIFIED OPENGL GLASS)")
            lines.append(f"  State: {state.upper()}  |  Vol: {vol}%")
            lines.append(f"  Track: {title}")
            lines.append(f"  Time:  {pos_fmt} / {dur_fmt} ({pct:.1f}%)")
            lines.append("")
            
            # Render visualizer bars
            vis_lines = self.visualizer.render(status, width=self.cols, height=8)
            for vl in vis_lines:
                lines.append(f"  {vl}")

            for r, text in enumerate(lines[:self.rows]):
                if not text:
                    continue
                y = r * self.char_h
                draw.text((8, y), text, fill=(200, 235, 255, 255), font=self.font)

            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA, self.img_w, self.img_h, 0,
                GL_RGBA, GL_UNSIGNED_BYTE, self.image.tobytes("raw", "RGBA", 0, 1)
            )
            glBindTexture(GL_TEXTURE_2D, 0)

            x1, y1 = -1.0, -1.0
            x2 = -1.0 + (2.0 * self.img_w / fw)
            y2 = -1.0 + (2.0 * self.img_h / fh)

            quad_data = np.array([
                x1, y1, 0.0, 1.0,
                x2, y1, 1.0, 1.0,
                x1, y2, 0.0, 0.0,
                x2, y1, 1.0, 1.0,
                x2, y2, 1.0, 0.0,
                x1, y2, 0.0, 0.0,
            ], dtype=np.float32)

            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glUseProgram(self.shader_program)
            glBindVertexArray(self.vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferData(GL_ARRAY_BUFFER, quad_data.nbytes, quad_data, GL_DYNAMIC_DRAW)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glDrawArrays(GL_TRIANGLES, 0, 6)
            glBindTexture(GL_TEXTURE_2D, 0)
            glBindVertexArray(0)
            glUseProgram(0)
        except Exception as e:
            print(f"Overlay draw error: {e}", flush=True)


class CustomGlassRenderer(LiquidGlassRendererOpenGL):
    def __init__(self, overlay, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.overlay = overlay
        self._dragging = False
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0

    def open(self):
        super().open()
        self._bind_callbacks()
        if hasattr(self._glfw, "glfwSwapInterval") and self._window:
            self._glfw.glfwSwapInterval(1)
        return self

    def _bind_callbacks(self):
        from ctypes import CFUNCTYPE, c_void_p, c_int, c_double, POINTER

        @CFUNCTYPE(None, c_void_p, c_int, c_int, c_int)
        def mouse_button_callback(_window, button, action, mods):
            if button == 0:
                if action == 1:
                    self._dragging = True
                    xpos, ypos = c_double(), c_double()
                    if hasattr(self._glfw, "glfwGetCursorPos"):
                        self._glfw.glfwGetCursorPos(_window, ctypes.byref(xpos), ctypes.byref(ypos))
                    self._drag_start_x, self._drag_start_y = xpos.value, ypos.value
                elif action == 0:
                    self._dragging = False

        @CFUNCTYPE(None, c_void_p, c_double, c_double)
        def cursor_pos_callback(_window, xpos, ypos):
            if self._dragging:
                dx, dy = xpos - self._drag_start_x, ypos - self._drag_start_y
                x_win, y_win = c_int(), c_int()
                if hasattr(self._glfw, "glfwGetWindowPos") and hasattr(self._glfw, "glfwSetWindowPos"):
                    self._glfw.glfwGetWindowPos(_window, ctypes.byref(x_win), ctypes.byref(y_win))
                    self._glfw.glfwSetWindowPos(_window, int(x_win.value + dx), int(y_win.value + dy))

        @CFUNCTYPE(None, c_void_p, c_int, c_int, c_int, c_int)
        def key_callback(_window, key, scancode, action, mods):
            if action in (1, 2) and key in (81, 256):
                os._exit(0)

        self._on_mouse_btn_ref = mouse_button_callback
        self._on_cursor_pos_ref = cursor_pos_callback
        self._on_key_ref = key_callback

        if self._window:
            if hasattr(self._glfw, "glfwSetMouseButtonCallback"):
                self._glfw.glfwSetMouseButtonCallback.argtypes = [c_void_p, c_void_p]
                self._glfw.glfwSetMouseButtonCallback(self._window, ctypes.cast(self._on_mouse_btn_ref, c_void_p))
            if hasattr(self._glfw, "glfwSetCursorPosCallback"):
                self._glfw.glfwSetCursorPosCallback.argtypes = [c_void_p, c_void_p]
                self._glfw.glfwSetCursorPosCallback(self._window, ctypes.cast(self._on_cursor_pos_ref, c_void_p))
            if hasattr(self._glfw, "glfwSetKeyCallback"):
                self._glfw.glfwSetKeyCallback.argtypes = [c_void_p, c_void_p]
                self._glfw.glfwSetKeyCallback(self._window, ctypes.cast(self._on_key_ref, c_void_p))

    def draw(self, theme_name, status, opacity=1.0, capture=False):
        if not self.poll():
            return None
        fw, fh = self.framebuffer_size()
        ww, wh = self.window_size()
        if fw < 2 or fh < 2 or ww < 2 or wh < 2:
            return None

        if self.window_size() != self._shape_size:
            self._apply_shape()

        from OpenGL import GL
        GL.glViewport(0, 0, fw, fh)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glUseProgram(self._prog)

        colors, effective_opacity, factor = get_dynamic_theme_state(theme_name, opacity)
        a = _rgb01(colors[0])
        b = _rgb01(colors[1])
        c = _rgb01(colors[2])
        aspect = float(fw) / max(1.0, float(fh))
        u = self._u_locs

        GL.glUniform4f(u["u_res"], float(fw), float(fh), float(time.monotonic() - getattr(self, "_start", 0)), aspect)
        GL.glUniform4f(u["u_themeA"], a[0], a[1], a[2], float(self.cursor[0]) / max(1.0, float(fw)))
        GL.glUniform4f(u["u_themeB"], b[0], b[1], b[2], float(self.cursor[1]) / max(1.0, float(fw)))
        GL.glUniform4f(u["u_themeC"], c[0], c[1], c[2], float(effective_opacity))
        GL.glUniform4f(u["u_bezel"], float(self.bezel_px), float(self.radius_px), 0.0, 1.0)

        p0 = self.panels[0]
        p1 = self.panels[1]
        GL.glUniform4f(u["u_panel0"], float(p0[0]), float(p0[1]), float(p0[2]), float(p0[3]))
        GL.glUniform4f(u["u_panel1"], float(p1[0]), float(p1[1]), float(p1[2]), float(p1[3]))

        skin_key = THEME_ALIASES.get(str(theme_name or "").strip().lower(), str(theme_name or "").strip().lower())
        tex_id = self._load_skin_texture(skin_key)
        if tex_id:
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex_id)
            if u.get("u_skinTex", -1) != -1:
                GL.glUniform1i(u["u_skinTex"], 0)
            if u.get("u_hasSkin", -1) != -1:
                GL.glUniform1f(u["u_hasSkin"], 1.0)
        else:
            if u.get("u_hasSkin", -1) != -1:
                GL.glUniform1f(u["u_hasSkin"], 0.0)

        GL.glBindVertexArray(self._vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)

        # Render status via headless overlay
        self.overlay.render_status(status, fw, fh)

        pixels = None
        if capture:
            raw = GL.glReadPixels(0, 0, fw, fh, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            pixels = self._format_capture(fw, fh, raw)

        self._glfw.glfwSwapBuffers(self._window)
        return pixels


def main():
    # 1. Ensure audio player backend daemon is running headlessly
    if not is_player_daemon_running():
        _spawn_player_daemon(auto_bluetooth=True, mode="MIX_ARCHIVE")
        time.sleep(0.5)

    scanner = MixArchiveScanner(ROOT)
    overlay = HeadlessTerminalOverlay(scanner, COLS, ROWS)

    char_w, char_h = CHAR_W, CHAR_H
    margin = LiquidGlassRendererOpenGL.bezel_px
    init_w = COLS * char_w + (2 * margin)
    init_h = ROWS * char_h + (2 * margin)

    renderer = CustomGlassRenderer(
        overlay=overlay, width=init_w, height=init_h, title="MP Audio Player (Liquid Glass)"
    )
    renderer.open()
    renderer.set_panels(player_panel_rects(COLS, ROWS, char_w, char_h, margin, margin))

    theme = read_player_theme()
    theme_at = 0.0

    try:
        while not renderer.should_close:
            now = time.monotonic()
            if now - theme_at > 0.4:
                theme = read_player_theme()
                theme_at = now

            # Fetch live status from headless daemon
            status = {}
            if STATE_FILE.exists():
                import json
                try:
                    status = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass

            renderer.poll()
            renderer.draw(theme, status)
    finally:
        renderer.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(1)