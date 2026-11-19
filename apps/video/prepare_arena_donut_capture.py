"""Append only missing Arena battles and approved Donut experiments.

Five real trials per condition. Existing no-buffer Arena recordings determine
eligibility and are reused; the share's current indexes include Cavalier fixes.
Preparation is one-shot. Resume the resulting finite queue, never reprepare it.
"""
import argparse
import contextlib
import dataclasses
import io
import re
import shutil
from collections import Counter
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import (_load_stack, _validate_scenario, capture_template_path,
                           _camera_configuration, _player_runtime_configuration, _trigger_structure)
from aoe2x.lab.planner import plan_matchup
from prepare_jomsviking_capture import DAT, audited_price
from prepare_norse_standard_capture import CATALOGS, available, load_scenario
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/arena-donut-standard'
SHARE = Path(r'\\100.123.128.35\AoE2-Incoming')
RUN_NAME = 'Standard_Units_Detailed_Winter_5_Repeats'
PREVIEW = ROOT / 'data/local/legacy-kiting-preview'
APPROVED = PREVIEW / 'Winter Rock - Jomsviking vs Arbalester.aoe2scenario'
APPROVED_HASH = '47db0f80ab716e299f12a21c38a2fadbfedbd90355a701210fafa7027b388ada'
NEW = [('halberdier', 359, 'Halberdier'), ('elite_fire_lancer', 1903, 'Elite Fire Lancer')]
RANGED_TARGETS = {492, 474, 875}
SUBJECTS = {'elite_jomsviking_danes', 'elite_hearth_troop_saxons', 'elite_jarl_varangians',
            'elite_varangian_guard_varangians', 'elite_varangian_guard_vikings',
            'heavy_mounted_crossbowman_danes'}


def quiet_ai():
    """Keep absolute rule jumps intact; add discovery for the new Jarl ID.

    Jarl has the Cavalry class, so the old ranged-class searches cannot find it.
    Extra search actions do not add rules. Timing overrides are appended after
    the numbered core, using installed DAT projectile-release delays + 60 ms.
    """
    original = (PREVIEW / 'ddkRockQuietAI.per').read_text(encoding='utf-8')
    assert not re.search(r'^\s*\((?:chat|up-chat|taunt)', original, re.M)
    marker = '\t(up-find-local c: elite-mameluke c: 240)'
    assert original.count(marker) == 3, 'Unexpected discovery pipeline; review before editing'
    ai = original.replace(marker, marker + '\n\t(up-find-local c: 2709 c: 240)')
    assert ai.count('(defrule') == original.count('(defrule')
    units = {u['id']: u for u in read(ROOT / 'data/local/dat-release-audit/installed/units.json')}
    for master in (2709, 2701):
        delay = round(units[master]['attack_delay'] * 1000) + 60
        ai += (f'\n; Installed DAT release delay for {units[master]["name"]}: {delay} ms.\n'
               f'(defrule\n\t(up-compare-goal gWset c:== 1)\n'
               f'\t(up-compare-goal gUType c:== {master})\n\t=>\n'
               f'\t(up-modify-goal gWfire c:= {delay})\n)\n')
    # The historical table divides animation frames by 60, which cancels
    # Slinger windups. New templates use its installed graphic timing and a
    # protected volley window; never mutate a previously frozen template.
    from donut_ai_timing import protect_slinger_volley, slinger_timing
    return protect_slinger_volley(ai, slinger_timing(DAT))


def donut_template():
    """Freeze approved art, quiet AI and the first 27 legacy formation slots."""
    from build_run import _ai_configuration
    if sha256(APPROVED) != APPROVED_HASH:
        raise ValueError('Reviewed Donut scenery changed; do not silently substitute it')
    source = load_scenario(APPROVED)
    legacy_path = PREVIEW / 'golden_rangedvsinf.aoe2scenario'
    legacy = load_scenario(legacy_path)
    before = (_camera_configuration(source), _player_runtime_configuration(source), _trigger_structure(source))
    # Preview had 25 Jomsvikings. Restore only its two missing authored slots;
    # generation then takes first-N in precisely the same player record order.
    for p in (2, 3):
        old = list(legacy.unit_manager.units[p])[:27]
        current = list(source.unit_manager.units[p])
        assert [(u.x, u.y) for u in current] == [(u.x, u.y) for u in old[:len(current)]]
        for u in old[len(current):]:
            source.unit_manager.add_unit(player=p, unit_const=current[0].unit_const,
                x=u.x, y=u.y, z=u.z, rotation=u.rotation, reference_id=u.reference_id)
        assert len(source.unit_manager.units[p]) == 27
    assert not source.unit_manager.units[4]
    ai = quiet_ai()
    name = 'ddkDonutQuietAI'
    pd = source.sections['PlayerDataTwo']
    pd.ai_names[1] = name + '.ai'
    pd.retriever_map['ai_files'].data[1].retriever_map['ai_per_file_text'].data = ai
    for entry in source.sections['Files'].retriever_map['ai_files'].data:
        if entry.retriever_map['ai_file_name'].data == 'ddkRockQuietAI.per':
            entry.retriever_map['ai_file_name'].data = name + '.per'
            entry.retriever_map['ai_file'].data = ai
    folder = WORK / 'donut-template'
    folder.mkdir(parents=True)
    path = folder / 'Winter Donut.aoe2scenario'
    (folder / (name + '.per')).write_text(ai, encoding='utf-8')
    (folder / (name + '.ai')).write_bytes(b'')
    with contextlib.redirect_stdout(io.StringIO()):
        source.write_to_file(str(path))
    checked = load_scenario(path)
    assert before == (_camera_configuration(checked), _player_runtime_configuration(checked), _trigger_structure(checked))
    assert _ai_configuration(checked) == _ai_configuration(source)
    assert all(t.elevation == 0 for t in checked.map_manager.terrain)
    refs = [u.reference_id for p in range(9) for u in checked.unit_manager.units[p]]
    assert len(refs) == len(set(refs))
    audit = path.with_suffix('.audit.json')
    save(audit, dict(state='PASSED', layout='Donut', approvedScenerySha256=APPROVED_HASH,
        legacyFormationSha256=sha256(legacy_path), templateSha256=sha256(path),
        slotsPerSide=27, bufferUnits=0, terrainFlat=True, quietAi=True,
        aiName=name, aiSha256=sha256(folder / (name + '.per')),
        rangedOwner=2, meleeOwner=3, coreRuleNumbersPreserved=True,
        discoveryExtension='Elite Jarl 2709; installed release delays for Jarl and Mounted Crossbow',
        sceneryUnchanged=True, cameraAndDiplomacyUnchanged=True))
    return dict(path=path.relative_to(ROOT).as_posix(), sha256=sha256(path),
                auditPath=audit.relative_to(ROOT).as_posix(), auditSha256=sha256(audit))


def main(trigger):
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Already frozen: resume the queue instead of preparing again')
    if shutil.disk_usage(ROOT).free < 8 * 2**30 or shutil.disk_usage(SHARE).free < 4 * 2**30:
        raise RuntimeError('Local/share reserve unavailable; preserve existing work')
    prior_queue = read(ROOT / 'data/local/detailed-standard-capture/queue.json')
    prior_queue['campaigns'] = [c for c in prior_queue['campaigns'] if c['slug'] in SUBJECTS]
    assert len(prior_queue['campaigns']) == len(SUBJECTS)
    indexes = {}
    for c in prior_queue['campaigns']:
        path = SHARE / c['slug'] / RUN_NAME / 'run.json'
        index = read(path)
        if index.get('state') != 'COMPLETE':
            raise RuntimeError(f'Prior archive is not complete: {path}')
        indexes[c['slug']] = (path, index, sha256(path))
    import aoe2x.dbgen.unit_analyzer as module
    from build_run import unit_const
    module.OUTPUT_DIR = ROOT / 'data/local/dat-release-audit/installed'
    analyzer = module.UnitAnalyzer()
    if sha256(DAT) != read(ROOT / 'data/local/dat-release-audit/audit.json')['sources']['installed_dat']['sha256']:
        raise ValueError('Installed DAT changed since the cost extraction')
    catalogs = {n: read(ROOT / 'data' / n) for n in CATALOGS}
    for n, v in catalogs.items():
        if not (WORK / 'prior-catalogs' / n).exists():
            save(WORK / 'prior-catalogs' / n, v)
    new_opponents = []
    for key, master, label in NEW:
        assert unit_const(key) == master
        available('Chinese', master)
        row = dict(civ='Chinese', slug=key + '_chinese', master=master,
                   label=label, scenarioKey=key, **{'class': 'melee'})
        base = analyzer.get_base_stats(analyzer.get_unit(master))
        row.update(baseCost={r: getattr(base, 'cost_' + r) for r in ('food', 'wood', 'gold')},
                   costSource='Installed DAT: Arena/Donut standard opponents, 2026-10-03')
        existing = next((u for u in catalogs['recording-subjects.json']['units'] if u['slug'] == row['slug']), None)
        if existing and any(existing[k] != row[k] for k in ('civ', 'master', 'class', 'baseCost')):
            raise ValueError('Conflicting registered Chinese opponent')
        if not existing:
            catalogs['recording-subjects.json']['units'].append(row)
        identity = 'Chinese|' + row['slug']
        catalogs['recording-costs.json']['units'][identity] = audited_price(analyzer, row)
        catalogs['recording-balance.json']['units'][identity] = dict(master=master, population=1,
            sharedAcrossCivilizations=True, populationEvidence='One comparison population per physical unit',
            classificationEvidence='Standard unit, available across civilizations')
        new_opponents.append(row)
    for n in CATALOGS[1:]:
        save(ROOT / 'data' / n, catalogs[n])
    entries = catalogs['unique-unit-roster.json']['units'] + catalogs['recording-subjects.json']['units']
    by_slug = {u['slug']: u for u in entries}
    config = load_config()
    stack = _load_stack(config)
    donut = donut_template()
    campaigns, reuse, eligibility = [], [], []
    for c in prior_queue['campaigns']:
        subject = by_slug[c['slug']]
        destination_index, prior, prior_hash = indexes[c['slug']]
        groups = {}
        for r in prior['matchups']:
            if r.get('bufferSetting') == 'no_buffer':
                groups.setdefault(r['opponentIndex'], []).append(r)
        if len(groups) != 14 or any(len(v) != 5 for v in groups.values()):
            raise ValueError('Need all five corrected no-buffer Arena trials for each opponent')
        campaign = WORK / c['slug']
        rows, conditions, validated, deferred = [], [], set(), []
        conditional_mounted = subject['slug'] == 'heavy_mounted_crossbowman_danes'
        for oi, recordings in sorted(groups.items()):
            old_plan = recordings[0]['plan']
            opponent = by_slug[old_plan['side3']['slug']]
            if subject['class'] != 'melee':
                losses = sum(r['capture']['capture']['winnerOwner'] == 3 for r in recordings)
                selected = opponent['class'] == 'melee' and (not conditional_mounted or losses >= 3)
                reason = (f'Ranged subject lost {losses}/5 Arena trials; trigger=majority'
                          if conditional_mounted else 'All melee opponents explicitly requested for Jarl')
                if conditional_mounted:
                    eligibility.append(dict(subject=c['slug'], opponent=opponent['slug'],
                        rangedLosses=losses, trials=5, runDonut=selected, reason=reason))
            else:
                losses = sum(r['capture']['capture']['winnerOwner'] == 2 for r in recordings)
                selected = opponent['master'] in RANGED_TARGETS and (losses >= 3 if trigger == 'majority' else losses >= 1)
                reason = f'Ranged army lost {losses}/5 Arena trials; trigger={trigger}'
                if opponent['master'] in RANGED_TARGETS:
                    eligibility.append(dict(subject=c['slug'], opponent=opponent['slug'],
                        rangedLosses=losses, trials=5, runDonut=selected, reason=reason))
            if selected:
                conditions.append((oi, opponent, 'Donut', reason))
            reuse.extend(dict(subject=c['slug'], jobId=r['jobId'], files=r['files'],
                              opponentIndex=oi, indexSha256=prior_hash) for r in recordings)
        for oi, opponent in enumerate(new_opponents, 15):
            conditions.append((oi, opponent, 'Arena', 'Missing Chinese standard opponent'))
            if subject['class'] != 'melee':
                conditions.append((oi, opponent, 'Donut', 'All melee opponents for the ranged subject'))
        arena_scenery = read(Path(c['workDirectory']).parent / 'queue.json')['scenery']
        for oi, opponent, layout, reason in conditions:
            owner = 3 if layout == 'Donut' and subject['class'] == 'melee' else 2
            side2, side3 = (opponent, subject) if owner == 3 else (subject, opponent)
            family = 'ranged_vs_ranged' if layout == 'Donut' or side2['class'] != 'melee' or side3['class'] != 'melee' else 'melee_vs_melee'
            scenario = dict(goldenFamily=family, player4Buffer='none', subjectOwner=owner,
                            **({'donut': donut} if layout == 'Donut' else {'scenery': arena_scenery[family]}))
            condition_rows = [dict(id=f"adstd_{subject['slug']}_{oi:02}_{layout.lower()}_r{i}",
                side2=side2['slug'], civ2=side2['civ'], side3=side3['slug'], civ3=side3['civ'],
                subjectSlug=subject['slug'], subjectOwner=owner, opponentSlug=opponent['slug'],
                opponentIndex=oi, iteration=i, layout=layout, selectionReason=reason,
                bufferSetting='no_buffer', bufferComparisonApplicable=False,
                balance=dict(mode='geometric_shared_discount', cap=27,
                             weights=dict(food=1, wood=.9, gold=1.1)), scenario=scenario) for i in range(1, 6)]
            save(campaign / 'condition.json', dict(schemaVersion=1, matchups=condition_rows[:1]))
            plan = plan_matchup(config, _load_batch(campaign / 'condition.json')[1][0])
            validate_plan_costs(plan)
            assert plan['scenario']['hasPlayer4Gate'] is False
            # Reused Arena conditions must have the same actual fielded counts.
            if oi <= 14:
                old = groups[oi][0]['plan']
                expected = {old[k]['slug']: old[k]['count'] for k in ('side2', 'side3')}
                assert all(plan[k]['count'] == expected[plan[k]['slug']] for k in ('side2', 'side3'))
            case = (layout, family)
            if case not in validated:
                path = campaign / 'preflight-scenarios' / f'{layout}-{family}.aoe2scenario'
                path.parent.mkdir(parents=True, exist_ok=True)
                sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2', 'side3')]
                with contextlib.redirect_stdout(io.StringIO()):
                    stack['build_run'](*sides, path, counts=tuple(plan[k]['count'] for k in ('side2', 'side3')),
                        template=capture_template_path(config, plan), remove_player4_buffer=True,
                        subject_owner=plan['scenario']['subjectOwner'])
                    check = _validate_scenario(config, plan, path, stack)
                save(path.with_suffix('.validation.json'), check)
                validated.add(case)
            for r in condition_rows:
                save(campaign / 'plans' / (r['id'] + '.json'), {**plan, 'jobId': r['id']})
            if conditional_mounted and oi >= 15 and layout == 'Donut':
                deferred.extend(condition_rows)
            else:
                rows.extend(condition_rows)
        for name in CATALOGS:
            target = campaign / 'frozen-catalogs' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'data' / name, target)
        pilot = rows[0]
        pilot_unit = by_slug[pilot['side2']]
        stats = analyzer.calculate_unique_unit_stats(pilot['civ2'],
            dict(base_id=pilot_unit['master'], display_name=pilot_unit['label'],
                 unit_class=analyzer.get_unit(pilot_unit['master'])['class']), 4)
        save(campaign / 'subject-stats.json', [dict(civ_name=pilot['civ2'], final_hp=stats['stats'].hp,
            stats=dataclasses.asdict(stats['stats']))])
        save(campaign / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        save(campaign / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        save(campaign / 'preflight.json', dict(state='PASSED', total=len(rows), cases=list(map(list, validated))))
        prepared = dict(**{k: c[k] for k in ('key', 'slug', 'civilization', 'unit')},
            total=len(rows), workDirectory=str(campaign), destination=str(destination_index.parent),
            originalIndexSha256=prior_hash)
        if deferred:
            save(campaign / 'conditional-donut-plans.json', dict(schemaVersion=1, matchups=deferred))
            prepared['conditionalDonut'] = dict(pending=True, minimumLosses=3,
                manifest='conditional-donut-plans.json')
        campaigns.append(prepared)
    save(WORK / 'reuse.json', dict(reusedArenaTrials=len(reuse), matchups=reuse))
    save(WORK / 'eligibility.json', dict(trigger=trigger, comparisons=eligibility))
    save(WORK / 'queue.json', dict(schemaVersion=1, total=sum(c['total'] for c in campaigns),
        campaigns=campaigns, captureOnly=True, iterationsPerCondition=5, noBuffers=True,
        donut=donut, sourceDatSha256=sha256(DAT), existingArenaTrialsReused=len(reuse)))
    print({'total': sum(c['total'] for c in campaigns), 'reusedArena': len(reuse), 'campaigns': len(campaigns)})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trigger', choices=('majority', 'any-loss'), default='majority')
    main(p.parse_args().trigger)
