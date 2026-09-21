"""Prepare a normal land-unit episode without driving the game or uploading.

Defaults to a dry run. --write creates reviewed-template adapters and manifests
only after every canonical plan passes the installed-cost checks. Existing
episodes are never overwritten. See docs/VIDEO_PRODUCTION_RUNBOOK.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from aoe2x.lab.config import load_config
from aoe2x.lab.balance import DEFAULT_BALANCE, DEFAULT_COMPARISON_POLICY, balance_description
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import safe_slug, write_json
from aoe2x.lab.planner import plan_matchup

ROOT = Path(__file__).resolve().parents[2]


def episode_files(root: Path, key: str, slug: str) -> tuple[dict, dict[Path, str]]:
    """Return prospective source files; no filesystem or external mutations.

    The Monaspa assembly and selection adapters are the current complete land
    template. Copy their behavior, but derive counts and every identity from the
    roster. Deliberately reject special scenarios rather than inherit a screen
    or description that would misrepresent them.
    """
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', key):
        raise ValueError('Use a lowercase kebab-case episode key')
    roster = json.loads((root / 'data/unique-unit-roster.json').read_text())['units']
    subjects = roster + json.loads((root / 'data/recording-subjects.json').read_text())['units']
    unit = next((u for u in subjects if u['slug'] == slug), None)
    if unit is None:
        raise ValueError('Register the exact civilization/unit identity before scaffolding')
    if unit.get('naval') or unit['label'] in ('Flaming Camel', 'Mounted Trebuchet', 'Missionary'):
        raise ValueError('Special scenario: use the exception procedure in the runbook')
    label, civ = unit['label'], unit['civ']
    # Names enter reviewed Python string templates. Fail instead of emitting an
    # unescaped script for a future identity containing quotes or control text.
    if not all(re.fullmatch(r'[A-Za-z0-9 _()/-]+', value) for value in (label, civ, slug)):
        raise ValueError('This identity needs an explicitly escaped custom adapter')
    opponents = sorted((u for u in roster if u['slug'] != slug),
                       key=lambda u: (u['civ'].casefold(), u['label'].casefold()))
    if len(opponents) < 10:
        raise ValueError('A full episode needs at least ten distinct opponents')
    ident = key.replace('-', '_')
    rows = [dict(id=f'{ident}_unique_{i:02}_{safe_slug(u["civ"])}_{safe_slug(u["slug"])}',
                 side2=slug, civ2=civ, side3=u['slug'], civ3=u['civ'],
                 balance=dict(mode=DEFAULT_BALANCE, cap=27))
            for i, u in enumerate(opponents, 1)]
    manifest = dict(schemaVersion=1, matchups=rows)
    encoded = json.dumps(manifest, indent=2) + '\n'
    files = {Path(f'aoe2lab.recorder.{key}-all-unique.json'): encoded,
             Path(f'aoe2lab.overlays.{key}-final.json'): encoded}
    replacements = [('elite_monaspa_georgians', slug), ('elite-monaspa', key),
                    ('elite_monaspa', ident), ('Elite Monaspa', label),
                    ('Georgians', civ), ('#FlemishMilitia', '#' + re.sub(r'[^A-Za-z0-9]', '', label)),
                    ('#EliteMonaspa', '#' + re.sub(r'[^A-Za-z0-9]', '', label))]
    for source, target in [
        ('build_elite_monaspa_final.py', f'build_{ident}_final.py'),
        ('prepare_elite_monaspa_final_shorts.py', f'prepare_{ident}_final_shorts.py'),
    ]:
        text = (root / 'apps/video' / source).read_text(encoding='utf-8')
        for old, new in replacements:
            text = text.replace(old, new)
        # Historical assembly adapters describe their original equal-resource
        # captures. New episodes must describe the benchmark they actually use.
        text = text.replace(
            'Equal resources using civilization-specific Imperial costs per individual unit, maximum 27 units per main army.',
            balance_description({'balance': {'mode': DEFAULT_BALANCE, 'comparisonPolicy': DEFAULT_COMPARISON_POLICY, 'cap': 27}}))
        # The roster may have 74 opponents when the subject is outside it.
        text = text.replace('==73', f'=={len(rows)}').replace("'matchups':73", f"'matchups':{len(rows)}")
        text = text.replace('vs 73 Unique', f'vs {len(rows)} Unique')
        compile(text, target, 'exec')
        files[Path('apps/video') / target] = text
    capture = (root / 'apps/video/run_elite_obuch_capture.py').read_text(encoding='utf-8')
    for old, new in [('elite-obuch', key), ('elite_obuch', ident), ('Obuch', label)]:
        capture = capture.replace(old, new)
    capture = capture.replace(f"report=LAB/'campaigns/{key}-all-unique'", f"report=LAB/'campaigns/{key}-canonical'")
    capture = capture.replace("result['total']=73", f"result['total']={len(rows)}")
    compile(capture, f'run_{ident}_capture.py', 'exec')
    files[Path(f'apps/video/run_{ident}_capture.py')] = capture
    # Offline steps can be invoked individually before approval. This finisher
    # explicitly acknowledges upload authorization and still waits for visual QA.
    finisher = f'''"""Finish the {label} package after recorded upload authorization."""
import argparse
import msvcrt
import traceback
import finish_pending_production as production

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upload-authorized', action='store_true')
    args = parser.parse_args()
    if not args.upload_authorized:
        parser.error('Use individual offline stages until upload authorization is recorded')
    production.EPISODES = [({key!r}, {label!r}, {civ!r}, {slug!r})]
    production.STATE = production.ROOT / 'data/local/{key}-production-status.json'
    lock = (production.ROOT / 'data/local/final-production.lock').open('a+b')
    lock.write(b'0'); lock.flush(); lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        production.main()
    except Exception:
        production.status({key!r}, 'NEEDS_ATTENTION', error=traceback.format_exc())
        raise
'''
    files[Path(f'apps/video/finish_{ident}_production.py')] = finisher
    intro = dict(civilization=civ.upper(), unit=label,
                 art=f'assets/{key}-campaign.png', sources=[],
                 slides=[dict(duration=25, paragraphs=['TODO: source and review the unit overview.']),
                         dict(duration=25, paragraphs=['TODO: source and review the unique abilities.'])],
                 videoFilename=f'{key}-intro.mp4',
                 music=dict(file=f'assets/{civ.lower()}-theme.wav', identity='TODO: verified civilization theme'))
    files[Path(f'apps/video/intro/{key}.json')] = json.dumps(intro, indent=2) + '\n'
    episode = dict(key=key, subject=unit, manifest=f'aoe2lab.recorder.{key}-all-unique.json',
                   matchups=len(rows), status='planned', opponents='all_except_self',
                   player4Buffer='golden', deliverables=['raw_video_and_grpc'],
                   authorization='Scaffold only; operator must record capture and publication authorization.',
                   recordingReports=f'aoe2x/js_simulation/calibration/lab/campaigns/{key}-canonical')
    return episode, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--write', action='store_true', help='Write new files after a complete cost preflight')
    args = parser.parse_args()
    episode, files = episode_files(ROOT, args.key, args.slug)
    queue_path = ROOT / 'data/video-production-queue.json'
    queue = json.loads(queue_path.read_text(encoding='utf-8-sig'))
    existing = queue.get('episodes', []) + queue.get('followupQueue', {}).get('episodes', [])
    collisions = [str(p) for p in files if (ROOT / p).exists()]
    if any(e['key'] == args.key for e in existing) or collisions:
        parser.error('Episode already exists; resume it instead of overwriting: ' + ', '.join(collisions))
    print(json.dumps(dict(episode=episode, files=list(map(str, files)), dryRun=not args.write), indent=2))
    if not args.write:
        return
    manifest = json.loads(files[Path(episode['manifest'])])
    plans = []
    config = load_config()
    for spec in manifest['matchups']:
        request = dict(schemaVersion=1, jobId=spec['id'],
                       side2=dict(slug=spec['side2'], civ=spec['civ2']),
                       side3=dict(slug=spec['side3'], civ=spec['civ3']), balance=spec['balance'])
        plan = plan_matchup(config, request)
        validate_plan_costs(plan)
        plans.append(plan)
    # No production metadata is published until all plans are known to be valid.
    for relative, text in files.items():
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as output:
            output.write(text)
    episode['order'] = max((e.get('order', 0) for e in existing), default=0) + 1
    queue.setdefault('episodes', []).append(episode)
    write_json(queue_path, queue)
    write_json(ROOT / f'data/local/{args.key}-capture-preflight.json',
               dict(passed=True, subject=episode['subject'], matchups=len(plans), plans=plans))
    print('Prepared only. Review the roster, complete the intro draft, and follow the runbook before capture or upload.')


if __name__ == '__main__':
    main()
