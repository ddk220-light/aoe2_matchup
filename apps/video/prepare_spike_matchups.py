"""Freeze a small multi-map spike: subjects x opponents x layouts -> recorder manifest.

Layouts:
  arena   frozen detailed-winter Arena Goldens (tracked under data/local/detailed-standard-norse)
  donut   frozen Winter Donut kiting map + ddkDonutQuietAI; only ranged subject (P2) vs melee
  theme   a themed Arena built now from --theme-source with the audited winter_templates()
          pipeline (terrain/Gaia only; armies, AI, camera and triggers stay the Golden's)

Every row: v3 geometric balance (cap 27, weights 1/0.9/1.1), no buffer, subject on P2,
subject blue / opponent red. Plans are made and cost-validated before anything is
saved; nothing here touches the game.

    python apps/video/prepare_spike_matchups.py --work data/local/steppe-spike \
        --subject Cumans:elite_kipchak_cumans --subject Tatars:heavy_cavalry_archer_tatars \
        --opponent Franks:paladin_franks ... --layouts arena donut theme \
        --theme-source "data/local/arena-theme-review/scenarios/Biome 08A - Savannah Scenic.aoe2scenario" \
        --theme-opponents paladin_franks arbalester_saracens

Then: python -m aoe2x.lab.recording_campaign <work>/manifest.json --reports <lab>/campaigns/<name>
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import sha256
from aoe2x.lab.planner import plan_matchup

ROOT = Path(__file__).resolve().parents[2]
ARENA = ROOT / 'data/local/detailed-standard-norse/winter-templates'
DONUT = ROOT / 'data/local/arena-donut-standard/donut-template/Winter Donut.aoe2scenario'
PICKLED_DAT = ROOT / 'data/local/viking-sagas-research/installed-dat.pkl'
WEIGHTS = {'food': 1, 'wood': 0.9, 'gold': 1.1}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def frozen(path: Path, audit: Path) -> dict:
    return dict(path=rel(path), sha256=sha256(path), auditPath=rel(audit), auditSha256=sha256(audit))


def unit_class(slug: str) -> str:
    for name in ('unique-unit-roster.json', 'recording-subjects.json'):
        for u in json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))['units']:
            if u['slug'] == slug:
                return u['class']
    raise SystemExit(f'Unregistered unit {slug}; see apps/video/register_recording_unit.py')


def build_theme(source: Path, work: Path, extra_land=()) -> Path:
    """Run the audited scenery derivative pipeline into <work>/theme-templates."""
    from aoe2x.lab.live import _load_stack
    from prepare_norse_standard_capture import winter_templates
    config = load_config()
    _load_stack(config)
    with PICKLED_DAT.open('rb') as stream:
        raw_dat = pickle.load(stream)
    scratch = work / '_theme'
    winter_templates(config, raw_dat, visual_source=source, work=scratch, extra_land=frozenset(extra_land))
    out = work / 'theme-templates'
    out.mkdir(parents=True, exist_ok=True)
    for f in (scratch / 'winter-templates').iterdir():
        f.replace(out / f.name)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--subject', action='append', required=True, help='Civ:slug, repeatable')
    ap.add_argument('--opponent', action='append', required=True, help='Civ:slug, repeatable')
    ap.add_argument('--layouts', nargs='+', default=['arena'], choices=['arena', 'donut', 'theme'])
    ap.add_argument('--theme-source', type=Path)
    ap.add_argument('--theme-name', default='Theme')
    ap.add_argument('--theme-extra-land', type=int, nargs='*', default=[],
                    help='extra flat passable terrain ids allowed in the combat band (e.g. 41 DIRT_SAVANNAH)')
    ap.add_argument('--theme-opponents', nargs='*', help='limit theme rows to these opponent slugs')
    ap.add_argument('--prefix', default='spike')
    args = ap.parse_args()
    work = args.work if args.work.is_absolute() else ROOT / args.work
    if (work / 'manifest.json').exists():
        raise SystemExit(f'{work}/manifest.json exists; frozen spikes are never rewritten')
    theme_dir = None
    if 'theme' in args.layouts:
        if not args.theme_source:
            raise SystemExit('--theme-source is required for the theme layout')
        src = args.theme_source if args.theme_source.is_absolute() else ROOT / args.theme_source
        theme_dir = build_theme(src, work, args.theme_extra_land)
    rows = []
    for subject in args.subject:
        civ2, slug2 = subject.split(':')
        if unit_class(slug2) == 'melee':
            raise SystemExit('Spike subjects must be ranged (Donut puts ranged on P2)')
        for index, opponent in enumerate(args.opponent, 1):
            civ3, slug3 = opponent.split(':')
            melee = unit_class(slug3) == 'melee'
            family = 'ranged_vs_ranged'  # no buffer + any ranged side
            layouts = []
            if 'arena' in args.layouts:
                layouts.append(('arena', dict(scenery=frozen(ARENA / f'{family}.aoe2scenario', ARENA / f'{family}.audit.json'))))
            if 'donut' in args.layouts and melee:
                layouts.append(('donut', dict(donut=frozen(DONUT, DONUT.with_name('Winter Donut.audit.json')))))
            if theme_dir and (not args.theme_opponents or slug3 in args.theme_opponents):
                layouts.append(('theme', dict(scenery=frozen(theme_dir / f'{family}.aoe2scenario', theme_dir / f'{family}.audit.json'))))
            for layout, extra in layouts:
                rows.append(dict(
                    id=f'{args.prefix}_{slug2}_{index:02}_{slug3}_{layout}',
                    side2=slug2, civ2=civ2, side3=slug3, civ3=civ3, subjectOwner=2,
                    layout={'arena': 'Arena', 'donut': 'Donut', 'theme': args.theme_name}[layout],
                    balance=dict(mode='geometric_shared_discount', cap=27, weights=WEIGHTS),
                    scenario=dict(goldenFamily=family, player4Buffer='none', subjectOwner=2, **extra)))
    work.mkdir(parents=True, exist_ok=True)
    manifest = dict(schemaVersion=1, matchups=rows)
    tmp = work / 'manifest.candidate.json'
    tmp.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    defaults, requests = _load_batch(tmp)
    config = load_config()
    plans = []
    for request in requests:
        plan = plan_matchup(config, request)
        validate_plan_costs(plan)
        plans.append(plan)
    tmp.replace(work / 'manifest.json')
    summary = [dict(id=r['id'], layout=r['layout'],
                    subject=f"{p['side2']['count']} {p['side2']['label']}",
                    opponent=f"{p['side3']['count']} {p['side3']['label']} ({p['side3']['civ']})",
                    planHash=p['planHash'][:12])
               for r, p in zip(rows, plans)]
    (work / 'plans-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    for s in summary:
        print(f"{s['id']:<70} {s['layout']:<8} {s['subject']:>26} vs {s['opponent']}")
    print(f'{len(rows)} battles frozen in {work / "manifest.json"}')


if __name__ == '__main__':
    main()
