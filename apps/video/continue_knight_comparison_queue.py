"""Finish the two authorized episodes with the reviewed short narrations.

Heavy episode processing stays sequential. Narration uses the saved authorized
voice and cached responses; the API key is decrypted only inside this process.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from build_knight_comparison_series import REPO, read, save

STATE = REPO / 'data/local/knight-comparison-production-queue.json'


def state(phase, **details):
    save(STATE, dict(state=phase, pid=os.getpid(), updatedAt=time.time(), **details))


def run(script, *args):
    subprocess.run([sys.executable, '-u', str(REPO / 'apps/video' / script),
                    *map(str, args)], check=True, cwd=REPO)


def intro_and_upload(unit, voice_file, render=False):
    plan = REPO / f'apps/video/intro/{unit}-comparison.json'
    intro = REPO / f'data/local/{unit}-comparison-intro'
    series = REPO / f'data/local/{unit}-comparison-full'
    approved = read(intro / 'approved-narration-update.json')
    if not approved.get('approved') or approved.get('uploadPrivacy') != 'private':
        raise ValueError('Expected approved narration and private upload')
    profile = read(plan)
    profile['page2Narration'] = approved['page2Narration']
    save(plan, profile)
    state(unit.upper() + '_NARRATION')
    from upload_youtube import unprotect
    from generate_intro_narration import generate
    voice = read(plan.parent / voice_file)
    if voice.get('retired'):
        raise ValueError('Cavalier narration voice has been retired')
    os.environ['ELEVENLABS_API_KEY'] = unprotect(
        (REPO / 'data/local/elevenlabs.dpapi').read_bytes()).decode().strip()
    try:
        for page in ('opening', 'observations'):
            generate(plan.with_name(f'{unit}-comparison-{page}.json'),
                     intro / f'narration-{page}', voice['voice_id'], 'instant_clone')
    finally:
        os.environ.pop('ELEVENLABS_API_KEY', None)

    state(unit.upper() + '_INTRO')
    run('build_champi_comparison_intro.py', '--plan', plan, '--output', intro)
    run('build_champi_comparison_bookends.py', '--plan', plan, '--output', intro,
        '--series-dir', series, '--defer-assembly',
        '--narration-plan', plan.with_name(f'{unit}-comparison-opening-cloned.json'),
        '--page-two-narration-plan', plan.with_name(f'{unit}-comparison-observations-cloned.json'))
    (intro / 'narration-review-pending.json').unlink(missing_ok=True)
    if render:
        state(unit.upper() + '_OVERLAYS')
        run('build_knight_comparison_series.py', '--plan', plan, '--output', series)
    state(unit.upper() + '_ASSEMBLY_AND_UPLOAD')
    run('finish_knight_comparison.py', unit)
    return read(series / 'production-status.json')


def main():
    previous = REPO / 'data/local/paladin-comparison-full/status.json'
    deadline = time.monotonic() + 12 * 3600
    state('WAITING_FOR_PALADIN_RENDER')
    while True:
        status = read(previous) if previous.exists() else {}
        if status.get('state') == 'NEEDS_ATTENTION':
            raise RuntimeError('Paladin needs attention: ' + status.get('error', 'unknown'))
        if status.get('state') == 'COMPLETE':
            break
        if time.monotonic() > deadline:
            raise TimeoutError('Paladin render did not finish within 12 hours')
        time.sleep(30)
    # Updating the intro profile only after the active render finishes preserves
    # that renderer's existing checkpoint signatures and avoids redundant work.
    paladin = intro_and_upload('paladin', 'joan-voice-clone.json')
    cavalier = intro_and_upload('cavalier', 'ivaylo-voice-clone.json', render=True)
    state('UPLOADS_RETURNED', paladin=paladin, cavalier=cavalier)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        state('NEEDS_ATTENTION', error=str(error))
        raise
