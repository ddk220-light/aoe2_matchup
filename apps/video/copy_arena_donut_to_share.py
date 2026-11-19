"""Append complete Arena/Donut extensions to existing approved unit folders.

The original index is checksum-bound, copied locally, and retained unchanged.
Never overwrite media; publish an extended index only after all new media and
rebuild metadata verify. A pending index checksum makes publication resumable.
Every local base recording is preserved. This finite worker is not a schedule.
"""
import argparse
import json
import msvcrt
import os
import re
import shutil
import time
import traceback
from pathlib import Path

from compact_recording_archive import digest, prepare, read
from copy_capture_campaign import copy_file, now
from run_champi_comparison_capture import save

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK = ROOT / 'data/local/arena-donut-standard'
RUNS = (ROOT / 'aoe2x/js_simulation/calibration/lab/runs').resolve()


def extension_row(row, item):
    """Name from the test subject, although Donut always puts ranged units in P2."""
    owner = item['subjectOwner']
    sides = (row['plan'][f'side{owner}'], row['plan'][f'side{5-owner}'])
    stem = re.sub(r'[^\w-]+', '_', '_vs_'.join(f"{s['civ']}_{s['label']}" for s in sides)).strip('_')
    stem += f"_no_buffer_r{item['iteration']:02}"
    if item['layout'] == 'Donut':
        stem += ' - Donut'
    if item.get('colorCorrected'):
        stem += ' - Color Corrected'
    if item.get('firingTimingCorrected'):
        stem += ' - Firing Timing Corrected'
    if item.get('openingPatrolCorrected'):
        stem += ' - Opening Patrol Corrected'
    row.update(name=stem, layout=item['layout'], subjectSlug=item['subjectSlug'],
        subjectOwner=owner, opponentOwner=5-owner, opponentSlug=item['opponentSlug'],
        opponentIndex=item['opponentIndex'], iteration=item['iteration'],
        bufferSetting='no_buffer', bufferComparisonApplicable=False,
        selectionReason=item['selectionReason'])
    if item.get('colorCorrected'):
        row['colorCorrected'] = True
    if item.get('firingTimingCorrected'):
        row['firingTimingCorrected'] = True
    if item.get('openingPatrolCorrected'):
        row['openingPatrolCorrected'] = True
    for key, info in row['files'].items():
        info['path'] = stem + ('.mp4' if key == 'battle.mp4' else '.frames.bin')
    return row


def deliver(work, campaign, state):
    slug = campaign['slug']
    target = Path(campaign['destination'])
    index_path = target / 'run.json'
    receipt_path = work / 'delivery/status.json'
    metadata_name = campaign.get('metadataDirectory', '_arena_donut_metadata')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*', metadata_name):
        raise ValueError('Extension metadata must be a single safe directory name')
    metadata = target / metadata_name

    def guard():
        if (work / 'PAUSE').exists() or (ROOT / 'data/local/thermal/PAUSED.json').exists():
            raise RuntimeError('Copy paused; all local sources retained')
        if not target.is_dir() or shutil.disk_usage(target).free < 4 * 2**30:
            raise RuntimeError('Approved share unavailable or below reserve; sources retained')

    guard()
    receipt = state['packages'].get(slug)
    if receipt is None:
        if digest(index_path) != campaign['originalIndexSha256']:
            raise RuntimeError('Existing index changed after preparation; review instead of overwriting')
        if metadata.exists():
            raise FileExistsError('Refusing to claim preexisting extension metadata')
        original = read(index_path)
        receipt = dict(state='COPYING', destination=str(target),
            originalIndexSha256=campaign['originalIndexSha256'], verified=0, total=campaign['total'],
            indexSha256=None, pendingIndexSha256=None, localSourcesRetained=True)
        save(work / 'delivery/original-indexes' / (slug + '.json'), original)
        state['packages'][slug] = receipt
        save(receipt_path, state)  # Claim before any destination write.
    current_hash = digest(index_path)
    if receipt.get('pendingIndexSha256') == current_hash:
        receipt.update(state='COMPLETE', indexSha256=current_hash, verified=campaign['total'])
        save(receipt_path, state)
        return
    if receipt['state'] == 'COMPLETE':
        if current_hash != receipt['indexSha256']:
            raise RuntimeError('Published extension index changed outside this worker')
        return
    if current_hash != receipt['originalIndexSha256']:
        raise RuntimeError('Destination index changed outside this worker')
    directory = Path(campaign['workDirectory'])
    manifest = read(directory / 'manifest.json')['matchups']
    status = read(directory / 'capture/status.json')
    sources = {r['jobId']: r for r in status['results'] if r['status'] == 'verified'}
    new_rows = []
    original = read(work / 'delivery/original-indexes' / (slug + '.json'))
    old_jobs = {r['jobId'] for r in original['matchups']}
    old_names = {f['path'].casefold() for r in original['matchups'] for f in r['files'].values()}
    for item in manifest:
        if item['id'] in old_jobs:
            raise RuntimeError('Extension job already exists in baseline')
        source = Path(sources[item['id']]['runDirectory']).resolve()
        if not source.is_relative_to(RUNS / item['id'] / 'live'):
            raise ValueError('Capture source escaped its job directory')
        row = extension_row(prepare(source), item)
        for info in row['files'].values():
            if info['path'].casefold() in old_names:
                raise RuntimeError('Extension media filename conflicts with existing media')
            copy_file(info, target / info['path'], guard)
        new_rows.append(row)
        receipt['verified'] = len(new_rows)
        save(receipt_path, state)
    metadata.mkdir(exist_ok=True)
    files = {work / 'queue.json', work / 'eligibility.json',
             ROOT / campaign.get('documentationPath', 'docs/video-production/ARENA_DONUT_CAPTURE.md')}
    files.update(work / name for name in ('installed-cost-audit.json', 'count-summary.json')
                 if (work / name).exists())
    files.update((work / 'catalog-registration').glob('*.json'))
    files.update((work / 'donut-template').glob('*'))
    files.update(directory / n for n in ('manifest.json', 'pilot-validation.json',
                                         'subject-stats.json', 'preflight.json'))
    files.update(directory.glob('conditional-donut-*.json'))
    files.update(directory / name for name in ('pilot-opponent-expectations.json',)
                 if (directory / name).exists())
    files.update((directory / 'frozen-catalogs').glob('*.json'))
    # Also carry the Arena scenery and audit referred to by each new plan.
    for row in new_rows:
        scenery = row['plan']['scenario'].get('scenery')
        if scenery:
            files.update(ROOT / scenery[k] for k in ('path', 'auditPath'))
        donut = row['plan']['scenario'].get('donut')
        if donut:
            files.update(ROOT / donut[k] for k in ('path', 'auditPath'))
            files.update((ROOT / donut['path']).parent.glob('*.per'))
            files.update((ROOT / donut['path']).parent.glob('*.ai'))
    metadata_receipts = []
    for source in sorted(files):
        relative = source.relative_to(ROOT)
        destination = metadata / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        info = dict(source=str(source), bytes=source.stat().st_size, sha256=digest(source))
        copy_file(info, destination, guard)
        metadata_receipts.append(dict(path=destination.relative_to(target).as_posix(),
                                      bytes=info['bytes'], sha256=info['sha256']))
    extended = {**original, 'matchups': original['matchups'] + new_rows}
    extended.setdefault('extensions', []).append(dict(kind=campaign.get('extensionKind', 'arena-donut-no-buffer'),
        addedTrials=len(new_rows), subjectOwnerRecordedPerMatchup=True,
        metadata=metadata_receipts, originalIndexSha256=receipt['originalIndexSha256']))
    opponent_indexes = {r['opponentIndex'] for r in extended['matchups'] if 'opponentIndex' in r}
    extended.update(opponents=len(opponent_indexes), currentCapturePolicy='Arena first; mixed Donut retests; no buffers',
                    state='COMPLETE', sourceDeletionAuthorizedByThisTool=False)
    payload = json.dumps(extended, indent=2).encode('utf-8')
    import hashlib
    new_hash = hashlib.sha256(payload).hexdigest()
    receipt['pendingIndexSha256'] = new_hash
    save(receipt_path, state)
    guard()
    if digest(index_path) != receipt['originalIndexSha256']:
        raise RuntimeError('Index changed while copying; media retained, publication stopped')
    temporary_name = ('run.arena-donut.partial.json' if metadata_name == '_arena_donut_metadata'
                      else f'run.{metadata_name.removeprefix("_")}.partial.json')
    temporary = target / temporary_name
    if temporary.exists() and digest(temporary) != new_hash:
        raise RuntimeError('Conflicting partial index; preserve and review')
    if not temporary.exists():
        with temporary.open('xb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    if digest(temporary) != new_hash:
        raise RuntimeError('Extended index checksum failed')
    temporary.replace(index_path)  # Only the explicitly authorized index extension.
    if digest(index_path) != new_hash:
        raise RuntimeError('Published index verification failed')
    receipt.update(state='COMPLETE', indexSha256=new_hash, completedAt=now())
    save(receipt_path, state)


def main(work, follow):
    queue = read(work / 'queue.json')
    folder = work / 'delivery'
    folder.mkdir(exist_ok=True)
    state_path = folder / 'status.json'
    with (folder / 'copy.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        state = read(state_path) if state_path.exists() else dict(state='WAITING', packages={}, total=queue['total'])
        while True:
            # Conditional Arena decisions may add a few frozen Donut trials.
            # Re-read membership, and publish only after that decision closes.
            queue = read(work / 'queue.json')
            state['total'] = queue['total']
            for campaign in queue['campaigns']:
                if state['packages'].get(campaign['slug'], {}).get('state') == 'COMPLETE':
                    continue
                status_path = Path(campaign['workDirectory']) / 'capture/status.json'
                status = read(status_path) if status_path.exists() else {}
                if (not campaign.get('conditionalDonut', {}).get('pending')
                        and status.get('state') == 'COMPLETE' and status.get('completed') == campaign['total']
                        and not status.get('pendingExports') and not status.get('failed')):
                    deliver(work, campaign, state)
            state['verified'] = sum(r.get('verified', 0) for r in state['packages'].values())
            complete = len(state['packages']) == len(queue['campaigns']) and all(
                r['state'] == 'COMPLETE' for r in state['packages'].values())
            state.update(state='COMPLETE' if complete else 'WAITING', updatedAt=now())
            save(state_path, state)
            if complete or not follow or (work / 'PAUSE').exists():
                return
            capture_path = work / 'status.json'
            if capture_path.exists() and read(capture_path)['state'] in ('NEEDS_ATTENTION', 'PAUSED', 'NEEDS_RETAKES'):
                state.update(state='CAPTURE_NEEDS_ATTENTION'); save(state_path, state)
                return
            time.sleep(30)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=DEFAULT_WORK)
    p.add_argument('--follow', action='store_true')
    args = p.parse_args()
    try:
        main(args.work.resolve(), args.follow)
    except Exception:
        save(args.work / 'delivery/error.json', dict(state='NEEDS_ATTENTION', error=traceback.format_exc(),
             localSourcesRetained=True, updatedAt=now()))
        raise
