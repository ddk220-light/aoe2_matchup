"""Mechanics bundles and scenario sets: the frozen inputs of a matchup run.

A **mechanics bundle** is one self-contained, hash-identified file holding the
unit roster and every roster variant's runtime combat mechanics for one game
build. Runs read the bundle, never the live reference DB, so regenerating or
swapping ``data/golden/aoe2_reference_simulation.db`` (a simulator
configuration input of the live site) cannot silently change a run.

Two producers:

* :func:`import_campaign_2026` freezes exactly what the 2026 campaigns used:
  the ``profiles``/``roster`` of the frozen definition
  ``RB:<campaigns>/unit-rankings-path-recovery-2026-10-29/manifest.json``
  (campaign hash ``1ac49a6a...``, reference DB ``234ad0a6...``). Every 2026
  runner loaded mechanics from that file as ``FROZEN``.
* :func:`export_from_reference_db` builds a bundle from any reference DB
  path (a future patch or DLC). It ports the roster rule of
  ``RB:aoe2x/js_simulation/tools/export_ranking_roster.py`` (``export_roster``)
  and the per-variant query of ``prepareFull()`` in
  ``RB:aoe2x/js_simulation/node/full-ranking-campaign.mjs``.

A **scenario set** holds the arena scenarios (map, formations, opening
patrols) keyed by scenario hash, in their frozen order. Order matters: a
family/engine-family combination with no authored scenario clones the first
scenario of that family (``scenario()`` in RB forecast-validation-lib.mjs).
"""
from __future__ import annotations

import gzip
import json
import sqlite3
from collections import Counter
from pathlib import Path

from aoe2x.matchups.canonical import digest, profile_hash, sha256_bytes

BUNDLE_SCHEMA = "aoe2-matchup-mechanics-bundle/v1"
SCENARIO_SCHEMA = "aoe2-matchup-scenario-set/v1"

FROZEN_2026_CAMPAIGN_HASH = "1ac49a6abf1f3a1a104c7bcf675a3a327b6939d49273ae49c51eb6157264693d"
FROZEN_2026_REFERENCE_DB_SHA256 = "234ad0a6c40e413563f737886f6eed2e71c0de41a6a373b569d34dbcaa5c0216"

MECHANICS_QUERY = ("ref_units JOIN ref_unit_mechanics ON ref_unit_id=id "
                   "WHERE age='Imperial' AND is_default=1")

# RB:aoe2x/js_simulation/tools/export_ranking_roster.py PATCH_LINES / GROUPS.
DEFAULT_ROSTER_RULE = {
    "rule": "ranking-roster-v1",
    "groups": {"Infantry": "infantry", "Ranged": "archery", "Cavalry": "stable"},
    "extraLines": {
        "heavy_mounted_crossbowman": "cav_archer",
        "elite_varangian_guard": "militia",
        "elite_hearth_troop_saxons": "militia",
        "elite_jomsviking_danes": "militia",
        "elite_jarl_varangians": "gunpowder",  # Ranged, as specified by the owner.
    },
    "excludeKeys": [],
    "requireModes": {"war_chariot_shu": "focus_fire"},
}


# --------------------------------------------------------------------------- io

def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def write_json_gz(value, path: Path) -> bytes:
    """Deterministic gzip (mtime 0) so the same content gives the same bytes."""
    data = gzip.compress(_json_bytes(value), compresslevel=9, mtime=0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def read_json_any(path: Path):
    data = Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return json.loads(data)


# ---------------------------------------------------------------------- bundles

def bundle_hash(bundle: dict) -> str:
    return digest({k: v for k, v in bundle.items() if k != "bundleHash"})


def seal(bundle: dict) -> dict:
    bundle = {k: v for k, v in bundle.items() if k != "bundleHash"}
    bundle["bundleHash"] = digest(bundle)
    return bundle


def load_bundle(path: Path, expect_hash: str | None = None) -> dict:
    bundle = read_json_any(path)
    if bundle.get("schema") != BUNDLE_SCHEMA:
        raise ValueError(f"{path}: not a mechanics bundle ({bundle.get('schema')!r})")
    actual = bundle_hash(bundle)
    if actual != bundle["bundleHash"]:
        raise ValueError(f"{path}: bundleHash {bundle['bundleHash']} but content hashes to {actual}")
    if expect_hash and not actual.startswith(expect_hash):
        raise ValueError(f"{path}: bundle {actual} is not the expected {expect_hash}")
    for v in bundle["variants"]:
        if profile_hash(v["mechanics"]) != v["profileHash"]:
            raise ValueError(f"{path}: profile hash of {v['key']} does not match its mechanics")
    return bundle


def _variant(unit: dict, mechanics: dict, *, reference_id, source_build, stored_hash, purchase_cost) -> dict:
    return {
        "key": f"{unit['civilization']}|{unit['slug']}",
        "civilization": unit["civilization"], "slug": unit["slug"], "name": unit["name"],
        "line": unit["line"], "group": unit["group"], "mode": unit["mode"],
        "referenceId": reference_id, "sourceBuild": source_build,
        "storedMechanicsHash": stored_hash, "referencePurchaseCost": purchase_cost,
        "mechanicsHash": digest(mechanics),
        "profileHash": profile_hash(mechanics),
        "mechanics": mechanics,
    }


def summarize_bundle(bundle: dict) -> dict:
    variants = bundle["variants"]
    return {"bundleHash": bundle["bundleHash"], "variants": len(variants),
            "profiles": len({v["profileHash"] for v in variants}),
            "civilizations": len({v["civilization"] for v in variants}),
            "groups": dict(sorted(Counter(v["group"] for v in variants).items())),
            "excluded": len(bundle["roster"]["excluded"]),
            "game": bundle["game"]}


def import_campaign_2026(rb) -> tuple[dict, dict]:
    """Freeze the 2026 campaign definition from RB into (bundle, scenario set)."""
    from aoe2x.matchups.rbsource import FROZEN_DEFINITION
    raw = rb.show(FROZEN_DEFINITION)
    frozen = json.loads(raw)
    body = {k: v for k, v in frozen.items() if k != "campaignHash"}
    if digest(body) != frozen["campaignHash"] or frozen["campaignHash"] != FROZEN_2026_CAMPAIGN_HASH:
        raise ValueError("frozen definition hash mismatch")
    if frozen["referenceDbSha256"] != FROZEN_2026_REFERENCE_DB_SHA256:
        raise ValueError("frozen definition names a different reference DB")
    roster = frozen["roster"]
    units = {f"{u['civilization']}|{u['slug']}": u for u in roster["units"]}
    if set(units) != set(frozen["profiles"]):
        raise ValueError("roster units and profiles differ")
    variants = []
    # Keep the frozen profile insertion order: 2026 job teamKeys used the first
    # variant of each profile hash in this order (prepare-adaptive.mjs).
    for key, entry in frozen["profiles"].items():
        v = _variant(units[key], entry["mechanics"], reference_id=entry["referenceId"],
                     source_build=entry["sourceBuild"], stored_hash=entry["storedMechanicsHash"],
                     purchase_cost=entry["referencePurchaseCost"])
        if v["mechanicsHash"] != entry["profileHash"]:
            raise ValueError(f"mechanics hash mismatch for {key}")
        variants.append(v)
    source_builds = sorted({v["sourceBuild"] for v in variants})
    bundle = seal({
        "schema": BUNDLE_SCHEMA,
        "bundleId": "campaign-2026-185872-188329",
        "description": ("Unit roster and combat mechanics of the Oct 31 - Nov 11, 2026 civ-matchup "
                        "campaigns (build 185872 plus the selected 188329 changes), frozen from the "
                        "2026 ranking definition."),
        "game": {
            "gameBuild": "185872+188329-selected",
            "datSha256": source_builds[0] if len(source_builds) == 1 else source_builds,
            "referenceDb": frozen["referenceDb"],
            "referenceDbSha256": frozen["referenceDbSha256"],
            "referenceDbCommit": "58e480b76",
            "mechanicsQuery": MECHANICS_QUERY,
        },
        "source": {
            "kind": "campaign-definition",
            "branch": rb.ref.removeprefix("origin/"),
            "branchTip": rb.commit(),
            "path": FROZEN_DEFINITION,
            "fileSha256": sha256_bytes(raw),
            "campaignHash": frozen["campaignHash"],
        },
        "roster": {
            "rule": dict(DEFAULT_ROSTER_RULE),
            "scope": roster["scope"], "source": roster["source"],
            "units": [f"{u['civilization']}|{u['slug']}" for u in roster["units"]],
            "excluded": roster["excluded"],
            "counts": roster["counts"], "civilizations": roster["civilizations"],
        },
        "variants": variants,
    })
    scenarios = scenario_set_from_frozen(frozen, sha256_bytes(raw))
    return bundle, scenarios


def roster_from_reference_db(conn: sqlite3.Connection, rule: dict | None = None) -> dict:
    """Port of ``export_roster()`` (RB:aoe2x/js_simulation/tools/export_ranking_roster.py)."""
    from aoe2x.rank.derive_unit_rankings import build_slug_to_line
    from aoe2x.sim.unit_lines import CIV_MISSING_UNITS, UNIT_LINES
    rule = {**DEFAULT_ROSTER_RULE, **(rule or {})}
    lines = build_slug_to_line() | rule["extraLines"]
    groups = {line: group for group, aggregate in rule["groups"].items()
              for line in UNIT_LINES[aggregate]["sub_lines"]}
    excluded_keys = {tuple(k.split("|", 1)) for k in rule.get("excludeKeys", [])}
    rows = conn.execute("""SELECT u.id,u.civ_name,u.unit_slug,u.unit_name,u.unit_type,
        m.mode,m.is_default,m.mechanics_json FROM ref_units u
        LEFT JOIN ref_unit_mechanics m ON u.id=m.ref_unit_id AND m.is_default=1
        WHERE u.age='Imperial' ORDER BY u.civ_name,u.unit_slug""").fetchall()
    units, excluded, seen = [], [], set()
    for row in rows:
        key = (row["civ_name"], row["unit_slug"])
        if key in seen:
            raise ValueError(f"Duplicate default profile: {key}")
        seen.add(key)
        line = lines.get(row["unit_slug"])
        group = groups.get(line)
        entry = {"referenceId": row["id"], "civilization": key[0], "slug": key[1],
                 "name": row["unit_name"], "line": line, "group": group, "mode": row["mode"]}
        if key in CIV_MISSING_UNITS:
            excluded.append(entry | {"reason": "civilization cannot field this line"})
        elif key in excluded_keys:
            excluded.append(entry | {"reason": "excluded by run configuration"})
        elif group:
            if not row["mechanics_json"]:
                raise ValueError(f"Missing mechanics: {key}")
            required = rule.get("requireModes", {}).get(key[1])
            if required and row["mode"] != required:
                raise ValueError(f"{key[1]} must use mode {required}")
            units.append(entry)
        else:
            if line is None and not (row["unit_type"] == "naval" or any(
                    name in key[1] for name in ("galleon", "longship", "xebec"))):
                raise ValueError(f"Unclassified Imperial land unit: {key}")
            excluded.append(entry | {"reason": "naval or anti-building/siege group outside agreed land pools"})
    return {"scope": "Imperial Infantry, Ranged and Cavalry; scoring deferred",
            "source": "UNIT_LINES first-line-wins plus explicit patch185872 additions",
            "units": units, "excluded": excluded,
            "counts": dict(Counter(u["group"] for u in units)),
            "civilizations": len({u["civilization"] for u in units})}


def export_from_reference_db(db_path: Path, *, rule: dict | None = None, game_build: str,
                             bundle_id: str | None = None, description: str = "") -> dict:
    """Build a bundle from a reference DB (``aoe2_reference_simulation.db`` schema), read-only."""
    db_path = Path(db_path)
    db_sha = sha256_bytes(db_path.read_bytes())
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        roster = roster_from_reference_db(conn, rule)
        variants = []
        for unit in roster["units"]:
            # prepareFull(): exactly one default Imperial mechanics row per (civ, slug).
            rows = conn.execute("""SELECT u.id,u.final_cost_food,u.final_cost_wood,u.final_cost_gold,
                m.mechanics_json,m.mechanics_hash,m.source_build FROM ref_units u
                JOIN ref_unit_mechanics m ON m.ref_unit_id=u.id
                WHERE u.civ_name=? AND u.unit_slug=? AND u.age='Imperial' AND m.is_default=1""",
                                (unit["civilization"], unit["slug"])).fetchall()
            if len(rows) != 1:
                raise ValueError(f"missing/ambiguous {unit['civilization']}|{unit['slug']}")
            r = rows[0]
            mechanics = json.loads(r["mechanics_json"])
            for field in ("provenance", "mode_validation"):
                if field in mechanics:
                    raise ValueError("runtime mechanics must not contain calibration provenance")
            variants.append(_variant(unit, mechanics, reference_id=r["id"], source_build=r["source_build"],
                                     stored_hash=r["mechanics_hash"],
                                     purchase_cost={"food": r["final_cost_food"], "wood": r["final_cost_wood"],
                                                    "gold": r["final_cost_gold"]}))
    finally:
        conn.close()
    source_builds = sorted({v["sourceBuild"] for v in variants})
    return seal({
        "schema": BUNDLE_SCHEMA,
        "bundleId": bundle_id or f"reference-{game_build}-{db_sha[:8]}",
        "description": description,
        "game": {"gameBuild": game_build,
                 "datSha256": source_builds[0] if len(source_builds) == 1 else source_builds,
                 "referenceDb": db_path.name, "referenceDbSha256": db_sha,
                 "mechanicsQuery": MECHANICS_QUERY},
        "source": {"kind": "reference-db", "referenceDbSha256": db_sha},
        "roster": {"rule": {**DEFAULT_ROSTER_RULE, **(rule or {})},
                   "scope": roster["scope"], "source": roster["source"],
                   "units": [f"{u['civilization']}|{u['slug']}" for u in roster["units"]],
                   "excluded": roster["excluded"], "counts": roster["counts"],
                   "civilizations": roster["civilizations"]},
        "variants": variants,
    })


def compare_bundles(a: dict, b: dict) -> dict:
    """Roster and per-variant mechanics differences (order-insensitive)."""
    va = {v["key"]: v for v in a["variants"]}
    vb = {v["key"]: v for v in b["variants"]}
    changed = sorted(k for k in set(va) & set(vb) if va[k]["mechanicsHash"] != vb[k]["mechanicsHash"])
    return {"onlyInA": sorted(set(va) - set(vb)), "onlyInB": sorted(set(vb) - set(va)),
            "changedMechanics": changed,
            "sameRosterOrder": a["roster"]["units"] == b["roster"]["units"],
            "sameExcluded": a["roster"]["excluded"] == b["roster"]["excluded"],
            "identicalVariants": not changed and set(va) == set(vb)}


# -------------------------------------------------------------------- scenarios

def scenario_set_from_frozen(frozen: dict, source_sha: str) -> dict:
    scenarios = [{"hash": h, "scenario": s} for h, s in frozen["scenarios"].items()]
    for entry in scenarios:
        if digest(entry["scenario"]) != entry["hash"]:
            raise ValueError("scenario hash mismatch")
    body = {"schema": SCENARIO_SCHEMA, "scenarioSetId": "frozen-ranking-scenarios-v1",
            "description": ("The five arena scenarios of the 2026 frozen ranking definition: "
                            "16x16 golden map, recorded 27-cell formations, opening patrols."),
            "source": {"campaignHash": frozen["campaignHash"], "fileSha256": source_sha},
            "engineConfig": frozen["engineConfig"],
            "fallback": "first listed scenario of the family with engineFamily replaced",
            "scenarios": scenarios}
    return {**body, "setHash": digest(body)}


def load_scenario_set(path: Path) -> dict:
    data = read_json_any(path)
    if data.get("schema") != SCENARIO_SCHEMA:
        raise ValueError(f"{path}: not a scenario set")
    body = {k: v for k, v in data.items() if k != "setHash"}
    if digest(body) != data["setHash"]:
        raise ValueError(f"{path}: setHash mismatch")
    return data


class Scenarios:
    """Scenario lookup with the 2026 family fallback."""

    def __init__(self, scenario_set: dict):
        self.set = scenario_set
        self.by_hash = {e["hash"]: e["scenario"] for e in scenario_set["scenarios"]}
        self.by_key = {}
        self.first_of_family = {}
        for e in scenario_set["scenarios"]:
            s = e["scenario"]
            key = (s["family"], s["engineFamily"])
            if key in self.by_key:
                raise ValueError(f"duplicate scenario {key}")
            self.by_key[key] = e["hash"]
            self.first_of_family.setdefault(s["family"], s)

    def resolve(self, family: str, engine_family: str) -> tuple[str, dict]:
        """``context()`` in RB phase-one.mjs / ``scenario()`` in forecast-validation-lib.mjs."""
        h = self.by_key.get((family, engine_family))
        if h:
            return h, self.by_hash[h]
        base = self.first_of_family.get(family)
        if base is None:
            raise KeyError(f"no scenario for family {family}")
        scenario = {**base, "engineFamily": engine_family}
        return digest(scenario), scenario
