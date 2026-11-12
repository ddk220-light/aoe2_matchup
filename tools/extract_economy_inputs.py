#!/usr/bin/env python3
"""Preserve DAT economic actors, infrastructure, tasks and resource objects.

This is a source snapshot, not an income model. Run using the Genieutils venv.
"""
import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from army_economics_paths import scratch_path, dat_path

from build_production_review import attach_game_trees

ROOT = scratch_path('production-review')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=scratch_path('economy-review/labor-source.json'))
    args = p.parse_args()
    raw = json.loads((ROOT/'current-raw-source.json').read_text())
    attach_game_trees(raw, ROOT/'current-input/dat/CivTechTrees')
    from genieutils.datfile import DatFile
    data = DatFile.parse(dat_path(raw))
    assert hashlib.sha256(dat_path(raw).read_bytes()).hexdigest() == raw['source']['sha256']

    def snapshot(u):
        names = ('id', 'name', 'type', 'class_', 'enabled', 'disabled', 'speed',
                 'resource_capacity', 'resource_decay', 'resource_gather_group',
                 'garrison_capacity', 'collision_size_x', 'collision_size_y',
                 'dead_unit_id', 'hit_points', 'line_of_sight', 'trait',
                 'recyclable', 'enable_auto_gather', 'terrain_restriction')
        result = {k: getattr(u, k) for k in names}
        result['resource_storages'] = [asdict(x) for x in u.resource_storages]
        for field in ('bird', 'building', 'creatable', 'dead_fish'):
            value = getattr(u, field, None)
            result[field] = asdict(value) if value else None
        return result

    civs = {}
    targets = set()
    production = sqlite3.connect(str(scratch_path('economy-review/corrected-production/production-review.sqlite')))
    logs = {n: json.loads(v) for n,v in production.execute('select civ_name,active_technologies from civilization_evaluation')}
    for name, base in sorted(raw['civs'].items()):
        civ = data.civs[base['id']]
        nodes = {n['Node ID']: n for n in base['game_tree']['civ_techs_buildings']}
        # All shipped infrastructure is included, even if unavailable, with its
        # status attached. This catches settlement/mule cart/fish trap variants
        # and military buildings that generate resources on completion.
        ids = set(nodes)
        ids.update(i for i,u in enumerate(civ.units) if u and u.class_ in {2,4,19,21,49})
        for i,u in enumerate(civ.units):
            if u and any(x in u.name.lower() for x in ('mule', 'feitoria', 'caravans', 'pasture', 'folwark', 'settlement')):
                ids.add(i)
        # Age variants and annexes are separate records. Preserve their raw
        # definitions as well as the tree's representative building ID.
        effects = [raw['effects'][str(raw['techs'][str(t['tech_id'])]['effect_id'])]
                   for t in logs[name] if str(raw['techs'][str(t['tech_id'])]['effect_id']) in raw['effects']]
        effects += [raw['effects'][str(t['effect_id'])] for t in raw['techs'].values()
                    if t['civ'] == base['id'] and str(t['effect_id']) in raw['effects']]
        ids.update(c['a'] for e in effects for c in e['effect_commands'] if c['type'] == 7 and c['a'] >= 0)
        while True:
            extra = set()
            for uid in ids:
                u = civ.units[uid]
                if u and u.building:
                    b = u.building
                    extra.update(i for i in (b.head_unit,b.stack_unit_id,b.transform_unit) if i >= 0)
                    extra.update(a.unit_id for a in b.annexes if a.unit_id >= 0)
                if u and u.dead_unit_id >= 0:
                    extra.add(u.dead_unit_id)
            extra.update(c['b'] for e in effects for c in e['effect_commands'] if c['type'] == 3 and c['a'] in ids and c['b'] >= 0)
            # Dead-unit overrides can instantiate hidden reward objects, e.g.
            # Lithuanian Town Center annex 890 -> food object 888.
            extra.update(int(c['d']) for e in effects for c in e['effect_commands']
                         if c['type'] in (0,10) and c['c'] == 57 and c['a'] in ids and c['d'] >= 0)
            if extra <= ids:
                break
            ids |= extra
        for uid in list(ids):
            u = civ.units[uid]
            if not u or not u.bird:
                continue
            ids.update(d for d in u.bird.drop_sites if d >= 0)
            targets.update(t.unit_id for t in u.bird.tasks if t.action_type in (5,110) and t.unit_id >= 0)
        units = {}
        for uid in sorted(ids):
            u = civ.units[uid]
            if not u:
                continue
            units[str(uid)] = dict(snapshot(u), tree_node=nodes.get(uid),
                selection_reason='shipped_building' if uid in nodes else 'economic_actor_or_linked_drop_site')
        civs[name] = dict(id=base['id'], resources=list(civ.resources), units=units)

    gaia = data.civs[0]
    ids = targets | {i for i,u in enumerate(gaia.units) if u and (
        u.resource_capacity > 0 or any(r.type in (0,1,2,3) and r.amount > 0 for r in u.resource_storages))}
    # Keep depletion/death forms of resource objects, such as felled trees.
    while True:
        extra = {gaia.units[i].dead_unit_id for i in ids if i < len(gaia.units) and gaia.units[i] and gaia.units[i].dead_unit_id >= 0}
        if extra <= ids:
            break
        ids |= extra
    objects = {str(i): snapshot(gaia.units[i]) for i in sorted(ids) if i < len(gaia.units) and gaia.units[i]}
    out = dict(source=raw['source'], scope='Raw economic candidates and all shipped infrastructure; availability is explicit',
               civs=civs, gaia_resource_candidates=objects,
               limits=['Engine hook implementations and map layouts are not present in the DAT.',
                       'Gaia candidates include editor/scenario objects; no assertion that every object occurs in ranked games.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, separators=(',',':'))+'\n')
    print(json.dumps(dict(path=str(args.output), civilizations=len(civs),
                         unit_snapshots=sum(len(c['units']) for c in civs.values()),
                         gaia_candidates=len(objects), bytes=args.output.stat().st_size)))


if __name__ == '__main__':
    main()
