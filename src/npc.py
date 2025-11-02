import math
import pygame


class Particle:
    def __init__(self, pos, mass=1.0):
        self.pos = pygame.math.Vector2(pos)
        self.prev = pygame.math.Vector2(pos)
        self.acc = pygame.math.Vector2(0, 0)
        self.mass = mass

    def apply_force(self, f):
        self.acc += f / max(self.mass, 1e-6)

    def update(self, dt):
        # Verlet integration
        vel = self.pos - self.prev
        self.prev = self.pos.copy()
        self.pos += vel + self.acc * (dt * dt)
        # reset accel
        self.acc.update(0, 0)


class NPC:
    """A simple blocky NPC: head + torso chain + arms + legs with distance constraints.
    Coordinates are in pixels (same space as the sand/water game surface).
    """

    def __init__(self, x, y):
        self.particles = []
        self.constraints = []

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

        # Torso chain
        connect(0, 1)
        connect(1, 2)
        connect(2, 3)
        connect(3, 4)
        # Arms to mid torso
        connect(2, 5)
        connect(2, 6)
        # Legs to lower torso
        connect(4, 7)
        connect(4, 8)
        # Extra diagonals for a bit of rigidity
        connect(1, 3, slack=0.05)
        connect(2, 4, slack=0.05)

        # Visuals tuned to match a simple pixel-doll look (light gray body)
        self.size = 12
        self.head_size = 28
        self.color = (205, 205, 210)
        self.outline = (120, 120, 130)

        # Physics and solver
        self.gravity = pygame.math.Vector2(0, 1800)  # original gravity feel
        self.iterations = 5  # constraint solver iterations per frame

        # Control
        self.user_dragging = False
        self._stand_anchor_x = None

    def apply_global_force(self, f):
        for p in self.particles:
            p.apply_force(f)

    def update(self, dt, bounds: tuple[int, int] | None = None):
        # Gravity
        for p in self.particles:
            p.apply_force(self.gravity * p.mass)

        # Integrate
        for p in self.particles:
            p.update(dt)

        ground_y = bounds[1] - 1 if bounds else None

        # Mild ground interaction to reduce sideways oscillation
        if ground_y is not None:
            for idx in (7, 8):
                foot = self.particles[idx]
                if foot.pos.y > ground_y:
                    foot.pos.y = ground_y
                # add mild horizontal friction
                vx = foot.pos.x - foot.prev.x
                foot.prev.x = foot.pos.x - vx * 0.5

        # Always apply a gentle standing controller (no special states)
        self._apply_stand_controller(dt, ground_y)

        # Satisfy constraints
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

        # Keep in bounds
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

    def draw(self, surf: pygame.Surface):
        # Helper: draw an oriented rectangle (bone) between a and b
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
            # inner poly
            def inset_pt(px, py, qx, qy):
                return (px + (qx - px) * 0.15, py + (qy - py) * 0.15)
            ip1 = inset_pt(*p1, *p2)
            ip2 = inset_pt(*p2, *p3)
            ip3 = inset_pt(*p3, *p4)
            ip4 = inset_pt(*p4, *p1)
            pygame.draw.polygon(surf, self.color, (ip1, ip2, ip3, ip4))

        # Torso
        torso = [self.particles[i].pos for i in (0, 1, 2, 3, 4)]
        for a, b in zip(torso[:-1], torso[1:]):
            draw_bone(a, b, self.size * 0.55)

        # Arms
        mid = self.particles[2].pos
        la = self.particles[5].pos
        ra = self.particles[6].pos
        draw_bone(mid, la, self.size * 0.35)
        draw_bone(mid, ra, self.size * 0.35)

        # Legs
        hip = self.particles[4].pos
        ll = self.particles[7].pos
        rl = self.particles[8].pos
        draw_bone(hip, ll, self.size * 0.42)
        draw_bone(hip, rl, self.size * 0.42)

        # Head (square with small eye)
        head_pos = self.particles[0].pos
        hs = int(self.head_size)
        head_rect = pygame.Rect(0, 0, hs, hs)
        head_rect.center = (int(head_pos.x), int(head_pos.y))
        pygame.draw.rect(surf, self.outline, head_rect)
        inner = head_rect.inflate(-3, -3)
        pygame.draw.rect(surf, self.color, inner)
        # eye
        eye = pygame.Rect(0, 0, max(2, hs//10), max(2, hs//10))
        eye.center = (head_rect.centerx + hs//5, head_rect.centery - hs//8)
        pygame.draw.rect(surf, (90, 90, 100), eye)

    # --- Control helpers ---
    def _apply_motors(self, targets: dict[int, pygame.math.Vector2], strength: float, damping: float, dt: float):
        for idx, tgt in targets.items():
            p = self.particles[idx]
            # Move position slightly toward target
            dx = (tgt.x - p.pos.x)
            dy = (tgt.y - p.pos.y)
            # deadband to avoid micro jitters
            if abs(dx) < 0.5 and abs(dy) < 0.5:
                continue
            # feet move less horizontally to prevent see-saw
            if idx in (7, 8):
                sx, sy = 0.5, 1.0
            else:
                sx, sy = 1.0, 1.0
            p.pos.x += dx * strength * dt * sx
            p.pos.y += dy * strength * dt * sy
            # Damp velocity
            p.prev.x = p.pos.x - (p.pos.x - p.prev.x) * damping
            p.prev.y = p.pos.y - (p.pos.y - p.prev.y) * damping

    def _stand_targets(self, ground_y: float | None) -> dict[int, pygame.math.Vector2]:
        # Reference points
        pelvis = self.particles[4].pos
        # Anchor base to feet average when available to avoid lateral chasing
        if ground_y is not None:
            fx = (self.particles[7].pos.x + self.particles[8].pos.x) * 0.5
        else:
            fx = pelvis.x
        if self.user_dragging or self._stand_anchor_x is None:
            self._stand_anchor_x = fx
        else:
            # smooth the anchor
            self._stand_anchor_x = self._stand_anchor_x * 0.9 + fx * 0.1
        base_x = self._stand_anchor_x
        gy = ground_y if ground_y is not None else pelvis.y + 60
        spacing = 22
        targets = {}
        # Torso stack vertically above pelvis
        targets[4] = pygame.math.Vector2(base_x, min(gy - 60, pelvis.y))
        targets[3] = pygame.math.Vector2(base_x, targets[4].y - spacing)
        targets[2] = pygame.math.Vector2(base_x, targets[3].y - spacing)
        targets[1] = pygame.math.Vector2(base_x, targets[2].y - spacing)
        targets[0] = pygame.math.Vector2(base_x, targets[1].y - self.head_size * 0.6)
        # Feet under pelvis
        foot_off = 10
        targets[7] = pygame.math.Vector2(base_x - foot_off, gy)
        targets[8] = pygame.math.Vector2(base_x + foot_off, gy)
        # Arms hanging
        arm_drop = 14
        targets[5] = pygame.math.Vector2(base_x - 18, targets[2].y + arm_drop)
        targets[6] = pygame.math.Vector2(base_x + 18, targets[2].y + arm_drop)
        return targets

    def _apply_stand_controller(self, dt: float, ground_y: float | None):
        targets = self._stand_targets(ground_y)
        # Reduce strength while dragging; increase damping a bit to reduce overshoot
        strength = 5.5 if self.user_dragging else 8.5
        damping = 0.9 if self.user_dragging else 0.92
        self._apply_motors(targets, strength=strength, damping=damping, dt=dt)

    # External control hooks
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
