"""Copy audited Donuts with a different starting age for the fighting players.

Every Donut ships Post-Imperial (6): the armies spawn with every technology.
An Imperial-start (5) copy fights with the upgrades a player has entering the
Imperial Age (Castle Age and earlier), the "Castle Age upgrades" comparison.
Only players 1-3's starting age changes; armies, terrain, AI, camera and
triggers are verified unchanged. Sources are never modified.

    python apps/video/prepare_donut_starting_age.py --age imperial --out data/local/donut-imperial-start \
        --themes data/local/themed-donuts/civ-themes.json \
        --civ Huns="data/local/arena-donut-standard/donut-template/Winter Donut.aoe2scenario" \
        --civ Mapuche="data/local/bolas-donut-timing/donut-template/<...>.aoe2scenario"

--civ entries override/extend --themes. Writes <out>/<theme>/<name> - Imperial Start.aoe2scenario,
its audit, and <out>/civ-themes.json for prepare_spike_matchups.py --donut-themes.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path

from aoe2x.lab.io import sha256
from prepare_norse_standard_capture import load_scenario

ROOT = Path(__file__).resolve().parents[2]
AGES = {'imperial': (5, 'Imperial Start'), 'castle': (4, 'Castle Start')}
FIGHTERS = (1, 2, 3)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def copy_with_age(source: Path, out: Path, age: int, suffix: str) -> Path:
    from aoe2x.lab.live import _camera_configuration, _trigger_structure
    audit_in = json.loads(source.with_suffix('.audit.json').read_text(encoding='utf-8'))
    if audit_in.get('state') != 'PASSED' or audit_in.get('templateSha256') != sha256(source):
        raise SystemExit(f'{source} is not an audited, unchanged template')
    target = out / f'{source.stem} - {suffix}.aoe2scenario'
    if target.exists():
        raise SystemExit(f'{target} exists; frozen templates are never rewritten')
    s = load_scenario(source)
    players = {int(p.player_id): p for p in s.player_manager.players}
    if any(int(players[i].starting_age) != 6 for i in FIGHTERS):
        raise SystemExit(f'{source} fighters are not Post-Imperial')
    for i in FIGHTERS:
        players[i].starting_age = age
    out.mkdir(parents=True, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        s.write_to_file(str(target))
    before, after = load_scenario(source), load_scenario(target)
    for check in (_camera_configuration, _trigger_structure):
        assert check(before) == check(after), check.__name__
    units = lambda sc: [(p, u.unit_const, u.x, u.y) for p in range(9) for u in sc.unit_manager.units[p]]
    assert units(before) == units(after), 'units moved'
    assert [(t.terrain_id, t.elevation) for t in before.map_manager.terrain] == \
           [(t.terrain_id, t.elevation) for t in after.map_manager.terrain], 'terrain changed'
    ai = lambda sc: (list(sc.sections['PlayerDataTwo'].ai_names),
                     [e.retriever_map['ai_file'].data for e in sc.sections['Files'].retriever_map['ai_files'].data])
    assert ai(before) == ai(after), 'AI changed'
    ages = {int(p.player_id): int(p.starting_age) for p in after.player_manager.players}
    assert all(ages[i] == age for i in FIGHTERS)
    audit = dict(audit_in, templateSha256=sha256(target), startingAge=age, startingAgeName=suffix,
                 derivedFrom=dict(path=rel(source), sha256=sha256(source)),
                 startingAgeNote='Players 1-3 starting age changed from Post-Imperial (6); '
                                 'armies, terrain, AI, camera and triggers unchanged')
    target.with_suffix('.audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--age', required=True, choices=sorted(AGES))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--themes', type=Path, help='civ-themes.json from build_themed_donuts.py')
    ap.add_argument('--civ', action='append', default=[], help='Civ=path/to/donut.aoe2scenario')
    args = ap.parse_args()
    age, suffix = AGES[args.age]
    out = args.out if args.out.is_absolute() else ROOT / args.out
    sources = {}
    if args.themes:
        for civ, spec in json.loads((ROOT / args.themes).read_text(encoding='utf-8')).items():
            sources[civ] = ROOT / spec['path']
    for entry in args.civ:
        civ, path = entry.split('=', 1)
        sources[civ] = ROOT / path
    themes, done = {}, {}
    for civ, source in sorted(sources.items()):
        if source not in done:
            done[source] = copy_with_age(source, out / source.parent.name, age, suffix)
        themes[civ] = dict(path=rel(done[source]), startingAge=age)
        print(f'{civ:<10} {rel(done[source])}')
    (out / 'civ-themes.json').write_text(json.dumps(themes, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
