"""Wrap a vertical battle in animated bookends with cached or direct enhancement.

prepare: lossless, overlay-free camera crop for the standalone SeedVR2 CLI.
render: blend 75/25 enhanced/source gameplay and compose the floating battle HUD.
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from overlay.battle_camera import BattleCamera, reframe_enhanced
from overlay.battle_end import terminal_row
from overlay.ffutil import find_ffmpeg, find_ffprobe
from overlay.shorts_story import (AttackAnimation, split_reveal, winning_result,
                                 hp_label, result_backing, story_audio_filter,
                                 framed_panel, intro_unit_name, ending_frame_count, story_video_name,
                                 sweep_to_victory, sequential_intro_seconds)
from overlay.shorts_battle import BattleOverlay, GAME_Y
from overlay.civ_theme import theme_for
from overlay.static_stats import GAME, REPO
from build_champi_comparison_overlay import put, result_art, text_tile

W, H = 1080, 1920
INTRO, OPEN = 3.0, .6
GOLD = (205, 168, 100, 255)
BLUE, RED = (107, 163, 255, 255), (240, 115, 104, 255)
PAPER_INK = (63, 39, 24, 255)
BACKGROUND_ART = 'widgetui/textures/backgrounds/wide_default_background.dds'
FRAME_ART = 'widgetui/textures/menu/decoration/frame_bronze.png'
VS_ART = 'widgetui/textures/menu/icons/medal_rank_bronze.png'


def info(battle):
    manifest = json.loads((battle / 'manifest.json').read_text())
    return manifest, Path(manifest['source']), manifest['fps'], round(manifest['durationSeconds'] * manifest['fps'])


def prepare(battle, output):
    manifest, run, fps, frames = info(battle)
    output.mkdir(parents=True, exist_ok=True)
    camera = BattleCamera(json.loads((battle / 'camera.json').read_text())['keyframes'])
    cap = cv2.VideoCapture(str(run / 'battle.mp4'))
    start = manifest['trimStartSeconds']
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(start * fps))
    path = output / 'gameplay.mkv'
    cmd = [find_ffmpeg(), '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
           '-s', '1080x1080', '-r', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
           '-level', '3', '-threads', '4', '-pix_fmt', 'bgr0', str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for index in range(frames):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('Clean recording ended before approved battle trim')
            proc.stdin.write(camera.crop(frame, start + index / fps).tobytes())
        proc.stdin.close()
        if proc.wait():
            raise RuntimeError('Gameplay extraction failed')
    except BaseException:
        proc.kill(); proc.wait(); raise
    finally:
        cap.release()
    print(path, flush=True)


def attack_path(name):
    slug = name.lower().replace(' ', '_')
    return REPO / 'graphics/units' / slug / f'{slug}_attack_dir06_dat4x.gif'


def game_panel(size):
    # Original menu artwork: timber, iron hinges, weathered parchment and bronze.
    # Crop some exterior timber to give phone-sized labels enough paper width.
    with Image.open(GAME / BACKGROUND_ART) as source:
        background = source.convert('RGBA').crop((500,0,4620,2160))
        background = background.resize((1080,566), Image.Resampling.LANCZOS)
    with Image.open(GAME / FRAME_ART) as source:
        frame = source.convert('RGBA').resize((180,180), Image.Resampling.LANCZOS)
    return framed_panel(background, frame, size)


def paper_put(im, text, x, y, size, color=PAPER_INK):
    tile = text_tile(text, size, color, shadow=False)
    im.alpha_composite(tile, (round(x-tile.width/2), y))


def intro_unit_label(unit):
    theme = theme_for(GAME,unit['stats']['civ_name'])
    with Image.open(theme['emblemPath']) as source:
        emblem = source.convert('RGBA')
        emblem = emblem.crop(emblem.getbbox())
        emblem.thumbnail((70,70),Image.Resampling.LANCZOS)
    name = intro_unit_name(unit['unit'])
    text = text_tile(name,60,PAPER_INK,shadow=False)
    available = 920-emblem.width-18
    if text.width > available:
        text = text_tile(name,max(1,int(60*available/text.width)),PAPER_INK,shadow=False)
    label = Image.new('RGBA',(emblem.width+18+text.width,max(emblem.height,text.height)))
    label.alpha_composite(emblem,(0,(label.height-emblem.height)//2))
    label.alpha_composite(text,(emblem.width+18,(label.height-text.height)//2))
    return label


def intro_background(units):
    im = Image.new('RGBA', (W,H))
    panel = game_panel((W,H//2))
    im.alpha_composite(panel, (0,0))
    im.alpha_composite(panel, (0,H//2))
    paper_put(im, 'Who wins?', 540, 90, 78)
    for index, unit in enumerate(units):
        offset = 0 if index == 0 else 960
        label = intro_unit_label(unit)
        im.alpha_composite(label,((W-label.width)//2,780+offset if index == 0 else 710+offset))
    with Image.open(GAME / VS_ART) as source:
        badge = source.convert('RGBA')
        # Ignore nearly transparent atlas padding below the ribbonless medal.
        bounds = badge.getchannel('A').point(lambda alpha: 255 if alpha > 64 else 0).getbbox()
        badge = badge.crop(bounds).resize((190,190), Image.Resampling.LANCZOS)
    # Retain the actual bronze rim, with the same game parchment behind the text.
    parchment = panel.crop((490,400,590,500))
    circle = Image.new('L', parchment.size)
    ImageDraw.Draw(circle).ellipse((1,1,98,98), fill=255)
    parchment.putalpha(circle)
    badge.alpha_composite(parchment, (45,45))
    im.alpha_composite(badge, (445,865))
    paper_put(im, 'VS', 540, 933, 42)
    paper_put(im, 'aoe2matchup.com', 540, 1842, 26)
    return im


def paste_attack(im, tile, center):
    # Keep a stable sprite canvas across frames; never recrop each pose.
    x, y = center
    if 'nativeShadow' in tile.info:
        shadow, (sx, sy) = tile.info['nativeShadow']
        origin = (round(x-tile.width/2), round(y-tile.height/2))
        im.alpha_composite(shadow, (origin[0]+sx, origin[1]+sy))
        im.alpha_composite(tile, origin)
        return
    shadow = Image.new('RGBA', (430,90))
    ImageDraw.Draw(shadow).ellipse((30,20,400,60), fill=(0,0,0,130))
    shadow = shadow.filter(ImageFilter.GaussianBlur(13))
    im.alpha_composite(shadow, (round(x-215), round(y+tile.height/2-48)))
    im.alpha_composite(tile, (round(x-tile.width/2), round(y-tile.height/2)))


def intro_frame(opener, attacks, seconds, battle, *, intro_seconds=INTRO, speed=1,
                attack_starts=None, fps=60):
    im = opener.copy()
    for index,y in enumerate((515,1380)):
        start = attack_starts[index] if attack_starts is not None else 0
        tile = attacks[index].at(seconds-start,speed=speed,loop=attack_starts is None)
        paste_attack(im,tile,(540,y))
    progress = (seconds-(intro_seconds-OPEN))/(OPEN-1/fps)
    return split_reveal(im,battle,progress)


def ending_background(winner_unit, winner_index, hp_fraction, *, transparent=False):
    """Winner-only game-art screen: no battle stat cards or detailed footer."""
    end = Image.new('RGBA',(W,H))
    paper_put(end, winner_unit['stats']['civ_name'].upper(), 540, 90, 34,
              (49,65,75,255) if winner_index == 0 else (100,51,36,255))
    paper_put(end, winner_unit['unit'], 540, 155, 49)
    # result_art's '2' selects victory artwork, not the recording's winner owner.
    result = result_art(winner_unit['stats']['civ_name'], '2', 0, 4, backing=False).crop((0,0,640,246))
    result = result.resize((900,346), Image.Resampling.LANCZOS)
    end = result_backing(end, 882, 1326)
    end.alpha_composite(result, (90,775))
    put(end, hp_label(hp_fraction), 540, 1160, 54, GOLD, center=True)
    d = ImageDraw.Draw(end)
    d.rectangle((210,1260,869,1268), fill=(16,17,17,255))
    if hp_fraction > 0:
        d.rectangle((210,1260,210+round(660*hp_fraction)-1,1268),
                    fill=(92,113,127,255) if winner_index == 0 else (149,88,64,255))
    paper_put(end, 'Visit aoe2matchup.com', 540, 1570, 52)
    paper_put(end, 'for more simulations.', 540, 1650, 38)
    return end if transparent else Image.alpha_composite(game_panel((W,H)),end)


def enhance_battle_frame(recording, camera, time, upscaler):
    """Enhance the current camera crop once, before any overlays, at delivery size."""
    enhanced = upscaler(camera.crop(recording, time))
    return Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))


def render(battle, output, seed_frames=None, *, victory_audio, gameplay=None, attack_frames=None,
           enhanced_camera=None, upscaler=None, intro_seconds=INTRO, intro_attack_speed=1,
           intro_audio=None, exit_seconds=0, intro_attack_starts=None):
    manifest, run, fps, frames = info(battle)
    output.mkdir(parents=True, exist_ok=True)
    victory_probe = json.loads(subprocess.check_output([find_ffprobe(),'-v','error',
        '-show_entries','format=duration','-of','json',str(victory_audio)]))
    cue_seconds = float(victory_probe['format']['duration'])
    ending_frames = ending_frame_count(cue_seconds, fps)
    ending_seconds = ending_frames/fps
    exit_frames = round(exit_seconds*fps)
    exit_seconds = exit_frames/fps
    # Start the victory cue with the content fade when its native duration allows;
    # keep the full five-second hold after the transition instead of stealing it.
    victory_lead = min(exit_seconds/3, max(0,cue_seconds-ending_seconds))
    paths = sorted(seed_frames.glob('gameplay_*.png')) if seed_frames else []
    if upscaler is None and len(paths) != frames:
        raise ValueError(f'Expected {frames} enhanced frames, found {len(paths)}')
    units = json.loads((run / 'static-stats-overlay/stats.json').read_text())['units']
    rows = json.loads((run / 'unit-hp-overlay/units.json').read_text())['rows']
    plan = json.loads((run.parent.parent/'plan.json').read_text())
    overlay = BattleOverlay(units,rows,plan,GAME,start=manifest['trimStartSeconds'],
                            recording_top=160 if upscaler else 0)
    camera = BattleCamera(json.loads((battle/'camera.json').read_text())['keyframes'])
    cached_camera = BattleCamera(json.loads(enhanced_camera.read_text())['keyframes']) if enhanced_camera else None
    for index,card in enumerate(overlay.cards):
        card.save(output/f'stat-card-{index}.png')
    last = terminal_row(rows)
    outcome = winning_result(rows[0], last)
    winner_index = outcome['unitIndex']
    winner_unit = units[winner_index]
    hp_fraction = outcome['hpFraction']
    attacks = [AttackAnimation(attack_frames/unit['unit'].lower().replace(' ','_')
               if attack_frames else attack_path(unit['unit']), (580,510)) for unit in units]
    if intro_attack_starts is not None:
        intro_seconds = round(sequential_intro_seconds(attacks,intro_attack_starts,intro_attack_speed)*fps)/fps
    opener = intro_background(units)
    end = ending_background(winner_unit, winner_index, hp_fraction)
    ending_paper = game_panel((W,H)) if exit_frames else None
    ending_details = ending_background(winner_unit,winner_index,hp_fraction,transparent=True) if exit_frames else None
    clean_cap = None if upscaler else cv2.VideoCapture(str(gameplay or output / 'gameplay.mkv'))
    if clean_cap and (int(clean_cap.get(cv2.CAP_PROP_FRAME_COUNT)) != frames or abs(clean_cap.get(cv2.CAP_PROP_FPS)-fps) > .01):
        raise ValueError('Battle, clean crop and enhanced frames must have identical timing')
    recorded_cap = cv2.VideoCapture(str(run/'battle.mp4'))
    recorded_cap.set(cv2.CAP_PROP_POS_FRAMES,round(manifest['trimStartSeconds']*fps))
    last_battle = None
    def battle_frame(index):
        nonlocal last_battle
        ok_recorded, recording = recorded_cap.read()
        if not ok_recorded:
            raise RuntimeError('Battle input ended unexpectedly')
        seconds = index/fps
        time = manifest['trimStartSeconds']+seconds
        if upscaler:
            mixed = enhance_battle_frame(recording, camera, time, upscaler)
        else:
            ok_clean, clean = clean_cap.read()
            if not ok_clean:
                raise RuntimeError('Clean battle crop ended unexpectedly')
            if cached_camera:
                clean = camera.crop(recording, time)
            source = Image.fromarray(cv2.cvtColor(clean, cv2.COLOR_BGR2RGB))
            with Image.open(paths[index]) as enhanced:
                if enhanced.size != (2160,2160):
                    raise ValueError('This preset expects a true 1080-to-2160 2x enhancement')
                source = source.resize((2160,2160), Image.Resampling.LANCZOS)
                enhanced = enhanced.convert('RGB')
                if cached_camera:
                    enhanced = Image.fromarray(reframe_enhanced(np.array(enhanced), cached_camera.at(time),
                                                                camera.at(time), np.array(source)))
                mixed = Image.blend(source, enhanced, .75)
        last_battle = (mixed,seconds,recording,camera.at(time))
        return overlay.compose(mixed,seconds,recording=recording,
                               crop=camera.at(manifest['trimStartSeconds']+seconds))
    first = battle_frame(0)
    total_frames = frames + round(intro_seconds*fps) + exit_frames + ending_frames
    video = output / story_video_name([unit['unit'] for unit in units])
    source_probe = json.loads(subprocess.check_output([find_ffprobe(),'-v','error',
        '-show_entries','format=duration','-of','json',str(run/'battle.mp4')]))
    audio_filter = story_audio_filter(manifest['trimStartSeconds'],frames/fps,
                                     float(source_probe['format']['duration']),intro_seconds,ending_seconds+victory_lead,
                                     intro_label='3:a' if intro_audio else None,
                                     transition=exit_seconds-victory_lead)
    cmd = [find_ffmpeg(), '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{W}x{H}', '-r', str(fps), '-i', 'pipe:0',
           '-i', str(run/'battle.mp4'), '-i', str(victory_audio),
           *(['-i',str(intro_audio)] if intro_audio else []), '-filter_complex',
           audio_filter,
           '-map', '0:v', '-map', '[a]', '-t', str(total_frames/fps),
           '-c:v', 'libx264', '-threads', '4', '-preset', 'fast', '-crf', '17', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', str(video)]
    with (output/'render.log').open('w') as log:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log, stderr=log)
        def write(im):
            proc.stdin.write(im.convert('RGB').tobytes())
        try:
            for index in range(round(intro_seconds*fps)):
                t = index/fps
                im = intro_frame(opener,attacks,t,first,intro_seconds=intro_seconds,
                                 speed=intro_attack_speed,attack_starts=intro_attack_starts,fps=fps)
                if index in (0, round((intro_seconds-.3)*fps)):
                    im.convert('RGB').save(output/f'preview-intro-{index}.jpg', quality=95)
                write(im)
            for index in range(frames):
                im = first if index == 0 else battle_frame(index)
                write(im)
                if index in (0, round(.325*fps), round(.65*fps), frames//2, frames-1):
                    im.convert('RGB').save(output/f'preview-battle-{index}.jpg', quality=95)
                if index % 120 == 0:
                    print(f'Battle composed: {index+1}/{frames}', flush=True)
            for index in range(exit_frames):
                progress = index/(exit_frames-1)
                mixed,seconds,recording,crop = last_battle
                outgoing = overlay.compose(mixed,seconds,recording=recording,crop=crop,
                                           exit_progress=progress/.35)
                details = ending_details.copy()
                pose_time = max(0,index/fps-exit_seconds*2/3)
                paste_attack(details,attacks[winner_index].at(pose_time),(540,485))
                im = sweep_to_victory(outgoing,ending_paper,details,progress)
                if index in (0,exit_frames//4,exit_frames//2,3*exit_frames//4,exit_frames-1):
                    im.convert('RGB').save(output/f'preview-exit-{index}.jpg',quality=95)
                write(im)
            for index in range(ending_frames):
                im = end.copy()
                paste_attack(im, attacks[winner_index].at(exit_seconds/3+index/fps), (540,485))
                if index == 0:
                    im.convert('RGB').save(output/'preview-ending.jpg', quality=95)
                write(im)
            proc.stdin.close()
            if proc.wait():
                raise RuntimeError('Story encoding failed; see render.log')
        except BaseException:
            proc.kill(); proc.wait(); raise
        finally:
            if clean_cap:
                clean_cap.release()
            recorded_cap.release()
    (output/'story.json').write_text(json.dumps({
        'sourceBattle':str(battle.resolve()), 'cleanRun':str(run.resolve()), 'video':str(video.resolve()),
        'canvas':[W,H], 'fps':fps, 'frames':total_frames, 'durationSeconds':total_frames/fps,
        'introSeconds':intro_seconds, 'openingSeconds':OPEN, 'battleFrames':frames, 'endingSeconds':ending_seconds,
        'introAttackSpeed':intro_attack_speed, 'introAudio':str(intro_audio.resolve()) if intro_audio else None,
        'introAttackStarts':intro_attack_starts,
        'introAttackPlayback':'Once each; hold first/last pose' if intro_attack_starts is not None else 'Looping',
        'aftermathSeconds':manifest.get('aftermathSeconds',0),
        'exitTransition':{'seconds':exit_seconds,'startSeconds':intro_seconds+frames/fps,
                          'endingHoldStartSeconds':intro_seconds+frames/fps+exit_seconds,
                          'style':'Opposing card slide/fade; top-down game-art wipe; winner details fade in',
                          'battleUnderlay':'Last recorded aftermath frame, held only during transition'} if exit_frames else None,
        'featuredUnit':winner_unit['unit'], 'winnerOwner':outcome['owner'],
        'result':outcome['title'], 'survivors':outcome['survivors'], 'hp':outcome['hp'],
        'hpFraction':hp_fraction, 'hpLabel':hp_label(hp_fraction),
        'resultBackingOpacity':140/255,
        'bookendArtwork':{'background':str(GAME/BACKGROUND_ART), 'border':str(GAME/FRAME_ART),
                          'versusBadge':str(GAME/VS_ART), 'proceduralGradientsOrGlints':False},
        'attackFrames':str(attack_frames.resolve()) if attack_frames else 'Original GIF assets',
        'gameplayCache':None if upscaler else str((gameplay or output/'gameplay.mkv').resolve()),
        'enhancement':upscaler.metadata if upscaler else 'SeedVR2 7B Sharp, 1080->2160; 75% model/25% Lanczos source, then 1080 delivery',
        'enhancementPipeline':'Direct GPU enhancement at 1080 delivery size; no intermediate image sequence' if upscaler else 'Cached 2160 PNG frames',
        'enhancedFrames':str(seed_frames.resolve()) if seed_frames else None,
        'enhancedFramesCamera':str(enhanced_camera.resolve()) if enhanced_camera else str((battle/'camera.json').resolve()),
        'enhancementReframing':'World-coordinate reprojection; original pixels for any uncovered edge terrain' if cached_camera else None,
        'attackShadows':'Native game shadow layers, registered to each attack pose; no padded-canvas ellipse',
        'overlays':'Transparent verified HP queues; opposing 0.65s card slides; neutral fades capped at 15% opacity',
        'cards':overlay.card_details, 'cardEntranceSeconds':.65,
        'battleBackdrop':'Matching full recording under the same camera transform; genuine adjacent terrain, black beyond recording bounds',
        'backdropExcludedTopPixels':160 if upscaler else 0,
        'protectedBattleViewport':[0,GAME_Y,W,W],
        'framing':'Telemetry-guided camera; no HUD or cards inside protected viewport',
        'introLabels':[intro_unit_name(unit['unit']) for unit in units],
        'introCivilizations':'Emblem immediately before each single-line unit name',
        'victoryFooter':'Full-height game artwork; no stat cards or detailed footer',
        'victoryMessage':'Visit aoe2matchup.com for more simulations.',
        'victoryAudio':{'path':str(victory_audio.resolve()), 'sourceSeconds':cue_seconds,
                        'startSeconds':intro_seconds+frames/fps+exit_seconds-victory_lead,
                        'durationSeconds':ending_seconds+victory_lead,
                        'endFadeSeconds':.08},
        'audio':f'{"Dedicated intro track" if intro_audio else "Recorded soundtrack prelude; 150ms crossfade"}; combat aligned at {intro_seconds}s; dedicated victory cue at ending reveal',
        'audioFilter':audio_filter,
        'status':'preview_for_user_review'}, indent=2))
    print(video, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare','render'))
    parser.add_argument('--battle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed-frames', type=Path)
    parser.add_argument('--enhance-model', type=Path, help='Direct local model; bypasses Seed frames and clean-crop cache')
    parser.add_argument('--gameplay', type=Path, help='Reuse an existing clean gameplay.mkv cache')
    parser.add_argument('--attack-frames', type=Path, help='Lossless unit animation folders')
    parser.add_argument('--enhanced-camera', type=Path, help='Original camera.json when reframing cached enhanced pixels')
    parser.add_argument('--victory-audio', type=Path, help='Decoded game victory cue; ending lasts up to 5 seconds')
    parser.add_argument('--intro-seconds',type=float,default=INTRO,
                        help='Looping intro duration; one-shot intros instead end one second after the final attack')
    parser.add_argument('--intro-attack-speed',type=float,default=1)
    parser.add_argument('--intro-audio',type=Path,help='Dedicated intro audio, replacing the recording prelude')
    parser.add_argument('--intro-attack-starts',type=float,nargs=2,help='Two one-shot attack start times; each unit holds still outside its turn')
    parser.add_argument('--exit-seconds',type=float,default=0,help='Card exit, downward artwork wipe and victory fade before the full ending hold')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.battle, args.output)
    else:
        if args.seed_frames is None and args.enhance_model is None:
            parser.error('render requires --seed-frames or --enhance-model')
        if args.victory_audio is None:
            parser.error('render requires --victory-audio')
        upscaler = None
        if args.enhance_model:
            from overlay.video_enhance import LocalUpscaler
            upscaler = LocalUpscaler(args.enhance_model)
        render(args.battle, args.output, args.seed_frames, victory_audio=args.victory_audio,
               gameplay=args.gameplay, attack_frames=args.attack_frames,
               enhanced_camera=args.enhanced_camera, upscaler=upscaler,
               intro_seconds=args.intro_seconds,intro_attack_speed=args.intro_attack_speed,
               intro_audio=args.intro_audio,exit_seconds=args.exit_seconds,
               intro_attack_starts=args.intro_attack_starts)
