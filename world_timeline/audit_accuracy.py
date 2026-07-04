#!/usr/bin/env python3
"""Accuracy audit for the World History Timeline extraction.

Oracle: several hundred entry labels embed their own date range
("Mamluk Egypt (AD 1250–1517)"). The extractor stores those as
label_year_start/label_year_end; this script compares them against the
positional years recovered from the sheet geometry and reports the
agreement rate and the worst disagreements.

A start clipped at the sheet's 3400 BC left edge (continues_left) is not
counted as an error when the label says the entry begins earlier.

Usage:
    python world_timeline/audit_accuracy.py [path/to/world_timeline.json]
"""

import json
import os
import sys

TOL = 4  # years; the sheet grid is 2 years/column, both ends can round


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output", "world_timeline.json"
    )
    entries = json.load(open(path, encoding="utf-8"))["entries"]

    errs, outliers = [], []
    for e in entries:
        ya, yb = e["label_year_start"], e["label_year_end"]
        if ya is None or yb is None:
            continue  # no range in label (or open-ended '- present')
        start_err = (
            0
            if (e["continues_left"] and ya < -3400)
            else e["year_start"] - ya
        )
        end_err = e["year_end"] - yb
        errs.append((start_err, end_err, e))
        if abs(start_err) > TOL or abs(end_err) > TOL:
            outliers.append((e, start_err, end_err))

    within = sum(1 for a, b, _ in errs if abs(a) <= TOL and abs(b) <= TOL)
    active = [(a, b, e) for a, b, e in errs if not e["is_layout"]]
    w_act = sum(1 for a, b, _ in active if abs(a) <= TOL and abs(b) <= TOL)
    print(f"range-labeled entries checked: {len(errs)}")
    print(f"agreement within ±{TOL} yrs (all):        {within}/{len(errs)}"
          f" = {within/len(errs):.1%}")
    print(f"agreement within ±{TOL} yrs (non-layout): {w_act}/{len(active)}"
          f" = {w_act/len(active):.1%}")

    outliers = [o for o in outliers if not o[0]["is_layout"]]
    outliers.sort(key=lambda o: -(abs(o[1]) + abs(o[2])))
    print(f"\nworst non-layout disagreements ({len(outliers)} total) — mostly bars"
          " whose drawn extent legitimately differs from the label"
          " (interrupted parent bars, see ACCURACY.md):")
    for e, se, ee in outliers[:20]:
        print(f"  [{e['section'][:16]:16s}] r{e['row']:4d}"
              f" {e['label'][:52]!r:54s}"
              f" label {e['label_year_start']}..{e['label_year_end']}"
              f" drawn {e['year_start']}..{e['year_end']} ({se:+d},{ee:+d})")


if __name__ == "__main__":
    main()
