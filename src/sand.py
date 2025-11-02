import math
import pygame
from typing import List, Tuple, Dict

class SandParticle:
    """Individual sand particle with physics properties"""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mass = 1.0
        self.color = (194, 178, 128)  # Sand color
        self.settled = False
        self.wet = False  # Becomes true when touched by water
        
    def apply_gravity(self, gravity: float):
        """Apply gravity to vertical velocity"""
        self.vy += gravity
        
    def apply_friction(self, friction: float):
        """Apply friction to horizontal movement"""
        self.vx *= (1 - friction)
        if abs(self.vx) < 0.01:
            self.vx = 0
            
    def update(self, gravity: float, friction: float):
        """Update particle position and velocity"""
        self.apply_gravity(gravity)
        self.apply_friction(friction)
        
        # Update position
        self.x += self.vx
        self.y += self.vy
        
        # Cap falling speed
        if self.vy > 10:
            self.vy = 10


class SandSystem:
    """Manages all sand particles and their interactions"""
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: List[SandParticle] = []
        self.gravity = 0.2
        self.friction = 0.05
        self.cell_size = 3  # Slightly larger cells reduce neighbor checks
        self.grid = {}
        # Adaptive collision controls
        self.neighbor_radius: int = 2
        self.max_neighbors: int = 12
        self.skip_mod: int = 1  # 1 means run collisions every frame
        
    def add_particle(self, x: float, y: float):
        """Add a new sand particle"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.particles.append(SandParticle(x, y))
            
    def add_particle_cluster(self, center_x: float, center_y: float, radius: int = 5):
        """Add multiple particles in a circular pattern"""
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx*dx + dy*dy <= radius*radius:
                    x = center_x + dx
                    y = center_y + dy
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.add_particle(x, y)
    
    def _get_cell(self, x: float, y: float) -> Tuple[int, int]:
        """Get grid cell from position"""
        return (int(x // self.cell_size), int(y // self.cell_size))
    
    def _rebuild_grid(self):
        """Rebuild spatial partitioning grid"""
        self.grid.clear()
        for particle in self.particles:
            cell = self._get_cell(particle.x, particle.y)
            if cell not in self.grid:
                self.grid[cell] = []
            self.grid[cell].append(particle)
    
    def _get_neighbors(self, x: float, y: float, radius: int = 1) -> List[SandParticle]:
        """Get particles near a position"""
        neighbors = []
        cell_x, cell_y = self._get_cell(x, y)
        
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = (cell_x + dx, cell_y + dy)
                if cell in self.grid:
                    neighbors.extend(self.grid[cell])
        return neighbors
    
    def _handle_collisions(self, frame_index: int = 0):
        """Handle sand-to-sand collisions"""
        # Optionally skip collision resolution this frame for performance
        if self.skip_mod > 1 and (frame_index % self.skip_mod) != 0:
            return
        self._rebuild_grid()
        
        for particle in self.particles:
            neighbors = self._get_neighbors(particle.x, particle.y, radius=self.neighbor_radius)
            checked = 0
            
            for other in neighbors:
                if particle is other:
                    continue
                
                dx = other.x - particle.x
                dy = other.y - particle.y
                dist = math.hypot(dx, dy)
                
                # If particles overlap
                if dist < 2:
                    # Separate them
                    if dist == 0:
                        dist = 0.1
                    nx = dx / dist
                    ny = dy / dist
                    
                    overlap = 2 - dist
                    particle.x -= nx * overlap * 0.5
                    particle.y -= ny * overlap * 0.5
                    other.x += nx * overlap * 0.5
                    other.y += ny * overlap * 0.5
                    
                    # Transfer momentum slightly
                    particle.vx -= nx * 0.1
                    particle.vy -= ny * 0.1

                    checked += 1
                    if checked >= self.max_neighbors:
                        break
    
    def _handle_boundaries(self):
        """Handle boundary collisions"""
        for particle in self.particles:
            # Bottom boundary
            if particle.y + 1 >= self.height:
                particle.y = self.height - 1
                particle.vy = 0
                particle.settled = True
                
            # Top boundary
            if particle.y < 0:
                particle.y = 0
                particle.vy = 0
                
            # Left boundary
            if particle.x < 0:
                particle.x = 0
                particle.vx *= -0.5
                
            # Right boundary
            if particle.x >= self.width:
                particle.x = self.width - 1
                particle.vx *= -0.5
    
    def update(self, frame_index: int = 0):
        """Update all sand particles"""
        for particle in self.particles:
            particle.update(self.gravity, self.friction)
        
        self._handle_collisions(frame_index)
        self._handle_boundaries()
        
        # Remove particles that are far out of bounds
        self.particles = [p for p in self.particles if -10 <= p.x < self.width + 10 and -10 <= p.y < self.height + 10]
    
    def draw(self, surface: pygame.Surface):
        """Draw all sand particles"""
        for particle in self.particles:
            if 0 <= particle.x < self.width and 0 <= particle.y < self.height:
                color = (194, 178, 128) if not particle.wet else (180, 160, 100)
                pygame.draw.circle(surface, color, (int(particle.x), int(particle.y)), 1)

    def get_point_groups(self) -> Dict[Tuple[int, int, int], List[Tuple[int, int]]]:
        """Return points grouped by color for fast, batched GPU drawing.
        Keys are RGB color tuples; values are lists of (x, y) integer points.
        """
        dry_color = (194, 178, 128)
        wet_color = (180, 160, 100)
        groups: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = {
            dry_color: [],
            wet_color: [],
        }
        for p in self.particles:
            if 0 <= p.x < self.width and 0 <= p.y < self.height:
                pt = (int(p.x), int(p.y))
                if p.wet:
                    groups[wet_color].append(pt)
                else:
                    groups[dry_color].append(pt)
        # Remove empty lists to avoid redundant draw calls
        return {c: pts for c, pts in groups.items() if pts}
    
    def get_particle_count(self) -> int:
        """Return number of particles"""
        return len(self.particles)
    
    def get_particles_at(self, x: float, y: float, radius: float = 5) -> List[SandParticle]:
        """Get particles within a radius of a position"""
        result = []
        for particle in self.particles:
            dx = particle.x - x
            dy = particle.y - y
            if dx*dx + dy*dy <= radius*radius:
                result.append(particle)
        return result
    
    def clear(self):
        """Clear all particles"""
        self.particles.clear()
        self.grid.clear()
