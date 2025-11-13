import math
import random
import pygame
from typing import List, Tuple, Dict, Optional


class GoldParticle:
    __slots__ = (
        "x", "y", "vx", "vy", "age",
        "heat", "last_heat",
        "tarnished", "molten", "electro", "blood_stain",
        "corrosion", "dead"
    )

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.age = 0

        # Thermal/chemical state
        self.heat = 0.0
        self.last_heat = 0.0
        self.tarnished = False          # Toxic contact -> duller gold
        self.molten = False             # Lava contact -> molten pool
        self.electro = False            # Blue lava contact -> conductive electro-gold
        self.blood_stain = 0.0          # Blood contact -> cosmetic stain [0..1]
        self.corrosion = 0.0            # Accumulates with toxic
        self.dead = False


class GoldSystem:
    """
    Gold is a heavy, very malleable metal.
    - High density: falls fast, settles firmly.
    - Low hardness/malleable: converts vertical impact into lateral spread, low bounce.
    - Chemical interactions are modeled as state flags, set via helper methods that
      can be called by a global collision manager (e.g. from app.py).
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: List[GoldParticle] = []

        # Dynamics tuned for a dense but soft metal
        self.gravity = 0.58
        self.friction = 0.014
        self.cell_size = 3
        self.grid: Dict[Tuple[int, int], List[GoldParticle]] = {}
        self.neighbor_radius = 2
        self.max_neighbors = 14
        self.skip_mod = 1
        self._is_solid = None  # external occupancy query

        # Visuals
        self.base_color = (250, 215, 60)         # bright yellow metallic
        self.tarnish_tint = (140, 130, 70)       # dull/olive tint when tarnished
        self.molten_tint = (255, 160, 60)        # more orange when molten
        self.blood_tint = (150, 20, 20)          # slight red stain
        self.electro_glow = self._make_glow_surface(7, (80, 190, 255))
        self.molten_glow = self._make_glow_surface(6, (255, 180, 60))

    # ----------------------- public API -----------------------
    def set_obstacle_query(self, fn):
        self._is_solid = fn

    def add_particle(self, x: float, y: float):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(GoldParticle(x, y))

    def add_particle_cluster(self, cx: int, cy: int, brush_size: int):
        r = max(1, int(brush_size))
        for _ in range(r * r):
            ox = random.uniform(-r, r)
            oy = random.uniform(-r, r)
            if ox * ox + oy * oy <= r * r:
                self.add_particle(cx + ox, cy + oy)

    def clear(self):
        self.particles.clear()
        self.grid.clear()

    def get_particle_count(self) -> int:
        return len(self.particles)

    # Reaction helpers to be called externally by cross-material logic
    def apply_toxic_contact(self, p: GoldParticle, strength: float = 1.0):
        p.tarnished = True
        p.corrosion = min(1.0, p.corrosion + 0.05 * max(0.2, strength))

    def apply_lava_contact(self, p: GoldParticle, heat: float = 60.0):
        p.heat += heat
        if p.heat >= 50.0:
            p.molten = True

    def apply_blue_lava_contact(self, p: GoldParticle, heat: float = 40.0):
        p.electro = True
        p.heat += heat

    def apply_blood_contact(self, p: GoldParticle, amount: float = 0.4):
        p.blood_stain = max(p.blood_stain, max(0.0, min(1.0, amount)))

    def apply_milk_contact(self, p: GoldParticle):
        # No effect by design
        return

    # ----------------------- internals ------------------------
    def _make_glow_surface(self, radius: int, col: Tuple[int, int, int]) -> pygame.Surface:
        d = radius * 2 + 1
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            a = int(255 * (r / radius) ** 2 * 0.26)
            pygame.draw.circle(s, (*col, a), (radius, radius), r)
        return s

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        return (int(x // self.cell_size), int(y // self.cell_size))

    def _rebuild_grid(self):
        self.grid.clear()
        for p in self.particles:
            self.grid.setdefault(self._cell(p.x, p.y), []).append(p)

    def _neighbors(self, x: float, y: float, radius: int = 1) -> List[GoldParticle]:
        out: List[GoldParticle] = []
        cx, cy = self._cell(x, y)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                lst = self.grid.get((cx + dx, cy + dy))
                if lst:
                    out.extend(lst)
        return out

    def _collide(self):
        # soft, malleable collisions: more overlap resolution, low bounce, lateral spread
        for p in self.particles:
            neigh = self._neighbors(p.x, p.y, self.neighbor_radius)
            checked = 0
            for q in neigh:
                if q is p:
                    continue
                dx = q.x - p.x
                dy = q.y - p.y
                d2 = dx * dx + dy * dy
                if d2 < 2.0 * 2.0 and d2 > 1e-4:
                    d = math.sqrt(d2)
                    nx, ny = dx / d, dy / d
                    overlap = 2.0 - d
                    # push apart strongly (soft gold deforms easily)
                    p.x -= nx * overlap * 0.6
                    p.y -= ny * overlap * 0.6
                    q.x += nx * overlap * 0.6
                    q.y += ny * overlap * 0.6

                    # convert some vertical impulse into lateral spread
                    lateral = nx * 0.06
                    p.vx -= lateral
                    p.vy *= 0.8

                    checked += 1
                    if checked >= self.max_neighbors:
                        break

    def update(self, frame_index: int = 0):
        for p in self.particles:
            p.age += 1

            # Heavier fall, but when molten flow more laterally
            g = self.gravity * (0.9 if p.molten else 1.0)
            fr = self.friction * (0.6 if p.molten else 1.0)
            p.vy += g
            p.vx *= (1 - fr)
            p.vy *= (1 - fr * 0.5)

            # slight side-flow if molten
            if p.molten:
                p.vx += random.uniform(-0.02, 0.02)

            p.x += p.vx
            p.y += p.vy

            # collide with external obstacles
            if self._is_solid and self._is_solid(int(p.x), int(p.y)):
                p.x -= p.vx
                p.y -= p.vy
                # gold is soft: nearly no bounce
                p.vx *= -0.06
                p.vy = 0.0

            # floor clamp
            if p.y >= self.height - 1:
                p.y = self.height - 1
                p.vy = 0.0

            # passive cooling
            cool = 0.03 if p.molten else 0.015
            p.heat = max(0.0, p.heat - cool)
            if p.molten and p.heat < 35.0:
                p.molten = False

        self._rebuild_grid()
        if self.skip_mod == 1 or frame_index % self.skip_mod == 0:
            self._collide()

        # Rare failure when extreme thermal shock (placeholder safety like diamond)
        for p in list(self.particles):
            d_heat = abs(p.heat - p.last_heat)
            p.last_heat = p.heat
            if d_heat >= 80.0 and random.random() < 0.05:
                p.dead = True
        self._sweep_dead()

    def _sweep_dead(self):
        self.particles = [p for p in self.particles if not getattr(p, 'dead', False)]

    def draw(self, surf: pygame.Surface):
        w, h = self.width, self.height
        e_glow = self.electro_glow
        m_glow = self.molten_glow
        er = e_glow.get_width() // 2 if e_glow else 0
        mr = m_glow.get_width() // 2 if m_glow else 0

        for p in self.particles:
            x, y = int(p.x), int(p.y)
            if x < 0 or x >= w or y < 0 or y >= h:
                continue

            # Base metallic color
            col = self.base_color

            # Tarnish/corrosion dims and shifts color
            if p.tarnished or p.corrosion > 0:
                t = 0.25 + 0.5 * min(1.0, p.corrosion)
                col = (
                    int(col[0] * (1 - t) + self.tarnish_tint[0] * t),
                    int(col[1] * (1 - t) + self.tarnish_tint[1] * t),
                    int(col[2] * (1 - t) + self.tarnish_tint[2] * t),
                )

            # Molten makes it warmer/orange
            if p.molten:
                t = min(1.0, 0.3 + p.heat / 120.0)
                col = (
                    int(col[0] * (1 - t) + self.molten_tint[0] * t),
                    int(col[1] * (1 - t) + self.molten_tint[1] * t),
                    int(col[2] * (1 - t) + self.molten_tint[2] * t),
                )

            # Blood stains are subtle
            if p.blood_stain > 0.01:
                t = min(0.35, p.blood_stain * 0.35)
                col = (
                    int(col[0] * (1 - t) + self.blood_tint[0] * t),
                    int(col[1] * (1 - t) + self.blood_tint[1] * t),
                    int(col[2] * (1 - t) + self.blood_tint[2] * t),
                )

            surf.set_at((x, y), col)

            # Glows
            if p.molten and m_glow is not None:
                surf.blit(m_glow, (x - mr, y - mr), special_flags=pygame.BLEND_ADD)
            if p.electro and e_glow is not None:
                # Small flicker for electro effect
                if (p.age // 3) % 2 == 0 or random.random() < 0.1:
                    surf.blit(e_glow, (x - er, y - er), special_flags=pygame.BLEND_ADD)

    def get_point_groups(self) -> Tuple[Tuple[int, int, int], List[Tuple[int, int]]]:
        pts: List[Tuple[int, int]] = []
        w, h = self.width, self.height
        for p in self.particles:
            x, y = int(p.x), int(p.y)
            if 0 <= x < w and 0 <= y < h:
                pts.append((x, y))
        return (self.base_color, pts)
