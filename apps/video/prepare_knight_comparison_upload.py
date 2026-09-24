"""Prepare the historical knight comparison package from encoded chapters.

Episode-specific: 74 chapters, historical balance wording and fixed profile
assumptions are not defaults for new v3 recordings. Adapt them from saved plans.
Description rows summarize the best chapter result; chapter-results.json keeps
all civilizations. These results are not the ranking report's adjusted draws.
Preparation is not upload approval; authorized=True requires existing permission.
Workflow: docs/video-production/YOUTUBE_PACKAGE_HANDOFF.md.
"""
import argparse
from pathlib import Path
from build_knight_comparison_series import read,save,read_probe,REPO
from prepare_champi_comparison_upload import stamp
from build_campaign_thumbnail import build as thumbnail


def prepare(plan,series_dir,intro,authorized=False):
    profile=read(plan);series=read(series_dir/'series-manifest.json')
    assembly=read(intro/'assembly-manifest.json');inputs=read(series_dir/'series-inputs.json')['chapters']
    civs=[c['civ'] for c in profile['columns']];unit=profile['unit']
    assert len(inputs)==len(series['chapters'])==74
    assert assembly['narrationPage1'] and assembly['narrationPage2']
    assert assembly['page2Timing']['postSpeechHoldSeconds']==3
    out=series_dir/'youtube';out.mkdir(exist_ok=True)
    title=f'{unit}: '+ ' vs '.join(civs)+' | 74 AoE2 DE Matchups'
    side=profile['columns'][0]['side']
    description=(f'Compare {", ".join(civs[:-1])} and {civs[-1]} {unit}-line armies against 74 opponents in recorded Age of Empires II DE battles.\n\n'
       'Army sizes balance resource cost and population using a geometric mean. The cheaper side has 27 units; there is no 5,000-resource limit. '
       'Shared-unit food/wood discounts count at half strength; gold discounts count fully. '
       'Ranged units get a small front line of hussars against melee units. '
       'Starting counts, surviving HP and the tally of best winners appear in the overlay.\n\n')
    if unit=='Paladin':description+='Lithuanian Paladins have four relics. Persians use Savar; Savar vs itself is not tested.\n\n'
    description+='Opponent Elite Leitis also have four relics.\n\n'
    description+=f'Try your own matchup: https://aoe2matchup.com/?civ1={side["civ"]}&unit1={side["slug"]}&age1=Imperial\n\n'
    description+="Chapters show the best result: W = victory, L = defeat, D = draw. HP is the winning army's remaining percentage (opponent HP for L).\n\n00:00 Introduction\n"
    description+=f"{stamp(assembly['firstPageSeconds'])} Four civilizations compared\n"
    cursor=assembly['matchupStartSeconds'];rows=[];checks=0
    for chapter,data in zip(series['chapters'],inputs):
        assert {r['civ'] for r in chapter['results']}==set(civs)
        for i,civ in enumerate(civs):
            path=data['runs'][civ]
            if path is None:
                assert profile['columns'][i]['side']['slug']==data['opponent']['slug']
                assert chapter['startingCounts'][i]==[None,None]
                continue
            recording=read(Path(path)/'recording.json')
            counts=[recording['sides'][s]['count'] for s in ('side1','side2')]
            assert counts==chapter['startingCounts'][i] and max(counts)<=27
            checks+=1
        # Chapter rank, not overall benchmark rank. Credit all tied best results;
        # retain every civilization in rows below even when the public line is short.
        best=[r for r in chapter['results'] if r['rank']==1 and r['winner']!='not_tested'];assert best
        outcome='W' if best[0]['winner']=='2' else 'L' if best[0]['winner']=='3' else 'D'
        # Encoded durations include frame rounding and the result hold. Accumulate
        # these after the measured intro offset; round only the displayed timestamp.
        duration=float(read_probe(Path(chapter['video']))['format']['duration'])
        label=data['opponent']['label'].removeprefix('Elite ')
        description+=f"{stamp(cursor)} {label} | {'/'.join(r['civ'] for r in best)} {outcome} {best[0]['percent']:.0f}%\n"
        rows.append(dict(opponent=data['opponent']['label'],opponentCivilization=data['opponent']['civ'],startSeconds=cursor,durationSeconds=duration,results=chapter['results'],startingCounts=chapter['startingCounts']))
        cursor+=duration
    assert abs(cursor-assembly['endingStartSeconds'])<.25
    description+=f"{stamp(cursor)} Thank you\n\n#AoE2 #AoE2DE #{unit} #RTS #BattleSimulation #UnitCounters"
    assert len(description)<=5000,(len(description),'description limit')
    assert len(title)<=100
    desc=out/'youtube-description.txt';desc.write_text(description,encoding='utf-8')
    prefix=out/'thumbnail';thumbnail(plan,prefix,unit,'Four Civilizations Compared')
    image=Path(str(prefix)+'-long.jpg')
    settings=dict(title=title,descriptionFile=str(desc),thumbnail=str(image),tags=['AoE2','Age of Empires II',unit,*civs,'unit matchups','battle simulation'],categoryId='20',defaultLanguage='en',defaultAudioLanguage='en',privacyStatus='private',selfDeclaredMadeForKids=False,containsSyntheticMedia=True,license='youtube',embeddable=True,uploadAuthorized=authorized)
    save(out/'youtube-proposed-settings.json',settings);save(out/'chapter-results.json',rows)
    preparation=out/'youtube-preparation.json'
    save(preparation,dict(video=assembly['video'],uploadAuthorized=authorized,targetChannelVerified=True,targetChannel=dict(id='UCKYN-pN4AZ3w4LpRxcdSciA',handle='@aoe2matchup'),authorization='Owner approved these intros and requested full comparison videos uploaded to YouTube.',sourceAssembly=str(intro/'assembly-manifest.json'),sourceSeries=str(series_dir/'series-manifest.json'),countChecks=checks,comparisonPolicy='geometric_shared_discount_v1'))
    if authorized:
        queue_path=REPO/'data/video-production-queue.json';queue=read(queue_path)
        approved=queue.setdefault('correctedMedia',{}).setdefault('approvedUploadPreparations',[])
        relative=preparation.relative_to(REPO).as_posix()
        if relative not in approved:approved.append(relative)
        save(queue_path,queue)
    print(preparation,flush=True);return preparation


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','series','intro'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--authorize-upload',action='store_true');a=p.parse_args()
    prepare(a.plan.resolve(),a.series.resolve(),a.intro.resolve(),a.authorize_upload)
