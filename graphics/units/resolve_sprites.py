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
