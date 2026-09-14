"""Resume the three final episodes, serially, with durable stage and upload receipts."""
import json, os, subprocess, sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'
STATE = ROOT / 'data/local/final-production-status.json'
PY = sys.executable
LAST_THERMAL = 0
EPISODES = [('champi-warrior','Elite Champi Warrior','Incas','elite_champi_warrior_incas'),
            ('guecha-warrior','Elite Guecha Warrior','Muisca','elite_guecha_warrior_muisca'),
            ('temple-guard','Elite Temple Guard','Muisca','elite_temple_guard_muisca')]

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(p)
def status(key,stage,**extra):
    write(STATE,dict(subject=key,state=stage,pid=os.getpid(),updatedAt=time.time(),**extra))
    print(key,stage,flush=True)
def pause_check():
    global LAST_THERMAL
    if time.time()-LAST_THERMAL>=900:
        subprocess.run([PY,str(ROOT/'apps/video/thermal_guard.py')],check=True,stdout=subprocess.DEVNULL)
        LAST_THERMAL=time.time()
    while (ROOT/'data/local/thermal/PAUSED.json').exists() or read(ROOT/'data/video-production-queue.json').get('userPause',{}).get('state')=='PAUSED': time.sleep(15)
def run(script,*args):
    pause_check()
    child=subprocess.Popen([PY,'-u',str(ROOT/'apps/video'/script),*map(str,args)])
    while child.poll() is None:
        time.sleep(5);pause_check()
    if child.returncode:raise subprocess.CalledProcessError(child.returncode,child.args)
def running(pid):
    if not pid:return False
    import ctypes
    handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,int(pid))
    if handle:ctypes.windll.kernel32.CloseHandle(handle)
    return bool(handle)

def prepare(key,label,civ,slug,video,description,thumb,directory,statekey,title,synthetic):
    prep=directory/'youtube-upload-preparation.json'
    write(directory/'youtube-proposed-settings.json',dict(uploadAuthorized=True,title=title,
        descriptionFile=str(description),thumbnail=str(thumb),tags=['Age of Empires II','AoE2 DE',label,civ,'unit matchup','battle simulation'],
        categoryId='20',defaultLanguage='en',defaultAudioLanguage='en',privacyStatus='private',
        selfDeclaredMadeForKids=False,containsSyntheticMedia=synthetic,license='youtube',embeddable=True))
    write(prep,dict(uploadAuthorized=True,targetChannelVerified=True,targetChannel={'id':'UCKYN-pN4AZ3w4LpRxcdSciA','handle':'@aoe2matchup'},video=str(video)))
    queue=read(ROOT/'data/video-production-queue.json')
    approved=queue['correctedMedia'].setdefault('approvedUploadPreparations',[])
    if str(prep) not in approved:approved.append(str(prep))
    write(ROOT/'data/video-production-queue.json',queue)
    return dict(preparation=str(prep),stateKey=statekey)

def verify_transferred(key,items):
    """Remote processing may continue while the next local episode is built."""
    from upload_youtube import API,require
    from urllib.parse import urlencode
    api=API(ROOT/'data/local/youtube')
    local={read(ROOT/f'data/local/youtube/{x["stateKey"]}-upload-status.json')['videoId']:x for x in items}
    code,_,body=api.request('https://www.googleapis.com/youtube/v3/videos?'+urlencode({'part':'snippet,status,processingDetails,contentDetails','id':','.join(local)}))
    remote=require(code,body)['items'];assert len(remote)==len(items), 'An uploaded video is unavailable'
    complete=0
    for video in remote:
        assert video['snippet']['channelId']=='UCKYN-pN4AZ3w4LpRxcdSciA'
        phase=video.get('processingDetails',{}).get('processingStatus')
        assert phase not in ('failed','terminated'), 'YouTube could not process '+video['id']
        item=local[video['id']];statepath=ROOT/f'data/local/youtube/{item["stateKey"]}-upload-status.json'
        saved=read(statepath);saved.update(state='COMPLETE' if phase=='succeeded' else 'PROCESSING',processingStatus=phase,privacyStatus=video['status']['privacyStatus'])
        assert saved.get('thumbnailSet')
        write(statepath,saved);write(Path(item['preparation']).parent/'youtube-video-status.json',video)
        complete+=phase=='succeeded'
    receipt=LAB/f'compilations/{key}-unique-units/upload-completion.json'
    write(receipt,dict(state='COMPLETE' if complete==len(items) else 'PROCESSING',completed=complete,total=len(items),videos=[read(ROOT/f'data/local/youtube/{x["stateKey"]}-upload-status.json') for x in items]))
    queue=read(ROOT/'data/video-production-queue.json')
    for entries in [queue['episodes'],queue['followupQueue']['episodes']]:
        for episode in entries:
            if episode['key']==key:episode.update(status='complete' if complete==len(items) else 'uploaded_processing',verifiedYouTubeVideos=complete,verification=str(receipt))
    write(ROOT/'data/video-production-queue.json',queue)
    return complete

def main():
    target_videos = len(EPISODES) * 11
    for key,label,civ,slug in EPISODES:
        receipt=LAB/f'compilations/{key}-unique-units/upload-completion.json'
        if receipt.exists() and read(receipt).get('state')=='COMPLETE':continue
        if receipt.exists() and read(receipt).get('state')=='PROCESSING':
            verify_transferred(key,read(receipt.parent/'upload-manifest.json')['items']);continue
        comp=receipt.parent;intro=comp/'intro-v1';out=comp/'final-cost-v2'
        shorts=LAB/f'shorts/{key}-selected-10'
        overlay=LAB/f'campaigns/{key}-final-overlays/status.json'
        status(key,'INTRO')
        if not (intro/f'{key}-intro.mp4').exists():
            run('build_campaign_intro.py','--plan',f'apps/video/intro/{key}-cloned.json','--output',intro)
        run('build_campaign_thumbnail.py','--plan',f'apps/video/intro/{key}-cloned.json','--prefix',f'apps/video/intro/thumbnails/{key}','--title',label)
        status(key,'OVERLAYS')
        while overlay.exists() and read(overlay).get('state')=='RUNNING' and running(read(overlay).get('pid')):
            pause_check();time.sleep(20)
        if not overlay.exists() or read(overlay)['state']!='COMPLETE':
            run('render_campaign_overlays.py','--manifest',f'aoe2lab.overlays.{key}-final.json','--output',overlay.parent,'--workers','8','--recording-status',LAB/f'campaigns/{key}-canonical/status.json')
        assert read(overlay)['state']=='COMPLETE', 'Overlay failures require repair'
        status(key,'COMPILATION')
        if not (out/'manifest.json').exists():run(f'build_{key.replace("-","_")}_final.py')
        assert read(out/'manifest.json')['fullDecode']=='passed'
        status(key,'SHORTS')
        if not (shorts/'selection.json').exists():run(f'prepare_{key.replace("-","_")}_final_shorts.py')
        run('render_selected_shorts.py','--selection',shorts/'selection.json','--workers','8')
        assert read(shorts/'status.json')['state']=='COMPLETE'
        status(key,'READY_FOR_VISUAL_QA')
        while not (out/'visual-qa.json').exists():
            pause_check();time.sleep(20)
        assert read(out/'visual-qa.json')['passed']
        items=[prepare(key,label,civ,slug,Path(read(out/'manifest.json')['output']),out/'youtube-description.txt',ROOT/f'apps/video/intro/thumbnails/{key}-long.jpg',out/'youtube',key+'-full-cost-v2',f'{label} vs {read(out/"manifest.json")["matchups"]} Unique Units | AoE2 DE',True)]
        for x in read(shorts/'selection.json')['items']:
            target=Path(x['output']);desc=target/'youtube-description.txt'
            desc.write_text(f'{label} vs {x["unit"]} ({x["civ"]}) in Age of Empires II: Definitive Edition.\n\nEqual resources using civilization-specific Imperial costs per unit, with a 27-unit cap. Ranged units get a small front line of hussars against melee units.\n\nTry your own matchup: https://aoe2matchup.com/?civ1={civ}&unit1={slug}&age1=Imperial\n\n#Shorts #AoE2 #AoE2DE #RTS #BattleSimulation #UnitCounters\n',encoding='utf-8')
            title=f'{label} vs {x["unit"]} | AoE2 DE #Shorts'
            assert len(title)<=100
            items.append(prepare(key,label,civ,slug,target/'short.mp4',desc,ROOT/f'apps/video/intro/thumbnails/{key}-shorts.jpg',target/'youtube',f'{key}-short-{x["number"]:02}-cost-v2',title,False))
        write(comp/'upload-manifest.json',dict(items=items))
        for item in items:
            status(key,'UPLOADING',upload=item['stateKey'])
            statepath=ROOT/f'data/local/youtube/{item["stateKey"]}-upload-status.json'
            for attempt in range(4):
                try:run('upload_youtube.py','--preparation',item['preparation'],'--state-key',item['stateKey'],'--processing-wait-seconds','0')
                except subprocess.CalledProcessError:
                    if attempt==3:raise
                    time.sleep(30);continue
                if read(statepath)['state'] in ('COMPLETE','PROCESSING'):break
            assert read(statepath)['state'] in ('COMPLETE','PROCESSING'), 'YouTube upload incomplete'
        complete=verify_transferred(key,items)
        status(key,'COMPLETE' if complete==11 else 'UPLOADED_PROCESSING',completed=complete,total=11)
    deadline=time.time()+3600
    while True:
        pause_check();complete=0
        for key,*_ in EPISODES:
            comp=LAB/f'compilations/{key}-unique-units'
            if read(comp/'upload-completion.json')['state']=='COMPLETE':complete+=11
            else:complete+=verify_transferred(key,read(comp/'upload-manifest.json')['items'])
        if complete==target_videos:break
        status('all','YOUTUBE_PROCESSING',completed=complete,total=target_videos)
        assert time.time()<deadline, 'YouTube processing requires a later status check'
        time.sleep(20)
    status('all','COMPLETE',videos=target_videos)

if __name__=='__main__':
    import msvcrt
    lock=(ROOT/'data/local/final-production.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:main()
    except Exception:
        previous=read(STATE) if STATE.exists() else {}
        status(previous.get('subject'),'NEEDS_ATTENTION',error=traceback.format_exc())
        raise
