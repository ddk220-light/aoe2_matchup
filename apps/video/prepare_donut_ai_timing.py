"""Copy an audited Donut with its embedded kiting AI given installed firing windows.

The Donut AI's per-type fire window comes from the legacy frame_delay / 60
table. For units whose real windup is longer (Bolas Rider: 760 ms release vs a
377 ms window), the AI walks them away mid-throw and they barely attack. This
writes a NEW template (never touches the source) whose embedded AI is patched
with donut_ai_timing.protect_volley, plus an audit and a one-civ civ-themes
JSON for prepare_spike_matchups.py --donut-themes.

    python apps/video/prepare_donut_ai_timing.py --units bolas --civ Mapuche \
        --source "data/local/themed-donuts/araucania/Araucania Highlands Donut.aoe2scenario" \
        --out data/local/bolas-donut-timing
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path

from aoe2x.lab.io import sha256
from prepare_jomsviking_capture import DAT
from prepare_norse_standard_capture import load_scenario
from functools import partial

from donut_ai_timing import (add_discovery, bolas_timing, cap_volley, hold_volley, min_retreat, protect_volley,
                             threat_gate, unique_timing, war_wagon_timing)

ROOT = Path(__file__).resolve().parents[2]
# key: (timing function, new AI name, extra discovery (master, after-master) pairs)
UNITS = {'bolas': (bolas_timing, 'ddkDonutBolasTiming', ()),
         'war-wagon': (war_wagon_timing, 'ddkDonutWarWagonTiming', ()),
         'arambai': (partial(unique_timing, key='arambai'), 'ddkDonutArambaiTiming', ()),
         'gbeto': (partial(unique_timing, key='gbeto'), 'ddkDonutGbetoTiming', ()),
         'guecha': (partial(unique_timing, key='guecha'), 'ddkDonutGuechaTiming', ()),
         'jarl': (partial(unique_timing, key='jarl'), 'ddkDonutJarlTiming', ((2708, 2709),)),
         'mameluke': (partial(unique_timing, key='mameluke'), 'ddkDonutMamelukeTiming', ()),
         'chakram': (partial(unique_timing, key='chakram'), 'ddkDonutChakramTiming', ((1741, 2709), (1743, 2709)))}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def main() -> None:
    from aoe2x.lab.live import _camera_configuration, _player_runtime_configuration, _trigger_structure
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--units', choices=sorted(UNITS), help='unit firing-window fix (optional)')
    ap.add_argument('--min-retreat-ms', type=int, help='minimum kite retreat before turning to fire')
    ap.add_argument('--cap-volley', action='store_true', help='one shot per volley (fast-reload units)')
    ap.add_argument('--cap-margin-ms', type=int, default=100, help='end the volley this long before reload')
    ap.add_argument('--cap-after-fire-ms', type=int, help='also end the volley this long after the fire window')
    ap.add_argument('--hold-volley-ms', type=int, help='stand and fire at least this long before retreating')
    ap.add_argument('--threat-gate', type=int, help='keep firing until an enemy is this close (100 = 1 tile)')
    ap.add_argument('--name', help='AI name (required with any behaviour patch; fresh per variant)')
    ap.add_argument('--civ', required=True, help='civ key for the civ-themes JSON')
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    source = args.source if args.source.is_absolute() else ROOT / args.source
    out = args.out if args.out.is_absolute() else ROOT / args.out
    audit_in = json.loads(source.with_suffix('.audit.json').read_text(encoding='utf-8'))
    if audit_in.get('state') != 'PASSED' or audit_in.get('templateSha256') != sha256(source):
        raise SystemExit('Source Donut is not an audited, unchanged template')
    behaviour = args.min_retreat_ms or args.cap_volley or args.hold_volley_ms or args.threat_gate
    if not (args.units or behaviour):
        raise SystemExit('Nothing to patch: give --units and/or a behaviour patch')
    timing_fn, name, discovery = UNITS[args.units] if args.units else (None, None, ())
    timings = timing_fn(DAT) if timing_fn else []
    if behaviour:
        if not args.name:
            raise SystemExit('Behaviour patches need a fresh --name (the game caches AIs by name)')
        name = args.name

    s = load_scenario(source)
    pd = s.sections['PlayerDataTwo']
    embedded = pd.retriever_map['ai_files'].data[1].retriever_map['ai_per_file_text']
    old_name = pd.ai_names[1].replace('.ai', '.per')
    if old_name != audit_in.get('aiName', '') + '.per':
        raise SystemExit(f'Unexpected embedded AI {old_name}')
    ai = embedded.data
    for master, after in discovery:
        ai = add_discovery(ai, master, after)
    if timings:
        ai = protect_volley(ai, timings)
    if args.min_retreat_ms:
        ai = min_retreat(ai, args.min_retreat_ms)
    if args.cap_volley:
        ai = cap_volley(ai, args.cap_margin_ms, args.cap_after_fire_ms)
    if args.hold_volley_ms:
        ai = hold_volley(ai, args.hold_volley_ms)
    if args.threat_gate:
        ai = threat_gate(ai, args.threat_gate)
    pd.ai_names[1] = name + '.ai'
    embedded.data = ai
    matched = 0
    for entry in s.sections['Files'].retriever_map['ai_files'].data:
        if entry.retriever_map['ai_file_name'].data == old_name:
            entry.retriever_map['ai_file_name'].data = name + '.per'
            entry.retriever_map['ai_file'].data = ai
            matched += 1
    if matched != 1:
        raise SystemExit(f'Expected one embedded AI file entry, found {matched}')

    folder = out / 'donut-template'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{source.stem} - {name}.aoe2scenario'
    if target.exists():
        raise SystemExit(f'{target} exists; frozen templates are never rewritten')
    (folder / (name + '.per')).write_text(ai, encoding='utf-8')
    (folder / (name + '.ai')).write_bytes(b'')
    with contextlib.redirect_stdout(io.StringIO()):
        s.write_to_file(str(target))

    before, after = load_scenario(source), load_scenario(target)
    for check in (_camera_configuration, _trigger_structure):
        assert check(before) == check(after), check.__name__
    units = lambda sc: [(p, u.unit_const, u.x, u.y) for p in range(9) for u in sc.unit_manager.units[p]]
    assert units(before) == units(after), 'units moved'
    assert [(t.terrain_id, t.elevation) for t in before.map_manager.terrain] == \
           [(t.terrain_id, t.elevation) for t in after.map_manager.terrain], 'terrain changed'
    pd2 = after.sections['PlayerDataTwo']
    assert pd2.ai_names[1] == name + '.ai'
    assert pd2.retriever_map['ai_files'].data[1].retriever_map['ai_per_file_text'].data == ai
    files = [e for e in after.sections['Files'].retriever_map['ai_files'].data
             if e.retriever_map['ai_file_name'].data == name + '.per']
    assert len(files) == 1 and files[0].retriever_map['ai_file'].data == ai
    runtime_same = _player_runtime_configuration(before) == _player_runtime_configuration(after)

    audit = dict(audit_in, templateSha256=sha256(target), aiName=name,
                 aiSha256=sha256(folder / (name + '.per')),
                 derivedFrom=dict(path=rel(source), sha256=sha256(source)),
                 aiTiming=[{k: v for k, v in t.items()} for t in timings],
                 aiDiscoveryAdded=[dict(master=m, nextTo=a) for m, a in discovery],
                 aiMinRetreatMs=args.min_retreat_ms, aiVolleyCap=args.cap_volley,
                 aiVolleyCapMarginMs=args.cap_margin_ms if args.cap_volley else None,
                 aiVolleyCapAfterFireMs=args.cap_after_fire_ms if args.cap_volley else None,
                 aiHoldVolleyMs=args.hold_volley_ms, aiThreatGate=args.threat_gate,
                 aiTimingNote='Embedded AI patched by donut_ai_timing (protect_volley / min_retreat / cap_volley / hold_volley / threat_gate); '
                              'armies, terrain, camera and triggers unchanged',
                 playerRuntimeConfigurationUnchanged=runtime_same)
    audit_path = target.with_suffix('.audit.json')
    audit_path.write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    themes = {args.civ: dict(theme=audit_in.get('theme'), title=audit_in.get('title'), path=rel(target))}
    (out / 'civ-themes.json').write_text(json.dumps(themes, indent=2) + '\n', encoding='utf-8')
    print(f'{target}\n  windows: ' + ', '.join(f"{t['label']} {t['firingWindowMs']} ms" for t in timings)
          + f'\n  player runtime config unchanged: {runtime_same}')


if __name__ == '__main__':
    main()
