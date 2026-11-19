"""Finish five corrected Slinger Donut trials per actually eligible opponent.

Reuse the verified Guard probe. Freeze only four Guard and five Hearth games;
old Arena trials, historical Donut tapes and the working timing template stay
untouched. The selection receipt identifies the five trials to use per set.
"""
import contextlib
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
from prepare_jomsviking_capture import DAT
from prepare_norse_standard_capture import CATALOGS
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'data/local/slinger-donut-corrections'
PROBE = ROOT/'data/local/slinger-donut-timing'
GUARD = 'elite_varangian_guard_varangians'
HEARTH = 'elite_hearth_troop_saxons'


def main():
    if (WORK/'queue.json').exists():
        raise FileExistsError('Already frozen: resume the existing correction queue')
    prior = read(ROOT/'data/local/inca-slinger-standard/queue.json')
    if sha256(DAT) != prior['sourceDatSha256']:
        raise ValueError('Installed DAT changed: review actual inputs before recording')
    if shutil.disk_usage(ROOT).free < 8*2**30:
        raise RuntimeError('Local reserve unavailable')
    probe_campaign = read(PROBE/'queue.json')['campaigns'][0]
    probe_dir = Path(probe_campaign['workDirectory'])
    probe_row = read(probe_dir/'manifest.json')['matchups'][0]
    donut = probe_row['scenario']['donut']
    for path_key, hash_key in (('path','sha256'),('auditPath','auditSha256')):
        assert sha256(ROOT/donut[path_key]) == donut[hash_key]
    evidence = read(PROBE/'final-verification.json')
    assert evidence['state'] == 'COMPLETE'
    assert evidence['timingComparison']['probe']['earlyWalkInterruptions'] == 0
    campaigns, decisions, selections = [], [], []
    config = load_config(); stack = _load_stack(config)
    for slug in (GUARD, HEARTH):
        source = next(c for c in prior['campaigns'] if c['slug'] == slug)
        source_dir = Path(source['workDirectory'])
        decision = read(source_dir/'conditional-donut-decision.json')['comparisons'][0]
        assert decision['runDonut'] and decision['rangedLosses'] == 5
        index_path = Path(source['destination'])/'run.json'
        original = read(index_path)
        if shutil.disk_usage(index_path.parent).free < 4*2**30:
            raise RuntimeError('Share reserve unavailable')
        existing = [r for r in original['matchups']
                    if r.get('layout') == 'Donut' and r.get('opponentSlug') == 'imp_slinger_incas']
        reused = [r for r in existing if r['jobId'] == probe_row['id']]
        assert len(reused) == (1 if slug == GUARD else 0)
        for r in reused:
            assert r['plan']['scenario']['donut']['sha256'] == donut['sha256']
            for f in r['files'].values():
                assert (index_path.parent/f['path']).stat().st_size == f['bytes']
        old_row = next(r for r in read(source_dir/'manifest.json')['matchups'] if r['layout'] == 'Donut')
        old_plan = read(source_dir/'plans'/(old_row['id']+'.json'))
        rows = []
        first = max(r['iteration'] for r in existing) + 1
        for iteration in range(first, first + 5 - len(reused)):
            row = copy.deepcopy(old_row)
            row.update(id=f'slingfix_{slug}_donut_r{iteration}', iteration=iteration,
                colorCorrected=True, firingTimingCorrected=True, subjectOwner=3,
                selectionReason='Corrected Slinger animation release timing; part of five-trial replacement set')
            row['scenario'].update(donut=copy.deepcopy(donut), subjectOwner=3)
            rows.append(row)
        directory = WORK/slug
        for row in rows:
            plan = plan_matchup(config, _normalize_batch_row(row, {})); validate_plan_costs(plan)
            assert all(plan[k]['count'] == old_plan[k]['count'] for k in ('side2','side3'))
            assert plan['scenario']['playerColors'] == {'2':1,'3':0}
            save(directory/'plans'/(row['id']+'.json'), plan)
        plan = read(directory/'plans'/(rows[0]['id']+'.json'))
        path = directory/'preflight-scenarios'/'slinger-donut.aoe2scenario'
        sides = [stack['resolve_side'](plan[k]['civ'],plan[k]['slug']) for k in ('side2','side3')]
        with contextlib.redirect_stdout(io.StringIO()):
            stack['build_run'](*sides, path, counts=tuple(plan[k]['count'] for k in ('side2','side3')),
                template=capture_template_path(config,plan), remove_player4_buffer=True, subject_owner=3)
            validation = _validate_scenario(config,plan,path,stack)
        save(path.with_suffix('.validation.json'),validation)
        save(directory/'manifest.json',dict(schemaVersion=1,matchups=rows))
        save(directory/'pilot.json',dict(schemaVersion=1,matchups=rows[:1]))
        save(directory/'subject-stats.json',[dict(civ_name='Incas',final_hp=35)])
        enemy_hp = read(source_dir/'subject-stats.json')[0]['final_hp']
        save(directory/'pilot-opponent-expectations.json',{rows[0]['id']:dict(civ=source['civilization'],hpPerUnit=enemy_hp)})
        save(directory/'preflight.json',dict(state='PASSED',total=len(rows),countsUnchanged=True,
             counts=[plan[k]['count'] for k in ('side2','side3')],firingWindowMs=856))
        save(directory/'previous-run.json',original)
        for filename in CATALOGS:
            path = directory/'frozen-catalogs'/filename; path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source_dir/'frozen-catalogs'/filename,path)
        campaigns.append(dict(key=slug,slug=slug,civilization=source['civilization'],unit=source['unit'],
            total=len(rows),workDirectory=str(directory),destination=source['destination'],
            originalIndexSha256=sha256(index_path),metadataDirectory='_slinger_five_corrected_metadata',
            extensionKind='slinger-firing-timing-corrected-five-trials',
            documentationPath='docs/video-production/INCA_SLINGER_STANDARD_CAPTURE.md'))
        selections.append(dict(subject=slug,opponent='imp_slinger_incas',layout='Donut',
            correctedJobIds=[r['jobId'] for r in reused]+[r['id'] for r in rows],
            reusedJobIds=[r['jobId'] for r in reused],
            supersededForAnalysisJobIds=[r['jobId'] for r in existing if r not in reused],
            historicalMediaPreserved=True,selectionReason='Use these five timing-corrected trials instead of the interrupted-fire trials'))
    for c in prior['campaigns']:
        path = Path(c['workDirectory'])/'conditional-donut-decision.json'
        decisions.append(dict(subject=c['slug'],decision=read(path) if path.exists() else 'Ranged/ranged: Arena only'))
    save(WORK/'eligibility.json',dict(state='APPROVED',newTrials=9,reusedTrials=1,
         correctedTrialsPerCondition=5,correctedTrialSets=selections,arenaDecisions=decisions,
         timingEvidence=evidence['timingComparison']))
    save(WORK/'queue.json',dict(schemaVersion=1,total=9,captureOnly=True,campaigns=campaigns,
         correctedTrialSets=selections,noBuffers=True,sourceDatSha256=prior['sourceDatSha256']))
    print(dict(prepared=9,reused=1,sets=selections))


if __name__ == '__main__':
    main()
