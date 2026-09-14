"""Validate explicitly reviewed death-event timing when HP bars are obscured.

This is an offline recovery path, not an automatic approval of guessed anchors.
The review document names real before/after video frames and the corresponding
archived main-army death transitions. Ordinary HP fits retain their own gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from overlay.unit_timeline import decode


def fit(anchors):
    if len(anchors) < 3 or len({a['gameSeconds'] for a in anchors}) != len(anchors):
        raise ValueError('Need at least three distinct reviewed events')
    if max(a['gameSeconds'] for a in anchors) - min(a['gameSeconds'] for a in anchors) < 4:
        raise ValueError('Events need enough time separation to identify game speed')
    for a in anchors:
        if not 0 < a['videoMaxSeconds'] - a['videoMinSeconds'] <= .1:
            raise ValueError('Review event brackets within 100 milliseconds')
    fits = []
    for speed in (1.7, 2.0):
        low = max(a['videoMinSeconds'] - a['gameSeconds'] / speed for a in anchors)
        high = min(a['videoMaxSeconds'] - a['gameSeconds'] / speed for a in anchors)
        if low <= high:
            fits.append((speed, low, high))
    if len(fits) != 1:
        raise ValueError('Reviewed events do not identify one consistent game speed')
    speed, low, high = fits[0]
    return speed, (low + high) / 2, [low, high]


def verify(run, review_path):
    run, review_path = Path(run), Path(review_path)
    review = json.loads(review_path.read_text())
    recording = json.loads((run / 'recording.json').read_text())
    for key, file_key in [('videoSha256', 'battleVideo'), ('framesSha256', 'frames')]:
        path = run / recording['files'][file_key]['path']
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if review.get(key) != actual or actual != recording['files'][file_key]['sha256']:
            raise ValueError('Reviewed evidence belongs to different media: ' + key)
    if not review.get('reviewedBy') or not review.get('evidence'):
        raise ValueError('A real visual review and saved evidence are required')
    for item in review['evidence']:
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Review image changed')
    rows = decode(run)['rows']
    for anchor in review['anchors']:
        owner = str(anchor['owner'])
        found = False
        for previous, current in zip(rows, rows[1:]):
            before = sum(u['hp'] > 0 for u in previous['sides'][owner])
            after = sum(u['hp'] > 0 for u in current['sides'][owner])
            if current['gameMs'] == round(anchor['gameSeconds'] * 1000):
                found = before == anchor['aliveBefore'] and after == anchor['aliveAfter'] and after < before
                break
        if not found:
            raise ValueError('Reviewed event does not match an archived death transition')
    speed, offset, interval = fit(review['anchors'])
    result = dict(videoSha256=review['videoSha256'], framesSha256=review['framesSha256'],
                  gameSpeed=speed, videoOffsetSeconds=offset,
                  method='manually reviewed visible death transitions matched to archived unit deaths',
                  verifiedBy=review['reviewedBy'], eventAnchors=review,
                  quality=dict(eventCount=len(review['anchors']), offsetIntervalSeconds=interval,
                               maximumTimingUncertaintySeconds=(interval[1] - interval[0]) / 2))
    destination = run / 'unit-hp-overlay/alignment.json'
    if destination.exists():
        raise ValueError('Preserve the existing alignment; review disagreement separately')
    destination.write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    p.add_argument('--review', type=Path, required=True)
    a = p.parse_args()
    result = verify(a.run, a.review)
    print(json.dumps({k: v for k, v in result.items() if k != 'eventAnchors'}, indent=2))
