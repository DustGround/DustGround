import random
import pygame

class MilkParticle:
    __slots__ = ("x","y","vx","vy","temp","age","spoiled","cheese","toxic","dead")
    def __init__(self, x:int, y:int):
        self.x = int(x); self.y = int(y)
        self.vx = 0.0; self.vy = 0.0
        self.temp = 20.0           
        self.age = 0
        self.spoiled = False                    
        self.cheese = False                        
        self.toxic = False
        self.dead = False

class MilkSystem:
    def __init__(self, width:int, height:int):
        self.width = width
        self.height = height
        self.particles:list[MilkParticle] = []
        self.cell_size = 6
        self.grid:dict[tuple[int,int], list[MilkParticle]] = {}
                  
        self.gravity = 0.22                                    
        self.drag = 0.04                    
        self.flow = 0.65                                          
        self.buoyancy = -0.02                                         
        self.evap_temp = 85.0                                    
        self.evap_rate = 0.002
        self.spoil_time = 60 * 10                                      

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
                      
        pts = [(p.x, p.y) for p in self.particles if not p.dead]
        return ((240, 240, 245), pts)

    def get_particle_count(self):
        return len(self.particles)

    def sweep_dead(self):
        self.particles = [p for p in self.particles if not p.dead]

    def is_solid(self, x:int, y:int) -> bool:
        return False

    def _near_heat(self, x:int, y:int) -> bool:
                                                                                                  
                                                                             
        return False

    def update(self):
        cs = self.cell_size
        for p in self.particles:
            if p.dead:
                continue
            p.age += 1
                             
            if not (p.spoiled or p.cheese) and p.age >= self.spoil_time:
                                                                            
                if random.random() < 0.3:
                    p.cheese = True
                else:
                    p.spoiled = True

                                   
            if self._near_heat(p.x, p.y):
                if random.random() < self.evap_rate:
                    p.dead = True
                    continue

                                                                   
                     
            p.vy += self.gravity
            p.vy *= (1.0 - self.drag)
            p.vx *= (1.0 - self.drag)

            nx = int(p.x + p.vx)
            ny = int(p.y + p.vy)

                                                                  
            def open_cell(xx:int, yy:int) -> bool:
                if xx < 0 or xx >= self.width or yy < 0 or yy >= self.height:
                    return False
                if hasattr(self, '_is_obstacle') and self._is_obstacle(xx, yy):
                    return False
                                                              
                cx, cy = (xx // cs, yy // cs)
                for q in self.grid.get((cx, cy), []):
                    if q is not p and q.x == xx and q.y == yy:
                        return False
                return True

            moved = False
                  
            if open_cell(p.x, p.y + 1):
                p.y += 1
                moved = True
            else:
                           
                dirs = [-1, 1]
                random.shuffle(dirs)
                for dx in dirs:
                    if random.random() < self.flow and open_cell(p.x + dx, p.y + 1):
                        p.x += dx; p.y += 1
                        moved = True
                        break
                if not moved:
                                   
                    for dx in dirs:
                        if random.random() < (self.flow * 0.6) and open_cell(p.x + dx, p.y):
                            p.x += dx
                            moved = True
                            break
            if not moved:
                                     
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

    def clear(self):
        self.particles.clear()
        self.grid.clear()
