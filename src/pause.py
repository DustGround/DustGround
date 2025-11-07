from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import math
import time
import pygame
try:
    from pygame._sdl2.video import Texture
    from pygame._sdl2 import rect as sdl2rect
except Exception:
    Texture = None
    sdl2rect = None
from src.pluginman.pluginmenu import PluginMenuPanel

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
        return abs(self.scale - 1.0) < 1e-06 and abs(self.off_x) < 1e-06 and (abs(self.off_y) < 1e-06)

class PauseMenu:

    def __init__(self):
        self.options: List[str] = ['Resume', 'Plugins', 'Exit']
        self.state: str = 'main'
        self.selected: int = 0
        self._last_time = time.time()
        self._t = 0.0
        self._pulse_speed = 1.6
        self.title_font = pygame.font.Font(None, 56)
        self.item_font = pygame.font.Font(None, 36)
        self.accent = (160, 180, 210)
        self.accent_fill = (55, 70, 95)
        self.accent_outline = (100, 130, 170)
        self._text_cache = {}
        self.plugin_panel = PluginMenuPanel()
        self.back_label = 'Back'

    def _advance_time(self) -> float:
        now = time.time()
        dt = max(0.0, min(0.1, now - self._last_time))
        self._last_time = now
        self._t += dt
        return dt

    def update(self) -> None:
        self._advance_time()

    def _pulse(self) -> float:
        return 0.925 + 0.075 * math.sin(self._t * self._pulse_speed * math.tau)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if self.state == 'plugins':
            res = self.plugin_panel.handle_event(event)
            if res == 'back':
                self.state = 'main'
            return None
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._activate()
        elif event.type == pygame.MOUSEWHEEL:
            if getattr(event, 'y', 0) > 0:
                self.selected = (self.selected - 1) % len(self.options)
            elif getattr(event, 'y', 0) < 0:
                self.selected = (self.selected + 1) % len(self.options)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = pygame.mouse.get_pos()
            left_margin = 64
            spacing = self.item_font.get_height() + 12
            try:
                height = pygame.display.get_surface().get_height()
            except Exception:
                height = 800
            center_y = height // 2
            items_h = len(self.options) * spacing
            start_y = center_y - items_h // 2
            x = left_margin
            for idx, text in enumerate(self.options):
                y = start_y + idx * spacing
                rect = pygame.Rect(x, y, 400, self.item_font.get_height())
                if rect.collidepoint(mx, my):
                    self.selected = idx
                    return self._activate()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            return self._activate()
        return None

    def _activate(self) -> Optional[str]:
        text = self.options[self.selected]
        lc = text.lower()
        if lc.startswith('resume'):
            return 'resume'
        if lc.startswith('plugins'):
            self.state = 'plugins'
            return None
        if lc.startswith('exit'):
            return 'exit'
        return None

    def draw_cpu(self, screen: pygame.Surface, left_margin: int=64) -> None:
        width, height = screen.get_size()
        center_y = height // 2
        if self.state == 'plugins':
            self.plugin_panel.draw_cpu(screen)
            return
        title = 'paused'
        title_surf = self.title_font.render(title, True, (220, 220, 220))
        screen.blit(title_surf, (left_margin, 40))
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
            if is_sel:
                under_w = int(surf.get_width() * pulse)
                under_h = 3
                ux = x
                uy = y + surf.get_height() + 6
                pygame.draw.rect(screen, self.accent, (ux, uy, under_w, under_h))

    def _get_text_tex(self, renderer, text: str, color: Tuple[int, int, int]):
        key = (text, color)
        if Texture is None:
            raise RuntimeError('SDL2 Texture is unavailable')
        if key in self._text_cache:
            surf = self.item_font.render(text, True, color)
            return (self._text_cache[key], surf)
        surf = self.item_font.render(text, True, color)
        tex = Texture.from_surface(renderer, surf)
        self._text_cache[key] = tex
        return (tex, surf)

    def draw_gpu(self, renderer, left_margin: int=64) -> None:
        try:
            out_w, out_h = renderer.output_size
        except Exception:
            out_w, out_h = (1200, 800)
        center_y = out_h // 2
        if self.state == 'plugins':
            self.plugin_panel.draw_gpu(renderer)
            return
        title = 'paused'
        title_surf = self.title_font.render(title, True, (220, 220, 220))
        title_tex = Texture.from_surface(renderer, title_surf) if Texture is not None else None
        if title_tex is not None and sdl2rect is not None:
            renderer.copy(title_tex, dstrect=sdl2rect.Rect(left_margin, 40, title_surf.get_width(), title_surf.get_height()))
        spacing = self.item_font.get_height() + 12
        items_h = len(self.options) * spacing
        start_y = center_y - items_h // 2
        pulse = self._pulse()
        for idx, text in enumerate(self.options):
            is_sel = idx == self.selected
            color = (235, 235, 235) if is_sel else (200, 200, 200)
            surf = self.item_font.render(text, True, color)
            tex = Texture.from_surface(renderer, surf) if Texture is not None else None
            x = left_margin
            y = start_y + idx * spacing
            if tex is not None and sdl2rect is not None:
                renderer.copy(tex, dstrect=sdl2rect.Rect(x, y, surf.get_width(), surf.get_height()))
            if is_sel and sdl2rect is not None:
                under_w = int(surf.get_width() * pulse)
                under_h = 3
                ux = x
                uy = y + surf.get_height() + 6
                renderer.draw_color = (self.accent[0], self.accent[1], self.accent[2], 255)
                renderer.fill_rect(sdl2rect.Rect(ux, uy, under_w, under_h))
