"""``audit-db``: verify a built serving DB against its inputs; compare two DBs; release summary.

Verification (no battles) re-derives everything a cell shows from the inputs
named in the DB's ``matchup_build`` record and checks:

* inputs: bundle, setup, engine digest, result-index sha256, every snapshot's
  manifest (files, ``snapshotHash``) and the previous DB equal the record;
* units: exactly the bundle roster, same profile hashes;
* cells: exactly the displayed cells of the roster (variants of different
  civilizations), each once;
* cell -> evidence -> source row: the evidence ``pairKey`` is the cell's pair
  (or, for a flag-4 carried cell, the previous release's pair with the cell's
  pair in ``carriedTo``); outcome orientation, counts and evidence type follow
  from the evidence; the evidence equals the merged index/snapshot row
  (outcome, type, context, compact seeds, source); the stored context is the
  one this setup gives for the two profiles; observed seed sets classify to
  the stored outcome (unanimous winner, else ``close_uncertain``);
* no unreferenced evidence; counts by evidence type equal the ``dataset``
  metadata; blocked contexts are flagged; size under the limit.

Comparison (two DBs, matched by unit key, not id) lists units and cells
added/removed/changed by civilization and by evidence-type transition, the
contexts re-simulated in this release (evidence from a run that the old DB
did not have), carried (not re-simulated) cells, and - with ``--api`` - which
API responses changed and the advisor component versions.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from aoe2x.matchups import servingdb as S
from aoe2x.matchups.battle import ContextBuilder
from aoe2x.matchups.bundle import Scenarios
from aoe2x.matchups.canonical import key2
from aoe2x.matchups.sampling import physical_outcome


def _check(checks: list, name: str, ok: bool, detail=None) -> None:
    checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail is not None else {})})


def _orient(outcome: str, pair_key: str, profile_a: str) -> str:
    if outcome not in ("a_win", "b_win"):
        return outcome
    first, second = pair_key.split("|")
    winner = first if outcome == "a_win" else second
    return "a_win" if profile_a == winner else "b_win"


def verify(db_path: Path, *, bundle: dict, scenario_set: dict, battle: dict, setup_hash: str,
           engine_files_digest: str, index: list, index_sha256: str, snapshots: list,
           previous: dict | None = None, max_bytes: int = S.MAX_BYTES) -> dict:
    db = S.read_db(db_path)
    checks: list = []
    record = json.loads(db["metadata"].get("matchup_build", "null") or "null")
    _check(checks, "build record present", record is not None and record.get("schema") == S.BUILD_SCHEMA)
    record = record or {}
    _check(checks, "inputs: bundle", record.get("bundle", {}).get("bundleHash") == bundle["bundleHash"],
           record.get("bundle", {}).get("bundleHash"))
    _check(checks, "inputs: setup hash", record.get("setupHash") == setup_hash)
    _check(checks, "inputs: engine files digest", record.get("engineFilesDigest") == engine_files_digest)
    _check(checks, "inputs: scenario set", record.get("scenarioSetHash") == scenario_set["setHash"])
    _check(checks, "inputs: result index sha256", record.get("resultIndex", {}).get("sha256") == index_sha256,
           index_sha256)
    want_snaps = [{"runId": s["manifest"]["runId"], "snapshotHash": s["manifest"]["snapshotHash"],
                   "manifestSha256": s["manifestSha256"]} for s in snapshots]
    _check(checks, "inputs: run snapshots (verified manifests)", record.get("snapshots") == want_snaps,
           [s["runId"] for s in want_snaps])
    _check(checks, "inputs: previous DB", (record.get("previousDb") or {}).get("sha256") ==
           (previous or {}).get("sha256"))
    setup = {"bundleHash": bundle["bundleHash"], "setupHash": setup_hash, "engineFilesDigest": engine_files_digest,
             "indexSha256": index_sha256}
    rows, blocked, _ = S.merge(index, snapshots, setup)

    # units
    by_key = {v["key"]: v for v in bundle["variants"]}
    roster = [by_key[k] for k in bundle["roster"]["units"]]
    units = {u["key"]: u for u in db["units"].values()}
    _check(checks, "units = bundle roster", set(units) == {v["key"] for v in roster},
           {"onlyDb": len(set(units) - {v["key"] for v in roster}),
            "onlyRoster": len({v["key"] for v in roster} - set(units))})
    _check(checks, "unit profile hashes", all(units[v["key"]]["profileHash"] == v["profileHash"]
                                              for v in roster if v["key"] in units))
    _check(checks, "unit ids unique", len({u["id"] for u in units.values()}) == len(units))

    # cells
    id_key = {i: u["key"] for i, u in db["units"].items()}
    expected = set()
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            if a["civilization"] != b["civilization"]:
                expected.add(frozenset((a["key"], b["key"])))
    present = Counter(frozenset((id_key[c[0]], id_key[c[1]])) for c in db["cells"])
    _check(checks, "cells = displayed cells of the roster, each once",
           set(present) == expected and max(present.values(), default=1) == 1,
           {"cells": len(db["cells"]), "expected": len(expected), "missing": len(expected - set(present)),
            "extra": len(set(present) - expected)})

    mechanics = {}
    for v in bundle["variants"]:
        mechanics.setdefault(v["profileHash"], v["mechanics"])
    context_of = ContextBuilder(mechanics, Scenarios(scenario_set), battle)
    problems = Counter()
    examples = {}

    def bad(kind, detail):
        problems[kind] += 1
        examples.setdefault(kind, detail)

    used = Counter()
    flagged = carried = 0
    current_pks, carried_pks = set(), set()
    for c in db["cells"]:
        a, b, outcome, etype, ca, cb, tier, flags, eid = c
        used[eid] += 1
        e = db["evidence"].get(eid)
        if e is None:
            bad("cell without evidence", c[:2])
            continue
        ua, ub = db["units"][a], db["units"][b]
        pk = key2(ua["profileHash"], ub["profileHash"])
        if flags & S.FLAG_NOT_RESIMULATED:
            flagged += 1
        if e["pairKey"] != pk:
            if not flags & S.FLAG_NOT_RESIMULATED or pk not in e.get("carriedTo", []):
                bad("evidence pairKey is not the cell's pair", [ua["key"], ub["key"]])
            elif not (pk in blocked or record.get("carryUnsimulated")):
                bad("carried cell without a blocked context or --carry-unsimulated", [ua["key"], ub["key"]])
            else:
                carried += 1
                carried_pks.add(e["pairKey"])
            continue
        current_pks.add(pk)
        if pk in blocked and not flags & S.FLAG_NOT_RESIMULATED:
            bad("blocked context not flagged", pk)
        if etype != e["evidenceType"]:
            bad("cell evidence type differs from evidence", [ua["key"], ub["key"]])
        if outcome != _orient(e["outcome"], pk, ua["profileHash"]):
            bad("cell outcome orientation", [ua["key"], ub["key"]])
        ctx = e["context"]
        try:
            counts = [ctx["counts"][ctx["profiles"].index(h)] for h in (ua["profileHash"], ub["profileHash"])]
        except (TypeError, ValueError, KeyError):
            counts = None
        if counts != [ca, cb]:
            bad("cell counts differ from the context", [ua["key"], ub["key"]])
    if previous and carried:
        prev_cells = {frozenset((previous["units"][p[0]]["key"], previous["units"][p[1]]["key"])): p
                      for p in previous["cells"]}
        for c in db["cells"]:
            if not c[7] & S.FLAG_NOT_RESIMULATED:
                continue
            e = db["evidence"][c[8]]
            ka, kb = id_key[c[0]], id_key[c[1]]
            if key2(units[ka]["profileHash"], units[kb]["profileHash"]) == e["pairKey"]:
                continue
            p = prev_cells.get(frozenset((ka, kb)))
            if p is None:
                bad("carried cell has no previous cell", [ka, kb])
                continue
            same = previous["units"][p[0]]["key"] == ka
            want = (p[2] if same else S.INVERSE[p[2]], p[3], *((p[4], p[5]) if same else (p[5], p[4])))
            if (c[2], c[3], c[4], c[5]) != want or previous["evidence"][p[8]]["pairKey"] != e["pairKey"]:
                bad("carried cell differs from the previous release", [ka, kb])
    elif carried:
        bad("carried cells need --previous-db to be verified", carried)

    # evidence <-> source rows
    reclassified = Counter()
    for eid, e in db["evidence"].items():
        pk = e["pairKey"]
        if pk not in current_pks:
            continue
        h1, h2 = pk.split("|")
        row = rows.get(pk)
        if row is None and h1 == h2:
            row = {"pairKey": pk, "outcome": "equivalent", "evidenceType": "identity", "source": "identity",
                   "context": None, "seeds": []}
        if row is None:
            bad("evidence without a source row", pk)
            continue
        ctx = context_of(h1, h1) if h1 == h2 else row["context"]
        want = S.compact_evidence({**row}, ctx)
        if pk in blocked:
            want["rerun"] = blocked[pk]
        got = {k: v for k, v in e.items() if k != "carriedTo"}
        if got != want:
            diff = sorted(k for k in set(got) | set(want) if got.get(k) != want.get(k))
            bad("evidence differs from its index/snapshot row", [pk, diff])
        if h1 != h2 and ctx != context_of(*ctx["profiles"]):
            bad("stored context is not this setup's context", pk)
        seeds = row.get("seeds") or []
        if row["evidenceType"] == "observed" and seeds and h1 != h2:
            job = {"profileHashes": ctx["profiles"], "pairKey": pk}
            winners = {s[1] for s in seeds}
            cls = physical_outcome(job, next(iter(winners))) if len(winners) == 1 else "close_uncertain"
            reclassified["agree" if cls == row["outcome"] else "disagree"] += 1
            if cls != row["outcome"]:
                bad("observed seeds do not classify to the stored outcome", pk)
    unreferenced = sorted(set(db["evidence"]) - set(used))
    _check(checks, "no unreferenced evidence rows", not unreferenced, len(unreferenced))
    for kind in ("cell without evidence", "evidence pairKey is not the cell's pair",
                 "carried cell without a blocked context or --carry-unsimulated", "blocked context not flagged",
                 "cell evidence type differs from evidence", "cell outcome orientation",
                 "cell counts differ from the context", "carried cell has no previous cell",
                 "carried cell differs from the previous release", "carried cells need --previous-db to be verified",
                 "evidence without a source row", "evidence differs from its index/snapshot row",
                 "stored context is not this setup's context",
                 "observed seeds do not classify to the stored outcome"):
        _check(checks, kind + ": none", problems[kind] == 0,
               {"count": problems[kind], "example": examples.get(kind)} if problems[kind] else None)
    dataset = json.loads(db["metadata"]["dataset"])
    cell_types = dict(sorted(Counter(c[3] for c in db["cells"]).items()))
    ev_types = dict(sorted(Counter(db["evidence"][i]["evidenceType"] for i in used).items()))
    _check(checks, "dataset displayedEvidenceCounts = cells by type",
           dataset.get("displayedEvidenceCounts") == cell_types, cell_types)
    _check(checks, "dataset evidenceCounts = evidence by type", dataset.get("evidenceCounts") == ev_types, ev_types)
    _check(checks, "dataset displayedCells", dataset.get("displayedCells") == len(db["cells"]), len(db["cells"]))
    _check(checks, f"size < {max_bytes / 1048576:.0f} MiB", db["bytes"] < max_bytes, db["bytes"])
    return {"db": str(db_path), "sha256": db["sha256"], "bytes": db["bytes"], "ok": all(c["ok"] for c in checks),
            "checks": checks, "cells": len(db["cells"]), "evidence": len(db["evidence"]),
            "cellEvidenceTypes": cell_types, "evidenceTypes": ev_types, "flaggedCells": flagged,
            "carriedCells": carried, "blockedContexts": len(blocked),
            "seedClassification": dict(reclassified)}


# ------------------------------------------------------------------ compare

def _cell_map(db: dict) -> dict:
    """{frozenset(keys): (keyA, keyB, outcome, type, countA, countB, flags, evidence)} oriented by sorted key."""
    out = {}
    for a, b, outcome, etype, ca, cb, tier, flags, eid in db["cells"]:
        ka, kb = db["units"][a]["key"], db["units"][b]["key"]
        if ka > kb:
            ka, kb, ca, cb, outcome = kb, ka, cb, ca, S.INVERSE[outcome]
        out[frozenset((ka, kb))] = (ka, kb, outcome, etype, ca, cb, flags, db["evidence"][eid])
    return out


def _run_of(e: dict):
    src = e.get("source") or ""
    return (src, e.get("jobId")) if src.startswith("run:") else None


def compare(old: dict, new: dict) -> dict:
    ou = {u["key"]: u for u in old["units"].values()}
    nu = {u["key"]: u for u in new["units"].values()}
    strip = lambda u: {k: v for k, v in u.items() if k != "id"}
    units = {"added": sorted(set(nu) - set(ou)), "removed": sorted(set(ou) - set(nu)),
             "profileChanged": sorted(k for k in set(ou) & set(nu) if ou[k]["profileHash"] != nu[k]["profileHash"]),
             "otherwiseChanged": sorted(k for k in set(ou) & set(nu) if ou[k]["profileHash"] == nu[k]["profileHash"]
                                        and strip(ou[k]) != strip(nu[k])),
             "idChanged": sorted(k for k in set(ou) & set(nu) if ou[k]["id"] != nu[k]["id"])}
    oc, nc = _cell_map(old), _cell_map(new)
    by_civ = defaultdict(Counter)
    transitions = Counter()
    status = Counter()
    changed_examples = []
    resimulated, carried = {}, {}
    for key in set(oc) | set(nc):
        o, n = oc.get(key), nc.get(key)
        civs = {k.split("|")[0] for k in key}
        if o is None:
            kind = "added"
        elif n is None:
            kind = "removed"
        else:
            if o[2] != n[2]:
                kind = "outcomeChanged"
            elif o[3] != n[3]:
                kind = "evidenceTypeChanged"
            elif o[4:6] != n[4:6]:
                kind = "countsChanged"
            elif o[6] != n[6]:
                kind = "flagsChanged"
            elif o[7]["pairKey"] != n[7]["pairKey"] or _run_of(o[7]) != _run_of(n[7]):
                kind = "sameResultNewEvidence"
            else:
                kind = "unchanged"
            transitions[(o[3], n[3])] += 1
        status[kind] += 1
        if kind != "unchanged":
            for civ in civs:
                by_civ[civ][kind] += 1
            if kind == "outcomeChanged" and len(changed_examples) < 25:
                changed_examples.append({"cell": [n[0], n[1]], "old": o[2], "new": n[2], "evidenceType": n[3],
                                         "counts": [n[4], n[5]]})
        if n is not None:
            run = _run_of(n[7])
            if run and (o is None or _run_of(o[7]) != run):
                resimulated.setdefault(n[7]["pairKey"], {"pairKey": n[7]["pairKey"], "source": run[0], "jobId": run[1],
                                                         "outcome": n[7]["outcome"], "cells": 0,
                                                         "evidenceLevel": n[7].get("evidenceLevel"),
                                                         "seeds": len(n[7].get("seeds", []))})["cells"] += 1
            if n[6] & S.FLAG_NOT_RESIMULATED:
                carried.setdefault(n[7]["pairKey"], {"evidencePairKey": n[7]["pairKey"], "cells": 0,
                                                     "reason": "blocked" if n[7].get("rerun") else "kept"})["cells"] += 1
    o_pk = {e["pairKey"] for e in old["evidence"].values()}
    n_pk = {e["pairKey"] for e in new["evidence"].values()}
    return {"old": {"sha256": old["sha256"], "bytes": old["bytes"], "cells": len(old["cells"]),
                    "evidence": len(old["evidence"]), "units": len(ou)},
            "new": {"sha256": new["sha256"], "bytes": new["bytes"], "cells": len(new["cells"]),
                    "evidence": len(new["evidence"]), "units": len(nu)},
            "units": units, "cells": dict(sorted(status.items())),
            "byCivilization": {c: dict(v) for c, v in sorted(by_civ.items())},
            "evidenceTypeTransitions": {f"{a}->{b}": n for (a, b), n in sorted(transitions.items()) if a != b},
            "contexts": {"added": len(n_pk - o_pk), "removed": len(o_pk - n_pk), "kept": len(o_pk & n_pk)},
            "resimulated": sorted(resimulated.values(), key=lambda r: r["pairKey"]),
            "carried": sorted(carried.values(), key=lambda r: r["evidencePairKey"]),
            "outcomeChangedExamples": sorted(changed_examples, key=lambda r: r["cell"])}


# ------------------------------------------------------------------ summary

def summary_markdown(verification: dict | None, comparison: dict | None, api: dict | None) -> str:
    L = ["# Matchup Advisor data release summary", ""]
    if comparison:
        c = comparison
        changed = sum(v for k, v in c["cells"].items() if k != "unchanged")
        visible = sum(c["cells"].get(k, 0) for k in ("added", "removed", "outcomeChanged", "countsChanged"))
        L += ["## In plain words", "",
              f"- The new table has **{c['new']['cells']:,} unit-vs-unit cells** for {c['new']['units']} units "
              f"(was {c['old']['cells']:,} for {c['old']['units']}).",
              f"- **{visible:,} cells change what visitors see** (added, removed, a different winner, or different "
              f"army sizes); {changed - visible:,} more change only their evidence or flags.",
              f"- **{len(c['resimulated']):,} battle contexts were re-simulated** in this release "
              f"({sum(r['cells'] for r in c['resimulated']):,} cells).",
              f"- **{sum(r['cells'] for r in c['carried']):,} cells keep a previous result that was not re-simulated** "
              f"({len(c['carried'])} contexts; flagged, the site shows them as before).",
              f"- File size {c['old']['bytes'] / 1e6:.1f} MB -> {c['new']['bytes'] / 1e6:.1f} MB.", ""]
        if api:
            L += [f"- Website data: {api['identical']} of {api['files']} advisor API responses are byte-identical; "
                  f"advisor component version `{api['componentVersionOld'][:12]}` -> `{api['componentVersionNew'][:12]}`"
                  + (" (unchanged)." if api["componentVersionOld"] == api["componentVersionNew"] else "."), ""]
            if api["different"]:
                L += ["  Changed responses: " + ", ".join(f"`{n}`" for n in api["different"]), ""]
        L += ["## Cells", "", "| Status | Cells |", "|---|---:|"]
        L += [f"| {k} | {v:,} |" for k, v in c["cells"].items()]
        u = c["units"]
        L += ["", "## Units", "",
              f"- added {len(u['added'])}, removed {len(u['removed'])}, changed profile {len(u['profileChanged'])}, "
              f"other data changed {len(u['otherwiseChanged'])}, id changed {len(u['idChanged'])}"]
        for name in ("added", "removed", "profileChanged", "otherwiseChanged"):
            if u[name]:
                L.append(f"- {name}: " + ", ".join(f"`{k}`" for k in u[name][:40]) + (" ..." if len(u[name]) > 40 else ""))
        if c["byCivilization"]:
            kinds = sorted({k for v in c["byCivilization"].values() for k in v})
            L += ["", "## By civilization (cells involving the civilization)", "",
                  "| Civilization | " + " | ".join(kinds) + " |", "|---|" + "---:|" * len(kinds)]
            L += [f"| {civ} | " + " | ".join(f"{v.get(k, 0):,}" for k in kinds) + " |"
                  for civ, v in c["byCivilization"].items()]
        if c["evidenceTypeTransitions"]:
            L += ["", "## Evidence type changes", "", "| Old -> new | Cells |", "|---|---:|"]
            L += [f"| {k} | {v:,} |" for k, v in c["evidenceTypeTransitions"].items()]
        L += ["", f"## Contexts", "", f"- evidence rows added {c['contexts']['added']:,}, removed "
              f"{c['contexts']['removed']:,}, kept {c['contexts']['kept']:,}"]
        if c["resimulated"]:
            L += ["", "### Re-simulated in this release", "", "| pairKey | run | job | outcome | seeds | cells |",
                  "|---|---|---|---|---:|---:|"]
            L += [f"| `{r['pairKey'][:16]}…` | {r['source']} | {r['jobId']} | {r['outcome']} | {r['seeds']} | {r['cells']} |"
                  for r in c["resimulated"]]
        if c["carried"]:
            L += ["", "### Kept from the previous release (not re-simulated, flag 4)", "", "| evidence pairKey | reason | cells |",
                  "|---|---|---:|"]
            L += [f"| `{r['evidencePairKey'][:16]}…` | {r['reason']} | {r['cells']} |" for r in c["carried"][:200]]
            if len(c["carried"]) > 200:
                L.append(f"| ... {len(c['carried']) - 200} more | | |")
        if c["outcomeChangedExamples"]:
            L += ["", "### Examples of changed winners", "", "| Unit A | Unit B | old | new | type |", "|---|---|---|---|---|"]
            L += [f"| {r['cell'][0]} | {r['cell'][1]} | {r['old']} | {r['new']} | {r['evidenceType']} |"
                  for r in c["outcomeChangedExamples"]]
        L.append("")
    if verification:
        v = verification
        L += ["## Verification against inputs", "",
              f"Result: **{'PASSED' if v['ok'] else 'FAILED'}** - {v['cells']:,} cells, {v['evidence']:,} evidence rows, "
              f"{v['bytes']:,} bytes, sha256 `{v['sha256']}`.", "", "| Check | OK | Detail |", "|---|---|---|"]
        L += [f"| {c['check']} | {'yes' if c['ok'] else '**NO**'} | {json.dumps(c.get('detail')) if 'detail' in c else ''} |"
              for c in v["checks"]]
        L.append("")
    return "\n".join(L)
