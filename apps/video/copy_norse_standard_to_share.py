"""Deliver four self-contained Norse standard-unit archives to the approved SMB share.

Copy only complete sets; keep every local source. Durable local receipts own new
destination folders and bind their indexes. Partial files are never published
until size and SHA-256 verify. Repeated battles get explicit iteration suffixes.
The finite --follow worker waits for the 40 no-Hussar retakes, then exits.
"""
import argparse
from datetime import datetime, timezone
import json
import msvcrt
import os
from pathlib import Path
import shutil
import time
import traceback

from compact_recording_archive import digest, prepare, read
from copy_capture_campaign import copy_file
from run_champi_comparison_capture import save

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/local/norse-standard-capture'
RETAKE = ROOT / 'data/local/jarl-standard-without-hussar'
WORK = ROOT / 'data/local/norse-standard-delivery'
SHARE = Path(r'\\100.123.128.35\AoE2-Incoming')
RUNS = (ROOT / 'aoe2x/js_simulation/calibration/lab/runs').resolve()
RUN_NAME = 'Standard_Units_Winter_5_Repeats'
RESERVE = 4 * 2**30
QUEUE = None
RETIRE_UNTRIMMED = False


def now():
    return datetime.now(timezone.utc).isoformat()


def selection():
    if QUEUE is not None:
        queue = read(QUEUE)
        packages = []
        for row in queue['campaigns']:
            campaign = Path(row['workDirectory'])
            jobs = [dict(jobId=r['id'], sourceCampaign=str(campaign), reused=False,
                         iteration=r['iteration'], opponentIndex=r['opponentIndex'],
                         bufferSetting=r['bufferSetting'],
                         bufferComparisonApplicable=r['bufferComparisonApplicable'])
                    for r in read(campaign / 'manifest.json')['matchups']]
            keys = {(r['opponentIndex'], r['bufferSetting'], r['iteration']) for r in jobs}
            if len(keys) != len(jobs) or len(jobs) != row['total']:
                raise ValueError('Duplicate trials or incomplete campaign manifest')
            conditions = {(o, b) for o, b, _ in keys}
            if keys != {(o, b, i) for o, b in conditions for i in range(1, 6)}:
                raise ValueError('Every condition must retain all five trials')
            packages.append(dict(folder=row['slug'], title=row['civilization'] + ' ' + row['unit'], matchups=jobs))
        if sum(len(p['matchups']) for p in packages) != queue['total']:
            raise ValueError('Queue total does not match delivery manifests')
        return packages
    packages = []
    for slug, folder in [('elite_jomsviking_danes', 'Elite_Jomsviking'),
                         ('elite_hearth_troop_saxons', 'Elite_Hearth_Troop'),
                         ('elite_jarl_varangians', 'Elite_Jarl_with_Hussar')]:
        campaign = BASE / slug
        jobs = [dict(jobId=r['id'], sourceCampaign=str(campaign), reused=False,
                     iteration=r['iteration'], opponentIndex=r['opponentIndex'])
                for r in read(campaign / 'manifest.json')['matchups']]
        packages.append(dict(folder=folder, title=folder.replace('_', ' '), matchups=jobs))
    packages.append(dict(folder='Elite_Jarl_without_Hussar',
        title='Elite Jarl without Hussar', matchups=read(RETAKE / 'selection.json')['matchups']))
    for package in packages:
        pairs = {(r['opponentIndex'], r['iteration']) for r in package['matchups']}
        if len(package['matchups']) != 70 or pairs != {(o, r) for o in range(1, 15) for r in range(1, 6)}:
            raise ValueError('Expected all 14 opponents and five distinct trials each')
    return packages


def ready_sources(package):
    statuses = {}
    sources = []
    for item in package['matchups']:
        campaign = Path(item['sourceCampaign'])
        if campaign not in statuses:
            path = campaign / 'capture/status.json'
            status = read(path) if path.exists() else {}
            if status.get('state') in ('NEEDS_ATTENTION', 'CRASHED', 'STOPPED_AFTER_ERRORS', 'COMPLETE_WITH_FAILURES'):
                raise RuntimeError(f'Capture needs attention: {campaign}')
            if status.get('state') != 'COMPLETE' or status.get('pendingExports') or status.get('failed'):
                return None
            statuses[campaign] = {r['jobId']: r for r in status['results'] if r['status'] == 'verified'}
        result = statuses[campaign].get(item['jobId'])
        if not result:
            return None
        source = Path(result['runDirectory']).resolve()
        if not source.is_relative_to(RUNS / item['jobId'] / 'live'):
            raise ValueError('Run path escaped its recorded job')
        sources.append((item, source))
    return sources


def repeated_row(row, item):
    """Retain all trials even when their matchup labels are identical."""
    condition = '_' + item['bufferSetting'] if 'bufferSetting' in item else ''
    row['name'] += f"{condition}_r{item['iteration']:02}"
    for key, info in row['files'].items():
        info['path'] = row['name'] + ('.mp4' if key == 'battle.mp4' else '.frames.bin')
    row.update(iteration=item['iteration'], opponentIndex=item['opponentIndex'],
               reusedUnchangedRecording=item['reused'], originalJobId=item.get('originalJobId', item['jobId']))
    if 'bufferSetting' in item:
        row.update(bufferSetting=item['bufferSetting'],
                   bufferComparisonApplicable=item['bufferComparisonApplicable'])
    return row


def guard():
    if (WORK / 'PAUSE').exists() or (ROOT / 'data/local/thermal/PAUSED.json').exists():
        raise RuntimeError('Copy paused; local sources retained')
    if not SHARE.is_dir():
        raise RuntimeError('Approved SMB share unavailable; local sources retained')
    if shutil.disk_usage(SHARE).free < RESERVE:
        raise RuntimeError('Network destination is below the 4 GiB reserve')


def metadata_files(package):
    """Explicit allowlist: no credentials, caches, unrelated runs or huge logs."""
    if QUEUE is not None:
        files = {QUEUE, ROOT / 'docs/video-production/DETAILED_STANDARD_CAPTURE.md'}
        for campaign in {Path(r['sourceCampaign']) for r in package['matchups']}:
            base = campaign.parent
            files.update(base / n for n in ('opponents.json', 'source.json', 'queue.json'))
            files.update((base / 'winter-templates').glob('*'))
            files.update((base / 'scenery-source').glob('*'))
            files.update(p for name in ('manifest.json', 'subject-stats.json', 'preflight.json',
                                       'pilot-validation.json') if (p := campaign / name).is_file())
            files.update((campaign / 'frozen-catalogs').glob('*.json'))
        return sorted(p for p in files if p.is_file())
    files = {BASE / 'opponents.json', BASE / 'source.json', BASE / 'queue.json',
             ROOT / 'docs/video-production/NORSE_STANDARD_CAPTURE.md'}
    files.update((BASE / 'winter-templates').glob('*'))
    for campaign in {Path(r['sourceCampaign']) for r in package['matchups']}:
        files.update(p for name in ('manifest.json', 'subject-stats.json', 'preflight.json',
                                   'pilot-validation.json') if (p := campaign / name).is_file())
        files.update((campaign / 'frozen-catalogs').glob('*.json'))
    if package['folder'].endswith('without_Hussar'):
        files.add(RETAKE / 'selection.json')
    return sorted(files)


def deliver(package, sources, state, state_path):
    destination = SHARE / package['folder'] / RUN_NAME
    receipt = state['packages'].get(package['folder'])
    identity = dict(destination=str(destination), jobs=[r['jobId'] for r in package['matchups']])
    if receipt is None:
        if destination.exists():
            raise FileExistsError(f'Refusing to claim existing destination: {destination}')
        receipt = dict(identity=identity, verified=0, indexSha256=None, state='COPYING')
        state['packages'][package['folder']] = receipt
        save(state_path, state)  # Claim is durable before creating the new folder.
    elif receipt['identity'] != identity:
        raise RuntimeError('Receipt identity changed; refuse to mix recordings')
    destination.mkdir(parents=True, exist_ok=True)
    index_path = destination / 'run.json'
    index = dict(schemaVersion=1, kind='aoe2lab.compact-archive', title=package['title'],
        matchups=[], finalVideo=None, sourceDeletionAuthorizedByThisTool=False,
        iterationsPerOpponent=5, opponents=14,
        bufferNote='with_hussars applies only to mixed melee/ranged fights; same-type fights have one five-trial no_buffer set.',
        state='COPYING')
    if index_path.exists():
        if digest(index_path) != receipt['indexSha256']:
            raise RuntimeError('Destination index changed outside this worker')
        index = read(index_path)
    elif receipt['verified']:
        raise RuntimeError('Previously verified index is missing')
    copied = {r['jobId']: r for r in index['matchups']}
    if not set(copied).issubset(identity['jobs']):
        raise RuntimeError('Unexpected destination job IDs')
    for item, source in sources:
        guard()
        if item['jobId'] in copied:
            for info in copied[item['jobId']]['files'].values():
                target = destination / info['path']
                if not target.is_file() or target.stat().st_size != info['bytes'] or digest(target) != info['sha256']:
                    raise RuntimeError(f'Copied recording changed: {target}')
            continue
        row = repeated_row(prepare(source), item)
        if row['jobId'] != item['jobId'] or row['name'].casefold() in {r['name'].casefold() for r in copied.values()}:
            raise ValueError('Duplicate recording name or wrong job identity')
        state.update(state='COPYING', currentUnit=package['folder'], currentJob=item['jobId'], updatedAt=now())
        save(state_path, state)
        for info in row['files'].values():
            target = destination / info['path']
            if target.parent != destination:
                raise ValueError('Unsafe archive filename')
            copy_file(info, target, guard)
        index['matchups'].append(row)
        if index_path.exists() and digest(index_path) != receipt['indexSha256']:
            raise RuntimeError('Archive index changed during copy')
        save(index_path, index)
        copied[row['jobId']] = row
        receipt.update(verified=len(copied), indexSha256=digest(index_path),
            bytes=sum(f['bytes'] for r in copied.values() for f in r['files'].values()))
        save(state_path, state)
        print(f"{package['folder']}: {len(copied)}/{len(package['matchups'])} copied and checksum verified", flush=True)
    # Include small reconstruction files with portable project-relative paths.
    metadata = []
    for path in metadata_files(package):
        relative = Path('metadata') / path.relative_to(ROOT)
        info = dict(source=str(path), path=relative.as_posix(), bytes=path.stat().st_size, sha256=digest(path))
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        copy_file(info, target, guard)
        metadata.append(info)
    index.update(state='COMPLETE', metadataFiles=metadata, completedAt=now())
    if digest(index_path) != receipt['indexSha256']:
        raise RuntimeError('Archive index changed before finalization')
    save(index_path, index)
    receipt.update(state='COMPLETE', indexSha256=digest(index_path), completedAt=now())
    save(state_path, state)


def retire_untrimmed(package, sources, state, state_path):
    """Retire only redundant MOVs after complete, verified battle/frame delivery.

    Clean battle MP4s, frame streams and all alignment metadata remain local.
    Explicit file paths and durable per-file receipts make interruption safe;
    no recursive removal and no remote file deletion is ever performed.
    """
    receipt = state['packages'][package['folder']]
    destination = Path(receipt['identity']['destination'])
    index_path = destination / 'run.json'
    guard()
    if receipt['state'] != 'COMPLETE' or digest(index_path) != receipt['indexSha256']:
        raise RuntimeError('Complete, unchanged archive required before retiring MOVs')
    index = read(index_path)
    archived = {r['jobId']: r for r in index['matchups']}
    retired = receipt.setdefault('retiredUntrimmed', {})
    for item, source in sources:
        guard()
        row = archived[item['jobId']]
        bundle = read(source / 'recording.json')
        video = bundle['files']['video']
        target = (source / video['path']).resolve()
        expected_root = RUNS / item['jobId'] / 'live'
        if not source.is_relative_to(expected_root) or not target.is_relative_to(source) or target.suffix.lower() != '.mov':
            raise ValueError('Untrimmed path escaped this completed recording')
        previous = retired.get(item['jobId'])
        if previous and previous['state'] == 'REMOVED':
            continue
        if not target.exists():
            if previous and previous['state'] == 'VERIFIED_FOR_REMOVAL':
                previous.update(state='REMOVED', completedAt=now())
                save(state_path, state)
                continue
            raise FileNotFoundError(f'Unreceipted missing source: {target}')
        # Recheck the irreplaceable local AND destination pair immediately
        # before touching the redundant untrimmed file.
        for key in ('battleVideo', 'frames', 'battleHp'):
            info = bundle['files'][key]
            local = (source / info['path']).resolve()
            if not local.is_relative_to(source) or local.stat().st_size != info['bytes'] or digest(local) != info['sha256']:
                raise RuntimeError(f'Local reconstruction source failed verification: {local}')
        for info in row['files'].values():
            remote = destination / info['path']
            if remote.parent != destination or remote.stat().st_size != info['bytes'] or digest(remote) != info['sha256']:
                raise RuntimeError(f'Archive failed verification: {remote}')
        if target.stat().st_size != video['bytes'] or digest(target) != video['sha256']:
            raise RuntimeError(f'Untrimmed source changed: {target}')
        retired[item['jobId']] = dict(state='VERIFIED_FOR_REMOVAL', path=str(target),
            bytes=video['bytes'], sha256=video['sha256'], verifiedAt=now())
        save(state_path, state)
        target.unlink()
        retired[item['jobId']].update(state='REMOVED', completedAt=now())
        save(state_path, state)
    receipt['untrimmedRetirementComplete'] = True
    save(state_path, state)


def main(follow):
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'copy.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        state_path = WORK / 'status.json'
        state = read(state_path) if state_path.exists() else dict(packages={}, localSourcesRetained=True,
            destination=str(SHARE), sourceDeletionAuthorized=False, startedAt=now())
        state['pid'] = os.getpid()
        try:
            packages = selection()
            while True:
                guard()
                for package in packages:
                    receipt = state['packages'].get(package['folder'], {})
                    if receipt.get('state') == 'COMPLETE' and (not RETIRE_UNTRIMMED or receipt.get('untrimmedRetirementComplete')):
                        continue
                    sources = ready_sources(package)
                    if sources is not None:
                        if receipt.get('state') != 'COMPLETE':
                            deliver(package, sources, state, state_path)
                        if RETIRE_UNTRIMMED:
                            retire_untrimmed(package, sources, state, state_path)
                complete = len(state['packages']) == len(packages) and all(p['state'] == 'COMPLETE' for p in state['packages'].values())
                state.update(state='COMPLETE' if complete else 'WAITING_FOR_CAPTURE',
                    currentUnit=None, currentJob=None, updatedAt=now(),
                    copied=sum(p['verified'] for p in state['packages'].values()), total=sum(len(p['matchups']) for p in packages),
                    destinationFreeBytes=shutil.disk_usage(SHARE).free)
                save(state_path, state)
                if complete or not follow:
                    return
                time.sleep(30)
        except Exception:
            state.update(state='NEEDS_ATTENTION', error=traceback.format_exc(), updatedAt=now())
            save(state_path, state)
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--follow', action='store_true')
    parser.add_argument('--queue', type=Path, help='Prepared repeated-trial queue with explicit buffer settings')
    parser.add_argument('--work', type=Path, help='Separate local receipts for this delivery')
    parser.add_argument('--run-name', help='New destination run subfolder; existing folders are never claimed')
    parser.add_argument('--retire-untrimmed', action='store_true', help='After verified complete delivery, retire redundant local MOVs; retain battle MP4s/frames/metadata')
    args = parser.parse_args()
    if args.queue and not (args.work and args.run_name):
        parser.error('--queue requires separate --work and --run-name')
    QUEUE = args.queue.resolve() if args.queue else None
    WORK = args.work.resolve() if args.work else WORK
    RETIRE_UNTRIMMED = args.retire_untrimmed
    if RETIRE_UNTRIMMED and not QUEUE:
        parser.error('--retire-untrimmed requires an explicit finite queue')
    if args.run_name:
        if Path(args.run_name).name != args.run_name or args.run_name in ('.', '..'):
            parser.error('--run-name must be a single folder name')
        RUN_NAME = args.run_name
    main(args.follow)
