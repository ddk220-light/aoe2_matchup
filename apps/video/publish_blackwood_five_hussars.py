"""Upload the reviewed revision after Obuch, retaining the original title/video.

The September 13 request authorizes a separate private upload. Reuse this state
key to resume it; never reuse the original Blackwood upload session or video ID.
"""
import argparse
import hashlib
import time
from pathlib import Path
from urllib.parse import urlencode

import finish_pending_production as production
from upload_youtube import API, require

ROOT, LAB = production.ROOT, production.LAB
COMP = LAB / 'compilations/blackwood-archer-five-hussars'
OUT = COMP / 'final'
STATE_KEY = 'blackwood-archer-full-five-hussars-v1'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upload-authorized', action='store_true')
    args = p.parse_args()
    if not args.upload_authorized:
        p.error('Explicit upload authorization is required')
    obuch = production.read(LAB / 'compilations/elite-obuch-unique-units/upload-completion.json')
    assert obuch['state'] == 'COMPLETE' and obuch['completed'] == 11, 'Finish earlier Obuch uploads first'
    master = production.read(OUT / 'manifest.json')
    qa = production.read(OUT / 'visual-qa.json')
    video = Path(master['output'])
    with video.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert master['fullDecode'] == 'passed' and master['matchups'] == 73
    assert qa['passed'] and qa['fullVideoSha256'] == sha == master['videoSha256']
    original = production.read(ROOT / 'data/local/youtube/blackwood-archer-full-upload-status.json')
    api = API(ROOT / 'data/local/youtube')
    code, _, body = api.request('https://www.googleapis.com/youtube/v3/videos?' + urlencode(
        dict(part='snippet', id=original['videoId'])))
    old = require(code, body)['items']
    assert len(old) == 1 and old[0]['snippet']['channelId'] == 'UCKYN-pN4AZ3w4LpRxcdSciA'
    title = old[0]['snippet']['title']
    thumb = Path(production.read(Path(original['preparation']).parent / 'youtube-proposed-settings.json')['thumbnail'])
    item = production.prepare('blackwood-archer-five-hussars', 'Elite Blackwood Archer', 'Tupi',
        'elite_blackwood_archer_tupi', video, OUT / 'youtube-description-draft.txt', thumb,
        OUT / 'youtube', STATE_KEY, title, True)
    production.write(COMP / 'upload-manifest.json', dict(items=[item], originalVideoId=original['videoId'],
        titlePolicy='Same title as original; separate private upload; owner chooses any later replacement.'))
    production.run('upload_youtube.py', '--preparation', item['preparation'], '--state-key', STATE_KEY,
                   '--processing-wait-seconds', '0')
    state_path = ROOT / f'data/local/youtube/{STATE_KEY}-upload-status.json'
    saved = production.read(state_path)
    assert saved['state'] in ('COMPLETE', 'PROCESSING') and saved['videoId'] != original['videoId']
    deadline = time.time() + 3600
    while True:
        production.pause_check()
        code, _, body = api.request('https://www.googleapis.com/youtube/v3/videos?' + urlencode(
            dict(part='snippet,status,processingDetails,contentDetails', id=saved['videoId'])))
        remote = require(code, body)['items']
        assert len(remote) == 1 and remote[0]['snippet']['channelId'] == 'UCKYN-pN4AZ3w4LpRxcdSciA'
        phase = remote[0].get('processingDetails', {}).get('processingStatus')
        assert phase not in ('failed', 'terminated'), 'YouTube processing failed'
        saved.update(state='COMPLETE' if phase == 'succeeded' else 'PROCESSING', processingStatus=phase,
                     privacyStatus=remote[0]['status']['privacyStatus'])
        production.write(state_path, saved)
        production.write(OUT / 'youtube/youtube-video-status.json', remote[0])
        production.write(COMP / 'upload-completion.json', dict(state=saved['state'],
            completed=int(phase == 'succeeded'), total=1, videos=[saved], originalVideoId=original['videoId']))
        print(saved['state'], saved['videoId'], flush=True)
        if phase == 'succeeded':
            return
        assert time.time() < deadline, 'Check YouTube processing later; keep the existing upload ID'
        time.sleep(30)


if __name__ == '__main__':
    main()
