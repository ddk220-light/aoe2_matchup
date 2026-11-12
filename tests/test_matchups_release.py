"""Matchup release tooling (build steps 4-5): build-db merge rules, audit, bundle diff/plan, archive.

Runs in seconds without the research branch: a three-civilization world cut
from the committed 2026 bundle, with fabricated (clearly synthetic) result
rows whose contexts come from the real battle rules.
"""
import copy
import gzip
import json
import sqlite3
import tarfile

import pytest

from aoe2x.matchups import archive as AR
from aoe2x.matchups import artifacts
from aoe2x.matchups import audit as AU
from aoe2x.matchups import bundle as B
from aoe2x.matchups import plan as P
from aoe2x.matchups import servingdb as S
from aoe2x.matchups.battle import ContextBuilder
from aoe2x.matchups.canonical import digest, key2, profile_hash, sha256_bytes
from aoe2x.matchups.config import DEFAULTS

CIVS = ("Britons", "Franks", "Mongols")
BATTLE = copy.deepcopy(DEFAULTS["battle"])
SETUP = "setup-hash-for-tests"
ENGINE = "engine-digest-for-tests"
DATASET = json.dumps({"source_commit": "test", "displayedCells": 0}, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="module")
def world():
    full = B.load_bundle(artifacts.CAMPAIGN_2026_BUNDLE)
    scen = B.load_scenario_set(artifacts.FROZEN_SCENARIOS)
    b = copy.deepcopy(full)
    b["variants"] = [v for v in b["variants"] if v["civilization"] in CIVS]
    b["roster"]["units"] = [k for k in b["roster"]["units"] if k.split("|")[0] in CIVS]
    return B.seal(b), scen


def _context_builder(bundle, scen):
    mech = {}
    for v in bundle["variants"]:
        mech.setdefault(v["profileHash"], v["mechanics"])
    return ContextBuilder(mech, B.Scenarios(scen), BATTLE)


def _pairs(bundle):
    by = {v["key"]: v for v in bundle["variants"]}
    roster = [by[k] for k in bundle["roster"]["units"]]
    out = set()
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            if a["civilization"] != b["civilization"]:
                out.add(key2(a["profileHash"], b["profileHash"]))
    return sorted(out)


def _seed(seed, winner):
    loser_hp = 0
    return [seed, winner, 1000 + seed, 500.0 if winner == 2 else loser_hp, 400.0 if winner == 3 else loser_hp,
            5 if winner == 2 else 0, 4 if winner == 3 else 0, 1000.0, 900.0, "f" * 64, "e" * 64,
            "frozen-civ-matchups-v3"]


def _row(pk, ctx_of, winner=2, source="test-baseline", reusable=True):
    a, b = pk.split("|")
    if a == b:
        return {"pairKey": pk, "outcome": "equivalent", "evidenceType": "identity", "source": "identity",
                "context": None, "seeds": []}
    ctx = ctx_of(a, b)
    outcome = "a_win" if (ctx["profiles"][winner - 2] == a) else "b_win"
    row = {"pairKey": pk, "outcome": outcome, "evidenceType": "observed", "source": source, "context": ctx,
           "contextHash": digest(ctx), "jobId": "test_" + digest(pk)[:8],
           "seeds": [_seed(s, winner) for s in range(3)], "reusable": reusable}
    if reusable:
        row["resultKey"] = digest({"contextHash": row["contextHash"], "setupHash": SETUP})
    return row


def _index(bundle, scen):
    ctx_of = _context_builder(bundle, scen)
    rows = []
    for i, pk in enumerate(_pairs(bundle)):
        r = _row(pk, ctx_of, winner=2 + i % 2)
        if i % 7 == 3 and r["evidenceType"] == "observed":      # some rule-inferred rows (kept, not reusable)
            r.update(evidenceType="inferred", source="first-pass-inference", seeds=[], reusable=False,
                     ruleId="R1_STATIC_DIRECTION", ruleVersion="test")
            r.pop("resultKey")
        rows.append(r)
    return rows


def _gz(rows):
    return gzip.compress("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows).encode(),
                         mtime=0)


def _snapshot(tmp, name, bundle, results, reused=(), blocked=(), index_sha=None):
    d = tmp / name
    d.mkdir()
    files = {"results.jsonl.gz": _gz(results), "reused.jsonl.gz": _gz(list(reused)),
             "blocked.jsonl.gz": _gz(list(blocked))}
    for n, data in files.items():
        (d / n).write_bytes(data)
    m = {"schema": "aoe2-matchup-run-snapshot/v1", "runId": name, "runHash": "run-" + name,
         "bundleHash": bundle["bundleHash"], "setupHash": SETUP, "resultIndexSha256": index_sha,
         "engine": {"engineId": "frozen-civ-matchups-v3", "filesDigest": ENGINE},
         "counts": {"reviewed": len(results), "reused": len(reused), "blocked": len(blocked), "seeds": 3 * len(results)},
         "files": {n: {"sha256": sha256_bytes(data), "bytes": len(data)} for n, data in files.items()}}
    m["snapshotHash"] = digest(m)
    (d / "manifest.json").write_text(json.dumps(m))
    return S.load_snapshot(d)


def _build(tmp, bundle, scen, index, snapshots=(), previous=None, name="out.db", **kw):
    return S.build(bundle=bundle, scenario_set=scen, battle=BATTLE, setup_hash=SETUP, engine_files_digest=ENGINE,
                   index=index, index_sha256="i" * 64, snapshots=list(snapshots), out=tmp / name, previous=previous,
                   dataset_base=kw.pop("dataset_base", DATASET), costs="bundle", **kw)


def _verify(path, bundle, scen, index, snapshots=(), previous=None):
    return AU.verify(path, bundle=bundle, scenario_set=scen, battle=BATTLE, setup_hash=SETUP,
                     engine_files_digest=ENGINE, index=index, index_sha256="i" * 64, snapshots=list(snapshots),
                     previous=previous)


def _patched(bundle, key, bump=1):
    b = copy.deepcopy(bundle)
    for v in b["variants"]:
        if v["key"] == key:
            v["mechanics"]["attack_classes"]["4"] += bump
            v["mechanicsHash"], v["profileHash"] = digest(v["mechanics"]), profile_hash(v["mechanics"])
    return B.seal(b)


# ------------------------------------------------------------------ build-db

def test_build_from_index_schema_orientation_and_audit(tmp_path, world):
    bundle, scen = world
    index = _index(bundle, scen)
    record = _build(tmp_path, bundle, scen, index)
    db = S.read_db(tmp_path / "out.db")
    con = sqlite3.connect(tmp_path / "out.db")
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"metadata", "units", "evidence", "cells"}
    assert con.execute("PRAGMA page_size").fetchone()[0] == 32768
    assert len(db["cells"]) == 299 and len(db["units"]) == 30 and record["counts"]["evidence"] == 263
    units = db["units"]
    rows = {r["pairKey"]: r for r in index}
    for a, b, outcome, etype, ca, cb, tier, flags, eid in db["cells"]:
        e = db["evidence"][eid]
        pk = key2(units[a]["profileHash"], units[b]["profileHash"])
        assert e["pairKey"] == pk and etype == e["evidenceType"] == rows[pk]["evidenceType"]
        if outcome in ("a_win", "b_win"):  # orientation: the winning profile is the cell's a (or b)
            winner = pk.split("|")[0 if rows[pk]["outcome"] == "a_win" else 1]
            assert (outcome == "a_win") == (units[a]["profileHash"] == winner)
        ctx = e["context"]
        assert [ca, cb] == [ctx["counts"][ctx["profiles"].index(units[x]["profileHash"])] for x in (a, b)]
        assert (tier, flags) == ("", 0)
    # compact evidence: summaries kept, per-seed hashes dropped
    e = next(e for e in db["evidence"].values() if e["evidenceType"] == "observed")
    assert all(len(s) == len(S.COMPACT_SEED_FIELDS) for s in e["seeds"]) and e["physics"] == ["frozen-civ-matchups-v3"]
    assert "f" * 64 not in json.dumps(e)
    # units sorted by key; evidence ids by first appearance in the roster walk
    assert [units[i]["key"] for i in sorted(units)] == sorted(u["key"] for u in units.values())
    first = []
    for c in db["cells"]:
        if c[8] not in first:
            first.append(c[8])
    assert first == sorted(first)
    v = _verify(tmp_path / "out.db", bundle, scen, index)
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]
    # deterministic bytes
    _build(tmp_path, bundle, scen, index, name="again.db")
    assert (tmp_path / "out.db").read_bytes() == (tmp_path / "again.db").read_bytes()
    # the dataset text is kept verbatim when nothing it records changed... and updated when it did
    assert json.loads(db["metadata"]["dataset"])["displayedCells"] == 299


def test_audit_detects_tampering(tmp_path, world):
    bundle, scen = world
    index = _index(bundle, scen)
    _build(tmp_path, bundle, scen, index)
    con = sqlite3.connect(tmp_path / "out.db")
    a, b, outcome = con.execute("SELECT a, b, outcome FROM cells WHERE outcome IN ('a_win','b_win') LIMIT 1").fetchone()
    con.execute("UPDATE cells SET outcome=? WHERE a=? AND b=?", ("b_win" if outcome == "a_win" else "a_win", a, b))
    con.execute("DELETE FROM cells WHERE rowid = (SELECT MAX(rowid) FROM cells)")
    con.commit()
    con.close()
    v = _verify(tmp_path / "out.db", bundle, scen, index)
    failed = {c["check"] for c in v["checks"] if not c["ok"]}
    assert "cell outcome orientation: none" in failed
    assert "cells = displayed cells of the roster, each once" in failed


def test_snapshot_rows_replace_index_rows_and_ids_stay_stable(tmp_path, world):
    bundle, scen = world
    index = _index(bundle, scen)
    _build(tmp_path, bundle, scen, index, name="prev.db")
    prev = S.read_db(tmp_path / "prev.db")
    # patch one unit: its pairs get new pairKeys; a run simulates them (snapshot), reuses one baseline row
    key = "Franks|paladin"
    new = _patched(bundle, key)
    plan = P.build_plan(bundle, new, scen, BATTLE, index)
    sched = plan["schedule"]
    new_profile = next(v["profileHash"] for v in new["variants"] if v["key"] == key)
    assert sched and all(new_profile in pk.split("|") for pk in sched)
    assert plan["partnerCheck"]["scheduledNotTouchingThem"] == 0
    ctx_of = _context_builder(new, scen)
    results = [{**_row(pk, ctx_of, winner=3, source=f"run:patch"), "orientation": "same"} for pk in sched]
    reused_row = next(r for r in index if r.get("reusable"))
    reused = [["job-x", reused_row["pairKey"], reused_row["resultKey"], reused_row["outcome"]]]
    snap = _snapshot(tmp_path, "patch", new, results, reused=reused, index_sha="i" * 64)
    _build(tmp_path, new, scen, index, [snap], previous=prev, name="new.db")
    db = S.read_db(tmp_path / "new.db")
    v = _verify(tmp_path / "new.db", new, scen, index, [snap], prev)
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]
    # unit ids and the evidence ids of untouched pairs are the previous release's
    assert {u["key"]: i for i, u in db["units"].items()} == {u["key"]: i for i, u in prev["units"].items()}
    prev_ids = {e["pairKey"]: i for i, e in prev["evidence"].items()}
    for i, e in db["evidence"].items():
        if e["pairKey"] in prev_ids:
            assert prev_ids[e["pairKey"]] == i
        else:
            assert i > max(prev["evidence"]) and e["source"] == "run:patch" and e["replaces"] is None
    # comparison: exactly the scheduled contexts are re-simulated; only the patched unit's cells change
    c = AU.compare(prev, db)
    assert sorted(r["pairKey"] for r in c["resimulated"]) == sorted(sched)
    changed = {k for k, n in c["cells"].items() if k != "unchanged"}
    assert c["units"]["profileChanged"] == [key]
    assert sum(c["cells"][k] for k in changed) == sum(r["cells"] for r in c["resimulated"])
    assert set(c["byCivilization"]) <= set(CIVS)
    dataset = json.loads(db["metadata"]["dataset"])
    assert dataset["matchupRuns"][0]["runId"] == "patch"
    md = AU.summary_markdown(v, c, None)
    assert "Re-simulated in this release" in md and "PASSED" in md


def test_blocked_and_missing_contexts(tmp_path, world):
    bundle, scen = world
    index = _index(bundle, scen)
    _build(tmp_path, bundle, scen, index, name="prev.db")
    prev = S.read_db(tmp_path / "prev.db")
    new = _patched(bundle, "Franks|paladin")
    sched = P.build_plan(bundle, new, scen, BATTLE, index)["schedule"]
    ctx_of = _context_builder(new, scen)
    done, stuck = sched[:-1], sched[-1]
    results = [_row(pk, ctx_of, source="run:p") for pk in done]
    blocked = [{"jobId": "cm_stuck", "pairKey": stuck, "contextHash": "c" * 64, "resultKey": "r" * 64, "seed": 0,
                "failedAttempts": 4, "lastError": "Timeout", "watchdog": True, "lastLimitSeconds": 3600,
                "seedsCompleted": []}]
    # an incomplete run without the blocked list is refused
    partial = _snapshot(tmp_path, "partial", new, results, index_sha="i" * 64)
    with pytest.raises(S.BuildError, match="have no result"):
        _build(tmp_path, new, scen, index, [partial], previous=prev, name="x.db")
    # ... unless carried explicitly; the blocked context keeps the previous release's cells, flagged
    snap = _snapshot(tmp_path, "p", new, results, blocked=blocked, index_sha="i" * 64)
    with pytest.raises(S.BuildError, match="previous"):
        _build(tmp_path, new, scen, index, [snap], name="x.db")
    record = _build(tmp_path, new, scen, index, [snap], previous=prev, name="new.db")
    db = S.read_db(tmp_path / "new.db")
    flagged = [c for c in db["cells"] if c[7] & S.FLAG_NOT_RESIMULATED]
    assert flagged and record["counts"]["marked"] == {"blocked": len(flagged)}
    prev_cells = {frozenset((prev["units"][c[0]]["key"], prev["units"][c[1]]["key"])): c for c in prev["cells"]}
    for c in flagged:
        p = prev_cells[frozenset((db["units"][c[0]]["key"], db["units"][c[1]]["key"]))]
        assert c[2:6] == p[2:6] and c[8] == p[8]
        assert stuck in db["evidence"][c[8]]["carriedTo"]
    assert json.loads(db["metadata"]["dataset"])["notResimulatedCells"] == len(flagged)
    v = _verify(tmp_path / "new.db", new, scen, index, [snap], prev)
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]
    assert AU.compare(prev, db)["carried"][0]["reason"] == "kept"
    # a blocked pair that still has a baseline row keeps it and is flagged
    keep_pk = next(r["pairKey"] for r in index if r["evidenceType"] == "observed")
    snap2 = _snapshot(tmp_path, "p2", bundle, [], blocked=[{**blocked[0], "pairKey": keep_pk}], index_sha="i" * 64)
    _build(tmp_path, bundle, scen, index, [snap2], previous=prev, name="kept.db")
    db2 = S.read_db(tmp_path / "kept.db")
    marked = [c for c in db2["cells"] if c[7]]
    assert marked and all(db2["evidence"][c[8]]["pairKey"] == keep_pk and db2["evidence"][c[8]]["rerun"]["status"]
                          == "blocked" for c in marked)


def test_results_from_another_setup_and_snapshot_mismatches_are_refused(tmp_path, world):
    bundle, scen = world
    index = _index(bundle, scen)
    other = copy.deepcopy(BATTLE)
    other["armyCap"] = 20
    with pytest.raises(S.BuildError, match="different setup"):
        S.build(bundle=bundle, scenario_set=scen, battle=other, setup_hash=SETUP, engine_files_digest=ENGINE,
                index=index, index_sha256="i" * 64, snapshots=[], out=tmp_path / "x.db", dataset_base=DATASET,
                costs="bundle")
    snap = _snapshot(tmp_path, "s", bundle, [], index_sha="j" * 64)
    with pytest.raises(S.BuildError, match="result index"):
        _build(tmp_path, bundle, scen, index, [snap])
    snap_dir = tmp_path / "s"
    (snap_dir / "results.jsonl.gz").write_bytes(_gz([{"x": 1}]))
    with pytest.raises(S.BuildError, match="does not match"):
        S.load_snapshot(snap_dir)
    with pytest.raises(S.BuildError, match="limit"):
        _build(tmp_path, bundle, scen, index, max_bytes=10_000)


def test_removed_units_disappear_and_ids_stay(tmp_path, world):
    bundle, scen = world
    index = _index(bundle, scen)
    _build(tmp_path, bundle, scen, index, name="prev.db")
    prev = S.read_db(tmp_path / "prev.db")
    smaller = copy.deepcopy(bundle)
    gone = "Mongols|steppe_lancer" if "Mongols|steppe_lancer" in smaller["roster"]["units"] else smaller["roster"]["units"][-1]
    smaller["roster"]["units"] = [k for k in smaller["roster"]["units"] if k != gone]
    smaller = B.seal(smaller)
    _build(tmp_path, smaller, scen, index, previous=prev, name="small.db")
    db = S.read_db(tmp_path / "small.db")
    assert gone not in {u["key"] for u in db["units"].values()}
    c = AU.compare(prev, db)
    assert c["units"]["removed"] == [gone] and c["cells"]["removed"] > 0 and "added" not in c["cells"]
    assert _verify(tmp_path / "small.db", smaller, scen, index, previous=prev)["ok"]


def test_api_reads_a_built_db_through_the_unchanged_service(tmp_path, world):
    from aoe2x.matchups import apicheck
    import aoe2_api.services.advisor as advisor
    bundle, scen = world
    _build(tmp_path, bundle, scen, _index(bundle, scen))
    live = advisor.DATASET
    r = apicheck.responses(tmp_path / "out.db", evidence_ids=(0, 10 ** 6))
    assert advisor.DATASET == live  # the live default is restored
    catalog = json.loads(r["files"]["catalog"])
    assert catalog["civilizations"] == list(CIVS) and len(catalog["units"]) == 30
    franks = json.loads(r["files"]["franks"])
    assert sum(len(v) for v in franks["opponents"].values()) == 10 * 20
    assert r["evidence"][0][0] == 200 and "pairKey" in r["evidence"][0][1] and r["evidence"][10 ** 6][0] == 404
    same = apicheck.compare(tmp_path / "out.db", tmp_path / "out.db")
    assert same["identical"] == same["files"] == 4 and same["componentVersionOld"] == same["componentVersionNew"]


# ------------------------------------------------------------- diff / plan

def test_plan_classes_estimate_and_priors(tmp_path, world):
    bundle, scen = world
    index = _index(bundle, scen)
    same = P.build_plan(bundle, bundle, scen, BATTLE, index)
    assert same["pairs"].get("simulate", 0) == 0 and same["diff"]["identical"]
    assert same["pairs"]["keep"] == sum(1 for r in index if r["evidenceType"] == "inferred")
    assert P.build_plan(bundle, bundle, scen, BATTLE, index, resimulate_kept=True)["pairs"]["simulate"] == same["pairs"]["keep"]
    new = _patched(bundle, "Britons|champion")
    plan = P.build_plan(bundle, new, scen, BATTLE, index)
    d = plan["diff"]
    assert [c["key"] for c in d["variantsChanged"]] == ["Britons|champion"] and d["variantsChanged"][0]["fields"] == ["attack_classes"]
    e = plan["estimate"]
    assert e["expectedSeeds"] == round(len(plan["schedule"]) * 3.3)
    assert e["workerHours"] == round(len(plan["schedule"]) * 3.3 / (1490 / 4), 1)
    written = P.write_outputs(plan, tmp_path / "plan", old=bundle, new=new, index=index, with_priors=True,
                              base_config={"schema": "aoe2-matchup-run/v1", "runId": "x", "battle": {}},
                              new_bundle_path="new.json.gz", run_id="patch-test")
    cfg = json.loads((tmp_path / "plan/config.json").read_text())
    assert json.loads((tmp_path / "plan/contexts.json").read_text()) == plan["schedule"]
    assert cfg["selection"]["contexts"]["sha256"] == written["contexts.json"]
    assert cfg["sampling"]["forecastSource"] == "priors-file"
    priors = [json.loads(l) for l in gzip.decompress((tmp_path / "plan/priors.jsonl.gz").read_bytes()).splitlines()]
    rows = {r["pairKey"]: r for r in index}
    old_p = {v["key"]: v["profileHash"] for v in bundle["variants"]}
    new_p = {v["key"]: v["profileHash"] for v in new["variants"]}
    for pr in priors:  # the previous winner of the same cells, re-expressed in the new pairKey order
        cells = plan["_pairs"][pr["pairKey"]]["cellKeys"]
        for ka, kb in cells:
            old = rows[key2(old_p[ka], old_p[kb])]
            if old["outcome"] in ("a_win", "b_win"):
                w_old = old["pairKey"].split("|")[0 if old["outcome"] == "a_win" else 1]
                winner = ka if old_p[ka] == w_old else kb
                assert ("a_win" if new_p[winner] == pr["pairKey"].split("|")[0] else "b_win") in pr["outcomes"]
    assert "new battles" in (tmp_path / "plan/plan.md").read_text()


def test_cloned_civilization_reuses_shared_profiles(world):
    bundle, scen = world
    index = _index(bundle, scen)
    dlc = copy.deepcopy(bundle)
    clones = []
    for v in dlc["variants"]:
        if v["civilization"] == "Franks":
            c = copy.deepcopy(v)
            c["civilization"], c["key"] = "Atlanteans", "Atlanteans|" + v["slug"]
            c["mechanics"]["civilization"] = "Atlanteans"
            c["mechanicsHash"] = digest(c["mechanics"])
            clones.append(c)
    dlc["variants"] += clones
    dlc["roster"]["units"] = sorted(dlc["roster"]["units"] + [c["key"] for c in clones])
    dlc = B.seal(dlc)
    plan = P.build_plan(bundle, dlc, scen, BATTLE, index)
    franks = {v["profileHash"] for v in bundle["variants"] if v["civilization"] == "Franks"}
    assert plan["diff"]["civilizationsAdded"] == ["Atlanteans"] and not plan["diff"]["profilesAdded"]
    # only Franks-internal profile pairs never fought across civilizations are new
    assert plan["schedule"] and all(set(pk.split("|")) <= franks for pk in plan["schedule"])
    assert all(pk not in {r["pairKey"] for r in index} for pk in plan["schedule"])


# ------------------------------------------------------------------ archive

def test_archive_is_deterministic_and_keeps_the_essential_records(tmp_path):
    r = tmp_path / "records"
    for rel, text in {"runs.jsonl": '{"seed":0}\n', "attempts.jsonl": json.dumps(
            {"exhausted": True, "progressPath": str(r / "progress/a-0.jsonl")}) + "\n",
            "pair-reviews/cm_1.json": "{}", "reviews/001.json": "{}", "state.json": '{"runId":"t"}',
            "inventory/inventory-summary.json": "{}", "inventory/jobs.jsonl.gz": "x", "progress/a-0.jsonl": "p",
            "progress/b-0.jsonl": "p", "logs/runner.log": "l", ".runner.lock": "1",
            "export/manifest.json": "{}"}.items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_text(text)
    one = AR.archive_run(r, tmp_path / "a.tar.gz")
    two = AR.archive_run(r, tmp_path / "b.tar.gz")
    assert (tmp_path / "a.tar.gz").read_bytes() == (tmp_path / "b.tar.gz").read_bytes()
    assert one["archive"]["sha256"] == two["archive"]["sha256"]
    with tarfile.open(tmp_path / "a.tar.gz") as tar:
        names = tar.getnames()
        assert names[0] == "MANIFEST.json" and names[1:] == sorted(names[1:])
        assert all(m.mtime == 0 and m.uid == 0 and not m.uname for m in tar.getmembers())
        manifest = json.loads(tar.extractfile("MANIFEST.json").read())
    assert {"runs.jsonl", "attempts.jsonl", "pair-reviews/cm_1.json", "progress/a-0.jsonl",
            "export/manifest.json"} <= set(names)
    assert not {"progress/b-0.jsonl", "logs/runner.log", ".runner.lock", "inventory/jobs.jsonl.gz"} & set(names)
    assert {f["path"] for f in manifest["files"]} == set(names[1:])


@pytest.mark.parametrize("path,kind,cls,archived", [
    (AR.CAMPAIGNS["forecast"] + "runs.jsonl", "seed journals", AR.ESSENTIAL, True),
    (AR.CAMPAIGNS["forecast"] + "progress/fv_x-0-a-1.jsonl", "progress diagnostics", AR.DISPOSABLE, False),
    (AR.CAMPAIGNS["forecast"] + "correction-snapshots/070/manifest.json", "final correction snapshot", AR.ESSENTIAL, True),
    (AR.CAMPAIGNS["forecast"] + "correction-snapshots/002/manifest.json", "intermediate correction snapshots",
     AR.DERIVABLE, False),
    (AR.CAMPAIGNS["recovery"] + "correction-snapshots/002/runs.jsonl.gz", "final correction snapshot", AR.ESSENTIAL, True),
    (AR.CAMPAIGNS["adaptive"] + "predictions/031/profile-table.jsonl.gz", "selector predictions/estimates/refinement",
     AR.DISPOSABLE, False),
    (AR.CAMPAIGNS["mismatch"] + "pair-reviews/mv_1.json", "pair reviews", AR.ESSENTIAL, True),
    (AR.CAMPAIGNS["forecast"] + "monitor-reports/milestone-001000.json", "monitor reports", AR.DISPOSABLE, False),
])
def test_rb_triage_rules(path, kind, cls, archived):
    assert AR.classify_rb(path)[2:] == (kind, cls, archived)
    assert AR.classify_rb("apps/website/app.py") is None
