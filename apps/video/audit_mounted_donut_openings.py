"""Inspect the latest nine Danish Donut trials for passive opening units.

Movement, sprite changes and damage distinguish delayed engagement from an
attacker holding its position. This reads local frames and never starts games.
"""
import math
import tempfile
from pathlib import Path

from audit_jarl_opening_stalls import read_samples
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/mounted-donut-opening-fix'


def inspect(rows, owner, seconds=30):
    start = rows[0]
    initial = {u['id']: u for u in start['sides'][owner]}
    end = min(start['gameSeconds'] + seconds, rows[-1]['gameSeconds'])
    units = []
    for eid, u in initial.items():
        first_move = first_activity = None
        for row in rows:
            if row['gameSeconds'] > end:
                break
            v = next((x for x in row['sides'][owner] if x['id'] == eid), None)
            if v is None:
                break
            moved = math.hypot(v['x'] - u['x'], v['y'] - u['y']) > 0.25
            t = round(row['gameSeconds'] - start['gameSeconds'], 3)
            if moved and first_move is None:
                first_move = t
            if (moved or v['hp'] < u['hp'] or v['sprite'] != u['sprite']) and first_activity is None:
                first_activity = t
        units.append(dict(id=eid, start=[u['x'], u['y']], firstMoveSeconds=first_move,
                          firstActivitySeconds=first_activity))
    # P3 begins away from the ranged army and must advance. An idle animation
    # can change sprite before the camel actually moves; it is not engagement.
    activity_key = 'firstMoveSeconds' if owner == '3' else 'firstActivitySeconds'
    delayed = [u for u in units if u[activity_key] is None or u[activity_key] > 8]
    return dict(unitCount=len(units), delayedUnits=delayed, units=units,
                maxFirstMovementSeconds=max((u['firstMoveSeconds'] or 0) for u in units))


def main():
    (WORK / 'tmp').mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(WORK / 'tmp')
    manifest = read(ROOT / 'data/local/donut-color-sixth-iteration/heavy_mounted_crossbowman_danes/manifest.json')
    destination = Path(r'\\100.123.128.35\AoE2-Incoming\heavy_mounted_crossbowman_danes\Standard_Units_Detailed_Winter_5_Repeats')
    archive = {row['jobId']: row for row in read(destination / 'run.json')['matchups']}
    results = []
    for entry in manifest['matchups']:
        job = entry['id']
        run = ROOT / 'aoe2x/js_simulation/calibration/lab/runs' / job / 'live/run_001'
        recorded = archive[job]
        counts = recorded['capture']['capture']['startCounts']
        source = run / 'frames.bin'
        if not source.exists():
            source = destination / recorded['files']['frames.bin']['path']
        assert source.stat().st_size == recorded['files']['frames.bin']['bytes']
        rows, tail = read_samples(source, counts)
        sides = {owner: inspect(rows, owner) for owner in ('2', '3')}
        result = dict(jobId=job, opponent=entry['opponentSlug'], startCounts=counts,
                      sides=sides, trailingPartialBytes=tail)
        results.append(result)
        save(WORK / 'opening-audit.json', dict(state='AUDITING', results=results))
        print(entry['opponentSlug'], 'delayed P2/P3',
              [len(sides[o]['delayedUnits']) for o in ('2', '3')], flush=True)
    save(WORK / 'opening-audit.json', dict(state='COMPLETE', results=results,
         criterion='P3 must move >0.25 tiles within8 seconds. For P2, movement, sprite changes or damage distinguish standing attackers from idle units.'))


if __name__ == '__main__':
    main()
