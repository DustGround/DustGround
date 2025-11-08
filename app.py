import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import sys
import threading
import time
from pathlib import Path
from typing import Tuple, Dict, List, Tuple as Tup
from src.sand import SandSystem, SandParticle
from src.water import WaterSystem, WaterParticle
from src.lava import LavaSystem, LavaParticle
from src.bluelava import BlueLavaSystem, BlueLavaParticle
from src.toxic import ToxicSystem
from src.oil import OilSystem
from src.metal import MetalSystem
from src.ruby import RubySystem
from src.milk import MilkSystem
from src.dirt import DirtSystem
from src.blocks import BlocksSystem
from src.blood import BloodSystem
from src.npc import NPC
from src.opt import get_or_create_optimizations
from src.scaling import recommend_settings
from src.zoom import Camera
from src.admin import clear_everything, clear_living, clear_blocks
from src.bg import GridBackground
from src.menu import MainMenu
from src.pause import PauseMenu
from src.settings import load_settings, save_settings
from src.pluginman.pluginmain import start_plugin_service, get_service
from src.pluginman import pluginload
from src import discord as dg_discord
from src import sound as sfx
GPU_AVAILABLE = False
try:
    from pygame._sdl2.video import Window, Renderer, Texture
    from pygame._sdl2 import rect as sdl2rect
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

class ParticleGame:

    def __init__(self, width: int=1200, height: int=800):
        pygame.init()
        self.width = width
        self.height = height
        self.sidebar_width = 0
        self.game_width = width
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE | pygame.DOUBLEBUF)
        pygame.display.set_caption('Dustground')
        self.ready = False
        self._bench_done = False
        self._bench_cfg = None
        self.use_gpu = False
        self.target_fps = 60
        self.max_particles = 50000

        def _bench_job():
            cfg = get_or_create_optimizations((self.game_width, self.height))
            self._bench_cfg = cfg
            self._bench_done = True
        threading.Thread(target=_bench_job, daemon=True).start()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 14)
        self.button_font = pygame.font.Font(None, 12)
        self.sand_system = SandSystem(self.game_width, height)
        self.water_system = WaterSystem(self.game_width, height)
        self.lava_system = LavaSystem(self.game_width, height)
        self.blue_lava_system = BlueLavaSystem(self.game_width, height)
        self.toxic_system = ToxicSystem(self.game_width, height)
        self.oil_system = OilSystem(self.game_width, height)
        self.metal_system = MetalSystem(self.game_width, height)
        self.ruby_system = RubySystem(self.game_width, height)
        self.milk_system = MilkSystem(self.game_width, height)
        self.dirt_system = DirtSystem(self.game_width, height)
        self.blood_system = BloodSystem(self.game_width, height)
        self.blocks_system = BlocksSystem(self.game_width, height)

        def _is_solid_obstacle(x: int, y: int) -> bool:
            return self.metal_system.is_solid(x, y) or self.blocks_system.is_solid(x, y)
        self._is_solid_obstacle = _is_solid_obstacle
        self.sand_system.set_obstacle_query(self._is_solid_obstacle)
        self.dirt_system.set_obstacle_query(self._is_solid_obstacle)
        self.water_system.set_obstacle_query(self._is_solid_obstacle)
        self.lava_system.set_obstacle_query(self._is_solid_obstacle)
        self.blue_lava_system.set_obstacle_query(self._is_solid_obstacle)
        self.toxic_system.set_obstacle_query(self._is_solid_obstacle)
        self.oil_system.set_obstacle_query(self._is_solid_obstacle)
        self.blood_system.set_obstacle_query(self._is_solid_obstacle)
        if hasattr(self, 'milk_system'):
            self.milk_system.set_obstacle_query(self._is_solid_obstacle)
        if hasattr(self, 'ruby_system'):
            self.ruby_system.set_obstacle_query(self._is_solid_obstacle)
        self.blocks_system.set_external_obstacle(self.metal_system.is_solid)
        self.camera = Camera(world_w=self.game_width, world_h=self.height, view_w=self.game_width, view_h=self.height)
        self.grid_bg = GridBackground()
        self.show_main_menu = True
        self.show_pause_menu = False
        self.user_settings = load_settings()
        self.show_grid = bool(self.user_settings.get('show_grid', True))
        self.invert_zoom = bool(self.user_settings.get('invert_zoom', False))
        self._apply_user_settings(self.user_settings)
        self.menu = MainMenu(on_settings_change=self._on_menu_settings_change, initial_settings=self.user_settings)
        self.pause_menu = PauseMenu()
        try:
            start_plugin_service(Path.cwd())
        except Exception:
            pass
        try:
            dg_discord.init()
        except Exception:
            pass
        self.current_tool = 'sand'
        self.brush_size = 5
        self.is_drawing = False
        self.buttons = {}
        self.ui_show_spawn = False
        self.ui_show_admin = False
        self.ui_icon_size = 56
        self.ui_menu_size = (460, 340)
        self.ui_admin_menu_size = (300, 220)
        self.ui_header_h = 36
        self.ui_grid_cols = 4
        self.ui_flask_surf = self._load_image('src/assets/flask.png')
        if not self.ui_flask_surf:
            self.ui_flask_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.ui_flask_surf.fill((220, 220, 220, 255))
        self.ui_water_surf = self._load_image('src/assets/water.png')
        if not self.ui_water_surf:
            self.ui_water_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_water_surf.fill((80, 140, 255, 255))
        self.ui_sand_surf = self._load_image('src/assets/Sand.png')
        if not self.ui_sand_surf:
            self.ui_sand_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_sand_surf.fill((200, 180, 120, 255))
        self.ui_lava_surf = self._load_image('src/assets/Lava.png')
        if not self.ui_lava_surf:
            self.ui_lava_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_lava_surf.fill((255, 120, 60, 255))
        self.ui_npc_surf = self._load_image('src/assets/npc.png')
        if not self.ui_npc_surf:
            self.ui_npc_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_npc_surf.fill((180, 180, 200, 255))
        self.ui_toxic_surf = self._load_image('src/assets/ToxicWaste.png')
        if not self.ui_toxic_surf:
            self.ui_toxic_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_toxic_surf.fill((90, 220, 90, 255))
        self.ui_oil_surf = self._load_image('src/assets/oil.png')
        if not self.ui_oil_surf:
            self.ui_oil_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_oil_surf.fill((60, 50, 30, 255))
        self.ui_metal_surf = self._load_image('src/assets/metal.png')
        if not self.ui_metal_surf:
            self.ui_metal_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_metal_surf.fill((140, 140, 150, 255))
        self.ui_dirt_surf = self._load_image('src/assets/dirt.png')
        if not self.ui_dirt_surf:
            self.ui_dirt_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_dirt_surf.fill((130, 100, 70, 255))
        self.ui_milk_surf = self._load_image('src/assets/milk.png')
        if not self.ui_milk_surf:
            self.ui_milk_surf = pygame.Surface((64,64), pygame.SRCALPHA)
            self.ui_milk_surf.fill((240,240,245,255))
        self.ui_blocks_surf = self._load_image('src/assets/blocks.png')
        if not self.ui_blocks_surf:
            self.ui_blocks_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_blocks_surf.fill((180, 180, 190, 255))
        self._ui_flask_tex = None
        self._ui_water_tex = None
        self._ui_sand_tex = None
        self._ui_lava_tex = None
        self._ui_blue_lava_tex = None
        self._ui_npc_tex = None
        self._ui_toxic_tex = None
        self._ui_oil_tex = None
        self._ui_metal_tex = None
        self._ui_dirt_tex = None
        self._ui_blocks_tex = None
    # Removed AIR overlay support: no air texture caching
        self._ui_admin_tex = None
        self.ui_tiles = [
            {'key': 'blocks', 'label': 'BLOCKS', 'color': (180, 180, 190), 'surf': self.ui_blocks_surf},
            {'key': 'sand', 'label': 'SAND', 'color': (200, 180, 120), 'surf': self.ui_sand_surf},
            {'key': 'dirt', 'label': 'DIRT', 'color': (130, 100, 70), 'surf': self.ui_dirt_surf},
            {'key': 'water', 'label': 'WATER', 'color': (80, 140, 255), 'surf': self.ui_water_surf},
            {'key': 'oil', 'label': 'OIL', 'color': (60, 50, 30), 'surf': self.ui_oil_surf},
            {'key': 'lava', 'label': 'LAVA', 'color': (255, 120, 60), 'surf': self.ui_lava_surf},
            {'key': 'bluelava', 'label': 'BLUE LAVA', 'color': (70, 170, 255), 'surf': self._load_image('src/assets/bluelava.png') or self.ui_lava_surf},
            {'key': 'metal', 'label': 'METAL', 'color': (140, 140, 150), 'surf': self.ui_metal_surf},
            {'key': 'ruby', 'label': 'RUBY', 'color': (180, 20, 30), 'surf': self._load_image('src/assets/ruby.png') or self.ui_metal_surf},
            {'key': 'toxic', 'label': 'TOXIC', 'color': (90, 220, 90), 'surf': self.ui_toxic_surf},
            {'key': 'milk', 'label': 'MILK', 'color': (240, 240, 245), 'surf': self.ui_milk_surf},
            {'key': 'blood', 'label': 'BLOOD', 'color': (170, 20, 30), 'surf': self._load_image('src/assets/blood.png') or self.ui_oil_surf},
            {'key': 'npc', 'label': 'NPC', 'color': (180, 180, 200), 'surf': self.ui_npc_surf}
        ]
        # AIR tile removed entirely
        self.ui_tile_rects = {}
        self.ui_spawn_search_text = ''
        self.ui_search_active = False
        self._layout_overlay_ui()
        # Ensure plugins are loaded early so their tools show up in the spawn UI
        try:
            pluginload.load_enabled_plugins(self)
        except Exception:
            pass
        self.fps = 0
        self._stats_cache_tex = None
        self._stats_cache_surf = None
        self._stats_updated_at = 0.0
        self._game_surface = None
        self._frame_index = 0
        self._fps_avg = 0.0
        self._last_scale_apply = 0
        self._prev_mouse = None
        self.npcs = []
        self.active_npc = None
        self.npc_drag_index = None
        self._pan_active = False
        self._pan_prev = None
        self.blocks_drag_active = False
        self.blocks_drag_start = None
        self.blocks_drag_current = None

    def _get_text_texture(self, text: str, color: Tup[int, int, int]) -> 'Texture':
        key = (text, color)
        if key in getattr(self, '_text_cache', {}):
            return self._text_cache[key]
        surf = self.button_font.render(text, True, color)
        tex = Texture.from_surface(self.renderer, surf)
        self._text_cache[key] = tex
        return tex

    def _on_menu_settings_change(self, new_settings: Dict):
        self.user_settings.update(new_settings or {})
        save_settings(self.user_settings)
        self._apply_user_settings(self.user_settings)

    def _apply_user_settings(self, s: Dict):
        tfps = int(s.get('target_fps', self.target_fps))
        if tfps > 0:
            self.target_fps = tfps
        self.max_particles = int(s.get('max_particles', self.max_particles))
        self.show_grid = bool(s.get('show_grid', True))
        self.invert_zoom = bool(s.get('invert_zoom', False))
        vol = int(s.get('master_volume', 100))
        try:
            if not pygame.mixer.get_init():
                try:
                    pygame.mixer.init()
                except Exception:
                    pass
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(max(0.0, min(1.0, vol / 100.0)))
        except Exception:
            pass

    def _load_image(self, rel_path: str):
        candidates = [Path(rel_path), Path(__file__).resolve().parent / rel_path, Path(__file__).resolve().parent / rel_path.lstrip('./')]
        for p in candidates:
            try:
                if p.is_file():
                    return pygame.image.load(str(p)).convert_alpha()
            except Exception:
                continue
        try:
            target = Path(rel_path).name.lower()
            dir_candidates = []
            pr = Path(rel_path)
            dir_candidates.append(pr if pr.is_dir() else pr.parent)
            dir_candidates.append(Path(__file__).resolve().parent / (pr if pr.is_dir() else pr.parent))
            dir_candidates.append(Path(__file__).resolve().parent / 'src' / 'assets')
            seen = set()
            for d in dir_candidates:
                try:
                    d = d.resolve()
                except Exception:
                    continue
                if not d.exists() or not d.is_dir():
                    continue
                if str(d) in seen:
                    continue
                seen.add(str(d))
                for child in d.iterdir():
                    try:
                        if child.is_file() and child.name.lower() == target:
                            return pygame.image.load(str(child)).convert_alpha()
                    except Exception:
                        continue
        except Exception:
            pass
        try:
            return pygame.image.load(rel_path).convert_alpha()
        except Exception:
            return None

    def _get_filtered_tiles(self):
        q = getattr(self, 'ui_spawn_search_text', '') or ''
        tiles = list(getattr(self, 'ui_tiles', []))
        if not q:
            return tiles
        ql = q.lower()
        out = []
        for t in tiles:
            key = str(t.get('key', ''))
            label = str(t.get('label', ''))
            if ql in key.lower() or ql in label.lower():
                out.append(t)
        return out

    def _layout_overlay_ui(self):
        self.ui_flask_rect = pygame.Rect(10, 10, self.ui_icon_size, self.ui_icon_size)
        self.ui_admin_rect = pygame.Rect(self.ui_flask_rect.right + 8, 10, self.ui_icon_size, self.ui_icon_size)
        mw, mh = self.ui_menu_size
        self.ui_menu_rect = pygame.Rect(self.ui_flask_rect.right + 10, 10, mw, mh)
        amw, amh = self.ui_admin_menu_size
        self.ui_admin_menu_rect = pygame.Rect(self.ui_admin_rect.right + 10, 10, amw, amh)
        gpad = 14
        gap = 10
        header_h = getattr(self, 'ui_header_h', 36)
        area_x = self.ui_menu_rect.x + gpad
        search_h = 26
        spad = 4
        self.ui_search_rect = pygame.Rect(area_x, self.ui_menu_rect.y + header_h + spad, mw - 2 * gpad, search_h)
        area_y = self.ui_search_rect.bottom + gpad
        area_w = mw - 2 * gpad
        area_h = mh - header_h - 2 * gpad - 20 - (search_h + spad)
        tiles = self._get_filtered_tiles()
        n = len(tiles)
        min_tile_w = 48
        max_tile_w = 72
        max_cols_fit = max(1, int((area_w + gap) // (min_tile_w + gap)))
        cols = max(1, min(n, max_cols_fit))
        rows = max(1, (n + cols - 1) // cols)
        tile_w_avail = max(1, (area_w - (cols - 1) * gap) // cols)
        tile_h_avail = max(1, (area_h - (rows - 1) * gap) // rows)
        tile_w = max(min_tile_w, min(max_tile_w, tile_w_avail))
        tile_h = max(48, min(72, tile_h_avail))
        self.ui_tile_rects = {}
        for idx, tile in enumerate(tiles):
            r = idx // cols
            c = idx % cols
            x = area_x + c * (tile_w + gap)
            y = area_y + r * (tile_h + gap)
            self.ui_tile_rects[tile['key']] = pygame.Rect(x, y, tile_w, tile_h)

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if getattr(self, 'show_main_menu', False):
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.VIDEORESIZE:
                    self._apply_resize(event.w, event.h)
                    continue
                action = self.menu.handle_event(event)
                if action == 'play':
                    self.show_main_menu = False
                    try:
                        pluginload.load_enabled_plugins(self)
                    except Exception:
                        pass
                    if hasattr(self, 'camera') and self.camera:
                        self.camera.scale = 1.0
                        self.camera.off_x = 0.0
                        self.camera.off_y = 0.0
                    continue
                elif action == 'quit':
                    return False
                continue
            if getattr(self, 'show_pause_menu', False):
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.VIDEORESIZE:
                    self._apply_resize(event.w, event.h)
                    continue
                action = self.pause_menu.handle_event(event)
                if action == 'resume':
                    self.show_pause_menu = False
                    continue
                if action == 'exit':
                    self.show_pause_menu = False
                    self.show_main_menu = True
                    if hasattr(self, 'camera') and self.camera:
                        self.camera.scale = 1.0
                        self.camera.off_x = 0.0
                        self.camera.off_y = 0.0
                    self.ui_show_spawn = False
                    setattr(self, 'ui_show_admin', False)
                    continue
                continue
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.VIDEORESIZE:
                self._apply_resize(event.w, event.h)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx, my = event.pos
                    if self.ui_flask_rect.collidepoint(mx, my):
                        self.ui_show_spawn = not self.ui_show_spawn
                        if self.ui_show_spawn:
                            setattr(self, 'ui_show_admin', False)
                            self._layout_overlay_ui()
                            self.ui_search_active = False
                        continue
                    if hasattr(self, 'ui_admin_rect') and self.ui_admin_rect.collidepoint(mx, my):
                        self.ui_show_admin = not getattr(self, 'ui_show_admin', False)
                        if self.ui_show_admin:
                            self.ui_show_spawn = False
                        continue
                    if self.ui_show_spawn and self.ui_menu_rect.collidepoint(mx, my):
                        if hasattr(self, 'ui_search_rect') and self.ui_search_rect.collidepoint(mx, my):
                            self.ui_search_active = True
                        else:
                            self.ui_search_active = False
                            for key, rect in getattr(self, 'ui_tile_rects', {}).items():
                                if rect.collidepoint(mx, my):
                                    self.current_tool = key
                                    break
                        continue
                    if getattr(self, 'ui_show_admin', False) and hasattr(self, 'ui_admin_menu_rect') and self.ui_admin_menu_rect.collidepoint(mx, my):
                        if hasattr(self, 'ui_admin_clear_rect') and self.ui_admin_clear_rect and self.ui_admin_clear_rect.collidepoint(mx, my):
                            try:
                                clear_everything(self)
                            except Exception:
                                try:
                                    self.sand_system.clear()
                                    self.water_system.clear()
                                    self.lava_system.clear()
                                    if hasattr(self, 'blue_lava_system'):
                                        self.blue_lava_system.clear()
                                    if hasattr(self, 'ruby_system'):
                                        self.ruby_system.clear()
                                    self.toxic_system.clear()
                                    if hasattr(self, 'oil_system'):
                                        self.oil_system.clear()
                                    self.metal_system.clear()
                                    self.blood_system.clear()
                                    self.blocks_system.clear()
                                    if hasattr(self, 'npcs'):
                                        self.npcs.clear()
                                    self.active_npc = None
                                    self.npc_drag_index = None
                                except Exception:
                                    pass
                            continue
                        if hasattr(self, 'ui_admin_clear_npcs_rect') and self.ui_admin_clear_npcs_rect and self.ui_admin_clear_npcs_rect.collidepoint(mx, my):
                            try:
                                clear_living(self)
                            except Exception:
                                try:
                                    if hasattr(self, 'npcs'):
                                        self.npcs.clear()
                                    self.active_npc = None
                                    self.npc_drag_index = None
                                    if hasattr(self, 'npc'):
                                        self.npc = None
                                except Exception:
                                    pass
                            continue
                        if hasattr(self, 'ui_admin_clear_blocks_rect') and self.ui_admin_clear_blocks_rect and self.ui_admin_clear_blocks_rect.collidepoint(mx, my):
                            try:
                                clear_blocks(self)
                            except Exception:
                                try:
                                    if hasattr(self, 'blocks_system'):
                                        self.blocks_system.clear()
                                except Exception:
                                    pass
                            continue
                    if self.current_tool == 'npc':
                        if mx >= self.sidebar_width:
                            vx = mx - self.sidebar_width
                            gx, gy = self.camera.view_to_world(vx, my)
                            npc_hit, part_idx, _ = self._find_nearest_npc(gx, gy, max_dist=40)
                            if npc_hit is not None and part_idx is not None:
                                self.active_npc = npc_hit
                                self.npc_drag_index = part_idx
                                self.active_npc.set_user_dragging(True)
                                self.is_drawing = True
                            else:
                                npc = NPC(gx, gy)
                                self.npcs.append(npc)
                                self.active_npc = npc
                                self.npc_drag_index = npc.nearest_particle_index((gx, gy))
                                npc.set_user_dragging(True)
                                self.is_drawing = True
                    elif self.current_tool == 'blocks':
                        if mx >= self.sidebar_width:
                            vx = mx - self.sidebar_width
                            gx, gy = self.camera.view_to_world(vx, my)
                            self.blocks_drag_active = True
                            self.blocks_drag_start = (int(gx), int(gy))
                            self.blocks_drag_current = (int(gx), int(gy))
                            self.is_drawing = True
                    else:
                        self.is_drawing = True
                elif event.button == 3:
                    mx, my = event.pos
                    if not (self.ui_flask_rect.collidepoint(mx, my) or (self.ui_show_spawn and self.ui_menu_rect.collidepoint(mx, my))):
                        self._pan_active = True
                        self._pan_prev = (mx, my)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.is_drawing = False
                    if self.current_tool == 'npc':
                        self.npc_drag_index = None
                        if self.active_npc is not None:
                            try:
                                self.active_npc.set_user_dragging(False)
                            except Exception:
                                pass
                        self.active_npc = None
                    if self.current_tool == 'blocks' and self.blocks_drag_active and self.blocks_drag_start and self.blocks_drag_current:
                        x0, y0 = self.blocks_drag_start
                        x1, y1 = self.blocks_drag_current
                        self.blocks_system.add_block_rect(x0, y0, x1, y1)
                        try:
                            sfx.play_place()
                        except Exception:
                            pass
                        self.blocks_drag_active = False
                        self.blocks_drag_start = None
                        self.blocks_drag_current = None
                elif event.button == 3:
                    self._pan_active = False
                    self._pan_prev = None
            elif event.type == pygame.MOUSEMOTION:
                if self._pan_active and self._pan_prev is not None:
                    mx, my = event.pos
                    pmx, pmy = self._pan_prev
                    dx = mx - pmx
                    dy = my - pmy
                    self.camera.pan_by(-dx, -dy)
                    self._pan_prev = (mx, my)
                if self.current_tool == 'blocks' and self.blocks_drag_active:
                    mx, my = event.pos
                    if mx >= self.sidebar_width:
                        vx = mx - self.sidebar_width
                        gx, gy = self.camera.view_to_world(vx, my)
                        self.blocks_drag_current = (int(gx), int(gy))
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.show_pause_menu = True
                    continue
                if self.ui_show_spawn and getattr(self, 'ui_search_active', False):
                    if event.key == pygame.K_BACKSPACE:
                        if self.ui_spawn_search_text:
                            self.ui_spawn_search_text = self.ui_spawn_search_text[:-1]
                            self._layout_overlay_ui()
                        continue
                    elif event.key == pygame.K_RETURN:
                        continue
                    else:
                        ch = getattr(event, 'unicode', '')
                        if ch and ch.isprintable() and not ch.isspace() or ch == ' ':
                            self.ui_spawn_search_text = (self.ui_spawn_search_text or '') + ch
                            self._layout_overlay_ui()
                            continue
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_CTRL:
                    mx, my = pygame.mouse.get_pos()
                    if mx >= self.sidebar_width:
                        vx = mx - self.sidebar_width
                        if event.key in (getattr(pygame, 'K_PLUS', pygame.K_EQUALS), pygame.K_EQUALS, pygame.K_KP_PLUS):
                            scale = 1.1 if not self.invert_zoom else 1.0 / 1.1
                            self.camera.zoom_at(scale, vx, my)
                        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                            scale = 1.0 / 1.1 if not self.invert_zoom else 1.1
                            self.camera.zoom_at(scale, vx, my)
                elif event.key == pygame.K_UP:
                    self.brush_size = min(20, self.brush_size + 1)
                elif event.key == pygame.K_DOWN:
                    self.brush_size = max(1, self.brush_size - 1)
        return True

    def _handle_sidebar_click(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        if x >= self.sidebar_width:
            return False
        if self.buttons['sand'].collidepoint(pos):
            self.current_tool = 'sand'
            return True
        elif self.buttons['water'].collidepoint(pos):
            self.current_tool = 'water'
            return True
        elif self.buttons.get('lava') and self.buttons['lava'].collidepoint(pos):
            self.current_tool = 'lava'
            return True
        elif self.buttons.get('bluelava') and self.buttons['bluelava'].collidepoint(pos):
            self.current_tool = 'bluelava'
            return True
        elif self.buttons.get('npc') and self.buttons['npc'].collidepoint(pos):
            self.current_tool = 'npc'
            return True
        elif self.buttons['clear'].collidepoint(pos):
            self.sand_system.clear()
            self.water_system.clear()
            if hasattr(self, 'dirt_system'):
                self.dirt_system.clear()
            if hasattr(self, 'milk_system'):
                self.milk_system.clear()
            if hasattr(self, 'blood_system'):
                self.blood_system.clear()
            if hasattr(self, 'lava_system'):
                self.lava_system.clear()
            if hasattr(self, 'blue_lava_system'):
                self.blue_lava_system.clear()
            if hasattr(self, 'ruby_system'):
                self.ruby_system.clear()
            if hasattr(self, 'toxic_system'):
                self.toxic_system.clear()
            if hasattr(self, 'oil_system'):
                self.oil_system.clear()
            if hasattr(self, 'blood_system'):
                self.blood_system.clear()
            if hasattr(self, 'metal_system'):
                self.metal_system.clear()
            self.npcs.clear()
            self.active_npc = None
            self.npc_drag_index = None
            return True
        return False

    def _compute_sidebar_width(self, w: int) -> int:
        return int(max(120, min(260, w * 0.18)))

    def _layout_ui(self):
        margin = 10
        bw = max(100, self.sidebar_width - margin * 2)
        bh = 40
        y = 20
        self.buttons = {
            'sand': pygame.Rect(margin, y, bw, bh),
            'water': pygame.Rect(margin, y + 50, bw, bh),
            'lava': pygame.Rect(margin, y + 100, bw, bh),
            'bluelava': pygame.Rect(margin, y + 150, bw, bh),
            'npc': pygame.Rect(margin, y + 200, bw, bh),
            'clear': pygame.Rect(margin, y + 250, bw, bh)
        }

    def _apply_resize(self, new_w: int, new_h: int):
        self.width = int(max(400, new_w))
        self.height = int(max(300, new_h))
        self.sidebar_width = 0
        self.game_width = self.width
        self.sand_system.width = self.game_width
        self.sand_system.height = self.height
        if hasattr(self, 'dirt_system'):
            self.dirt_system.width = self.game_width
            self.dirt_system.height = self.height
        self.water_system.width = self.game_width
        self.water_system.height = self.height
        if hasattr(self, 'milk_system'):
            self.milk_system.width = self.game_width
            self.milk_system.height = self.height
        self.lava_system.width = self.game_width
        self.lava_system.height = self.height
        if hasattr(self, 'blue_lava_system'):
            self.blue_lava_system.width = self.game_width
            self.blue_lava_system.height = self.height
        if hasattr(self, 'ruby_system'):
            self.ruby_system.width = self.game_width
            self.ruby_system.height = self.height
        if hasattr(self, 'toxic_system'):
            self.toxic_system.width = self.game_width
            self.toxic_system.height = self.height
        if hasattr(self, 'oil_system'):
            self.oil_system.width = self.game_width
            self.oil_system.height = self.height
        if hasattr(self, 'metal_system'):
            self.metal_system.width = self.game_width
            self.metal_system.height = self.height
        if hasattr(self, 'blocks_system'):
            self.blocks_system.width = self.game_width
            self.blocks_system.height = self.height
        if hasattr(self, 'blood_system'):
            self.blood_system.width = self.game_width
            self.blood_system.height = self.height
        if hasattr(self, '_layout_overlay_ui'):
            self._layout_overlay_ui()
        if hasattr(self, 'camera') and self.camera:
            self.camera.update_view(self.game_width, self.height, self.game_width, self.height)
        self._game_surface = None
        if not self.use_gpu:
            flags = pygame.RESIZABLE | pygame.DOUBLEBUF
            pygame.display.set_mode((self.width, self.height), flags)
        else:
            try:
                if hasattr(self, 'window'):
                    self.window.resizable = True
                    self.window.size = (self.width, self.height)
            except Exception:
                pass

    def _poll_size_change(self):
        try:
            if self.use_gpu and hasattr(self, 'window'):
                w, h = self.window.size
            else:
                surf = pygame.display.get_surface()
                if not surf:
                    return
                w, h = surf.get_size()
            if int(w) != self.width or int(h) != self.height:
                self._apply_resize(int(w), int(h))
        except Exception:
            pass

    def _draw_on_canvas(self):
        if not self.is_drawing:
            return
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if self.ui_flask_rect.collidepoint(mouse_x, mouse_y) or (getattr(self, 'ui_admin_rect', None) and self.ui_admin_rect.collidepoint(mouse_x, mouse_y)) or (self.ui_show_spawn and self.ui_menu_rect.collidepoint(mouse_x, mouse_y)) or (getattr(self, 'ui_show_admin', False) and getattr(self, 'ui_admin_menu_rect', None) and self.ui_admin_menu_rect.collidepoint(mouse_x, mouse_y)):
            return
        if self.current_tool == 'blocks':
            return
        view_x = mouse_x - self.sidebar_width
        game_x, game_y = self.camera.view_to_world(view_x, mouse_y)
        total = (self.sand_system.get_particle_count() +
                  self.water_system.get_particle_count() +
                  (self.milk_system.get_particle_count() if hasattr(self, 'milk_system') else 0) +
                  (self.oil_system.get_particle_count() if hasattr(self, 'oil_system') else 0) +
                  self.lava_system.get_particle_count() +
                  (self.blue_lava_system.get_particle_count() if hasattr(self, 'blue_lava_system') else 0) +
                  self.toxic_system.get_particle_count() +
                  self.metal_system.get_particle_count() +
                  self.blood_system.get_particle_count() +
                  (self.dirt_system.get_particle_count() if hasattr(self, 'dirt_system') else 0))
        if total >= self.max_particles:
            if self.current_tool != 'npc':
                return
        placed = False
        if self.current_tool == 'sand':
            self.sand_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
            placed = True
        elif self.current_tool == 'water':
            self.water_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
            placed = True
        elif self.current_tool == 'oil':
            self.oil_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
            placed = True
        elif self.current_tool == 'lava':
            self.lava_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
            placed = True
        elif self.current_tool == 'bluelava':
            if hasattr(self, 'blue_lava_system'):
                self.blue_lava_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
                placed = True
        elif self.current_tool == 'ruby':
            if hasattr(self, 'ruby_system'):
                self.ruby_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
                placed = True
        elif self.current_tool == 'metal':
            self.metal_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
            placed = True
        elif self.current_tool == 'toxic':
            self.toxic_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
            placed = True
        elif self.current_tool == 'milk':
            if hasattr(self, 'milk_system'):
                for _ in range(self.brush_size * 2):
                    self.milk_system.add_particle(int(game_x), int(game_y))
                placed = True
        elif self.current_tool == 'blood':
            if hasattr(self, 'blood_system'):
                # Use spray to feel like a splatter
                self.blood_system.add_spray(int(game_x), int(game_y), count=max(4, self.brush_size), speed=1.8)
                placed = True
        elif self.current_tool == 'dirt':
            if hasattr(self, 'dirt_system'):
                self.dirt_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
                placed = True
        elif self.current_tool == 'dirt':
            if hasattr(self, 'dirt_system'):
                self.dirt_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
                placed = True
        elif self.current_tool == 'npc':
            if self.active_npc is not None and self.npc_drag_index is not None:
                try:
                    p = self.active_npc.particles[self.npc_drag_index]
                    p.pos[0] = float(game_x)
                    p.pos[1] = float(game_y)
                    p.prev[0] = float(game_x)
                    p.prev[1] = float(game_y)
                except Exception:
                    pass
        else:
            try:
                from DgPy.core import get_tools
                tools = get_tools()
                if self.current_tool in tools:
                    spawn = tools[self.current_tool].get('spawn')
                    if callable(spawn):
                        spawn(self, int(game_x), int(game_y), int(self.brush_size))
            except Exception:
                pass
        if placed:
            try:
                sfx.play_place()
            except Exception:
                pass

    def _handle_cross_material_collisions(self):
        MAX_NEIGHBORS = 12
        if getattr(self, 'oil_system', None) and self.oil_system.particles:
            for oil in self.oil_system.particles:
                waters = self._get_nearby_water(oil.x, oil.y, radius=2)
                if len(waters) > MAX_NEIGHBORS:
                    waters = waters[:MAX_NEIGHBORS]
                for w in waters:
                    if w.y > oil.y + 0.5:
                        oil.y -= 0.6
                        oil.vy -= 0.25
                        w.y += 0.3
                        w.vy += 0.12
        for water in self.water_system.particles:
            sand_neighbors = self._get_nearby_sand(water.x, water.y, radius=2)
            if len(sand_neighbors) > MAX_NEIGHBORS:
                sand_neighbors = sand_neighbors[:MAX_NEIGHBORS]
            for sand in sand_neighbors:
                dx = sand.x - water.x
                dy = sand.y - water.y
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < 2.5 and dist > 0.1:
                    sand.wet = True
                    nx = dx / dist if dist > 0 else 0
                    ny = dy / dist if dist > 0 else 1
                    sand.vx += nx * 0.15
                    sand.vy += ny * 0.15
                    water.vx -= nx * 0.1
                    water.vy -= ny * 0.1
        sand_kill = set()
        water_kill = set()
        for lava in self.lava_system.particles:
            sands = self._get_nearby_sand(lava.x, lava.y, radius=2)
            if len(sands) > MAX_NEIGHBORS:
                sands = sands[:MAX_NEIGHBORS]
            for s in sands:
                dx = s.x - lava.x
                dy = s.y - lava.y
                d2 = dx * dx + dy * dy
                if 0.01 < d2 < 2.5 * 2.5:
                    sand_kill.add(id(s))
                    d = d2 ** 0.5
                    nx, ny = (dx / d, dy / d)
                    lava.vx -= nx * 0.05
                    lava.vy -= ny * 0.05
            waters = self._get_nearby_water(lava.x, lava.y, radius=2)
            if len(waters) > MAX_NEIGHBORS:
                waters = waters[:MAX_NEIGHBORS]
            for w in waters:
                dx = w.x - lava.x
                dy = w.y - lava.y
                d2 = dx * dx + dy * dy
                if 0.01 < d2 < 2.5 * 2.5:
                    water_kill.add(id(w))
                    d = d2 ** 0.5
                    nx, ny = (dx / d, dy / d)
                    lava.vx -= nx * 0.03
                    lava.vy -= ny * 0.03
            if getattr(self, 'oil_system', None) and self.oil_system.particles:
                oils = self._get_nearby_oil(lava.x, lava.y, radius=2)
                if len(oils) > MAX_NEIGHBORS:
                    oils = oils[:MAX_NEIGHBORS]
                for o in oils:
                    dx = o.x - lava.x
                    dy = o.y - lava.y
                    d2 = dx * dx + dy * dy
                    if 0.01 < d2 <= 9.0:
                        ignite = getattr(o, 'ignite', None)
                        if ignite:
                            ignite(220)
        if sand_kill:
            for p in self.sand_system.particles:
                if id(p) in sand_kill:
                    setattr(p, 'dead', True)
            self.sand_system.sweep_dead()
        if water_kill:
            for p in self.water_system.particles:
                if id(p) in water_kill:
                    setattr(p, 'dead', True)
            self.water_system.sweep_dead()

    def _get_nearby_sand(self, x: float, y: float, radius: int=2) -> list:
        cell_x, cell_y = (int(x // self.sand_system.cell_size), int(y // self.sand_system.cell_size))
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.sand_system.grid:
                    nearby.extend(self.sand_system.grid[cell])
        return nearby

    def _get_nearby_water(self, x: float, y: float, radius: int=2) -> list:
        cell_x, cell_y = (int(x // self.water_system.cell_size), int(y // self.water_system.cell_size))
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.water_system.grid:
                    nearby.extend(self.water_system.grid[cell])
        return nearby

    def _get_nearby_blood(self, x: float, y: float, radius: int=2) -> list:
        if not hasattr(self, 'blood_system'):
            return []
        cs = getattr(self.blood_system, 'cell_size', 3)
        cell_x, cell_y = (int(x // cs), int(y // cs))
        out = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cx = cell_x + dx
                cy = cell_y + dy
                for p in getattr(self.blood_system, 'particles', []):
                    if int(p.x // cs) == cx and int(p.y // cs) == cy:
                        out.append(p)
        return out

    def _get_nearby_lava(self, x: float, y: float, radius: int=2) -> list:
        cell_x, cell_y = (int(x // self.lava_system.cell_size), int(y // self.lava_system.cell_size))
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.lava_system.grid:
                    nearby.extend(self.lava_system.grid[cell])
        return nearby

    def _get_nearby_bluelava(self, x: float, y: float, radius: int=2) -> list:
        if not hasattr(self, 'blue_lava_system'):
            return []
        cs = self.blue_lava_system.cell_size
        cell_x, cell_y = (int(x // cs), int(y // cs))
        nearby = []
        grid = self.blue_lava_system.grid
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in grid:
                    nearby.extend(grid[cell])
        return nearby

    def _get_nearby_ruby(self, x: float, y: float, radius: int=2) -> list:
        if not hasattr(self, 'ruby_system'):
            return []
        cs = getattr(self.ruby_system, 'cell_size', 3)
        cell_x, cell_y = (int(x // cs), int(y // cs))
        nearby = []
        grid = getattr(self.ruby_system, 'grid', {})
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in grid:
                    nearby.extend(grid[cell])
        return nearby

    def _get_nearby_toxic(self, x: float, y: float, radius: int=2) -> list:
        cell_x, cell_y = (int(x // self.toxic_system.cell_size), int(y // self.toxic_system.cell_size))
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.toxic_system.grid:
                    nearby.extend(self.toxic_system.grid[cell])
        return nearby

    def _get_nearby_oil(self, x: float, y: float, radius: int=2) -> list:
        cell_x, cell_y = (int(x // self.oil_system.cell_size), int(y // self.oil_system.cell_size))
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.oil_system.grid:
                    nearby.extend(self.oil_system.grid[cell])
        return nearby

    def _get_nearby_milk(self, x: float, y: float, radius: int=2) -> list:
        if not hasattr(self, 'milk_system'):
            return []
        cell_x, cell_y = (int(x // self.milk_system.cell_size), int(y // self.milk_system.cell_size))
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.milk_system.grid:
                    nearby.extend(self.milk_system.grid[cell])
        return nearby

    def _get_nearby_dirt(self, x: float, y: float, radius: int=2) -> list:
        if not hasattr(self, 'dirt_system'):
            return []
        cell_x, cell_y = (int(x // self.dirt_system.cell_size), int(y // self.dirt_system.cell_size))
        nearby = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.dirt_system.grid:
                    nearby.extend(self.dirt_system.grid[cell])
        return nearby

    def _find_nearest_npc(self, x: float, y: float, max_dist: float=40.0):
        if not getattr(self, 'npcs', None):
            return (None, None, None)
        best_npc = None
        best_idx = None
        best_d2 = max_dist * max_dist
        for npc in self.npcs:
            for i, p in enumerate(npc.particles):
                dx = float(p.pos.x) - float(x)
                dy = float(p.pos.y) - float(y)
                d2 = dx * dx + dy * dy
                if d2 < best_d2:
                    best_d2 = d2
                    best_npc = npc
                    best_idx = i
        if best_npc is None:
            return (None, None, None)
        return (best_npc, best_idx, best_d2 ** 0.5)

    def _npc_particle_coupling(self):
        if not getattr(self, 'npcs', None) or (not self.sand_system.particles and (not self.water_system.particles)):
            return
        push_radius = 8.0
        push_r2 = push_radius * push_radius
        sand_push = 0.2
        water_push = 0.25
        npc_react = 0.04
        radius_cells = 2
        max_neighbors = 10
        for npc in self.npcs:
            for p in npc.particles:
                px, py = p.pos
                sands = self._get_nearby_sand(px, py, radius=radius_cells)
                if len(sands) > max_neighbors:
                    sands = sands[:max_neighbors]
                for s in sands:
                    dx = s.x - px
                    dy = s.y - py
                    d2 = dx * dx + dy * dy
                    if d2 > push_r2 or d2 <= 0.0001:
                        continue
                    d = d2 ** 0.5
                    nx = dx / d
                    ny = dy / d
                    s.vx += nx * sand_push
                    s.vy += ny * sand_push
                    p.pos[0] -= nx * npc_react
                    p.pos[1] -= ny * npc_react
                waters = self._get_nearby_water(px, py, radius=radius_cells)
                if len(waters) > max_neighbors:
                    waters = waters[:max_neighbors]
                for w in waters:
                    dx = w.x - px
                    dy = w.y - py
                    d2 = dx * dx + dy * dy
                    if d2 > push_r2 or d2 <= 0.0001:
                        continue
                    d = d2 ** 0.5
                    nx = dx / d
                    ny = dy / d
                    w.vx += nx * water_push
                    w.vy += ny * water_push
                    p.pos[0] -= nx * npc_react
                    p.pos[1] -= ny * npc_react

    def _apply_cursor_interaction(self):
        mx, my = pygame.mouse.get_pos()
        if self.ui_flask_rect.collidepoint(mx, my) or (getattr(self, 'ui_admin_rect', None) and self.ui_admin_rect.collidepoint(mx, my)) or (self.ui_show_spawn and self.ui_menu_rect.collidepoint(mx, my)) or (getattr(self, 'ui_show_admin', False) and getattr(self, 'ui_admin_menu_rect', None) and self.ui_admin_menu_rect.collidepoint(mx, my)):
            self._prev_mouse = (mx, my)
            return
        if self._prev_mouse is None:
            self._prev_mouse = (mx, my)
            return
        if not self.ready or mx < self.sidebar_width:
            self._prev_mouse = (mx, my)
            return
        gvx = mx - self.sidebar_width
        gvy = my
        gx, gy = self.camera.view_to_world(gvx, gvy)
        pmx, pmy = self._prev_mouse
        dx = (mx - pmx) / max(self.camera.scale, 1e-06)
        dy = (my - pmy) / max(self.camera.scale, 1e-06)
        self._prev_mouse = (mx, my)
        moved = (dx * dx + dy * dy) ** 0.5
        if moved < 0.1:
            dx = 0.0
            dy = 0.0
        self.sand_system._rebuild_grid()
        self.water_system._rebuild_grid()
        radius_cells = 2
        push_radius = 10
        move_strength_sand = 0.15
        move_strength_water = 0.25
        outward_strength = 0.12
        sand_neighbors = self._get_nearby_sand(gx, gy, radius=radius_cells)
        for s in sand_neighbors:
            ox = s.x - gx
            oy = s.y - gy
            dist2 = ox * ox + oy * oy
            if dist2 <= push_radius * push_radius:
                d = dist2 ** 0.5 if dist2 > 0 else 0.01
                nx = ox / d
                ny = oy / d
                s.vx += -nx * outward_strength
                s.vy += -ny * outward_strength
            s.vx += dx * move_strength_sand * 0.1
            s.vy += dy * move_strength_sand * 0.1
        water_neighbors = self._get_nearby_water(gx, gy, radius=radius_cells)
        for w in water_neighbors:
            ox = w.x - gx
            oy = w.y - gy
            dist2 = ox * ox + oy * oy
            if dist2 <= push_radius * push_radius:
                d = dist2 ** 0.5 if dist2 > 0 else 0.01
                nx = ox / d
                ny = oy / d
                w.vx += -nx * outward_strength
                w.vy += -ny * outward_strength
            w.vx += dx * move_strength_water * 0.1
            w.vy += dy * move_strength_water * 0.1

    def _handle_npc_hazards(self):
        if not getattr(self, 'npcs', None):
            return
        if not (self.lava_system.particles or self.toxic_system.particles):
            return
        contact_r2 = 4.0
        blood_per_frame = 3
        toxic_drip_radius = 1
        for npc in self.npcs:
            for part in npc.particles:
                px, py = part.pos
                lavas = self._get_nearby_lava(px, py, radius=2)
                for lv in lavas[:8]:
                    dx = lv.x - px
                    dy = lv.y - py
                    if dx * dx + dy * dy <= contact_r2:
                        npc.burn_timer = max(npc.burn_timer, 45)
                        self.blood_system.add_spray(px, py, count=blood_per_frame, speed=1.0)
                        break
                else:
                    tox = self._get_nearby_toxic(px, py, radius=2)
                    for tv in tox[:8]:
                        dx = tv.x - px
                        dy = tv.y - py
                        if dx * dx + dy * dy <= contact_r2:
                            npc.toxic_timer = max(npc.toxic_timer, 90)
                            self.blood_system.add_spray(px, py, count=2, speed=1.2)
                            self.toxic_system.add_particle_cluster(int(px), int(py), radius=toxic_drip_radius)
                            break

    def update(self):
        try:
            if getattr(self, 'show_main_menu', False):
                dg_discord.update_for_menu()
            else:
                pc = 0
                try:
                    svc = get_service()
                    if svc is not None:
                        pc = sum((1 for p in svc.get_plugins() if getattr(p, 'enabled', False)))
                except Exception:
                    pc = 0
                dg_discord.update_for_sandbox(pc)
        except Exception:
            pass
        if getattr(self, 'show_main_menu', False):
            if hasattr(self, 'menu'):
                self.menu.update()
            self._frame_index += 1
            if hasattr(self, 'clock'):
                self.fps = int(self.clock.get_fps())
            return
        if getattr(self, 'show_pause_menu', False):
            if hasattr(self, 'pause_menu'):
                self.pause_menu.update()
            self._frame_index += 1
            if hasattr(self, 'clock'):
                self.fps = int(self.clock.get_fps())
            return
        self._draw_on_canvas()
        if not self.ready:
            return
        self._apply_cursor_interaction()
        if self.active_npc is not None and self.current_tool == 'npc' and self.is_drawing and (self.npc_drag_index is not None):
            mx, my = pygame.mouse.get_pos()
            if mx >= self.sidebar_width:
                vx = mx - self.sidebar_width
                gx, gy = self.camera.view_to_world(vx, my)
                try:
                    p = self.active_npc.particles[self.npc_drag_index]
                    p.pos[0] = gx
                    p.pos[1] = gy
                    p.prev[0] = gx
                    p.prev[1] = gy
                except Exception:
                    pass
        total = (self.sand_system.get_particle_count() + self.water_system.get_particle_count() +
                 self.lava_system.get_particle_count() +
                 (self.blue_lava_system.get_particle_count() if hasattr(self, 'blue_lava_system') else 0) +
                 self.toxic_system.get_particle_count() + self.blood_system.get_particle_count())
        if self._frame_index - self._last_scale_apply >= 15:
            settings = recommend_settings(total, self._fps_avg or self.fps, self.target_fps, self.use_gpu)
            s = settings['sand']
            w = settings['water']
            self.sand_system.neighbor_radius = s['neighbor_radius']
            self.sand_system.max_neighbors = s['max_neighbors']
            self.sand_system.skip_mod = s['skip_mod']
            self.water_system.neighbor_radius = w['neighbor_radius']
            self.water_system.max_neighbors = w['max_neighbors']
            self.water_system.skip_mod = w['skip_mod']
            self.lava_system.neighbor_radius = w['neighbor_radius']
            self.lava_system.max_neighbors = w['max_neighbors']
            self.lava_system.skip_mod = w['skip_mod']
            self.toxic_system.neighbor_radius = w['neighbor_radius']
            self.toxic_system.max_neighbors = w['max_neighbors']
            self.toxic_system.skip_mod = w['skip_mod']
            if hasattr(self, 'oil_system'):
                self.oil_system.neighbor_radius = w['neighbor_radius']
                self.oil_system.max_neighbors = w['max_neighbors']
                self.oil_system.skip_mod = w['skip_mod']
            self._last_scale_apply = self._frame_index
        self.sand_system.update(self._frame_index)
        self.water_system.update(self._frame_index)
        if hasattr(self, 'milk_system'):
            self.milk_system.update()
        if hasattr(self, 'oil_system'):
            self.oil_system.update(self._frame_index)
        self.lava_system.update(self._frame_index)
        if hasattr(self, 'blue_lava_system'):
            self.blue_lava_system.update(self._frame_index)
        self.toxic_system.update(self._frame_index)
        self.metal_system.update(self._frame_index)
        if hasattr(self, 'ruby_system'):
            self.ruby_system.update(self._frame_index)
        if hasattr(self, 'blood_system'):
            self.blood_system.update(self._frame_index)
        if hasattr(self, 'dirt_system'):
            self.dirt_system.update(self._frame_index)
        self.blocks_system.update(self._frame_index)
        dt = 1.0 / max(self.target_fps, 1)
        if self.npcs:
            for npc in list(self.npcs):
                try:
                    npc.update(dt, bounds=(self.game_width, self.height))
                except Exception:
                    try:
                        self.npcs.remove(npc)
                    except Exception:
                        pass
        if self.npcs:
            self._npc_particle_coupling()
        try:
            from src import reactions as dg_react
            dg_react.apply(self)
        except Exception:
            # Fallback to legacy local interactions if reactions module fails
            try:
                self._handle_cross_material_collisions()
            except Exception:
                pass
        self._handle_npc_hazards()

    def draw_sidebar(self):
        if not self.use_gpu:
            pygame.draw.rect(self.screen, (40, 40, 40), (0, 0, self.sidebar_width, self.height))
            for button_name, button_rect in self.buttons.items():
                is_active = self.current_tool == button_name
                color = (100, 150, 255) if is_active else (60, 60, 60)
                pygame.draw.rect(self.screen, color, button_rect)
                pygame.draw.rect(self.screen, (150, 150, 150), button_rect, 2)
                text = self.button_font.render(button_name.upper(), True, (255, 255, 255))
                text_rect = text.get_rect(center=button_rect.center)
                self.screen.blit(text, text_rect)
            size_y = 220
            size_text = self.button_font.render(f'Size: {self.brush_size}', True, (200, 200, 200))
            self.screen.blit(size_text, (10, size_y))
            info_y = 250
            info_lines = ['UP/DOWN: Size', 'ESC: Quit']
            for i, line in enumerate(info_lines):
                info_text = self.button_font.render(line, True, (150, 150, 150))
                self.screen.blit(info_text, (10, info_y + i * 20))
            return
        self.renderer.draw_color = (40, 40, 40, 255)
        self.renderer.fill_rect(sdl2rect.Rect(0, 0, self.sidebar_width, self.height))
        for button_name, button_rect in self.buttons.items():
            is_active = self.current_tool == button_name
            color = (100, 150, 255, 255) if is_active else (60, 60, 60, 255)
            border = (150, 150, 150, 255)
            rect = sdl2rect.Rect(button_rect.x, button_rect.y, button_rect.w, button_rect.h)
            self.renderer.draw_color = color
            self.renderer.fill_rect(rect)
            self.renderer.draw_color = border
            self.renderer.draw_rect(rect)
            text = button_name.upper()
            text_surf = self.button_font.render(text, True, (255, 255, 255))
            text_tex = self._get_text_texture(text, (255, 255, 255))
            tr = text_surf.get_rect(center=(button_rect.x + button_rect.w // 2, button_rect.y + button_rect.h // 2))
            self.renderer.copy(text_tex, dstrect=sdl2rect.Rect(tr.x, tr.y, tr.w, tr.h))
        size_label = f'Size: {self.brush_size}'
        size_surf = self.button_font.render(size_label, True, (200, 200, 200))
        size_tex = self._get_text_texture(size_label, (200, 200, 200))
        self.renderer.copy(size_tex, dstrect=sdl2rect.Rect(10, 220, size_surf.get_width(), size_surf.get_height()))
        info_lines = ['UP/DOWN: Size', 'ESC: Pause']
        y = 250
        for line in info_lines:
            info_surf = self.button_font.render(line, True, (150, 150, 150))
            info_tex = self._get_text_texture(line, (150, 150, 150))
            self.renderer.copy(info_tex, dstrect=sdl2rect.Rect(10, y, info_surf.get_width(), info_surf.get_height()))
            y += 20

    def draw(self):
        if getattr(self, 'show_main_menu', False) or (not self.ready or not self.use_gpu):
            self.screen.fill((20, 20, 20))
            if getattr(self, 'show_main_menu', False):
                pygame.draw.rect(self.screen, (30, 30, 30), (self.sidebar_width, 0, self.game_width, self.height))
                if self._game_surface is None or self._game_surface.get_size() != (self.game_width, self.height):
                    self._game_surface = pygame.Surface((self.game_width, self.height)).convert()
                game_surface = self._game_surface
                game_surface.fill((30, 30, 30))
                if hasattr(self, 'grid_bg') and hasattr(self, 'menu'):
                    self.grid_bg.draw_cpu(game_surface, self.menu.camera)
                self.screen.blit(game_surface, (self.sidebar_width, 0))
                self.menu.draw_cpu(self.screen)
                pygame.display.flip()
                return
            if self.ready:
                pygame.draw.rect(self.screen, (30, 30, 30), (self.sidebar_width, 0, self.game_width, self.height))
                if self._game_surface is None or self._game_surface.get_size() != (self.game_width, self.height):
                    self._game_surface = pygame.Surface((self.game_width, self.height)).convert()
                game_surface = self._game_surface
                game_surface.fill((20, 20, 20))
                if getattr(self, 'show_grid', True) and hasattr(self, 'grid_bg') and hasattr(self, 'camera'):
                    self.grid_bg.draw_cpu(game_surface, self.camera)
                self.blocks_system.draw(game_surface)
                self.metal_system.draw(game_surface)
                if hasattr(self, 'ruby_system'):
                    self.ruby_system.draw(game_surface)
                if hasattr(self, 'dirt_system'):
                    self.dirt_system.draw(game_surface)
                self.sand_system.draw(game_surface)
                self.water_system.draw(game_surface)
                if hasattr(self, 'milk_system'):
                    self.milk_system.draw(game_surface)
                if hasattr(self, 'oil_system'):
                    self.oil_system.draw(game_surface)
                self.lava_system.draw(game_surface)
                if hasattr(self, 'blue_lava_system'):
                    self.blue_lava_system.draw(game_surface)
                self.toxic_system.draw(game_surface)
                self.blood_system.draw(game_surface)
                # AIR overlay removed
                if getattr(self, 'npcs', None):
                    for npc in self.npcs:
                        try:
                            npc.draw(game_surface)
                        except Exception:
                            pass
                if getattr(self, 'camera', None) and (not self.camera.is_identity()):
                    vw = self.game_width
                    vh = self.height
                    src_w = max(1, int(vw / self.camera.scale))
                    src_h = max(1, int(vh / self.camera.scale))
                    src_x = max(0, min(int(self.camera.off_x), self.game_width - src_w))
                    src_y = max(0, min(int(self.camera.off_y), self.height - src_h))
                    src_rect = pygame.Rect(src_x, src_y, src_w, src_h)
                    sub = game_surface.subsurface(src_rect).copy()
                    scaled = pygame.transform.smoothscale(sub, (vw, vh))
                    self.screen.blit(scaled, (self.sidebar_width, 0))
                else:
                    self.screen.blit(game_surface, (self.sidebar_width, 0))
                self._draw_overlays_cpu()
                if getattr(self, 'show_pause_menu', False):
                    dim = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                    dim.fill((0, 0, 0, 140))
                    self.screen.blit(dim, (0, 0))
                    if hasattr(self, 'pause_menu'):
                        self.pause_menu.draw_cpu(self.screen)
                now = time.time()
                if now - self._stats_updated_at > 0.25:
                    self._stats_updated_at = now
                    parts = [f'Blocks: {self.blocks_system.get_particle_count()}', f'Metal: {self.metal_system.get_particle_count()}']
                    if hasattr(self, 'ruby_system'):
                        parts.append(f'Ruby: {self.ruby_system.get_particle_count()}')
                    if hasattr(self, 'dirt_system'):
                        parts.append(f'Dirt: {self.dirt_system.get_particle_count()}')
                    parts.extend([f'Sand: {self.sand_system.get_particle_count()}', f'Water: {self.water_system.get_particle_count()}'])
                    if hasattr(self, 'oil_system'):
                        parts.append(f'Oil: {self.oil_system.get_particle_count()}')
                    parts.extend([
                        f'Lava: {self.lava_system.get_particle_count()}',
                        f"BlueLava: {self.blue_lava_system.get_particle_count() if hasattr(self, 'blue_lava_system') else 0}",
                        f'Toxic: {self.toxic_system.get_particle_count()}',
                        f'Blood: {self.blood_system.get_particle_count()}'
                    ])
                    stats = ' | '.join(parts) + f' | FPS: {self.fps}'
                    self._stats_cache_surf = self.font.render(stats, True, (200, 200, 200))
                if self._stats_cache_surf:
                    self.screen.blit(self._stats_cache_surf, (self.sidebar_width + 10, self.height - 25))
                mouse_x, mouse_y = pygame.mouse.get_pos()
                if self.sidebar_width <= mouse_x < self.width:
                    color = (200, 100, 100) if self.current_tool == 'sand' else (100, 150, 255)
                    pygame.draw.circle(self.screen, color, (mouse_x, mouse_y), self.brush_size, 1)
            pygame.display.flip()
            return
        self.renderer.draw_color = (20, 20, 20, 255)
        self.renderer.clear()
        self.renderer.draw_color = (30, 30, 30, 255)
        self.renderer.fill_rect(sdl2rect.Rect(self.sidebar_width, 0, self.game_width, self.height))
        if getattr(self, 'show_main_menu', False):
            if hasattr(self, 'grid_bg') and hasattr(self, 'menu'):
                self.grid_bg.draw_gpu(self.renderer, (self.sidebar_width, 0, self.game_width, self.height), self.menu.camera)
                self.menu.draw_gpu(self.renderer)
            self.renderer.present()
            return
            if getattr(self, 'show_grid', True) and hasattr(self, 'grid_bg') and hasattr(self, 'camera'):
                self.grid_bg.draw_gpu(self.renderer, (self.sidebar_width, 0, self.game_width, self.height), self.camera)
        use_cpu_composite = getattr(self, 'camera', None) and (not self.camera.is_identity())
        if use_cpu_composite:
            cpu_layer = pygame.Surface((self.game_width, self.height), pygame.SRCALPHA)
            cpu_layer.fill((20, 20, 20, 255))
            if hasattr(self, 'grid_bg') and hasattr(self, 'camera'):
                self.grid_bg.draw_cpu(cpu_layer, self.camera)
            self.blocks_system.draw(cpu_layer)
            self.metal_system.draw(cpu_layer)
            if hasattr(self, 'ruby_system'):
                self.ruby_system.draw(cpu_layer)
            if hasattr(self, 'dirt_system'):
                self.dirt_system.draw(cpu_layer)
            self.sand_system.draw(cpu_layer)
            self.water_system.draw(cpu_layer)
            if hasattr(self, 'oil_system'):
                self.oil_system.draw(cpu_layer)
            self.lava_system.draw(cpu_layer)
            if hasattr(self, 'blue_lava_system'):
                self.blue_lava_system.draw(cpu_layer)
            self.toxic_system.draw(cpu_layer)
            self.blood_system.draw(cpu_layer)
            if self.npc is not None:
                self.npc.draw(cpu_layer)
            vw = self.game_width
            vh = self.height
            src_w = max(1, int(vw / self.camera.scale))
            src_h = max(1, int(vh / self.camera.scale))
            src_x = max(0, min(int(self.camera.off_x), self.game_width - src_w))
            src_y = max(0, min(int(self.camera.off_y), self.height - src_h))
            src_rect = pygame.Rect(src_x, src_y, src_w, src_h)
            sub = cpu_layer.subsurface(src_rect).copy()
            scaled = pygame.transform.smoothscale(sub, (vw, vh))
            tex = Texture.from_surface(self.renderer, scaled)
            self.renderer.copy(tex, dstrect=sdl2rect.Rect(self.sidebar_width, 0, self.game_width, self.height))
        else:
            if hasattr(self, 'dirt_system'):
                try:
                    dirt_groups = self.dirt_system.get_point_groups()
                    if hasattr(dirt_groups, 'items'):
                        for color, pts in dirt_groups.items():
                            if not pts:
                                continue
                            pts_offset = [(x + self.sidebar_width, y) for x, y in pts]
                            self.renderer.draw_color = (color[0], color[1], color[2], 255)
                            self.renderer.draw_points(pts_offset)
                except Exception:
                    pass
            sand_groups = self.sand_system.get_point_groups()
            for color, pts in sand_groups.items():
                if not pts:
                    continue
                pts_offset = [(x + self.sidebar_width, y) for x, y in pts]
                self.renderer.draw_color = (color[0], color[1], color[2], 255)
                self.renderer.draw_points(pts_offset)
            m_color, m_points = self.metal_system.get_point_groups()
            if m_points:
                m_pts_offset = [(x + self.sidebar_width, y) for x, y in m_points]
                self.renderer.draw_color = (m_color[0], m_color[1], m_color[2], 255)
                self.renderer.draw_points(m_pts_offset)
            if hasattr(self, 'ruby_system'):
                try:
                    r_color, r_points = self.ruby_system.get_point_groups()
                    if r_points:
                        r_pts_offset = [(x + self.sidebar_width, y) for x, y in r_points]
                        self.renderer.draw_color = (r_color[0], r_color[1], r_color[2], 255)
                        self.renderer.draw_points(r_pts_offset)
                except Exception:
                    pass
            bl_color, bl_points = self.blocks_system.get_point_groups()
            if bl_points:
                bl_pts_offset = [(x + self.sidebar_width, y) for x, y in bl_points]
                self.renderer.draw_color = (bl_color[0], bl_color[1], bl_color[2], 255)
                self.renderer.draw_points(bl_pts_offset)
            oil_groups = self.oil_system.get_point_groups() if hasattr(self, 'oil_system') else None
            if oil_groups:
                if hasattr(oil_groups, 'items'):
                    for color, pts in oil_groups.items():
                        if not pts:
                            continue
                        pts_offset = [(x + self.sidebar_width, y) for x, y in pts]
                        self.renderer.draw_color = (color[0], color[1], color[2], 255)
                        self.renderer.draw_points(pts_offset)
                else:
                    o_color, o_points = oil_groups
                    if o_points:
                        o_pts_offset = [(x + self.sidebar_width, y) for x, y in o_points]
                        self.renderer.draw_color = (o_color[0], o_color[1], o_color[2], 255)
                        self.renderer.draw_points(o_pts_offset)
            w_color, w_points = self.water_system.get_point_groups()
            if w_points:
                w_pts_offset = [(x + self.sidebar_width, y) for x, y in w_points]
                self.renderer.draw_color = (w_color[0], w_color[1], w_color[2], 255)
                self.renderer.draw_points(w_pts_offset)
            l_color, l_points = self.lava_system.get_point_groups()
            if hasattr(self, 'blue_lava_system'):
                bl_col, bl_pts = self.blue_lava_system.get_point_groups()
                if bl_pts:
                    bl_pts_offset = [(x + self.sidebar_width, y) for x, y in bl_pts]
                    self.renderer.draw_color = (bl_col[0], bl_col[1], bl_col[2], 255)
                    self.renderer.draw_points(bl_pts_offset)
            if l_points:
                l_pts_offset = [(x + self.sidebar_width, y) for x, y in l_points]
                self.renderer.draw_color = (l_color[0], l_color[1], l_color[2], 255)
                self.renderer.draw_points(l_pts_offset)
            t_color, t_points = self.toxic_system.get_point_groups()
            if t_points:
                t_pts_offset = [(x + self.sidebar_width, y) for x, y in t_points]
                self.renderer.draw_color = (t_color[0], t_color[1], t_color[2], 255)
                self.renderer.draw_points(t_pts_offset)
            b_color, b_points = self.blood_system.get_point_groups()
            if b_points:
                b_pts_offset = [(x + self.sidebar_width, y) for x, y in b_points]
                self.renderer.draw_color = (b_color[0], b_color[1], b_color[2], 255)
                self.renderer.draw_points(b_pts_offset)
            if getattr(self, 'npcs', None):
                cpu_layer = pygame.Surface((self.game_width, self.height), pygame.SRCALPHA)
                for npc in self.npcs:
                    try:
                        npc.draw(cpu_layer)
                    except Exception:
                        pass
                npc_tex = Texture.from_surface(self.renderer, cpu_layer)
                self.renderer.copy(npc_tex, dstrect=sdl2rect.Rect(self.sidebar_width, 0, self.game_width, self.height))
        self._draw_overlays_gpu()
        if getattr(self, 'show_pause_menu', False):
            self.renderer.draw_color = (0, 0, 0, 140)
            self.renderer.fill_rect(sdl2rect.Rect(0, 0, self.width, self.height))
            if hasattr(self, 'pause_menu'):
                self.pause_menu.draw_gpu(self.renderer)
        now = time.time()
        if self._stats_cache_tex is None or now - self._stats_updated_at > 0.25:
            self._stats_updated_at = now
            parts = [f'Blocks: {self.blocks_system.get_particle_count()}', f'Metal: {self.metal_system.get_particle_count()}']
            if hasattr(self, 'ruby_system'):
                parts.append(f'Ruby: {self.ruby_system.get_particle_count()}')
            if hasattr(self, 'dirt_system'):
                parts.append(f'Dirt: {self.dirt_system.get_particle_count()}')
            parts.extend([f'Sand: {self.sand_system.get_particle_count()}', f'Water: {self.water_system.get_particle_count()}'])
            if hasattr(self, 'milk_system'):
                parts.append(f'Milk: {self.milk_system.get_particle_count()}')
            if hasattr(self, 'milk_system'):
                parts.append(f'Milk: {self.milk_system.get_particle_count()}')
            if hasattr(self, 'oil_system'):
                parts.append(f'Oil: {self.oil_system.get_particle_count()}')
            parts.extend([
                f'Lava: {self.lava_system.get_particle_count()}',
                f"BlueLava: {self.blue_lava_system.get_particle_count() if hasattr(self, 'blue_lava_system') else 0}",
                f'Toxic: {self.toxic_system.get_particle_count()}',
                f'Blood: {self.blood_system.get_particle_count()}'
            ])
            stats = ' | '.join(parts) + f' | FPS: {self.fps}'
            stats_surf = self.font.render(stats, True, (200, 200, 200))
            self._stats_cache_tex = Texture.from_surface(self.renderer, stats_surf)
            self._stats_cache_surf = stats_surf
        if self._stats_cache_tex and self._stats_cache_surf:
            self.renderer.copy(self._stats_cache_tex, dstrect=sdl2rect.Rect(self.sidebar_width + 10, self.height - 25, self._stats_cache_surf.get_width(), self._stats_cache_surf.get_height()))
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if self.sidebar_width <= mouse_x < self.width:
            r = self.brush_size
            self.renderer.draw_color = (200, 100, 100, 255) if self.current_tool == 'sand' else (100, 150, 255, 255)
            outline = sdl2rect.Rect(mouse_x - r, mouse_y - r, r * 2, r * 2)
            self.renderer.draw_rect(outline)
        self.renderer.present()

    def _ensure_ui_textures(self):
        if not getattr(self, 'use_gpu', False):
            return
        if not hasattr(self, 'renderer'):
            return
        if self._ui_flask_tex is None and hasattr(self, 'ui_flask_surf'):
            try:
                self._ui_flask_tex = Texture.from_surface(self.renderer, self.ui_flask_surf)
            except Exception:
                self._ui_flask_tex = None
        if self._ui_water_tex is None and hasattr(self, 'ui_water_surf'):
            try:
                self._ui_water_tex = Texture.from_surface(self.renderer, self.ui_water_surf)
            except Exception:
                self._ui_water_tex = None
        if self._ui_sand_tex is None and hasattr(self, 'ui_sand_surf'):
            try:
                self._ui_sand_tex = Texture.from_surface(self.renderer, self.ui_sand_surf)
            except Exception:
                self._ui_sand_tex = None
        if self._ui_lava_tex is None and hasattr(self, 'ui_lava_surf'):
            try:
                self._ui_lava_tex = Texture.from_surface(self.renderer, self.ui_lava_surf)
            except Exception:
                self._ui_lava_tex = None
        if self._ui_npc_tex is None and hasattr(self, 'ui_npc_surf'):
            try:
                self._ui_npc_tex = Texture.from_surface(self.renderer, self.ui_npc_surf)
            except Exception:
                self._ui_npc_tex = None
        if self._ui_toxic_tex is None and hasattr(self, 'ui_toxic_surf'):
            try:
                self._ui_toxic_tex = Texture.from_surface(self.renderer, self.ui_toxic_surf)
            except Exception:
                self._ui_toxic_tex = None
        if self._ui_oil_tex is None and hasattr(self, 'ui_oil_surf'):
            try:
                self._ui_oil_tex = Texture.from_surface(self.renderer, self.ui_oil_surf)
            except Exception:
                self._ui_oil_tex = None
        if self._ui_blocks_tex is None and hasattr(self, 'ui_blocks_surf'):
            try:
                self._ui_blocks_tex = Texture.from_surface(self.renderer, self.ui_blocks_surf)
            except Exception:
                self._ui_blocks_tex = None

    def _draw_overlays_cpu(self):
        overlay = pygame.Surface(self.ui_flask_rect.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.screen.blit(overlay, self.ui_flask_rect.topleft)
        pygame.draw.rect(self.screen, (90, 90, 90), self.ui_flask_rect, 1)
        pad = 6
        dest_w = max(1, self.ui_flask_rect.w - 2 * pad)
        dest_h = max(1, self.ui_flask_rect.h - 2 * pad)
        if self.ui_flask_surf:
            iw, ih = self.ui_flask_surf.get_size()
            scale = min(dest_w / iw, dest_h / ih)
            scaled = pygame.transform.smoothscale(self.ui_flask_surf, (int(iw * scale), int(ih * scale)))
            dx = self.ui_flask_rect.x + (self.ui_flask_rect.w - scaled.get_width()) // 2
            dy = self.ui_flask_rect.y + (self.ui_flask_rect.h - scaled.get_height()) // 2
            self.screen.blit(scaled, (dx, dy))
        if hasattr(self, 'ui_admin_rect'):
            overlay2 = pygame.Surface(self.ui_admin_rect.size, pygame.SRCALPHA)
            overlay2.fill((0, 0, 0, 128))
            self.screen.blit(overlay2, self.ui_admin_rect.topleft)
            pygame.draw.rect(self.screen, (90, 90, 90), self.ui_admin_rect, 1)
            if not hasattr(self, 'ui_admin_surf'):
                self.ui_admin_surf = self._load_image('src/assets/admin.png')
                if not self.ui_admin_surf:
                    self.ui_admin_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
                    self.ui_admin_surf.fill((220, 220, 220, 255))
            pad2 = 6
            dest_w2 = max(1, self.ui_admin_rect.w - 2 * pad2)
            dest_h2 = max(1, self.ui_admin_rect.h - 2 * pad2)
            iw2, ih2 = self.ui_admin_surf.get_size()
            scale2 = min(dest_w2 / iw2, dest_h2 / ih2)
            scaled2 = pygame.transform.smoothscale(self.ui_admin_surf, (int(iw2 * scale2), int(ih2 * scale2)))
            dx2 = self.ui_admin_rect.x + (self.ui_admin_rect.w - scaled2.get_width()) // 2
            dy2 = self.ui_admin_rect.y + (self.ui_admin_rect.h - scaled2.get_height()) // 2
            self.screen.blit(scaled2, (dx2, dy2))
        if self.ui_show_spawn:
            mw, mh = self.ui_menu_rect.size
            header_h = getattr(self, 'ui_header_h', 36)
            shadow = pygame.Surface((mw, mh), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 100), pygame.Rect(0, 0, mw, mh), border_radius=10)
            self.screen.blit(shadow, (self.ui_menu_rect.x + 3, self.ui_menu_rect.y + 4))
            panel = pygame.Surface((mw, mh), pygame.SRCALPHA)
            pygame.draw.rect(panel, (0, 0, 0, 180), pygame.Rect(0, 0, mw, mh), border_radius=10)
            pygame.draw.rect(panel, (12, 12, 12, 210), pygame.Rect(0, 0, mw, header_h), border_radius=10)
            pygame.draw.rect(panel, (100, 100, 100, 220), pygame.Rect(0, 0, mw, mh), width=1, border_radius=10)
            pygame.draw.rect(panel, (255, 255, 255, 25), pygame.Rect(1, 1, mw - 2, mh - 2), width=1, border_radius=9)
            self.screen.blit(panel, self.ui_menu_rect.topleft)
            title_text = self.button_font.render('SPAWN', True, (220, 220, 220))
            ty = self.ui_menu_rect.y + (header_h - title_text.get_height()) // 2
            self.screen.blit(title_text, (self.ui_menu_rect.x + 12, ty))
            if hasattr(self, 'ui_search_rect'):
                sr = self.ui_search_rect
                pygame.draw.rect(self.screen, (30, 30, 30), sr, border_radius=6)
                pygame.draw.rect(self.screen, (70, 70, 70), sr, width=1, border_radius=6)
                q = self.ui_spawn_search_text or ''
                placeholder = 'Search'
                show_text = q if q else placeholder
                color = (220, 220, 220) if q else (150, 150, 150)
                ts = self.button_font.render(show_text, True, color)
                self.screen.blit(ts, (sr.x + 8, sr.y + (sr.h - ts.get_height()) // 2))
                if self.ui_search_active:
                    cx = sr.x + 8 + ts.get_width()
                    cy0 = sr.y + 5
                    cy1 = sr.y + sr.h - 5
                    pygame.draw.line(self.screen, (200, 200, 200), (cx, cy0), (cx, cy1), 1)
            mx, my = pygame.mouse.get_pos()
            for tile in getattr(self, 'ui_tiles', []):
                rect = self.ui_tile_rects.get(tile['key']) if hasattr(self, 'ui_tile_rects') else None
                if not rect:
                    continue
                hovered = rect.collidepoint(mx, my)
                tile_bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                base_alpha = 215 if hovered else 190
                if self.current_tool == tile['key']:
                    base_alpha = 230 if hovered else 210
                pygame.draw.rect(tile_bg, (25, 25, 25, base_alpha), pygame.Rect(0, 0, rect.w, rect.h), border_radius=8)
                self.screen.blit(tile_bg, rect.topleft)
                surf = tile.get('surf')
                if surf:
                    iw, ih = surf.get_size()
                    pad = 8
                    dw = max(1, rect.w - 2 * pad)
                    dh = max(1, rect.h - 2 * pad)
                    scale = min(dw / iw, dh / ih)
                    img = pygame.transform.smoothscale(surf, (int(iw * scale), int(ih * scale)))
                    dx = rect.x + (rect.w - img.get_width()) // 2
                    dy = rect.y + (rect.h - img.get_height()) // 2 - 6
                    self.screen.blit(img, (dx, dy))
                else:
                    ph = pygame.Surface((rect.w - 16, rect.h - 24), pygame.SRCALPHA)
                    ph.fill((*tile.get('color', (120, 120, 120)), 220))
                    px = rect.x + (rect.w - ph.get_width()) // 2
                    py = rect.y + (rect.h - ph.get_height()) // 2
                    self.screen.blit(ph, (px, py))
                label_surf = self.button_font.render(tile['label'], True, (210, 210, 210))
                lx = rect.x + (rect.w - label_surf.get_width()) // 2
                ly = rect.bottom - label_surf.get_height() - 6
                label_bg = pygame.Surface((label_surf.get_width() + 8, label_surf.get_height() + 4), pygame.SRCALPHA)
                label_bg.fill((0, 0, 0, 90))
                self.screen.blit(label_bg, (lx - 4, ly - 2))
                self.screen.blit(label_surf, (lx, ly))
        if getattr(self, 'ui_show_admin', False):
            amw, amh = self.ui_admin_menu_rect.size
            header_h = getattr(self, 'ui_header_h', 36)
            shadow = pygame.Surface((amw, amh), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 100), pygame.Rect(0, 0, amw, amh), border_radius=10)
            self.screen.blit(shadow, (self.ui_admin_menu_rect.x + 3, self.ui_admin_menu_rect.y + 4))
            panel = pygame.Surface((amw, amh), pygame.SRCALPHA)
            pygame.draw.rect(panel, (0, 0, 0, 180), pygame.Rect(0, 0, amw, amh), border_radius=10)
            pygame.draw.rect(panel, (12, 12, 12, 210), pygame.Rect(0, 0, amw, header_h), border_radius=10)
            pygame.draw.rect(panel, (100, 100, 100, 220), pygame.Rect(0, 0, amw, amh), width=1, border_radius=10)
            pygame.draw.rect(panel, (255, 255, 255, 25), pygame.Rect(1, 1, amw - 2, amh - 2), width=1, border_radius=9)
            self.screen.blit(panel, self.ui_admin_menu_rect.topleft)
            title_text = self.button_font.render('ADMIN', True, (220, 220, 220))
            ty = self.ui_admin_menu_rect.y + (header_h - title_text.get_height()) // 2
            self.screen.blit(title_text, (self.ui_admin_menu_rect.x + 12, ty))
            btn_w, btn_h = (amw - 32, 40)
            btn_x = self.ui_admin_menu_rect.x + 16
            btn_y1 = self.ui_admin_menu_rect.y + header_h + 20
            self.ui_admin_clear_rect = pygame.Rect(btn_x, btn_y1, btn_w, btn_h)
            hovered1 = self.ui_admin_clear_rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, (30, 30, 30), self.ui_admin_clear_rect, border_radius=8)
            if hovered1:
                pygame.draw.rect(self.screen, (60, 60, 60), self.ui_admin_clear_rect, 0, border_radius=8)
            label1 = self.button_font.render('CLEAR EVERYTHING', True, (220, 220, 220))
            lrx1 = self.ui_admin_clear_rect.x + (self.ui_admin_clear_rect.w - label1.get_width()) // 2
            lry1 = self.ui_admin_clear_rect.y + (self.ui_admin_clear_rect.h - label1.get_height()) // 2
            self.screen.blit(label1, (lrx1, lry1))
            btn_y2 = btn_y1 + btn_h + 12
            self.ui_admin_clear_npcs_rect = pygame.Rect(btn_x, btn_y2, btn_w, btn_h)
            hovered2 = self.ui_admin_clear_npcs_rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, (30, 30, 30), self.ui_admin_clear_npcs_rect, border_radius=8)
            if hovered2:
                pygame.draw.rect(self.screen, (60, 60, 60), self.ui_admin_clear_npcs_rect, 0, border_radius=8)
            label2 = self.button_font.render('CLEAR THE LIVING', True, (220, 220, 220))
            lrx2 = self.ui_admin_clear_npcs_rect.x + (self.ui_admin_clear_npcs_rect.w - label2.get_width()) // 2
            lry2 = self.ui_admin_clear_npcs_rect.y + (self.ui_admin_clear_npcs_rect.h - label2.get_height()) // 2
            self.screen.blit(label2, (lrx2, lry2))
            btn_y3 = btn_y2 + btn_h + 12
            self.ui_admin_clear_blocks_rect = pygame.Rect(btn_x, btn_y3, btn_w, btn_h)
            hovered3 = self.ui_admin_clear_blocks_rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(self.screen, (30, 30, 30), self.ui_admin_clear_blocks_rect, border_radius=8)
            if hovered3:
                pygame.draw.rect(self.screen, (60, 60, 60), self.ui_admin_clear_blocks_rect, 0, border_radius=8)
            label3 = self.button_font.render('CLEAR ALL BLOCKS', True, (220, 220, 220))
            lrx3 = self.ui_admin_clear_blocks_rect.x + (self.ui_admin_clear_blocks_rect.w - label3.get_width()) // 2
            lry3 = self.ui_admin_clear_blocks_rect.y + (self.ui_admin_clear_blocks_rect.h - label3.get_height()) // 2
            self.screen.blit(label3, (lrx3, lry3))
        if self.current_tool == 'blocks' and self.blocks_drag_active and self.blocks_drag_start and self.blocks_drag_current:
            sx, sy = self.blocks_drag_start
            cx, cy = self.blocks_drag_current
            v1x, v1y = self.camera.world_to_view(sx, sy)
            v2x, v2y = self.camera.world_to_view(cx, cy)
            x = self.sidebar_width + min(v1x, v2x)
            y = min(v1y, v2y)
            w = abs(v2x - v1x)
            h = abs(v2y - v1y)
            preview = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
            preview.fill((100, 150, 255, 50))
            self.screen.blit(preview, (x, y))
            pygame.draw.rect(self.screen, (100, 160, 255), pygame.Rect(x, y, w, h), 1)

    def _draw_overlays_gpu(self):
        self._ensure_ui_textures()
        self.renderer.draw_color = (0, 0, 0, 128)
        self.renderer.fill_rect(sdl2rect.Rect(self.ui_flask_rect.x, self.ui_flask_rect.y, self.ui_flask_rect.w, self.ui_flask_rect.h))
        self.renderer.draw_color = (90, 90, 90, 255)
        self.renderer.draw_rect(sdl2rect.Rect(self.ui_flask_rect.x, self.ui_flask_rect.y, self.ui_flask_rect.w, self.ui_flask_rect.h))
        iw, ih = (0, 0)
        if self.ui_flask_surf:
            iw, ih = self.ui_flask_surf.get_size()
        pad = 6
        dest_w = max(1, self.ui_flask_rect.w - 2 * pad)
        dest_h = max(1, self.ui_flask_rect.h - 2 * pad)
        scale = min(dest_w / (iw or 1), dest_h / (ih or 1))
        w = int((iw or 1) * scale)
        h = int((ih or 1) * scale)
        dx = self.ui_flask_rect.x + (self.ui_flask_rect.w - w) // 2
        dy = self.ui_flask_rect.y + (self.ui_flask_rect.h - h) // 2
        if self._ui_flask_tex:
            self.renderer.copy(self._ui_flask_tex, dstrect=sdl2rect.Rect(dx, dy, w, h))
        else:
            try:
                tmp_tex = Texture.from_surface(self.renderer, self.ui_flask_surf)
                self.renderer.copy(tmp_tex, dstrect=sdl2rect.Rect(dx, dy, w, h))
            except Exception:
                pass
        if hasattr(self, 'ui_admin_rect'):
            self.renderer.draw_color = (0, 0, 0, 128)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_admin_rect.x, self.ui_admin_rect.y, self.ui_admin_rect.w, self.ui_admin_rect.h))
            self.renderer.draw_color = (90, 90, 90, 255)
            self.renderer.draw_rect(sdl2rect.Rect(self.ui_admin_rect.x, self.ui_admin_rect.y, self.ui_admin_rect.w, self.ui_admin_rect.h))
            if self._ui_admin_tex is None:
                try:
                    if not hasattr(self, 'ui_admin_surf'):
                        self.ui_admin_surf = self._load_image('src/assets/admin.png')
                    if self.ui_admin_surf:
                        self._ui_admin_tex = Texture.from_surface(self.renderer, self.ui_admin_surf)
                except Exception:
                    self._ui_admin_tex = None
            iw2, ih2 = (0, 0)
            if hasattr(self, 'ui_admin_surf') and self.ui_admin_surf:
                iw2, ih2 = self.ui_admin_surf.get_size()
            pad2 = 6
            dest_w2 = max(1, self.ui_admin_rect.w - 2 * pad2)
            dest_h2 = max(1, self.ui_admin_rect.h - 2 * pad2)
            scale2 = min(dest_w2 / (iw2 or 1), dest_h2 / (ih2 or 1))
            w2 = int((iw2 or 1) * scale2)
            h2 = int((ih2 or 1) * scale2)
            dx2 = self.ui_admin_rect.x + (self.ui_admin_rect.w - w2) // 2
            dy2 = self.ui_admin_rect.y + (self.ui_admin_rect.h - h2) // 2
            if self._ui_admin_tex:
                self.renderer.copy(self._ui_admin_tex, dstrect=sdl2rect.Rect(dx2, dy2, w2, h2))
            elif hasattr(self, 'ui_admin_surf') and self.ui_admin_surf:
                try:
                    tmp2 = Texture.from_surface(self.renderer, self.ui_admin_surf)
                    self.renderer.copy(tmp2, dstrect=sdl2rect.Rect(dx2, dy2, w2, h2))
                except Exception:
                    pass
        if self.ui_show_spawn:
            header_h = getattr(self, 'ui_header_h', 36)
            self.renderer.draw_color = (0, 0, 0, 100)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_menu_rect.x + 3, self.ui_menu_rect.y + 4, self.ui_menu_rect.w, self.ui_menu_rect.h))
            self.renderer.draw_color = (0, 0, 0, 180)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_menu_rect.x, self.ui_menu_rect.y, self.ui_menu_rect.w, self.ui_menu_rect.h))
            self.renderer.draw_color = (12, 12, 12, 210)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_menu_rect.x, self.ui_menu_rect.y, self.ui_menu_rect.w, header_h))
            self.renderer.draw_color = (100, 100, 100, 255)
            self.renderer.draw_rect(sdl2rect.Rect(self.ui_menu_rect.x, self.ui_menu_rect.y, self.ui_menu_rect.w, self.ui_menu_rect.h))
            title = 'SPAWN'
            title_tex = self._get_text_texture(title, (220, 220, 220))
            title_surf = self.button_font.render(title, True, (220, 220, 220))
            ty = self.ui_menu_rect.y + (header_h - title_surf.get_height()) // 2
            self.renderer.copy(title_tex, dstrect=sdl2rect.Rect(self.ui_menu_rect.x + 12, ty, title_surf.get_width(), title_surf.get_height()))
            if hasattr(self, 'ui_search_rect'):
                sr = self.ui_search_rect
                self.renderer.draw_color = (30, 30, 30, 255)
                self.renderer.fill_rect(sdl2rect.Rect(sr.x, sr.y, sr.w, sr.h))
                self.renderer.draw_color = (70, 70, 70, 255)
                self.renderer.draw_rect(sdl2rect.Rect(sr.x, sr.y, sr.w, sr.h))
                q = self.ui_spawn_search_text or ''
                placeholder = 'Search'
                show_text = q if q else placeholder
                color = (220, 220, 220) if q else (150, 150, 150)
                ts = self.button_font.render(show_text, True, color)
                tex = self._get_text_texture(show_text, color)
                tx = sr.x + 8
                ty2 = sr.y + (sr.h - ts.get_height()) // 2
                self.renderer.copy(tex, dstrect=sdl2rect.Rect(tx, ty2, ts.get_width(), ts.get_height()))
                if self.ui_search_active:
                    cx = tx + ts.get_width()
                    self.renderer.draw_color = (200, 200, 200, 255)
                    self.renderer.draw_line((cx, sr.y + 5), (cx, sr.y + sr.h - 5))
            mx, my = pygame.mouse.get_pos()
            for tile in getattr(self, 'ui_tiles', []):
                rect = self.ui_tile_rects.get(tile['key']) if hasattr(self, 'ui_tile_rects') else None
                if not rect:
                    continue
                hovered = rect.collidepoint(mx, my)
                alpha = 215 if hovered else 185
                if self.current_tool == tile['key']:
                    alpha = 230 if hovered else 205
                self.renderer.draw_color = (25, 25, 25, alpha)
                self.renderer.fill_rect(sdl2rect.Rect(rect.x, rect.y, rect.w, rect.h))
                surf = tile.get('surf')
                if surf is not None:
                    iw, ih = surf.get_size()
                    pad = 8
                    dest_w = max(1, rect.w - 2 * pad)
                    dest_h = max(1, rect.h - 2 * pad)
                    scale = min(dest_w / (iw or 1), dest_h / (ih or 1))
                    w = int((iw or 1) * scale)
                    h = int((ih or 1) * scale)
                    dx = rect.x + (rect.w - w) // 2
                    dy = rect.y + (rect.h - h) // 2
                    tex = None
                    if tile['key'] == 'water':
                        tex = self._ui_water_tex
                    elif tile['key'] == 'sand':
                        tex = self._ui_sand_tex
                    elif tile['key'] == 'oil':
                        tex = self._ui_oil_tex
                    elif tile['key'] == 'lava':
                        tex = self._ui_lava_tex
                    elif tile['key'] == 'npc':
                        tex = self._ui_npc_tex
                    elif tile['key'] == 'toxic':
                        tex = self._ui_toxic_tex
                    elif tile['key'] == 'blocks':
                        tex = self._ui_blocks_tex
                    if tex:
                        self.renderer.copy(tex, dstrect=sdl2rect.Rect(dx, dy, w, h))
                    else:
                        try:
                            tmp_tex = Texture.from_surface(self.renderer, surf)
                            self.renderer.copy(tmp_tex, dstrect=sdl2rect.Rect(dx, dy, w, h))
                        except Exception:
                            pass
                else:
                    self.renderer.draw_color = (tile.get('color', (120, 120, 120))[0], tile.get('color', (120, 120, 120))[1], tile.get('color', (120, 120, 120))[2], 220)
                    inset = 8
                    self.renderer.fill_rect(sdl2rect.Rect(rect.x + inset, rect.y + inset, max(0, rect.w - 2 * inset), max(0, rect.h - 2 * inset)))
                lbl = tile['label']
                label_surf = self.button_font.render(lbl, True, (210, 210, 210))
                label_tex = self._get_text_texture(lbl, (210, 210, 210))
                lx = rect.x + (rect.w - label_surf.get_width()) // 2
                ly = rect.bottom - label_surf.get_height() - 6
                self.renderer.draw_color = (0, 0, 0, 90)
                self.renderer.fill_rect(sdl2rect.Rect(lx - 4, ly - 2, label_surf.get_width() + 8, label_surf.get_height() + 4))
                self.renderer.copy(label_tex, dstrect=sdl2rect.Rect(lx, ly, label_surf.get_width(), label_surf.get_height()))
        if getattr(self, 'ui_show_admin', False) and hasattr(self, 'ui_admin_menu_rect'):
            header_h = getattr(self, 'ui_header_h', 36)
            self.renderer.draw_color = (0, 0, 0, 100)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_admin_menu_rect.x + 3, self.ui_admin_menu_rect.y + 4, self.ui_admin_menu_rect.w, self.ui_admin_menu_rect.h))
            self.renderer.draw_color = (0, 0, 0, 180)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_admin_menu_rect.x, self.ui_admin_menu_rect.y, self.ui_admin_menu_rect.w, self.ui_admin_menu_rect.h))
            self.renderer.draw_color = (12, 12, 12, 210)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_admin_menu_rect.x, self.ui_admin_menu_rect.y, self.ui_admin_menu_rect.w, header_h))
            self.renderer.draw_color = (100, 100, 100, 255)
            self.renderer.draw_rect(sdl2rect.Rect(self.ui_admin_menu_rect.x, self.ui_admin_menu_rect.y, self.ui_admin_menu_rect.w, self.ui_admin_menu_rect.h))
            title = 'ADMIN'
            title_tex = self._get_text_texture(title, (220, 220, 220))
            title_surf = self.button_font.render(title, True, (220, 220, 220))
            ty = self.ui_admin_menu_rect.y + (header_h - title_surf.get_height()) // 2
            self.renderer.copy(title_tex, dstrect=sdl2rect.Rect(self.ui_admin_menu_rect.x + 12, ty, title_surf.get_width(), title_surf.get_height()))
            btn_w, btn_h = (self.ui_admin_menu_rect.w - 32, 40)
            btn_x = self.ui_admin_menu_rect.x + 16
            btn_y1 = self.ui_admin_menu_rect.y + header_h + 20
            self.ui_admin_clear_rect = pygame.Rect(btn_x, btn_y1, btn_w, btn_h)
            self.renderer.draw_color = (30, 30, 30, 255)
            self.renderer.fill_rect(sdl2rect.Rect(btn_x, btn_y1, btn_w, btn_h))
            lbl1 = 'CLEAR EVERYTHING'
            lbl1_surf = self.button_font.render(lbl1, True, (220, 220, 220))
            lbl1_tex = self._get_text_texture(lbl1, (220, 220, 220))
            lrx1 = btn_x + (btn_w - lbl1_surf.get_width()) // 2
            lry1 = btn_y1 + (btn_h - lbl1_surf.get_height()) // 2
            self.renderer.copy(lbl1_tex, dstrect=sdl2rect.Rect(lrx1, lry1, lbl1_surf.get_width(), lbl1_surf.get_height()))
            btn_y2 = btn_y1 + btn_h + 12
            self.ui_admin_clear_npcs_rect = pygame.Rect(btn_x, btn_y2, btn_w, btn_h)
            self.renderer.draw_color = (30, 30, 30, 255)
            self.renderer.fill_rect(sdl2rect.Rect(btn_x, btn_y2, btn_w, btn_h))
            lbl2 = 'CLEAR THE LIVING'
            lbl2_surf = self.button_font.render(lbl2, True, (220, 220, 220))
            lbl2_tex = self._get_text_texture(lbl2, (220, 220, 220))
            lrx2 = btn_x + (btn_w - lbl2_surf.get_width()) // 2
            lry2 = btn_y2 + (btn_h - lbl2_surf.get_height()) // 2
            self.renderer.copy(lbl2_tex, dstrect=sdl2rect.Rect(lrx2, lry2, lbl2_surf.get_width(), lbl2_surf.get_height()))
            btn_y3 = btn_y2 + btn_h + 12
            self.ui_admin_clear_blocks_rect = pygame.Rect(btn_x, btn_y3, btn_w, btn_h)
            self.renderer.draw_color = (30, 30, 30, 255)
            self.renderer.fill_rect(sdl2rect.Rect(btn_x, btn_y3, btn_w, btn_h))
            lbl3 = 'CLEAR ALL BLOCKS'
            lbl3_surf = self.button_font.render(lbl3, True, (220, 220, 220))
            lbl3_tex = self._get_text_texture(lbl3, (220, 220, 220))
            lrx3 = btn_x + (btn_w - lbl3_surf.get_width()) // 2
            lry3 = btn_y3 + (btn_h - lbl3_surf.get_height()) // 2
            self.renderer.copy(lbl3_tex, dstrect=sdl2rect.Rect(lrx3, lry3, lbl3_surf.get_width(), lbl3_surf.get_height()))
        if self.current_tool == 'blocks' and self.blocks_drag_active and self.blocks_drag_start and self.blocks_drag_current:
            sx, sy = self.blocks_drag_start
            cx, cy = self.blocks_drag_current
            v1x, v1y = self.camera.world_to_view(sx, sy)
            v2x, v2y = self.camera.world_to_view(cx, cy)
            x = self.sidebar_width + min(v1x, v2x)
            y = min(v1y, v2y)
            w = abs(v2x - v1x)
            h = abs(v2y - v1y)
            self.renderer.draw_color = (100, 160, 255, 255)
            self.renderer.draw_rect(sdl2rect.Rect(x, y, w, h))

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self._poll_size_change()
            if not self.ready and self._bench_done:
                self.opt = self._bench_cfg or {}
                pref = str(self.user_settings.get('renderer', 'Auto')).lower() if hasattr(self, 'user_settings') else 'auto'
                if pref == 'cpu':
                    self.use_gpu = False
                elif pref == 'gpu':
                    self.use_gpu = bool(GPU_AVAILABLE)
                else:
                    self.use_gpu = bool(self.opt.get('use_gpu', GPU_AVAILABLE) and GPU_AVAILABLE)
                self.target_fps = int(self.opt.get('target_fps', 60))
                self.max_particles = int(self.opt.get('max_particles', 50000))
                if self.use_gpu:
                    try:
                        pygame.display.quit()
                    except Exception:
                        pass
                    self.window = Window('Dustground', size=(self.width, self.height))
                    try:
                        self.window.resizable = True
                    except Exception:
                        pass
                    self.renderer = Renderer(self.window, vsync=True)
                    self._text_cache = {}
                elif not pygame.display.get_init():
                    pygame.display.init()
                    self.screen = pygame.display.set_mode((self.width, self.height), pygame.SCALED | pygame.DOUBLEBUF)
                    pygame.display.set_caption('Dustground')
                self.ready = True
            self.update()
            self.draw()
            self.clock.tick(self.target_fps)
            self.fps = int(self.clock.get_fps())
            if self._fps_avg <= 0:
                self._fps_avg = float(self.fps)
            else:
                self._fps_avg = self._fps_avg * 0.9 + self.fps * 0.1
            self._frame_index += 1

def main():
    game = ParticleGame()
    game.run()
    try:
        dg_discord.shutdown()
    except Exception:
        pass
    pygame.quit()
    sys.exit()
if __name__ == '__main__':
    main()
