import pygame


class PlatformTile:
    def __init__(self, x, y, w, h, kind="solid"):
        self.rect = pygame.Rect(x, y, w, h)
        self.kind = kind


class Coin:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 18, 18)
        self.collected = False


class Player:
    def __init__(self, x, y):
        self.spawn = (x, y)
        self.rect = pygame.Rect(x, y, 28, 38)
        self.pos = pygame.Vector2(float(x), float(y))
        self.vel = pygame.Vector2(0.0, 0.0)
        self.on_ground = False
        self.facing = 1

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
    """Builds a Pygame sprite atlas once and submits instanced quads to WgpuSpriteBatchRenderer."""

    # Atlas sub-rectangles (x, y, w, h) inside the 1024x256 texture atlas
    UV_WHITE = (0, 0, 8, 8)
    UV_SOLID = (16, 0, 64, 64)
    UV_HAZARD = (96, 0, 16, 24)
    UV_COIN = (128, 0, 18, 18)
    UV_PLAYER = (160, 0, 28, 38)
    UV_HUD = (0, 80, 900, 32)

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.font = pygame.font.SysFont("monospace", 20, bold=True)
        self.hud_surface = pygame.Surface((self.UV_HUD[2], self.UV_HUD[3]), pygame.SRCALPHA)
        self.score = 0
        self.cam_x = 0.0
        self._last_hud_key = None

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

    @classmethod
    def build_atlas_surface(cls):
        """Paints all game sprites into a single Pygame Surface atlas."""
        atlas = pygame.Surface((1024, 256), pygame.SRCALPHA)
        atlas.fill((0, 0, 0, 0))

        # 1. White pixel block (for tinted grid lines & borders)
        pygame.draw.rect(atlas, (255, 255, 255, 255), cls.UV_WHITE)

        # 2. Solid platform tile (64x64)
        sx, sy, sw, sh = cls.UV_SOLID
        pygame.draw.rect(atlas, (58, 68, 92, 255), (sx, sy, sw, sh))
        pygame.draw.rect(atlas, (95, 195, 130, 255), (sx, sy, sw, 6))
        pygame.draw.rect(atlas, (38, 44, 62, 255), (sx, sy, sw, sh), 2)

        # 3. Single spike hazard tile (16x24, repeated horizontally by GPU)
        hx, hy, hw, hh = cls.UV_HAZARD
        pts = [(hx, hy + hh), (hx + hw // 2, hy + 4), (hx + hw, hy + hh)]
        pygame.draw.polygon(atlas, (235, 75, 95, 255), pts)

        # 4. Coin (18x18)
        cx, cy, _, _ = cls.UV_COIN
        pygame.draw.circle(atlas, (255, 210, 60, 255), (cx + 9, cy + 9), 8)
        pygame.draw.circle(atlas, (255, 248, 180, 255), (cx + 6, cy + 6), 3)

        # 5. Player (28x38)
        px, py, _, _ = cls.UV_PLAYER
        pygame.draw.rect(atlas, (70, 175, 255, 255), (px + 2, py + 8, 24, 28), border_radius=5)
        pygame.draw.rect(atlas, (230, 248, 255, 255), (px + 12, py + 13, 12, 7), border_radius=2)
        pygame.draw.rect(atlas, (255, 95, 110, 255), (px + 2, py + 22, 24, 5))

        return atlas

    def update(self, dt, keys):
        self.score += self.player.update(dt, keys, self.tiles, self.coins)
        target_cam = max(0.0, self.player.rect.centerx - self.width * 0.4)
        self.cam_x += (target_cam - self.cam_x) * min(1.0, dt * 8.0)

    def render_gpu(self, renderer, fps=0.0):
        renderer.begin_batch()
        ox = int(self.cam_x)

        # Background grid lines (tinted white texel)
        grid_color = (30 / 255.0, 36 / 255.0, 52 / 255.0, 1.0)
        for gx in range(-(ox // 2) % 80, self.width, 80):
            renderer.draw_sprite((gx, 0, 1, self.height), self.UV_WHITE, color=grid_color)

        # Tiles & repeating spike quads
        for tile in self.tiles:
            sx = tile.rect.x - ox
            if sx + tile.rect.w < 0 or sx > self.width:
                continue
            if tile.kind == "solid":
                renderer.draw_sprite((sx, tile.rect.y, tile.rect.w, tile.rect.h), self.UV_SOLID)
            elif tile.kind == "hazard":
                for sub_x in range(0, tile.rect.w, 16):
                    renderer.draw_sprite((sx + sub_x, tile.rect.y, 16, tile.rect.h), self.UV_HAZARD)

        # Coins
        for coin in self.coins:
            if not coin.collected:
                renderer.draw_sprite((coin.rect.x - ox, coin.rect.y, 18, 18), self.UV_COIN)

        # Player (UV flipped horizontally on GPU when facing left)
        renderer.draw_sprite(
            (self.player.rect.x - ox, self.player.rect.y, 28, 38),
            self.UV_PLAYER,
            flip_x=(self.player.facing == -1),
        )

        # Re-upload HUD strip only when FPS integer or score changes
        hud_key = (int(fps), self.score)
        if hud_key != self._last_hud_key:
            self._last_hud_key = hud_key
            self.hud_surface.fill((0, 0, 0, 0))
            txt = self.font.render(
                f"FPS: {fps:5.1f} | COINS: {self.score}/{len(self.coins)}   [A/D: Move | Space: Jump | R: Reset]",
                True,
                (235, 240, 250),
            )
            self.hud_surface.blit(txt, (0, 0))
            renderer.upload_atlas_region(self.hud_surface, self.UV_HUD[0], self.UV_HUD[1])

        renderer.draw_sprite((16, 16, self.UV_HUD[2], self.UV_HUD[3]), self.UV_HUD)
        renderer.end_batch_and_present()
