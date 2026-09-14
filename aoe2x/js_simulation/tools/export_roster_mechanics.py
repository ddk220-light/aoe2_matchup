"""Export missing canonical-roster fixtures using the shared DB/DAT exporter.

Does not modify existing calibrated fixtures or start simulation campaigns.
"""
from __future__ import annotations
import json
import subprocess
import sqlite3
import argparse
from pathlib import Path
from aoe2x.js_simulation.tools.export_unit_mechanics import export_unit_mechanics, _raw_unit, _unit_analyzer

ROOT = Path(__file__).resolve().parents[3]


def supplemental_reference(unit):
    """Evaluate explicit roster units absent from the site's public selection list."""
    from aoe2x.extract.extract_units import extract_unit_data
    data, raw = _raw_unit(ROOT / 'data/inputs/empires2_x2_p1.dat', unit['civ'], unit['master'])
    analyzer = _unit_analyzer()
    analyzer.units[unit['master']] = extract_unit_data(raw, {v.id:v for v in data.civs[0].units if v})
    stats = analyzer.calculate_form_stats(unit['civ'], unit['master'], 4)
    if stats is None:
        raise ValueError('No DAT-backed stats for ' + unit['slug'])
    return dict(civ_name=unit['civ'], age='Imperial', applied_tech_ids=(),
        final_hp=stats.hp, final_speed=stats.speed, exact_speed=stats.speed,
        final_range=stats.range, min_range=raw.type_50.min_range,
        final_reload_time=stats.reload_time, final_attack_delay=stats.attack_delay,
        final_accuracy=stats.accuracy, base_accuracy=raw.type_50.accuracy_percent,
        final_los=stats.los, final_attacks_json=json.dumps(stats.attacks),
        final_armors_json=json.dumps(stats.armors), pop_space=1,
        source_selector=f'DAT master {unit["master"]} through UnitAnalyzer.calculate_form_stats({unit["civ"]}, Imperial); absent from ref_units')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slugs', help='Explicit comma-separated fixtures to regenerate')
    args = parser.parse_args()
    script = "import {UNIT_REGISTRY} from './aoe2x/js_simulation/src/unit-registry.js'; console.log(JSON.stringify(UNIT_REGISTRY));"
    registered = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', script], cwd=ROOT))
    existing = {u['slug'] for u in registered
                if (ROOT / 'aoe2x/js_simulation/fixtures/unit_stats' / u['fixture']).is_file()}
    roster = json.loads((ROOT / 'data/unique-unit-roster.json').read_text())['units']
    output = ROOT / 'aoe2x/js_simulation/fixtures/unit_stats'
    report = []
    db = sqlite3.connect(ROOT / 'data/golden/aoe2_reference.db')
    for unit in roster:
        if (args.slugs and unit['slug'] not in args.slugs.split(',')) or (not args.slugs and unit['slug'] in existing):
            continue
        try:
            rows = db.execute('SELECT unit_slug FROM ref_units WHERE unit_name=? AND civ_name=? AND age=?',
                              (unit['label'], unit['civ'], 'Imperial')).fetchall()
            supplemental = None
            if not rows and unit['master'] in (775, 1263):
                supplemental = supplemental_reference(unit)
            elif len(rows) != 1:
                raise ValueError(f"No unique reference row for {unit['label']} / {unit['civ']}")
            value = export_unit_mechanics(ROOT / 'data/golden/aoe2_reference.db',
                ROOT / 'data/inputs/empires2_x2_p1.dat', rows[0][0] if rows else unit['slug'],
                unit['civ'], unit['master'], reference_row=supplemental)
            path = output / (unit['slug'] + '_imperial.json')
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            row = {'slug': unit['slug'], 'status': 'exported', 'fixture': path.name}
        except Exception as exc:
            row = {'slug': unit['slug'], 'status': 'failed', 'error': str(exc)}
        report.append(row)
        print(json.dumps(row), flush=True)
    # Keep the generated registry reproducible when new canonical units arrive.
    registry_path = ROOT / 'aoe2x/js_simulation/src/roster-unit-registry.js'
    registry_text = registry_path.read_text() if registry_path.exists() else 'export const ROSTER_UNITS = [];'
    additions = json.loads(registry_text[registry_text.index('['):registry_text.rindex(']') + 1])
    additions_by_slug = {row['slug']: row for row in additions}
    for row in report:
        if row['status'] != 'exported' or row['slug'] in existing:
            continue
        unit = next(u for u in roster if u['slug'] == row['slug'])
        additions_by_slug[unit['slug']] = {**unit, 'fixture': row['fixture']}
    registry_path.write_text('// Source-backed additions from data/unique-unit-roster.json.\nexport const ROSTER_UNITS = ' +
        json.dumps(list(additions_by_slug.values()), indent=2) + ';\n', encoding='utf-8')
    (ROOT / '.tools').mkdir(exist_ok=True)
    (ROOT / '.tools/roster-fixture-export.json').write_text(json.dumps(report, indent=2))
    if any(row['status'] == 'failed' for row in report):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
