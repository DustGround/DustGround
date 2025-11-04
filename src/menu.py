from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import math
import time

import pygame

try:
    from pygame._sdl2.video import Texture  # type: ignore
    from pygame._sdl2 import rect as sdl2rect  # type: ignore
except Exception:  # pragma: no cover
    Texture = None  # type: ignore
    sdl2rect = None  # type: ignore


@dataclass
class _CameraLike:
    world_w: int = 1000
    world_h: int = 1000
    view_w: int = 1000
    view_h: int = 1000
    scale: float = 1.0
    off_x: float = 0.0
    off_y: float = 0.0

    def is_identity(self) -> bool:
        return abs(self.scale - 1.0) < 1e-6 and abs(self.off_x) < 1e-6 and abs(self.off_y) < 1e-6


class MainMenu:
    def __init__(self):
        self.options: List[str] = [
            "Play",
            "Options",
            "Plugins",
            "About",
            "Quit to Desktop",
        ]
        self.selected: int = 0
        self._last_time = time.time()
        self._t = 0.0
        self._pulse_speed = 1.6  # underline pulse speed
        self._camera = _CameraLike()
        self._min_scale = 0.65
        self._max_scale = 1.25
        self._zoom_speed = -0.02  # scale units per second (negative for zoom out)
        # Fonts (bigger for better readability)
        self.title_font = pygame.font.Font(None, 56)
        self.item_font = pygame.font.Font(None, 36)
        # Cache for GPU text textures (keyed by (text, color))
        self._text_cache = {}

    @property
    def camera(self) -> _CameraLike:
        return self._camera

    def _advance_time(self) -> float:
        now = time.time()
        dt = max(0.0, min(0.1, now - self._last_time))
        self._last_time = now
        self._t += dt
        # Zoom update
        s = self._camera.scale + self._zoom_speed * dt
        if s < self._min_scale:
            s = self._max_scale  # loop back for continuous slow zoom out
        self._camera.scale = s
        return dt

    def update(self) -> None:
        self._advance_time()

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._activate()
        elif event.type == pygame.MOUSEWHEEL:
            # Positive y is scroll up
            if getattr(event, 'y', 0) > 0:
                self.selected = (self.selected - 1) % len(self.options)
            elif getattr(event, 'y', 0) < 0:
                self.selected = (self.selected + 1) % len(self.options)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # right click
            return self._activate()
        return None

    def _activate(self) -> str:
        text = self.options[self.selected]
        if text.lower().startswith("play"):
            return "play"
        if text.lower().startswith("options"):
            return "options"
        if text.lower().startswith("plugins"):
            return "plugins"
        if text.lower().startswith("about"):
            return "about"
        if text.lower().startswith("quit"):
            return "quit"
        return ""

    def _pulse(self) -> float:
        # 0.85 .. 1.0 range pulse
        return 0.925 + 0.075 * math.sin(self._t * self._pulse_speed * math.tau)

    def draw_cpu(self, screen: pygame.Surface, left_margin: int = 64) -> None:
        # Dimensions
        width, height = screen.get_size()
        center_y = height // 2
        # Items
        # Dynamic spacing based on font height
        spacing = self.item_font.get_height() + 12
        items_h = len(self.options) * spacing
        start_y = center_y - items_h // 2
        pulse = self._pulse()
        for idx, text in enumerate(self.options):
            is_sel = idx == self.selected
            color = (235, 235, 235) if is_sel else (200, 200, 200)
            surf = self.item_font.render(text, True, color)
            x = left_margin
            y = start_y + idx * spacing
            screen.blit(surf, (x, y))
            # Underline animation (only for selected option)
            if is_sel:
                under_w = int(surf.get_width() * pulse)
                under_h = 3
                ux = x
                uy = y + surf.get_height() + 6
                pygame.draw.rect(screen, (200, 200, 200), (ux, uy, under_w, under_h))

    def _get_text_tex(self, renderer, text: str, color: Tuple[int, int, int]):
        key = (text, color)
        if Texture is None:
            raise RuntimeError("SDL2 Texture is unavailable")
        if key in self._text_cache:
            # Need surf size too for layout; regenerate a surf via font as light cost
            surf = self.item_font.render(text, True, color)
            return self._text_cache[key], surf
        surf = self.item_font.render(text, True, color)
        tex = Texture.from_surface(renderer, surf)
        self._text_cache[key] = tex
        return tex, surf

    def draw_gpu(self, renderer, left_margin: int = 64) -> None:
        # Title
        title = "Dustground"
        title_surf = self.title_font.render(title, True, (220, 220, 220))
        if Texture is not None and sdl2rect is not None:
            title_tex = Texture.from_surface(renderer, title_surf)
            renderer.copy(title_tex, dstrect=sdl2rect.Rect(left_margin, 40, title_surf.get_width(), title_surf.get_height()))
        # Items
        # We still use CPU font renders to surfaces, then copy as textures for simplicity
        # Layout similar to CPU
        # Get screen size through renderer? We draw relative positions without needing it here
        spacing = self.item_font.get_height() + 12
        # Assume caller computes center
        # We'll position relative to renderer viewport height: try to query via logical size if available
        try:
            vp = renderer.output_size
            height = vp[1]
        except Exception:
            height = 800
        center_y = height // 2
        items_h = len(self.options) * spacing
        start_y = center_y - items_h // 2
        pulse = self._pulse()
        for idx, text in enumerate(self.options):
            is_sel = idx == self.selected
            color = (235, 235, 235) if is_sel else (200, 200, 200)
            # Text
            if Texture is not None and sdl2rect is not None:
                tex, surf = self._get_text_tex(renderer, text, color)
                x = left_margin
                y = start_y + idx * spacing
                renderer.copy(tex, dstrect=sdl2rect.Rect(x, y, surf.get_width(), surf.get_height()))
                # Underline only when selected
                if is_sel:
                    under_w = int(surf.get_width() * pulse)
                    under_h = 3
                    ux = x
                    uy = y + surf.get_height() + 6
                    renderer.draw_color = (200, 200, 200, 255)
                    renderer.fill_rect(sdl2rect.Rect(ux, uy, under_w, under_h))

