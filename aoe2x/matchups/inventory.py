"""Inventory: config + bundle -> the physical battle contexts of a run.

One generic builder replacing the 2026 ``prepare-*.mjs`` scripts (see
RERUN_SYSTEM_PROPOSAL.md section 3.3). The steps follow ``profilesAndPairs()``
and ``context()`` in RB ``aoe2x/js_simulation/node/civ-matchups/phase-one.mjs``
and the job rows of RB ``prepare-adaptive.mjs``:

1. displayed cells = unordered pairs of roster variants from *different*
   civilizations (filtered by ``selection``);
2. variants collapse to combat profiles (``profileHash``); a cell maps to the
   profile pair ``pairKey = "<hashA>|<hashB>"`` (sorted);
3. a pair with the same profile on both sides is an identity pair
   (``equivalent``, never simulated);
4. every other pair gets one physical orientation (player 2 = ``profiles[0]``)
   and its context: counts, weighted costs, scenario, family, policy.

Job ids use the 2026 adaptive formula
``cm_ + digest({profiles, counts, scenarioHash, policy})[:24]`` and
``teamKeys`` take the first bundle variant of each profile, so the 2026
reproduction matches ``adaptive/inventory.jsonl.gz`` row for row.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

from aoe2x.matchups.battle import ContextBuilder
from aoe2x.matchups.bundle import Scenarios, read_json_any, write_json_gz
from aoe2x.matchups.canonical import digest, key2, sha256_bytes

ORIENTATION_SCHEMA = "aoe2-matchup-orientation/v1"


# ------------------------------------------------------------------ orientation

def orientation_table(contexts: dict[str, list[str]], source: dict) -> dict:
    """Store the pairs whose player-2 profile is not the lexicographically smaller one."""
    hashes = sorted({h for profiles in contexts.values() for h in profiles})
    index = {h: i for i, h in enumerate(hashes)}
    reversed_pairs = []
    for pair_key, profiles in contexts.items():
        a, b = pair_key.split("|")
        if profiles == [b, a]:
            reversed_pairs.append([index[a], index[b]])
        elif profiles != [a, b]:
            raise ValueError(f"orientation of {pair_key} is not one of its two profiles")
    body = {"schema": ORIENTATION_SCHEMA, "source": source, "profiles": hashes,
            "reversed": sorted(reversed_pairs), "pairs": len(contexts)}
    return {**body, "tableHash": digest(body)}


def load_orientation(path: Path, expect_hash: str | None = None) -> dict:
    table = read_json_any(path)
    if table.get("schema") != ORIENTATION_SCHEMA:
        raise ValueError(f"{path}: not an orientation table")
    body = {k: v for k, v in table.items() if k != "tableHash"}
    if digest(body) != table["tableHash"]:
        raise ValueError(f"{path}: tableHash mismatch")
    if expect_hash and not table["tableHash"].startswith(expect_hash):
        raise ValueError(f"{path}: orientation table {table['tableHash']} is not the expected {expect_hash}")
    return table


class Orientation:
    def __init__(self, table: dict | None):
        self.reversed = set()
        if table:
            hashes = table["profiles"]
            self.reversed = {f"{hashes[i]}|{hashes[j]}" for i, j in table["reversed"]}

    def __call__(self, pair_key: str) -> tuple[list[str], str]:
        a, b = pair_key.split("|")
        return ([b, a], "table-reversed") if pair_key in self.reversed else ([a, b], "sorted")


# -------------------------------------------------------------------- selection

def _matches(variant: dict, spec: dict) -> bool:
    civs, units = spec.get("civilizations"), spec.get("units")
    if civs is not None and variant["civilization"] not in civs:
        return False
    if units is not None and variant["key"] not in units and variant["slug"] not in units:
        return False
    return True


def load_context_filter(ref: dict | None) -> set | None:
    """``selection.contexts``: the pairKeys a run is restricted to (sha256-checked), or None."""
    if not ref:
        return None
    from aoe2x.matchups.config import ConfigError, resolve_path
    from aoe2x.matchups.paths import REPO_ROOT
    path = resolve_path(ref["file"], REPO_ROOT)
    raw = path.read_bytes()
    if sha256_bytes(raw) != ref["sha256"]:
        raise ConfigError(f"{path} has sha256 {sha256_bytes(raw)}, config expects {ref['sha256']}")
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    text = raw.decode()
    if text.lstrip().startswith("["):
        keys = json.loads(text)
    else:
        keys = [json.loads(line)["pairKey"] for line in text.splitlines() if line.strip()]
    return set(keys)


def select_variants(variants: list[dict], selection: dict) -> tuple[set, set]:
    excluded = set(selection.get("excludeUnits") or [])
    usable = [v for v in variants if v["key"] not in excluded and v["slug"] not in excluded]
    focus = {v["key"] for v in usable if _matches(v, selection)}
    against = selection.get("against", "*")
    opponents = {v["key"] for v in usable} if against == "*" else {v["key"] for v in usable if _matches(v, against)}
    return focus, opponents


# ---------------------------------------------------------------------- builder

def build(cfg: dict, bundle: dict, scenario_set: dict, orientation: dict | None = None,
          setup_hash: str | None = None) -> dict:
    """Return {"jobs", "identity", "summary"}; pure function of its inputs."""
    by_key = {v["key"]: v for v in bundle["variants"]}
    roster = [by_key[k] for k in bundle["roster"]["units"]]  # displayed-cell order
    first_key, mechanics = {}, {}
    for v in bundle["variants"]:  # bundle order decides teamKeys (prepare-adaptive.mjs)
        first_key.setdefault(v["profileHash"], v["key"])
        mechanics.setdefault(v["profileHash"], v["mechanics"])
    focus, opponents = select_variants(roster, cfg["selection"])
    pairs: dict[str, dict] = {}
    cells = 0
    civ_pairs, used_variants = set(), set()
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            if a["civilization"] == b["civilization"]:
                continue
            if not ((a["key"] in focus and b["key"] in opponents) or (b["key"] in focus and a["key"] in opponents)):
                continue
            cells += 1
            civ_pairs.add(key2(a["civilization"], b["civilization"]))
            used_variants.update((a["key"], b["key"]))
            pk = key2(a["profileHash"], b["profileHash"])
            pairs.setdefault(pk, {"cells": 0})["cells"] += 1
    only = load_context_filter(cfg["selection"].get("contexts"))
    if only is not None:
        missing = only - set(pairs)
        if missing:
            raise ValueError(f"selection.contexts names {len(missing)} pairKey(s) outside the selection, "
                             f"e.g. {sorted(missing)[0]}")
        pairs = {pk: v for pk, v in pairs.items() if pk in only}
    scenarios = Scenarios(scenario_set)
    context = ContextBuilder(mechanics, scenarios, cfg["battle"])
    orient = Orientation(orientation)
    jobs, identity = [], []
    orientation_counts = Counter()
    for pk in sorted(pairs):
        a, b = pk.split("|")
        if a == b:
            identity.append({"pairKey": pk, "profileHash": a, "displayedCells": pairs[pk]["cells"],
                             "outcome": "equivalent", "evidenceType": "identity"})
            continue
        profiles, how = orient(pk)
        orientation_counts[how] += 1
        c = context(*profiles)
        row = {"id": "cm_" + digest({"profiles": c["profiles"], "counts": c["counts"],
                                      "scenarioHash": c["scenarioHash"], "policy": c["policy"]})[:24],
               "pairKey": pk, "teamKeys": [first_key[h] for h in profiles], "profileHashes": profiles,
               "counts": c["counts"], "weightedCosts": c["weightedCosts"], "scenarioHash": c["scenarioHash"],
               "family": c["family"], "engineFamily": c["engineFamily"], "policy": c["policy"],
               "contextHash": digest(c), "displayedCells": pairs[pk]["cells"], "orientation": how}
        if setup_hash:
            row["resultKey"] = digest({"contextHash": row["contextHash"], "setupHash": setup_hash})
        jobs.append(row)
    if len({j["id"] for j in jobs}) != len(jobs):
        raise ValueError("duplicate job ids")
    scenario_hashes = Counter(j["scenarioHash"] for j in jobs)
    summary = {
        "variants": len(used_variants), "rosterVariants": len(roster),
        "profiles": len({by_key[k]["profileHash"] for k in used_variants}),
        "civilizations": len({by_key[k]["civilization"] for k in used_variants}),
        "cells": cells, "civilizationPairs": len(civ_pairs), "profilePairs": len(pairs),
        "identityPairs": len(identity), "identityCells": sum(r["displayedCells"] for r in identity),
        "contexts": len(jobs), "orientation": dict(sorted(orientation_counts.items())),
        "families": dict(sorted(Counter(j["family"] for j in jobs).items())),
        "engineFamilies": dict(sorted(Counter(j["engineFamily"] for j in jobs).items())),
        "scenarioHashes": dict(sorted(scenario_hashes.items())),
        "pairKeysDigest": digest(sorted(pairs)),
        "contextPairKeysDigest": digest([j["pairKey"] for j in jobs]),
        "contextsDigest": digest([j["contextHash"] for j in jobs]),
    }
    return {"jobs": jobs, "identity": identity, "summary": summary}


def write(result: dict, directory: Path, header: dict) -> dict:
    """Write jobs.jsonl.gz, identity-pairs.jsonl.gz and inventory-summary.json."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, rows in (("jobs.jsonl.gz", result["jobs"]), ("identity-pairs.jsonl.gz", result["identity"])):
        data = gzip.compress("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows).encode(),
                            compresslevel=9, mtime=0)
        (directory / name).write_bytes(data)
        files[name] = {"sha256": sha256_bytes(data), "rows": len(rows), "bytes": len(data)}
    summary = {**header, **result["summary"], "files": files}
    (directory / "inventory-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def compare_with_reference(jobs: list[dict], reference: list[dict]) -> dict:
    """Field-by-field comparison with a 2026 inventory (e.g. RB adaptive/inventory.jsonl.gz)."""
    fields = ("id", "pairKey", "teamKeys", "profileHashes", "counts", "weightedCosts", "scenarioHash",
              "family", "engineFamily", "policy")
    ours = {j["pairKey"]: j for j in jobs}
    theirs = {r["pairKey"]: r for r in reference}
    differing = Counter()
    examples = {}
    for pk in set(ours) & set(theirs):
        for f in fields:
            if ours[pk].get(f) != theirs[pk].get(f):
                differing[f] += 1
                examples.setdefault(f, pk)
    return {"ours": len(ours), "reference": len(theirs), "common": len(set(ours) & set(theirs)),
            "onlyOurs": len(set(ours) - set(theirs)), "onlyReference": len(set(theirs) - set(ours)),
            "samePairKeySet": set(ours) == set(theirs), "differingFields": dict(differing),
            "examples": examples, "identical": set(ours) == set(theirs) and not differing}
