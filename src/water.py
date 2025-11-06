import math
import pygame
from typing import List, Tuple

class WaterParticle:

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = 0.8
        self.color = (100, 149, 237)
        self.pressure = 0.0

    def apply_gravity(self, gravity: float):
        self.vy += gravity

    def apply_viscosity(self, viscosity: float):
        self.vx *= 1 - viscosity
        self.vy *= 1 - viscosity

    def update(self, gravity: float, viscosity: float):
        self.apply_gravity(gravity)
        self.apply_viscosity(viscosity)
        self.x += self.vx
        self.y += self.vy
        if self.vy > 15:
            self.vy = 15

class WaterSystem:

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: List[WaterParticle] = []
        self.gravity = 0.15
        self.viscosity = 0.08
        self.cell_size = 3
        self.grid = {}
        self.neighbor_radius: int = 2
        self.max_neighbors: int = 10
        self.skip_mod: int = 1
        self._is_solid = None

    def set_obstacle_query(self, fn):
        self._is_solid = fn

    def add_particle(self, x: float, y: float):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(WaterParticle(x, y))

    def add_particle_cluster(self, center_x: float, center_y: float, radius: int=5):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    x = center_x + dx
                    y = center_y + dy
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.add_particle(x, y)

    def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
        return (int(x // self.cell_size), int(y // self.cell_size))

    def _rebuild_grid(self):
        self.grid.clear()
        for particle in self.particles:
            cell = self._get_cell(particle.x, particle.y)
            if cell not in self.grid:
                self.grid[cell] = []
            self.grid[cell].append(particle)

    def _get_neighbors(self, x: float, y: float, radius: int=1) -> List[WaterParticle]:
        neighbors = []
        cell_x, cell_y = self._get_cell(x, y)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.grid:
                    neighbors.extend(self.grid[cell])
        return neighbors

    def _handle_collisions(self, frame_index: int=0):
        if self.skip_mod > 1 and frame_index % self.skip_mod != 0:
            return
        self._rebuild_grid()
        for particle in self.particles:
            neighbors = self._get_neighbors(particle.x, particle.y, radius=self.neighbor_radius)
            checked = 0
            for other in neighbors:
                if particle is other:
                    continue
                dx = other.x - particle.x
                dy = other.y - particle.y
                dist = math.hypot(dx, dy)
                if 0.1 < dist < 2.5:
                    if dist == 0:
                        dist = 0.1
                    nx = dx / dist
                    ny = dy / dist
                    separation = 0.3
                    particle.vx -= nx * separation
                    particle.vy -= ny * separation
                    other.vx += nx * separation
                    other.vy += ny * separation
                    checked += 1
                    if checked >= self.max_neighbors:
                        break

    def _handle_boundaries(self):
        for particle in self.particles:
            if particle.y + 1 >= self.height:
                particle.y = self.height - 1
                particle.vy *= -0.3
            if particle.y < 0:
                particle.y = 0
                particle.vy = 0
            if particle.x < 0:
                particle.x = 0
                particle.vx *= -0.3
            if particle.x >= self.width:
                particle.x = self.width - 1
                particle.vx *= -0.3

    def update(self, frame_index: int=0):
        for particle in self.particles:
            particle.update(self.gravity, self.viscosity)
            if self._is_solid and self._is_solid(int(particle.x), int(particle.y)):
                particle.x -= particle.vx
                particle.y -= particle.vy
                particle.vx *= -0.2
                particle.vy *= -0.2
        self._handle_collisions(frame_index)
        self._handle_boundaries()
        self.particles = [p for p in self.particles if -10 <= p.x < self.width + 10 and -10 <= p.y < self.height + 10]

    def draw(self, surface: pygame.Surface):
        for particle in self.particles:
            if 0 <= particle.x < self.width and 0 <= particle.y < self.height:
                pygame.draw.circle(surface, particle.color, (int(particle.x), int(particle.y)), 1)

    def get_point_groups(self) -> Tuple[Tuple[int, int, int], List[Tuple[int, int]]]:
        color = (100, 149, 237)
        points: List[Tuple[int, int]] = []
        for p in self.particles:
            if 0 <= p.x < self.width and 0 <= p.y < self.height:
                points.append((int(p.x), int(p.y)))
        return (color, points)

    def get_particle_count(self) -> int:
        return len(self.particles)

    def sweep_dead(self):
        if not self.particles:
            return
        self.particles = [p for p in self.particles if not getattr(p, 'dead', False)]

    def get_particles_at(self, x: float, y: float, radius: float=5) -> List[WaterParticle]:
        result = []
        for particle in self.particles:
            dx = particle.x - x
            dy = particle.y - y
            if dx * dx + dy * dy <= radius * radius:
                result.append(particle)
        return result

    def clear(self):
        self.particles.clear()
        self.grid.clear()
