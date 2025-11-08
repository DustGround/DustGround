import random
import pygame

class MilkParticle:
    __slots__ = ("x","y","vx","vy","temp","age","spoiled","cheese","toxic","dead")
    def __init__(self, x:int, y:int):
        self.x = int(x); self.y = int(y)
        self.vx = 0.0; self.vy = 0.0
        self.temp = 20.0  # ambient
        self.age = 0
        self.spoiled = False  # rotten milk flag
        self.cheese = False   # curdled/cheese flag
        self.toxic = False
        self.dead = False

class MilkSystem:
    def __init__(self, width:int, height:int):
        self.width = width
        self.height = height
        self.particles:list[MilkParticle] = []
        self.cell_size = 6
        self.grid:dict[tuple[int,int], list[MilkParticle]] = {}
        # Tunables
        self.gravity = 0.22   # slightly slower than water fall
        self.drag = 0.04      # viscous drag
        self.flow = 0.65      # lateral flow tendency (water ~0.9)
        self.buoyancy = -0.02 # tiny upward push to make it feel light
        self.evap_temp = 85.0 # starts evaporating when near heat
        self.evap_rate = 0.002
        self.spoil_time = 60 * 10  # frames until spoil (~10s at 60fps)

    def add_particle(self, x:int, y:int):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(MilkParticle(x, y))

    def set_obstacle_query(self, q):
        self._is_obstacle = q

    def _rebuild_grid(self):
        self.grid.clear()
        cs = self.cell_size
        for p in self.particles:
            cx, cy = (p.x // cs, p.y // cs)
            self.grid.setdefault((cx, cy), []).append(p)

    def get_point_groups(self):
        # White opaque
        pts = [(p.x, p.y) for p in self.particles if not p.dead]
        return ((240, 240, 245), pts)

    def get_particle_count(self):
        return len(self.particles)

    def sweep_dead(self):
        self.particles = [p for p in self.particles if not p.dead]

    def is_solid(self, x:int, y:int) -> bool:
        return False

    def _near_heat(self, x:int, y:int) -> bool:
        # Simple heuristic: check for nearby lava via app hook later; fallback random heat patches
        # This function can be enhanced by callers setting a proper heat map.
        return False

    def update(self):
        cs = self.cell_size
        for p in self.particles:
            if p.dead:
                continue
            p.age += 1
            # Spoil over time
            if not (p.spoiled or p.cheese) and p.age >= self.spoil_time:
                # 70% rotten, 30% cheese by default; heat can bias to cheese
                if random.random() < 0.3:
                    p.cheese = True
                else:
                    p.spoiled = True

            # Evaporation near heat
            if self._near_heat(p.x, p.y):
                if random.random() < self.evap_rate:
                    p.dead = True
                    continue

            # Simple fluid-like motion similar to water but thicker
            # gravity
            p.vy += self.gravity
            p.vy *= (1.0 - self.drag)
            p.vx *= (1.0 - self.drag)

            nx = int(p.x + p.vx)
            ny = int(p.y + p.vy)

            # lateral flow: try diagonals if straight down blocked
            def open_cell(xx:int, yy:int) -> bool:
                if xx < 0 or xx >= self.width or yy < 0 or yy >= self.height:
                    return False
                if hasattr(self, '_is_obstacle') and self._is_obstacle(xx, yy):
                    return False
                # avoid stacking on another milk pixel densely
                cx, cy = (xx // cs, yy // cs)
                for q in self.grid.get((cx, cy), []):
                    if q is not p and q.x == xx and q.y == yy:
                        return False
                return True

            moved = False
            # down
            if open_cell(p.x, p.y + 1):
                p.y += 1
                moved = True
            else:
                # diagonals
                dirs = [-1, 1]
                random.shuffle(dirs)
                for dx in dirs:
                    if random.random() < self.flow and open_cell(p.x + dx, p.y + 1):
                        p.x += dx; p.y += 1
                        moved = True
                        break
                if not moved:
                    # sideways seep
                    for dx in dirs:
                        if random.random() < (self.flow * 0.6) and open_cell(p.x + dx, p.y):
                            p.x += dx
                            moved = True
                            break
            if not moved:
                # light jitter settle
                if open_cell(p.x, p.y - 1) and random.random() < 0.02:
                    p.y -= 1

        self._rebuild_grid()

    def draw(self, surf: pygame.Surface):
        col = (240, 240, 245)
        for p in self.particles:
            if p.dead:
                continue
            if p.toxic:
                col = (210, 255, 210)
            elif p.spoiled:
                col = (235, 235, 210)
            elif p.cheese:
                col = (250, 245, 200)
            else:
                col = (240, 240, 245)
            surf.fill(col, (p.x, p.y, 1, 1))
