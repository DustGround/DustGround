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
    blue_lava = getattr(game, 'blue_lava_system', None)
    ruby = getattr(game, 'ruby_system', None)
    diamond = getattr(game, 'diamond_system', None)
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
    if ruby:
        try:
            ruby._rebuild_grid()
        except Exception:
            pass
    if diamond:
        try:
            diamond._rebuild_grid()
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
    get_ruby = getattr(game, '_get_nearby_ruby', None)
    get_bluelava = getattr(game, '_get_nearby_bluelava', None)
    get_diamond = getattr(game, '_get_nearby_diamond', None)

    MAX_N = 12

    sand_to_kill = set()
    water_to_kill = set()
    lava_to_kill = set()
    toxic_to_kill = set()
    extinguish_oil = []
    dirt_to_kill = set()
    milk_to_kill = set()
    blood_to_kill = set()

    # Regular lava interactions
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
    # Blue lava ultra-hot interactions
    if blue_lava:
        for bp in list(blue_lava.particles):
            # Water: explosive -> convert water to metal shards (obsidian-like) and kill nearby blue lava sometimes
            if get_water:
                waters = get_water(bp.x, bp.y, radius=2)
                waters = _limit(waters, MAX_N)
                if waters:
                    for w in waters:
                        try:
                            metal.add_particle(w.x, w.y)
                        except Exception:
                            pass
                        water_to_kill.add(id(w))
                    # chance to remove some blue lava from explosive cooling
                    if len(waters) >= 2 and random.random() < 0.4:
                        lava_to_kill.add(id(bp))
            # Sand: fuse into blue glass -> add metal particle tinted (placeholder) and remove sand
            if get_sand:
                sands = get_sand(bp.x, bp.y, radius=2)
                sands = _limit(sands, MAX_N)
                for s in sands:
                    try:
                        metal.add_particle(s.x, s.y)
                        setattr(metal.particles[-1], 'blue_glass', True)
                    except Exception:
                        pass
                    sand_to_kill.add(id(s))
            # Dirt: slag/obsidian -> convert to metal
            if dirt and get_dirt:
                dirts = get_dirt(bp.x, bp.y, radius=2)
                dirts = _limit(dirts, MAX_N)
                for d in dirts:
                    try:
                        metal.add_particle(d.x, d.y)
                    except Exception:
                        pass
                    dirt_to_kill.add(id(d))
            # Metal: melt into alloy -> duplicate/mutate existing metal particles nearby
            m_near = []
            try:
                m_near = [m for m in metal.particles if abs(m.x - bp.x) < 2 and abs(m.y - bp.y) < 2][:MAX_N]
            except Exception:
                m_near = []
            for mp in m_near:
                try:
                    # accelerate rust_age or alloy_age
                    setattr(mp, 'alloy_age', getattr(mp, 'alloy_age', 0) + 3)
                except Exception:
                    pass
            # Toxic: vapor -> kill toxic and spawn more metal (radioactive residue placeholder)
            if toxic and get_toxic:
                toxics = get_toxic(bp.x, bp.y, radius=2)
                toxics = _limit(toxics, MAX_N)
                for tp in toxics:
                    try:
                        metal.add_particle(tp.x, tp.y)
                        setattr(metal.particles[-1], 'radioactive', True)
                    except Exception:
                        pass
                    toxic_to_kill.add(id(tp))
            # Milk: burn instantly
            if milk and get_milk:
                milks = get_milk(bp.x, bp.y, radius=2)
                milks = _limit(milks, MAX_N)
                for m in milks:
                    milk_to_kill.add(id(m))
            # Blood: violent vaporization
            if blood and get_blood:
                bloods = get_blood(bp.x, bp.y, radius=2)
                bloods = _limit(bloods, MAX_N)
                for b in bloods:
                    try:
                        setattr(b, 'dead', True)
                    except Exception:
                        pass
                    blood_to_kill.add(id(b))
            # Fuse with regular lava: chance -> both die and spawn metal
            if lava and random.random() < 0.02:
                # check for nearby regular lava
                near_lava = get_lava(bp.x, bp.y, radius=2) if get_lava else []
                if near_lava:
                    lava_to_kill.add(id(bp))
                    for lv in near_lava[:3]:
                        lava_to_kill.add(id(lv))
                        try:
                            metal.add_particle(lv.x, lv.y)
                        except Exception:
                            pass
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

    # Ruby interactions
    if ruby:
        for rp in list(ruby.particles):
            # Toxic: slow corrosion, occasionally neutralize a toxic particle
            if toxic and get_toxic:
                toxics = _limit(get_toxic(rp.x, rp.y, radius=1), MAX_N)
                for tp in toxics:
                    try:
                        setattr(rp, 'corroded', getattr(rp, 'corroded', 0) + 1)
                    except Exception:
                        pass

    # Diamond interactions
    if diamond:
        for dp in list(diamond.particles):
            # Toxic Waste: inert (no change)
            if toxic and get_toxic:
                _ = get_toxic(dp.x, dp.y, radius=1)  # ignored intentionally
            # Lava: absorb heat slowly; potential sublimation to carbon gas
            if lava and get_lava:
                lavas = get_lava(dp.x, dp.y, radius=1)
                if lavas:
                    try:
                        dp.heat = getattr(dp, 'heat', 0.0) + 0.4 * len(lavas)
                        # Sublimation threshold (very high heat)
                        if dp.heat > 220 and random.random() < 0.05:
                            # Replace with carbon gas placeholder -> toxic particle tinted dark
                            try:
                                toxic.add_particle(dp.x, dp.y)
                                setattr(toxic.particles[-1], 'carbon_gas', True)
                            except Exception:
                                pass
                            dp.dead = True
                    except Exception:
                        pass
            # Blue Lava: convert to synthetic diamond (bluish & conductive)
            if blue_lava and get_bluelava:
                bls = get_bluelava(dp.x, dp.y, radius=1)
                if bls:
                    try:
                        dp.synthetic = True
                        dp.heat = min(300.0, getattr(dp, 'heat', 0.0) + 1.0 * len(bls))
                    except Exception:
                        pass
            # Blood: stain only
            if blood and get_blood:
                bloods = get_blood(dp.x, dp.y, radius=1)
                if bloods:
                    try:
                        dp.stained = True
                    except Exception:
                        pass
            # Milk: frosting effect
            if milk and get_milk:
                milks = get_milk(dp.x, dp.y, radius=1)
                if milks:
                    try:
                        dp.frosted = True
                    except Exception:
                        pass
                    if random.random() < 0.04:
                        toxic_to_kill.add(id(tp))
            # Lava: heat up and charge over time
            if lava and get_lava:
                lavas = _limit(get_lava(rp.x, rp.y, radius=1), MAX_N)
                if lavas:
                    try:
                        rp.heat = getattr(rp, 'heat', 0) + len(lavas)
                        if random.random() < 0.02:
                            rp.charged = True
                    except Exception:
                        pass
            # Blue lava: overcharge and become unstable (may explode via ruby.update)
            if blue_lava and get_bluelava:
                bls = _limit(get_bluelava(rp.x, rp.y, radius=1), MAX_N)
                if bls:
                    try:
                        rp.charged = True
                        rp.overcharged = True
                        rp.unstable = max(getattr(rp, 'unstable', 0), random.randint(20, 90))
                    except Exception:
                        pass
            # Blood: curse
            if blood and get_blood:
                bloods = _limit(get_blood(rp.x, rp.y, radius=1), MAX_N)
                if bloods:
                    try:
                        rp.cursed = True
                    except Exception:
                        pass
            # Milk: dull/opaque
            if milk and get_milk:
                milks = _limit(get_milk(rp.x, rp.y, radius=1), MAX_N)
                if milks:
                    try:
                        rp.dulled = True
                    except Exception:
                        pass

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

        # Remove mehedi behavior: ensure any prior 'mehedi' sand reverts to 'meh' image/state.
        if sand:
            try:
                meh_img = getattr(game, '_meh_img', None)
                for sp in sand.particles:
                    if getattr(sp, 'mehedi', False):
                        try:
                            sp.mehedi = False
                            sp.meh = True
                            if meh_img is not None:
                                sp.image = meh_img
                        except Exception:
                            pass
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
