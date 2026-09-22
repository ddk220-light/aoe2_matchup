"""Finalize the canonical knight archive and retire only enumerated duplicates.

User authorization is the September 21 request to keep one reproducible knight
set on the original disk and clean redundant PC/disk copies. No recursive
deletion, broad wildcard deletion, or unrelated campaign cleanup is performed.
"""
import argparse
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil

from compact_recording_archive import digest, read
from consolidate_knight_recordings import DEST, ROOT, RUNS, WORK, guard, now, save


def hydrated(row):
    row = deepcopy(row)
    if row.get('metadataOnly'):
        path = Path(row['sourceMetadata']['recording']['path'])
        recording = read(path)
        row['recording'] = recording
        hp = read(path.parent / recording['files']['battleHp']['path'])
        row['timing'] = {k:v for k,v in hp.items() if k != 'rows'}
        row['streamMetadata'] = read(path.parent / recording['files']['metadata']['path'])
        # With frames absent these samples are surviving evidence, rather than
        # a disposable cache that can safely be decoded again.
        row['retainedHpSamples'] = hp
        row['retainedCaptureHpSamples'] = read(path.parent / recording['files']['hp']['path'])
    if 'replacedResult' in row:
        row['replacedResult'] = hydrated(row['replacedResult'])
    return row


def prepare_cleanup():
    """Freeze exact file candidates; this phase does not alter either disk."""
    plan = read(WORK / 'plan.json')
    variants = {v['key']: v for v in plan['variants']}
    by_civ = {v['matchups'][0]['plan']['side2']['civ']: v['key'] for v in variants.values()}
    selected = {(v['key'],r['plan']['side3']['slug']): r for v in variants.values() for r in v['matchups']}
    history = deepcopy(plan['sourceIndexes'])
    for civ in ('franks','teutons','lithuanians','persians'):
        for prefix in ('paladin-line-', 'paladin-leitis-four-relics-'):
            path = Path('E:/AoE2 Renders') / (prefix+civ) / 'run.json'
            if path.is_file():
                history[str(path)] = dict(sha256=digest(path), index=read(path))
    candidates = {}; skipped=[]

    def add(source, entry, key, row, source_root, reason):
        source = source.resolve(); source_root = source_root.resolve()
        if not source.is_relative_to(source_root) or source.is_relative_to(DEST.resolve()):
            raise ValueError(f'Escaped cleanup path: {source}')
        if not source.is_file():
            return
        if source.suffix.lower() not in ('.mp4','.mov','.bin'):
            raise ValueError('Only explicitly listed capture media may be removed')
        if source.stat().st_size != entry['bytes']:
            raise ValueError(f'Source size changed: {source}')
        dependencies=[dict(path=str(DEST/key/f['path']),bytes=f['bytes'],sha256=f['sha256'])
                      for f in row['files'].values()]
        candidates[str(source)]=dict(source=str(source),sourceRoot=str(source_root),
            bytes=entry['bytes'],sha256=entry['sha256'],reason=reason,
            replacementJobId=row['jobId'],replacement=dependencies)

    for text, item in history.items():
        index=Path(text)
        # Metadata-only result indexes have no files and never cause deletion.
        if index.drive not in ('D:','E:'):
            continue
        if index.parent.parent not in (Path('D:/AoE2 Renders'),Path('E:/AoE2 Renders')):
            raise ValueError('Unexpected archive cleanup root')
        for old in item['index']['matchups']:
            key=by_civ[old['plan']['side2']['civ']]
            row=selected[(key,old['plan']['side3']['slug'])]
            if not row['mediaAvailable']:
                skipped.append(dict(jobId=old['jobId'],reason='No complete canonical replacement; preserve any source'))
                continue
            if old['plan']['side2']['slug'] != row['plan']['side2']['slug']:
                raise ValueError('Different subject unit must not be retired as a duplicate')
            for name in ('battle.mp4','frames.bin'):
                if name in old.get('files',{}):
                    entry=old['files'][name]
                    add(index.parent/entry['path'],entry,key,row,index.parent,
                        'Verified canonical copy' if old['jobId']==row['jobId'] else
                        'Superseded trial; original results and metadata retained in source history')
    for key, variant in variants.items():
        for row in variant['matchups']:
            if not row['mediaAvailable']:
                continue
            live=(RUNS/row['jobId']/'live/run_001').resolve()
            if not live.is_relative_to(RUNS.resolve()):
                raise ValueError('Capture path escaped the lab')
            for name in ('battleVideo','frames','video'):
                entry=row['recording']['files'].get(name)
                if entry:
                    add(live/entry['path'],entry,key,row,live,
                        'Verified clean battle and frame pair retained; remove local working/untrimmed copy')
    # These explicitly identified failed attempts have successful replacements.
    # They are not selected by a broad "failure" filename sweep.
    failed = [
        ('heavy-hei-guang-cavalry-wei', 'elite_composite_bowman_armenians',
         RUNS/'knight_expansion_heavy_hei_guang_cavalry_wei_unique_01_armenians_elite_composite_bowman_armenians/live/bad_001',
         ('failure_attempt_1.grpc.frames.bin','failure_attempt_1.mov',
          'raw recordings/heavy_hei_guang_cavalry_wei_vs_elite_composite_bowman_armenians.mov')),
        ('cavalier-bulgarians', 'flaming_camel_tatars',
         Path('E:/AoE2 Renders/retained-source-versions/cavalier_bulgarians_unique_63_tatars_flaming_camel_tatars/live/run_001'),
         ('failure_attempt_1.grpc.frames.bin','failure_attempt_1.mov')),
    ]
    for key, slug, folder, names in failed:
        row=selected[(key,slug)]
        if not row['mediaAvailable']:
            continue
        for name in names:
            source=folder/name
            if source.is_file():
                add(source,dict(bytes=source.stat().st_size,sha256=digest(source)),key,row,folder,
                    'Failed diagnostic capture; verified successful canonical battle retained')
    save(WORK/'cleanup-plan.json',dict(createdAt=now(),candidates=list(candidates.values()),
        bytes=sum(c['bytes'] for c in candidates.values()),skipped=skipped,history=history,
        variants=[dict(v,matchups=[hydrated(r) for r in v['matchups']]) for v in variants.values()]))
    totals={}
    for item in candidates.values():
        drive=Path(item['source']).drive;totals[drive]=totals.get(drive,0)+item['bytes']
    print(json.dumps(dict(files=len(candidates),GiBByDrive={k:round(v/2**30,2) for k,v in totals.items()},skipped=len(skipped))))


def receipt_map():
    return {r['destination']:r for r in (json.loads(line) for line in
            (WORK/'copy-receipts.jsonl').read_text().splitlines())}


def check_replacement(candidate, receipts):
    if len(candidate['replacement']) != 2:
        raise ValueError('Both clean video and frames are required before deletion')
    for entry in candidate['replacement']:
        path=Path(entry['path']).resolve()
        if not path.is_relative_to(DEST.resolve()) or not path.is_file():
            raise ValueError('Replacement is missing or outside the canonical archive')
        receipt=receipts.get(str(path))
        if not receipt or (receipt['sha256'],receipt['bytes']) != (entry['sha256'],entry['bytes']):
            raise ValueError('No matching destination checksum receipt')
        if path.stat().st_size != entry['bytes']:
            raise ValueError('Canonical file changed after copy verification')


def validated_source(candidate, verified_copies=None, inventory=None):
    source=Path(candidate['source']).resolve(); allowed=Path(candidate['sourceRoot']).resolve()
    scope = RUNS.resolve() if source.drive == ROOT.drive else (
        Path('D:/AoE2 Renders') if source.drive == 'D:' else Path('E:/AoE2 Renders'))
    if source.drive not in (ROOT.drive,'D:','E:') or not source.is_relative_to(scope):
        raise ValueError('Cleanup is restricted to known capture and archive roots')
    if not source.is_relative_to(allowed) or source.is_relative_to(DEST.resolve()):
        raise ValueError('Unsafe cleanup path')
    if source.suffix.lower() not in ('.mp4','.mov','.bin'):
        raise ValueError('Unexpected file type')
    if not source.is_file() or source.stat().st_size != candidate['bytes']:
        raise ValueError(f'Changed source; preserve it: {source}')
    stamp=source.stat()
    key=str(source).casefold()
    receipt=(verified_copies or {}).get(key)
    # The copy pass just hashed both source and destination. Reuse that proof
    # only when the source also retains its independently inventoried mtime.
    # Alternate trials and changed/unknown files still receive a fresh hash.
    unchanged=(receipt is not None
        and (receipt['bytes'],receipt['sha256'])==(candidate['bytes'],candidate['sha256'])
        and (inventory or {}).get(key)==stamp.st_mtime_ns
        and stamp.st_mtime_ns <= datetime.fromisoformat(receipt['verifiedAt']).timestamp()*1e9)
    if not unchanged and digest(source)!=candidate['sha256']:
        raise ValueError(f'Changed source; preserve it: {source}')
    candidate['sourceVerification']=dict(
        method='Current copy SHA-256 receipt plus unchanged inventory mtime' if unchanged else 'Fresh source SHA-256',
        mtimeNs=stamp.st_mtime_ns,copyVerifiedAt=receipt['verifiedAt'] if unchanged else None)
    return source


def append_receipt(path, row):
    with path.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(row)+'\n');stream.flush();os.fsync(stream.fileno())


def remove_empty_source_archives(cleanup, log):
    """Remove only copied indexes and empty, explicitly known archive folders."""
    for text,item in cleanup['history'].items():
        index=Path(text)
        if index.drive not in ('D:','E:') or not index.is_file():
            continue
        folder=index.parent.resolve()
        if folder.parent not in (Path('D:/AoE2 Renders'),Path('E:/AoE2 Renders')) or folder.is_relative_to(DEST.resolve()):
            raise ValueError('Source archive escaped approved roots')
        # Do not detach an index from unexpected surviving media or other files.
        remaining=[p for p in folder.iterdir() if p.name!='run.json']
        if remaining:
            continue
        if digest(index)!=item['sha256']:
            raise ValueError('Source index changed; preserve it')
        index.unlink()
        append_receipt(log,dict(source=str(index),state='index_retired_to_history',at=now()))
        if not any(folder.iterdir()):
            folder.rmdir()  # Non-recursive; fails if any file appeared meanwhile.


def retain_finished_video():
    """Rename the existing master within the same disk; never recopy 8 GiB."""
    source=Path('E:/AoE2 Renders/paladin-four-civs-production/production/Paladin_Four_Civs_Complete_With_Intro.mp4')
    target=DEST/'finished-videos'/source.name
    if not source.exists():
        return
    if target.exists() or source.resolve().parent!=Path('E:/AoE2 Renders/paladin-four-civs-production/production'):
        raise ValueError('Finished-video destination conflict; preserve source')
    before=source.stat()
    if before.st_size!=8550239102:
        raise ValueError('Finished master differs from its saved transfer receipt')
    target.parent.mkdir(parents=True,exist_ok=True)
    guard()
    source.rename(target)
    after=target.stat()
    if (before.st_ino,before.st_size)!=(after.st_ino,after.st_size):
        raise RuntimeError('Unexpected file identity after same-volume rename; retain file')
    save(DEST/'finished-videos/manifest.json',dict(path=target.name,bytes=after.st_size,
        sha256FromPriorVerifiedReceipt='466cc62781d3c37169d07893ffd9d2e8f0fda77dbc513d28031318f99490d62d',
        movedFrom=str(source),method='Same-volume rename; identical file ID and size',movedAt=now()))


def retain_rebuild_data():
    """Keep one small snapshot of non-derivable stat inputs, without caches."""
    assets=[]
    source=ROOT/'data/golden/aoe2_reference.db'
    assets.append((source,DEST/'rebuild-data/aoe2_reference.db'))
    seen=set()
    for folder in ('knight-expansion','knight-v2-recapture'):
        queue=read(ROOT/'data/local'/folder/'queue.json')
        for campaign in queue['campaigns']:
            if campaign['key']=='expansion-leitis-four-relics':
                continue
            source=Path(campaign['workDirectory'])/'subject-stats.json'
            stats=read(source)
            civ=stats[0]['civ_name']
            if civ in seen:
                continue
            seen.add(civ)
            assets.append((source,DEST/'rebuild-data/subjects'/(civ.lower()+'.json')))
    manifest=[]
    for source,target in assets:
        sha=digest(source)
        if target.exists():
            if digest(target)!=sha:
                raise ValueError('Rebuild snapshot conflict; preserve both inputs')
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
            if digest(target)!=sha:
                raise ValueError('Rebuild snapshot checksum failed')
        manifest.append(dict(path=str(target.relative_to(DEST)),bytes=target.stat().st_size,sha256=sha))
    save(DEST/'rebuild-data/manifest.json',dict(files=manifest,createdAt=now()))
    text=(ROOT/'docs/video-production/KNIGHT_CANONICAL_ARCHIVE.md').read_text(encoding='utf-8')
    (DEST/'README.md').write_text(text,encoding='utf-8')


def finish():
    import msvcrt
    import win32api
    guard()
    completed=WORK/'cleanup-status.json'
    if completed.is_file() and read(completed).get('state')=='COMPLETE_AVAILABLE_RECORDINGS':
        print(json.dumps(read(completed)))
        return
    if (win32api.GetVolumeInformation('D:/')[1]&0xFFFFFFFF) != int('5EA9EEEF',16):
        raise RuntimeError('SAFEHOUSE identity changed; no cleanup performed')
    state=read(WORK/'status.json')
    if state['state']!='AVAILABLE_MEDIA_VERIFIED':
        raise RuntimeError('Complete verified copies are required before cleanup')
    plan=read(WORK/'plan.json'); cleanup=read(WORK/'cleanup-plan.json'); receipts=receipt_map()
    verified_copies={str(Path(r['source']).resolve()).casefold():r for r in receipts.values()}
    inventory={str(Path(r['path']).resolve()).casefold():r['mtimeNs']
               for r in read(WORK/'media-inventory.json')['files']}
    if len(receipts)!=len(plan['assets']):
        raise ValueError('Copy receipts are incomplete')
    # Keep all historical outcomes and complete reconstruction metadata before
    # retiring an alternate trial. No reported result is selected by winning HP.
    save(DEST/'source-index-history.json',cleanup['history'])
    for variant in cleanup['variants']:
        save(DEST/variant['key']/'run.json',dict(schemaVersion=1,
            kind='aoe2lab.canonical-recording-set',title=variant['label'],matchups=variant['matchups'],
            finalVideo=None,allMediaAvailable=all(r['mediaAvailable'] for r in variant['matchups'])))
    save(DEST/'maintenance/cleanup-plan.json',{k:v for k,v in cleanup.items() if k not in ('history','variants')})
    save(DEST/'maintenance/copy-receipts.json',list(receipts.values()))
    retain_rebuild_data()
    with (WORK/'cleanup.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        log=WORK/'deletion-receipts.jsonl'
        prior=[json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        done={r['source'] for r in prior if r.get('state')=='deleted'}
        freed={}
        for row in prior:
            if row.get('state')=='deleted':
                drive=Path(row['source']).drive;freed[drive]=freed.get(drive,0)+row['bytes']
        for n,item in enumerate(cleanup['candidates'],1):
            if item['source'] in done:
                continue
            guard();check_replacement(item,receipts)
            source=Path(item['source'])
            if source.drive=='D:' and (win32api.GetVolumeInformation('D:/')[1]&0xFFFFFFFF)!=int('5EA9EEEF',16):
                raise RuntimeError('SAFEHOUSE identity changed; sources retained')
            if not source.exists():
                # Could be an interrupted deletion or an outside change. Do not
                # invent reclaimed-byte counts; keep a distinct recovery receipt.
                append_receipt(log,dict(source=str(source),state='already_absent',at=now()))
                continue
            source=validated_source(item,verified_copies,inventory)
            append_receipt(log,dict(item,state='verified_before_delete',at=now()))
            source.unlink()
            append_receipt(log,dict(item,state='deleted',at=now()))
            freed[source.drive]=freed.get(source.drive,0)+item['bytes']
            save(WORK/'cleanup-status.json',dict(state='CLEANING_VERIFIED_DUPLICATES',at=now(),
                filesProcessed=n,totalFiles=len(cleanup['candidates']),freedBytes=freed))
        remove_empty_source_archives(cleanup,log)
        retain_finished_video()
        save(DEST/'maintenance/deletion-receipts.json',[json.loads(line) for line in log.read_text().splitlines()])
        save(WORK/'cleanup-status.json',dict(state='COMPLETE_AVAILABLE_RECORDINGS',at=now(),
            pairedRecordings=len(plan['assets'])//2,missingPairs=len(plan['missing']),
            freedBytes=freed,freeGiB={d:round(shutil.disk_usage(d+':/').free/2**30,2) for d in ('C','D','E')}))
        result=read(WORK/'cleanup-status.json')
        save(WORK/'status.json',dict(result,sourceDeletionPerformed=True))
        print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','finish'))
    args=parser.parse_args()
    prepare_cleanup() if args.action=='prepare' else finish()
