"""Measure premature walk interruptions in a Slinger recording's animations.

Uses actual per-entity sprite frames, not win/loss, as the timing check. A
completed windup is evidence of reaching the release frame, not a guarantee
that a projectile hit (accuracy, targets and line of sight still matter).
"""
import argparse
from pathlib import Path

from overlay.unit_timeline import decode
from run_champi_comparison_capture import read, save


def field(model, key, default=None):
    return model.get(key, model.get(str(key), default))


def measure(data, timing):
    graphic = timing['animation']['graphic']
    release = timing['frameDelay']
    active, cycles = {}, []
    for row in data['rows']:
        for unit in row['sides']['2']:
            if unit['masterId'] != 185:
                raise ValueError('Expected the Slinger army in P2')
            eid = unit['id']
            animation = next((field(s, 3, 0) for s in unit['spriteModels']
                              if field(s, 0) == graphic), None)
            previous = active.get(eid)
            if previous and (animation is None or animation < previous['maxFrame']):
                previous.update(endMs=row['gameMs'], endingSprite=unit.get('sprite'), hpEnd=unit['hp'])
                cycles.append(previous)
                del active[eid]
            if animation is not None and unit['hp'] > 0:
                if eid not in active:
                    active[eid] = dict(entityId=eid, startMs=row['gameMs'], maxFrame=animation)
                active[eid]['maxFrame'] = max(active[eid]['maxFrame'], animation)
    premature = [c for c in cycles if c['maxFrame'] < release and c['hpEnd'] > 0
                 and c['endingSprite'] == 7645]  # DAT Slinger walking graphic
    return dict(closedAttackAnimations=len(cycles),
        reachedReleaseFrame=sum(c['maxFrame'] >= release for c in cycles),
        earlyWalkInterruptions=len(premature), firstInterruptions=premature[:5],
        opponentHpRemoved=sum(u['hp'] for u in data['rows'][0]['sides']['3'])
                         - sum(u['hp'] for u in data['rows'][-1]['sides']['3']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--timing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    timing = read(args.timing)
    result = dict(timing=timing)
    for name, run in (('baseline', args.baseline), ('probe', args.probe)):
        data = decode(run, include_combat=True)
        result[name] = dict(run=str(run), framesSha256=data['sourceSha256'],
            **measure(data, timing), outcome=read(run/'manifest.json')['capture'])
    save(args.output, result)
    print({name:{k:v for k,v in result[name].items() if k not in ('outcome','firstInterruptions')}
           for name in ('baseline','probe')})


if __name__ == '__main__':
    main()
