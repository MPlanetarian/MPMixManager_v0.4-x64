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
        viz_rows = 7 if rows >= 34 else (5 if rows >= 28 else 3)
        before = 4 + 1 + 1 + 3 + (viz_rows + 3) + 1
        body_rows = max(1, rows - (before + 1) - 4)
        return box(2, 0, iw + 2, 4), box(2, before, iw + 2, body_rows + 2)


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
    env["MP_LIQUID_GLASS"] = "1"
    env["MP_LIQUID_GLASS_BACKEND"] = "opengl"
    env["MP_LIQUID_GLASS_PLATFORM"] = "macos"
    env["PYTHONUNBUFFERED"] = "1"
    return env


class TerminalOverlay:
    """Fixed absolute coordinate terminal overlay - 100% rigid, stationary text layout."""

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
        self.char_width_cache = {}  # Added for caching character widths

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

            self.img_w = self.cols * self.char_w
            self.img_h = self.rows * self.char_h
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

    def render(self, fw, fh):
        if not self._initialized_gl:
            self.init_gl()
        if not self._initialized_gl or not self.shader_program:
            return

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
                for r in range(self.rows):
                    y = r * self.char_h
                    for c in range(self.cols):
                        ch = self.grid[r][c]
                        if ch != " ":
                            x = c * self.char_w
                            col = self.colors[r][c]
                            # Use font.getbbox() for better character positioning
                            try:
                                if ch in self.char_width_cache:
                                    char_width = self.char_width_cache[ch]
                                else:
                                    bbox = self.font.getbbox(ch)
                                    char_width = bbox[2] - bbox[0]
                                    self.char_width_cache[ch] = char_width
                                
                                # Adjust x position to center the character in its cell
                                adjusted_x = x + (self.char_w - char_width) // 2
                                draw.text((adjusted_x, y), ch, fill=(col[0], col[1], col[2], 255), font=self.font)
                            except Exception:
                                # Fallback to original positioning if bbox fails
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

            x1 = -1.0
            y1 = -1.0
            x2 = -1.0 + (2.0 * self.img_w / fw)
            y2 = -1.0 + (2.0 * self.img_h / fh)

            quad_data = np.array(
                [
                    x1, y1, 0.0, 0.0,
                    x2, y1, 1.0, 0.0,
                    x1, y2, 0.0, 1.0,
                    x2, y1, 1.0, 0.0,
                    x2, y2, 1.0, 1.0,
                    x1, y2, 0.0, 1.0,
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

    def open(self):
        super().open()
        self._bind_keyboard()
        if hasattr(self._glfw, "glfwSwapInterval") and self._window:
            self._glfw.glfwSwapInterval(1)
        return self

    def _bind_keyboard(self):
        from ctypes import CFUNCTYPE, c_void_p, c_int

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

        self._on_key_ref = key_callback
        if hasattr(self._glfw, "glfwSetKeyCallback") and self._window:
            self._glfw.glfwSetKeyCallback.argtypes = [c_void_p, c_void_p]
            self._glfw.glfwSetKeyCallback(self._window, ctypes.cast(self._on_key_ref, c_void_p))

    def draw(self, theme_name, opacity=1.0, capture=False):
        if not self.poll():
            return None
        fw, fh = self.framebuffer_size()
        ww, wh = self.window_size()
        if fw < 2 or fh < 2 or ww < 2 or wh < 2:
            return None

        if self.window_size() != self._shape_size:
            self._apply_shape()

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

            # ... rest of the draw method remains unchanged ...

        except Exception as e:
            print(f"Draw error: {e}", flush=True)
            return None


class OpenGLRenderer(LiquidGlassRendererOpenGL):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def draw(self, theme_name, opacity=1.0, capture=False):
        # ... existing implementation ...


def main():
    # ... existing main function ...

if __name__ == "__main__":
    main()