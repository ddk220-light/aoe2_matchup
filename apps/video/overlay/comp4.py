"""Five-card Comp4 review overlay using installed game art and font assets.

Result timing comes from timestamped per-owner gRPC HP, not a scripted battle
duration. The renderer handles each arena independently and holds the final
results for three real video seconds. No other campaign videos are rendered.
"""
from __future__ import annotations
import argparse, json, sqlite3, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from overlay.static_stats import GAME,REPO,GameFont,panel,resolve_stats,portrait_path,upgraded,number,INK
from overlay.civ_theme import theme_for,panel_art
from overlay.ffutil import find_ffmpeg

CIVS=['Incas','Mapuche','Muisca','Tupi']
COLORS=[(54,111,224,255),(37,164,75,255),(225,190,41,255),(174,72,214,255)]
CORNERS=[(16,16),(1954,16),(16,1104),(1954,1104)]
RESULTS=[(275,555),(1080,150),(1100,1040),(1900,580)]

def center_text(image,font,text,y,size,color=INK,cx=None):
    cx=image.width/2 if cx is None else cx
    font.draw(image,(cx-font.width(text,size)/2,y),text,size,color)

def emblem(civ,size):
    im=Image.open(theme_for(GAME,civ)['emblemPath']).convert('RGBA')
    im=im.crop(im.getbbox());im.thumbnail((size,size),Image.Resampling.LANCZOS);return im

def stat(im,font,icon,text,x,y,size=29):
    symbol=Image.open(GAME/f'widgetui/textures/ingame/staticons/{icon}.png').convert('RGBA')
    symbol.thumbnail((30,30),Image.Resampling.LANCZOS);im.alpha_composite(symbol,(x,y-3))
    font.draw(im,(x+38,y),text,size)

def champi_card(unit,civ,color,font):
    card=Image.new('RGBA',(590,320),(23,24,23,255))
    card.alpha_composite(panel_art(theme_for(GAME,civ),(590,320)))
    draw=ImageDraw.Draw(card)
    font.draw(card,(51,51),'Elite Champi Warrior',34)
    draw.rounded_rectangle((51,86,64,114),radius=3,fill=color)
    font.draw(card,(76,88),civ,27)
    portrait=Image.open(portrait_path(unit['unit_name'])).convert('RGBA').resize((108,108),Image.Resampling.LANCZOS)
    draw.rectangle((51,124,164,237),fill=(27,24,20),outline=(106,76,42),width=3)
    card.alpha_composite(portrait,(54,127))
    draw.rectangle((52,240,164,250),fill=color,outline=INK,width=2)
    badge=emblem(civ,43);card.alpha_composite(badge,(164-badge.width//2,237-badge.height//2))
    font.draw(card,(52,260),f"{number(unit['final_hp'])}/{number(unit['final_hp'])}",26)
    rows=[('damage',upgraded(unit,'attack')),('armor',upgraded(unit,'melee_armor')+' / '+upgraded(unit,'pierce_armor')),
          ('reloadTime',f"{unit['final_reload_time']:.2f}"),('movementSpeed',f"{unit['final_speed']:.2f}")]
    for j,(icon,value) in enumerate(rows):stat(card,font,icon,value,213,127+j*35,30)
    return card

def cross_card(unit,font):
    # An X in screen space follows the two diagonal forest strips. Concave
    # notches leave the four arena floors visible instead of using a rectangle.
    out=Image.new('RGBA',(2560,1440));mask=Image.new('L',out.size)
    points=[(970,547),(1135,624),(1280,688),(1425,624),(1590,547),(1623,629),
            (1425,733),(1623,837),(1590,919),(1400,837),(1280,784),(1160,837),
            (970,919),(937,837),(1135,733),(937,629)]
    ImageDraw.Draw(mask).polygon(points,fill=255)
    art=Image.open(theme_for(GAME,'Armenians')['panelPath']).convert('RGBA')
    parchment=art.crop((150,110,850,350)).resize(out.size,Image.Resampling.LANCZOS)
    parchment.putalpha(mask)
    shadow=Image.new('RGBA',out.size,(10,8,5,180));shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(8)))
    out.alpha_composite(shadow,(4,7));out.alpha_composite(parchment)
    draw=ImageDraw.Draw(out)
    draw.line(points+[points[0]],fill=(49,32,19,255),width=10,joint='curve')
    draw.line(points+[points[0]],fill=(182,145,83,255),width=4,joint='curve')
    # The portrait occupies the central knot; labels and stat rows use the arms.
    portrait=Image.open(portrait_path(unit['unit_name'])).convert('RGBA').resize((90,90),Image.Resampling.LANCZOS)
    draw.rectangle((1232,691,1327,786),fill=(28,23,17),outline=(95,69,36),width=3)
    out.alpha_composite(portrait,(1235,694))
    badge=emblem('Armenians',34);out.alpha_composite(badge,(1327-badge.width//2,786-badge.height//2))
    # The title is typeset along the diagonal arm instead of crossing its edge.
    title=Image.new('RGBA',(260,78))
    center_text(title,font,'Elite Composite',5,29)
    center_text(title,font,'Bowman',41,29)
    title=title.rotate(-27,resample=Image.Resampling.BICUBIC,expand=True)
    out.alpha_composite(title,(1090-title.width//2,670-title.height//2))
    stat(out,font,'pierceAttackBypass',upgraded(unit,'attack'),1475,610)
    stat(out,font,'range',upgraded(unit,'range'),1380,660)
    stat(out,font,'reloadTime',f"{unit['final_reload_time']:.2f}",985,839)
    stat(out,font,'movementSpeed',f"{unit['final_speed']:.2f}",1475,839)
    stat(out,font,'armor',upgraded(unit,'melee_armor')+' / '+upgraded(unit,'pierce_armor'),1360,792,25)
    center_text(out,font,f"{number(unit['final_hp'])}/{number(unit['final_hp'])} HP",793,26,cx=1105)
    return out,points

def result_card(civ,result,initial,font):
    image=Image.new('RGBA',(490,153));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((3,3,484,147),radius=16,fill=(16,17,14,230),outline=(176,146,92,235),width=2)
    icon=emblem(civ,92);image.alpha_composite(icon,(18,30))
    won=result['winnerOwner']==result['subjectOwner'];drawn=result['winnerOwner'] is None
    label=civ+(' Draw' if drawn else ' Victory' if won else ' Defeat')
    color=(242,211,142,255) if drawn else (111,237,139,255) if won else (255,115,110,255)
    size=min(37,345/font.width(label,1))
    font.draw(image,(122,35),label,size,color)
    owner=result['subjectOwner'] if won else result['opponentOwner']
    remaining=result['subject' if won else 'opponent']['hp']
    denominator=initial[str(owner)]['hp']
    percent=remaining/denominator*100 if denominator else 0
    text=f'{percent:.1f}% '+('HP left' if won or drawn else 'enemy HP left')
    font.draw(image,(123,88),text,29,(245,232,203,255))
    return image,percent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=REPO/'data/local/comp4-champi-spike')
    parser.add_argument('--out',type=Path,default=REPO/'data/local/comp4-champi-overlay-review')
    parser.add_argument('--assets-only',action='store_true')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    font=GameFont(GAME);db=sqlite3.connect(REPO/'data/golden/aoe2_reference.db');db.row_factory=sqlite3.Row
    opponent=resolve_stats(db,{'label':'Elite Composite Bowman','civ':'Armenians','slug':'elite_composite_bowman_armenians'})
    units=[resolve_stats(db,{'label':'Elite Champi Warrior','civ':civ,'slug':'elite_champi_warrior_'+civ.lower()}) for civ in CIVS]
    db.close();static=Image.new('RGBA',(2560,1440))
    for i,unit in enumerate(units):
        card=champi_card(unit,CIVS[i],COLORS[i],font)
        card.save(args.out/f'card-{i+1}.png');static.alpha_composite(card,CORNERS[i])
    cross,polygon=cross_card(opponent,font);static.alpha_composite(cross)
    static.save(args.out/'static.png');cross.save(args.out/'center.png')
    capture=args.source/'capture-01';status=json.loads((capture/'status.json').read_text())
    validation=json.loads((args.source/'validation.json').read_text())
    if validation['state']!='PASSED':raise ValueError('Pilot capture is not validated')
    rows=[json.loads(line) for line in (capture/'timeline.jsonl').read_text().splitlines()]
    first=next(r for r in rows if r['gameSeconds']==0)
    events=[]
    for i,civ in enumerate(CIVS):
        p=str(i+1);q=str(i+5)
        # First terminal frame, independently per pair. Ensure no later revival
        # before declaring a result (Konnik-style replacements may reappear).
        terminal=next(r for j,r in enumerate(rows) if r['gameSeconds']>1 and (r['totals'][p]['count']==0 or r['totals'][q]['count']==0)
                      and all(s['totals'][p]['count']==0 or s['totals'][q]['count']==0 for s in rows[j:]))
        result={'subjectOwner':i+1,'opponentOwner':i+5,'subject':terminal['totals'][p],'opponent':terminal['totals'][q],
                'winnerOwner':i+1 if terminal['totals'][p]['count'] else i+5 if terminal['totals'][q]['count'] else None}
        card,percent=result_card(civ,result,validation['initialState']['totals'],font)
        card.save(args.out/f'result-{p}.png')
        events.append({'owner':i+1,'civ':civ,'videoSeconds':terminal['wallEpoch']-first['wallEpoch'],
                       'gameSeconds':terminal['gameSeconds'],'hpPercent':percent,**result})
    duration=max(e['videoSeconds'] for e in events)+3
    metadata={'source':str(capture),'videoStartSeconds':28.9166666667,'endHoldSeconds':3,'duration':duration,'events':events,
              'centralPolygon':polygon,'cornerMapping':dict(zip(CIVS,CORNERS)),
              'timing':'First visible arena frame anchored to gRPC game zero; per-frame wall timestamps preserve startup delays and actual game speed.'}
    (args.out/'overlay.json').write_text(json.dumps(metadata,indent=2))
    # Contact previews of the actual recording plus only the layers enabled at
    # that time. These are media artifact checks, not game UI screenshots.
    import cv2
    cap=cv2.VideoCapture(str(capture/'raw.mp4'))
    for name,t in [('opening',1),('first-result',min(e['videoSeconds'] for e in events)+.2),('all-results',duration-1)]:
        source_t=min(44.1,28.9166666667+t);cap.set(cv2.CAP_PROP_POS_MSEC,source_t*1000);ok,frame=cap.read()
        if not ok:raise ValueError(name)
        image=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGBA));image.alpha_composite(static)
        for i,e in enumerate(events):
            if e['videoSeconds']<=t:image.alpha_composite(Image.open(args.out/f'result-{i+1}.png'),RESULTS[i])
        image.convert('RGB').resize((1600,900),Image.Resampling.LANCZOS).save(args.out/f'{name}.jpg',quality=94)
    cap.release()
    if args.assets_only:return
    ffmpeg=find_ffmpeg();cmd=[str(ffmpeg),'-y','-hide_banner','-loglevel','warning','-threads','2','-ss','28.9166666667','-i',str(capture/'raw.mp4')]
    for name in ['static.png']+[f'result-{i}.png' for i in range(1,5)]:cmd+=['-loop','1','-i',str(args.out/name)]
    graph=[f'[0:v]setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=5[v0]', '[v0][1:v]overlay=0:0[v1]']
    for i,e in enumerate(events):
        x,y=RESULTS[i];graph.append(f"[v{i+1}][{i+2}:v]overlay={x}:{y}:enable='gte(t,{e['videoSeconds']:.6f})'[v{i+2}]")
    graph+=['[0:a]asetpts=PTS-STARTPTS,apad[a]']
    cmd+=['-filter_complex_threads','1','-filter_complex',';'.join(graph),'-map','[v5]','-map','[a]','-t',str(duration),'-r','60','-c:v','h264_nvenc','-preset','p5','-cq','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(args.out/'Champi_Four_Civilizations_Armenian_Overlay.mp4')]
    with (args.out/'encode.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    print(json.dumps(metadata,indent=2))

if __name__=='__main__':main()
