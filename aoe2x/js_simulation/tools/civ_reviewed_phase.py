"""Read a phase's evidence only after its review and source checks succeed."""
import gzip
import hashlib
import json


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_reviewed_phase(campaign, phase, inference=None):
    root = inference or campaign / 'latest-inference'
    adaptive = campaign / 'adaptive'
    phase_id = f'{phase:03d}'
    review_path = adaptive / 'phases' / f'{phase_id}-review.json'
    state = json.loads((adaptive / 'state.json').read_bytes())
    if phase_id not in state['completedPhases'] or not review_path.is_file():
        raise ValueError(f'phase {phase_id} has no completed review; validation is pending')
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    if review['status'] not in ('passed', 'complete_with_blocked'):
        raise ValueError(f'phase {phase_id} review did not pass integrity checks')
    manifest_bytes = (root / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest['buildHash'] != review['inferenceHash']:
        raise ValueError('inference snapshot does not match the requested phase review')
    outputs = {entry['file']: entry for entry in manifest['outputs']}
    source_bytes = (root / 'profile-matchups.jsonl.gz').read_bytes()
    variant_bytes = (root / 'variant-profiles.json').read_bytes()
    for name, data in (('profile-matchups.jsonl.gz', source_bytes),
                       ('variant-profiles.json', variant_bytes)):
        if digest(data) != outputs[name]['sha256']:
            raise ValueError(f'{name} does not match the reviewed manifest hash')
    rows = [json.loads(line) for line in gzip.decompress(source_bytes).splitlines()]
    by_key = {row['pairKey']: row for row in rows}
    if len(by_key) != len(rows) or len(rows) != outputs['profile-matchups.jsonl.gz']['rows']:
        raise ValueError('duplicate or missing profile-pair rows in reviewed snapshot')
    plan_bytes = (adaptive / 'phases' / f'{phase_id}.json').read_bytes()
    planned = json.loads(plan_bytes)['pairKeys']
    blocked = set(review['blockedPairs'])
    if (len(set(planned)) != len(planned) or review['pairs'] != len(planned)
            or not blocked.issubset(planned)):
        raise ValueError('phase plan and review pair coverage disagree')
    if review['status'] == 'passed' and (blocked or review['missingSeeds']):
        raise ValueError('passed phase still contains blocked pairs or missing seeds')
    selected = []
    for key in planned:
        row = by_key.get(key)
        if row is None:
            raise ValueError(f'missing planned pair: {key}')
        if key in blocked:
            if row['outcome'] != 'unresolved':
                raise ValueError('blocked pair has been classified as a completed result')
            continue
        if (row['evidenceType'] != 'observed'
                or row['outcome'] not in ('a_win', 'b_win', 'close_uncertain')):
            raise ValueError(f'planned pair has no completed observed seed set: {key}')
        selected.append(row)
    # Do not accept a snapshot replaced by the live runner during this read.
    if (root / 'manifest.json').read_bytes() != manifest_bytes:
        raise ValueError('inference snapshot changed during validation; retry after review')
    return selected, json.loads(variant_bytes), {
        'phaseReview': digest(review_bytes), 'phasePlan': digest(plan_bytes),
        'inferenceManifest': digest(manifest_bytes), 'inferenceBuildHash': manifest['buildHash'],
        'profileMatchups': digest(source_bytes), 'variantProfiles': digest(variant_bytes),
        'plannedPairs': len(planned), 'observedPairs': len(selected),
        'blockedPairs': sorted(blocked), 'missingSeeds': review['missingSeeds']}
