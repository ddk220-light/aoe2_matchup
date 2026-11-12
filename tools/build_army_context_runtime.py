#!/usr/bin/env python3
"""Compile the review ledger into the Battle Simulation context database.

No campaign, mechanics database, or source review file is modified. Incomplete
models produce explicit null labor and block release, never generic substitutes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aoe2x.army_economics import (
    CONTEXT_SCHEMA_VERSION, TRAINING_WINDOW_SECONDS, RESOURCE_WEIGHTS, MAX_ARMY, RESOURCES, building_value,
    select_investment_route, compile_labor_prices, compiled_labor, weighted_cost, purchase_bill,
    queue_seconds, research_infrastructure, research_totals, resources, solve_labor,
)
from aoe2x.js_simulation.battle_setup import effective_cost
from aoe2x.dbgen.config_units import PAIRED_UNITS
from validate_army_observations import validate_observations
from army_context_policy import AURA_ASSUMPTION, GATHERING_VALIDATION_POLICY, excluded_record, exclusion_reason
from special_economy import apply_special_economy, pasture_activity

DEFAULT_REVIEW = ROOT / "aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/army-context.sqlite"
AGE_TECHS = {101, 102, 103, 104}
BLOCKING_SCOPES = {"conditional_land_income", "pasture_model_required", "review_scope_required"}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_db(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def rows(db, table):
    return [dict(r) for r in db.execute(f'SELECT * FROM "{table}"')]


class Compiler:
    def __init__(self, review, reference):
        self.db = read_db(review)
        self.ref = read_db(reference)
        self.source = dict(self.db.execute("SELECT key,value FROM analysis_metadata"))
        self.game_source = json.loads(self.source["game_source"])
        for table in ("eco_metadata", "production_metadata", "research_metadata"):
            source = self.db.execute(f"SELECT value FROM {table} WHERE key='source'").fetchone()
            if source is None or json.loads(source[0])["sha256"] != self.game_source["sha256"]:
                raise ValueError(f"{table}: game data provenance does not match the review")
        self.audit = []
        self.blockers = []
        self.scope_exceptions = []
        supplement_path = Path(review).parent / "special-gather-rates.json"
        online_path = Path(review).parent / "online-mechanic-evidence.json"
        self.special_hashes = {}
        pasture_path = Path(review).parent / "pasture-online-reference.json"
        self.pasture_reference = json.loads(pasture_path.read_text()) if pasture_path.exists() else None
        if self.pasture_reference:
            self.special_hashes["pastureReference"] = sha(pasture_path)
        self.special_scenarios = defaultdict(dict)
        self.online_source = None
        if supplement_path.exists():
            supplement = json.loads(supplement_path.read_text())
            expected = {"inputs": Path(review).parent / "eco-inputs.json", "evidence": online_path,
                        "runner": ROOT / "tools/run_special_economy.mjs",
                        **{n: ROOT / "tools" / n for n in
                           ("farm-gathering-sim.mjs", "wood-gathering-sim.mjs", "gold-mining-sim.mjs")}}
            if any(supplement["sourceHashes"].get(k) != sha(p) for k, p in expected.items()):
                raise ValueError("Special gathering scenarios are stale; rerun tools/run_special_economy.mjs")
            self.special_hashes.update(scenarios=sha(supplement_path), onlineEvidence=sha(online_path))
            self.online_source = json.loads(online_path.read_text())["source"]
            for r in supplement["rows"]:
                self.special_scenarios[r["civ"]][r["resource"]] = r
        self.resource_parameters = defaultdict(dict)
        for r in rows(self.db, "eco_resource_parameters"):
            self.resource_parameters[r["civ_name"]][r["resource_id"]] = r
        self.by_civ = defaultdict(list)
        for r in rows(self.db, "late_effect_scopes"):
            self.by_civ[r["civ_name"]].append(r)
        self.rates = {(r["civ_name"], r["resource"]): r for r in rows(self.db, "gather_rates")}
        self.parameters = {r["civ_name"]: r for r in rows(self.db, "eco_civilization_parameters")}
        self.units = {(r["civ_name"], r["unit_id"]): r for r in rows(self.db, "unit_economy")}
        self.costs = {(r["civ_name"], r["unit_id"]): r for r in rows(self.db, "eco_replacement_resource_costs")}
        self.techs = {(r["civ_name"], r["tech_id"]): r for r in rows(self.db, "research_civilization_upgrades")}
        self.rawtechs = {r["tech_id"]: json.loads(r["definition"]) for r in rows(self.db, "research_raw_technologies")}
        self.buildings = {(r["civ_name"], r["building_id"]): r for r in rows(self.db, "research_buildings")}
        self.upgrades = defaultdict(list)
        for r in rows(self.db, "research_unit_upgrade_data"):
            self.upgrades[r["unit_key"]].append(r)
        self.routes = defaultdict(list)
        for r in rows(self.db, "production_production_routes"):
            self.routes[r["civ_name"], r["reference_unit_id"]].append(r)
        self.source_routes = defaultdict(list)
        for r in rows(self.db, "production_source_trainable_routes"):
            self.source_routes[r["civ_name"], r["source_unit_id"]].append(r)
        self.form_pairs = {}
        reference_units = rows(self.ref, "ref_units")
        by_slug = {(r["civ_name"], r["unit_slug"]): r for r in reference_units}
        for r in reference_units:
            for base, paired in PAIRED_UNITS.items():
                if r["unit_slug"].startswith(base + "_"):
                    target = by_slug.get((r["civ_name"], paired + r["unit_slug"][len(base):]))
                    if target:
                        self.form_pairs[r["civ_name"], r["unit_master"]] = target["unit_master"]
        self.eco_techs = defaultdict(list)
        for r in rows(self.db, "late_eco_technology_ledger"):
            self.eco_techs[r["civ_name"]].append(r)
        self.unique_eco = defaultdict(list)
        for r in rows(self.db, "late_unique_eco_technologies"):
            self.unique_eco[r["civ_name"]].append(r)

    def record_issue(self, issue):
        reason = exclusion_reason(issue)
        if reason:
            excluded = excluded_record(issue, reason)
            self.scope_exceptions.append(excluded)
            return excluded
        self.blockers.append(issue)
        return issue

    def building(self, civ, bid):
        b = self.buildings.get((civ, bid))
        return None if b is None else {"id": bid, "name": b["building_name"],
                                      "cost": {r: b["cost_" + r] for r in RESOURCES}}

    def tech(self, r):
        t = {"id": r["tech_id"], "name": r["technology"], "seconds": r["final_seconds"],
             "baseSeconds": r["base_seconds"], "automaticFree": bool(r["automatic_free"]),
             "costIsFixed": bool(r["cost_is_fixed"]),
             "building": self.building(r["civ_name"], r["selected_building_id"]),
             "modifiers": json.loads(r["modifiers"]), "flags": json.loads(r["flags"]),
             "pricingTechnologyIds": json.loads(r["pricing_tech_ids"]),
             "reasons": json.loads(r.get("reasons", "[]")),
             **{dst: {res: r[src + "_" + res] for res in RESOURCES}
                for src, dst in (("upfront", "upfront"), ("reward", "refund"), ("net", "net"))}}
        if t["automaticFree"]:
            t.update(seconds=0, upfront=resources(), refund=resources(), net=resources())
        if not t["costIsFixed"]:
            # Hook 55 uses the technology base and the age-initialized increment.
            # Retain the source formula; compiled-engine semantics still require
            # an observation before promotion to a verified exact total.
            base = {res: r["base_" + res] for res in RESOURCES}
            increment = {res: t["upfront"][res] - base[res] for res in RESOURCES}
            t["variableCost"] = {"input": "convertedVillagers", "base": base,
                                 "perVillager": increment, "status": "engine_observation_pending"}
            t["upfront"] = base
            t["net"] = {res: base[res] - t["refund"][res] for res in RESOURCES}
        return t

    def pasture_inputs(self, civ):
        if self.parameters[civ]["farm_available"]:
            return None
        # Replay all resource commands, including fields absent from the older
        # curated parameter table. 289 is animal count; 290 is herder count.
        values = json.loads(self.db.execute(
            "SELECT resources FROM eco_initial_player_resources WHERE civ_name=?", (civ,)).fetchone()[0])
        values = dict(enumerate(values))
        evidence = []
        for row in self.db.execute(
                "SELECT * FROM eco_active_effect_commands WHERE civ_name=? ORDER BY sequence", (civ,)):
            cmd = json.loads(row["command"])
            rid = cmd["a"]
            if cmd["type"] == 1:
                value = cmd["d"] * values.get(cmd["c"], 0) if cmd["c"] >= 0 else cmd["d"]
                values[rid] = value if cmd["b"] == 0 else values.get(rid, 0) + value
            elif cmd["type"] == 6:
                values[rid] = values.get(rid, 0) * cmd["d"]
            if cmd["type"] in (1, 6) and rid in (288, 289, 290, 293, 294):
                evidence.append({"technologyId": row["tech_id"], "effectId": row["effect_id"], "command": cmd})
        actors = {}
        for uid in (118, 1889, 1892, 1897):
            row = self.db.execute("SELECT * FROM eco_actor_parameters WHERE civ_name=? AND unit_id=?", (civ, uid)).fetchone()
            base, final = json.loads(row["base_parameters"]), json.loads(row["final_parameters"])
            changes = json.loads(row["evidence"])
            carry = base["carry_capacity"]
            for change in changes:
                if change["field"] == "carry_capacity":
                    cmd = change["command"]
                    carry = cmd["d"] if cmd["type"] == 0 else carry + cmd["d"] if cmd["type"] == 4 else carry * cmd["d"]
                    carry = math.floor(carry + .5)
            actors[str(uid)] = {"parameters": final, "roundedCarry": carry,
                                "cost": json.loads(row["final_cost"]), "evidence": changes}
        return {"status": "source_parameters_only", "food": values[288],
                "animalCount": values[289], "herderCount": values[290],
                "resourceParameters": {str(i): values[i] for i in (288, 289, 290, 293, 294)},
                "actors": actors, "evidence": evidence,
                "missingBehavior": "Shared food generation, worker movement/drop-off and renewal require engine behavior evidence before deriving a delivered gather rate."}

    def civilization(self, civ):
        p = self.parameters[civ]
        pending = [r for r in self.by_civ[civ] if r["scope"] in BLOCKING_SCOPES]
        activities = []
        for resource in RESOURCES:
            row = self.rates[civ, resource]
            if row["rate"] is None:
                continue
            outputs = resources({resource: row["rate"]})
            if resource == "food":
                outputs["wood"] = -row["rate"] * p["farm_wood_cost"] / (
                    p["farm_food_parameter"] * p["farmer_task_multiplier"])
            activities.append({"id": resource, "outputs": outputs,
                               "scenarioSignature": row["signature"], "status": "scenario_estimate"})
        # Secondary outputs and timed income enter the same vectors as the primary
        # activity, preserving recurring farm wood and preventing double credit.
        activities, modeled_effects = apply_special_economy(
            activities, self.resource_parameters[civ], self.special_scenarios[civ], pending, self.online_source)
        pasture_source = self.pasture_inputs(civ)
        pasture_model = None
        if pasture_source is not None and self.pasture_reference is not None and civ == "Khitans":
            activity = pasture_activity(pasture_source, self.pasture_reference)
            activities.append(activity)
            pasture_model = activity["appliedMechanics"][0]
            modeled_effects.update(e["effectId"] for e in pasture_source["evidence"])
            pasture_source["status"] = "online_reference_estimate"
            pasture_source.pop("missingBehavior", None)
        pending = [r for r in pending if r["effect_id"] not in modeled_effects]
        technologies, missing = {}, []
        for r in self.eco_techs[civ]:
            if r["scope"] not in ("core_land", "pasture", "construction", "worker_protection"):
                continue
            if not r["available"]:
                missing.append({"id": r["tech_id"], "name": r["technology"], "scope": r["scope"]})
                continue
            t = self.tech(self.techs[civ, r["tech_id"]])
            t.update(seconds=r["seconds"], upfront=json.loads(r["upfront_cost"]),
                     refund=json.loads(r["reward"]), net=json.loads(r["net_cost"]),
                     completionUnitRewards=json.loads(r["completion_unit_reward_events"]),
                     advantage=r["advantage"], scope=r["scope"])
            technologies[t["id"]] = t
        for r in self.unique_eco[civ]:
            t = self.tech(self.techs[civ, r["tech_id"]])
            t["effectSummary"] = r["effect_summary"]
            technologies.setdefault(t["id"], t)
        effects = [{"technologyId": r["tech_id"], "effectId": r["effect_id"],
                    "name": r["mechanic"], "scope": r["scope"], "description": r["description"],
                    "evidence": json.loads(r["evidence"])} for r in self.by_civ[civ]]
        blockers = [{"code": "unresolved_economy_mechanic", "civ": civ,
                     "technologyId": r["tech_id"], "effectId": r["effect_id"],
                     "detail": r["description"]} for r in pending]
        reviewed = [self.record_issue(issue) for issue in blockers]
        excluded = [issue for issue in reviewed if issue.get("status") == "excluded_by_user"]
        blockers = [issue for issue in reviewed if issue.get("status") != "excluded_by_user"]
        excluded_ids = {issue["technologyId"] for issue in excluded}
        for effect in effects:
            if effect["effectId"] in modeled_effects:
                effect["calculationStatus"] = "online_reference_estimate" if pasture_model and effect["scope"] == "pasture_model_required" else "modeled_scenario_estimate"
            if effect["technologyId"] in excluded_ids:
                effect["calculationStatus"] = "excluded_by_user"
                effect["description"] += " Excluded from villager income at the user's request."
        return {"civ": civ, "activities": activities,
                "scopeExceptions": excluded, "auraAssumption": AURA_ASSUMPTION,
                "pastureSourceInputs": pasture_source, "pastureModel": pasture_model,
                "laborPrices": compile_labor_prices(activities) if not blockers else None,
                "laborStatus": "unresolved_mechanics" if blockers else "scenario_estimate",
                "blockers": blockers, "effects": effects,
                "technologies": list(technologies.values()), "missingTechnologies": missing,
                "totals": research_totals(list(technologies.values()))}

    def route(self, unit):
        candidates = self.routes[unit["civ_name"], unit["reference_unit_id"]]
        unresolved = "unit_not_resolved_as_trainable_in_final_source_state"
        valid = [r for r in candidates if r["final_train_seconds"] is not None and unresolved not in json.loads(r["flags"])]
        identity = None
        if not valid:
            # Existing explicit form pairing supplies identity only. Prices and
            # training parameters must independently agree in the DAT review,
            # and the paired form must be trainable in the resolved source tree.
            paired = self.form_pairs.get((unit["civ_name"], unit["unit_id"]))
            paired_routes = self.source_routes.get((unit["civ_name"], paired), [])
            for p in paired_routes:
                matches = [r for r in candidates if r["building_id"] == p["building_id"]
                           and r["base_train_seconds"] == p["base_train_seconds"]
                           and abs((r["final_train_seconds"] or 0) - (p["final_train_seconds"] or 0)) < 1e-6]
                if matches and all(abs(self.costs[unit["civ_name"], paired][k] - unit[k]) < 1e-6 for k in RESOURCES):
                    valid.append(p)
                    identity = {"kind": "explicit_catalog_form_pair_with_DAT_training_agreement",
                                "displayUnitId": unit["unit_id"], "trainedUnitId": paired}
        valid.sort(key=lambda r: (building_value({k: r["building_" + k] for k in RESOURCES}),
                                  r["final_train_seconds"], r["building_id"], r["source_unit_id"]))
        def convert(r):
            return {"id": r["building_id"], "name": r["building"],
                    "trainedUnitId": r["source_unit_id"], "secondsPerOrder": r["final_train_seconds"],
                    "baseTrainSeconds": r["base_train_seconds"],
                    "cost": {k: r["building_" + k] for k in RESOURCES},
                    "modifiers": json.loads(r["applied"]), "activation": json.loads(r["activation"]),
                    "special": json.loads(r["special"]), "sourceFlags": json.loads(r["flags"]),
                    "formIdentity": identity}
        return [convert(r) for r in valid]

    def research(self, unit, production):
        civ = unit["civ_name"]
        packages = {"military": {}, "production": {}}
        for row in self.upgrades[unit["research_unit_key"]]:
            t = self.tech(row)
            # A technology enabling the selected cheaper training location is
            # part of the required military setup (Anarchy / Marauders).
            unlock = any(e.get("target") == "production_location"
                         for e in production.get("modifiers", []) if e.get("tech_id") == t["id"])
            unlock |= "production_location" in t["reasons"]
            key = "military" if row["scope"] == "direct" or unlock else "production"
            if t["id"] not in AGE_TECHS:
                packages[key][t["id"]] = t
        # Descend through hidden activation gates so unlocks cannot disappear
        # merely because a shadow technology, rather than the paid tech, enables
        # the unit. Already-associated prerequisites remain deduplicated.
        visited = set()
        def require(tid):
            if tid in visited or tid in AGE_TECHS or tid is None:
                return
            visited.add(tid)
            if (civ, tid) in self.techs:
                packages["military"].setdefault(tid, self.tech(self.techs[civ, tid]))
            raw = self.rawtechs.get(tid, {})
            for parent in raw.get("required_techs", []):
                if parent >= 0:
                    require(parent)
        for item in production.get("activation", []) + production.get("special", []):
            require(item.get("tech_id"))
        for tid in list(packages["military"]):
            packages["production"].pop(tid, None)
        result = {}
        for scope, technologies in packages.items():
            techs = [technologies[k] for k in sorted(technologies)]
            result[scope] = {"technologies": techs, "totals": research_totals(techs),
                             "infrastructure": research_infrastructure(techs, production)}
        result["infrastructure"] = research_infrastructure(
            result["military"]["technologies"] + result["production"]["technologies"], production)
        return result

    def unit(self, profile, economy):
        mechanics = json.loads(profile["mechanics_json"])
        civ, uid = mechanics["civilization"], mechanics["unit_master"]
        reference = dict(self.ref.execute("SELECT * FROM ref_units WHERE id=?", (profile["ref_unit_id"],)).fetchone())
        # Explicit profile FK identifies alternate modes of the same purchased
        # unit (War Chariot barrage); never join forms by their display name.
        source_uid = reference["unit_master"]
        unit = self.units[civ, source_uid]
        source_cost = self.costs[civ, source_uid]
        for r in ("food", "wood", "gold"):
            reference["final_cost_" + r] = source_cost[r]
        physical_cost, policy = effective_cost(reference)
        batch = policy["unitsPerPurchase"]
        purchase = {r: physical_cost[r] * batch if r in physical_cost else round(source_cost[r]) for r in RESOURCES}
        physical = {r: purchase[r] / batch for r in RESOURCES}
        pricing = {"purchaseCost": purchase, "unitsPerPurchase": batch, "physicalUnitCost": physical,
                   "conditionalMultiplier": policy["conditionalMultiplier"],
                   "conditionalContext": policy["conditionalContext"],
                   "sourceCost": resources(source_cost), "evidence": json.loads(source_cost["cost_evidence"])}
        if any(abs(mechanics["cost"].get(r, 0) - physical[r]) > 1e-6 for r in RESOURCES):
            self.audit.append({"civ": civ, "unitId": uid, "mode": profile["mode"],
                               "before": mechanics["cost"], "after": physical,
                               "evidence": pricing["evidence"]})
        # Solve once per purchase; shared research costs are paired by the endpoint.
        per_order = solve_labor(purchase, economy["activities"]) if not economy["blockers"] else None
        routes = self.route(unit)
        initial = purchase_bill(MAX_ARMY, purchase, batch)
        production, alternatives = select_investment_route(routes, initial["orders"], batch,
                                                         initial["cost"], economy["laborPrices"])
        if not alternatives:
            self.record_issue({"code": "unresolved_training_route", "civ": civ,
                                  "unitId": uid, "detail": unit["unit_name"]})
        research = self.research(unit, production)
        all_military_ids = {t["id"] for s in ("military", "production") for t in research[s]["technologies"]}
        eco = [t for t in economy["technologies"] if t["id"] not in all_military_ids]
        research["economicSetup"] = {"technologies": eco, "totals": research_totals(eco),
                                     "infrastructure": research_infrastructure(eco, production)}
        research["allInfrastructure"] = research_infrastructure(
            research["military"]["technologies"] + research["production"]["technologies"] + eco, production)
        # Homogeneous linear program: solve one purchase, scale for integer
        # purchase orders. This also preserves indivisible batch purchases.
        lookups = []
        for count in range(MAX_ARMY + 1):
            bill = purchase_bill(count, purchase, batch)
            labor = None
            if count == 0:
                labor = {"seconds": 0, "villagerMinutes": 0, "workByActivity": {}, "surplus": resources()}
            elif per_order is not None:
                q = bill["orders"]
                labor = {"seconds": per_order["seconds"] * q, "villagerMinutes": per_order["villagerMinutes"] * q,
                         "workByActivity": {k: v * q for k, v in per_order["workByActivity"].items()},
                         "surplus": {k: v * q for k, v in per_order["surplus"].items()}}
            lookups.append({**bill, "labor": labor,
                            "weightedLabor": compiled_labor(weighted_cost(bill["cost"]), economy["laborPrices"]),
                            "trainingSeconds": queue_seconds(bill["orders"], production)})
        return {"civ": civ, "unitId": uid, "sourceUnitId": source_uid, "mode": profile["mode"], "name": unit["unit_name"],
                "slug": mechanics["unit_slug"], "sourceMechanicsHash": profile["mechanics_hash"],
                "pricing": pricing, "production": production, "productionRoutes": routes, "alternativeRoutes": alternatives,
                "research": research, "lookup": lookups, "laborStatus": economy["laborStatus"]}


def compile_database(review, reference, output, observations=None):
    compiler = Compiler(review, reference)
    civilizations = {civ: compiler.civilization(civ) for civ in sorted(compiler.parameters)}
    profiles = rows(compiler.ref, "ref_unit_mechanics")
    units = [compiler.unit(p, civilizations[json.loads(p["mechanics_json"])["civilization"]]) for p in profiles]
    # Captures only validate; they never provide runtime model parameters.
    observation_review = validate_observations(civilizations, observations, compiler.game_source["sha256"],
                                              ROOT / "aoe2x/js_simulation/calibration",
                                              require_measurements=GATHERING_VALIDATION_POLICY["requiredForRelease"])
    compiler.blockers.extend(observation_review["blockers"])
    for unit in units:
        for tech in unit["research"]["military"]["technologies"]:
            if tech.get("variableCost"):
                compiler.record_issue({"code": "dynamic_research_cost_unvalidated", "civ": unit["civ"],
                                         "technologyId": tech["id"], "detail": tech["name"]})
    blockers = list({encode(b): b for b in compiler.blockers}.values())
    metadata = {"schemaVersion": CONTEXT_SCHEMA_VERSION, "trainingWindowSeconds": TRAINING_WINDOW_SECONDS,
                "resourceWeights": RESOURCE_WEIGHTS,
                "releaseReady": not blockers, "blockers": blockers,
                "scopeExceptions": list({encode(x): x for x in compiler.scope_exceptions}.values()),
                "auraAssumption": AURA_ASSUMPTION,
                "gatheringValidationPolicy": GATHERING_VALIDATION_POLICY,
                "civilizationCount": len(civilizations), "profileCount": len(units),
                "source": {k: v for k, v in compiler.game_source.items() if k not in ("path", "game_tree_directory", "patch_signature")},
                "sourceHashes": {"review": sha(review), "reference": sha(reference), "compiler": sha(__file__),
                                 "accounting": sha(ROOT / "aoe2x/army_economics.py"),
                                 "scopePolicy": sha(ROOT / "tools/army_context_policy.py"),
                                 "specialEconomy": sha(ROOT / "tools/special_economy.py"),
                                 **compiler.special_hashes,
                                 "observationValidator": sha(ROOT / "tools/validate_army_observations.py"),
                                 "formIdentityCatalog": sha(ROOT / "aoe2x/dbgen/config_units.py")},
                "priceCorrections": compiler.audit,
                "gatheringValidation": observation_review,
                "assumptions": ["Post-Imperial; all available upgrades; Imperial research pricing; own bonuses only.",
                    "The headline is weighted villager-minutes for the displayed army, production buildings completing it within 60 seconds, and common military upgrade net costs.",
                    "Apply food x1, wood x1, gold x1.5 and stone x3 to the combined resource bill before evaluating labor. These are scarcity preferences, not literal gathering delays.",
                    "Gathering uses the reviewed resource layouts, including reseeding downtime and recurring farm wood; resource coproducts satisfy the combined bill without resale credit.",
                    "Khitan pasture food uses an online lifecycle average of 25.2 food per villager-minute as a post-Imperial estimate, with immediate food credit and no external drop-off trip. Recurring pasture wood uses the supplied DAT cost and yield; rebuilding downtime is already in the reference rate.",
                    "Controlled in-game gathering measurements are deferred by user instruction. Release eligibility does not certify measured accuracy; gathering rates remain estimates.",
                    "Folwark: 8 of 10 farms covered. Applicable auras are assumed fully active, once, without placement requirements or aura-building costs (user instruction 2026-11-11).",
                    "Wei Tuntian income is excluded. Berber Xebec, Chinese Fire Ship and Flemish Revolution verification are excluded from release requirements; missing values remain unverified, not filled in.",
                    "Production uses complete purchase cycles: orders per building = floor(60 / training seconds); required buildings = ceil(orders / orders per building). A slower-than-60s purchase cannot meet the window.",
                    "Choose the route minimizing total weighted labor; ties use faster queue completion then building ID. Unresolved labor allows provisional resource-priced infrastructure only.",
                    "Buildings and common upgrades are one-time investments. Casualty replacement work charges neither again, carries initial batch surplus and rounds new purchases cumulatively. Extra units are not added to combat.",
                    "The 60-second window starts with buildings, upgrades and resources ready. Villager construction animations, rally travel, economic setup, research-building infrastructure and exclusive upgrades are separate from the headline.",
                    "Research time is summed workload, not a parallel build order. Refunds arrive after payment.",
                    "Passive income, relics, trade, combat rewards and early-game grants are outside villager labor."]}
    metadata["contextVersion"] = hashlib.sha256(encode({"metadata": metadata, "units": units, "civilizations": civilizations}).encode()).hexdigest()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() in (Path(review).resolve(), Path(reference).resolve()):
        raise ValueError("output must not overwrite a source database")
    temporary = output.with_suffix(".building.sqlite")
    if temporary.exists():
        temporary.unlink()
    with sqlite3.connect(temporary) as db:
        db.executescript("""
            CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
            CREATE TABLE civilizations (civ TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE units (civ TEXT NOT NULL, unit_id INTEGER NOT NULL, mode TEXT NOT NULL,
                                payload TEXT NOT NULL, PRIMARY KEY(civ,unit_id,mode));
        """)
        db.execute("INSERT INTO metadata VALUES(1,?)", (encode(metadata),))
        db.executemany("INSERT INTO civilizations VALUES(?,?)", [(k, encode(v)) for k, v in civilizations.items()])
        db.executemany("INSERT INTO units VALUES(?,?,?,?)", [(u["civ"], u["unitId"], u["mode"], encode(u)) for u in units])
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("runtime database integrity check failed")
    temporary.replace(output)
    report = output.with_suffix(".validation.json")
    report.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    compiler.db.close()
    compiler.ref.close()
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--reference", type=Path, default=ROOT / "data/golden/aoe2_reference_simulation.db")
    parser.add_argument("--output", type=Path, default=ROOT / "data/golden/army_context.db")
    parser.add_argument("--require-release-ready", action="store_true")
    parser.add_argument("--observations", type=Path, help="Independent controlled game measurement manifest")
    args = parser.parse_args()
    metadata = compile_database(args.review, args.reference, args.output, args.observations)
    print(json.dumps({k: metadata[k] for k in ("civilizationCount", "profileCount", "releaseReady", "contextVersion")}, indent=2))
    print(f"Release blockers: {len(metadata['blockers'])}; price corrections: {len(metadata['priceCorrections'])}")
    if args.require_release_ready and not metadata["releaseReady"]:
        raise SystemExit("Release blocked; see the generated .validation.json report")


if __name__ == "__main__":
    main()
