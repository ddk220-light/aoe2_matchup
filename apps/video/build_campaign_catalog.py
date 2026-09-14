"""Discover campaign art and infer civs from parsed first-scenario Player 1.

GPV/encrypted campaigns are recorded as unresolved, never silently guessed.
"""
import contextlib
import hashlib
import io
import json
import os
import re
import tempfile
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

GAME = Path(os.environ.get('AOE2_GAME_DIR', 'C:/Program Files (x86)/Steam/steamapps/common/AoE2DE'))
OUTPUT = Path(__file__).parent / 'intro/campaign_catalog.json'


def probe(archive):
    raw=Path(archive).read_bytes()
    candidate=re.search(rb'1\.[0-9]{2}\x00\x00\x00\x00',raw)
    if not candidate:
        return {'status':'unresolved','parseError':'No supported embedded scenario header'}
    try:
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'first.aoe2scenario';p.write_bytes(raw[candidate.start():])
            with contextlib.redirect_stdout(io.StringIO()):
                scenario=AoE2DEScenario.from_file(str(p))
            player=next(p for p in scenario.player_manager.players if int(p.player_id)==1)
            return {'civilization':player.civilization.name,'player1Human':bool(player.human),
                    'status':'scenario-player-1','embeddedOffset':candidate.start(),
                    'archiveSha256':hashlib.sha256(raw).hexdigest()}
    except Exception as error:
        return {'status':'unresolved','parseError':str(error)[:180]}


def isolated_probe(archive):
    # Parser schema version is process-global; never mix versions in one process.
    try:
        r=subprocess.run([sys.executable,__file__,'--probe',str(archive)],capture_output=True,text=True,timeout=60)
        return json.loads(r.stdout)
    except Exception as error:
        return {'status':'unresolved','parseError':str(error)[:180]}


def apply_overrides(result):
    overrides=json.loads((OUTPUT.parent/'campaign_overrides.json').read_text())
    preferred={}
    for row in result['campaigns']:
        override=overrides.get(row['campaign'])
        if override:
            row['artAssociation']=override
        civ=override['civilization'] if override else row.get('civilization')
        if civ:
            preferred.setdefault(civ,{'campaign':row['campaign'],'background':row['backgrounds'][0],
                'reason':override['reason'] if override else 'Parsed first-scenario Player 1 civilization',
                'associationKind':'curated' if override else 'scenario-derived'})
        elif row['campaign'].startswith('cam0'):
            row['artAssociation']={'civilization':None,'reason':'Art of War learning collection; shared thematic fallback'}
        elif row['campaign'] in ('ccam1','fcam7'):
            row['artAssociation']={'civilization':None,'reason':'Historical battle collection; no single civilization'}
    preferred['WEI']={'campaign':'cam0intro','background':'textures/campaign/cam0/challenges_background.dds',
        'reason':'User-directed Art of War fallback for Wei','associationKind':'user-override'}
    scenario_overrides=OUTPUT.parent/'scenario_civilization_overrides.json'
    if scenario_overrides.exists():
        for civ, entry in json.loads(scenario_overrides.read_text()).items():
            config=GAME/'resources/_common/campaign'/(entry['campaign']+'.json')
            scenario=json.loads(config.read_text(encoding='utf-8-sig'))['Scenarios'][entry['scenarioIndex']]
            sequence=next(item['Data'] for item in scenario['IntroSequence']['SequenceItems']
                if any(slide.get('String')==entry['expectedIntroString'] for slide in item.get('Data',{}).get('Slides',[])))
            preferred[civ]={**entry,'background':sequence['SlideBackgroundImage'],
                'narrationEvent':sequence['Sound'],'associationKind':'scenario-localization'}
    result['preferredByCivilization']=preferred
    result['sources']=['https://www.ageofempires.com/games/aoeiide/the-mountain-royals/',
        'https://www.ageofempires.com/news/the-last-chieftains-campaign-preview/',
        'https://www.ageofempires.com/news/faq-the-last-chieftains/',
        'Installed campaign scenarios, slideshow JSON, peru_campaign.json; explicit curated exceptions in campaign_overrides.json']
    return result


def build():
    records = []
    root = GAME / 'resources/_common/campaign'
    for config in sorted(root.glob('*.json')):
        if config.stem.endswith('_layout') or config.stem.startswith('coop'):
            continue
        backgrounds = list(dict.fromkeys(re.findall(
            r'"SlideBackgroundImage"\s*:\s*"([^"]+)"', config.read_text())))
        if not backgrounds:
            continue
        row = {'campaign': config.stem, 'backgrounds': backgrounds,
               'config': str(config.relative_to(GAME)), 'status': 'unresolved'}
        archive = root / (config.stem + '.aoe2campaign')
        records.append(row)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[(row,pool.submit(isolated_probe,root/(row['campaign']+'.aoe2campaign')))
              for row in records if (root/(row['campaign']+'.aoe2campaign')).exists()]
        for row,future in jobs:
            row.update(future.result())
    preferred = {}
    for row in records:
        if row['status'] == 'scenario-player-1':
            preferred.setdefault(row['civilization'], {
                'campaign': row['campaign'], 'background': row['backgrounds'][0],
                'reason': 'First playable scenario Player 1 civilization; first candidate if multiple campaigns.'})
    # Explicit art-direction overrides are distinct from inferred campaign civs.
    preferred['WEI'] = {'campaign': 'cam0intro',
        'background': 'textures/campaign/cam0/challenges_background.dds',
        'reason': 'User-directed Art of War fallback for Wei; not a Wei campaign attribution.'}
    result = {'schemaVersion': 1, 'gameRoot': str(GAME), 'campaigns': records,
              'preferredByCivilization': preferred,
              'fallback': {'background': 'textures/campaign/cam0/challenges_background.dds',
                           'reason': 'Unmapped civilization: explicitly labeled generic Art of War fallback.'}}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(apply_overrides(result), indent=2) + '\n')
    print(f'{len(records)} campaigns; {sum(r["status"]=="scenario-player-1" for r in records)} scenario-derived mappings; {OUTPUT}')


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--probe':
        print(json.dumps(probe(sys.argv[2])))
    elif len(sys.argv)>1 and sys.argv[1]=='--refresh-themes':
        OUTPUT.write_text(json.dumps(apply_overrides(json.loads(OUTPUT.read_text())),indent=2)+'\n')
    else:
        build()
