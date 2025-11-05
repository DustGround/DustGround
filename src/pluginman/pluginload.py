from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict

from .pluginmain import get_service
try:
    # Make active game available to DgPy before plugin init
    from DgPy.core import set_game as _dgpy_set_game
except Exception:  # pragma: no cover
    _dgpy_set_game = None

_loaded: Dict[str, ModuleType] = {}


def _ensure_sys_path(zip_path: str) -> None:
    zp = str(zip_path)
    if zp not in sys.path:
        sys.path.insert(0, zp)


def load_enabled_plugins(game) -> None:
    """Import and initialize all enabled plugins.
    Each plugin zip may declare a module in its manifest; default is plugin id.
    We attempt to import that module, falling back to 'plugin' if needed.
    If the module exposes init(game) or register(game), it will be called.
    """
    service = get_service()
    # Provide active game to DgPy so plugins can immediately register content
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
            mod_name = p.module or p.id or "plugin"
            if p.id in _loaded:
                continue  # already loaded this session
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                # fallback to a generic 'plugin' module name
                mod = importlib.import_module("plugin")
            _loaded[p.id] = mod
            # Initialize if entry point exists
            init_fn = getattr(mod, "init", None) or getattr(mod, "register", None)
            if callable(init_fn):
                try:
                    init_fn(game)
                except Exception:
                    # Don't break the app due to plugin errors
                    pass
        except Exception:
            # Skip on any error; a broken plugin shouldn't crash the game
            continue
