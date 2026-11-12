"""Check that advisor_model.py (variant "current") reproduces the real JS model.

Runs apps/web/src/features/advisor/model.mjs through node (dump_js_plans.mjs) for
all 1,540 civilization pairs and compares main, sidekick, additions, unanswered,
uncovered, alternatives and the main unit's win/loss lists with the Python port.
Usage: python tools/economy/advisor_eco/check_js_parity.py
"""
import itertools
import json
import subprocess
from pathlib import Path

from advisor_model import build, summary
from common import OUT, advisor_units, civ_documents, connect

HERE = Path(__file__).resolve().parent


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    db = connect()
    units = advisor_units(db)
    documents = civ_documents(db, units)
    catalog = OUT / "advisor_units.json"
    catalog.write_text(json.dumps(list(units.values())))
    pairs = list(itertools.combinations(sorted(documents), 2))
    payload = "".join(json.dumps({"left": l, "right": r, "rows": documents[l][r]}) + "\n" for l, r in pairs)
    result = subprocess.run(["node", str(HERE / "dump_js_plans.mjs"), str(catalog)], input=payload,
                            capture_output=True, text=True, check=True)
    mismatches = 0
    for line, (left, right) in zip(result.stdout.splitlines(), pairs):
        js = json.loads(line)
        assert (js["left"], js["right"]) == (left, right)
        py = build(documents[left][right], units)
        for side in ("left", "right"):
            if summary(py[side]) != js["plans"][side]:
                mismatches += 1
                if mismatches <= 5:
                    print("MISMATCH", left, right, side, summary(py[side]), js["plans"][side])
    print(f"pairs {len(pairs)}, plans {2 * len(pairs)}, mismatches {mismatches}")
    raise SystemExit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
