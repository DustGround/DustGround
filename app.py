import pygame
import sys
import threading
import time
from typing import Tuple, Dict, List, Tuple as Tup
from src.sand import SandSystem, SandParticle
from src.water import WaterSystem, WaterParticle
from src.npc import NPC
from src.opt import get_or_create_optimizations
from src.scaling import recommend_settings

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
        self.sidebar_width = self._compute_sidebar_width(width)
        self.game_width = width - self.sidebar_width

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
        
        # Current tool selection
        self.current_tool = "sand"  # "sand" or "water"
        self.brush_size = 5
        self.is_drawing = False
        
        # UI Elements
        self.buttons = {}
        self._layout_ui()
        
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

    def _get_text_texture(self, text: str, color: Tup[int, int, int]) -> "Texture":
        """Cache and return a Texture for text rendering in GPU mode."""
        key = (text, color)
        if key in getattr(self, "_text_cache", {}):
            return self._text_cache[key]
        surf = self.button_font.render(text, True, color)
        tex = Texture.from_surface(self.renderer, surf)
        self._text_cache[key] = tex
        return tex
        
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
                    if self._handle_sidebar_click(event.pos):
                        continue
                    # If NPC tool active, start dragging nearest body part in game area
                    if self.current_tool == "npc":
                        mx, my = event.pos
                        if mx >= self.sidebar_width:
                            gx, gy = mx - self.sidebar_width, my
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
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.is_drawing = False
                    if self.current_tool == "npc":
                        self.npc_drag_index = None
                        if self.npc:
                            self.npc.set_user_dragging(False)
                    
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
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
        self.buttons = {
            "sand": pygame.Rect(margin, 20, bw, bh),
            "water": pygame.Rect(margin, 70, bw, bh),
            "npc": pygame.Rect(margin, 120, bw, bh),
            "clear": pygame.Rect(margin, 170, bw, bh),
        }

    def _apply_resize(self, new_w: int, new_h: int):
        # Update sizes
        self.width = int(max(400, new_w))
        self.height = int(max(300, new_h))
        self.sidebar_width = self._compute_sidebar_width(self.width)
        self.game_width = self.width - self.sidebar_width
        # Relayout UI
        self._layout_ui()
        # Update systems' bounds
        self.sand_system.width = self.game_width
        self.sand_system.height = self.height
        self.water_system.width = self.game_width
        self.water_system.height = self.height
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
        
        # Don't draw in sidebar
        if mouse_x < self.sidebar_width:
            return
        
        # Adjust coordinates to game space
        game_x = mouse_x - self.sidebar_width
        
        # enforce particle cap
        total = self.sand_system.get_particle_count() + self.water_system.get_particle_count()
        if total >= self.max_particles:
            # Still allow NPC dragging when at cap
            if self.current_tool != "npc":
                return

        if self.current_tool == "sand":
            self.sand_system.add_particle_cluster(game_x, mouse_y, self.brush_size)
        elif self.current_tool == "water":
            self.water_system.add_particle_cluster(game_x, mouse_y, self.brush_size)
        elif self.current_tool == "npc":
            # Drag current selected NPC particle to cursor
            if self.npc is not None and self.npc_drag_index is not None:
                p = self.npc.particles[self.npc_drag_index]
                p.pos[0] = game_x
                p.pos[1] = mouse_y
                p.prev[0] = game_x
                p.prev[1] = mouse_y
    
    def _handle_cross_material_collisions(self):
        """Handle collisions between sand and water particles"""
        # Grids were rebuilt during each system update; avoid extra rebuild here
        # Check each water particle against sand particles
        MAX_NEIGHBORS = 12
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
        # Update previous mouse storage
        if self._prev_mouse is None:
            self._prev_mouse = (mx, my)
            return

        # Don't interact in the sidebar or while loading
        if (not self.ready) or (mx < self.sidebar_width):
            self._prev_mouse = (mx, my)
            return

        # Convert to game coords
        gx = mx - self.sidebar_width
        gy = my

        # Movement delta
        pmx, pmy = self._prev_mouse
        dx = mx - pmx
        dy = my - pmy
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
                gx, gy = mx - self.sidebar_width, my
                p = self.npc.particles[self.npc_drag_index]
                p.pos[0] = gx
                p.pos[1] = gy
                p.prev[0] = gx
                p.prev[1] = gy

        # Adaptive scaling every 15 frames
        total = self.sand_system.get_particle_count() + self.water_system.get_particle_count()
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
            self._last_scale_apply = self._frame_index

        # Update particle systems (pass frame index for collision skipping)
        self.sand_system.update(self._frame_index)
        self.water_system.update(self._frame_index)
        # Update NPC physics
        dt = 1.0 / max(self.target_fps, 1)
        if self.npc is not None:
            self.npc.update(dt, bounds=(self.game_width, self.height))

        # Couple NPC with nearby particles (two-way gentle push)
        if self.npc is not None:
            self._npc_particle_coupling()

        # Handle cross-material collisions (grids were rebuilt during updates; avoid rebuilding here)
        self._handle_cross_material_collisions()
    
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
                # Draw NPC if present
                if self.npc is not None:
                    self.npc.draw(game_surface)
                # Blit game area
                self.screen.blit(game_surface, (self.sidebar_width, 0))
                # Sidebar and HUD
                self.draw_sidebar()
                # Throttle stats update
                now = time.time()
                if now - self._stats_updated_at > 0.25:
                    self._stats_updated_at = now
                    self._stats_cache_surf = self.font.render(
                        f"Sand: {self.sand_system.get_particle_count()} | Water: {self.water_system.get_particle_count()} | FPS: {self.fps}",
                        True,
                        (200, 200, 200)
                    )
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

        # NPC: draw via CPU surface turned into texture (only if present)
        if self.npc is not None:
            cpu_layer = pygame.Surface((self.game_width, self.height), pygame.SRCALPHA)
            self.npc.draw(cpu_layer)
            npc_tex = Texture.from_surface(self.renderer, cpu_layer)
            self.renderer.copy(npc_tex, dstrect=sdl2rect.Rect(self.sidebar_width, 0, self.game_width, self.height))

        # Sidebar and HUD
        self.draw_sidebar()

        # Stats text (throttled)
        now = time.time()
        if (self._stats_cache_tex is None) or (now - self._stats_updated_at > 0.25):
            self._stats_updated_at = now
            stats = f"Sand: {self.sand_system.get_particle_count()} | Water: {self.water_system.get_particle_count()} | FPS: {self.fps}"
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
