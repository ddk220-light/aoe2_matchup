"""Resumable local production, then explicitly authorized private upload."""
import argparse,concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
from aoe2x.lab.io import write_json
ROOT=Path(__file__).resolve().parents[2]
LAB=ROOT/'aoe2x/js_simulation/calibration/lab'
OUT=LAB/'flaming-camel-video-production'
CHANNEL={'id':'UCKYN-pN4AZ3w4LpRxcdSciA','handle':'@aoe2matchup'}
URL='https://aoe2matchup.com/?civ1=Tatars&age1=Imperial'

def call(script,*args,log_name=None):
    with (OUT/(log_name or Path(script).stem+'.log')).open('a',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-u',script,*map(str,args)],cwd=ROOT,check=True,stdout=log,stderr=log)

def prepare_uploads(include_full=True):
    full=LAB/'compilations/flaming-camel-unique-units/final'
    if include_full:
        media=json.loads((full/'manifest.json').read_text());assert media['fullDecode']=='passed' and media['matchups']==73
    selected=json.loads((LAB/'shorts/flaming-camel-selected-10/selection.json').read_text())['items']
    items=[]
    def add(key,video,title,desc,kind):
        assert video.is_file() and len(desc)<=5000 and len(title)<=100
        directory=video.parent/'youtube';directory.mkdir(exist_ok=True)
        description=directory/'youtube-description.txt';description.write_text(desc,encoding='utf-8')
        preparation=directory/'youtube-upload-preparation.json'
        # Upload response fields must survive retries.
        if not preparation.exists():write_json(preparation,{'uploadAuthorized':True,'targetChannelVerified':True,'targetChannel':CHANNEL,'video':str(video),'stateKey':key,'uploadScope':'Flaming Camel media prepared locally. Upload execution requires upload-approval.json recording existing user authorization.'})
        write_json(directory/'youtube-proposed-settings.json',{'uploadAuthorized':True,'channel':CHANNEL['handle'],'title':title,'descriptionFile':str(description),'categoryId':'20','defaultLanguage':'en','defaultAudioLanguage':'en','privacyStatus':'private','selfDeclaredMadeForKids':False,'containsSyntheticMedia':kind=='full','license':'youtube','embeddable':True,'tags':['AoE2','Age of Empires II Definitive Edition','Flaming Camel','Tatars','unit counters','equal resources','battle simulation','RTS'],'thumbnail':str(ROOT/'apps/video/intro/thumbnails'/('flaming-camel-long.jpg' if kind=='full' else 'flaming-camel-shorts.jpg'))})
        items.append({'key':key,'preparation':str(preparation),'title':title,'kind':kind,'subject':'Flaming Camel'})
    if include_full:add('flaming-camel-full',Path(media['output']),'Flaming Camel vs 73 Unique-Unit Matchups | AoE2 DE',(full/'youtube-description.txt').read_text(encoding='utf-8'),'full')
    for x in selected:
        directory=Path(x['output']);validation=json.loads((directory/'validation.json').read_text());assert validation['status']=='passed' and validation['fullDecode'] and validation['audio'] and validation['durationSeconds']<=180
        plan=json.loads((Path(x['run']).parent.parent/'plan.json').read_text())
        winner='Flaming Camel' if x['winner']==2 else x['unit'] if x['winner']==3 else 'Mutual elimination'
        desc=f"Flaming Camel vs {x['unit']} in Age of Empires II: Definitive Edition.\n\nEqual resources, maximum 27 units per main army. "
        desc+='No extra frontline buffer, including against ranged opponents. '
        desc+='Live per-unit HP overlays and original game audio. Whole-unit rounding applies.\n\n'
        desc+=f"Winner: {winner}. Remaining HP: {round(x['winnerHp'])}."+(' Missionary totals include converted units.' if x['unit']=='Missionary' else '')
        desc+=f'\n\nTry your own matchup:\n{URL}\n\n#Shorts #AoE2 #AoE2DE #FlamingCamel #Tatars #RTS #BattleSimulation #UnitCounters #StrategyGaming\n'
        add(f"flaming-camel-short-{x['number']:02}",directory/'short.mp4',f"Flaming Camel vs {x['unit']} | AoE2 DE #Shorts",desc,'short')
    batch=LAB/'youtube-batch-flaming-camel';batch.mkdir(exist_ok=True)
    manifest=batch/('manifest.json' if include_full else 'shorts-manifest.json')
    write_json(manifest,{'authorized':True,'title':'Flaming Camel uploads','targetChannel':CHANNEL,'items':items})
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument('--upload',action='store_true');a=p.parse_args();OUT.mkdir(exist_ok=True)
    import msvcrt
    lock=(OUT/'worker.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    state={'state':'WAITING_FOR_OVERLAYS','pid':os.getpid()}
    def save(label):state.update(state=label,updatedAt=time.time());write_json(OUT/'status.json',state);print(label,flush=True)
    try:
        save('WAITING_FOR_OVERLAYS')
        while True:
            if any((ROOT/'data/local/thermal'/name).exists() for name in ('PAUSED.json','SETUP_PENDING.json')):
                save('WAITING_FOR_THERMAL_CLEARANCE');time.sleep(30);continue
            overlays=json.loads((LAB/'campaigns/flaming-camel-all-unique-overlays/status.json').read_text())
            if overlays['state']=='COMPLETE':break
            if overlays['state']=='NEEDS_ATTENTION':
                # Retry only failed jobs. Successful artifacts remain cached;
                # recovered alignments and the dense fallback are reused.
                time.sleep(2)
                call('apps/video/render_campaign_overlays.py','--manifest',ROOT/'aoe2lab.recorder.flaming-camel-all-unique.toml','--output',LAB/'campaigns/flaming-camel-all-unique-overlays','--workers','1','--recording-status',LAB/'campaigns/flaming-camel-all-unique/status.json',log_name='overlay-recovery.log')
                retried=json.loads((LAB/'campaigns/flaming-camel-all-unique-overlays/status.json').read_text())
                if retried['state']!='COMPLETE':raise RuntimeError('Overlay timing failures need review before compilation; see campaign overlay status.')
                break
            time.sleep(30)
        save('SELECTING_SHORTS');call('apps/video/prepare_flaming_camel_shorts.py')
        intro=LAB/'compilations/flaming-camel-unique-units/intro-v1/flaming-camel-intro.mp4'
        from overlay.ffutil import find_ffprobe
        for attempt in range(120):
            result=subprocess.run([find_ffprobe(),'-v','error','-show_entries','format=duration','-of','json',str(intro)],capture_output=True)
            if result.returncode==0 and json.loads(result.stdout).get('format',{}).get('duration'):break
            time.sleep(10)
        else:raise RuntimeError('Intro render did not finish')
        save('RENDERING_FULL_AND_SHORTS')
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            tasks=[]
            if not (LAB/'compilations/flaming-camel-unique-units/final/manifest.json').exists():tasks.append(pool.submit(call,'apps/video/build_flaming_camel_compilation.py'))
            tasks.append(pool.submit(call,'apps/video/render_selected_shorts.py','--selection',LAB/'shorts/flaming-camel-selected-10/selection.json','--workers','1'))
            for task in tasks:task.result()
        batch=prepare_uploads();state['uploadManifest']=str(batch);save('READY_FOR_VISUAL_QA')
        if a.upload:
            approval=json.loads((OUT/'upload-approval.json').read_text());assert approval.get('authorized') is True,'Saved user upload authorization required'
            qa=json.loads((OUT/'visual-qa.json').read_text());assert qa['status']=='passed','Review representative intro/overlay/Shorts frames first'
            save('UPLOADING');call('apps/video/upload_youtube_batch.py',batch);call('apps/video/check_youtube_batch.py',batch)
            verification=json.loads((batch.parent/'verification.json').read_text());state['verification']=verification
            assert len(verification)==11 and all(v['processing']=='succeeded' and all(v[k] for k in ('thumbnail','channelMatches','titleMatches','descriptionMatches')) for v in verification),'Uploads require further processing or metadata review'
            save('COMPLETE')
    except Exception as e:
        state['error']=repr(e);save('NEEDS_ATTENTION');raise
if __name__=='__main__':main()
