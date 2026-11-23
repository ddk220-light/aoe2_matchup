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
from donut_ai_timing import bolas_timing, protect_volley, war_wagon_timing

ROOT = Path(__file__).resolve().parents[2]
UNITS = {'bolas': (bolas_timing, 'ddkDonutBolasTiming'),
         'war-wagon': (war_wagon_timing, 'ddkDonutWarWagonTiming')}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def main() -> None:
    from aoe2x.lab.live import _camera_configuration, _player_runtime_configuration, _trigger_structure
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--units', required=True, choices=sorted(UNITS))
    ap.add_argument('--civ', required=True, help='civ key for the civ-themes JSON')
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    source = args.source if args.source.is_absolute() else ROOT / args.source
    out = args.out if args.out.is_absolute() else ROOT / args.out
    audit_in = json.loads(source.with_suffix('.audit.json').read_text(encoding='utf-8'))
    if audit_in.get('state') != 'PASSED' or audit_in.get('templateSha256') != sha256(source):
        raise SystemExit('Source Donut is not an audited, unchanged template')
    timing_fn, name = UNITS[args.units]
    timings = timing_fn(DAT)

    s = load_scenario(source)
    pd = s.sections['PlayerDataTwo']
    embedded = pd.retriever_map['ai_files'].data[1].retriever_map['ai_per_file_text']
    old_name = pd.ai_names[1].replace('.ai', '.per')
    if old_name != audit_in.get('aiName', '') + '.per':
        raise SystemExit(f'Unexpected embedded AI {old_name}')
    ai = protect_volley(embedded.data, timings)
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
                 aiTimingNote='Embedded AI patched by donut_ai_timing.protect_volley; '
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
