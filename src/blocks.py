import pygame
from typing import List, Tuple, Dict


class Block:
    """Axis-aligned rectangular rigid body with simple gravity and collisions."""
    def __init__(self, x: float, y: float, w: int, h: int):
        self.x = float(x)
        self.y = float(y)
        self.w = int(max(1, w))
        self.h = int(max(1, h))
        self.vx = 0.0
        self.vy = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))


class BlocksSystem:
    """Manages draggable block structures made of square pixels.

    - Blocks fall under gravity, collide with bounds and other blocks.
    - Exposes is_solid(x,y) so particles treat blocks as obstacles.
    - Rebuilds a per-pixel occupancy each frame for fast queries.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.blocks: List[Block] = []
        self.gravity = 0.5
        self.bounce = 0.1
        self.friction = 0.02
        # Per-pixel occupancy of all blocks for obstacle queries
        self._cells: set[Tuple[int, int]] = set()
        # Optional external solid query (e.g., metal) to avoid interpenetration
        self._is_solid_external = None
        self.color = (180, 180, 190)

    def set_external_obstacle(self, fn):
        """Provide function is_solid(x:int,y:int)->bool for external solids (e.g., metal)."""
        self._is_solid_external = fn

    def is_solid(self, x: int, y: int) -> bool:
        return (int(x), int(y)) in self._cells

    def add_block_rect(self, x0: int, y0: int, x1: int, y1: int):
        # Normalize and clamp
        x_min = max(0, min(x0, x1))
        y_min = max(0, min(y0, y1))
        x_max = min(self.width - 1, max(x0, x1))
        y_max = min(self.height - 1, max(y0, y1))
        w = max(1, x_max - x_min + 1)
        h = max(1, y_max - y_min + 1)
        self.blocks.append(Block(x_min, y_min, w, h))
        self._rebuild_occupancy()

    def clear(self):
        self.blocks.clear()
        self._cells.clear()

    def _rebuild_occupancy(self):
        cells = set()
        for b in self.blocks:
            bx = int(max(0, min(self.width - 1, b.x)))
            by = int(max(0, min(self.height - 1, b.y)))
            bw = int(max(1, min(b.w, self.width - bx)))
            bh = int(max(1, min(b.h, self.height - by)))
            for yy in range(by, by + bh):
                for xx in range(bx, bx + bw):
                    cells.add((xx, yy))
        self._cells = cells

    def _collide_bounds(self, b: Block):
        # Bottom
        if b.y + b.h >= self.height:
            b.y = float(self.height - b.h)
            b.vy *= -self.bounce
        # Top
        if b.y < 0:
            b.y = 0.0
            b.vy = 0.0
        # Left
        if b.x < 0:
            b.x = 0.0
            b.vx *= -self.bounce
        # Right
        if b.x + b.w >= self.width:
            b.x = float(self.width - b.w)
            b.vx *= -self.bounce

    def _collide_external(self, b: Block):
        if not self._is_solid_external:
            return
        # Sample bottom edge to prevent sinking into external solids
        step = max(1, b.w // 8)
        collided = False
        for xx in range(int(b.x), int(b.x + b.w), step):
            if self._is_solid_external(xx, int(b.y + b.h)):
                collided = True
                break
        if collided:
            # Move up until not colliding
            while self._is_solid_external(int(b.x + b.w // 2), int(b.y + b.h)) and b.y > 0:
                b.y -= 1.0
            b.vy = 0.0
        # Side sampling for horizontal collisions
        if b.vx > 0:
            yy = int(b.y + b.h // 2)
            if self._is_solid_external(int(b.x + b.w), yy):
                b.x = float(int(b.x))
                b.vx = 0.0
        elif b.vx < 0:
            yy = int(b.y + b.h // 2)
            if self._is_solid_external(int(b.x) - 1, yy):
                b.x = float(int(b.x))
                b.vx = 0.0

    def _collide_blocks(self):
        # Simple pairwise AABB resolution; stable for small counts
        n = len(self.blocks)
        for i in range(n):
            bi = self.blocks[i]
            ri = bi.rect
            for j in range(i + 1, n):
                bj = self.blocks[j]
                rj = bj.rect
                if not ri.colliderect(rj):
                    continue
                # Minimum translation along axis
                dx1 = rj.right - ri.left
                dx2 = ri.right - rj.left
                dy1 = rj.bottom - ri.top
                dy2 = ri.bottom - rj.top
                # Choose smallest magnitude separation
                sep_x = dx1 if dx1 < dx2 else -dx2
                sep_y = dy1 if dy1 < dy2 else -dy2
                if abs(sep_x) < abs(sep_y):
                    # Separate horizontally
                    move = sep_x / 2.0
                    bi.x -= move
                    bj.x += move
                    bi.vx *= (1 - self.friction)
                    bj.vx *= (1 - self.friction)
                else:
                    move = sep_y / 2.0
                    bi.y -= move
                    bj.y += move
                    bi.vy *= (1 - self.friction)
                    bj.vy *= (1 - self.friction)
                # Update rects after adjustment
                ri = bi.rect
                rj = bj.rect

    def update(self, frame_index: int = 0):
        # Integrate motion
        for b in self.blocks:
            b.vy += self.gravity
            b.vx *= (1 - self.friction)
            if abs(b.vx) < 0.01:
                b.vx = 0.0
            b.x += b.vx
            b.y += b.vy
            self._collide_bounds(b)
        # Resolve inter-block collisions
        self._collide_blocks()
        # External solids (e.g., metal) resolution
        for b in self.blocks:
            self._collide_external(b)
        # Rebuild occupancy for obstacle queries
        self._rebuild_occupancy()

    def draw(self, surf: pygame.Surface):
        col = self.color
        for b in self.blocks:
            pygame.draw.rect(surf, col, b.rect)

    def get_point_groups(self) -> Tuple[Tuple[int, int, int], List[Tuple[int, int]]]:
        pts: List[Tuple[int, int]] = []
        for b in self.blocks:
            bx = int(b.x)
            by = int(b.y)
            bw = int(b.w)
            bh = int(b.h)
            for yy in range(by, by + bh):
                for xx in range(bx, bx + bw):
                    pts.append((xx, yy))
        return (self.color, pts)

    def get_particle_count(self) -> int:
        # Count blocks, not pixels, for stats readability
        return len(self.blocks)
