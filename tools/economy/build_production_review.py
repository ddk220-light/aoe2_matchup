#!/usr/bin/env python3
"""Build a disposable, source-derived Imperial production review database.

First-pass rules: raw civilization/team effects, prerequisite-resolved standard
and unique technologies, attribute set/add/multiply, actual training locations,
and wood + 2*stone building ranking. Unknowns remain visible for owner review.
The reference DB supplies the comparison roster and display labels ONLY.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGES = (104, 101, 102, 103)
ATTRS = {13: "work_rate", 101: "train_time", 100: "all_costs",
         103: "food", 104: "wood", 105: "gold", 106: "stone"}
RESOURCES = {0: "food", 1: "wood", 2: "stone", 3: "gold"}
OPS = {0: "set", 4: "add", 5: "multiply", 10: "set", 14: "add", 15: "multiply"}
BUILDINGS = {12: "Barracks", 20: "Barracks", 87: "Archery Range", 101: "Stable",
             86: "Stable", 153: "Stable", 49: "Siege Workshop", 82: "Castle",
             104: "Monastery", 109: "Town Center", 621: "Town Center", 45: "Dock",
             84: "Market", 1251: "Krepost", 1665: "Donjon"}


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def extract(path):
    from genieutils.datfile import DatFile
    data = DatFile.parse(path)
    module = ast.parse((ROOT / "aoe2x/extract/extract_constants.py").read_text())
    labels = next(ast.literal_eval(n.value) for n in module.body
                  if isinstance(n, ast.Assign) and any(
                      isinstance(t, ast.Name) and t.id == "CIV_NAMES" for t in n.targets))
    civs = {}
    for cid, c in enumerate(data.civs):
        if not cid or cid >= len(labels) or not labels[cid]:
            continue
        units = {}
        for uid, u in enumerate(c.units):
            if not u or not u.creatable:
                continue
            units[str(uid)] = {
                "id": uid, "name": u.name, "class_id": u.class_, "type": u.type,
                "enabled": u.enabled, "copy_id": u.copy_id, "base_id": u.base_id,
                "language_dll_name": u.language_dll_name, "icon_id": u.icon_id,
                "work_rate": u.bird.work_rate if u.bird else None,
                "costs": [asdict(x) for x in u.creatable.resource_costs],
                "train_locations": [asdict(x) for x in u.creatable.train_locations],
                "building": {**{k: getattr(u.building, k) for k in
                    ("tech_id", "head_unit", "stack_unit_id", "transform_unit")},
                    "annexes": [asdict(x) for x in u.building.annexes]}
                    if u.building else None,
            }
        civs[labels[cid]] = {"id": cid, "name": labels[cid], "raw_name": c.name,
                             "tree_id": c.tech_tree_id, "team_id": c.team_bonus_id,
                             "units": units}
    return {"source": {"path": str(path.resolve()), "format_version": data.version,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "game_patch": "unknown; binary format does not identify patch"},
            "civs": civs, "techs": {str(i): asdict(t) for i, t in enumerate(data.techs)},
            "effects": {str(i): asdict(e) for i, e in enumerate(data.effects)}}


def match(cmd, unit):
    return cmd["a"] == unit["id"] or (cmd["a"] == -1 and cmd["b"] == unit["class_id"])


def apply(value, cmd):
    op = OPS[cmd["type"]]
    return cmd["d"] if op == "set" else value + cmd["d"] if op == "add" else value * cmd["d"]


def costs(unit):
    result = dict.fromkeys(RESOURCES.values(), 0.0)
    for c in unit["costs"]:
        if c["type"] in RESOURCES:
            result[RESOURCES[c["type"]]] += c["amount"]
    return result


def attach_game_trees(data, directory):
    """Read same-install availability/labels; values still come from the DAT."""
    aliases = {"Hindustanis": "INDIANS", "Magyars": "MAGYAR"}
    for name, civ in data["civs"].items():
        path = directory / (aliases.get(name, name.upper()) + ".json")
        if path.exists():
            civ["game_tree"] = json.loads(path.read_text())
            civ["game_tree_source"] = str(path.resolve())
    data["source"]["game_tree_directory"] = str(directory.resolve())
    data["source"]["game_tree_count"] = sum("game_tree" in c for c in data["civs"].values())



def prerequisites_met(tech, active):
    """Genie prerequisite rule: ``required_tech_count`` of the listed techs must be active.

    A count of 0 means "no prerequisite", whatever the slots contain (the only
    non-empty such slot in this DAT is tech 0, the dummy "New Research"); -1 is
    empty. No tech with a positive count lists slot 0, so that rule is unchanged.
    (Fixed 2026-11-12: the earlier rule read count 0 as "all listed slots", so a
    slot holding 0 blocked e.g. the Danes +5% food drop-off bonus, tech 1494.)
    """
    count = tech["required_tech_count"]
    if count <= 0:
        return True
    return sum(r in active for r in tech["required_techs"] if r >= 0) >= count

class CivState:
    def __init__(self, data, civ):
        self.data, self.civ = data, civ
        self.units = {int(k): u for k, u in civ["units"].items()}
        self.techs = {int(k): t for k, t in data["techs"].items()}
        self.active, self.disabled = set(), set()
        tree = civ.get("game_tree", {})
        self.tree_units = {n["Node ID"]: n for n in tree.get("civ_techs_units", []) if n.get("Use Type") == "Unit"}
        self.tree_buildings = {n["Node ID"]: n for n in tree.get("civ_techs_buildings", [])}
        self.tree_techs = {n["Node ID"]: n for n in tree.get("civ_techs_units", []) if n.get("Use Type") == "Tech"}
        self.tree_granted = {tid for tid, n in self.tree_techs.items() if n["Node Status"] != "NotAvailable"}
        self.tree_granted.update(n["Trigger Tech ID"] for n in self.tree_units.values()
                                 if n["Node Status"] != "NotAvailable" and n.get("Trigger Tech ID", -1) >= 0)
        self.tree_blocked = {tid for tid, n in self.tree_techs.items() if n["Node Status"] == "NotAvailable"}
        self.tree_blocked.update(n["Trigger Tech ID"] for n in self.tree_units.values()
                                 if n["Node Status"] == "NotAvailable" and n.get("Trigger Tech ID", -1) >= 0)
        self.tree_blocked -= self.tree_granted
        self.enabled = {uid for uid, u in self.units.items() if u["enabled"] == 1}
        self.edges, self.commands, self.special, self.tech_log = [], [], [], []
        self.activation = defaultdict(list)
        self.effect(civ["tree_id"], "civilization", None)
        self.effect(civ["team_id"], "own_team_bonus", None)
        self.disabled.update(self.tree_blocked)
        for age_number, age in enumerate(AGES, 1):
            self.fire(age, "age")
            for uid, node in self.tree_units.items():
                if node["Node Status"] != "NotAvailable" and node.get("Age ID", 1) <= age_number:
                    self.enabled.add(uid)
            for bid, node in self.tree_buildings.items():
                if node["Node Status"] != "NotAvailable" and node.get("Age ID", 1) <= age_number:
                    self.enabled.add(bid)
            while True:
                previous = len(self.active)
                self.building_events()
                for tid, t in self.techs.items():
                    if tid in self.active or tid in self.disabled or tid in AGES:
                        continue
                    if t["civ"] not in {-1, civ["id"]} or t["full_tech_mode"] not in {0, 1}:
                        continue
                    if not any(loc["location_id"] >= 0 for loc in t["research_locations"]) and not self.hidden_tech_is_automatic(tid):
                        continue
                    if prerequisites_met(t, self.active):
                        self.fire(tid, "technology")
                # The game ships regional grants and available upgrades outside
                # the DAT. In this fully researched scenario, stage those grants
                # by their explicit age instead of guessing regional civ rules.
                for node in list(self.tree_units.values()) + list(self.tree_techs.values()):
                    if node["Node Status"] == "NotAvailable" or node.get("Age ID", 1) > age_number:
                        continue
                    tid = node["Node ID"] if node.get("Use Type") == "Tech" else node.get("Trigger Tech ID", -1)
                    if tid in self.tree_granted:
                        self.fire(tid, "game_tree_grant")
                if len(self.active) == previous:
                    break
        self.final_units = set()
        for uid in self.enabled:
            current = uid
            for a, b in self.edges:
                if a == current:
                    current = b
            self.final_units.add(current)
        self.attributes = [s for s in self.commands if s["command"]["type"] in OPS
                           and s["command"]["c"] in ATTRS]
        self.groups = self.make_groups()
        if self.tree_units:
            available = {uid for uid, node in self.tree_units.items() if node["Node Status"] != "NotAvailable"}
            self.final_units = {uid for uid in self.final_units
                                if (uid in available or (uid not in self.tree_units
                                    and any(i in available for i in self.groups.get(uid, []))))
                                or not self.is_production_unit(self.units.get(uid, {"train_locations": []}))}
        self._location_cache = {}

    def hidden_tech_is_automatic(self, tid):
        """Dummy research costs/times gate hidden team and campaign technologies.

        They are automatic only after the relevant effect makes them free and
        instantaneous. Explicit building-completion and shipped-tree grants
        still call fire() directly.
        """
        tech = self.techs[tid]
        price = {r["type"]: float(r["amount"]) for r in tech["resource_costs"]
                 if r["type"] >= 0 and r["flag"]}
        times = [float(loc["research_time"]) for loc in tech["research_locations"]]
        for source in self.commands:
            cmd = source["command"]
            if cmd["type"] not in {101, 103} or cmd["a"] not in {tid, -1}:
                continue
            def change(value):
                return cmd["d"] if cmd["c"] == 0 else value * cmd["d"] if cmd["c"] == 2 else value + cmd["d"]
            if cmd["type"] == 101:
                for resource in price:
                    if cmd["b"] in {resource, -1}:
                        price[resource] = change(price[resource])
            else:
                times = [change(value) for value in times]
        return all(value <= 1e-6 for value in price.values()) and all(value <= 1e-6 for value in times)

    def effect(self, eid, kind, tid):
        if eid < 0 or str(eid) not in self.data["effects"]:
            return
        effect = self.data["effects"][str(eid)]
        for index, cmd in enumerate(effect["effect_commands"]):
            source = {"source_kind": kind, "tech_id": tid, "effect_id": eid,
                      "effect_name": effect["name"], "command_index": index,
                      "command": cmd, "civ_specific": kind in {"civilization", "own_team_bonus"}
                      or (tid is not None and self.techs[tid]["civ"] == self.civ["id"])}
            self.commands.append(source)
            if cmd["type"] == 102:
                if int(cmd["d"]) not in self.tree_granted:
                    self.disabled.add(int(cmd["d"]))
            elif cmd["type"] == 2 and cmd["b"] in {0, 1}:
                if cmd["b"] == 1:
                    self.enabled.add(cmd["a"])
                    self.activation[cmd["a"]].append(source)
                else:
                    self.enabled.discard(cmd["a"])
            elif cmd["type"] == 3 and cmd["c"] in {-1, 0}:
                self.edges.append((cmd["a"], cmd["b"]))
                self.activation[cmd["b"]].append(source)
            elif cmd["type"] in {7, 12, 26} or (cmd["type"] == 3 and cmd["c"] not in {-1, 0}) or (cmd["type"] == 2 and cmd["b"] not in {0, 1}):
                self.special.append(source)

    def fire(self, tid, reason):
        if tid in self.active or tid in self.disabled or tid not in self.techs:
            return
        self.active.add(tid)
        t = self.techs[tid]
        self.tech_log.append({"tech_id": tid, "name": t["name"], "reason": reason,
                              "required_techs": t["required_techs"],
                              "required_tech_count": t["required_tech_count"]})
        self.effect(t["effect_id"], reason, tid)

    def building_events(self):
        # Fully developed economy: enabled constructible buildings can be built.
        # Their explicit DAT completion markers also unlock shadow technologies.
        todo = [uid for uid in self.enabled if uid in self.units and self.units[uid]["building"]
                and any(l["unit_id"] >= 0 and l["button_id"] > 0 for l in self.units[uid]["train_locations"])]
        seen = set()
        while todo:
            uid = todo.pop()
            if uid in seen or uid not in self.units:
                continue
            seen.add(uid)
            b = self.units[uid]["building"]
            if not b:
                continue
            if b["tech_id"] >= 0:
                self.fire(b["tech_id"], "building_completion")
            todo.extend([b["stack_unit_id"], b["head_unit"]])
            todo.extend(a["unit_id"] for a in b["annexes"])

    def is_production_unit(self, unit):
        return any(l["unit_id"] in self.units and self.units[l["unit_id"]]["type"] == 80
                   and l["train_time"] > 0 for l in unit["train_locations"])

    def training_locations(self, uid):
        if uid in self._location_cache:
            return self._location_cache[uid]
        unit = self.units[uid]
        result = [dict(loc, location_effects=[]) for loc in unit["train_locations"]]
        selected = 0
        selector_source = None
        for source in self.commands:
            cmd = source["command"]
            if cmd["type"] not in OPS or not match(cmd, unit):
                continue
            if cmd["c"] == 158:
                selected = int(apply(selected, cmd))
                selector_source = source
            elif cmd["c"] in {42, 43} and 0 <= selected < len(result):
                key = "unit_id" if cmd["c"] == 42 else "button_id"
                before = result[selected][key]
                after = int(apply(before, cmd))
                result[selected][key] = after
                if before != after:
                    result[selected]["location_effects"].append(dict(source,
                        target="production_location" if key == "unit_id" else "production_button",
                        before=before, after=after, location_index=selected,
                        selector_effect=selector_source))
        self._location_cache[uid] = result
        return result

    def make_groups(self):
        parent = {uid: uid for uid, u in self.units.items() if self.is_production_unit(u)}
        def find(uid):
            while parent[uid] != uid:
                parent[uid] = parent[parent[uid]]
                uid = parent[uid]
            return uid
        def union(a, b):
            if a in parent and b in parent:
                parent[find(b)] = find(a)
        names = {}
        for uid in parent:
            u = self.units[uid]
            key = (u["language_dll_name"], u["class_id"], u["icon_id"])
            if key[0] > 0:
                if key in names:
                    union(names[key], uid)
                names[key] = uid
            if u["building"]:
                union(uid, u["building"]["transform_unit"])
        groups = defaultdict(list)
        for uid in parent:
            groups[find(uid)].append(uid)
        return {uid: sorted(group) for group in groups.values() for uid in group}

    def route(self, uid, index):
        unit = self.units[uid]
        loc = self.training_locations(uid)[index]
        bid = loc["unit_id"]
        building = self.units[bid]
        cost_building = building
        seen = set()
        while cost_building["building"] and cost_building["building"]["head_unit"] in self.units:
            if cost_building["id"] in seen:
                break
            seen.add(cost_building["id"])
            cost_building = self.units[cost_building["building"]["head_unit"]]
        time, rate = float(loc["train_time"]), building["work_rate"]
        base_cost = costs(cost_building)
        final_cost = dict(base_cost)
        applied = list(loc["location_effects"])
        for source in self.attributes:
            c = source["command"]
            target, before, after = None, None, None
            if c["c"] == 101 and match(c, unit):
                target, before = "unit_training_time", time
                time = after = apply(time, c)
            elif c["c"] == 13 and match(c, building) and rate is not None:
                target, before = "production_building_work_rate", rate
                rate = after = apply(rate, c)
            elif c["c"] in {100, 103, 104, 105, 106} and match(c, cost_building):
                target, before = "building_cost", dict(final_cost)
                keys = list(final_cost) if c["c"] == 100 else [ATTRS[c["c"]]]
                for key in keys:
                    final_cost[key] = apply(final_cost[key], c)
                after = dict(final_cost)
            if target and before != after:
                applied.append(dict(source, target=target, before=before, after=after))
        flags = []
        if uid not in self.final_units:
            flags.append("unit_not_resolved_as_trainable_in_final_source_state")
        if bid not in self.enabled and bid not in self.final_units:
            flags.append("production_building_availability_needs_review")
        if bid in self.tree_buildings and self.tree_buildings[bid]["Node Status"] == "NotAvailable":
            flags.append("production_building_availability_needs_review")
        seconds = time / rate if rate and rate > 0 and time > 0 else None
        if seconds is None:
            flags.append("invalid_or_instant_production_time")
        weighted = final_cost["wood"] + 2 * final_cost["stone"]
        if final_cost["food"] or final_cost["gold"]:
            weighted = None
            flags.append("building_food_or_gold_weight_unspecified")
        special = [s for s in self.special if s["command"]["a"] in {uid, bid}
                   or (s["command"]["type"] == 3 and s["command"]["b"] == uid)]
        if special:
            flags.append("special_production_or_transformation_effect_review")
        return {"source_unit_id": uid, "source_unit_name": unit["name"],
                "building_id": bid, "building": BUILDINGS.get(bid, building["name"]),
                "building_cost_unit_id": cost_building["id"], "location_index": index,
                "base_train_seconds": loc["train_time"], "modified_train_seconds": time,
                "base_building_work_rate": building["work_rate"], "final_building_work_rate": rate,
                "final_train_seconds": seconds, "units_per_game_minute": 60 / seconds if seconds else None,
                **{"base_building_" + k: v for k, v in base_cost.items()},
                **{"building_" + k: v for k, v in final_cost.items()},
                "building_wood_equivalent": weighted, "applied": applied,
                "activation": self.activation[uid], "special": special, "flags": flags}


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sql_table(con, name, rows, json_fields=()):
    if not rows:
        return
    fields = list(rows[0])
    types = {}
    for k in fields:
        values = [r[k] for r in rows if r[k] is not None]
        types[k] = "TEXT" if k in json_fields or any(isinstance(v, (str, list, dict)) for v in values) else "REAL" if any(isinstance(v, float) for v in values) else "INTEGER"
    con.execute(f'CREATE TABLE "{name}" (' + ", ".join(f'"{k}" {types[k]}' for k in fields) + ")")
    con.executemany(f'INSERT INTO "{name}" VALUES (' + ",".join("?" for _ in fields) + ")",
                    [[json.dumps(r[k], ensure_ascii=False) if k in json_fields else r[k] for k in fields] for r in rows])


def build(data, reference, output, labels=None):
    output.mkdir(parents=True, exist_ok=True)
    ref = sqlite3.connect(f"file:{reference.resolve()}?mode=ro", uri=True)
    ref.row_factory = sqlite3.Row
    roster = [dict(r) for r in ref.execute("SELECT id AS reference_unit_id,civ_name,unit_name,unit_master AS unit_id,base_train_time AS reference_base_train_seconds FROM ref_units ORDER BY civ_name,unit_name")]
    ref.close()
    names = {r["unit_id"]: r["unit_name"] for r in roster}
    roster_pairs = {(r["civ_name"], r["unit_id"]) for r in roster}
    by_civ = defaultdict(list)
    for r in roster:
        by_civ[r["civ_name"]].append(r)
    labels = labels or {}
    rows, routes, modifiers, evaluations, special_effects = [], [], [], [], []
    states = {}
    for civ_name, requested in sorted(by_civ.items()):
        c = data["civs"].get(civ_name)
        state = CivState(data, c) if c else None
        if state:
            states[civ_name] = state
            evaluations.append({"civ_name": civ_name, "source_civ_id": c["id"],
                                "active_technologies": state.tech_log,
                                "disabled_technologies": sorted(state.disabled),
                                "resolved_final_unit_ids": sorted(state.final_units)})
            special_effects.extend({"civ_name": civ_name, **s} for s in state.special)
        for requested_unit in requested:
            uid = requested_unit["unit_id"]
            flags, available_routes = [], []
            if not state:
                flags.append("civilization_missing_from_source")
            elif uid not in state.units:
                flags.append("unit_missing_from_source")
            else:
                candidates = state.groups.get(uid, [uid])
                active_candidates = [i for i in candidates if i in state.final_units]
                # Keep calculable unresolved rows for owner review instead of dropping them.
                # Current DAT units carry all training locations themselves.
                # Prefer the requested identity over legacy/limited-use clones.
                chosen_candidates = ([uid] if uid in active_candidates and c.get("game_tree")
                                     else active_candidates or [uid])
                if not active_candidates:
                    flags.append("unit_availability_needs_review")
                for candidate in chosen_candidates:
                    for index, loc in enumerate(state.training_locations(candidate)):
                        if loc["unit_id"] not in state.units or state.units[loc["unit_id"]]["type"] != 80 or loc["train_time"] <= 0:
                            continue
                        if loc["button_id"] <= 0 and active_candidates:
                            continue
                        route = state.route(candidate, index)
                        route.update({"route_id": len(routes) + len(available_routes) + 1,
                                      "reference_unit_id": requested_unit["reference_unit_id"],
                                      "civ_name": civ_name, "unit_name": requested_unit["unit_name"],
                                      "selected": 0})
                        if candidate != uid:
                            route["flags"].append("alternate_form_linked_by_DAT_identity_or_transform")
                        available_routes.append(route)
                if not available_routes:
                    flags.append("no_production_building_route")
            eligible = [r for r in available_routes if r["final_train_seconds"] is not None and r["building_wood_equivalent"] is not None]
            known_buildings = [r for r in eligible if "production_building_availability_needs_review" not in r["flags"]]
            eligible = known_buildings or eligible
            best = min(eligible, key=lambda r: (r["building_wood_equivalent"], r["final_train_seconds"], r["building_id"], r["source_unit_id"])) if eligible else None
            if best:
                best["selected"] = 1
                flags.extend(best["flags"])
                if not math.isclose(best["base_train_seconds"], requested_unit["reference_base_train_seconds"], abs_tol=1e-5):
                    flags.append("source_base_time_differs_from_current_reference")
            for route in available_routes:
                for order, m in enumerate(route["applied"]):
                    modifiers.append({"route_id": route["route_id"], "step": order, "civ_name": civ_name,
                                      "unit_name": requested_unit["unit_name"], **m})
                routes.append(route)
            applied = best["applied"] if best else []
            rows.append({**requested_unit, "status": "missing_source" if not state or uid not in state.units else "needs_review" if flags else "calculated",
                         "selected_route_id": best["route_id"] if best else None,
                         "source_unit_id": best["source_unit_id"] if best else None,
                         "source_unit_name": best["source_unit_name"] if best else None,
                         "building": best["building"] if best else None,
                         "building_id": best["building_id"] if best else None,
                         "base_train_seconds": best["base_train_seconds"] if best else None,
                         "final_train_seconds": best["final_train_seconds"] if best else None,
                         "units_per_game_minute": best["units_per_game_minute"] if best else None,
                         "final_building_work_rate": best["final_building_work_rate"] if best else None,
                         **{k: best[k] if best else None for k in ["building_food", "building_wood", "building_stone", "building_gold", "building_wood_equivalent"]},
                         "production_building_count": len({r["building_id"] for r in known_buildings}),
                         "applied_modifiers": "; ".join(f"{m['effect_name']} [effect {m['effect_id']}, command {m['command_index']}]: {m['target']} {OPS[m['command']['type']]} {m['command']['d']:.7g}" for m in applied),
                         "review_flags": "; ".join(sorted(set(flags)))})
        print(f"{civ_name}: {len(requested)} roster rows", flush=True)
    # Also expose every raw trainable form the source resolver reaches, including
    # economic units and variants outside the current combat-only comparison roster.
    source_units = []
    for ev in evaluations:
        c = data["civs"][ev["civ_name"]]
        state = states[ev["civ_name"]]
        for uid in sorted(state.final_units):
            u = state.units.get(uid)
            if not u or not state.is_production_unit(u):
                continue
            for index, loc in enumerate(state.training_locations(uid)):
                if loc["unit_id"] not in state.units or state.units[loc["unit_id"]]["type"] != 80 or loc["train_time"] <= 0 or loc["button_id"] <= 0:
                    continue
                tree_name = state.tree_units.get(uid, {}).get("Name")
                display_name = " ".join((tree_name or labels.get(str(u["language_dll_name"]), names.get(uid, u["name"]))).split())
                source_units.append({"civ_name": c["name"], "unit_name": display_name,
                                     "availability_status": "game_tree_and_DAT_first_pass" if c.get("game_tree") else "first_pass_candidate",
                                     "in_advisor_roster": int((c["name"], uid) in roster_pairs),
                                     "in_game_tree": int(uid in state.tree_units),
                                     "source_group_id": min(state.groups.get(uid, [uid])),
                                     **state.route(uid, index)})
    source_groups = defaultdict(list)
    for row in source_units:
        if "production_building_availability_needs_review" not in row["flags"]:
            source_groups[(row["civ_name"], row["source_group_id"])].append(row)
    source_cheapest = []
    for group in source_groups.values():
        canonical = [r for r in group if r["in_game_tree"]]
        group = canonical or group
        eligible = [r for r in group if r["building_wood_equivalent"] is not None and r["final_train_seconds"] is not None]
        if eligible:
            cheapest = min(eligible, key=lambda r: (r["building_wood_equivalent"], r["final_train_seconds"], r["building_id"], r["source_unit_id"]))
            source_cheapest.append(dict(cheapest, production_building_count=len({r["building_id"] for r in eligible})))
    metadata = {"source": data["source"], "reference_roster": str(reference.resolve()),
                "reference_used_for": "roster, comparison base time, display labels only; never production modifiers or costs",
                "display_labels": "Supplied game tech trees, advisor roster labels, and raw internal names; optional labels only when explicitly supplied",
                "scenario": "fully researched Imperial; own team bonus; enabled buildings built; normal game modes 0/1",
                "selection": "minimum wood + 2*stone; ties choose faster training then lower building/unit IDs",
                "source_version_warning": "Source provenance is recorded above; binary format alone does not establish the game build. No outside game values used.",
                "assumptions": ["Reference unit rows unresolved by DAT are calculated provisionally and explicitly flagged.",
                    "Alternate forms linked by shared language-name ID, class and icon, or explicit transform pointer.",
                    "One-time transformations/spawns and unsupported commands are retained for review, not treated as repeatable queues.",
                    "The broader source inventory has provisional availability; the first-pass resolver can over-include ally-granted or otherwise conditional units. The advisor comparison roster stays fixed.",
                    "Building construction labor, unlock research cost/time, travel time, resource shortages, other allies excluded.",
                    "Nonzero food/gold building costs have no specified weight, so cannot be ranked."],
                "row_count": len(rows), "calculated_time_count": sum(r["final_train_seconds"] is not None for r in rows),
                "missing_source_count": sum(r["status"] == "missing_source" for r in rows),
                "review_flagged_count": sum(r["status"] == "needs_review" for r in rows),
                "source_civilization_count": len(evaluations), "roster_civilization_count": len(by_civ),
                "production_route_count": len(routes), "source_trainable_route_count": len(source_units),
                "source_unit_group_count": len(source_cheapest)}
    db = output / "production-review.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    sql_table(con, "metadata", [{"key": k, "value": json.dumps(v)} for k, v in metadata.items()])
    sql_table(con, "unit_production", rows)
    sql_table(con, "production_routes", routes, ("applied", "activation", "special", "flags"))
    sql_table(con, "applied_modifiers", modifiers, ("command", "before", "after"))
    sql_table(con, "civilization_evaluation", evaluations, ("active_technologies", "disabled_technologies", "resolved_final_unit_ids"))
    sql_table(con, "special_effects_review", special_effects, ("command",))
    sql_table(con, "source_trainable_routes", source_units, ("applied", "activation", "special", "flags"))
    sql_table(con, "source_unit_production", source_cheapest, ("applied", "activation", "special", "flags"))
    sql_table(con, "raw_effects", [{"effect_id": int(eid), "name": e["name"], "commands": e["effect_commands"]} for eid, e in data["effects"].items()], ("commands",))
    sql_table(con, "raw_technologies", [{"tech_id": int(tid), "definition": t} for tid, t in data["techs"].items()], ("definition",))
    con.execute("CREATE UNIQUE INDEX production_roster_id ON unit_production(reference_unit_id)")
    con.execute("CREATE UNIQUE INDEX route_id ON production_routes(route_id)")
    con.execute("CREATE INDEX production_civ ON unit_production(civ_name)")
    con.execute("CREATE VIEW review_exceptions AS SELECT * FROM unit_production WHERE status != 'calculated'")
    con.commit()
    con.close()
    write_csv(output / "unit-production.csv", rows)
    write_csv(output / "review-exceptions.csv", [r for r in rows if r["status"] != "calculated"])
    flat_routes = [{k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in routes]
    write_csv(output / "all-production-buildings.csv", flat_routes)
    write_csv(output / "source-trainable-units.csv", [{k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in source_units])
    write_csv(output / "all-source-units.csv", [{k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in source_cheapest])
    dump(output / "manifest.json", metadata)
    summaries = ["# Civilization production review — first pass", "",
                 "User-supplied DAT snapshot; fully researched Imperial. All numbers and modifier rules come from that source. Matching shipped tech trees supply availability and labels when present. The advisor roster supplies comparison coverage only.", "",
                 "Building ranking: wood + 2 × stone. All alternatives remain in the database. Rows with review flags are provisional.", ""]
    summaries += ["The broader source inventory is a candidate list: availability gates may over-include conditional or ally-granted units. Source-only candidates are marked below for owner review.", ""]
    for name in sorted(by_civ):
        rr = [r for r in rows if r["civ_name"] == name]
        total_source = sum(r["civ_name"] == name for r in source_cheapest)
        summaries += [f"## {name}", "", f"{len(rr)} advisor roster units; {sum(r['final_train_seconds'] is not None for r in rr)} times calculated; {sum(bool(r['review_flags']) for r in rr)} rows flagged. Separately, {total_source} unit groups resolved from the source, including economic units.", ""]
        if name not in data["civs"]:
            summaries += ["Civilization absent from this DAT snapshot.", ""]
            continue
        effects = defaultdict(lambda: {"units": set(), "targets": set()})
        for r in routes + source_units:
            if r["civ_name"] != name or "production_building_availability_needs_review" in r["flags"]:
                continue
            for m in r["applied"]:
                if m["civ_specific"]:
                    key = (m["effect_id"], m["effect_name"], m["target"], OPS[m["command"]["type"]], round(m["command"]["d"], 7))
                    effects[key]["units"].add(r["unit_name"])
                    effects[key]["targets"].add(r["building"])
        for (eid, effect, target, op, value), detail in sorted(effects.items()):
            examples = ", ".join(sorted(detail["units"]))
            summaries.append(f"- **{effect}** (effect {eid}): {target.replace('_', ' ')} {op} {value:g}; buildings: {', '.join(sorted(detail['targets']))}; units/candidates: {examples}.")
        if not effects:
            summaries.append("No civilization-specific production-speed or production-building-cost modifiers matched the resolved units or comparison roster in this pass.")
        extra = sorted({r["unit_name"] for r in source_cheapest if r["civ_name"] == name and not r["in_advisor_roster"]})
        if extra:
            summaries += ["", "Source-only candidates (availability needs review): " + ", ".join(extra) + "."]
        alt = [r for r in rr if r["production_building_count"] > 1]
        if alt:
            summaries += ["", "Cheapest alternate-building selections:", ""] + [f"- {r['unit_name']}: {r['building']}, {r['building_wood_equivalent']:.2f} wood-equivalent, {r['final_train_seconds']:.2f}s." for r in alt if r["final_train_seconds"] is not None]
        flags = defaultdict(list)
        for r in rr:
            for flag in filter(None, r["review_flags"].split("; ")):
                flags[flag].append(r["unit_name"])
        if flags:
            summaries += ["", "Review boundaries:", ""] + [f"- `{flag}`: {', '.join(units)}." for flag, units in sorted(flags.items())]
        summaries.append("")
    (output / "civilization-summary.md").write_text("\n".join(summaries) + "\n")
    print(json.dumps(metadata, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--dat", type=Path)
    source.add_argument("--raw-json", type=Path)
    p.add_argument("--reference", type=Path, default=ROOT / "data/golden/aoe2_reference_simulation.db")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--labels", type=Path, help="Optional local language-ID display labels; never used for calculations")
    p.add_argument("--game-trees", type=Path, help="Matching game's CivTechTrees directory")
    args = p.parse_args()
    data = extract(args.dat) if args.dat else json.loads(args.raw_json.read_text())
    if args.game_trees:
        attach_game_trees(data, args.game_trees)
    build(data, args.reference, args.out, json.loads(args.labels.read_text()) if args.labels else None)


if __name__ == "__main__":
    main()
