import os
import sys
import struct
import inspect

os.environ["WGPU_BACKENDS"] = "vulkan,dx12"
os.environ["WGPU_BACKEND_TYPE"] = "Vulkan"
#os.environ["__GL_SYNC_TO_VBLANK"] = "0"

import pygame
import wgpu

from config import *


class WgpuSpriteBatchRenderer:
    """Renders thousands of 2D sprites via GPU instanced quads on Vulkan."""

    def __init__(self, host, atlas_surface, wgsl_path="shaders.wgsl"):
        self.host = host
        self.width = RENDER_SIZE[0]
        self.height = RENDER_SIZE[1]
        self.atlas_w, self.atlas_h = atlas_surface.get_size()

        self.adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        print(
            f"WGPU Adapter: {self.adapter.info.get('device', 'GPU')} "
            f"({self.adapter.info.get('backend_type', 'Vulkan')})"
        )
        self.device = self.adapter.request_device_sync()

        info = self.host.get_wgpu_window_kwargs()
        if sys.platform == "win32":
            present_info = {"platform": "windows", "window": info["window"], "hinstance": info["hinstance"]}
        elif sys.platform.startswith("linux"):
            present_info = {"platform": "x11", "window": info["window"], "display": info["display"]}
        else:
            raise NotImplementedError(f"Unsupported OS: {sys.platform}")

        self.present_context = wgpu.gpu.get_canvas_context(present_info)
        self.present_context.set_physical_size(self.width, self.height)
        self.render_format = self.present_context.get_preferred_format(self.adapter)
                
        self._configure_surface()

        # 1. Screen-size uniform buffer
        self.uniform_buf = self.device.create_buffer_with_data(
            data=struct.pack("2f2f", float(self.width), float(self.height), 0.0, 0.0),
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )

        # 2. GPU Texture Atlas (uploaded once at startup; HUD sub-rect updated dynamically)
        self.atlas_tex = self.device.create_texture(
            size=(self.atlas_w, self.atlas_h, 1),
            format=wgpu.TextureFormat.rgba8unorm_srgb,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self.upload_atlas_region(atlas_surface, 0, 0)

        self.atlas_view = self.atlas_tex.create_view()
        self.sampler = self.device.create_sampler(
            mag_filter=wgpu.FilterMode.nearest,
            min_filter=wgpu.FilterMode.nearest,
        )
        #self.sampler = self.device.create_sampler(
        #    mag_filter=wgpu.FilterMode.linear,
        #    min_filter=wgpu.FilterMode.linear,
        #)

        # 3. Dynamic Instance Buffer
        self.instance_buf = self.device.create_buffer(
            size=MAX_INSTANCES * INSTANCE_STRIDE,
            usage=wgpu.BufferUsage.VERTEX | wgpu.BufferUsage.COPY_DST,
        )
        self._batch_data = bytearray()
        self._instance_count = 0

        # 4. Pipeline & Bind Group
        with open(wgsl_path, "r", encoding="utf-8") as f:
            shader_module = self.device.create_shader_module(code=f.read())

        self.bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {"binding": 0, "visibility": wgpu.ShaderStage.VERTEX, "buffer": {"type": wgpu.BufferBindingType.uniform}},
                {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}},
                {"binding": 2, "visibility": wgpu.ShaderStage.FRAGMENT, "sampler": {"type": wgpu.SamplerBindingType.filtering}},
            ]
        )
        self.bind_group = self.device.create_bind_group(
            layout=self.bind_group_layout,
            entries=[
                {"binding": 0, "resource": {"buffer": self.uniform_buf, "offset": 0, "size": 16}},
                {"binding": 1, "resource": self.atlas_view},
                {"binding": 2, "resource": self.sampler},
            ],
        )

        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[self.bind_group_layout])
        self.pipeline = self.device.create_render_pipeline(
            layout=pipeline_layout,
            vertex={
                "module": shader_module,
                "entry_point": "vs_main",
                "buffers": [
                    {
                        "array_stride": INSTANCE_STRIDE,
                        "step_mode": wgpu.VertexStepMode.instance,
                        "attributes": [
                            {"shader_location": 0, "offset": 0, "format": wgpu.VertexFormat.float32x4},
                            {"shader_location": 1, "offset": 16, "format": wgpu.VertexFormat.float32x4},
                            {"shader_location": 2, "offset": 32, "format": wgpu.VertexFormat.float32x4},
                        ],
                    }
                ],
            },
            primitive={"topology": wgpu.PrimitiveTopology.triangle_list},
            fragment={
                "module": shader_module,
                "entry_point": "fs_main",
                "targets": [
                    {
                        "format": self.render_format,
                        "blend": {
                            "color": {
                                "src_factor": wgpu.BlendFactor.src_alpha,
                                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                                "operation": wgpu.BlendOperation.add,
                            },
                            "alpha": {
                                "src_factor": wgpu.BlendFactor.one,
                                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                                "operation": wgpu.BlendOperation.add,
                            },
                        },
                    }
                ],
            },
        )


    def _configure_surface(self):
        #cfg_params = inspect.signature(self.present_context.configure).parameters
        cfg_kwargs = {
            "device": self.device,
            "format": self.render_format,
            "usage": wgpu.TextureUsage.RENDER_ATTACHMENT,
        }
        #if "present_mode" in cfg_params:
        #    cfg_kwargs["present_mode"] = "immediate"
        #elif "vsync" in cfg_params:
        #    cfg_kwargs["vsync"] = False
        self.present_context.configure(**cfg_kwargs)


    def resize(self, width, height):
        if width <= 0 or height <= 0:
            return
        self.width = width
        self.height = height
        self.present_context.set_physical_size(width, height)
        self._configure_surface()
        self.device.queue.write_buffer(
            self.uniform_buf,
            0,
            struct.pack("2f2f", float(width), float(height), 0.0, 0.0),
        )



    def upload_atlas_region(self, surface, dst_x, dst_y):
        """Uploads a Pygame Surface into a sub-rectangle of the GPU texture atlas."""
        w, h = surface.get_size()
        raw = pygame.image.tobytes(surface, "RGBA")
        self.device.queue.write_texture(
            destination={"texture": self.atlas_tex, "origin": (dst_x, dst_y, 0)},
            data=raw,
            data_layout={"bytes_per_row": w * 4, "rows_per_image": h},
            size=(w, h, 1),
        )

    def begin_batch(self):
        self._batch_data.clear()
        self._instance_count = 0

    def draw_sprite(self, dst_rect, src_rect, flip_x=False, color=(1.0, 1.0, 1.0, 1.0)):
        """Queues a single sprite instance (in screen pixels) for GPU rendering."""
        if self._instance_count >= MAX_INSTANCES:
            return
        x, y, w, h = dst_rect
        sx, sy, sw, sh = src_rect
        u0 = sx / self.atlas_w
        v0 = sy / self.atlas_h
        u1 = (sx + sw) / self.atlas_w
        v1 = (sy + sh) / self.atlas_h
        if flip_x:
            u0, u1 = u1, u0

        self._batch_data.extend(
            struct.pack(
                "12f",
                float(x), float(y), float(w), float(h),
                u0, v0, u1, v1,
                color[0], color[1], color[2], color[3],
            )
        )
        self._instance_count += 1


    def end_batch_and_present(self, clear_color=(0.086, 0.102, 0.149, 1.0)):
        """Uploads the tiny instance array and draws all queued sprites in 1 GPU draw call."""
        # Sync if the window manager resized the fullscreen window after creation
        cur_w, cur_h = self.host.sdl_window.size
        if (cur_w, cur_h) != (self.width, self.height):
            self.resize(cur_w, cur_h)

        try:
            current_tex = self.present_context.get_current_texture()
        except wgpu.DrawCancelled:
            cur_w, cur_h = self.host.sdl_window.size
            self.resize(cur_w, cur_h)
            return

        if self._instance_count > 0:
            self.device.queue.write_buffer(self.instance_buf, 0, self._batch_data)

        view = current_tex.create_view()
        encoder = self.device.create_command_encoder()
        render_pass = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": view,
                    "clear_value": clear_color,
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ]
        )
        if self._instance_count > 0:
            render_pass.set_pipeline(self.pipeline)
            render_pass.set_bind_group(0, self.bind_group)
            render_pass.set_vertex_buffer(0, self.instance_buf)
            render_pass.draw(6, self._instance_count)
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
        del self.atlas_view
        self.atlas_tex.destroy()
        del self.atlas_tex
        self.instance_buf.destroy()
        del self.instance_buf
        self.uniform_buf.destroy()
        del self.uniform_buf
        self.device.destroy()
        del self.device
        del self.adapter
