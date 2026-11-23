"""Re-take Donut trials whose melee army opened passively, with the validated patrol.

Themed and starting-age Donuts were reskinned from the plain Winter Donut, so
they lack the October whole-army opening patrol (fix_jarl_opening_patrol.py).
Without it, rear melee units can stand idle for 15-30 s and trickle into the
fight. For every Donut a selected row uses, this writes an audited
"<name> - Army Patrol" sibling with the same trigger: at second 1, P3 patrols
the whole army by unit type to (11, 5). build_run retargets the unit-type
filter onto the generated army. Each selected row is then copied with its
iteration shifted by --shift, pointing at the patrol sibling. Existing
recordings and templates are never modified.

    python add_donut_opening_patrol.py OUT.manifest.json --shift 3 \
        --manifest data/local/a/manifest.json --match s15_ [--manifest ... --match ...]
"""
import argparse
import contextlib
import copy
import io
import json
import re
from pathlib import Path

from aoe2x.lab.io import sha256
from prepare_norse_standard_capture import load_scenario

ROOT = Path(__file__).resolve().parents[2]
PATROL = dict(owner=3, timerSeconds=1, selection='whole-map army unit type', target=[11, 5], looping=False)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def patrol_sibling(donut):
    source = ROOT / donut['path']
    audit_path = ROOT / donut['auditPath']
    assert sha256(source) == donut['sha256'] and sha256(audit_path) == donut['auditSha256'], source
    audit = read(audit_path)
    assert 'openingPatrol' not in audit, f'{source} already has an opening patrol'
    target = source.with_name(source.stem + ' - Army Patrol.aoe2scenario')
    target_audit = target.with_suffix('.audit.json')
    if not target.exists():
        scn = load_scenario(source)
        t = scn.trigger_manager.add_trigger('P3 opening patrol: whole army by unit type')
        t.looping = False
        t.new_condition.timer(timer=1)
        t.new_effect.patrol(source_player=3, object_list_unit_id=scn.unit_manager.units[3][0].unit_const,
                            area_x1=0, area_y1=0, area_x2=15, area_y2=15, location_x=11, location_y=5)
        with contextlib.redirect_stdout(io.StringIO()):
            scn.write_to_file(str(target))
    audit.update(templateSha256=sha256(target), parentTemplateSha256=donut['sha256'],
                 parentTemplate=donut['path'], openingPatrol=PATROL)
    save(target_audit, audit)
    rel = lambda p: p.relative_to(ROOT).as_posix()
    return dict(path=rel(target), sha256=sha256(target), auditPath=rel(target_audit),
                auditSha256=sha256(target_audit))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--manifest', action='append', required=True)
    ap.add_argument('--match', action='append', required=True, help='regex on row id, one per --manifest')
    ap.add_argument('--shift', type=int, default=3)
    a = ap.parse_args()
    assert len(a.manifest) == len(a.match)
    siblings, rows = {}, []
    for manifest, pattern in zip(a.manifest, a.match):
        for row in read(ROOT / manifest)['matchups']:
            if not re.search(pattern, row['id']):
                continue
            donut = row['scenario']['donut']
            if donut['path'] not in siblings:
                siblings[donut['path']] = patrol_sibling(donut)
            new = copy.deepcopy(row)
            base, n = re.fullmatch(r'(.*)_r(\d+)', row['id']).groups()
            new['id'] = f'{base}_r{int(n) + a.shift}'
            if 'iteration' in new:
                new['iteration'] = int(n) + a.shift
            new['scenario']['donut'] = siblings[donut['path']]
            new['openingPatrolCorrected'] = True
            new['supersedes'] = row['id']
            rows.append(new)
    assert len({r['id'] for r in rows}) == len(rows)
    save(ROOT / a.out, dict(schemaVersion=1, matchups=rows))
    print(len(rows), 'rows,', len(siblings), 'patrol Donuts ->', a.out)


if __name__ == '__main__':
    main()
