"""Join the approved intro and completed compilation; export chapter results."""
import json
import math
import subprocess
from pathlib import Path
from overlay.ffutil import find_ffmpeg, find_ffprobe

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT/'aoe2x/js_simulation/calibration/lab'
BASE = LAB/'compilations/tiger-unique-units'
OUT = BASE/'final'
LINK = 'https://aoe2matchup.com/?civ1=Wei&unit1=elite_tiger_cavalry_wei&age1=Imperial'


def probe(path):
    return json.loads(subprocess.check_output([find_ffprobe(), '-v', 'error',
        '-show_format', '-show_streams', '-of', 'json', str(path)]))


def timestamp(seconds):
    value = math.floor(seconds)
    return f'{value//60:02}:{value%60:02}'


def main():
    OUT.mkdir(exist_ok=True)
    ff = find_ffmpeg()
    original = json.loads((BASE/'manifest.json').read_text())
    intro = BASE/'intro-v4/tiger-cavalry-intro.mp4'
    intro_duration = float(probe(intro)['format']['duration'])
    battle = BASE/'tiger-cavalry-all-completed-overlays.mp4'
    battle_duration = float(probe(battle)['format']['duration'])
    results = []
    for chapter in original['chapters']:
        hpfile = LAB/'runs'/chapter['jobId']/'live/run_001/unit-hp-overlay/units.json'
        data = json.loads(hpfile.read_text())
        visible = [r for r in data['rows'] if r['videoSeconds'] < chapter['durationSeconds']]
        last = visible[-1]
        sides = {}
        for player in ('2', '3'):
            living = [u for u in last['sides'][player] if u['hp'] > 0]
            sides[player] = {'count': len(living), 'hp': sum(u['hp'] for u in living)}
        alive = [p for p in ('2','3') if sides[p]['count']]
        if len(alive) != 1:
            raise ValueError(f'Unresolved result: {chapter["title"]} {sides}')
        winner = alive[0]
        opponent = chapter['title'].split(' — ', 1)[1]
        results.append({**chapter, 'startSeconds': chapter['startSeconds']+intro_duration,
            'timestamp': timestamp(chapter['startSeconds']+intro_duration),
            'tigerResult': 'WIN' if winner=='2' else 'LOSS',
            'winner': 'Elite Tiger Cavalry' if winner=='2' else opponent,
            'loser': opponent if winner=='2' else 'Elite Tiger Cavalry',
            'winnerRemainingHp': sides[winner]['hp'], 'winnerSurvivors': sides[winner]['count'],
            'sides': sides, 'hpSource': str(hpfile), 'hpVideoSeconds': last['videoSeconds'],
            'conversionNote': 'Includes converted Tiger Cavalry' if opponent=='Missionary' else None})
    preface = f'''Elite Tiger Cavalry vs 59 Unique-Unit Matchups | AoE2 DE

Which unique units can Wei's Elite Tiger Cavalry beat? Watch 59 recorded Age of Empires II: Definitive Edition battles with live unit HP overlays, from close finishes to decisive counters.

Try your own matchup:
{LINK}

RULES
Equal resource cost, up to 27 units per main army; whole-unit rounding applies. In melee vs ranged fights, the ranged army gets nine Spanish cavalry as a free screening force. These controlled in-game tests are separate from the website simulation.

CHAPTERS / SPOILERS
WIN = Tiger Cavalry wins; LOSS = the named opponent wins. HP and survivors describe the winning army; HP is rounded and the screen is excluded. Missionary totals include converted Tigers.
00:00 Introduction
'''
    lines = []
    for row in results:
        label = row['title'].replace(' — ', ': ')
        lines.append(f'{row["timestamp"]} {label} | {row["tigerResult"]} {round(row["winnerRemainingHp"])} HP, {row["winnerSurvivors"]} left')
    description = preface+'\n'.join(lines)+'''

#AoE2 #AgeOfEmpires2 #AoE2DE #TigerCavalry #RTS #BattleSimulation #UnitCounters #StrategyGaming #DefenseStrategy
'''
    if len(description)>5000:
        raise ValueError(f'Description exceeds 5000 characters: {len(description)}')
    (OUT/'youtube-description.txt').write_text(description, encoding='utf-8')
    (OUT/'youtube-title.txt').write_text('Elite Tiger Cavalry vs 59 Unique-Unit Matchups | AoE2 DE', encoding='utf-8')
    (OUT/'chapter-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    meta = ';FFMETADATA1\ntitle=Elite Tiger Cavalry vs 59 Unique-Unit Matchups\n'
    chapters = [{'startSeconds':0,'title':'Introduction'}]+results
    for i, chapter in enumerate(chapters):
        end = chapters[i+1]['startSeconds'] if i+1<len(chapters) else intro_duration+battle_duration
        label = chapter['title']
        if i:
            label += f' | {chapter["tigerResult"]} | {round(chapter["winnerRemainingHp"])} HP'
        meta += f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(chapter["startSeconds"]*1000)}\nEND={round(end*1000)}\ntitle={label}\n'
    (OUT/'chapters.ffmeta').write_text(meta,encoding='utf-8')
    normalized = OUT/'intro-1440p60.mp4'
    with (OUT/'encode.log').open('w') as log:
        subprocess.run([ff,'-y','-v','warning','-i',str(intro),'-vf','scale=2560:1440:flags=lanczos,fps=60,format=yuv420p',
            '-c:v','libx264','-preset','fast','-crf','18','-threads','4','-video_track_timescale','15360',
            '-c:a','aac','-ar','48000','-ac','2','-b:a','192k','-map','0:v:0','-map','0:a:0',
            '-movflags','+faststart',str(normalized)],stdout=log,stderr=log,check=True)
        (OUT/'concat.txt').write_text(f"file '{normalized.as_posix()}'\nfile '{battle.as_posix()}'\n")
        final = OUT/'tiger-cavalry-complete-with-intro.mp4'
        subprocess.run([ff,'-y','-v','warning','-f','concat','-safe','0','-i',str(OUT/'concat.txt'),
            '-i',str(OUT/'chapters.ffmeta'),'-map','0:v:0','-map','0:a:0','-map_metadata','1','-map_chapters','1',
            '-c:v','copy','-c:a','aac','-ar','48000','-b:a','192k','-af','aresample=async=1',
            '-movflags','+faststart',str(final)],stdout=log,stderr=log,check=True)
    info=probe(final)
    if abs(float(info['format']['duration'])-intro_duration-battle_duration)>1:
        raise ValueError('Unexpected final duration')
    manifest={'output':str(final),'intro':str(intro),'battleCompilation':str(battle),
        'introDuration':intro_duration,'expectedDuration':intro_duration+battle_duration,
        'media':info,'matchups':len(results),'chapters':len(chapters),
        'descriptionCharacters':len(description),'websiteLink':LINK,
        'websiteVerified':'Browser showed Wei and Elite Tiger Cavalry selected without clicking',
        'battleVideoEncoding':'original H264 packets copied; intro upscaled to 1440p60'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'output':str(final),'seconds':info['format']['duration'],'descriptionCharacters':len(description)}))


if __name__=='__main__':
    main()
