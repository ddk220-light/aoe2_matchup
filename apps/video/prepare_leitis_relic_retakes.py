"""Prepare isolated four-relic Leitis corrections without replacing old captures."""
import contextlib
import copy
import io
import json
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.live import _load_stack, _validate_scenario, golden_path
from aoe2x.lab.planner import plan_matchup
from report_champi_geometric import save

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGNS = (('paladin-line-comparison', 'paladin-leitis-four-relics'),
             ('cavalier-comparison', 'cavalier-leitis-four-relics'))


def main():
    cfg = load_config()
    stack = _load_stack(cfg)
    summary = []
    for old_name, name in CAMPAIGNS:
        previous = ROOT / 'data/local' / old_name
        output = ROOT / 'data/local' / name
        if (output / 'preflight.json').exists():
            raise FileExistsError(f'{output} already prepared; resume its manifest')
        source = json.loads((previous / 'manifest.json').read_text())
        rows, baseline_ids = [], {}
        for row in source['matchups']:
            if row['side3'] != 'elite_leitis_lithuanians':
                continue
            new = dict(row, id=row['id'] + '_leitis_attack4',
                       scenario={**row.get('scenario', {}), 'opponentLithuanianRelics': 4})
            rows.append(new)
            baseline_ids[new['id']] = row['id']
        if len(rows) != 4:
            raise ValueError(f'Expected exactly four Leitis opponents in {old_name}')
        manifest = output / 'manifest.json'
        save(manifest, dict(schemaVersion=1, matchups=rows))
        _, requests = _load_batch(manifest)
        evidence = []
        for request in requests:
            plan = plan_matchup(cfg, request)
            old_id = baseline_ids[plan['jobId']]
            old = json.loads((previous/'plans'/f'{old_id}.json').read_text())
            validate_plan_costs(plan)
            for side in ('side2', 'side3'):
                current_side, old_side = copy.deepcopy(plan[side]), copy.deepcopy(old[side])
                # New subject registrations change the catalog hash, not any
                # of these existing costs, bonuses or physical unit counts.
                for value in (current_side, old_side):
                    value.get('comparison', {}).pop('catalogSha256', None)
                if current_side != old_side:
                    raise ValueError(f'Retake unexpectedly changes army/costs: {old_id} {side}')
            if plan['planHash'] == old['planHash']:
                raise ValueError('Relic condition must change the plan hash')
            scenario = output/'scenarios'/f'{plan["jobId"]}.aoe2scenario'
            with contextlib.redirect_stdout(io.StringIO()):
                stack['build_run'](*(stack['resolve_side'](plan[s]['civ'],plan[s]['slug']) for s in ('side2','side3')),
                    scenario, counts=tuple(plan[s]['count'] for s in ('side2','side3')),
                    template=golden_path(cfg,plan['scenario']['family']),
                    lithuanian_relics=plan['scenario'].get('lithuanianRelics'),
                    opponent_lithuanian_relics=4)
                checked = _validate_scenario(cfg,plan,scenario,stack)
            save(output/'plans'/f'{plan["jobId"]}.json',plan)
            evidence.append(dict(jobId=plan['jobId'], baselineJobId=old_id,
                civilization=plan['side2']['civ'], counts=[plan[s]['count'] for s in ('side2','side3')],
                scenarioValidation=checked, liveDamageValidation='pending capture'))
        save(output/'preflight.json',dict(state='PASSED',jobs=evidence,total=4,
            baselineWork=str(previous), purpose='P3 Elite Leitis four-relic attack correction only; original recordings preserved'))
        summary.append(dict(work=str(output),jobs=evidence))
    save(ROOT/'data/local/leitis-four-relic-retakes/queue.json',dict(
        state='PREPARED_WAITING_FOR_CURRENT_CAVALIER',
        prerequisiteWork=str(ROOT/'data/local/cavalier-comparison'),
        order=[x['work'] for x in summary],total=8,
        preserveChampi=True,preserveOriginals=True,liveDamageValidation='required on first retake',
        campaigns=summary))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
