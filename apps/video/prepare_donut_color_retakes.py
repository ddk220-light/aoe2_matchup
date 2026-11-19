"""Freeze exactly the six user-selected Donut color retakes, one trial each."""
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
WORK = ROOT / 'data/local/donut-color-retakes-six'
SUBJECTS = ('elite_jomsviking_danes', 'elite_hearth_troop_saxons')
OPPONENTS = ('arbalester_saracens', 'heavy_cav_archer_saracens', 'elite_elephant_archer_bengalis')


def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Prepared already; resume exactly these six jobs')
    config = load_config()
    stack = _load_stack(config)
    previous = read(ROOT / 'data/local/arena-donut-standard/queue.json')
    campaigns = []
    for slug in SUBJECTS:
        prior = next(c for c in previous['campaigns'] if c['slug'] == slug)
        old_work = Path(prior['workDirectory'])
        directory = WORK / slug
        index_path = Path(prior['destination']) / 'run.json'
        original = read(index_path)
        if original.get('state') != 'COMPLETE':
            raise RuntimeError('Prior archive is incomplete')
        save(directory / 'previous-run.json', original)
        manifest = read(old_work / 'manifest.json')['matchups']
        rows, mapping = [], []
        for opponent in OPPONENTS:
            selected = [r for r in manifest if r['opponentSlug'] == opponent
                        and r['layout'] == 'Donut' and r['iteration'] == 1]
            if len(selected) != 1:
                raise ValueError('Expected one original first Donut trial')
            old = selected[0]
            archive_row = next(r for r in original['matchups'] if r['jobId'] == old['id'])
            row = copy.deepcopy(old)
            row['id'] = old['id'].replace('adstd_', 'dc6_')
            row['scenario']['subjectOwner'] = 3
            row['selectionReason'] = 'User selected one blue-subject/red-opponent Donut retake'
            plan = plan_matchup(config, _normalize_batch_row(row, {}))
            validate_plan_costs(plan)
            old_plan = archive_row['plan']
            for side in ('side2', 'side3'):
                for field in ('slug', 'civ', 'count', 'effectiveCost', 'weightedCost'):
                    if plan[side][field] != old_plan[side][field]:
                        raise ValueError(f'Unrequested change: {slug}/{opponent}/{field}')
            if plan['scenario']['donut'] != old_plan['scenario']['donut']:
                raise ValueError('Donut template changed')
            save(directory / 'plans' / (row['id'] + '.json'), plan)
            target = directory / 'preflight-scenarios' / (row['id'] + '.aoe2scenario')
            sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2', 'side3')]
            with contextlib.redirect_stdout(io.StringIO()):
                stack['build_run'](*sides, target, counts=tuple(plan[k]['count'] for k in ('side2', 'side3')),
                    template=capture_template_path(config, plan), remove_player4_buffer=True, subject_owner=3)
                validation = _validate_scenario(config, plan, target, stack)
            save(target.with_suffix('.validation.json'), validation)
            rows.append(row)
            mapping.append(dict(oldJobId=old['id'], jobId=row['id'], files=archive_row['files']))
        save(directory / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        save(directory / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        # First actual Arbalester recording is the pilot, not an extra battle.
        save(directory / 'subject-stats.json', read(old_work / 'subject-stats.json'))
        for name in CATALOGS:
            path = directory / 'frozen-catalogs' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'data' / name, path)
        save(directory / 'replacement.json', dict(destination=prior['destination'],
            previousIndexSha256=sha256(index_path), mapping=mapping,
            reason='Six authorized color retakes; replace first Donut trial only'))
        campaigns.append(dict(key=slug, slug=slug, civilization=prior['civilization'],
            unit=prior['unit'], total=3, workDirectory=str(directory), destination=prior['destination']))
    save(WORK / 'queue.json', dict(schemaVersion=1, total=6, campaigns=campaigns,
        captureOnly=True, colorPolicy='subject_blue_opponent_red_v1'))
    print({'prepared': 6, 'subjects': list(SUBJECTS), 'iterations': 1})


if __name__ == '__main__':
    main()
