from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class SystemProps:
	name: str
	sys: Any
	kind: str                      
	radius: float = 1.0
	mass: float = 1.0
	elasticity: float = 0.05
	friction: float = 0.02
	max_neighbors: int = 6

	def particles(self) -> List[Any]:
		return getattr(self.sys, 'particles', [])

	def grid(self) -> Dict[Tuple[int, int], List[Any]]:
		return getattr(self.sys, 'grid', {})

	def cell_size(self) -> int:
		return int(getattr(self.sys, 'cell_size', 3))

	def rebuild_grid(self):
		fn = getattr(self.sys, '_rebuild_grid', None)
		if callable(fn):
			try:
				fn()
			except Exception:
				pass


class CollisionManager:
	def __init__(self, world_w: int, world_h: int):
		self.world_w = int(world_w)
		self.world_h = int(world_h)
		self.systems: List[SystemProps] = []
		self.blocks = None                
		self.enabled = True
		self._frame_stride = 1

	def register_system(self, name: str, sys: Any, *, kind: str, radius: float = 1.0,
	     mass: float = 1.0, elasticity: float = 0.05, friction: float = 0.02,
	     max_neighbors: int = 6):
		self.systems.append(SystemProps(name=name, sys=sys, kind=kind, radius=radius,
		        mass=mass, elasticity=elasticity, friction=friction,
		        max_neighbors=max_neighbors))

	def register_blocks(self, blocks_system: Any):
		self.blocks = blocks_system

                           
	def _neighbors_from(self, sp: SystemProps, x: float, y: float, radius_cells: int) -> List[Any]:
		out: List[Any] = []
		grid = sp.grid()
		if not grid:
			return out
		cs = max(1, sp.cell_size())
		cx = int(x // cs)
		cy = int(y // cs)
		for dx in range(-radius_cells, radius_cells + 1):
			for dy in range(-radius_cells, radius_cells + 1):
				cell = (cx + dx, cy + dy)
				lst = grid.get(cell)
				if lst:
					out.extend(lst)
		return out

	def _resolve_pair(self, A: SystemProps, B: SystemProps):
                                                   
		plistA = A.particles()
		plistB = B.particles()
		if not plistA or not plistB:
			return
		if len(plistB) < len(plistA):
			A, B = B, A
			plistA, plistB = plistB, plistA

                            
		A.rebuild_grid()
		B.rebuild_grid()

                        
		rsum_base = A.radius + B.radius
		if A.kind == 'fluid' and B.kind == 'fluid':
			thresh = max(2.2, rsum_base + 0.2)
			elasticity = (A.elasticity + B.elasticity) * 0.6
			fluid_mode = True
		elif (A.kind == 'fluid') ^ (B.kind == 'fluid'):
			thresh = max(2.1, rsum_base + 0.1)
			elasticity = (A.elasticity + B.elasticity) * 0.5
			fluid_mode = False
		else:
			thresh = max(2.0, rsum_base)
			elasticity = (A.elasticity + B.elasticity) * 0.7
			fluid_mode = False

		thresh2 = thresh * thresh
		invMA = 1.0 / max(1e-6, A.mass)
		invMB = 1.0 / max(1e-6, B.mass)

                                                 
		rad_cells = max(1, int(math.ceil(thresh / max(1, B.cell_size()))))

		for p in plistA:
			if getattr(p, 'dead', False):
				continue
			px = getattr(p, 'x', None); py = getattr(p, 'y', None)
			if px is None or py is None:
				continue
			neigh = self._neighbors_from(B, px, py, rad_cells)
			checked = 0
			for q in neigh:
				if p is q or getattr(q, 'dead', False):
					continue
				qx = getattr(q, 'x', None); qy = getattr(q, 'y', None)
				if qx is None or qy is None:
					continue
				dx = qx - px
				dy = qy - py
				d2 = dx * dx + dy * dy
				if d2 <= 1e-12 or d2 > thresh2:
					continue
				d = math.sqrt(d2)
            
				nx = dx / d
				ny = dy / d
                                                      
				overlap = max(0.0, thresh - d)
				if overlap <= 0:
					continue
                                                 
				wA = invMA / (invMA + invMB)
				wB = invMB / (invMA + invMB)
                                                  
				sep_scale = 0.9 if (A.kind == 'solid' and B.kind == 'solid') else 0.6
				ax = -nx * overlap * wA * sep_scale
				ay = -ny * overlap * wA * sep_scale
				bx = nx * overlap * wB * sep_scale
				by = ny * overlap * wB * sep_scale
                        
				try:
					p.x += ax; p.y += ay
					q.x += bx; q.y += by
				except Exception:
					pass
                                                    
				pvx = getattr(p, 'vx', 0.0); pvy = getattr(p, 'vy', 0.0)
				qvx = getattr(q, 'vx', 0.0); qvy = getattr(q, 'vy', 0.0)
				rvx = pvx - qvx
				rvy = pvy - qvy
				vn = rvx * nx + rvy * ny
				if vn < 0.0:
                                      
					e = elasticity
					j = -(1 + e) * vn / (invMA + invMB)
					impAx = -j * invMA * nx
					impAy = -j * invMA * ny
					impBx = j * invMB * nx
					impBy = j * invMB * ny
					try:
						p.vx = pvx + impAx
						p.vy = pvy + impAy
						q.vx = qvx + impBx
						q.vy = qvy + impBy
					except Exception:
						pass
				else:
                                                         
					tf = (A.friction + B.friction) * 0.5
					try:
						p.vx *= 1.0 - tf
						p.vy *= 1.0 - tf * 0.5
						q.vx *= 1.0 - tf
						q.vy *= 1.0 - tf * 0.5
					except Exception:
						pass
				checked += 1
				if checked >= A.max_neighbors:
					break

	def _resolve_blocks(self, S: SystemProps):
		if not self.blocks:
			return
		is_solid = getattr(self.blocks, 'is_solid', None)
		if not callable(is_solid):
			return
		for p in S.particles():
			if getattr(p, 'dead', False):
				continue
			x = getattr(p, 'x', None); y = getattr(p, 'y', None)
			if x is None or y is None:
				continue
			ix = int(x); iy = int(y)
			try:
				inside = bool(is_solid(ix, iy))
			except Exception:
				inside = False
			if not inside:
				continue
                                                              
			dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
			best = None
			for dx, dy in dirs:
				tx, ty = ix + dx, iy + dy
				try:
					if not is_solid(tx, ty):
						best = (dx, dy)
						break
				except Exception:
					continue
			if best is None:
                                     
				best = (0, -1)
			bx, by = best
			try:
				p.x = float(ix + bx)
				p.y = float(iy + by)
                   
				if hasattr(p, 'vx'):
					p.vx *= -0.05
				if hasattr(p, 'vy'):
					p.vy = 0.0
			except Exception:
				pass

	def apply(self, frame_index: int = 0):
		if not self.enabled or not self.systems:
			return
                                                 
		total = sum(len(sp.particles()) for sp in self.systems)
		if total > 120_000:
			self._frame_stride = 3
		elif total > 80_000:
			self._frame_stride = 2
		else:
			self._frame_stride = 1
		if (frame_index % self._frame_stride) != 0:
			return

                      
		n = len(self.systems)
		for i in range(n):
			Si = self.systems[i]
			for j in range(i + 1, n):
				Sj = self.systems[j]
				try:
					self._resolve_pair(Si, Sj)
				except Exception:
                                            
					continue
                                             
		try:
			for S in self.systems:
				self._resolve_blocks(S)
		except Exception:
			pass


                                       
def default_register_all(game: Any) -> CollisionManager:
	cm = CollisionManager(game.game_width, game.height)
                    
	cm.register_system('sand', game.sand_system, kind='solid', radius=1.0, mass=1.0)
	if hasattr(game, 'dirt_system'):
		cm.register_system('dirt', game.dirt_system, kind='solid', radius=1.0, mass=1.1)
	cm.register_system('metal', game.metal_system, kind='solid', radius=1.0, mass=4.0)
	if hasattr(game, 'ruby_system'):
		cm.register_system('ruby', game.ruby_system, kind='solid', radius=1.0, mass=2.2)
	if hasattr(game, 'diamond_system'):
		cm.register_system('diamond', game.diamond_system, kind='solid', radius=1.0, mass=1.9)
         
	cm.register_system('water', game.water_system, kind='fluid', radius=1.1, mass=0.8, elasticity=0.03)
	if hasattr(game, 'milk_system'):
		cm.register_system('milk', game.milk_system, kind='fluid', radius=1.1, mass=0.9, elasticity=0.03)
	if hasattr(game, 'oil_system'):
		cm.register_system('oil', game.oil_system, kind='fluid', radius=1.1, mass=0.85, elasticity=0.03)
	cm.register_system('lava', game.lava_system, kind='fluid', radius=1.15, mass=1.2, elasticity=0.04)
	if hasattr(game, 'blue_lava_system'):
		cm.register_system('bluelava', game.blue_lava_system, kind='fluid', radius=1.15, mass=1.3, elasticity=0.04)
	cm.register_system('toxic', game.toxic_system, kind='fluid', radius=1.1, mass=1.5, elasticity=0.03)
	if hasattr(game, 'blood_system'):
		cm.register_system('blood', game.blood_system, kind='fluid', radius=1.1, mass=1.1, elasticity=0.03)
                            
	cm.register_blocks(game.blocks_system)
	return cm
