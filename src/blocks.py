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
        # True when resting on something (ground or another block) after resolution
        self.grounded = False
        # Previous-frame position for CCD-like sweep tests
        self.px = float(self.x)
        self.py = float(self.y)

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

    def _resolve_pair(self, bi: Block, bj: Block) -> bool:
        """Resolve collision between two blocks with stacking-friendly logic.
        Returns True if a resolution was applied.
        """
        ri = bi.rect
        rj = bj.rect
        if not ri.colliderect(rj):
            return False

        # Compute overlaps along axes
        overlap_left = rj.right - ri.left
        overlap_right = ri.right - rj.left
        overlap_top = rj.bottom - ri.top
        overlap_bottom = ri.bottom - rj.top

        sep_x = overlap_left if overlap_left < overlap_right else -overlap_right
        sep_y = overlap_top if overlap_top < overlap_bottom else -overlap_bottom

        resolved = False

        # Prefer vertical when falling or when vertical overlap is similar to horizontal
        prefer_vertical = abs(sep_y) <= abs(sep_x) or bi.vy > 0.05 or bj.vy < -0.05
        if prefer_vertical:
            # Prefer resolving vertically for stacking stability
            # Determine who is on top based on centers
            if ri.centery <= rj.centery:
                # bi is above bj -> snap bi to top of bj
                target_y = bj.y - bi.h
                if bi.y > target_y - 0.001:
                    bi.y = float(target_y)
                else:
                    bi.y = float(target_y)
                # If falling, stop vertical velocity and mark grounded
                if bi.vy > 0:
                    bi.vy = 0.0
                bi.grounded = True
                # Apply horizontal friction on landing to reduce jitter
                bi.vx *= (1 - min(1.0, self.friction * 4))
            else:
                # bi is below bj -> snap bi under bj
                target_y = bj.y + bj.h
                bi.y = float(target_y)
                if bi.vy < 0:
                    bi.vy = 0.0
            resolved = True
        else:
            # Horizontal resolution: push away along X, damp vx (side bump)
            if ri.centerx <= rj.centerx:
                # bi is left of bj
                target_x = bj.x - bi.w
                bi.x = float(target_x)
                if bi.vx > 0:
                    bi.vx *= -self.bounce  # small bounce to separate
            else:
                # bi is right of bj
                target_x = bj.x + bj.w
                bi.x = float(target_x)
                if bi.vx < 0:
                    bi.vx *= -self.bounce
            # Additional friction to settle stacks
            bi.vx *= (1 - min(1.0, self.friction * 2))
            resolved = True

        return resolved

    def _collide_blocks(self):
        """Iteratively resolve block-vs-block collisions for stable stacks."""
        n = len(self.blocks)
        if n <= 1:
            return
        # First, continuous-like vertical sweep to catch pass-throughs between frames
        for i in range(n):
            bi = self.blocks[i]
            ri = bi.rect
            prev_bottom = int(bi.py) + bi.h
            curr_bottom = ri.bottom
            for j in range(n):
                if i == j:
                    continue
                bj = self.blocks[j]
                rj = bj.rect
                # Only consider downward motion of bi passing a top face of bj
                if bi.vy <= 0:
                    continue
                top_face = rj.top
                # Check if bottom swept across the top face between frames
                if prev_bottom <= top_face < curr_bottom:
                    # Horizontal overlap?
                    if (ri.right > rj.left) and (ri.left < rj.right):
                        bi.y = float(bj.y - bi.h)
                        bi.vy = 0.0
                        bi.grounded = True
                        # Update rect for later passes
                        ri = bi.rect
                        curr_bottom = ri.bottom
        
        # Run a few passes to propagate corrections through stacks
        max_passes = 4
        for _ in range(max_passes):
            any_resolved = False
            for i in range(n):
                bi = self.blocks[i]
                for j in range(i + 1, n):
                    bj = self.blocks[j]
                    # Resolve in both orders to bias moving the likely intruder first
                    r1 = self._resolve_pair(bi, bj)
                    r2 = self._resolve_pair(bj, bi)
                    if r1 or r2:
                        any_resolved = True
            if not any_resolved:
                break

    def update(self, frame_index: int = 0):
        # Integrate motion
        for b in self.blocks:
            # Store previous position for sweep tests
            b.px = b.x
            b.py = b.y
            b.grounded = False
            b.vy += self.gravity
            b.vx *= (1 - self.friction)
            if abs(b.vx) < 0.01:
                b.vx = 0.0
            b.x += b.vx
            b.y += b.vy
            self._collide_bounds(b)
        # Resolve inter-block collisions
        self._collide_blocks()
        # Dampen tiny velocities when grounded to avoid jitter
        for b in self.blocks:
            if b.grounded:
                if abs(b.vy) < 0.05:
                    b.vy = 0.0
                if abs(b.vx) < 0.02:
                    b.vx = 0.0
                # Micro-snap to pixel grid to stabilize resting
                b.y = float(int(round(b.y)))
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
