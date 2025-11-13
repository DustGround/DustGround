import json
import os
from typing import Dict, Any
SETTINGS_FILENAME = '.dustground_settings.json'

def _project_root() -> str:
    return os.path.dirname(os.path.dirname(__file__))

def _settings_path() -> str:
    return os.path.join(_project_root(), SETTINGS_FILENAME)

def default_settings() -> Dict[str, Any]:
    return {
        'renderer': 'Auto',
        'show_grid': True,
        'target_fps': 60,
        'max_particles': 50000,
        'invert_zoom': False,
        'master_volume': 100,
        'discord_rpc': True,
    }
essential_keys = set(default_settings().keys())

def load_settings() -> Dict[str, Any]:
    path = _settings_path()
    if not os.path.exists(path):
        cfg = default_settings()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass
        return cfg
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        base = default_settings()
        for k, v in base.items():
            data.setdefault(k, v)
        return {k: data.get(k, base[k]) for k in base.keys()}
    except Exception:
        return default_settings()

def save_settings(cfg: Dict[str, Any]) -> None:
    base = default_settings()
    out = {k: cfg.get(k, base[k]) for k in base.keys()}
    try:
        with open(_settings_path(), 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2)
    except Exception:
        pass
