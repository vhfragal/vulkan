import os
import sys
import glob
import ctypes

from config import RENDER_SIZE

if sys.platform.startswith("linux"):
    os.environ["SDL_VIDEODRIVER"] = "x11"

import pygame
from pygame._sdl2.video import Window as SDL2Window


class _SDL_SysWMinfo_X11(ctypes.Structure):
    _fields_ = [("display", ctypes.c_void_p), ("window", ctypes.c_ulong)]


class _SDL_SysWMinfo_Win(ctypes.Structure):
    _fields_ = [
        ("window", ctypes.c_void_p),
        ("hdc", ctypes.c_void_p),
        ("hinstance", ctypes.c_void_p),
    ]

class _SDL_SysWMinfo_Union(ctypes.Union):
    _fields_ = [
        ("x11", _SDL_SysWMinfo_X11),
        ("win", _SDL_SysWMinfo_Win),
        ("dummy", ctypes.c_uint8 * 64),
    ]


class _SDL_SysWMinfo(ctypes.Structure):
    _fields_ = [
        ("major", ctypes.c_uint8),
        ("minor", ctypes.c_uint8),
        ("patch", ctypes.c_uint8),
        ("subsystem", ctypes.c_int),
        ("info", _SDL_SysWMinfo_Union),
    ]


def _load_pygame_sdl2():
    pg_dir = os.path.dirname(pygame.__file__)
    parent_dir = os.path.dirname(pg_dir)
    search_dirs = [
        pg_dir,
        os.path.join(parent_dir, "pygame_ce.libs"),
        os.path.join(parent_dir, "pygame.libs"),
    ]

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        search_dirs.extend([
            exe_dir,
            os.path.join(exe_dir, "lib"),
            os.path.join(exe_dir, "lib", "pygame"),
            os.path.join(exe_dir, "lib", "pygame_ce.libs"),
        ])

    ext_glob = "*SDL2*.dll" if sys.platform == "win32" else "*SDL2*.so*"
    default_lib = "SDL2.dll" if sys.platform == "win32" else "libSDL2-2.0.so.0"

    for folder in search_dirs:
        matches = glob.glob(os.path.join(folder, ext_glob))
        if matches:
            return ctypes.CDLL(next(iter(matches)))
    return ctypes.CDLL(default_lib)




class PygameWindowHost:
    def __init__(self, width=RENDER_SIZE[0], height=RENDER_SIZE[1], 
                 title="Pygame-CE + WGPU (Vulkan) 2D Platformer", fullscreen=True):
        #On Windows 10/11 with 125% or 150% display scaling enabled, prevents Windows from stretching a blurred window.
        #ctypes.windll.user32.SetProcessDPIAware()
        pygame.init()        
        # Raw SDL2Window creates an X11 Window WITHOUT attaching a 2D SDL_WindowSurface (prevents BadAccess)
        self.sdl_window = SDL2Window(title=title, size=(width, height))
        if fullscreen:
            # Desktop fullscreen (borderless native resolution, avoids display mode flicker)
            self.sdl_window.set_fullscreen(True)
        self.sdl_window.show()
        pygame.event.pump()
        self.width, self.height = self.sdl_window.size


    def get_wgpu_window_kwargs(self):
        sdl2 = _load_pygame_sdl2()
        sdl2.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
        sdl2.SDL_GetWindowFromID.restype = ctypes.c_void_p
        sdl2.SDL_GetWindowWMInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_SDL_SysWMinfo),
        ]
        sdl2.SDL_GetWindowWMInfo.restype = ctypes.c_int

        win_ptr = sdl2.SDL_GetWindowFromID(self.sdl_window.id)
        if not win_ptr:
            raise RuntimeError("SDL_GetWindowFromID returned NULL")

        wm_info = _SDL_SysWMinfo(major=2, minor=32, patch=0)
        if not sdl2.SDL_GetWindowWMInfo(win_ptr, ctypes.byref(wm_info)):
            raise RuntimeError("SDL_GetWindowWMInfo failed")

        if sys.platform == "win32":
            hinstance = wm_info.info.win.hinstance or ctypes.windll.kernel32.GetModuleHandleW(None)
            return {
                "window": int(wm_info.info.win.window),
                "hinstance": int(hinstance),
            }
        elif sys.platform.startswith("linux"):
            return {
                "window": int(wm_info.info.x11.window),
                "display": int(wm_info.info.x11.display),
            }
        raise NotImplementedError(f"Unsupported OS: {sys.platform}")
    

    def close(self):
        self.sdl_window.destroy()
        pygame.quit()
