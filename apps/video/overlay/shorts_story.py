"""Animated matchup bookends; public timing uses seconds, not GIF frame indices."""
from bisect import bisect_right
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageSequence
from overlay.civ_theme import nine_slice


def eased(progress):
    p = min(1, max(0, progress))
    return p*p*p*(10+p*(-15+6*p))


def faded_layer(layer, opacity):
    image = layer.copy()
    image.putalpha(image.getchannel('A').point(lambda a: round(a*opacity)))
    return image


def sweep_to_victory(battle, background, details, progress):
    """Game artwork wipes down; only then do winner details become visible."""
    reveal = eased((progress-.15)/.5)
    height = round(background.height*reveal)
    image = battle.copy()
    if height:
        image.alpha_composite(background.crop((0,0,background.width,height)))
    opacity = eased((progress-2/3)*3)
    if opacity:
        image.alpha_composite(faded_layer(details,opacity))
    return image

def intro_unit_name(name):
    """Short opening title; keep full upgrade names in the actual stat cards."""
    return name.removeprefix('Elite ').removeprefix('Heavy ')


def longest_command_voice(variants, civilization):
    return max((v for v in variants if v['civilization']==civilization),
               key=lambda v:v['durationSeconds'])


def sequential_intro_seconds(attacks, starts, speed=1):
    """Begin battle one second after the final one-shot attack finishes."""
    return max(start+attack.ends[-1]/1000/speed
               for attack,start in zip(attacks,starts)) + 1.0


def story_video_name(names):
    return '-vs-'.join(intro_unit_name(name).replace(' ', '-') for name in names) + '-Short-v8.mp4'


def framed_panel(background, frame, size, edge=24):
    """Fit existing artwork while protecting its painted border corners."""
    panel = nine_slice(background, size, edge=edge*4)
    panel.alpha_composite(nine_slice(frame, size, edge=edge))
    return panel


class AttackAnimation:
    def __init__(self, path, size):
        self.frames, self.ends = [], []
        total = 0
        path = Path(path)
        if path.is_dir():
            meta = json.loads((path / 'animation.json').read_text())
            source = []
            for name, duration in zip(meta['frames'], meta['durationsMs']):
                with Image.open(path / name) as frame:
                    source.append((frame.convert('RGBA'), duration))
        else:
            with Image.open(path) as gif:
                source = [(frame.convert('RGBA'), frame.info.get('duration', 100))
                          for frame in ImageSequence.Iterator(gif)]
        for tile, duration in source:
            tile.thumbnail(size, Image.Resampling.LANCZOS)
            self.frames.append(tile)
            # Integer milliseconds avoid an extra video-frame hold at 150 ms.
            total += duration
            self.ends.append(total)
        if path.is_dir() and meta.get('source', '').lower().endswith('.sld'):
            from prepare_story_attacks import native_shadow_frames
            shadows = native_shadow_frames(meta['source'], self.frames[0].size, meta['direction'])
            for tile, shadow in zip(self.frames, shadows):
                tile.info['nativeShadow'] = shadow

    def at(self, seconds, speed=1, loop=True):
        milliseconds = seconds*speed*1000
        if loop:
            milliseconds %= self.ends[-1]
        else:
            milliseconds = max(0,milliseconds)
        return self.frames[min(len(self.frames)-1,bisect_right(self.ends,milliseconds))]


def split_reveal(panel, battle, progress):
    """One eased upward/downward move, leaving the first battle frame beneath."""
    p = min(1, max(0, progress))
    ease = p * p * p * (10 + p * (-15 + 6 * p))
    half = panel.height // 2
    distance = round(half * ease)
    result = battle.copy()
    result.alpha_composite(panel.crop((0, 0, panel.width, half)), (0, -distance))
    result.alpha_composite(panel.crop((0, half, panel.width, panel.height)), (0, half + distance))
    return result


def featured_result(row, owner='2'):
    own = row['sides'][owner]
    opponent = row['sides']['3' if owner == '2' else '2']
    count = sum(u['hp'] > 0 for u in own)
    hp = round(sum(u['hp'] for u in own))
    enemy_hp = sum(u['hp'] for u in opponent)
    title = 'Victorious' if hp > 0 and enemy_hp == 0 else 'Defeated' if hp == 0 and enemy_hp > 0 else 'Draw'
    return title, count, hp


def ending_frame_count(cue_seconds, fps):
    """Hold up to five seconds, without extending past the victory cue."""
    return int(min(5.0, cue_seconds) * fps)


def featured_hp_fraction(initial, final, owner='2'):
    return sum(u['hp'] for u in final['sides'][owner]) / sum(u['hp'] for u in initial['sides'][owner])


def winning_result(initial, final):
    """Choose the victorious main army, never the P4 buffer or the losing top side."""
    for index, owner in enumerate(('2','3')):
        title, survivors, hp = featured_result(final, owner)
        if title == 'Victorious':
            return {'owner':owner, 'unitIndex':index, 'title':title,
                    'survivors':survivors, 'hp':hp,
                    'hpFraction':featured_hp_fraction(initial, final, owner)}
    raise ValueError('A victory ending requires a decided main-army winner')


def hp_label(fraction):
    return f'{fraction:.0%} HP'


def result_backing(base, top, bottom):
    shade = Image.new('RGBA', base.size)
    ImageDraw.Draw(shade).rectangle((0, top, base.width-1, bottom-1), fill=(35,35,35,140))
    return Image.alpha_composite(base, shade)


def story_audio_filter(start, battle_seconds, source_seconds, intro=3, ending=5,
                       input_label='1:a', victory_label='2:a', intro_label=None, transition=0):
    """Post-battle soundtrack under the opener; combat remains aligned at intro.

    The extra 150 ms of prelude is consumed by the crossfade, not by moving
    combat. At the first ending frame, replace the recording with the win cue.
    """
    gap = (f'anullsrc=r=48000:cl=stereo:d={transition}[exit];' if transition else '')
    if intro_label is not None:
        game_fade = f',afade=t=out:st={battle_seconds-.12}:d=0.12' if transition else ''
        return (f'[{intro_label}]atrim=duration={intro},apad=whole_dur={intro},asetpts=N/SR/TB,'
                f'afade=t=out:st={intro-.03}:d=0.03[opener];'
                f'[{input_label}]atrim=start={start}:duration={battle_seconds},asetpts=N/SR/TB{game_fade}[game];'
                f'[{victory_label}]atrim=duration={ending},asetpts=N/SR/TB,'
                f'afade=t=out:st={ending-.08}:d=0.08[victory];'+gap+
                '[opener][game]'+('[exit]' if transition else '')+
                f'[victory]concat=n={4 if transition else 3}:v=0:a=1[a]')
    overlap = .15
    prelude_start = source_seconds - intro - overlap - .1
    return (f'[{input_label}]asplit=2[pre][game];'
            f'[pre]atrim=start={prelude_start}:duration={intro+overlap},asetpts=N/SR/TB,'
            'afade=t=in:d=0.1[p];'
            f'[game]atrim=start={start}:duration={battle_seconds},asetpts=N/SR/TB[g];'
            f'[p][g]acrossfade=d={overlap}:c1=tri:c2=tri,'
            f'atrim=duration={intro+battle_seconds}[main];'
            f'[{victory_label}]atrim=duration={ending},asetpts=N/SR/TB,'
            f'afade=t=out:st={ending-.08}:d=0.08[victory];'+gap+
            '[main]'+('[exit]' if transition else '')+
            f'[victory]concat=n={3 if transition else 2}:v=0:a=1[a]')
