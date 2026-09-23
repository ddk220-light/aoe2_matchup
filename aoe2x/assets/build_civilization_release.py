"""Build the page-only 185872 reference supplement and approved web media.

Run with explicit --dat, --trees, --assets, --output (website static directory),
and --extracted (ignored scratch directory). Never writes the reference/ranking DB.
"""
import argparse
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

from PIL import Image, ImageSequence

from aoe2x.dbgen.unit_analyzer import UnitAnalyzer

BUILD = 185872
NEW_CIVS = {'Danes', 'Saxons', 'Varangians'}
MC_CIVS = {'Britons', 'Celts', 'Franks', 'Poles', 'Sicilians', 'Spanish',
           'Teutons', 'Danes', 'Saxons', 'Varangians', 'Bohemians',
           'Burgundians', 'Italians', 'Portuguese', 'Vikings'}
GUARD_CIVS = {'Byzantines', 'Vikings', 'Danes', 'Saxons', 'Varangians'}
NEW_NAMES = {2700: 'Mounted Crossbowman', 2701: 'Heavy Mounted Crossbowman',
             2703: 'Varangian Guard', 2704: 'Elite Varangian Guard',
             2705: 'Hearth Troop', 2706: 'Elite Hearth Troop',
             2708: 'Jarl', 2709: 'Elite Jarl',
             2711: 'Jomsviking', 2712: 'Elite Jomsviking'}
BUILDINGS = {87: 'archery_range', 12: 'barracks', 101: 'stable',
             49: 'siege_workshop', 45: 'dock', 82: 'castle'}
# These are support/civilian units outside the existing combat page categories.
EXCLUDED = {13, 17, 83, 125, 128, 440, 545, 1105}
LINES = {4: 'archer', 24: 'archer', 492: 'archer', 7: 'skirmisher', 6: 'skirmisher',
         74: 'militia', 75: 'militia', 77: 'militia', 473: 'militia', 567: 'militia',
         93: 'spear', 358: 'spear', 359: 'spear', 448: 'light_cav', 546: 'light_cav', 441: 'light_cav',
         38: 'knight', 283: 'knight', 569: 'knight', 1258: 'ram', 422: 'ram', 548: 'ram',
         280: 'mangonel', 550: 'mangonel', 588: 'mangonel', 279: 'scorpion', 542: 'scorpion',
         331: 'trebuchet', 42: 'trebuchet', 1103: 'fire', 529: 'fire', 532: 'fire',
         539: 'galleon', 21: 'galleon', 442: 'galleon', 2626: 'hulk', 2627: 'hulk',
         2628: 'hulk', 250: 'longship', 533: 'longship',
         2700: 'mounted_crossbowman', 2701: 'mounted_crossbowman',
         2703: 'varangian_guard', 2704: 'varangian_guard',
         2705: 'hearth_troop', 2706: 'hearth_troop',
         2708: 'jarl', 2709: 'jarl', 2711: 'jomsviking', 2712: 'jomsviking'}
DESCRIPTIONS = {
    'Danes': 'Infantry and siege civilization. Jomsvikings throw torches at buildings and ships; Northmen’s Fury strengthens siege attacks. Varangian Guards and Longships move faster.',
    'Saxons': 'Infantry and defensive civilization. Hearth Troops open combat with a javelin. Foot-soldier discounts depend on Town Centers and Castles; Shield Wall rewards massed infantry.',
    'Varangians': 'Cavalry and naval civilization. Jarls throw axes that reduce armor. Stronger Bloodlines, faster-attacking Varangian Guards, and faster-firing Longships support their armies.',
}


def slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def removed_slugs(civ):
    removed = ['cavalry_archer', 'heavy_cavalry_archer'] if civ in MC_CIVS - NEW_CIVS - {'Bohemians'} else []
    if civ == 'Vikings':
        removed += ['longboat', 'elite_longboat']
    return removed


def select_roster(civ, tree):
    """Use available units and actual unit upgrade links, never display positions."""
    nodes = [n for n in tree['civ_techs_units']
             if n.get('Use Type') == 'Unit' and n.get('Node Status') != 'NotAvailable'
             and n.get('Building ID') in BUILDINGS and n['Node ID'] not in EXCLUDED]
    superseded = {n['Link ID'] for n in nodes if n.get('Link Node Type') in
                  {'Unit', 'UnitUpgrade', 'RegionalUnit', 'UniqueUnit'} and 'Link ID' in n}
    nodes = [n for n in nodes if n['Node ID'] not in superseded]
    if civ not in NEW_CIVS:
        allowed = set()
        if civ in MC_CIVS:
            allowed.update((2700, 2701))
        if civ in GUARD_CIVS:
            allowed.update((2703, 2704))
        if civ == 'Vikings':
            allowed.update((250, 533))
        nodes = [n for n in nodes if n['Node ID'] in allowed]
    return nodes


def identity(node):
    uid, name = node['Node ID'], node['Name']
    unit_slug = 'trebuchet' if uid == 331 else slug(name)
    building = BUILDINGS[node['Building ID']]
    column = {'archery_range': 'ranged', 'barracks': 'infantry', 'stable': 'cavalry',
              'siege_workshop': 'siege', 'dock': 'navy'}.get(building, 'infantry')
    if uid in (2708, 2709):
        column = 'cavalry'
    if uid in (279, 542):
        column = 'ranged'
    if uid in (331, 42):
        column = 'siege'
    return (unit_slug, LINES.get(uid, unit_slug), column, building,
            node.get('Node Type') == 'UniqueUnit')


def media_for(name):
    unit_slug = slug(name)
    if name in NEW_NAMES.values():
        base = f'/static/media/civilizations/{BUILD}/{unit_slug}/'
        return {key: base + filename for key, filename in {
            'icon': 'icon.png', 'icon_transparent': 'icon_transparent.png',
            'idle': 'idle.png', 'attack': 'attack.webp'}.items()}
    # Page-only aliases: the engine and shared display-name icon catalog stay intact.
    aliases = {'Longship': 'Longboat', 'Elite Longship': 'Elite Longboat',
               'Trebuchet (Packed)': 'Trebuchet'}
    legacy = aliases.get(name, name)
    icons = json.loads(Path(__file__).with_name('presentation.json').read_text())['icon_names']
    icon = icons[legacy]
    return {'icon': f'/static/img/units/{icon}.png'}


def apply_tree_availability(analyzer, trees):
    """Constrain this page release with the shipped tree's explicit tech availability."""
    analyzer.release_trees = trees
    for civ, tree in trees.items():
        analyzer.civ_disabled_tech_ids.setdefault(civ, set()).update(
            n['Node ID'] for n in tree['civ_techs_units']
            if n.get('Use Type') == 'Tech' and n.get('Node Status') == 'NotAvailable')


def reference_row(civ, node, analyzer):
    uid = node['Node ID']
    unit = analyzer.get_unit(uid)
    if unit is None:
        raise ValueError(f'{civ}: selected tree unit {uid} ({node["Name"]}) missing from extraction')
    config = {'base_id': uid, 'display_name': node['Name'], 'unit_class': unit['class'], 'upgrades': []}
    result = analyzer.calculate_unit_stats_for_civ(civ, config, max_age=4)
    stats = result['stats']
    if stats is None:
        raise ValueError(f'{civ}: cannot calculate selected unit {uid}')
    unit_slug, line, column, building, unique = identity(node)
    display = 'Trebuchet' if uid == 331 else node['Name']
    values = {key: getattr(stats, key) for key in ('hp', 'attack', 'reload_time', 'range',
              'melee_armor', 'pierce_armor', 'cost_food', 'cost_wood', 'cost_gold')}
    values['is_ranged'] = stats.range > 0
    effects = []
    if line == 'mounted_crossbowman':
        if any(t['Name'] == 'Cranequins' and t['Node Status'] != 'NotAvailable'
               for t in getattr(analyzer, 'release_trees', {}).get(civ, {}).get('civ_techs_units', [])):
            effects.append('Cranequins: +1 range and +2 attack against infantry.')
    if line == 'varangian_guard':
        effects.append('Generates gold while fighting other units.')
        if civ == 'Byzantines':
            effects.append('Logistica: trample damage.')
        if civ == 'Varangians':
            effects += ['Attacks 25% faster and generates 50% more gold.',
                        'Gothikon: periodically throws axes.']
    if line == 'hearth_troop':
        effects.append('Throws a javelin before engaging in melee; javelin damage is separate from the displayed melee attack.')
    if line == 'jarl':
        effects.append('Ranged melee attacks reduce enemy armor.')
    if line == 'jomsviking':
        effects.append('Throws torches against buildings and ships; torch damage is separate from the displayed melee attack.')
    if civ == 'Saxons' and unit['class'] in (0, 6, 44):
        effects.append('Foot soldiers cost 5% less per controlled Town Center or Castle (maximum 20%); listed costs exclude this variable discount.')
    if civ == 'Saxons' and column == 'infantry':
        effects.append('Shield Wall grants armor when infantry are massed; listed armor excludes formation-dependent bonuses.')
    if civ == 'Danes' and column == 'infantry':
        effects.append('Hamask increases damage as hit points are lost; listed attack is at full health.')
    if civ == 'Varangians' and line == 'knight':
        effects += ['Vendel Legacy: trample damage.', 'Team bonus: +1 attack against infantry.']
    if civ == 'Danes' and line in ('mangonel', 'catapult_galleon'):
        effects.append('Northmen’s Fury: +1 range and +40% siege attack against buildings.')
    # Internal DAT tech names contain stale development labels (e.g. +65%
    # Bloodlines while the actual effect is +10 HP). Use verified public wording.
    bonus_names = {
        'C-Bonus, Bloodlines +65% more effective': 'Bloodlines adds 30 HP instead of 20.',
        'C-Bonus, All units -20% gold': 'Units cost 20% less gold.',
        'C-Bonus, Cavalry +20% HP': 'Cavalry have 20% more HP.',
        'C-Bonus, Inf +20% HP': 'Infantry have 20% more HP.',
        'C-Bonus, Bonus damage resistance': 'Land military units resist bonus damage.',
        'C-Bonus, Inf Cav +1 armor Age3': 'Infantry and cavalry gain +1 melee armor in Castle Age.',
        'C-Bonus, Inf Cav +1 armor Age4': 'Infantry and cavalry gain another +1 melee armor in Imperial Age.',
        'C-Bonus, Lonbgoats and Catapult Galleon attack +15% faster': 'Longships and Catapult Galleons attack 15% faster.',
        'C-Bonus, Longboats & VG move +10% faster': 'Longships and Varangian Guards move 10% faster.',
        'C-Bonus, Longboats and Catapult Galleon +20% HP': 'Longships and Catapult Galleons have 20% more HP.',
        'C-Bonus, VG attack +25% faster': 'Varangian Guards attack 25% faster.',
        'Byzantine Logistica': 'Logistica: trample damage.',
        'Viking Chieftains': 'Chieftains: infantry gain bonus attack against cavalry.',
        'Conscription': 'Conscription: faster military training.',
    }
    bonuses = [bonus_names.get(b, b) for b in result['applied_bonuses']
               if not b.startswith('C-Bonus, Warship cost')]
    if any(b.startswith('C-Bonus, Warship cost') for b in result['applied_bonuses']):
        bonuses.append('Warships cost less as the civilization advances through the ages.')
    return {'unit_name': display, 'unit_slug': unit_slug, 'line_slug': line,
            'column': column, 'building': building, 'reference_build': BUILD,
            'is_unique': unique, 'stats': values, 'special_effects': effects,
            'bonus_abilities': bonuses, 'media': media_for(node['Name'])}


def convert_attack(source, target):
    with Image.open(source) as gif:
        frames = [frame.convert('RGBA') for frame in ImageSequence.Iterator(gif)]
        durations = [frame.info.get('duration', 0) for frame in ImageSequence.Iterator(gif)]
        loop = gif.info.get('loop', 1)
        frames[0].save(target, format='WEBP', save_all=True, append_images=frames[1:],
                       lossless=True, exact=True, duration=durations, loop=loop, method=6)
    with Image.open(target) as webp:
        actual_durations = []
        for frame in ImageSequence.Iterator(webp):
            frame.load()
            actual_durations.append(frame.info['duration'])
        if webp.n_frames != len(frames) or actual_durations != durations or webp.info['loop'] != loop:
            raise ValueError(f'Animation timing/frame/loop mismatch: {target}')
    return {'frames': len(frames), 'duration_ms': sum(durations), 'loop': loop}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_emblem(game_root, output, civ):
    src = game_root / 'widgetui' / 'textures' / 'menu' / 'civs' / f'{civ.lower()}.png'
    dst = output / 'img' / 'civilizations' / str(BUILD) / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return {'source': str(src), 'output': '/static/' + dst.relative_to(output).as_posix(),
            'bytes': dst.stat().st_size, 'source_sha256': digest(src)}


def build_release(dat, trees, assets, output, extracted, *, reuse_extracted=False):
    """All input paths are read-only; output is a website static directory."""
    from aoe2x.extract.run import extract_all
    extracted.mkdir(parents=True, exist_ok=True)
    if not reuse_extracted:
        extract_all(dat, extracted)
    analyzer = UnitAnalyzer(extracted)
    source_trees = {c: trees / f'{c.upper()}.json' for c in sorted(MC_CIVS | GUARD_CIVS)}
    apply_tree_availability(analyzer, {c: json.loads(p.read_text()) for c, p in source_trees.items()})
    release = {'schema_version': 1, 'reference_build': BUILD, 'published_at': date.today().isoformat(),
               'source_dat_sha256': digest(dat),
               'source_tech_tree_sha256': {c: digest(p) for c, p in source_trees.items()},
               'civilizations': {}, 'media': {}, 'sources': {'dat': str(dat),
               'tech_trees': str(trees), 'approved_assets': str(assets), 'asset_revision': '68e99758'},
               'media_inventory': [],
               'media_notes': ['Enhanced dat4x and ultrasharp idle PNGs contain visible streaks. '
                   'This release reuses clean native red idle sprites. No clean existing blue '
                   'idle source was available; idle_blue is intentionally absent. '
                   'Approved attack GIFs remain the source of lossless animated WebP.']}
    for name in NEW_NAMES.values():
        unit_slug = slug(name)
        source = assets / unit_slug
        dest = output / 'media' / 'civilizations' / str(BUILD) / unit_slug
        dest.mkdir(parents=True, exist_ok=True)
        sources = {'icon.png': source / 'icon.png', 'icon_transparent.png': source / 'icon_transparent.png',
                   'idle.png': source / f'{unit_slug}_idle_dir06.png',
                   'attack.webp': source / f'{unit_slug}_attack_dir06_dat4x.gif'}
        for filename, path in sources.items():
            details = convert_attack(path, dest / filename) if filename == 'attack.webp' else {}
            if filename != 'attack.webp':
                shutil.copyfile(path, dest / filename)
            release['media_inventory'].append({'source': str(path),
                'output': '/static/' + (dest / filename).relative_to(output).as_posix(),
                'bytes': (dest / filename).stat().st_size, 'source_sha256': digest(path), **details})
        release['media'][unit_slug] = media_for(name)
    game_root = dat.parents[3]
    for civ, tree in analyzer.release_trees.items():
        emblem = ''
        if civ in NEW_CIVS:
            inventory = copy_emblem(game_root, output, civ)
            emblem = inventory['output']
            release['media_inventory'].append(inventory)
        release['civilizations'][civ] = {'description': DESCRIPTIONS.get(civ, ''),
            'emblem_url': emblem, 'complete_roster': civ in NEW_CIVS,
            'remove_slugs': removed_slugs(civ),
            'units': [reference_row(civ, n, analyzer) for n in select_roster(civ, tree)]}
    for record in release['civilizations'].values():
        for row in record['units']:
            for url in row['media'].values():
                if not (output / url.removeprefix('/static/')).is_file():
                    raise ValueError(f'Missing referenced media: {url}')
    target = output / 'data' / f'civilizations-{BUILD}.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(release, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {target}: {sum(len(c["units"]) for c in release["civilizations"].values())} reference rows, '
          f'{len(release["media_inventory"])} media files')
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('dat', 'trees', 'assets', 'output', 'extracted'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--reuse-extracted', action='store_true', help='Reuse this release’s already extracted DAT')
    args = parser.parse_args()
    build_release(**vars(args))


if __name__ == '__main__':
    main()
