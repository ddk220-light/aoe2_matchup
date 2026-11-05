#!/usr/bin/env python3
"""Read-only integrity checks for the portable Matchup Table v3 handoff."""
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / 'handoff/matchup-table-v3'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    status = read_json(HANDOFF / 'status.json')
    checksums = read_json(HANDOFF / 'files.sha256.json')
    for entry in checksums['files']:
        path = ROOT / entry['path']
        require(path.is_file(), f"Missing handoff file: {entry['path']}")
        require(path.stat().st_size == entry['bytes'], f"Size changed: {entry['path']}")
        require(sha256(path) == entry['sha256'], f"Hash changed: {entry['path']}")

    campaign = ROOT / status['validation']['campaignPath']
    manifest = read_json(campaign / 'manifest.json')
    require(manifest['campaignHash'] == status['validation']['campaignHash'], 'Wrong campaign')
    for entry in manifest['runtimeFiles'] + manifest['inputFiles']:
        require(sha256(ROOT / entry['path']) == entry['sha256'],
                f"Frozen input/runtime changed: {entry['path']}")

    journal = {}
    with (campaign / 'runs.jsonl').open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            key = (row['matchupId'], row['seed'])
            require(key not in journal, f'Duplicate seed: {key}')
            require(row['campaignHash'] == manifest['campaignHash'], f'Wrong seed campaign: {key}')
            journal[key] = row

    reviews = [read_json(path) for path in (campaign / 'pair-reviews').glob('*.json')]
    require(len(reviews) == status['validation']['reviewedContexts'], 'Review count changed')
    require(len(journal) == status['validation']['savedJournalRecords'], 'Journal count changed')
    reviewed_ids = {row['jobId'] for row in reviews}
    require(not reviewed_ids.intersection(status['validation']['blockedJobs']), 'Blocked context counted')
    for review in reviews:
        require(review['status'] == 'passed' and review['requiredSeeds'] == []
                and review['exactReplay']['exact'] is True, f"Incomplete review: {review['jobId']}")
        for seed in review['seedResults']:
            # Previously observed V3 sets retain their original source records;
            # fresh sets must have every measured seed in this campaign journal.
            if review['validationMode'] == 'fresh_seed_set':
                require((review['jobId'], seed['seed']) in journal,
                        f"Missing measured seed: {review['jobId']}:{seed['seed']}")

    snapshot = ROOT / status['validation']['latestCorrectionSnapshot']
    summary = read_json(snapshot / 'summary.json')
    for name, expected in read_json(snapshot / 'manifest.json')['files'].items():
        require(sha256(snapshot / name) == expected, f'Correction snapshot changed: {name}')
    with gzip.open(snapshot / 'reviewed-contexts.jsonl.gz', 'rt', encoding='utf-8') as source:
        exported_ids = {json.loads(line)['jobId'] for line in source if line.strip()}
    require(len(exported_ids) == summary['reviewedContexts'], 'Correction snapshot count changed')
    require(exported_ids <= reviewed_ids, 'Snapshot contains an unknown review')
    require(sha256(ROOT / 'data/golden/civ_matchups_first_pass.db')
            == status['website']['servingDatabaseSha256'], 'Serving database changed')
    require(read_json(ROOT / 'vercel.json').get('git', {}).get('deploymentEnabled', {})
            .get('matchup-table-v3') is False, 'Handoff branch deployment must remain disabled')
    print(json.dumps({
        'passed': True,
        'hashedFiles': len(checksums['files']),
        'savedJournalRecords': len(journal),
        'reviewedContexts': len(reviews),
        'remainingContexts': status['validation']['remainingContexts'],
        'exportedCorrectionContexts': summary['reviewedContexts'],
        'productionModified': False,
        'simulationStarted': False,
    }, indent=2))


if __name__ == '__main__':
    main()
