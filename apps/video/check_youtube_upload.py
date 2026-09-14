"""Refresh processing status without uploading or changing remote settings."""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from upload_youtube import API, require, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--credentials', type=Path, default=Path('data/local/youtube'))
    args = parser.parse_args()
    state = json.loads(args.state.read_text(encoding='utf-8'))
    prep = json.loads(args.preparation.read_text(encoding='utf-8'))
    api = API(args.credentials)
    query = urlencode({'part': 'status,processingDetails,contentDetails,fileDetails,suggestions,snippet', 'id': state['videoId']})
    code, _, body = api.request('https://www.googleapis.com/youtube/v3/videos?' + query)
    item = require(code, body)['items'][0]
    assert item['snippet']['channelId'] == prep['targetChannel']['id']
    processing = item.get('processingDetails', {}).get('processingStatus')
    phase = 'COMPLETE' if processing == 'succeeded' else ('NEEDS_ATTENTION' if processing in ('failed', 'terminated') else 'PROCESSING')
    state.update(state=phase, processingStatus=processing, privacyStatus=item['status']['privacyStatus'], updatedAt=time.time())
    state.pop('error', None)
    state.pop('errorType', None)
    write(args.state, state)
    write(args.preparation.parent / 'youtube-video-status.json', item)
    prep.update(state='processing_complete' if processing == 'succeeded' else 'uploaded_processing', processingStatus=processing, privacyStatus=item['status']['privacyStatus'])
    write(args.preparation, prep)
    print(json.dumps({k: state.get(k) for k in ('videoId', 'videoUrl', 'state', 'processingStatus', 'privacyStatus')}))


if __name__ == '__main__':
    main()
