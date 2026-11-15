"""Python-reference fixture for the browser Revision 5 advisor model (all 3,080 plans).

Runs ``advisor_model_v5.plan`` on exactly the rows the site serves
(``aoe2_api.services.advisor.advisor_matchups``: advisor DB + the committed
``data/golden/advisor_cell_metrics.json.gz``) and writes
``tests/advisor/fixtures/v5-plans.json.gz``, which ``tests/advisor/v5-parity.test.mjs``
compares with ``apps/web/src/features/advisor/model.mjs`` plan by plan.

Usage: python tools/economy/advisor_eco/build_advisor_parity_fixture.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys

import advisor_model_v5 as m5
from common import REPO

sys.path.insert(0, str(REPO / "apps" / "backend"))
from aoe2_api.services.advisor import advisor_catalog, advisor_matchups, cell_metrics  # noqa: E402

FIXTURE = REPO / "tests" / "advisor" / "fixtures" / "v5-plans.json.gz"
DIGITS = 9  # scores in the fixture; the browser rounds the same way before comparing


def _js_number(value):
    """JSON text as JavaScript's JSON.stringify writes it (integral floats without '.0', no -0)."""
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


def summary(p):
    r = lambda x: round(x, DIGITS)  # noqa: E731
    return {"main": p["main"], "support": p["support"],
            "supportGain": None if p["supportGain"] is None else r(p["supportGain"]),
            "gaps": p["gaps"], "additions": p["additions"], "unanswered": p["unanswered"],
            "score": {str(k): r(v) for k, v in sorted(p["score"].items())},
            "multiplier": {str(k): r(v) for k, v in sorted(p["multiplier"].items())}}


def main():
    catalog = advisor_catalog()
    units = {u["id"]: u for u in catalog["units"]}
    documents = {civ: advisor_matchups(civ)["opponents"] for civ in catalog["civilizations"]}
    plans = [{"civ": civ, "enemy": enemy, **summary(m5.plan(rows, units))}
             for civ in sorted(documents) for enemy, rows in sorted(documents[civ].items())]
    _, header = cell_metrics()
    metrics_bytes = (REPO / "data" / "golden" / "advisor_cell_metrics.json.gz").read_bytes()
    fixture = {"header": {"plans": len(plans), "config": m5.CONFIG, "digits": DIGITS,
                          "advisorDatasetSha256": header["advisorDataset"]["sha256"],
                          "cellMetricsSha256": hashlib.sha256(metrics_bytes).hexdigest(),
                          "rowsSha256": row_digest(documents)},
               "plans": plans}
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    data = gzip.compress(json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode(), compresslevel=9, mtime=0)
    FIXTURE.write_bytes(data)
    print("wrote", FIXTURE.relative_to(REPO), len(plans), "plans,", len(data), "bytes")


if __name__ == "__main__":
    main()
