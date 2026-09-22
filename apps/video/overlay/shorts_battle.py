"""Transparent Short HUD, rich cards and a gentle opposing card entrance."""
from functools import lru_cache
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from overlay.static_stats import GameFont, portrait_path, panel, effective_cost, special_effects
from overlay.shorts_story import eased, faded_layer

W, H = 1080, 1920
GAME_Y, CARD_Y = 330, 1435
LIGHT = (246,230,191,255)
DARK = (57,28,27,255)
BLUE, RED = (88,140,255,255), (244,101,89,255)


def readability_scrim(size=(W,H), *, top=GAME_Y, bottom=H-GAME_Y-W):
    """Neutral fades capped at 15% opacity, with a fully clear middle."""
    width, height = size
    y = np.arange(height)
    upper = np.clip(1-y/top,0,1)**1.3
    lower = np.clip((y-(height-bottom))/(bottom-1),0,1)**1.3
    alpha = np.rint(255*.15*np.maximum(upper,lower)).astype(np.uint8)
    image = Image.new('RGBA',size,(20,18,15,0))
    image.putalpha(Image.fromarray(np.repeat(alpha[:,None],width,axis=1)))
    return image


def battlefield_canvas(gameplay, recording, crop, *, size=(W,H), game_y=GAME_Y,
                       recording_top=0):
    """Protect the approved battle crop; reveal only adjacent real recorded terrain."""
    x,y,extent = crop
    scale = size[0]/extent
    transform = np.array([[scale,0,-x*scale],[0,scale,game_y-(y-recording_top)*scale]],dtype=np.float32)
    field = cv2.warpAffine(recording[recording_top:],transform,size,flags=cv2.INTER_LANCZOS4,
                           borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0))
    result = Image.fromarray(cv2.cvtColor(field,cv2.COLOR_BGR2RGB)).convert('RGBA')
    sharp = gameplay.resize((size[0],size[0]),Image.Resampling.LANCZOS).convert('RGBA')
    result.alpha_composite(sharp,(0,game_y))
    return result


def slide_cards(base, cards, seconds, *, y=CARD_Y, duration=.65):
    p = min(1,max(0,seconds/duration))
    ease = p*p*p*(10+p*(-15+6*p))
    image = base.copy()
    for index,card in enumerate(cards):
        start = -card.width if index == 0 else base.width
        finish = 20 if index == 0 else base.width-20-card.width
        x = round(start+(finish-start)*ease)
        image.alpha_composite(card,(x,y))
    return image


def exit_cards(base, cards, progress, *, y=CARD_Y):
    ease = eased(progress)
    image = base.copy()
    for index,card in enumerate(cards):
        start = 20 if index == 0 else base.width-20-card.width
        finish = -card.width if index == 0 else base.width
        x = round(start+(finish-start)*ease)
        image.alpha_composite(faded_layer(card,1-ease),(x,y))
    return image


class BattleOverlay:
    def __init__(self, units, rows, plan, game, *, start=.2, recording_top=0):
        from overlay.unit_timeline import sample_at, ordered_units
        from aoe2x.lab.balance import balance_caption
        self.sample_at, self.ordered_units = sample_at, ordered_units
        self.rows, self.times = rows, [r['videoSeconds'] for r in rows]
        self.start = start
        self.recording_top = recording_top
        self.font = GameFont(game)
        self.scrim = readability_scrim()
        self.cards, self.card_details = [], []
        for index, entry in enumerate(units):
            stats = entry['stats']
            relics = plan['scenario'].get('opponentLithuanianRelics',0) if index == 1 else 0
            detail = {'cost':effective_cost(plan[f'side{index+2}']),
                      'effects':special_effects(stats,relics=relics)}
            card,_ = panel(stats,units[1-index]['stats'],self.font,game,
                           BLUE if index == 0 else RED,details=detail)
            card.thumbnail((510,350),Image.Resampling.LANCZOS)
            self.cards.append(card)
            self.card_details.append({'unit':entry['unit'], 'costBasis':'per unit after discounts', **detail})
        mixed = plan['scenario']['family'] in ('melee_vs_ranged','ranged_vs_melee')
        self.footer_lines = [(balance_caption(plan),1808 if mixed else 1812,29)]
        if mixed:
            rule = ('No extra frontline buffer' if plan['scenario'].get('player4Buffer') == 'none'
                    else 'Ranged units get a small front line of Hussars')
            self.footer_lines.append((rule,1844,27))
        self.footer_lines.append(('aoe2matchup.com',1880 if mixed else 1860,25))
        self.origins = {}
        for row in rows:
            for index,owner in enumerate(('2','3')):
                for unit in row['sides'][owner]:
                    self.origins.setdefault(unit['id'],index)
        capacity = max(27,max(sum(u['hp']>0 for u in r['sides'][o]) for r in rows for o in ('2','3')))
        self.columns = math.ceil(capacity/3)
        self.step = min(56,504//self.columns)
        self.tile_size = self.step-4
        self.portraits = [Image.open(portrait_path(u['unit'])).convert('RGBA').resize((48,48),Image.Resampling.LANCZOS)
                          for u in units]
        self.dead = [ImageEnhance.Brightness(ImageOps.grayscale(im).convert('RGBA')).enhance(.35)
                     for im in self.portraits]
        self.battle_footer = self.footer(LIGHT)

    @lru_cache(maxsize=1024)
    def label(self,text,size,color):
        image = Image.new('RGBA',(math.ceil(self.font.width(text,size))+8,size+18))
        self.font.draw(image,(2,0),text,size,color)
        return image

    def put(self,image,text,x,y,size,color=LIGHT,center=False):
        tile = self.label(text,size,color)
        image.alpha_composite(tile,(round(x-tile.width/2) if center else x,y))

    def footer(self,color):
        image = Image.new('RGBA',(W,H))
        for text,y,size in self.footer_lines:
            self.put(image,text,540,y,size,color,center=True)
        return image

    @lru_cache(maxsize=1024)
    def unit_tile(self,side,origin,hp,max_hp):
        image = Image.new('RGBA',(52,61))
        draw = ImageDraw.Draw(image)
        image.alpha_composite(self.portraits[origin] if hp>0 else self.dead[origin],(2,2))
        draw.rectangle((0,0,51,51),outline=(192,162,104,255) if hp>0 else (74,71,66,255),width=2)
        draw.rectangle((1,53,50,59),fill=(42,39,32,210))
        if hp>0:
            width = max(1,round(48*min(1,hp/max(1,max_hp))))
            draw.rectangle((2,54,1+width,58),fill=BLUE if side == 0 else RED)
        return image.resize((self.tile_size,round(61*self.tile_size/52)),Image.Resampling.LANCZOS)

    @lru_cache(maxsize=24)
    def queues(self,side2,side3):
        image = Image.new('RGBA',(W,320))
        ImageDraw.Draw(image).line((540,32,540,301),fill=(120,97,57,130),width=1)
        for side,units in enumerate((side2,side3)):
            x = 28+530*side
            count = sum(hp>0 for _,hp,_ in units)
            hp = round(sum(hp for _,hp,_ in units))
            self.put(image,str(count),x+2,33,54)
            self.put(image,f'{hp} HP',x+113,51,29)
            for index,(entity,hp,max_hp) in enumerate(units[:self.columns*3]):
                row,col = divmod(index,self.columns)
                image.alpha_composite(self.unit_tile(side,self.origins[entity],hp,max_hp),
                                      (x+col*self.step,101+row*66))
        return image

    def header(self,seconds):
        row = self.sample_at(self.rows,self.times,seconds+self.start)
        sides = [tuple((u['id'],u['hp'],u['maxHp']) for u in self.ordered_units(row['sides'][owner]))
                 for owner in ('2','3')]
        return self.queues(*sides)

    def compose(self,gameplay,seconds,*,recording,crop,exit_progress=None):
        image = battlefield_canvas(gameplay,recording,crop,recording_top=self.recording_top)
        if exit_progress is not None:
            opacity = 1-eased(exit_progress)
            for layer in (self.scrim,self.header(seconds),self.battle_footer):
                image.alpha_composite(faded_layer(layer,opacity))
            return exit_cards(image,self.cards,exit_progress)
        image.alpha_composite(self.scrim)
        image.alpha_composite(self.header(seconds))
        image.alpha_composite(self.battle_footer)
        return slide_cards(image,self.cards,seconds)

    def victory_footer(self,base):
        image = base.copy()
        ImageDraw.Draw(image).rectangle((0,1422,W-1,H-1),fill=(205,183,147,255))
        image.alpha_composite(self.footer(DARK))
        return slide_cards(image,self.cards,.65)
