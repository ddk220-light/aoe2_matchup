"""Decode archived per-entity state without altering the recorder or raw bundle."""
from __future__ import annotations

import bisect
import json
import struct
import sys
import tempfile
from pathlib import Path

from overlay.static_stats import REPO

sys.path.insert(0, str(REPO / 'aoe2x/grpc'))
import cade_api_pb2 as pb
import decode_state_v2 as D
from redecode_hp import SNAP_RESEED, derive_army, refresh_army_membership


def sample_at(rows, times, video_s):
    """Hold the last observed state; never anticipate damage or interpolate deaths."""
    return rows[max(0, bisect.bisect_right(times, video_s) - 1)]


def ordered_units(units):
    """Stable entity order within survivors, then dimmed casualties."""
    return sorted(units, key=lambda u: (u['hp'] <= 0, u['id']))


def decode(run):
    run = Path(run)
    recording = json.loads((run / 'recording.json').read_text())
    source = run / recording['files']['frames']['path']
    expected = tuple(recording['sides'][s]['count'] for s in ('side1', 'side2'))
    segments, rows = [], []
    es = None
    last_ms = None
    identities, kills, maxima = {}, {}, {}
    frame_count = 0
    kill_events = 0
    trailing_partial_bytes = 0
    with tempfile.TemporaryDirectory(prefix='aoe2-unit-decode-') as temporary:
        snapshot = Path(temporary) / 'snapshot.bin'
        with source.open('rb') as stream:
            while header := stream.read(4):
                if len(header) != 4:
                    trailing_partial_bytes = len(header)
                    break
                size = struct.unpack('<I', header)[0]
                payload = stream.read(size)
                if len(payload) != size:
                    trailing_partial_bytes = len(payload) + 4
                    break
                sequence = pb.FrameSequence.FromString(payload)
                for frame in sequence.frame:
                    frame_count += 1
                    if frame.patch and len(frame.patch) > SNAP_RESEED:
                        if rows:
                            segments.append(rows)
                        rows, identities, kills, maxima = [], {}, {}, {}
                        snapshot.write_bytes(frame.patch)
                        doc, es = D.Doc(), {}
                        _, world = D.seed_from_snapshot(str(snapshot), doc, es)
                        army = derive_army(es)
                        last_ms = None
                        continue
                    if es is None:
                        continue
                    if last_ms is not None and frame.time < last_ms - 2000:
                        if rows:
                            segments.append(rows)
                        rows, es = [], None
                        continue
                    last_ms = frame.time
                    if frame.patch:
                        D.apply_patch(doc, frame.patch, es, world)
                        refresh_army_membership(es, army)
                    for event in frame.event:
                        if event.HasField('entityKilled'):
                            killed = event.entityKilled
                            kill_events += 1
                            kills[killed.killerId] = kills.get(killed.killerId, 0) + 1
                            es.pop(killed.id, None)
                    sides = {}
                    for owner in (2, 3):
                        units = []
                        for entity_id in sorted(army[owner]):
                            entity = es.get(entity_id, {})
                            hp = max(0.0, float(entity.get(12, 0)))
                            if entity_id not in identities:
                                identities[entity_id] = (entity.get(1), hp)
                            master, initial_hp = identities[entity_id]
                            # Own-master HP includes per-entity growth effects. The
                            # entity store holds scalar fields; child models live in Doc.
                            entity_model_id = doc.models[world].get(1, {}).get(entity_id)
                            entity_model = doc.models.get(entity_model_id, {})
                            own_master = doc.models.get(entity_model.get(14), {})
                            observed_max = own_master.get(5)
                            if isinstance(observed_max, (int, float)) and observed_max >= hp and observed_max > 0:
                                maxima[entity_id] = float(observed_max)
                            max_hp = maxima.get(entity_id, initial_hp)
                            units.append({'id': entity_id, 'masterId': master,
                                          'hp': hp, 'maxHp': max_hp,
                                          'maxHpObserved': entity_id in maxima})
                        sides[str(owner)] = units
                    row = {'gameMs': frame.time, 'sides': sides}
                    if rows and rows[-1]['gameMs'] == frame.time:
                        rows[-1] = row
                    else:
                        rows.append(row)
    if rows:
        segments.append(rows)
    plausible = [s for s in segments if tuple(sum(u['hp'] > 0 for u in s[0]['sides'][o]) for o in ('2', '3')) == expected]
    if not plausible:
        raise ValueError(f'No stream segment matches scenario counts {expected}')
    fights = [s for s in plausible if any(sum(u['hp'] > 0 for u in s[-1]['sides'][o]) < expected[i] for i, o in enumerate(('2', '3')))]
    rows = (fights or plausible)[-1]
    speed = recording['clock']['gameSpeed']
    offset = recording['clock']['videoGameStartSeconds'] - recording['presentation']['startRawSeconds']
    alignment_path = run / 'unit-hp-overlay' / 'alignment.json'
    alignment = json.loads(alignment_path.read_text()) if alignment_path.exists() else None
    if alignment:
        if alignment['videoSha256'] != recording['files']['battleVideo']['sha256']:
            raise ValueError('Alignment belongs to different footage')
        speed = alignment['gameSpeed']
        offset = alignment['videoOffsetSeconds']
    for row in rows:
        row['videoSeconds'] = row['gameMs'] / 1000 / speed + offset
    return {'schemaVersion': 1, 'sourceFrames': str(source),
            'sourceSha256': recording['files']['frames']['sha256'],
            'mapping': {'gameSpeed': speed, 'videoOffsetSeconds': offset,
                        'formula': 'videoSeconds = gameMs / 1000 / gameSpeed + videoOffsetSeconds',
                        'alignment': alignment,
                        'precision': 'Game timestamps preserved; video alignment measured from visible HP transitions.' if alignment else 'Unverified legacy wall-clock estimate.'},
            'trailingPartialBytes': trailing_partial_bytes, 'decodedFrames': frame_count, 'segments': len(segments), 'killEvents': kill_events,
            'maxHpSource': 'Per-entity own-master HP where present; initial HP fallback explicitly marked per unit.',
            'rows': rows}


if __name__ == '__main__':
    run = Path(sys.argv[1]).resolve()
    out = run / 'unit-hp-overlay'
    out.mkdir(exist_ok=True)
    data = decode(run)
    (out / 'units.json').write_text(json.dumps(data, separators=(',', ':')))
    print(json.dumps({k: v for k, v in data.items() if k != 'rows'}, indent=2))
    print('rows', len(data['rows']))
    for row in (data['rows'][0], data['rows'][-1]):
        print(row['videoSeconds'], {o: (len(us), sum(u['hp'] > 0 for u in us), sum(u['hp'] for u in us)) for o, us in row['sides'].items()})
