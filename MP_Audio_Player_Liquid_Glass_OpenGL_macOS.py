#!/usr/bin/env python3
"""
MP Audio Player - Liquid Glass OpenGL Host (macOS Single-Window Edition)
Renders a fluid glass UI and blits the player's PTY text buffer as an 
OpenGL texture inside a single, unified window.
"""

import os
import sys
import pty
import select
import struct
import fcntl
import termios
import OpenGL
OpenGL.ERROR_CHECKING = False

from OpenGL.GL import *
import glfw
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --- macOS Compatibility Patch for Missing Linux GLX Symbols ---
import ctypes
import ctypes.util
try:
    _opengl_lib = ctypes.CDLL(ctypes.util.find_library("OpenGL"))
    if not hasattr(_opengl_lib, "glXGetCurrentContext"):
        _opengl_lib.glXGetCurrentContext = lambda: None
        _opengl_lib.glXGetCurrentDisplay = lambda: None
except Exception:
    pass

# --- Configuration & Layout ---
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
COLS = 120
ROWS = 35

class ANSIParser:
    """Parses standard ANSI escape sequences from the audio player PTY stream."""
    def __init__(self, cols=COLS, rows=ROWS):
        self.cols = cols
        self.rows = rows
        self.buffer = [[" " for _ in range(cols)] for _ in range(rows)]
        self.fg_color = (200, 220, 255, 255)
        self.cursor_x = 0
        self.cursor_y = 0

    def write(self, data):
        i = 0
        n = len(data)
        while i < n:
            char = data[i]
            if char == '\033' and i + 1 < n and data[i+1] == '[':
                i += 2
                param_str = ""
                while i < n and (data[i].isdigit() or data[i] == ';'):
                    param_str += data[i]
                    i += 1
                if i < n:
                    cmd = data[i]
                    self._handle_csi(param_str, cmd)
                    i += 1
            elif char == '\n':
                self.cursor_x = 0
                self.cursor_y = min(self.rows - 1, self.cursor_y + 1)
                i += 1
            elif char == '\r':
                self.cursor_x = 0
                i += 1
            elif ord(char) >= 32:
                if self.cursor_y < self.rows and self.cursor_x < self.cols:
                    self.buffer[self.cursor_y][self.cursor_x] = char
                    self.cursor_x += 1
                    if self.cursor_x >= self.cols:
                        self.cursor_x = 0
                        self.cursor_y = min(self.rows - 1, self.cursor_y + 1)
                i += 1
            else:
                i += 1

    def _handle_csi(self, param_str, cmd):
        params = [int(p) for p in param_str.split(';')] if param_str else [0]
        if cmd == 'H' or cmd == 'f':
            self.cursor_y = max(0, min(self.rows - 1, (params[0] - 1 if len(params) > 0 and params[0] > 0 else 0)))
            self.cursor_x = max(0, min(self.cols - 1, (params[1] - 1 if len(params) > 1 and params[1] > 0 else 0)))
        elif cmd == 'J':
            if params[0] == 2:
                self.buffer = [[" " for _ in range(self.cols)] for _ in range(self.rows)]
                self.cursor_x = 0
                self.cursor_y = 0


class TerminalOverlay:
    """Renders the parsed ANSI buffer as a dynamic texture mapped inside the OpenGL glass window."""
    def __init__(self, cols=COLS, rows=ROWS):
        self.cols = cols
        self.rows = rows
        self.parser = ANSIParser(cols, rows)
        
        # Setup PTY
        self.master_fd, self.slave_fd = pty.openpty()
        s = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, s)

        # Spawn audio player headless backend process via PTY
        self.pid = os.fork()
        if self.pid == 0:
            os.setsid()
            os.dup2(self.slave_fd, 0)
            os.dup2(self.slave_fd, 1)
            os.dup2(self.slave_fd, 2)
            os.close(self.master_fd)
            
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["PYTHONUNBUFFERED"] = "1"
            
            # Change to your actual backend player entry point if needed
            os.execve("/usr/bin/env", ["python3", "player_backend.py"], env)
            os._exit(1)
        else:
            os.close(self.slave_fd)
            fl = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        # Setup Pillow Font & Texture Dimensions
        self.char_w = 8
        self.char_height = 16
        try:
            self.font = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 13)
        except IOError:
            self.font = ImageFont.load_default()

        self.tex_width = cols * self.char_w
        self.tex_height = rows * self.char_height
        
        # Create OpenGL texture handle
        self.texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    def update(self):
        r, _, _ = select.select([self.master_fd], [], [], 0.0)
        if r:
            try:
                data = os.read(self.master_fd, 4096).decode('utf-8', errors='ignore')
                if data:
                    self.parser.write(data)
            except OSError:
                pass

    def render_glass_ui(self):
        self.update()

        # 1. Rasterize terminal text grid to an in-memory PIL Image
        img = Image.new("RGBA", (self.tex_width, self.tex_height), (15, 18, 25, 210))
        draw = ImageDraw.Draw(img)

        for r_idx, row in enumerate(self.parser.buffer):
            line_str = "".join(row)
            draw.text((4, r_idx * self.char_height + 2), line_str, font=self.font, fill=(210, 225, 255, 255))

        img_data = img.tobytes("raw", "RGBA", 0, 1)

        # 2. Upload to GPU texture
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.tex_width, self.tex_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)

        # 3. Setup Orthographic Projection for 2D Blitting
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, WINDOW_WIDTH, WINDOW_HEIGHT, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Draw Liquid Glass Panel Frame
        glColor4f(0.08, 0.09, 0.12, 0.85)
        glBegin(GL_QUADS)
        glVertex2f(30, 30)
        glVertex2f(WINDOW_WIDTH - 30, 30)
        glVertex2f(WINDOW_WIDTH - 30, WINDOW_HEIGHT - 30)
        glVertex2f(30, WINDOW_HEIGHT - 30)
        glEnd()

        # Draw Glass Border Frame
        glColor4f(0.35, 0.45, 0.7, 0.5)
        glLineWidth(1.5)
        glBegin(GL_LINE_LOOP)
        glVertex2f(30, 30)
        glVertex2f(WINDOW_WIDTH - 30, 30)
        glVertex2f(WINDOW_WIDTH - 30, WINDOW_HEIGHT - 30)
        glVertex2f(30, WINDOW_HEIGHT - 30)
        glEnd()

        # 4. Render the Terminal Text Texture inside the Glass Box
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glColor4f(1.0, 1.0, 1.0, 1.0)

        tx1, ty1 = 45, 45
        tx2, ty2 = tx1 + self.tex_width, ty1 + self.tex_height

        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(tx1, ty1)
        glTexCoord2f(1.0, 0.0); glVertex2f(tx2, ty1)
        glTexCoord2f(1.0, 1.0); glVertex2f(tx2, ty2)
        glTexCoord2f(0.0, 1.0); glVertex2f(tx1, ty2)
        glEnd()
        glDisable(GL_TEXTURE_2D)


def main():
    if not glfw.init():
        sys.exit(1)

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "MP Audio Player - Liquid Glass", None, None)
    if not window:
        glfw.terminate()
        sys.exit(1)

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    overlay = TerminalOverlay()

    while not glfw.window_should_close(window):
        glfw.poll_events()

        glClearColor(0.03, 0.03, 0.05, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        overlay.render_glass_ui()

        glfw.swap_buffers(window)

    glfw.terminate()

if __name__ == "__main__":
    main()