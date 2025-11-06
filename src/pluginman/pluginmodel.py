from __future__ import annotations
from dataclasses import dataclass

@dataclass
class PluginInfo:
    id: str
    name: str
    version: str
    author: str
    description: str
    zip_path: str
    module: str
    enabled: bool = True
    mtime: float = 0.0
