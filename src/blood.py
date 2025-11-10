import random
import math
import pygame
from typing import List, Tuple

class BloodParticle:
    __slots__ = (
        'x', 'y', 'vx', 'vy', 'age',
        'diluted', 'mutant', 'curdled', 'clotted', 'dead', 'soaked'
    )

    def __init__(self, x: float, y: float, vx: float=0.0, vy: float=0.0):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.age = 0
        self.diluted = False
        self.mutant = False
        self.curdled = False
        self.clotted = False
        self.dead = False
        self.soaked = False

class BloodSystem:

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: List[BloodParticle] = []
        self.gravity = 0.7                    
        self.low_speed_damp = 0.9
        self.high_speed_damp = 0.975
        self.shear_ref = 2.0
        self.clot_frames = 240
        self.clot_low_extra = 0.08
        self.ground_restitution = 0.05
        self.ground_friction = 0.8
        self.color = (170, 20, 30)
        self.curdled_color = (215, 150, 170)
        self.diluted_color = (200, 60, 70)
        self.mutant_color = (60, 200, 90)
        self.clotted_color = (90, 15, 20)
        self.cell_size = 3
        self.grid = {}
        self.neighbor_radius = 2
        self.max_neighbors = 10
        self.skip_mod = 1
        self.repulse_dist = 1.8
        self.repulse_strength = 0.08
        self.tension_rest = 3.2
        self.tension_range = 6.0
        self.tension_strength = 0.015
        self._is_solid = None

    def set_obstacle_query(self, fn):
        self._is_solid = fn

    def add_particle(self, x: float, y: float, vx: float=0.0, vy: float=0.0):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(BloodParticle(x, y, vx, vy))

    def add_spray(self, x: float, y: float, count: int=4, speed: float=1.5):
        c = max(1, int(count))
        for _ in range(c):
            ang = random.uniform(math.pi * 0.25, math.pi * 0.75)
            sp = random.uniform(0.2, speed)
            vx = sp * math.cos(ang) * 0.6
            vy = sp * math.sin(ang)
            vy = max(vy, 0.5)
            self.add_particle(x + random.uniform(-1, 1), y + random.uniform(-1, 1), vx, vy)

    def add_particle_cluster(self, cx: int, cy: int, brush_size: int):
        r = max(1, int(brush_size))
        for _ in range(r * r):
            ox = random.uniform(-r, r)
            oy = random.uniform(-r, r)
            if ox * ox + oy * oy <= r * r:
                self.add_particle(cx + ox, cy + oy)

    def _rebuild_grid(self):
        self.grid.clear()
        cs = self.cell_size
        for p in self.particles:
            cx = int(p.x // cs)
            cy = int(p.y // cs)
            self.grid.setdefault((cx, cy), []).append(p)

    def _handle_collisions(self, frame_index: int):
        if self.skip_mod > 1 and frame_index % self.skip_mod != 0:
            return
        cs = self.cell_size
        radius = self.neighbor_radius
        MAXN = self.max_neighbors
        for p in self.particles:
            cx = int(p.x // cs)
            cy = int(p.y // cs)
            neighbors = []
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    cell = (cx + dx, cy + dy)
                    if cell in self.grid:
                        neighbors.extend(self.grid[cell])
                        if len(neighbors) > MAXN:
                            break
                if len(neighbors) > MAXN:
                    break
            for q in neighbors:
                if q is p:
                    continue
                dx = p.x - q.x
                dy = p.y - q.y
                d2 = dx * dx + dy * dy
                if d2 > 0.0001:
                    d = d2 ** 0.5
                    nx, ny = (dx / d, dy / d)
                    if d < self.repulse_dist:
                        push = (self.repulse_dist - d) * self.repulse_strength
                        p.vx += nx * push
                        p.vy += ny * push
                        q.vx -= nx * push * 0.5
                        q.vy -= ny * push * 0.5
                    elif d < self.tension_range:
                        stretch = d - self.tension_rest
                        if stretch > 0.0:
                            k = self.tension_strength * (stretch / self.tension_range)
                            ax = -nx * k
                            ay = -ny * k
                            p.vx += ax
                            p.vy += ay
                            q.vx -= ax * 0.5
                            q.vy -= ay * 0.5
                    blend = 0.035
                    dvx = (q.vx - p.vx) * blend
                    dvy = (q.vy - p.vy) * blend
                    p.vx += dvx
                    p.vy += dvy
                    q.vx -= dvx
                    q.vy -= dvy

    def update(self, frame_index: int=0):
        if not self.particles:
            return
        for p in self.particles:
            if p.dead:
                continue
                             
            p.vy += self.gravity
            p.age += 1
                                   
            if not p.clotted and p.age >= self.clot_frames:
                p.clotted = True
                                       
            speed = (p.vx * p.vx + p.vy * p.vy) ** 0.5
            t = speed / (speed + self.shear_ref) if speed > 0.0 else 0.0
            clot_frac = min(1.0, p.age / float(self.clot_frames))
            eff_low = max(0.75, self.low_speed_damp - clot_frac * self.clot_low_extra)
            eff_high = max(0.85, self.high_speed_damp - min(0.03, clot_frac * 0.015))
            damping = eff_low * (1.0 - t) + eff_high * t
            if p.clotted:
                                            
                p.vx *= 0.5
                p.vy *= 0.5
            else:
                p.vx *= damping
                p.vy *= damping
                                       
            if p.diluted:
                p.vx *= 0.95; p.vy *= 0.95
            if p.curdled:
                p.vx *= 0.6; p.vy *= 0.6
            if p.mutant:
                p.vx *= 1.02; p.vy *= 1.02
            p.x += p.vx
            p.y += p.vy
                                            
            if self._is_solid and self._is_solid(int(p.x), int(p.y)):
                p.x -= p.vx
                p.y -= p.vy
                p.vx *= -0.08
                p.vy = 0.0
                        
            if p.x < 0:
                p.x = 0; p.vx *= -0.12
            elif p.x > self.width - 1:
                p.x = self.width - 1; p.vx *= -0.12
            if p.y < 0:
                p.y = 0; p.vy *= -0.08
            elif p.y > self.height - 1:
                p.y = self.height - 1
                p.vy = -abs(p.vy) * self.ground_restitution
                p.vx *= self.ground_friction
                if abs(p.vy) < 0.06:
                    p.vy = 0.0
                    p.vx += random.uniform(-0.02, 0.02)
                           
        self._rebuild_grid()
        self._handle_collisions(frame_index)
              
        self.particles = [p for p in self.particles if not p.dead and -10 <= p.x < self.width + 10 and -10 <= p.y < self.height + 10]

    def draw(self, surf: pygame.Surface):
        for p in self.particles:
            x, y = (int(p.x), int(p.y))
            if 0 <= x < self.width and 0 <= y < self.height:
                if p.dead:
                    continue
                if p.mutant:
                    col = self.mutant_color
                elif p.curdled:
                    col = self.curdled_color
                elif p.diluted:
                    col = self.diluted_color
                elif p.clotted:
                    col = self.clotted_color
                else:
                    col = self.color
                surf.set_at((x, y), col)

    def get_point_groups(self) -> Tuple[Tuple[int, int, int], List[Tuple[int, int]]]:
        col = self.color
        pts = [(int(p.x), int(p.y)) for p in self.particles]
        return (col, pts)

    def get_particle_count(self) -> int:
        return len(self.particles)

    def clear(self):
        self.particles.clear()
