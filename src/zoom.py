from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Camera:
    """2D camera for panning and zooming in game-world space.

    Coordinates use a "view" rectangle (the game canvas, excluding the sidebar).
    - World space: physics coordinates (0..world_w-1, 0..world_h-1)
    - View space: pixels inside the game area (0..view_w-1, 0..view_h-1)
    """

    world_w: int
    world_h: int
    view_w: int
    view_h: int
    scale: float = 1.0
    min_scale: float = 0.5
    max_scale: float = 6.0
    off_x: float = 0.0
    off_y: float = 0.0

    def update_view(self, view_w: int, view_h: int, world_w: int | None = None, world_h: int | None = None):
        self.view_w = int(view_w)
        self.view_h = int(view_h)
        if world_w is not None:
            self.world_w = int(world_w)
        if world_h is not None:
            self.world_h = int(world_h)
        self.clamp()

    def is_identity(self) -> bool:
        return abs(self.scale - 1.0) < 1e-6 and abs(self.off_x) < 1e-6 and abs(self.off_y) < 1e-6

    def world_to_view(self, x: float, y: float) -> tuple[int, int]:
        vx = int((x - self.off_x) * self.scale)
        vy = int((y - self.off_y) * self.scale)
        return vx, vy

    def view_to_world(self, vx: float, vy: float) -> tuple[float, float]:
        wx = vx / self.scale + self.off_x
        wy = vy / self.scale + self.off_y
        return wx, wy

    def zoom_at(self, factor: float, anchor_vx: float, anchor_vy: float):
        """Zoom keeping the world point under the given view pixel as the focus."""
        # World position before zoom
        wx, wy = self.view_to_world(anchor_vx, anchor_vy)
        # Apply clamped scale
        new_scale = max(self.min_scale, min(self.max_scale, self.scale * factor))
        if abs(new_scale - self.scale) < 1e-6:
            return
        self.scale = new_scale
        # Recompute offset so (wx, wy) maps back to the same screen point
        self.off_x = wx - anchor_vx / self.scale
        self.off_y = wy - anchor_vy / self.scale
        self.clamp()

    def pan_by(self, dx_view: float, dy_view: float):
        """Pan by view-space delta in pixels."""
        self.off_x += dx_view / self.scale
        self.off_y += dy_view / self.scale
        self.clamp()

    def clamp(self):
        # Clamp offset so the view stays within world bounds where possible
        max_off_x = max(0.0, self.world_w - self.view_w / self.scale)
        max_off_y = max(0.0, self.world_h - self.view_h / self.scale)
        self.off_x = max(0.0, min(self.off_x, max_off_x))
        self.off_y = max(0.0, min(self.off_y, max_off_y))
