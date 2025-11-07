import math
import pygame
from typing import List, Tuple, Dict

class DirtParticle:
	__slots__ = ('x', 'y', 'vx', 'vy', 'is_mud', 'contaminated', 'age')

	def __init__(self, x: float, y: float):
		self.x = float(x)
		self.y = float(y)
		self.vx = 0.0
		self.vy = 0.0
		self.is_mud = False
		self.contaminated = False
		self.age = 0

class DirtSystem:

	def __init__(self, width: int, height: int):
		self.width = width
		self.height = height
		self.particles: List[DirtParticle] = []
		self.gravity = 0.25
		self.friction = 0.06
		self.cell_size = 3
		self.grid: Dict[Tuple[int, int], List[DirtParticle]] = {}
		self.neighbor_radius: int = 2
		self.max_neighbors: int = 12
		self.skip_mod: int = 1
		self._is_solid = None

	def set_obstacle_query(self, fn):
		self._is_solid = fn

	def add_particle(self, x: float, y: float):
		if 0 <= x < self.width and 0 <= y < self.height:
			self.particles.append(DirtParticle(x, y))

	def add_particle_cluster(self, cx: int, cy: int, brush_size: int=5):
		r = max(1, int(brush_size))
		for dx in range(-r, r + 1):
			for dy in range(-r, r + 1):
				if dx * dx + dy * dy <= r * r:
					x = cx + dx
					y = cy + dy
					if 0 <= x < self.width and 0 <= y < self.height:
						self.add_particle(x, y)

	def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
		return (int(x // self.cell_size), int(y // self.cell_size))

	def _rebuild_grid(self):
		self.grid.clear()
		for p in self.particles:
			c = self._get_cell(p.x, p.y)
			self.grid.setdefault(c, []).append(p)

	def _get_neighbors(self, x: float, y: float, radius: int=1) -> List[DirtParticle]:
		out: List[DirtParticle] = []
		cx, cy = self._get_cell(x, y)
		for dx in range(-radius, radius + 1):
			for dy in range(-radius, radius + 1):
				cell = (cx + dx, cy + dy)
				if cell in self.grid:
					out.extend(self.grid[cell])
		return out

	def update(self, frame_index: int=0):
		for p in self.particles:
			p.age += 1
			g = self.gravity * (0.5 if p.is_mud else 1.0)
			fr = self.friction * (1.5 if p.is_mud else 1.0)
			p.vy += g
			p.vx *= 1 - fr
			if abs(p.vx) < 0.01:
				p.vx = 0.0
			p.x += p.vx
			p.y += p.vy
			if self._is_solid and self._is_solid(int(p.x), int(p.y)):
				p.x -= p.vx
				p.y -= p.vy
				p.vx *= -0.1
				p.vy = 0.0
		# boundaries
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
		# mild neighbor separation
		if self.skip_mod <= 1 or frame_index % self.skip_mod == 0:
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
						checked += 1
						if checked >= self.max_neighbors:
							break
		# keep particles in reasonable range
		self.particles = [p for p in self.particles if -10 <= p.x < self.width + 10 and -10 <= p.y < self.height + 10]

	def draw(self, surface: pygame.Surface):
		for p in self.particles:
			x, y = int(p.x), int(p.y)
			if 0 <= x < self.width and 0 <= y < self.height:
				if p.is_mud:
					col = (110, 85, 60)
				elif p.contaminated:
					col = (100, 90, 60)
				else:
					col = (130, 100, 70)
				surface.set_at((x, y), col)

	def get_point_groups(self) -> Dict[Tuple[int, int, int], List[Tuple[int, int]]]:
		groups: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = {}
		for p in self.particles:
			x, y = int(p.x), int(p.y)
			if 0 <= x < self.width and 0 <= y < self.height:
				if p.is_mud:
					col = (110, 85, 60)
				elif p.contaminated:
					col = (100, 90, 60)
				else:
					col = (130, 100, 70)
				groups.setdefault(col, []).append((x, y))
		return {c: pts for c, pts in groups.items() if pts}

	def get_particle_count(self) -> int:
		return len(self.particles)

	def sweep_dead(self):
		self.particles = [p for p in self.particles if not getattr(p, 'dead', False)]

	def get_particles_at(self, x: float, y: float, radius: float=5) -> List[DirtParticle]:
		out: List[DirtParticle] = []
		r2 = radius * radius
		for p in self.particles:
			dx = p.x - x
			dy = p.y - y
			if dx * dx + dy * dy <= r2:
				out.append(p)
		return out

	def clear(self):
		self.particles.clear()
		self.grid.clear()
