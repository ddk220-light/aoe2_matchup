"""Prepare four independent standard-Golden Champi campaigns; capture only."""
import copy
import hashlib
import json
from pathlib import Path

from build_comp4_scenario import audited_costs
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.cli import _load_batch
from aoe2x.lab.planner import plan_matchup

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/local/champi-standard-comparison'
CIVS = ['Incas', 'Mapuche', 'Muisca', 'Tupi']


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subject_path = ROOT / 'data/recording-subjects.json'
    cost_path = ROOT / 'data/recording-costs.json'
    subjects = json.loads(subject_path.read_text())
    catalog = json.loads(cost_path.read_text())
    costs, hashes = audited_costs()
    assert hashes == catalog['extractionHashes']
    base = next(x for x in subjects['units'] if x['slug'] == 'elite_champi_warrior_incas')
    # Extend only the three missing identities; do not rewrite historic costs.
    for cost in costs[:4]:
        civ = cost['civ']
        slug = f'elite_champi_warrior_{civ.lower()}'
        if not any(x['slug'] == slug for x in subjects['units']):
            row = {**copy.deepcopy(base), 'slug': slug, 'civ': civ,
                   'costSource': 'Installed DAT, master 2554; audited Imperial civilization costs'}
            subjects['units'].append(row)
        key = civ + '|' + slug
        if key in catalog['units']:
            assert catalog['units'][key]['effectiveCost'] == cost['final']
        else:
            catalog['units'][key] = dict(civ=civ, slug=slug, master=2554,
                label='Elite Champi Warrior', baseCost=cost['base'],
                purchaseCost=cost['final'], unitsPerPurchase=1,
                productionEvidence='One physical unit per purchase; population is not a cost divisor',
                effectiveCost=cost['final'], effects=cost['effects'])
    old = cost_path.read_bytes()
    snapshot = OUT / ('cost-catalog-before-' + hashlib.sha256(old).hexdigest() + '.json')
    if not snapshot.exists():
        snapshot.write_bytes(old)
    save(subject_path, subjects)
    save(cost_path, catalog)
    roster = sorted(json.loads((ROOT/'data/unique-unit-roster.json').read_text())['units'],
                    key=lambda x: (x['civ'].casefold(), x['label'].casefold()))
    rows = []
    for civ in CIVS:
        own = []
        for i, unit in enumerate(roster, 1):
            if unit['master'] == 2554:
                continue
            row = dict(id=f'champi_standard_{civ.lower()}_{i:02}_{unit["slug"].replace("(", "").replace(")", "")}',
                       side2=f'elite_champi_warrior_{civ.lower()}', civ2=civ,
                       side3=unit['slug'], civ3=unit['civ'],
                       balance=dict(mode='equal_resources', cap=27, maxResources=5000))
            own.append(row)
        save(OUT/f'{civ.lower()}.json', dict(schemaVersion=1, matchups=own))
        rows.extend(own)
    # First test the same opponent once with every civilization, then continue
    # each civilization's remaining roster. Stable IDs preserve later pairing.
    pilots = [next(r for r in rows if r['civ2'] == civ) for civ in CIVS]
    ordered = pilots + [r for r in rows if r not in pilots]
    manifest = OUT/'manifest.json'
    save(manifest, dict(schemaVersion=1, matchups=ordered))
    config = load_config()
    _, requests = _load_batch(manifest)
    evidence = []
    for request in requests:
        plan = plan_matchup(config, request)
        validate_plan_costs(plan)
        assert catalog['units'][plan['side2']['civ']+'|'+plan['side2']['slug']]['master'] == 2554
        save(OUT/'plans'/f"{plan['jobId']}.json", plan)
        evidence.append(dict(jobId=plan['jobId'], civ=plan['side2']['civ'],
                             opponent=plan['side3']['slug'],
                             counts=[plan[s]['count'] for s in ['side2','side3']],
                             costs=[plan[s]['weightedCost'] for s in ['side2','side3']],
                             scenario=plan.get('scenario')))
    save(OUT/'preflight.json', dict(state='PASSED', total=len(evidence),
        costCatalogSha256=hashlib.sha256(cost_path.read_bytes()).hexdigest(),
        costs=costs[:4], jobs=evidence, policy='Standard Golden templates. Capture raw video and full frames only. No comp4 HP handicap. No overlay/render/upload authorization.'))
    print(json.dumps({'prepared':len(evidence), 'costs':costs[:4], 'manifest':str(manifest)}), flush=True)


if __name__ == '__main__':
    main()
