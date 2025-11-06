import json
import os
import random
import time
from typing import Dict, Tuple
import pygame
CONFIG_FILENAME = '.dustground_opt.json'

def _project_root() -> str:
    return os.path.dirname(os.path.dirname(__file__))

def _config_path() -> str:
    return os.path.join(_project_root(), CONFIG_FILENAME)

def _detect_gpu_available() -> bool:
    try:
        from pygame._sdl2.video import Window, Renderer, Texture
        from pygame._sdl2 import rect as sdl2rect
        return True
    except Exception:
        return False

def _bench_gpu_points(size: Tuple[int, int], n_points: int=40000, seconds: float=0.35) -> float:
    if not _detect_gpu_available():
        return 0.0
    from pygame._sdl2.video import Window, Renderer
    window = Window('bench', size=size)
    renderer = Renderer(window, vsync=False)
    clock = pygame.time.Clock()
    w, h = size
    points = [(random.randint(0, w - 1), random.randint(0, h - 1)) for _ in range(n_points)]
    frames = 0
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        pygame.event.pump()
        renderer.draw_color = (20, 20, 20, 255)
        renderer.clear()
        renderer.draw_color = (200, 200, 200, 255)
        renderer.draw_points(points)
        renderer.present()
        frames += 1
        clock.tick()
    elapsed = time.perf_counter() - start
    return frames / elapsed if elapsed > 0 else 0.0

def _bench_cpu_points(size: Tuple[int, int], n_points: int=40000, seconds: float=0.35) -> float:
    w, h = size
    surf = pygame.Surface((w, h))
    clock = pygame.time.Clock()
    pts = [(random.randint(0, w - 1), random.randint(0, h - 1)) for _ in range(n_points)]
    frames = 0
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        surf.fill((20, 20, 20))
        for x, y in pts:
            pygame.draw.circle(surf, (200, 200, 200), (x, y), 1)
        frames += 1
        clock.tick()
    elapsed = time.perf_counter() - start
    return frames / elapsed if elapsed > 0 else 0.0

def load_optimizations() -> Dict:
    path = _config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception:
            return {}
    return {}

def save_optimizations(cfg: Dict) -> None:
    path = _config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def get_or_create_optimizations(game_size: Tuple[int, int]) -> Dict:
    cfg = load_optimizations()
    gpu_avail = _detect_gpu_available()
    pygame_ver = pygame.version.ver
    if cfg.get('_meta', {}).get('pygame_version') == pygame_ver and cfg.get('_meta', {}).get('gpu_available') == gpu_avail:
        return cfg
    cpu_fps = _bench_cpu_points(game_size)
    gpu_fps = _bench_gpu_points(game_size) if gpu_avail else 0.0
    best_is_gpu = gpu_avail and gpu_fps > cpu_fps * 1.05
    best_fps = max(cpu_fps, gpu_fps)
    target_fps = 120 if best_fps >= 115 else 60
    n_points = 40000
    capacity_scale = best_fps / target_fps if target_fps > 0 else 1.0
    max_particles = int(n_points * max(0.2, min(2.0, capacity_scale)) * 0.85)
    max_particles = max(8000, min(150000, max_particles))
    new_cfg = {'use_gpu': bool(best_is_gpu), 'target_fps': int(target_fps), 'max_particles': int(max_particles), 'cpu_fps': float(round(cpu_fps, 2)), 'gpu_fps': float(round(gpu_fps, 2)), '_meta': {'pygame_version': pygame_ver, 'gpu_available': gpu_avail, 'generated_at': time.time()}}
    save_optimizations(new_cfg)
    return new_cfg
