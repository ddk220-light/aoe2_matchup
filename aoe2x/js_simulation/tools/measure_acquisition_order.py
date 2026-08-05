"""Is acquisition order structured, or random?

Needs traces decoded by decode_tape_frames.py. For each ratio it ranks every
unit by acquisition time within each run and reports how far a unit's rank
moves between runs. Uniformly random ordering gives an expected spread of
(n - 1) * (runs - 1) / (runs + 1).
"""
import argparse
import collections
import json
import os
import statistics

MASTERS = (567, 569)


def acquisitions(path):
    by = collections.defaultdict(list)
    with open(path) as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("master") not in MASTERS:
                continue
            by[row["id"]].append(row)
    out = {}
    for uid, series in by.items():
        series.sort(key=lambda r: r["t_ms"])
        first = next(
            (r for r in series if r.get("target_id") not in (None, -1)), None)
        if first:
            out[uid] = first["t_ms"] / 1000 - 0.2
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("ratios", nargs="+")
    args = parser.parse_args()

    pooled = []
    for ratio in args.ratios:
        tags = [ratio] + [f"{ratio}_r{i}" for i in range(2, args.runs + 1)]
        runs = []
        for tag in tags:
            path = os.path.join(args.trace_dir, f"{tag}.tape_trace.jsonl")
            if os.path.exists(path):
                runs.append(acquisitions(path))
        if len(runs) < 2:
            continue
        ranks = collections.defaultdict(list)
        for run in runs:
            for index, uid in enumerate(sorted(run, key=lambda u: run[u])):
                ranks[uid].append(index)
            pooled.extend(run.values())
        units = sorted(set().union(*[set(r) for r in runs]))
        spreads = [max(v) - min(v) for v in ranks.values() if len(v) == len(runs)]
        expected = (len(units) - 1) * (len(runs) - 1) / (len(runs) + 1)
        print(f"{ratio:6} units {len(units):3d} runs {len(runs)}  "
              f"rank spread median {statistics.median(spreads):5.1f} "
              f"of max {len(units) - 1:3d}   random expectation {expected:5.1f}")

    if pooled:
        print(f"\npooled delays n={len(pooled)}  min {min(pooled):.3f} "
              f"max {max(pooled):.3f} mean {statistics.mean(pooled):.3f} "
              f"stdev {statistics.stdev(pooled):.3f}")
        print("model Uniform[0.952, 1.708]: mean 1.330 stdev 0.218")


if __name__ == "__main__":
    main()
