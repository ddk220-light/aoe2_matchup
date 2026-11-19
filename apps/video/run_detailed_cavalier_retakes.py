"""Capture and replace the authorized Chinese Cavalier trials in existing archives.

Finish Jomsviking, Hearth Troop and Jarl first, including their verified archive
updates; then process the remaining eight variants. Never change other matchups,
delete local base recordings, or create a duplicate corrected archive folder.
"""
import copy
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

from compact_recording_archive import digest, prepare
from copy_capture_campaign import copy_file, now
from copy_norse_standard_to_share import repeated_row
from prepare_detailed_cavalier_retakes import ROOT, WORK, SHARE
from run_champi_comparison_capture import read, save

RUNS = (ROOT/'aoe2x/js_simulation/calibration/lab/runs').resolve()


def guard():
    if (WORK/'PAUSE').exists() or (ROOT/'data/local/thermal/PAUSED.json').exists():
        raise RuntimeError('User or thermal pause; preserve all sources')
    if not SHARE.is_dir() or shutil.disk_usage(SHARE).free < 4*2**30:
        raise RuntimeError('Dragonstar unavailable or below reserve; preserve all sources')


def replace_rows(index, mapping, new_rows):
    """Pure projection: retain every unaffected row byte-for-byte logically."""
    old_ids = [r['oldJobId'] for r in mapping]
    new_ids = [r['jobId'] for r in mapping]
    existing = [r['jobId'] for r in index['matchups']]
    if len(set(old_ids)) != len(old_ids) or len(set(new_ids)) != len(new_ids):
        raise ValueError('Duplicate replacement identity')
    if not set(old_ids).issubset(existing) or set(new_ids).intersection(existing):
        raise ValueError('Missing original or duplicate new archive identity')
    replacements = {r['jobId']: r for r in new_rows}
    if set(replacements) != set(new_ids):
        raise ValueError('Replacement rows do not match the approved mapping')
    by_old = {r['oldJobId']: replacements[r['jobId']] for r in mapping}
    result = copy.deepcopy(index)
    result['matchups'] = [copy.deepcopy(by_old.get(r['jobId'], r)) for r in index['matchups']]
    if len(result['matchups']) != len(index['matchups']):
        raise ValueError('Archive size changed')
    return result


def safe_child(destination, info):
    # Exact authorized filenames only; no recursive deletion or glob selection.
    target = destination/info['path']
    if target.parent != destination or Path(info['path']).name != info['path']:
        raise ValueError('Archive file escaped the selected run directory')
    return target


def replace_campaign(campaign):
    work = Path(campaign['workDirectory'])
    binding = read(work/'replacement.json')
    destination = Path(binding['destination'])
    if not destination.is_relative_to(SHARE):
        raise ValueError('Destination escaped the authorized share')
    guard()
    state_path = work/'replacement-status.json'
    state = read(state_path) if state_path.exists() else dict(state='PREPARING',
        destination=str(destination),previousIndexSha256=binding['previousIndexSha256'],
        retiredFiles={},startedAt=now())
    if state['destination'] != str(destination) or state['previousIndexSha256'] != binding['previousIndexSha256']:
        raise ValueError('Replacement receipt belongs to another archive')
    index_path = destination/'run.json'
    prepared_path = work/'prepared-run.json'
    if state.get('state') == 'COMPLETE':
        if digest(index_path) != state['newIndexSha256']:
            raise RuntimeError('Completed archive index changed')
        return
    capture = read(work/'capture/status.json')
    if (capture['state'] != 'COMPLETE' or capture['completed'] != campaign['total']
            or capture['failed'] or capture['pendingExports']):
        raise RuntimeError('All replacement captures must verify before archive edits')
    pilot = read(work/'pilot-validation.json')
    if pilot['state'] != 'PASSED' or any(p['opponent']['openingHpPerUnit'] != 140 for p in pilot['pilots']):
        raise RuntimeError('Chinese Cavalier opening-HP gate did not pass')
    original = read(work/'previous-run.json')
    old_rows = {r['jobId']: r for r in original['matchups']}
    results = {r['jobId']: r for r in capture['results'] if r['status'] == 'verified'}
    if not prepared_path.exists():
        new_rows = []
        for item in binding['mapping']:
            guard()
            source = Path(results[item['jobId']]['runDirectory']).resolve()
            if not source.is_relative_to(RUNS/item['jobId']/'live'):
                raise ValueError('Source escaped its replacement job')
            bundle = read(source/'recording.json')
            hp = read(source/bundle['files']['hp']['path'])['rows'][0]['side2']
            if abs(hp['hp']/hp['count']-140) > .1:
                raise RuntimeError('A replacement opponent is not a 140-HP Cavalier')
            row = repeated_row(prepare(source), dict(item,reused=False))
            if row['jobId'] != item['jobId'] or row['plan']['side3']['civ'] != 'Chinese':
                raise ValueError('Wrong replacement job or civilization')
            row['replacesJobId'] = item['oldJobId']
            new_rows.append(row)
        updated = replace_rows(original, binding['mapping'], new_rows)
        updated.setdefault('corrections', []).append(dict(opponentIndex=3,civilization='Chinese',
            unit='Cavalier',expectedHpPerUnit=140,previousRecordedHpPerUnit=180,
            reason=binding['reason'],mapping=binding['mapping'],correctedAt=now()))
        # Portable correction inputs supplement the original frozen provenance.
        metadata = []
        paths = [work/n for n in ('manifest.json','pilot-validation.json','pilot-opponent-expectations.json','preflight.json','replacement.json')]
        paths += list((work/'frozen-catalogs').glob('*.json'))
        paths.append(WORK/'opponent-reference.json')
        for path in paths:
            sub = Path('frozen-catalogs')/path.name if path.parent.name == 'frozen-catalogs' else Path(path.name)
            relative = Path('metadata/cavalier-correction')/sub
            info = dict(source=str(path),path=relative.as_posix(),bytes=path.stat().st_size,sha256=digest(path))
            target = destination/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            copy_file(info,target,guard)
            metadata.append(info)
        updated.setdefault('metadataFiles', []).extend(metadata)
        save(prepared_path,updated)
        state.update(state='COPYING',newIndexSha256=digest(prepared_path))
        save(state_path,state)
    elif state.get('newIndexSha256') != digest(prepared_path):
        raise RuntimeError('Prepared replacement index changed')
    updated = read(prepared_path)
    new_rows = {r['jobId']:r for r in updated['matchups']}
    for item in binding['mapping']:
        for info in new_rows[item['jobId']]['files'].values():
            copy_file(info,safe_child(destination,info),guard)
    # Publish only after every new video/frame pair verifies. Recover safely if
    # publication succeeded just before the previous process stopped.
    current_hash = digest(index_path)
    if current_hash == binding['previousIndexSha256']:
        stage = destination/'run.cavalier-replacement.publish'
        copy_file(dict(source=str(prepared_path),bytes=prepared_path.stat().st_size,
                       sha256=state['newIndexSha256']),stage,guard)
        if digest(index_path) != binding['previousIndexSha256']:
            raise RuntimeError('Archive changed during replacement; preserve old files')
        stage.replace(index_path)  # Explicitly authorized replacement of this index.
    elif current_hash != state['newIndexSha256']:
        raise RuntimeError('Archive index changed outside this correction')
    if digest(index_path) != state['newIndexSha256']:
        raise RuntimeError('Published replacement index failed verification')
    state.update(state='RETIRING_SUPERSEDED',publishedAt=now())
    save(state_path,state)
    # Retire only the exact superseded Spanish Cavalier pairs after publication.
    for item in binding['mapping']:
        for info in old_rows[item['oldJobId']]['files'].values():
            guard()
            target = safe_child(destination,info)
            previous = state['retiredFiles'].get(info['path'])
            if not target.exists():
                if previous and previous['state'] in ('VERIFIED_FOR_REMOVAL','REMOVED'):
                    previous['state'] = 'REMOVED'
                    save(state_path,state)
                    continue
                raise FileNotFoundError('Unreceipted missing superseded archive file')
            if target.stat().st_size != info['bytes'] or digest(target) != info['sha256']:
                raise RuntimeError('Superseded file changed; refuse deletion')
            state['retiredFiles'][info['path']] = dict(state='VERIFIED_FOR_REMOVAL',
                bytes=info['bytes'],sha256=info['sha256'],path=str(target))
            save(state_path,state)
            target.unlink()
            state['retiredFiles'][info['path']]['state'] = 'REMOVED'
            save(state_path,state)
    state.update(state='COMPLETE',verified=campaign['total'],completedAt=now(),localSourcesRetained=True)
    save(state_path,state)


def main():
    with (WORK/'queue.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        queue = read(WORK/'queue.json')
        completed = []
        status_path = WORK/'status.json'
        for campaign in queue['campaigns']:
            guard()
            if shutil.disk_usage(ROOT).free < 8*2**30:
                raise RuntimeError('Local disk below capture reserve')
            work = Path(campaign['workDirectory'])
            state = read(work/'capture/status.json') if (work/'capture/status.json').exists() else {}
            save(status_path,dict(state='CAPTURING',pid=os.getpid(),total=80,current=campaign,completed=completed,updatedAt=now()))
            if state.get('completed') != campaign['total'] or state.get('failed') or state.get('pendingExports'):
                with (work/'worker-output.log').open('a',encoding='utf-8') as out, (work/'worker-error.log').open('a',encoding='utf-8') as err:
                    subprocess.run([sys.executable,'-u',str(ROOT/'apps/video/run_camel_comparison_capture.py'),
                                    '--work',str(work)],cwd=ROOT,stdout=out,stderr=err,check=True)
            save(status_path,dict(state='REPLACING',pid=os.getpid(),total=80,current=campaign,completed=completed,updatedAt=now()))
            replace_campaign(campaign)
            completed.append(dict(key=campaign['key'],verified=campaign['total'],replaced=True))
        save(status_path,dict(state='COMPLETE',total=80,verified=80,completed=completed,updatedAt=now()))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        save(WORK/'status.json',dict(state='NEEDS_ATTENTION',error=traceback.format_exc(),updatedAt=now()))
        raise
