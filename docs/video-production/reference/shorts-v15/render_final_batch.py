"""Finalize the planned ten v15 Shorts, reusing approved composited combat."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw
import run_batch
from build_story_batch import read, save, verify
from build_story_short import intro_background, intro_frame, ending_background, game_panel, paste_attack
from overlay.battle_camera import BattleCamera
from overlay.shorts_battle import BattleOverlay
from overlay.shorts_story import AttackAnimation, sequential_intro_seconds, story_audio_filter, sweep_to_victory
from overlay.ffutil import find_ffmpeg
from overlay.static_stats import GAME

ROOT = Path(__file__).resolve().parent
DEST = ROOT/'final-v15'
MODEL = ROOT.parent/'video-recreate-blackwood-20260920/realesr-general-x4v3.pth'


def splice_video_filter(intro_frames, old_intro_frames, battle_frames):
    return ('[0:v]split=2[newintro][newtail];'
            f'[newintro]trim=end_frame={intro_frames},setpts=PTS-STARTPTS[intro];'
            f'[newtail]trim=start_frame={intro_frames},setpts=PTS-STARTPTS[tail];'
            f'[1:v]trim=start_frame={old_intro_frames}:end_frame={old_intro_frames+battle_frames},'
            'setpts=PTS-STARTPTS[battle];'
            '[intro][battle][tail]concat=n=3:v=1:a=0[v]')


def previous_folder(item):
    base = ROOT/f"{item['number']:02d}-{item['key']}"
    return base.with_name(base.name+'-fixed') if item['number']==3 else base if item['number']==4 else base.with_name(base.name+'-compact')


def pcm(path):
    return np.frombuffer(subprocess.check_output([find_ffmpeg(),'-v','error','-i',str(path),
        '-vn','-ac','1','-ar','48000','-f','f32le','pipe:1']),dtype='<f4')


def prepare_voices(out, units, attacks, fps):
    catalog = read(DEST/'voices/catalog.json')
    selected = catalog if isinstance(catalog,list) else catalog['selected']
    spoken_candidates = read(DEST/'voices/editorial-candidates.json')
    speed = 1.5
    prepared = []
    for index,unit in enumerate(units):
        voice = next(v for v in selected if v['unit']==unit['unit'] and v['civilization']==unit['stats']['civ_name'])
        if voice.get('spoken') is False:
            voice = next(v for v in spoken_candidates if v['unit']==unit['unit'] and v['civilization']==unit['stats']['civ_name'])
            voice = {**voice,'candidateOnly':False,'spoken':True,
                     'selectionApproval':'User chose same-civilization spoken attack line on 2026-09-22'}
        samples = pcm(voice['wav'])
        onset = int(np.flatnonzero(abs(samples)>float(abs(samples).max())*.02)[0])/48000
        silence_trim = max(0,onset-.012) if onset>.05 else 0
        samples = samples[round(silence_trim*48000):]
        gain = float(10**(-6/20)/np.max(abs(samples)))
        tail_trim = 0
        if len(samples)/48000 > attacks[index].ends[-1]/1000/speed:
            audible_end = int(np.flatnonzero(abs(samples)>float(abs(samples).max())*.02)[-1])+1
            if (len(samples)-audible_end)/48000 > .05:
                keep = min(len(samples),audible_end+round(.012*48000))
                tail_trim = (len(samples)-keep)/48000
                samples = samples[:keep]
        prepared.append((voice,samples,silence_trim,gain,tail_trim))
    turn_lengths = [max(a.ends[-1]/1000/speed,len(p[1])/48000) for a,p in zip(attacks,prepared)]
    starts = [.25,.25+turn_lengths[0]+.2]
    intro_frames = round((starts[1]+turn_lengths[1]+1)*fps)
    seconds = intro_frames/fps
    command = [find_ffmpeg(),'-y','-v','error','-f','lavfi','-i',f'anullsrc=r=48000:cl=stereo:d={seconds}']
    filters, cues = [], []
    for index,(voice,samples,silence_trim,gain,tail_trim) in enumerate(prepared):
        start = starts[index]
        end = start+attacks[index].ends[-1]/1000/speed
        assert start+len(samples)/48000 <= (starts[1] if index==0 else seconds-.6), (voice['unit'],'Voice extends past its turn')
        command += ['-i',voice['wav']]
        filters.append(f'[{index+1}:a]atrim=start={silence_trim}:end={silence_trim+len(samples)/48000},aresample=48000,asetpts=PTS-STARTPTS,volume={gain},'
                       f'adelay={round(start*48000)}S:all=1[v{index}]')
        cues.append({**voice,'animationStartSeconds':start,'animationEndSeconds':end,
                     'turnEndSeconds':start+turn_lengths[index],
                     'poseHoldForVoiceSeconds':turn_lengths[index]-attacks[index].ends[-1]/1000/speed,
                     'startSeconds':start,'gain':gain,'playedOnce':True,
                     'rawDurationSeconds':voice['durationSeconds'],'durationSeconds':len(samples)/48000,
                     'leadingSilenceTrimSeconds':silence_trim,'trailingSilenceTrimSeconds':tail_trim})
    filters.append('[0:a][v0][v1]amix=inputs=3:duration=first:normalize=0[intro]')
    path = out/'intro-command-voices.wav'
    subprocess.run(command+['-filter_complex',';'.join(filters),'-map','[intro]',
        '-ar','48000','-c:a','pcm_s16le',str(path)],check=True)
    save(out/'voice-provenance.json',{'source':'Installed unit attack-command events and civilization switches',
         'cues':cues,'introSeconds':seconds,'voiceSpeed':1,'music':None,'weaponEffects':False,
         'selection':'Longest measured spoken attack variant; user-approved same-civilization speech for non-speaking mounted units',
         'sequence':'One attack cycle and simultaneous voice per unit; hold pose if speech lasts longer; 0.2s handoff; battle one second after final turn'})
    return path, starts, seconds


def compose(item, upscaler):
    started = time.perf_counter()
    out = DEST/f"{item['number']:02d}-{item['key']}"
    out.mkdir(parents=True,exist_ok=True)
    old = previous_folder(item)
    story = read(old/'story.json')
    previous_video = Path(story['video'])
    battle = Path(story['sourceBattle'])
    manifest = read(battle/'manifest.json')
    run, fps = Path(story['cleanRun']),story['fps']
    units = read(run/'static-stats-overlay/stats.json')['units']
    rows = read(run/'unit-hp-overlay/units.json')['rows']
    plan = read(run.parent.parent/'plan.json')
    attacks = [AttackAnimation(ROOT/'attacks'/u['unit'].lower().replace(' ','_'),(580,510)) for u in units]
    intro_audio, starts, intro_seconds = prepare_voices(out,units,attacks,fps)
    intro_frames, old_intro_frames = round(intro_seconds*fps),round(story['introSeconds']*fps)
    combat_frames = story['battleFrames']
    aftermath_frames, exit_frames, ending_frames = round(2*fps),round(1.2*fps),round(5*fps)
    battle_frames = combat_frames+aftermath_frames
    total_frames = intro_frames+battle_frames+exit_frames+ending_frames
    camera = BattleCamera(read(battle/'camera.json')['keyframes'])
    overlay = BattleOverlay(units,rows,plan,GAME,start=manifest['trimStartSeconds'],
                            recording_top=160)
    raw_cap = cv2.VideoCapture(str(run/'battle.mp4'))
    tail_start = round(manifest['trimStartSeconds']*fps)+combat_frames
    assert tail_start+aftermath_frames <= int(raw_cap.get(cv2.CAP_PROP_FRAME_COUNT))
    raw_cap.set(cv2.CAP_PROP_POS_FRAMES,tail_start)
    cached = cv2.VideoCapture(str(previous_video))
    cached.set(cv2.CAP_PROP_POS_FRAMES,old_intro_frames)
    ok, first = cached.read()
    cached.release()
    assert ok
    first = Image.fromarray(cv2.cvtColor(first,cv2.COLOR_BGR2RGB)).convert('RGBA')
    opener = intro_background(units)
    winner = 0 if story['winnerOwner']=='2' else 1
    end = ending_background(units[winner],winner,story['hpFraction'])
    paper = game_panel((1080,1920))
    details_base = ending_background(units[winner],winner,story['hpFraction'],transparent=True)
    video = out/f"{item['number']:02d}-{item['key']}-Short-v15.mp4"
    source_victory = Path(read(ROOT/'batch.json')['victoryAudio'])
    victory = DEST/'victory-at-70-percent.wav'
    if not victory.exists():
        subprocess.run([find_ffmpeg(),'-y','-v','error','-i',str(source_victory),'-af','volume=0.7',
            '-ar','48000','-c:a','pcm_s16le',str(victory)],check=True)
    audio_filter = story_audio_filter(manifest['trimStartSeconds'],battle_frames/fps,0,
        intro=intro_seconds,ending=5.4,input_label='2:a',victory_label='3:a',intro_label='4:a',transition=.8)
    video_filter = splice_video_filter(intro_frames,old_intro_frames,combat_frames)
    command = [find_ffmpeg(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920',
        '-r',str(fps),'-i','pipe:0','-i',str(previous_video),'-i',str(run/'battle.mp4'),
        '-i',str(victory),'-i',str(intro_audio),'-filter_complex',video_filter+';'+audio_filter,
        '-map','[v]','-map','[a]','-t',str(total_frames/fps),'-c:v','libx264','-threads','4',
        '-preset','fast','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000',
        '-movflags','+faststart',str(video)]
    print(f"{item['number']:02d} composing {item['title']}: dynamic intro {intro_seconds:.3f}s, reused combat {combat_frames/fps:.2f}s",flush=True)
    with (out/'render.log').open('w') as log:
        proc = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=log)
        def write(frame):
            proc.stdin.write(frame.convert('RGB').tobytes())
        try:
            for index in range(intro_frames):
                write(intro_frame(opener,attacks,index/fps,first,intro_seconds=intro_seconds,
                                  speed=1.5,attack_starts=starts,fps=fps))
            for index in range(aftermath_frames):
                ok, recording = raw_cap.read()
                assert ok
                seconds = (combat_frames+index)/fps
                source_time = manifest['trimStartSeconds']+seconds
                crop = camera.at(source_time)
                mixed = Image.fromarray(cv2.cvtColor(upscaler(camera.crop(recording,source_time)),cv2.COLOR_BGR2RGB))
                write(overlay.compose(mixed,seconds,recording=recording,crop=crop))
            raw_cap.release()
            for index in range(exit_frames):
                progress = index/(exit_frames-1)
                outgoing = overlay.compose(mixed,seconds,recording=recording,crop=crop,exit_progress=progress/.35)
                details = details_base.copy()
                paste_attack(details,attacks[winner].at(max(0,index/fps-.8)),(540,485))
                write(sweep_to_victory(outgoing,paper,details,progress))
            for index in range(ending_frames):
                frame = end.copy()
                paste_attack(frame,attacks[winner].at(.4+index/fps),(540,485))
                write(frame)
            proc.stdin.close()
            if proc.wait():
                raise RuntimeError(f'Encoder failed: {out}/render.log')
        except BaseException:
            proc.kill(); proc.wait(); raw_cap.release(); raise
    new_battle = out/'battle'
    manifest.update(durationSeconds=battle_frames/fps,aftermathSeconds=2)
    save(new_battle/'manifest.json',manifest)
    shutil.copy2(battle/'camera.json',new_battle/'camera.json')
    story.update(video=str(video),sourceBattle=str(new_battle),fps=fps,frames=total_frames,
        durationSeconds=total_frames/fps,introSeconds=intro_seconds,openingSeconds=.6,
        introAttackSpeed=1.5,introAttackStarts=starts,introAttackPlayback='Once each; hold first/last pose',
        introAudio=str(intro_audio),introAudioProvenance=str(out/'voice-provenance.json'),
        battleFrames=battle_frames,aftermathSeconds=2,endingSeconds=5,
        exitTransition={'seconds':1.2,'startSeconds':intro_seconds+battle_frames/fps,
                        'endingHoldStartSeconds':intro_seconds+battle_frames/fps+1.2,
                        'style':'Opposing card slide/fade; top-down game-art wipe; winner details fade in',
                        'battleUnderlay':'Last real aftermath frame held only during transition'},
        victoryAudio={'path':str(victory),'originalPath':str(source_victory),'sourceSeconds':5.5,
                      'startSeconds':intro_seconds+battle_frames/fps+.8,'durationSeconds':5.4,
                      'endFadeSeconds':.08,'gain':.7},
        audio='Native command voices with one-shot attacks; original battle audio; victory at 70%',
        audioFilter=audio_filter,videoFilter=video_filter,
        reusedBattle={'video':str(previous_video),'startFrame':old_intro_frames,'frames':combat_frames,
                      'note':'Previously approved composited battle; no GPU rerender of combat'},
        aftermathEnhancement=upscaler.metadata,
        aftermathBackdropExcludedTopPixels=160,
        attackShadows='Pose-matched native game shadows; no generic ellipse',
        status='preview_for_user_review',approvedWorkflow='docs/video-production/SHORTS_APPROVED_WORKFLOW.md')
    save(out/'story.json',story)
    verify(out)
    audit(out)
    save(out/'timing.json',{'elapsedSeconds':time.perf_counter()-started,
        'scope':'New bookends and recorded aftermath; cached combat spliced; media verification and audit'})
    return out


def audit(out):
    story = read(out/'story.json')
    cues = read(out/'voice-provenance.json')['cues']
    fps = story['fps']
    first_turn_end = cues[0].get('turnEndSeconds',cues[0]['animationEndSeconds'])
    last_turn_end = cues[1].get('turnEndSeconds',cues[1]['animationEndSeconds'])
    assert abs(cues[1]['animationStartSeconds']-first_turn_end-.2)<1/fps
    assert abs(story['introSeconds']-last_turn_end-1)<1/fps
    decoded = pcm(story['video'])
    onsets, audible_ends = [], []
    for cue in cues:
        start = cue['startSeconds']
        segment = decoded[round(start*48000):round((start+cue['durationSeconds'])*48000)]
        onset = int(np.flatnonzero(abs(segment)>float(abs(segment).max())*.02)[0])/48000
        assert onset<.05,(cue['unit'],onset)
        onsets.append(onset)
        audible_ends.append(start+(int(np.flatnonzero(abs(segment)>float(abs(segment).max())*.02)[-1])+1)/48000)
    voice_handoff = cues[1]['animationStartSeconds']-audible_ends[0]
    if cues[0]['durationSeconds'] > cues[0]['animationEndSeconds']-cues[0]['animationStartSeconds']:
        assert .18 <= voice_handoff <= .24,voice_handoff
    original = pcm(story['victoryAudio'].get('originalPath',story['victoryAudio']['path']))
    vs = story['victoryAudio']['startSeconds']
    actual = decoded[round((vs+.2)*48000):round((vs+5)*48000)]
    expected = original[9600:240000]
    ratio = float(np.sqrt(np.mean(actual**2)/np.mean(expected**2)))
    assert abs(ratio-.7)<.015,ratio
    cap = cv2.VideoCapture(story['video'])
    reused_errors = []
    if 'reusedBattle' in story:
        previous = cv2.VideoCapture(story['reusedBattle']['video'])
        count = story['reusedBattle']['frames']
        for index in (0,count//2,count-1):
            previous.set(cv2.CAP_PROP_POS_FRAMES,story['reusedBattle']['startFrame']+index)
            cap.set(cv2.CAP_PROP_POS_FRAMES,round(story['introSeconds']*fps)+index)
            ok_a,a = previous.read(); ok_b,b = cap.read()
            assert ok_a and ok_b
            error = float(np.abs(a.astype(float)-b.astype(float)).mean())
            assert error<3,(index,error)
            reused_errors.append(error)
        previous.release()
    ending_start = story['exitTransition']['endingHoldStartSeconds']
    assert story['frames']-round(ending_start*fps)==round(5*fps)
    times = (0,story['introSeconds']-.3,story['introSeconds']+.7,
             story['introSeconds']+(story['battleFrames']/fps-2)*.5,
             story['exitTransition']['startSeconds']-2.05,
             story['exitTransition']['startSeconds']-.05,
             ending_start-.5,story['durationSeconds']-.1)
    sheet = Image.new('RGB',(1080,1004))
    for i,t in enumerate(times):
        cap.set(cv2.CAP_PROP_POS_FRAMES,min(story['frames']-1,round(t*fps)))
        ok, frame = cap.read(); assert ok
        picture = Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)).resize((270,480),Image.Resampling.LANCZOS)
        x,y=i%4*270,i//4*502
        sheet.paste(picture,(x,y+22))
        ImageDraw.Draw(sheet).text((x+8,y+4),f'{t:.2f}s',fill='white')
    sheet.save(out/'review-sheet.jpg',quality=95)
    cap.release()
    save(out/'timing-audit.json',{'introHandoffSeconds':cues[1]['animationStartSeconds']-first_turn_end,
        'finalTurnToBattleSeconds':story['introSeconds']-last_turn_end,
        'finalAnimationToBattleSeconds':story['introSeconds']-cues[1]['animationEndSeconds'],
        'battleStartSeconds':story['introSeconds'],'voiceOnsetsSeconds':onsets,
        'firstVoiceAudibleEndToNextAnimationSeconds':voice_handoff,
        'victoryAmplitudeRatio':ratio,'endingFrames':300,'aftermathFrames':120,
        'reusedBattleMeanEncodingErrors':reused_errors,
        'visualReview':'Pending actual contact sheet inspection'})
    print(f"VERIFIED {out.name}: {story['durationSeconds']:.2f}s; victory gain measured {ratio:.3f}",flush=True)


def copy_approved(item):
    source = ROOT/'command-voice-preview/10-grenadier-vs-huskarl-v15'
    out = DEST/f"{item['number']:02d}-{item['key']}"
    out.mkdir(parents=True,exist_ok=True)
    story = read(source/'story.json')
    video = out/f"{item['number']:02d}-{item['key']}-Short-v15.mp4"
    shutil.copy2(story['video'],video)
    shutil.copy2(source/'voice-provenance.json',out/'voice-provenance.json')
    story.update(video=str(video),introAudioProvenance=str(out/'voice-provenance.json'),
                 retainedApprovedExport=str(source))
    save(out/'story.json',story)
    verify(out)
    assert read(out/'verification.json')['sha256']==read(source/'verification.json')['sha256']
    audit(out)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--numbers',type=int,nargs='+',required=True)
    args = parser.parse_args()
    DEST.mkdir(parents=True,exist_ok=True)
    from overlay.video_enhance import LocalUpscaler
    upscaler = None
    for item in read(ROOT/'batch.json')['items']:
        if item['number'] not in args.numbers:
            continue
        out = DEST/f"{item['number']:02d}-{item['key']}"
        if (out/'timing-audit.json').exists() and read(out/'story.json').get('status')!='held_for_user_audio_choice':
            print('Already verified:',out.name,flush=True)
            continue
        save(DEST/'status.json',{'phase':'rendering','active':item['number'],'title':item['title'],
            'updatedAt':datetime.now(timezone.utc).isoformat()})
        if item['number']==10:
            copy_approved(item)
        else:
            if upscaler is None:
                upscaler = LocalUpscaler(MODEL)
            compose(item,upscaler)
    save(DEST/'status.json',{'phase':'awaiting_visual_review','active':None,'requested':args.numbers,
        'updatedAt':datetime.now(timezone.utc).isoformat()})


if __name__=='__main__':
    main()
