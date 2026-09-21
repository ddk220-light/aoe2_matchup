"""Generate per-page ElevenLabs narration and character alignment.

Only the original intro text is submitted. Supply ELEVENLABS_API_KEY through the
process environment; credentials are never stored in the plan or output files.
"""
import argparse
import base64
import json
import math
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from overlay.ffutil import find_ffmpeg, find_ffprobe


def generate(plan_path, output, voice_id, voice_kind='library'):
    key = os.environ.get('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError('Set ELEVENLABS_API_KEY in the process environment')
    ff, probe = find_ffmpeg(), find_ffprobe()
    if not ff or not probe:
        raise FileNotFoundError('FFmpeg and FFprobe must be accessible')
    plan_path = Path(plan_path).resolve()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = json.loads(plan_path.read_text())
    settings = {'stability': .65, 'similarity_boost': .75,
                'style': .15, 'use_speaker_boost': True, 'speed': .90}
    clips = []
    for i, slide in enumerate(plan['slides'], 1):
        text = '\n\n'.join(slide['paragraphs'])
        payload = {'text': text, 'model_id': 'eleven_multilingual_v2',
                   'voice_settings': settings}
        audio_path = output / f'narration-{i:02}.mp3'
        timing_path = output / f'narration-{i:02}.json'
        # Reuse a successful identical request, avoiding duplicate paid calls.
        cached = json.loads(timing_path.read_text()) if timing_path.exists() else None
        if not (audio_path.exists() and cached and cached.get('request') == payload
                and cached.get('voiceId') == voice_id):
            req = urllib.request.Request(
                f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128',
                data=json.dumps(payload).encode(),
                headers={'xi-api-key': key, 'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=120) as response:
                    result = json.load(response)
            except urllib.error.HTTPError as error:
                raise RuntimeError(f'ElevenLabs HTTP {error.code}: {error.read().decode()}') from None
            audio_path.write_bytes(base64.b64decode(result.pop('audio_base64')))
            result.update({'voiceId': voice_id, 'request': payload})
            timing_path.write_text(json.dumps(result, indent=2))
        result = json.loads(timing_path.read_text())
        alignment = result['alignment']
        if ''.join(alignment['characters']) != text:
            raise ValueError('Alignment text differs from requested script; review before rendering')
        seconds = float(subprocess.check_output([probe, '-v', 'error', '-show_entries',
                        'format=duration', '-of', 'default=nw=1:nk=1', str(audio_path)]))
        lead = float(slide.get('narrationLeadSeconds', .4))
        hold = float(slide.get('narrationHoldSeconds', 2))
        if lead < 0 or hold < 0:
            raise ValueError('Narration lead and hold must be nonnegative')
        slide['duration'] = math.ceil((seconds + lead + hold) * 30) / 30
        slide['narrationAlignment'] = str(timing_path)
        slide['narrationLeadSeconds'] = lead
        slide['narrationHoldSeconds'] = hold
        slide['speechDurationSeconds'] = seconds
        padded = output / f'narration-{i:02}-padded.wav'
        subprocess.run([ff, '-y', '-v', 'error', '-i', str(audio_path),
                        '-af', f'adelay={round(lead*1000)}:all=1,apad', '-t', str(slide['duration']),
                        '-ar', '48000', '-ac', '2', str(padded)], check=True)
        clips.append(padded)
        print(f'Page {i}: {seconds:.2f}s speech; {slide["duration"]:.2f}s page', flush=True)
    listing = output / 'narration-concat.txt'
    listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
    full_audio = output / 'narration.wav'
    subprocess.run([ff, '-y', '-v', 'error', '-f', 'concat', '-safe', '0',
                    '-i', str(listing), '-c:a', 'pcm_s16le', str(full_audio)], check=True)
    plan['narration'] = {'file': str(full_audio), 'voiceId': voice_id,
                         'provider': 'ElevenLabs', 'model': 'eleven_multilingual_v2',
                         'settings': settings, 'identity': (plan.get('voiceSelection', 'instant voice clone from Wei campaign reference; user confirmed permission') if voice_kind=='instant_clone' else 'licensed library voice, not original actor')}
    # Keep the generated plan beside the base plan so art/catalog paths still work.
    final_plan = plan_path.with_name(plan_path.stem + ('-cloned.json' if voice_kind=='instant_clone' else '-narrated.json'))
    final_plan.write_text(json.dumps(plan, indent=2))
    print(final_plan)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--plan', default='apps/video/intro/tiger-cavalry.json')
    p.add_argument('--output', default='aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/intro-v3')
    p.add_argument('--voice-id', required=True)
    p.add_argument('--voice-kind', choices=['library','instant_clone'], default='library')
    a = p.parse_args()
    generate(a.plan, a.output, a.voice_id, a.voice_kind)
