"""Copy complete Champi campaigns to the flat archive; preserve sources until reader migration."""
import json
import argparse
import os
from pathlib import Path
import time
from compact_recording_archive import export, read

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/compact-storage'


def save(value):
    value.update(pid=os.getpid(), updatedAt=time.time())
    temp = WORK / 'champi-copy.partial.json'
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(WORK / 'champi-copy.json')


def main():
    import msvcrt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--civ', choices=('incas', 'mapuche', 'muisca', 'tupi'))
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    lock = (WORK / 'champi-copy.lock').open('a+b')
    lock.write(b'0'); lock.flush(); lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    if not Path('D:/AoE2 Renders').is_dir():
        raise RuntimeError('External archive is not mounted')
    captures = read(ROOT / 'data/local/champi-standard-comparison/capture/status.json')
    previous = read(WORK / 'champi-copy.json') if (WORK / 'champi-copy.json').exists() else {}
    state = dict(state='RUNNING', completed=[r for r in previous.get('completed', []) if args.civ and r['civ'] != args.civ], skipped=[], sourceDeletionPerformed=False)
    try:
        for civ in ('incas', 'mapuche', 'muisca', 'tupi'):
            if args.civ and civ != args.civ:
                continue
            rows = [r for r in captures['results'] if r['status'] == 'verified'
                    and r['jobId'].startswith('champi_standard_' + civ + '_')]
            if len(rows) != 74:
                state['skipped'].append(dict(civ=civ, verified=len(rows)))
                continue
            state['current'] = civ
            save(state)
            result = export([Path(r['runDirectory']) for r in rows],
                            Path('D:/AoE2 Renders') / ('champi-standard-' + civ),
                            'Champi Standard ' + civ.title())
            state['completed'].append(dict(civ=civ, captures=len(result['matchups'])))
            save(state)
        state.update(state='COMPLETE', current=None)
        save(state)
    except Exception as e:
        state.update(state='FAILED', error=repr(e))
        save(state)
        raise


if __name__ == '__main__':
    main()
