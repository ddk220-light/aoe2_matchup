"""``build-db``: the Matchup Advisor serving DB from a result index plus run snapshots.

Output schema = ``scripts/build_advisor_first_pass.py`` (tables ``metadata``,
``units``, ``evidence``, ``cells``; 32 KiB pages), so
``apps/backend/aoe2_api/services/advisor.py`` and
``scripts/migration/export_data.py`` read it unchanged. What visitors get
(``/api/advisor-catalog``, ``/api/advisor-matchups/<civ>``) depends only on
``units``, ``cells`` and the ``dataset`` metadata; ``evidence`` is served only
by ``/api/advisor-evidence/<id>`` (no caller in ``apps/web``).

Inputs
------
* a run config (``game`` -> mechanics bundle = the unit roster; ``battle`` +
  ``engine`` + scenario set -> the setup every result must belong to);
* a **result index** (``import-results`` output, 2026 baseline): one row per
  profile pair;
* zero or more **run snapshots** (``export`` output), applied in order.

Merge rules (README "Seams for steps 4-5")
------------------------------------------
1. Start from the index rows, keyed by ``pairKey``.
2. A snapshot's ``results.jsonl.gz`` row replaces the row with the same
   ``pairKey`` (later snapshots win). Its manifest is verified first: file and
   snapshot hashes, ``bundleHash``, ``setupHash``, engine ``filesDigest`` equal
   to the config's, ``resultIndexSha256`` equal to the index used here.
3. ``reused.jsonl.gz`` rows keep their index row (checked: same ``resultKey``
   and outcome).
4. ``blocked.jsonl.gz`` rows have no new result. If the index has a row for
   the same ``pairKey`` it is kept and marked; otherwise the displayed cells of
   that pair keep the **previous release's** result (``--previous-db``: the
   pair of the units' previous profiles) and are marked. Marked cells get
   ``flags`` bit ``FLAG_NOT_RESIMULATED`` (4) - the site reads only columns
   0-5 of a cell row (``apps/web/src/features/advisor/{model.mjs,view.js}``), so
   it ignores the flag today - and their evidence row carries ``rerun`` /
   ``carriedTo`` details.
5. A displayed cell whose pair has no result at all is an error, unless
   ``carry_unsimulated`` is set (then it is carried from the previous release
   like a blocked one): a partial run never silently publishes holes.
6. Every non-identity result must belong to this setup: its stored physical
   context must equal the context the config's battle rules give for the same
   two profiles in the same order. Identity pairs (same profile on both sides)
   are ``equivalent`` by definition and need no stored row.

Identifiers
-----------
Unit ids and evidence ids appear in the API output. Without a previous DB they
follow the 2026 builder: units in sorted-key order, evidence ids in order of
first appearance while walking the displayed cells in roster order (this
reproduces the 2026 ids exactly). With ``--previous-db`` every unit key and
every ``pairKey`` that still exists keeps its previous id; new ones get the
next free ids (same order rule), removed ones leave gaps. So a release that
touches some civilizations leaves the API output of the others byte-identical.

Compact evidence (``EVIDENCE_FORMAT``)
-------------------------------------
One zlib (dictionary) JSON object per used ``pairKey``: ``pairKey``,
``outcome``, ``evidenceType``, physical ``context``, ``source`` and the short
labels of the row (``jobId``, ``evidenceLevel``, ``validationMode``,
``ruleId``/``ruleVersion``, run fields), per-seed summaries ``seeds`` in
``COMPACT_SEED_FIELDS`` order and the engine labels ``physics``. Dropped
against the 2026 DB: per-seed ``finalStateHash``/``eventLogHash`` and the
journal/record hashes (kept in the result index and run snapshots, whose
sha256 are in the ``matchup_build`` metadata), ``contextHash`` (= digest of
``context``), and the cumulative 2026 provenance chains (``originalEvidence``,
``originalPrediction``/``prediction*``, ``sourceContext``, ``rootAnchorIds``,
``reasonCodes``, ``sourceRunIds``/``validationRunIds``, and the
``forecastValidation``/``mismatchValidation``/``recoveryValidation`` review
blocks); those stay in git history of ``data/golden/civ_matchups_first_pass.db``
(blob ``bdbbeacf...``) and on RB.
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import zlib
from collections import Counter, defaultdict
from pathlib import Path

from aoe2x.matchups.battle import ContextBuilder
from aoe2x.matchups.bundle import Scenarios
from aoe2x.matchups.canonical import digest, key2, sha256_bytes
from aoe2x.matchups.paths import BASELINES_DIR, REPO_ROOT

BUILD_SCHEMA = "aoe2-matchup-serving-build/v1"
EVIDENCE_FORMAT = "aoe2-advisor-evidence-compact/v1"
COMPACT_SEED_FIELDS = ["seed", "winnerOwner", "ticks", "unitRemainingHp", "opponentRemainingHp", "unitSurvivors",
                       "opponentSurvivors", "unitStartingHp", "opponentStartingHp"]
FLAG_NOT_RESIMULATED = 4
MAX_BYTES = 95 * 1024 * 1024          # proposal section 9.3: fail well before GitHub's 100 MiB limit
PAGE_SIZE = 32768
DATASET_2026 = BASELINES_DIR / "campaign-2026" / "serving-dataset.json"
OUTCOMES = ("a_win", "b_win", "close_uncertain", "equivalent")
INVERSE = {"a_win": "b_win", "b_win": "a_win", "equivalent": "equivalent", "close_uncertain": "close_uncertain"}
SCHEMA_SQL = '''
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE units (id INTEGER PRIMARY KEY, key TEXT UNIQUE, civilization TEXT, data TEXT);
        CREATE INDEX units_civ ON units(civilization);
        CREATE TABLE evidence (id INTEGER PRIMARY KEY, data BLOB);
        CREATE TABLE cells (a INTEGER, b INTEGER, outcome TEXT, evidence_type TEXT,
            count_a INTEGER, count_b INTEGER, tier TEXT, flags INTEGER, evidence_id INTEGER,
            PRIMARY KEY(a,b));
        CREATE INDEX cells_b ON cells(b);
    '''


class BuildError(ValueError):
    pass


def encode(value, ascii_only: bool = False) -> str:
    """The 2026 builder's JSON encoding (sorted keys, no whitespace)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii_only, allow_nan=False)


def gz_rows(raw: bytes) -> list:
    return [json.loads(line) for line in gzip.decompress(raw).decode().splitlines() if line.strip()]


# ------------------------------------------------------------------- inputs

def load_index(path: Path, expect_sha256: str | None = None) -> tuple[list, str]:
    raw = Path(path).read_bytes()
    sha = sha256_bytes(raw)
    if expect_sha256 and sha != expect_sha256:
        raise BuildError(f"{path} has sha256 {sha}, expected {expect_sha256}")
    return gz_rows(raw), sha


def load_snapshot(directory: Path) -> dict:
    """Read and verify an ``export`` snapshot directory."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema") != "aoe2-matchup-run-snapshot/v1":
        raise BuildError(f"{directory}: not a run snapshot ({manifest.get('schema')!r})")
    body = {k: v for k, v in manifest.items() if k != "snapshotHash"}
    if digest(body) != manifest["snapshotHash"]:
        raise BuildError(f"{directory}: snapshotHash does not match its manifest")
    files = {}
    for name, info in manifest["files"].items():
        raw = (directory / name).read_bytes()
        if sha256_bytes(raw) != info["sha256"]:
            raise BuildError(f"{directory}/{name} does not match the snapshot manifest")
        files[name] = gz_rows(raw)
    return {"dir": str(directory), "manifest": manifest, "results": files["results.jsonl.gz"],
            "reused": files["reused.jsonl.gz"], "blocked": files["blocked.jsonl.gz"],
            "manifestSha256": sha256_bytes((directory / "manifest.json").read_bytes())}


def read_db(path: Path) -> dict:
    """Units, cells and decoded evidence of an existing serving DB (any evidence format)."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        meta = dict(db.execute("SELECT key, value FROM metadata WHERE key != 'compression_dictionary'"))
        units = {i: json.loads(d) for i, d in db.execute("SELECT id, data FROM units")}
        evidence = {i: json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
                    for i, blob in db.execute("SELECT id, data FROM evidence")}
        cells = db.execute("SELECT * FROM cells ORDER BY a, b").fetchall()
    finally:
        db.close()
    return {"path": str(path), "sha256": sha256_bytes(Path(path).read_bytes()), "bytes": Path(path).stat().st_size,
            "metadata": meta, "units": units, "evidence": evidence, "cells": cells, "dictionary": dictionary}


# -------------------------------------------------------------------- merge

def merge(index: list, snapshots: list, setup: dict) -> tuple[dict, dict, dict]:
    """Rows by pairKey after applying the snapshots; markers for blocked contexts; merge counts."""
    rows = {}
    for r in index:
        if r["pairKey"] in rows:
            raise BuildError(f"index has {r['pairKey']} twice")
        rows[r["pairKey"]] = r
    blocked: dict[str, dict] = {}
    counts = Counter()
    for snap in snapshots:
        m = snap["manifest"]
        for field, expected in (("bundleHash", setup["bundleHash"]), ("setupHash", setup["setupHash"])):
            if m[field] != expected:
                raise BuildError(f"{snap['dir']}: {field} {m[field]} is not this build's {expected}")
        if m["engine"]["filesDigest"] != setup["engineFilesDigest"]:
            raise BuildError(f"{snap['dir']}: engine files digest differs from the config's engine")
        if m.get("resultIndexSha256") not in (None, setup["indexSha256"]):
            raise BuildError(f"{snap['dir']}: run used result index {m['resultIndexSha256']}, "
                             f"this build uses {setup['indexSha256']}")
        run_id = m["runId"]
        seen = set()
        for r in snap["results"]:
            pk = r["pairKey"]
            if pk in seen:
                raise BuildError(f"{snap['dir']}: {pk} twice")
            seen.add(pk)
            if r.get("evidenceType") != "observed" or r.get("outcome") not in OUTCOMES[:3] or not r.get("seeds"):
                raise BuildError(f"{snap['dir']}: {pk} is not an observed result")
            if digest(r["context"]) != r["contextHash"]:
                raise BuildError(f"{snap['dir']}: {pk} contextHash does not match its context")
            counts["replaced" if pk in rows else "added"] += 1
            rows[pk] = {**r, "_previous": (rows.get(pk) or {}).get("source")}
            blocked.pop(pk, None)
        for job_id, pk, result_key, outcome in snap["reused"]:
            base = rows.get(pk)
            if not base or base.get("resultKey") != result_key or base.get("outcome") != outcome:
                raise BuildError(f"{snap['dir']}: reused {job_id} does not match the index row for {pk}")
            counts["reused"] += 1
        for b in snap["blocked"]:
            if b["pairKey"] in seen:
                raise BuildError(f"{snap['dir']}: {b['pairKey']} is both reviewed and blocked")
            blocked[b["pairKey"]] = {"status": "blocked", "runId": run_id, "jobId": b["jobId"],
                                     "contextHash": b["contextHash"], "failedAttempts": b["failedAttempts"],
                                     "lastError": b["lastError"], "seedsCompleted": b["seedsCompleted"]}
            counts["blocked"] += 1
    return rows, blocked, dict(counts)


# ----------------------------------------------------------------- evidence

def compact_seed(seed: list, mixed: bool) -> list:
    out = list(seed[:len(COMPACT_SEED_FIELDS)])
    return out + [seed[-1]] if mixed else out


def compact_evidence(row: dict, context: dict | None) -> dict:
    """One serving evidence object from a result-index / snapshot row (``EVIDENCE_FORMAT``)."""
    out = {"pairKey": row["pairKey"], "outcome": row["outcome"], "evidenceType": row["evidenceType"],
           "context": context, "source": row.get("source")}
    for field in ("jobId", "evidenceLevel", "validationMode", "ruleId", "ruleVersion", "samplingPolicy",
                  "changed", "priorOutcomes", "physicsVersions"):
        if row.get(field) is not None:
            out[field] = row[field]
    seeds = row.get("seeds") or []
    if seeds:
        physics = sorted({s[-1] for s in seeds})
        out["physics"] = physics
        out["seeds"] = [compact_seed(s, len(physics) > 1) for s in seeds]
    mirror = row.get("mirrorValidation")
    if mirror:
        mp = sorted({s[-1] for s in mirror["seeds"]})
        out["mirror"] = {"jobId": mirror["jobId"], "physics": mp,
                         "seeds": [compact_seed(s, len(mp) > 1) for s in mirror["seeds"]]}
    if row.get("_previous") is not None or str(row.get("source", "")).startswith("run:"):
        out["replaces"] = row.get("_previous")
    return out


def make_dictionary(profile_hashes: list, scenario_hashes: list, policy: str) -> bytes:
    """zlib preset dictionary: profile and scenario hashes + the recurring JSON vocabulary."""
    template = encode({"context": {"counts": [27, 27], "engineFamily": "kite", "family": "ranged_vs_melee",
                                   "policy": policy, "profiles": [], "scenarioHash": "", "weightedCosts": []},
                       "evidenceLevel": "single_seed_confirmation", "evidenceType": "observed",
                       "jobId": "fv_", "outcome": "a_win", "pairKey": "", "physics": ["frozen-civ-matchups-v3"],
                       "seeds": [[0, 2]], "source": "forecast-validation",
                       "validationMode": "single_seed_forecast_screen"})
    words = ("melee_vs_melee melee_vs_ranged ranged_vs_ranged waves siege rvr b_win close_uncertain "
             "equivalent inferred identity first-pass-inference first-pass-observed mismatch-validation "
             "fresh_seed_set multi_seed_validation exact_replay_of_measured_seed_set ruleId R1_STATIC_DIRECTION "
             "R2_ROBUST_TRADEOFF ruleVersion phase1-direct-root-inert-group-v5c "
             "frozen-civ-matchups-v3:adaptive-2026-10-31 ranking-corrected-engine-2026-10-29 ")
    text = ",".join(sorted(profile_hashes)) + "," + ",".join(sorted(scenario_hashes)) + words + template
    return text.encode()[-32768:]


def zpack(value: dict, dictionary: bytes) -> bytes:
    c = zlib.compressobj(9, zdict=dictionary)
    return c.compress(encode(value).encode()) + c.flush()


# -------------------------------------------------------------------- build

def unit_costs(variants: list, source: str, reference_db: Path | None) -> dict:
    """``units.data.costs``: from a reference DB (2026 builder default) or the bundle."""
    if source == "bundle":
        return {v["key"]: {k: float(v["referencePurchaseCost"][k]) for k in ("food", "wood", "gold")}
                for v in variants}
    ref = sqlite3.connect(f"file:{reference_db}?mode=ro", uri=True)
    ref.row_factory = sqlite3.Row
    out, missing = {}, []
    try:
        for v in variants:
            r = ref.execute("SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
                            (v["civilization"], v["slug"], "Imperial")).fetchone()
            if r is None:
                missing.append(v["key"])
                continue
            out[v["key"]] = {k: r[f"final_cost_{k}"] for k in ("food", "wood", "gold")}
    finally:
        ref.close()
    if missing:
        raise BuildError(f"{len(missing)} roster unit(s) are not in {reference_db} (e.g. {missing[0]}); "
                         "pass the new reference DB with --costs-db or use --costs bundle")
    return out


def build(*, bundle: dict, scenario_set: dict, battle: dict, setup_hash: str, engine_files_digest: str,
          index: list, index_sha256: str, snapshots: list, out: Path, previous: dict | None = None,
          dataset_base: str | None = None, costs: str = "reference-db",
          costs_db: Path = REPO_ROOT / "data/golden/aoe2_reference_simulation.db",
          carry_unsimulated: bool = False, max_bytes: int = MAX_BYTES) -> dict:
    """Write the serving DB to ``out`` (atomically) and return the build record."""
    setup = {"bundleHash": bundle["bundleHash"], "setupHash": setup_hash, "engineFilesDigest": engine_files_digest,
             "indexSha256": index_sha256}
    rows, blocked, merge_counts = merge(index, snapshots, setup)
    by_key = {v["key"]: v for v in bundle["variants"]}
    roster = [by_key[k] for k in bundle["roster"]["units"]]
    mechanics = {}
    for v in bundle["variants"]:
        mechanics.setdefault(v["profileHash"], v["mechanics"])
    context_of = ContextBuilder(mechanics, Scenarios(scenario_set), battle)
    presentation = json.loads((REPO_ROOT / "aoe2x/assets/presentation.json").read_text())
    prices = unit_costs(roster, costs, costs_db)

    # ---- units (ids stable against the previous release when given)
    prev_unit_id = {u["key"]: i for i, u in previous["units"].items()} if previous else {}
    unit_id = {}
    if previous:
        next_id = max(previous["units"]) + 1 if previous["units"] else 0
        for key in sorted(v["key"] for v in roster):
            if key in prev_unit_id:
                unit_id[key] = prev_unit_id[key]
            else:
                unit_id[key] = next_id
                next_id += 1
    else:
        unit_id = {key: i for i, key in enumerate(sorted(v["key"] for v in roster))}
    units = {}
    for v in roster:
        icon = presentation["icon_names"].get(v["name"])
        if not icon or not (REPO_ROOT / f"data/media/img/units/{icon}.png").is_file():
            raise BuildError(f"no unit icon for {v['name']!r} (aoe2x/assets/presentation.json icon_names)")
        units[v["key"]] = {"civilization": v["civilization"], "group": v["group"], "key": v["key"],
                           "line": v["line"], "name": v["name"], "profileHash": v["profileHash"],
                           "slug": v["slug"], "id": unit_id[v["key"]], "icon": f"/static/img/units/{icon}.png",
                           "costs": prices[v["key"]]}

    # ---- cells
    prev_orientation = {}
    if previous:
        pu = previous["units"]
        for c in previous["cells"]:
            prev_orientation[frozenset((pu[c[0]]["key"], pu[c[1]]["key"]))] = (pu[c[0]]["key"], pu[c[1]]["key"], c)
    cells, order = [], []           # order: pairKeys by first appearance
    seen_pairs, current_pks = set(), set()
    missing = Counter()
    missing_examples = []
    carried_to = defaultdict(set)   # evidence pairKey -> current pairKeys whose cells show it un-resimulated
    marked = Counter()
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            if a["civilization"] == b["civilization"]:
                continue
            ka, kb = a["key"], b["key"]
            prev = prev_orientation.get(frozenset((ka, kb)))
            if prev and prev[0] == kb:
                ka, kb = kb, ka
            ua, ub = units[ka], units[kb]
            pk = key2(ua["profileHash"], ub["profileHash"])
            ha, hb = pk.split("|")
            row = rows.get(pk)
            if ha == hb:
                if row is None:
                    rows[pk] = row = {"pairKey": pk, "outcome": "equivalent", "evidenceType": "identity",
                                      "source": "identity", "context": None, "seeds": []}
                if row["outcome"] != "equivalent" or row["evidenceType"] != "identity":
                    raise BuildError(f"identity pair {pk} is stored as {row['outcome']}/{row['evidenceType']}")
            if row is None:
                if not (pk in blocked or carry_unsimulated):
                    missing[pk] += 1
                    if len(missing_examples) < 5:
                        missing_examples.append(f"{ka} / {kb}")
                    continue
                # Keep the previous release's cell (same two units), flagged as not re-simulated.
                if not prev:
                    raise BuildError(f"cell {ka} / {kb}: no result for {pk} and no previous release cell to keep "
                                     "(carrying needs --previous-db)")
                pu = previous["units"]
                p = prev[2]
                same = pu[p[0]]["key"] == ka
                old_pk = previous["evidence"][p[8]]["pairKey"]
                carried_to[old_pk].add(pk)
                marked["blocked" if pk in blocked else "notYetSimulated"] += 1
                outcome = p[2] if same else INVERSE[p[2]]
                ca, cb = (p[4], p[5]) if same else (p[5], p[4])
                if old_pk not in seen_pairs:
                    seen_pairs.add(old_pk)
                    order.append(old_pk)
                cells.append([ua["id"], ub["id"], outcome, p[3], ca, cb, p[6], p[7] | FLAG_NOT_RESIMULATED, old_pk])
                continue
            flags = 0
            if pk in blocked:
                flags |= FLAG_NOT_RESIMULATED
                marked["blockedKeptBaseline"] += 1
            current_pks.add(pk)
            if pk not in seen_pairs:
                seen_pairs.add(pk)
                order.append(pk)
            ctx = context_of(ha, ha) if ha == hb else row["context"]
            counts = [ctx["counts"][ctx["profiles"].index(h)] for h in (ua["profileHash"], ub["profileHash"])]
            if row["outcome"] in ("a_win", "b_win"):
                winner = ha if row["outcome"] == "a_win" else hb
                outcome = "a_win" if ua["profileHash"] == winner else "b_win"
            else:
                outcome = row["outcome"]
            cells.append([ua["id"], ub["id"], outcome, row["evidenceType"], counts[0], counts[1], "", flags, pk])
    if missing:
        raise BuildError(f"{sum(missing.values())} displayed cell(s) in {len(missing)} pair(s) have no result "
                         f"(run not complete? use --carry-unsimulated with --previous-db to keep the previous "
                         f"release for them), e.g. {missing_examples[0]}")

    # ---- every stored context must belong to this setup
    wrong = []
    for pk in order:
        h1, h2 = pk.split("|")
        if h1 == h2 or pk not in current_pks:
            continue
        row = rows[pk]
        ctx = row["context"]
        if ctx is None or set(ctx["profiles"]) != {h1, h2} or ctx != context_of(*ctx["profiles"]):
            wrong.append(pk)
    if wrong:
        raise BuildError(f"{len(wrong)} stored result(s) were simulated under a different setup than this config "
                         f"(army cap, weights, scenarios or mechanics), e.g. {wrong[0]}")

    # ---- evidence ids
    prev_ev_id = {}
    if previous:
        for i, e in previous["evidence"].items():
            prev_ev_id.setdefault(e["pairKey"], i)
        next_ev = max(previous["evidence"]) + 1 if previous["evidence"] else 0
    else:
        next_ev = 0
    ev_id = {}
    for pk in order:
        if pk in prev_ev_id:
            ev_id[pk] = prev_ev_id[pk]
    for pk in order:
        if pk not in ev_id:
            ev_id[pk] = next_ev
            next_ev += 1
    for c in cells:
        c[8] = ev_id[c[8]]

    # ---- evidence objects
    scenario_hashes = [e["hash"] for e in scenario_set["scenarios"]]
    dictionary = make_dictionary(sorted(mechanics), scenario_hashes, context_of.policy)
    evidence = {}
    for pk in order:
        h1, h2 = pk.split("|")
        if pk in current_pks:
            row = rows[pk]
            e = compact_evidence(row, context_of(h1, h1) if h1 == h2 else row["context"])
        else:
            # Shown only by carried cells: the previous release's evidence object, as it was.
            e = dict(previous["evidence"][prev_ev_id[pk]])
        if pk in blocked:
            e["rerun"] = blocked[pk]
        if pk in carried_to:
            e["carriedTo"] = sorted(carried_to[pk])
        evidence[ev_id[pk]] = e

    # ---- dataset (served in the catalog): the base text, updated only where the content differs
    if dataset_base is None:
        dataset_base = (previous or {}).get("metadata", {}).get("dataset") or DATASET_2026.read_text()
    dataset = json.loads(dataset_base)
    ev_types = Counter(e["evidenceType"] for e in evidence.values())
    cell_types = Counter(c[3] for c in cells)
    civs = {v["civilization"] for v in roster}
    recomputed = {"displayedCells": len(cells), "displayedEvidenceCounts": dict(sorted(cell_types.items())),
                  "evidenceCounts": dict(sorted(ev_types.items())), "profilePairs": len(evidence),
                  "variants": len(roster), "civPairs": len(civs) * (len(civs) - 1) // 2}
    updated = dict(dataset)
    updated.update(recomputed)
    if snapshots:
        runs = list(updated.get("matchupRuns", []))
        known = {r["snapshotHash"] for r in runs}
        for snap in snapshots:
            m = snap["manifest"]
            if m["snapshotHash"] not in known:
                runs.append({"runId": m["runId"], "runHash": m["runHash"], "snapshotHash": m["snapshotHash"],
                             "bundleHash": m["bundleHash"], "setupHash": m["setupHash"],
                             "engineId": m["engine"]["engineId"], "counts": {k: m["counts"][k] for k in
                                                                             ("reviewed", "reused", "blocked", "seeds")}})
        updated["matchupRuns"] = runs
    flagged = sum(1 for c in cells if c[7] & FLAG_NOT_RESIMULATED)
    if flagged or "notResimulatedCells" in updated:
        updated["notResimulatedCells"] = flagged
    dataset_text = dataset_base if updated == dataset else encode(updated, ascii_only=True)

    # ---- write
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pending = out.with_name(out.name + ".building")
    pending.unlink(missing_ok=True)
    db = sqlite3.connect(pending)
    try:
        db.execute(f"PRAGMA page_size={PAGE_SIZE}")
        db.executescript(SCHEMA_SQL)
        for key in sorted(units, key=lambda k: units[k]["id"]):
            u = units[key]
            db.execute("INSERT INTO units VALUES (?,?,?,?)", (u["id"], key, u["civilization"], encode(u)))
        db.execute("INSERT INTO metadata VALUES (?,?)", ("compression_dictionary", dictionary))
        for i in sorted(evidence):
            db.execute("INSERT INTO evidence VALUES (?,?)", (i, zpack(evidence[i], dictionary)))
        db.executemany("INSERT INTO cells VALUES (?,?,?,?,?,?,?,?,?)", cells)
        db.execute("INSERT INTO metadata VALUES (?,?)", ("dataset", dataset_text))
        record = {
            "schema": BUILD_SCHEMA, "evidenceFormat": EVIDENCE_FORMAT, "compactSeedFields": COMPACT_SEED_FIELDS,
            "flags": {"4": "not re-simulated: shows the kept/previous result (rerun blocked or not yet run)"},
            "bundle": {"bundleHash": bundle["bundleHash"], "bundleId": bundle.get("bundleId"),
                       "variants": len(roster), "civilizations": len(civs)},
            "setupHash": setup_hash, "engineFilesDigest": engine_files_digest,
            "scenarioSetHash": scenario_set["setHash"],
            "resultIndex": {"sha256": index_sha256, "rows": len(index)},
            "snapshots": [{"runId": s["manifest"]["runId"], "snapshotHash": s["manifest"]["snapshotHash"],
                           "manifestSha256": s["manifestSha256"]} for s in snapshots],
            "previousDb": {"sha256": previous["sha256"]} if previous else None,
            "costs": {"source": costs, "referenceDbSha256": sha256_bytes(Path(costs_db).read_bytes())
                      if costs == "reference-db" else None},
            "carryUnsimulated": carry_unsimulated,
            "counts": {"units": len(units), "cells": len(cells), "evidence": len(evidence),
                       "cellEvidenceTypes": dict(sorted(cell_types.items())),
                       "evidenceTypes": dict(sorted(ev_types.items())),
                       "notResimulatedCells": flagged, "marked": dict(sorted(marked.items())),
                       "merge": merge_counts},
            "fullEvidence": ("per-seed state/event hashes: result index + run snapshots above; 2026 provenance "
                             "chains: git history of data/golden/civ_matchups_first_pass.db (sha256 bdbbeacf...)"),
        }
        db.execute("INSERT INTO metadata VALUES (?,?)", ("matchup_build", encode(record)))
        db.commit()
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BuildError("integrity_check failed")
        db.execute("VACUUM")
    finally:
        db.close()
    size = pending.stat().st_size
    if size >= max_bytes:
        pending.unlink()
        raise BuildError(f"serving DB would be {size:,} bytes (limit {max_bytes:,})")
    pending.replace(out)
    return {**record, "out": str(out), "bytes": size, "sha256": sha256_bytes(out.read_bytes())}
