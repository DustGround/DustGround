import math
import random
import pygame
from typing import List, Tuple, Dict


class ToxicParticle:
	"""A heavy, viscous, bubbly toxic-waste particle."""
	__slots__ = ("x", "y", "vx", "vy", "mass", "age", "bubble_t")

	def __init__(self, x: float, y: float):
		self.x = x
		self.y = y
		self.vx = 0.0
		self.vy = 0.0
		self.mass = 1.5  # heavier than water/sand
		self.age = 0
		# Bubble timer: periodic small upward impulses for a "bubbly" look
		self.bubble_t = random.randint(12, 28)

	def update(self, gravity: float, friction: float):
		# Heavier downward acceleration
		self.vy += gravity * self.mass
		# Stronger viscosity/friction
		self.vx *= (1.0 - friction * 1.2)
		self.vy *= (1.0 - friction * 0.4)

		# Periodic upward impulse (bubble)
		self.age += 1
		if self.age % self.bubble_t == 0:
			# Small upward kick and a tiny horizontal jitter
			self.vy -= 0.8
			self.vx += (random.random() - 0.5) * 0.3
			# Resample bubble period a bit
			self.bubble_t = random.randint(12, 28)

		# Integrate position
		self.x += self.vx
		self.y += self.vy

		# Clamp terminal velocity
		if self.vy > 12:
			self.vy = 12


class ToxicSystem:
	"""Manages toxic-waste particles with simple spatial partitioning and collisions."""

	def __init__(self, width: int, height: int):
		self.width = width
		self.height = height
		self.particles: List[ToxicParticle] = []
		self.gravity = 0.22
		self.friction = 0.06
		# Spatial grid (cell size similar to sand)
		self.cell_size = 3
		self.grid: Dict[Tuple[int, int], List[ToxicParticle]] = {}
		# Neighbor/collision budget
		self.neighbor_radius: int = 2
		self.max_neighbors: int = 10
		self.skip_mod: int = 1
		# Optional solid query (e.g., metal blocks)
		self._is_solid = None

	def set_obstacle_query(self, fn):
		self._is_solid = fn

	def add_particle(self, x: float, y: float):
		if 0 <= x < self.width and 0 <= y < self.height:
			self.particles.append(ToxicParticle(x, y))

	def add_particle_cluster(self, cx: float, cy: float, radius: int = 5):
		r = max(1, int(radius))
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

	def _get_neighbors(self, x: float, y: float, radius: int) -> List[ToxicParticle]:
		out: List[ToxicParticle] = []
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
			neighbors = self._get_neighbors(p.x, p.y, self.neighbor_radius)
			checked = 0
			for q in neighbors:
				if p is q:
					continue
				dx = q.x - p.x
				dy = q.y - p.y
				dist = math.hypot(dx, dy)
				# Gentle separation if too close (acts like thick fluid)
				if dist < 2:
					if dist == 0:
						dist = 0.1
					nx = dx / dist
					ny = dy / dist
					overlap = 2 - dist
					p.x -= nx * overlap * 0.5
					p.y -= ny * overlap * 0.5
					q.x += nx * overlap * 0.5
					q.y += ny * overlap * 0.5
					# Dampen relative velocity (viscosity)
					p.vx *= 0.95
					p.vy *= 0.95
					q.vx *= 0.95
					q.vy *= 0.95
					checked += 1
					if checked >= self.max_neighbors:
						break

	def _handle_boundaries(self):
		for p in self.particles:
			# Bottom
			if p.y + 1 >= self.height:
				p.y = self.height - 1
				p.vy = 0
			# Top
			if p.y < 0:
				p.y = 0
				p.vy = 0
			# Left
			if p.x < 0:
				p.x = 0
				p.vx *= -0.3
			# Right
			if p.x >= self.width:
				p.x = self.width - 1
				p.vx *= -0.3

	def update(self, frame_index: int = 0):
		if not self.particles:
			return
		for p in self.particles:
			p.update(self.gravity, self.friction)
			# Solid collision
			if getattr(self, "_is_solid", None) and self._is_solid(int(p.x), int(p.y)):
				p.x -= p.vx
				p.y -= p.vy
				p.vx *= -0.2
				p.vy *= -0.1
		self._handle_collisions(frame_index)
		self._handle_boundaries()
		# Cull out-of-bounds (with small margins)
		self.particles = [p for p in self.particles if -10 <= p.x < self.width + 10 and -10 <= p.y < self.height + 10]

	def draw(self, surface: pygame.Surface):
		if not self.particles:
			return
		color = (90, 220, 90)  # toxic green
		for p in self.particles:
			if 0 <= p.x < self.width and 0 <= p.y < self.height:
				pygame.draw.circle(surface, color, (int(p.x), int(p.y)), 1)

	def get_point_groups(self) -> Tuple[Tuple[int, int, int], List[Tuple[int, int]]]:
		"""Return a single color and a list of points for batched GPU rendering."""
		color = (90, 220, 90)
		pts: List[Tuple[int, int]] = []
		for p in self.particles:
			if 0 <= p.x < self.width and 0 <= p.y < self.height:
				pts.append((int(p.x), int(p.y)))
		return color, pts

	def get_particle_count(self) -> int:
		return len(self.particles)

	def clear(self):
		self.particles.clear()
		self.grid.clear()

