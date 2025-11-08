import random
import pygame

class BlueLavaParticle:
    __slots__ = ("x", "y", "vx", "vy", "age", "dead")

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.age = 0
        self.dead = False

class BlueLavaSystem:

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: list[BlueLavaParticle] = []
        # Faster/more fluid than regular lava
        self.gravity = 0.42
        self.viscosity = 0.22  # lower = more fluid
        self.cell_size = 3
        self.neighbor_radius = 2
        self.max_neighbors = 8
        self.skip_mod = 1
        self.grid: dict[tuple[int, int], list[BlueLavaParticle]] = {}
        self.color = (70, 170, 255)  # core pixel color
        self._is_solid = None
        # Glow setup
        self._glow_surf = self._make_glow_surface(12, (90, 190, 255))
        self._glow_stride = 2  # draw glow for every Nth particle to keep perf sane

    def _make_glow_surface(self, radius: int, col: tuple[int, int, int]) -> pygame.Surface:
        d = radius * 2 + 1
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        # simple radial falloff
        for r in range(radius, 0, -1):
            alpha = int(255 * (r / radius) ** 2 * 0.35)
            pygame.draw.circle(s, (*col, alpha), (radius, radius), r)
        return s

    def set_obstacle_query(self, fn):
        self._is_solid = fn

    def add_particle(self, x: float, y: float):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(BlueLavaParticle(x, y))

    def add_particle_cluster(self, x: int, y: int, brush_size: int):
        r = max(1, int(brush_size))
        for _ in range(r * r):
            ox = random.uniform(-r, r)
            oy = random.uniform(-r, r)
            if ox * ox + oy * oy <= r * r:
                self.add_particle(x + ox, y + oy)

    def clear(self):
        self.particles.clear()
        self.grid.clear()

    def get_particle_count(self) -> int:
        return len(self.particles)

    def sweep_dead(self):
        if not self.particles:
            return
        self.particles = [p for p in self.particles if not getattr(p, "dead", False)]

    def _rebuild_grid(self):
        self.grid.clear()
        cs = self.cell_size
        for p in self.particles:
            cx = int(p.x // cs)
            cy = int(p.y // cs)
            self.grid.setdefault((cx, cy), []).append(p)

    def _handle_collisions(self, frame_index: int):
        if self.skip_mod > 1 and frame_index % self.skip_mod != 0:
            return
        cs = self.cell_size
        radius = self.neighbor_radius
        MAXN = self.max_neighbors
        for p in self.particles:
            cx = int(p.x // cs)
            cy = int(p.y // cs)
            neighbors = []
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    cell = (cx + dx, cy + dy)
                    if cell in self.grid:
                        neighbors.extend(self.grid[cell])
                        if len(neighbors) > MAXN:
                            break
                if len(neighbors) > MAXN:
                    break
            for q in neighbors:
                if q is p:
                    continue
                dx = p.x - q.x
                dy = p.y - q.y
                d2 = dx * dx + dy * dy
                if d2 < 2.2 * 2.2 and d2 > 0.01:
                    d = d2 ** 0.5
                    nx, ny = (dx / d, dy / d)
                    # lighter separation + fluid shear blending
                    push = 0.06
                    p.vx += nx * push
                    p.vy += ny * push
                    q.vx -= nx * push * 0.5
                    q.vy -= ny * push * 0.5
                    blend = 0.10
                    dvx = (q.vx - p.vx) * blend
                    dvy = (q.vy - p.vy) * blend
                    p.vx += dvx
                    p.vy += dvy
                    q.vx -= dvx
                    q.vy -= dvy

    def update(self, frame_index: int):
        for p in self.particles:
            p.age += 1
            # gravity + thin damping
            p.vy += self.gravity
            damp_x = max(0.0, 1.0 - self.viscosity * 0.9)
            damp_y = max(0.0, 1.0 - self.viscosity * 0.5)
            p.vx *= damp_x
            p.vy *= damp_y
            p.x += p.vx
            p.y += p.vy

            # collision with solids
            if self._is_solid and self._is_solid(int(p.x), int(p.y)):
                p.x -= p.vx
                p.y -= p.vy
                p.vx *= -0.12
                p.vy *= -0.12

            # boundaries
            if p.x < 0:
                p.x = 0
                p.vx *= -0.18
            elif p.x > self.width - 1:
                p.x = self.width - 1
                p.vx *= -0.18
            if p.y < 0:
                p.y = 0
                p.vy *= -0.18
            elif p.y > self.height - 1:
                p.y = self.height - 1
                p.vy *= -0.18

            # super-hot evaporation to "plasma": slowly disappear
            if p.age > 480 and random.random() < 0.002:
                p.dead = True

        self._rebuild_grid()
        self._handle_collisions(frame_index)

    def draw(self, surf: pygame.Surface):
        col = self.color
        glow = self._glow_surf
        gr = glow.get_width() // 2 if glow else 0
        # Draw core pixels + halos
        for i, p in enumerate(self.particles):
            x, y = (int(p.x), int(p.y))
            if 0 <= x < self.width and 0 <= y < self.height:
                surf.set_at((x, y), col)
                # blue flame flicker: occasionally raise a brighter pixel above
                if (p.age & 7) == 0 and y > 0:
                    yy = y - 1
                    surf.set_at((x, yy), (120, 210, 255))
                # glow halo for a subset to save perf
                if glow is not None and (i % self._glow_stride == 0):
                    surf.blit(glow, (x - gr, y - gr), special_flags=pygame.BLEND_ADD)

    def get_point_groups(self):
        points = [(int(p.x), int(p.y)) for p in self.particles]
        return (self.color, points)
