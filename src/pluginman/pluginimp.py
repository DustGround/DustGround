from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import List

from .pluginmodel import PluginInfo


def _read_manifest(z: zipfile.ZipFile) -> dict:
    # Try common manifest names
    for name in ("plugin.json", "manifest.json", "plugin/manifest.json"):
        try:
            with z.open(name) as f:
                return json.loads(f.read().decode("utf-8"))
        except Exception:
            continue
    return {}


def discover_plugins(plugins_dir: Path) -> List[PluginInfo]:
    plugins: List[PluginInfo] = []
    plugins_dir.mkdir(parents=True, exist_ok=True)
    for zip_path in sorted(plugins_dir.glob("*.zip")):
        try:
            with zipfile.ZipFile(zip_path) as z:
                manifest = _read_manifest(z)
        except Exception:
            manifest = {}
        pid = (manifest.get("id") or zip_path.stem).strip()
        name = manifest.get("name") or pid
        version = str(manifest.get("version", "1.0"))
        author = manifest.get("author", "Unknown")
        desc = manifest.get("description", "")
        module = manifest.get("module") or pid
        try:
            mtime = zip_path.stat().st_mtime
        except Exception:
            mtime = 0.0
        plugins.append(
            PluginInfo(
                id=pid,
                name=name,
                version=version,
                author=author,
                description=desc,
                zip_path=str(zip_path.resolve()),
                module=module,
                enabled=True,
                mtime=mtime,
            )
        )
    return plugins
