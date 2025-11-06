import random
import pygame

class LavaParticle:
    __slots__ = ('x', 'y', 'vx', 'vy')

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0

class LavaSystem:

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: list[LavaParticle] = []
        self.gravity = 0.4
        self.viscosity = 0.55
        self.cell_size = 3
        self.neighbor_radius = 2
        self.max_neighbors = 8
        self.skip_mod = 1
        self.grid: dict[tuple[int, int], list[LavaParticle]] = {}
        self.color = (255, 110, 20)
        self._is_solid = None

    def set_obstacle_query(self, fn):
        self._is_solid = fn

    def add_particle(self, x: float, y: float):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(LavaParticle(x, y))

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
        self.particles = [p for p in self.particles if not getattr(p, 'dead', False)]

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
                if d2 < 2.5 * 2.5 and d2 > 0.01:
                    d = d2 ** 0.5
                    nx, ny = (dx / d, dy / d)
                    push = 0.08
                    p.vx += nx * push
                    p.vy += ny * push
                    q.vx -= nx * push * 0.5
                    q.vy -= ny * push * 0.5
                    blend = 0.06
                    dvx = (q.vx - p.vx) * blend
                    dvy = (q.vy - p.vy) * blend
                    p.vx += dvx
                    p.vy += dvy
                    q.vx -= dvx
                    q.vy -= dvy

    def update(self, frame_index: int):
        for p in self.particles:
            p.vy += self.gravity
            damp_x = max(0.0, 1.0 - self.viscosity * 1.25)
            damp_y = max(0.0, 1.0 - self.viscosity * 0.7)
            p.vx *= damp_x
            p.vy *= damp_y
            p.x += p.vx
            p.y += p.vy
            if self._is_solid and self._is_solid(int(p.x), int(p.y)):
                p.x -= p.vx
                p.y -= p.vy
                p.vx *= -0.15
                p.vy *= -0.15
            if p.x < 0:
                p.x = 0
                p.vx *= -0.2
            elif p.x > self.width - 1:
                p.x = self.width - 1
                p.vx *= -0.2
            if p.y < 0:
                p.y = 0
                p.vy *= -0.2
            elif p.y > self.height - 1:
                p.y = self.height - 1
                p.vy *= -0.2
        self._rebuild_grid()
        self._handle_collisions(frame_index)

    def draw(self, surf: pygame.Surface):
        col = self.color
        for p in self.particles:
            x, y = (int(p.x), int(p.y))
            if 0 <= x < self.width and 0 <= y < self.height:
                surf.set_at((x, y), col)

    def get_point_groups(self):
        points = [(int(p.x), int(p.y)) for p in self.particles]
        return (self.color, points)
