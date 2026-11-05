"""Wait for the bulk campaign, then collect resumable timeout diagnostics."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
SIM = ROOT / 'aoe2x/js_simulation'
HERE = Path(__file__).resolve()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read(path):
    return json.loads(path.read_text())


def records(campaign):
    with sqlite3.connect(f'file:{campaign}/results.sqlite?mode=ro', uri=True) as connection:
        return [json.loads(row[0]) for row in connection.execute('select record_json from runs')]


def make_job(manifest, row):
    matchup = next(item for item in manifest['matchups'] if item['id'] == row['matchupId'])
    return {
        'jobId': matchup['id'], 'seed': row['seed'],
        'teams': [{'mechanics': manifest['profiles'][key]['mechanics'], 'count': count}
                  for key, count in zip(matchup['teamKeys'], matchup['counts'])],
        'scenario': manifest['scenarios'][matchup['scenarioHash']],
        'disableAiOrders': True, 'disableKiting': True,
        'preserveOwnerOrientation': True, 'retainSnapshots': False,
    }


def build_plan(manifest, rows):
    matchups = {item['id']: item for item in manifest['matchups']}
    controls = []
    for group in ['Infantry', 'Ranged', 'Cavalry']:
        candidates = [row for row in rows if row['outcome'] in ('win', 'loss', 'draw')
                      and matchups[row['matchupId']]['group'] == group]
        row = min(candidates, key=lambda item: item['wallSeconds'])
        controls.append({'task': 'parity_control', 'original': row, 'removeGameCap': False})
    extended = [{'task': 'extend_game_time', 'original': row, 'removeGameCap': True}
                for row in rows if row.get('reason') == 'simulation_timeout']
    slow = [{'task': 'diagnose_processing_timeout', 'original': row, 'removeGameCap': False}
            for row in rows if row.get('reason') == 'wall_timeout']
    errors = [{'task': 'diagnose_engine_error', 'original': row, 'removeGameCap': False}
              for row in rows if row['outcome'] == 'error']
    # Investigate complete three-seed failures early, while retaining every seed.
    failure_counts = Counter(item['original']['matchupId'] for item in slow)
    slow.sort(key=lambda item: (-failure_counts[item['original']['matchupId']],
                               item['original']['matchupId'], item['original']['seed']))
    return controls + extended + errors + slow


def verify_runtime(manifest):
    for entry in manifest['runtimeFiles']:
        actual = hashlib.sha256((ROOT / entry['path']).read_bytes()).hexdigest()
        if actual != entry['sha256']:
            raise RuntimeError(f"Frozen campaign source changed: {entry['path']}")
    node_version = subprocess.check_output(['node', '--version'], text=True).strip()
    if node_version != manifest['nodeVersion']:
        raise RuntimeError('Node version differs from the original campaign')
    environment = {key: value for key, value in os.environ.items() if key.startswith('AOE2X_EXP_')}
    if environment != manifest['simulationEnvironment']:
        raise RuntimeError('Simulation environment differs from the original campaign')


def prepare_runtime(manifest, output):
    runtime = output / 'runtime'
    runtime.mkdir(exist_ok=True)
    for entry in manifest['runtimeFiles']:
        source = ROOT / entry['path']
        target = runtime / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    package = SIM / 'package.json'
    if package.exists():
        shutil.copy2(package, runtime / package.relative_to(ROOT))
    script = """
import { readFileSync, writeFileSync } from 'node:fs';
import { instrumentSource } from './aoe2x/js_simulation/node/ranking-diagnostic-hooks.mjs';
const runtime = process.argv[1];
for (const suffix of ['/aoe2x/js_simulation/src/fight.js', '/aoe2x/js_simulation/src/combat/world.js']) {
 const path = runtime + suffix;
 writeFileSync(path, instrumentSource(path, readFileSync(path, 'utf8')));
}
"""
    subprocess.run(['node', '--input-type=module', '-e', script, str(runtime)], cwd=ROOT, check=True)
    changes = []
    for entry in manifest['runtimeFiles']:
        digest = hashlib.sha256((runtime / entry['path']).read_bytes()).hexdigest()
        if digest != entry['sha256']:
            changes.append({'path': entry['path'], 'originalSha256': entry['sha256'], 'diagnosticSha256': digest})
    atomic(output / 'runtime-provenance.json', {
        'campaignHash': manifest['campaignHash'], 'nodeVersion': manifest['nodeVersion'],
        'purpose': 'An isolated engine copy with timing/trace hooks and a configurable game-time cap.',
        'changes': changes, 'createdAt': now(),
    })
    return runtime


def run_one(task, manifest, runtime, output, wall_seconds):
    original = task['original']
    key = f"{task['task']}_{original['matchupId']}_{original['seed']}"
    directory = output / 'runs' / key
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / 'result.json'
    if result_path.exists():
        return read(result_path)
    # Interrupted attempts keep their partial traces instead of losing evidence.
    if (directory / 'heartbeat.json').exists():
        archive = directory / f'interrupted-{time.time_ns()}'
        archive.mkdir()
        for name in ['heartbeat.json', 'timeline.jsonl', 'cpu.cpuprofile']:
            if (directory / name).exists():
                shutil.move(str(directory / name), archive / name)
    specification = {**{key: value for key, value in task.items() if key != 'original'},
                     'runtime': str(runtime), 'output': str(directory),
                     'job': make_job(manifest, original), 'wallSeconds': wall_seconds}
    atomic(directory / 'job.json', specification)
    start = time.monotonic()
    with (directory / 'process.log').open('a') as log:
        process = subprocess.Popen(['node', str(SIM / 'node/ranking-diagnostic-job.mjs'),
                                    str(directory / 'job.json')], cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            process.wait(timeout=wall_seconds + 10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    if not result_path.exists():
        heartbeat = read(directory / 'heartbeat.json') if (directory / 'heartbeat.json').exists() else None
        atomic(result_path, {
            'task': task['task'], 'matchupId': original['matchupId'], 'seed': original['seed'],
            'stopReason': 'hard_processing_cutoff' if process.returncode == -9 else 'diagnostic_process_error',
            'processingWallSeconds': time.monotonic() - start,
            'nominalWallLimitSeconds': wall_seconds, 'lastProgress': heartbeat,
            'result': None, 'error': {'returncode': process.returncode},
            'notes': 'Last progress is a lower bound on game time; a stuck tick may prevent a final update.',
        })
    result = read(result_path)
    result['teams'] = [f"{team['mechanics']['civilization']} {team['mechanics']['unit_name']}"
                       for team in specification['job']['teams']]
    result['original'] = {key: original.get(key) for key in
                          ['outcome', 'reason', 'wallSeconds', 'simulationSeconds',
                           'finalStateHash', 'eventLogHash', 'campaignHash']}
    if task['task'] == 'parity_control':
        current = result.get('result') or {}
        result['exactReplay'] = all(current.get(key) == original[key]
                                    for key in ['finalStateHash', 'eventLogHash'])
    atomic(result_path, result)
    return result


def export_report(output, state):
    rows = [read(path) for path in sorted((output / 'runs').glob('*/result.json'))]
    atomic(output / 'summary.json', rows)
    state['completedTasks'] = len(rows)
    state['updatedAt'] = now()
    atomic(output / 'state.json', state)
    lines = [
        '# Ranking timeout diagnostics', '',
        f"Status: **{state['status']}**. Completed {len(rows)}/{state.get('totalTasks', '?')} diagnostic tasks.", '',
        'The bulk campaign and its saved outcomes remain the source records. These are supplemental diagnostic reruns.', '',
        'Three controls must reproduce exact final-state and event hashes before any flagged run is investigated. ',
        'Runs execute one at a time after the bulk campaign stops. The nominal processing allowance is 120 seconds; ',
        'an external 130-second cutoff covers an unresponsive tick and profile flushing. ',
        'Game-time-cutoff cases have no practical game-time cap. Original processing-time-cutoff cases ',
        'first retain the original 150-game-second cap to make their timings interpretable. ',
        'Tracing and CPU profiling add overhead, and the original campaign used four workers. ',
        'A faster rerun alone does not prove a contention bug. Inactivity observations require inspection.', '',
        '| Task | Matchup / seed | Stop reason | Processing seconds | Last game seconds |',
        '|---|---|---|---:|---:|',
    ]
    for row in rows:
        progress = row.get('lastProgress') or {}
        game = (row.get('result') or {}).get('ticks')
        game = game / 60 if game is not None else progress.get('simulationSeconds')
        label = ' vs. '.join(row.get('teams', [row['matchupId']]))
        lines.append(f"| {row['task']} | {label} / seed {row['seed']} | {row['stopReason']} "
                     f"| {row.get('processingWallSeconds', 0):.2f} | {game if game is not None else 'unknown'} |")
    lines.extend(['', 'Per-run `result.json` includes CPU hotspots, tick timings, last unit states, and original provenance. ',
                  '`timeline.jsonl` records progress, positions, targets, HP, and event counts. ',
                  'Raw CPU profiles and the copied runtime remain local to keep Git checkpoints manageable.', ''])
    (output / 'README.md').write_text('\n'.join(lines))


def publish(output, state):
    paths = [str(output.relative_to(ROOT)), str(HERE.relative_to(ROOT)),
             'aoe2x/js_simulation/node/ranking-diagnostic-hooks.mjs',
             'aoe2x/js_simulation/node/ranking-diagnostic-job.mjs',
             'aoe2x/js_simulation/tests/ranking-diagnostic-hooks.test.mjs']
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=60)
    try:
        branch = 'simulations/v3-engine-ranking-pilot-2026-10-29'
        if git('branch', '--show-current').strip() != branch:
            raise RuntimeError('Unexpected publishing branch')
        if git('diff', '--cached', '--name-only').strip():
            raise RuntimeError('Existing staged changes; retain checkpoint locally')
        git('add', '--', *paths)
        if git('diff', '--cached', '--name-only').strip():
            git('commit', '-m', f"Checkpoint ranking timeout diagnostics: {state['completedTasks']} runs")
        git('push', 'origin', branch)
        state['lastPublishedAt'] = now()
        state['lastPublishError'] = None
    except Exception as error:
        state['lastPublishError'] = str(error)[-2000:]
    atomic(output / 'state.json', state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    campaign, output = args.campaign.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / '.gitignore').write_text('runtime/\n*.pid\n*.lock\n*.log\n*.tmp\n**/*.log\n**/*.cpuprofile\n')
    with (output / 'supervisor.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        (output / 'supervisor.pid').write_text(str(os.getpid()))
        state = read(output / 'state.json') if (output / 'state.json').exists() else {'createdAt': now()}
        state.update(status='waiting_for_bulk_completion', sourceCampaign=str(campaign.relative_to(ROOT)),
                     pid=os.getpid(), workers=1)
        export_report(output, state)
        while True:
            bulk_state = read(campaign / 'state.json')
            progress = read(campaign / 'progress.json')
            if bulk_state['status'] == 'complete' and progress['pendingRuns'] == 0 and not (campaign / '.runner.lock').exists():
                break
            if bulk_state['status'] == 'failed':
                raise RuntimeError('Bulk campaign failed; diagnostics must wait for its recovery')
            time.sleep(30)
        manifest = read(campaign / 'manifest.json')
        verify_runtime(manifest)
        plan_path = output / 'tasks.json'
        if plan_path.exists():
            frozen = read(plan_path)
            if frozen['campaignHash'] != manifest['campaignHash']:
                raise RuntimeError('Diagnostic source campaign changed')
            plan = frozen['tasks']
        else:
            plan = build_plan(manifest, records(campaign))
            atomic(plan_path, {'campaignHash': manifest['campaignHash'], 'createdAt': now(), 'tasks': plan})
        runtime = prepare_runtime(manifest, output)
        state.update(status='running', totalTasks=len(plan), startedAt=state.get('startedAt', now()))
        export_report(output, state)
        if args.publish:
            publish(output, state)
        for index, task in enumerate(plan):
            state['activeTask'] = {'task': task['task'], 'matchupId': task['original']['matchupId'],
                                   'seed': task['original']['seed']}
            atomic(output / 'state.json', state)
            result = run_one(task, manifest, runtime, output, 120)
            if task['task'] == 'parity_control' and not result.get('exactReplay'):
                state.update(status='failed', failure='Diagnostic instrumentation failed exact replay')
                export_report(output, state)
                if args.publish:
                    publish(output, state)
                raise RuntimeError(state['failure'])
            export_report(output, state)
            print(json.dumps({'completed': index + 1, 'total': len(plan),
                              'task': task['task'], 'stopReason': result['stopReason']}), flush=True)
            if args.publish and (index % 5 == 4 or task['task'] == 'extend_game_time'):
                publish(output, state)
        state.update(status='complete', completedAt=now(), activeTask=None)
        export_report(output, state)
        if args.publish:
            publish(output, state)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Make a failure visible to the next status check, including setup failures.
        import sys
        if '--output' in sys.argv:
            output_path = Path(sys.argv[sys.argv.index('--output') + 1]).resolve()
            state_path = output_path / 'state.json'
            if state_path.exists():
                failure_state = read(state_path)
                if failure_state.get('pid') == os.getpid():
                    failure_state.update(status='failed', failure=str(error), failedAt=now())
                    atomic(state_path, failure_state)
        raise
