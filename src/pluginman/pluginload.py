from __future__ import annotations
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict
from .pluginmain import get_service
try:
    from DgPy.core import set_game as _dgpy_set_game
except Exception:
    _dgpy_set_game = None
_loaded: Dict[str, ModuleType] = {}

def _ensure_sys_path(zip_path: str) -> None:
    zp = str(zip_path)
    if zp not in sys.path:
        sys.path.insert(0, zp)

def load_enabled_plugins(game) -> None:
    service = get_service()
    try:
        if callable(_dgpy_set_game):
            _dgpy_set_game(game)
    except Exception:
        pass
    for p in service.get_plugins():
        if not p.enabled:
            continue
        try:
            _ensure_sys_path(p.zip_path)
            mod_name = p.module or p.id or 'plugin'
            if p.id in _loaded:
                continue
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                mod = importlib.import_module('plugin')
            _loaded[p.id] = mod
            init_fn = getattr(mod, 'init', None) or getattr(mod, 'register', None)
            if callable(init_fn):
                try:
                    init_fn(game)
                except Exception:
                    pass
        except Exception:
            continue
