"""Offline action framing for the clean, fixed-camera Golden battle recordings.

The camera affects gameplay only; stat panels and HP queues are composed later.
Framing uses recorded living-unit positions when requested, otherwise vision.
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path

import cv2
import numpy as np


def action_box(frame, previous=None):
    """Return sprite bounds in source pixels, excluding the game's HUD bands."""
    small = cv2.resize(frame, (0, 0), fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    # Golden uses blue/red armies and an orange P4 screen. Saturation rejects
    # most sand and vegetation; motion rejects settled corpses and terrain.
    blue = (h >= 98) & (h <= 133) & (s > 100) & (v > 65)
    red = ((h < 9) | (h > 173)) & (s > 145) & (v > 85)
    orange = (h >= 9) & (h <= 23) & (s > 180) & (v > 100)
    colors = blue | red | orange
    colors[:70] = False
    colors[-55:] = False
    colors[:, :50] = False
    colors[:, -50:] = False
    if previous is not None:
        old = cv2.resize(previous, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA)
        motion = (np.max(cv2.absdiff(small, old), axis=2) > 24).astype('uint8')
        motion = cv2.dilate(motion, np.ones((5, 5), dtype='uint8'))
        colors &= motion.astype(bool)
    mask = cv2.dilate(colors.astype('uint8'), np.ones((5, 5), dtype='uint8'))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes = []
    for label in range(1, count):
        x, y, w, height, area = stats[label]
        if area < 32 or int(colors[y:y+height, x:x+w].sum()) < 5:
            continue
        boxes.append((x * 2, y * 2, (x + w) * 2, (y + height) * 2))
    if not boxes:
        return None
    return [int(min(b[0] for b in boxes)), int(min(b[1] for b in boxes)),
            int(max(b[2] for b in boxes)), int(max(b[3] for b in boxes))]


def plan_camera(boxes, times, width, height, min_size=760, margin=100,
                engagement_time=None):
    """Hold until contact, then smoothly tighten without chasing stragglers.

    Horizontal framing follows the main fight, not the final survivor. A
    future-bound envelope permits progressive zoom without any zoom-out.
    """
    bounds = []
    last = [width/2-620, 160, width/2+620, height-160]
    for box in boxes:
        if box is not None:
            last = box
        bounds.append(last)
    bounds = np.asarray(bounds, dtype=float)
    timeline = np.asarray(times)
    # Brief scene motion/particles can produce distant color hits. Require
    # temporal support before allowing those hits to drive a large zoom-out.
    bounds = np.asarray([np.median(bounds[np.abs(timeline-t) <= 1], axis=0)
                         for t in timeline])
    expanded = bounds + np.array([-margin, -margin, margin, margin])
    first = expanded[0]
    tail = expanded[timeline >= timeline[-1] - min(2, (timeline[-1]-timeline[0])/4)]
    last_box = np.median(tail, axis=0)
    first_center = (first[:2] + first[2:]) / 2
    last_center = (last_box[:2] + last_box[2:]) / 2
    first_size = min(width, max(min_size, np.max(first[2:]-first[:2])))
    last_size = min(first_size, max(min_size, np.max(last_box[2:]-last_box[:2])))
    contact = timeline[0] if engagement_time is None else engagement_time
    fighting = expanded[timeline >= contact]
    if len(fighting):
        fight_x = np.median((fighting[:, 0]+fighting[:, 2])/2)
        last_center[0] = first_center[0] + np.clip(fight_x-first_center[0], -40, 40)
    # Clamp center endpoints once; do not introduce per-frame pan corrections.
    for center, size in ((first_center, first_size), (last_center, last_size)):
        center[0] = np.clip(center[0], size/2, width-size/2)
        center[1] = np.clip(center[1], size/2, height-size/2) if size <= height else height/2
    duration = max(.001, float(timeline[-1]-contact))
    progress = np.clip((timeline-contact) / (duration*.9), 0, 1)
    ease = progress**3 * (10 - 15*progress + 6*progress**2)
    centers = first_center + ease[:, None]*(last_center-first_center)
    # Fit each stage of the fight. A wide mid-fight formation must not lock
    # the entire remaining clip to a nearly unchanged establishing shot.
    needed = 2*np.max(np.abs(expanded.reshape(-1, 2, 2)-centers[:, None, :]), axis=(1, 2))
    targets = np.clip(np.maximum.accumulate(needed[::-1])[::-1], min_size, first_size)
    # Three causal smoothing stages soften both acceleration and braking.
    # Their input is non-increasing, so they cannot create a zoom reversal.
    stages = [first_size]*3
    sizes = []
    for i, t in enumerate(timeline):
        dt = 0 if i == 0 else float(t-timeline[i-1])
        alpha = 1-np.exp(-dt/.8)
        target = first_size if t <= contact else targets[i]
        for stage in range(3):
            stages[stage] += alpha*(target-stages[stage])
            target = stages[stage]
        sizes.append(stages[-1])
    return [{'time': float(t), 'x': float(c[0]-s/2), 'y': float(c[1]-s/2),
             'size': float(s)} for t, c, s in zip(timeline, centers, sizes)]


def first_combat_time(rows):
    initial = {owner: sum(u['hp'] for u in units)
               for owner, units in rows[0]['sides'].items()}
    return next((row['videoSeconds'] for row in rows
                 if any(sum(u['hp'] for u in row['sides'][owner]) < hp
                        for owner, hp in initial.items())), None)


def reframe_enhanced(enhanced, old_crop, new_crop, clean):
    """Reuse enhanced pixels in world coordinates; uncovered terrain stays raw."""
    old_x, old_y, old_size = old_crop
    new_x, new_y, new_size = new_crop
    output_size = clean.shape[0]
    scale = old_size/new_size * output_size/enhanced.shape[0]
    transform = np.float32([[scale, 0, (old_x-new_x)*output_size/new_size],
                            [0, scale, (old_y-new_y)*output_size/new_size]])
    return cv2.warpAffine(enhanced, transform, (output_size, output_size),
                          dst=clean.copy(), flags=cv2.INTER_LANCZOS4,
                          borderMode=cv2.BORDER_TRANSPARENT)


class BattleCamera:
    def __init__(self, keyframes):
        self.keyframes = keyframes
        self.times = [k['time'] for k in keyframes]

    def at(self, seconds):
        i = max(0, bisect.bisect_right(self.times, seconds)-1)
        a = self.keyframes[i]
        b = self.keyframes[min(i+1, len(self.keyframes)-1)]
        ratio = np.clip((seconds-a['time'])/max(1e-9, b['time']-a['time']), 0, 1)
        return tuple(float(a[k]+(b[k]-a[k])*ratio) for k in ('x', 'y', 'size'))

    def crop(self, frame, seconds, output_size=1080):
        x, y, size = self.at(seconds)
        scale = output_size / size
        transform = np.array([[scale, 0, -x*scale], [0, scale, -y*scale]], dtype=np.float32)
        return cv2.warpAffine(frame, transform, (output_size, output_size),
                              flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(20, 22, 24))


def calibrate_projection(rows, evidence):
    """Match unique HP fractions to recorded coordinates; fit screen projection.

    Existing alignment evidence supplies bar top-lefts. A common offset to
    sprite centers is sufficient for framing; the outer margin covers height.
    """
    from overlay.unit_timeline import sample_at
    times = [r['videoSeconds'] for r in rows]
    world, pixels = [], []
    for observation in evidence:
        row = sample_at(rows, times, observation['videoSeconds'])
        for bar in observation['bars']:
            candidates = [u for u in row['sides'][bar['owner']]
                          if u['hp'] > 0 and u.get('x') is not None
                          and abs(u['hp']/u['maxHp']-bar['fraction']) < .012]
            if len(candidates) == 1:
                unit = candidates[0]
                world.append([unit['x'], unit['y']])
                pixels.append([bar['x']+34, bar['y']+60])
    if len(world) < 6:
        raise ValueError('Telemetry camera needs six unique HP-position calibration matches')
    matrix, inliers = cv2.estimateAffine2D(np.float32(world), np.float32(pixels),
                                         ransacReprojThreshold=12)
    if matrix is None or int(inliers.sum()) < 6:
        raise ValueError('Could not calibrate telemetry to this recording')
    errors = np.linalg.norm(np.c_[world, np.ones(len(world))] @ matrix.T-pixels, axis=1)
    return matrix, {'matches': len(world), 'inliers': int(inliers.sum()),
                    'medianErrorPixels': float(np.median(errors[inliers.ravel() > 0]))}


def position_bounds(units, matrix):
    points = np.array([[u['x'], u['y'], 1] for u in units]) @ matrix.T
    return [float(points[:, 0].min()), float(points[:, 1].min()),
            float(points[:, 0].max()), float(points[:, 1].max())]


def analyze(video, output, start, duration, telemetry_run=None):
    capture = cv2.VideoCapture(str(video))
    fps = capture.get(cv2.CAP_PROP_FPS)
    width, height = int(capture.get(3)), int(capture.get(4))
    stride = max(1, round(fps / 10))
    last_frame = min(int(capture.get(7)), int(np.ceil((start+duration)*fps))+1)
    boxes, times, previous = [], [], None
    calibration = None
    engagement_time = None
    if telemetry_run:
        from overlay.unit_timeline import decode, sample_at
        data = decode(telemetry_run, include_combat=True, include_positions=True)
        engagement_time = first_combat_time(data['rows'])
        matrix, quality = calibrate_projection(data['rows'], data['mapping']['alignment']['evidence'])
        row_times = [r['videoSeconds'] for r in data['rows']]
        for t in np.arange(start, start+duration+.0001, .1):
            units = sample_at(data['rows'], row_times, t)['positions']
            boxes.append(position_bounds(units, matrix) if units else None)
            times.append(float(t))
        calibration = {'matrix': matrix.tolist(), **quality, 'sourceFrames': data['sourceFrames'],
                       'sourceSha256': data['sourceSha256'], 'owners': [2, 3, 4]}
    else:
        for frame_number in range(last_frame):
            if not capture.grab():
                break
            if frame_number % stride:
                continue
            ok, frame = capture.retrieve()
            if not ok:
                break
            boxes.append(action_box(frame, previous))
            times.append(frame_number / fps)
            previous = frame
    capture.release()
    keys = plan_camera(boxes, times, width, height, engagement_time=engagement_time)
    document = {'source': str(Path(video).resolve()), 'sourceSize': [width, height],
                'method': 'Living telemetry positions' if telemetry_run else 'Blue/red/orange sprite colors plus local motion',
                'motion': 'Hold until contact; horizontal travel capped at 40 px; smooth vertical pan and progressive zoom-in only',
                'engagementTime': engagement_time,
                'calibration': calibration,
                'timeBasis': 'untrimmed battle.mp4 seconds', 'minimumCropSize': 760,
                'marginPixels': 100, 'keyframes': keys,
                'observations': [{'time': t, 'bounds': b} for t, b in zip(times, boxes)]}
    Path(output).write_text(json.dumps(document, indent=2))
    return BattleCamera(keys)
