"""Background grid rendering utilities (CPU + GPU paths).

Draws a subtle grid that aligns to world-space and adapts to window size and zoom.
"""
from __future__ import annotations

from typing import Tuple

try:
    # For GPU path rects
    from pygame._sdl2 import rect as sdl2rect  # type: ignore
except Exception:  # pragma: no cover - fallback when not using GPU
    sdl2rect = None  # type: ignore

import pygame


class GridBackground:
    def __init__(
        self,
        base_color: Tuple[int, int, int] = (30, 30, 30),
        minor_color: Tuple[int, int, int] = (36, 36, 36),
        major_color: Tuple[int, int, int] = (58, 58, 58),
        target_px: int = 28,
        major_every: int = 5,
    ) -> None:
        self.base_color = base_color
        self.minor_color = minor_color
        self.major_color = major_color
        self.target_px = max(8, int(target_px))
        self.major_every = max(2, int(major_every))

    def _iter_lines(self, view_w: int, view_h: int, off_x: float, off_y: float, scale: float):
        """Yield vertical and horizontal line positions in view space.
        Returns generators of tuples: (x, is_major) for verticals and (y, is_major) for horizontals.
        """
        s = max(1e-6, float(scale))
        spacing_world = max(4.0, self.target_px / s)

        # Vertical lines: index in world space so major lines are stable with camera moves
        start_idx_x = int(off_x // spacing_world)
        end_idx_x = int((off_x + view_w / s) // spacing_world) + 1
        def vert_gen():
            for idx in range(start_idx_x, end_idx_x + 1):
                wx = idx * spacing_world
                vx = int((wx - off_x) * s)
                if 0 <= vx <= view_w:
                    yield vx, (idx % self.major_every == 0)
        # Horizontal lines
        start_idx_y = int(off_y // spacing_world)
        end_idx_y = int((off_y + view_h / s) // spacing_world) + 1
        def hori_gen():
            for idx in range(start_idx_y, end_idx_y + 1):
                wy = idx * spacing_world
                vy = int((wy - off_y) * s)
                if 0 <= vy <= view_h:
                    yield vy, (idx % self.major_every == 0)
        return vert_gen(), hori_gen()

    def draw_cpu(self, surface: pygame.Surface, camera) -> None:
        """Draw grid on a CPU surface representing the current game view.

        The surface is assumed to represent the game area in view space.
        """
        view_w, view_h = surface.get_size()
        s = max(1e-6, float(camera.scale))
        off_x = float(camera.off_x)
        off_y = float(camera.off_y)

        # Optional: fill the base (caller usually does)
        # surface.fill(self.base_color)

        vgen, hgen = self._iter_lines(view_w, view_h, off_x, off_y, s)
        # Draw verticals
        for x, is_major in vgen:
            color = self.major_color if is_major else self.minor_color
            pygame.draw.line(surface, color, (x, 0), (x, view_h))
        # Draw horizontals
        for y, is_major in hgen:
            color = self.major_color if is_major else self.minor_color
            pygame.draw.line(surface, color, (0, y), (view_w, y))

    def draw_gpu(self, renderer, game_rect: Tuple[int, int, int, int], camera) -> None:
        """Draw grid using SDL2 renderer.

        game_rect: (x, y, w, h) rectangle in window coordinates where the game area lives.
        """
        gx, gy, gw, gh = game_rect
        s = max(1e-6, float(camera.scale))
        off_x = float(camera.off_x)
        off_y = float(camera.off_y)

        vgen, hgen = self._iter_lines(gw, gh, off_x, off_y, s)

        # Draw vertical lines as 1px wide rects to minimize API variability
        for x, is_major in vgen:
            color = self.major_color if is_major else self.minor_color
            renderer.draw_color = (*color, 255)
            if sdl2rect is not None:
                renderer.fill_rect(sdl2rect.Rect(gx + x, gy, 1, gh))
            else:
                try:
                    renderer.draw_line(gx + x, gy, gx + x, gy + gh)
                except Exception:
                    # If draw_line unavailable, skip
                    pass
        # Horizontal lines
        for y, is_major in hgen:
            color = self.major_color if is_major else self.minor_color
            renderer.draw_color = (*color, 255)
            if sdl2rect is not None:
                renderer.fill_rect(sdl2rect.Rect(gx, gy + y, gw, 1))
            else:
                try:
                    renderer.draw_line(gx, gy + y, gx + gw, gy + y)
                except Exception:
                    pass
