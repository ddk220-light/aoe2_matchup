"""Summarize exact-parity checks and supplemental retry outcomes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validation', required=True, type=Path)
    parser.add_argument('--diagnostics', required=True, type=Path)
    args = parser.parse_args()
    directory = args.validation
    rows = [json.loads(line) for line in (directory / 'runs.jsonl').read_text().splitlines() if line]
    diagnostics = json.loads((args.diagnostics / 'summary.json').read_text())
    diagnostic_by_key = {(row['matchupId'], row['seed']): row for row in diagnostics}
    checks = [row for row in rows if row.get('exact') is not None]
    completions = [row for row in rows if row['kind'] == 'completion']
    paired = []
    for row in rows:
        reference = diagnostic_by_key.get((row['matchupId'], row['seed']))
        if row['kind'] != 'prefix' or not reference:
            continue
        expected = reference.get('result') or {}
        actual = row.get('result') or {}
        paired.append({
            'teams': row['teams'], 'matchupId': row['matchupId'], 'seed': row['seed'],
            'gameSeconds': row['maxTicks'] / 60,
            'baselineWallSeconds': reference['processingWallSeconds'],
            'candidateWallSeconds': row['wallSeconds'],
            'speedRatio': reference['processingWallSeconds'] / row['wallSeconds'],
            'expectedFinalStateHash': expected.get('finalStateHash'),
            'actualFinalStateHash': actual.get('finalStateHash'),
            'expectedEventLogHash': expected.get('eventLogHash'),
            'actualEventLogHash': actual.get('eventLogHash'),
            'exact': row['exact'],
        })
    full_baselines = []
    for path in (directory / 'baseline-completions').glob('*.json'):
        baseline = json.loads(path.read_text())
        candidate = next((row for row in completions if row['matchupId'] == baseline['matchupId']
                          and row['seed'] == baseline['seed']), None)
        if candidate is None or not baseline.get('result') or not candidate.get('result'):
            continue
        exact = all(candidate['result'][key] == baseline['result'][key]
                    for key in ['finalStateHash', 'eventLogHash'])
        full_baselines.append({'teams': candidate['teams'], 'matchupId': baseline['matchupId'],
                               'seed': baseline['seed'], 'exact': exact,
                               'baselineWallSeconds': baseline['wallSeconds'],
                               'candidateWallSeconds': candidate['wallSeconds']})
    counts = Counter('processing_timeout' if row.get('watchdog') else 'engine_error' if row.get('error')
                     else row.get('result', {}).get('outcome', 'missing') for row in completions)
    summary = {
        'updatedAt': datetime.now(timezone.utc).isoformat(),
        'candidateSourceSha256': rows[0]['sourceSha256'] if rows else None,
        'validationRuns': len(rows), 'exactChecks': len(checks),
        'exactMatches': sum(row['exact'] for row in checks),
        'mismatches': sum(row['exact'] is False for row in checks),
        'completionRetries': len(completions), 'completionOutcomes': dict(counts),
        'prefixComparisons': paired, 'completeBaselineComparisons': full_baselines,
        'medianPrefixSpeedRatio': statistics.median(row['speedRatio'] for row in paired) if paired else None,
        'timingCaveat': 'Prefix baselines had CPU profiling and detailed tracing; candidates use lightweight progress reporting. Concurrent workloads differ. Exact state/event comparisons are independent of timing.',
        'knownPreexistingTests': ['collision-recovery: sub-tile obstacle residual has invalid starting allied overlap on baseline and candidate',
                                 'collision-recovery: HCA Steppe expected -41.875, actual 29 on both baseline and candidate'],
    }
    temporary = directory / 'summary.json.tmp'
    temporary.write_text(json.dumps(summary, indent=2) + '\n')
    temporary.replace(directory / 'summary.json')
    lines = ['# Collision optimization validation', '',
             f"{len(checks)} exact state/event checks; {summary['mismatches']} mismatches. "
             f"{len(completions)} flagged-run retries recorded.", '',
             f"Retry outcomes: {dict(counts)}.", '',
             'The candidate preserves solver order, tolerances, random seeds, unit stats, and attack mechanics. ',
             'It caches pair properties and repeated static-obstacle passes within one solve, conservatively ',
             'rejects unreachable obstacles, and skips exactly repeated fixed-point sweeps. ',
             'A full-state hash checks movement and other state; an event hash additionally checks the event sequence.', '',
             'Full retry runs use only the 120-second wall watchdog. Prefix runs deliberately stop at their ',
             'reference tick, so their timeout result is expected and does not represent a failed retry.', '',
             '| Matchup / seed | Baseline processing seconds | Optimized processing seconds | Exact complete fight |',
             '|---|---:|---:|---|']
    for row in full_baselines:
        lines.append(f"| {' vs. '.join(row['teams'])} / {row['seed']} | {row['baselineWallSeconds']:.2f} | "
                     f"{row['candidateWallSeconds']:.2f} | {row['exact']} |")
    lines.extend(['', 'See [summary.json](summary.json) for each partial-run hash comparison, ',
                  '[runs.jsonl](runs.jsonl) for every run, and [manifest.json](manifest.json) for the task list.', '',
                  summary['timingCaveat'], '',
                  'Verification also includes 1,200 seeded exact movement comparisons and 119 passing ',
                  'focused/active V3 tests. Two legacy collision-recovery assertions fail identically on ',
                  'the unchanged baseline and candidate; their expectations have not been rewritten.', ''])
    (directory / 'README.md').write_text('\n'.join(lines))
    print(json.dumps({key: value for key, value in summary.items()
                      if key not in ['prefixComparisons', 'knownPreexistingTests', 'timingCaveat']}))


if __name__ == '__main__':
    main()
