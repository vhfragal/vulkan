import pygame


class PlatformTile:
    def __init__(self, x, y, w, h, kind="solid"):
        self.rect = pygame.Rect(x, y, w, h)
        self.kind = kind
        self.surface = pygame.Surface((w, h))
        self._paint()

    def _paint(self):
        w, h = self.rect.size
        if self.kind == "solid":
            self.surface.fill((58, 68, 92))
            pygame.draw.rect(self.surface, (95, 195, 130), (0, 0, w, 6))
            pygame.draw.rect(self.surface, (38, 44, 62), (0, 0, w, h), 2)
        elif self.kind == "hazard":
            self.surface.fill((30, 32, 46))
            spike_w = 16
            for sx in range(0, w, spike_w):
                pts = [(sx, h), (sx + spike_w // 2, 4), (sx + spike_w, h)]
                pygame.draw.polygon(self.surface, (235, 75, 95), pts)


class Coin:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 18, 18)
        self.collected = False
        self.surface = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(self.surface, (255, 210, 60), (9, 9), 8)
        pygame.draw.circle(self.surface, (255, 248, 180), (6, 6), 3)


class Player:
    def __init__(self, x, y):
        self.spawn = (x, y)
        self.rect = pygame.Rect(x, y, 28, 38)
        self.pos = pygame.Vector2(float(x), float(y))
        self.vel = pygame.Vector2(0.0, 0.0)
        self.on_ground = False
        self.facing = 1

        self.surface = pygame.Surface((28, 38), pygame.SRCALPHA)
        self._paint()

    def _paint(self):
        self.surface.fill((0, 0, 0, 0))
        pygame.draw.rect(self.surface, (70, 175, 255), (2, 8, 24, 28), border_radius=5)
        pygame.draw.rect(self.surface, (230, 248, 255), (12, 13, 12, 7), border_radius=2)
        pygame.draw.rect(self.surface, (255, 95, 110), (2, 22, 24, 5))

    def respawn(self):
        self.pos.update(self.spawn)
        self.rect.topleft = self.spawn
        self.vel.update(0.0, 0.0)

    def update(self, dt, keys, tiles, coins):
        move_x = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move_x -= 1.0
            self.facing = -1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move_x += 1.0
            self.facing = 1

        self.vel.x = move_x * 310.0
        if (keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]) and self.on_ground:
            self.vel.y = -640.0
            self.on_ground = False

        self.vel.y = min(self.vel.y + 1350.0 * dt, 900.0)

        self.pos.x += self.vel.x * dt
        self.rect.x = round(self.pos.x)
        for tile in tiles:
            if self.rect.colliderect(tile.rect):
                if tile.kind == "hazard":
                    self.respawn()
                    return 0
                if self.vel.x > 0:
                    self.rect.right = tile.rect.left
                elif self.vel.x < 0:
                    self.rect.left = tile.rect.right
                self.pos.x = float(self.rect.x)

        self.pos.y += self.vel.y * dt
        self.rect.y = round(self.pos.y)
        self.on_ground = False
        for tile in tiles:
            if self.rect.colliderect(tile.rect):
                if tile.kind == "hazard":
                    self.respawn()
                    return 0
                if self.vel.y > 0:
                    self.rect.bottom = tile.rect.top
                    self.vel.y = 0.0
                    self.on_ground = True
                elif self.vel.y < 0:
                    self.rect.top = tile.rect.bottom
                    self.vel.y = 0.0
                self.pos.y = float(self.rect.y)

        gained = 0
        for coin in coins:
            if not coin.collected and self.rect.colliderect(coin.rect):
                coin.collected = True
                gained += 1

        if self.rect.top > 900:
            self.respawn()
        return gained


class PlatformerWorld:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        #self.canvas = pygame.Surface((width, height))
        # Native 32-bit RGBA layout matching Vulkan/WGPU rgba8unorm_srgb with zero channel swizzling
        self.canvas = pygame.Surface(
            (width, height),
            flags=pygame.SRCALPHA,
            depth=32,
            masks=(0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000),
        )
        self.font = pygame.font.SysFont("monospace", 20, bold=True)
        self.score = 0
        self.cam_x = 0.0

        self.player = Player(80, 380)
        self.tiles = [
            PlatformTile(0, 520, 480, 80, "solid"),
            PlatformTile(580, 520, 620, 80, "solid"),
            PlatformTile(1280, 520, 600, 80, "solid"),
            PlatformTile(240, 410, 160, 24, "solid"),
            PlatformTile(470, 330, 160, 24, "solid"),
            PlatformTile(720, 390, 180, 24, "solid"),
            PlatformTile(960, 290, 180, 24, "solid"),
            PlatformTile(1240, 360, 160, 24, "solid"),
            PlatformTile(1480, 260, 220, 24, "solid"),
            PlatformTile(820, 496, 96, 24, "hazard"),
            PlatformTile(1420, 496, 128, 24, "hazard"),
        ]
        self.coins = [
            Coin(310, 375),
            Coin(540, 295),
            Coin(800, 355),
            Coin(1040, 255),
            Coin(1310, 325),
            Coin(1580, 225),
        ]

    def update(self, dt, keys):
        self.score += self.player.update(dt, keys, self.tiles, self.coins)
        target_cam = max(0.0, self.player.rect.centerx - self.width * 0.4)
        self.cam_x += (target_cam - self.cam_x) * min(1.0, dt * 8.0)


    def render(self, fps=0.0):
        self.canvas.fill((22, 26, 38))
        ox = int(self.cam_x)

        for gx in range(-(ox // 2) % 80, self.width, 80):
            pygame.draw.line(self.canvas, (30, 36, 52), (gx, 0), (gx, self.height), 1)

        for tile in self.tiles:
            self.canvas.blit(tile.surface, (tile.rect.x - ox, tile.rect.y))

        for coin in self.coins:
            if not coin.collected:
                self.canvas.blit(coin.surface, (coin.rect.x - ox, coin.rect.y))

        sprite = (
            self.player.surface
            if self.player.facing == 1
            else pygame.transform.flip(self.player.surface, True, False)
        )
        self.canvas.blit(sprite, (self.player.rect.x - ox, self.player.rect.y))

        hud = self.font.render(
            f"FPS: {fps:5.1f} | COINS: {self.score}/{len(self.coins)}   R: Reset",
            True,
            (235, 240, 250),
        )
        self.canvas.blit(hud, (16, 16))
        return self.canvas
