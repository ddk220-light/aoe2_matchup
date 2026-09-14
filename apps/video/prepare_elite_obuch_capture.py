"""Prepare the approved Elite Obuch capture roster with audited unit costs."""
import json
from pathlib import Path
from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.io import safe_slug, write_json
from aoe2x.lab.planner import plan_matchup

ROOT = Path(__file__).resolve().parents[2]

def main():
    roster = json.loads((ROOT / 'data/unique-unit-roster.json').read_text())['units']
    subject = next(x for x in roster if x['slug'] == 'elite_obuch_poles')
    opponents = sorted((x for x in roster if x['slug'] != subject['slug']), key=lambda x: (x['civ'].casefold(), x['label'].casefold()))
    rows = [dict(id=f'elite_obuch_unique_{i:02}_{safe_slug(x["civ"])}_{safe_slug(x["slug"])}',
                 side2=subject['slug'], civ2=subject['civ'], side3=x['slug'], civ3=x['civ'],
                 balance=dict(mode='equal_resources', cap=27, maxResources=5000))
            for i, x in enumerate(opponents, 1)]
    manifest = ROOT / 'aoe2lab.recorder.elite-obuch-all-unique.json'
    write_json(manifest, dict(schemaVersion=1, matchups=rows))
    costs = json.loads((ROOT / 'data/recording-costs.json').read_text())['units']
    _, requests = _load_batch(manifest)
    plans = []
    config = load_config()
    for request in requests:
        plan = plan_matchup(config, request)
        for side in ('side2', 'side3'):
            unit = plan[side]
            expected = costs[unit['civ'] + '|' + unit['slug']]['effectiveCost']
            assert unit['effectiveCost'] == expected, (side, unit['slug'])
        plans.append(plan)
    assert len(plans) == 73
    write_json(ROOT / 'data/local/elite-obuch-capture-preflight.json', dict(
        passed=True, subject=subject, matchups=len(plans), manifest=str(manifest),
        costBasis='Corrected Imperial purchase costs per physical unit; Elite Obuch costs 55 food and 20 gold.',
        plans=plans))
    print(f'Prepared and cost-validated {len(plans)} matchups: {manifest}')

if __name__ == '__main__':
    main()
