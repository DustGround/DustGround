import math
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
        head = Particle((x, y - 100))
        t1 = Particle((x, y - 60))
        t2 = Particle((x, y - 20))
        t3 = Particle((x, y + 20))
        t4 = Particle((x, y + 60))
        l_arm = Particle((x - 30, y - 10))
        r_arm = Particle((x + 30, y - 10))
        l_leg = Particle((x - 8, y + 140))
        r_leg = Particle((x + 8, y + 140))
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
        self.gravity = pygame.math.Vector2(0, 1800)
        self.iterations = 5
        self.user_dragging = False
        self._stand_anchor_x = None

    def apply_global_force(self, f):
        for p in self.particles:
            p.apply_force(f)

    def update(self, dt, bounds: tuple[int, int] | None=None):
        for p in self.particles:
            p.apply_force(self.gravity * p.mass)
        for p in self.particles:
            p.update(dt)
        ground_y = bounds[1] - 1 if bounds else None
        if ground_y is not None:
            for idx in (7, 8):
                foot = self.particles[idx]
                if foot.pos.y > ground_y:
                    foot.pos.y = ground_y
                foot.prev.x = foot.pos.x
        if self.user_dragging:
            self._apply_stand_controller(dt, ground_y)
        for _ in range(self.iterations):
            for i, j, rest in self.constraints:
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

    def _apply_motors(self, targets: dict[int, pygame.math.Vector2], strength: float, damping: float, dt: float):
        for idx, tgt in targets.items():
            p = self.particles[idx]
            dx = tgt.x - p.pos.x
            dy = tgt.y - p.pos.y
            if abs(dx) < 0.5 and abs(dy) < 0.5:
                continue
            if idx in (7, 8):
                sx, sy = (0.5, 1.0)
            else:
                sx, sy = (1.0, 1.0)
            p.pos.x += dx * strength * dt * sx
            p.pos.y += dy * strength * dt * sy
            p.prev.x = p.pos.x - (p.pos.x - p.prev.x) * damping
            p.prev.y = p.pos.y - (p.pos.y - p.prev.y) * damping

    def _stand_targets(self, ground_y: float | None) -> dict[int, pygame.math.Vector2]:
        pelvis = self.particles[4].pos
        if ground_y is not None:
            fx = (self.particles[7].pos.x + self.particles[8].pos.x) * 0.5
        else:
            fx = pelvis.x
        if self.user_dragging or self._stand_anchor_x is None:
            self._stand_anchor_x = fx
        else:
            self._stand_anchor_x = self._stand_anchor_x * 0.9 + fx * 0.1
        base_x = self._stand_anchor_x
        gy = ground_y if ground_y is not None else pelvis.y + 60
        spacing = 22
        targets = {}
        targets[4] = pygame.math.Vector2(base_x, min(gy - 60, pelvis.y))
        targets[3] = pygame.math.Vector2(base_x, targets[4].y - spacing)
        targets[2] = pygame.math.Vector2(base_x, targets[3].y - spacing)
        targets[1] = pygame.math.Vector2(base_x, targets[2].y - spacing)
        targets[0] = pygame.math.Vector2(base_x, targets[1].y - self.head_size * 0.6)
        foot_off = 10
        targets[7] = pygame.math.Vector2(base_x - foot_off, gy)
        targets[8] = pygame.math.Vector2(base_x + foot_off, gy)
        arm_drop = 14
        targets[5] = pygame.math.Vector2(base_x - 18, targets[2].y + arm_drop)
        targets[6] = pygame.math.Vector2(base_x + 18, targets[2].y + arm_drop)
        return targets

    def _apply_stand_controller(self, dt: float, ground_y: float | None):
        targets = self._stand_targets(ground_y)
        strength = 5.5 if self.user_dragging else 8.5
        damping = 0.9 if self.user_dragging else 0.92
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
