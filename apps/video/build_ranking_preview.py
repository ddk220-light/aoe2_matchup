"""Preview cuts of a ranking video with one of the live-ranking overlay concepts (A/B/C).

Each selected battle becomes: title card -> narrated opening -> the last seconds of the
battle -> frozen final frame under the ranking beat (with the result line). Then the
finale board. Narration uses the local Windows voice as a placeholder (no network).

    python apps/video/build_ranking_preview.py --facts <ranking_facts.json> --video imperial \
        --script <script-imperial.json> --picks Bengalis Saracens Wei --concepts A B C --out <dir>
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from multiprocessing import Pool
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

from build_spike_episode import probe, title_card
from overlay.battle_end import terminal_row
from overlay.civ_theme import theme_for
from overlay.ffutil import find_ffmpeg
from overlay.static_stats import GAME, portrait_path
import ranking_overlay as ro

FPS = 60
CARD, TAIL, BEAT = 2.2, 5.0, 4.6
XF_IN, XF_CARD, XF_CUT = .7, .5, .4   # dissolves: previous segment -> card, card -> battle, mid-battle skip
_C = None
FADE = {'BannerRow': 17.0, 'ScrollOfHonour': 19.0, 'BattleLine': 18.0, 'LadderThenLine': 18.0}
INTRO_CARD, MONTAGE_CLIP = 3.0, 4.0


def _init(key, opp_short, entries, subtitle):
    global _C
    _C = ro.CONCEPTS[key](opp_short, '').bind(entries)
    _C.subtitle = subtitle


def _frame(job):
    kind, n, t = job[:3]
    if kind == 'card':
        return ro.card_title(_C.entries[n], job[3], t, CARD + XF_CARD).tobytes()
    if kind == 'finale':
        # hold the settled board until the last second, then play the concept's own fade
        fade, length = FADE[_C.__class__.__name__], n
        t = t if t < fade else (fade - .01 if t < length - 1 else fade + t - (length - 1))
    im = _C.beat(n, t) if kind == 'beat' else _C.finale(t, _C.subtitle)
    return im.tobytes()


def render_frames(pool, jobs):
    """Ordered frame bytes, rendered in worker processes."""
    return pool.imap(_frame, jobs, chunksize=4)


TTS_PYTHON = {'kokoro': 'data/local/tts/.venv/Scripts/python.exe', 'chatterbox': 'data/local/tts/cb/.venv/Scripts/python.exe'}


def tts(lines: list[tuple[str, Path]], voice: str = 'windows', root: Path = Path('.')):
    """Voice each (text, wav) line. A .txt sidecar records the text, so edited lines are re-voiced."""
    todo = [(t, p) for t, p in lines
            if not p.exists() or not p.with_suffix('.txt').exists()
            or p.with_suffix('.txt').read_text(encoding='utf-8') != t]
    if not todo:
        return
    spec = Path(todo[0][1]).parent / 'tts-todo.json'
    spec.write_text(json.dumps([{'text': t, 'path': str(p)} for t, p in todo]), encoding='utf-8')
    if voice == 'windows':
        ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              "$s.SelectVoice('Microsoft David Desktop'); $s.Rate = 0; "
              f"foreach ($j in (Get-Content -Raw -Encoding UTF8 '{spec}' | ConvertFrom-Json)) "
              "{ $s.SetOutputToWaveFile($j.path); $s.Speak($j.text); $s.SetOutputToNull() }")
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True)
    else:
        python = root / TTS_PYTHON[voice.split(':')[0]]
        subprocess.run([str(python), str(Path(__file__).with_name('tts_local.py')), str(spec), voice], check=True)
    for t, p in todo:
        p.with_suffix('.txt').write_text(t, encoding='utf-8')


def seconds(path):
    return float(probe(path)['format']['duration'])


def shown_pick(average_runs, civ, unit):
    for r in average_runs:
        if r['civ'] == civ and (r['unit'] == unit or unit.endswith(r['unit'])):
            return r['pick']
    raise KeyError((civ, unit))


def entries_for(facts, video, opp, average_runs):
    """One shown run per unit: the number is that run's HP left (+ ranged army kept, - opponent kept)."""
    out = []
    for u in facts[video]['units']:
        pick = shown_pick(average_runs, u['civ'], u['unit'])
        out.append(ro.Entry(key=u['civ'] + '|' + u['unit'], civ=u['civ'], unit=u['unit'], count=u['count'], opp=opp,
                            record=[pick['res']], margin=pick['margin'], rank=0, icon=portrait_path(u['unit']),
                            emblem=Path(theme_for(GAME, u['civ'])['emblemPath'])))
    for rank, e in enumerate(sorted(out, key=lambda e: -e.margin), 1):
        e.rank = rank
    # alphabetical by civ; a civ's unique unit before its Cavalry Archer
    out.sort(key=lambda e: (e.civ, 'Cavalry Archer' in e.unit))
    return out


def run_dir(average_runs, civ, unit):
    return Path(shown_pick(average_runs, civ, unit)['run'])


def card_background(still, path):
    base = Image.open(still).convert('RGB').resize((2560, 1440)).filter(ImageFilter.GaussianBlur(14))
    ImageEnhance.Brightness(base).enhance(0.38).save(path)


def last_frame(ff, video, path):
    subprocess.run([ff, '-y', '-v', 'error', '-sseof', '-0.2', '-i', str(video), '-update', '1', '-q:v', '2',
                    str(path)], check=True)
    return path


def render_segment(ff, concept, n, entries, run, voice, out, log, opp, prev_frame):
    """One battle: dissolve from the previous frame into an animated title card, dissolve into the
    narrated opening, dissolve to the last seconds, then the frozen final frame under the ranking beat."""
    e = entries[n]
    video = run / 'unit-hp-overlay/battle-with-unit-hp.mp4'
    rows = json.loads((run / 'unit-hp-overlay/units.json').read_text())['rows']
    end = terminal_row(rows)['videoSeconds']
    pre, res = voice
    head = max(6.0, seconds(pre) + .3 - CARD + 1.0)
    tail0 = max(head, end - TAIL)
    jump = tail0 > head + XF_CUT + .5          # skip the middle of the battle with a dissolve
    body_len = head + (end - tail0) if jump else end
    frames = round((CARD + body_len + BEAT) * FPS)
    total = frames / FPS
    beat_at = CARD + body_len
    dest = out / f'seg-{concept.key}-{n:02}.mp4'
    if (concept.reuse and dest.exists()
            and dest.stat().st_mtime > max(p.stat().st_mtime for p in (video, prev_frame, pre, res))):
        return dest
    still = out / f'still-{n}.png'
    card = out / f'cardbg-{n}.png'
    subprocess.run([ff, '-y', '-v', 'error', '-ss', '0.5', '-i', str(video), '-frames:v', '1', str(still)], check=True)
    card_background(still, card)
    v = f'fps={FPS},scale=2560:1440,setsar=1,format=yuv420p'
    if jump:
        body = (f"[1:v]split=2[v1][v2];[v1]trim=0:{head + XF_CUT:.3f},setpts=PTS-STARTPTS,{v}[h];"
                f"[v2]trim={tail0:.3f}:{end:.3f},setpts=PTS-STARTPTS,{v},"
                f"tpad=stop_mode=clone:stop_duration={BEAT + 1}[t];"
                f"[h][t]xfade=transition=fade:duration={XF_CUT}:offset={head:.3f}[b];"
                f"[1:a]asplit=2[a1][a2];[a1]atrim=0:{head + XF_CUT:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.4[ha];"
                f"[a2]atrim={tail0:.3f}:{end:.3f},asetpts=PTS-STARTPTS,apad=pad_dur={BEAT + 1}[ta];"
                f"[ha][ta]acrossfade=d={XF_CUT}[ga];")
    else:
        body = (f"[1:v]trim=0:{end:.3f},setpts=PTS-STARTPTS,{v},tpad=stop_mode=clone:stop_duration={BEAT + 1}[b];"
                f"[1:a]atrim=0:{end:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.4,apad=pad_dur={BEAT + 1}[ga];")
    d2 = int((beat_at + .6) * 1000)
    fc = (f"[5:v]{v},trim=0:{XF_IN}[p];[0:v]{v},trim=0:{CARD + XF_CARD}[c0];"
          f"[p][c0]xfade=transition=fade:duration={XF_IN}:offset=0[c];" + body +
          f"[c][b]xfade=transition=fade:duration={XF_CARD}:offset={CARD}[bg0];[bg0]trim=0:{total:.4f}[bg];"
          f"[bg][4:v]overlay=0:0:format=auto:eof_action=pass,format=yuv420p[v];"
          f"anullsrc=r=48000:cl=stereo,atrim=0:{CARD}[ca];[ca][ga]concat=n=2:v=0:a=1,"
          f"aresample=48000,volume=0.45,atrim=0:{total:.4f}[g];"
          f"[2:a]aresample=48000,adelay=300|300[n1];[3:a]aresample=48000,adelay={d2}|{d2}[n2];"
          f"[g][n1][n2]amix=inputs=3:normalize=0:duration=first[a]")
    cmd = [ff, '-y', '-v', 'warning', '-loop', '1', '-i', str(card), '-i', str(video), '-i', str(pre), '-i', str(res),
           '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '2560x1440', '-r', str(FPS), '-i', '-',
           '-loop', '1', '-i', str(prev_frame),
           '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-t', f'{total:.4f}',
           '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '20', '-r', str(FPS), '-c:a', 'aac', '-b:a', '192k',
           '-ar', '48000', str(dest)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=log)
    blank = ro.blank().tobytes()
    line2 = f'{e.count} vs 15 {opp}'
    in_card = lambda s: s < CARD + XF_CARD
    in_beat = lambda s: 0 <= s - beat_at < 4.2
    jobs = [('card', n, i / FPS, line2) if in_card(i / FPS) else ('beat', n, i / FPS - beat_at)
            for i in range(frames) if in_card(i / FPS) or in_beat(i / FPS)]
    rendered = render_frames(concept.pool, jobs)
    for i in range(frames):
        s = i / FPS
        proc.stdin.write(next(rendered) if in_card(s) or in_beat(s) else blank)
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError(f'ffmpeg failed for {dest}')
    return dest


def render_intro(ff, runs, voice, out, log, title, subtitle):
    """Title card, then a montage of battle clips under the cold open and the rules."""
    cold, rules = voice
    gap = .5
    length = math.ceil(max(INTRO_CARD + 2, .4 + seconds(cold) + gap + seconds(rules) + 1.0))
    still = out / 'still-intro.png'
    card = out / 'card-intro.png'
    first = runs[0] / 'unit-hp-overlay/battle-with-unit-hp.mp4'
    subprocess.run([ff, '-y', '-v', 'error', '-ss', '8', '-i', str(first), '-frames:v', '1', str(still)], check=True)
    title_card(card, still, title, [subtitle])
    clips = math.ceil((length - INTRO_CARD) / MONTAGE_CLIP)
    inputs, parts = ['-loop', '1', '-t', str(INTRO_CARD), '-i', str(card)], []
    for i in range(clips):
        run = runs[i % len(runs)]
        rows = json.loads((run / 'unit-hp-overlay/units.json').read_text())['rows']
        start = max(2.0, .4 * terminal_row(rows)['videoSeconds'])
        inputs += ['-ss', f'{start:.2f}', '-t', str(MONTAGE_CLIP), '-i', str(run / 'unit-hp-overlay/battle-with-unit-hp.mp4')]
        parts.append(f'[{i + 1}:v]fps={FPS},scale=2560:1440,setsar=1,format=yuv420p,fade=t=in:st=0:d=0.25[m{i}];'
                     f'[{i + 1}:a]aresample=48000,volume=0.3[g{i}];')
    k = clips + 1
    inputs += ['-i', str(cold), '-i', str(rules)]
    delay2 = int((.4 + seconds(cold) + gap) * 1000)
    fc = (f"[0:v]fps={FPS},scale=2560:1440,setsar=1,format=yuv420p[c];" + ''.join(parts) +
          f"[c]{''.join(f'[m{i}]' for i in range(clips))}concat=n={clips + 1}:v=1:a=0,trim=0:{length}[v];"
          f"anullsrc=r=48000:cl=stereo,atrim=0:{INTRO_CARD}[ca];"
          f"[ca]{''.join(f'[g{i}]' for i in range(clips))}concat=n={clips + 1}:v=0:a=1,atrim=0:{length}[g];"
          f"[{k}:a]aresample=48000,adelay=400|400[n1];[{k + 1}:a]aresample=48000,adelay={delay2}|{delay2}[n2];"
          f"[g][n1][n2]amix=inputs=3:normalize=0:duration=first[a]")
    dest = out / 'seg-intro.mp4'
    subprocess.run([ff, '-y', '-v', 'warning', *inputs, '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
                    '-t', str(length), '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '20', '-r', str(FPS),
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', str(dest)], check=True, stdout=log, stderr=log)
    return dest


def render_finale(ff, concept, still, voice, out, log, subtitle):
    intro, outro = voice
    length = math.ceil(max(20.0, 9.5 + seconds(outro) + 1.5))
    frames_fn = render_frames
    frames = round(length * FPS)
    fc = (f"[0:v]fps={FPS},scale=2560:1440,setsar=1,format=yuv420p,trim=0:{length}[bg];"
          f"[bg][3:v]overlay=0:0:format=auto,format=yuv420p[v];"
          f"[1:a]aresample=48000,adelay=500|500[n1];[2:a]aresample=48000,adelay=9500|9500[n2];"
          f"anullsrc=r=48000:cl=stereo,atrim=0:{length}[s];[s][n1][n2]amix=inputs=3:normalize=0:duration=first[a]")
    dest = out / f'seg-{concept.key}-finale.mp4'
    cmd = [ff, '-y', '-v', 'warning', '-loop', '1', '-i', str(still), '-i', str(intro), '-i', str(outro),
           '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '2560x1440', '-r', str(FPS), '-i', '-',
           '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-t', str(length),
           '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '20', '-r', str(FPS), '-c:a', 'aac', '-b:a', '192k',
           '-ar', '48000', str(dest)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=log)
    for data in frames_fn(concept.pool, [('finale', length, i / FPS) for i in range(frames)]):
        proc.stdin.write(data)
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError('ffmpeg failed for finale')
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--facts', type=Path, required=True)
    ap.add_argument('--video', choices=['castle', 'imperial'], required=True)
    ap.add_argument('--script', type=Path, required=True)
    ap.add_argument('--average-runs', type=Path, required=True)
    ap.add_argument('--picks', nargs='+', required=True, help="civ names (first unit of that civ), or 'all'")
    ap.add_argument('--intro', action='store_true', help='open with the cold open + rules montage')
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--voice', default='windows', help="windows | kokoro:<voice> | chatterbox[:reference.wav]")
    ap.add_argument('--tts-root', default='C:/dev/aoe2/aoe2_matchup', help='checkout holding data/local/tts venvs')
    ap.add_argument('--reuse', action='store_true', help='keep battle segments newer than their recording')
    ap.add_argument('--name', help='output file name (default preview-<concept>-<name>.mp4)')
    ap.add_argument('--concepts', nargs='+', default=['A', 'B', 'C'])
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    out = a.out.resolve()
    vdir = out / ('voice' if a.voice == 'windows' else 'voice-' + a.voice.replace(':', '-').replace('/', '_')[:40])
    vdir.mkdir(parents=True, exist_ok=True)
    ff = find_ffmpeg()
    facts = json.loads(a.facts.read_text(encoding='utf-8'))
    script = json.loads(a.script.read_text(encoding='utf-8'))
    avg = json.loads(a.average_runs.read_text(encoding='utf-8'))
    opp = 'Frankish Knights' if a.video == 'castle' else 'Spanish Paladins'
    opp_short = 'Knights' if a.video == 'castle' else 'Paladins'
    entries = entries_for(facts, a.video, 15, avg)
    lines = {(u['civ'], u['unit']): u for u in script['units']}
    picks = (list(range(len(entries))) if a.picks == ['all'] else
             [next(i for i, e in enumerate(entries) if e.civ == civ) for civ in a.picks])
    speech = []
    for n in picks:
        e = entries[n]
        u = lines[(e.civ, e.unit)]
        speech += [(u['stats'] + ' ' + u['expectation'], vdir / f'pre-{n:02}.wav'),
                   (u['result'], vdir / f'res-{n:02}.wav')]
    speech += [(script['finaleIntro'], vdir / 'finale.wav'), (script['outro'], vdir / 'outro.wav')]
    if a.intro:
        speech += [(script['coldOpen'], vdir / 'cold.wav'), (script['rules'], vdir / 'rules.wav')]
    tts(speech, a.voice, Path(a.tts_root))
    subtitle = f"{'Castle' if a.video == 'castle' else 'Imperial'} Age - ranked by HP left"
    log = (out / 'render.log').open('a', encoding='utf-8')
    results = {}
    for key in a.concepts:
        concept = ro.CONCEPTS[key](opp_short, '').bind(entries)
        concept.key = key
        concept.reuse = a.reuse
        concept.pool = Pool(a.workers, _init, (key, opp_short, entries, subtitle))
        segs = []
        if a.intro:
            top = sorted(entries, key=lambda e: e.rank)[:10]
            title = script['title'].split(':')[0]
            segs.append(render_intro(ff, [run_dir(avg, e.civ, e.unit) for e in top],
                                     (vdir / 'cold.wav', vdir / 'rules.wav'), out, log, title,
                                     script['title'].split(':', 1)[1].strip() if ':' in script['title'] else ''))
            print(key, 'intro', flush=True)
        prev = out / 'black.png'
        if not prev.exists():
            Image.new('RGB', (2560, 1440)).save(prev)

        def tail_frame(seg, name):
            png = out / name
            if not png.exists() or png.stat().st_mtime < seg.stat().st_mtime:
                last_frame(ff, seg, png)
            return png
        if segs:
            prev = tail_frame(segs[-1], f'last-{key}-intro.png')
        for n in picks:
            e = entries[n]
            seg = render_segment(ff, concept, n, entries, run_dir(avg, e.civ, e.unit),
                                 (vdir / f'pre-{n:02}.wav', vdir / f'res-{n:02}.wav'),
                                 out, log, opp, prev)
            segs.append(seg)
            prev = tail_frame(seg, f'last-{key}-{n:02}.png')
            print(key, 'segment', e.civ, flush=True)
        segs.append(render_finale(ff, concept, prev, (vdir / 'finale.wav', vdir / 'outro.wav'),
                                  out, log, subtitle))
        listing = out / f'concat-{key}.txt'
        listing.write_text(''.join(f"file '{s.as_posix()}'\n" for s in segs), encoding='utf-8')
        final = out / (a.name or f'preview-{key}-{concept.name.split(" - ")[1].lower().replace(" ", "-")}.mp4')
        subprocess.run([ff, '-y', '-v', 'warning', '-f', 'concat', '-safe', '0', '-i', str(listing),
                        '-c', 'copy', '-movflags', '+faststart', str(final)], check=True, stdout=log, stderr=log)
        concept.pool.close()
        results[key] = str(final)
        print(key, final, round(seconds(final), 1), flush=True)
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
