"""Verify the +4 relic spike using nonlethal damage in recorded game frames."""
import argparse
import collections
import json
from pathlib import Path

from overlay.unit_timeline import decode


def validate(run, output):
    timeline = decode(run)
    previous, histogram = {}, collections.Counter()
    for row in timeline['rows']:
        for unit in row['sides']['2']:
            hp = unit['hp']
            old = previous.get(unit['id'], hp)
            if 0 < hp < old:
                histogram[round(old-hp, 3)] += 1
            previous[unit['id']] = hp
    # These eight targets do not heal during combat. Elite Leitis has 16 base
    # attack +2 from available smith upgrades +4 relics and ignores melee armor.
    # Exclude killing hits because remaining HP truncates their damage.
    unexpected = {d:n for d,n in histogram.items() if abs(d/22-round(d/22)) > 1e-5}
    passed = histogram[22] >= 10 and not unexpected
    result = dict(state='PASSED' if passed else 'FAILED', expectedSingleHit=22,
                  singleHitObservations=histogram[22], nonlethalP2HpDrops=dict(histogram),
                  unexpectedDrops=unexpected, sourceFramesSha256=timeline['sourceSha256'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    if not passed:
        raise ValueError('Leitis relic damage needs investigation; do not accept the remaining retakes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    validate(args.run,args.output)
