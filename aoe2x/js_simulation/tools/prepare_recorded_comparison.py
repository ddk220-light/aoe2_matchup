"""Prepare headless comparison jobs from reference mechanics and archive metadata.

The reference DB and archives are read-only. Counts in captured plans remain
expected evidence; generated setup comes from reference purchase costs and the
September 22, 2026 comparison policy. Output is restricted to local calibration.
"""
import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from aoe2x.js_simulation.battle_setup import effective_cost

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / 'aoe2x/js_simulation/calibration/lab/patch185872'
POLICY = 'geometric_full_discount_weighted_resources_v3'
DEFAULT_ARCHIVES = ('hearth-troop-saxons', 'jarl-varangians', 'jomsviking-danes')
OPPONENTS = ('elite_composite_bowman_armenians', 'elite_jaguar_warrior_aztecs',
             'elite_cataphract_byzantines', 'houfnice_bohemians', 'elite_mangudai')
RESOURCES = ('food', 'wood', 'gold')


def calculate_setup(teams):
    costs = [t['effectiveCost']['food'] + .9 * t['effectiveCost']['wood']
             + 1.1 * t['effectiveCost']['gold'] for t in teams]
    smaller = max(1, math.floor(27 * math.sqrt(min(costs) / max(costs)) + .5))
    counts = [27, smaller] if costs[0] <= costs[1] else [smaller, 27]
    ranged = [t['mechanics']['behavior_class'] in ('mobile_ranged', 'siege_ranged') for t in teams]
    index = ranged.index(True) if sum(ranged) == 1 else None
    total = counts[index] * costs[index] if index is not None else None
    screen = math.floor(max(5, min(10, 5 + (total - 1000) / 1800)) + .5) if total is not None else 0
    return dict(counts=counts, weightedCosts=costs, player4Count=screen,
                rangedOwner=index + 2 if index is not None else None,
                rangedArmyWeightedCost=total)


def resolve_reference(connection, side):
    civ = side.get('mechanicsCiv', side['civ'])
    rows = connection.execute("SELECT * FROM ref_units WHERE civ_name=? AND age='Imperial' AND unit_slug=?",
                              (civ, side['slug'])).fetchall()
    if not rows and side.get('master') is not None:
        rows = connection.execute("SELECT * FROM ref_units WHERE civ_name=? AND age='Imperial' AND unit_master=?",
                                  (civ, side['master'])).fetchall()
    if not rows:
        rows = connection.execute("SELECT * FROM ref_units WHERE civ_name=? AND age='Imperial' AND unit_name=?",
                                  (civ, side['label'])).fetchall()
    if len(rows) != 1:
        raise ValueError(f"Unresolved or ambiguous reference identity: {civ}|{side['slug']}")
    row = dict(rows[0])
    profiles = connection.execute('SELECT * FROM ref_unit_mechanics WHERE ref_unit_id=? AND is_default=1',
                                  (row['id'],)).fetchall()
    if len(profiles) != 1:
        raise ValueError(f"Missing or ambiguous mechanics: {civ}|{row['unit_slug']}")
    profile = dict(profiles[0])
    mechanics = json.loads(profile['mechanics_json'])
    if mechanics['unit_master'] != row['unit_master'] or mechanics['civilization'] != civ:
        raise ValueError(f"Mechanics identity mismatch: {civ}|{side['slug']}")
    costs, cost_evidence = effective_cost(row)
    team = dict(mechanics=mechanics, effectiveCost=costs)
    provenance = dict(refUnitId=row['id'], civilization=civ, unitSlug=row['unit_slug'],
                      unitMaster=row['unit_master'], mechanicsHash=profile['mechanics_hash'],
                      sourceBuild=profile['source_build'], costEvidence=cost_evidence)
    return team, provenance


def prepare_document(reference_db, archive_paths, all_opponents=False,
                     min_winner_hp_percent=60, job_ids=None):
    reference_db = Path(reference_db).resolve()
    jobs, metadata = [], []
    with closing(sqlite3.connect(reference_db.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        auxiliary = None
        for archive_path in archive_paths:
            archive_path = Path(archive_path).resolve()
            archive = json.loads(archive_path.read_text(encoding='utf-8-sig'))
            for match in archive['matchups']:
                plan = match['plan']
                if job_ids is not None and match['jobId'] not in job_ids:
                    continue
                if job_ids is None and not all_opponents and plan['side3']['slug'] not in OPPONENTS:
                    continue
                outcome = match['capture']['capture']
                remaining_percent = 100 * outcome['winnerHp'] / outcome['winnerStartingHp']
                if remaining_percent < min_winner_hp_percent:
                    continue
                resolved = [resolve_reference(connection, plan[key]) for key in ('side2', 'side3')]
                teams = [entry[0] for entry in resolved]
                setup = calculate_setup(teams)
                job = dict(jobId=match['jobId'], teams=teams, balancePolicy=POLICY,
                           engagementMode='ranged_buffer' if setup['player4Count'] else 'direct',
                           player4Count=setup['player4Count'], preserveOwnerOrientation=True,
                           seed=0)
                if setup['player4Count']:
                    if auxiliary is None:
                        row = connection.execute("SELECT * FROM ref_auxiliary_mechanics WHERE actor_slug='scout_cavalry' AND mode='default'").fetchone()
                        if row is None:
                            raise ValueError('Missing scout_cavalry auxiliary mechanics')
                        auxiliary = dict(row)
                    job['scenario'] = dict(auxiliaryArmiesByOwner={
                        '4': dict(mechanics=json.loads(auxiliary['mechanics_json']))})
                jobs.append(job)
                expected = {key: {field: plan[key].get(field) for field in
                                  ('slug', 'civ', 'count', 'effectiveCost', 'weightedCost', 'armyWeightedResources')}
                            for key in ('side2', 'side3')}
                expected.update(player4Count=plan['scenario'].get('player4Count', 0),
                                scenario=plan['scenario'], balance=plan['balance'],
                                outcome=match['capture']['capture'])
                metadata.append(dict(jobId=match['jobId'], archive=str(archive_path),
                    recordingClock=match['recording']['clock'],
                    matchupId=plan['matchupId'], repeat=match['capture'].get('repeat'),
                    framesPath=str(archive_path.parent / match['files']['frames.bin']['path']),
                    videoPath=str(archive_path.parent / match['files']['battle.mp4']['path']),
                    calculatedSetup=setup, referenceTeams=[entry[1] for entry in resolved],
                    auxiliaryMechanicsHash=auxiliary['mechanics_hash'] if setup['player4Count'] else None,
                    expected=expected))
    return dict(schemaVersion=1, jobs=jobs, metadata=dict(referenceDb=str(reference_db),
        referenceDbSha256=hashlib.sha256(reference_db.read_bytes()).hexdigest(),
        policy=POLICY, policySource='docs/video-production/BALANCE_POLICY.md at 2cced342',
        bufferPolicy='fielded_weighted_cost_v1',
        minWinnerHpPercent=min_winner_hp_percent,
        selection=list(job_ids) if job_ids is not None else ('all' if all_opponents else list(OPPONENTS)),
        matchups=metadata))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-db', type=Path, default=ROOT / 'data/local/generated/patch-185872/aoe2_reference.db')
    parser.add_argument('--archive', type=Path, action='append', help='Path to run.json; repeat for multiple archives')
    parser.add_argument('--all', action='store_true', help='Select all archived opponents')
    parser.add_argument('--job-id', action='append', help='Select an exact archived job; repeat for a diverse calibration set')
    parser.add_argument('--min-winner-hp-percent', type=float, default=60,
                        help='Minimum recorded winning-army HP remaining (default: 60; use 50 only for secondary coverage)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(LOCAL.resolve()):
        parser.error(f'--output must be inside {LOCAL}')
    archives = args.archive or [Path('E:/AoE2 Renders') / folder / 'run.json' for folder in DEFAULT_ARCHIVES]
    document = prepare_document(args.reference_db, archives, args.all,
                                args.min_winner_hp_percent, args.job_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(jobs=len(document['jobs']), output=str(output))))


if __name__ == '__main__':
    main()
