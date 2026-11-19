"""Turn a recorded spike (prepare_spike_matchups.py manifest) into one long video + Shorts.

For every manifest row with a verified raw bundle in any --campaign status.json:
  1. overlays (static panels, HP alignment, live HP queue) via postprocess_campaign.overlay,
     skipped when battle-with-unit-hp.mp4 already exists;
  2. a title-card intro (game font over a blurred battle frame, silent audio);
  3. chapters ordered subject -> opponent -> layout, each trimmed at the battle end,
     concatenated with FFMETADATA chapters, full-decoded, description written;
  4. Shorts for --shorts picks (default: per subject, the closest finish and the
     biggest win/loss), rendered with build_vertical_short.build and full-decoded.

Results are read from the recorded gRPC timeline only (subject = owner 2 in spike plans).
Nothing is uploaded. Output lands in <lab>/compilations/<name>/.

    python apps/video/build_spike_episode.py --manifest data/local/steppe-spike/manifest.json \
        --campaign <lab>/campaigns/steppe-spike-pilot --campaign <lab>/campaigns/steppe-spike \
        --name steppe-spike --title "Kipchak vs Tatar Horse Archers"
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageFilter, ImageEnhance

from aoe2x.lab.postprocess_campaign import overlay, source_hash
from overlay.battle_end import terminal_row
from overlay.ffutil import find_ffmpeg, find_ffprobe
from overlay.static_stats import GAME, GameFont

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'
INK = (246, 230, 191, 255)
GOLD = (214, 176, 96, 255)


def probe(path: Path) -> dict:
    return json.loads(subprocess.check_output([find_ffprobe(), '-v', 'error', '-show_format', '-show_streams',
                                               '-show_chapters', '-of', 'json', str(path)]))


def stamp(seconds: float) -> str:
    n = int(seconds)
    return f'{n // 3600}:{n // 60 % 60:02}:{n % 60:02}' if n >= 3600 else f'{n // 60:02}:{n % 60:02}'


def verified_runs(campaigns: list[Path]) -> dict[str, Path]:
    runs = {}
    for c in campaigns:
        for r in json.loads((c / 'status.json').read_text(encoding='utf-8'))['results']:
            if r['status'] == 'verified':
                runs[r['jobId']] = Path(r['runDirectory'])
    return runs


def outcome(run: Path) -> dict:
    rows = json.loads((run / 'unit-hp-overlay/units.json').read_text())['rows']
    end = terminal_row(rows)
    start = {o: sum(u['hp'] for u in rows[0]['sides'][o]) for o in ('2', '3')}
    final = {o: sum(u['hp'] for u in end['sides'][o]) for o in ('2', '3')}
    alive = [o for o in ('2', '3') if final[o] > 0]
    winner = alive[0] if len(alive) == 1 else None
    survivors = sum(u['hp'] > 0 for u in end['sides'][winner]) if winner else 0
    signed = (1 if winner == '2' else -1) * final[winner] / start[winner] * 100 if winner else 0.0
    return dict(end=end, winner=winner, winnerHp=final[winner] if winner else 0, survivors=survivors,
                signedHpPercent=signed, result='WIN' if winner == '2' else 'LOSS' if winner == '3' else 'DRAW')


def title_card(path: Path, still: Path, title: str, lines: list[str]) -> None:
    font = GameFont(GAME)
    base = Image.open(still).convert('RGB').resize((2560, 1440)).filter(ImageFilter.GaussianBlur(14))
    base = ImageEnhance.Brightness(base).enhance(0.38).convert('RGBA')

    def put(text, y, size, color):
        tile = Image.new('RGBA', (math.ceil(font.width(text, size)) + 8, size + 24))
        font.draw(tile, (2, 0), text, size, color)
        base.alpha_composite(tile, ((2560 - tile.width) // 2, y))

    put(title, 470, 112, GOLD)
    for i, line in enumerate(lines):
        put(line, 660 + i * 78, 54, INK)
    base.convert('RGB').save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--campaign', type=Path, action='append', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--title', required=True)
    ap.add_argument('--intro-seconds', type=float, default=7)
    ap.add_argument('--shorts', nargs='*', help='job ids for Shorts (default: automatic picks)')
    ap.add_argument('--skip-shorts', action='store_true')
    ap.add_argument('--workers', type=int, default=3, help='parallel overlay renders')
    a = ap.parse_args()
    out = LAB / 'compilations' / a.name
    out.mkdir(parents=True, exist_ok=True)
    ff = find_ffmpeg()
    log = (out / 'render.log').open('a', encoding='utf-8')

    def call(cmd):
        subprocess.run([ff, '-y', '-v', 'warning', *cmd], stdout=log, stderr=log, check=True)

    spec = json.loads(a.manifest.read_text(encoding='utf-8'))['matchups']
    runs = verified_runs(a.campaign)
    missing = [s['id'] for s in spec if s['id'] not in runs]
    if missing:
        print('Not recorded/verified (left out):', *missing, sep='\n  ')
    rows = [s for s in spec if s['id'] in runs]
    if not rows:
        raise SystemExit('No verified recordings')

    revision = source_hash()
    todo = [s['id'] for s in rows if not (runs[s['id']] / 'unit-hp-overlay/battle-with-unit-hp.mp4').is_file()]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for job, _ in zip(todo, pool.map(lambda j: overlay(runs[j], out / 'overlays' / j, revision), todo)):
            print('overlay', job, flush=True)
    episode = []
    for s in rows:
        run = runs[s['id']]
        plan = json.loads((run.parent.parent / 'plan.json').read_text(encoding='utf-8'))
        episode.append(dict(spec=s, run=run, plan=plan, **outcome(run)))

    # chapters: subject -> opponent (manifest order) -> layout
    clips, results, cursor = [], [], 0.0
    first = episode[0]
    still = out / 'intro-still.png'
    call(['-ss', '20', '-i', str(first['run'] / 'battle.mp4'), '-frames:v', '1', str(still)])
    subjects = list(dict.fromkeys(f"{e['plan']['side2']['label']} ({e['plan']['side2']['civ']})" for e in episode))
    opponents = list(dict.fromkeys(e['plan']['side3']['label'] for e in episode))
    layouts = list(dict.fromkeys(e['spec']['layout'] for e in episode))
    card = out / 'intro-card.png'
    title_card(card, still, a.title, [' vs '.join(subjects), 'against ' + ', '.join(opponents),
                                      f"{len(episode)} recorded battles on {', '.join(layouts)} maps",
                                      'Cost-balanced armies. Real in-game results.'])
    intro = out / 'intro-1440p60.mp4'
    call(['-loop', '1', '-framerate', '60', '-i', str(card), '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
          '-t', str(a.intro_seconds), '-vf', 'fade=in:0:30,format=yuv420p', '-c:v', 'libx264', '-crf', '18',
          '-r', '60', '-video_track_timescale', '15360', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k',
          str(intro)])
    cursor = float(probe(intro)['format']['duration'])
    clips.append(dict(title='Introduction', source=str(intro), startSeconds=0, durationSeconds=cursor))
    for e in episode:
        source = e['run'] / 'unit-hp-overlay/battle-with-unit-hp.mp4'
        end = e['end']['videoSeconds']
        if float(probe(source)['format']['duration']) > end + .5:
            duration = (math.ceil(end * 60) + 1) / 60
            trimmed = out / 'chapters' / (e['spec']['id'] + '.mp4')
            trimmed.parent.mkdir(exist_ok=True)
            if not trimmed.exists():
                partial = trimmed.with_suffix('.partial.mp4')
                call(['-i', str(source), '-t', str(duration), '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'libx264',
                      '-crf', '18', '-pix_fmt', 'yuv420p', '-video_track_timescale', '15360',
                      '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '192k', str(partial)])
                partial.replace(trimmed)
            source = trimmed
        duration = float(probe(source)['format']['duration'])
        p2, p3 = e['plan']['side2'], e['plan']['side3']
        title = f"{p2['count']} {p2['label']} vs {p3['count']} {p3['label']} - {e['spec']['layout']}"
        row = dict(jobId=e['spec']['id'], title=title, source=str(source), startSeconds=cursor,
                   durationSeconds=duration, timestamp=stamp(cursor), result=e['result'],
                   winnerHp=e['winnerHp'], survivors=e['survivors'], signedHpPercent=e['signedHpPercent'],
                   subject=p2['label'], opponent=p3['label'], opponentCiv=p3['civ'], layout=e['spec']['layout'],
                   run=str(e['run']))
        results.append(row)
        clips.append(row)
        cursor += duration
    (out / 'concat.txt').write_text(''.join(f"file '{Path(c['source']).as_posix()}'\n" for c in clips), encoding='utf-8')
    meta = f';FFMETADATA1\ntitle={a.title}\n'
    for c in clips:
        meta += (f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c['startSeconds'] * 1000)}\n"
                 f"END={round((c['startSeconds'] + c['durationSeconds']) * 1000)}\ntitle={c['title']}\n")
    (out / 'chapters.ffmeta').write_text(meta, encoding='utf-8')
    video = out / f'{a.name}.mp4'
    # Re-encode video on concat: intro and battle clips come from different encoders.
    call(['-f', 'concat', '-safe', '0', '-i', str(out / 'concat.txt'), '-i', str(out / 'chapters.ffmeta'),
          '-map', '0:v:0', '-map', '0:a:0', '-map_metadata', '1', '-map_chapters', '1',
          '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '19', '-pix_fmt', 'yuv420p',
          '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-af', 'aresample=async=1', '-movflags', '+faststart',
          str(video)])
    info = probe(video)
    assert abs(float(info['format']['duration']) - cursor) < 2, (info['format']['duration'], cursor)
    assert len(info['chapters']) == len(clips)
    call(['-xerror', '-threads', '8', '-i', str(video), '-f', 'null', '-'])

    desc = (f"{a.title} | Age of Empires II DE\n\nRecorded in-game battles with live unit HP overlays. "
            "Army sizes use a geometric cost balance (the cheaper unit gets 27; the other side is scaled by the "
            "square root of the cost ratio, with food 1, wood 0.9, gold 1.1 weights and fully upgraded Imperial "
            "costs), so neither equal numbers nor equal resources alone decide the fight.\n\n"
            "WIN/LOSS is from the horse archer's side; HP is the winning army's remaining HP.\n\n00:00 Introduction\n")
    desc += '\n'.join(f"{r['timestamp']} {r['title']} | {r['result']} | {round(r['winnerHp'])} HP" for r in results)
    desc += '\n\n#AoE2 #AoE2DE #AgeOfEmpires2 #HorseArcher #RTS #UnitCounters\n'
    assert len(desc) <= 5000
    (out / 'youtube-description.txt').write_text(desc, encoding='utf-8')
    manifest = dict(output=str(video), title=a.title, chapters=len(clips), expectedSeconds=cursor, fullDecode='passed',
                    left_out=missing, results=results)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(dict(video=str(video), seconds=round(cursor, 1), chapters=len(clips)), indent=2), flush=True)

    if a.skip_shorts:
        return
    from build_vertical_short import build
    picks = a.shorts
    if not picks:
        picks = []
        for subject in dict.fromkeys(r['subject'] for r in results):
            mine = [r for r in results if r['subject'] == subject and r['result'] != 'DRAW']
            for chooser in (lambda r: abs(r['signedHpPercent']),          # closest finish
                            lambda r: -abs(r['signedHpPercent'])):         # most one-sided
                for r in sorted(mine, key=chooser):
                    if r['jobId'] not in picks:
                        picks.append(r['jobId'])
                        break
    shorts = []
    for job in picks:
        r = next(x for x in results if x['jobId'] == job)
        dest = out / 'shorts' / job
        build(Path(r['run']), dest)
        short = dest / 'short.mp4'
        info = probe(short)
        v = next(s for s in info['streams'] if s['codec_type'] == 'video')
        assert (v['width'], v['height']) == (1080, 1920) and float(info['format']['duration']) <= 180
        call(['-xerror', '-threads', '4', '-i', str(short), '-f', 'null', '-'])
        shorts.append(dict(jobId=job, video=str(short), seconds=float(info['format']['duration']),
                           result=r['result'], title=r['title']))
        print('short', job, flush=True)
    (out / 'shorts.json').write_text(json.dumps(shorts, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
