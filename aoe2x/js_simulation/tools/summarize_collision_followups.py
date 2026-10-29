"""Report behavior-change validation without merging it into ranking data."""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

directory = Path(sys.argv[1])
rows = [json.loads(line) for line in (directory / 'runs.jsonl').read_text().splitlines() if line]
manifest = json.loads((directory / 'manifest.json').read_text())
key = lambda row: (row['kind'], row['matchupId'], row['seed'])
if len({key(row) for row in rows}) != len(rows):
    raise ValueError('duplicate validation records')
if any(row['sourceHashes'] != manifest['sourceHashes'] for row in rows):
    raise ValueError('mixed validation source versions')
complete = {key(row) for row in rows} == {key(row) for row in manifest['tasks']}
controls = [row for row in rows if row['kind'] == 'control']
anomalies = [row for row in rows if row['kind'] == 'anomaly']
changes = []
for row in controls:
    before, after = row.get('baseline') or {}, row.get('result') or {}
    changes.append({
        'matchupId': row['matchupId'], 'seed': row['seed'], 'teams': row['teams'],
        'exact': row['exact'], 'winnerChanged': before.get('winnerOwner') != after.get('winnerOwner'),
        'baselineWinner': before.get('winnerOwner'), 'candidateWinner': after.get('winnerOwner'),
        'baselineGameSeconds': before.get('ticks', 0) / 60,
        'candidateGameSeconds': after.get('ticks', 0) / 60,
        'baselineRemaining': before.get('remainingByOwner'),
        'candidateRemaining': after.get('remainingByOwner'),
    })
counts = Counter('processing_timeout' if row.get('watchdog') else 'engine_error' if row.get('error')
                 else row.get('result', {}).get('outcome', 'missing') for row in anomalies)
summary = {
    'updatedAt': datetime.now(timezone.utc).isoformat(),
    'sourceHashes': rows[0]['sourceHashes'] if rows else None,
    'complete': complete,
    'controlFailures': sum(bool(row.get('watchdog') or row.get('error') or row.get('result', {}).get('outcome') not in ('win', 'draw')) for row in controls),
    'controls': len(controls), 'exactControls': sum(row['exact'] is True for row in controls),
    'changedControls': sum(row['exact'] is False for row in controls),
    'winnerChanges': sum(row['winnerChanged'] for row in changes),
    'controlComparisons': changes,
    'anomalyRetries': len(anomalies), 'anomalyOutcomes': dict(counts),
    'anomalies': [{key: row.get(key) for key in ['matchupId', 'seed', 'teams', 'wallSeconds',
                  'lastProgress', 'result', 'error', 'watchdog']} for row in anomalies],
    'dataPolicy': 'Separate engine version. Keep original results immutable; do not combine changed behavior with original ranking samples. Recompute affected campaign results before scoring.',
}
if (directory / 'test-status.json').exists():
    summary['tests'] = json.loads((directory / 'test-status.json').read_text())
temporary = directory / 'summary.json.tmp'
temporary.write_text(json.dumps(summary, indent=2) + '\n')
temporary.replace(directory / 'summary.json')
lines = ['# Movement, pursuit and contact corrections: validation', '',
         f"Coverage: {len(rows)}/{len(manifest['tasks'])} recorded tasks; complete={complete}.", '',
         f"{len(controls)} pilot checks: {summary['exactControls']} exact, "
         f"{summary['changedControls']} changed, {summary['winnerChanges']} winner changes.", '',
         f"{len(anomalies)} anomaly retries: {dict(counts)}.", '',
         'The exact-preserving collision optimization has its own validation report. These ',
         'additional corrections intentionally repair pursuit, contact handoffs, obstacle routing and collision recovery.', '',
         '| Matchup / seed | Processing seconds | Game seconds reached | Status |',
         '|---|---:|---:|---|']
for row in anomalies:
    result, progress = row.get('result') or {}, row.get('lastProgress') or {}
    status = 'processing timeout' if row.get('watchdog') else 'engine error' if row.get('error') else result.get('outcome', 'missing')
    game = result.get('ticks', progress.get('tick', 0)) / 60
    lines.append(f"| {' vs. '.join(row['teams'])} / {row['seed']} | {row['wallSeconds']:.2f} | {game:.2f} | {status} |")
lines.extend(['', summary['dataPolicy'], '',
              (f"Regression checks: {summary['tests']['passed']}/{summary['tests']['tests']} passed; "
               f"{summary['tests']['failed']} failed. See [test-status.json](test-status.json)."
               if 'tests' in summary else 'Regression checks are still pending.'), '',
              'See [summary.json](summary.json) for winner, survivor, and duration comparisons; ',
              '[runs.jsonl](runs.jsonl) includes every result and its engine source hashes.', ''])
(directory / 'README.md').write_text('\n'.join(lines))
print(json.dumps({key: summary[key] for key in ['updatedAt', 'controls', 'exactControls',
                 'changedControls', 'winnerChanges', 'anomalyRetries', 'anomalyOutcomes']}))
