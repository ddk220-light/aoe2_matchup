"""Freeze one blue-subject/red-opponent r06 for each requested existing Donut test.

The first five trials are retained. Membership comes from the completed Donut
and Slinger manifests, checked against the current remote index. Only iteration,
job identity and player colors change; counts and capture conditions must match.
"""
import contextlib
import copy
import io
import shutil
from pathlib import Path

from aoe2x.lab.cli import _normalize_batch_row
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import _load_stack, _validate_scenario, capture_template_path
from aoe2x.lab.planner import plan_matchup
from prepare_norse_standard_capture import CATALOGS
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/donut-color-sixth-iteration'
SUBJECTS = {
    'elite_jarl_varangians': 10,
    'elite_varangian_guard_varangians': 3,
    'elite_varangian_guard_vikings': 2,
    'heavy_mounted_crossbowman_danes': 9,
}


def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Already prepared; resume the existing 24 jobs')
    config = load_config()
    stack = _load_stack(config)
    previous = read(ROOT / 'data/local/arena-donut-standard/queue.json')
    campaigns, eligibility = [], []
    for slug, expected in SUBJECTS.items():
        prior = next(c for c in previous['campaigns'] if c['slug'] == slug)
        old_work = Path(prior['workDirectory'])
        directory = WORK / slug
        index_path = Path(prior['destination']) / 'run.json'
        original = read(index_path)
        original_hash = sha256(index_path)
        if original.get('state') != 'COMPLETE':
            raise RuntimeError('Prior archive is incomplete')
        selected = []
        for parent in ('arena-donut-standard', 'inca-slinger-standard'):
            path = ROOT / 'data/local' / parent / slug / 'manifest.json'
            if path.exists():
                selected.extend(r for r in read(path)['matchups']
                                if r['layout'] == 'Donut' and r['iteration'] == 1)
        selected.sort(key=lambda r: r['opponentIndex'])
        if len(selected) != expected or len({r['opponentSlug'] for r in selected}) != expected:
            raise ValueError(f'Unexpected Donut membership for {slug}')
        rows, validations = [], []
        for old in selected:
            previous_trials = [r for r in original['matchups'] if r.get('layout') == 'Donut'
                               and r.get('opponentSlug') == old['opponentSlug']]
            if sorted(r['iteration'] for r in previous_trials) != [1, 2, 3, 4, 5]:
                raise ValueError('Expected exactly five existing Donut trials; do not duplicate r06')
            archive_row = next(r for r in previous_trials if r['jobId'] == old['id'])
            row = copy.deepcopy(old)
            row['id'] = f"dcc6_{slug}_{old['opponentSlug']}_r6"
            row['iteration'] = 6
            row['colorCorrected'] = True
            row['scenario']['subjectOwner'] = row['subjectOwner']
            row['selectionReason'] = 'User requested one color-corrected sixth Donut iteration; preserve r01-r05'
            plan = plan_matchup(config, _normalize_batch_row(row, {}))
            validate_plan_costs(plan)
            old_plan = archive_row['plan']
            for side in ('side2', 'side3'):
                for field in ('slug', 'civ', 'count', 'effectiveCost', 'weightedCost'):
                    if plan[side][field] != old_plan[side][field]:
                        raise ValueError(f'Unrequested change: {slug}/{old["opponentSlug"]}/{field}')
            if plan['scenario']['donut'] != old_plan['scenario']['donut']:
                raise ValueError('Donut template changed')
            save(directory / 'plans' / (row['id'] + '.json'), plan)
            target = directory / 'preflight-scenarios' / (row['id'] + '.aoe2scenario')
            sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2', 'side3')]
            with contextlib.redirect_stdout(io.StringIO()):
                stack['build_run'](*sides, target,
                    counts=tuple(plan[k]['count'] for k in ('side2', 'side3')),
                    template=capture_template_path(config, plan), remove_player4_buffer=True,
                    subject_owner=row['subjectOwner'])
                validation = _validate_scenario(config, plan, target, stack)
            save(target.with_suffix('.validation.json'), validation)
            validations.append(dict(jobId=row['id'], subjectOwner=row['subjectOwner'],
                playerColors=plan['scenario']['playerColors'], previousJobId=old['id'],
                countsUnchanged=True, templateUnchanged=True))
            rows.append(row)
        save(directory / 'previous-run.json', original)
        save(directory / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        save(directory / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        save(directory / 'subject-stats.json', read(old_work / 'subject-stats.json'))
        save(directory / 'preflight.json', dict(state='PASSED', total=len(rows), cases=validations))
        for name in CATALOGS:
            path = directory / 'frozen-catalogs' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'data' / name, path)
        campaigns.append(dict(key=slug, slug=slug, civilization=prior['civilization'],
            unit=prior['unit'], total=len(rows), workDirectory=str(directory),
            destination=prior['destination'], originalIndexSha256=original_hash,
            metadataDirectory='_donut_color_r06_metadata',
            extensionKind='donut-color-corrected-sixth-iteration'))
        eligibility.append(dict(subject=slug, opponents=[r['opponentSlug'] for r in rows],
            basis='Existing completed Donut tests; one additional color-corrected iteration'))
    save(WORK / 'eligibility.json', dict(state='APPROVED', subjects=eligibility))
    save(WORK / 'queue.json', dict(schemaVersion=1, total=24, campaigns=campaigns,
        captureOnly=True, colorPolicy='subject_blue_opponent_red_v1'))
    print({'prepared': 24, 'subjects': SUBJECTS, 'iteration': 6})


if __name__ == '__main__':
    main()
