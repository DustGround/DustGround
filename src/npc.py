import math
from typing import Callable, Optional

import pygame

class Particle:

    def __init__(self, pos, mass=1.0):
        self.pos = pygame.math.Vector2(pos)
        self.prev = pygame.math.Vector2(pos)
        self.acc = pygame.math.Vector2(0, 0)
        self.mass = mass

    def apply_force(self, f):
        self.acc += f / max(self.mass, 1e-06)

    def update(self, dt):
        vel = self.pos - self.prev
        self.prev = self.pos.copy()
        self.pos += vel + self.acc * (dt * dt)
        self.acc.update(0, 0)

class NPC:

    def __init__(self, x, y):
        self.particles = []
        self.constraints = []
        self.burn_timer = 0
        self.toxic_timer = 0
                                                                                     
        head = Particle((x, y - 60))
        t1 = Particle((x, y - 30))
        t2 = Particle((x, y))
        t3 = Particle((x, y + 30))
        t4 = Particle((x, y + 60))
        l_arm = Particle((x - 30, y + 5))
        r_arm = Particle((x + 30, y + 5))
        l_leg = Particle((x - 8, y + 120))
        r_leg = Particle((x + 8, y + 120))
        self.particles = [head, t1, t2, t3, t4, l_arm, r_arm, l_leg, r_leg]

        def connect(a, b, slack=0.0):
            pa = self.particles[a]
            pb = self.particles[b]
            dist = (pa.pos - pb.pos).length() * (1.0 + slack)
            self.constraints.append((a, b, dist))
        connect(0, 1)
        connect(1, 2)
        connect(2, 3)
        connect(3, 4)
        connect(2, 5)
        connect(2, 6)
        connect(4, 7)
        connect(4, 8)
        connect(1, 3, slack=0.05)
        connect(2, 4, slack=0.05)
        self.size = 12
        self.head_size = 28
        self.base_color = (205, 205, 210)
        self.color = self.base_color
        self.outline = (120, 120, 130)
        self.gravity = pygame.math.Vector2(0, 1600)
        self.iterations = 6
        self.user_dragging = False
        self._stand_anchor_x = None
        self._frame_counter = 0
        self._torso_still_frames = 0
        self._sleep_torso = False
                                                                                      
        self.freeze_torso = False
                                                               
        self._torso_layout = {0: -60, 1: -30, 2: 0, 3: 30, 4: 60}
                                                              
        self._feet_grounded = 0

    def apply_global_force(self, f):
        for p in self.particles:
            p.apply_force(f)

    def update(self, dt, bounds: tuple[int, int] | None=None, solid_query: Callable[[int, int], bool] | None=None):
        self._frame_counter += 1
        if self.user_dragging:
            self._sleep_torso = False
            self._torso_still_frames = 0
        for i, p in enumerate(self.particles):
            if (self.freeze_torso or self._sleep_torso) and i in (0, 1, 2, 3, 4):
                continue
            p.apply_force(self.gravity * p.mass)
        for p in self.particles:
            p.update(dt)
                                                         
        max_step = 40.0
        for p in self.particles:
            sx = p.pos.x - p.prev.x
            sy = p.pos.y - p.prev.y
            d2 = sx * sx + sy * sy
            if d2 > max_step * max_step:
                d = math.sqrt(d2)
                if d > 0:
                    s = max_step / d
                    p.pos.x = p.prev.x + sx * s
                    p.pos.y = p.prev.y + sy * s
                                                                                         
        if bounds is not None:
            w, h = bounds
            for p in self.particles:
                if p.pos.x < 0:
                    p.pos.x = 0
                if p.pos.x > w - 1:
                    p.pos.x = w - 1
                if p.pos.y < 0:
                    p.pos.y = 0
                if p.pos.y > h - 1:
                    p.pos.y = h - 1
        if solid_query is not None:
            for part in self.particles:
                self._nudge_particle_from_solid(part, solid_query, bounds)
        feet_grounded, ground_y = self._resolve_block_contacts(solid_query, bounds)
        self._feet_grounded = feet_grounded
                                                                                              
        rigid_active = (ground_y is not None and feet_grounded == 2 and not self.user_dragging)
        if rigid_active:
            fx = (self.particles[7].pos.x + self.particles[8].pos.x) * 0.5
            base_y = ground_y - 60
                                                           
            layout = [base_y - 120, base_y - 90, base_y - 60, base_y - 30, base_y]
            for idx, part in zip((0,1,2,3,4), layout):
                p = self.particles[idx]
                p.pos.x = fx
                p.pos.y = part
                p.prev.x = p.pos.x
                p.prev.y = p.pos.y
                                                               
            pelvis_y = base_y
                                                           
            arm_y = base_y - 10                                         
            left_arm = self.particles[5]; right_arm = self.particles[6]
            left_arm.pos.x = fx - 10; left_arm.pos.y = arm_y
            right_arm.pos.x = fx + 10; right_arm.pos.y = arm_y
            left_arm.prev.x = left_arm.pos.x; left_arm.prev.y = left_arm.pos.y
            right_arm.prev.x = right_arm.pos.x; right_arm.prev.y = right_arm.pos.y
                                                
            foot_y = ground_y
            left_leg = self.particles[7]; right_leg = self.particles[8]
            left_leg.pos.x = fx - 14; left_leg.pos.y = foot_y
            right_leg.pos.x = fx + 14; right_leg.pos.y = foot_y
            left_leg.prev.x = left_leg.pos.x; left_leg.prev.y = left_leg.pos.y
            right_leg.prev.x = right_leg.pos.x; right_leg.prev.y = right_leg.pos.y
                                                                              
        if (not self.freeze_torso) and (not rigid_active) and self._frame_counter % 2 == 0:
            self._apply_stand_controller(dt * 0.6, ground_y)
        for _ in range(self.iterations):
            for i, j, rest in self.constraints:
                if (self.freeze_torso or rigid_active) and (i in (0,1,2,3,4,5,6,7,8) or j in (0,1,2,3,4,5,6,7,8)):
                                                                         
                    continue
                pa = self.particles[i]
                pb = self.particles[j]
                delta = pb.pos - pa.pos
                d = delta.length()
                if d == 0:
                    continue
                diff = (d - rest) / d
                correction = delta * 0.5 * diff
                pa.pos += correction
                pb.pos -= correction
                                                                      
                if d > rest * 1.3:
                    pull = (d - rest * 1.1) / d
                    adjust = delta * (pull * 0.4)
                    pa.pos += adjust * -0.5
                    pb.pos += adjust * 0.5
                                                                              
        if bounds is not None:
            w, h = bounds
            for p in self.particles:
                if p.pos.x < 0:
                    p.pos.x = 0
                if p.pos.x > w - 1:
                    p.pos.x = w - 1
                if p.pos.y < 0:
                    p.pos.y = 0
                if p.pos.y > h - 1:
                    p.pos.y = h - 1
        if solid_query is not None:
            for part in self.particles:
                self._nudge_particle_from_solid(part, solid_query, bounds)
                                                
        torso = (0, 1, 2, 3, 4)
        if rigid_active:
                                                                                   
            for i in range(len(self.particles)):
                p = self.particles[i]
                p.prev.x = p.pos.x
                p.prev.y = p.pos.y
            if self.burn_timer > 0:
                self.burn_timer -= 1
            if self.toxic_timer > 0:
                self.toxic_timer -= 1
            return
        if self.freeze_torso:
            pelvis = self.particles[4].pos
                                                                           
            if bounds is not None:
                fx = (self.particles[7].pos.x + self.particles[8].pos.x) * 0.5
                pelvis.x = fx
                                        
            for idx in torso:
                off = self._torso_layout.get(idx, 0)
                p = self.particles[idx]
                target_y = pelvis.y + off - 60                            
                p.pos.x = pelvis.x
                p.pos.y = target_y
                p.prev.x = p.pos.x
                p.prev.y = p.pos.y
            if self.burn_timer > 0:
                self.burn_timer -= 1
            if self.toxic_timer > 0:
                self.toxic_timer -= 1
            return
        avg_x = sum(self.particles[i].pos.x for i in torso) / len(torso)
        for i in torso:
            p = self.particles[i]
            p.pos.x = p.pos.x * 0.9 + avg_x * 0.1
                                               
        for i in torso:
            p = self.particles[i]
            vx = p.pos.x - p.prev.x
            vy = p.pos.y - p.prev.y
            p.prev.x = p.pos.x - vx * 0.6
            p.prev.y = p.pos.y - vy * 0.6
                                                                            
        avg_v = 0.0
        for i in torso:
            p = self.particles[i]
            vx = p.pos.x - p.prev.x
            vy = p.pos.y - p.prev.y
            avg_v += (vx * vx + vy * vy) ** 0.5
        avg_v /= len(torso)
        if avg_v < 0.12 and feet_grounded == 2 and not self.user_dragging:
            self._torso_still_frames += 1
            if self._torso_still_frames > 20:
                self._sleep_torso = True
        else:
            self._torso_still_frames = 0
            if avg_v > 0.3:
                self._sleep_torso = False
                                                                            
        if self._sleep_torso and feet_grounded == 2 and not self.user_dragging:
            for i in torso:
                p = self.particles[i]
                p.prev.x = p.pos.x
                p.prev.y = p.pos.y
                                                                           
            for i in (0,1):
                p = self.particles[i]
                p.prev.x = p.pos.x
                p.prev.y = p.pos.y
        else:
                                                                                 
            if feet_grounded == 2 and not self.user_dragging and avg_v < 0.25:
                for i in (0,1):
                    p = self.particles[i]
                    vx = p.pos.x - p.prev.x
                    vy = p.pos.y - p.prev.y
                    if vx*vx + vy*vy < 0.04:                     
                        p.prev.x = p.pos.x
                        p.prev.y = p.pos.y
        if self.burn_timer > 0:
            self.burn_timer -= 1
        if self.toxic_timer > 0:
            self.toxic_timer -= 1

    def draw(self, surf: pygame.Surface):
        col = self.base_color
        if self.toxic_timer > 0:
            g = min(255, int(col[1] + 60))
            col = (max(0, col[0] - 20), g, max(0, col[2] - 20))
        if self.burn_timer > 0:
            r = min(255, int(col[0] + 50))
            col = (r, max(0, col[1] - 20), max(0, col[2] - 20))
        self.color = col

        def draw_bone(a: pygame.math.Vector2, b: pygame.math.Vector2, half_w: float):
            d = b - a
            if d.length_squared() == 0:
                return
            n = pygame.math.Vector2(-d.y, d.x)
            try:
                n = n.normalize() * half_w
            except ValueError:
                return
            p1 = (a.x + n.x, a.y + n.y)
            p2 = (b.x + n.x, b.y + n.y)
            p3 = (b.x - n.x, b.y - n.y)
            p4 = (a.x - n.x, a.y - n.y)
            pygame.draw.polygon(surf, self.outline, (p1, p2, p3, p4))
            inset = max(1, int(half_w * 0.5))

            def inset_pt(px, py, qx, qy):
                return (px + (qx - px) * 0.15, py + (qy - py) * 0.15)
            ip1 = inset_pt(*p1, *p2)
            ip2 = inset_pt(*p2, *p3)
            ip3 = inset_pt(*p3, *p4)
            ip4 = inset_pt(*p4, *p1)
            pygame.draw.polygon(surf, self.color, (ip1, ip2, ip3, ip4))
        torso = [self.particles[i].pos for i in (0, 1, 2, 3, 4)]
        for a, b in zip(torso[:-1], torso[1:]):
            draw_bone(a, b, self.size * 0.55)
        mid = self.particles[2].pos
        la = self.particles[5].pos
        ra = self.particles[6].pos
        draw_bone(mid, la, self.size * 0.35)
        draw_bone(mid, ra, self.size * 0.35)
        hip = self.particles[4].pos
        ll = self.particles[7].pos
        rl = self.particles[8].pos
        draw_bone(hip, ll, self.size * 0.42)
        draw_bone(hip, rl, self.size * 0.42)
        head_pos = self.particles[0].pos
        hs = int(self.head_size)
        head_rect = pygame.Rect(0, 0, hs, hs)
        head_rect.center = (int(head_pos.x), int(head_pos.y))
        pygame.draw.rect(surf, self.outline, head_rect)
        inner = head_rect.inflate(-3, -3)
        pygame.draw.rect(surf, self.color, inner)
        eye = pygame.Rect(0, 0, max(2, hs // 10), max(2, hs // 10))
        eye.center = (head_rect.centerx + hs // 5, head_rect.centery - hs // 8)
        pygame.draw.rect(surf, (90, 90, 100), eye)

    def _nudge_particle_from_solid(self, particle: Particle, solid_query: Callable[[int, int], bool],
                                   bounds: tuple[int, int] | None) -> None:
        """Minimal translation to push a particle out of any solid tile it overlaps."""
        max_iter = 4
        moved_x = False
        moved_y = False
        orig_prev_x = particle.prev.x
        orig_prev_y = particle.prev.y
        for _ in range(max_iter):
            ix = int(particle.pos.x)
            iy = int(particle.pos.y)
            if bounds is not None:
                w, h = bounds
                if ix < 0 or ix >= w or iy < 0 or iy >= h:
                    break
            try:
                inside = solid_query(ix, iy)
            except Exception:
                inside = False
            if not inside:
                break
            fx = particle.pos.x - ix
            fy = particle.pos.y - iy
            dist_left = fx
            dist_right = 1.0 - fx
            dist_top = fy
            dist_bottom = 1.0 - fy
            min_dist = min(dist_left, dist_right, dist_top, dist_bottom)
            if min_dist == dist_top:
                particle.pos.y = iy - 0.01
                moved_y = True
            elif min_dist == dist_bottom:
                particle.pos.y = iy + 1.01
                moved_y = True
            elif min_dist == dist_left:
                particle.pos.x = ix - 0.01
                moved_x = True
            else:
                particle.pos.x = ix + 1.01
                moved_x = True
        if bounds is not None:
            w, h = bounds
            if particle.pos.x < 0.0:
                particle.pos.x = 0.0
                moved_x = True
            elif particle.pos.x > w - 1:
                particle.pos.x = float(w - 1)
                moved_x = True
            if particle.pos.y < 0.0:
                particle.pos.y = 0.0
                moved_y = True
            elif particle.pos.y > h - 1:
                particle.pos.y = float(h - 1)
                moved_y = True
        if moved_x:
            vx = particle.pos.x - orig_prev_x
            particle.prev.x = particle.pos.x - vx * 0.1
        if moved_y:
            vy = particle.pos.y - orig_prev_y
            if vy < 0:
                particle.prev.y = particle.pos.y
            else:
                particle.prev.y = particle.pos.y - vy * 0.1

    def _resolve_block_contacts(self, solid_query: Callable[[int, int], bool] | None,
                                bounds: tuple[int, int] | None) -> tuple[int, Optional[float]]:
        """Snap feet onto solid surfaces or world ground and report contact metrics."""
        world_ground = float(bounds[1] - 1) if bounds else None
        grounded_samples: list[float] = []
        feet_grounded = 0
        for idx in (7, 8):
            foot = self.particles[idx]
            grounded = False
            if solid_query is not None:
                fx = int(foot.pos.x)
                base_y = int(foot.pos.y)
                for step in range(4):
                    tile_y = base_y + step
                    if bounds is not None:
                        _, h = bounds
                        if tile_y < 0 or tile_y >= h:
                            break
                    try:
                        if solid_query(fx, tile_y):
                            top = float(tile_y)
                            target = top - 0.01
                            if foot.pos.y > target:
                                foot.pos.y = target
                            vx = foot.pos.x - foot.prev.x
                            foot.prev.y = foot.pos.y
                            foot.prev.x = foot.pos.x - vx * 0.2
                            grounded = True
                            grounded_samples.append(foot.pos.y)
                            break
                    except Exception:
                        break
            if (not grounded) and world_ground is not None and foot.pos.y >= world_ground:
                foot.pos.y = world_ground
                vx = foot.pos.x - foot.prev.x
                foot.prev.y = foot.pos.y
                foot.prev.x = foot.pos.x - vx * 0.2
                grounded = True
                grounded_samples.append(foot.pos.y)
            if grounded:
                feet_grounded += 1
        ground_y: Optional[float] = None
        if grounded_samples:
            ground_y = sum(grounded_samples) / len(grounded_samples)
        elif world_ground is not None:
            ground_y = world_ground
        return feet_grounded, ground_y

    def _apply_motors(self, targets: dict[int, pygame.math.Vector2], strength: float, damping: float, dt: float):
        if self.freeze_torso:
                                                   
            targets = {k: v for k, v in targets.items() if k not in (0,1,2,3,4)}
        k = min(1.0, max(0.0, dt * 60.0))
        for idx, tgt in targets.items():
            if self._sleep_torso and idx in (0,1,2,3,4):
                continue
            p = self.particles[idx]
            dx = tgt.x - p.pos.x
            dy = tgt.y - p.pos.y
            if abs(dx) < 0.5 and abs(dy) < 0.5:
                continue
                                                                        
            if idx in (7, 8):
                sx, sy = (0.5, 1.0)
                gain = 0.8
                cap = 8.0
            elif idx in (0, 1, 2, 3, 4):
                sx, sy = (0.9, 0.9)
                gain = 0.5 if idx == 0 else 0.6
                cap = 6.0 if idx == 0 else 7.0
            else:
                sx, sy = (1.0, 1.0)
                gain = 1.0
                cap = 8.0
            mx = dx * strength * 0.5 * k * sx * gain
            my = dy * strength * 1.0 * k * sy * gain
                                                                      
            if mx > cap:
                mx = cap
            elif mx < -cap:
                mx = -cap
            if my > cap:
                my = cap
            elif my < -cap:
                my = -cap
            p.pos.x += mx
            p.pos.y += my
            p.prev.x = p.pos.x - (p.pos.x - p.prev.x) * damping
            p.prev.y = p.pos.y - (p.pos.y - p.prev.y) * damping

                                                    
        for p in self.particles:
            vx = p.pos.x - p.prev.x
            vy = p.pos.y - p.prev.y
            if vx * vx + vy * vy < 0.09:                     
                p.prev.x = p.pos.x
                p.prev.y = p.pos.y

    def _stand_targets(self, ground_y: float | None) -> dict[int, pygame.math.Vector2]:
        pelvis = self.particles[4].pos
        if ground_y is not None:
            fx = (self.particles[7].pos.x + self.particles[8].pos.x) * 0.5
        else:
            fx = pelvis.x
                                                                        
                                                                         
        if self._stand_anchor_x is None:
            self._stand_anchor_x = fx
        else:
            self._stand_anchor_x = self._stand_anchor_x * 0.85 + fx * 0.15
        base_x = self._stand_anchor_x
        gy = ground_y if ground_y is not None else pelvis.y + 60
        spacing = 22
        targets = {}
        targets[4] = pygame.math.Vector2(base_x, min(gy - 60, pelvis.y))
        targets[3] = pygame.math.Vector2(base_x, targets[4].y - spacing)
        targets[2] = pygame.math.Vector2(base_x, targets[3].y - spacing)
        targets[1] = pygame.math.Vector2(base_x, targets[2].y - spacing)
        targets[0] = pygame.math.Vector2(base_x, targets[1].y - self.head_size * 0.6)
                                                       
        foot_off = 14
        targets[7] = pygame.math.Vector2(base_x - foot_off, gy)
        targets[8] = pygame.math.Vector2(base_x + foot_off, gy)
        arm_drop = 14
        targets[5] = pygame.math.Vector2(base_x - 18, targets[2].y + arm_drop)
        targets[6] = pygame.math.Vector2(base_x + 18, targets[2].y + arm_drop)
        return targets

    def _apply_stand_controller(self, dt: float, ground_y: float | None):
        if self.freeze_torso:
            return
        targets = self._stand_targets(ground_y)
                                                                                      
        strength = 6.0 if self.user_dragging else 8.0
        damping = 0.9 if self.user_dragging else 0.925
        if self._sleep_torso:
                                                                                                     
            for idx in (0,1,2,3,4):
                p = self.particles[idx]
                targets[idx].x = p.pos.x
                targets[idx].y = p.pos.y
        self._apply_motors(targets, strength=strength, damping=damping, dt=dt)

    def set_user_dragging(self, dragging: bool):
        self.user_dragging = dragging

    def nearest_particle_index(self, pos, max_dist=40):
        best = None
        best_d = max_dist
        v = pygame.math.Vector2(pos)
        for i, p in enumerate(self.particles):
            d = (p.pos - v).length()
            if d < best_d:
                best_d = d
                best = i
        return best
