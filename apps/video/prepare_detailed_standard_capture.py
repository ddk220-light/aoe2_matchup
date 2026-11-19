"""Freeze five-trial standard matchups on the approved detailed winter map.

Mixed melee/ranged fights get both scaled-Hussar and no-Hussar trials. Same-type
fights are recorded once, since their buffer settings would be identical.
Catalogs, historical recordings and Golden templates are read-only inputs.
"""
import argparse
import contextlib
import dataclasses
import io
import json
import pickle
import shutil
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import _load_stack, _validate_scenario, capture_template_path
from aoe2x.lab.planner import plan_matchup
from prepare_jomsviking_capture import DAT, NEW_UNITS, audited_price
from prepare_norse_standard_capture import CATALOGS, OPPONENTS, available, winter_templates
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/local/norse-standard-capture'
VISUAL = ROOT / 'data/local/arena-theme-review/scenarios/Winter Campaign Study - Detailed Battlefield.aoe2scenario'
VISUAL_HASH = '50752ac0b67afa2ed91b47d1f02c3364355a673b729f88bf137f81b43b5b081b'
GUARD_CIVS = ('Byzantines', 'Danes', 'Saxons', 'Varangians', 'Vikings')
MOUNTED_CIVS = ('Danes', 'Saxons', 'Varangians', 'Franks')
EXTRACTED = ROOT / 'data/local/dat-release-audit/installed'


def trial_settings(subject_ranged, opponent_ranged):
    """Never manufacture duplicate buffer/no-buffer samples for same-type fights."""
    if subject_ranged == opponent_ranged:
        return ('no_buffer',)
    return ('with_hussars', 'no_buffer')


def scenario_settings(subject_ranged, opponent_ranged, setting, scenery):
    mixed = subject_ranged != opponent_ranged
    if mixed and setting == 'with_hussars':
        family = 'ranged_vs_melee' if subject_ranged else 'melee_vs_ranged'
        return dict(scenery=scenery[family], player4Buffer='scaled', subjectOwner=2)
    # The no-P4 Golden owns the correct patrols and diplomacy; never just erase
    # support units from a mixed-family map and leave its player configuration.
    family = 'ranged_vs_ranged' if subject_ranged or opponent_ranged else 'melee_vs_melee'
    return dict(goldenFamily=family, player4Buffer='none', scenery=scenery[family], subjectOwner=2)


def prepare(work, group, guards):
    if work.exists():
        raise FileExistsError(f'Refuse to overwrite any existing preparation: {work}')
    if sha256(VISUAL) != VISUAL_HASH:
        raise ValueError('Detailed scenery changed since review')
    prior = read(BASE / 'source.json')
    if sha256(DAT) != prior['datSha256']:
        raise ValueError('Installed DAT changed; review actual costs before planning')
    audit = read(ROOT / 'data/local/dat-release-audit/audit.json')
    if sha256(DAT) != audit['sources']['installed_dat']['sha256']:
        raise ValueError('Installed extraction belongs to a different DAT')
    for source in audit['sources']['audit_extractions']:
        if '/installed/' in source['path'].replace('\\', '/'):
            path = EXTRACTED / source['path'].replace('\\', '/').split('/')[-1]
            if sha256(path) != source['sha256']:
                raise ValueError(f'Installed extraction changed: {path.name}')
    import aoe2x.dbgen.unit_analyzer as module
    module.OUTPUT_DIR = EXTRACTED
    analyzer = module.UnitAnalyzer()
    catalogs = {name: read(ROOT / 'data' / name) for name in CATALOGS}
    catalog_hashes = {name: sha256(ROOT / 'data' / name) for name in CATALOGS}
    entries = catalogs['unique-unit-roster.json']['units'] + catalogs['recording-subjects.json']['units']

    def resolve(civ, master):
        found = [r for r in entries if r['civ'] == civ and r['master'] == master]
        if len(found) != 1:
            raise ValueError(f'Expected one registered unit for {civ}/{master}')
        row = found[0]
        available(civ, master)
        actual = audited_price(analyzer, row)
        saved = catalogs['recording-costs.json']['units'][civ + '|' + row['slug']]
        for key in ('effectiveCost', 'purchaseCost', 'unitsPerPurchase'):
            if actual[key] != saved[key]:
                raise ValueError(f'Cost mismatch: {civ}/{master}/{key}; do not change frozen catalogs')
        return row

    opponents = [resolve(c, m) for c, _, m, *_ in OPPONENTS]
    if group == 'norse':
        subjects = [resolve(c, m) for c, _, _, m, *_ in NEW_UNITS]
    elif group == 'guards':
        if len(guards) != 4 or len(set(guards)) != 4:
            raise ValueError('Four explicitly selected Guard civilizations are required')
        subjects = [resolve(c, 2704) for c in guards]
    else:
        subjects = [resolve(c, 2701) for c in MOUNTED_CIVS]

    work.mkdir(parents=True)
    # Freeze the actual scenery input with the capture package for later rebuilds.
    visual_copy = work / 'scenery-source' / VISUAL.name
    visual_copy.parent.mkdir()
    shutil.copyfile(VISUAL, visual_copy)
    config = load_config()
    stack = _load_stack(config)
    with (ROOT / 'data/local/viking-sagas-research/installed-dat.pkl').open('rb') as stream:
        raw_dat = pickle.load(stream)
    scenery = winter_templates(config, raw_dat, visual_source=visual_copy, work=work)
    save(work / 'opponents.json', read(BASE / 'opponents.json'))
    save(work / 'source.json', dict(datPath=str(DAT), datSha256=sha256(DAT),
        visualSource=str(VISUAL), visualSha256=VISUAL_HASH, catalogHashes=catalog_hashes,
        iterationsPerSetting=5, previousCaptureWork=str(BASE), previousCapturesPreserved=True,
        newCaptureReason='User selected a new detailed map and both mixed-matchup buffer conditions',
        sameTypeSettings='One set of five trials; buffer comparison is not applicable'))
    campaigns = []
    for subject in subjects:
        campaign = work / subject['slug']
        ranged = subject['class'] != 'melee'
        rows = []
        for index, opponent in enumerate(opponents, 1):
            other_ranged = opponent['class'] != 'melee'
            for setting in trial_settings(ranged, other_ranged):
                for iteration in range(1, 6):
                    rows.append(dict(id=f"dstd_{subject['slug']}_{index:02}_{setting}_r{iteration}",
                        side2=subject['slug'], civ2=subject['civ'], side3=opponent['slug'], civ3=opponent['civ'],
                        iteration=iteration, opponentIndex=index, bufferSetting=setting,
                        bufferComparisonApplicable=ranged != other_ranged,
                        balance=dict(mode='geometric_shared_discount', cap=27, weights=dict(food=1, wood=.9, gold=1.1)),
                        scenario=scenario_settings(ranged, other_ranged, setting, scenery)))
        save(campaign / 'requested.json', dict(schemaVersion=1, matchups=rows))
        evidence, validated = [], set()
        paired = {}
        for row, request in zip(rows, _load_batch(campaign / 'requested.json')[1]):
            plan = plan_matchup(config, request)
            validate_plan_costs(plan)
            signature = [plan[k] for k in ('side2', 'side3', 'balance')]
            old = paired.setdefault(row['opponentIndex'], signature)
            if signature != old:
                raise ValueError('Changing buffer conditions must not change army costs/counts')
            if row['bufferSetting'] == 'no_buffer':
                assert not plan['scenario']['hasPlayer4Gate']
                assert plan['scenario'].get('player4Count', 0) == 0
            else:
                assert plan['scenario']['hasPlayer4Gate'] and 5 <= plan['scenario']['player4Count'] <= 10
            save(campaign / 'plans' / f"{plan['jobId']}.json", plan)
            # Cover both no-buffer owner orientations as well as each family.
            case = (plan['scenario']['family'], row['bufferSetting'], plan['side3']['ranged'])
            if case not in validated:
                target = campaign / 'preflight-scenarios' / (f"{row['opponentIndex']:02}_{row['bufferSetting']}.aoe2scenario")
                target.parent.mkdir(parents=True, exist_ok=True)
                sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2', 'side3')]
                with contextlib.redirect_stdout(io.StringIO()):
                    stack['build_run'](*sides, target, counts=tuple(plan[k]['count'] for k in ('side2', 'side3')),
                        template=capture_template_path(config, plan),
                        player4_count=plan['scenario'].get('player4Count'),
                        subject_owner=plan['scenario']['subjectOwner'],
                        remove_player4_buffer=plan['scenario'].get('player4Buffer') == 'none')
                    check = _validate_scenario(config, plan, target, stack)
                save(target.with_suffix('.validation.json'), check)
                validated.add(case)
            evidence.append(dict(jobId=row['id'], opponentIndex=row['opponentIndex'],
                opponent=plan['side3']['label'], iteration=row['iteration'], bufferSetting=row['bufferSetting'],
                counts=[plan[k]['count'] for k in ('side2', 'side3')],
                hussars=plan['scenario'].get('player4Count', 0), family=plan['scenario']['family']))
        for name in CATALOGS:
            target = campaign / 'frozen-catalogs' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'data' / name, target)
        result = analyzer.calculate_unique_unit_stats(subject['civ'], dict(base_id=subject['master'],
            display_name=subject['label'], unit_class=analyzer.get_unit(subject['master'])['class']), 4)
        save(campaign / 'subject-stats.json', [dict(civ_name=subject['civ'], final_hp=result['stats'].hp,
            stats=dataclasses.asdict(result['stats']), appliedBonuses=result.get('applied_bonuses', []))])
        # First actual recording is the retained pilot, not an extra trial.
        save(campaign / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        save(campaign / 'preflight.json', dict(state='PASSED', total=len(rows), jobs=evidence))
        save(campaign / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        campaigns.append(dict(key=subject['slug'], slug=subject['slug'], civilization=subject['civ'],
            unit=subject['label'], total=len(rows), workDirectory=str(campaign)))
    assert catalog_hashes == {name: sha256(ROOT / 'data' / name) for name in CATALOGS}
    queue = dict(schemaVersion=1, total=sum(c['total'] for c in campaigns), campaigns=campaigns,
        captureOnly=True, opponents=14, iterationsPerSetting=5, scenery=scenery)
    save(work / 'queue.json', queue)
    print(json.dumps(dict(work=str(work), total=queue['total'], campaigns=campaigns), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('norse', 'guards', 'mounted'), required=True)
    parser.add_argument('--guard-civs', nargs='*', choices=GUARD_CIVS, default=[])
    parser.add_argument('--work', type=Path)
    args = parser.parse_args()
    prepare((args.work or ROOT / f'data/local/detailed-standard-{args.group}').resolve(), args.group, args.guard_civs)
