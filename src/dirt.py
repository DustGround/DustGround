import math
import random
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
                                                   
		self.gravity = 0.32                                                               
		self.friction = 0.06                         
		self.cell_size = 1                                   
		self.grid: Dict[Tuple[int, int], List[DirtParticle]] = {}
                                                 
		self.occ: Dict[Tuple[int, int], int] = {}
                                                                
		self.fall_max: int = 3
                                                                             
		self.relax_passes: int = 4
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
		self.occ.clear()
		for p in self.particles:
			xi, yi = int(p.x), int(p.y)
			if 0 <= xi < self.width and 0 <= yi < self.height:
				self.occ[(xi, yi)] = self.occ.get((xi, yi), 0) + 1

	def _occupied(self, xi: int, yi: int) -> bool:
		if xi < 0 or yi < 0 or xi >= self.width or yi >= self.height:
			return True
		if self._is_solid and self._is_solid(xi, yi):
			return True
		return self.occ.get((xi, yi), 0) > 0

	def _get_neighbors(self, x: float, y: float, radius: int=1) -> List[DirtParticle]:
                                                                 
		return []

	def update(self, frame_index: int=0):
                                                                                   
		for p in self.particles:
			p.age += 1
              
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
                                                            
		for _pass in range(self.relax_passes):
			self._rebuild_grid()
			order = list(range(len(self.particles)))
			random.shuffle(order)
			for idx in order:
				p = self.particles[idx]
				xi, yi = int(p.x), int(p.y)
				if xi < 0 or xi >= self.width or yi < 0 or yi >= self.height:
					continue
                                       
				max_fall = 2 if p.is_mud else self.fall_max
				falls = 0
				while falls < max_fall and not self._occupied(xi, yi + 1):
					self.occ[(xi, yi)] = max(0, self.occ.get((xi, yi), 1) - 1)
					yi += 1
					p.y = float(yi)
					self.occ[(xi, yi)] = self.occ.get((xi, yi), 0) + 1
					falls += 1
                                             
				if falls == 0:
					dirs = [-1, 1]
					if random.random() < 0.5:
						dirs.reverse()
					for dx in dirs:
						nx, ny = xi + dx, yi + 1
						if not self._occupied(nx, ny):
							self.occ[(xi, yi)] = max(0, self.occ.get((xi, yi), 1) - 1)
							xi, yi = nx, ny
							p.x = float(xi)
							p.y = float(yi)
							self.occ[(xi, yi)] = self.occ.get((xi, yi), 0) + 1
							break
                                      
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
		self.occ.clear()
