from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import math
import time
import pygame
from src.pluginman.pluginmenu import PluginMenuPanel
try:
    from pygame._sdl2.video import Texture
    from pygame._sdl2 import rect as sdl2rect
except Exception:
    Texture = None
    sdl2rect = None

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

class MainMenu:

    def __init__(self, on_settings_change=None, initial_settings: Optional[dict]=None):
        self._on_settings_change = on_settings_change
        self.options: List[str] = ['Play', 'Options', 'Plugins', 'About', 'Quit to Desktop']
        self.state: str = 'main'
        self.selected: int = 0
        self._last_time = time.time()
        self._t = 0.0
        self._pulse_speed = 1.6
        self._camera = _CameraLike()
        self._min_scale = 0.65
        self._max_scale = 1.25
        self._zoom_speed = -0.02
        self.title_font = pygame.font.Font(None, 56)
        self.item_font = pygame.font.Font(None, 36)
        self.accent = (160, 180, 210)
        self.accent_fill = (55, 70, 95)
        self.accent_outline = (100, 130, 170)
        self._text_cache = {}
        self.about_lines: List[str] = ['Dust Grounds by Impnet Studios', 'barrier', 'Lead Developer: qrunk', 'barrier', 'Secondary Developer 1: SoupUnit', 'barrier', 'Secondary Developer 2: nehiyawe', 'barrier', 'Special Thanks to:', 'People Playground and Studio Minus for the art style inspiration.']
        self.settings_tabs = [
            {
                'name': 'general',
                'items': [
                    {'key': 'renderer', 'label': 'Renderer', 'type': 'choice', 'choices': ['Auto', 'CPU', 'GPU'], 'value': 0},
                    {'key': 'show_grid', 'label': 'Grid Background', 'type': 'toggle', 'value': True},
                    {'key': 'target_fps', 'label': 'Target FPS', 'type': 'choice', 'choices': ['30', '60', '120'], 'value': 1},
                    {'key': 'discord_rpc', 'label': 'Discord Rich Presence', 'type': 'toggle', 'value': True},
                ],
            },
            {'name': 'controls', 'items': [{'key': 'max_particles', 'label': 'Max Particles', 'type': 'choice', 'choices': ['25k', '50k', '100k'], 'value': 1}]},
            {'name': 'user interface', 'items': [{'key': 'invert_zoom', 'label': 'Invert Zoom', 'type': 'toggle', 'value': False}]},
            {'name': 'audio', 'items': [{'key': 'master_volume', 'label': 'Master Volume', 'type': 'slider', 'min': 0, 'max': 100, 'step': 25, 'value': 100}]},
        ]
        self.setting_desc = {
            'renderer': 'Pick the rendering backend. Auto picks GPU when available for best performance.',
            'show_grid': 'Toggle the world-aligned grid in the background.',
            'target_fps': 'Desired frames per second for the simulation and rendering.',
            'max_particles': 'Upper bound for total particle count to cap performance.',
            'invert_zoom': 'Invert the zoom direction when scrolling.',
            'master_volume': 'Overall audio volume for all sounds.',
            'discord_rpc': 'Enable Discord Rich Presence integration (shows your status in Discord).',
        }
        self.options_has_back_tab = True
        self.opt_tab_idx = 0
        self.opt_item_idx = 0
        self.opt_active_pane = 'tabs'
        self._opt_hit = {'tabs': [], 'items': {}}
        self._drag_slider = None
        self._hover_tooltip = None
        self.plugin_panel = PluginMenuPanel()
        self.back_label = 'Back'
        if initial_settings:
            self._apply_initial_settings(initial_settings)

    @property
    def camera(self) -> _CameraLike:
        return self._camera

    def _advance_time(self) -> float:
        now = time.time()
        dt = max(0.0, min(0.1, now - self._last_time))
        self._last_time = now
        self._t += dt
        s = self._camera.scale + self._zoom_speed * dt
        if s < self._min_scale:
            s = self._max_scale
        self._camera.scale = s
        return dt

    def update(self) -> None:
        self._advance_time()

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if self.state == 'options':
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.opt_active_pane = 'items' if self.opt_active_pane == 'tabs' else 'tabs'
                    return None
                if event.key in (pygame.K_BACKSPACE,):
                    self.state = 'main'
                    return None
                if event.key in (pygame.K_UP, pygame.K_w):
                    if self.opt_active_pane == 'tabs':
                        n = len(self.settings_tabs) + (1 if self.options_has_back_tab else 0)
                        self.opt_tab_idx = (self.opt_tab_idx - 1) % max(1, n)
                        if self.options_has_back_tab and self.opt_tab_idx == len(self.settings_tabs):
                            items = []
                        else:
                            items = self.settings_tabs[self.opt_tab_idx]['items']
                        if items:
                            self.opt_item_idx = min(self.opt_item_idx, len(items) - 1)
                        else:
                            self.opt_item_idx = 0
                    else:
                        items = self.settings_tabs[self.opt_tab_idx]['items']
                        if items:
                            self.opt_item_idx = (self.opt_item_idx - 1) % len(items)
                        else:
                            self.opt_item_idx = 0
                    return None
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    if self.opt_active_pane == 'tabs':
                        n = len(self.settings_tabs) + (1 if self.options_has_back_tab else 0)
                        self.opt_tab_idx = (self.opt_tab_idx + 1) % max(1, n)
                        if self.options_has_back_tab and self.opt_tab_idx == len(self.settings_tabs):
                            items = []
                        else:
                            items = self.settings_tabs[self.opt_tab_idx]['items']
                        if items:
                            self.opt_item_idx = min(self.opt_item_idx, len(items) - 1)
                        else:
                            self.opt_item_idx = 0
                    else:
                        items = self.settings_tabs[self.opt_tab_idx]['items']
                        if items:
                            self.opt_item_idx = (self.opt_item_idx + 1) % len(items)
                        else:
                            self.opt_item_idx = 0
                    return None
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    if self.opt_active_pane == 'tabs':
                        n = len(self.settings_tabs) + (1 if self.options_has_back_tab else 0)
                        self.opt_tab_idx = (self.opt_tab_idx - 1) % max(1, n)
                    else:
                        items = self.settings_tabs[self.opt_tab_idx]['items']
                        if items:
                            item = items[self.opt_item_idx]
                            if item.get('type') == 'choice':
                                item['value'] = (item.get('value', 0) - 1) % max(1, len(item.get('choices', [])))
                            elif item.get('type') == 'toggle':
                                item['value'] = not item.get('value', False)
                            elif item.get('type') == 'slider':
                                step = max(1, int(item.get('step', 1)))
                                item['value'] = max(item.get('min', 0), int(item.get('value', 0)) - step)
                    return None
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    if self.opt_active_pane == 'tabs':
                        n = len(self.settings_tabs) + (1 if self.options_has_back_tab else 0)
                        self.opt_tab_idx = (self.opt_tab_idx + 1) % max(1, n)
                    else:
                        items = self.settings_tabs[self.opt_tab_idx]['items']
                        if items:
                            item = items[self.opt_item_idx]
                            if item.get('type') == 'choice':
                                item['value'] = (item.get('value', 0) + 1) % max(1, len(item.get('choices', [])))
                            elif item.get('type') == 'toggle':
                                item['value'] = not item.get('value', False)
                            elif item.get('type') == 'slider':
                                step = max(1, int(item.get('step', 1)))
                                item['value'] = min(item.get('max', 100), int(item.get('value', 0)) + step)
                    return None
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.opt_active_pane == 'items':
                        items = self.settings_tabs[self.opt_tab_idx]['items']
                        if items:
                            item = items[self.opt_item_idx]
                            if item.get('type') == 'toggle':
                                item['value'] = not item.get('value', False)
                            elif item.get('type') == 'choice':
                                item['value'] = (item.get('value', 0) + 1) % max(1, len(item.get('choices', [])))
                            elif item.get('type') == 'slider':
                                step = max(1, int(item.get('step', 1)))
                                item['value'] = min(item.get('max', 100), int(item.get('value', 0)) + step)
                    elif self.options_has_back_tab and self.opt_tab_idx == len(self.settings_tabs):
                        self.state = 'main'
                    else:
                        self.opt_active_pane = 'items'
                    return None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self.state = 'main'
                return None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = pygame.mouse.get_pos()
                for rect, idx in self._opt_hit.get('tabs', []):
                    if rect.collidepoint(mx, my):
                        if self.options_has_back_tab and idx == len(self.settings_tabs):
                            self.state = 'main'
                            return None
                        self.opt_tab_idx = idx
                        items = self.settings_tabs[self.opt_tab_idx]['items']
                        self.opt_item_idx = min(self.opt_item_idx, max(0, len(items) - 1))
                        return None
                hit = self._opt_hit.get('items', {}).get((self.opt_tab_idx, self.opt_item_idx))
                for (tab_i, item_i), info in self._opt_hit.get('items', {}).items():
                    if tab_i != self.opt_tab_idx:
                        continue
                    tr = info.get('toggle_rect')
                    if tr and tr.collidepoint(mx, my):
                        it = self.settings_tabs[tab_i]['items'][item_i]
                        if it.get('type') == 'toggle':
                            it['value'] = not it.get('value', False)
                            self.opt_item_idx = item_i
                            self._notify_settings_changed()
                            return None
                    for j, rr in enumerate(info.get('choice_rects', [])):
                        if rr.collidepoint(mx, my):
                            it = self.settings_tabs[tab_i]['items'][item_i]
                            if it.get('type') == 'choice':
                                it['value'] = j
                                self.opt_item_idx = item_i
                                self._notify_settings_changed()
                                return None
                    trk = info.get('slider_track')
                    if trk and trk.collidepoint(mx, my):
                        it = self.settings_tabs[tab_i]['items'][item_i]
                        if it.get('type') == 'slider':
                            self.opt_item_idx = item_i
                            self._drag_slider = {'tab': tab_i, 'item': item_i, 'track': trk.copy(), 'min': int(it.get('min', 0)), 'max': int(it.get('max', 100)), 'step': int(it.get('step', 1))}
                            self._update_slider_from_mouse(mx)
                            self._notify_settings_changed()
                            return None
                return None
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._drag_slider = None
                return None
            elif event.type == pygame.MOUSEMOTION:
                mx, my = pygame.mouse.get_pos()
                tip = None
                for (tab_i, item_i), info in self._opt_hit.get('items', {}).items():
                    if tab_i != self.opt_tab_idx:
                        continue
                    lr = info.get('label_rect')
                    if lr and lr.collidepoint(mx, my):
                        key = info.get('key')
                        tip = self.setting_desc.get(key, None)
                        break
                self._hover_tooltip = tip
                if self._drag_slider:
                    self._update_slider_from_mouse(mx)
                    self._notify_settings_changed()
                return None
            elif event.type == pygame.MOUSEWHEEL:
                if getattr(event, 'y', 0) > 0:
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
                elif getattr(event, 'y', 0) < 0:
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
                return None
            return None
        if self.state == 'plugins':
            res = self.plugin_panel.handle_event(event)
            if res == 'back':
                self.state = 'main'
            return None
        if self.state == 'about':
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE):
                    self.state = 'main'
                    return None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                self.state = 'main'
                return None
            elif event.type == pygame.MOUSEWHEEL:
                return None
            return None
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                current = self.options[self.selected]
                lc = current.lower()
                if lc.startswith('about'):
                    self.state = 'about'
                    return None
                if lc.startswith('options'):
                    self.state = 'options'
                    return None
                if lc.startswith('plugins'):
                    self.state = 'plugins'
                    return None
                return self._activate()
        elif event.type == pygame.MOUSEWHEEL:
            if getattr(event, 'y', 0) > 0:
                self.selected = (self.selected - 1) % len(self.options)
            elif getattr(event, 'y', 0) < 0:
                self.selected = (self.selected + 1) % len(self.options)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            current = self.options[self.selected]
            lc = current.lower()
            if lc.startswith('about'):
                self.state = 'about'
                return None
            if lc.startswith('options'):
                self.state = 'options'
                return None
            if lc.startswith('plugins'):
                self.state = 'plugins'
                return None
            return self._activate()
        return None

    def _apply_initial_settings(self, cfg: dict):
        for ti, tab in enumerate(self.settings_tabs):
            for ii, item in enumerate(tab.get('items', [])):
                k = item.get('key')
                if k not in cfg:
                    continue
                if item.get('type') == 'toggle':
                    item['value'] = bool(cfg[k])
                elif item.get('type') == 'choice':
                    choices = item.get('choices', [])
                    val = cfg[k]
                    try:
                        if isinstance(val, int):
                            val = str(val)
                    except Exception:
                        pass
                    if val in choices:
                        item['value'] = choices.index(val)
                    elif k == 'max_particles':
                        label = f'{int(val) // 1000}k'
                        if label in choices:
                            item['value'] = choices.index(label)
                elif item.get('type') == 'slider':
                    item['value'] = int(cfg[k])

    def _settings_dict(self) -> dict:
        out = {}
        for tab in self.settings_tabs:
            for item in tab.get('items', []):
                k = item.get('key')
                t = item.get('type')
                if t == 'toggle':
                    out[k] = bool(item.get('value', False))
                elif t == 'choice':
                    idx = int(item.get('value', 0))
                    choices = item.get('choices', [])
                    val = choices[idx] if 0 <= idx < len(choices) else None
                    if k == 'target_fps' and isinstance(val, str) and val.isdigit():
                        out[k] = int(val)
                    elif k == 'max_particles' and isinstance(val, str) and val.endswith('k'):
                        try:
                            out[k] = int(val[:-1]) * 1000
                        except Exception:
                            out[k] = 50000
                    else:
                        out[k] = val
                elif t == 'slider':
                    out[k] = int(item.get('value', 0))
        return out

    def _notify_settings_changed(self):
        if callable(self._on_settings_change):
            try:
                self._on_settings_change(self._settings_dict())
            except Exception:
                pass

    def _update_slider_from_mouse(self, mx: int):
        if not self._drag_slider:
            return
        tab_i = self._drag_slider['tab']
        item_i = self._drag_slider['item']
        trk = self._drag_slider['track']
        vmin = int(self._drag_slider.get('min', 0))
        vmax = int(self._drag_slider.get('max', 100))
        step = max(1, int(self._drag_slider.get('step', 1)))
        t = 0.0 if trk.w <= 0 else (mx - trk.x) / trk.w
        t = max(0.0, min(1.0, t))
        raw = vmin + t * (vmax - vmin)
        v = int(round(raw / step) * step)
        v = max(vmin, min(vmax, v))
        try:
            self.settings_tabs[tab_i]['items'][item_i]['value'] = v
        except Exception:
            pass

    def _activate(self) -> str:
        text = self.options[self.selected]
        if text.lower().startswith('play'):
            return 'play'
        if text.lower().startswith('options'):
            return 'options'
        if text.lower().startswith('plugins'):
            return 'plugins'
        if text.lower().startswith('about'):
            return 'about'
        if text.lower().startswith('quit'):
            return 'quit'
        return ''

    def _pulse(self) -> float:
        return 0.925 + 0.075 * math.sin(self._t * self._pulse_speed * math.tau)

    def draw_cpu(self, screen: pygame.Surface, left_margin: int=64) -> None:
        width, height = screen.get_size()
        center_y = height // 2
        if self.state == 'plugins':
            self.plugin_panel.draw_cpu(screen)
            return
        if self.state == 'about':
            spacing = self.item_font.get_height() + 10
            lines = self.about_lines
            lines_count = len(lines)
            items_h = lines_count * spacing + 40
            y = center_y - items_h // 2
            for i, text in enumerate(lines):
                if text == 'barrier':
                    y += spacing
                    continue
                if i == 0:
                    surf = self.title_font.render(text, True, (230, 230, 230))
                else:
                    surf = self.item_font.render(text, True, (210, 210, 210))
                screen.blit(surf, (left_margin, y))
                y += spacing
            pulse = self._pulse()
            back_surf = self.item_font.render(self.back_label, True, (235, 235, 235))
            bx = left_margin
            by = y + 10
            screen.blit(back_surf, (bx, by))
            under_w = int(back_surf.get_width() * pulse)
            under_h = 3
            ux = bx
            uy = by + back_surf.get_height() + 6
            pygame.draw.rect(screen, (200, 200, 200), (ux, uy, under_w, under_h))
            return
        if self.state == 'options':
            title_surf = self.title_font.render('settings', True, (230, 230, 230))
            screen.blit(title_surf, (left_margin, 36))
            spacing = self.item_font.get_height() + 12
            tabs_w = 180
            desc_w = 380
            gap = 28
            tabs_x = left_margin
            items_x = left_margin + tabs_w + gap
            desc_x = width - desc_w - left_margin
            pygame.draw.rect(screen, (32, 32, 32), (tabs_x - 8, 100, tabs_w + 16, height - 160), border_radius=6)
            ty = 120
            total_tabs = len(self.settings_tabs) + (1 if self.options_has_back_tab else 0)
            self._opt_hit['tabs'] = []
            for idx in range(total_tabs):
                is_back = self.options_has_back_tab and idx == len(self.settings_tabs)
                name = ('back' if is_back else self.settings_tabs[idx]['name']).lower()
                is_sel = self.opt_active_pane == 'tabs' and idx == self.opt_tab_idx
                row_rect = pygame.Rect(tabs_x, ty - 6, tabs_w, spacing)
                if idx == self.opt_tab_idx:
                    pygame.draw.rect(screen, (40, 40, 40), row_rect, border_radius=4)
                color = self.accent if is_sel else (220, 220, 220) if idx == self.opt_tab_idx else (180, 180, 180)
                surf = self.item_font.render(name, True, color)
                screen.blit(surf, (tabs_x + 10, ty))
                self._opt_hit['tabs'].append((row_rect.copy(), idx))
                ty += spacing
            pygame.draw.rect(screen, (30, 30, 30), (items_x - 8, 100, max(0, desc_x - items_x) - 20, height - 160), border_radius=6)
            if self.options_has_back_tab and self.opt_tab_idx == len(self.settings_tabs):
                self._opt_hit['items'] = {}
            else:
                items = self.settings_tabs[self.opt_tab_idx]['items']
                iy = 120
                row_h = spacing + 8
                self._opt_hit['items'] = {}
                for i, item in enumerate(items):
                    sel_item = self.opt_active_pane == 'items' and i == self.opt_item_idx
                    row_rect = pygame.Rect(items_x, iy - 6, desc_x - items_x - 24, row_h)
                    pygame.draw.rect(screen, (36, 36, 36), row_rect, border_radius=4)
                    label = item.get('label', item.get('key', ''))
                    lab_col = (230, 230, 230)
                    lab_surf = self.item_font.render(label, True, lab_col)
                    screen.blit(lab_surf, (items_x + 12, iy))
                    label_rect = pygame.Rect(items_x + 12, iy, lab_surf.get_width(), lab_surf.get_height())
                    ctrl_x = items_x + 360
                    hit_info = {'key': item.get('key'), 'label_rect': label_rect}
                    if item.get('type') == 'toggle':
                        enabled = bool(item.get('value', False))
                        pill_w, pill_h = (120, lab_surf.get_height() + 4)
                        pill_rect = pygame.Rect(ctrl_x, iy - 2, pill_w, pill_h)
                        pygame.draw.rect(screen, (25, 25, 25), pill_rect, border_radius=12)
                        txt = 'Enabled' if enabled else 'Disabled'
                        col = self.accent if enabled else (170, 170, 170)
                        val_surf = self.item_font.render(txt, True, col)
                        screen.blit(val_surf, (pill_rect.x + (pill_w - val_surf.get_width()) // 2, pill_rect.y + 2))
                        hit_info['toggle_rect'] = pill_rect.copy()
                    elif item.get('type') == 'choice':
                        choices = item.get('choices', [])
                        ci = int(item.get('value', 0)) % max(1, len(choices))
                        bx = ctrl_x
                        choice_rects = []
                        for j, ch in enumerate(choices):
                            w = max(84, self.item_font.size(ch)[0] + 18)
                            rect = pygame.Rect(bx, iy - 2, w, lab_surf.get_height() + 4)
                            pygame.draw.rect(screen, (22, 22, 22), rect, border_radius=8)
                            if j == ci:
                                pygame.draw.rect(screen, self.accent_fill, rect, border_radius=8)
                            ch_surf = self.item_font.render(ch, True, (220, 220, 220) if j == ci else (170, 170, 170))
                            screen.blit(ch_surf, (rect.x + (w - ch_surf.get_width()) // 2, rect.y + 2))
                            bx += w + 8
                            choice_rects.append(rect.copy())
                        hit_info['choice_rects'] = choice_rects
                    elif item.get('type') == 'slider':
                        vmin = int(item.get('min', 0))
                        vmax = int(item.get('max', 100))
                        v = int(item.get('value', vmin))
                        tr_w = 340
                        tr_rect = pygame.Rect(ctrl_x, iy + lab_surf.get_height() // 2, tr_w, 8)
                        pygame.draw.rect(screen, (20, 20, 20), tr_rect, border_radius=4)
                        pygame.draw.rect(screen, (80, 80, 80), tr_rect.inflate(-2, -2), border_radius=4)
                        t = 0 if vmax == vmin else (v - vmin) / (vmax - vmin)
                        hx = tr_rect.x + int(t * tr_rect.w)
                        h_rect = pygame.Rect(hx - 6, tr_rect.y - 6, 12, 20)
                        pygame.draw.rect(screen, (230, 230, 230), h_rect, border_radius=3)
                        val_surf = self.item_font.render(str(v), True, (200, 200, 200))
                        screen.blit(val_surf, (h_rect.centerx - val_surf.get_width() // 2, h_rect.bottom + 2))
                        hit_info['slider_track'] = tr_rect.copy()
                    if sel_item:
                        pygame.draw.rect(screen, self.accent_outline, row_rect, width=2, border_radius=4)
                    self._opt_hit['items'][self.opt_tab_idx, i] = hit_info
                    iy += row_h
            if self._hover_tooltip:
                mx, my = pygame.mouse.get_pos()
                tip = self._hover_tooltip
                words = tip.split()
                wrap_w = 360
                lines = []
                line = ''
                for w in words:
                    test = f'{line} {w}'.strip()
                    if self.item_font.size(test)[0] > wrap_w:
                        lines.append(line)
                        line = w
                    else:
                        line = test
                if line:
                    lines.append(line)
                pad = 8
                tw = max((self.item_font.size(l)[0] for l in lines)) if lines else 0
                th = len(lines) * (self.item_font.get_height() + 4)
                bx, by = (mx + 16, my + 16)
                bg = pygame.Surface((tw + pad * 2, th + pad * 2), pygame.SRCALPHA)
                bg.fill((10, 10, 10, 220))
                pygame.draw.rect(bg, (60, 60, 60, 255), pygame.Rect(0, 0, bg.get_width(), bg.get_height()), width=1)
                screen.blit(bg, (bx, by))
                yy = by + pad
                for l in lines:
                    s = self.item_font.render(l, True, (220, 220, 220))
                    screen.blit(s, (bx + pad, yy))
                    yy += self.item_font.get_height() + 4
            return
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
                pygame.draw.rect(screen, (200, 200, 200), (ux, uy, under_w, under_h))

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
        if self.state == 'plugins':
            self.plugin_panel.draw_gpu(renderer)
            return
        if self.state in ('about',):
            if Texture is None or sdl2rect is None:
                return
            spacing = self.item_font.get_height() + 10
            try:
                vp = renderer.output_size
                height = vp[1]
            except Exception:
                height = 800
            lines = self.about_lines if self.state == 'about' else self.plugins_lines
            items_h = len(lines) * spacing + 40
            y = height // 2 - items_h // 2
            for i, text in enumerate(lines):
                if text == 'barrier':
                    y += spacing
                    continue
                if i == 0:
                    surf = self.title_font.render(text, True, (230, 230, 230))
                else:
                    surf = self.item_font.render(text, True, (210, 210, 210))
                tex = Texture.from_surface(renderer, surf)
                renderer.copy(tex, dstrect=sdl2rect.Rect(left_margin, y, surf.get_width(), surf.get_height()))
                y += spacing
            pulse = self._pulse()
            back_surf = self.item_font.render(self.back_label, True, (235, 235, 235))
            back_tex = Texture.from_surface(renderer, back_surf)
            bx = left_margin
            by = y + 10
            renderer.copy(back_tex, dstrect=sdl2rect.Rect(bx, by, back_surf.get_width(), back_surf.get_height()))
            under_w = int(back_surf.get_width() * pulse)
            under_h = 3
            ux = bx
            uy = by + back_surf.get_height() + 6
            renderer.draw_color = (200, 200, 200, 255)
            renderer.fill_rect(sdl2rect.Rect(ux, uy, under_w, under_h))
            return
        if self.state == 'options':
            if Texture is None or sdl2rect is None:
                return
            title_surf = self.title_font.render('settings', True, (230, 230, 230))
            title_tex = Texture.from_surface(renderer, title_surf)
            renderer.copy(title_tex, dstrect=sdl2rect.Rect(left_margin, 36, title_surf.get_width(), title_surf.get_height()))
            spacing = self.item_font.get_height() + 12
            try:
                vp = renderer.output_size
                out_h = vp[1]
                out_w = vp[0]
            except Exception:
                out_w, out_h = (1200, 800)
            tabs_w = 180
            desc_w = 380
            gap = 28
            tabs_x = left_margin
            items_x = left_margin + tabs_w + gap
            desc_x = out_w - desc_w - left_margin
            renderer.draw_color = (32, 32, 32, 255)
            renderer.fill_rect(sdl2rect.Rect(tabs_x - 8, 100, tabs_w + 16, out_h - 160))
            ty = 120
            total_tabs = len(self.settings_tabs) + (1 if self.options_has_back_tab else 0)
            self._opt_hit['tabs'] = []
            for idx in range(total_tabs):
                is_back = self.options_has_back_tab and idx == len(self.settings_tabs)
                name = ('back' if is_back else self.settings_tabs[idx]['name']).lower()
                is_sel = self.opt_active_pane == 'tabs' and idx == self.opt_tab_idx
                row_rect = sdl2rect.Rect(tabs_x, ty - 6, tabs_w, spacing)
                if idx == self.opt_tab_idx:
                    renderer.draw_color = (40, 40, 40, 255)
                    renderer.fill_rect(row_rect)
                color = self.accent if is_sel else (220, 220, 220) if idx == self.opt_tab_idx else (180, 180, 180)
                surf = self.item_font.render(name, True, color)
                tex = Texture.from_surface(renderer, surf)
                renderer.copy(tex, dstrect=sdl2rect.Rect(tabs_x + 10, ty, surf.get_width(), surf.get_height()))
                self._opt_hit['tabs'].append((pygame.Rect(tabs_x, ty - 6, tabs_w, spacing), idx))
                ty += spacing
            renderer.draw_color = (30, 30, 30, 255)
            renderer.fill_rect(sdl2rect.Rect(items_x - 8, 100, max(0, desc_x - items_x) - 20, out_h - 160))
            if not (self.options_has_back_tab and self.opt_tab_idx == len(self.settings_tabs)):
                items = self.settings_tabs[self.opt_tab_idx]['items']
                iy = 120
                row_h = spacing + 8
                self._opt_hit['items'] = {}
                for i, item in enumerate(items):
                    sel_item = self.opt_active_pane == 'items' and i == self.opt_item_idx
                    row_rect = sdl2rect.Rect(items_x, iy - 6, desc_x - items_x - 24, row_h)
                    renderer.draw_color = (36, 36, 36, 255)
                    renderer.fill_rect(row_rect)
                    label = item.get('label', item.get('key', ''))
                    lab_surf = self.item_font.render(label, True, (230, 230, 230))
                    lab_tex = Texture.from_surface(renderer, lab_surf)
                    renderer.copy(lab_tex, dstrect=sdl2rect.Rect(items_x + 12, iy, lab_surf.get_width(), lab_surf.get_height()))
                    hit_info = {'key': item.get('key'), 'label_rect': pygame.Rect(items_x + 12, iy, lab_surf.get_width(), lab_surf.get_height())}
                    ctrl_x = items_x + 360
                    if item.get('type') == 'toggle':
                        enabled = bool(item.get('value', False))
                        pill_w = 120
                        pill_h = lab_surf.get_height() + 4
                        renderer.draw_color = (25, 25, 25, 255)
                        renderer.fill_rect(sdl2rect.Rect(ctrl_x, iy - 2, pill_w, pill_h))
                        txt = 'Enabled' if enabled else 'Disabled'
                        col = self.accent if enabled else (170, 170, 170)
                        v_surf = self.item_font.render(txt, True, col)
                        v_tex = Texture.from_surface(renderer, v_surf)
                        renderer.copy(v_tex, dstrect=sdl2rect.Rect(ctrl_x + (pill_w - v_surf.get_width()) // 2, iy - 2 + 2, v_surf.get_width(), v_surf.get_height()))
                        hit_info['toggle_rect'] = pygame.Rect(ctrl_x, iy - 2, pill_w, pill_h)
                    elif item.get('type') == 'choice':
                        choices = item.get('choices', [])
                        ci = int(item.get('value', 0)) % max(1, len(choices))
                        bx = ctrl_x
                        choice_rects = []
                        for j, ch in enumerate(choices):
                            w = max(84, self.item_font.size(ch)[0] + 18)
                            rect = sdl2rect.Rect(bx, iy - 2, w, lab_surf.get_height() + 4)
                            renderer.draw_color = (22, 22, 22, 255)
                            renderer.fill_rect(rect)
                            if j == ci:
                                renderer.draw_color = (self.accent_fill[0], self.accent_fill[1], self.accent_fill[2], 255)
                                renderer.fill_rect(rect)
                            ch_surf = self.item_font.render(ch, True, (220, 220, 220) if j == ci else (170, 170, 170))
                            ch_tex = Texture.from_surface(renderer, ch_surf)
                            renderer.copy(ch_tex, dstrect=sdl2rect.Rect(rect.x + (w - ch_surf.get_width()) // 2, rect.y + 2, ch_surf.get_width(), ch_surf.get_height()))
                            bx += w + 8
                            choice_rects.append(pygame.Rect(rect.x, rect.y, rect.w, rect.h))
                        hit_info['choice_rects'] = choice_rects
                    elif item.get('type') == 'slider':
                        vmin = int(item.get('min', 0))
                        vmax = int(item.get('max', 100))
                        v = int(item.get('value', vmin))
                        tr_w = 340
                        tr_rect = sdl2rect.Rect(ctrl_x, iy + lab_surf.get_height() // 2, tr_w, 8)
                        renderer.draw_color = (20, 20, 20, 255)
                        renderer.fill_rect(tr_rect)
                        inner = sdl2rect.Rect(tr_rect.x + 1, tr_rect.y + 1, tr_rect.w - 2, tr_rect.h - 2)
                        renderer.draw_color = (80, 80, 80, 255)
                        renderer.fill_rect(inner)
                        t = 0 if vmax == vmin else (v - vmin) / (vmax - vmin)
                        hx = tr_rect.x + int(t * tr_rect.w)
                        h_rect = sdl2rect.Rect(hx - 6, tr_rect.y - 6, 12, 20)
                        renderer.draw_color = (230, 230, 230, 255)
                        renderer.fill_rect(h_rect)
                        v_surf = self.item_font.render(str(v), True, (200, 200, 200))
                        v_tex = Texture.from_surface(renderer, v_surf)
                        renderer.copy(v_tex, dstrect=sdl2rect.Rect(h_rect.x + (h_rect.w - v_surf.get_width()) // 2, h_rect.y + h_rect.h + 2, v_surf.get_width(), v_surf.get_height()))
                        hit_info['slider_track'] = pygame.Rect(tr_rect.x, tr_rect.y, tr_rect.w, tr_rect.h)
                    if sel_item:
                        renderer.draw_color = (self.accent_outline[0], self.accent_outline[1], self.accent_outline[2], 255)
                        renderer.draw_rect(row_rect)
                    self._opt_hit['items'][self.opt_tab_idx, i] = hit_info
                    iy += row_h
            if self._hover_tooltip:
                try:
                    mx, my = pygame.mouse.get_pos()
                    tip = self._hover_tooltip
                    words = tip.split()
                    wrap_w = 360
                    lines = []
                    line = ''
                    for w in words:
                        test = f'{line} {w}'.strip()
                        if self.item_font.size(test)[0] > wrap_w:
                            lines.append(line)
                            line = w
                        else:
                            line = test
                    if line:
                        lines.append(line)
                    pad = 8
                    tw = max((self.item_font.size(l)[0] for l in lines)) if lines else 0
                    th = len(lines) * (self.item_font.get_height() + 4)
                    bx, by = (mx + 16, my + 16)
                    renderer.draw_color = (10, 10, 10, 220)
                    renderer.fill_rect(sdl2rect.Rect(bx, by, tw + pad * 2, th + pad * 2))
                    renderer.draw_color = (60, 60, 60, 255)
                    renderer.draw_rect(sdl2rect.Rect(bx, by, tw + pad * 2, th + pad * 2))
                    yy = by + pad
                    for l in lines:
                        s = self.item_font.render(l, True, (220, 220, 220))
                        t = Texture.from_surface(renderer, s)
                        renderer.copy(t, dstrect=sdl2rect.Rect(bx + pad, yy, s.get_width(), s.get_height()))
                        yy += self.item_font.get_height() + 4
                except Exception:
                    pass
            return
        title = 'Dustground'
        title_surf = self.title_font.render(title, True, (220, 220, 220))
        if Texture is not None and sdl2rect is not None:
            title_tex = Texture.from_surface(renderer, title_surf)
            renderer.copy(title_tex, dstrect=sdl2rect.Rect(left_margin, 40, title_surf.get_width(), title_surf.get_height()))
        spacing = self.item_font.get_height() + 12
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
            if Texture is not None and sdl2rect is not None:
                tex, surf = self._get_text_tex(renderer, text, color)
                x = left_margin
                y = start_y + idx * spacing
                renderer.copy(tex, dstrect=sdl2rect.Rect(x, y, surf.get_width(), surf.get_height()))
                if is_sel:
                    under_w = int(surf.get_width() * pulse)
                    under_h = 3
                    ux = x
                    uy = y + surf.get_height() + 6
                    renderer.draw_color = (200, 200, 200, 255)
                    renderer.fill_rect(sdl2rect.Rect(ux, uy, under_w, under_h))
