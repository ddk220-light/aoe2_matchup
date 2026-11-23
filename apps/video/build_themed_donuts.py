"""Reskin the audited Winter Donut into civilization-themed Donuts (terrain + Gaia art only).

Each theme maps every Winter Donut terrain texture and Gaia object to a themed
counterpart *in place*. Gameplay is untouched and checked:

- every Gaia object keeps its position, rotation and reference id, and the new
  object has the identical DAT footprint (obstruction type/class, collision size);
- every tile keeps its elevation, and the new texture has the same accessibility
  as the old one for every creatable land unit's terrain restriction;
- armies, AI (ddkDonutQuietAI), diplomacy, camera and triggers are unchanged.

Outputs <out>/<theme>/<Title> Donut.aoe2scenario + .audit.json, which the
recorder accepts as a frozen Donut (aoe2x/lab/live.py capture_template_path).

    python apps/video/build_themed_donuts.py --out data/local/themed-donuts            # all themes
    python apps/video/build_themed_donuts.py --out data/local/themed-donuts --themes desert jungle
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/local/arena-donut-standard/donut-template/Winter Donut.aoe2scenario'
SOURCE_HASH = '4a499ec8a75d293bc3168e480ad7bdf3d945362358835b67afb2d239273a387f'
PICKLED_DAT = ROOT / 'data/local/viking-sagas-research/installed-dat.pkl'

# Winter Donut texture roles: base snow (6 shades), forest floor, ring path, accents.
# Only textures with snow's exact passability survive the check: navigable beaches,
# plain/broken roads and bogland differ (e.g. for ships/landing), so shores use the
# non-navigable beach set.
SNOWS = ('SNOW', 'SNOW_LIGHT', 'SNOW_SOFT', 'SNOW_SOFT_LIGHT', 'SNOW_SOFT_STRONG', 'SNOW_STRONG')


def theme(title, civs, region, base, forest, path, accents, pines, spruces, rocks, props, deco, player2_slots=27):
    """base: 6 textures for the 6 snow shades; accents: GRASS_DRY, GRASS_2, UNDERBRUSH_LEAVES, DIRT_3, ROCK_1."""
    terrain = dict(zip(SNOWS, base), UNDERBRUSH_SNOW=forest, ROAD_GRAVEL=path,
                   **dict(zip(('GRASS_DRY', 'GRASS_2', 'UNDERBRUSH_LEAVES', 'DIRT_3', 'ROCK_1'), accents)))
    # Gaia roles: snow pines / spruces (trees), snow rocks, the two plain rocks, small decorations.
    gaia = dict(TREE_SNOW_PINE=pines, SPRUCESNOW=spruces, ROCKSNOW=rocks,
                ROCK_1=props, ROCK_2=props, GRASS_DRY=deco, PLANT_DEAD=deco, STUMP=deco)
    return dict(title=title, civs=civs, region=region, terrain=terrain, gaia=gaia, player2Slots=player2_slots)


THEMES = {
    'desert': theme('Maghreb Oasis', ['Berbers'], 'North African desert oasis',
                    ['DESERT_SAND', 'DESERT_SAND', 'DESERT_SAND', 'GRAVEL_DESERT', 'DESERT_CRACKED', 'DESERT_SAND'],
                    'FOREST_PALM_DESERT', 'DIRT_2', ['GRASS_DRY', 'GRASS_DRY', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_PALM_FOREST', 'TREE_PALM_FOREST', 'TREE_ACACIA'], ['TREE_PALM_FOREST'],
                    ['ROCK_3'], ['ROCK_3', 'ROCK_2'], ['PLANT_DEAD', 'ANIMAL_SKELETON', 'VASES']),
    'jungle': theme('Peten Rainforest', ['Mayans'], 'Mesoamerican lowland jungle',
                    ['GRASS_JUNGLE', 'GRASS_JUNGLE', 'GRASS_JUNGLE_RAINFOREST', 'GRASS_JUNGLE', 'GRASS_JUNGLE_RAINFOREST', 'GRASS_JUNGLE_RAINFOREST'],
                    'UNDERBRUSH_JUNGLE', 'DIRT_MUD', ['GRASS_2', 'GRASS_1', 'UNDERBRUSH_JUNGLE', 'DIRT_MUD', 'ROCK_1'],
                    ['TREE_JUNGLE', 'TREE_JUNGLE', 'TREE_RAINFOREST'], ['TREE_PALM_FOREST'],
                    ['ROCK_JUNGLE'], ['OLD_STONE_HEAD', 'ROCK_LIMESTONE'], ['FERN_PATCH', 'PLANT_JUNGLE']),
    'tropical-shore': theme('Atlantic Forest Coast', ['Tupi'], 'Brazilian tropical shore',
                    ['BEACH_NON_NAVIGABLE', 'GRASS_JUNGLE', 'BEACH_NON_NAVIGABLE', 'BEACH_NON_NAVIGABLE_WET_SAND', 'GRASS_JUNGLE_RAINFOREST', 'BEACH_NON_NAVIGABLE'],
                    'FOREST_PALM_GRASS', 'BEACH_NON_NAVIGABLE_WET_SAND', ['GRASS_JUNGLE', 'GRASS_1', 'UNDERBRUSH_JUNGLE', 'BEACH_NON_NAVIGABLE_WET_ROCK', 'ROCK_1'],
                    ['TREE_PALM_FOREST', 'TREE_BRAZILWOOD', 'TREE_PALM_FOREST'], ['TREE_BRAZILWOOD'],
                    ['ROCK_LIMESTONE'], ['ROCK_LIMESTONE'], ['GRASS_PATCH_GREEN', 'SEA_ROCKS_1', 'FERN_PATCH'],
                    # Blackwood Archers: 2 per purchase, 0.5 population each; population-aware
                    # geometric cost gives 15 Paladins (Franks) about 39 of them.
                    player2_slots=39),
    'mangrove': theme('Sundarbans Delta', ['Bengalis'], 'Bengal mangrove delta',
                    ['GRASS_2', 'DIRT_MUD', 'GRASS_2', 'UNDERBRUSH_JUNGLE', 'SHALLOWS_MANGROVE', 'GRASS_2'],
                    'FOREST_MANGROVE', 'DIRT_MUD', ['GRASS_1', 'GRASS_2', 'UNDERBRUSH_JUNGLE', 'DIRT_MUD', 'ROCK_1'],
                    ['TREE_MANGROVE'], ['TREE_WILLOW'],
                    ['ROCK_2'], ['ROCK_2'], ['PLANT_UNDERBRUSH', 'GRASS_PATCH_GREEN']),
    'mediterranean': theme('Castilian Dehesa', ['Spanish'], 'Iberian Mediterranean woodland',
                    ['GRASS_DRY', 'GRASS_DRY', 'DIRT_1', 'GRASS_2', 'DIRT_3', 'GRASS_DRY'],
                    'FOREST_MEDITERRANEAN', 'GRAVEL_DEFAULT', ['GRASS_DRY', 'GRASS_2', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_OLIVE', 'TREE_OLIVE', 'TREE_CYPRESS'], ['TREE_ITALIAN_PINE'],
                    ['ROCK_LIMESTONE'], ['ROCK_LIMESTONE', 'ROCK_2'], ['PLANT_FLOWERS', 'PLANT_SHRUB_GREEN']),
    'araucania': theme('Araucania Highlands', ['Mapuche'], 'Chilean araucaria uplands',
                    ['GRASS_2', 'GRASS_1', 'GRASS_DRY', 'GRASS_2', 'DIRT_1', 'GRASS_1'],
                    'FOREST_DRY_SOUTH_AMERICAN', 'DIRT_1', ['GRASS_DRY', 'GRASS_2', 'DIRT_3', 'DIRT_3', 'ROCK_1'],
                    ['TREE_MONKEY_PUZZLE', 'TREE_MONKEY_PUZZLE', 'TREE_OAK_GREEN'], ['TREE_PINE_FOREST'],
                    ['ROCK_3'], ['ROCK_3', 'ROCK_1'], ['PLANT_SHRUB_GREEN', 'PLANT_DEAD']),
    'korean-autumn': theme('Korean Autumn', ['Koreans'], 'Korean hills in autumn',
                    ['GRASS_2', 'UNDERBRUSH_LEAVES', 'GRASS_DRY', 'GRASS_2', 'UNDERBRUSH_LEAVES', 'GRASS_2'],
                    'FOREST_AUTUMN', 'ROAD_GRAVEL', ['GRASS_DRY', 'GRASS_2', 'UNDERBRUSH_LEAVES', 'DIRT_3', 'ROCK_1'],
                    ['TREE_ASIAN_MAPLE_AUTUMN', 'TREE_ASIAN_MAPLE_AUTUMN', 'TREE_OAK_AUTUMN'], ['TREE_ASIAN_PINE'],
                    ['ROCK_LIMESTONE'], ['ROCK_LIMESTONE', 'ROCK_1'], ['PLANT_FLOWERS', 'PLANT_SHRUB_GREEN']),
    'blossom': theme('Yellow River Blossom', ['Wei'], 'Northern Chinese loess garden',
                    ['GRASS_2', 'GRASS_FLOWERS_1', 'DIRT_1', 'GRASS_2', 'GRASS_FLOWERS_1', 'GRASS_2'],
                    'FOREST_LUSH_BAMBOO', 'ROAD_FUNGUS', ['GRASS_2', 'GRASS_1', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_PEACH_BLOSSOM', 'TREE_PEACH_BLOSSOM', 'TREE_ASIAN_MAPLE_GREEN'], ['TREE_ASIAN_PINE'],
                    ['ROCK_LIMESTONE'], ['ROCK_LIMESTONE'], ['FALLEN_LEAVES_PEACH_BLOSSOM', 'PLANT_FLOWERS']),
    'dry-steppe': theme('Golden Horde Steppe', ['Tatars'], 'dry Volga steppe',
                    ['GRASS_DRY', 'GRASS_DRY', 'DIRT_SAVANNAH', 'GRASS_DRY', 'GRAVEL_DEFAULT', 'DIRT_SAVANNAH'],
                    'FOREST_DEAD', 'DIRT_2', ['GRASS_DRY', 'GRASS_DRY', 'DIRT_3', 'DIRT_3', 'ROCK_1'],
                    ['TREE_BIRCH', 'TREE_DEAD', 'TREE_BIRCH'], ['TREE_PINE_FOREST'],
                    ['ROCK_2'], ['BROKEN_CART', 'ROCK_2'], ['PLANT_DEAD', 'ANIMAL_SKELETON', 'GRASS_DRY']),
    'green-steppe': theme('Mongolian Steppe', ['Mongols'], 'green high steppe',
                    ['GRASS_1', 'GRASS_3', 'GRASS_2', 'GRASS_1', 'GRASS_3', 'GRASS_1'],
                    'FOREST_PINE', 'DIRT_1', ['GRASS_2', 'GRASS_1', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_PINE_FOREST', 'TREE_PINE_FOREST', 'TREE_BIRCH'], ['TREE_BIRCH'],
                    ['ROCK_1'], ['ROCK_3', 'ROCK_1'], ['GRASS_GREEN', 'PLANT_SHRUB_GREEN']),
    'pontic-steppe': theme('Pontic Grassland', ['Cumans'], 'Black Sea forest-steppe',
                    ['GRASS_DRY', 'GRASS_2', 'GRASS_DRY', 'DIRT_3', 'GRASS_DRY', 'GRASS_2'],
                    'FOREST_OAK', 'DIRT_2', ['GRASS_DRY', 'GRASS_2', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_OAK', 'TREE_OAK_GREEN', 'TREE_OAK'], ['TREE_WILLOW'],
                    ['ROCK_2'], ['BROKEN_CART', 'ROCK_2'], ['GRASS_DRY', 'PLANT_SHRUB_GREEN']),
    'pannonian-meadow': theme('Pannonian Meadow', ['Magyars'], 'Carpathian basin grassland',
                    ['GRASS_1', 'GRASS_FLOWERS_2', 'GRASS_2', 'GRASS_1', 'GRASS_FLOWERS_2', 'GRASS_1'],
                    'FOREST_OAK', 'ROAD_GRAVEL', ['GRASS_2', 'GRASS_1', 'UNDERBRUSH_LEAVES', 'DIRT_3', 'ROCK_1'],
                    ['TREE_OAK_FOREST', 'TREE_OAK_FOREST', 'TREE_BIRCH'], ['TREE_PINE_FOREST'],
                    ['ROCK_1'], ['ROCK_1', 'ROCK_2'], ['PLANT_FLOWERS', 'GRASS_GREEN']),
    'nordic-shore': theme('Jutland Shore', ['Danes'], 'Danish coastal heath',
                    ['GRASS_2', 'BEACH_NON_NAVIGABLE', 'GRASS_DRY', 'GRASS_2', 'BEACH_NON_NAVIGABLE_WET_GRAVEL', 'GRASS_2'],
                    'FOREST_PINE', 'BEACH_NON_NAVIGABLE_WET_SAND', ['GRASS_DRY', 'GRASS_2', 'BEACH_NON_NAVIGABLE', 'DIRT_3', 'ROCK_1'],
                    ['TREE_PINE_FOREST', 'TREE_PINE_FOREST', 'TREE_BIRCH'], ['TREE_BIRCH'],
                    ['ROCK_2'], ['ROCK_2', 'ROCK_1'], ['SEA_ROCKS_1', 'STUMP', 'GRASS_GREEN']),
    'anatolia': theme('Anatolian Plateau', ['Turks'], 'dry central Anatolian upland',
                    ['GRASS_DRY', 'DIRT_1', 'GRASS_DRY', 'DIRT_3', 'GRAVEL_DEFAULT', 'DIRT_1'],
                    'FOREST_MEDITERRANEAN', 'DIRT_2', ['GRASS_DRY', 'GRASS_2', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_CYPRESS', 'TREE_OAK', 'TREE_CYPRESS'], ['TREE_ITALIAN_PINE'],
                    ['ROCK_3'], ['ROCK_3', 'ROCK_2'], ['PLANT_DEAD', 'PLANT_SHRUB_GREEN']),
    'irrawaddy': theme('Irrawaddy Bamboo', ['Burmese'], 'Burmese river-valley bamboo forest',
                    ['GRASS_JUNGLE', 'GRASS_2', 'GRASS_JUNGLE', 'DIRT_MUD', 'GRASS_JUNGLE_RAINFOREST', 'GRASS_2'],
                    'FOREST_BAMBOO', 'DIRT_MUD', ['GRASS_1', 'GRASS_2', 'UNDERBRUSH_JUNGLE', 'DIRT_MUD', 'ROCK_1'],
                    ['TREE_BAMBOO_FOREST', 'TREE_JUNGLE', 'TREE_BAMBOO_FOREST'], ['TREE_PALM_FOREST'],
                    ['ROCK_JUNGLE'], ['ROCK_JUNGLE', 'ROCK_LIMESTONE'], ['FERN_PATCH', 'PLANT_JUNGLE']),
    'sahel': theme('Niger Sahel', ['Malians'], 'West African savanna',
                    ['DIRT_SAVANNAH', 'GRASS_DRY', 'DIRT_SAVANNAH', 'DIRT_1', 'DESERT_CRACKED', 'GRASS_DRY'],
                    'FOREST_BAOBAB', 'DIRT_2', ['GRASS_DRY', 'GRASS_DRY', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_BAOBAB', 'TREE_ACACIA', 'TREE_ACACIA'], ['TREE_BAOBAB'],
                    ['ROCK_2'], ['ROCK_2', 'ROCK_3'], ['PLANT_DEAD', 'GRASS_DRY']),
    'andean': theme('Bogota Highlands', ['Muisca'], 'Colombian Andean plateau',
                    ['GRASS_2', 'GRASS_1', 'GRASS_DRY', 'GRASS_2', 'DIRT_1', 'GRASS_FLOWERS_1'],
                    'FOREST_RAINFOREST', 'DIRT_1', ['GRASS_DRY', 'GRASS_2', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_WAX_PALM', 'TREE_OAK_GREEN', 'TREE_WAX_PALM'], ['TREE_RAINFOREST'],
                    ['ROCK_LIMESTONE'], ['ROCK_LIMESTONE', 'ROCK_1'], ['PLANT_FLOWERS', 'FERN_PATCH']),
    'dnieper': theme('Dnieper Birchwood', ['Varangians'], 'Kievan Rus river birch forest',
                    ['GRASS_2', 'GRASS_1', 'UNDERBRUSH_LEAVES', 'GRASS_2', 'GRASS_DRY', 'GRASS_1'],
                    'FOREST_BIRCH', 'DIRT_2', ['GRASS_DRY', 'GRASS_2', 'UNDERBRUSH_LEAVES', 'DIRT_3', 'ROCK_1'],
                    ['TREE_BIRCH', 'TREE_BIRCH', 'TREE_PINE_FOREST'], ['TREE_PINE_FOREST'],
                    ['ROCK_1'], ['ROCK_1', 'ROCK_2'], ['STUMP', 'GRASS_GREEN']),
    'levant': theme('Syrian Desert', ['Saracens'], 'Levantine desert edge',
                    ['DESERT_SAND', 'GRAVEL_DESERT', 'DESERT_SAND', 'DESERT_CRACKED', 'DIRT_1', 'DESERT_SAND'],
                    'FOREST_PALM_DESERT', 'GRAVEL_DESERT', ['GRASS_DRY', 'DIRT_1', 'DIRT_1', 'DIRT_3', 'ROCK_1'],
                    ['TREE_PALM_FOREST', 'TREE_ACACIA', 'TREE_PALM_FOREST'], ['TREE_CYPRESS'],
                    ['ROCK_3'], ['ROCK_3', 'BROKEN_CART'], ['VASES', 'PLANT_DEAD']),
}
# Huns (Eurasian steppe) and Jurchens (Manchuria) keep the reviewed Winter Donut itself.
WINTER = dict(title='Winter Steppe', civs=['Huns', 'Jurchens'], region='Eurasian winter steppe')


def footprint(dat, const):
    u = dat.civs[0].units[const]
    return (u.obstruction_type, u.obstruction_class, round(u.collision_size_x, 3), round(u.collision_size_y, 3))


def add_player2_slots(s, n, dat):
    """Append n Player 2 formation slots on free tiles touching the authored formation,
    farthest from Player 3 first (behind the line). The literal first 27 slots are
    untouched, so any army of 27 or fewer is placed exactly as before."""
    if n <= 0:
        return []
    p2 = list(s.unit_manager.units[2])
    taken = {(int(u.x), int(u.y)) for p in range(1, 9) for u in s.unit_manager.units[p]}
    blocked = {(int(u.x), int(u.y)) for u in s.unit_manager.units[0] if footprint(dat, u.unit_const)[0]}
    size = s.map_manager.map_size
    near = {(x + dx, y + dy) for x, y in {(int(u.x), int(u.y)) for u in p2}
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    free = [t for t in near if 0 < t[0] < size - 1 and 0 < t[1] < size - 1 and t not in taken and t not in blocked]
    p3 = list(s.unit_manager.units[3])
    cx, cy = sum(u.x for u in p3) / len(p3), sum(u.y for u in p3) / len(p3)
    free.sort(key=lambda t: (-((t[0] + .5 - cx) ** 2 + (t[1] + .5 - cy) ** 2), t))
    if len(free) < n:
        raise SystemExit(f'only {len(free)} free tiles next to the Player 2 formation')
    next_ref = max(u.reference_id for p in range(9) for u in s.unit_manager.units[p]) + 1
    added = []
    for i, (x, y) in enumerate(free[:n]):
        s.unit_manager.add_unit(player=2, unit_const=p2[0].unit_const, x=x + .5, y=y + .5, z=p2[0].z,
                                rotation=p2[0].rotation, reference_id=next_ref + i)
        added.append((p2[0].unit_const, x + .5, y + .5))
    return added


def land_restrictions(dat):
    """Terrain restrictions of every creatable unit that can stand on Winter Donut snow."""
    from AoE2ScenarioParser.datasets.terrains import TerrainId
    snow = TerrainId.SNOW.value
    return sorted({u.terrain_restriction for u in dat.civs[0].units
                   if u is not None and u.type == 70
                   and dat.terrain_restrictions[u.terrain_restriction].passable_buildable_dmg_multiplier[snow] > 0})


def build(name, spec, out, dat, restrictions):
    from AoE2ScenarioParser.datasets.other import OtherInfo
    from AoE2ScenarioParser.datasets.terrains import TerrainId
    from aoe2x.lab.io import sha256
    from aoe2x.lab.live import _camera_configuration, _player_runtime_configuration, _trigger_structure
    from build_run import _ai_configuration
    from prepare_norse_standard_capture import load_scenario
    ids = {u.name: u.ID for u in OtherInfo}
    names = {v: k for k, v in ids.items()}
    # A few winter objects (SPRUCESNOW 2732, ROCKSNOW 2734) are newer than the parser's list.
    name_of = lambda c: names.get(c) or dat.civs[0].units[c].name.upper()
    tid = {t.name: t.value for t in TerrainId}
    tname = {v: k for k, v in tid.items()}
    src = load_scenario(SOURCE)
    s = load_scenario(SOURCE)
    tables = [dat.terrain_restrictions[r].passable_buildable_dmg_multiplier for r in restrictions]
    for t in s.map_manager.terrain:
        new = tid[spec['terrain'][tname[t.terrain_id]]]
        assert all(table[new] == table[t.terrain_id] for table in tables), (name, 'passability', tname[t.terrain_id], tname[new])
        t.terrain_id = new
    swapped = []
    for u in s.unit_manager.units[0]:
        choices = spec['gaia'][name_of(u.unit_const)]
        new = ids[choices[(int(u.x) * 7 + int(u.y) * 13) % len(choices)]]
        assert footprint(dat, new) == footprint(dat, u.unit_const), (name, 'footprint', name_of(u.unit_const), name_of(new))
        swapped.append(names[new])
        u.unit_const = new
    added = add_player2_slots(s, spec['player2Slots'] - 27, dat)
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{spec['title']} Donut.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        s.write_to_file(str(path))
    checked = load_scenario(path)
    same = lambda f: f(src) == f(checked)
    assert same(_camera_configuration) and same(_player_runtime_configuration) and same(_trigger_structure)
    assert same(_ai_configuration)
    army = lambda sc: [[(u.unit_const, u.x, u.y, u.rotation, u.reference_id) for u in sc.unit_manager.units[p]] for p in range(1, 9)]
    authored, extra = army(checked)[1][:27], army(checked)[1][27:]
    assert army(src)[0] == army(checked)[0] and army(src)[2:] == army(checked)[2:] and army(src)[1] == authored
    assert [(c, x, y) for c, x, y, _, _ in extra] == added, 'extra Player 2 slots'
    gaia = lambda sc: [(u.x, u.y, u.rotation, u.reference_id, footprint(dat, u.unit_const)) for u in sc.unit_manager.units[0]]
    assert gaia(src) == gaia(checked)
    assert [(t.x, t.y, t.elevation) for t in src.map_manager.terrain] == [(t.x, t.y, t.elevation) for t in checked.map_manager.terrain]
    assert all(t.elevation == 0 for t in checked.map_manager.terrain)
    audit = path.with_suffix('.audit.json')
    audit.write_text(json.dumps(dict(
        state='PASSED', layout='Donut', theme=name, title=spec['title'], civs=spec['civs'], region=spec['region'],
        templateSha256=sha256(path), sourceTemplate=SOURCE.relative_to(ROOT).as_posix(), sourceTemplateSha256=SOURCE_HASH,
        slotsPerSide=27, player2Slots=spec['player2Slots'], player2ExtraSlots=added, bufferUnits=0, terrainFlat=True, quietAi=True, aiName='ddkDonutQuietAI',
        rangedOwner=2, meleeOwner=3, armiesAiCameraTriggersUnchanged=True,
        gaiaPositionsAndFootprintsUnchanged=True, passabilityUnchangedForRestrictions=restrictions,
        terrainMap=spec['terrain'], gaiaCounts={n: swapped.count(n) for n in sorted(set(swapped))}), indent=2) + '\n',
        encoding='utf-8')
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--themes', nargs='*', choices=sorted(THEMES))
    args = ap.parse_args()
    from aoe2x.lab.io import sha256
    if sha256(SOURCE) != SOURCE_HASH:
        raise SystemExit('Winter Donut template changed; themes are only built from the reviewed one')
    out = args.out if args.out.is_absolute() else ROOT / args.out
    with PICKLED_DAT.open('rb') as f:
        dat = pickle.load(f)
    restrictions = land_restrictions(dat)
    index = {}
    for name in args.themes or sorted(THEMES):
        path = build(name, THEMES[name], out, dat, restrictions)
        for civ in THEMES[name]['civs']:
            index[civ] = dict(theme=name, title=THEMES[name]['title'], path=path.relative_to(ROOT).as_posix())
        print(f"{THEMES[name]['title']:<24} {', '.join(THEMES[name]['civs']):<10} {path.relative_to(ROOT).as_posix()}")
    for civ in WINTER['civs']:
        index[civ] = dict(theme='winter', title=WINTER['title'], path=SOURCE.relative_to(ROOT).as_posix())
    (out / 'civ-themes.json').write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
