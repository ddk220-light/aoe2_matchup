"""Resolve each military unit's idle SLD sprite path from the dat.

For every distinct named unit (UNIT_NAMES), find the id whose standing_graphic
file_name resolves to an idle SLD that exists on disk (x2 preferred, x1 fallback),
searched in graphics/game_raw_files then the AoE2:DE drs/graphics dir.

Emits a slug -> sld_path map to .scratch/sprite_paths.json (and prints a report).
Run with conda base python (genieutils).
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from build_unit_assets import RAW, GAME, NAME_FORCE_ID, NAME_DROP
from aoe2x.extract.extract_units import UNIT_NAMES

DAT = 'D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat'
DRS = os.path.join(GAME, 'resources', '_common', 'drs', 'graphics')

# Ships: the dat's standing_graphic.file_name is a placeholder ("W"/"X"), so they
# can't be resolved the normal way. Their real art lives under u_shp_<name> SLDs
# (16 directions, 1 static frame each — no _idle suffix). Map slug -> SLD basename.
# Note the Hulk line is spelled "holk" in the asset files (u_shp_holk / u_shp_war_holk),
# even though the dat graphic names are HULK_FNW / WARHULK_FNW.
NAVAL_SLD = {
    'galley': 'u_shp_galley', 'war_galley': 'u_shp_war_galley', 'galleon': 'u_shp_galleon',
    'fire_galley': 'u_shp_fire_galley', 'fire_ship': 'u_shp_fire_ship',
    'fast_fire_ship': 'u_shp_fast_fire_ship', 'demo_raft': 'u_shp_demo_raft',
    'demo_ship': 'u_shp_demo_ship', 'heavy_demo_ship': 'u_shp_heavy_demo_ship',
    'cannon_galleon': 'u_shp_cannon_galleon', 'elite_cannon_galleon': 'u_shp_elite_cannon_galleon',
    'carrack': 'u_shp_carrack', 'catapult_galleon': 'u_shp_catapult_galleon_idle',
    'hulk': 'u_shp_holk', 'war_hulk': 'u_shp_war_holk',
}

# Land units the name-based resolver mis-maps: UNIT_NAMES assigns the display
# name to the wrong dat id (several ids share a name, and the first one tried
# owns a neighbour's / placeholder's idle — e.g. "Steppe Lancer" lands on a
# battering-ram id, "Flemish Militia" on an iroquois id, the militia line is
# shifted). Pin these to the correct idle SLD directly, verified against each
# unit's standing_graphic in the dat. (NOTE: White Feather Guard -> ji_infantry
# and Xebec -> longboat_elite are dat-intended reuses, so they are NOT listed.)
LAND_SLD = {
    'militia': 'u_inf_militia_idleA',
    'man_at_arms': 'u_inf_manatarms_idleA',
    'long_swordsman': 'u_inf_longswordsman_idleA',
    'steppe_lancer': 'u_cav_steppe_lancer_idleA',
    'elite_steppe_lancer': 'u_cav_steppe_lancer_elite_idleA',
    'flemish_militia': 'u_inf_flemish_pikeman_idleA',
    'siege_tower': 'u_sie_siege_tower_idleA',
    'konnik_dismounted': 'u_inf_konnik_idleA',
}


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def find_on_disk(fname):
    """fname like 'u_cav_knight_idleC_x1' -> path of best matching .sld (x2>x1)."""
    if not fname or '_' not in fname:
        return None
    base = re.sub(r'_x[12]$', '', fname)            # strip resolution suffix
    for res in ('_x2', '_x1'):
        nm = base + res + '.sld'
        for d in (RAW, DRS):
            p = os.path.join(d, nm)
            if os.path.exists(p):
                return p
    return None


def main():
    from genieutils.datfile import DatFile
    df = DatFile.parse(DAT)
    g = df.civs[0]
    gby = {gr.id: gr for gr in df.graphics if gr}

    # name -> list of ids (preserve UNIT_NAMES order)
    name_ids = {}
    for uid, name in UNIT_NAMES.items():
        name_ids.setdefault(name, []).append(uid)
    # apply graphics-roster corrections (see build_unit_assets.NAME_FORCE_ID/NAME_DROP)
    for n in NAME_DROP:
        name_ids.pop(n, None)
    for n, fid in NAME_FORCE_ID.items():
        name_ids[n] = [fid]

    out, fails = {}, []
    for name, ids in name_ids.items():
        slug = slugify(name)
        found = None
        # Ships first: resolve directly from the u_shp_ name map (dat pointer is broken).
        if slug in NAVAL_SLD:
            found = find_on_disk(NAVAL_SLD[slug])
            if found:
                out[slug] = found
                continue
        # Land overrides for units the name->id heuristic mis-maps.
        if slug in LAND_SLD:
            found = find_on_disk(LAND_SLD[slug])
            if found:
                out[slug] = found
                continue
        for uid in ids:
            u = g.units[uid] if uid < len(g.units) else None
            sg = getattr(u, 'standing_graphic', None) if u else None
            gid = sg[0] if sg else -1
            gr = gby.get(gid)
            if gr:
                # Only accept a RESTING pose: an _idle sprite, or a ship sprite
                # (u_shp_*, which has no idle suffix). Reject deprecated dat ids whose
                # standing_graphic points at a decay/death/walk or building (p_) sprite.
                bn = re.sub(r'_x[12]$', '', gr.file_name or '').lower()
                if not ('idle' in bn or bn.startswith('u_shp_')):
                    continue
                p = find_on_disk(gr.file_name)
                if p:
                    found = p
                    break
        if found:
            out[slug] = found
        else:
            fails.append((slug, name))

    json.dump(out, open('.scratch/sprite_paths.json', 'w'), indent=0)
    print(f'resolved: {len(out)} / {len(name_ids)}')
    print(f'FAILED: {len(fails)}')
    for s, n in sorted(fails):
        print(f'   {s:30s} {n}')


if __name__ == '__main__':
    main()
