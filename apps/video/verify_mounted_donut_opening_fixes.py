"""Accept retakes only after every melee unit moves during the opening.

Use captured positions, rather than the final winner, to validate the patrol.
Keep the six already clean r06 trials and select one new trial per correction.
"""
import tempfile
import argparse
from pathlib import Path

from audit_jarl_opening_stalls import read_samples
from audit_mounted_donut_openings import inspect
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/mounted-donut-opening-fix'


def main():
    tempfile.tempdir = str(WORK / 'tmp')
    campaign = read(WORK / 'queue.json')['campaigns'][0]
    directory = Path(campaign['workDirectory'])
    status = read(directory / 'capture/status.json')
    assert status['state'] == 'COMPLETE' and status['completed'] == campaign['total']
    assert not status['failed'] and not status['pendingExports']
    jobs = {r['jobId']: r for r in status['results'] if r['status'] == 'verified'}
    rows = read(directory / 'manifest.json')['matchups']
    results = []
    for row in rows:
        run = Path(jobs[row['id']]['runDirectory'])
        manifest = read(run / 'manifest.json')
        capture = manifest['capture']
        source = run / capture['artifacts']['frames']
        samples, trailing = read_samples(source, capture['startCounts'])
        sides = {o: inspect(samples, o) for o in ('2', '3')}
        melee = sides['3']['units']
        assert all(u['firstMoveSeconds'] is not None and u['firstMoveSeconds'] <= 3 for u in melee), row['id']
        assert not sides['2']['delayedUnits'], row['id']
        plan = read(directory / 'plans' / (row['id'] + '.json'))
        assert plan['scenario']['playerColors'] == {'2': 0, '3': 1}
        results.append(dict(jobId=row['id'], opponent=row['opponentSlug'],
             allMeleeMovedBySeconds=sides['3']['maxFirstMovementSeconds'],
             delayedUnitsP2=0, delayedUnitsP3=0, startCounts=capture['startCounts'],
             trailingPartialBytes=trailing, winner=capture['winnerSlug'],
             winnerRemainingHpPercent=capture['winnerRemainingHpPercent']))
        print(results[-1], flush=True)
    selection = read(WORK / 'selection.json')
    selection.update(state='VERIFIED', openingVerification=results,
                     preferredCleanJobIds=selection['reusedCleanJobIds'] + selection['preferredNewJobIds'])
    save(WORK / 'eligibility.json', selection)
    save(WORK / 'opening-verification.json', dict(state='PASSED', results=results,
         newTrials=len(rows), reusedCleanTrials=len(selection['reusedCleanJobIds']), noOpeningStalls=True,
         criterion='Every P3 unit moves >0.25 tiles within3 game seconds; no P2 passive opening longer than8 seconds.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=WORK)
    WORK = parser.parse_args().work.resolve()
    (WORK / 'tmp').mkdir(parents=True, exist_ok=True)
    main()
