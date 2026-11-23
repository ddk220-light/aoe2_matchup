"""Count attack windups that a Donut AI cut off before the release frame.

Generic form of audit_slinger_release.py: works for any unit type on the
Donut's ranged side (Player 2), from the recorded per-entity sprite frames.
A windup that closes below the DAT release frame while the unit is still
alive never released its projectile. Reaching the release frame is evidence
of a throw, not a guaranteed hit.

    python apps/video/audit_donut_release.py --civ Mapuche --master 2571 --label "Elite Bolas Rider" \
        <run_dir> [<run_dir> ...]
"""
import argparse
import json
from pathlib import Path

from overlay.unit_timeline import decode
from prepare_jomsviking_capture import DAT
from donut_ai_timing import unit_timing


def field(model, key, default=None):
    return model.get(key, model.get(str(key), default))


def measure(data, timing):
    graphic = timing['animation']['graphic']
    release = timing['frameDelay']
    active, cycles = {}, []
    for row in data['rows']:
        for unit in row['sides']['2']:
            if unit['masterId'] != timing['master']:
                continue
            eid = unit['id']
            animation = next((field(s, 3, 0) for s in unit['spriteModels']
                              if field(s, 0) == graphic), None)
            previous = active.get(eid)
            if previous and (animation is None or animation < previous['maxFrame']):
                previous.update(endMs=row['gameMs'], hpEnd=unit['hp'])
                cycles.append(previous)
                del active[eid]
            if animation is not None and unit['hp'] > 0:
                if eid not in active:
                    active[eid] = dict(entityId=eid, startMs=row['gameMs'], maxFrame=animation)
                active[eid]['maxFrame'] = max(active[eid]['maxFrame'], animation)
    cut = [c for c in cycles if c['maxFrame'] < release and c['hpEnd'] > 0]
    return dict(closedAttackAnimations=len(cycles),
                reachedReleaseFrame=sum(c['maxFrame'] >= release for c in cycles),
                cutBeforeRelease=len(cut),
                opponentHpRemoved=sum(u['hp'] for u in data['rows'][0]['sides']['3'])
                                  - sum(u['hp'] for u in data['rows'][-1]['sides']['3']))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--civ', required=True)
    parser.add_argument('--master', type=int, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('runs', nargs='+', type=Path)
    args = parser.parse_args()
    timing = unit_timing(DAT, args.civ, args.master, args.label)
    for run in args.runs:
        result = measure(decode(run, include_combat=True), timing)
        print(json.dumps(dict(run=run.parent.parent.name, **result)))


if __name__ == '__main__':
    main()
