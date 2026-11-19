"""Replace only the six authorized r01 Donut video/frame pairs on Dragonstar.

Stage and checksum every pair before replacement, bind exact old hashes, and
retain local sources and the previous index. Receipts allow interrupted copies
to resume without recording another game or overwriting unrelated media.
"""
import copy
import msvcrt
import shutil
import time
import traceback
from pathlib import Path

from compact_recording_archive import digest, prepare
from copy_arena_donut_to_share import extension_row
from copy_capture_campaign import copy_file, now
from prepare_donut_color_retakes import ROOT, WORK
from run_champi_comparison_capture import read, save

SHARE = Path(r'\\100.123.128.35\AoE2-Incoming')
RUNS = (ROOT / 'aoe2x/js_simulation/calibration/lab/runs').resolve()


def guard():
    if (WORK / 'PAUSE').exists() or (ROOT / 'data/local/thermal/PAUSED.json').exists():
        raise RuntimeError('Paused; preserve all recording sources')
    if not SHARE.is_dir() or shutil.disk_usage(SHARE).free < 4 * 2**30:
        raise RuntimeError('Destination unavailable or below reserve; preserve sources')


def safe_child(destination, name):
    if Path(name).name != name or name in ('.', '..'):
        raise ValueError('Replacement filename escaped the approved run folder')
    return destination / name


def deliver(campaign):
    work = Path(campaign['workDirectory'])
    binding = read(work / 'replacement.json')
    destination = Path(binding['destination'])
    if not destination.is_relative_to(SHARE) or destination != Path(campaign['destination']):
        raise ValueError('Unexpected replacement destination')
    guard()
    index_path = destination / 'run.json'
    state_path = work / 'replacement-status.json'
    state = read(state_path) if state_path.exists() else dict(state='PREPARING',
        previousIndexSha256=binding['previousIndexSha256'], completedFiles=[], startedAt=now())
    current_hash = digest(index_path)
    if current_hash not in (binding['previousIndexSha256'], state.get('newIndexSha256')):
        raise RuntimeError('Remote index changed outside this correction; preserve it')
    if state['state'] == 'COMPLETE':
        if current_hash != state['newIndexSha256']:
            raise RuntimeError('Completed replacement index changed')
        return
    status = read(work / 'capture/status.json')
    if (status.get('completed') != 3 or status.get('failed') or status.get('pendingExports')
            or status.get('state') != 'COMPLETE'):
        raise RuntimeError('Three verified recordings with finished exports required')
    originals = read(work / 'previous-run.json')
    old_rows = {r['jobId']: r for r in originals['matchups']}
    results = {r['jobId']: r for r in status['results'] if r['status'] == 'verified'}
    items = {r['id']: r for r in read(work / 'manifest.json')['matchups']}
    replacements = {}
    for entry in binding['mapping']:
        source = Path(results[entry['jobId']]['runDirectory']).resolve()
        if not source.is_relative_to(RUNS / entry['jobId'] / 'live'):
            raise ValueError('Capture escaped its authorized job folder')
        row = extension_row(prepare(source), items[entry['jobId']])
        validation = row['capture']['scenario']
        if (row['plan']['scenario']['playerColors'] != {'2': 1, '3': 0}
                or not validation.get('playerColorsMatchPlan')):
            raise RuntimeError('Blue subject/red opponent validation missing')
        old = old_rows[entry['oldJobId']]
        if any(row['files'][k]['path'] != old['files'][k]['path'] for k in row['files']):
            raise ValueError('Correction must replace the exact original filenames')
        row['replacesJobId'] = entry['oldJobId']
        replacements[entry['oldJobId']] = row
    prepared_path = work / 'prepared-run.json'
    if not prepared_path.exists():
        updated = copy.deepcopy(originals)
        updated['matchups'] = [replacements.get(r['jobId'], r) for r in updated['matchups']]
        updated.setdefault('corrections', []).append(dict(kind='donut-player-colors',
            reason=binding['reason'], mapping=binding['mapping'], correctedAt=now(),
            subjectColor='blue', opponentColor='red', iterationsReplaced=[1]))
        save(prepared_path, updated)
    state.update(state='STAGING', newIndexSha256=digest(prepared_path))
    save(state_path, state)
    # Copy all six files for this subject before touching any old media.
    for old_id, row in replacements.items():
        for key, info in row['files'].items():
            target = safe_child(destination, info['path'])
            actual = digest(target)
            if actual not in (old_rows[old_id]['files'][key]['sha256'], info['sha256']):
                raise RuntimeError(f'Conflicting destination: {target.name}')
            if actual != info['sha256']:
                copy_file(info, target.with_name(target.name + '.dc6.partial'), guard)
    if digest(index_path) not in (binding['previousIndexSha256'], state['newIndexSha256']):
        raise RuntimeError('Remote index changed during staging')
    state['state'] = 'REPLACING'; save(state_path, state)
    for old_id, row in replacements.items():
        for key, info in row['files'].items():
            guard()
            target = safe_child(destination, info['path'])
            actual = digest(target)
            if actual != info['sha256']:
                if actual != old_rows[old_id]['files'][key]['sha256']:
                    raise RuntimeError('Original file changed before replacement')
                target.with_name(target.name + '.dc6.partial').replace(target)
            if target.stat().st_size != info['bytes'] or digest(target) != info['sha256']:
                raise RuntimeError('Replacement file verification failed')
            if info['path'] not in state['completedFiles']:
                state['completedFiles'].append(info['path'])
                save(state_path, state)
    current_hash = digest(index_path)
    if current_hash == binding['previousIndexSha256']:
        staged_index = destination / 'run.dc6.publish'
        copy_file(dict(source=str(prepared_path), bytes=prepared_path.stat().st_size,
            sha256=state['newIndexSha256']), staged_index, guard)
        if digest(index_path) != binding['previousIndexSha256']:
            raise RuntimeError('Index changed before publication')
        staged_index.replace(index_path)
    if digest(index_path) != state['newIndexSha256']:
        raise RuntimeError('Replacement index failed verification')
    state.update(state='COMPLETE', replaced=3, completedAt=now(), localSourcesRetained=True)
    save(state_path, state)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'replacement.lock').open('a+b') as lock:
        if not lock.tell():
            lock.write(b'0'); lock.flush()
        lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        queue = read(WORK / 'queue.json')
        while True:
            completed = []
            for campaign in queue['campaigns']:
                work = Path(campaign['workDirectory'])
                status = read(work / 'capture/status.json') if (work / 'capture/status.json').exists() else {}
                if status.get('state') == 'COMPLETE' and status.get('completed') == 3 and not status.get('pendingExports'):
                    deliver(campaign)
                    completed.append(campaign['slug'])
            save(WORK / 'delivery-status.json', dict(state='COMPLETE' if len(completed) == 2 else 'WAITING',
                replaced=3 * len(completed), total=6, completed=completed, updatedAt=now()))
            if len(completed) == 2:
                return
            guard()
            capture = read(WORK / 'status.json') if (WORK / 'status.json').exists() else {}
            if capture.get('state') in ('NEEDS_ATTENTION', 'NEEDS_RETAKES', 'PAUSED'):
                raise RuntimeError('Capture needs attention; completed sources preserved')
            time.sleep(10)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        save(WORK / 'delivery-error.json', dict(state='NEEDS_ATTENTION', error=traceback.format_exc(), updatedAt=now()))
        raise
