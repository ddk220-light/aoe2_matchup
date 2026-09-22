"""Run an explicitly selected, local V8 Short batch from archived clean recordings.

The manifest supplies exact sources. No capture, publication or source mutation.
Finished stages are retained so this fixed batch can be resumed between videos.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

import cv2
from PIL import Image

from build_story_short import prepare, render, intro_background, ending_background, paste_attack
from compact_recording_archive import digest
from materialize_compact_recording import materialize
from overlay.auto_alignment import align
from overlay.battle_camera import analyze, BattleCamera, plan_camera, first_combat_time
from overlay.battle_end import terminal_row, recorded_battle_frames
from overlay.ffutil import find_ffmpeg, find_ffprobe
from overlay.shorts_story import winning_result, AttackAnimation
from overlay.shorts_battle import BattleOverlay
from overlay.static_stats import REPO, GAME, resolve_stats
from overlay.unit_timeline import decode


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def stage(item, root):
    job_id = item.get('sourceJob') or Path(item['sourceRun']).parent.parent.name
    run = root/'sources'/job_id/'live/run_001'
    if (run/'recording.json').exists():
        return run
    if item.get('sourceIndex'):
        return materialize(Path(item['sourceIndex']), job_id, root/'sources')
    source = Path(item['sourceRun'])
    recording = read(source/'recording.json')
    run.mkdir(parents=True, exist_ok=True)
    for key, name in [('battleVideo','battle.mp4'), ('frames','frames.bin')]:
        entry = recording['files'][key]
        original = source/entry['path']
        if digest(original) != entry['sha256']:
            raise ValueError(f'Source hash mismatch: {original}')
        shutil.copyfile(original, run/name)
        entry['path'] = name
    for relative in ('manifest.json', 'unit-hp-overlay/alignment.json',
                     'static-stats-overlay/stats.json'):
        original = source/relative
        if original.exists():
            (run/relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, run/relative)
    shutil.copyfile(source.parent.parent/'plan.json', run.parent.parent/'plan.json')
    save(run/'archive-source.json', {'run':str(source)})
    save(run/'recording.json', recording)
    return run


def prepare_item(item, root, output, *, cache_gameplay=True, prior_battle=None, aftermath_seconds=0):
    run = stage(item, root)
    if not (run/'unit-hp-overlay/alignment.json').exists():
        align(run, sample_rate=6, color_components=True)
    timeline_path = run/'unit-hp-overlay/units.json'
    timeline = read(timeline_path) if timeline_path.exists() else decode(run)
    if not timeline_path.exists():
        save(timeline_path, timeline)
    if not timeline['mapping'].get('alignment'):
        raise ValueError('Verified video/HP alignment required')
    stats_path = run/'static-stats-overlay/stats.json'
    if not stats_path.exists():
        plan = read(run.parent.parent/'plan.json')
        with sqlite3.connect(f'file:{REPO / "data/golden/aoe2_reference.db"}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            units = [resolve_stats(db, plan[key]) for key in ('side2','side3')]
        save(stats_path, {'units':[{'unit':unit['unit_name'], 'stats':unit} for unit in units],
                          'source':'data/golden/aoe2_reference.db; read-only'})
    battle = output/'battle'
    battle.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(run/'battle.mp4'))
    fps, available = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    start = .2
    last = terminal_row(timeline['rows'])
    outcome = winning_result(timeline['rows'][0], last)
    combat_frames = recorded_battle_frames(start,last['videoSeconds'],fps,available)
    frames = recorded_battle_frames(start,last['videoSeconds'],fps,available,aftermath_seconds)
    if frames < 1:
        raise ValueError('Elimination is outside the recording')
    if not (battle/'camera.json').exists():
        if prior_battle:
            document = read(prior_battle/'camera.json')
            observations = document['observations']
            contact = first_combat_time(timeline['rows'])
            document.update(keyframes=plan_camera([o['bounds'] for o in observations],
                [o['time'] for o in observations], *document['sourceSize'], engagement_time=contact),
                engagementTime=contact,
                motion='Hold until contact; up to 40px horizontal travel; smooth vertical movement and progressive zoom-in only')
            save(battle/'camera.json',document)
        else:
            analyze(run/'battle.mp4', battle/'camera.json', start, frames/fps, telemetry_run=run)
    save(battle/'manifest.json', {'source':str(run.resolve()), 'fps':fps,
         'durationSeconds':frames/fps, 'trimStartSeconds':start, 'camera':'telemetry',
         'aftermathSeconds':(frames-combat_frames)/fps,
         'gameViewport':[0,330,1080,1080], 'outcome':outcome})
    if not (output/'prepared.json').exists():
        if cache_gameplay:
            prepare(battle, output)
        save(output/'prepared.json', {'frames':frames, 'fps':fps, 'outcome':outcome,
                                     'gameplayCache':cache_gameplay})
    return battle


def enhance(output, trials):
    if (output/'enhancement-complete.json').exists():
        return
    command = [sys.executable, str(trials/'seedvr2/inference_cli.py'), str(output/'gameplay.mkv'),
        '--output',str(output/'seed'), '--output_format','png', '--model_dir',str(trials/'models'),
        '--dit_model','seedvr2_ema_7b_sharp_fp16.safetensors', '--resolution','2160',
        '--batch_size','9', '--uniform_batch_size', '--temporal_overlap','1',
        '--chunk_size','72', '--cache_dit', '--cache_vae', '--color_correction','lab',
        '--input_noise_scale','0', '--latent_noise_scale','0', '--dit_offload_device','cpu',
        '--vae_offload_device','cpu', '--tensor_offload_device','cpu',
        '--vae_encode_tiled', '--vae_decode_tiled', '--vae_encode_tile_size','512',
        '--vae_decode_tile_size','512', '--attention_mode','sdpa', '--seed','42']
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = str(trials/'packages')
    save(output/'enhancement-command.json', {'command':command, 'packages':env['PYTHONPATH']})
    with (output/'seed.log').open('w', encoding='utf-8') as log:
        subprocess.run(command, cwd=REPO, env=env, stdout=log, stderr=log, check=True)
    expected = read(output/'prepared.json')['frames']
    actual = len(list((output/'seed/gameplay').glob('gameplay_*.png')))
    if actual != expected:
        raise ValueError(f'Enhanced frame count {actual} != {expected}')
    save(output/'enhancement-complete.json', {'frames':actual})


def previews(battle, output, attacks, *, recording_top=0):
    """Review framing and assets before expensive enhancement; unenhanced source."""
    manifest = read(battle/'manifest.json')
    run = Path(manifest['source'])
    units = read(run/'static-stats-overlay/stats.json')['units']
    rows = read(run/'unit-hp-overlay/units.json')['rows']
    overlay = BattleOverlay(units, rows, read(run.parent.parent/'plan.json'), GAME,
                            recording_top=recording_top)
    camera = BattleCamera(read(battle/'camera.json')['keyframes'])
    animations = [AttackAnimation(attacks/u['unit'].lower().replace(' ','_'), (580,510)) for u in units]
    intro = intro_background(units)
    for i, y in enumerate((515,1380)):
        paste_attack(intro, animations[i].at(.3), (540,y))
    outcome = manifest['outcome']
    winner = outcome['unitIndex']
    end = ending_background(units[winner], winner, outcome['hpFraction'])
    paste_attack(end, animations[winner].at(.3), (540,485))
    pictures = [intro]
    cap = cv2.VideoCapture(str(run/'battle.mp4'))
    for seconds in (1, manifest['durationSeconds']/2, manifest['durationSeconds']-1/manifest['fps']):
        time = manifest['trimStartSeconds']+seconds
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(time*manifest['fps']))
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError('Could not decode framing preview')
        crop = Image.fromarray(cv2.cvtColor(camera.crop(frame,time),cv2.COLOR_BGR2RGB))
        pictures.append(overlay.compose(crop,seconds,recording=frame,crop=camera.at(time)))
    cap.release()
    pictures.append(end)
    sheet = Image.new('RGB', (360*len(pictures),640))
    for i, picture in enumerate(pictures):
        picture.convert('RGB').save(output/f'preflight-{i}.jpg',quality=95)
        sheet.paste(picture.resize((360,640),Image.Resampling.LANCZOS), (360*i,0))
    sheet.save(output/'preflight-sheet.jpg',quality=95)
    save(output/'preflight-cards.json', overlay.card_details)


def verify(output):
    story = read(output/'story.json')
    video = Path(story['video'])
    probe = json.loads(subprocess.check_output([find_ffprobe(),'-v','error',
        '-show_streams','-show_format','-of','json',str(video)]))
    picture = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    sound = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    assert (picture['width'], picture['height']) == (1080,1920)
    assert int(picture['nb_frames']) == story['frames']
    assert picture['codec_name'] == 'h264' and sound['codec_name'] == 'aac'
    assert int(sound['sample_rate']) == 48000
    assert abs(float(sound['duration'])-story['durationSeconds']) <= .05
    subprocess.run([find_ffmpeg(),'-v','error','-xerror','-i',str(video),
                    '-f','null','-'],check=True)
    save(output/'verification.json', {'media':'passed', 'visualReview':'pending',
         'video':str(video), 'sha256':digest(video), 'frames':story['frames'],
         'fps':story['fps'], 'durationSeconds':story['durationSeconds'], 'probe':probe})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--numbers', type=int, nargs='+', required=True)
    parser.add_argument('--phase', choices=('prepare','preview','run'), default='run')
    parser.add_argument('--enhance-model', type=Path, help='Direct enhancement; separate -compact output folders')
    args = parser.parse_args()
    batch = read(args.manifest)
    root = Path(batch['root'])
    trials = REPO/'data/local/video-recreate-blackwood-20260920/model-trials'
    upscaler = None
    if args.enhance_model and args.phase == 'run':
        from overlay.video_enhance import LocalUpscaler
        upscaler = LocalUpscaler(args.enhance_model)
    failed = False
    for item in batch['items']:
        if item['number'] not in args.numbers:
            continue
        previous_output = root/f"{item['number']:02d}-{item['key']}"
        output = previous_output.with_name(previous_output.name+'-compact') if args.enhance_model else previous_output
        output.mkdir(parents=True, exist_ok=True)
        def status(phase, **extra):
            save(output/'status.json', {'number':item['number'], 'title':item['title'],
                 'phase':phase, 'updatedAt':datetime.now(timezone.utc).isoformat(), **extra})
            print(f"{item['number']:02d} {item['title']}: {phase}", flush=True)
        try:
            if item.get('sourceState') in ('locating','missing_raw_video'):
                raise ValueError('Clean source video is missing; no substitute selected')
            if (output/'verification.json').exists():
                status('awaiting_visual_review')
                continue
            status('preparing')
            battle = prepare_item(item, root, output, cache_gameplay=not args.enhance_model,
                                  prior_battle=previous_output/'battle' if args.enhance_model else None)
            status('prepared')
            if args.phase == 'prepare':
                continue
            previews(battle, output, root/'attacks',recording_top=160 if args.enhance_model else 0)
            if args.phase == 'preview':
                status('preflight_ready')
                continue
            if not upscaler:
                status('enhancing')
                enhance(output, trials)
            status('composing')
            render(battle, output, None if upscaler else output/'seed/gameplay',
                   victory_audio=Path(batch['victoryAudio']), attack_frames=root/'attacks', upscaler=upscaler)
            status('checking_media')
            verify(output)
            status('awaiting_visual_review')
        except Exception as error:
            failed = True
            status('failed', error=str(error))
            import traceback
            traceback.print_exc()
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
