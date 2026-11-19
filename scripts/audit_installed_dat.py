"""Read-only release audit, isolated from recording catalogs and golden databases.

Run with the video venv and PYTHONPATH=data/local/cost-audit-deps;.
Both DATs are parsed with the same extractor. Installed tech-tree JSON supplies
regional availability; mere presence in a civilization's DAT table does not.
Outputs are evidence, not authorization to regenerate databases or recordings.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import pickle
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aoe2x.dbgen.conditional_costs import has_max_saxon_foot_discount
ROOT = Path(__file__).resolve().parents[1]
GAME = Path('C:/Program Files (x86)/Steam/steamapps/common/AoE2DE/resources')
RESOURCES = ('food', 'wood', 'gold')
NEW_IDS = (2700, 2701, 2703, 2704, 2705, 2706, 2708, 2709, 2711, 2712)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def source(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def extract(dat, target, names):
    from aoe2x.extract import extract_units as units_module
    from aoe2x.extract.extract_constants import CIV_NAMES, ARMOR_CLASSES
    from aoe2x.extract.extract_effects import extract_effects, extract_civ_tech_trees, extract_tech_effects
    from aoe2x.extract.extract_techs import extract_technologies, generate_tech_ages
    # Extend in memory only. This does not change the production allowlist.
    units_module.UNIT_NAMES.update(names)
    raw_units = {u.id:u for u in dat.civs[0].units if u is not None}
    units = [units_module.extract_unit_data(u, all_units=raw_units)
             for u in raw_units.values() if u.type == 70 and u.id in names]
    techs = extract_technologies(dat)
    payloads = dict(units=units, technologies=techs, tech_ages=generate_tech_ages(techs),
                    civilizations=[dict(id=i, name=n) for i, n in enumerate(CIV_NAMES)
                                   if i and n and i < len(dat.civs)],
                    armor_classes=[dict(id=k, name=v) for k, v in ARMOR_CLASSES.items()],
                    effects=extract_effects(dat), tech_effects=extract_tech_effects(dat))
    payloads['civ_tech_trees'] = extract_civ_tech_trees(dat, {t['id']: t for t in techs},
                                                   {u['id']: u for u in units})
    for name, data in payloads.items():
        save(target / (name + '.json'), data)
    return payloads


def price(analyzer, civ, uid):
    """Same cost-attribute chain on both versions, with explicit conditional aura.

    The user's comparisons use Imperial technologies, maximum civ discounts and
    per-physical-unit prices. Do not turn half population into a price discount.
    """
    unit = analyzer.get_unit(uid)
    stats = analyzer.get_base_stats(unit)
    disabled = analyzer.get_disabled_techs(civ)
    tree = analyzer.civ_tech_trees.get(civ, {})
    stages = [dict(tech_id='civ-tree:' + str(tree.get('tech_tree_effect_id')),
                   commands=analyzer.effects.get(tree.get('tech_tree_effect_id'), {}).get('commands', []))]
    stages += [analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(uid, unit['class'], 4))
              if t not in disabled and t in analyzer.tech_effect_map]
    stages += analyzer.get_civ_bonus_techs_for_unit(civ, uid, unit['class'], 4)
    stages += analyzer.get_unique_techs_for_unit(civ, uid, unit['class'], 4)
    applied = []
    for tech in stages:
        for cmd in tech.get('commands', []):
            if cmd.get('c') not in (100, 103, 104, 105):
                continue
            before = [getattr(stats, 'cost_' + r) for r in RESOURCES]
            analyzer.apply_effect_command(cmd, stats, uid, unit['class'])
            after = [getattr(stats, 'cost_' + r) for r in RESOURCES]
            if before != after:
                applied.append(dict(tech_id=tech['tech_id'], command=cmd, before=before, after=after))
    purchase = {r: round(getattr(stats, 'cost_' + r)) for r in RESOURCES}
    # Saxon TC/Castle foot-soldier discount is an aura, not a price attribute.
    # The audited foot-soldier lines include Barracks Varangian Guards.
    if has_max_saxon_foot_discount(civ, uid):
        purchase = {r: round(v * .8) for r, v in purchase.items()}
        applied.append(dict(tech_id=1469, max_discount=.2, required_buildings=4,
                            evidence='Installed English help 120209; TC/Castle aura'))
    batch = 2 if uid in (2579, 2581) else 1
    per_unit = {r: v / batch for r, v in purchase.items()}
    return dict(cost=per_unit, purchase=purchase, units_per_purchase=batch,
                weighted_cost=round(per_unit['food'] + .9 * per_unit['wood'] + 1.1 * per_unit['gold'], 6),
                effects=applied)


def diff(old, new):
    return {k: dict(before=old.get(k), after=new.get(k)) for k in sorted(old.keys() | new.keys())
            if old.get(k) != new.get(k)}


def money(cost):
    return ' + '.join(f'{cost.get(r, 0):g}{r[0].upper()}' for r in RESOURCES if cost.get(r, 0)) or '0'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, default=ROOT / 'data/inputs/empires2_x2_p1.dat')
    ap.add_argument('--installed', type=Path, default=GAME / '_common/dat/empires2_x2_p1.dat')
    ap.add_argument('--output', type=Path, default=ROOT / 'data/local/dat-release-audit')
    ap.add_argument('--reuse-extraction', action='store_true', help='Use already extracted audit snapshots; include their hashes in the receipt')
    args = ap.parse_args()
    from genieutils.datfile import DatFile
    import aoe2x.dbgen.unit_analyzer as analyzer_module
    from aoe2x.extract.extract_constants import CIV_NAMES
    from aoe2x.extract.extract_units import UNIT_NAMES

    strings_path = GAME / 'en/strings/key-value/key-value-strings-utf8.txt'
    strings = {int(m[1]): m[2] for m in re.finditer(r'^(\d+)\s+"(.*)"',
               strings_path.read_text(encoding='utf-8-sig'), re.M)}
    trees = {}
    tree_sources = []
    civ_tokens = {name.upper(): name for name in CIV_NAMES if name and name != 'Gaia'}
    for path in sorted((GAME / '_common/dat/CivTechTrees').glob('*.json')):
        if path.stem not in civ_tokens:
            continue
        trees[civ_tokens[path.stem]] = [n for n in read(path)['civ_techs_units'] if n.get('Use Type') == 'Unit']
        tree_sources.append(source(path))
    names = dict(UNIT_NAMES)
    for nodes in trees.values():
        for node in nodes:
            names[node['Node ID']] = node['Name']
    print('Loading isolated DAT snapshots...', flush=True)
    if args.reuse_extraction:
        old_data = {p.stem:read(p) for p in (args.output / 'baseline').glob('*.json')}
        new_data = {p.stem:read(p) for p in (args.output / 'installed').glob('*.json')}
        for data, folder in ((old_data, 'baseline'), (new_data, 'installed')):
            for unit in data['units']:
                if unit['id'] in names:
                    unit['name'] = names[unit['id']]
            save(args.output / folder / 'units.json', data['units'])
        cached = ROOT / 'data/local/viking-sagas-research/installed-dat.pkl'
        receipt = read(ROOT / 'data/local/jomsviking-capture/release-cost-audit.json')
        if source(args.installed)['sha256'] != receipt['datSha256']:
            raise ValueError('Installed DAT changed; do not reuse the cached parse')
        new_dat = pickle.loads(cached.read_bytes())
    else:
        old_dat = DatFile.parse(args.baseline)
        new_dat = DatFile.parse(args.installed)
        old_data = extract(old_dat, args.output / 'baseline', names)
        new_data = extract(new_dat, args.output / 'installed', names)
    analyzer_module.OUTPUT_DIR = args.output / 'baseline'
    old_analyzer = analyzer_module.UnitAnalyzer()
    analyzer_module.OUTPUT_DIR = args.output / 'installed'
    new_analyzer = analyzer_module.UnitAnalyzer()
    old_units = {u['id']: u for u in old_data['units']}
    new_units = {u['id']: u for u in new_data['units']}
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), sources=dict(
        baseline_dat=source(args.baseline), installed_dat=source(args.installed),
        localized_strings=source(strings_path), installed_civ_trees=tree_sources,
        existing_extraction=[source(p) for p in sorted((ROOT / 'data/inputs/extracted_data').glob('*.json'))],
        existing_reference_db=source(ROOT / 'data/golden/aoe2_reference.db')),
        grain='unit master ID; effective cost additionally civilization, Imperial age and per physical unit',
        base_changes=[], effective_cost_changes=[], current_costs=[], new_units=[], technology_changes=[],
        new_technologies=[], database_cost_deltas=[], extraction_baseline_deltas=[])
    for uid in sorted(old_units.keys() & new_units.keys()):
        changes = diff(old_units[uid], new_units[uid])
        if changes:
            report['base_changes'].append(dict(id=uid, name=new_units[uid]['name'], changes=changes))
    for civ, nodes in trees.items():
        seen = set()
        for node in nodes:
            uid = node['Node ID']
            if node['Node Status'] == 'NotAvailable' or uid not in new_units or uid in seen:
                continue
            seen.add(uid)
            raw = new_dat.civs[0].units[uid]
            if raw.type != 70:
                continue
            after = price(new_analyzer, civ, uid)
            current = dict(civ=civ, id=uid, name=names[uid], **after)
            report['current_costs'].append(current)
            if uid in old_units and civ in old_analyzer.civ_name_to_id:
                before = price(old_analyzer, civ, uid)
                if before['cost'] != after['cost']:
                    report['effective_cost_changes'].append(dict(civ=civ, id=uid, name=names[uid], before=before, after=after))
    # Raw structures retain new abilities not yet supported by the simulator.
    for uid in sorted(new_units.keys() - old_units.keys()):
        raw = new_dat.civs[0].units[uid]
        if uid not in NEW_IDS:
            continue
        available = [r for r in report['current_costs'] if r['id'] == uid]
        report['new_units'].append(dict(id=uid, name=names[uid], base_stats=new_units[uid],
                                       civilizations=available, raw_unit=dataclasses.asdict(raw),
                                       tasks=(dataclasses.asdict(new_dat.unit_headers[uid])
                                              if uid < len(new_dat.unit_headers) else None)))
    old_techs = {t['id']: t for t in old_data['technologies']}
    old_effects = {t['tech_id']: t for t in old_data['tech_effects']}
    new_effects = {t['tech_id']: t for t in new_data['tech_effects']}
    for tech in new_data['technologies']:
        tid = tech['id']
        if tid not in old_techs:
            report['new_technologies'].append(dict(tech=tech, effect=new_effects.get(tid)))
            continue
        changes = diff(old_techs[tid], tech)
        before = old_effects.get(tid, {}).get('commands', [])
        after = new_effects.get(tid, {}).get('commands', [])
        if before != after:
            changes['commands'] = dict(before=before, after=after)
        if changes:
            report['technology_changes'].append(dict(id=tid, name=tech['name'], civ=tech.get('civ'), changes=changes))
    # Existing extracted JSON is checked separately: gaps are not new game units.
    for prior in read(ROOT / 'data/inputs/extracted_data/units.json'):
        if prior['id'] in old_units:
            changes = diff(prior, old_units[prior['id']])
            if changes:
                report['extraction_baseline_deltas'].append(dict(id=prior['id'], name=prior['name'], changes=changes))
    # Database names may differ; exact (civ,name,age) matches only, no fuzzy joins.
    connection = sqlite3.connect('file:' + (ROOT / 'data/golden/aoe2_reference.db').as_posix() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    db_rows = [dict(r) for r in connection.execute('SELECT * FROM ref_units')]
    connection.close()
    index = {(r['civ'], r['name']): r for r in report['current_costs']}
    compared = 0
    for row in db_rows:
        if row['age'].lower() != 'imperial':
            continue
        current = index.get((row['civ_name'], row['unit_name']))
        if not current or not any(current['purchase'].values()):
            continue
        compared += 1
        # Reference DB stores purchase price; match that grain before comparison.
        old_cost = {r: row['final_cost_' + r] for r in RESOURCES}
        if old_cost != current['purchase']:
            report['database_cost_deltas'].append(dict(civ=current['civ'], id=current['id'], name=current['name'],
                database_purchase=old_cost, installed_purchase=current['purchase'], installed_per_unit=current['cost']))
    report['database_exact_name_rows_compared'] = compared
    # Compare by master ID, never by display label or tech-tree helper alias.
    catalog_path = ROOT / 'data/recording-costs.json'
    catalog = read(catalog_path)
    roster = read(ROOT / 'data/unique-unit-roster.json')['units']
    report['recording_catalog_deltas'] = []
    for row in roster:
        calculated = price(new_analyzer, row['civ'], row['master'])
        key = row['civ'] + '|' + row['slug']
        prior = catalog['units'][key]['effectiveCost']
        if prior != calculated['cost']:
            report['recording_catalog_deltas'].append(dict(identity=key, id=row['master'],
                catalog=prior, installed=calculated['cost'], evidence=calculated['effects']))
    # Evaluate concrete count impact without changing or rerunning frozen plans.
    roster_by_identity = {(r['civ'],r['slug']):r for r in roster}
    report['current_capture_count_deltas'] = []
    for path in sorted((ROOT / 'data/local/jomsviking-capture/plans').glob('*.json')):
        plan = read(path)
        sides = [plan[k] for k in ('side2','side3')]
        weights = [price(new_analyzer, s['civ'], roster_by_identity[s['civ'],s['slug']]['master'])['weighted_cost'] for s in sides]
        counts = [max(1, math.floor(27 * math.sqrt(min(weights) / w) + .5)) for w in weights]
        previous = [s['count'] for s in sides]
        if counts != previous:
            report['current_capture_count_deltas'].append(dict(job=plan['jobId'], before=previous, after=counts,
                installed_weighted_costs=weights, plan_source=source(path)))
    report['sources']['recording_catalog'] = source(catalog_path)
    old_effects_by_id = {e['id']:e for e in old_data['effects']}
    new_effects_by_id = {e['id']:e for e in new_data['effects']}
    old_trees = {t['name']:t for t in old_data['civ_tech_trees']}
    report['civ_tree_changes'] = []
    for tree in new_data['civ_tech_trees']:
        previous = old_trees.get(tree['name'])
        if not previous:
            continue
        before = old_effects_by_id[previous['tech_tree_effect_id']]['commands']
        after = new_effects_by_id[tree['tech_tree_effect_id']]['commands']
        if before != after:
            report['civ_tree_changes'].append(dict(civ=tree['name'],
                removed=[c for c in before if c not in after], added=[c for c in after if c not in before]))
    report['sources']['audit_extractions'] = [source(p) for folder in ('baseline','installed')
                                               for p in sorted((args.output / folder).glob('*.json'))]
    report['counts'] = {k:len(report[k]) for k in ('base_changes','effective_cost_changes','current_costs','new_units',
                                                 'technology_changes','new_technologies','database_cost_deltas')}
    report['civ_help'] = {str(k):strings.get(k) for k in (120209,120210,120211)}
    report['interpretation_notes'] = [
        'Elite Cataphract base anti-infantry damage rises 12 to 18, while Logistica loses its +6: the fully upgraded total remains 18. Non-elite base rises 9 to 13, versus the former 15 with Logistica.',
        'Elite Teutonic Knight base melee armor falls 10 to 8; the expanded Teuton class bonus now adds +2, leaving its fully upgraded melee armor unchanged.',
        'Wagenburg Tactics movement multiplier falls 1.15 to 1.10.',
        'New Frankish tech 1496 discounts Mounted Crossbowman gold by 40%. Portuguese gold discount also applies. Saxon foot-soldier discounts include Barracks Varangian Guards.',
        'The new-unit table gives base combat stats, not fully upgraded stats. Civilization technologies and engine-coded abilities must be applied separately.',
        'The repository unit allowlist has stale labels, including master 1699 labelled Urumi Swordsman instead of Flemish Militia. Joins in this audit use IDs; installed Unit nodes supply names. Technology nodes are excluded from the unit ID namespace.',
        'The recording-cost helper omitted civilization tech-tree price commands. This is an existing bug, not a new patch change. In the approved unique-unit roster this affects Mayan Elite Plumed Archers only: 43W+43G in the catalog versus 39W+39G including the initial 10% modifier.',
        'Mounted Crossbowmen are available to 15 civilizations; 10 receive the Heavy upgrade. The other five are Bohemians, Burgundians, Italians, Portuguese and Vikings.',
        'The existing Longboat line is now labelled Longship and is shared by Vikings, Danes, Saxons and Varangians. This is an expanded existing line, separate from the two newly added regional lines.',
        'Some old extractor effect descriptions misname numeric attributes (for example attribute 22 is blast radius, not wood cost). This audit applies price attributes 100/103/104/105; preserve raw numeric commands when interpreting new mechanics.',
    ]
    save(args.output / 'audit.json', report)
    lines = ['# Installed DAT release audit', '',
        'This is a read-only comparison. Active capture catalogs and golden databases were not changed.', '',
        'Baseline: local pre-update DAT; installed: current Steam DAT. This is a delta across those snapshots, not a claim that every change arrived in one patch.', '',
        '## Effective Imperial costs that changed', '',
        'Prices below are per physical unit, including available cost technologies and maximum Saxon discount. Blackwood purchases produce two units.', '',
        '| Civilization | Unit | Before | Installed | Weighted before → after |', '|---|---|---:|---:|---:|']
    for r in report['effective_cost_changes']:
        lines.append(f"| {r['civ']} | {r['name']} | {money(r['before']['cost'])} | {money(r['after']['cost'])} | {r['before']['weighted_cost']:g} → {r['after']['weighted_cost']:g} |")
    lines += ['', '## New units and regional availability', '', 'Base stats are before civilization bonuses and technologies.', '',
              '| Unit | HP | Melee/pierce attack | Melee/pierce armor | Range | Reload | Speed | Base purchase | Civilizations and effective cost |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in report['new_units']:
        s=r['base_stats']; atk={a['class']:a['amount'] for a in s['attacks']}; arm={a['class']:a['amount'] for a in s['armors']}
        civs='; '.join(c['civ']+': '+money(c['cost']) for c in r['civilizations'])
        lines.append(f"| {r['name']} | {s['hit_points']} | {atk.get(4,0)}/{atk.get(3,0)} | {arm.get(4,0)}/{arm.get(3,0)} | {s['range']} | {s['reload_time']} | {s['speed']} | {money(s['cost'])} | {civs} |")
    lines += ['', '## Base-unit stat changes', '', '| Unit (master ID) | Field | Before | Installed |', '|---|---|---|---|']
    for r in report['base_changes']:
        for field,d in r['changes'].items():
            if field=='internal_name': continue
            def short(v):
                if isinstance(v,list) and v and isinstance(v[0],dict) and 'class' in v[0]:
                    return ', '.join(str(a['class'])+':'+str(a['amount']) for a in v)
                return str(v)
            lines.append(f"| {r['name']} ({r['id']}) | {field} | {short(d['before'])} | {short(d['after'])} |")
    lines += ['', '## Existing database purchase-price differences', '',
              f"Exact civilization/name/Imperial matches compared: {compared}. Unmatched names are not guessed.", '',
              '| Civilization | Unit | Existing DB | Installed purchase |', '|---|---|---:|---:|']
    for r in report['database_cost_deltas']:
        lines.append(f"| {r['civ']} | {r['name']} | {money(r['database_purchase'])} | {money(r['installed_purchase'])} |")
    lines += ['', '## Recording catalog discrepancies (separate from patch changes)', '',
              '| Identity | Current catalog | Installed fully discounted |', '|---|---:|---:|']
    for r in report['recording_catalog_deltas']:
        lines.append(f"| {r['identity']} | {money(r['catalog'])} | {money(r['installed'])} |")
    lines += ['', 'Frozen Jomsviking plans with a different army count after the full cost audit:', '']
    for r in report['current_capture_count_deltas']:
        lines.append(f"- `{r['job']}`: {r['before'][0]} vs {r['before'][1]} → {r['after'][0]} vs {r['after'][1]}. This is a correction candidate only; the recording was preserved and no retake was started.")
    lines += ['', '## Interpretation', ''] + ['- ' + note for note in report['interpretation_notes']]
    lines += ['', '## Technology changes', '', '| ID | Technology | Changed fields |', '|---|---|---|']
    for t in report['technology_changes']:
        lines.append(f"| {t['id']} | {t['name']} | {', '.join(k for k in t['changes'] if k != '_computed_age')} |")
    lines += ['', '## New technologies', '', '| ID | Technology | Civilization ID |', '|---|---|---|']
    for row in report['new_technologies']:
        t=row['tech']; lines.append(f"| {t['id']} | {t['name']} | {t['civ']} |")
    lines += ['', '## Source receipt', '',
              '- Baseline DAT: `' + str(args.baseline) + '`; SHA-256 `' + report['sources']['baseline_dat']['sha256'] + '`.',
              '- Installed DAT: `' + str(args.installed) + '`; SHA-256 `' + report['sources']['installed_dat']['sha256'] + '`.',
              '- Both snapshots and all source hashes are stored alongside `audit.json`. No live DB replacement or retake was performed.',
              '- Method: keyed DAT-unit and effect diff; compare effective Imperial prices using all cost attributes plus civ-tree starting modifiers; use shipped unit tech-tree nodes for availability.']
    lines += ['', '## Scope and limitations', '',
              '- All price effects are applied with the same repository analyzer on both DAT snapshots. Conditional Saxon castle/TC foot-soldier pricing is explicitly applied at its maximum to the audited Hearth Troop and Varangian Guard lines.',
              '- Availability uses the shipped CivTechTrees JSON. Presence in DAT civ unit arrays alone does not establish trainability. Old availability is not inferred from current trees.',
              '- `audit.json` contains every extracted technology/effect delta, raw new-unit structures/tasks, source hashes, and exact comparison grains.',
              '- The existing extractor computes `attack_delay` as frame delay / 60. This report does not certify that approximation as actual windup; raw frame/animation data is retained for new units.',
              '- New engine abilities require explicit simulation support. Extracting stats does not implement those abilities.',
              '- Existing extraction-only differences are separated in `extraction_baseline_deltas`. They are not automatically attributed to a game patch.',
              '', 'Reproduce in PowerShell from the repository:', '', '```powershell',
              "$env:PYTHONPATH='data/local/cost-audit-deps;.'", "$env:PYTHONUTF8='1'",
              '& apps/video/.venv/Scripts/python.exe scripts/audit_installed_dat.py', '```', '']
    (args.output / 'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(report['counts']), flush=True)
    print(args.output / 'REPORT.md', flush=True)


if __name__ == '__main__':
    main()
