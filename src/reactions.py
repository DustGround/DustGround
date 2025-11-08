from __future__ import annotations

from typing import Any
import random


def _mark_dead(items):
    for p in items:
        try:
            setattr(p, 'dead', True)
        except Exception:
            pass


def _limit(lst, n):
    return lst if len(lst) <= n else lst[:n]


def apply(game: Any) -> None:

    sand = getattr(game, 'sand_system', None)
    water = getattr(game, 'water_system', None)
    lava = getattr(game, 'lava_system', None)
    oil = getattr(game, 'oil_system', None)
    toxic = getattr(game, 'toxic_system', None)
    metal = getattr(game, 'metal_system', None)
    dirt = getattr(game, 'dirt_system', None)
    milk = getattr(game, 'milk_system', None)
    blood = getattr(game, 'blood_system', None)
    if not (sand and water and lava and metal):
        return

    try:
        sand._rebuild_grid()
    except Exception:
        pass
    try:
        water._rebuild_grid()
    except Exception:
        pass
    if oil:
        try:
            oil._rebuild_grid()
        except Exception:
            pass
    if toxic:
        try:
            toxic._rebuild_grid()
        except Exception:
            pass
    try:
        lava._rebuild_grid()
    except Exception:
        pass
    if dirt:
        try:
            dirt._rebuild_grid()
        except Exception:
            pass
    if milk:
        try:
            milk._rebuild_grid()
        except Exception:
            pass
    if blood:
        try:
            blood._rebuild_grid()
        except Exception:
            pass

    get_sand = getattr(game, '_get_nearby_sand', None)
    get_water = getattr(game, '_get_nearby_water', None)
    get_lava = getattr(game, '_get_nearby_lava', None)
    get_toxic = getattr(game, '_get_nearby_toxic', None)
    get_oil = getattr(game, '_get_nearby_oil', None)
    get_dirt = getattr(game, '_get_nearby_dirt', None)
    get_milk = getattr(game, '_get_nearby_milk', None)
    get_blood = getattr(game, '_get_nearby_blood', None)

    MAX_N = 12

    sand_to_kill = set()
    water_to_kill = set()
    lava_to_kill = set()
    toxic_to_kill = set()
    extinguish_oil = []
    dirt_to_kill = set()
    milk_to_kill = set()
    blood_to_kill = set()

    for lp in list(lava.particles):
        if get_water:
            waters = get_water(lp.x, lp.y, radius=2)
            waters = _limit(waters, MAX_N)
            if waters:
                for w in waters:
                    try:
                        metal.add_particle(w.x, w.y)
                    except Exception:
                        pass
                    water_to_kill.add(id(w))
                if len(waters) >= 3:
                    lava_to_kill.add(id(lp))
        if get_sand:
            sands = get_sand(lp.x, lp.y, radius=2)
            sands = _limit(sands, MAX_N)
            if sands:
                for s in sands:
                    try:
                        metal.add_particle(s.x, s.y)
                    except Exception:
                        pass
                    sand_to_kill.add(id(s))
        if dirt and get_dirt:
            dirts = get_dirt(lp.x, lp.y, radius=2)
            dirts = _limit(dirts, MAX_N)
            if dirts:
                for d in dirts:
                    try:
                        metal.add_particle(d.x, d.y)
                    except Exception:
                        pass
                    dirt_to_kill.add(id(d))
                if len(dirts) >= 3:
                    lava_to_kill.add(id(lp))
        if milk and get_milk:
            milks = get_milk(lp.x, lp.y, radius=2)
            milks = _limit(milks, MAX_N)
            if milks:
                for m in milks:
                    milk_to_kill.add(id(m))
                if len(milks) >= 2:
                    lava_to_kill.add(id(lp))
        if oil and get_oil:
            oils = get_oil(lp.x, lp.y, radius=2)
            oils = _limit(oils, MAX_N)
            for op in oils:
                try:
                    op.ignite(200)
                except Exception:
                    pass
        if toxic and get_toxic:
            toxics = get_toxic(lp.x, lp.y, radius=2)
            toxics = _limit(toxics, MAX_N)
            if toxics:
                for tp in toxics:
                    try:
                        metal.add_particle(tp.x, tp.y)
                    except Exception:
                        pass
                    toxic_to_kill.add(id(tp))

    if oil and get_water:
        for op in list(oil.particles):
            if getattr(op, 'burning', False):
                waters = get_water(op.x, op.y, radius=2)
                if waters:
                    try:
                        op.burning = False
                        op.burn_timer = 0
                    except Exception:
                        pass
                    extinguish_oil.append(op)

    if toxic and get_water:
        for tp in list(toxic.particles):
            waters = get_water(tp.x, tp.y, radius=1)
            if waters:
                try:
                    water.add_particle(tp.x, tp.y)
                except Exception:
                    pass
                toxic_to_kill.add(id(tp))

    if get_sand and water:
        for wp in _limit(list(water.particles), 3000):
            sands = get_sand(wp.x, wp.y, radius=1)
            for s in sands:
                try:
                    setattr(s, 'wet', True)
                except Exception:
                    pass
    # Water makes nearby dirt into mud (slower)
    if dirt and water and get_dirt:
        for wp in _limit(list(water.particles), 2000):
            dirts = get_dirt(wp.x, wp.y, radius=1)
            for d in dirts:
                try:
                    d.is_mud = True
                except Exception:
                    pass
                # Optional light absorption: rarely remove a water particle
                # if random.random() < 0.02:
                #     water_to_kill.add(id(wp))
                
    # Toxic contaminates dirt
    if dirt and toxic and get_toxic and get_dirt:
        for tp in _limit(list(toxic.particles), 2000):
            dirts = get_dirt(tp.x, tp.y, radius=1)
            for d in dirts:
                try:
                    d.contaminated = True
                except Exception:
                    pass
    # Milk interactions
    if milk and dirt and get_dirt:
        for mp in _limit(list(milk.particles), 1500):
            dirts = get_dirt(mp.x, mp.y, radius=1)
            for d in dirts:
                try:
                    setattr(d, 'fertile', True)
                except Exception:
                    pass
                if random.random() < 0.08:
                    milk_to_kill.add(id(mp))
    if milk and sand and get_sand:
        for mp in _limit(list(milk.particles), 1500):
            sands = get_sand(mp.x, mp.y, radius=1)
            for s in sands:
                try:
                    setattr(mp, 'sludge', True)
                except Exception:
                    pass
                if random.random() < 0.04:
                    milk_to_kill.add(id(mp))
    if milk and water and get_water:
        for mp in _limit(list(milk.particles), 1500):
            waters = get_water(mp.x, mp.y, radius=1)
            if waters:
                try:
                    setattr(mp, 'diluted', True)
                except Exception:
                    pass
    if milk and toxic and get_toxic:
        for tp in _limit(list(toxic.particles), 1500):
            milks = get_milk(tp.x, tp.y, radius=1) if get_milk else []
            for m in milks:
                try:
                    m.toxic = True
                except Exception:
                    pass
    # Blood interactions
    if blood and water and get_water and get_blood:
        for wp in _limit(list(water.particles), 1200):
            bloods = get_blood(wp.x, wp.y, radius=1)
            for b in bloods:
                try:
                    b.diluted = True
                except Exception:
                    pass
    if blood and sand and get_sand and get_blood:
        for sp in _limit(list(sand.particles), 1200):
            bloods = get_blood(sp.x, sp.y, radius=1)
            for b in bloods:
                try:
                    b.soaked = True
                except Exception:
                    pass
                try:
                    setattr(sp, 'wet', True)
                except Exception:
                    pass
    if blood and dirt and get_dirt and get_blood:
        for dp in _limit(list(dirt.particles), 1200):
            bloods = get_blood(dp.x, dp.y, radius=1)
            for b in bloods:
                try:
                    b.soaked = True
                except Exception:
                    pass
                try:
                    dp.is_mud = True
                except Exception:
                    pass
    if blood and toxic and get_toxic and get_blood:
        for tp in _limit(list(toxic.particles), 1200):
            bloods = get_blood(tp.x, tp.y, radius=1)
            for b in bloods:
                try:
                    b.mutant = True
                except Exception:
                    pass
    if blood and milk and get_milk and get_blood:
        for mp in _limit(list(milk.particles), 800):
            bloods = get_blood(mp.x, mp.y, radius=1)
            for b in bloods:
                try:
                    b.curdled = True
                    b.diluted = False  # pink chunky overrides dilution
                except Exception:
                    pass
    if blood and lava and get_lava and get_blood:
        for lp in _limit(list(lava.particles), 1200):
            bloods = get_blood(lp.x, lp.y, radius=2)
            for b in bloods:
                try:
                    b.dead = True
                except Exception:
                    pass
    # Optional simple corrosion placeholder: blood near metal darkens metal (TODO real rust)
    if blood and metal and get_blood:
        for mp in _limit(list(metal.particles), 800):
            bloods = get_blood(mp.x, mp.y, radius=1)
            if bloods:
                try:
                    setattr(mp, 'rust_age', getattr(mp, 'rust_age', 0) + 1)
                except Exception:
                    pass
    # Contamination spreads slowly among dirt
    if dirt:
        contaminated = [p for p in dirt.particles if getattr(p, 'contaminated', False)]
        for d in _limit(contaminated, 500):
            if getattr(d, 'age', 0) % 8 != 0:
                continue
            # spread to a couple nearby dirt
            try:
                nx = d.x + random.randint(-3, 3)
                ny = d.y + random.randint(-3, 3)
                if get_dirt:
                    neighbors = _limit(get_dirt(nx, ny, radius=1), 3)
                    for n in neighbors:
                        setattr(n, 'contaminated', True)
            except Exception:
                pass

    if sand_to_kill:
        for p in sand.particles:
            if id(p) in sand_to_kill:
                setattr(p, 'dead', True)
        sand.sweep_dead()
    if water_to_kill:
        for p in water.particles:
            if id(p) in water_to_kill:
                setattr(p, 'dead', True)
        water.sweep_dead()
    if lava_to_kill:
        for p in lava.particles:
            if id(p) in lava_to_kill:
                setattr(p, 'dead', True)
        lava.sweep_dead()
    if dirt and dirt_to_kill:
        for p in dirt.particles:
            if id(p) in dirt_to_kill:
                setattr(p, 'dead', True)
        dirt.sweep_dead()
    if toxic and toxic_to_kill:
        for p in toxic.particles:
            if id(p) in toxic_to_kill:
                setattr(p, 'dead', True)
        toxic.sweep_dead()
    if milk and milk_to_kill:
        for p in milk.particles:
            if id(p) in milk_to_kill:
                setattr(p, 'dead', True)
        milk.sweep_dead()
    if blood and blood_to_kill:
        for p in blood.particles:
            if id(p) in blood_to_kill:
                setattr(p, 'dead', True)
        try:
            blood.sweep_dead()
        except Exception:
            pass
