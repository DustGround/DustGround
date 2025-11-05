from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from . import pluginimp
from .pluginmodel import PluginInfo

_STATE_FILE = ".dustground_plugins.json"


class PluginService:
    """Background service that watches the Plugins directory and tracks plugin metadata.
    Stores enablement in a JSON file at project root, merges with discovery.
    """

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.plugins_dir = self.root_dir / "Plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._plugins: Dict[str, PluginInfo] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._state_path = self.root_dir / _STATE_FILE
        self._enabled_cache: Dict[str, bool] = self._load_enabled_state()

    # --- persistence ---
    def _load_enabled_state(self) -> Dict[str, bool]:
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text())
                if isinstance(data, dict):
                    return {str(k): bool(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def _save_enabled_state(self) -> None:
        try:
            self._state_path.write_text(json.dumps(self._enabled_cache, indent=2))
        except Exception:
            pass

    # --- public API ---
    def refresh_now(self) -> None:
        found = pluginimp.discover_plugins(self.plugins_dir)
        with self._lock:
            # merge
            by_id = {p.id: p for p in found}
            for pid, pinf in by_id.items():
                # preserve enabled state from cache if present
                if pid in self._enabled_cache:
                    pinf.enabled = bool(self._enabled_cache[pid])
            # rebuild
            self._plugins = by_id

    def get_plugins(self) -> List[PluginInfo]:
        with self._lock:
            return [p for p in self._plugins.values()]

    def get(self, plugin_id: str) -> Optional[PluginInfo]:
        with self._lock:
            return self._plugins.get(plugin_id)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self._lock:
            if plugin_id in self._plugins:
                self._plugins[plugin_id].enabled = bool(enabled)
            self._enabled_cache[plugin_id] = bool(enabled)
        self._save_enabled_state()

    def enable_all(self) -> None:
        with self._lock:
            for pid in self._plugins:
                self._plugins[pid].enabled = True
                self._enabled_cache[pid] = True
        self._save_enabled_state()

    def disable_all(self) -> None:
        with self._lock:
            for pid in self._plugins:
                self._plugins[pid].enabled = False
                self._enabled_cache[pid] = False
        self._save_enabled_state()

    def start(self, interval: float = 1.5) -> None:
        if self._thread is not None:
            return
        self.refresh_now()

        def _run():
            while not self._stop.is_set():
                try:
                    self.refresh_now()
                except Exception:
                    pass
                self._stop.wait(interval)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None


# --- module-level helpers ---
_service: Optional[PluginService] = None


def start_plugin_service(root_dir: Optional[Path] = None) -> PluginService:
    global _service
    if _service is None:
        base = Path(root_dir) if root_dir else Path.cwd()
        _service = PluginService(base)
        _service.start()
    return _service


def get_service() -> PluginService:
    if _service is None:
        # lazy start if not started
        return start_plugin_service(Path.cwd())
    return _service
