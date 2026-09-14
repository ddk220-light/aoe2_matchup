"""Explicitly approved private upload, resumable transfer, and thumbnail install.

Credentials and resumable session URLs are DPAPI encrypted in ignored local state.
Reruns resume the same upload and never create another video after receiving its ID.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import http.client
import json
import re
from pathlib import Path
import time
from urllib.parse import urlencode, urlparse
from authorize_youtube import protect


def unprotect(data):
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, output = Blob(len(data), buf), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel = ctypes.WinDLL('kernel32')
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def transport(url, method='GET', body=None, headers=None):
    u = urlparse(url)
    if u.scheme != 'https' or u.hostname not in ('www.googleapis.com', 'oauth2.googleapis.com'):
        raise ValueError('Unexpected Google API destination')
    conn = http.client.HTTPSConnection(u.hostname, timeout=60)
    try:
        conn.request(method, u.path + ('?' + u.query if u.query else ''), body=body, headers=headers or {})
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    finally:
        conn.close()


class API:
    def __init__(self, directory):
        self.path = directory / 'tokens.dpapi'
        self.token = json.loads(unprotect(self.path.read_bytes()))

    def request(self, url, method='GET', body=None, headers=None):
        if time.time() > self.token['obtained_at'] + self.token.get('expires_in', 3600) - 120:
            config = json.loads(Path(self.token['client_file']).read_text())['installed']
            data = urlencode({'client_id': config['client_id'], 'client_secret': config['client_secret'],
                'refresh_token': self.token['refresh_token'], 'grant_type': 'refresh_token'}).encode()
            code, _, content = transport('https://oauth2.googleapis.com/token', 'POST', data,
                {'Content-Type': 'application/x-www-form-urlencoded'})
            if code != 200:
                raise RuntimeError(f'Token refresh HTTP {code}')
            self.token.update(json.loads(content)); self.token['obtained_at'] = time.time()
            tmp = self.path.with_suffix('.dpapi.tmp'); tmp.write_bytes(protect(json.dumps(self.token).encode())); tmp.replace(self.path)
        return transport(url, method, body, {**(headers or {}), 'Authorization': 'Bearer ' + self.token['access_token']})


def require(code, body):
    if code not in (200, 201):
        try:
            error = json.loads(body).get('error', {})
            reasons = [e.get('reason') for e in error.get('errors', [])]
        except Exception:
            reasons = []
        raise RuntimeError(f'YouTube API HTTP {code}; reasons={reasons}')
    return json.loads(body) if body else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--credentials', type=Path, default=Path('data/local/youtube'))
    parser.add_argument('--state-key', default='tiger', help='Unique local upload identity; reuse it to resume the same video')
    parser.add_argument('--processing-wait-seconds', type=int, default=900)
    args = parser.parse_args()
    queue_path = Path(__file__).resolve().parents[2] / 'data/video-production-queue.json'
    if queue_path.exists():
        queue = json.loads(queue_path.read_text(encoding='utf-8'))
        approved_paths = queue.get('correctedMedia', {}).get('approvedUploadPreparations', [])
        specifically_approved = str(args.preparation.resolve()).casefold() in {str(Path(p).resolve()).casefold() for p in approved_paths}
        if queue.get('userPause', {}).get('state') == 'PAUSED' or (queue.get('costBasisReview', {}).get('state') == 'REQUIRED_BEFORE_PENDING_UPLOADS' and not specifically_approved):
            raise RuntimeError('Production paused or cost audit unresolved: upload blocked before API access')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', args.state_key):
        parser.error('--state-key must contain only lowercase letters, digits, underscores or hyphens')
    prep = json.loads(args.preparation.read_text(encoding='utf-8')); base = args.preparation.parent
    settings = json.loads((base / 'youtube-proposed-settings.json').read_text(encoding='utf-8'))
    assert prep['uploadAuthorized'] and settings['uploadAuthorized']
    assert prep['targetChannelVerified'] and settings['privacyStatus'] == 'private'
    video, thumb = Path(prep['video']), Path(settings['thumbnail'])
    description = Path(settings['descriptionFile']).read_text(encoding='utf-8')
    assert len(description) <= 5000 and thumb.stat().st_size < 2 * 1024 * 1024
    total = video.stat().st_size
    state_path = args.credentials / f'{args.state_key}-upload-status.json'
    session_path = args.credentials / f'{args.state_key}-upload-session.dpapi'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    api = API(args.credentials)
    code, _, body = api.request('https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true')
    channels = require(code, body)['items']
    expected = prep['targetChannel']['id']
    assert any(c['id'] == expected and c['snippet'].get('customUrl', '').lower() == '@aoe2matchup' for c in channels), 'Wrong authorized channel'
    metadata = {'snippet': {k: settings[k] for k in ('title', 'tags', 'categoryId', 'defaultLanguage', 'defaultAudioLanguage')},
        'status': {k: settings[k] for k in ('privacyStatus', 'selfDeclaredMadeForKids', 'containsSyntheticMedia', 'license', 'embeddable')}}
    metadata['snippet']['description'] = description
    identity = hashlib.sha256(json.dumps({'path': str(video), 'bytes': total, 'mtime': video.stat().st_mtime_ns,
        'metadata': metadata, 'channel': expected}, sort_keys=True).encode()).hexdigest()
    assert not state or state.get('identity') == identity, 'Existing upload belongs to different input/settings'

    def update(**values):
        state.update(identity=identity, channelId=expected, title=settings['title'], totalBytes=total,
            updatedAt=time.time(), **values)
        write(state_path, state)

    def completed(content):
        result = json.loads(content)
        assert result.get('id') and result['snippet']['channelId'] == expected
        update(state='UPLOADED', videoId=result['id'], videoUrl='https://www.youtube.com/watch?v=' + result['id'], uploadedBytes=total, percent=100)
        write(base / 'youtube-upload-response.json', result)

    try:
        if not state.get('videoId'):
            if session_path.exists():
                session = json.loads(unprotect(session_path.read_bytes()))
                assert session['identity'] == identity
                url = session['url']
            else:
                assert state.get('state') != 'STARTING_SESSION', 'Previous session creation was interrupted; inspect before retrying'
                update(state='STARTING_SESSION', uploadedBytes=0)
                code, headers, body = api.request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status&notifySubscribers=false',
                    'POST', json.dumps(metadata).encode(), {'Content-Type': 'application/json; charset=UTF-8',
                    'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(total)})
                require(code, body)
                url = headers['location']
                session_path.write_bytes(protect(json.dumps({'url': url, 'identity': identity}).encode()))

            def progress_query():
                code, headers, body = api.request(url, 'PUT', b'', {'Content-Length': '0', 'Content-Range': f'bytes */{total}'})
                if code in (200, 201):
                    completed(body); return total
                if code != 308:
                    require(code, body)
                return int(headers['range'].split('-')[-1]) + 1 if 'range' in headers else 0

            offset = progress_query()
            with video.open('rb') as source:
                failures = 0
                while offset < total:
                    source.seek(offset); chunk = source.read(16 * 1024 * 1024)
                    try:
                        code, headers, body = api.request(url, 'PUT', chunk, {'Content-Type': 'video/mp4',
                            'Content-Length': str(len(chunk)), 'Content-Range': f'bytes {offset}-{offset+len(chunk)-1}/{total}'})
                        if code in (200, 201):
                            completed(body); offset = total
                        elif code == 308:
                            new_offset = int(headers['range'].split('-')[-1]) + 1
                            if new_offset <= offset:
                                raise OSError('Upload did not advance')
                            offset = new_offset; update(state='UPLOADING', uploadedBytes=offset, percent=round(100*offset/total,1))
                        elif code in (500, 502, 503, 504):
                            raise OSError('Transient upload error')
                        else:
                            require(code, body)
                        failures = 0
                    except (OSError, http.client.HTTPException):
                        failures += 1
                        if failures > 5:
                            raise RuntimeError('Upload interrupted; rerun to resume this session')
                        time.sleep(min(2**failures, 30)); offset = progress_query()

        video_id = state['videoId']
        if not state.get('thumbnailSet'):
            code, _, body = api.request('https://www.googleapis.com/upload/youtube/v3/thumbnails/set?' + urlencode({'videoId': video_id, 'uploadType': 'media'}),
                'POST', thumb.read_bytes(), {'Content-Type': 'image/jpeg'})
            result = require(code, body)
            write(base / 'youtube-thumbnail-response.json', result); update(state='PROCESSING', thumbnailSet=True)
        deadline = time.time() + max(0, args.processing_wait_seconds)
        while True:
            code, _, body = api.request('https://www.googleapis.com/youtube/v3/videos?' + urlencode({'part': 'snippet,status,processingDetails,contentDetails', 'id': video_id}))
            result = require(code, body); item = result['items'][0]
            assert item['snippet']['channelId'] == expected
            # Preserve visibility changes made by the owner in Studio after upload.
            write(base / 'youtube-video-status.json', item)
            processing = item.get('processingDetails', {}).get('processingStatus')
            phase = 'COMPLETE' if processing == 'succeeded' else ('NEEDS_ATTENTION' if processing in ('failed', 'terminated') else 'PROCESSING')
            update(state=phase, processingStatus=processing,
                privacyStatus=item['status']['privacyStatus'])
            if processing in ('succeeded', 'failed', 'terminated') or time.time() >= deadline:
                break
            time.sleep(20)
        print(json.dumps(state), flush=True)
    except Exception as exc:
        update(state='NEEDS_ATTENTION', errorType=type(exc).__name__, error=str(exc) if isinstance(exc, (RuntimeError, AssertionError)) else 'Network or local operation failed; sensitive details suppressed')
        print(json.dumps(state), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
