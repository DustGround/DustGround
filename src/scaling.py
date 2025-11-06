from typing import Dict

def recommend_settings(total_particles: int, fps: float, target_fps: int, gpu: bool) -> Dict:
    if fps >= target_fps * 0.95:
        tier = 0
    elif fps >= target_fps * 0.8:
        tier = 1
    elif fps >= target_fps * 0.65:
        tier = 2
    else:
        tier = 3
    if total_particles > 100000:
        tier += 2
    elif total_particles > 60000:
        tier += 1
    if tier < 0:
        tier = 0
    if tier > 4:
        tier = 4
    sand = {'neighbor_radius': 2, 'max_neighbors': 12, 'skip_mod': 1}
    water = {'neighbor_radius': 2, 'max_neighbors': 10, 'skip_mod': 1}
    if tier == 1:
        sand.update({'max_neighbors': 8, 'skip_mod': 2})
        water.update({'max_neighbors': 8, 'skip_mod': 2})
    elif tier == 2:
        sand.update({'neighbor_radius': 2, 'max_neighbors': 6, 'skip_mod': 3})
        water.update({'neighbor_radius': 2, 'max_neighbors': 6, 'skip_mod': 3})
    elif tier >= 3:
        sand.update({'neighbor_radius': 1, 'max_neighbors': 4, 'skip_mod': 4})
        water.update({'neighbor_radius': 1, 'max_neighbors': 4, 'skip_mod': 4})
    if not gpu and tier >= 1:
        sand['skip_mod'] = max(2, sand['skip_mod'])
        water['skip_mod'] = max(2, water['skip_mod'])
    return {'sand': sand, 'water': water}
