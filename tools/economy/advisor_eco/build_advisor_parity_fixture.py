"""Python-reference fixture for the browser Revision 4 advisor model (all 3,080 plans).

Runs ``advisor_model_rev4.build`` (default weights, CONFIG) on exactly the rows the site
serves (``aoe2_api.services.advisor.advisor_matchups``: advisor DB + the committed
``data/golden/advisor_cell_metrics.json.gz``) and writes
``tests/advisor/fixtures/rev4-plans.json.gz``, which ``tests/advisor/rev4-parity.test.mjs``
compares with ``apps/web/src/features/advisor/model.mjs`` plan by plan.

It also compares the plans with the committed analysis output
``docs/army-economics/advisor-plans-rev4.json.gz`` (computed from the unrounded
``cells.csv.gz``) and prints every difference (expected: none).

Usage: python tools/economy/advisor_eco/build_advisor_parity_fixture.py
"""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import sys

import advisor_model_rev4 as m4
from common import REPO

sys.path.insert(0, str(REPO / "apps" / "backend"))
from aoe2_api.services.advisor import advisor_catalog, advisor_matchups, cell_metrics  # noqa: E402

FIXTURE = REPO / "tests" / "advisor" / "fixtures" / "rev4-plans.json.gz"
REFERENCE = REPO / "docs" / "army-economics" / "advisor-plans-rev4.json.gz"
DIGITS = 6  # scores in the fixture; the browser rounds the same way before comparing


def served_index(documents):
    """advisor_model_rev4.cell_index equivalent, built from the served rows (both orientations)."""
    idx = {}
    for opponents in documents.values():
        for rows in opponents.values():
            for row in rows:
                cat = row[9]
                if cat in ("close", "pending"):
                    continue
                won = cat in m4.WIN_CATS
                hp = row[11]
                idx[(row[0], row[1])] = {"cat": cat, "won": won, "hp_winner": hp, "hp_own": hp if won else 0.0,
                                         "vm_own": row[12], "vm_opp": row[13], "pending": False,
                                         "nohp": cat == "cheap_loss" and hp is None}
    return idx


def _js_number(value):
    """JSON text as JavaScript's JSON.stringify writes it (integral floats without '.0')."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def row_digest(documents):
    """SHA-256 over every (civ, opponent) row list, in the text JSON.stringify produces."""
    digest = hashlib.sha256()
    for key in sorted(f"{civ}|{enemy}" for civ, opponents in documents.items() for enemy in opponents):
        civ, enemy = key.split("|")
        rows = [[_js_number(v) for v in row] for row in documents[civ][enemy]]
        digest.update(f"{key}\n{json.dumps(rows, separators=(',', ':'), ensure_ascii=False)}\n".encode())
    return digest.hexdigest()


def plan_summary(p):
    r = lambda x: round(x, DIGITS)  # noqa: E731
    uid = lambda e: e["unit"]["id"]  # noqa: E731
    sup = p["support"]
    return {
        "main": uid(p["main"]), "mainAdvantage": r(p["main"]["adv"]), "mainBase": r(p["main"]["base"]),
        "targets": [[t, k] for t, k in p["targets"]],
        "support": uid(sup["entry"]) if sup else None,
        "supportScore": r(sup["score"]) if sup else None,
        "helps": [[h["opp"], h["kind"], h["why"], r(h["value"])] for h in sup["helps"]] if sup else [],
        "additions": [[uid(a["entry"]), a["covers"]] for a in p["additions"]],
        "uncovered": p["uncovered"], "unanswered": p["unanswered"],
        "alternatives": [uid(e) for e in p["alternatives"]],
        "strength": {str(k): r(v) for k, v in sorted(p["strength"].items())},
    }


def main():
    # The model's sum() calls use CPython >= 3.12 compensated float summation; the browser's
    # pySum() reproduces exactly that, so an older Python would write a different fixture.
    if sys.version_info < (3, 12):
        raise SystemExit("run with Python >= 3.12 (compensated sum(), as the site's Python 3.13)")
    catalog = advisor_catalog()
    units = {u["id"]: u for u in catalog["units"]}
    documents = {civ: advisor_matchups(civ)["opponents"] for civ in catalog["civilizations"]}
    idx = served_index(documents)
    plans = {}
    for left, right in itertools.combinations(sorted(documents), 2):
        res = m4.build(documents[left][right], units, idx, "default")
        plans[(left, right)] = res["left"]
        plans[(right, left)] = res["right"]

    # Compare with the committed analysis output (unrounded inputs).
    with gzip.open(REFERENCE, "rt") as handle:
        reference = {(p["civ"], p["enemy"]): p["rev4"] for p in json.load(handle)["plans"]}
    name = lambda i: units[i]["name"]  # noqa: E731
    diffs = []
    for key, p in sorted(plans.items()):
        ref = reference[key]
        got = {"main": p["main"]["unit"]["name"], "support": p["support"]["entry"]["unit"]["name"] if p["support"] else None,
               "targets": [[name(t), k] for t, k in p["targets"]],
               "additions": [[a["entry"]["unit"]["name"], [name(x) for x in a["covers"]]] for a in p["additions"]],
               "unanswered": [name(x) for x in p["unanswered"]],
               "advantage": round(p["main"]["adv"], 3), "base": round(p["main"]["base"], 3),
               "helps": len(p["support"]["helps"]) if p["support"] else 0,
               "supportScore": round(p["support"]["score"], 3) if p["support"] else None,
               "alternatives": [e["unit"]["name"] for e in p["alternatives"]]}
        want = {"main": ref["main"]["unit"], "support": ref["support"]["unit"] if ref["support"] else None,
                "targets": ref["targets"], "additions": ref["additions"], "unanswered": ref["unanswered"],
                "advantage": ref["main"]["advantage"], "base": ref["main"]["base"],
                "helps": len(ref["support"]["helps"]) if ref["support"] else 0,
                "supportScore": ref["support"]["score"] if ref["support"] else None,
                "alternatives": [a["unit"] for a in ref["alternatives"]]}
        for field in got:
            if got[field] != want[field]:
                diffs.append([*key, field, got[field], want[field]])
    print(f"{len(plans)} plans; differences vs {REFERENCE.name}: {len(diffs)}")
    for d in diffs[:40]:
        print("  ", d)

    _, header = cell_metrics()
    metrics_bytes = (REPO / "data" / "golden" / "advisor_cell_metrics.json.gz").read_bytes()
    fixture = {
        "header": {"plans": len(plans), "weights": "default", "weightValues": m4.WEIGHT_SETS["default"],
                   "config": {k: list(v) if isinstance(v, tuple) else v for k, v in m4.CONFIG.items()},
                   "digits": DIGITS, "advisorDatasetSha256": header["advisorDataset"]["sha256"],
                   "cellMetricsSha256": hashlib.sha256(metrics_bytes).hexdigest(),
                   "referenceDifferences": len(diffs), "rowsSha256": row_digest(documents)},
        "plans": [{"civ": civ, "enemy": enemy, **plan_summary(p)} for (civ, enemy), p in sorted(plans.items())],
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    data = gzip.compress(json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode(), compresslevel=9, mtime=0)
    FIXTURE.write_bytes(data)
    print("wrote", FIXTURE.relative_to(REPO), len(data), "bytes")
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
