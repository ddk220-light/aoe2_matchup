"""Upload an explicitly approved manifest; preserve one resumable identity per file."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import html
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode

from upload_youtube import API, require, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    queue_path = Path(__file__).resolve().parents[2] / 'data/video-production-queue.json'
    if queue_path.exists():
        queue = json.loads(queue_path.read_text(encoding='utf-8'))
        if queue.get('userPause', {}).get('state') == 'PAUSED' or queue.get('costBasisReview', {}).get('state') == 'REQUIRED_BEFORE_PENDING_UPLOADS':
            raise RuntimeError('Production is paused or cost audit unresolved; uploads are blocked before API access')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    assert manifest['authorized']
    directory = args.manifest.parent
    credentials = Path('data/local/youtube')
    api = API(credentials)
    code, _, body = api.request('https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true')
    assert any(x['id'] == manifest['targetChannel']['id'] for x in require(code, body)['items'])
    stop = threading.Event()
    state = {'state': 'RUNNING', 'total': len(manifest['items']), 'items': []}

    def report():
        state['updatedAt'] = time.time()
        state['uploaded'] = sum(bool(x.get('videoId')) for x in state['items'])
        state['processed'] = sum(x.get('processingStatus') == 'succeeded' for x in state['items'])
        write(directory / 'status.json', state)
        rows = []
        for item in state['items']:
            url = ('https://www.youtube.com/shorts/' if item['kind'] == 'short' else 'https://www.youtube.com/watch?v=') + item['videoId'] if item.get('videoId') else ''
            title = html.escape(item['title'])
            rows.append('<tr><td>' + (f'<a href="{url}">{title}</a>' if url else title) + '</td><td>' + html.escape(item.get('state', 'QUEUED')) + '</td><td>' + html.escape(item.get('privacyStatus', '')) + '</td></tr>')
        (directory / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>YouTube upload batch</title><style>body{font:17px system-ui;margin:40px;background:#f6f0e4;color:#29231c}td,th{padding:12px;border-bottom:1px solid #c6baa5;text-align:left}a{color:#745019}</style><h1>' + html.escape(manifest.get('title', 'Tiger Cavalry and Xianbei Raider uploads')) + '</h1><p>' + str(state['uploaded']) + '/' + str(state['total']) + ' uploaded; ' + str(state['processed']) + ' processed.</p><table><tr><th>Video</th><th>Status</th><th>Visibility</th></tr>' + ''.join(rows) + '</table>', encoding='utf-8')

    def upload(item):
        if stop.is_set():
            return {'state': 'PAUSED_AFTER_QUOTA'}
        log = directory / (item['key'] + '.log')
        with log.open('a', encoding='utf-8') as target:
            result = subprocess.run([sys.executable, '-u', 'apps/video/upload_youtube.py', '--preparation', item['preparation'], '--state-key', item['key'], '--processing-wait-seconds', '0'], stdout=target, stderr=subprocess.STDOUT)
        path = credentials / (item['key'] + '-upload-status.json')
        current = json.loads(path.read_text()) if path.exists() else {'state': 'NEEDS_ATTENTION', 'error': 'See local upload log'}
        if result.returncode and any(reason in current.get('error', '') for reason in ('quotaExceeded', 'uploadLimitExceeded', 'dailyLimitExceeded')):
            stop.set()
        return current

    # One full-video transfer can overlap the serial Shorts lane.
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(upload, item): item for item in manifest['items']}
        while jobs:
            for future, item in list(jobs.items()):
                if future.done():
                    item.update(future.result())
                    del jobs[future]
            state['items'] = []
            for item in manifest['items']:
                path = credentials / (item['key'] + '-upload-status.json')
                if path.exists():
                    item.update(json.loads(path.read_text()))
                state['items'].append(dict(item))
            report()
            if jobs:
                time.sleep(5)
    # Poll all completed transfers together, retaining visibility changes from Studio.
    deadline = time.time() + 7200
    while time.time() < deadline:
        ids = [x['videoId'] for x in state['items'] if x.get('videoId') and x.get('processingStatus') not in ('succeeded', 'failed', 'terminated')]
        if not ids:
            break
        code, _, body = api.request('https://www.googleapis.com/youtube/v3/videos?' + urlencode({'part': 'snippet,status,processingDetails,contentDetails', 'id': ','.join(ids)}))
        for remote in require(code, body)['items']:
            assert remote['snippet']['channelId'] == manifest['targetChannel']['id']
            item = next(x for x in state['items'] if x.get('videoId') == remote['id'])
            processing = remote.get('processingDetails', {}).get('processingStatus')
            item.update(processingStatus=processing, privacyStatus=remote['status']['privacyStatus'], state='COMPLETE' if processing == 'succeeded' else ('NEEDS_ATTENTION' if processing in ('failed', 'terminated') else 'PROCESSING'))
            write(credentials / (item['key'] + '-upload-status.json'), item)
            base = Path(item['preparation']).parent
            write(base / 'youtube-video-status.json', remote)
            prep = json.loads(Path(item['preparation']).read_text())
            prep.update(videoId=item['videoId'], videoUrl=item['videoUrl'], processingStatus=processing, state=item['state'], privacyStatus=item['privacyStatus'])
            write(Path(item['preparation']), prep)
        state['state'] = 'PROCESSING'
        report()
        time.sleep(30)
    state['state'] = 'COMPLETE' if all(x.get('processingStatus') == 'succeeded' and x.get('thumbnailSet') for x in state['items']) else 'NEEDS_ATTENTION'
    report()
    print(json.dumps({'state': state['state'], 'uploaded': state['uploaded'], 'processed': state['processed'], 'report': str(directory / 'index.html')}), flush=True)


if __name__ == '__main__':
    main()
