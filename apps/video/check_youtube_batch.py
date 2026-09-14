"""Verify an upload batch against local metadata, without changing YouTube."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from upload_youtube import API, require, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    creds = Path('data/local/youtube')
    local = {}
    for item in manifest['items']:
        path = creds / (item['key'] + '-upload-status.json')
        if path.exists():
            state = json.loads(path.read_text())
            if state.get('videoId'):
                local[state['videoId']] = (item, state, path)
    api = API(creds)
    code, _, body = api.request('https://www.googleapis.com/youtube/v3/videos?' + urlencode({'part': 'snippet,status,processingDetails,contentDetails', 'id': ','.join(local)}))
    rows = []
    for remote in require(code, body)['items']:
        item, state, path = local[remote['id']]
        base = Path(item['preparation']).parent
        settings = json.loads((base / 'youtube-proposed-settings.json').read_text(encoding='utf-8'))
        description = Path(settings['descriptionFile']).read_text(encoding='utf-8')
        processing = remote.get('processingDetails', {}).get('processingStatus')
        row = {'key': item['key'], 'videoId': remote['id'], 'processing': processing,
               'thumbnail': remote['contentDetails'].get('hasCustomThumbnail'),
               'privacy': remote['status']['privacyStatus'],
               'channelMatches': remote['snippet']['channelId'] == manifest['targetChannel']['id'],
               'titleMatches': remote['snippet']['title'] == settings['title'],
               'descriptionMatches': remote['snippet']['description'].strip() == description.strip()}
        rows.append(row)
        assert row['channelMatches'], 'Wrong target channel'
        state.update(processingStatus=processing, privacyStatus=row['privacy'])
        if processing == 'succeeded' and state.get('thumbnailSet'):
            state['state'] = 'COMPLETE'
        write(path, state)
        write(base / 'youtube-video-status.json', remote)
    write(args.manifest.parent / 'verification.json', rows)
    print(json.dumps({'verified': len(rows), 'processed': sum(r['processing'] == 'succeeded' for r in rows),
                      'metadataProblems': [r for r in rows if not all(r[k] for k in ('thumbnail', 'channelMatches', 'titleMatches', 'descriptionMatches'))]}))


if __name__ == '__main__':
    main()
