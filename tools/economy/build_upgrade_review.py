#!/usr/bin/env python3
"""Source-derived, disposable military upgrade ledger for owner review.

All costs use Imperial modifiers, including earlier upgrades. Research durations
are independent post-Imperial queue workloads, not an elapsed build order.
No production or serving database is modified. See the generated README.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import sqlite3
from dataclasses import asdict
from collections import defaultdict, deque
from pathlib import Path
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from aoe2x.economy.paths import scratch_path, dat_path  # noqa: E402

from build_production_review import AGES, ATTRS, OPS, RESOURCES, apply, attach_game_trees, costs, match, sql_table

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = scratch_path('production-review')
RES = tuple(RESOURCES.values())
# These DAT attributes concern queues, locations, costs or presentation rather
# than combat. Unit costs remain a direct military investment benefit.
PRESENTATION = {25, 42, 43, 53, 54, 71, 75, 84, 87, 158}
PRODUCTION = {101, 42, 43, 158}
ECONOMIC_CLASSES = {2, 4, 19, 21}  # trade cog, villager, trade cart, fishing ship


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def zeros():
    return {r: 0.0 for r in RES}


def clean(value):
    # Suppress float32 representation noise without guessing integer UI rounding.
    return round(float(value), 6)


def command_source(data, eid, kind, tid=None):
    effect = data['effects'].get(str(eid), {})
    return [dict(source_kind=kind, tech_id=tid, effect_id=eid,
                 command_index=i, command=cmd)
            for i, cmd in enumerate(effect.get('effect_commands', []))]


def extract_links(dat_path, destination):
    from genieutils.datfile import DatFile
    data = DatFile.parse(dat_path)
    civs = {}
    for cid, civ in enumerate(data.civs):
        units = {}
        for uid, u in enumerate(civ.units):
            if u is None:
                continue
            units[str(uid)] = dict(id=uid, name=u.name, type=u.type, class_id=u.class_,
                dead_unit_id=u.dead_unit_id, hit_points=u.hit_points,
                projectile_unit_id=u.type_50.projectile_unit_id if u.type_50 else -1,
                secondary_projectile_unit=u.creatable.secondary_projectile_unit if u.creatable else -1,
                charge_projectile_unit=u.creatable.charge_projectile_unit if u.creatable else -1,
                transform_unit=u.building.transform_unit if u.building else -1,
                resource_storages=[asdict(r) for r in u.resource_storages],
                tasks=[asdict(t) for t in u.bird.tasks] if u.bird else [],
                special_ability=u.creatable.special_ability if u.creatable else -1,
                hero_mode=u.creatable.hero_mode if u.creatable else -1)
        civs[str(cid)] = units
    destination.write_text(json.dumps(dict(source_sha256=hashlib.sha256(dat_path.read_bytes()).hexdigest(), civs=civs)))


class State:
    def __init__(self, data, civ, evaluation, links):
        self.data, self.civ = data, civ
        self.units = {int(k): v for k, v in civ['units'].items()}
        self.links = {int(k): v for k, v in links.items()}
        self.techs = {int(k): v for k, v in data['techs'].items()}
        self.log = json.loads(evaluation['active_technologies'])
        self.active = {x['tech_id'] for x in self.log}
        tree = civ['game_tree']
        self.building_nodes = {n['Node ID']: n for n in tree['civ_techs_buildings']}
        self.unit_nodes = {n['Node ID']: n for n in tree['civ_techs_units'] if n['Use Type'] == 'Unit'}
        self.tech_nodes = {n['Node ID']: n for n in tree['civ_techs_units'] if n['Use Type'] == 'Tech'}
        granted = {tid for tid, n in self.tech_nodes.items() if n['Node Status'] != 'NotAvailable'}
        granted.update(n['Trigger Tech ID'] for n in self.unit_nodes.values()
                       if n['Node Status'] != 'NotAvailable' and n.get('Trigger Tech ID', -1) >= 0)
        self.researchable = {i for i in self.active & granted if i not in AGES
                            and any(x['location_id'] >= 0 and x['button_id'] > 0
                                    for x in self.techs[i]['research_locations'])}
        self.commands = command_source(data, civ['tree_id'], 'civilization')
        self.commands += command_source(data, civ['team_id'], 'own_team_bonus')
        for item in self.log:
            tid = item['tech_id']
            self.commands += command_source(data, self.techs[tid]['effect_id'], item['reason'], tid)
        self.by_tech = defaultdict(list)
        self.reverse_edges, self.forward_edges = defaultdict(set), defaultdict(set)
        for source in self.commands:
            self.by_tech[source['tech_id']].append(source)
            c = source['command']
            if c['type'] == 3 and c['c'] in (-1, 0):
                self.reverse_edges[c['b']].add(c['a'])
                self.forward_edges[c['a']].add(c['b'])
        self.owner_cache, self.building_cache, self.target_cache, self.form_evidence = {}, {}, {}, {}
        self.bundles = defaultdict(list)
        self.pricing = [s for s in self.commands if s['command']['type'] in (101, 103)
                        or (s['command']['type'] in (1, 6) and s['command']['a'] in (85, 86, 269))
                        or (s['command']['type'] in OPS and s['command']['c'] == 13)]
        for source in self.commands:
            tid = source['tech_id']
            if tid is None or tid in AGES:
                continue
            for owner in self.owners(tid):
                self.bundles[owner].append(source)

    def owners(self, tid, seen=None):
        """Trace a shadow effect back to its available researchable gate(s)."""
        if tid in self.researchable:
            return {tid}
        if tid in self.owner_cache:
            return self.owner_cache[tid]
        if tid in AGES or tid not in self.active:
            return set()
        seen = (seen or set()) | {tid}
        result = set()
        for req in self.techs[tid]['required_techs']:
            if req >= 0 and req not in seen:
                result.update(self.owners(req, seen))
        self.owner_cache[tid] = result
        return result

    def label(self, tid):
        if tid in self.tech_nodes:
            return self.tech_nodes[tid]['Name']
        # Unit upgrades are represented by the resulting unit in the shipped tree.
        for n in self.unit_nodes.values():
            if n.get('Trigger Tech ID') == tid:
                return n['Name']
        return self.techs[tid]['name']

    def building(self, bid):
        if bid in self.building_cache:
            return self.building_cache[bid]
        unit = self.units[bid]
        parent, seen = unit, set()
        while parent['building'] and parent['building']['head_unit'] in self.units:
            if parent['id'] in seen:
                break
            seen.add(parent['id'])
            parent = self.units[parent['building']['head_unit']]
        base = costs(parent)
        final, evidence = dict(base), []
        for source in self.commands:
            c = source['command']
            if c['type'] not in OPS or c['c'] not in (100, 103, 104, 105, 106) or not match(c, parent):
                continue
            before = dict(final)
            for resource in RES if c['c'] == 100 else [ATTRS[c['c']]]:
                final[resource] = apply(final[resource], c)
            if before != final:
                evidence.append(dict(source, before=before, after=dict(final)))
        node = self.building_nodes.get(bid, self.building_nodes.get(parent['id'], {}))
        row = dict(civ_name=self.civ['name'], building_id=bid, cost_unit_id=parent['id'],
                   building_name=node.get('Name', unit['name']),
                   available=int(bool(node) and node.get('Node Status') != 'NotAvailable'),
                   base_work_rate=unit['work_rate'], modifiers=evidence)
        row.update({'base_' + r: clean(v) for r, v in base.items()})
        row.update({'cost_' + r: clean(v) for r, v in final.items()})
        row['wood_equivalent'] = clean(final['wood'] + 2 * final['stone']) if not final['food'] and not final['gold'] else None
        self.building_cache[bid] = row
        return row

    def evaluate(self, tid):
        tech = self.techs[tid]
        base = zeros()
        for item in tech['resource_costs']:
            if item['type'] in RESOURCES and item['flag']:
                base[RESOURCES[item['type']]] += item['amount']
        cost, modifiers, flags = dict(base), [], []
        locs = [dict(x, index=i) for i, x in enumerate(tech['research_locations'])]
        for source in self.commands:
            c = source['command']
            # Modern research locations use the tech-property command, slot c.
            if c['type'] == 8 and c['a'] == tid and c['b'] in (4, 5, 11):
                index = max(0, c['c'])
                while len(locs) <= index:
                    locs.append(dict(location_id=-1, research_time=locs[0]['research_time'], button_id=0, hot_key_id=-1, index=len(locs)))
                locs[index][{4: 'location_id', 5: 'button_id', 11: 'hot_key_id'}[c['b']]] = int(c['d'])
                modifiers.append(dict(source, target='research_location'))
        resolved_locs = []
        for loc in locs:
            bid = loc['location_id']
            if bid not in self.units:
                continue
            if self.building(bid)['available']:
                resolved_locs.append(loc)
                continue
            # The engine transfers a building's research to its civilization's
            # replacement (e.g. Monastery -> Fortified Church).
            visited, queue = set(), deque([bid])
            replacements = set()
            while queue:
                target = queue.popleft()
                if target in visited:
                    continue
                visited.add(target)
                if target in self.units and self.building(target)['available']:
                    replacements.add(target)
                queue.extend(self.forward_edges[target])
            for target in sorted(replacements):
                resolved_locs.append(dict(loc, location_id=target, original_building_id=bid))
                modifiers.append(dict(target='research_building_replacement', from_building_id=bid, to_building_id=target))
        locs = resolved_locs
        if not locs:
            flags.append('no_available_research_building')
        cost_factor = time_factor = 1.0
        reward_effect = None
        pricing_owners = set()
        for source in self.pricing:
            origin = source['tech_id']
            # An upgrade cannot provide its own discount or accelerate itself.
            if origin is not None and tid in self.owners(origin):
                continue
            c = source['command']
            typ, a, b, mode, value = (c[k] for k in ('type', 'a', 'b', 'c', 'd'))
            applied = False
            if typ in (101, 103) and a in (tid, -1):
                if mode not in (-1, 0, 1, 2):
                    flags.append('unhandled_research_modifier_mode')
                    continue
                def op(v):
                    return value if mode == 0 else v * value if mode == 2 else v + value
                if typ == 101:
                    for rid, name in RESOURCES.items():
                        if b in (-1, rid):
                            cost[name] = op(cost[name])
                else:
                    for loc in locs:
                        loc['research_time'] = op(loc['research_time'])
                applied = True
            elif typ in (1, 6) and a in (85, 86, 269):
                def rop(v):
                    return v * value if typ == 6 else value if b == 0 else v + value
                if a == 85:
                    cost_factor = rop(cost_factor)
                elif a == 86:
                    time_factor = rop(time_factor)
                else:
                    reward_effect = int(value)
                applied = True
            if applied:
                modifiers.append(dict(source, target='cost_time_or_completion_reward'))
                if origin is not None:
                    pricing_owners.update(self.owners(origin))
        cost = {r: clean(v * cost_factor) for r, v in cost.items()}
        free = all(abs(v) < 1e-6 for v in cost.values())
        routes = []
        for loc in locs:
            bid = loc['location_id']
            building = self.building(bid)
            # Research locations retain the base building ID even after age
            # upgrades replace its runtime form. Use that form's queue rate;
            # keep the buildable ID for availability and construction costs.
            work_bid, form_evidence = self.research_work_building(bid)
            rate = self.units[work_bid]['work_rate']
            innate_rate = rate
            evidence, required_techs = [], set()
            for source in self.pricing:
                c, origin = source['command'], source['tech_id']
                if c['type'] not in OPS or c['c'] != 13 or not match(c, self.units[work_bid]):
                    continue
                owners = self.owners(origin) if origin is not None else set()
                if tid in owners:
                    continue
                before = rate
                rate = apply(rate, c)
                if not owners:
                    innate_rate = apply(innate_rate, c)
                if before != rate:
                    required_techs.update(owners)
                    evidence.append(dict(source, before=before, after=rate))
            base_loc = tech['research_locations'][min(loc['index'], len(tech['research_locations']) - 1)]
            routes.append(dict(civ_name=self.civ['name'], tech_id=tid, location_index=loc['index'],
                               building_id=bid, work_rate_building_id=work_bid,
                               work_rate_building_evidence=form_evidence, base_seconds=base_loc['research_time'],
                               modified_seconds=clean(loc['research_time']),
                               final_work_rate=clean(rate), innate_work_rate=clean(innate_rate),
                               final_seconds=clean(loc['research_time'] * time_factor / rate) if rate and rate > 0 else None,
                               seconds_without_paid_work_rate_bonuses=clean(loc['research_time'] * time_factor / innate_rate) if innate_rate and innate_rate > 0 else None,
                               work_rate_modifiers=evidence, work_rate_tech_ids=sorted(required_techs), selected=0))
        valid = [r for r in routes if r['final_seconds'] is not None]
        def route_rank(r):
            w = self.building(r['building_id'])['wood_equivalent']
            return (w if w is not None else float('inf'), r['final_seconds'], r['building_id'])
        selected = min(valid, key=route_rank) if valid else None
        if selected:
            selected['selected'] = 1
        instant = bool(valid) and all(r['final_seconds'] == 0 for r in valid)
        reward = zeros()
        if reward_effect is not None and not (free and instant):
            for source in command_source(self.data, reward_effect, 'completion_reward'):
                c = source['command']
                if c['type'] == 1 and c['a'] in RESOURCES and c['b'] == 1:
                    reward[RESOURCES[c['a']]] += c['d']
                    modifiers.append(source)
                else:
                    flags.append('unhandled_completion_reward')
        # Dynamic technology costs are not a fixed amount. Resource 33 selects
        # an engine calculation whose inputs are not present in this snapshot.
        dynamic = any(s['command']['type'] == 1 and s['command']['a'] == 33
                      and s['command']['d'] == 55 for s in self.bundles[tid])
        if dynamic:
            flags.append('population_dependent_cost_base_component_only')
        row = dict(civ_name=self.civ['name'], tech_id=tid, technology=self.label(tid),
                   raw_name=tech['name'], is_civ_unique=int(tech['civ'] >= 0),
                   free=int(free), instant=int(instant), automatic_free=int(free and instant),
                   selected_building_id=selected['building_id'] if selected else None,
                   base_seconds=selected['base_seconds'] if selected else None,
                   final_seconds=selected['final_seconds'] if selected else None,
                   cost_is_fixed=int(not dynamic), pricing_tech_ids=sorted(pricing_owners),
                   modifiers=modifiers, flags=sorted(set(flags)))
        for r in RES:
            row.update({f'base_{r}': clean(base[r]), f'upfront_{r}': cost[r],
                        f'reward_{r}': clean(reward[r]), f'net_{r}': clean(cost[r] - reward[r])})
        return row, routes

    def research_work_building(self, bid):
        """Resolve researched age forms, without changing the buildable family."""
        replacements = {}
        for source in self.commands:
            c = source['command']
            if source['tech_id'] in AGES and c['type'] == 3 and c['c'] in (-1, 0):
                if c['a'] in self.units and c['b'] in self.units and self.units[c['b']]['building']:
                    replacements[c['a']] = source
        seen, evidence = set(), []
        while bid in replacements and bid not in seen:
            seen.add(bid)
            source = replacements[bid]
            evidence.append(source)
            bid = source['command']['b']
        return bid, evidence

    def targets(self, uid):
        """Final forms and projectile forms; lineage is tracked separately."""
        if uid in self.target_cache:
            return self.target_cache[uid]
        final_forms, related = {uid}, set()
        self.form_evidence[uid] = []
        for tid in self.researchable:
            changes = [s for s in self.bundles[tid] if s['command']['type'] == 3 and s['command']['c'] in (-1, 0)]
            if not any(s['command']['b'] == uid for s in changes):
                continue
            for source in changes:
                target = source['command']['b']
                raw = self.units.get(target, {})
                if (target != uid and raw.get('type') == 70 and raw.get('class_id') not in ECONOMIC_CLASSES
                        and not any(x['unit_id'] >= 0 for x in raw.get('train_locations', []))):
                    final_forms.add(target)
                    self.form_evidence[uid].append(dict(source, target_unit_id=target,
                        reason='non_trainable_combat_form_upgraded_by_same_tier_technology'))
        queue = deque(final_forms)
        while queue:
            current = queue.popleft()
            if current in related or current not in self.links:
                continue
            related.add(current)
            u = self.links[current]
            for field in ('projectile_unit_id', 'secondary_projectile_unit', 'charge_projectile_unit'):
                target = u[field]
                if target in self.links and target not in related:
                    queue.append(target)
            for field in ('dead_unit_id', 'transform_unit'):
                target = u[field]
                v = self.links.get(target, {})
                if v.get('type') == 70 and v.get('hit_points', 0) > 0:
                    queue.append(target)
                    final_forms.add(target)
            if u['type'] == 60:
                queue.extend(self.forward_edges[current] | self.reverse_edges[current])
        lineage = set(final_forms)
        queue = deque(final_forms)
        while queue:
            for parent in self.reverse_edges[queue.popleft()]:
                # Conversions (e.g. villagers -> militia) are unlocks, not a
                # military tier chain. Do not inherit villagers' upgrades.
                if parent in self.links and self.links[parent]['class_id'] not in ECONOMIC_CLASSES and parent not in lineage:
                    lineage.add(parent)
                    queue.append(parent)
        self.target_cache[uid] = final_forms, related, lineage
        return self.target_cache[uid]

    def associations(self, uid, production_buildings):
        final_forms, targets, lineage = self.targets(uid)
        rows, candidates = {}, []
        for tid in sorted(self.researchable):
            direct, support, reasons, evidence, unresolved = False, False, set(), [], []
            for source in self.bundles[tid]:
                c = source['command']
                typ, a, b, attr = (c[k] for k in ('type', 'a', 'b', 'c'))
                reason = None
                if typ in OPS:
                    hit = any(a == target or (a == -1 and b == self.links[target]['class_id']) for target in targets if target in self.links)
                    if hit and attr not in PRESENTATION:
                        if attr in PRODUCTION:
                            support, reason = True, 'unit_production'
                        else:
                            direct, reason = True, 'unit_or_projectile_attribute'
                    elif hit and attr in PRODUCTION:
                        support, reason = True, 'production_location'
                    elif attr == 13 and a in production_buildings:
                        support, reason = True, 'production_building_work_rate'
                elif typ == 3 and b in lineage and attr in (-1, 0):
                    direct, reason = True, 'unit_line_upgrade'
                elif typ == 2 and a in final_forms and b != 0:
                    direct, reason = True, 'unit_unlock' if b == 1 else 'unit_unlock_special_command'
                    if b != 1:
                        unresolved.append(source)
                elif typ == 8 and a in final_forms:
                    unresolved.append(source)
                elif typ in (1, 6):
                    # Numeric player resources do not identify target units.
                    # Preserve them for review rather than inventing coverage.
                    if a in {27, 28, 29, 33, 176, 177, 178, 179, 180, 181, 182, 192, 193, 203, 277}:
                        unresolved.append(source)
                elif typ not in (101, 102, 103, 8) and a in targets:
                    unresolved.append(source)
            # Capture exact matching evidence in a compact second pass.
                if reason:
                    reasons.add(reason)
                    evidence.append(dict(source, association_reason=reason))
            if direct or support:
                rows[tid] = dict(scope='direct' if direct else 'production_support',
                                 reasons=sorted(reasons), evidence=evidence, flags=[])
            if unresolved:
                candidates.append(dict(tech_id=tid, sources=unresolved,
                                       already_direct=int(direct), reason='player_resource_or_special_command_scope_needs_review'))
        # Unit unlock shadow effects can be gated by a researchable technology
        # without that technology directly modifying the unit.
        pending = list(rows)
        while pending:
            tid = pending.pop()
            t = self.techs[tid]
            reqs = [i for i in t['required_techs'] if i >= 0 and i in self.active]
            research_reqs = [i for i in reqs if i in self.researchable]
            for req in research_reqs:
                if req not in rows:
                    rows[req] = dict(scope=rows[tid]['scope'], reasons=['research_prerequisite'],
                                     evidence=[dict(required_by=tid, required_tech_count=t['required_tech_count'], required_techs=t['required_techs'])], flags=[])
                    pending.append(req)
                elif rows[tid]['scope'] == 'direct':
                    rows[req]['scope'] = 'direct'
        return rows, candidates


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)


def choose_unit_routes(state, found, evaluated, route_map):
    """Minimum construction-cost cover; reuse buildings across researches."""
    already = set()
    result = {}
    for scope in ('direct', 'production_support'):
        tids = [tid for tid, row in found.items() if row['scope'] == scope]
        choices = {tid: {r['building_id'] for r in route_map[tid] if r['final_seconds'] is not None}
                   for tid in tids if not evaluated[tid]['automatic_free']}
        choices = {tid: bids for tid, bids in choices.items() if bids}
        forced = already | {next(iter(bids)) for bids in choices.values() if len(bids) == 1}
        optional = sorted(set().union(*choices.values()) - forced) if choices else []
        best, best_key = forced, None
        for n in range(len(optional) + 1):
            for subset in itertools.combinations(optional, n):
                selected = forced | set(subset)
                if any(not bids & selected for bids in choices.values()):
                    continue
                cost = sum(state.building(b)['wood_equivalent'] if state.building(b)['wood_equivalent'] is not None
                           else float('inf') for b in selected - already)
                time = sum(min(r['final_seconds'] for r in route_map[tid]
                               if r['building_id'] in selected and r['final_seconds'] is not None) for tid in choices)
                key = cost, len(selected - already), time, sorted(selected)
                if best_key is None or key < best_key:
                    best, best_key = selected, key
        for tid in tids:
            available = [r for r in route_map[tid] if r['final_seconds'] is not None]
            fitting = [r for r in available if r['building_id'] in best]
            if not fitting:
                fitting = [r for r in available if r['selected']] or available
            result[tid] = min(fitting, key=lambda r: (r['final_seconds'], r['building_id'])) if fitting else None
        already = best
    return result


def build(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.raw.read_text())
    links = json.loads(args.links.read_text())
    assert data['source']['sha256'] == links['source_sha256']
    assert hashlib.sha256(Path(data['source']['path']).read_bytes()).hexdigest() == data['source']['sha256']
    attach_game_trees(data, args.trees)
    prod = sqlite3.connect(f'file:{args.production.resolve()}?mode=ro', uri=True)
    prod.row_factory = sqlite3.Row
    evaluations = {r['civ_name']: dict(r) for r in prod.execute('select * from civilization_evaluation')}
    source_rows = [dict(r) for r in prod.execute('select * from source_unit_production')]
    advisor = [dict(r) for r in prod.execute('select * from unit_production')]
    production_buildings = defaultdict(set)
    for r in prod.execute('select civ_name,source_unit_id,building_id from source_trainable_routes'):
        production_buildings[(r['civ_name'], r['source_unit_id'])].add(r['building_id'])
    units = {}
    for r in source_rows:
        c, uid = r['civ_name'], r['source_unit_id']
        raw = data['civs'][c]['units'][str(uid)]
        if raw['class_id'] in ECONOMIC_CLASSES:
            continue
        units[(c, uid)] = dict(unit_key=f'{c}:{uid}', civ_name=c, unit_id=uid,
                              unit_name=r['unit_name'], unit_class=raw['class_id'],
                              advisor_reference_id=None, in_advisor_roster=0,
                              source_availability=r['availability_status'], flags=[])
    for r in advisor:
        c, uid = r['civ_name'], r['unit_id']
        raw = data['civs'][c]['units'][str(uid)]
        units.setdefault((c, uid), dict(unit_key=f'{c}:{uid}', civ_name=c, unit_id=uid,
                                       unit_name=r['unit_name'], unit_class=raw['class_id'],
                                       source_availability=r['status'], flags=[]))
        units[(c, uid)].update(advisor_reference_id=r['reference_unit_id'], in_advisor_roster=1, unit_name=r['unit_name'])
        if r['building_id'] is not None:
            production_buildings[(c, uid)].add(r['building_id'])
    unit_rows, upgrades, routes, buildings, associations, candidates, prerequisites = [], [], [], [], [], [], []
    unassociated = []
    for name in sorted(data['civs']):
        state = State(data, data['civs'][name], evaluations[name], links['civs'][str(data['civs'][name]['id'])])
        evaluated, route_map = {}, {}
        for tid in sorted(state.researchable):
            row, locations = state.evaluate(tid)
            evaluated[tid] = row
            route_map[tid] = locations
            upgrades.append(row)
            routes.extend(locations)
            t = state.techs[tid]
            for req in t['required_techs']:
                if req >= 0:
                    prerequisites.append(dict(civ_name=name, tech_id=tid, prerequisite_id=req,
                                              prerequisite_name=state.techs[req]['name'],
                                              required_count=t['required_tech_count'],
                                              prerequisite_available=int(req in state.active),
                                              is_researchable=int(req in state.researchable)))
        used = set()
        for (c, uid), unit in sorted(units.items()):
            if c != name:
                continue
            found, review = state.associations(uid, production_buildings[(name, uid)])
            forms, related, lineage = state.targets(uid)
            unit.update(related_unit_ids=sorted(related), unit_lineage_ids=sorted(lineage),
                        alternate_form_evidence=state.form_evidence[uid])
            if state.form_evidence[uid]:
                unit['flags'].append('alternate_form_link_inferred_from_shared_tier_upgrade')
            selected_routes = choose_unit_routes(state, found, evaluated, route_map)
            for tid, association in found.items():
                chosen = selected_routes[tid]
                associations.append(dict(unit_key=unit['unit_key'], civ_name=name, tech_id=tid,
                    selected_building_id=chosen['building_id'] if chosen else None,
                    selected_location_index=chosen['location_index'] if chosen else None,
                    final_seconds=chosen['final_seconds'] if chosen else None, **association))
                used.add(tid)
            for candidate in review:
                candidates.append(dict(unit_key=unit['unit_key'], civ_name=name, **candidate))
            if not found:
                unit['flags'].append('no_direct_or_support_upgrade_associations')
            unit_rows.append(unit)
        for tid in state.researchable - used:
            unassociated.append(dict(civ_name=name, tech_id=tid, technology=state.label(tid),
                                     effect_id=state.techs[tid]['effect_id'],
                                     explanation='No direct military target found; may be economic, building-only or require special-scope review'))
        buildings.extend(state.building_cache.values())
        print(f'{name}: {len(state.researchable)} researchable technologies', flush=True)
    # Keep all available tech definitions for reference, including explicitly
    # unassociated eco techs. Only unit_upgrades drives military cost totals.
    db_path = output / 'unit-upgrades.sqlite'
    temporary = output / 'unit-upgrades.build.sqlite'
    if temporary.exists():
        temporary.unlink()
    con = sqlite3.connect(temporary)
    tables = [('units', unit_rows), ('civilization_upgrades', upgrades), ('research_locations', routes),
              ('buildings', buildings), ('unit_upgrades', associations), ('unit_upgrade_candidates', candidates),
              ('tech_prerequisites', prerequisites), ('unassociated_technologies', unassociated)]
    for table, rows in tables:
        json_fields = [k for k in rows[0] if any(isinstance(r[k], (dict, list)) for r in rows)] if rows else []
        sql_table(con, table, rows, json_fields)
    sql_table(con, 'raw_technologies', [dict(tech_id=int(i), definition=t) for i, t in data['techs'].items()], ['definition'])
    sql_table(con, 'raw_effects', [dict(effect_id=int(i), definition=e) for i, e in data['effects'].items()], ['definition'])
    manifest = dict(source=data['source'], assumptions={
        'age': 'All upgrades priced in Imperial, including earlier tiers',
        'scope': 'Direct military attributes, unit cost, projectiles, tier/unlock chains and research prerequisites',
        'support': 'Production-only technologies recorded separately',
        'research_time': 'Independent final-condition building workload; own/dependent modifiers excluded; not an elapsed build order',
        'buildings': 'All available routes; minimum construction-cost building cover per unit by wood + 2*stone; reuse buildings; fastest route on ties',
        'free_instant': 'Retained in upgrade lists; no research-queue building charged unless otherwise needed',
        'resources': 'Food, wood, stone, gold separate; float costs preserved without inferred UI rounding',
        'unresolved': 'Player-resource and special effects with no explicit target retained in candidate table for owner review'},
        production_source=str(args.production.resolve()), raw_cache=str(args.raw.resolve()), links_source=str(args.links.resolve()))
    sql_table(con, 'metadata', [dict(key=k, value=v) for k, v in manifest.items()], ['value'])
    con.executescript('''
    CREATE UNIQUE INDEX units_key ON units(unit_key);
    CREATE UNIQUE INDEX upgrades_key ON civilization_upgrades(civ_name,tech_id);
    CREATE UNIQUE INDEX associations_key ON unit_upgrades(unit_key,tech_id);
    CREATE UNIQUE INDEX buildings_key ON buildings(civ_name,building_id);
    CREATE UNIQUE INDEX locations_key ON research_locations(civ_name,tech_id,location_index);
    CREATE INDEX candidate_unit ON unit_upgrade_candidates(unit_key);
    CREATE VIEW unit_research_buildings AS
      SELECT DISTINCT a.unit_key,a.scope,b.* FROM unit_upgrades a
      JOIN civilization_upgrades t ON a.civ_name=t.civ_name AND a.tech_id=t.tech_id
      JOIN buildings b ON b.civ_name=t.civ_name AND b.building_id=a.selected_building_id
      WHERE t.automatic_free=0;
    ''')
    technology_columns = ','.join('t.'+k for k in upgrades[0] if k not in ('selected_building_id','final_seconds'))
    con.execute(f'''CREATE VIEW unit_upgrade_data AS
      SELECT u.unit_key,u.unit_name,a.scope,a.reasons,a.evidence,a.selected_building_id,a.final_seconds,
             t.selected_building_id AS standalone_building_id,t.final_seconds AS standalone_final_seconds,{technology_columns},
             b.building_name,b.cost_food AS building_food,b.cost_wood AS building_wood,
             b.cost_stone AS building_stone,b.cost_gold AS building_gold,b.wood_equivalent AS building_wood_equivalent
      FROM unit_upgrades a JOIN units u USING(unit_key)
      JOIN civilization_upgrades t ON t.civ_name=a.civ_name AND t.tech_id=a.tech_id
      LEFT JOIN buildings b ON b.civ_name=t.civ_name AND b.building_id=a.selected_building_id''')
    con.executescript('''
    CREATE VIEW unit_building_workloads AS
      SELECT unit_key,scope,selected_building_id AS building_id,building_name,
             COUNT(*) AS upgrade_count,SUM(final_seconds) AS research_workload_seconds
      FROM unit_upgrade_data GROUP BY unit_key,scope,selected_building_id;
    ''')
    total_columns = ','.join(f'COALESCE(SUM(d.{prefix}_{r}),0) AS {prefix}_{r}' for prefix in ('base','upfront','reward','net') for r in RES)
    con.execute(f'''CREATE VIEW unit_upgrade_totals AS SELECT u.unit_key,u.civ_name,u.unit_name,s.scope,
                  COUNT(d.tech_id) AS upgrade_count,{total_columns},COALESCE(SUM(d.final_seconds),0) AS research_workload_seconds,
                  COALESCE(MIN(d.cost_is_fixed),1) AS all_costs_fixed,
                  SUM(d.tech_id IS NOT NULL AND d.final_seconds IS NULL) AS missing_research_times
                  FROM units u CROSS JOIN (SELECT 'direct' AS scope UNION ALL SELECT 'production_support') s
                  LEFT JOIN unit_upgrade_data d ON d.unit_key=u.unit_key AND d.scope=s.scope GROUP BY u.unit_key,s.scope''')
    con.execute('''CREATE VIEW unit_building_totals AS SELECT u.unit_key,s.scope,COUNT(b.building_id) AS building_count,
                COALESCE(SUM(cost_food),0) AS food,COALESCE(SUM(cost_wood),0) AS wood,
                COALESCE(SUM(cost_stone),0) AS stone,COALESCE(SUM(cost_gold),0) AS gold,
                COALESCE(SUM(wood_equivalent),0) AS wood_equivalent FROM units u
                CROSS JOIN (SELECT 'direct' AS scope UNION ALL SELECT 'production_support') s
                LEFT JOIN unit_research_buildings b ON b.unit_key=u.unit_key AND b.scope=s.scope GROUP BY u.unit_key,s.scope''')
    con.execute('''CREATE VIEW unit_all_building_totals AS SELECT u.unit_key,COUNT(b.building_id) AS building_count,
                COALESCE(SUM(cost_food),0) AS food,COALESCE(SUM(cost_wood),0) AS wood,
                COALESCE(SUM(cost_stone),0) AS stone,COALESCE(SUM(cost_gold),0) AS gold,
                COALESCE(SUM(wood_equivalent),0) AS wood_equivalent FROM units u LEFT JOIN
                (SELECT DISTINCT unit_key,civ_name,building_id,cost_food,cost_wood,cost_stone,cost_gold,wood_equivalent
                 FROM unit_research_buildings) b ON b.unit_key=u.unit_key GROUP BY u.unit_key''')
    con.commit()
    checks = validate(con, data, len(advisor))
    con.row_factory = sqlite3.Row
    for table in ['unit_upgrade_data', 'unit_upgrade_totals', 'unit_research_buildings', 'unit_building_totals', 'unit_all_building_totals', 'unit_building_workloads']:
        write_csv(output / (table.replace('_', '-') + '.csv'), [dict(r) for r in con.execute('select * from '+table)])
    write_csv(output / 'review-candidates.csv', [dict(r) for r in con.execute('''SELECT DISTINCT c.civ_name,c.tech_id,t.technology,c.reason,
                 COUNT(DISTINCT c.unit_key) AS candidate_units,MAX(c.already_direct) AS has_direct_unit_links
                 FROM unit_upgrade_candidates c JOIN civilization_upgrades t USING(civ_name,tech_id) GROUP BY c.civ_name,c.tech_id,c.reason''')])
    con.close()
    temporary.replace(db_path)
    manifest['counts'] = checks['counts']
    dump(output / 'manifest.json', manifest)
    dump(output / 'validation.json', checks)
    write_readme(output)
    print(json.dumps(checks, indent=2))


def validate(con, data, advisor_count):
    counts = {table: con.execute('select count(*) from '+table).fetchone()[0] for table in
              ['units','civilization_upgrades','unit_upgrades','research_locations','buildings','unit_upgrade_candidates']}
    checks = {'integrity': con.execute('pragma integrity_check').fetchone()[0] == 'ok',
              'all_advisor_units': con.execute('select count(*) from units where in_advisor_roster=1').fetchone()[0] == advisor_count,
              'civilizations': con.execute('select count(distinct civ_name) from units').fetchone()[0] == len(data['civs']),
              'association_foreign_keys': con.execute('''select count(*) from unit_upgrades a left join units u using(unit_key)
                   left join civilization_upgrades t on a.civ_name=t.civ_name and a.tech_id=t.tech_id
                   where u.unit_key is null or t.tech_id is null''').fetchone()[0] == 0,
              'nonnegative_cost_and_time': con.execute('''select count(*) from civilization_upgrades where upfront_food < -0.001
                   or upfront_wood < -0.001 or upfront_stone < -0.001 or upfront_gold < -0.001 or final_seconds < 0''').fetchone()[0] == 0}
    def tech(civ, tid):
        con.row_factory = sqlite3.Row
        return dict(con.execute('select * from civilization_upgrades where civ_name=? and tech_id=?',(civ,tid)).fetchone())
    s = tech('Spanish',75)
    checks['spanish_gold_reward'] = s['upfront_gold'] == 0 and s['reward_gold'] == 20
    b = tech('Burgundians',265)
    checks['burgundian_paladin_discount'] = b['upfront_food'] == 650 and b['upfront_gold'] == 375
    c = tech('Chinese',67)
    checks['chinese_imperial_discount_on_feudal_upgrade'] = abs(c['upfront_food'] - 127.5) < 0.001
    v = tech('Vietnamese',315)
    checks['vietnamese_free_conscription'] = v['automatic_free'] == 1
    g = tech('Goths',22)
    checks['goth_loom_is_paid_one_second'] = g['upfront_gold'] == 50 and g['final_seconds'] == 1
    checks['own_conscription_not_self_accelerated'] = abs(tech('Spanish',315)['final_seconds']-60) < 0.001
    checks['portuguese_research_duration'] = abs(tech('Portuguese',75)['final_seconds']-80) < 0.001
    checks['persian_imperial_tc_work_rate'] = abs(tech('Persians',213)['final_seconds']-62.5) < 0.001 and abs(tech('Persians',249)['final_seconds']-55/1.2) < 0.001
    checks['persian_imperial_dock_work_rate'] = abs(tech('Persians',65)['final_seconds']-25) < 0.001
    checks['bulgarian_blacksmith_work_rate'] = abs(tech('Bulgarians',75)['final_seconds']-100/1.8) < 0.001
    def associated(key, tid):
        return bool(con.execute('select 1 from unit_upgrades where unit_key=? and tech_id=?',(key,tid)).fetchone())
    checks['arbalester_ballistics_via_projectile'] = associated('Chinese:492',93)
    checks['arbalester_crossbow_prerequisite'] = associated('Chinese:492',100)
    checks['champion_tier_chain'] = all(associated('Spanish:567',i) for i in (222,207,217,264))
    checks['fortified_church_research_route'] = tech('Armenians',231)['selected_building_id'] == 1806
    checks['konnik_reuses_required_castle'] = con.execute("select selected_building_id from unit_upgrades where unit_key='Bulgarians:1227' and tech_id=678").fetchone()[0] == 82
    checks['konnik_secondary_form_armor'] = all(associated('Bulgarians:1227', i) for i in (74,76,77))
    checks['flemish_unlock_cost_flagged'] = associated('Burgundians:1699',755) and tech('Burgundians',755)['cost_is_fixed'] == 0
    checks['all_research_times_present'] = con.execute('select count(*) from civilization_upgrades where final_seconds is null').fetchone()[0] == 0
    checks['totals_include_zero_upgrade_units'] = con.execute("select count(*) from unit_upgrade_totals where scope='direct'").fetchone()[0] == counts['units']
    checks['no_economic_tech_in_military_totals'] = con.execute('select count(*) from unit_upgrades where tech_id in (12,13,14,55,213,249,278,279,202,203,221)').fetchone()[0] == 0
    verified_commands = 0
    for table, field in [('civilization_upgrades','modifiers'),('research_locations','work_rate_modifiers'),
                         ('buildings','modifiers'),('unit_upgrades','evidence')]:
        for (encoded,) in con.execute(f'select {field} from {table}'):
            for source in json.loads(encoded):
                if 'command' not in source:
                    continue
                assert data['effects'][str(source['effect_id'])]['effect_commands'][source['command_index']] == source['command']
                verified_commands += 1
    checks['modifier_commands_match_source'] = verified_commands > 0
    failures = [name for name, ok in checks.items() if not ok]
    if failures:
        raise AssertionError(f'Validation failed: {failures}')
    return dict(counts=counts, checks=checks, verified_source_commands=verified_commands, all_passed=True)


def write_readme(output):
    (output / 'README.md').write_text('''# Military upgrade review database

Source: the user-supplied empires2_x2_p1.dat and matching CivTechTrees JSON files.
The manifest records the source checksum and paths. The accepted production
review supplies the resolved availability snapshot and comparison roster.

All upgrade costs use Imperial modifiers, including earlier-tier upgrades.
Food, wood, stone and gold are separate. Upfront cost, completion reward and net
cost are separate. Fractional calculations are retained; integer UI rounding
has not been inferred. Spanish rewards follow the DAT reward-effect pointer.

## Tables and views

- units: military units by civilization, including the entire advisor roster.
- civilization_upgrades: all available research definitions and final prices.
  Economic definitions remain reference-only; they are not associated to units.
- unit_upgrades: one row per unit/technology, direct or production_support.
- unit_upgrade_data: readable joined view, including selected building cost.
- unit_upgrade_totals: resource totals by unit and scope.
- research_locations: every available research route and per-route duration.
- buildings: base/final construction costs and exact modifier provenance.
- unit_research_buildings / unit_building_totals: distinct selected buildings;
  one building is charged once even if many upgrades use it. Automatic free
  upgrades retain their nominal research building but do not charge a queue.
- unit_building_workloads: research seconds grouped by building and scope.
- tech_prerequisites: original gate IDs, required count and availability.
- unit_upgrade_candidates: unresolved player-resource or special-effect scope;
  these are review candidates, not silently charged to the unit.
- raw_technologies / raw_effects: source definitions for auditing.

Direct associations follow final-unit/class attributes, projectile effects,
living alternate forms, unit-tier/unlock effects and research prerequisites.
Non-trainable combat forms upgraded by the same tier technology are linked with
an explicit inference flag and raw command evidence (including dismounted Konnik).
Unit cost changes are direct; production-only changes are a separate scope.
Civilian economy units are excluded. Packed/deployed aliases can have separate
rows when needed to retain all advisor identities; do not sum unit rows together.

Research time is an independent post-Imperial building workload. Available
work-rate upgrades apply except the target research's own dependent effects.
Paid speed modifiers and a duration without paid work-rate bonuses are recorded.
This is not an elapsed build order: queues can overlap and prerequisites/order
matter. All available modifiers are assumed active; their conditions remain
visible, even when an economic/production support technology is outside the
direct military upgrade package.

Standalone research routes use the cheapest building by wood + 2*stone, then
fastest time. Per-unit selections minimize the combined construction cost and
reuse already-required buildings: a Castle needed for Stirrups also handles the
Elite Konnik upgrade, avoiding an unnecessary Krepost charge. All alternatives
are retained. unit_all_building_totals deduplicates across both scopes as well.
Costs are construction costs, excluding age-up
fees, construction time and other buildings needed to unlock construction.
Population-dependent research prices retain the base component and are flagged;
totals with all_costs_fixed=0 require a scenario input before use as a final bill.

Comparison: join two unit_upgrades sets on tech_id for common upgrades. Compare
their cost and time rows; retain left-only and right-only upgrades separately.
Free upgrades stay in those sets. Never normalize by army size or rank with an
arbitrary threshold. Compare the direct and production_support scopes separately.

See validation.json for source-backed regression checks and coverage. This is a
review artifact; unresolved candidates should be reviewed before advisor use.

## Rebuild and compare

Run tools/build_upgrade_review.py in the advisor worktree. The CLI accepts raw
extraction, same-install trees, production review and unit-link cache paths.
Use --extract-links with the genieutils virtualenv to regenerate unit links from
the DAT. Run tools/compare_unit_upgrades.py Spanish:567 Goths:567 to obtain common
upgrade costs/times and separate one-sided upgrade bills. Technology IDs, rather
than localized names, define the intersection. comparison-example.json shows it.
''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=DEFAULT / 'current-raw-source.json')
    parser.add_argument('--trees', type=Path, default=DEFAULT / 'current-input/dat/CivTechTrees')
    parser.add_argument('--production', type=Path, default=DEFAULT / 'current-results/production-review.sqlite')
    parser.add_argument('--links', type=Path, default=scratch_path('research-review/unit-research-links.json'))
    parser.add_argument('--output', type=Path, default=scratch_path('research-review/current-results'))
    parser.add_argument('--extract-links', action='store_true', help='Refresh raw unit/projectile/form links using genieutils in its venv')
    args = parser.parse_args()
    if args.extract_links:
        raw = json.loads(args.raw.read_text())
        extract_links(dat_path(raw), args.links)
    build(args)
