import pygame
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    from src.npc import NPC

class Block:

    def __init__(self, x: float, y: float, w: int, h: int):
        self.x = float(x)
        self.y = float(y)
        self.w = int(max(1, w))
        self.h = int(max(1, h))
        self.vx = 0.0
        self.vy = 0.0
        self.grounded = False
        self.px = float(self.x)
        self.py = float(self.y)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

class BlocksSystem:

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.blocks: List[Block] = []
        self.gravity = 0.5
        self.bounce = 0.1
        self.friction = 0.02
        self._cells: set[Tuple[int, int]] = set()
        self._is_solid_external = None
        self.color = (180, 180, 190)

    def set_external_obstacle(self, fn):
        self._is_solid_external = fn

    def is_solid(self, x: int, y: int) -> bool:
        return (int(x), int(y)) in self._cells

    def add_block_rect(self, x0: int, y0: int, x1: int, y1: int):
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
        if b.y + b.h >= self.height:
            b.y = float(self.height - b.h)
            b.vy *= -self.bounce
        if b.y < 0:
            b.y = 0.0
            b.vy = 0.0
        if b.x < 0:
            b.x = 0.0
            b.vx *= -self.bounce
        if b.x + b.w >= self.width:
            b.x = float(self.width - b.w)
            b.vx *= -self.bounce

    def _collide_external(self, b: Block):
        if not self._is_solid_external:
            return
        step = max(1, b.w // 8)
        collided = False
        for xx in range(int(b.x), int(b.x + b.w), step):
            if self._is_solid_external(xx, int(b.y + b.h)):
                collided = True
                break
        if collided:
            while self._is_solid_external(int(b.x + b.w // 2), int(b.y + b.h)) and b.y > 0:
                b.y -= 1.0
            b.vy = 0.0
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
        ri = bi.rect
        rj = bj.rect
        if not ri.colliderect(rj):
            return False
        overlap_left = rj.right - ri.left
        overlap_right = ri.right - rj.left
        overlap_top = rj.bottom - ri.top
        overlap_bottom = ri.bottom - rj.top
        sep_x = overlap_left if overlap_left < overlap_right else -overlap_right
        sep_y = overlap_top if overlap_top < overlap_bottom else -overlap_bottom
        resolved = False
        prefer_vertical = abs(sep_y) <= abs(sep_x) or bi.vy > 0.05 or bj.vy < -0.05
        if prefer_vertical:
            if ri.centery <= rj.centery:
                target_y = bj.y - bi.h
                if bi.y > target_y - 0.001:
                    bi.y = float(target_y)
                else:
                    bi.y = float(target_y)
                if bi.vy > 0:
                    bi.vy = 0.0
                bi.grounded = True
                bi.vx *= 1 - min(1.0, self.friction * 4)
            else:
                target_y = bj.y + bj.h
                bi.y = float(target_y)
                if bi.vy < 0:
                    bi.vy = 0.0
            resolved = True
        else:
            if ri.centerx <= rj.centerx:
                target_x = bj.x - bi.w
                bi.x = float(target_x)
                if bi.vx > 0:
                    bi.vx *= -self.bounce
            else:
                target_x = bj.x + bj.w
                bi.x = float(target_x)
                if bi.vx < 0:
                    bi.vx *= -self.bounce
            bi.vx *= 1 - min(1.0, self.friction * 2)
            resolved = True
        return resolved

    def _collide_blocks(self):
        n = len(self.blocks)
        if n <= 1:
            return
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
                if bi.vy <= 0:
                    continue
                top_face = rj.top
                if prev_bottom <= top_face < curr_bottom:
                    if ri.right > rj.left and ri.left < rj.right:
                        bi.y = float(bj.y - bi.h)
                        bi.vy = 0.0
                        bi.grounded = True
                        ri = bi.rect
                        curr_bottom = ri.bottom
        max_passes = 4
        for _ in range(max_passes):
            any_resolved = False
            for i in range(n):
                bi = self.blocks[i]
                for j in range(i + 1, n):
                    bj = self.blocks[j]
                    r1 = self._resolve_pair(bi, bj)
                    r2 = self._resolve_pair(bj, bi)
                    if r1 or r2:
                        any_resolved = True
            if not any_resolved:
                break

    def update(self, frame_index: int=0, npcs: Optional[Iterable['NPC']] = None):
        for b in self.blocks:
            b.px = b.x
            b.py = b.y
            b.grounded = False
            b.vy += self.gravity
            b.vx *= 1 - self.friction
            if abs(b.vx) < 0.01:
                b.vx = 0.0
            b.x += b.vx
            b.y += b.vy
            self._collide_bounds(b)
        self._collide_blocks()
        if npcs:
            self._collide_npcs(npcs)
        for b in self.blocks:
            if b.grounded:
                if abs(b.vy) < 0.05:
                    b.vy = 0.0
                if abs(b.vx) < 0.02:
                    b.vx = 0.0
                b.y = float(int(round(b.y)))
        for b in self.blocks:
            self._collide_external(b)
        self._rebuild_occupancy()

    def _collide_npcs(self, npcs: Iterable['NPC']):
        for b in self.blocks:
            rect = b.rect
            for npc in npcs:
                if not getattr(npc, 'particles', None):
                    continue
                body_rects = self._npc_body_rects(npc)
                prev_rect = pygame.Rect(int(b.px), int(b.py), int(b.w), int(b.h))
                for body_rect, idx in body_rects:
                    if not rect.colliderect(body_rect):
                        continue
                    resolved = False
                                                                                         
                    if prev_rect.bottom <= body_rect.top and b.vy >= 0:
                        b.y = float(body_rect.top - b.h)
                        b.vy = 0.0
                        b.grounded = True
                        b.vx *= 1 - min(1.0, self.friction * 4)
                        resolved = True
                    elif prev_rect.top >= body_rect.bottom and b.vy <= 0:
                        b.y = float(body_rect.bottom)
                        b.vy = 0.0
                        resolved = True
                    else:
                                                                  
                        overlap_left = rect.right - body_rect.left
                        overlap_right = body_rect.right - rect.left
                        overlap_top = rect.bottom - body_rect.top
                        overlap_bottom = body_rect.bottom - rect.top
                        sep_x = overlap_left if overlap_left < overlap_right else -overlap_right
                        sep_y = overlap_top if overlap_top < overlap_bottom else -overlap_bottom
                        if abs(sep_y) <= abs(sep_x):
                            if sep_y > 0:
                                b.y -= sep_y
                            else:
                                b.y -= sep_y
                            b.vy = 0.0
                            if sep_y > 0:
                                b.grounded = True
                            resolved = True
                        else:
                            if sep_x > 0:
                                b.x -= sep_x
                                if b.vx > 0:
                                    b.vx *= -self.bounce
                            else:
                                b.x -= sep_x
                                if b.vx < 0:
                                    b.vx *= -self.bounce
                            resolved = True
                    if resolved:
                        rect = b.rect
                        prev_rect = pygame.Rect(int(b.px), int(b.py), int(b.w), int(b.h))
                                                                              
                        if abs(b.vx) < 0.02:
                            b.vx = 0.0
                                                                                             
                        break
                else:
                    continue
                break

    def _npc_body_rects(self, npc: 'NPC') -> List[Tuple[pygame.Rect, int]]:
        rects: List[Tuple[pygame.Rect, int]] = []
        base = max(6, int(getattr(npc, 'size', 12)))
        head_size = int(getattr(npc, 'head_size', 28))
        for idx, part in enumerate(getattr(npc, 'particles', [])):
            cx = int(part.pos.x)
            cy = int(part.pos.y)
            if idx == 0:
                rect = pygame.Rect(0, 0, head_size, head_size)
                rect.center = (cx, cy)
                rects.append((rect, idx))
                continue
            if idx in (1, 2, 3, 4):
                w = int(base * 1.4)
                h = int(base * 1.8)
            elif idx in (5, 6):
                w = int(base * 1.2)
                h = int(base * 1.2)
            else:
                w = int(base * 1.3)
                h = int(base * 1.3)
            rect = pygame.Rect(0, 0, max(6, w), max(6, h))
            rect.center = (cx, cy)
            rects.append((rect, idx))
        return rects

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
        return len(self.blocks)
