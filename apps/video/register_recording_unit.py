"""Register a standard (non-roster) unit for one civilization as a recording subject.

Adds or verifies the three catalog rows a plan needs, using the installed-DAT
cost chain (same `audited_price` as the Viking Sagas / Arena-Donut additions):

- data/recording-subjects.json: identity, class, scenario key, base cost
- data/recording-costs.json:    fully upgraded Imperial purchase/effective cost
- data/recording-balance.json:  comparison population 1, shared-unit provenance

Prerequisite: `python scripts/audit_installed_dat.py` (writes
data/local/dat-release-audit/). Refuses to run if the installed DAT changed
since that audit, and refuses to overwrite a conflicting existing identity.

    python apps/video/register_recording_unit.py --civ Tatars \
        --slug heavy_cavalry_archer_tatars --key heavy_cavalry_archer \
        --label "Heavy Cavalry Archer" --class mobile_ranged          # dry run
    ... --write                                                       # save

Changing a catalog changes its hash, so plans made before and after differ.
Historical plans keep their frozen catalogs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from build_run import unit_const
from prepare_jomsviking_capture import audited_price

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'data/local/dat-release-audit'
GAME = Path(os.environ.get('AOE2_GAME_DIR', r'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE'))
DAT = GAME / 'resources/_common/dat/empires2_x2_p1.dat'
CLASSES = ('melee', 'mobile_ranged', 'siege_ranged')


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--civ', required=True)
    ap.add_argument('--slug', required=True, help='catalog slug, e.g. heavy_cavalry_archer_tatars')
    ap.add_argument('--key', required=True, help='scenario unit key, e.g. heavy_cavalry_archer')
    ap.add_argument('--label', required=True)
    ap.add_argument('--class', dest='klass', required=True, choices=CLASSES)
    ap.add_argument('--shared', action=argparse.BooleanOptionalAction, default=True,
                    help='standard unit available to several civilizations (provenance only)')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    audit = read(AUDIT / 'audit.json')
    if hashlib.sha256(DAT.read_bytes()).hexdigest() != audit['sources']['installed_dat']['sha256']:
        raise SystemExit('Installed DAT changed since the audit; rerun scripts/audit_installed_dat.py')
    import aoe2x.dbgen.unit_analyzer as module
    module.OUTPUT_DIR = AUDIT / 'installed'
    analyzer = module.UnitAnalyzer()

    master = unit_const(args.key)
    from prepare_norse_standard_capture import available
    print('Tech tree:', available(args.civ, master))  # raises if the civ cannot build it
    row = {'civ': args.civ, 'slug': args.slug, 'master': master, 'label': args.label,
           'scenarioKey': args.key, 'class': args.klass}
    base = analyzer.get_base_stats(analyzer.get_unit(master))
    row['baseCost'] = {r: getattr(base, 'cost_' + r) for r in ('food', 'wood', 'gold')}
    row['costSource'] = f'Installed DAT {audit["sources"]["installed_dat"]["sha256"][:12]}; register_recording_unit.py'
    identity = f'{args.civ}|{args.slug}'
    price = audited_price(analyzer, row)
    balance = dict(master=master, population=1, sharedAcrossCivilizations=args.shared,
                   populationEvidence='One comparison population per physical unit',
                   classificationEvidence=('Standard unit, available across civilizations' if args.shared
                                           else 'Civilization-exclusive unit'))

    paths = {n: ROOT / 'data' / n for n in ('recording-subjects.json', 'recording-costs.json', 'recording-balance.json')}
    cats = {n: read(p) for n, p in paths.items()}
    roster = read(ROOT / 'data/unique-unit-roster.json')['units']
    if any(u['slug'] == args.slug for u in roster):
        raise SystemExit(f'{args.slug} is already a roster unit')
    subjects = cats['recording-subjects.json']['units']
    existing = next((u for u in subjects if u['slug'] == args.slug), None)
    if existing and any(existing[k] != row[k] for k in ('civ', 'master', 'class', 'baseCost')):
        raise SystemExit(f'Conflicting existing subject {args.slug}: {existing}')
    for name, value in (('recording-costs.json', price), ('recording-balance.json', balance)):
        old = cats[name]['units'].get(identity)
        if old and old != value:
            raise SystemExit(f'Conflicting existing {name} entry for {identity}: {old}')

    print(json.dumps(dict(subject=row, cost=price, balance=balance), indent=2))
    if not args.write:
        print('Dry run; pass --write to save.')
        return
    if not existing:
        subjects.append(row)
    cats['recording-costs.json']['units'][identity] = price
    cats['recording-balance.json']['units'][identity] = balance
    for name, path in paths.items():
        save(path, cats[name])
    print('Saved', ', '.join(paths))


if __name__ == '__main__':
    main()
