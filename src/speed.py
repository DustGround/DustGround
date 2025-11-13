import math
from typing import Optional

try:
    import pygame
except Exception:  # pragma: no cover - pygame may not be available in static analysis
    pygame = None  # type: ignore


class SpeedController:
    def __init__(
        self,
        default_scale: float = 1.0,
        min_scale: float = 0.1,
        max_scale: float = 5.0,
        step: float = 0.1,
        max_steps_per_frame: int = 8,
    ) -> None:
        self.default_scale = float(default_scale)
        self.min_scale = float(min_scale)
        self.max_scale = float(max_scale)
        self.step = float(step)
        self.max_steps_per_frame = int(max_steps_per_frame)
        self.scale = float(default_scale)
        self.paused = False
        self._accum = 0.0

    # --- Public API -----------------------------------------------------
    def handle_event(self, event) -> bool:
        """Handle pygame.KEYDOWN events. Returns True if consumed/handled."""
        if pygame is None:
            return False
        if getattr(event, 'type', None) != pygame.KEYDOWN:
            return False
        key = getattr(event, 'key', None)
        if key == pygame.K_LEFT:
            self.decrease()
            return True
        if key == pygame.K_RIGHT:
            self.increase()
            return True
        if key == pygame.K_SPACE:
            self.reset()
            return True
        if key == pygame.K_p:
            self.toggle_pause()
            return True
        return False

    def increase(self) -> float:
        self.paused = False
        self.scale = min(self.max_scale, self.scale + self.step)
        return self.scale

    def decrease(self) -> float:
        self.paused = False
        self.scale = max(self.min_scale, self.scale - self.step)
        return self.scale

    def reset(self) -> float:
        self.paused = False
        self.scale = float(self.default_scale)
        self._accum = 0.0
        return self.scale

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def steps_for_frame(self) -> int:
        """
        Compute how many simulation steps to execute this render frame.
        0 means no update (paused or slow motion frame), >=1 means run that many
        update() calls.
        """
        if self.paused:
            return 0
        s = max(self.min_scale, min(self.max_scale, self.scale))
        if s >= 1.0:
            steps = int(math.floor(s))
            self._accum += s - steps
            if self._accum >= 1.0:
                steps += 1
                self._accum -= 1.0
            return min(steps, self.max_steps_per_frame)
        else:
            self._accum += s
            if self._accum >= 1.0:
                self._accum -= 1.0
                return 1
            return 0

    # Optional helpers for UI/telemetry
    def get_state(self) -> dict:
        return {
            'paused': self.paused,
            'scale': self.scale,
            'accum': self._accum,
            'min': self.min_scale,
            'max': self.max_scale,
        }
