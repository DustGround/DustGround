from __future__ import annotations

import time
from pathlib import Path

try:
    import pygame
except Exception:  # pragma: no cover
    pygame = None  # type: ignore

_place_sound = None
_last_play = 0.0
_cooldown = 0.05  # seconds between plays to avoid spam


def _ensure_mixer():
    if pygame is None:
        return False
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        return True
    except Exception:
        return False


def _resolve_sound_path() -> Path | None:
    candidates = [
        Path(__file__).resolve().parent / "assets" / "sandplace.wav",
        Path(__file__).resolve().parent / "src" / "assets" / "sandplace.wav",
        Path("src/assets/sandplace.wav").resolve(),
    ]
    for p in candidates:
        try:
            if p.is_file():
                return p
        except Exception:
            continue
    return None


def _ensure_loaded():
    global _place_sound
    if _place_sound is not None:
        return
    if not _ensure_mixer():
        return
    sp = _resolve_sound_path()
    if sp is None:
        return
    try:
        _place_sound = pygame.mixer.Sound(str(sp))
    except Exception:
        _place_sound = None


def play_place():
    global _last_play
    if pygame is None:
        return
    _ensure_loaded()
    if _place_sound is None:
        return
    now = time.time()
    if now - _last_play < _cooldown:
        return
    try:
        _place_sound.play()
        _last_play = now
    except Exception:
        pass
