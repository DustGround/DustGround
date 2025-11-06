from __future__ import annotations
import os
import sys
import webbrowser
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
import pygame
try:
    from pygame._sdl2.video import Texture
    from pygame._sdl2 import rect as sdl2rect
except Exception:
    Texture = None
    sdl2rect = None
from .pluginmain import get_service
from .pluginmodel import PluginInfo

@dataclass
class _Layout:
    left_margin: int
    list_x: int
    list_y: int
    list_w: int
    list_h: int
    detail_x: int
    detail_w: int
    row_h: int

class PluginMenuPanel:

    def __init__(self):
        self.title_font = pygame.font.Font(None, 56)
        self.item_font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 22)
        self.selected_index = 0
        self.scroll = 0
        self.accent = (160, 180, 210)
        self._text_cache = {}
        self.back_label = 'Back'
        self._back_rect = None
        self._hover_back = False
        self._last_time = pygame.time.get_ticks() / 1000.0
        self._t = 0.0
        self._pulse_speed = 1.6

    def _plugins(self) -> List[PluginInfo]:
        return sorted(get_service().get_plugins(), key=lambda p: p.name.lower())

    def _compute_layout(self, surface_size: Tuple[int, int]) -> _Layout:
        width, height = surface_size
        left_margin = 64
        total_w = max(300, width - left_margin * 2)
        list_w = int(total_w * 0.45)
        detail_w = total_w - list_w - 28
        list_x = left_margin
        list_y = 110
        list_h = height - list_y - 100
        detail_x = list_x + list_w + 28
        row_h = self.item_font.get_height() + 14
        return _Layout(left_margin, list_x, list_y, list_w, list_h, detail_x, detail_w, row_h)

    def _compute_back_rect(self, surface_size: Tuple[int, int]) -> pygame.Rect:
        width, height = surface_size
        left_margin = 64
        label_surf = self.item_font.render(self.back_label, True, (235, 235, 235))
        bx = left_margin
        by = height - (label_surf.get_height() + 28)
        return pygame.Rect(bx, by, label_surf.get_width(), label_surf.get_height())

    def _window_size(self) -> Tuple[int, int]:
        try:
            w, h = pygame.display.get_window_size()
            if w and h:
                return (int(w), int(h))
        except Exception:
            pass
        surf = pygame.display.get_surface()
        if surf:
            return surf.get_size()
        try:
            info = pygame.display.Info()
            return (info.current_w, info.current_h)
        except Exception:
            return (1200, 800)

    def _selected(self, plugins: List[PluginInfo]) -> Optional[PluginInfo]:
        if not plugins:
            return None
        i = max(0, min(self.selected_index, len(plugins) - 1))
        return plugins[i]

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        plugins = self._plugins()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_BACKSPACE,):
                return 'back'
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected_index = max(0, self.selected_index - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected_index = min(max(0, len(plugins) - 1), self.selected_index + 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                sel = self._selected(plugins)
                if sel:
                    get_service().set_enabled(sel.id, not sel.enabled)
            elif event.key == pygame.K_a and pygame.key.get_mods() & pygame.KMOD_CTRL:
                get_service().enable_all()
            elif event.key == pygame.K_d and pygame.key.get_mods() & pygame.KMOD_CTRL:
                get_service().disable_all()
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y * 40)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            if event.button == 3:
                return 'back'
            if event.button == 1:
                back_rect = self._compute_back_rect(self._window_size())
                if back_rect.collidepoint(mx, my):
                    return 'back'
                surf = pygame.display.get_surface()
                layout = self._compute_layout(surf.get_size())
                row_h = layout.row_h
                idx = (my - layout.list_y + self.scroll) // row_h
                if layout.list_x <= mx < layout.list_x + layout.list_w and layout.list_y <= my < layout.list_y + layout.list_h:
                    idx = int(idx)
                    if 0 <= idx < len(plugins):
                        self.selected_index = idx
                        if mx > layout.list_x + layout.list_w - 120:
                            sel = self._selected(plugins)
                            if sel:
                                get_service().set_enabled(sel.id, not sel.enabled)
                sel = self._selected(plugins)
                if sel and layout.detail_x <= mx < layout.detail_x + layout.detail_w:
                    by = layout.list_y
                    btn_rect = pygame.Rect(layout.detail_x, by, 120, 36)
                    if btn_rect.collidepoint(mx, my):
                        get_service().set_enabled(sel.id, not sel.enabled)
                    btn2 = pygame.Rect(layout.detail_x + 130, by, 180, 36)
                    if btn2.collidepoint(mx, my):
                        try:
                            folder = str(get_service().plugins_dir.resolve())
                            if sys.platform.startswith('linux'):
                                os.system(f'xdg-open "{folder}" >/dev/null 2>&1 &')
                            elif sys.platform == 'win32':
                                os.startfile(folder)
                            elif sys.platform == 'darwin':
                                os.system(f'open "{folder}"')
                        except Exception:
                            pass
                    btn3 = pygame.Rect(layout.detail_x + 320, by, 160, 36)
                    if btn3.collidepoint(mx, my):
                        get_service().refresh_now()
        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self._hover_back = self._compute_back_rect(self._window_size()).collidepoint(mx, my)
        return None

    def draw_cpu(self, screen: pygame.Surface) -> None:
        layout = self._compute_layout(screen.get_size())
        plugins = self._plugins()
        title_surf = self.title_font.render('plugins', True, (230, 230, 230))
        screen.blit(title_surf, (layout.left_margin, 36))
        pygame.draw.rect(screen, (32, 32, 32), (layout.list_x - 8, layout.list_y - 8, layout.list_w + 16, layout.list_h + 16), border_radius=6)
        pygame.draw.rect(screen, (30, 30, 30), (layout.detail_x - 8, layout.list_y - 8, layout.detail_w + 16, layout.list_h + 16), border_radius=6)
        row_h = layout.row_h
        y0 = layout.list_y - self.scroll
        for i, p in enumerate(plugins):
            ry = y0 + i * row_h
            if ry + row_h < layout.list_y or ry > layout.list_y + layout.list_h:
                continue
            pygame.draw.rect(screen, (40, 40, 40), (layout.list_x, ry, layout.list_w, row_h - 2))
            is_sel = i == self.selected_index
            color = (235, 235, 235) if is_sel else (200, 200, 200)
            name = f'{p.name}'
            surf = self.item_font.render(name, True, color)
            screen.blit(surf, (layout.list_x + 10, ry + 6))
            badge = 'ACTIVE' if p.enabled else 'INACTIVE'
            bcolor = (100, 220, 100) if p.enabled else (160, 160, 160)
            bsurf = self.small_font.render(badge, True, bcolor)
            screen.blit(bsurf, (layout.list_x + layout.list_w - 120, ry + 8))
        sel = self._selected(plugins)
        if sel:
            y = layout.list_y
            btn = pygame.Rect(layout.detail_x, y, 120, 36)
            pygame.draw.rect(screen, (60, 60, 60), btn, border_radius=4)
            btxt = 'Disable' if sel.enabled else 'Enable'
            bsurf = self.small_font.render(btxt, True, (230, 230, 230))
            screen.blit(bsurf, (btn.x + 12, btn.y + 8))
            btn2 = pygame.Rect(layout.detail_x + 130, y, 180, 36)
            pygame.draw.rect(screen, (60, 60, 60), btn2, border_radius=4)
            b2 = self.small_font.render('Open Mods Folder', True, (230, 230, 230))
            screen.blit(b2, (btn2.x + 12, btn2.y + 8))
            btn3 = pygame.Rect(layout.detail_x + 320, y, 160, 36)
            pygame.draw.rect(screen, (60, 60, 60), btn3, border_radius=4)
            b3 = self.small_font.render('Reload Browser', True, (230, 230, 230))
            screen.blit(b3, (btn3.x + 12, btn3.y + 8))
            y += 52
            name_surf = self.item_font.render(f'{sel.name} v{sel.version}', True, (235, 235, 235))
            screen.blit(name_surf, (layout.detail_x, y))
            y += name_surf.get_height() + 6
            auth_surf = self.small_font.render(f'by {sel.author}', True, (180, 180, 180))
            screen.blit(auth_surf, (layout.detail_x, y))
            y += auth_surf.get_height() + 12
            desc = sel.description or 'No description provided.'
            wrap_w = layout.detail_w - 16
            words = desc.split()
            line = ''
            while words:
                while words and self.small_font.size(line + (' ' if line else '') + words[0])[0] <= wrap_w:
                    line = (line + ' ' + words.pop(0)).strip()
                if not line:
                    line = words.pop(0)
                ds = self.small_font.render(line, True, (200, 200, 200))
                screen.blit(ds, (layout.detail_x, y))
                y += ds.get_height() + 4
                line = ''
        width, height = screen.get_size()
        rect = self._compute_back_rect((width, height))
        now = pygame.time.get_ticks() / 1000.0
        self._t += max(0.0, min(0.1, now - self._last_time))
        self._last_time = now
        pulse = 0.925 + 0.075 * math.sin(self._t * self._pulse_speed * math.tau)
        color = (235, 235, 235)
        label_surf = self.item_font.render(self.back_label, True, color)
        screen.blit(label_surf, rect.topleft)
        under_w = int(label_surf.get_width() * (pulse if self._hover_back else 1.0))
        under_h = 3
        ux = rect.x
        uy = rect.y + label_surf.get_height() + 6
        pygame.draw.rect(screen, self.accent, (ux, uy, under_w, under_h))
        self._back_rect = rect

    def draw_gpu(self, renderer, left_margin: int=64) -> None:
        if Texture is None or sdl2rect is None:
            return
        try:
            out_w, out_h = renderer.output_size
        except Exception:
            out_w, out_h = (1200, 800)
        layout = self._compute_layout((out_w, out_h))
        title_surf = self.title_font.render('plugins', True, (230, 230, 230))
        title_tex = Texture.from_surface(renderer, title_surf)
        renderer.copy(title_tex, dstrect=sdl2rect.Rect(layout.left_margin, 36, title_surf.get_width(), title_surf.get_height()))
        renderer.draw_color = (32, 32, 32, 255)
        renderer.fill_rect(sdl2rect.Rect(layout.list_x - 8, layout.list_y - 8, layout.list_w + 16, layout.list_h + 16))
        renderer.draw_color = (30, 30, 30, 255)
        renderer.fill_rect(sdl2rect.Rect(layout.detail_x - 8, layout.list_y - 8, layout.detail_w + 16, layout.list_h + 16))
        plugins = self._plugins()
        row_h = layout.row_h
        y0 = layout.list_y - self.scroll
        for i, p in enumerate(plugins):
            ry = y0 + i * row_h
            if ry + row_h < layout.list_y or ry > layout.list_y + layout.list_h:
                continue
            renderer.draw_color = (40, 40, 40, 255)
            renderer.fill_rect(sdl2rect.Rect(layout.list_x, ry, layout.list_w, row_h - 2))
            is_sel = i == self.selected_index
            color = (235, 235, 235) if is_sel else (200, 200, 200)
            name = f'{p.name}'
            surf = self.item_font.render(name, True, color)
            tex = Texture.from_surface(renderer, surf)
            renderer.copy(tex, dstrect=sdl2rect.Rect(layout.list_x + 10, ry + 6, surf.get_width(), surf.get_height()))
            badge = 'ACTIVE' if p.enabled else 'INACTIVE'
            bcolor = (100, 220, 100) if p.enabled else (160, 160, 160)
            bs = self.small_font.render(badge, True, bcolor)
            btex = Texture.from_surface(renderer, bs)
            renderer.copy(btex, dstrect=sdl2rect.Rect(layout.list_x + layout.list_w - 120, ry + 8, bs.get_width(), bs.get_height()))
        sel = self._selected(plugins)
        if sel:
            y = layout.list_y
            renderer.draw_color = (60, 60, 60, 255)
            renderer.fill_rect(sdl2rect.Rect(layout.detail_x, y, 120, 36))
            bt = self.small_font.render('Disable' if sel.enabled else 'Enable', True, (230, 230, 230))
            bttex = Texture.from_surface(renderer, bt)
            renderer.copy(bttex, dstrect=sdl2rect.Rect(layout.detail_x + 12, y + 8, bt.get_width(), bt.get_height()))
            renderer.draw_color = (60, 60, 60, 255)
            renderer.fill_rect(sdl2rect.Rect(layout.detail_x + 130, y, 180, 36))
            b2 = self.small_font.render('Open Mods Folder', True, (230, 230, 230))
            b2t = Texture.from_surface(renderer, b2)
            renderer.copy(b2t, dstrect=sdl2rect.Rect(layout.detail_x + 142, y + 8, b2.get_width(), b2.get_height()))
            renderer.draw_color = (60, 60, 60, 255)
            renderer.fill_rect(sdl2rect.Rect(layout.detail_x + 320, y, 160, 36))
            b3 = self.small_font.render('Reload Browser', True, (230, 230, 230))
            b3t = Texture.from_surface(renderer, b3)
            renderer.copy(b3t, dstrect=sdl2rect.Rect(layout.detail_x + 332, y + 8, b3.get_width(), b3.get_height()))
            y += 52
            name_surf = self.item_font.render(f'{sel.name} v{sel.version}', True, (235, 235, 235))
            name_tex = Texture.from_surface(renderer, name_surf)
            renderer.copy(name_tex, dstrect=sdl2rect.Rect(layout.detail_x, y, name_surf.get_width(), name_surf.get_height()))
            y += name_surf.get_height() + 6
            auth_surf = self.small_font.render(f'by {sel.author}', True, (180, 180, 180))
            auth_tex = Texture.from_surface(renderer, auth_surf)
            renderer.copy(auth_tex, dstrect=sdl2rect.Rect(layout.detail_x, y, auth_surf.get_width(), auth_surf.get_height()))
            y += auth_surf.get_height() + 12
            desc = sel.description or 'No description provided.'
            wrap_w = layout.detail_w - 16
            words = desc.split()
            line = ''
            while words:
                while words and self.small_font.size(line + (' ' if line else '') + words[0])[0] <= wrap_w:
                    line = (line + ' ' + words.pop(0)).strip()
                if not line:
                    line = words.pop(0)
                ds = self.small_font.render(line, True, (200, 200, 200))
                dtex = Texture.from_surface(renderer, ds)
                renderer.copy(dtex, dstrect=sdl2rect.Rect(layout.detail_x, y, ds.get_width(), ds.get_height()))
                y += ds.get_height() + 4
                line = ''
        label_surf = self.item_font.render(self.back_label, True, (235, 235, 235))
        bx = layout.left_margin
        by = out_h - (label_surf.get_height() + 28)
        tex = Texture.from_surface(renderer, label_surf)
        renderer.copy(tex, dstrect=sdl2rect.Rect(bx, by, label_surf.get_width(), label_surf.get_height()))
        renderer.draw_color = (self.accent[0], self.accent[1], self.accent[2], 255)
        renderer.fill_rect(sdl2rect.Rect(bx, by + label_surf.get_height() + 6, label_surf.get_width(), 3))
