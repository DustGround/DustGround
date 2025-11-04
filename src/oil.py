import math
import pygame
from typing import List, Tuple, Dict, Optional


class OilParticle:
    """A light, viscous, flammable particle. Floats on water; can ignite and spread fire.
    Attributes:
        x, y: position in pixels
        vx, vy: velocity
        burning: whether this oil particle is on fire
        burn_timer: frames remaining while burning; when it reaches 0, particle evaporates
    """

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.burning: bool = False
        self.burn_timer: int = 0

    def ignite(self, duration: int = 240):
        if not self.burning:
            self.burning = True
            self.burn_timer = int(max(60, duration))
        else:
            # Refresh a bit to sustain fire when hit repeatedly
            self.burn_timer = max(self.burn_timer, int(duration * 0.6))

    def apply_gravity(self, gravity: float):
        self.vy += gravity

    def apply_friction(self, friction: float):
        self.vx *= (1 - friction)
        if abs(self.vx) < 0.01:
            self.vx = 0.0

    def update(self, gravity: float, friction: float):
        self.apply_gravity(gravity)
        self.apply_friction(friction)
        self.x += self.vx
        self.y += self.vy
        # Cap speeds moderately
        if self.vy > 8.0:
            self.vy = 8.0
        if self.vx > 4.0:
            self.vx = 4.0
        if self.vx < -4.0:
            self.vx = -4.0


class OilSystem:
    """Manages all oil particles and their interactions.

    - Light and slightly viscous, flows like a thin fluid.
    - Flammable: ignites on contact with lava; burning spreads quickly to neighbor oil.
    - Provides get_point_groups for batched GPU drawing, with separate colors for burning vs normal.
    - Supports set_obstacle_query to avoid entering solid metal.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: List[OilParticle] = []
        # Physics tuned for light, viscous flow
        self.gravity = 0.12
        self.friction = 0.01
        self.cell_size = 3
        self.grid: Dict[Tuple[int, int], List[OilParticle]] = {}
        self.neighbor_radius: int = 2
        self.max_neighbors: int = 14
        self.skip_mod: int = 1
        # Obstacle query
        self._is_solid = None
        # Colors
        self.color_normal = (40, 35, 20)
        self.color_burning = (255, 160, 60)

    def set_obstacle_query(self, fn):
        """Provide a function is_solid(x:int,y:int)->bool to block movement into solids."""
        self._is_solid = fn

    def add_particle(self, x: float, y: float):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(OilParticle(x, y))

    def add_particle_cluster(self, center_x: int, center_y: int, radius: int = 5):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx*dx + dy*dy <= radius*radius:
                    x = center_x + dx
                    y = center_y + dy
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.add_particle(x, y)

    def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
        return (int(x // self.cell_size), int(y // self.cell_size))

    def _rebuild_grid(self):
        self.grid.clear()
        for p in self.particles:
            cell = self._get_cell(p.x, p.y)
            self.grid.setdefault(cell, []).append(p)

    def _get_neighbors(self, x: float, y: float, radius: int = 1) -> List[OilParticle]:
        out: List[OilParticle] = []
        cx, cy = self._get_cell(x, y)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cx + dx, cy + dy)
                if cell in self.grid:
                    out.extend(self.grid[cell])
        return out

    def _handle_collisions(self, frame_index: int = 0):
        if self.skip_mod > 1 and (frame_index % self.skip_mod) != 0:
            return
        self._rebuild_grid()
        for p in self.particles:
            neigh = self._get_neighbors(p.x, p.y, radius=self.neighbor_radius)
            checked = 0
            for o in neigh:
                if o is p:
                    continue
                dx = o.x - p.x
                dy = o.y - p.y
                dist = math.hypot(dx, dy)
                if dist < 2.0:
                    if dist == 0:
                        dist = 0.1
                    nx = dx / dist
                    ny = dy / dist
                    overlap = 2.0 - dist
                    p.x -= nx * overlap * 0.5
                    p.y -= ny * overlap * 0.5
                    o.x += nx * overlap * 0.5
                    o.y += ny * overlap * 0.5
                    # light damping to avoid jitter
                    p.vx -= nx * 0.03
                    p.vy -= ny * 0.03
                    checked += 1
                    if checked >= self.max_neighbors:
                        break

    def _handle_boundaries(self):
        for p in self.particles:
            if p.y + 1 >= self.height:
                p.y = self.height - 1
                p.vy = 0.0
            if p.y < 0:
                p.y = 0
                p.vy = 0.0
            if p.x < 0:
                p.x = 0
                p.vx *= -0.2
            if p.x >= self.width:
                p.x = self.width - 1
                p.vx *= -0.2

    def _handle_obstacles(self):
        if not self._is_solid:
            return
        for p in self.particles:
            if self._is_solid(int(p.x), int(p.y)):
                # Step back and damp
                p.x -= p.vx
                p.y -= p.vy
                p.vx *= -0.1
                p.vy = 0.0

    def _propagate_burning(self):
        # Burning oil ignites nearby oil quickly
        self._rebuild_grid()
        for p in self.particles:
            if not p.burning:
                continue
            neigh = self._get_neighbors(p.x, p.y, radius=2)
            for o in neigh:
                if (o is p) or o.burning:
                    continue
                # Ignite with high probability to feel fast
                # Also bias upward to model flame rising slightly
                dx = o.x - p.x
                dy = o.y - p.y
                if dx*dx + dy*dy <= 9.0:  # within ~3px
                    o.ignite(200)

    def update(self, frame_index: int = 0):
        # Integrate motion
        for p in self.particles:
            p.update(self.gravity, self.friction)
            if p.burning:
                p.burn_timer -= 1
        # Resolve internal collisions and bounds
        self._handle_collisions(frame_index)
        self._handle_obstacles()
        self._handle_boundaries()
        # Burn propagation
        self._propagate_burning()
        # Remove burned-out oil
        self.particles = [p for p in self.particles if (not p.burning) or (p.burn_timer > 0)]

    def draw(self, surface: pygame.Surface):
        w, h = self.width, self.height
        for p in self.particles:
            if 0 <= p.x < w and 0 <= p.y < h:
                col = self.color_burning if p.burning else self.color_normal
                surface.set_at((int(p.x), int(p.y)), col)

    def get_point_groups(self) -> Dict[Tuple[int, int, int], List[Tuple[int, int]]]:
        groups: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = {
            self.color_normal: [],
            self.color_burning: [],
        }
        w, h = self.width, self.height
        for p in self.particles:
            x = int(p.x)
            y = int(p.y)
            if 0 <= x < w and 0 <= y < h:
                if p.burning:
                    groups[self.color_burning].append((x, y))
                else:
                    groups[self.color_normal].append((x, y))
        # Remove empties
        return {c: pts for c, pts in groups.items() if pts}

    def get_particle_count(self) -> int:
        return len(self.particles)

    def sweep_dead(self):
        if not self.particles:
            return
        self.particles = [p for p in self.particles if not getattr(p, "dead", False)]

    def clear(self):
        self.particles.clear()
        self.grid.clear()
