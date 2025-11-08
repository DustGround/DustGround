from typing import Any

def _try_clear_system(sys_obj: Any):
    if sys_obj is None:
        return
    if hasattr(sys_obj, 'clear') and callable(getattr(sys_obj, 'clear')):
        try:
            sys_obj.clear()
            return
        except Exception:
            pass
    for attr in ('particles', 'blocks', 'grid', 'cells'):
        if hasattr(sys_obj, attr):
            try:
                val = getattr(sys_obj, attr)
                if isinstance(val, dict):
                    val.clear()
                elif isinstance(val, list):
                    val.clear()
                else:
                    try:
                        setattr(sys_obj, attr, type(val)())
                    except Exception:
                        pass
            except Exception:
                pass

def clear_everything(game: Any) -> None:
    for name in (
        'sand_system', 'water_system', 'oil_system', 'lava_system', 'blue_lava_system', 'toxic_system',
        'metal_system', 'blood_system', 'blocks_system', 'dirt_system', 'milk_system'
    ):
        sys_obj = getattr(game, name, None)
        _try_clear_system(sys_obj)
    if hasattr(game, 'npc'):
        game.npc = None
    if hasattr(game, 'npc_drag_index'):
        game.npc_drag_index = None
    if hasattr(game, 'blocks_drag_active'):
        game.blocks_drag_active = False
    if hasattr(game, 'blocks_drag_start'):
        game.blocks_drag_start = None
    if hasattr(game, 'blocks_drag_current'):
        game.blocks_drag_current = None
    if hasattr(game, 'ui_show_admin'):
        game.ui_show_admin = False
    if hasattr(game, 'ui_show_spawn'):
        game.ui_show_spawn = False
    if hasattr(game, '_game_surface'):
        game._game_surface = None

def clear_living(game: Any) -> None:
    if hasattr(game, 'npcs'):
        try:
            game.npcs.clear()
        except Exception:
            try:
                game.npcs = []
            except Exception:
                pass
    if hasattr(game, 'active_npc'):
        game.active_npc = None
    if hasattr(game, 'npc_drag_index'):
        game.npc_drag_index = None
    if hasattr(game, 'npc'):
        game.npc = None

def clear_blocks(game: Any) -> None:
    sys_obj = getattr(game, 'blocks_system', None)
    _try_clear_system(sys_obj)
