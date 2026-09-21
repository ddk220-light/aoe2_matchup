"""Render the approved four-column Champi intro page using installed UI assets.

This is a static review page, not a narration/video render. It never touches the
active recorder or comparison video. Text is kept separate for future animation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from PIL import Image, ImageDraw, ImageFilter
from build_campaign_intro import lines
from overlay.comp4 import emblem
from overlay.civ_theme import nine_slice
from overlay.static_stats import GAME, REPO, GameFont, INK, portrait_path, resolve_stats, upgraded, number

PLAN=REPO/'apps/video/intro/champi-comparison.json'
OUT=REPO/'data/local/champi-comparison-intro'
W,H=2560,1440


def centered(im,font,text,cx,y,size,color=INK):
    font.draw(im,(cx-font.width(text,size)/2,y),text,size,color)


def icon(im,name,xy,size=32):
    art=Image.open(GAME/f'widgetui/textures/ingame/staticons/{name}.png').convert('RGBA')
    art.thumbnail((size,size),Image.Resampling.LANCZOS)
    im.alpha_composite(art,xy)


def unit_card(unit,font):
    # Intro stats belong to the shared campaign parchment, without HUD framing.
    card=Image.new('RGBA',(500,370),(0,0,0,0))
    d=ImageDraw.Draw(card)
    font.draw(card,(35,54),unit['unit_name'],30)
    portrait=Image.open(portrait_path(unit['unit_name'])).convert('RGBA').resize((110,110),Image.Resampling.LANCZOS)
    d.rectangle((34,96,148,210),fill=(27,22,17),outline=(100,76,44),width=2)
    card.alpha_composite(portrait,(36,98))
    d.rectangle((35,215,148,224),fill=(190,48,36),outline=INK,width=1)
    centered(card,font,f"{number(unit['final_hp'])}/{number(unit['final_hp'])}",92,241,27)
    rows=[('damage',upgraded(unit,'attack')),
          ('armor',upgraded(unit,'melee_armor')+' / '+upgraded(unit,'pierce_armor')),
          ('reloadTime',f"{unit['final_reload_time']:.2f}"),
          ('movementSpeed',f"{unit['final_speed']:.2f}")]
    for i,(symbol,value) in enumerate(rows):
        y=107+i*40
        icon(card,symbol,(185,y-3))
        font.draw(card,(229,y),value,min(30,210/font.width(value,1)))
    d.line((36,280,441,280),fill=(148,110,65),width=1)
    icon(card,'food',(64,299));font.draw(card,(105,304),number(unit['final_cost_food']),29)
    icon(card,'gold',(239,299));font.draw(card,(280,304),number(unit['final_cost_gold']),29)
    return card


def build(output=OUT, plan_path=PLAN):
    output.mkdir(parents=True,exist_ok=True)
    plan=json.loads(plan_path.read_text())
    catalog=json.loads((PLAN.parent/'campaign_catalog.json').read_text())
    theme=catalog['preferredByCivilization'][plan['civilization']]
    source=GAME/'widgetui'/theme['background']
    # Match the existing intro's landscape framing, then reuse its actual blank
    # parchment with preserved border thickness to fit the comparison layout.
    bg=Image.open(source).convert('RGBA').resize((2560,1080),Image.Resampling.LANCZOS).crop((320,0,2240,1080))
    paper=bg.crop((389,190,1495,897))
    im=bg.resize((W,H),Image.Resampling.LANCZOS)
    shade=Image.new('RGBA',(W,H),(0,0,0,0))
    ImageDraw.Draw(shade).rectangle((132,105,2440,1370),fill=(0,0,0,125))
    im.alpha_composite(shade.filter(ImageFilter.GaussianBlur(15)))
    im.alpha_composite(nine_slice(paper,(2320,1260),edge=50),(120,90))
    font=GameFont(GAME);draw=ImageDraw.Draw(im)
    db=REPO/'data/golden/aoe2_reference.db'
    con=sqlite3.connect(f'file:{db}?mode=ro',uri=True);con.row_factory=sqlite3.Row
    records=[]
    layers=[]
    # Joan's parchment has a broad curled left edge and foreground objects.
    # Its writing area is narrower than the Champi background's flat sheet.
    frank_parchment = plan['civilization'] == 'FRANKS'
    left, column_width = (330, 500) if frank_parchment else (200, 540)
    note_width = column_width - 80
    notes_top, notes_bottom = (830, 1190) if frank_parchment else (882, 1280)
    for i,col in enumerate(plan['columns']):
        x=left+i*column_width;cx=x+column_width/2
        if i:
            draw.line((x,167,x,1260),fill=(143,110,65,120),width=2)
        badge=emblem(col['civ'],104)
        im.alpha_composite(badge,(round(cx-badge.width/2),167))
        content=Image.new('RGBA',(W,H),(0,0,0,0))
        centered(content,font,col['civ'],cx,302,46)
        reminder=lines(font,col['reminder'],29,min(450,column_width-80))
        for n,line in enumerate(reminder):centered(content,font,line,cx,365+n*37,29)
        if 365+len(reminder)*37>487:raise ValueError('Reminder overlaps card')
        unit=resolve_stats(con,col.get('side') or dict(label=plan['unit'],civ=col['civ'],slug='elite_champi_warrior_'+col['civ'].lower()))
        card=unit_card(unit,font)
        if frank_parchment:
            card=card.resize((460,340),Image.Resampling.LANCZOS)
        content.alpha_composite(card,(x+20,440 if frank_parchment else 470))
        y=notes_top
        note_size=29
        while note_size>22 and sum(len(lines(font,h+' '+b,note_size,note_width))*(note_size+8)+23 for h,b in col['notes'])>notes_bottom-notes_top:
            note_size-=1
        for heading,body in col['notes']:
            for line in lines(font,heading+' '+body,note_size,note_width):
                font.draw(content,(x+38,y),line,note_size);y+=note_size+8
            y+=23
        if y>notes_bottom:raise ValueError(f"{col['civ']} text overflows parchment: {y}")
        records.append(dict(civilization=col['civ'],stats=unit,content=col,bottom=y))
        layers.append(content)
    con.close()
    # Stage zero preserves all four emblems; each next stage reveals a whole
    # civilization column. Video timing comes from speech character alignment.
    stages=[]
    for i in range(5):
        if i: im.alpha_composite(layers[i-1])
        stage=output/f'page-2-stage-{i}.png'
        im.convert('RGB').save(stage)
        stages.append(str(stage))
    dest=output/'Champi_Comparison_Intro_Page_2.png'
    im.convert('RGB').save(dest)
    (output/'page-2-manifest.json').write_text(json.dumps(dict(image=str(dest),resolution=[W,H],
        plan=str(plan_path),background=str(source),font='Installed combined.txt GameFont atlas, identical to campaign intro',
        referenceSha256=hashlib.sha256(db.read_bytes()).hexdigest(),columns=records,stages=stages),indent=2))
    print(dest)
    return dest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=OUT)
    p.add_argument('--plan',type=Path,default=PLAN)
    args=p.parse_args();build(args.output,args.plan)
