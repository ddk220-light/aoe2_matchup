#!/usr/bin/env python3
"""Reproduce this read-only analysis from the frozen inventory and reviewed export."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05'
BRANCH = 'simulations/civ-matchups-mismatch-validation-2026-11-05'
GITHUB = 'https://github.com/ddk220-light/aoe2_matchup/blob/' + BRANCH + '/'
SHA = lambda data: hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def read_rows(path):
    return [json.loads(x) for x in gzip.decompress(path.read_bytes()).splitlines() if x]


def percent(n, total):
    return 100 * n / total if total else None


def write_csv(path, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode()
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == '.gz' else data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', default=BASE)
    parser.add_argument('--snapshot', default=BASE + '/correction-snapshots/review-ready-2026-11-07')
    parser.add_argument('--output', default=str(Path(__file__).parent))
    args = parser.parse_args()
    campaign, snapshot, output = ROOT / args.campaign, ROOT / args.snapshot, Path(args.output).resolve()
    assert not (output / 'analysis.json').exists(), 'Use a new output directory; preserve prior analysis.'
    output.mkdir(parents=True, exist_ok=True)
    summary = read_json(snapshot / 'summary.json')
    manifest = read_json(snapshot / 'manifest.json')
    state = read_json(campaign / 'state.json')
    assert summary['reviewedContexts'] == 10222 and summary['remainingValidationContexts'] == 5
    assert summary['complete'] is False and state['status'] == 'blocked_needs_diagnosis'
    for name, digest in manifest['files'].items():
        assert SHA((snapshot / name).read_bytes()) == digest
    jobs = {j['id']: j for j in read_rows(campaign / 'jobs.jsonl.gz')}
    originals = {r['evidenceId']: r['evidence'] for r in read_rows(campaign / 'original-evidence.jsonl.gz')}
    cells = read_rows(campaign / 'mismatches.jsonl.gz')
    reviews = {r['jobId']: r for r in read_rows(snapshot / 'reviewed-contexts.jsonl.gz')}
    native = [json.loads(x) for x in (campaign / 'runs.jsonl').read_text().splitlines()]
    attempts = [json.loads(x) for x in (campaign / 'attempts.jsonl').read_text().splitlines()]
    native_by_job = defaultdict(list)
    for r in native:
        native_by_job[r['matchupId']].append(r)
    blocked = sorted(set(jobs) - set(reviews))
    assert set(blocked) == set(state['blockedJobs']) and len(blocked) == 5
    by_type, by_tier, by_rule, by_mode = [defaultdict(Counter) for _ in range(4)]
    transitions, outcomes, seed_counts = Counter(), Counter(), Counter()
    context_rows, blockers, low_hp, mixed, hp_growth = [], [], [], [], []
    growth_seed_ratios = []

    for job_id, job in sorted(jobs.items()):
        assert len(job['evidenceIds']) == 1
        evidence_id = job['evidenceIds'][0]
        original, review = originals[evidence_id], reviews.get(job_id)
        evidence_type = original['evidenceType']
        tier, rule = original.get('predictionTier') or '(none)', original.get('ruleId') or '(none)'
        groups = [by_type[evidence_type], by_rule[(evidence_type, rule)], by_mode[job['validationMode']]]
        if evidence_type == 'predicted_unvalidated':
            groups.append(by_tier[tier])
        for group in groups:
            group['inventory'] += 1
            group['reviewed' if review else 'blocked'] += 1
            if review:
                group['changed' if review['changed'] else 'unchanged'] += 1
        missing, median_hp, grows_above_initial = [], '', False
        if review:
            assert review['status'] == 'passed' and review['exactReplay']['exact'] and not review['requiredSeeds']
            assert review['context'] == job['context'] and review['contextHash'] == job['contextHash']
            assert review['originalEvidence'] == [{'evidenceId': evidence_id, 'evidence': original}]
            transitions[(original['outcome'], review['outcome'])] += 1
            outcomes[review['outcome']] += 1
            seed_counts[len(review['seedResults'])] += 1
            if review['outcome'] in ['a_win', 'b_win']:
                fractions = [r['winnerHpFraction'] for r in review['seedResults']]
                assert all(math.isfinite(value) and value >= 0 for value in fractions)
                for seed in review['seedResults']:
                    measured = next(record for record in review['measuredRecords'] if record['seed'] == seed['seed'])
                    ratio = max(measured['unitRemainingHp'] / measured['unitStartingHp'],
                                measured['opponentRemainingHp'] / measured['opponentStartingHp'])
                    assert math.isclose(seed['winnerHpFraction'], ratio, rel_tol=1e-12, abs_tol=1e-12)
                    if ratio > 1.000000001:
                        growth_seed_ratios.append(ratio)
                        grows_above_initial = True
                median_hp = statistics.median(fractions)
        else:
            saved = {r['seed']: r for r in native_by_job[job_id]}
            missing = [seed for seed in [0, 1, 2] if seed not in saved]
            if not missing and len({saved[seed]['winnerOwner'] for seed in [0, 1, 2]}) > 1:
                missing = [seed for seed in range(3, 10) if seed not in saved]
            diagnosis_file = campaign / 'diagnostics' / job_id / 'REVIEW.json'
            diagnosis = read_json(diagnosis_file)
            assert diagnosis['diagnosticOnly'] is True and missing
            description = diagnosis.get('diagnosis') or diagnosis.get('classification')
            blockers.append({'jobId': job_id, 'physicalTeam2': job['teamKeys'][0],
                             'physicalTeam3': job['teamKeys'][1], 'counts': job['counts'],
                             'contextHash': job['contextHash'], 'validSeeds': sorted(saved),
                             'missingRequiredSeeds': missing, 'exactReplayMissing': True,
                             'diagnosis': description,
                             'diagnosisPath': str(diagnosis_file.relative_to(ROOT)),
                             'diagnosisSha256': SHA(diagnosis_file.read_bytes())})
        row = {'jobId': job_id, 'status': 'reviewed' if review else 'blocked',
               'contextHash': job['contextHash'], 'physicalTeam2': job['teamKeys'][0],
               'physicalTeam3': job['teamKeys'][1], 'count2': job['counts'][0], 'count3': job['counts'][1],
               'family': job['family'], 'scenarioHash': job['scenarioHash'], 'pairKey': job['pairKey'],
               'originalEvidenceId': evidence_id, 'originalEvidenceType': evidence_type,
               'originalRuleId': rule, 'originalPredictionTier': tier,
               'originalPredictionPolicy': original.get('predictionPolicy', ''),
               'originalPredictionRuleHash': original.get('predictionRuleHash', ''),
               'originalPredictionSourceSha256': original.get('predictionSourceSha256', ''),
               'originalCanonicalOutcome': original['outcome'],
               'reviewedCanonicalOutcome': review['outcome'] if review else '',
               'changedClassification': review['changed'] if review else '',
               'completeSeedCount': len(review['seedResults']) if review else '',
               'savedPartialSeedCount': len(native_by_job[job_id]) if not review else '',
               'missingRequiredSeeds': ','.join(map(str, missing)),
               'exactReplayStatus': 'passed' if review else 'missing',
               'displayedMismatchCells': job['displayedCells'],
               'medianWinningHpFraction': median_hp,
               'hasHpRatioAboveInitialTotal': grows_above_initial,
               'lowMedianWinningHpAtMost10Percent': median_hp != '' and median_hp <= .1,
               'evidencePath': review['reviewFile'] if review else str((campaign / 'diagnostics' / job_id / 'REVIEW.json').relative_to(ROOT))}
        context_rows.append(row)
        if row['lowMedianWinningHpAtMost10Percent']:
            low_hp.append(row)
        if grows_above_initial:
            hp_growth.append(row)
        if review and review['outcome'] == 'close_uncertain':
            mixed.append(row)

    cell_rows, cell_types, direct_opposites = [], defaultdict(Counter), Counter()
    direct_by_type, direct_contexts, direct_rows = defaultdict(Counter), {}, []
    flip = lambda value: {'a_win': 'b_win', 'b_win': 'a_win'}.get(value, value)
    for number, cell in enumerate(cells, 1):
        job, review = jobs[cell['validationJob']], reviews.get(cell['validationJob'])
        original = originals[job['evidenceIds'][0]]
        assert '|'.join(sorted([cell['unitA']['profileHash'], cell['unitB']['profileHash']])) == job['pairKey']
        display = lambda outcome: outcome if cell['unitA']['profileHash'] == job['pairKey'].split('|')[0] else flip(outcome)
        before = cell['current']['outcome']
        assert before == display(original['outcome']), 'Original display orientation mismatch.'
        after = display(review['outcome']) if review else ''
        changed = before != after if review else ''
        cell_types[original['evidenceType']]['inventory'] += 1
        cell_types[original['evidenceType']]['reviewed' if review else 'blocked'] += 1
        if review:
            cell_types[original['evidenceType']]['changed' if changed else 'unchanged'] += 1
        legacy = {claim.get('legacyOutcome') for claim in cell['claims'] if claim.get('category') == 'opposite_winner'}
        if len(legacy) == 1 and next(iter(legacy)) in ['a_win', 'b_win']:
            old = next(iter(legacy))
            assert old == flip(before)
            direct_opposites['inventoryDisplayedCells'] += 1
            verdict = 'blocked' if not review else 'currentRetained' if after == before else 'legacyWinnerMatched' if after == old else 'mixedResult'
            direct_opposites[verdict] += 1
            direct_by_type[original['evidenceType']][verdict] += 1
            record = (original['evidenceType'], verdict)
            assert job['id'] not in direct_contexts or direct_contexts[job['id']] == record, 'Conflicting legacy verdicts across display aliases.'
            direct_contexts[job['id']] = record
            direct_rows.append({'mismatchRow': number, 'jobId': job['id'], 'contextHash': job['contextHash'],
                                'unitA': cell['unitA']['key'], 'unitB': cell['unitB']['key'],
                                'originalEvidenceType': original['evidenceType'], 'legacyDisplayedOutcome': old,
                                'originalDisplayedOutcome': before, 'reviewedDisplayedOutcome': after,
                                'verdict': verdict})
        cell_rows.append({'mismatchRow': number, 'jobId': job['id'], 'contextHash': job['contextHash'],
                          'unitA': cell['unitA']['key'], 'unitB': cell['unitB']['key'],
                          'status': 'reviewed' if review else 'blocked',
                          'originalDisplayedOutcome': before, 'reviewedDisplayedOutcome': after,
                          'changedClassification': changed, 'originalEvidenceType': original['evidenceType'],
                          'originalRuleId': original.get('ruleId') or '(none)',
                          'claimCategories': '|'.join(sorted({claim['category'] for claim in cell['claims']}))})

    assert len(context_rows) == 10227 and len(reviews) == 10222 and len(cell_rows) == 18298
    changed_contexts = [r for r in context_rows if r['changedClassification'] is True]
    assert len(changed_contexts) == 1164
    assert sum(r['changedClassification'] is True for r in cell_rows) == 1362
    assert sum(r['status'] == 'reviewed' for r in cell_rows) == 18293
    assert len(mixed) == 412 and len(low_hp) == 367
    assert len(hp_growth) == 7 and len(growth_seed_ratios) == 21
    assert all('Wei|elite_tiger_cavalry_wei' in [r['physicalTeam2'], r['physicalTeam3']] for r in hp_growth)
    for groups in [by_type, by_tier, by_rule, by_mode, cell_types]:
        for group in groups.values():
            for key in ['inventory', 'reviewed', 'changed', 'unchanged', 'blocked']:
                group.setdefault(key, 0)
            assert group['inventory'] == group['reviewed'] + group['blocked']
            assert group['reviewed'] == group['changed'] + group['unchanged']
            group['agreementPercentWithinSelectedReviewedSubset'] = percent(group['unchanged'], group['reviewed'])
    phases = [read_json(f) for f in sorted((campaign / 'reviews').glob('[0-9][0-9][0-9].json'))]
    attempt_jobs = {r['matchupId'] for r in attempts}
    direct_context_totals = Counter(v[1] for v in direct_contexts.values())
    direct_context_types = defaultdict(Counter)
    for evidence_type, verdict in direct_contexts.values():
        direct_context_types[evidence_type][verdict] += 1
    assert dict(direct_context_totals) == {'currentRetained': 396, 'legacyWinnerMatched': 125, 'mixedResult': 39, 'blocked': 1}
    assert dict(direct_context_types['predicted_unvalidated']) == {'currentRetained': 193, 'legacyWinnerMatched': 125, 'mixedResult': 39, 'blocked': 1}
    analysis = {'version': 'civ-mismatch-available-data-analysis-v2', 'asOf': state['finishedAt'],
                'scope': {'inventoryContexts': 10227, 'inventoryDisplayedCells': 18298,
                          'reviewedContexts': 10222, 'blockedContexts': 5,
                          'reviewedDisplayedCells': 18293, 'blockedDisplayedCells': 5,
                          'coveragePercent': percent(10222, 10227),
                          'changedContexts': 1164, 'unchangedContexts': 9058,
                          'changedDisplayedCells': 1362, 'unchangedDisplayedCells': 16931,
                          'oppositeWinnerChanges': 842, 'decisiveToMixedChanges': 322,
                          'mixedResultContexts': len(mixed), 'decisiveLowMedianHpContexts': len(low_hp),
                          'allContextsVerified': False, 'allPermittedQueueWorkFinished': True},
                'definitions': {'context': 'Original physical profile order, counts, weighted costs, family, scenario and policy; distinct from displayed alias cells.',
                                'changed': 'Winner/close classification differs from immutable original baseline, not necessarily a new change versus current production.',
                                'close_uncertain': 'Required seed set contains mixed winners or a non-decisive result; identity equivalence remains semantic.',
                                'lowMedianHp': 'Decisive contexts whose median winning army HP divided by its recorded initial HP is at most 10%; descriptive only, no classification change. HP growth mechanics can produce ratios above 100%.',
                                'agreement': 'Unchanged classification within this selected legacy/current mismatch inventory; not unbiased global forecast accuracy.'},
                'originalEvidenceTypesByContext': dict(by_type), 'originalEvidenceTypesByDisplayedCell': dict(cell_types),
                'originalForecastTiers': dict(by_tier),
                'originalRules': [{'evidenceType': key[0], 'ruleId': key[1], **value} for key, value in sorted(by_rule.items())],
                'validationModes': dict(by_mode),
                'transitions': [{'original': key[0], 'reviewed': key[1], 'contexts': count} for key, count in sorted(transitions.items())],
                'reviewedOutcomes': dict(sorted(outcomes.items())), 'requiredSeedSetSizes': dict(sorted(seed_counts.items())),
                'hpRatiosAboveInitialTotal': {'contexts': len(hp_growth), 'seedRatios': len(growth_seed_ratios),
                                             'minimumRatio': min(growth_seed_ratios), 'maximumRatio': max(growth_seed_ratios),
                                             'winningProfile': 'Wei|elite_tiger_cavalry_wei',
                                             'frozenMechanic': 'hp_per_kill=10, hp_per_kill_max=40, hp_per_kill_increases_maximum=true',
                                             'sourceCode': 'aoe2x/js_simulation/src/combat/world.js:5785',
                                             'valuesClampedOrChanged': False},
                'directOppositeWinnerDisplayRows': dict(direct_opposites),
                'directOppositeWinnerDisplayedCellsByOriginalEvidence': dict(direct_by_type),
                'directOppositeWinnerPhysicalContexts': {'inventory': len(direct_contexts), **dict(direct_context_totals)},
                'directOppositeWinnerContextsByOriginalEvidence': dict(direct_context_types),
                'blocked': blockers,
                'failures': {'attemptJournalRecords': len(attempts), 'contextsWithAttemptFailures': len(attempt_jobs),
                             'eventuallyReviewedContextsWithAttemptFailures': len(attempt_jobs & set(reviews)),
                             'unfinishedContextsWithAttemptFailures': len(attempt_jobs - set(reviews)),
                             'watchdogRecords': sum(bool(r.get('watchdog')) for r in attempts),
                             'missingRequiredSeedMeasurementsMinimum': sum(len(r['missingRequiredSeeds']) for r in blockers),
                             'missingPairReplays': len(blockers)},
                'checks': {'validUniqueCampaignJournalRecords': len(native), 'exactReplayChecks': 10222,
                           'phaseReviews': len(phases), 'passedPhases': sum(r['status'] == 'passed' for r in phases),
                           'phasesWithBlockedContexts': sum(r['status'] == 'complete_with_blocked' for r in phases),
                           'displayOrientationMismatches': 0, 'originalEvidenceObjectsPreserved': True},
                'sources': {'campaignHash': summary['campaignHash'], 'campaignManifestSha256': summary['campaignManifestSha256'],
                            'snapshotPath': str(snapshot.relative_to(ROOT)), 'snapshotSourceCommit': summary['sourceCommit'],
                            'snapshotManifestSha256': SHA((snapshot / 'manifest.json').read_bytes()),
                            'originalDatabaseSha256': summary['originalDatabaseSha256'],
                            'physicsVersion': summary['physicsVersion'], 'predictionPolicy': 'prediction-first-pass-v2',
                            'servingDatabaseSha256Unchanged': '2ea93603cf9b4e69ee6572c36938a0e49c63bca7a6384c0a2409d7d762325c1e',
                            'productionAndStagingCommitUnchanged': '2315f74ad12d57bb2af73d47c622eb0c7d06c3b2'},
                'limitations': ['The inventory was selected because old/current tables disagreed; these agreement rates are not global accuracy estimates.',
                                'Exact replay and export checks establish reproducibility and provenance in frozen V3, not independent AoE2 game fidelity.',
                                'Five incomplete contexts remain excluded; saved partial seeds and diagnostic snapshots do not establish outcomes.',
                                'Original flags, sourceContext, policy and rule/source hashes remain in the cumulative snapshot; no model, physics or ranking formula was changed.',
                                'Production remains unchanged. A consolidated website release requires analysis/discussion and explicit approval.']}
    (output / 'analysis.json').write_text(json.dumps(analysis, indent=2, sort_keys=True) + '\n')
    write_csv(output / 'context-analysis.csv.gz', context_rows)
    write_csv(output / 'display-cell-analysis.csv.gz', cell_rows)
    write_csv(output / 'changed-contexts.csv', changed_contexts)
    write_csv(output / 'close-or-low-survival-contexts.csv.gz', sorted(mixed + low_hp, key=lambda r: r['jobId']))
    write_csv(output / 'hp-growth-contexts.csv.gz', hp_growth)
    write_csv(output / 'direct-winner-conflicts.csv.gz', direct_rows)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    order = ['stronger_support', 'broader_agreement', 'weak_model_agreement', 'opponent_specific_forecast']
    labels = ['Stronger support', 'Broader agreement', 'Weak model agreement', 'Opponent-specific forecast']
    agreement = [by_tier[t]['agreementPercentWithinSelectedReviewedSubset'] for t in order]
    fig, ax = plt.subplots(figsize=(10.5, 4.4))
    fig.patch.set_facecolor('#fafaf7'); ax.set_facecolor('#fafaf7')
    ax.barh(labels, agreement, color='#285f87', label='Classification unchanged', height=.55)
    ax.barh(labels, [100-v for v in agreement], left=agreement, color='#d99c3f', label='Classification changed', height=.55)
    for i, (tier, value) in enumerate(zip(order, agreement)):
        ax.text(value / 2, i, f'{value:.1f}%', ha='center', va='center', color='white', weight='bold')
        ax.text(101.5, i, f'n = {by_tier[tier]["reviewed"]:,}', ha='left', va='center', fontsize=10)
    ax.set_xlim(0, 117); ax.set_xticks([0,25,50,75,100], ['0%', '25%', '50%', '75%', '100%'])
    ax.invert_yaxis(); ax.tick_params(axis='both', length=0, labelsize=10)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.legend(loc='lower left', bbox_to_anchor=(-.02, -.35), frameon=False, ncol=2, fontsize=10)
    fig.suptitle('Forecast agreement within the selected mismatch inventory', x=.02, ha='left', fontsize=15, weight='bold')
    fig.text(.02, .885, 'Unchanged winner/close classification against frozen V3 seeds; five unresolved forecasts excluded.', fontsize=10)
    fig.text(.02, .025, 'These selected-subset rates do not estimate global forecast accuracy.', fontsize=10)
    fig.subplots_adjust(left=.28, right=.98, top=.79, bottom=.28)
    fig.savefig(output / 'forecast-tier-agreement.png', dpi=180, metadata={'Software': 'matplotlib'})
    plt.close(fig)

    def table(headers, rows):
        return '| ' + ' | '.join(headers) + ' |\n|' + '|'.join(['---']*len(headers)) + '|\n' + ''.join('| ' + ' | '.join(str(v) for v in row) + ' |\n' for row in rows)
    tier_table = table(['Original tier', 'Reviewed contexts', 'Unchanged', 'Changed', 'Unresolved', 'Agreement in this subset'],
                       [(t, f'{by_tier[t]["reviewed"]:,}', f'{by_tier[t]["unchanged"]:,}', f'{by_tier[t]["changed"]:,}', by_tier[t]['blocked'], f'{by_tier[t]["agreementPercentWithinSelectedReviewedSubset"]:.1f}%') for t in order])
    type_table = table(['Original evidence', 'Reviewed', 'Unchanged', 'Changed', 'Unresolved'],
                       [(t, f'{g["reviewed"]:,}', f'{g["unchanged"]:,}', f'{g["changed"]:,}', g['blocked']) for t,g in sorted(by_type.items())])
    blocker_names = {'mv_5e1e0d268234acff1d6e9008': 'Armenian Champion / Tupi Imperial Slinger',
                     'mv_306dd795e5f68374d24e2a99': 'Aztec Elite Skirmisher / Hunnic Elite Tarkan',
                     'mv_9bc2d959cf36c2b00f7ffa75': 'Chinese Elite Chu Ko Nu / Khitan Mounted Trebuchet',
                     'mv_c72552550f46f7a6f193d254': 'Muisca Elite Guecha Warrior / Viking Champion',
                     'mv_e50435eb3040ac8928d195ee': 'Lithuanian Elite Skirmisher / Gurjara Heavy Camel'}
    blocker_rows = []
    for b in blockers:
        label = blocker_names[b['jobId']]
        blocker_rows.append([f'[{label}]({GITHUB}{b["diagnosisPath"]})', '/'.join(map(str,b['counts'])), ', '.join(map(str,b['validSeeds'])), ', '.join(map(str,b['missingRequiredSeeds']))])
    blocker_table = table(['Original physical matchup (diagnosis)', 'Army counts', 'Saved seeds', 'Missing required seeds'], blocker_rows)
    snapshot_url = GITHUB + str(snapshot.relative_to(ROOT))
    report = f'''# 10,222 contexts verified; five remain unresolved

Evidence cutoff: {state['finishedAt']}. This is the available-data review checkpoint for the frozen legacy/current mismatch inventory.

## Available corrections are ready for discussion

- **10,222 of 10,227 physical contexts are verified (99.95%)**, covering **18,293 of 18,298 selected displayed cells**. Five diagnosed contexts still lack complete seed/replay evidence.
- **1,164 baseline classifications changed:** 842 now have the opposite winner and 322 became mixed/close results. These changes affect 1,362 displayed alias cells. The other 9,058 reviewed contexts retained their classifications.
- All changes came from the originally forecasted group. Historical stronger-support forecasts agreed in 2,823 of 2,886 reviewed contexts (97.8%); weak-model-agreement forecasts agreed in 1,147 of 1,875 (61.2%).
- The available queue is finished and only the five blocked contexts remain. Production is unchanged. Review the data and blockers before authorizing one consolidated website release.

These are **selected mismatch results**, not an unbiased estimate of global forecast accuracy. The comparisons use the immutable original database; they include corrections published before the data-only pause and are not all additional changes versus current production.

## Historical forecast tiers separated the stronger and weaker cases

![Agreement by the four original forecast tiers](forecast-tier-agreement.png)

{tier_table}

Across the 6,748 reviewed forecasts, 5,584 retained their original winner/close classification (**82.8%**). Opponent-specific forecasts had 69 changes in 137 reviewed contexts, so that small subgroup needs particular attention during review. Weak-model-agreement forecasts account for 728 of the 1,164 changes. The tier names are preserved historical categories, not calibrated probabilities or new model judgments. No forecasts were retrained or expanded.

## Original observations and inference classifications were retained

{type_table}

The 1,004 originally inferred contexts comprise 870 `R1_STATIC_DIRECTION`, 110 `R2_ROBUST_TRADEOFF` and 24 `R3_TWO_SIDED_STATIC` contexts; all retained their classifications in these tests. An additional 124 forecast contexts carry R1/R2 provenance and stay in the forecast group: 3 of 56 carrying R1 and 4 of 68 carrying R2 changed. They must not be relabeled as failed inferred measurements.

Verification used 7,843 complete freshly computed seed sets and 2,379 complete pre-existing native sets with a fresh exact replay. The latter verify reproducibility of prior measured evidence; they do not test forecast accuracy. All 10,222 included contexts have complete required seeds and an exact replay under the original physical context.

## Direct old/current winner conflicts favor the current label more often

The direct opposite-winner source claims resolve to **{direct_opposites['inventoryDisplayedCells']:,} unique displayed cells**; repeated claims from overlapping sources are counted once here. Among the reviewed cells, the current classification was retained in {direct_opposites['currentRetained']:,}, the legacy winner matched in {direct_opposites['legacyWinnerMatched']:,}, and {direct_opposites['mixedResult']:,} became mixed results; {direct_opposites['blocked']} remains unresolved. These outcomes apply to the frozen current physical scenarios and do not establish the legacy table's original battle conditions.

Deduplicating displayed aliases gives **561 physical contexts**, of which 560 have reviewed results: 396 retained the current classification, 125 matched the legacy winner, and 39 were mixed. The 396 include 156 originally observed and 47 inferred contexts, so they must not all be described as successful guesses.

For the **357 reviewed physical contexts that were forecasts and directly named the opposite winner to the legacy table**, the split is:

| Validation supports | Contexts | Share of the 357 reviewed forecast conflicts |
|---|---|---|
| Newer forecast | 193 | 54.1% |
| Legacy winner | 125 | 35.0% |
| Mixed/close outcome | 39 | 10.9% |

One further forecast conflict is simulator-blocked and excluded. Counting displayed cells instead gives 244 newer-forecast matches, 155 legacy matches and 54 mixed results (453 reviewed cells). See the [full direct-conflict list](direct-winner-conflicts.csv.gz). The rest of the 10,227-context inventory also includes mixed/close and composition-coverage differences; it is not entirely direct opposite-winner disputes or forecasts. The five user-supplied winners are recorded separately in the [user-outcome addendum](USER_OUTCOMES.md) and excluded from all simulator agreement rates.

## Mixed outcomes and low surviving HP need different interpretations

There are **412 mixed/close results**: 90 retain an original close classification and 322 replace a decisive forecast. The frozen classifier uses initial seeds 0–2 and requires seeds 3–9 if the initial winners differ. Identity equivalence remains a separate semantic classification.

Separately, **367 decisive contexts have median winning-army surviving HP at or below 10%** across their required seeds. This descriptive review aid does not change their winners, classifications or scores. The [close-or-low-survival list](close-or-low-survival-contexts.csv.gz) retains both kinds with their distinct result and HP fields.

HP is expressed relative to the recorded initial army HP. Twenty-one seed ratios in [seven Wei Elite Tiger Cavalry contexts](hp-growth-contexts.csv.gz) exceed 100% (105.0–107.5%). The frozen profile grants 10 HP and maximum HP per kill, capped at 40; these are preserved ratios, not percentages of a fixed maximum. All reported ratios were checked against the original remaining/starting HP fields, with no clamping or measurement changes.

## Five cases cannot currently become corrections

{blocker_table}

The Armenian/Tupi and Muisca/Viking cases repeat idle patrol-endpoint states. The Aztec/Hunnic and Lithuanian/Gurjara cases retain survivors in prolonged pursuit/contact loops without further damage. The Chinese/Khitan case retains two survivors with no further damage while movement and route activity continue. Each linked diagnosis binds the original context, attempt lines and saved timelines. None establishes a real-game draw or a winner.

At least **10 required seed measurements and five pair replay reviews remain missing**. More seeds could be needed if newly completed initial seeds disagreed. Four contexts exhausted the normal watchdog schedule; the Armenian fourth attempt was deliberately canceled after its repeated diagnostic state was preserved. Blind retries, copied winners and physics changes are outside the current scope. A separately reviewed recovery decision is needed to advance them.

The campaign retains 39 watchdog attempt records across 18 contexts. Thirteen of those contexts eventually completed validly; five remain unresolved. Timeouts and diagnostic snapshots contribute no outcomes.

## Full data and reproducibility

- [Cumulative correction snapshot]({snapshot_url}/manifest.json): full native records, original evidence/flags, exact replay references and original physical contexts. Its `complete` field is **false**, with five contexts excluded.
- [Full frozen displayed mismatch list]({GITHUB}{BASE}/mismatches.jsonl.gz) and [full physical-context inventory]({GITHUB}{BASE}/jobs.jsonl.gz).
- [All context analysis rows](context-analysis.csv.gz), [all displayed-cell rows](display-cell-analysis.csv.gz), and [all 1,164 changed contexts](changed-contexts.csv).
- [Exact analytical counts and definitions](analysis.json), [reproducible analysis script](build_analysis.py), and [verification receipt](verification.json).
- [Frozen campaign manifest]({GITHUB}{BASE}/manifest.json), [source checkpoint](https://github.com/ddk220-light/aoe2_matchup/commit/{summary['sourceCommit']}), and [retained export-buffer regression check]({GITHUB}{BASE}/exporter-checks/large-review-list-2026-11-06.json).

The source audit reconciles all 80 phase reviews (75 passed and five with blocked contexts), 28,195 unique campaign journal records, all 62 frozen runtime files and 62 frozen input files, and zero display-orientation mismatches. Every original evidence object is retained unchanged in the snapshot, including prediction policy `prediction-first-pass-v2`, per-row rule/source hashes, `sourceContext`, flags and prior validation status. Display aliases are mapped through their frozen validation job; a physical winner is never transferred into a reversed context.

Reproduce the tables and chart from the repository root, choosing a new output directory:

```sh
python {str(Path(__file__).resolve().relative_to(ROOT))} --output /tmp/aoe2-mismatch-review-reproduction
```

The complete seed/replay checks and these analytical summaries establish provenance and reproducibility **inside frozen V3**. They are not independent in-game fidelity validation. The separate YouTube recording indexes discussed earlier have not been imported or mixed into these native records.

## Release hold

The serving database remains at SHA-256 `{analysis['sources']['servingDatabaseSha256Unchanged']}`. The immutable comparison baseline is `{summary['originalDatabaseSha256']}`. Website main/staging remain at `{analysis['sources']['productionAndStagingCommitUnchanged']}`.

No serving-data import, website rebuild/export, release CI/preview, staging/main push or production deployment is part of this checkpoint. Keep the monitor paused for analysis and discussion. One consolidated release still requires the user's explicit approval and the saved release gates; preserve all unresolved cases and historical evidence.
'''
    (output / 'README.md').write_text(report)
    print(json.dumps({'reviewedContexts': len(reviews), 'changedContexts': len(changed_contexts),
                      'displayedRows': len(cell_rows), 'blocked': len(blockers),
                      'mixedResults': len(mixed), 'lowMedianHpDecisive': len(low_hp), 'output': str(output)}))


if __name__ == '__main__':
    main()
