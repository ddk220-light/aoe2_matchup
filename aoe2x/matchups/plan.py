"""``diff-bundles``: what a new game version changes, and what re-running it will cost.

Builds on ``bundle.compare_bundles`` (variants by ``mechanicsHash``) and the
reuse rule of the runner: a stored result applies when it is for the same
profile pair, under the same battle setup, in the stored physical context.

For every displayed cell of the **new** bundle's roster the profile pair is
classified:

``identity``  same profile on both sides: ``equivalent``, never simulated;
``reuse``     the result index has a reusable measured result (frozen engine)
              whose stored context is this setup's context for the pair;
``keep``      the index has a valid result that is not "reusable" in the
              runner's sense (rule-inferred, ranking-era or recovery-engine
              seeds - the 2026 site shows them); both profiles are unchanged,
              so the result still describes exactly these two units. Kept, not
              re-simulated (``--resimulate-kept`` schedules them too);
``simulate``  no stored result for this pair under this setup: a new or
              changed profile, a new civilization's new profile, or new
              conditions.

Why ``keep`` is safe: a stored result is a fact about two fixed combat
profiles (mechanics hashes) under a fixed setup. A rule-inferred result was
derived from other fixed profiles' fights; those facts stay true when other
units change, because a changed unit gets a new profile hash rather than
changing the old one.

Cost estimate: ``expected seeds`` per scheduled context times
``SECONDS_PER_SEED`` (measured: ~1,490 seeds/hour at 4 workers on this
4-vCPU machine, i.e. 372.5 seeds per worker-hour; the measured sample was
biased to fast fights, so a conservative figure using the 2026 campaign mean of
17.3 s per seed per worker is shown too). Expected seeds per context: 3.3
without a prior (three-then-ten, 2026 adaptive campaign: 38,326 seeds /
11,580 pairs) and 1.56 with an agreeing prior (one-three-ten, 2026 forecast
campaign: 61,114 / 39,112).

``--priors`` writes a ``priors-file`` (``sampling.forecastSource:
"priors-file"``) for changed pairs: for each scheduled pair, the previous
version's outcomes of the same displayed cells (old bundle profiles -> result
index), in the new pair's ``pairKey`` order. The one-seed shortcut then needs
the first seed to agree with every one of them and be decisive. Not used by
default (owner decision Q3: no prior -> at least 3 seeds).
"""
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from aoe2x.matchups.battle import ContextBuilder
from aoe2x.matchups.bundle import Scenarios, compare_bundles
from aoe2x.matchups.canonical import key2, sha256_bytes

SEEDS_PER_HOUR_4_WORKERS = 1490.0
SEEDS_PER_WORKER_HOUR = SEEDS_PER_HOUR_4_WORKERS / 4
CONSERVATIVE_SECONDS_PER_SEED = 17.3
EXPECTED_SEEDS = {"none": 3.3, "prior": 1.56}
INVERSE = {"a_win": "b_win", "b_win": "a_win", "close_uncertain": "close_uncertain", "equivalent": "equivalent"}


def estimate(contexts: int, with_prior: int = 0, workers: int = 4) -> dict:
    seeds = (contexts - with_prior) * EXPECTED_SEEDS["none"] + with_prior * EXPECTED_SEEDS["prior"]
    worker_hours = seeds / SEEDS_PER_WORKER_HOUR
    conservative = seeds * CONSERVATIVE_SECONDS_PER_SEED / 3600
    return {"contexts": contexts, "withPrior": with_prior, "expectedSeeds": round(seeds),
            "workerHours": round(worker_hours, 1), "wallHours": {str(workers): round(worker_hours / workers, 1)},
            "conservativeWorkerHours": round(conservative, 1),
            "conservativeWallHours": {str(workers): round(conservative / workers, 1)},
            "basis": f"{EXPECTED_SEEDS['none']} seeds/context without prior, {EXPECTED_SEEDS['prior']} with; "
                     f"{SEEDS_PER_HOUR_4_WORKERS:.0f} seeds/h at 4 workers (conservative: "
                     f"{CONSERVATIVE_SECONDS_PER_SEED} s/seed/worker)"}


def variant_diff(old: dict, new: dict) -> dict:
    base = compare_bundles(old, new)
    vo = {v["key"]: v for v in old["variants"]}
    vn = {v["key"]: v for v in new["variants"]}
    changed = []
    for key in base["changedMechanics"]:
        a, b = vo[key]["mechanics"], vn[key]["mechanics"]
        fields = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        changed.append({"key": key, "oldProfile": vo[key]["profileHash"], "newProfile": vn[key]["profileHash"],
                        "fields": fields, "profileChanged": vo[key]["profileHash"] != vn[key]["profileHash"]})
    po = {v["profileHash"] for v in old["variants"]}
    pn = {v["profileHash"] for v in new["variants"]}
    roster_o, roster_n = set(old["roster"]["units"]), set(new["roster"]["units"])
    return {"old": {"bundleHash": old["bundleHash"], "variants": len(vo), "profiles": len(po),
                    "civilizations": len({v["civilization"] for v in old["variants"]})},
            "new": {"bundleHash": new["bundleHash"], "variants": len(vn), "profiles": len(pn),
                    "civilizations": len({v["civilization"] for v in new["variants"]})},
            "variantsAdded": base["onlyInB"], "variantsRemoved": base["onlyInA"], "variantsChanged": changed,
            "rosterAdded": sorted(roster_n - roster_o), "rosterRemoved": sorted(roster_o - roster_n),
            "civilizationsAdded": sorted({v["civilization"] for v in new["variants"]} -
                                         {v["civilization"] for v in old["variants"]}),
            "civilizationsRemoved": sorted({v["civilization"] for v in old["variants"]} -
                                           {v["civilization"] for v in new["variants"]}),
            "profilesAdded": sorted(pn - po), "profilesRemoved": sorted(po - pn),
            "profilesKept": len(po & pn), "identical": base["identicalVariants"]}


def classify(new: dict, scenario_set: dict, battle: dict, index: list, *, resimulate_kept: bool = False) -> dict:
    """Per profile pair of the new roster: identity / reuse / keep / simulate, with cells and civilizations."""
    rows = {r["pairKey"]: r for r in index}
    by_key = {v["key"]: v for v in new["variants"]}
    roster = [by_key[k] for k in new["roster"]["units"]]
    mechanics = {}
    for v in new["variants"]:
        mechanics.setdefault(v["profileHash"], v["mechanics"])
    context_of = ContextBuilder(mechanics, Scenarios(scenario_set), battle)
    pairs: dict[str, dict] = {}
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            if a["civilization"] == b["civilization"]:
                continue
            pk = key2(a["profileHash"], b["profileHash"])
            p = pairs.setdefault(pk, {"cells": 0, "civs": set(), "cellKeys": []})
            p["cells"] += 1
            p["civs"].update((a["civilization"], b["civilization"]))
            p["cellKeys"].append((a["key"], b["key"]))
    for pk, p in pairs.items():
        h1, h2 = pk.split("|")
        row = rows.get(pk)
        if h1 == h2:
            p["class"] = "identity"
            continue
        valid = (row is not None and row.get("context") is not None
                 and row["context"] == context_of(*row["context"]["profiles"]))
        if valid and row.get("reusable"):
            p["class"] = "reuse"
        elif valid and not resimulate_kept:
            p["class"] = "keep"
            p["keptSource"] = row.get("source")
        else:
            p["class"] = "simulate"
            p["reason"] = ("stored under another setup" if row is not None and not valid else
                           "kept result re-simulated on request" if valid else "no stored result")
    return pairs


def build_plan(old: dict, new: dict, scenario_set: dict, battle: dict, index: list, *, workers: int = 4,
               resimulate_kept: bool = False) -> dict:
    diff = variant_diff(old, new)
    pairs = classify(new, scenario_set, battle, index, resimulate_kept=resimulate_kept)
    classes = Counter(p["class"] for p in pairs.values())
    cells = Counter()
    for p in pairs.values():
        cells[p["class"]] += p["cells"]
    schedule = sorted(pk for pk, p in pairs.items() if p["class"] == "simulate")
    by_civ = defaultdict(lambda: {"contexts": 0, "cells": 0})
    for pk in schedule:
        p = pairs[pk]
        civ_cells = Counter()
        for ka, kb in p["cellKeys"]:
            civ_cells[ka.split("|")[0]] += 1
            civ_cells[kb.split("|")[0]] += 1
        for civ, n in civ_cells.items():
            by_civ[civ]["contexts"] += 1
            by_civ[civ]["cells"] += n
    changed_profiles = {c["newProfile"] for c in diff["variantsChanged"]} | set(diff["profilesAdded"])
    partner_check = {"changedOrNewProfiles": len(changed_profiles),
                     "scheduledTouchingThem": sum(1 for pk in schedule if set(pk.split("|")) & changed_profiles),
                     "scheduledNotTouchingThem": sum(1 for pk in schedule if not set(pk.split("|")) & changed_profiles)}
    return {"schema": "aoe2-matchup-plan/v1", "diff": diff,
            "pairs": {"total": len(pairs), **dict(sorted(classes.items()))},
            "cells": {"total": sum(cells.values()), **dict(sorted(cells.items()))},
            "keptBySource": dict(sorted(Counter(p.get("keptSource") for p in pairs.values()
                                                if p["class"] == "keep").items())),
            "simulateReasons": dict(sorted(Counter(p.get("reason") for p in pairs.values()
                                                   if p["class"] == "simulate").items())),
            "schedule": schedule, "partnerCheck": partner_check,
            "estimate": estimate(len(schedule), 0, workers),
            "byCivilization": dict(sorted(by_civ.items(), key=lambda kv: (-kv[1]["contexts"], kv[0]))),
            "_pairs": pairs}


def priors_rows(plan: dict, old: dict, index: list, new: dict) -> list:
    """``priors-file`` rows for the scheduled pairs (see module docstring)."""
    rows = {r["pairKey"]: r for r in index}
    old_profile = {v["key"]: v["profileHash"] for v in old["variants"]}
    new_profile = {v["key"]: v["profileHash"] for v in new["variants"]}
    out = []
    for pk in plan["schedule"]:
        outcomes = set()
        for ka, kb in plan["_pairs"][pk]["cellKeys"]:
            if ka not in old_profile or kb not in old_profile:
                continue
            opk = key2(old_profile[ka], old_profile[kb])
            row = rows.get(opk)
            if row is None or row["outcome"] not in ("a_win", "b_win", "close_uncertain"):
                continue
            if row["outcome"] == "close_uncertain":
                outcomes.add("close_uncertain")
                continue
            winner_old = opk.split("|")[0 if row["outcome"] == "a_win" else 1]
            winner = ka if old_profile[ka] == winner_old else kb       # the unit that won before
            first = pk.split("|")[0]
            outcomes.add("a_win" if new_profile[winner] == first else "b_win")
        if outcomes:
            out.append({"pairKey": pk, "outcomes": sorted(outcomes),
                        "source": f"previous-version:{old['bundleHash'][:12]}"})
    return out


def write_outputs(plan: dict, out: Path, *, old: dict | None = None, new: dict | None = None,
                  index: list | None = None, with_priors: bool = False, base_config: dict | None = None,
                  new_bundle_path: str | None = None, index_ref: dict | None = None, run_id: str | None = None,
                  orientation: dict | None = None) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    contexts = (json.dumps(plan["schedule"]) + "\n").encode()
    (out / "contexts.json").write_bytes(contexts)
    written["contexts.json"] = sha256_bytes(contexts)
    priors_ref = None
    if with_priors:
        rows = priors_rows(plan, old, index, new)
        data = gzip.compress("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
                                     for r in rows).encode(), compresslevel=9, mtime=0)
        (out / "priors.jsonl.gz").write_bytes(data)
        written["priors.jsonl.gz"] = sha256_bytes(data)
        plan["priors"] = {"rows": len(rows), "scheduled": len(plan["schedule"])}
        plan["estimate"] = estimate(len(plan["schedule"]), len(rows),
                                    int(next(iter(plan["estimate"]["wallHours"]))))
        priors_ref = {"file": str((out / "priors.jsonl.gz").resolve()), "sha256": written["priors.jsonl.gz"]}
    if base_config is not None:
        import copy
        cfg = copy.deepcopy(base_config)
        cfg["runId"] = run_id or cfg["runId"]
        cfg["description"] = (f"Incremental rerun: {len(plan['schedule'])} contexts of bundle "
                              f"{plan['diff']['new']['bundleHash'][:12]} not covered by the baseline results "
                              "(generated by diff-bundles).")
        cfg["game"] = {"bundle": new_bundle_path, "bundleHash": plan["diff"]["new"]["bundleHash"]}
        cfg.pop("roster", None)
        sel = cfg.setdefault("selection", {})
        sel.update({"mode": "full", "civilizations": None, "units": None, "against": "*",
                    "contexts": {"file": str((out / "contexts.json").resolve()), "sha256": written["contexts.json"]}})
        if index_ref:
            sel["baselineResults"] = index_ref
        if orientation:
            cfg.setdefault("battle", {})["orientation"] = orientation
        if priors_ref:
            cfg.setdefault("sampling", {}).update(forecastSource="priors-file", priors=priors_ref)
        for k in ("output",):
            cfg.pop(k, None)
        (out / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
        written["config.json"] = sha256_bytes((out / "config.json").read_bytes())
    public = {k: v for k, v in plan.items() if not k.startswith("_")}
    (out / "plan.json").write_text(json.dumps(public, indent=2) + "\n")
    (out / "plan.md").write_text(render(public))
    return written


def render(plan: dict) -> str:
    d, e = plan["diff"], plan["estimate"]
    workers = next(iter(e["wallHours"]))
    L = ["# Matchup rerun plan", "",
         f"Old bundle `{d['old']['bundleHash'][:12]}` ({d['old']['variants']} units, {d['old']['civilizations']} "
         f"civilizations) -> new bundle `{d['new']['bundleHash'][:12]}` ({d['new']['variants']} units, "
         f"{d['new']['civilizations']} civilizations).", "",
         "## What changed", "",
         f"- units changed: {len(d['variantsChanged'])}, added: {len(d['variantsAdded'])}, removed: "
         f"{len(d['variantsRemoved'])}; civilizations added: {', '.join(d['civilizationsAdded']) or 'none'}, "
         f"removed: {', '.join(d['civilizationsRemoved']) or 'none'}",
         f"- combat profiles: {d['profilesKept']} kept, {len(d['profilesAdded'])} new, {len(d['profilesRemoved'])} gone"]
    for c in d["variantsChanged"][:30]:
        L.append(f"  - `{c['key']}`: {', '.join(c['fields'])} (profile `{c['oldProfile'][:10]}` -> `{c['newProfile'][:10]}`)")
    if len(d["variantsChanged"]) > 30:
        L.append(f"  - ... {len(d['variantsChanged']) - 30} more")
    p, c = plan["pairs"], plan["cells"]
    L += ["", "## What has to be simulated", "",
          f"**{p.get('simulate', 0):,} new battles (contexts)** must be simulated; "
          f"{p.get('reuse', 0):,} reuse a measured result, {p.get('keep', 0):,} keep a stored (inferred or "
          f"other-engine) result, {p.get('identity', 0):,} are identical-unit pairs.", "",
          "| | contexts | cells shown on the site |", "|---|---:|---:|"]
    for k in ("simulate", "reuse", "keep", "identity"):
        L.append(f"| {k} | {p.get(k, 0):,} | {c.get(k, 0):,} |")
    L += ["", "## Cost", "",
          f"- expected seeds: **{e['expectedSeeds']:,}** ({e['withPrior']:,} contexts with a prior)",
          f"- estimated compute: **{e['workerHours']:,} worker-hours** = about **{e['wallHours'][workers]:,} hours "
          f"on {workers} workers** (conservative: {e['conservativeWorkerHours']:,} worker-hours, "
          f"{e['conservativeWallHours'][workers]:,} h on {workers} workers)",
          f"- basis: {e['basis']}", ""]
    if plan["byCivilization"]:
        L += ["## By civilization (contexts that involve the civilization's units)", "",
              "| Civilization | contexts | cells | ≈ worker-hours |", "|---|---:|---:|---:|"]
        for civ, v in list(plan["byCivilization"].items())[:80]:
            L.append(f"| {civ} | {v['contexts']:,} | {v['cells']:,} | "
                     f"{v['contexts'] * EXPECTED_SEEDS['none'] / SEEDS_PER_WORKER_HOUR:,.1f} |")
        L.append("")
        L.append("A context can involve several civilizations, so the rows add up to more than the total.")
    return "\n".join(L) + "\n"


def civ_breakdown(bundle: dict, pair_keys: set) -> dict:
    """Contexts and displayed cells per civilization for the given profile pairs (roster walk)."""
    by_key = {v["key"]: v for v in bundle["variants"]}
    roster = [by_key[k] for k in bundle["roster"]["units"]]
    contexts = defaultdict(set)
    cells = Counter()
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            if a["civilization"] == b["civilization"]:
                continue
            pk = key2(a["profileHash"], b["profileHash"])
            if pk in pair_keys:
                for civ in (a["civilization"], b["civilization"]):
                    contexts[civ].add(pk)
                    cells[civ] += 1
    return {civ: {"contexts": len(contexts[civ]), "cells": cells[civ]}
            for civ in sorted(contexts, key=lambda c: (-len(contexts[c]), c))}
