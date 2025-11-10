import math
import random
import pygame
from typing import List, Tuple, Dict


class DiamondParticle:
    __slots__ = (
        "x", "y", "vx", "vy", "age",
        "heat", "last_heat",
        "synthetic", "stained", "frosted",
        "dead"
    )

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.age = 0
        self.heat = 0.0
        self.last_heat = 0.0
                
        self.synthetic = False                                
        self.stained = False                   
        self.frosted = False                           
        self.dead = False


class DiamondSystem:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: List[DiamondParticle] = []
                                                    
        self.gravity = 0.30
        self.friction = 0.012
        self.cell_size = 3
        self.grid: Dict[Tuple[int, int], List[DiamondParticle]] = {}
        self.neighbor_radius = 2
        self.max_neighbors = 12
        self.skip_mod = 1
        self._is_solid = None
                                                
        self.base_color = (140, 190, 255)                           
        self.synthetic_color = (110, 175, 255)                        
        self.stained_tint = (220, 60, 60)
        self.frost_tint = (240, 240, 250)
                                
        self._refract = self._make_refract_surface(6)

    def _make_refract_surface(self, radius: int) -> pygame.Surface:
                                                          
        d = radius * 2 + 1
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            a = int(255 * (r / radius) ** 2 * 0.22)
            pygame.draw.circle(s, (140, 180, 255, a), (radius, radius), r)
        return s

    def set_obstacle_query(self, fn):
        self._is_solid = fn

    def add_particle(self, x: float, y: float):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(DiamondParticle(x, y))

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

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        return (int(x // self.cell_size), int(y // self.cell_size))

    def _rebuild_grid(self):
        self.grid.clear()
        for p in self.particles:
            self.grid.setdefault(self._cell(p.x, p.y), []).append(p)

    def _neighbors(self, x: float, y: float, radius: int = 1) -> List[DiamondParticle]:
        out: List[DiamondParticle] = []
        cx, cy = self._cell(x, y)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                lst = self.grid.get((cx + dx, cy + dy))
                if lst:
                    out.extend(lst)
        return out

    def _collide(self):
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
                    p.x -= nx * overlap * 0.5
                    p.y -= ny * overlap * 0.5
                    q.x += nx * overlap * 0.5
                    q.y += ny * overlap * 0.5
                    p.vx -= nx * 0.04
                    p.vy -= ny * 0.04
                    checked += 1
                    if checked >= self.max_neighbors:
                        break

    def sweep_dead(self):
        self.particles = [p for p in self.particles if not getattr(p, 'dead', False)]

    def update(self, frame_index: int = 0):
        for p in self.particles:
            p.age += 1
                            
            p.vy += self.gravity
            p.vx *= (1 - self.friction)
            p.vy *= (1 - self.friction * 0.5)
            p.x += p.vx
            p.y += p.vy
                                    
            if self._is_solid and self._is_solid(int(p.x), int(p.y)):
                p.x -= p.vx
                p.y -= p.vy
                p.vx *= -0.08
                p.vy = 0.0
            if p.y >= self.height - 1:
                p.y = self.height - 1
                p.vy = 0.0

                                                
            p.heat = max(0.0, p.heat - 0.02)

        self._rebuild_grid()
        if self.skip_mod == 1 or frame_index % self.skip_mod == 0:
            self._collide()

                                                         
        for p in list(self.particles):
            d_heat = abs(p.heat - p.last_heat)
            p.last_heat = p.heat
            if d_heat >= 50.0:
                                                         
                if random.random() < 0.6:
                    p.dead = True
            elif d_heat >= 25.0:
                                                
                if random.random() < 0.2:
                    p.dead = True
        self.sweep_dead()

    def draw(self, surf: pygame.Surface):
        w, h = self.width, self.height
        refr = self._refract
        rr = refr.get_width() // 2 if refr else 0
        for p in self.particles:
            x, y = int(p.x), int(p.y)
            if x < 0 or x >= w or y < 0 or y >= h:
                continue
            col = self.synthetic_color if p.synthetic else self.base_color
                                                                             
            if p.frosted:
                         
                col = (
                    min(255, int(col[0] * 0.9 + self.frost_tint[0] * 0.1)),
                    min(255, int(col[1] * 0.9 + self.frost_tint[1] * 0.1)),
                    min(255, int(col[2] * 0.9 + self.frost_tint[2] * 0.1)),
                )
            if p.stained:
                col = (
                    min(255, int(col[0] * 0.7 + self.stained_tint[0] * 0.3)),
                    min(255, int(col[1] * 0.7 + self.stained_tint[1] * 0.3)),
                    min(255, int(col[2] * 0.7 + self.stained_tint[2] * 0.3)),
                )
            surf.set_at((x, y), col)
            if refr is not None:
                                
                surf.blit(refr, (x - rr, y - rr), special_flags=pygame.BLEND_ADD)
                                                                 
                if p.synthetic:
                    surf.blit(refr, (x - rr, y - rr), special_flags=pygame.BLEND_ADD)

    def get_point_groups(self) -> Tuple[Tuple[int, int, int], List[Tuple[int, int]]]:
        pts: List[Tuple[int, int]] = []
        w, h = self.width, self.height
        for p in self.particles:
            x, y = int(p.x), int(p.y)
            if 0 <= x < w and 0 <= y < h:
                pts.append((x, y))
                                                                     
        return (self.base_color, pts)
