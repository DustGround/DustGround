import math
import random
import pygame
from typing import List, Tuple, Dict

class RubyParticle:
    __slots__ = ("x","y","vx","vy","age","charged","overcharged","unstable","cursed","dulled","corroded","heat")
    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.age = 0
                
        self.charged = False
        self.overcharged = False
        self.unstable = 0                                      
        self.cursed = False
        self.dulled = False
        self.corroded = 0                       
        self.heat = 0                         

class RubySystem:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: List[RubyParticle] = []
        self.gravity = 0.35                
        self.friction = 0.015
        self.cell_size = 3
        self.grid: Dict[Tuple[int,int], List[RubyParticle]] = {}
        self.neighbor_radius = 2
        self.max_neighbors = 12
        self.skip_mod = 1
        self._is_solid = None
                     
        self.base_color = (180, 20, 30)
        self.charged_color = (220, 30, 50)
        self.overcharged_color = (255, 80, 120)
        self.cursed_color = (120, 10, 20)
        self.dulled_color = (120, 90, 100)
                                      
        self._glow = self._make_glow_surface(7, (255, 60, 80))

    def _make_glow_surface(self, radius: int, col: Tuple[int,int,int]) -> pygame.Surface:
        d = radius*2+1
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        for r in range(radius, 0, -1):
            a = int(255 * (r / radius) ** 2 * 0.25)
            pygame.draw.circle(s, (*col, a), (radius, radius), r)
        return s

    def set_obstacle_query(self, fn):
        self._is_solid = fn

    def add_particle(self, x: float, y: float):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(RubyParticle(x, y))

    def add_particle_cluster(self, cx: int, cy: int, brush_size: int):
        r = max(1, int(brush_size))
        for _ in range(r * r):
            ox = random.uniform(-r, r)
            oy = random.uniform(-r, r)
            if ox*ox + oy*oy <= r*r:
                self.add_particle(cx + ox, cy + oy)

    def clear(self):
        self.particles.clear()
        self.grid.clear()

    def get_particle_count(self) -> int:
        return len(self.particles)

    def _cell(self, x: float, y: float) -> Tuple[int,int]:
        return (int(x // self.cell_size), int(y // self.cell_size))

    def _rebuild_grid(self):
        self.grid.clear()
        for p in self.particles:
            self.grid.setdefault(self._cell(p.x, p.y), []).append(p)

    def _neighbors(self, x: float, y: float, radius: int=1) -> List[RubyParticle]:
        out: List[RubyParticle] = []
        cx, cy = self._cell(x, y)
        for dx in range(-radius, radius+1):
            for dy in range(-radius, radius+1):
                lst = self.grid.get((cx+dx, cy+dy))
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
                d2 = dx*dx + dy*dy
                if d2 < 2.0*2.0 and d2 > 1e-4:
                    d = math.sqrt(d2)
                    nx, ny = dx/d, dy/d
                    overlap = 2.0 - d
                    p.x -= nx * overlap * 0.5
                    p.y -= ny * overlap * 0.5
                    q.x += nx * overlap * 0.5
                    q.y += ny * overlap * 0.5
                    p.vx -= nx * 0.05
                    p.vy -= ny * 0.05
                    checked += 1
                    if checked >= self.max_neighbors:
                        break

    def update(self, frame_index: int=0):
        for p in self.particles:
            p.age += 1
            p.vy += self.gravity
            p.vx *= (1 - self.friction)
            p.vy *= (1 - self.friction*0.5)
            p.x += p.vx
            p.y += p.vy
            if self._is_solid and self._is_solid(int(p.x), int(p.y)):
                p.x -= p.vx
                p.y -= p.vy
                p.vx *= -0.1
                p.vy = 0.0
                                                                                                                
            if p.y >= self.height - 1:
                p.y = self.height - 1
                p.vy = 0.0
        self._rebuild_grid()
        if self.skip_mod == 1 or frame_index % self.skip_mod == 0:
            self._collide()

                                                                                             
        for p in list(self.particles):
            if p.unstable > 0:
                p.unstable -= 1
                if p.unstable == 0 and random.random() < 0.25:
                                                                                      
                    try:
                        p_index = self.particles.index(p)
                    except ValueError:
                        p_index = -1
                    if p_index >= 0:
                        del self.particles[p_index]

    def draw(self, surf: pygame.Surface):
        w, h = self.width, self.height
        glow = self._glow
        gr = glow.get_width()//2 if glow else 0
        for p in self.particles:
            x, y = int(p.x), int(p.y)
            if 0 <= x < w and 0 <= y < h:
                                        
                col = self.base_color
                if p.dulled:
                    col = self.dulled_color
                if p.cursed:
                    col = self.cursed_color
                if p.charged:
                    col = self.charged_color
                if p.overcharged:
                    col = self.overcharged_color
                surf.set_at((x, y), col)
                                                 
                if (p.charged or p.overcharged or p.heat > 0) and glow is not None:
                    surf.blit(glow, (x - gr, y - gr), special_flags=pygame.BLEND_ADD)

    def get_point_groups(self) -> Tuple[Tuple[int,int,int], List[Tuple[int,int]]]:
        pts: List[Tuple[int,int]] = []
        w, h = self.width, self.height
        for p in self.particles:
            x, y = int(p.x), int(p.y)
            if 0 <= x < w and 0 <= y < h:
                pts.append((x, y))
        return (self.base_color, pts)
