import os
import sys
import gc
import pygame
from window_host import PygameWindowHost
from wgpu_blitter import WgpuSurfaceBlitter
from platformer import PlatformerWorld

from config import RENDER_SIZE
import time

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def main():
    
    base_dir = get_base_dir()
    shader_path = os.path.join(base_dir, "shaders.wgsl")

    host = PygameWindowHost()
    blitter = WgpuSurfaceBlitter(host, shader_path)
    world = PlatformerWorld(*RENDER_SIZE)
    clock = pygame.time.Clock()

    running = True
    while running:
        dt = min(clock.tick(0) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    world = PlatformerWorld(*RENDER_SIZE)

        #t0 = time.perf_counter()
        keys = pygame.key.get_pressed()
        world.update(dt, keys)
        frame = world.render(fps=clock.get_fps())
        blitter.present(frame)
        #work_ms = (time.perf_counter() - t0) * 1000.0
        #print(work_ms)

    blitter.cleanup()
    del blitter
    gc.collect()
    host.close()


if __name__ == "__main__":
    main()
