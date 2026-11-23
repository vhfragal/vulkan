import os
import sys
import inspect

# Disable GLES/EGL probing completely so wgpu-hal only initializes Vulkan
os.environ["WGPU_BACKENDS"] = "vulkan,dx12"
os.environ["WGPU_BACKEND_TYPE"] = "Vulkan"
#os.environ["__GL_SYNC_TO_VBLANK"] = "0"  # Disables NVIDIA driver V-Sync on Linux

import pygame
import wgpu

from config import RENDER_SIZE


class WgpuSurfaceBlitter:
    """Uploads a Pygame Surface to a GPU texture and renders it via WGPU on Vulkan."""

    def __init__(self, host, wgsl_path="shaders.wgsl"):
        self.host = host
        self.width = RENDER_SIZE[0]
        self.height = RENDER_SIZE[1]

        self.adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        print(
            f"WGPU Adapter: {self.adapter.info.get('device', 'GPU')} "
            f"({self.adapter.info.get('backend_type', 'Vulkan')})"
        )
        self.device = self.adapter.request_device_sync()

        # Build the present_info dictionary expected by wgpu.gpu.get_canvas_context()
        info = self.host.get_wgpu_window_kwargs()
        if sys.platform == "win32":
            present_info = {
                "platform": "windows",
                "window": info["window"],
                "hinstance": info["hinstance"],
            }
        elif sys.platform.startswith("linux"):
            present_info = {
                "platform": "x11",
                "window": info["window"],
                "display": info["display"],
            }        
        else:
            raise NotImplementedError(f"Unsupported OS: {sys.platform}")

        self.present_context = wgpu.gpu.get_canvas_context(present_info)
        self.present_context.set_physical_size(*host.sdl_window.size)
        self.render_format = self.present_context.get_preferred_format(self.adapter)
        
        cfg_kwargs = {
            "device": self.device,
            "format": self.render_format,
            "usage": wgpu.TextureUsage.RENDER_ATTACHMENT,
        }
        
        '''cfg_params = inspect.signature(self.present_context.configure).parameters
        if "present_mode" in cfg_params:
            cfg_kwargs["present_mode"] = "immediate"
        elif "vsync" in cfg_params:
            cfg_kwargs["vsync"] = False'''

        self.present_context.configure(**cfg_kwargs)
        #print("Configure signature:", inspect.signature(self.present_context.configure))

        # GPU texture matching the Pygame Surface dimensions
        self.texture = self.device.create_texture(
            size=(self.width, self.height, 1),
            format=wgpu.TextureFormat.rgba8unorm_srgb,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self.texture_view = self.texture.create_view()

        #self.sampler = self.device.create_sampler(
        #    mag_filter=wgpu.FilterMode.nearest,
        #    min_filter=wgpu.FilterMode.nearest,
        #)
        self.sampler = self.device.create_sampler(
            mag_filter=wgpu.FilterMode.linear,
            min_filter=wgpu.FilterMode.linear,
        )

        with open(wgsl_path, "r", encoding="utf-8") as f:
            wgsl_source = f.read()

        shader_module = self.device.create_shader_module(code=wgsl_source)

        self.bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "texture": {"sample_type": wgpu.TextureSampleType.float},
                },
                {
                    "binding": 1,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "sampler": {"type": wgpu.SamplerBindingType.filtering},
                },
            ]
        )
        self.bind_group = self.device.create_bind_group(
            layout=self.bind_group_layout,
            entries=[
                {"binding": 0, "resource": self.texture_view},
                {"binding": 1, "resource": self.sampler},
            ],
        )

        pipeline_layout = self.device.create_pipeline_layout(
            bind_group_layouts=[self.bind_group_layout]
        )
        self.pipeline = self.device.create_render_pipeline(
            layout=pipeline_layout,
            vertex={"module": shader_module, "entry_point": "vs_main"},
            primitive={"topology": wgpu.PrimitiveTopology.triangle_list},
            fragment={
                "module": shader_module,
                "entry_point": "fs_main",
                "targets": [{"format": self.render_format}],
            },
        )


    def present(self, surface):
        """Copies Pygame Surface RGBA pixels to Vulkan texture and presents the frame."""
        '''raw_rgba = pygame.image.tobytes(surface, "RGBA")
        self.device.queue.write_texture(
            destination={"texture": self.texture},
            data=raw_rgba,
            data_layout={"bytes_per_row": self.width * 4, "rows_per_image": self.height},
            size=(self.width, self.height, 1),
        )'''

        """Zero-copy upload of Pygame Surface buffer to Vulkan texture and present."""
        buf = surface.get_buffer()
        try:
            self.device.queue.write_texture(
                destination={"texture": self.texture},
                data=buf,
                data_layout={"bytes_per_row": self.width * 4, "rows_per_image": self.height},
                size=(self.width, self.height, 1),
            )
        finally:
            del buf  # Immediately unlock the Pygame Surface after DMA/staging upload

        current_tex = self.present_context.get_current_texture()
        view = current_tex.create_view()

        encoder = self.device.create_command_encoder()
        render_pass = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": view,
                    "clear_value": (0.0, 0.0, 0.0, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ]
        )
        render_pass.set_pipeline(self.pipeline)
        render_pass.set_bind_group(0, self.bind_group)
        render_pass.draw(6)
        render_pass.end()

        self.device.queue.submit([encoder.finish()])
        self.present_context.present()


    def cleanup(self):
        if getattr(self, "_cleaned", False):
            return
        self._cleaned = True

        self.present_context.unconfigure()
        del self.present_context
        del self.bind_group
        del self.bind_group_layout
        del self.pipeline
        del self.sampler
        del self.texture_view
        self.texture.destroy()
        del self.texture
        self.device.destroy()
        del self.device
        del self.adapter
