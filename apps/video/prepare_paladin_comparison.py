"""Prepare isolated Frankish, Teutonic, four-relic Lithuanian and Savar captures.

No game interaction. Extend audited identities without rewriting old entries;
freeze both prior catalogs and every new plan before the recorder starts.
"""
import copy
import argparse
import hashlib
import json
from pathlib import Path

from aoe2x.lab.balance import DEFAULT_BALANCE
from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.planner import plan_matchup
from report_champi_geometric import read, save

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/local/paladin-line-comparison'
SUBJECTS = [
    ('Franks', 'paladin_franks', 'Paladin'),
    ('Teutons', 'paladin_teutons', 'Paladin'),
    ('Lithuanians', 'paladin_lithuanians_four_relics', 'Paladin (4 relics)'),
    ('Persians', 'savar_persians', 'Savar'),
]


def register():
    import aoe2x.dbgen.unit_analyzer as module
    cost_path = ROOT / 'data/recording-costs.json'
    policy_path = ROOT / 'data/recording-balance.json'
    subject_path = ROOT / 'data/recording-subjects.json'
    catalog, policy, subjects = map(read, (cost_path, policy_path, subject_path))
    extracted = ROOT / 'data/local/cost-audit-extracted'
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in extracted.glob('*.json')}
    if hashes != catalog['extractionHashes']:
        raise ValueError('Installed cost extraction differs from audited catalog')
    for path in (cost_path, policy_path, subject_path):
        raw = path.read_bytes()
        snapshot = OUT / 'provenance' / f'{path.stem}-{hashlib.sha256(raw).hexdigest()}.json'
        if not snapshot.exists():
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(raw)
    module.OUTPUT_DIR = extracted
    analyzer = module.UnitAnalyzer()
    resources = ('food', 'wood', 'gold')
    for civ, slug, label in SUBJECTS[:3]:
        master = 569
        unit = analyzer.get_unit(master)
        stats = analyzer.get_base_stats(unit)
        base = {r: getattr(stats, 'cost_' + r) for r in resources}
        disabled = analyzer.get_disabled_techs(civ)
        stages = [analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(master, unit['class'], 4))
                  if t not in disabled and t in analyzer.tech_effect_map]
        stages += analyzer.get_civ_bonus_techs_for_unit(civ, master, unit['class'], 4)
        stages += analyzer.get_unique_techs_for_unit(civ, master, unit['class'], 4)
        effects = []
        for tech in stages:
            for command in tech.get('commands', []):
                if command.get('c') not in (100, 103, 104, 105):
                    continue
                before = {r: getattr(stats, 'cost_' + r) for r in resources}
                analyzer.apply_effect_command(command, stats, master, unit['class'])
                after = {r: getattr(stats, 'cost_' + r) for r in resources}
                if before != after:
                    effects.append(dict(techId=tech['tech_id'], command=command, before=before, after=after))
        final = {r: round(getattr(stats, 'cost_' + r)) for r in resources}
        if final != {'food': 60, 'wood': 0, 'gold': 75}:
            raise ValueError(f'Unexpected audited Paladin price: {civ}: {final}')
        key = civ + '|' + slug
        cost = dict(civ=civ, slug=slug, master=master, label=label, baseCost=base,
                    purchaseCost=final, unitsPerPurchase=1,
                    productionEvidence='One physical unit per purchase; population is not a cost divisor',
                    effectiveCost=final, effects=effects)
        if key in catalog['units'] and catalog['units'][key] != cost:
            raise ValueError(f'Refusing to rewrite registered cost {key}')
        catalog['units'][key] = cost
        population = copy.deepcopy(policy['units']['Spanish|paladin'])
        if key in policy['units'] and policy['units'][key] != population:
            raise ValueError(f'Refusing to rewrite population identity {key}')
        policy['units'][key] = population
        row = dict(slug=slug, label=label, civ=civ, master=master, **{'class': 'melee'},
                   baseCost=base, scenarioKey='paladin', websiteSlug='paladin',
                   costSource='Installed DAT master 569; own-civilization Imperial cost effects audited')
        existing = next((r for r in subjects['units'] if r['slug'] == slug), None)
        if existing and existing != row:
            raise ValueError(f'Refusing to rewrite recording subject {slug}')
        if not existing:
            subjects['units'].append(row)
    for path, value in ((cost_path, catalog), (policy_path, policy), (subject_path, subjects)):
        save(path, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-preflight', action='store_true',
                        help='Apply the approved no-ceiling policy; preserve completed compatible pilot plans')
    args = parser.parse_args()
    if (OUT / 'preflight.json').exists():
        if not args.refresh_preflight:
            raise FileExistsError('Campaign already prepared; resume its frozen manifest instead')
        for name in ('manifest.json', 'preflight.json', 'requested.json'):
            raw = (OUT / name).read_bytes()
            snapshot = OUT / 'provenance' / f'{Path(name).stem}-{hashlib.sha256(raw).hexdigest()}.json'
            if not snapshot.exists():
                snapshot.write_bytes(raw)
    else:
        register()
    # These three capture pilots already used exactly the approved counts.
    # Retain their recorded request/hash even though their now-redundant budget
    # was specified before the owner removed the ceiling.
    compatible = {}
    pilot_status = OUT / 'capture/pass-pilot/status.json'
    if pilot_status.exists():
        verified = {r['jobId'] for r in read(pilot_status)['results'] if r['status'] == 'verified'}
        compatible = {r['id']: r for r in read(OUT / 'pilot.json')['matchups']
                      if r['id'] in verified and r['civ2'] != 'Lithuanians'}
    roster = sorted(read(ROOT / 'data/unique-unit-roster.json')['units'],
                    key=lambda r: (r['civ'].casefold(), r['label'].casefold()))
    rows = []
    # Interleave civilizations per opponent for early side-by-side comparisons.
    for i, opponent in enumerate(roster, 1):
        for civ, slug, _ in SUBJECTS:
            if slug == opponent['slug']:
                continue
            row = dict(id=f'paladin_line_{civ.lower()}_{i:02}_{opponent["slug"].replace("(", "").replace(")", "")}',
                       side2=slug, civ2=civ, side3=opponent['slug'], civ3=opponent['civ'],
                       balance=dict(mode=DEFAULT_BALANCE, cap=27))
            if civ == 'Lithuanians':
                row['scenario'] = {'lithuanianRelics': 4}
                row['id'] += '_attack4'
            row = compatible.get(row['id'], row)
            rows.append(row)
    save(OUT / 'requested.json', dict(schemaVersion=1, matchups=rows))
    save(OUT / 'manifest.json', dict(schemaVersion=1, matchups=rows))
    _, requests = _load_batch(OUT / 'manifest.json')
    cfg, evidence = load_config(), []
    for row, request in zip(rows, requests):
        plan = plan_matchup(cfg, request)
        validate_plan_costs(plan)
        save(OUT / 'plans' / f'{plan["jobId"]}.json', plan)
        evidence.append(dict(jobId=plan['jobId'], civ=plan['side2']['civ'],
                             opponent=plan['side3']['slug'],
                             counts=[plan[s]['count'] for s in ('side2', 'side3')],
                             comparison=[plan[s]['comparison'] for s in ('side2', 'side3')]))
    save(OUT / 'deferred-budget.json', dict(schemaVersion=1, matchups=[],
         reason='Owner removed the ceiling; all requested matchups are included'))
    by_civ = {c: sum(r['civ2'] == c for r in rows) for c, _, _ in SUBJECTS}
    save(OUT / 'preflight.json', dict(state='PASSED', total=len(rows), deferred=0, byCivilization=by_civ,
         jobs=evidence, purpose='Raw gameplay and full gRPC frames; no rendering or publishing.',
         policy=DEFAULT_BALANCE, resourceCeiling=None, compatiblePilotIds=list(compatible),
         lithuanianRelics='One non-looping P2 Paladin melee attack +4 trigger; no relic resource modification'))
    print(json.dumps(dict(total=len(rows), byCivilization=by_civ, manifest=str(OUT / 'manifest.json'))))


if __name__ == '__main__':
    main()
