"""Review renderer: four archived Champi battles, one opponent card and a tally.

Only disposable render-workspace files are read/written. Archives and the live
recorder are never changed. Run preparation with materialize_compact_recording
and overlay.auto_alignment first; a verified timeline.json is required per run.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
import sqlite3
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

from overlay.battle_end import terminal_row
from overlay.comp4 import emblem
from overlay.ffutil import find_ffmpeg
from overlay.static_stats import GAME, REPO, GameFont, panel, resolve_stats, portrait_path, upgraded, number
from overlay.civ_theme import panel_art, theme_for

CIVS = ('Incas', 'Mapuche', 'Muisca', 'Tupi')
W, H, PANEL_W, VIDEO_H, FPS = 2560, 1440, 640, 960, 30
START, HOLD = .4, 3.0
OUT = REPO / 'data/local/champi-comparison-overlay-v2'
INK = (240, 224, 189, 255)
MUTED = (180, 163, 132, 255)
GOLD = (222, 181, 80, 255)
GREEN = (116, 236, 136, 255)
RED = (255, 112, 99, 255)
FONTS = GAME / 'resources/_common/wpfg/fonts'
STATS_DIVIDER = 650
REMINDERS = {
    'Incas': 'Cheaper food; +1 melee/+1 pierce armor',
    'Mapuche': '+15 HP; moves slower',
    'Muisca': 'Moves faster; +3 melee armor; -2 attack',
    'Tupi': 'Attacks faster; -2 attack',
}


def update_tally(previous, opponent, results):
    """Credit only victories, highest unrounded HP fraction; ties share credit.

    A sole victorious civilization gets a soft glow, even if another civ lost narrowly.
    The serialized 'bold' key is retained for compatibility with earlier tallies.
    Each call represents one completed opponent; callers must not append twice.
    """
    tally = deepcopy(previous)
    winners = [r for r in results if r['winner'] == '2']
    if winners:
        best = max(r['percent'] for r in winners)
        for r in winners:
            if math.isclose(r['percent'], best, abs_tol=1e-7):
                tally.setdefault(r['civ'], []).append(
                    {'opponent': opponent, 'bold': len(winners) == 1})
    return tally


@lru_cache(maxsize=64)
def trajan(size, bold=False):
    name = 'TrajanPro-Bold.ttf' if bold else 'TrajanPro-Regular.ttf'
    return ImageFont.truetype(str(FONTS / name), size)


@lru_cache(maxsize=256)
def text_tile(text, size, color=INK, bold=False, shadow=True):
    f = trajan(size, bold)
    box = f.getbbox(text)
    tile = Image.new('RGBA', (math.ceil(f.getlength(text)) + 20, box[3]-box[1]+22))
    d = ImageDraw.Draw(tile)
    xy = (10, 8-box[1])
    if shadow:
        d.text((xy[0]+2, xy[1]+3), text, font=f, fill=(0, 0, 0, 240),
               stroke_width=3, stroke_fill=(0, 0, 0, 220))
    d.text(xy, text, font=f, fill=color)
    return tile


def put(im, text, x, y, size=32, color=INK, bold=False, center=False):
    tile = text_tile(text, size, color, bold, shadow=y < VIDEO_H)
    im.alpha_composite(tile, (round(x-tile.width/2 if center else x), round(y)))


def rank_results(results):
    """Victories outrank defeats; minimize enemy HP on defeats. Ignore time."""
    scores = {r['civ']: (r['percent'] if r['winner']=='2' else -r['percent']) for r in results}
    return {c: 1+sum(other > score+1e-7 for other in scores.values()) for c,score in scores.items()}


def rank_medal(rank, won):
    if rank >= 4:
        return Image.new('RGBA',(77,90))
    metal = {1:'gold', 2:'silver', 3:'bronze'}[rank]
    medal = Image.open(GAME / f'widgetui/textures/menu/icons/medal_rank_{metal}.png').convert('RGBA')
    # Preserve the metal hues: desaturation makes gold and silver too similar.
    medal = ImageEnhance.Color(medal).enhance(1.15)
    medal = ImageEnhance.Brightness(medal).enhance(.94 if not won else 1)
    medal = medal.resize((77,90), Image.Resampling.LANCZOS)
    return medal


def result_art(civ, winner, percent, rank, *, backing=True):
    """Actual game ornaments/font over the requested translucent grey panel."""
    won = winner == '2'
    name = 'victory' if won else 'defeat'
    asset = GAME / f'resources/_common/wpfg/resources/dialog/dialog_{name}2.png'
    ornament = Image.open(asset).convert('RGBA')
    # The shipped banner includes a half-transparent black dialog backdrop.
    # Retain only the colored ornament plus its narrow black outline.
    pixels = np.array(ornament)
    foreground = ((pixels[:,:,:3].max(axis=2) > 40) & (pixels[:,:,3] > 160)).astype('uint8')
    support = cv2.dilate(foreground, np.ones((5,5), dtype='uint8'))
    pixels[:,:,3] *= support
    ornament = Image.fromarray(pixels)
    im = Image.new('RGBA', (640, 450))
    # Separate the two borders to make room for the result without distorting art.
    upper = ornament.crop((0, 0, ornament.width, 268))
    upper.thumbnail((560, 146), Image.Resampling.LANCZOS)
    lower = ornament.crop((0, 298, ornament.width, ornament.height))
    lower.thumbnail((560, 65), Image.Resampling.LANCZOS)
    im.alpha_composite(upper, ((640-upper.width)//2, 5))
    badge = emblem(civ, 88)
    im.alpha_composite(badge, ((640-badge.width)//2, 36))
    title = 'Victorious' if won else 'Defeated' if winner == '3' else 'Draw'
    put(im, title, 320, 171, 60, GOLD if won else (229, 226, 219, 255), center=True)
    im.alpha_composite(rank_medal(rank, won), (77,252))
    put(im, f'{percent:.1f}% HP', 363, 263, 46, GREEN if won else RED, center=True)
    if winner == '3':
        put(im, 'Opponent remaining', 320, 329, 23, INK, center=True)
    im.alpha_composite(lower, ((640-lower.width)//2, 385))
    # A soft shadow follows the artwork; the grey backing remains translucent.
    a = im.getchannel('A').filter(ImageFilter.GaussianBlur(4))
    shadow = Image.new('RGBA', im.size, (0, 0, 0, 0)); shadow.putalpha(a)
    shadow.alpha_composite(im)
    result = Image.new('RGBA', im.size)
    if backing:
        ImageDraw.Draw(result).rectangle((40,76,599,409), fill=(35,35,35,162))
    result.alpha_composite(shadow)
    return result


def tally_sprite_path(entry):
    aliases = {'War Chariot (Barrage)': 'war_chariot_3k',
               'War Chariot (Focus Fire)': 'war_chariot_3k'}
    slug = aliases.get(entry['opponent'], entry['opponent'].lower().replace('(','').replace(')','').replace(' ','_'))
    path = Path(entry['iconPath']) if entry.get('iconPath') else REPO/'apps/website/static/img/unit_sprites'/f'{slug}.png'
    if not path.is_file():
        raise FileNotFoundError(f'Transparent tally sprite required: {entry["opponent"]}: {path}')
    return path


def tally_icon(entry, size=66):
    path = tally_sprite_path(entry)
    icon = Image.open(path).convert('RGBA')
    if icon.getchannel('A').getextrema()[0] != 0:
        raise ValueError(f'Tally sprite has an opaque background: {path}')
    icon = icon.crop(icon.getbbox()); icon.thumbnail((size-8,size-8),Image.Resampling.LANCZOS)
    tile = Image.new('RGBA',(size,size)); tile.alpha_composite(icon,((size-icon.width)//2,(size-icon.height)//2))
    if entry.get('bold'):  # Existing serialized key means sole winner.
        # Glow sits behind the unchanged sprite. No solid stroke covers its
        # fine details; a padded tile lets the halo fade without a square edge.
        pad = 12
        padded = Image.new('RGBA',(size+pad*2,size+pad*2))
        padded.alpha_composite(tile,(pad,pad))
        tile = padded
        alpha = tile.getchannel('A')
        glow = Image.new('RGBA',tile.size,(239,166,34,0))
        glow.putalpha(alpha.filter(ImageFilter.GaussianBlur(5)).point(lambda a:min(205,round(a*2.2))))
        glow.alpha_composite(tile)
        return glow
    return tile


def draw_tally(im, tally, font, civs=CIVS, reminders=REMINDERS):
    left = STATS_DIVIDER + 44
    font.draw(im,(left,1040),'Tally of best winners',36)
    for i, civ in enumerate(civs):
        y = 1095 + i*70
        badge = emblem(civ, 42)
        im.alpha_composite(badge, (left+(42-badge.width)//2, y+4))
        font.draw(im,(left+61,y+2),civ,30)
        font.draw(im,(left+61,y+37),reminders[civ],23,(87,58,36,255))
        entries = tally.get(civ, [])
        icon_left, icon_right = 1250, 2450
        size = 66 if len(entries)<=17 else 34
        columns = (icon_right-icon_left)//(size+3)
        if len(entries)>columns*(70//(size+1)):
            raise ValueError('Tally requires another page')
        for n,entry in enumerate(entries):
            tile=tally_icon(entry,size)
            pad=(tile.width-size)//2
            im.alpha_composite(tile,(icon_left+(n%columns)*(size+3)-pad,y+(n//columns)*(size+1)-pad))


def shared_footer(enemy, bonus, font):
    base = Image.new('RGBA',(W,H),(27,25,22,255))
    base.alpha_composite(panel_art(theme_for(GAME,enemy['civ_name']),(2528,450)),(16,979))
    d=ImageDraw.Draw(base)
    d.line((STATS_DIVIDER,1027,STATS_DIVIDER,1380),fill=(131,94,56,255),width=2)
    right = STATS_DIVIDER-28
    # The Indian HUD's decorative left band is wider than its outer frame.
    # One shared safe inset keeps title, portrait, HP bar and HP text aligned
    # on clear parchment across every opponent civilization theme.
    left, stats_x, value_x = 192, 378, 425
    title_size = min(36,(right-left)/font.width(enemy['unit_name'],1))
    font.draw(base,(left,1040),enemy['unit_name'],title_size)
    portrait=Image.open(portrait_path(enemy['unit_name'])).convert('RGBA').resize((154,154),Image.Resampling.LANCZOS)
    d.rectangle((left,1084,left+158,1242),fill=(28,23,20),outline=(90,66,38),width=2)
    base.alpha_composite(portrait,(left+2,1086))
    d.rectangle((left,1246,left+158,1258),fill=(224,47,40),outline=(57,28,27),width=2)
    badge=emblem(enemy['civ_name'],48)
    base.alpha_composite(badge,(left+158-badge.width//2,1242-badge.height//2))
    hp_text=f"{number(enemy['final_hp'])}/{number(enemy['final_hp'])}"
    font.draw(base,(left,1280),hp_text,min(30,158/font.width(hp_text,1)))
    attacks=json.loads(enemy['final_attacks_json'])
    pierce=attacks.get('3',0)>attacks.get('4',0)
    attack_icon='pierceAttackBypass' if pierce and enemy['ignores_pierce_armor'] else 'pierceAttack' if pierce else 'damage'
    rows=[(attack_icon,upgraded(enemy,'attack')),('armor',upgraded(enemy,'melee_armor')+' / '+upgraded(enemy,'pierce_armor'))]
    if enemy['final_range']>0: rows.append(('range',upgraded(enemy,'range')))
    rows += [('reloadTime',f"{enemy['final_reload_time']:.2f}"),('movementSpeed',f"{enemy['final_speed']:.2f}")]
    for i,(icon,value) in enumerate(rows):
        y=1088+i*43
        symbol=Image.open(GAME/f'widgetui/textures/ingame/staticons/{icon}.png').convert('RGBA')
        symbol.thumbnail((32,32),Image.Resampling.LANCZOS);base.alpha_composite(symbol,(stats_x,y-4))
        end=font.draw(base,(value_x,y),value,min(30,(right-value_x)/font.width(value,1)))
        if i==0 and bonus:
            text=f'({number(bonus)} bonus damage)'
            # Put long matchup annotations underneath the rows rather than
            # allowing any content to cross the fixed stats/tally divider.
            bx,by=(end+12,y+4) if font.width(text,22)<=right-end-12 else (stats_x,1309)
            font.draw(base,(bx,by),text,min(22,(right-bx)/font.width(text,1)),(24,112,35,255))
    if enemy['ignores_pierce_armor']:
        note='Arrows ignore pierce armor.'
        font.draw(base,(stats_x,1328),note,min(25,(right-stats_x)/font.width(note,1)))
    return base


def starting_counts_layer(counts, font):
    """Fixed opening army sizes: featured unit first, opponent second, no buffer."""
    layer = Image.new('RGBA',(W,150))
    for i,(featured,opponent) in enumerate(counts):
        if featured is None:continue
        text=f'{featured} vs {opponent}'
        x=i*PANEL_W+(PANEL_W-font.width(text,34))/2
        font.draw(layer,(x+2,98),text,34,(0,0,0,255))
        font.draw(layer,(x,96),text,34,INK)
    return layer


def load_jobs(out, run_paths=None, civs=CIVS):
    jobs = []
    for civ in civs:
        if run_paths is not None and run_paths[civ] is None:
            jobs.append(dict(civ=civ,run=None,cap=None,end=0,endSource=0,winner='not_tested',
                             percent=0,initialHp={},finalHp={},gameEndSeconds=None,rank=4))
            continue
        job = f'champi_geometric_{civ.lower()}_01_elite_composite_bowman_armenians'
        run = Path(run_paths[civ]) if run_paths else out / 'render-workspace' / job / 'live/run_001'
        timeline = json.loads((run/'timeline.json').read_text())
        alignment = json.loads((run/'unit-hp-overlay/alignment.json').read_text())
        recording = json.loads((run/'recording.json').read_text())
        if alignment['videoSha256'] != recording['files']['battleVideo']['sha256']:
            raise ValueError(f'{civ}: alignment belongs to another video')
        if not timeline['mapping'].get('alignment'):
            raise ValueError(f'{civ}: verified timeline required')
        rows = timeline['rows']; end = terminal_row(rows)
        initial = {o: sum(u['hp'] for u in rows[0]['sides'][o]) for o in ('2', '3')}
        hp = {o: sum(u['hp'] for u in end['sides'][o]) for o in ('2', '3')}
        if hp['2'] > 0 and hp['3'] > 0:
            raise ValueError(f'{civ}: capture ended before elimination')
        winner = '2' if hp['2'] > 0 else '3' if hp['3'] > 0 else None
        percent = 100*hp[winner]/initial[winner] if winner else 0
        cap = cv2.VideoCapture(str(run/'battle.mp4'), cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_N_THREADS, 2])
        fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        end_source = end['videoSeconds']
        if end_source < START or end_source > (count-1)/fps:
            raise ValueError(f'{civ}: outcome outside recorded footage')
        jobs.append(dict(civ=civ, run=run, cap=cap, fps=fps, index=-1, last=None,
                         end=end_source-START, endSource=end_source, winner=winner,
                         percent=percent, initialHp=initial, finalHp=hp,
                         gameEndSeconds=end['gameMs']/1000))
    ranks=rank_results([j for j in jobs if j['cap'] is not None])
    for j in jobs:
        if j['cap'] is None:
            j['result']=Image.new('RGBA',(640,450))
            put(j['result'],'Same unit',320,171,44,center=True)
            put(j['result'],'Not tested',320,250,32,center=True)
            continue
        j['rank']=ranks[j['civ']]
        j['result']=result_art(j['civ'],j['winner'],j['percent'],j['rank'])
    return jobs


def frame_at(job, seconds, seek=False):
    if job['cap'] is None:return Image.new('RGB',(640,960),(35,32,27))
    target = round(min(seconds+START, job['endSource'])*job['fps'])
    cap = job['cap']
    if seek or target < job['index']:
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        job['index'] = target-1
    while job['index'] < target:
        ok, bgr = cap.read()
        if not ok:
            raise RuntimeError(f"Cannot decode {job['civ']} frame {target}")
        job['last'], job['index'] = bgr, job['index']+1
    # The first .4s camera pan is excluded. This portrait window contains both
    # starting armies and all combat, and excludes the source desktop toast.
    # No stretching: 960x1440 source -> 640x960 display, scale exactly 2/3.
    # User-approved fixed crop; occasional units touching its edges are accepted.
    source = job['last'][:, 890:1850]
    return Image.fromarray(cv2.cvtColor(cv2.resize(source, (640, 960)), cv2.COLOR_BGR2RGB))


def build(out=OUT, stills_only=False, opponent=None, run_paths=None, prior_tally=None, profile=None):
    out.mkdir(parents=True, exist_ok=True)
    civs=tuple(c['civ'] for c in profile['columns']) if profile else CIVS
    reminders={c['civ']:c['reminder'] for c in profile['columns']} if profile else REMINDERS
    cv2.setNumThreads(2)
    font = GameFont(GAME)
    db = sqlite3.connect(f'file:{REPO / "data/golden/aoe2_reference.db"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    opponent = opponent or {'label':'Elite Composite Bowman', 'civ':'Armenians',
                           'slug':'elite_composite_bowman_armenians'}
    enemy = resolve_stats(db, opponent)
    cards = []
    for index,civ in enumerate(civs):
        side=profile['columns'][index]['side'] if profile else {'label':'Elite Champi Warrior', 'civ':civ,
                                     'slug':f'elite_champi_warrior_{civ.lower()}'}
        featured = resolve_stats(db, side)
        cards.append(panel(enemy, featured, font, GAME, (232, 58, 49, 255)))
    if not profile and any(m != cards[0][1] for _, m in cards):
        raise ValueError('Opponent bonuses differ: cannot use one shared stat card')
    db.close()
    bonuses={c:m['attackBonus'] for c,(_,m) in zip(civs,cards)}
    base = shared_footer(enemy,max(bonuses.values()),font)
    if len(set(bonuses.values()))>1:
        text='; '.join(f'{c}: {number(v)} bonus' for c,v in bonuses.items() if v!=max(bonuses.values()))
        font.draw(base,(192,1360),text,min(22,425/font.width(text,1)),(24,112,35,255))
    empty = deepcopy(prior_tally) if prior_tally is not None else {c: [] for c in civs}
    jobs = load_jobs(out, run_paths, civs)
    counts=[]
    for job in jobs:
        if job['run'] is None:
            counts.append((None,None));continue
        recording=json.loads((job['run']/'recording.json').read_text())
        counts.append(tuple(recording['sides'][s]['count'] for s in ('side1','side2')))
    counts_layer=starting_counts_layer(counts,font)
    duration = max(j['end'] for j in jobs)+HOLD
    results = [{k:j[k] for k in ('civ','winner','percent','end','endSource',
                                'initialHp','finalHp','gameEndSeconds','rank')} for j in jobs]
    tally = update_tally(empty, enemy['unit_name'], results)
    footer_before, footer_after = base.copy(), base.copy()
    draw_tally(footer_before, empty, font,civs,reminders); draw_tally(footer_after, tally, font,civs,reminders)
    headers = []
    for civ in civs:
        header = Image.new('RGBA', (640, 112))
        # Feather the top for contrast while keeping footage visible beneath it.
        a = np.tile(np.linspace(170,0,112).astype(np.uint8)[:,None], (1,640))
        shade = Image.new('RGBA', header.size, (0,0,0));shade.putalpha(Image.fromarray(a))
        header.alpha_composite(shade)
        badge = emblem(civ, 62)
        tw = font.width(civ,36)
        left = round((640-(62+18+tw))/2)
        header.alpha_composite(badge, (left, 20))
        font.draw(header,(left+74,42),civ,36,(0,0,0,255))
        font.draw(header,(left+72,40),civ,36,INK)
        headers.append(header)

    def compose(t, seek=False):
        im = (footer_after if t >= duration-HOLD else footer_before).copy()
        for i, job in enumerate(jobs):
            x = PANEL_W*i
            im.paste(frame_at(job, t, seek), (x,0))
            im.alpha_composite(headers[i], (x,0))
            if t >= job['end']:
                im.alpha_composite(job['result'], (x, 245))
        d = ImageDraw.Draw(im)
        for x in (640,1280,1920):
            d.line((x,0,x,VIDEO_H),fill=(43,35,23),width=4)
            d.line((x+1,0,x+1,VIDEO_H),fill=(156,126,74),width=1)
        d.line((0,VIDEO_H,W,VIDEO_H),fill=(163,129,74),width=3)
        im.alpha_composite(counts_layer,(0,0))
        return im.convert('RGB')

    for t in (0, 5, 12, min(j['end'] for j in jobs)+.15, duration-.1):
        compose(t, True).save(out/f'comparison-{t:05.2f}.jpg', quality=93)
    metadata = dict(resolution=[W,H], fps=FPS, durationSeconds=duration, results=results,
                    effectiveBonusByCivilization=bonuses,
                    tally=tally, trimStartSeconds=START, resultHoldSeconds=HOLD,
                    sourceCrop=[890,0,960,1440], viewport=[640,960],
                    hpMeaning='Winner surviving HP / winner opening HP, excludes buffer units; defeats label opponent remaining.',
                    startingCounts=counts,
                    tallyRule='Transparent unit icons enlarged 10%; sole victory soft glow; exact ties share credit.',
                    rankingRule='Descending featured surviving HP for victories; ascending enemy surviving HP for defeats; victories outrank defeats; ties share medals; no time criterion.',
                    assets='Installed AoE2DE Trajan Pro, dialog_victory2/dialog_defeat2, civ emblems and existing opponent card; translucent grey result backing.',
                    status='draft_pending_review')
    if not stills_only and profile:
        from encode_comparison_fast import encode
        video=out/(profile['id']+'_vs_'+opponent['slug']+'_Overlay.mp4')
        encode(video,jobs,headers,counts_layer,footer_before,footer_after,duration,START,HOLD)
        metadata.update(video=str(video),audioSource=max(jobs,key=lambda j:j['end'])['civ'])
    elif not stills_only:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError('FFmpeg unavailable: add its installed bin directory to PATH')
        video = out/('Champi_Four_Civs_vs_'+opponent['slug']+'_Overlay.mp4')
        # One soundtrack only, from the longest battle. Never mix four recordings.
        audio_job = max(jobs, key=lambda j:j['end'])
        cmd = [ffmpeg,'-y','-v','error','-f','rawvideo','-pixel_format','rgb24',
               '-video_size',f'{W}x{H}','-framerate',str(FPS),'-i','pipe:0',
               '-ss',str(START),'-i',str(audio_job['run']/'battle.mp4'),
               '-map','0:v','-map','1:a?','-af','apad,afade=t=out:st='+str(duration-1)+':d=1',
               '-t',str(duration),'-c:v','libx264','-threads','3','-preset','veryfast',
               '-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
               '-movflags','+faststart',str(video)]
        with (out/'render.log').open('w') as log:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log)
            try:
                for n in range(math.ceil(duration*FPS)):
                    proc.stdin.write(compose(n/FPS).tobytes())
                    if n % 150 == 0:
                        print(f'Rendered {n}/{math.ceil(duration*FPS)} frames', flush=True)
                proc.stdin.close()
                if proc.wait(): raise RuntimeError('FFmpeg failed; see render.log')
            except BaseException:
                proc.kill(); proc.wait(); raise
        metadata.update(video=str(video), audioSource=audio_job['civ'])
        print(video, flush=True)
    (out/'comparison-manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    for j in jobs:
        if j['cap'] is not None:j['cap'].release()
    return metadata


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUT)
    p.add_argument('--stills-only', action='store_true')
    args = p.parse_args()
    build(args.output, args.stills_only)
