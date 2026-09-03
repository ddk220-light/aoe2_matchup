"""Task 11 — cross-engine comparison report generator. READ-ONLY.

Reads js_results.json + py_results.json (600 rows each: 120 unordered pairs of
the 16-unit roster, 10 v 10, seeds 1-5) and writes REPORT.md.

    python lab/cross_engine/compare.py

It states differences; it draws no conclusions about which engine is right.

METRIC DEFINITIONS (all of them are stated in the report too, because a number
without its definition is not a measurement):

  survivor margin  m = alive_a - alive_b, computed per fight in each engine.
                   Delta = |m_js - m_py|. Range 0..20.
  HP% margin       h = hp_a/(10 x maxhp_a) - hp_b/(10 x maxhp_b), per fight,
                   where maxhp comes from combat_dicts.json ("hp") and hp_x is
                   the sum over LIVING units only (both runners use that rule).
                   Delta = |h_js - h_py|, reported in percentage points.
  fight-time ratio t_js / t_py per fight (both engines report game-seconds).
  majority winner  the normalised winner value held by >= 3 of the 5 seeds;
                   "split" when no value reaches 3.
  agreement        both engines produced a (non-"split") majority AND they are
                   equal. "split" on either side counts as disagreement and is
                   reported separately so it cannot hide inside the percentage.
"""

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNT = 10
DECISIVE = ("a", "b")


def load(name):
    # encoding is explicit: read_text() would use the Windows locale codepage
    # and turn the roster's em dashes into mojibake.
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def majority(values):
    c = Counter(values)
    val, n = c.most_common(1)[0]
    return val if n >= 3 else "split"


def fmt(x, nd=2):
    return f"{x:.{nd}f}"


def main():
    js = load("js_results.json")
    py = load("py_results.json")
    roster = load("roster.json")
    dicts = load("combat_dicts.json")

    maxhp, ranged = {}, {}
    for u in roster["units"]:
        cd = dicts[f"{u['civ']}|{u['slug']}"]
        maxhp[u["key"]] = float(cd["hp"])
        ranged[u["key"]] = float(cd.get("attack_range") or 0) > 0
    label = {u["key"]: u["name"] for u in roster["units"]}
    civ = {u["key"]: u["civ"] for u in roster["units"]}

    jsr = {(r["a"], r["b"], r["seed"]): r for r in js["rows"]}
    pyr = {(r["a"], r["b"], r["seed"]): r for r in py["rows"]}
    assert set(jsr) == set(pyr), "the two runs cover different fights"
    keys = sorted(jsr)
    seeds = js["seeds"]
    pairs = sorted({(a, b) for a, b, _ in keys})

    def hp_margin(r, a, b):
        return r["hp_a"] / (COUNT * maxhp[a]) - r["hp_b"] / (COUNT * maxhp[b])

    def surv_margin(r):
        return r["alive_a"] - r["alive_b"]

    # ---- per-fight deltas ---------------------------------------------------
    d_surv, d_hp, t_ratio, row_agree = [], [], [], []
    per_pair = defaultdict(lambda: {"surv": [], "hp": [], "ratio": []})
    for k in keys:
        a, b, _ = k
        j, p = jsr[k], pyr[k]
        ds = abs(surv_margin(j) - surv_margin(p))
        dh = abs(hp_margin(j, a, b) - hp_margin(p, a, b))
        d_surv.append(ds)
        d_hp.append(dh)
        per_pair[(a, b)]["surv"].append(ds)
        per_pair[(a, b)]["hp"].append(dh)
        if p["time"] > 0 and j["time"] > 0:
            r = j["time"] / p["time"]
            t_ratio.append(r)
            per_pair[(a, b)]["ratio"].append(r)
        row_agree.append(j["winner"] == p["winner"])

    # ---- per-pair majorities ------------------------------------------------
    pair_rows = []
    for (a, b) in pairs:
        jm = majority([jsr[(a, b, s)]["winner"] for s in seeds])
        pm = majority([pyr[(a, b, s)]["winner"] for s in seeds])
        agree = (jm == pm) and jm != "split"
        pp = per_pair[(a, b)]
        pair_rows.append({
            "a": a, "b": b, "js": jm, "py": pm, "agree": agree,
            "d_surv": statistics.mean(pp["surv"]),
            "d_hp": statistics.mean(pp["hp"]),
            "ratio": statistics.mean(pp["ratio"]) if pp["ratio"] else float("nan"),
        })

    n_pairs = len(pair_rows)
    agreed = sum(1 for r in pair_rows if r["agree"])
    split_js = sum(1 for r in pair_rows if r["js"] == "split")
    split_py = sum(1 for r in pair_rows if r["py"] == "split")
    both_dec = [r for r in pair_rows if r["js"] in DECISIVE and r["py"] in DECISIVE]
    both_dec_agree = sum(1 for r in both_dec if r["js"] == r["py"])

    # sensitivity: honour the Python's HP%-tiebreak at the 600 s cap
    alt_agreed = 0
    for (a, b) in pairs:
        jm = majority([jsr[(a, b, s)]["winner"] for s in seeds])
        alt = []
        for s in seeds:
            p = pyr[(a, b, s)]
            w = p["winner"]
            if w == "timeout_both_alive" and p["end_reason"] == "time_cap":
                w = "a" if p["raw_winner"] == 1 else ("b" if p["raw_winner"] == 2 else "draw")
            alt.append(w)
        if majority(alt) == jm and jm != "split":
            alt_agreed += 1

    # ---- timeouts / end reasons --------------------------------------------
    js_end = Counter(r["end_reason"] for r in js["rows"])
    py_end = Counter(r["end_reason"] for r in py["rows"])
    js_to = [r for r in js["rows"] if r["winner"] == "timeout_both_alive"]
    py_to = [r for r in py["rows"] if r["winner"] == "timeout_both_alive"]
    js_to_pairs = Counter((r["a"], r["b"]) for r in js_to)
    py_to_pairs = Counter((r["a"], r["b"]) for r in py_to)
    py_kite = [r for r in py["rows"] if r["end_reason"] == "kite_win"]
    py_kite_pairs = Counter((r["a"], r["b"]) for r in py_kite)

    # ---- worst-diverging pairs ---------------------------------------------
    # Rank: majority-winner disagreement first, then mean |delta survivor
    # margin|, then mean |delta HP% margin|. Stated in the report.
    worst = sorted(pair_rows,
                   key=lambda r: (0 if not r["agree"] else 1, -r["d_surv"], -r["d_hp"]))[:10]

    # ---- write --------------------------------------------------------------
    L = []
    w = L.append
    w("# Cross-engine comparison — extracted JS engine vs `simulation_real.py`")
    w("")
    w("Generated by `lab/cross_engine/compare.py`. READ-ONLY experiment: nothing in "
      "`aoe2x/`, `apps/`, `tools/` or `data/golden/` was modified to produce it. "
      "**Divergence is expected** — `docs/simulation-engine-migration.md` §6 documents "
      "six behavioural differences between these two engines (map size, spawn X, spawn "
      "jitter, collision radius, kite gate, crowd churn). This file maps where and how "
      "big the differences land; it draws no conclusion about which engine is right.")
    w("")
    w("## Methods")
    w("")
    w(f"16-unit roster (below), all **{len(pairs)} unordered pairs**, **{COUNT} v {COUNT}** "
      f"units a side, seeds **{', '.join(str(s) for s in seeds)}** = "
      f"**{len(keys)} fights per engine**. Team 1 = `a`, team 2 = `b` in both engines. "
      "Both engines are fed the SAME combat dicts (`combat_dicts.json`, built from "
      "`data/golden/aoe2_reference.db` age='Imperial' rows by `run_py.py`, same payload "
      "shape the webapp serves), so unit stats are identical and every difference below "
      "comes from the engines themselves.")
    w("")
    w(f"**Caps.** JS: 600 game-seconds = 36000 ticks at 1/60 s, no wall-clock cap, no "
      f"early exit; on running out with both sides alive `sim.winner` stays `null`. "
      f"Python: 600 game-seconds = 18000 ticks at 1/30 s (`MAX_BATTLE_SECONDS`), "
      f"wall-clock backstop disabled (`max_wallclock=None`) so results do not depend on "
      f"the host; at the cap it declares a winner by HP%, and from "
      f"{py['kite_decision_time']:.0f} s (`KITE_DECISION_TIME`) it can also end a fight "
      f"early as `kite_win` (decisive) or `stalemate` (winner 0, both sides alive).")
    w("")
    w("**Winner normalisation** (the same four values on both sides; raw engine values "
      "are preserved in the JSON as `raw_winner` / `end_reason`):")
    w("")
    w("| normalised | JS | Python |")
    w("|---|---|---|")
    w("| `a` | `winner === 1` | `winner == 1` (`eliminated` or `kite_win`) |")
    w("| `b` | `winner === 2` | `winner == 2` (`eliminated` or `kite_win`) |")
    w("| `draw` | `winner === 0` (mutual annihilation) | `winner == 0`, `eliminated`, both teams wiped |")
    w("| `timeout_both_alive` | `winner === null` — 600 s spent, both sides alive | `end_reason` `time_cap` (600 s) **or** `stalemate` (kite decision), both sides alive |")
    w("")
    w("The Python's HP%-tiebreak at the 600 s cap is **discarded** in the normalised "
      "field, because the JS refuses to break that tie and scoring one engine's "
      "tiebreak against the other's abstention would manufacture disagreement. A "
      "sensitivity figure with the tiebreak honoured is given in §2. The Python's "
      "`kite_win` early exit IS kept as decisive, because the engine does declare a "
      "winner there; those fights are counted in §4.")
    w("")
    w("**RNG.** The two engines use different RNG algorithms, so the same seed does NOT "
      "produce comparable draws. The comparison is therefore distributional: 5 seeds a "
      "pair, majority (3-of-5) winner, and means over all "
      f"{len(keys)} fights.")
    w("")
    w("**Metrics.** survivor margin `m = alive_a - alive_b` per fight, delta = "
      "`|m_js - m_py|` (0..20). HP% margin `h = hp_a/(10 x maxhp_a) - hp_b/(10 x "
      "maxhp_b)` per fight, living units only, delta = `|h_js - h_py|` in percentage "
      "points. Fight-time ratio = `t_js / t_py` in game-seconds. Majority winner = the "
      "value held by >= 3 of 5 seeds, else `split`. Two pairs agree when both engines "
      "produced a non-`split` majority and the majorities are equal.")
    w("")
    w("## Roster")
    w("")
    w("Five slugs from the task brief do not exist in the Imperial-only reference DB and "
      "were corrected by `LIKE` lookup (no unit class was dropped):")
    w("")
    w("| key | civ | unit | class | brief asked for | corrected |")
    w("|---|---|---|---|---|---|")
    for u in roster["units"]:
        w(f"| `{u['key']}` | {u['civ']} | {u['name']} | {u['class']} | "
          f"`{u['brief_slug']}` | {'**yes**' if u['corrected'] else 'no'} |")
    w("")
    w("## 1. Per-pair majority winner (3 of 5 seeds)")
    w("")
    w("`a` is team 1, `b` is team 2. Delta columns are means over the pair's 5 seeds.")
    w("")
    w("| a | b | JS majority | Python majority | agree | mean \\|delta surv margin\\| | mean \\|delta HP% margin\\| | mean t_js/t_py |")
    w("|---|---|---|---|---|---|---|---|")
    for r in sorted(pair_rows, key=lambda r: (r["a"], r["b"])):
        ratio = "n/a" if r["ratio"] != r["ratio"] else fmt(r["ratio"])
        w(f"| `{r['a']}` | `{r['b']}` | {r['js']} | {r['py']} | "
          f"{'yes' if r['agree'] else '**NO**'} | {fmt(r['d_surv'])} | "
          f"{fmt(100 * r['d_hp'], 1)} pp | {ratio} |")
    w("")
    w("## 2. Aggregates")
    w("")
    w("| metric | value |")
    w("|---|---|")
    w(f"| pairs compared | {n_pairs} |")
    w(f"| **winner agreement (per-pair majority)** | **{agreed}/{n_pairs} = {fmt(100 * agreed / n_pairs, 1)}%** |")
    w(f"| winner agreement (per-fight, all {len(keys)} fights) | {sum(row_agree)}/{len(keys)} = {fmt(100 * sum(row_agree) / len(keys), 1)}% |")
    w(f"| pairs where BOTH engines were decisive (`a`/`b`) | {len(both_dec)} |")
    w(f"| ...of those, same winner | {both_dec_agree}/{len(both_dec)} = {fmt(100 * both_dec_agree / len(both_dec), 1) if both_dec else 'n/a'}% |")
    w(f"| pairs with a `split` majority — JS / Python | {split_js} / {split_py} |")
    w(f"| sensitivity: agreement if the Python's 600 s HP%-tiebreak is honoured | {alt_agreed}/{n_pairs} = {fmt(100 * alt_agreed / n_pairs, 1)}% |")
    w(f"| **mean \\|delta survivor margin\\|** | **{fmt(statistics.mean(d_surv))} units** (median {fmt(statistics.median(d_surv))}, max {max(d_surv)}) |")
    w(f"| **mean \\|delta HP% margin\\|** | **{fmt(100 * statistics.mean(d_hp), 1)} pp** (median {fmt(100 * statistics.median(d_hp), 1)} pp, max {fmt(100 * max(d_hp), 1)} pp) |")
    w(f"| **mean fight-time ratio t_js/t_py** | **{fmt(statistics.mean(t_ratio))}x** (median {fmt(statistics.median(t_ratio))}x, min {fmt(min(t_ratio))}x, max {fmt(max(t_ratio))}x) |")
    w(f"| mean fight length — JS / Python | {fmt(statistics.mean([r['time'] for r in js['rows']]), 1)} s / {fmt(statistics.mean([r['time'] for r in py['rows']]), 1)} s |")
    w("")
    # Same aggregates split by whether the pair contains a ranged unit. Purely a
    # partition of the same 120 pairs — no claim attached.
    rng_pairs = [r for r in pair_rows if ranged[r["a"]] or ranged[r["b"]]]
    mel_pairs = [r for r in pair_rows if not (ranged[r["a"]] or ranged[r["b"]])]
    w("Split by composition (a pair is 'ranged' if either side has `attack_range` > 0):")
    w("")
    w("| subset | pairs | agree | mean \\|delta surv margin\\| | mean \\|delta HP% margin\\| | mean t_js/t_py |")
    w("|---|---|---|---|---|---|")
    for name, subset in ((">= 1 ranged unit", rng_pairs), ("melee only", mel_pairs)):
        if not subset:
            continue
        ag = sum(1 for r in subset if r["agree"])
        rr = [r["ratio"] for r in subset if r["ratio"] == r["ratio"]]
        w(f"| {name} | {len(subset)} | {ag}/{len(subset)} = "
          f"{fmt(100 * ag / len(subset), 1)}% | "
          f"{fmt(statistics.mean([r['d_surv'] for r in subset]))} | "
          f"{fmt(100 * statistics.mean([r['d_hp'] for r in subset]), 1)} pp | "
          f"{fmt(statistics.mean(rr)) if rr else 'n/a'} |")
    w("")
    w("## 3. Ten worst-diverging pairs")
    w("")
    w("Ranked by: majority-winner disagreement first, then mean |delta survivor margin|, "
      "then mean |delta HP% margin|. Per-seed detail follows each pair — "
      "`winner alive_a/alive_b @ time s`.")
    w("")
    disagreeing = [r for r in pair_rows if not r["agree"]]
    dis_ranged = sum(1 for r in disagreeing if ranged[r["a"]] or ranged[r["b"]])
    w(f"{len(disagreeing)} of {n_pairs} pairs disagree; {dis_ranged} of those "
      f"{len(disagreeing)} contain at least one ranged unit"
      + (f" ({len(rng_pairs)} of the {n_pairs} pairs do)." if rng_pairs else ".")
      + (" The ten shown below are the worst by the ranking above."
         if len(disagreeing) > 10 else
         " All disagreeing pairs are listed; the remainder of the ten are the "
         "largest-magnitude agreeing pairs."))
    w("")
    for i, r in enumerate(worst, start=1):
        a, b = r["a"], r["b"]
        w(f"### {i}. `{a}` ({civ[a]} {label[a]}) vs `{b}` ({civ[b]} {label[b]})")
        w("")
        w(f"JS majority **{r['js']}** / Python majority **{r['py']}** — "
          f"{'AGREE' if r['agree'] else 'DISAGREE'}; mean |delta surv margin| "
          f"{fmt(r['d_surv'])}, mean |delta HP% margin| {fmt(100 * r['d_hp'], 1)} pp.")
        w("")
        w("| seed | JS | Python | Python end_reason |")
        w("|---|---|---|---|")
        for s in seeds:
            j, p = jsr[(a, b, s)], pyr[(a, b, s)]
            w(f"| {s} | {j['winner']} {j['alive_a']}/{j['alive_b']} @ {fmt(j['time'], 1)} s "
              f"| {p['winner']} {p['alive_a']}/{p['alive_b']} @ {fmt(p['time'], 1)} s "
              f"| {p['end_reason']} |")
        w("")
    w("## 4. 600 s timeouts and early exits")
    w("")
    w(f"| | JS | Python |")
    w("|---|---|---|")
    w(f"| fights normalised `timeout_both_alive` | {len(js_to)}/{len(keys)} | {len(py_to)}/{len(keys)} |")
    w(f"| ...reached at the 600 s cap | {sum(1 for r in js_to if r['end_reason'] == 'time_cap')} | {sum(1 for r in py_to if r['end_reason'] == 'time_cap')} |")
    w(f"| ...reached early via `stalemate` (kite decision, {py['kite_decision_time']:.0f} s+) | n/a (no such rule) | {sum(1 for r in py_to if r['end_reason'] == 'stalemate')} |")
    w(f"| decisive early exits via `kite_win` | n/a (no such rule) | {len(py_kite)} |")
    w("")
    w("Raw `end_reason` counts — JS: "
      + ", ".join(f"`{k}` {v}" for k, v in sorted(js_end.items()))
      + "; Python: " + ", ".join(f"`{k}` {v}" for k, v in sorted(py_end.items())) + ".")
    w("")
    js_max_t = max(r["time"] for r in js["rows"])
    py_max_t = max(r["time"] for r in py["rows"])
    w(f"Longest fight — JS {fmt(js_max_t, 1)} s, Python {fmt(py_max_t, 1)} s. The Python's "
      f"kite-decision exits (`kite_win` / `stalemate`) are only evaluated from "
      f"`KITE_DECISION_TIME` {py['kite_decision_time']:.0f} s; the longest Python fight "
      f"in this run is {fmt(py_max_t, 1)} s, so neither rule fired anywhere in the "
      f"{len(keys)} fights.")
    w("")
    if js_to_pairs:
        w("**JS pairs that ran the full 600 s** (fights out of 5):")
        w("")
        for (a, b), n in js_to_pairs.most_common():
            w(f"- `{a}` vs `{b}` — {n}/5")
        w("")
    else:
        w("No JS fight reached the 600 s cap.")
        w("")
    if py_to_pairs:
        w("**Python pairs that ended unresolved** (fights out of 5, cap or stalemate):")
        w("")
        for (a, b), n in py_to_pairs.most_common():
            reasons = Counter(r["end_reason"] for r in py_to if (r["a"], r["b"]) == (a, b))
            w(f"- `{a}` vs `{b}` — {n}/5 ({', '.join(f'{k} {v}' for k, v in sorted(reasons.items()))})")
        w("")
    else:
        w("No Python fight ended unresolved.")
        w("")
    if py_kite_pairs:
        w("**Python pairs decided by `kite_win`** (fights out of 5):")
        w("")
        for (a, b), n in py_kite_pairs.most_common():
            w(f"- `{a}` vs `{b}` — {n}/5")
        w("")

    (HERE / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote REPORT.md — {agreed}/{n_pairs} pairs agree "
          f"({fmt(100 * agreed / n_pairs, 1)}%), mean |d surv| {fmt(statistics.mean(d_surv))}, "
          f"mean |d HP%| {fmt(100 * statistics.mean(d_hp), 1)} pp, "
          f"mean t_js/t_py {fmt(statistics.mean(t_ratio))}")


if __name__ == "__main__":
    main()
