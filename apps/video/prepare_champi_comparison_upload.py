"""Prepare chapter/results metadata for the approved four-civilization video.

No network operations. Authorization is recorded only when explicitly supplied.
The upload command still verifies the live channel and resumable source identity.
This historical 74-chapter package has fixed paths and v1 policy wording; adapt
those from saved inputs for a new family. Public chapter lines summarize only
the best result, while chapter-results.json retains every civilization. The
ranking report's close-finish draw convention is not applied here automatically.
Workflow: docs/video-production/YOUTUBE_PACKAGE_HANDOFF.md.
"""
import argparse
import json
from pathlib import Path

from build_champi_comparison_bookends import probe
from build_champi_comparison_overlay import CIVS

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT/'data/local/champi-overlay-v3'
INTRO = ROOT/'data/local/champi-comparison-intro'


def stamp(seconds):
    value = int(seconds)
    return f'{value//60:02}:{value%60:02}'


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def main(authorized=False):
    series = json.loads((SERIES/'series-manifest.json').read_text())
    assembly = json.loads((INTRO/'assembly-manifest.json').read_text())
    inputs = json.loads((ROOT/'data/local/champi-comparison-full/series-inputs.json').read_text())['chapters']
    assert len(inputs) == len(series['chapters']) == 74
    assert assembly['narrationPage1'] and assembly['narrationPage2']
    assert assembly['page2Timing']['postSpeechHoldSeconds'] == 3
    video = Path(assembly['video'])
    details = probe(video)
    assert abs(float(details['format']['duration'])-assembly['durationSeconds']) < .1
    out = SERIES/'youtube'; out.mkdir(exist_ok=True)
    title = 'Champi Warrior: Incas vs Mapuche vs Muisca vs Tupi | 74 AoE2 DE Matchups'
    description = (
        'Four fully upgraded Champi armies face the same 74 opponents, side by side. '
        'Compare Incas, Mapuche, Muisca and Tupi in recorded Age of Empires II DE battles.\n\n'
        'Army sizes balance resource cost and population using a geometric mean, capped at 27. '
        'Shared-unit food/wood discounts count at half strength; gold discounts count fully. '
        'Ranged units get a small front line of hussars against melee units. '
        'The overlay shows starting counts, results, surviving HP and a tally of best winners.\n\n'
        'Try your own matchup: https://aoe2matchup.com/?civ1=Incas&unit1=elite_champi_warrior_incas&age1=Imperial\n\n'
        'Chapters list the best Champi result: W = victory, L = defeat. '
        'HP is the winning army\'s remaining percentage (opponent HP for L). '
        'Ties credit every listed civilization.\n\n'
        '00:00 Introduction\n'
        f"{stamp(assembly['firstPageSeconds'])} Four civilizations compared\n"
    )
    cursor = assembly['matchupStartSeconds']
    rows = []
    for chapter, data in zip(series['chapters'], inputs):
        assert data['opponent']['comparison']['policy'] == 'geometric_shared_discount_v1'
        assert {r['civ'] for r in chapter['results']} == set(CIVS)
        for i, civ in enumerate(CIVS):
            run = data['runs'][civ]
            recorded = json.loads((Path(run)/'recording.json').read_text())
            counts = [recorded['sides'][side]['count'] for side in ('side1','side2')]
            assert counts == chapter['startingCounts'][i]
            assert max(counts) <= 27
        best = [r for r in chapter['results'] if r['rank'] == 1]
        assert best
        outcome = 'W' if best[0]['winner'] == '2' else 'L'
        credit = '/'.join(r['civ'] for r in best)
        # Actual encoded chapter duration includes frame rounding; use it for
        # cumulative timestamps rather than summing ideal fractional durations.
        duration = float(probe(Path(chapter['video']))['format']['duration'])
        label = data['opponent']['label'].removeprefix('Elite ')
        description += f"{stamp(cursor)} {label} | {credit} {outcome} {best[0]['percent']:.0f}%\n"
        rows.append(dict(opponent=data['opponent']['label'],opponentCivilization=data['opponent']['civ'],
                         startSeconds=cursor,durationSeconds=duration,startingCounts=chapter['startingCounts'],
                         results=chapter['results']))
        cursor += duration
    assert abs(cursor-assembly['endingStartSeconds']) < .25
    description += f"{stamp(assembly['endingStartSeconds'])} Thank you\n\n#AoE2 #AoE2DE #ChampiWarrior #Incas #RTS #BattleSimulation #UnitCounters"
    assert len(description) <= 5000, len(description)
    assert len(title) <= 100
    desc = out/'youtube-description.txt'; desc.write_text(description, encoding='utf-8')
    thumbnail = ROOT/'apps/video/intro/thumbnails/champi-warrior-long.jpg'
    assert thumbnail.is_file() and thumbnail.stat().st_size < 2*1024*1024
    settings = dict(title=title,descriptionFile=str(desc),thumbnail=str(thumbnail),
                    tags=['AoE2','Age of Empires II','Champi Warrior','Incas','Mapuche','Muisca','Tupi','unit matchups','battle simulation'],
                    categoryId='20',defaultLanguage='en',defaultAudioLanguage='en',privacyStatus='private',
                    selfDeclaredMadeForKids=False,containsSyntheticMedia=True,license='youtube',embeddable=True,
                    uploadAuthorized=authorized)
    save(out/'youtube-proposed-settings.json',settings)
    save(out/'chapter-results.json',rows)
    save(out/'youtube-preparation.json',dict(video=str(video),uploadAuthorized=authorized,
         targetChannelVerified=True,targetChannel=dict(id='UCKYN-pN4AZ3w4LpRxcdSciA',handle='@aoe2matchup'),
         authorization='User requested revised narrated comparison and YouTube upload; no Taildrop.',
         sourceAssembly=str(INTRO/'assembly-manifest.json'),sourceSeries=str(SERIES/'series-manifest.json'),
         countChecks=296,comparisonPolicy='geometric_shared_discount_v1'))
    print(json.dumps(dict(preparation=str(out/'youtube-preparation.json'),descriptionCharacters=len(description),
                          durationSeconds=assembly['durationSeconds'],countChecks=296)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-upload',action='store_true',help='Only after explicit user upload authorization')
    main(parser.parse_args().authorize_upload)
