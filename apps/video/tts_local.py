"""Local neural narration: render a JSON list of {"text", "path"} lines to WAV files.

Runs inside the separate TTS virtualenv (it needs torch + kokoro or chatterbox-tts), not the
video venv:  <tts-venv>/python tts_local.py <spec.json> kokoro:bm_george
             <tts-venv>/python tts_local.py <spec.json> chatterbox[:reference.wav][@exaggeration,cfg]
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

GAP = .3  # seconds of silence between sentences


def kokoro(lines, voice):
    from kokoro import KPipeline
    pipe = KPipeline(lang_code=voice[0], repo_id='hexgrad/Kokoro-82M')
    for text, path in lines:
        parts = []
        for _, _, audio in pipe(text, voice=voice, speed=1.0):
            parts += [audio.numpy(), np.zeros(int(24000 * GAP), dtype=np.float32)]
        sf.write(path, np.concatenate(parts[:-1]), 24000)


def chatterbox(lines, arg):
    """arg = [reference.wav][@exaggeration,cfg]. Exaggeration ~0.5 is neutral, 0.8+ more emotive
    (above ~1.2 it gets unstable); a lower cfg (0.3) keeps the pace natural at high exaggeration."""
    import torch
    from chatterbox.tts import ChatterboxTTS
    reference, _, knobs = arg.partition('@')
    exaggeration, cfg = (float(x) for x in knobs.split(',')) if knobs else (.5, .5)
    model = ChatterboxTTS.from_pretrained(device='cuda' if torch.cuda.is_available() else 'cpu')
    extra = {'audio_prompt_path': reference} if reference else {}
    for text, path in lines:
        torch.manual_seed(7)
        parts = []
        for sentence in (s for s in re.split(r'(?<=[.!?:])\s+', text) if s.strip()):
            wav = model.generate(sentence, exaggeration=exaggeration, cfg_weight=cfg,
                                 **extra).squeeze(0).cpu().numpy()
            parts += [wav, np.zeros(int(model.sr * GAP), dtype=np.float32)]
        sf.write(path, np.concatenate(parts[:-1]), model.sr)


def main():
    spec, engine = sys.argv[1], sys.argv[2]
    lines = [(j['text'], j['path']) for j in json.loads(Path(spec).read_text(encoding='utf-8'))]
    name, _, arg = engine.partition(':')
    {'kokoro': kokoro, 'chatterbox': chatterbox}[name](lines, arg or ('am_michael' if name == 'kokoro' else ''))
    print(len(lines), 'lines voiced with', engine)


if __name__ == '__main__':
    main()
