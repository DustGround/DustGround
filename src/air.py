import pygame
from typing import List, Tuple

class AirSystem:
	def __init__(self, width: int, height: int):
		self.width = width
		self.height = height
		self.alpha = 13  # ~5% opacity (255 * 0.05 ≈ 12.75)
		self.color = (220, 235, 255)  # very subtle cool tint
		self._top_y: int | None = None

	def rebuild(self, sources: List[Tuple[Tuple[int, int, int], List[Tuple[int, int]]]]):
		# Compute the highest (smallest y) occupied pixel across all sources
		min_y = None
		for _col, pts in sources:
			for (x, y) in pts:
				if 0 <= x < self.width and 0 <= y < self.height:
					if min_y is None or y < min_y:
						min_y = y
		self._top_y = int(min_y) if min_y is not None else None

	def draw(self, surface: pygame.Surface):
		# Air is invisible; no visual overlay.
		return

	def clear(self):
		self._top_y = None
