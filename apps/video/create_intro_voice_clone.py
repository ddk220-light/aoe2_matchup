"""Create an authorized campaign instant voice clone in ElevenLabs.

Only run with permission to upload and clone the supplied speaker recording.
The API key is read from the environment and is never written to disk.
"""
import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def create(sample, output, campaign='Wei', source_event='PLAY_WEI1S1', source_media_id=513736269):
    sample, output = Path(sample), Path(output)
    data = sample.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if output.exists():
        cached = json.loads(output.read_text())
        # A deleted cloud profile can still have matching, preserved local audio.
        # Its provenance is an archive, not a usable voice for new narration.
        if cached.get('retired'):
            raise ValueError('Voice profile is retired; select an active authorized voice or create new metadata')
        if cached.get('sampleSha256') == digest and cached.get('voice_id'):
            print(json.dumps(cached))
            return
        raise ValueError('Existing clone metadata differs; review before creating another voice')
    boundary = uuid.uuid4().hex
    fields = {'name': f'{campaign} campaign narrator - authorized clone',
              'description': f'Clone of extracted {campaign} campaign narration. User confirmed permission from narrator or rights holder.',
              'remove_background_noise': 'false'}
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="campaign.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    parts += [data, f'\r\n--{boundary}--\r\n'.encode()]
    req = urllib.request.Request('https://api.elevenlabs.io/v1/voices/add',
        data=b''.join(parts), headers={'xi-api-key': os.environ['ELEVENLABS_API_KEY'],
                                     'Content-Type': 'multipart/form-data; boundary='+boundary})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'ElevenLabs HTTP {error.code}: {error.read().decode()}') from None
    result.update({'sample': str(sample.resolve()), 'sampleSha256': digest,
                   'permission': 'User explicitly confirmed permission to clone the campaign narrator',
                   'campaign': campaign, 'sourceEvent': source_event, 'sourceMediaId': source_media_id,
                   'provider': 'ElevenLabs', 'method': 'Instant Voice Cloning'})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--sample', default='.tools/intro-voice/wei.wav')
    p.add_argument('--output', default='apps/video/intro/wei-voice-clone.json')
    p.add_argument('--campaign', default='Wei')
    p.add_argument('--source-event', default='PLAY_WEI1S1')
    p.add_argument('--source-media-id', type=int, default=513736269)
    a = p.parse_args()
    create(a.sample, a.output, a.campaign, a.source_event, a.source_media_id)
