"""Render campaign bookends and join the approved comparison without re-encoding it.

Page two reveals civilization columns in sync with its off-screen voiceover.
Page-one narration must match the approved text and have character alignment.
Frames stream to FFmpeg, avoiding hundreds of disposable PNGs. Source battles,
frames.bin, and the existing matchups-only compilation are never modified.
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageChops
from build_campaign_intro import lines
from overlay.static_stats import GAME, GameFont
from overlay.ffutil import find_ffmpeg, find_ffprobe

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'apps/video/intro'
OUT = ROOT / 'data/local/champi-comparison-intro'
SERIES = ROOT / 'data/local/champi-comparison-full'
FPS = 30
PLAN = ASSETS / 'champi-comparison.json'
NAME = 'Champi'


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def background():
    catalog = json.loads((ASSETS / 'campaign_catalog.json').read_text())
    theme = catalog['preferredByCivilization'][json.loads(PLAN.read_text())['civilization']]
    return Image.open(GAME / 'widgetui' / theme['background']).convert('RGB').resize(
        (2560, 1080), Image.Resampling.LANCZOS).crop((320, 0, 2240, 1080))


def ink(base, asset, size, xy):
    art = Image.open(asset).convert('RGBA')
    art.thumbnail(size, Image.Resampling.LANCZOS)
    x, y = xy
    box = (x, y, x + art.width, y + art.height)
    base.paste(ImageChops.multiply(base.crop(box), art.convert('RGB')), box, art.getchannel('A'))


def pages():
    OUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(PLAN.read_text())
    font = GameFont(GAME)
    first = background()
    ink(first, ASSETS / config.get('art','assets/champi-warrior-campaign.png'), (320, 550), (490, 295))
    first = first.convert('RGBA')
    glyphs = []
    size, y = 27, 295
    for paragraph in config['page1']:
        for line in lines(font, paragraph, size, 570):
            x = 845
            for char in line:
                glyphs.append((x, y, char))
                x += font.width(char, size)
            y += 36
        y += 24
    if y > 840:
        raise ValueError(f'Introduction text exceeds parchment: {y}')
    full = first.copy()
    for x, y, char in glyphs:
        font.draw(full, (x, y), char, size)
    full.convert('RGB').save(OUT / 'Champi_Comparison_Intro_Page_1.png')
    end = background()
    ink(end, ASSETS / 'assets/youtube-campaign-sketch.png', (570, 400), (400, 340))
    end = end.convert('RGBA')
    for y, text, size in [(400, 'Thank you for watching.', 34),
                          (495, 'Please like and subscribe.', 32)]:
        font.draw(end, (940, y), text, size)
    end.convert('RGB').save(OUT / 'Champi_Comparison_End_Page.png')
    return first, glyphs, end, config


def encode(output, duration, frames, input_size, audio, filters):
    command = [find_ffmpeg(), '-y', '-v', 'warning', '-filter_complex_threads', '1',
               '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', input_size,
               '-framerate', str(FPS), '-i', 'pipe:0', *audio,
               '-filter_complex', filters, '-map', '0:v', '-map', '[mix]',
               '-vf', 'scale=2560:1440:flags=lanczos,setsar=1,format=yuv420p',
               '-t', str(duration), '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '18', '-b:v', '0',
               '-threads', '0', '-video_track_timescale', '15360',
               '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k',
               '-movflags', '+faststart', str(output)]
    with output.with_suffix('.log').open('w') as log:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=log)
        try:
            for frame in frames:
                proc.stdin.write(frame)
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError(f'Encoding failed; inspect {output.with_suffix(".log")}')


def probe(path):
    return json.loads(subprocess.check_output([find_ffprobe(), '-v', 'error',
        '-show_streams', '-show_format', '-of', 'json', str(path)]))


def build(narration_plan=None, stills_only=False, page_two_narration_plan=None, defer_assembly=False):
    first, glyphs, end, config = pages()
    if stills_only:
        return
    font = GameFont(GAME)
    reveal = [0.4 + i / 18 for i in range(len(glyphs))]
    first_duration = math.ceil((reveal[-1] + 3) * FPS) / FPS
    narration = None
    if narration_plan:
        plan = json.loads(Path(narration_plan).read_text())
        slide = plan['slides'][0]
        if slide['paragraphs'] != config['page1']:
            raise ValueError('Narration must match the approved first-page text')
        alignment = json.loads(Path(slide['narrationAlignment']).read_text())['alignment']
        cursor, reveal = 0, []
        for _, _, char in glyphs:
            while cursor < len(alignment['characters']) and alignment['characters'][cursor].isspace() and alignment['characters'][cursor] != char:
                cursor += 1
            if cursor >= len(alignment['characters']) or alignment['characters'][cursor] != char:
                raise ValueError('Narration alignment differs from visible text')
            reveal.append(alignment['character_start_times_seconds'][cursor] + .4)
            cursor += 1
        first_duration = slide['duration']
        narration = Path(plan['narration']['file'])
    page2 = Image.open(OUT / 'Champi_Comparison_Intro_Page_2.png').convert('RGB')
    # Render the opening at its established 1080p layout, then scale uniformly.
    # Page two remains at native 1440p in its separate segment to preserve text.
    def first_frames():
        frame, cursor, cached = first.copy(), 0, None
        for n in range(round(first_duration * FPS)):
            changed = False
            while cursor < len(glyphs) and reveal[cursor] <= n / FPS:
                x, y, char = glyphs[cursor]
                font.draw(frame, (x, y), char, 27)
                cursor += 1
                changed = True
            if changed or cached is None:
                cached = frame.convert('RGB').tobytes()
            yield cached
    music = ASSETS / config.get('music',{}).get('file','assets/incas-theme.wav')
    audio = ['-stream_loop', '-1', '-i', str(music)]
    if narration:
        audio += ['-i', str(narration)]
        filters = '[1:a]loudnorm=I=-31:TP=-4:LRA=7,afade=t=in:d=1[m];[2:a]loudnorm=I=-17:TP=-2:LRA=7[v];[m][v]amix=inputs=2:normalize=0:duration=shortest,alimiter=limit=0.89[mix]'
    else:
        filters = '[1:a]loudnorm=I=-25:TP=-3:LRA=7,afade=t=in:d=1[mix]'
    encode(OUT/'page-1.mp4', first_duration, first_frames(), '1920x1080', audio, filters)
    second_duration = 5
    # Seeking a looping WAV input can reset its timestamps at the loop boundary
    # and truncate the mixed voice track. Trim the continuous decoded stream
    # instead, then generate contiguous timestamps for this page's music.
    second_audio = ['-stream_loop','-1','-i',str(music)]
    music_trim = f'atrim=start={first_duration},asetpts=N/SR/TB,'
    second_filters = '[1:a]'+music_trim+'loudnorm=I=-25:TP=-3:LRA=7,afade=t=out:st=4:d=1[mix]'
    column_reveals = []
    if page_two_narration_plan:
        second_plan = json.loads(Path(page_two_narration_plan).read_text())
        if len(second_plan['slides']) != 1 or second_plan['slides'][0]['paragraphs'] != config['page2Narration']:
            raise ValueError('Page-two narration differs from the approved off-screen script')
        second_duration = second_plan['slides'][0]['duration']
        slide = second_plan['slides'][0]
        alignment = json.loads(Path(slide['narrationAlignment']).read_text())['alignment']
        spoken = '\n\n'.join(slide['paragraphs'])
        if ''.join(alignment['characters']) != spoken:
            raise ValueError('Page-two alignment must match the complete spoken script')
        cursor = 0
        for paragraph in slide['paragraphs']:
            column_reveals.append(alignment['character_start_times_seconds'][cursor] + slide['narrationLeadSeconds'])
            cursor += len(paragraph) + 2
        if second_duration - slide['narrationLeadSeconds'] - slide['speechDurationSeconds'] < 3:
            raise ValueError('Page two must hold for three seconds after speech')
        second_audio += ['-i',second_plan['narration']['file']]
        second_filters = ('[1:a]'+music_trim+'loudnorm=I=-31:TP=-4:LRA=7[m];'
                          '[2:a]loudnorm=I=-17:TP=-2:LRA=7[v];'
                          '[m][v]amix=inputs=2:normalize=0:duration=shortest,'
                          f'alimiter=limit=0.89,afade=t=out:st={second_duration-1}:d=1[mix]')
    def second_frames():
        if column_reveals:
            stages = [Image.open(OUT/f'page-2-stage-{i}.png').convert('RGB').tobytes() for i in range(5)]
        else:
            stages = [page2.tobytes()]
        for n in range(round(second_duration*FPS)):
            stage = sum(t <= n/FPS for t in column_reveals)
            yield stages[stage]
    encode(OUT/'page-2.mp4', second_duration, second_frames(),
           '2560x1440', second_audio, second_filters)
    second_probe = probe(OUT/'page-2.mp4')
    for stream in second_probe['streams']:
        if stream['codec_type'] in ('audio','video') and abs(float(stream['duration'])-second_duration) > .1:
            raise ValueError('Second-page audio/video must both cover the full narration and hold')
    save(OUT/'page-2-timing.json',dict(columnRevealSeconds=column_reveals,
         durationSeconds=second_duration,narrationPlan=str(page_two_narration_plan) if page_two_narration_plan else None,
         postSpeechHoldSeconds=3 if page_two_narration_plan else None))
    still = end.convert('RGB').tobytes()
    encode(OUT/'ending.mp4', 5, (still for _ in range(150)), '1920x1080',
           ['-stream_loop','-1','-i',str(music)],
           '[1:a]loudnorm=I=-25:TP=-3:LRA=7,afade=t=in:d=0.5,afade=t=out:st=3.5:d=1.5[mix]')
    if defer_assembly:
        save(OUT/'bookends-ready.json',dict(firstPageSeconds=first_duration,
             narrationPage1=bool(narration),narrationPage2=bool(page_two_narration_plan)))
    else:
        assemble(first_duration, bool(narration), bool(page_two_narration_plan))


def assemble(first_duration, narration, narration_page_two=False):
    """Copy video bit-for-bit; normalize joined audio timestamps after AAC padding."""
    source = SERIES/f'{NAME}_Four_Civs_All_Unique_Units.mp4'
    final = SERIES/f'{NAME}_Four_Civs_Complete_With_Intro.mp4'
    parts = [OUT/'page-1.mp4', OUT/'page-2.mp4', source, OUT/'ending.mp4']
    details = [probe(p) for p in parts]
    # Compatibility is required for safe stream-copy concatenation.
    for d in details:
        v = next(s for s in d['streams'] if s['codec_type']=='video')
        a = next(s for s in d['streams'] if s['codec_type']=='audio')
        assert (v['codec_name'],v['width'],v['height'],v['r_frame_rate']) == ('h264',2560,1440,'30/1')
        assert (a['codec_name'],a['sample_rate'],a['channels']) == ('aac','48000',2)
    listing = OUT/'final-concat.txt'
    listing.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts))
    expected = sum(float(d['format']['duration']) for d in details)
    with (OUT/'assembly.log').open('w') as log:
        subprocess.run([find_ffmpeg(),'-y','-v','warning','-f','concat','-safe','0','-i',str(listing),
                        '-c:v','copy','-af','aresample=async=1:first_pts=0','-c:a','aac','-ar','48000',
                        '-ac','2','-b:a','192k','-threads','2',
                        '-t',str(expected),
                        '-movflags','+faststart',str(final)],check=True,stdout=log,stderr=log)
    result = probe(final)
    actual = float(result['format']['duration'])
    if abs(actual-expected) > .2:
        raise ValueError(f'Unexpected joined duration: {actual} vs {expected}')
    manifest = dict(video=str(final), durationSeconds=actual, firstPageSeconds=first_duration,
                    secondPageSeconds=float(details[1]['format']['duration']), endingSeconds=5,
                    narrationPage1=bool(narration), narrationPage2=bool(narration_page_two),
                    textAnimationPage2=False, parts=[str(p) for p in parts],
                    matchupCount=74, sourceSeriesManifest=str(SERIES/'series-manifest.json'),
                    matchupStartSeconds=sum(float(d['format']['duration']) for d in details[:2]),
                    endingStartSeconds=sum(float(d['format']['duration']) for d in details[:3]))
    timing = OUT/'page-2-timing.json'
    if timing.exists():
        manifest['page2Timing'] = json.loads(timing.read_text())
    save(OUT/'assembly-manifest.json',manifest)
    print(json.dumps(manifest),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--narration-plan',type=Path)
    parser.add_argument('--page-two-narration-plan',type=Path)
    parser.add_argument('--series-dir',type=Path,default=SERIES)
    parser.add_argument('--plan',type=Path,default=PLAN)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--stills-only',action='store_true')
    parser.add_argument('--assemble-only',action='store_true',help='Reuse already rendered bookends')
    parser.add_argument('--defer-assembly',action='store_true')
    args = parser.parse_args()
    SERIES = args.series_dir.resolve()
    PLAN = args.plan.resolve();OUT=args.output.resolve()
    NAME=json.loads(PLAN.read_text()).get('unit','Champi')
    if NAME=='Elite Champi Warrior':NAME='Champi'
    if args.assemble_only:
        previous = json.loads((OUT/('bookends-ready.json' if (OUT/'bookends-ready.json').exists() else 'assembly-manifest.json')).read_text())
        assemble(previous['firstPageSeconds'],previous['narrationPage1'],previous.get('narrationPage2',False))
    else:
        build(args.narration_plan,args.stills_only,args.page_two_narration_plan,args.defer_assembly)
