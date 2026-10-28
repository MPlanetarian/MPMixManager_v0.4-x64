from __future__ import annotations
import ctypes
import ctypes.util
import faulthandler
import fcntl
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time
from pathlib import Path
from typing import TYPE_CHECKING

faulthandler.enable()

if not hasattr(ctypes, "_CData"):
    for base in getattr(ctypes.c_int, "__mro__", ()):
        if base.__name__ == "_CData":
            ctypes._CData = base
            break
if not hasattr(ctypes, "_CData"):
    for base in getattr(ctypes.c_void_p, "__mro__", ()):
        if base.__name__ == "_CData":
            ctypes._CData = base
            break

_orig_cfunctype = ctypes.CFUNCTYPE
_type_proxy_cache: dict = {}


def _is_valid_ctype(tp):
    if tp is None:
        return True
    if isinstance(tp, type):
        try:
            return issubclass(
                tp,
                (
                    ctypes._SimpleCData,
                    ctypes.Structure,
                    ctypes.Union,
                    ctypes._Pointer,
                    ctypes.Array,
                    ctypes._CFuncPtr,
                ),
            )
        except TypeError:
            return False
    return False


def _sanitize_ctype(tp):
    if _is_valid_ctype(tp):
        return tp
    if tp in _type_proxy_cache:
        return _type_proxy_cache[tp]

    orig_from_param = getattr(tp, "from_param", None)

    class _PyOpenGLTypeProxy(ctypes.c_void_p):
        @classmethod
        def from_param(cls, value):
            if value is None:
                return None
            if orig_from_param is not None:
                try:
                    res = orig_from_param(value)
                    if isinstance(res, ctypes._CData) or hasattr(
                        res, "_as_parameter_"
                    ):
                        return res
                except Exception:
                    pass
            if isinstance(value, (bytes, bytearray)):
                return ctypes.c_char_p(bytes(value))
            if isinstance(value, str):
                return ctypes.c_char_p(value.encode("utf-8"))
            if isinstance(value, int):
                return ctypes.c_void_p(value)
            if isinstance(value, ctypes._CData):
                return (
                    ctypes.byref(value)
                    if not isinstance(
                        value,
                        (
                            ctypes._Pointer,
                            ctypes.Array,
                            ctypes.c_void_p,
                            ctypes.c_char_p,
                        ),
                    )
                    else value
                )
            if hasattr(value, "ctypes"):
                return value.ctypes.data_as(ctypes.c_void_p)
            return ctypes.c_void_p.from_param(value)

    _PyOpenGLTypeProxy.__name__ = f"Proxy_{getattr(tp, '__name__', 'Param')}"
    _type_proxy_cache[tp] = _PyOpenGLTypeProxy
    return _PyOpenGLTypeProxy


def _py315_safe_cfunctype(restype, *argtypes, **kwargs):
    safe_restype = _sanitize_ctype(restype)
    safe_argtypes = tuple(_sanitize_ctype(a) for a in argtypes)
    try:
        return _orig_cfunctype(restype, *argtypes, **kwargs)
    except (TypeError, ValueError):
        return _orig_cfunctype(safe_restype, *safe_argtypes, **kwargs)


ctypes.CFUNCTYPE = _py315_safe_cfunctype

os.environ["PYOPENGL_PLATFORM"] = "darwin"

try:
    import OpenGL.platform.baseplatform as _bp


    def _safe_function_type_for(self, dll):
        def _builder(restype, *argtypes):
            safe_res = _sanitize_ctype(restype)
            safe_args = tuple(_sanitize_ctype(a) for a in argtypes)
            return _orig_cfunctype(safe_res, *safe_args)

        return _builder


    _bp.BasePlatform.functionTypeFor = _safe_function_type_for
except ImportError:
    pass

_orig_cdll = ctypes.CDLL
_c_func_refs: dict = {}
_FALLBACK_DYLIB = "/usr/lib/libSystem.B.dylib"
_OPENGL_FRAMEWORK = ctypes.util.find_library("OpenGL") or "/System/Library/Frameworks/OpenGL.framework/OpenGL"
_GLFW_DYLIB = None

for _cand in (
    "/opt/homebrew/lib/libglfw.3.dylib",
    "/usr/local/lib/libglfw.3.dylib",
    ctypes.util.find_library("glfw"),
    ctypes.util.find_library("glfw3"),
):
    if _cand and os.path.exists(_cand):
        _GLFW_DYLIB = _cand
        break

try:
    _RAW_MACOS_GL = _orig_cdll(_OPENGL_FRAMEWORK)
except OSError:
    _RAW_MACOS_GL = _orig_cdll(_FALLBACK_DYLIB)

_RAW_GLFW = _orig_cdll(_GLFW_DYLIB) if _GLFW_DYLIB else _RAW_MACOS_GL
_DUMMY_CFUNCTYPE = _orig_cfunctype(ctypes.c_void_p)


def _get_dummy_cfunc(name: str):
    sname = str(name)
    if sname not in _c_func_refs:
        def _noop(*args):
            return 0

        cfunc = _DUMMY_CFUNCTYPE(_noop)
        cfunc.__name__ = sname
        _c_func_refs[sname] = cfunc
    return _c_func_refs[sname]


class SafeMacOSCDLL(_orig_cdll):
    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name.startswith("glfw") and _GLFW_DYLIB:
            try:
                func = _orig_cdll.__getitem__(self, name)
                super().__setattr__(name, func)
                return func
            except Exception:
                pass
        try:
            func = _orig_cdll.__getitem__(self, name)
            super().__setattr__(name, func)
            return func
        except (AttributeError, OSError, KeyError):
            if name.startswith("gl") and not name.startswith("glX") and not name.startswith("glfw"):
                try:
                    func = _orig_cdll.__getitem__(_RAW_MACOS_GL, name)
                    super().__setattr__(name, func)
                    return func
                except Exception:
                    pass
            fn = _get_dummy_cfunc(name)
            super().__setattr__(name, fn)
            return fn


def _mock_cdll(name, *args, **kwargs):
    if isinstance(name, _orig_cdll):
        return name
    sname = str(name) if name else ""
    if "glfw" in sname.lower() and _GLFW_DYLIB:
        return SafeMacOSCDLL(_GLFW_DYLIB, *args, **kwargs)
    return SafeMacOSCDLL(
        _OPENGL_FRAMEWORK if os.path.exists(_OPENGL_FRAMEWORK) else _FALLBACK_DYLIB,
        *args,
        **kwargs,
    )


ctypes.CDLL = _mock_cdll
ctypes.cdll = ctypes.LibraryLoader(_mock_cdll)

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

os.environ["PYOPENGL_PLATFORM"] = "darwin"

COLS = 120
ROWS = 40
CHAR_W = 9
CHAR_H = 18

ANSI_COLORS = {
    30: (0, 0, 0),
    31: (220, 50, 50),
    32: (50, 200, 50),
    33: (220, 220, 50),
    34: (50, 100, 220),
    35: (220, 50, 220),
    36: (50, 200, 200),
    37: (230, 230, 230),
    90: (120, 120, 120),
    91: (255, 90, 90),
    92: (90, 255, 90),
    93: (255, 255, 90),
    94: (90, 160, 255),
    95: (255, 90, 255),
    96: (90, 255, 255),
    97: (255, 255, 90),
}


def player_panel_rects(cols=COLS, rows=ROWS, char_w=CHAR_W, char_h=CHAR_H, origin_x=0, origin_y=0, mode="NORMAL"):
    def box(col, row, box_cols, box_rows):
        return (
            float(origin_x + col * char_w),
            float(origin_y + row * char_h),
            float(box_cols * char_w),
            float(box_rows * char_h),
        )

    m = str(mode).upper()
    if m == "MICRO":
        return box(2, 0, max(20, cols - 4), rows), (0.0, 0.0, 0.0, 0.0)
    elif m == "MINI":
        return box(2, 0, max(20, cols - 4), 3), box(2, 3, max(20, cols - 4), max(1, rows - 3))
    elif m == "TRACKLIST":
        iw = max(20, cols - 4)
        if rows <= 7:
            return box(2, 0, iw, rows), (0.0, 0.0, 0.0, 0.0)
        return box(2, 0, iw, 7), box(2, 7, iw, max(1, rows - 7))
    else:
        iw = max(20, cols - 6)
        # Playlist container box precisely aligned right below VU meters and ending above the help/status bars
        before = 16
        body_rows = 15
        return box(2, 0, iw + 2, 4), box(2, before, iw + 2, body_rows)


def player_argv(mode="NORMAL", extra_args=None):
    cmd = [sys.executable, str(ROOT / "MP_Audio_Player.py"), "--interactive"]
    m = str(mode).upper()
    if m == "MINI":
        cmd.append("--mini")
    elif m == "MICRO":
        cmd.append("--micro")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _child_env():
    env = {key: value for key, value in os.environ.items()}
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    env["MP_LIQUID_GLASS"] = "0"
    env["MP_LIQUID_GLASS_BACKEND"] = "none"
    env["PYTHONUNBUFFERED"] = "1"
    return env


class TerminalOverlay:
    """Fixed absolute coordinate terminal overlay with Retina scaling support."""

    def __init__(self, cols=COLS, rows=ROWS, char_w=CHAR_W, char_h=CHAR_H):
        self.cols = cols
        self.rows = rows
        self.char_w = char_w
        self.char_h = char_h
        self.grid: list[list[str]] = [[" " for _ in range(cols)] for _ in range(rows)]
        self.colors: list[list[tuple]] = [[(200, 235, 255) for _ in range(cols)] for _ in range(rows)]
        self.cursor_row = 0
        self.cursor_col = 0
        self.current_fg = (200, 235, 255)
        self._buf = bytearray()
        self.dirty = True
        self.texture_id = 0
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self._initialized_gl = False
        self.font = None
        self.image = None
        self.img_w = self.cols * self.char_w
        self.img_h = self.rows * self.char_h
        self._last_scale_x = 1.0
        self._last_scale_y = 1.0

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
                glCreateShader,
                glShaderSource,
                glCompileShader,
                glCreateProgram,
                glAttachShader,
                glLinkProgram,
                glGenVertexArrays,
                glBindVertexArray,
                glGenBuffers,
                glBindBuffer,
                glBufferData,
                glVertexAttribPointer,
                glEnableVertexAttribArray,
                GL_VERTEX_SHADER,
                GL_FRAGMENT_SHADER,
                GL_ARRAY_BUFFER,
                GL_DYNAMIC_DRAW,
                GL_FLOAT,
                GL_FALSE,
                glGenTextures,
                glBindTexture,
                glTexParameteri,
                glTexImage2D,
                GL_TEXTURE_2D,
                GL_TEXTURE_MIN_FILTER,
                GL_TEXTURE_MAG_FILTER,
                GL_NEAREST,
                GL_TEXTURE_WRAP_S,
                GL_TEXTURE_WRAP_T,
                GL_CLAMP_TO_EDGE,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
            )

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

    def _clamp_cursor(self):
        self.cursor_row = max(0, min(self.rows - 1, self.cursor_row))
        self.cursor_col = max(0, min(self.cols - 1, self.cursor_col))

    def feed(self, data: bytes):
        if not data:
            return
        self._buf.extend(data)
        try:
            text = self._buf.decode("utf-8", errors="replace")
        except Exception:
            return

        i = 0
        n = len(text)
        consumed = 0

        while i < n:
            ch = text[i]
            if ch == "\x1b":
                if i + 1 >= n:
                    break
                if text[i + 1] == "[":
                    end = i + 2
                    while end < n and not (64 <= ord(text[end]) <= 126):
                        end += 1
                    if end >= n:
                        break
                    cmd = text[end]
                    param_str = text[i + 2 : end]
                    params = []
                    for p in param_str.split(";"):
                        clean_p = re.sub(r"[^0-9]", "", p)
                        params.append(int(clean_p) if clean_p else 0)

                    if cmd == "m":
                        self._apply_sgr(params if params else [0])
                    elif cmd in ("H", "f"):
                        r = params[0] if len(params) > 0 and params[0] > 0 else 1
                        c = params[1] if len(params) > 1 and params[1] > 0 else 1
                        self.cursor_row = r - 1
                        self.cursor_col = c - 1
                        self._clamp_cursor()
                    elif cmd == "A":
                        self.cursor_row -= max(1, params[0] if params else 1)
                        self._clamp_cursor()
                    elif cmd == "B":
                        self.cursor_row += max(1, params[0] if params else 1)
                        self._clamp_cursor()
                    elif cmd == "C":
                        self.cursor_col += max(1, params[0] if params else 1)
                        self._clamp_cursor()
                    elif cmd == "D":
                        self.cursor_col -= max(1, params[0] if params else 1)
                        self._clamp_cursor()
                    elif cmd == "G":
                        self.cursor_col = (params[0] if params else 1) - 1
                        self._clamp_cursor()
                    elif cmd in ("L", "M", "S", "T", "r"):
                        pass
                    elif cmd == "J":
                        if not params or params[0] == 2:
                            for r in range(self.rows):
                                for c in range(self.cols):
                                    self.grid[r][c] = " "
                            self.cursor_row = 0
                            self.cursor_col = 0
                            self.dirty = True
                    elif cmd == "K":
                        if 0 <= self.cursor_row < self.rows:
                            for c in range(self.cursor_col, self.cols):
                                self.grid[self.cursor_row][c] = " "
                            self.dirty = True
                    i = end + 1
                    consumed = i
                    continue
                else:
                    if i + 1 < n:
                        i += 2
                        consumed = i
                        continue
                    break
            elif ch == "\n":
                self.cursor_row += 1
                self.cursor_col = 0
                if self.cursor_row >= self.rows:
                    self.cursor_row = self.rows - 1
                self.dirty = True
            elif ch == "\r":
                self.cursor_col = 0
            elif ord(ch) >= 32:
                if 0 <= self.cursor_row < self.rows and 0 <= self.cursor_col < self.cols:
                    if (
                        self.grid[self.cursor_row][self.cursor_col] != ch
                        or self.colors[self.cursor_row][self.cursor_col] != self.current_fg
                    ):
                        self.grid[self.cursor_row][self.cursor_col] = ch
                        self.colors[self.cursor_row][self.cursor_col] = self.current_fg
                        self.dirty = True
                    self.cursor_col += 1
                    if self.cursor_col >= self.cols:
                        self.cursor_col = self.cols - 1
                        self.dirty = True
            i += 1
            consumed = i

        if consumed > 0:
            try:
                remaining = text[consumed:].encode("utf-8", errors="replace")
                self._buf = bytearray(remaining)
            except Exception:
                self._buf.clear()

    def _apply_sgr(self, params):
        idx = 0
        while idx < len(params):
            p = params[idx]
            if p == 0:
                self.current_fg = (200, 235, 255)
            elif 30 <= p <= 37:
                self.current_fg = ANSI_COLORS.get(p, (200, 235, 255))
            elif 90 <= p <= 97:
                self.current_fg = ANSI_COLORS.get(p, (100, 255, 255))
            elif p == 38:
                if idx + 4 < len(params) and params[idx + 1] == 2:
                    r = params[idx + 2]
                    g = params[idx + 3]
                    b = params[idx + 4]
                    self.current_fg = (r, g, b)
                    idx += 4
            idx += 1

    def render(self, fw, fh, ww, wh):
        if not self._initialized_gl:
            self.init_gl()
        if not self._initialized_gl or not self.shader_program:
            return

        scale_x = float(fw) / float(ww) if ww > 0 else 1.0
        scale_y = float(fh) / float(wh) if wh > 0 else 1.0

        target_img_w = int(self.cols * self.char_w * scale_x)
        target_img_h = int(self.rows * self.char_h * scale_y)

        if self.image is None or self.image.size != (target_img_w, target_img_h) or abs(scale_x - self._last_scale_x) > 0.01:
            self.img_w = target_img_w
            self.img_h = target_img_h
            self._last_scale_x = scale_x
            self._last_scale_y = scale_y
            scaled_font_size = max(8, int(13 * scale_y))
            try:
                from PIL import Image, ImageFont

                font_loaded = False
                for font_path in [
                    "/System/Library/Fonts/SFNSMono.ttf",
                    "/System/Library/Fonts/Monaco.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/Library/Fonts/Courier New.ttf",
                ]:
                    if os.path.exists(font_path):
                        self.font = ImageFont.truetype(font_path, scaled_font_size)
                        font_loaded = True
                        break
                if not font_loaded:
                    self.font = ImageFont.load_default()
            except Exception:
                pass
            self.image = Image.new("RGBA", (self.img_w, self.img_h), (0, 0, 0, 0))
            self.dirty = True

            try:
                from OpenGL.GL import glBindTexture, glTexImage2D, GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE
                glBindTexture(GL_TEXTURE_2D, self.texture_id)
                glTexImage2D(
                    GL_TEXTURE_2D,
                    0,
                    GL_RGBA,
                    self.img_w,
                    self.img_h,
                    0,
                    GL_RGBA,
                    GL_UNSIGNED_BYTE,
                    None,
                )
                glBindTexture(GL_TEXTURE_2D, 0)
            except Exception:
                pass

        try:
            from OpenGL.GL import (
                glUseProgram,
                glBindVertexArray,
                glDrawArrays,
                glBindBuffer,
                glBufferData,
                glDisable,
                glEnable,
                glBlendFunc,
                GL_DEPTH_TEST,
                GL_BLEND,
                GL_SRC_ALPHA,
                GL_ONE_MINUS_SRC_ALPHA,
                GL_TRIANGLES,
                GL_ARRAY_BUFFER,
                GL_DYNAMIC_DRAW,
                glBindTexture,
                GL_TEXTURE_2D,
                glTexImage2D,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
            )
            import numpy as np
            from PIL import ImageDraw

            if self.dirty and self.image:
                self.image.paste((0, 0, 0, 0), [0, 0, self.img_w, self.img_h])
                draw = ImageDraw.Draw(self.image)
                s_char_w = self.char_w * scale_x
                s_char_h = self.char_h * scale_y
                for r in range(self.rows):
                    y = int(r * s_char_h)
                    for c in range(self.cols):
                        ch = self.grid[r][c]
                        if ch != " ":
                            x = int(c * s_char_w)
                            col = self.colors[r][c]
                            draw.text((x, y), ch, fill=(col[0], col[1], col[2], 255), font=self.font)

                glBindTexture(GL_TEXTURE_2D, self.texture_id)
                glTexImage2D(
                    GL_TEXTURE_2D,
                    0,
                    GL_RGBA,
                    self.img_w,
                    self.img_h,
                    0,
                    GL_RGBA,
                    GL_UNSIGNED_BYTE,
                    self.image.tobytes("raw", "RGBA", 0, 1),
                )
                glBindTexture(GL_TEXTURE_2D, 0)
                self.dirty = False

            bezel = float(getattr(LiquidGlassRendererOpenGL, "bezel_px", 12.0))
            x_off = bezel * scale_x
            y_off = bezel * scale_y

            x1 = -1.0 + (2.0 * x_off / fw)
            x2 = x1 + (2.0 * self.img_w / fw)
            y2 = 1.0 - (2.0 * y_off / fh)
            y1 = y2 - (2.0 * self.img_h / fh)

            quad_data = np.array(
                [
                    x1, y1, 0.0, 1.0,
                    x2, y1, 1.0, 1.0,
                    x1, y2, 0.0, 0.0,
                    x2, y1, 1.0, 1.0,
                    x2, y2, 1.0, 0.0,
                    x1, y2, 0.0, 0.0,
                ],
                dtype=np.float32,
            )

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
    def __init__(self, overlay, host_ref, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.overlay = overlay
        self.host_ref = host_ref
        self._on_key_ref = None
        self._on_mouse_btn_ref = None
        self._on_cursor_pos_ref = None
        self._dragging = False
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0
        
        # Window transparency reduced by 20% (Default clear opacity set to 0.60 instead of 0.80)
        self.clear_opacity = 0.60
        self.slider_val = 0.60
        self._slider_dragging = False

    def open(self):
        super().open()
        self._bind_callbacks()
        # Apply initial 60% opacity to macOS window via GLFW
        if hasattr(self, "_glfw") and hasattr(self._glfw, "glfwSetWindowOpacity") and self._window:
            try:
                self._glfw.glfwSetWindowOpacity.argtypes = [ctypes.c_void_p, ctypes.c_float]
                self._glfw.glfwSetWindowOpacity(self._window, ctypes.c_float(self.clear_opacity))
            except Exception:
                pass
        if hasattr(self._glfw, "glfwSwapInterval") and self._window:
            self._glfw.glfwSwapInterval(1)
        return self

    def _bind_callbacks(self):
        from ctypes import CFUNCTYPE, c_void_p, c_int, c_double, POINTER

        if hasattr(self._glfw, "glfwSetWindowOpacity"):
            self._glfw.glfwSetWindowOpacity.argtypes = [c_void_p, ctypes.c_float]

        @CFUNCTYPE(None, c_void_p, c_int, c_int, c_int)
        def mouse_button_callback(_window, button, action, mods):
            if button == 0:  # Left mouse button
                xpos = c_double()
                ypos = c_double()
                if hasattr(self._glfw, "glfwGetCursorPos"):
                    self._glfw.glfwGetCursorPos(_window, ctypes.byref(xpos), ctypes.byref(ypos))
                
                ww, wh = self.window_size()
                # Check if click is inside the bottom slider bar region (bottom 35 pixels)
                if wh - ypos.value <= 35 and 40 <= xpos.value <= ww - 40:
                    if action == 1:  # Pressed
                        self._slider_dragging = True
                        self._update_slider(xpos.value, ww)
                    elif action == 0:
                        self._slider_dragging = False
                else:
                    if action == 1:  # Pressed
                        self._dragging = True
                        self._drag_start_x = xpos.value
                        self._drag_start_y = ypos.value
                    elif action == 0:  # Released
                        self._dragging = False
                        self._slider_dragging = False

        @CFUNCTYPE(None, c_void_p, c_double, c_double)
        def cursor_pos_callback(_window, xpos, ypos):
            ww, wh = self.window_size()
            if self._slider_dragging:
                self._update_slider(xpos, ww)
            elif self._dragging:
                dx = xpos - self._drag_start_x
                dy = ypos - self._drag_start_y
                x_win = c_int()
                y_win = c_int()
                if hasattr(self._glfw, "glfwGetWindowPos") and hasattr(self._glfw, "glfwSetWindowPos"):
                    self._glfw.glfwGetWindowPos(_window, ctypes.byref(x_win), ctypes.byref(y_win))
                    self._glfw.glfwSetWindowPos(_window, int(x_win.value + dx), int(y_win.value + dy))

        @CFUNCTYPE(None, c_void_p, c_int, c_int, c_int, c_int)
        def key_callback(_window, key, scancode, action, mods):
            if action in (1, 2):
                if key in (81, 256):
                    os._exit(0)
                char_map = {
                    257: b"\n",
                    259: b"\x7f",
                    262: b"\x1b[C",
                    263: b"\x1b[D",
                    264: b"\x1b[B",
                    265: b"\x1b[A",
                }
                if key in char_map:
                    self.host_ref.send_input(char_map[key])
                elif 32 <= key <= 126:
                    char_byte = chr(key).encode("utf-8")
                    if mods & 1 == 0:
                        char_byte = char_byte.lower()
                    self.host_ref.send_input(char_byte)

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

            if hasattr(self._glfw, "glfwGetCursorPos"):
                self._glfw.glfwGetCursorPos.argtypes = [c_void_p, POINTER(c_double), POINTER(c_double)]
            if hasattr(self._glfw, "glfwGetWindowPos"):
                self._glfw.glfwGetWindowPos.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
            if hasattr(self._glfw, "glfwSetWindowPos"):
                self._glfw.glfwSetWindowPos.argtypes = [c_void_p, c_int, c_int]

    def _update_slider(self, xpos, ww):
        slider_left = 40.0
        slider_right = max(80.0, float(ww) - 40.0)
        t = max(0.0, min(1.0, (xpos - slider_left) / (slider_right - slider_left)))
        
        # Map t (0.0 to 1.0) to opacity range 40% to 80% (0.40 to 0.80)
        self.slider_val = 0.40 + t * (0.80 - 0.40)
        self.clear_opacity = self.slider_val

        # Update macOS native window opacity via GLFW
        if hasattr(self, "_glfw") and hasattr(self._glfw, "glfwSetWindowOpacity") and self._window:
            try:
                self._glfw.glfwSetWindowOpacity(self._window, ctypes.c_float(self.clear_opacity))
            except Exception:
                pass

        # Fallback for X11 / Linux environments if applicable
        win = self.x11_window() if hasattr(self, "x11_window") else None
        if win:
            self._set_opacity(win, self.clear_opacity)

    def draw(self, theme_name, opacity=1.0, capture=False):
        if not self.poll():
            return None
        fw, fh = self.framebuffer_size()
        ww, wh = self.window_size()
        if fw < 2 or fh < 2 or ww < 2 or wh < 2:
            return None

        scale_x = float(fw) / float(ww) if ww > 0 else 1.0
        scale_y = float(fh) / float(wh) if wh > 0 else 1.0

        if self.window_size() != self._shape_size:
            self._apply_shape()

        from OpenGL import GL

        GL.glViewport(0, 0, fw, fh)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
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
        GL.glUniform4f(u["u_themeB"], b[0], b[1], b[2], float(self.cursor[1]) / max(1.0, float(fw)))
        GL.glUniform4f(u["u_themeC"], c[0], c[1], c[2], float(effective_opacity))
        GL.glUniform4f(u["u_bezel"], float(self.bezel_px) * scale_x, float(self.radius_px) * scale_y, 0.0, 1.0)

        p0 = self.panels[0]
        p1 = self.panels[1]
        GL.glUniform4f(u["u_panel0"], float(p0[0]) * scale_x, float(p0[1]) * scale_y, float(p0[2]) * scale_x, float(p0[3]) * scale_y)
        GL.glUniform4f(u["u_panel1"], float(p1[0]) * scale_x, float(p1[1]) * scale_y, float(p1[2]) * scale_x, float(p1[3]) * scale_y)

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

        self.overlay.render(fw, fh, ww, wh)
        
        # Draw interactive bottom slider bar for transparency control (40% to 80%)
        self._draw_transparency_slider(fw, fh, ww, wh)

        pixels = None
        if capture:
            raw = GL.glReadPixels(0, 0, fw, fh, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            pixels = self._format_capture(fw, fh, raw)

        self._glfw.glfwSwapBuffers(self._window)
        return pixels

    def _draw_transparency_slider(self, fw, fh, ww, wh):
        try:
            from OpenGL.GL import (
                glUseProgram, glGenVertexArrays, glBindVertexArray, glGenBuffers,
                glBindBuffer, glBufferData, glVertexAttribPointer, glEnableVertexAttribArray,
                glDrawArrays, glDisable, glEnable, glBlendFunc, GL_BLEND, GL_SRC_ALPHA,
                GL_ONE_MINUS_SRC_ALPHA, GL_TRIANGLES, GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW,
                GL_FLOAT, GL_FALSE, glUniform4f, glCreateShader, glShaderSource,
                glCompileShader, glCreateProgram, glAttachShader, glLinkProgram,
                GL_VERTEX_SHADER, GL_FRAGMENT_SHADER
            )
            import numpy as np

            if not hasattr(self, "_slider_prog"):
                vs_src = b"""
                #version 410 core
                layout(location = 0) in vec2 a_pos;
                void main() {
                    gl_Position = vec4(a_pos, 0.0, 1.0);
                }
                """
                fs_src = b"""
                #version 410 core
                uniform vec4 u_color;
                out vec4 fragColor;
                void main() {
                    fragColor = u_color;
                }
                """
                vs = glCreateShader(GL_VERTEX_SHADER)
                glShaderSource(vs, vs_src)
                glCompileShader(vs)
                fs = glCreateShader(GL_FRAGMENT_SHADER)
                glShaderSource(fs, fs_src)
                glCompileShader(fs)
                self._slider_prog = glCreateProgram()
                glAttachShader(self._slider_prog, vs)
                glAttachShader(self._slider_prog, fs)
                glLinkProgram(self._slider_prog)
                self._slider_vao = glGenVertexArrays(1)
                self._slider_vbo = glGenBuffers(1)

            x_left = 40.0
            x_right = float(ww) - 40.0
            y_track = 18.0
            
            ndc_x1 = (x_left / ww) * 2.0 - 1.0
            ndc_x2 = (x_right / ww) * 2.0 - 1.0
            ndc_y1 = ((wh - y_track - 4.0) / wh) * -2.0 + 1.0
            ndc_y2 = ((wh - y_track + 4.0) / wh) * -2.0 + 1.0

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glUseProgram(self._slider_prog)
            glBindVertexArray(self._slider_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._slider_vbo)

            track_quad = np.array([
                ndc_x1, ndc_y1,  ndc_x2, ndc_y1,  ndc_x1, ndc_y2,
                ndc_x2, ndc_y1,  ndc_x2, ndc_y2,  ndc_x1, ndc_y2
            ], dtype=np.float32)

            from OpenGL.GL import glGetUniformLocation
            u_col_loc = glGetUniformLocation(self._slider_prog, "u_color")
            
            glUniform4f(u_col_loc, 0.2, 0.4, 0.6, 0.6)
            glBufferData(GL_ARRAY_BUFFER, track_quad.nbytes, track_quad, GL_DYNAMIC_DRAW)
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            glDrawArrays(GL_TRIANGLES, 0, 6)

            t = (self.slider_val - 0.40) / (0.80 - 0.40)
            thumb_x = x_left + t * (x_right - x_left)
            
            t_x1 = ((thumb_x - 6.0) / ww) * 2.0 - 1.0
            t_x2 = ((thumb_x + 6.0) / ww) * 2.0 - 1.0
            t_y1 = ((wh - y_track - 10.0) / wh) * -2.0 + 1.0
            t_y2 = ((wh - y_track + 10.0) / wh) * -2.0 + 1.0

            thumb_quad = np.array([
                t_x1, t_y1,  t_x2, t_y1,  t_x1, t_y2,
                t_x2, t_y1,  t_x2, t_y2,  t_x1, t_y2
            ], dtype=np.float32)

            glUniform4f(u_col_loc, 0.6, 0.8, 1.0, 0.9)
            glBufferData(GL_ARRAY_BUFFER, thumb_quad.nbytes, thumb_quad, GL_DYNAMIC_DRAW)
            glDrawArrays(GL_TRIANGLES, 0, 6)

            glBindVertexArray(0)
            glUseProgram(0)
        except Exception as e:
            print(f"Slider draw error: {e}", flush=True)


class OpenGLGlassHost:
    def __init__(self, mode="NORMAL", cli_theme=None):
        self.mode = mode.upper()
        self.cli_theme = cli_theme
        self.renderer = None
        self.child_pid = 0
        self.master_fd = None
        self._target_cols = COLS
        self._target_rows = ROWS
        self.overlay = TerminalOverlay(COLS, ROWS)

    def send_input(self, data: bytes):
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, data)
            except OSError:
                pass

    def _sync_panels(self):
        if self.renderer is None:
            return
        char_w = CHAR_W
        char_h = CHAR_H
        margin = self.renderer.bezel_px
        self.renderer.set_panels(
            player_panel_rects(
                self._target_cols, self._target_rows, char_w, char_h, margin, margin, mode=self.mode
            )
        )

    def run(self):
        self.master_fd, slave_fd = pty.openpty()
        winsize = struct.pack("HHHH", ROWS, COLS, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

        extra = []
        if self.cli_theme:
            extra.extend(["--theme", self.cli_theme])
        command = player_argv(mode=self.mode, extra_args=extra)

        pid = os.fork()
        if pid == 0:
            os.close(self.master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            try:
                err_log = open(str(ROOT / "player_stderr.log"), "w")
                os.dup2(err_log.fileno(), 2)
            except Exception:
                os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            env = _child_env()
            os.execvpe(command[0], command, env)
            sys.exit(1)

        os.close(slave_fd)
        self.child_pid = pid

        char_w = CHAR_W
        char_h = CHAR_H
        margin = LiquidGlassRendererOpenGL.bezel_px
        init_w = self._target_cols * char_w + (2 * margin)
        init_h = self._target_rows * char_h + (2 * margin)
        title = "MP Audio Player (Liquid Glass - OpenGL / macOS)"

        self.renderer = CustomGlassRenderer(
            overlay=self.overlay, host_ref=self, width=init_w, height=init_h, title=title
        )
        self.renderer.open()
        self._sync_panels()

        theme = read_player_theme()
        theme_at = 0.0
        print("DEBUG: Entering OpenGL event loop...", flush=True)

        try:
            while not self.renderer.should_close:
                now = time.monotonic()
                if now - theme_at > 0.4:
                    theme = read_player_theme()
                    theme_at = now

                if self.master_fd is not None:
                    r, _, _ = select.select([self.master_fd], [], [], 0.0)
                    if self.master_fd in r:
                        try:
                            data = os.read(self.master_fd, 16384)
                            if data:
                                self.overlay.feed(data)
                        except OSError:
                            pass

                self.renderer.poll()
                self.renderer.draw(theme)

                pid_res, _ = os.waitpid(self.child_pid, os.WNOHANG)
                if pid_res == self.child_pid:
                    break
        finally:
            if self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except OSError:
                    pass
            if self.child_pid:
                try:
                    os.kill(self.child_pid, signal.SIGTERM)
                    time.sleep(0.05)
                    os.kill(self.child_pid, signal.SIGKILL)
                except OSError:
                    pass
            if self.renderer:
                self.renderer.close()
                self.renderer = None

        return True


def main():
    theme_arg = None
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ("--theme", "-t") and i + 1 < len(sys.argv):
            theme_arg = sys.argv[i + 1]
            i += 2
            continue
        i += 1

    host = OpenGLGlassHost(mode="NORMAL", cli_theme=theme_arg)
    host.run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        sys.exit(1)
