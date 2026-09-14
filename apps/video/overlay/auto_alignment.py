"""Estimate archived video/game alignment from visible colored HP bars.

Evidence and fit quality are persisted; ambiguous fits require review.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from overlay.unit_timeline import decode


def visible_bars(frame, compact=False, color_components=False):
    dark = (np.max(frame, axis=2) < 65).astype('uint8') * 255
    contours, _ = cv2.findContours(dark, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    result = []
    for contour in contours:
        x,y,w,h = cv2.boundingRect(contour)
        if not ((68 <= w <= 72 or (compact and 52 <= w <= 56)) and 10 <= h <= 13):
            continue
        region = frame[y+2:y+h-2,x+2:x+w-2].astype(float)
        b,g,r = cv2.split(region)
        masks = [(b>100)&(b>r*1.6)&(g>r*1.3), (r>100)&(r>g*1.6)&(r>b*1.6)]
        for owner,mask in zip(('2','3'), masks):
            length = int((mask.sum(axis=0) >= 3).sum())
            if 3 <= length <= w-7:
                result.append({'owner':owner,'fraction':length/(w-4),'x':x,'y':y})
    # A health bar's black outline can touch a dark unit sprite, merging the
    # contour. Its colored fill remains a separate rectangular component.
    if color_components:
        b,g,r=cv2.split(frame.astype(float))
        masks=[(b>100)&(b>r*1.6)&(g>r*1.3),(r>100)&(r>g*1.6)&(r>b*1.6)]
        for owner,mask in zip(('2','3'),masks):
            count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),8)
            for x,y,w,h,area in stats[1:]:
                if not (3<=w<=65 and 5<=h<=9 and area>=w*h*.88):continue
                left,top=int(x)-2,int(y)-2
                region=frame[top:top+int(h)+4,left:left+70]
                if region.shape[:2]!=(int(h)+4,70):continue
                black=np.max(region,axis=2)<65
                if min(black[:2,:].mean(),black[-2:,:].mean(),black[:,:2].mean(),black[:,-2:].mean())<.8:continue
                if any(v['owner']==owner and abs(v['x']-left)<5 and abs(v['y']-top)<5 for v in result):continue
                result.append({'owner':owner,'fraction':float(w/66),'x':left,'y':top,'detector':'colored fill with verified rectangular black border'})
    return result


def anchor_matches(speed, offset, anchors):
    return all(a['videoMinSeconds'] <= a['gameSeconds'] / speed + offset <= a['videoMaxSeconds']
               for a in anchors)


def align(run, recheck=False, sample_rate=3, compact=False, color_components=False, anchors_path=None):
    run = Path(run)
    out = run/'unit-hp-overlay'; out.mkdir(exist_ok=True)
    destination = out/'alignment.json'
    existing=json.loads(destination.read_text()) if destination.exists() else None
    if existing and not recheck:
        return json.loads(destination.read_text())
    video_hash=json.loads((run/'recording.json').read_text())['files']['battleVideo']['sha256']
    anchors_document=json.loads(Path(anchors_path).read_text()) if anchors_path else None
    anchors=anchors_document['anchors'] if anchors_document else []
    if anchors_document and anchors_document.get('videoSha256') != video_hash:
        raise ValueError('Timing anchors belong to a different video')
    data = decode(run)
    rows = data['rows']; times=np.array([r['gameMs']/1000 for r in rows])
    capture=cv2.VideoCapture(str(run/'battle.mp4'))
    fps=capture.get(cv2.CAP_PROP_FPS); n=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    samples=[]
    # Sequential decoding keeps this inexpensive and makes sample timestamps exact.
    stride=max(1,round(fps/sample_rate))
    for index in range(n):
        ok= capture.grab()
        if not ok: break
        if index % stride: continue
        ok,frame=capture.retrieve()
        if ok:
            bars=visible_bars(frame, compact=compact, color_components=color_components)
            if bars: samples.append({'videoSeconds':index/fps,'bars':bars})
    capture.release()
    fractions={owner:[np.array([u['hp']/max(1,u['maxHp']) for u in row['sides'][owner] if u['hp']>0])
                      for row in rows] for owner in ('2','3')}
    def score(speed,offset,parity=None):
        errors=[]
        for i,sample in enumerate(samples):
            if parity is not None and i%2 != parity: continue
            game=(sample['videoSeconds']-offset)*speed
            index=int(np.searchsorted(times,game,side='right'))-1
            for bar in sample['bars']:
                candidates=fractions[bar['owner']][max(0,min(index,len(rows)-1))]
                errors.append(min(.25,float(np.min(np.abs(candidates-bar['fraction'])))) if len(candidates) else .25)
        return float(np.mean(np.square(errors))) if errors else 1
    fits=sorted((score(speed,offset),speed,float(offset)) for speed in (1.7,2.0)
                for offset in np.arange(-4,2.01,.05) if anchor_matches(speed,offset,anchors))
    if not fits:
        raise ValueError('No timing fit satisfies the measured video event anchors')
    _,speed,offset=fits[0]
    fine=sorted((score(speed,o),speed,float(o)) for o in np.arange(offset-.08,offset+.081,1/fps)
                if anchor_matches(speed,o,anchors))
    best,speed,offset=fine[0]
    rivals=[s for s,v,o in fits if abs(o-offset)>.3 or v!=speed]
    quality={'samples':len(samples),'bars':sum(len(s['bars']) for s in samples),
             'rmsFractionError':best**.5,'alternativeErrorRatio':min(rivals)/max(best,1e-8) if rivals else 0}
    result={'videoSha256':json.loads((run/'recording.json').read_text())['files']['battleVideo']['sha256'],
            'gameSpeed':speed,'videoOffsetSeconds':offset,'method':'visible HP bar fractions matched to archived per-unit state',
            'quality':quality,'evidence':samples,'sampleRate':sample_rate,'compactBars':compact,'colorComponents':color_components}
    if anchors_document:
        result['eventAnchors']=anchors_document
    (out/'alignment-candidate.json').write_text(json.dumps(result,indent=2))
    if quality['bars']<30 or quality['rmsFractionError']>.045 or quality['alternativeErrorRatio']<1.4:
        raise ValueError('Ambiguous HP/video alignment; inspect alignment-candidate.json: '+str(quality))
    result['verifiedBy']='automated multi-observation HP alignment'
    if existing:
        result['existingOffsetDifferenceSeconds']=offset-existing['videoOffsetSeconds']
        if speed!=existing['gameSpeed'] or abs(result['existingOffsetDifferenceSeconds'])>2/fps:
            raise ValueError('Automated alignment disagrees with the existing measured anchor: '+str(result['existingOffsetDifferenceSeconds']))
    else:
        destination.write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);parser.add_argument('--recheck',action='store_true')
    parser.add_argument('--sample-rate',type=float,default=3)
    parser.add_argument('--compact-bars',action='store_true',help='Also detect the shorter siege-unit HP bars')
    parser.add_argument('--color-components',action='store_true',help='Recover HP bars whose black outline touches a sprite')
    parser.add_argument('--anchors',type=Path,help='Reviewed game/video event intervals, bound to this video hash')
    args=parser.parse_args()
    try:
        result=align(args.run,args.recheck,args.sample_rate,args.compact_bars,args.color_components,args.anchors)
    except ValueError as error:
        if 'Ambiguous HP/video alignment' not in str(error) or args.sample_rate>3 or args.color_components:raise
        candidate=args.run/'unit-hp-overlay/alignment-candidate.json'
        candidate.with_name('alignment-initial-candidate.json').write_bytes(candidate.read_bytes())
        result=align(args.run,args.recheck,6,args.compact_bars,True,args.anchors)
    print(json.dumps({k:v for k,v in result.items() if k!='evidence'},indent=2))
