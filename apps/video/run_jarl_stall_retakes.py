"""One-time, bounded Jarl retakes after the active mounted capture releases the game.

Preserves all 76 originals, reruns only four reviewed opening stalls, and
checks movement/animation again before marking a replacement ready. Does not
change Golden templates, battle rules, or start a recurring scheduled task.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from audit_jarl_opening_stalls import find_stalls, read_samples
from capture_storage_guard import archive_storage_error
from compact_recording_archive import export
from run_champi_comparison_capture import read, save
from run_italian_mounted_crossbow_after_expansion import acquire

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/jarl-stall-retakes'
MOUNTED = ROOT / 'data/local/mounted-crossbow-expansion'
SOURCE = Path('E:/AoE2 Renders/jarl-varangians/run.json')
DEST = Path('E:/AoE2 Renders/jarl-varangians-stall-retakes-20260923')
SELECTED = ('47_elite_mangudai', '06_elite_camel_archer_berbers',
            '35_grenadier_jurchens', '58_war_chariot_shu_barrage')
GUARD = dict(root='E:/AoE2 Renders', label='Archives',
             volumeSerial=int('F274E9A2', 16), reserveGiB=4)
CATALOGS = ('recording-costs.json', 'recording-balance.json',
            'recording-subjects.json', 'unique-unit-roster.json')


def status(state, **fields):
    save(WORK/'status.json', dict(state=state, pid=os.getpid(), updatedAt=time.time(), **fields))


def paused():
    return ((WORK/'PAUSE').exists() or (MOUNTED/'PAUSE').exists()
            or bool(list(MOUNTED.glob('*/PAUSE')))
            or (ROOT/'data/local/thermal/PAUSED.json').exists())


def comparable_inputs(plan):
    # Catalog membership grows as new civilizations are prepared. Compare the
    # actual combat inputs, never infer a needed rerun from a catalog hash.
    return dict(sides=[{k: plan[s][k] for k in
        ('slug','civ','mechanicsCiv','count','effectiveCost','weightedCost','ranged')}
        for s in ('side2','side3')], scenario=plan['scenario'],
        balance={k: plan['balance'][k] for k in ('mode','cap','weights','comparisonPolicy')})


def prepare():
    from aoe2x.lab.cli import _load_batch
    from aoe2x.lab.config import load_config
    from aoe2x.lab.planner import plan_matchup
    if (WORK/'manifest.json').exists():
        return
    source = read(SOURCE)
    audit = read(ROOT/'data/local/jarl-idle-audit/evidence/audit.json')
    hits = {r['jobId']: r for r in audit['results'] if r['candidateUnits']}
    expected = {'jarl_v3_unique_'+s for s in SELECTED}
    if audit['checked'] != 76 or set(hits) != expected:
        raise ValueError('Reviewed four-matchup scope no longer matches the audit')
    originals = {r['jobId']: r for r in source['matchups']}
    requests = {r['id']: r for r in read(ROOT/'data/local/jarl-capture/manifest.json')['matchups']}
    rows, mapping = [], []
    for suffix in SELECTED:
        old = 'jarl_v3_unique_'+suffix
        row = copy.deepcopy(requests[old])
        row['id'] = 'jarl_stall_retake_'+suffix
        if hits[old]['framesSha256'] != originals[old]['files']['frames.bin']['sha256']:
            raise ValueError('Review refers to different original footage')
        rows.append(row)
        mapping.append(dict(originalJobId=old, retakeJobId=row['id'],
            originalFramesSha256=hits[old]['framesSha256'], evidence=hits[old],
            originalInputs=comparable_inputs(originals[old]['plan'])))
    save(WORK/'requested.json', dict(schemaVersion=1, matchups=rows))
    config = load_config()
    for request, origin in zip(_load_batch(WORK/'requested.json')[1], mapping):
        plan = plan_matchup(config, request)
        if comparable_inputs(plan) != origin['originalInputs']:
            raise ValueError('Current inputs differ from original battle; do not silently change the comparison')
        save(WORK/'plans'/(plan['jobId']+'.json'), plan)
    save(WORK/'manifest.json', dict(schemaVersion=1, matchups=rows))
    for name in CATALOGS:
        save(WORK/'frozen-catalogs'/name, read(ROOT/'data'/name))
    save(WORK/'request.json', dict(authorizedAt='2026-09-23', sourceIndex=str(SOURCE),
        destination=str(DEST), preserveOriginals=True, reviewed=4, reused=72,
        archiveGuard=GUARD, mapping=mapping,
        reason='User-reported Jarl rear cluster confirmed in all four by frames and video',
        acceptance='No repeated opening-stall signature; original unit counts and 105 Jarl opening HP',
        noOutcomeSelection=True, noAutomaticRepeatOnStall=True))
    status('WAITING_FOR_CURRENT_CAPTURE', total=4)


def wait_for_game():
    while True:
        if paused():
            status('PAUSED'); return None
        current = read(MOUNTED/'status.json')
        if current['state'] in ('COMPLETE', 'NEEDS_RETAKES'):
            queue = acquire(MOUNTED/'queue.lock')
            if queue:
                handoff = acquire(MOUNTED/'italian-handoff.lock')
                if handoff:
                    return queue, handoff
                queue.close()
        elif current['state'] in ('PAUSED', 'NEEDS_ATTENTION', 'SUPERSEDED'):
            status('PREDECESSOR_NEEDS_ATTENTION', predecessorState=current['state'])
            return None
        status('WAITING_FOR_CURRENT_CAPTURE', total=4,
               currentCivilization=current.get('current', {}).get('civilization'),
               predecessorState=current['state'])
        time.sleep(30)


def run_script(script, *args, log='capture'):
    with (WORK/(log+'-output.log')).open('a', encoding='utf-8') as out, \
            (WORK/(log+'-error.log')).open('a', encoding='utf-8') as err:
        return subprocess.run([sys.executable, '-u', str(ROOT/'apps/video'/script), *args],
            cwd=ROOT, stdout=out, stderr=err).returncode


def verify_and_archive():
    current = read(WORK/'capture/status.json')
    if current.get('completed') != 4 or current.get('pendingExports') or current.get('failed'):
        status('RETAKES_NEED_ATTENTION', captureState=current.get('state'))
        return
    reviews, sources = [], []
    for row in current['results']:
        run = Path(row['runDirectory'])
        recording = read(run/'recording.json')
        plan = read(run.parents[1]/'plan.json')
        frames = run/recording['files']['frames']['path']
        expected = [plan[s]['count'] for s in ('side2','side3')]
        samples, tail = read_samples(frames, expected)
        if any(abs(u['hp']-105) > .1 for u in samples[0]['sides']['2']):
            raise ValueError('Retake opening Jarl HP differs from original')
        stalls = find_stalls(samples)
        reviews.append(dict(jobId=row['jobId'],
            state='STILL_STALLED_REVIEW_REQUIRED' if stalls else 'READY_FOR_REPLACEMENT',
            stalls=stalls, trailingPartialBytes=tail,
            framesSha256=recording['files']['frames']['sha256']))
        sources.append(run)
    save(WORK/'retake-review.json', dict(originalsPreserved=True, reviews=reviews,
        originalMapping=read(WORK/'request.json')['mapping']))
    error = archive_storage_error(GUARD)
    needed = sum(read(run/'recording.json')['files'][key]['bytes']
                 for run in sources for key in ('battleVideo','frames'))
    if error or shutil.disk_usage(Path(GUARD['root'])).free < needed + 4*2**30:
        status('CAPTURED_ARCHIVE_WAITING', reason=error or 'Archive reserve', reviews=reviews)
        return
    # Only a new destination is permitted. An interrupted own export may resume
    # if a durable ownership receipt preceded directory creation.
    owner = WORK/'archive-ownership.json'
    if DEST.exists() and not owner.exists():
        raise FileExistsError('Destination pre-exists; originals are never overwritten')
    if not owner.exists():
        save(owner, dict(destination=str(DEST), createdAt=time.time()))
    if read(owner)['destination'] != str(DEST):
        raise ValueError('Archive ownership mismatch')
    export(sources, DEST, 'Jarl opening-stall retakes, September 23 2026')
    target = DEST/'retake-review.json'
    data = (WORK/'retake-review.json').read_bytes()
    if target.exists() and target.read_bytes() != data:
        raise FileExistsError('Existing review differs; preserve it')
    if not target.exists():
        target.write_bytes(data)
    status('COMPLETE' if all(r['state']=='READY_FOR_REPLACEMENT' for r in reviews)
           else 'CAPTURED_WITH_PERSISTENT_STALLS', total=4, archived=4,
           destination=str(DEST), reviews=reviews, originalsPreserved=True)


def resume_mounted():
    """Resume only pending predecessor jobs, then its existing Italian handoff."""
    if paused():
        return
    # A failed Celt/Arambai battle has no valid completed result. Existing
    # verified cells are skipped by the established capture supervisor.
    current = read(MOUNTED/'status.json')
    if current['state'] == 'NEEDS_RETAKES':
        code = run_script('run_knight_expansion.py', '--work', str(MOUNTED), log='mounted-resume')
        if code or read(MOUNTED/'status.json')['state'] != 'COMPLETE':
            save(WORK/'mounted-follow-on.json', dict(state='NEEDS_ATTENTION'))
            return
    if not paused():
        code = run_script('run_italian_mounted_crossbow_after_expansion.py', log='italian-resume')
        save(WORK/'mounted-follow-on.json', dict(returnCode=code,
            handoff=read(MOUNTED/'italian-handoff-status.json')))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare-only', action='store_true')
    a = p.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    owner = acquire(WORK/'worker.lock')
    if owner is None:
        return
    with owner:
        prepare()
        if a.prepare_only:
            print(read(WORK/'status.json')); return
        gates = wait_for_game()
        if gates is None:
            return
        try:
            if paused():
                status('PAUSED'); return
            for name in CATALOGS:
                if read(WORK/'frozen-catalogs'/name) != read(ROOT/'data'/name):
                    raise RuntimeError('Catalog changed while waiting; compare inputs before resuming')
            status('CAPTURING', total=4)
            run_script('run_champi_comparison_capture.py', '--work', str(WORK))
            verify_and_archive()
        finally:
            for gate in reversed(gates):
                gate.close()
        resume_mounted()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        status('NEEDS_ATTENTION', error=traceback.format_exc())
        raise
