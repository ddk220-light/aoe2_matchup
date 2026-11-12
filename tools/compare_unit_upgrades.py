#!/usr/bin/env python3
"""Compare common and exclusive technologies in the disposable upgrade ledger."""
import argparse
import json
import sqlite3
from pathlib import Path
from army_economics_paths import scratch_path

RESOURCES = ('food', 'wood', 'stone', 'gold')


def compare(path, unit_a, unit_b, scope='direct'):
    con = sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    def load(key):
        unit = con.execute('select * from units where unit_key=?', (key,)).fetchone()
        if not unit:
            raise ValueError(f'Unknown unit key: {key}')
        rows = {r['tech_id']: dict(r) for r in con.execute(
            'select * from unit_upgrade_data where unit_key=? and scope=?', (key, scope))}
        return dict(unit), rows
    a, rows_a = load(unit_a)
    b, rows_b = load(unit_b)
    shared = sorted(rows_a.keys() & rows_b.keys())
    only_a, only_b = sorted(rows_a.keys() - rows_b.keys()), sorted(rows_b.keys() - rows_a.keys())
    def cost_totals(rows):
        return {kind: {resource: round(sum(r[kind+'_'+resource] for r in rows), 6)
                       for resource in RESOURCES} for kind in ('upfront','reward','net')}
    common = []
    for tid in shared:
        ra, rb = rows_a[tid], rows_b[tid]
        common.append(dict(tech_id=tid, technology=ra['technology'],
            a=ra, b=rb,
            cost_difference_a_minus_b={kind: {resource: round(ra[kind+'_'+resource]-rb[kind+'_'+resource],6)
                                      for resource in RESOURCES} for kind in ('upfront','reward','net')},
            research_seconds_difference_a_minus_b=round(ra['final_seconds']-rb['final_seconds'],6)
                if ra['final_seconds'] is not None and rb['final_seconds'] is not None else None))
    result = dict(unit_a=a, unit_b=b, scope=scope,
        common=dict(upgrades=common,
                    a_cost=cost_totals([rows_a[i] for i in shared]),
                    b_cost=cost_totals([rows_b[i] for i in shared]),
                    a_research_workload_seconds=sum(rows_a[i]['final_seconds'] or 0 for i in shared),
                    b_research_workload_seconds=sum(rows_b[i]['final_seconds'] or 0 for i in shared)),
        only_a=dict(upgrades=[rows_a[i] for i in only_a], costs=cost_totals([rows_a[i] for i in only_a])),
        only_b=dict(upgrades=[rows_b[i] for i in only_b], costs=cost_totals([rows_b[i] for i in only_b])),
        notes=['Time differences use common technology IDs only; sums are workload, not elapsed upgrade time.',
               'Exclusive upgrade costs remain separate. No army-size normalization or cutoff.',
               'Building costs are shown per row; use the distinct building lists to avoid double counting.',
               'Review unresolved unit_upgrade_candidates before treating a package as exhaustive.'])
    for label,key in [('a',unit_a),('b',unit_b)]:
        result['buildings_'+label] = [dict(r) for r in con.execute(
            'select * from unit_research_buildings where unit_key=? and scope=?', (key,scope))]
    con.close()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('unit_a', help='Civ:unit_id, e.g. Spanish:567')
    parser.add_argument('unit_b', help='Civ:unit_id, e.g. Goths:567')
    parser.add_argument('--database', type=Path, default=scratch_path('research-review/current-results/unit-upgrades.sqlite'))
    parser.add_argument('--scope', choices=['direct','production_support'], default='direct')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    content = json.dumps(compare(args.database,args.unit_a,args.unit_b,args.scope),indent=2)+'\n'
    if args.output:
        args.output.write_text(content)
    else:
        print(content,end='')
