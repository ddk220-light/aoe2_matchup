"""Prepare only Jarl standard-unit trials whose original battle had a frontline.

Unchanged ranged trials retain their original job IDs and recordings. New melee
trials use the reviewed winter ranged/ranged Golden, including its diplomacy,
instead of leaving an empty Player 4 in a mixed-family scenario.
"""
import contextlib
import copy
import io
import shutil
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import _load_stack, _validate_scenario, capture_template_path
from aoe2x.lab.planner import plan_matchup
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/local/norse-standard-capture'
WORK = ROOT / 'data/local/jarl-standard-without-hussar'
SLUG = 'elite_jarl_varangians'


def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Already prepared; resume the frozen queue.')
    original = BASE / SLUG
    target = WORK / SLUG
    for frozen in (original / 'frozen-catalogs').glob('*.json'):
        if sha256(frozen) != sha256(ROOT / 'data' / frozen.name):
            raise ValueError(f'Catalog changed: {frozen.name}; audit before planning.')
    source = read(BASE / 'source.json')
    if sha256(Path(source['datPath'])) != source['datSha256']:
        raise ValueError('Installed game DAT changed; review before reusing captures.')
    previous = read(original / 'capture/status.json')
    verified = {r['jobId']: r for r in previous['results'] if r['status'] == 'verified'}
    assert previous['completed'] == 70 and not previous['pendingExports']
    scenery = read(BASE / 'queue.json')['scenery']['ranged_vs_ranged']
    rows, selections, evidence = [], [], []
    for old in read(original / 'manifest.json')['matchups']:
        plan = read(original / 'plans' / (old['id'] + '.json'))
        assert old['id'] in verified
        changed = plan['scenario'].get('hasPlayer4Gate', False)
        if changed:
            assert plan['side3']['class'] == 'melee'
            new = copy.deepcopy(old)
            new['id'] = old['id'].replace('norse_std_', 'norse_nobuffer_', 1)
            new['scenario'] = dict(goldenFamily='ranged_vs_ranged', player4Buffer='none', scenery=scenery)
            rows.append(new)
            campaign, job = target, new['id']
        else:
            assert plan['scenario']['family'] == 'ranged_vs_ranged'
            campaign, job = original, old['id']
        selections.append(dict(jobId=job, sourceCampaign=str(campaign), originalJobId=old['id'],
            reused=not changed, iteration=old['iteration'], opponentIndex=old['opponentIndex'],
            reason='Original had no frontline; unchanged recording reused' if not changed else
                   'Remove Hussar frontline using winter ranged/ranged Golden'))
    assert len(rows) == 40 and len(selections) == 70
    save(target / 'manifest.json', dict(schemaVersion=1, matchups=rows))
    config = load_config()
    for request in _load_batch(target / 'manifest.json')[1]:
        plan = plan_matchup(config, request)
        validate_plan_costs(plan)
        old_id = plan['jobId'].replace('norse_nobuffer_', 'norse_std_', 1)
        old_plan = read(original / 'plans' / (old_id + '.json'))
        for key in ('side2', 'side3', 'balance'):
            assert plan[key] == old_plan[key], (plan['jobId'], key)
        assert not plan['scenario']['hasPlayer4Gate']
        save(target / 'plans' / (plan['jobId'] + '.json'), plan)
        evidence.append(dict(jobId=plan['jobId'], originalJobId=old_id,
            counts=[plan['side2']['count'], plan['side3']['count']],
            oldHussars=old_plan['scenario']['player4Count'], newHussars=0))
    # One representative scenario validates the family's patrol/diplomacy/slots.
    first = read(target / 'plans' / (rows[0]['id'] + '.json'))
    stack = _load_stack(config)
    sides = [stack['resolve_side'](first[s]['civ'], first[s]['slug']) for s in ('side2', 'side3')]
    output = target / 'preflight.aoe2scenario'
    with contextlib.redirect_stdout(io.StringIO()):
        stack['build_run'](*sides, output,
            counts=(first['side2']['count'], first['side3']['count']),
            template=capture_template_path(config, first), remove_player4_buffer=True)
        validation = _validate_scenario(config, first, output, stack)
    assert validation['player4Count'] == 0
    save(target / 'preflight.json', dict(state='PASSED', validation=validation, jobs=evidence))
    shutil.copytree(original / 'frozen-catalogs', target / 'frozen-catalogs', dirs_exist_ok=True)
    shutil.copyfile(original / 'subject-stats.json', target / 'subject-stats.json')
    save(target / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
    save(WORK / 'selection.json', dict(schemaVersion=1, title='Elite Jarl without Hussar',
        total=70, newCaptures=40, reusedCaptures=30, matchups=selections))
    save(WORK / 'queue.json', dict(schemaVersion=1, total=40, captureOnly=True, campaigns=[dict(
        key=SLUG, slug=SLUG, civilization='Varangians', unit='Elite Jarl without Hussar',
        total=40, workDirectory=str(target))]))
    print('Frozen: 40 new recordings, 30 unchanged recordings reused; all army counts unchanged.')


if __name__ == '__main__':
    main()
