import os
import sys
import glob
from cx_Freeze import setup, Executable
import wgpu

# HOW TO RUN BUILD
# python setup.py build


# Locate wgpu's native binary (wgpu_native.dll / libwgpu_native.so)
wgpu_dir = os.path.dirname(wgpu.__file__)
wgpu_resources_dir = os.path.join(wgpu_dir, "resources")
native_libs = []
if os.path.isdir(wgpu_resources_dir):
    for f in glob.glob(os.path.join(wgpu_resources_dir, "*wgpu_native*")):
        native_libs.append((f, os.path.join("lib", "wgpu", "resources", os.path.basename(f))))

include_files = [
    ("shaders.wgsl", "shaders.wgsl"),
    *native_libs,
]

build_exe_options = {
    "packages": ["pygame", "wgpu", "cffi"],
    "includes": ["window_host", "wgpu_blitter", "platformer"],
    "include_files": include_files,
    "excludes": ["tkinter", "unittest", "email", "http", "xml", "pydoc"],
}

# Hide the background console window on Windows release builds
#base = None
base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="PygameWgpuPlatformer",
    version="1.0.0",
    description="Pygame-CE + WGPU (Vulkan) 2D Platformer",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "main.py",
            base=base,
            target_name="Platformer.exe" if sys.platform == "win32" else "Platformer",
        )
    ],
)
