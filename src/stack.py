from __future__ import annotations

from typing import Dict, List, Tuple, Any, Optional, Iterable

class StackEntry:
	__slots__ = ("obj", "material", "z", "x", "y")
	def __init__(self, obj: Any, material: str, z: int, x: int, y: int):
		self.obj = obj                                        
		self.material = material
		self.z = z                                                  
		self.x = x
		self.y = y

	def __repr__(self) -> str:
		return f"StackEntry(material={self.material}, z={self.z}, pos=({self.x},{self.y}))"

class StackManager:
	def __init__(self, max_height: Optional[int] = None, auto_compact_interval: int = 600):
		self._cells: Dict[Tuple[int,int], List[StackEntry]] = {}
		self._index: Dict[int, StackEntry] = {}                    
		self.max_height = max_height
		self._frame = 0
		self._auto_compact_interval = max(60, int(auto_compact_interval))
                                                                                        
		self.material_density: Dict[str, float] = {
		 'blocks': 9.0,
		 'metal': 8.0,
		 'ruby': 7.5,
		 'diamond': 7.4,
		 'lava': 7.0,
		 'bluelava': 7.2,
		 'toxic': 3.0,
		 'oil': 2.5,
		 'water': 2.0,
		 'milk': 2.1,
		 'blood': 2.2,
		 'sand': 4.0,
		 'dirt': 4.5,
		}

                                                                           
	def add(self, x: int, y: int, obj: Any, material: str) -> int:
		"""Add an object at integer cell (x,y). Returns assigned z index.
		If max_height is set and would exceed, skip adding and return top z."""
		cell = (int(x), int(y))
		lst = self._cells.get(cell)
		if lst is None:
			lst = []
			self._cells[cell] = lst
		if self.max_height is not None and len(lst) >= self.max_height:
                                                           
			return len(lst) - 1
		entry = StackEntry(obj=obj, material=material, z=0, x=cell[0], y=cell[1])
		lst.append(entry)
                                                                         
		dens = self.material_density
		lst.sort(key=lambda e: dens.get(e.material, 5.0))
		for i, ent in enumerate(lst):
			ent.z = i
			try:
				setattr(ent.obj, 'stack_z', i)
			except Exception:
				pass
		z = entry.z
		self._index[id(obj)] = entry
		try:
			setattr(obj, 'stack_z', z)
			setattr(obj, 'stack_cell', cell)
		except Exception:
			pass
		return z

	def remove(self, obj: Any) -> bool:
		e = self._index.pop(id(obj), None)
		if e is None:
			return False
		cell = (e.x, e.y)
		lst = self._cells.get(cell)
		if not lst:
			return False
		try:
			lst.remove(e)
		except ValueError:
			pass
                            
		for i, ent in enumerate(lst):
			ent.z = i
			try:
				setattr(ent.obj, 'stack_z', i)
			except Exception:
				pass
		if not lst:
			self._cells.pop(cell, None)
		return True

	def move(self, obj: Any, old_x: int, old_y: int, new_x: int, new_y: int) -> int:
		"""Update an object's cell, returning new z index. If unchanged cell,
		returns existing z. If object not tracked, calls add."""
		e = self._index.get(id(obj))
		if e is None:
			return self.add(new_x, new_y, obj, getattr(obj, 'material', 'unknown'))
		new_cell = (int(new_x), int(new_y))
		if (e.x, e.y) == new_cell:
			return e.z
                        
		old_cell = (e.x, e.y)
		lst_old = self._cells.get(old_cell)
		if lst_old and e in lst_old:
			lst_old.remove(e)
			for i, ent in enumerate(lst_old):
				ent.z = i
				try:
					setattr(ent.obj, 'stack_z', i)
				except Exception:
					pass
			if not lst_old:
				self._cells.pop(old_cell, None)
                            
		lst_new = self._cells.get(new_cell)
		if lst_new is None:
			lst_new = []
			self._cells[new_cell] = lst_new
		if self.max_height is not None and len(lst_new) >= self.max_height:
                                                       
			self.add(e.x, e.y, obj, e.material)
			return e.z
		e.x, e.y = new_cell
		lst_new.append(e)
                              
		dens = self.material_density
		lst_new.sort(key=lambda en: dens.get(en.material, 5.0))
		for i, ent in enumerate(lst_new):
			ent.z = i
			try:
				setattr(ent.obj, 'stack_z', i)
				setattr(ent.obj, 'stack_cell', new_cell)
			except Exception:
				pass
		return e.z

                                                                            
	def get_stack(self, x: int, y: int) -> List[StackEntry]:
		return list(self._cells.get((int(x), int(y)), []))

	def get_top(self, x: int, y: int) -> Optional[StackEntry]:
		lst = self._cells.get((int(x), int(y)))
		if lst:
			return lst[-1]
		return None

	def get_below(self, obj: Any) -> Optional[StackEntry]:
		e = self._index.get(id(obj))
		if not e:
			return None
		lst = self._cells.get((e.x, e.y))
		if not lst or e.z == 0:
			return None
		return lst[e.z - 1]

	def iter_cells(self) -> Iterable[Tuple[Tuple[int,int], List[StackEntry]]]:
		for cell, lst in self._cells.items():
			yield cell, list(lst)

	def iter_top(self) -> Iterable[StackEntry]:
		for lst in self._cells.values():
			if lst:
				yield lst[-1]

                                                                            
	def compact(self) -> None:
		"""Remove entries whose obj appears dead / missing, reindex layers."""
		to_delete = []
		for cell, lst in self._cells.items():
			alive = []
			for ent in lst:
				if getattr(ent.obj, 'dead', False):
					self._index.pop(id(ent.obj), None)
				else:
					alive.append(ent)
			if alive:
				for i, ent in enumerate(alive):
					ent.z = i
					try:
						setattr(ent.obj, 'stack_z', i)
					except Exception:
						pass
				self._cells[cell] = alive
			else:
				to_delete.append(cell)
		for c in to_delete:
			self._cells.pop(c, None)

                                                                            
	def promote(self, obj: Any) -> int:
		"""Move object one layer up within its cell (if possible). Returns new z."""
		e = self._index.get(id(obj))
		if not e:
			return -1
		lst = self._cells.get((e.x, e.y))
		if not lst or e.z == len(lst) - 1:
			return e.z
		lst[e.z], lst[e.z + 1] = lst[e.z + 1], lst[e.z]
		lst[e.z].z = e.z
		lst[e.z + 1].z = e.z + 1
		for ent in (lst[e.z], lst[e.z + 1]):
			try:
				setattr(ent.obj, 'stack_z', ent.z)
			except Exception:
				pass
		return e.z + 1

	def demote(self, obj: Any) -> int:
		"""Move object one layer down within its cell. Returns new z."""
		e = self._index.get(id(obj))
		if not e or e.z == 0:
			return e.z if e else -1
		lst = self._cells.get((e.x, e.y))
		if not lst:
			return -1
		lst[e.z], lst[e.z - 1] = lst[e.z - 1], lst[e.z]
		lst[e.z].z = e.z
		lst[e.z - 1].z = e.z - 1
		for ent in (lst[e.z], lst[e.z - 1]):
			try:
				setattr(ent.obj, 'stack_z', ent.z)
			except Exception:
				pass
		return e.z - 1

	def tallest_in_region(self, x0: int, y0: int, x1: int, y1: int) -> Tuple[int, Tuple[int,int]]:
		"""Return (height,(x,y)) of tallest stack within inclusive rectangle."""
		if x0 > x1:
			x0, x1 = x1, x0
		if y0 > y1:
			y0, y1 = y1, y0
		best_h = 0
		best_cell = (x0, y0)
		for (cx, cy), lst in self._cells.items():
			if x0 <= cx <= x1 and y0 <= cy <= y1:
				h = len(lst)
				if h > best_h:
					best_h = h
					best_cell = (cx, cy)
		return best_h, best_cell

	def set_max_height(self, new_max: Optional[int]) -> None:
		self.max_height = new_max
		if new_max is None:
			return
                                 
		for cell, lst in list(self._cells.items()):
			if len(lst) > new_max:
                       
				to_trim = lst[new_max:]
				for ent in to_trim:
					self._index.pop(id(ent.obj), None)
				del lst[new_max:]
				for i, ent in enumerate(lst):
					ent.z = i
					try:
						setattr(ent.obj, 'stack_z', i)
					except Exception:
						pass

	def update(self) -> None:
		"""Optional periodic housekeeping. Call each frame if integrated."""
		self._frame += 1
		if self._frame % self._auto_compact_interval == 0:
			self.compact()

	def rebuild_from_game(self, game: Any, material_map: Optional[Dict[str, Any]] = None) -> None:
		"""Rebuild stacks from existing systems in the game.

		material_map: optional dict mapping material key -> system attribute
		name. If not provided, defaults to common system names.
		Each particle gets its integer position; objects at identical cells form stacks.
		Existing stack state is discarded.
		"""
		self._cells.clear()
		self._index.clear()
		if material_map is None:
			material_map = {
			 'sand': 'sand_system',
			 'water': 'water_system',
			 'lava': 'lava_system',
			 'bluelava': 'blue_lava_system',
			 'toxic': 'toxic_system',
			 'oil': 'oil_system',
			 'metal': 'metal_system',
			 'ruby': 'ruby_system',
			 'milk': 'milk_system',
			 'dirt': 'dirt_system',
			 'blood': 'blood_system',
			 'blocks': 'blocks_system'
			}
		for mat, attr in material_map.items():
			sys_obj = getattr(game, attr, None)
			if sys_obj is None:
				continue
			particles = getattr(sys_obj, 'particles', [])
			for p in particles:
				try:
					x = int(getattr(p, 'x', getattr(p, 'pos', [0,0])[0]))
					y = int(getattr(p, 'y', getattr(p, 'pos', [0,0])[1]))
				except Exception:
					continue
				self.add(x, y, p, mat)

                                                                            
	def stats(self) -> Dict[str, int]:
		total_entries = sum(len(v) for v in self._cells.values())
		occupied_cells = len(self._cells)
		tallest = max((len(v) for v in self._cells.values()), default=0)
		return {
		 'entries': total_entries,
		 'cells': occupied_cells,
		 'tallest_stack': tallest,
		 'max_height': self.max_height if self.max_height is not None else -1,
		 'avg_height': (total_entries / occupied_cells) if occupied_cells else 0.0,
		}

	def describe_column(self, x: int, y: int) -> List[Tuple[str,int]]:
		"""Return list of (material, z) for a column sorted bottom->top."""
		lst = self._cells.get((int(x), int(y)), [])
		return [(e.material, e.z) for e in lst]


                                          
_GLOBAL_STACK: Optional[StackManager] = None

def get_stack_manager() -> StackManager:
	global _GLOBAL_STACK
	if _GLOBAL_STACK is None:
		_GLOBAL_STACK = StackManager(max_height=None)
	return _GLOBAL_STACK

def integrate_game(game: Any) -> StackManager:
	mgr = get_stack_manager()
	mgr.rebuild_from_game(game)
	return mgr

__all__ = [
 'StackEntry',
 'StackManager',
 'get_stack_manager',
 'integrate_game'
]

