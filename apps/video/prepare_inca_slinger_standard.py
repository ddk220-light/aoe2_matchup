"""Freeze only the missing Inca Slinger cells after the Arena/Donut batch.

Six subjects, five Arena trials each. The four melee subjects get five Donut
trials only if the Slinger loses at least three Arena games. Ranged/ranged never
uses Donut. Existing recordings and their catalogs are neither rewritten nor
recaptured. No game input occurs during preparation.
"""
import contextlib
import dataclasses
import io
import shutil
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.live import _load_stack, _validate_scenario, capture_template_path
from aoe2x.lab.planner import plan_matchup
from prepare_jomsviking_capture import DAT, audited_price
from prepare_norse_standard_capture import CATALOGS, available
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR = ROOT / 'data/local/arena-donut-standard'
WORK = ROOT / 'data/local/inca-slinger-standard'
ORDER = ('elite_jomsviking_danes', 'elite_hearth_troop_saxons', 'elite_jarl_varangians',
         'elite_varangian_guard_varangians', 'elite_varangian_guard_vikings',
         'heavy_mounted_crossbowman_danes')
SLINGER = 'imp_slinger_incas'


def register_slinger_balance(catalogs):
    """Add the audited identity only; never regenerate other catalog entries."""
    identity = 'Incas|' + SLINGER
    entry = dict(master=185, population=1.0, sharedAcrossCivilizations=True,
        classificationEvidence='Installed tech trees: Slinger 185 available to Incas and Mapuche',
        populationEvidence='Installed DAT: negative resource 4 and resource 11 both 1; one comparison population per physical unit')
    balance = catalogs['recording-balance.json']
    current = balance['units'].get(identity)
    if current:
        if any(current[k] != entry[k] for k in ('master', 'population', 'sharedAcrossCivilizations')):
            raise ValueError('Conflicting Slinger balance identity; inspect instead of overwriting')
        return
    for civ in ('Incas', 'Mapuche'):
        available(civ, 185)
    path = ROOT / 'data/recording-balance.json'
    backup = WORK / 'catalog-registration/prior-recording-balance.json'
    if backup.exists() and sha256(backup) != sha256(path):
        raise ValueError('Prior balance catalog backup conflict')
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copyfile(path, backup)
    before = sha256(path)
    balance['units'][identity] = entry
    save(path, balance)
    save(WORK / 'catalog-registration/receipt.json', dict(identity=identity,
        beforeSha256=before, afterSha256=sha256(path), entry=entry,
        scope='Only missing Slinger identity; existing prices/count rules/identities unchanged'))


def predecessor_complete():
    """Membership, captures and copy receipts must all agree before handoff."""
    paths = [PREDECESSOR / p for p in ('queue.json', 'status.json', 'delivery/status.json')]
    if not all(p.exists() for p in paths):
        return False
    queue, state, copies = map(read, paths)
    if (state.get('state') != 'COMPLETE' or copies.get('state') != 'COMPLETE'
            or state.get('verified') != queue['total'] or copies.get('verified') != queue['total']
            or state.get('failures')):
        return False
    if {c['slug'] for c in queue['campaigns']} != set(ORDER):
        raise ValueError('Predecessor membership differs from the approved six subjects')
    for campaign in queue['campaigns']:
        directory = Path(campaign['workDirectory'])
        capture = read(directory / 'capture/status.json')
        expected = {r['id'] for r in read(directory / 'manifest.json')['matchups']}
        verified = {r['jobId'] for r in capture.get('results', []) if r['status'] == 'verified'}
        receipt = copies.get('packages', {}).get(campaign['slug'], {})
        if (capture.get('state') != 'COMPLETE' or capture.get('completed') != campaign['total']
                or capture.get('pendingExports') or capture.get('failed') or verified != expected
                or len(expected) != campaign['total'] or campaign.get('conditionalDonut', {}).get('pending')
                or receipt.get('state') != 'COMPLETE' or receipt.get('verified') != campaign['total']):
            return False
    return True


def main():
    if (WORK / 'queue.json').exists():
        raise FileExistsError('Slinger plans already frozen: resume, never reprepare')
    if not predecessor_complete():
        raise RuntimeError('Wait for all preceding recordings, exports and verified copies')
    if shutil.disk_usage(ROOT).free < 8 * 2**30:
        raise RuntimeError('Local reserve below 8 GiB; preserve sources')
    previous = read(PREDECESSOR / 'queue.json')
    by_campaign = {c['slug']: c for c in previous['campaigns']}
    receipts = read(PREDECESSOR / 'delivery/status.json')['packages']
    catalogs = {name: read(ROOT / 'data' / name) for name in CATALOGS}
    units = {u['slug']: u for name in CATALOGS[:2] for u in catalogs[name]['units']}
    slinger = units[SLINGER]
    if slinger['master'] != 185 or slinger['civ'] != 'Incas' or slinger['class'] == 'melee':
        raise ValueError('Unexpected Inca Slinger identity')
    import aoe2x.dbgen.unit_analyzer as module
    module.OUTPUT_DIR = ROOT / 'data/local/dat-release-audit/installed'
    if sha256(DAT) != read(ROOT / 'data/local/dat-release-audit/audit.json')['sources']['installed_dat']['sha256']:
        raise ValueError('Installed DAT changed; inspect actual changes before planning')
    analyzer = module.UnitAnalyzer()
    cost_evidence = []
    for slug in (SLINGER, *ORDER):
        unit = units[slug]
        price = audited_price(analyzer, unit)
        existing = catalogs['recording-costs.json']['units'][unit['civ'] + '|' + slug]
        if price['effectiveCost'] != existing['effectiveCost']:
            raise ValueError(f'Actual cost changed for {slug}; do not use stale counts')
        cost_evidence.append(price)
    save(WORK / 'installed-cost-audit.json', dict(state='PASSED', sourceDatSha256=sha256(DAT), units=cost_evidence))
    # The registered recording subject had a purchase price but no geometric
    # identity. Establish that one missing entry before calling the planner.
    register_slinger_balance(catalogs)
    # Preserve the exact approved scenery/AI, without regenerating or installing it.
    donut = previous['donut']
    for key, hash_key in (('path', 'sha256'), ('auditPath', 'auditSha256')):
        if sha256(ROOT / donut[key]) != donut[hash_key]:
            raise ValueError('Approved Donut template or audit changed')
    frozen_donut = WORK / 'donut-template'
    frozen_donut.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / donut['path']).parent.iterdir():
        if source.is_file():
            target = frozen_donut / source.name
            if target.exists() and sha256(target) != sha256(source):
                raise FileExistsError('Conflicting local frozen template')
            if not target.exists():
                shutil.copyfile(source, target)
    # The complete no-P4 ranged/ranged Arena template handles both mixed and
    # ranged/ranged battles. It is the same approved detailed-winter battlefield.
    old_mounted = Path(by_campaign[ORDER[-1]]['workDirectory'])
    arena_row = next(r for r in read(old_mounted / 'manifest.json')['matchups'] if r['layout'] == 'Arena')
    arena_scenery = read(old_mounted / 'plans' / (arena_row['id'] + '.json'))['scenario']['scenery']
    config = load_config()
    stack = _load_stack(config)
    campaigns, eligibility, counts, existing_rows = [], [], [], 0
    for slug in ORDER:
        prior = by_campaign[slug]
        index_path = Path(prior['destination']) / 'run.json'
        index_hash = sha256(index_path)
        if index_hash != receipts[slug]['indexSha256']:
            raise RuntimeError('Completed destination index changed; preserve and review')
        index = read(index_path)
        if index.get('state') != 'COMPLETE':
            raise RuntimeError('Destination baseline is incomplete')
        existing_rows += len(index['matchups'])
        if any(r.get('opponentSlug') == SLINGER or
               r['plan']['side3']['slug'] == SLINGER for r in index['matchups']):
            raise ValueError('Slinger cells already exist; review and reuse before capturing')
        subject = units[slug]
        mixed = subject['class'] == 'melee'
        opponent_index = max(r['opponentIndex'] for r in index['matchups']) + 1
        directory = WORK / slug
        rows, deferred, evidence = [], [], []
        for layout in (('Arena', 'Donut') if mixed else ('Arena',)):
            owner = 3 if layout == 'Donut' else 2
            side2, side3 = (slinger, subject) if owner == 3 else (subject, slinger)
            scenario = dict(goldenFamily='ranged_vs_ranged', player4Buffer='none', subjectOwner=owner,
                **({'donut': donut} if layout == 'Donut' else {'scenery': arena_scenery}))
            condition = [dict(id=f'slingstd_{slug}_{opponent_index:02}_{layout.lower()}_r{i}',
                side2=side2['slug'], civ2=side2['civ'], side3=side3['slug'], civ3=side3['civ'],
                subjectSlug=slug, subjectOwner=owner, opponentSlug=SLINGER,
                opponentIndex=opponent_index, iteration=i, layout=layout,
                rangedOwner=2 if layout == 'Donut' else 3,
                selectionReason='Missing Slinger Arena cell' if layout == 'Arena' else 'Frozen pending Arena loss decision',
                bufferSetting='no_buffer', bufferComparisonApplicable=False,
                balance=dict(mode='geometric_shared_discount', cap=27,
                    weights=dict(food=1, wood=.9, gold=1.1)), scenario=scenario) for i in range(1, 6)]
            save(directory / 'condition.json', dict(schemaVersion=1, matchups=condition[:1]))
            plan = plan_matchup(config, _load_batch(directory / 'condition.json')[1][0])
            validate_plan_costs(plan)
            if plan['scenario']['hasPlayer4Gate']:
                raise ValueError('Slinger captures must have no buffer')
            for item in condition:
                save(directory / 'plans' / (item['id'] + '.json'), {**plan, 'jobId': item['id']})
            path = directory / 'preflight-scenarios' / (layout + '.aoe2scenario')
            path.parent.mkdir(parents=True, exist_ok=True)
            sides = [stack['resolve_side'](plan[k]['civ'], plan[k]['slug']) for k in ('side2', 'side3')]
            with contextlib.redirect_stdout(io.StringIO()):
                stack['build_run'](*sides, path, counts=tuple(plan[k]['count'] for k in ('side2', 'side3')),
                    template=capture_template_path(config, plan), remove_player4_buffer=True,
                    subject_owner=plan['scenario']['subjectOwner'])
                validation = _validate_scenario(config, plan, path, stack)
            save(path.with_suffix('.validation.json'), validation)
            evidence.append(dict(layout=layout, validation=validation))
            counts.append(dict(subject=slug, layout=layout,
                subjectCount=plan[f'side{owner}']['count'], slingerCount=plan[f'side{5-owner}']['count']))
            (deferred if layout == 'Donut' else rows).extend(condition)
        if mixed and any(counts[-1][k] != counts[-2][k] for k in ('subjectCount', 'slingerCount')):
            raise ValueError('Changing maps must not change either army count')
        for name in CATALOGS:
            save(directory / 'frozen-catalogs' / name, catalogs[name])
        stats = analyzer.calculate_unique_unit_stats(subject['civ'], dict(base_id=subject['master'],
            display_name=subject['label'], unit_class=analyzer.get_unit(subject['master'])['class']), 4)['stats']
        slinger_stats = analyzer.calculate_unique_unit_stats('Incas', dict(base_id=185,
            display_name='Slinger', unit_class=analyzer.get_unit(185)['class']), 4)['stats']
        save(directory / 'subject-stats.json', [dict(civ_name=subject['civ'], final_hp=stats.hp,
            stats=dataclasses.asdict(stats))])
        save(directory / 'pilot-opponent-expectations.json', {rows[0]['id']:
            dict(civ='Incas', hpPerUnit=slinger_stats.hp)})
        save(directory / 'manifest.json', dict(schemaVersion=1, matchups=rows))
        save(directory / 'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
        save(directory / 'preflight.json', dict(state='PASSED', total=5, cases=evidence))
        campaign = dict(key=slug, slug=slug, civilization=subject['civ'], unit=subject['label'],
            total=5, workDirectory=str(directory), destination=prior['destination'],
            originalIndexSha256=index_hash, metadataDirectory='_inca_slinger_metadata',
            extensionKind='inca-slinger-arena-donut-no-buffer',
            documentationPath='docs/video-production/INCA_SLINGER_STANDARD_CAPTURE.md')
        if mixed:
            save(directory / 'conditional-donut-plans.json', dict(schemaVersion=1, matchups=deferred))
            campaign['conditionalDonut'] = dict(pending=True, minimumLosses=3, rangedOwner=3,
                manifest='conditional-donut-plans.json')
        campaigns.append(campaign)
        eligibility.append(dict(subject=slug, opponent=SLINGER, arenaTrials=5,
            donutEligibility='Slinger loses at least 3/5 Arena games' if mixed else 'Never ranged/ranged on Donut',
            pendingArenaDecision=mixed))
    save(WORK / 'eligibility.json', dict(trigger='majority', comparisons=eligibility))
    save(WORK / 'count-summary.json', dict(comparisons=counts))
    save(WORK / 'queue.json', dict(schemaVersion=1, total=30, maximumTotal=50, campaigns=campaigns,
        captureOnly=True, noBuffers=True, iterationsPerCondition=5, donut=donut,
        sourceDatSha256=sha256(DAT), existingArchiveRowsPreserved=existing_rows,
        predecessorQueueSha256=sha256(PREDECESSOR / 'queue.json')))
    print(dict(total=30, maximumTotal=50, subjects=list(ORDER), counts=counts), flush=True)


if __name__ == '__main__':
    main()
