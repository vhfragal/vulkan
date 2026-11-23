import os
import sys
import gc
import pygame
from window_host import PygameWindowHost
from wgpu_blitter_batch import WgpuSpriteBatchRenderer
from platformer import PlatformerWorld


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def main():
    
    base_dir = get_base_dir()
    shader_path = os.path.join(base_dir, "shaders.wgsl")

    host = PygameWindowHost()
    atlas = PlatformerWorld.build_atlas_surface()
    renderer = WgpuSpriteBatchRenderer(host, atlas, shader_path)
    #blitter = WgpuSurfaceBlitter(host, shader_path)
    world = PlatformerWorld(renderer.width, renderer.height)
    clock = pygame.time.Clock()

    running = True
    try:
        while running:
            dt = min(clock.tick(0) / 1000.0, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        world = PlatformerWorld(renderer.width, renderer.height)
            
            keys = pygame.key.get_pressed()
            world.update(dt, keys)
            world.width, world.height = renderer.width, renderer.height
            world.render_gpu(renderer, fps=clock.get_fps())
            
    finally:
        renderer.cleanup()
        del renderer
        gc.collect()
        host.close()


if __name__ == "__main__":
    main()
