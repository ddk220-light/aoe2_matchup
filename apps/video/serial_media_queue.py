"""Finish one episode through verified upload and cleanup before the next.

Actual visual review remains a gate, never synthesized by this worker.
Game capture is a separate lane; publication-blocking retakes have priority.
"""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from aoe2x.lab.io import write_json, utc_now

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'
OUT = LAB / 'continuous-production'
ORDER = ('missionary', 'korean-war-wagon', 'korean-fire-lancer', 'magyar-huszar')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def paused():
    return (OUT/'STOP').exists() or (ROOT/'data/local/thermal/PAUSED.json').exists()


def verified(rows):
    return len(rows) == 11 and len({r['key'] for r in rows}) == 11 and all(
        r['processing'] == 'succeeded' and all(r[k] for k in
        ('thumbnail', 'channelMatches', 'titleMatches', 'descriptionMatches')) for r in rows)


def cleanup(key, batch):
    """Delete only manifest-listed individual videos after fresh verification."""
    assert verified(read(batch.parent/'verification.json'))
    capture = read(LAB/f'campaigns/{key}-all-unique/status.json')
    assert capture['state'] == 'COMPLETE' and capture['failed'] == 0
    full = read(LAB/f'compilations/{key}-unique-units/final/manifest.json')
    assert full['fullDecode'] == 'passed' and Path(full['output']).is_file()
    plan, frames = [], []
    for job in capture['results']:
        run = Path(job['runDirectory']).resolve()
        assert run.is_relative_to((LAB/'runs').resolve())
        manifest = read(run/'recording.json')
        frame = (run/manifest['files']['frames']['path']).resolve()
        assert frame.is_file() and frame.stat().st_size == manifest['files']['frames']['bytes']
        frames.append({'path': str(frame), 'bytes': frame.stat().st_size})
        candidates = [run/manifest['files'][k]['path'] for k in ('video', 'battleVideo')]
        candidates.append(run/'unit-hp-overlay/battle-with-unit-hp.mp4')
        for candidate in candidates:
            candidate = candidate.resolve()
            assert candidate.is_relative_to(run) and candidate.suffix.lower() in ('.mp4', '.mov', '.mkv')
            if candidate.is_file():
                plan.append({'path': str(candidate), 'bytes': candidate.stat().st_size})
    audit = LAB/'media-cleanup'/key
    audit.mkdir(parents=True, exist_ok=True)
    write_json(audit/'deletion-plan.json', {'files': plan, 'framesPreserved': frames})
    for item in plan:
        if paused():
            raise RuntimeError('Paused during cleanup; exact deletion plan retained')
        Path(item['path']).unlink()
    assert all(Path(f['path']).stat().st_size == f['bytes'] for f in frames)
    write_json(audit/'receipt.json', {'completedAt': utc_now(), 'deletedVideoFiles': len(plan),
        'freedGiB': round(sum(f['bytes'] for f in plan)/2**30, 2),
        'framesPreserved': len(frames), 'fullVideoPreserved': full['output']})


def main():
    import msvcrt
    OUT.mkdir(parents=True, exist_ok=True)
    lock = (OUT/'serial-media.lock').open('a+b')
    lock.write(b'0'); lock.flush(); lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    state = {'pid': os.getpid(), 'startedAt': utc_now(), 'order': ORDER}

    def save(label, key, **extra):
        state.update(state=label, currentEpisode=key, updatedAt=utc_now(), **extra)
        write_json(OUT/'serial-media.json', state)

    def call(key, script, *args):
        while paused():
            save('PAUSED', key); time.sleep(5)
        with (OUT/f'serial-{key}.log').open('a', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-u', str(ROOT/script), *map(str, args)],
                           cwd=ROOT, stdout=log, stderr=log, check=True)

    key = None
    try:
        for key in ORDER:
            queue = read(ROOT/'data/video-production-queue.json')
            episode = next(e for e in queue['episodes'] if e['key'] == key)
            if episode.get('status') == 'complete':
                continue
            while paused():
                save('PAUSED', key); time.sleep(5)
            module_name = 'produce_' + key.replace('-', '_') + '_videos'
            module = importlib.import_module(module_name)
            batch = LAB/f'youtube-batch-{key}/manifest.json'
            if key == 'missionary':
                qa = read(LAB/'missionary-video-production/full-visual-qa.json')
                video = Path(qa['video'])
                assert qa['status'] == 'passed' and video.stat().st_size == qa['videoBytes']
                assert video.stat().st_mtime_ns == qa['videoMtimeNs']
                batch = module.prepare_uploads()
            else:
                capture = LAB/f'campaigns/{key}-all-unique/status.json'
                while read(capture).get('state') != 'COMPLETE':
                    save('WAITING_FOR_PRIORITY_RETAKES', key); time.sleep(30)
                overlays = LAB/f'campaigns/{key}-all-unique-overlays'
                save('OVERLAYS', key)
                call(key, 'apps/video/render_campaign_overlays.py', '--manifest',
                     ROOT/f'aoe2lab.recorder.{key}-all-unique.toml', '--output', overlays,
                     '--workers', '2', '--recording-status', capture)
                assert read(overlays/'status.json')['state'] == 'COMPLETE', 'Review failed overlays'
                save('BUILDING_VIDEO_AND_SHORTS', key)
                call(key, f'apps/video/{module_name}.py')
                save('WAITING_FOR_VISUAL_QA', key)
                while read(LAB/f'{key}-video-production/visual-qa.json').get('status') != 'passed':
                    time.sleep(30)
            save('UPLOADING', key)
            call(key, 'apps/video/upload_youtube_batch.py', batch)
            call(key, 'apps/video/check_youtube_batch.py', batch)
            assert verified(read(batch.parent/'verification.json')), 'Upload verification incomplete'
            save('CLEANUP', key)
            cleanup(key, batch)
            queue = read(ROOT/'data/video-production-queue.json')
            episode = next(e for e in queue['episodes'] if e['key'] == key)
            episode.update(status='complete', completedAt=utc_now(), verifiedYouTubeVideos=11)
            write_json(ROOT/'data/video-production-queue.json', queue)
            write_json(LAB/f'{key}-video-production/status.json',
                       {'state': 'COMPLETE', 'completedAt': utc_now(), 'uploadManifest': str(batch)})
        save('COMPLETE', None)
    except Exception as error:
        save('NEEDS_ATTENTION', key, error=repr(error))
        raise


if __name__ == '__main__':
    main()
