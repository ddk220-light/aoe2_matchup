"""Recover an ended mutual-elimination capture without replaying the game.

The live decoder deliberately waits for a stable zero army. A game-end dialog
can freeze the simulation clock before that grace period expires. Recovery
requires independent video evidence and the full-resolution terminal stream;
the spectator's victory text is never used to choose an army winner.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from .io import sha256, utc_now, write_json
from .errors import LiveCaptureError


def mutual_elimination_evidence(timeline: dict, expected: tuple[int, int]) -> dict:
    rows = timeline['rows']
    if not rows:
        raise LiveCaptureError('Recovery stream has no rows')
    counts = lambda r: tuple(sum(u['hp'] > 0 for u in r['sides'][o]) for o in ('2', '3'))
    if counts(rows[0]) != expected or min(expected) < 2:
        raise LiveCaptureError('Recovery stream does not match planned starting armies')
    if counts(rows[-1]) != (0, 0):
        raise LiveCaptureError('Recovery requires observed mutual elimination')
    start = len(rows) - 1
    while start > 0 and counts(rows[start - 1]) == (0, 0):
        start -= 1
    # Several independent patches must confirm the final state. This is not a
    # replacement for the visual game-end check (spawn-on-death units exist).
    stable_ms = rows[-1]['gameMs'] - rows[start]['gameMs']
    if len(rows) - start < 3 or stable_ms < 250:
        raise LiveCaptureError('Insufficient terminal telemetry for recovery')
    return dict(outcome='mutual_elimination', winnerOwner=None,
                terminalGameMs=rows[start]['gameMs'], finalGameMs=rows[-1]['gameMs'],
                stableZeroGameMs=stable_ms, terminalObservations=len(rows)-start,
                startCounts=list(expected), finalCounts=[0, 0], finalHp=[0, 0])


def recover_mutual_elimination(run_directory: Path, plan: dict) -> dict:
    """Create a labeled recovery receipt; retain the original sidecar as evidence.

    Called only when the raw video/frames/metadata/sidecar exist and END does
    not. Originals are not relabeled as live-verified. No wall-clock completion
    timestamp is invented, so downstream video alignment still has to be measured.
    """
    import cv2
    from PIL import Image
    from auto.vision import detect_end
    from overlay.unit_timeline import decode

    from .capture_paths import capture_prefix
    prefix = capture_prefix(run_directory, plan['matchupId'])
    video, frames = prefix.with_suffix('.mov'), Path(f'{prefix}.frames.bin')
    hp_path, end_path = Path(f'{prefix}.hp.json'), Path(f'{prefix}.END')
    if end_path.exists():
        raise LiveCaptureError('Refusing to overwrite an existing END marker')
    hp = json.loads(hp_path.read_text(encoding='utf-8'))
    speed = hp.get('game_speed')
    if not isinstance(speed, (float, int)) or speed <= 0:
        raise LiveCaptureError('Missing stream/video game speed')
    expected = (plan['side2']['count'], plan['side3']['count'])
    frames_hash = sha256(frames)
    with tempfile.TemporaryDirectory(prefix='aoe2-recovery-') as temporary:
        root = Path(temporary)
        write_json(root / 'recording.json', {
            'sides': {'side1': {'count': expected[0]}, 'side2': {'count': expected[1]}},
            'files': {'frames': {'path': str(frames.resolve()), 'sha256': frames_hash}},
            'clock': {'gameSpeed': speed, 'videoGameStartSeconds': hp['video_game_start_s']},
            'presentation': {'startRawSeconds': 0},
        })
        timeline = decode(root)
    evidence = mutual_elimination_evidence(timeline, expected)
    cap = cv2.VideoCapture(str(video))
    try:
        fps, count = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps <= 0 or count < fps * 3:
            raise LiveCaptureError('Recovery video is not readable')
        observations = []
        for seconds_before_end in (2.0, .5):
            frame_index = round(count - fps * seconds_before_end)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, bgr = cap.read()
            if not ok or not detect_end(Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))):
                raise LiveCaptureError('Video does not independently confirm an ended game')
            observations.append(frame_index / fps)
    finally:
        cap.release()
    evidence.update(schemaVersion=1, method='offline_mutual_elimination_and_game_end_video_v1',
                    recoveredAt=utc_now(), liveMarker=False, framesSha256=frames_hash,
                    videoSha256=sha256(video), gameEndScreenVideoSeconds=observations,
                    trailingPartialBytes=timeline['trailingPartialBytes'])
    backup = hp_path.with_suffix('.pre-recovery.json')
    if backup.exists():
        raise LiveCaptureError('Recovery backup already exists; inspect before retrying')
    backup.write_bytes(hp_path.read_bytes())
    # The old one-second sampler misses deaths in the final fractional second.
    # Rebuild from every decoded patch, preserving the sidecar's video-clock contract.
    hp['rows'] = [dict(game_s=r['gameMs']/1000/speed, **{
        f'side{i}': {'count': sum(u['hp'] > 0 for u in r['sides'][owner]),
                    'hp': sum(u['hp'] for u in r['sides'][owner])}
        for i, owner in ((1, '2'), (2, '3'))}) for r in timeline['rows']]
    hp['recovery'] = evidence
    write_json(hp_path, hp)
    write_json(end_path, dict(end_stream_s=evidence['terminalGameMs']/1000,
                              side1=0, side2=0, winner=None, recovery=evidence))
    write_json(run_directory / 'capture-recovery.json', evidence)
    return evidence
