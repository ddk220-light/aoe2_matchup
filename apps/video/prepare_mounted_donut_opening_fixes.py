"""Freeze one opening-patrol retake for each proven Danish Donut stall.

Use the validated Jarl whole-army patrol derivative. Preserve army counts,
positions, quiet kiting AI, scenery and every existing trial. Six clean r06
conditions are reused; only Cavalier, Paladin and Steppe Lancer need new games.
"""
import contextlib
import argparse
import copy
import io
import shutil
from pathlib import Path

from aoe2x.lab.cli import _normalize_batch_row
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import _load_stack, _validate_scenario, capture_template_path
from aoe2x.lab.planner import plan_matchup
from prepare_norse_standard_capture import CATALOGS, load_scenario
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/mounted-donut-opening-fix'
SLUG = 'heavy_mounted_crossbowman_danes'
EXPECTED_HP = {'cavalier_chinese': 140, 'paladin_spanish': 180, 'elite_steppe_cumans': 100}
CAMEL_FOLLOWUP = False


def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Already prepared; resume pending jobs only')
    audit_work = ROOT / 'data/local/mounted-donut-opening-fix' if CAMEL_FOLLOWUP else WORK
    audit = read(audit_work / 'opening-audit.json')
    assert audit['state'] == 'COMPLETE'
    needed = ([r for r in audit['results'] if r['opponent'] == 'heavy_camel_turks'] if CAMEL_FOLLOWUP
              else [r for r in audit['results'] if any(r['sides'][o]['delayedUnits'] for o in ('2', '3'))])
    assert {r['opponent'] for r in needed} == set(EXPECTED_HP)
    for r in needed:
        assert not r['sides']['2']['delayedUnits'], 'P3 patrol does not fix a P2 stall'
        if CAMEL_FOLLOWUP:
            assert any(u['firstMoveSeconds'] is None or u['firstMoveSeconds'] > 8
                       for u in r['sides']['3']['units'])
    old_campaign = next(c for c in read(ROOT / 'data/local/donut-color-sixth-iteration/queue.json')['campaigns'] if c['slug'] == SLUG)
    source_dir = Path(old_campaign['workDirectory'])
    index_path = Path(old_campaign['destination']) / 'run.json'
    original = read(index_path)
    assert shutil.disk_usage(ROOT).free >= 8 * 2**30
    assert shutil.disk_usage(index_path.parent).free >= 4 * 2**30
    descriptor = read(ROOT / 'data/local/jarl-kiting-followup/elite_jarl_varangians/manifest.json')['matchups'][0]['scenario']['donut']
    assert read(ROOT / 'data/local/jarl-kiting-followup/final-verification.json')['allCamelUnitsMovedBySeconds'] < 2
    for path_key, hash_key in (('path', 'sha256'), ('auditPath', 'auditSha256')):
        assert sha256(ROOT / descriptor[path_key]) == descriptor[hash_key]
    config = load_config()
    stack = _load_stack(config)
    rows = []
    checks = []
    directory = WORK / SLUG
    old_rows = read(source_dir / 'manifest.json')['matchups']
    for evidence in needed:
        opponent = evidence['opponent']
        old = next(r for r in old_rows if r['opponentSlug'] == opponent)
        row = copy.deepcopy(old)
        iteration = max(r.get('iteration', 0) for r in original['matchups']
                        if r.get('layout') == 'Donut' and r.get('opponentSlug') == opponent) + 1
        row.update(id=f'mdopen_{opponent}_r{iteration}', iteration=iteration, openingPatrolCorrected=True,
                   selectionReason='One clean opening trial: full P3 army patrol at second1 fixes verified passive rear units')
        row['scenario']['donut'] = copy.deepcopy(descriptor)
        plan = plan_matchup(config, _normalize_batch_row(row, {}))
        validate_plan_costs(plan)
        prior = read(source_dir / 'plans' / (old['id'] + '.json'))
        assert all(plan[k]['count'] == prior[k]['count'] for k in ('side2', 'side3'))
        assert plan['scenario']['playerColors'] == {'2': 0, '3': 1}
        save(directory / 'plans' / (row['id'] + '.json'), plan)
        path = directory / 'preflight-scenarios' / (row['id'] + '.aoe2scenario')
        sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2', 'side3')]
        with contextlib.redirect_stdout(io.StringIO()):
            stack['build_run'](*sides, path, counts=tuple(plan[k]['count'] for k in ('side2', 'side3')),
                              template=capture_template_path(config, plan), remove_player4_buffer=True, subject_owner=2)
            check = _validate_scenario(config, plan, path, stack)
        scenario = load_scenario(path)
        effect = scenario.trigger_manager.triggers[-1].effects[0]
        assert effect.object_list_unit_id == scenario.unit_manager.units[3][0].unit_const
        assert not effect.selected_object_ids
        save(path.with_suffix('.validation.json'), check)
        checks.append(dict(jobId=row['id'], countsUnchanged=True, wholeArmyPatrol=True,
                           counts=[plan[k]['count'] for k in ('side2', 'side3')]))
        rows.append(row)
    save(directory / 'manifest.json', dict(schemaVersion=1, matchups=rows))
    save(directory / 'pilot.json', dict(schemaVersion=1, matchups=rows))
    save(directory / 'pilot-opponent-expectations.json', {
        r['id']: dict(civ=r['civ3'], hpPerUnit=EXPECTED_HP[r['opponentSlug']]) for r in rows})
    save(directory / 'subject-stats.json', read(source_dir / 'subject-stats.json'))
    save(directory / 'preflight.json', dict(state='PASSED', total=len(rows), cases=checks))
    save(directory / 'previous-run.json', original)
    for name in CATALOGS:
        path = directory / 'frozen-catalogs' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'data' / name, path)
    reused = [r['jobId'] for r in audit['results'] if r not in needed]
    if CAMEL_FOLLOWUP:
        prior_selection = read(audit_work / 'eligibility.json')
        replaced = needed[0]['jobId']
        reused = [job for job in prior_selection['preferredCleanJobIds'] if job != replaced]
        assert len(reused) == 8
    save(WORK / 'selection.json', dict(state='PREPARED', newTrials=len(rows),
         reusedCleanJobIds=reused,
         preferredNewJobIds=[r['id'] for r in rows], historicalTrialsPreserved=True,
         reason=('Two Camels first moved at22.05/25.548s; an idle sprite change incorrectly passed the earlier activity check'
                 if CAMEL_FOLLOWUP else 'Opening-frame evidence, not victory/defeat, determines the three corrections')))
    save(WORK / 'eligibility.json', read(WORK / 'selection.json'))
    save(WORK / 'queue.json', dict(schemaVersion=1, total=len(rows), captureOnly=True,
         campaigns=[dict(key=SLUG, slug=SLUG, civilization='Danes', unit='Heavy Mounted Crossbowman',
         total=len(rows), workDirectory=str(directory), destination=old_campaign['destination'],
         originalIndexSha256=sha256(index_path), metadataDirectory=('_mounted_camel_opening_patrol_metadata'
                                     if CAMEL_FOLLOWUP else '_mounted_opening_patrol_metadata'),
         extensionKind='mounted-donut-clean-opening-trials')]))
    print(dict(prepared=len(rows), reused=len(reused), cases=checks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camel-followup', action='store_true', help='One authorized Camel correction; retain the completed three-job queue')
    CAMEL_FOLLOWUP = parser.parse_args().camel_followup
    if CAMEL_FOLLOWUP:
        WORK = ROOT / 'data/local/mounted-donut-camel-opening-fix'
        EXPECTED_HP = {'heavy_camel_turks': 140}
    main()
