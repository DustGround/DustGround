import math
import pygame
from typing import List, Tuple, Dict


class MetalParticle:
	"""A heavy granular metal particle that can move and settle."""
	def __init__(self, x: float, y: float):
		self.x = x
		self.y = y
		self.vx = 0.0
		self.vy = 0.0
		self.mass = 4.0  # heavier than sand
		self.settled = False

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
		# Cap falling speed a bit higher than sand to feel heavy
		if self.vy > 12:
			self.vy = 12


class MetalSystem:
	"""Heavy, movable granular metal that other materials treat as solid.

	- Behaves like sand but much heavier, so it holds things up.
	- Exposes an occupancy-based is_solid(x,y) for other systems to collide with.
	"""

	def __init__(self, width: int, height: int):
		self.width = width
		self.height = height
		self.particles: List[MetalParticle] = []
		# Physics tuned heavier than sand
		self.gravity = 0.6
		self.friction = 0.02
		# Spatial grid for neighbor queries
		self.cell_size = 3
		self.grid: Dict[Tuple[int, int], List[MetalParticle]] = {}
		self.neighbor_radius: int = 2
		self.max_neighbors: int = 16
		self.skip_mod: int = 1
		# Occupancy for is_solid queries from other systems
		self._cells: set[Tuple[int, int]] = set()
		self.color = (140, 140, 150)

	def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
		return (int(x // self.cell_size), int(y // self.cell_size))

	def _rebuild_grid(self):
		self.grid.clear()
		for p in self.particles:
			cell = self._get_cell(p.x, p.y)
			self.grid.setdefault(cell, []).append(p)

	def _get_neighbors(self, x: float, y: float, radius: int = 1) -> List[MetalParticle]:
		neighbors: List[MetalParticle] = []
		cx, cy = self._get_cell(x, y)
		for dx in range(-radius, radius + 1):
			for dy in range(-radius, radius + 1):
				cell = (cx + dx, cy + dy)
				if cell in self.grid:
					neighbors.extend(self.grid[cell])
		return neighbors

	def _handle_collisions(self, frame_index: int = 0):
		# Optionally skip for perf
		if self.skip_mod > 1 and (frame_index % self.skip_mod) != 0:
			return
		self._rebuild_grid()
		for p in self.particles:
			neighbors = self._get_neighbors(p.x, p.y, radius=self.neighbor_radius)
			checked = 0
			for o in neighbors:
				if o is p:
					continue
				dx = o.x - p.x
				dy = o.y - p.y
				dist = math.hypot(dx, dy)
				if dist < 2.0:
					# separate
					if dist == 0:
						dist = 0.1
					nx = dx / dist
					ny = dy / dist
					overlap = 2.0 - dist
					p.x -= nx * overlap * 0.5
					p.y -= ny * overlap * 0.5
					o.x += nx * overlap * 0.5
					o.y += ny * overlap * 0.5
					# very slight damping to keep piles stable
					p.vx -= nx * 0.05
					p.vy -= ny * 0.05
					checked += 1
					if checked >= self.max_neighbors:
						break

	def _handle_boundaries(self):
		for p in self.particles:
			# bottom
			if p.y + 1 >= self.height:
				p.y = self.height - 1
				p.vy = 0.0
				p.settled = True
			# top
			if p.y < 0:
				p.y = 0
				p.vy = 0.0
			# left
			if p.x < 0:
				p.x = 0
				p.vx *= -0.2
			# right
			if p.x >= self.width:
				p.x = self.width - 1
				p.vx *= -0.2

	def _rebuild_occupancy(self):
		cells = set()
		w = self.width
		h = self.height
		for p in self.particles:
			x = int(p.x)
			y = int(p.y)
			if 0 <= x < w and 0 <= y < h:
				cells.add((x, y))
		self._cells = cells

	def is_solid(self, x: int, y: int) -> bool:
		return (int(x), int(y)) in self._cells

	def add_particle(self, x: float, y: float):
		if 0 <= x < self.width and 0 <= y < self.height:
			self.particles.append(MetalParticle(x, y))

	def add_block(self, cx: int, cy: int, half_size: int):
		"""Stamp a dense square of heavy metal particles centered at (cx, cy)."""
		s = max(1, int(half_size))
		x0 = max(0, cx - s)
		y0 = max(0, cy - s)
		x1 = min(self.width - 1, cx + s)
		y1 = min(self.height - 1, cy + s)
		# Fill every pixel to behave as a very thick solid mass
		for y in range(y0, y1 + 1):
			for x in range(x0, x1 + 1):
				self.add_particle(x, y)
		# Update occupancy immediately so other systems see it as solid this frame
		self._rebuild_occupancy()

	def add_particle_cluster(self, cx: int, cy: int, brush_size: int):
		self.add_block(cx, cy, brush_size)

	def clear(self):
		self.particles.clear()
		self.grid.clear()
		self._cells.clear()

	def update(self, frame_index: int = 0):
		# Integrate motion
		for p in self.particles:
			p.update(self.gravity, self.friction)
		# Intra-metal collisions and stability
		self._handle_collisions(frame_index)
		self._handle_boundaries()
		# Rebuild occupancy for cross-system collision queries
		self._rebuild_occupancy()
		# Cull far-out-of-bounds just in case
		self.particles = [p for p in self.particles if -10 <= p.x < self.width + 10 and -10 <= p.y < self.height + 10]

	def draw(self, surf: pygame.Surface):
		col = self.color
		w = self.width
		h = self.height
		for p in self.particles:
			if 0 <= p.x < w and 0 <= p.y < h:
				surf.set_at((int(p.x), int(p.y)), col)

	def get_point_groups(self) -> Tuple[Tuple[int, int, int], List[Tuple[int, int]]]:
		pts: List[Tuple[int, int]] = []
		w = self.width
		h = self.height
		for p in self.particles:
			x = int(p.x)
			y = int(p.y)
			if 0 <= x < w and 0 <= y < h:
				pts.append((x, y))
		return (self.color, pts)

	def get_particle_count(self) -> int:
		return len(self.particles)

