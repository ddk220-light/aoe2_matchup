"""Activate frozen Donut plans only after all five matching Arena trials verify.

This changes queue membership, never the already frozen counts or scenarios.
The decision and manifest update are idempotent so interrupted publication can
resume without recapturing any verified game.
"""
from pathlib import Path

from run_champi_comparison_capture import read, save


def activate_conditional_donut(queue, campaign, queue_root):
    rule = campaign.get('conditionalDonut')
    if not rule or not rule.get('pending'):
        return False
    work = Path(campaign['workDirectory'])
    manifest = read(work / 'manifest.json')
    status = read(work / 'capture/status.json')
    verified = {r['jobId']: r for r in status['results'] if r['status'] == 'verified'}
    deferred = read(work / rule['manifest'])['matchups']
    # The ranged army can be the opponent (Slinger in P3 on Arena). Donut still
    # assigns it P2. Selection follows that army, not the subject's filename.
    ranged_owner = rule.get('rangedOwner', 2)
    if ranged_owner not in (2, 3):
        raise ValueError('Conditional Donut requires ranged owner P2 or P3')
    decisions, additions = [], []
    for oi in sorted({r['opponentIndex'] for r in deferred}):
        arena = [r for r in manifest['matchups'] if r['layout'] == 'Arena' and r['opponentIndex'] == oi]
        if len(arena) != 5 or {r['iteration'] for r in arena} != set(range(1, 6)):
            raise ValueError('Conditional Donut needs exactly five Arena iterations')
        losses = 0
        for item in arena:
            if item['id'] not in verified:
                raise ValueError('Conditional Donut needs every Arena trial verified')
            if item.get('rangedOwner', item['subjectOwner']) != ranged_owner:
                raise ValueError('Arena ranged ownership disagrees with the frozen selection rule')
            capture = read(Path(verified[item['id']]['runDirectory']) / 'manifest.json')['capture']
            losses += capture['winnerOwner'] == 5 - ranged_owner
        selected = losses >= rule.get('minimumLosses', 3)
        reason = f'Ranged army lost {losses}/5 Arena trials; conditional Donut={selected}'
        decisions.append(dict(opponentIndex=oi, rangedOwnerOnArena=ranged_owner,
            rangedLosses=losses, trials=5, runDonut=selected, reason=reason))
        if selected:
            additions.extend({**r, 'selectionReason': reason} for r in deferred if r['opponentIndex'] == oi)
    decision_path = work / 'conditional-donut-decision.json'
    save(decision_path, dict(state='COMPLETE', comparisons=decisions, addedTrials=len(additions)))
    old_ids = {r['id'] for r in manifest['matchups']}
    manifest['matchups'].extend(r for r in additions if r['id'] not in old_ids)
    save(work / 'manifest.json', manifest)
    campaign['total'] = len(manifest['matchups'])
    rule.update(pending=False, decision=decision_path.name, addedTrials=len(additions))
    queue['total'] = sum(c['total'] for c in queue['campaigns'])
    save(Path(queue_root) / 'queue.json', queue)
    return bool(additions)
