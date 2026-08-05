"""golden_report.py — turn decoded fights into a readable ground-truth report, and
check the MEASURED engine behaviour against what the reference DB claims.

Per side it reports what the game actually did: damage per hit (-> effective armour),
swing interval vs the DB's reload_time, the gap between a unit's median and minimum
swing (that gap IS crowd churn, measured rather than fitted), shots fired vs hits
landed (-> accuracy), engagement distance, and time-to-first-blood.

  python golden_report.py <decoded_dir> [--md OUT.md]
"""
import argparse
import glob
import gzip
import json
import os
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REF_DB = os.path.join(REPO, "data", "golden", "aoe2_reference.db")


def load_jsonl_gz(path):
    if not os.path.exists(path):
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def db_row(civ, slug):
    if not os.path.exists(REF_DB):
        return None
    con = sqlite3.connect(REF_DB)
    con.row_factory = sqlite3.Row
    for cand in (slug, f"{slug}_{civ.lower()}"):
        r = con.execute("SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?",
                        (civ, cand)).fetchone()
        if r:
            return dict(r)
    return None


def report(base, civs=None):
    name = os.path.basename(base)
    meta = json.load(open(base + ".meta.json"))
    summ = json.load(open(base + ".summary.json"))
    dmg = load_jsonl_gz(base + ".damage.jsonl.gz")
    miss = load_jsonl_gz(base + ".missiles.jsonl.gz")

    out = [f"## {name}", ""]
    out.append(f"- stream {meta['stream_hz']} Hz, fight {meta['duration_s']}s, "
               f"{meta['damage_events']} hits, {meta['unit_samples']} unit samples, "
               f"{meta['missile_samples']} missile samples")
    out.append(f"- outcome: **{summ['outcome']}**")
    out.append("")

    # shots fired per shooter: a missile id is one projectile; count distinct ids
    shots = defaultdict(set)
    for m in miss:
        if m.get("fired_from") is not None:
            shots[m["fired_from"]].add(m["id"])

    for key in ("side2", "side3"):
        s = summ["sides"][key]
        units = [u for u in summ["units"] if u["owner"] == s["owner"]]
        if not units:
            continue
        dph = Counter()
        for u in units:
            for k, v in u["damage_per_hit"].items():
                dph[float(k)] += v
        # `is not None`, NOT truthiness: an interval of exactly 0.0 is real (two hits
        # landing in the same frame) and truthiness silently drops it — which emptied
        # `mins` while `ivs` stayed populated and crashed the report.
        ivs = [u["swing_interval_median"] for u in units
               if u["swing_interval_median"] is not None]
        mins = [u["swing_interval_min"] for u in units
                if u["swing_interval_min"] is not None]
        firsts = [u["first_hit_t"] for u in units if u["first_hit_t"] is not None]
        dists = [u.get("distance_tiles", 0) for u in units]
        n_shots = sum(len(shots.get(u["id"], ())) for u in units)

        out.append(f"### {s['unit']}  ({s['start_count']} -> {s['survivors']} survivors, "
                   f"{s['hp_remaining']:.0f} hp left)")
        out.append("")
        out.append("| measured | value |")
        out.append("|---|---|")
        out.append(f"| hits landed | {s['hits_landed']} |")
        out.append(f"| total damage | {s['damage_dealt']:.0f} |")
        out.append(f"| kills | {s['kills']} |")
        top = ", ".join(f"{d:g}x{n}" for d, n in sorted(dph.items(), reverse=True)[:6])
        out.append(f"| damage per hit | {top} |")
        if ivs and mins:
            out.append(f"| swing interval, median of units | {statistics.median(ivs):.3f}s |")
            out.append(f"| swing interval, fastest observed | {min(mins):.3f}s |")
            out.append(f"| churn (median - fastest) | "
                       f"{statistics.median(ivs) - min(mins):+.3f}s |")
        if firsts:
            out.append(f"| first blood | {min(firsts):.2f}s |")
        out.append(f"| mean distance travelled | {sum(dists)/len(dists):.1f} tiles |")
        if n_shots:
            # a projectile that never produced a damage event is a MISS, measured
            out.append(f"| projectiles fired | {n_shots} |")
            out.append(f"| projectiles that hit | {s['hits_landed']} |")
            out.append(f"| projectiles that missed | {max(0, n_shots - s['hits_landed'])} |")
            out.append(f"| measured accuracy | {100.0*s['hits_landed']/n_shots:.1f}% |")

        # TRAMPLE: one swing landing on several victims at the same instant. The primary
        # target takes full damage, the neighbours take the splash fraction.
        swings = defaultdict(list)
        for d in dmg:
            if d.get("attacker_owner") == s["owner"]:
                swings[(round(d["t"], 2), d["attacker"])].append(d)
        multi = [v for v in swings.values() if len(v) > 1]
        if multi:
            victims = [len(v) for v in multi]
            splash = [min(x["damage"] for x in v) / max(x["damage"] for x in v)
                      for v in multi if max(x["damage"] for x in v) > 0]
            out.append(f"| swings hitting >1 victim (trample) | {len(multi)} of "
                       f"{len(swings)} ({100.0*len(multi)/len(swings):.0f}%) |")
            out.append(f"| victims per trample swing | mean "
                       f"{sum(victims)/len(victims):.2f}, max {max(victims)} |")
            if splash:
                out.append(f"| splash fraction of primary | "
                           f"{statistics.median(splash):.2f} |")

        # DB cross-check
        civ = (civs or {}).get(key)
        row = db_row(civ, _slug_guess(s["unit"])) if civ else None
        if row:
            out.append("")
            out.append("| DB claims | measured |")
            out.append("|---|---|")
            if mins:
                out.append(f"| reload_time {row['final_reload_time']:.2f}s | "
                           f"fastest swing {min(mins):.3f}s |")
            if dph:
                out.append(f"| attack {row['final_attack']:.0f} | "
                           f"most common hit {max(dph, key=dph.get):g} |")
            if row["final_accuracy"] and n_shots:
                out.append(f"| accuracy {row['final_accuracy']:.0f}% | "
                           f"{100.0*s['hits_landed']/n_shots:.0f}% connected |")
        out.append("")
    return "\n".join(out)


def _slug_guess(label):
    return label.lower().replace(" ", "_")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("decoded_dir")
    ap.add_argument("--md")
    args = ap.parse_args(argv)
    bases = sorted({p[: -len(".meta.json")]
                    for p in glob.glob(os.path.join(args.decoded_dir, "*.meta.json"))})
    chunks = ["# In-game ground truth — decoded fights", ""]
    for b in bases:
        chunks.append(report(b))
    text = "\n".join(chunks)
    if args.md:
        open(args.md, "w", encoding="utf-8").write(text)
        print(f"-> {args.md}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
