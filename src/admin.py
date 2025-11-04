"""Admin panel logic for sandbox management.

This module centralizes admin actions so UI code can call into here.
"""
from typing import Any


def _try_clear_system(sys_obj: Any):
    """Attempt to clear a particle/block system gracefully."""
    if sys_obj is None:
        return
    # Preferred: dedicated clear method
    if hasattr(sys_obj, "clear") and callable(getattr(sys_obj, "clear")):
        try:
            sys_obj.clear()
            return
        except Exception:
            pass
    # Fallbacks for common attributes
    for attr in ("particles", "blocks", "grid", "cells"):
        if hasattr(sys_obj, attr):
            try:
                val = getattr(sys_obj, attr)
                if isinstance(val, dict):
                    val.clear()
                elif isinstance(val, list):
                    val.clear()
                else:
                    # Overwrite with empty collection of same type if possible
                    try:
                        setattr(sys_obj, attr, type(val)())
                    except Exception:
                        pass
            except Exception:
                pass


def clear_everything(game: Any) -> None:
    """Remove all content from the sandbox: particles, blocks, NPC, and effects.

    Parameters
    ----------
    game: the main game object that holds references to all systems.
    """
    # Clear particle/material systems
    for name in (
        "sand_system",
        "water_system",
        "oil_system",
        "lava_system",
        "toxic_system",
        "metal_system",
        "blood_system",
        "blocks_system",
    ):
        sys_obj = getattr(game, name, None)
        _try_clear_system(sys_obj)

    # Remove NPC and any drag state
    if hasattr(game, "npc"):
        game.npc = None
    if hasattr(game, "npc_drag_index"):
        game.npc_drag_index = None

    # Reset block drawing state
    if hasattr(game, "blocks_drag_active"):
        game.blocks_drag_active = False
    if hasattr(game, "blocks_drag_start"):
        game.blocks_drag_start = None
    if hasattr(game, "blocks_drag_current"):
        game.blocks_drag_current = None

    # Optionally hide panels after action
    if hasattr(game, "ui_show_admin"):
        game.ui_show_admin = False
    if hasattr(game, "ui_show_spawn"):
        game.ui_show_spawn = False

    # Invalidate any cached composite surfaces so next frame redraws cleanly
    if hasattr(game, "_game_surface"):
        game._game_surface = None
