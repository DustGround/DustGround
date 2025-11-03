import pygame
import sys
import threading
import time
from pathlib import Path
from typing import Tuple, Dict, List, Tuple as Tup
from src.sand import SandSystem, SandParticle
from src.water import WaterSystem, WaterParticle
from src.lava import LavaSystem, LavaParticle
from src.toxic import ToxicSystem
from src.blood import BloodSystem
from src.npc import NPC
from src.opt import get_or_create_optimizations
from src.scaling import recommend_settings
from src.zoom import Camera

# Detect GPU API availability once; the decision to USE it is based on benchmark config
GPU_AVAILABLE = False
try:
    from pygame._sdl2.video import Window, Renderer, Texture
    from pygame._sdl2 import rect as sdl2rect
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False


class ParticleGame:
    """Main game class for the 2D particle physics simulation"""
    
    def __init__(self, width: int = 1200, height: int = 800):
        pygame.init()

        self.width = width
        self.height = height
        # No sidebar; full width is game area
        self.sidebar_width = 0
        self.game_width = width

        # Show black CPU window immediately
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE | pygame.DOUBLEBUF)
        pygame.display.set_caption("Particle Physics Playground")

        # Defer benchmark and final renderer selection to background thread
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
        
        # Particle systems
        self.sand_system = SandSystem(self.game_width, height)
        self.water_system = WaterSystem(self.game_width, height)
        self.lava_system = LavaSystem(self.game_width, height)
        self.toxic_system = ToxicSystem(self.game_width, height)
        self.blood_system = BloodSystem(self.game_width, height)
        # Camera for pan/zoom inside game area
        self.camera = Camera(world_w=self.game_width, world_h=self.height, view_w=self.game_width, view_h=self.height)
        
        # Current tool selection
        self.current_tool = "sand"  # "sand" or "water"
        self.brush_size = 5
        self.is_drawing = False
        
        # Overlay UI (no sidebar)
        self.buttons = {}
        self.ui_show_spawn = False
        # Tunable overlay sizes
        self.ui_icon_size = 56
        # Bigger spawn menu by default
        self.ui_menu_size = (460, 340)  # width, height
        # Header height for the spawn menu (used by layout and drawing)
        self.ui_header_h = 36
        # Grid columns for spawn tiles (horizontal row)
        self.ui_grid_cols = 4
        # Load UI images (robust path resolution)
        self.ui_flask_surf = self._load_image("src/assets/flask.png")
        if not self.ui_flask_surf:
            self.ui_flask_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.ui_flask_surf.fill((220, 220, 220, 255))
        self.ui_water_surf = self._load_image("src/assets/water.png")
        if not self.ui_water_surf:
            self.ui_water_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_water_surf.fill((80, 140, 255, 255))
        # Sand icon (now with image support)
        self.ui_sand_surf = self._load_image("src/assets/Sand.png")
        if not self.ui_sand_surf:
            self.ui_sand_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_sand_surf.fill((200, 180, 120, 255))
        # Lava icon
        self.ui_lava_surf = self._load_image("src/assets/Lava.png")
        if not self.ui_lava_surf:
            self.ui_lava_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_lava_surf.fill((255, 120, 60, 255))
        # NPC icon
        self.ui_npc_surf = self._load_image("src/assets/npc.png")
        if not self.ui_npc_surf:
            self.ui_npc_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_npc_surf.fill((180, 180, 200, 255))
        # Toxic waste icon
        self.ui_toxic_surf = self._load_image("src/assets/ToxicWaste.png")
        if not self.ui_toxic_surf:
            self.ui_toxic_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.ui_toxic_surf.fill((90, 220, 90, 255))
        self._ui_flask_tex = None
        self._ui_water_tex = None
        self._ui_sand_tex = None
        self._ui_lava_tex = None
        self._ui_npc_tex = None
        self._ui_toxic_tex = None

        # Spawn menu tiles definition (order matters)
        # For now we have an image only for water; others will render as colored tiles with labels
        self.ui_tiles = [
            {"key": "sand", "label": "SAND", "color": (200, 180, 120), "surf": self.ui_sand_surf},
            {"key": "water", "label": "WATER", "color": (80, 140, 255), "surf": self.ui_water_surf},
            {"key": "lava", "label": "LAVA", "color": (255, 120, 60), "surf": self.ui_lava_surf},
            {"key": "toxic", "label": "TOXIC", "color": (90, 220, 90), "surf": self.ui_toxic_surf},
            {"key": "npc", "label": "NPC", "color": (180, 180, 200), "surf": self.ui_npc_surf},
        ]
        self.ui_tile_rects = {}
        # Keep a single horizontal row across all tiles
        self.ui_grid_cols = len(self.ui_tiles)
        # Recompute layout now that tiles are defined
        self._layout_overlay_ui()
        
        # FPS tracking and HUD cache
        self.fps = 0
        self._stats_cache_tex = None
        self._stats_cache_surf = None
        self._stats_updated_at = 0.0
        self._game_surface = None
        self._frame_index = 0
        self._fps_avg = 0.0
        self._last_scale_apply = 0
        self._prev_mouse = None
        # NPC state (spawn on demand)
        self.npc = None
        self.npc_drag_index = None
        # Panning state
        self._pan_active = False
        self._pan_prev = None

    def _get_text_texture(self, text: str, color: Tup[int, int, int]) -> "Texture":
        """Cache and return a Texture for text rendering in GPU mode."""
        key = (text, color)
        if key in getattr(self, "_text_cache", {}):
            return self._text_cache[key]
        surf = self.button_font.render(text, True, color)
        tex = Texture.from_surface(self.renderer, surf)
        self._text_cache[key] = tex
        return tex

    def _load_image(self, rel_path: str):
        """Load an image robustly from several candidate locations.
        Returns a Surface with per-pixel alpha or None on failure.
        """
        candidates = [
            Path(rel_path),
            Path(__file__).resolve().parent / rel_path,
            Path(__file__).resolve().parent / rel_path.lstrip("./"),
        ]
        # Direct exact-path attempts first (fast path)
        for p in candidates:
            try:
                if p.is_file():
                    return pygame.image.load(str(p)).convert_alpha()
            except Exception:
                continue

        # Case-insensitive fallback: search in candidate directories for a filename match ignoring case
        try:
            target = Path(rel_path).name.lower()
            dir_candidates = []
            # Direct parent (relative to CWD)
            pr = Path(rel_path)
            dir_candidates.append(pr if pr.is_dir() else pr.parent)
            # Parent relative to this file's directory
            dir_candidates.append((Path(__file__).resolve().parent / (pr if pr.is_dir() else pr.parent)))
            # Also include explicit src/assets under this file if rel_path points there
            dir_candidates.append(Path(__file__).resolve().parent / "src" / "assets")

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

        # Last resort: try pygame's default loader with given path
        try:
            return pygame.image.load(rel_path).convert_alpha()
        except Exception:
            return None

    def _layout_overlay_ui(self):
        # Icon at top-left
        self.ui_flask_rect = pygame.Rect(10, 10, self.ui_icon_size, self.ui_icon_size)
        # Menu to the right of icon
        mw, mh = self.ui_menu_size
        self.ui_menu_rect = pygame.Rect(self.ui_flask_rect.right + 10, 10, mw, mh)
        # Compute grid for tiles
        gpad = 16
        gap = 12
        header_h = getattr(self, 'ui_header_h', 36)
        area_x = self.ui_menu_rect.x + gpad
        area_y = self.ui_menu_rect.y + header_h + gpad
        area_w = mw - 2 * gpad
        area_h = mh - header_h - 2 * gpad - 20  # reserve some space for labels

        cols = max(1, int(getattr(self, 'ui_grid_cols', 2)))
        rows = max(1, (len(getattr(self, 'ui_tiles', [])) + cols - 1) // cols)
        # Prefer compact tiles; clamp to avoid oversized visuals
        tile_w_avail = max(1, (area_w - (cols - 1) * gap) // cols)
        tile_h_avail = max(1, (area_h - (rows - 1) * gap) // rows)
        tile_w = max(64, min(90, tile_w_avail))
        tile_h = max(64, min(96, tile_h_avail))

        # Build rects per tile in order
        self.ui_tile_rects = {}
        for idx, tile in enumerate(getattr(self, 'ui_tiles', [])):
            r = idx // cols
            c = idx % cols
            x = area_x + c * (tile_w + gap)
            y = area_y + r * (tile_h + gap)
            self.ui_tile_rects[tile["key"]] = pygame.Rect(x, y, tile_w, tile_h)
        
    def handle_events(self) -> bool:
        """Handle pygame events. Returns False if game should quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            # Handle window resize for both CPU and GPU paths
            elif event.type == pygame.VIDEORESIZE:
                self._apply_resize(event.w, event.h)
            # Some platforms don't emit VIDEORESIZE reliably; we'll also poll size changes each frame
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    mx, my = event.pos
                    # UI clicks first
                    if self.ui_flask_rect.collidepoint(mx, my):
                        self.ui_show_spawn = not self.ui_show_spawn
                        continue
                    if self.ui_show_spawn and self.ui_menu_rect.collidepoint(mx, my):
                        # Handle clicks on any tile
                        for key, rect in getattr(self, 'ui_tile_rects', {}).items():
                            if rect.collidepoint(mx, my):
                                # Only allow known tools (blood is hazard-only, not paintable)
                                if key in ("sand", "water", "lava", "toxic", "npc"):
                                    self.current_tool = key
                                break
                        continue
                    # If NPC tool active, start dragging nearest body part in game area
                    if self.current_tool == "npc":
                        if mx >= self.sidebar_width:
                            vx = mx - self.sidebar_width
                            gx, gy = self.camera.view_to_world(vx, my)
                            # Spawn on first click if NPC doesn't exist
                            if self.npc is None:
                                self.npc = NPC(gx, gy)
                                self.npc_drag_index = self.npc.nearest_particle_index((gx, gy))
                                self.npc.set_user_dragging(True)
                                self.is_drawing = True
                            else:
                                self.npc_drag_index = self.npc.nearest_particle_index((gx, gy))
                                self.npc.set_user_dragging(True)
                                self.is_drawing = True
                    else:
                        self.is_drawing = True
                elif event.button == 3:  # Right click starts panning
                    mx, my = event.pos
                    if not (self.ui_flask_rect.collidepoint(mx, my) or (self.ui_show_spawn and self.ui_menu_rect.collidepoint(mx, my))):
                        self._pan_active = True
                        self._pan_prev = (mx, my)
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.is_drawing = False
                    if self.current_tool == "npc":
                        self.npc_drag_index = None
                        if self.npc:
                            self.npc.set_user_dragging(False)
                elif event.button == 3:
                    self._pan_active = False
                    self._pan_prev = None

            elif event.type == pygame.MOUSEMOTION:
                if self._pan_active and self._pan_prev is not None:
                    mx, my = event.pos
                    pmx, pmy = self._pan_prev
                    dx = mx - pmx
                    dy = my - pmy
                    # Pan opposite to drag for natural feel
                    self.camera.pan_by(-dx, -dy)
                    self._pan_prev = (mx, my)
                    
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                # Zoom controls when holding CTRL
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_CTRL:
                    mx, my = pygame.mouse.get_pos()
                    if mx >= self.sidebar_width:
                        vx = mx - self.sidebar_width
                        # Plus (main) or equals (often shift+'+') or keypad plus
                        if event.key in (getattr(pygame, 'K_PLUS', pygame.K_EQUALS), pygame.K_EQUALS, pygame.K_KP_PLUS):
                            self.camera.zoom_at(1.1, vx, my)
                        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                            self.camera.zoom_at(1.0/1.1, vx, my)
                elif event.key == pygame.K_UP:
                    self.brush_size = min(20, self.brush_size + 1)
                elif event.key == pygame.K_DOWN:
                    self.brush_size = max(1, self.brush_size - 1)
        
        return True
    
    def _handle_sidebar_click(self, pos: Tuple[int, int]) -> bool:
        """Handle clicks on sidebar buttons. Returns True if a button was clicked."""
        x, y = pos
        
        # Only handle clicks in sidebar area
        if x >= self.sidebar_width:
            return False
        
        if self.buttons["sand"].collidepoint(pos):
            self.current_tool = "sand"
            return True
        elif self.buttons["water"].collidepoint(pos):
            self.current_tool = "water"
            return True
        elif self.buttons.get("lava") and self.buttons["lava"].collidepoint(pos):
            self.current_tool = "lava"
            return True
        elif self.buttons.get("npc") and self.buttons["npc"].collidepoint(pos):
            self.current_tool = "npc"
            return True
        elif self.buttons["clear"].collidepoint(pos):
            self.sand_system.clear()
            self.water_system.clear()
            # Also remove NPC if present
            self.npc = None
            self.npc_drag_index = None
            return True
        
        return False

    def _compute_sidebar_width(self, w: int) -> int:
        # Sidebar scales with window width, clamped to a sensible range
        return int(max(120, min(260, w * 0.18)))

    def _layout_ui(self):
        # Layout buttons to fit current sidebar width
        margin = 10
        bw = max(100, self.sidebar_width - margin * 2)
        bh = 40
        y = 20
        self.buttons = {
            "sand": pygame.Rect(margin, y, bw, bh),
            "water": pygame.Rect(margin, y + 50, bw, bh),
            "lava": pygame.Rect(margin, y + 100, bw, bh),
            "npc": pygame.Rect(margin, y + 150, bw, bh),
            "clear": pygame.Rect(margin, y + 200, bw, bh),
        }

    def _apply_resize(self, new_w: int, new_h: int):
        # Update sizes
        self.width = int(max(400, new_w))
        self.height = int(max(300, new_h))
        self.sidebar_width = 0
        self.game_width = self.width
        # Update systems' bounds
        self.sand_system.width = self.game_width
        self.sand_system.height = self.height
        self.water_system.width = self.game_width
        self.water_system.height = self.height
        self.lava_system.width = self.game_width
        self.lava_system.height = self.height
        if hasattr(self, 'toxic_system'):
            self.toxic_system.width = self.game_width
            self.toxic_system.height = self.height
        if hasattr(self, 'blood_system'):
            self.blood_system.width = self.game_width
            self.blood_system.height = self.height
        # Recompute overlay layout
        if hasattr(self, '_layout_overlay_ui'):
            self._layout_overlay_ui()
        # Update camera bounds and view
        if hasattr(self, 'camera') and self.camera:
            self.camera.update_view(self.game_width, self.height, self.game_width, self.height)
        # Invalidate CPU game surface (recreated lazily)
        self._game_surface = None
        # Resize window for CPU path
        if (not self.use_gpu):
            flags = pygame.RESIZABLE | pygame.DOUBLEBUF
            pygame.display.set_mode((self.width, self.height), flags)
        else:
            # Ensure SDL2 Window is resizable and sized
            try:
                if hasattr(self, 'window'):
                    self.window.resizable = True
                    self.window.size = (self.width, self.height)
            except Exception:
                pass

    def _poll_size_change(self):
        """Poll current window size and apply if it changed (platform-agnostic)."""
        try:
            if self.use_gpu and hasattr(self, 'window'):
                w, h = self.window.size
            else:
                surf = pygame.display.get_surface()
                if not surf:
                    return
                w, h = surf.get_size()
            if (int(w) != self.width) or (int(h) != self.height):
                self._apply_resize(int(w), int(h))
        except Exception:
            pass
    
    def _draw_on_canvas(self):
        """Draw particles when mouse is pressed"""
        if not self.is_drawing:
            return
        
        mouse_x, mouse_y = pygame.mouse.get_pos()
        
        # Block drawing when cursor over overlay UI
        if self.ui_flask_rect.collidepoint(mouse_x, mouse_y) or (self.ui_show_spawn and self.ui_menu_rect.collidepoint(mouse_x, mouse_y)):
            return
        
        # Adjust coordinates to game view then world space (camera aware)
        view_x = mouse_x - self.sidebar_width
        game_x, game_y = self.camera.view_to_world(view_x, mouse_y)
        
        # enforce particle cap
        total = (
            self.sand_system.get_particle_count()
            + self.water_system.get_particle_count()
            + self.lava_system.get_particle_count()
            + self.toxic_system.get_particle_count()
            + self.blood_system.get_particle_count()
        )
        if total >= self.max_particles:
            # Still allow NPC dragging when at cap
            if self.current_tool != "npc":
                return

        if self.current_tool == "sand":
            self.sand_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
        elif self.current_tool == "water":
            self.water_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
        elif self.current_tool == "lava":
            self.lava_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
        elif self.current_tool == "toxic":
            self.toxic_system.add_particle_cluster(int(game_x), int(game_y), self.brush_size)
        elif self.current_tool == "npc":
            # Drag current selected NPC particle to cursor
            if self.npc is not None and self.npc_drag_index is not None:
                p = self.npc.particles[self.npc_drag_index]
                p.pos[0] = float(game_x)
                p.pos[1] = float(game_y)
                p.prev[0] = float(game_x)
                p.prev[1] = float(game_y)
    
    def _handle_cross_material_collisions(self):
        """Handle collisions between materials (sand, water, lava)."""
        # Grids were rebuilt during each system update; avoid extra rebuild here
        MAX_NEIGHBORS = 12
        # Water vs Sand: wet sand and exchange momentum
        for water in self.water_system.particles:
            sand_neighbors = self._get_nearby_sand(water.x, water.y, radius=2)
            if len(sand_neighbors) > MAX_NEIGHBORS:
                sand_neighbors = sand_neighbors[:MAX_NEIGHBORS]
            
            for sand in sand_neighbors:
                dx = sand.x - water.x
                dy = sand.y - water.y
                dist = (dx*dx + dy*dy) ** 0.5
                
                if dist < 2.5 and dist > 0.1:
                    # Mark sand as wet
                    sand.wet = True
                    
                    # Water pushes sand slightly
                    nx = dx / dist if dist > 0 else 0
                    ny = dy / dist if dist > 0 else 1
                    
                    sand.vx += nx * 0.15
                    sand.vy += ny * 0.15
                    
                    # Sand creates drag on water
                    water.vx -= nx * 0.1
                    water.vy -= ny * 0.1

        # Lava interactions: lava destroys nearby sand/water
        # Build removal sets and sweep afterwards
        sand_kill = set()
        water_kill = set()
        for lava in self.lava_system.particles:
            # Against sand
            sands = self._get_nearby_sand(lava.x, lava.y, radius=2)
            if len(sands) > MAX_NEIGHBORS:
                sands = sands[:MAX_NEIGHBORS]
            for s in sands:
                dx = s.x - lava.x
                dy = s.y - lava.y
                d2 = dx*dx + dy*dy
                if 0.01 < d2 < 2.5*2.5:
                    sand_kill.add(id(s))
                    # small reaction to lava
                    d = d2 ** 0.5
                    nx, ny = dx/d, dy/d
                    lava.vx -= nx * 0.05
                    lava.vy -= ny * 0.05
            # Against water
            waters = self._get_nearby_water(lava.x, lava.y, radius=2)
            if len(waters) > MAX_NEIGHBORS:
                waters = waters[:MAX_NEIGHBORS]
            for w in waters:
                dx = w.x - lava.x
                dy = w.y - lava.y
                d2 = dx*dx + dy*dy
                if 0.01 < d2 < 2.5*2.5:
                    water_kill.add(id(w))
                    d = d2 ** 0.5
                    nx, ny = dx/d, dy/d
                    lava.vx -= nx * 0.03
                    lava.vy -= ny * 0.03

        # Sweep dead sand/water
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
    
    def _get_nearby_sand(self, x: float, y: float, radius: int = 2) -> list:
        """Get sand particles near a position"""
        cell_x, cell_y = int(x // self.sand_system.cell_size), int(y // self.sand_system.cell_size)
        nearby = []
        
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.sand_system.grid:
                    nearby.extend(self.sand_system.grid[cell])
        
        return nearby

    def _get_nearby_water(self, x: float, y: float, radius: int = 2) -> list:
        """Get water particles near a position"""
        cell_x, cell_y = int(x // self.water_system.cell_size), int(y // self.water_system.cell_size)
        nearby = []

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.water_system.grid:
                    nearby.extend(self.water_system.grid[cell])
        return nearby

    def _get_nearby_lava(self, x: float, y: float, radius: int = 2) -> list:
        """Get lava particles near a position"""
        cell_x, cell_y = int(x // self.lava_system.cell_size), int(y // self.lava_system.cell_size)
        nearby = []

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.lava_system.grid:
                    nearby.extend(self.lava_system.grid[cell])
        return nearby

    def _get_nearby_toxic(self, x: float, y: float, radius: int = 2) -> list:
        """Get toxic particles near a position"""
        cell_x, cell_y = int(x // self.toxic_system.cell_size), int(y // self.toxic_system.cell_size)
        nearby = []

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.toxic_system.grid:
                    nearby.extend(self.toxic_system.grid[cell])
        return nearby

    def _npc_particle_coupling(self):
        """Gently couple NPC body parts with nearby particles: push particles away and apply a tiny reaction to NPC."""
        # Assume grids are up-to-date from the latest system.update calls.
        if not self.npc or (not self.sand_system.particles and not self.water_system.particles):
            return

        push_radius = 8.0
        push_r2 = push_radius * push_radius
        sand_push = 0.2
        water_push = 0.25
        npc_react = 0.04
        radius_cells = 2
        max_neighbors = 10

        for p in self.npc.particles:
            px, py = p.pos
            # Sand neighbors
            sands = self._get_nearby_sand(px, py, radius=radius_cells)
            if len(sands) > max_neighbors:
                sands = sands[:max_neighbors]
            for s in sands:
                dx = s.x - px
                dy = s.y - py
                d2 = dx*dx + dy*dy
                if d2 > push_r2 or d2 <= 0.0001:
                    continue
                d = d2 ** 0.5
                nx = dx / d
                ny = dy / d
                s.vx += nx * sand_push
                s.vy += ny * sand_push
                # Reaction on NPC
                p.pos[0] -= nx * npc_react
                p.pos[1] -= ny * npc_react

            # Water neighbors
            waters = self._get_nearby_water(px, py, radius=radius_cells)
            if len(waters) > max_neighbors:
                waters = waters[:max_neighbors]
            for w in waters:
                dx = w.x - px
                dy = w.y - py
                d2 = dx*dx + dy*dy
                if d2 > push_r2 or d2 <= 0.0001:
                    continue
                d = d2 ** 0.5
                nx = dx / d
                ny = dy / d
                w.vx += nx * water_push
                w.vy += ny * water_push
                # Reaction on NPC
                p.pos[0] -= nx * npc_react
                p.pos[1] -= ny * npc_react

    def _apply_cursor_interaction(self):
        """Apply a gentle push to particles under the mouse, based on cursor movement.
        Works without clicking—just moving the cursor through particles moves them.
        """
        # Mouse position
        mx, my = pygame.mouse.get_pos()
        # Skip when hovering overlay UI
        if self.ui_flask_rect.collidepoint(mx, my) or (self.ui_show_spawn and self.ui_menu_rect.collidepoint(mx, my)):
            self._prev_mouse = (mx, my)
            return
        # Update previous mouse storage
        if self._prev_mouse is None:
            self._prev_mouse = (mx, my)
            return

        # Don't interact in the sidebar or while loading
        if (not self.ready) or (mx < self.sidebar_width):
            self._prev_mouse = (mx, my)
            return

        # Convert to game view then to world coords (camera-aware)
        gvx = mx - self.sidebar_width
        gvy = my
        gx, gy = self.camera.view_to_world(gvx, gvy)

        # Movement delta in world units (account for zoom)
        pmx, pmy = self._prev_mouse
        dx = (mx - pmx) / max(self.camera.scale, 1e-6)
        dy = (my - pmy) / max(self.camera.scale, 1e-6)
        self._prev_mouse = (mx, my)

        # If barely moving, still allow a slight outward nudge
        moved = (dx*dx + dy*dy) ** 0.5
        if moved < 0.1:
            dx = 0.0
            dy = 0.0

        # Rebuild grids once for fresh neighborhood queries
        self.sand_system._rebuild_grid()
        self.water_system._rebuild_grid()

        # Influence radius and strength
        radius_cells = 2  # search 2x cells around
        push_radius = 10  # pixel radius for outward nudge
        move_strength_sand = 0.15
        move_strength_water = 0.25
        outward_strength = 0.12

        # Sand neighbors
        sand_neighbors = self._get_nearby_sand(gx, gy, radius=radius_cells)
        for s in sand_neighbors:
            # Check within pixel radius for outward component
            ox = s.x - gx
            oy = s.y - gy
            dist2 = ox*ox + oy*oy
            if dist2 <= push_radius*push_radius:
                d = dist2 ** 0.5 if dist2 > 0 else 0.01
                nx = ox / d
                ny = oy / d
                s.vx += -nx * outward_strength
                s.vy += -ny * outward_strength
            # Add movement-based push
            s.vx += dx * move_strength_sand * 0.1
            s.vy += dy * move_strength_sand * 0.1

        # Water neighbors
        water_neighbors = self._get_nearby_water(gx, gy, radius=radius_cells)
        for w in water_neighbors:
            ox = w.x - gx
            oy = w.y - gy
            dist2 = ox*ox + oy*oy
            if dist2 <= push_radius*push_radius:
                d = dist2 ** 0.5 if dist2 > 0 else 0.01
                nx = ox / d
                ny = oy / d
                w.vx += -nx * outward_strength
                w.vy += -ny * outward_strength
            w.vx += dx * move_strength_water * 0.1
            w.vy += dy * move_strength_water * 0.1

    def _handle_npc_hazards(self):
        """Apply burn/bleed/toxic effects to the NPC when touching lava or toxic waste."""
        if self.npc is None:
            return
        if not (self.lava_system.particles or self.toxic_system.particles):
            return
        contact_r2 = 4.0  # within ~2px
        blood_per_frame = 3
        toxic_drip_radius = 1
        for part in self.npc.particles:
            px, py = part.pos
            # Check lava first
            lavas = self._get_nearby_lava(px, py, radius=2)
            for lv in lavas[:8]:
                dx = lv.x - px
                dy = lv.y - py
                if dx*dx + dy*dy <= contact_r2:
                    self.npc.burn_timer = max(self.npc.burn_timer, 45)
                    # Lower speed to avoid long horizontal streaks; spray now biased downward
                    self.blood_system.add_spray(px, py, count=blood_per_frame, speed=1.0)
                    break
            else:
                # Check toxic if no lava hit
                tox = self._get_nearby_toxic(px, py, radius=2)
                for tv in tox[:8]:
                    dx = tv.x - px
                    dy = tv.y - py
                    if dx*dx + dy*dy <= contact_r2:
                        self.npc.toxic_timer = max(self.npc.toxic_timer, 90)
                        self.blood_system.add_spray(px, py, count=2, speed=1.2)
                        self.toxic_system.add_particle_cluster(int(px), int(py), radius=toxic_drip_radius)
                        break
    
    def update(self):
        """Update all game logic"""
        self._draw_on_canvas()
        
        # During loading screen, skip updates
        if not self.ready:
            return

        # Apply cursor interaction before physics integrates
        self._apply_cursor_interaction()

        # NPC dragging (if active tool and mouse held)
        if self.npc is not None and self.current_tool == "npc" and self.is_drawing and self.npc_drag_index is not None:
            mx, my = pygame.mouse.get_pos()
            if mx >= self.sidebar_width:
                vx = mx - self.sidebar_width
                gx, gy = self.camera.view_to_world(vx, my)
                p = self.npc.particles[self.npc_drag_index]
                p.pos[0] = gx
                p.pos[1] = gy
                p.prev[0] = gx
                p.prev[1] = gy

        # Adaptive scaling every 15 frames
        total = (
            self.sand_system.get_particle_count()
            + self.water_system.get_particle_count()
            + self.lava_system.get_particle_count()
            + self.toxic_system.get_particle_count()
            + self.blood_system.get_particle_count()
        )
        if (self._frame_index - self._last_scale_apply) >= 15:
            # Use smoothed FPS
            settings = recommend_settings(total, self._fps_avg or self.fps, self.target_fps, self.use_gpu)
            s = settings["sand"]
            w = settings["water"]
            self.sand_system.neighbor_radius = s["neighbor_radius"]
            self.sand_system.max_neighbors = s["max_neighbors"]
            self.sand_system.skip_mod = s["skip_mod"]
            self.water_system.neighbor_radius = w["neighbor_radius"]
            self.water_system.max_neighbors = w["max_neighbors"]
            self.water_system.skip_mod = w["skip_mod"]
            # Lava uses water-like settings (similar fluid budget)
            self.lava_system.neighbor_radius = w["neighbor_radius"]
            self.lava_system.max_neighbors = w["max_neighbors"]
            self.lava_system.skip_mod = w["skip_mod"]
            # Toxic uses water-like settings too (viscous fluid)
            self.toxic_system.neighbor_radius = w["neighbor_radius"]
            self.toxic_system.max_neighbors = w["max_neighbors"]
            self.toxic_system.skip_mod = w["skip_mod"]
            self._last_scale_apply = self._frame_index

        # Update particle systems (pass frame index for collision skipping)
        self.sand_system.update(self._frame_index)
        self.water_system.update(self._frame_index)
        self.lava_system.update(self._frame_index)
        self.toxic_system.update(self._frame_index)
        # Update NPC physics
        dt = 1.0 / max(self.target_fps, 1)
        if self.npc is not None:
            self.npc.update(dt, bounds=(self.game_width, self.height))

        # Couple NPC with nearby particles (two-way gentle push)
        if self.npc is not None:
            self._npc_particle_coupling()

        # Handle cross-material collisions (grids were rebuilt during updates; avoid rebuilding here)
        self._handle_cross_material_collisions()
        # NPC hazard effects from lava/toxic
        self._handle_npc_hazards()
    
    def draw_sidebar(self):
        """Draw the sidebar UI"""
        if not self.use_gpu:
            # Sidebar background
            pygame.draw.rect(self.screen, (40, 40, 40), (0, 0, self.sidebar_width, self.height))
            # Draw buttons
            for button_name, button_rect in self.buttons.items():
                is_active = (self.current_tool == button_name)
                color = (100, 150, 255) if is_active else (60, 60, 60)
                pygame.draw.rect(self.screen, color, button_rect)
                pygame.draw.rect(self.screen, (150, 150, 150), button_rect, 2)
                text = self.button_font.render(button_name.upper(), True, (255, 255, 255))
                text_rect = text.get_rect(center=button_rect.center)
                self.screen.blit(text, text_rect)
            size_y = 220
            size_text = self.button_font.render(f"Size: {self.brush_size}", True, (200, 200, 200))
            self.screen.blit(size_text, (10, size_y))
            info_y = 250
            info_lines = ["UP/DOWN: Size", "ESC: Quit"]
            for i, line in enumerate(info_lines):
                info_text = self.button_font.render(line, True, (150, 150, 150))
                self.screen.blit(info_text, (10, info_y + i * 20))
            return

        # GPU path
        self.renderer.draw_color = (40, 40, 40, 255)
        self.renderer.fill_rect(sdl2rect.Rect(0, 0, self.sidebar_width, self.height))

        # Buttons
        for button_name, button_rect in self.buttons.items():
            is_active = (self.current_tool == button_name)
            color = (100, 150, 255, 255) if is_active else (60, 60, 60, 255)
            border = (150, 150, 150, 255)
            rect = sdl2rect.Rect(button_rect.x, button_rect.y, button_rect.w, button_rect.h)
            self.renderer.draw_color = color
            self.renderer.fill_rect(rect)
            self.renderer.draw_color = border
            self.renderer.draw_rect(rect)
            # Text -> Texture
            text = button_name.upper()
            text_surf = self.button_font.render(text, True, (255, 255, 255))
            text_tex = self._get_text_texture(text, (255, 255, 255))
            tr = text_surf.get_rect(center=(button_rect.x + button_rect.w//2, button_rect.y + button_rect.h//2))
            self.renderer.copy(text_tex, dstrect=sdl2rect.Rect(tr.x, tr.y, tr.w, tr.h))

        # Brush size and info
        size_label = f"Size: {self.brush_size}"
        size_surf = self.button_font.render(size_label, True, (200, 200, 200))
        size_tex = self._get_text_texture(size_label, (200, 200, 200))
        self.renderer.copy(size_tex, dstrect=sdl2rect.Rect(10, 220, size_surf.get_width(), size_surf.get_height()))

        info_lines = ["UP/DOWN: Size", "ESC: Quit"]
        y = 250
        for line in info_lines:
            info_surf = self.button_font.render(line, True, (150, 150, 150))
            info_tex = self._get_text_texture(line, (150, 150, 150))
            self.renderer.copy(info_tex, dstrect=sdl2rect.Rect(10, y, info_surf.get_width(), info_surf.get_height()))
            y += 20
    
    def draw(self):
        """Render the game"""
        if not self.ready or not self.use_gpu:
            # Clear screen
            self.screen.fill((20, 20, 20))
            if self.ready:
                # Draw game area
                pygame.draw.rect(self.screen, (30, 30, 30), (self.sidebar_width, 0, self.game_width, self.height))
                # Reuse a surface for the game area
                if (self._game_surface is None) or (self._game_surface.get_size() != (self.game_width, self.height)):
                    self._game_surface = pygame.Surface((self.game_width, self.height)).convert()
                game_surface = self._game_surface
                game_surface.fill((20, 20, 20))
                # Draw particles (CPU path)
                self.sand_system.draw(game_surface)
                self.water_system.draw(game_surface)
                self.lava_system.draw(game_surface)
                self.toxic_system.draw(game_surface)
                self.blood_system.draw(game_surface)
                # Draw NPC if present
                if self.npc is not None:
                    self.npc.draw(game_surface)
                if getattr(self, 'camera', None) and not self.camera.is_identity():
                    # Crop and scale according to camera
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
                    # Blit full game area
                    self.screen.blit(game_surface, (self.sidebar_width, 0))
                # Overlay UI
                self._draw_overlays_cpu()
                # Throttle stats update
                now = time.time()
                if now - self._stats_updated_at > 0.25:
                    self._stats_updated_at = now
                    stats = (
                        f"Sand: {self.sand_system.get_particle_count()} | "
                        f"Water: {self.water_system.get_particle_count()} | "
                        f"Lava: {self.lava_system.get_particle_count()} | "
                        f"Toxic: {self.toxic_system.get_particle_count()} | "
                        f"Blood: {self.blood_system.get_particle_count()} | FPS: {self.fps}"
                    )
                    self._stats_cache_surf = self.font.render(stats, True, (200, 200, 200))
                if self._stats_cache_surf:
                    self.screen.blit(self._stats_cache_surf, (self.sidebar_width + 10, self.height - 25))
                # Cursor indicator
                mouse_x, mouse_y = pygame.mouse.get_pos()
                if self.sidebar_width <= mouse_x < self.width:
                    color = (200, 100, 100) if self.current_tool == "sand" else (100, 150, 255)
                    pygame.draw.circle(self.screen, color, (mouse_x, mouse_y), self.brush_size, 1)
            pygame.display.flip()
            return

        # GPU path
        self.renderer.draw_color = (20, 20, 20, 255)
        self.renderer.clear()
        # Game area background
        self.renderer.draw_color = (30, 30, 30, 255)
        self.renderer.fill_rect(sdl2rect.Rect(self.sidebar_width, 0, self.game_width, self.height))
        use_cpu_composite = getattr(self, 'camera', None) and not self.camera.is_identity()
        if use_cpu_composite:
            # Composite to CPU surface, then crop/scale and upload as texture
            cpu_layer = pygame.Surface((self.game_width, self.height), pygame.SRCALPHA)
            cpu_layer.fill((20, 20, 20, 255))
            self.sand_system.draw(cpu_layer)
            self.water_system.draw(cpu_layer)
            self.lava_system.draw(cpu_layer)
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
            # Draw particles via batched point rendering
            # Sand: grouped by color
            sand_groups = self.sand_system.get_point_groups()
            for color, pts in sand_groups.items():
                if not pts:
                    continue
                # Add sidebar offset
                pts_offset = [(x + self.sidebar_width, y) for (x, y) in pts]
                self.renderer.draw_color = (color[0], color[1], color[2], 255)
                self.renderer.draw_points(pts_offset)

            # Water: single color
            w_color, w_points = self.water_system.get_point_groups()
            if w_points:
                w_pts_offset = [(x + self.sidebar_width, y) for (x, y) in w_points]
                self.renderer.draw_color = (w_color[0], w_color[1], w_color[2], 255)
                self.renderer.draw_points(w_pts_offset)

            # Lava: single color
            l_color, l_points = self.lava_system.get_point_groups()
            if l_points:
                l_pts_offset = [(x + self.sidebar_width, y) for (x, y) in l_points]
                self.renderer.draw_color = (l_color[0], l_color[1], l_color[2], 255)
                self.renderer.draw_points(l_pts_offset)

            # Toxic waste: single color
            t_color, t_points = self.toxic_system.get_point_groups()
            if t_points:
                t_pts_offset = [(x + self.sidebar_width, y) for (x, y) in t_points]
                self.renderer.draw_color = (t_color[0], t_color[1], t_color[2], 255)
                self.renderer.draw_points(t_pts_offset)

            # Blood: single color
            b_color, b_points = self.blood_system.get_point_groups()
            if b_points:
                b_pts_offset = [(x + self.sidebar_width, y) for (x, y) in b_points]
                self.renderer.draw_color = (b_color[0], b_color[1], b_color[2], 255)
                self.renderer.draw_points(b_pts_offset)

            # NPC: draw via CPU surface turned into texture (only if present)
            if self.npc is not None:
                cpu_layer = pygame.Surface((self.game_width, self.height), pygame.SRCALPHA)
                self.npc.draw(cpu_layer)
                npc_tex = Texture.from_surface(self.renderer, cpu_layer)
                self.renderer.copy(npc_tex, dstrect=sdl2rect.Rect(self.sidebar_width, 0, self.game_width, self.height))

        # Overlay UI
        self._draw_overlays_gpu()

        # Stats text (throttled)
        now = time.time()
        if (self._stats_cache_tex is None) or (now - self._stats_updated_at > 0.25):
            self._stats_updated_at = now
            stats = (
                f"Sand: {self.sand_system.get_particle_count()} | "
                f"Water: {self.water_system.get_particle_count()} | "
                f"Lava: {self.lava_system.get_particle_count()} | "
                f"Toxic: {self.toxic_system.get_particle_count()} | "
                f"Blood: {self.blood_system.get_particle_count()} | FPS: {self.fps}"
            )
            stats_surf = self.font.render(stats, True, (200, 200, 200))
            self._stats_cache_tex = Texture.from_surface(self.renderer, stats_surf)
            self._stats_cache_surf = stats_surf
        if self._stats_cache_tex and self._stats_cache_surf:
            self.renderer.copy(self._stats_cache_tex, dstrect=sdl2rect.Rect(self.sidebar_width + 10, self.height - 25, self._stats_cache_surf.get_width(), self._stats_cache_surf.get_height()))

        # Cursor indicator (draw a thin rectangle as approximate brush outline)
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if self.sidebar_width <= mouse_x < self.width:
            r = self.brush_size
            self.renderer.draw_color = (200, 100, 100, 255) if self.current_tool == "sand" else (100, 150, 255, 255)
            outline = sdl2rect.Rect(mouse_x - r, mouse_y - r, r*2, r*2)
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

    def _draw_overlays_cpu(self):
        # Icon button: 50% transparent black box with icon image
        overlay = pygame.Surface(self.ui_flask_rect.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))  # 50% black
        self.screen.blit(overlay, self.ui_flask_rect.topleft)
        # Border for icon box for a cleaner look
        pygame.draw.rect(self.screen, (90, 90, 90), self.ui_flask_rect, 1)
        # Draw image centered and scaled to fit with padding
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

        # Spawn menu if visible: larger, styled panel with header and shadow
        if self.ui_show_spawn:
            mw, mh = self.ui_menu_rect.size
            header_h = getattr(self, 'ui_header_h', 36)
            # Drop shadow
            shadow = pygame.Surface((mw, mh), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 100), pygame.Rect(0, 0, mw, mh), border_radius=10)
            self.screen.blit(shadow, (self.ui_menu_rect.x + 3, self.ui_menu_rect.y + 4))

            # Panel with rounded corners
            panel = pygame.Surface((mw, mh), pygame.SRCALPHA)
            pygame.draw.rect(panel, (0, 0, 0, 180), pygame.Rect(0, 0, mw, mh), border_radius=10)
            # Header bar
            pygame.draw.rect(panel, (12, 12, 12, 210), pygame.Rect(0, 0, mw, header_h), border_radius=10)
            # Panel border and inner highlight
            pygame.draw.rect(panel, (100, 100, 100, 220), pygame.Rect(0, 0, mw, mh), width=1, border_radius=10)
            pygame.draw.rect(panel, (255, 255, 255, 25), pygame.Rect(1, 1, mw - 2, mh - 2), width=1, border_radius=9)
            # Blit panel
            self.screen.blit(panel, self.ui_menu_rect.topleft)
            # Title centered in header
            title_text = self.button_font.render("SPAWN", True, (220, 220, 220))
            ty = self.ui_menu_rect.y + (header_h - title_text.get_height()) // 2
            self.screen.blit(title_text, (self.ui_menu_rect.x + 12, ty))

            # Tiles
            mx, my = pygame.mouse.get_pos()
            for tile in getattr(self, 'ui_tiles', []):
                rect = self.ui_tile_rects.get(tile["key"]) if hasattr(self, 'ui_tile_rects') else None
                if not rect:
                    continue
                hovered = rect.collidepoint(mx, my)
                tile_bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                base_alpha = 205 if hovered else 190
                pygame.draw.rect(tile_bg, (25, 25, 25, base_alpha), pygame.Rect(0, 0, rect.w, rect.h), border_radius=8)
                self.screen.blit(tile_bg, rect.topleft)
                # Border and hover
                border_col = (120, 120, 120) if not hovered else (170, 170, 170)
                pygame.draw.rect(self.screen, border_col, rect, 1, border_radius=8)
                # Image or placeholder
                surf = tile.get("surf")
                if surf:
                    iw, ih = surf.get_size()
                    pad = 8
                    dw = max(1, rect.w - 2 * pad)
                    dh = max(1, rect.h - 2 * pad)
                    scale = min(dw / iw, dh / ih)
                    img = pygame.transform.smoothscale(surf, (int(iw * scale), int(ih * scale)))
                    dx = rect.x + (rect.w - img.get_width()) // 2
                    dy = rect.y + (rect.h - img.get_height()) // 2
                    self.screen.blit(img, (dx, dy))
                else:
                    # Colored placeholder
                    ph = pygame.Surface((rect.w - 16, rect.h - 24), pygame.SRCALPHA)
                    ph.fill((*tile.get("color", (120, 120, 120)), 220))
                    px = rect.x + (rect.w - ph.get_width()) // 2
                    py = rect.y + (rect.h - ph.get_height()) // 2
                    self.screen.blit(ph, (px, py))
                # Selection border if selected
                if self.current_tool == tile["key"]:
                    pygame.draw.rect(self.screen, (100, 160, 255), rect, 2, border_radius=8)
                # Label under tile
                label_surf = self.button_font.render(tile["label"], True, (200, 200, 200))
                lx = rect.x + (rect.w - label_surf.get_width()) // 2
                ly = rect.bottom + 6
                self.screen.blit(label_surf, (lx, ly))

    def _draw_overlays_gpu(self):
        self._ensure_ui_textures()
        # Icon button box
        self.renderer.draw_color = (0, 0, 0, 128)
        self.renderer.fill_rect(sdl2rect.Rect(self.ui_flask_rect.x, self.ui_flask_rect.y, self.ui_flask_rect.w, self.ui_flask_rect.h))
        # Border for icon box
        self.renderer.draw_color = (90, 90, 90, 255)
        self.renderer.draw_rect(sdl2rect.Rect(self.ui_flask_rect.x, self.ui_flask_rect.y, self.ui_flask_rect.w, self.ui_flask_rect.h))
        # Icon image sizing and copy
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

        if self.ui_show_spawn:
            header_h = getattr(self, 'ui_header_h', 36)
            # Shadow behind panel
            self.renderer.draw_color = (0, 0, 0, 100)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_menu_rect.x + 3, self.ui_menu_rect.y + 4, self.ui_menu_rect.w, self.ui_menu_rect.h))
            # Panel
            self.renderer.draw_color = (0, 0, 0, 180)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_menu_rect.x, self.ui_menu_rect.y, self.ui_menu_rect.w, self.ui_menu_rect.h))
            # Header bar
            self.renderer.draw_color = (12, 12, 12, 210)
            self.renderer.fill_rect(sdl2rect.Rect(self.ui_menu_rect.x, self.ui_menu_rect.y, self.ui_menu_rect.w, header_h))
            # Panel border
            self.renderer.draw_color = (100, 100, 100, 255)
            self.renderer.draw_rect(sdl2rect.Rect(self.ui_menu_rect.x, self.ui_menu_rect.y, self.ui_menu_rect.w, self.ui_menu_rect.h))
            # Title centered in header
            title = "SPAWN"
            title_tex = self._get_text_texture(title, (220, 220, 220))
            title_surf = self.button_font.render(title, True, (220, 220, 220))
            ty = self.ui_menu_rect.y + (header_h - title_surf.get_height()) // 2
            self.renderer.copy(title_tex, dstrect=sdl2rect.Rect(self.ui_menu_rect.x + 12, ty, title_surf.get_width(), title_surf.get_height()))

            # Tiles (water uses texture if available, others are colored rects with label)
            mx, my = pygame.mouse.get_pos()
            for tile in getattr(self, 'ui_tiles', []):
                rect = self.ui_tile_rects.get(tile["key"]) if hasattr(self, 'ui_tile_rects') else None
                if not rect:
                    continue
                hovered = rect.collidepoint(mx, my)
                alpha = 200 if hovered else 180
                self.renderer.draw_color = (25, 25, 25, alpha)
                self.renderer.fill_rect(sdl2rect.Rect(rect.x, rect.y, rect.w, rect.h))
                border_col = (120, 120, 120, 255) if not hovered else (170, 170, 170, 255)
                self.renderer.draw_color = border_col
                self.renderer.draw_rect(sdl2rect.Rect(rect.x, rect.y, rect.w, rect.h))

                surf = tile.get("surf")
                if surf is not None and tile["key"] in ("water", "sand", "lava", "toxic", "npc"):
                    iw, ih = surf.get_size()
                    pad = 8
                    dest_w = max(1, rect.w - 2 * pad)
                    dest_h = max(1, rect.h - 2 * pad)
                    scale = min(dest_w / (iw or 1), dest_h / (ih or 1))
                    w = int((iw or 1) * scale)
                    h = int((ih or 1) * scale)
                    dx = rect.x + (rect.w - w) // 2
                    dy = rect.y + (rect.h - h) // 2
                    # Use cached texture per known tile
                    tex = None
                    if tile["key"] == "water":
                        tex = self._ui_water_tex
                    elif tile["key"] == "sand":
                        tex = self._ui_sand_tex
                    elif tile["key"] == "lava":
                        tex = self._ui_lava_tex
                    elif tile["key"] == "npc":
                        tex = self._ui_npc_tex
                    elif tile["key"] == "toxic":
                        tex = self._ui_toxic_tex
                    if tex:
                        self.renderer.copy(tex, dstrect=sdl2rect.Rect(dx, dy, w, h))
                    else:
                        try:
                            tmp_tex = Texture.from_surface(self.renderer, surf)
                            self.renderer.copy(tmp_tex, dstrect=sdl2rect.Rect(dx, dy, w, h))
                        except Exception:
                            pass
                else:
                    # Colored placeholder rectangle
                    self.renderer.draw_color = (tile.get("color", (120, 120, 120))[0], tile.get("color", (120, 120, 120))[1], tile.get("color", (120, 120, 120))[2], 220)
                    inset = 8
                    self.renderer.fill_rect(sdl2rect.Rect(rect.x + inset, rect.y + inset, max(0, rect.w - 2 * inset), max(0, rect.h - 2 * inset)))

                # Selection border
                if self.current_tool == tile["key"]:
                    self.renderer.draw_color = (100, 160, 255, 255)
                    self.renderer.draw_rect(sdl2rect.Rect(rect.x, rect.y, rect.w, rect.h))
                # Label
                lbl = tile["label"]
                label_tex = self._get_text_texture(lbl, (200, 200, 200))
                label_surf = self.button_font.render(lbl, True, (200, 200, 200))
                lx = rect.x + (rect.w - label_surf.get_width()) // 2
                ly = rect.bottom + 6
                self.renderer.copy(label_tex, dstrect=sdl2rect.Rect(lx, ly, label_surf.get_width(), label_surf.get_height()))
    
    def run(self):
        """Main game loop"""
        running = True
        while running:
            running = self.handle_events()
            # Poll for size change in case no VIDEORESIZE event was fired
            self._poll_size_change()
            # If benchmarking finished and not yet ready, finalize renderer choice on main thread
            if (not self.ready) and self._bench_done:
                # Apply cfg and (re)create renderer if needed
                self.opt = self._bench_cfg or {}
                self.use_gpu = bool(self.opt.get("use_gpu", GPU_AVAILABLE) and GPU_AVAILABLE)
                self.target_fps = int(self.opt.get("target_fps", 60))
                self.max_particles = int(self.opt.get("max_particles", 50000))

                if self.use_gpu:
                    # Close the CPU window before creating SDL2 Window/Renderer
                    try:
                        pygame.display.quit()
                    except Exception:
                        pass
                    # Create GPU window/renderer
                    self.window = Window("Particle Physics Playground", size=(self.width, self.height))
                    try:
                        self.window.resizable = True
                    except Exception:
                        pass
                    self.renderer = Renderer(self.window, vsync=True)
                    self._text_cache = {}
                else:
                    # Ensure display exists
                    if not pygame.display.get_init():
                        pygame.display.init()
                        self.screen = pygame.display.set_mode((self.width, self.height), pygame.SCALED | pygame.DOUBLEBUF)
                        pygame.display.set_caption("Particle Physics Playground")

                self.ready = True
            self.update()
            self.draw()
            
            self.clock.tick(self.target_fps)
            self.fps = int(self.clock.get_fps())
            # Smoothed FPS for scaling decisions
            if self._fps_avg <= 0:
                self._fps_avg = float(self.fps)
            else:
                self._fps_avg = self._fps_avg * 0.9 + self.fps * 0.1
            self._frame_index += 1


def main():
    """Entry point"""
    game = ParticleGame()
    game.run()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
