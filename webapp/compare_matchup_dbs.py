"""
Compare matchup_combos.db (fast sim) vs matchup_combos_real.db (real sim).

Looks at the same (civ, opponent) directional pairs in both DBs and reports:
- Top-unit changes (different unit recommended as #1 vs same)
- Partner/sidekick changes
- Distribution: top units that appear most often in each
- Per-civ summary: how many of this civ's matchups changed

Real DB may be partial (still running); we restrict to overlap pairs.
"""

import os
import sqlite3
from collections import Counter, defaultdict

OLD_DB = os.path.join(os.path.dirname(__file__), "matchup_combos.db")
NEW_DB = os.path.join(os.path.dirname(__file__), "matchup_combos_real.db")


def fetch_top_combos(db_path):
    """Return {(civ, opponent): {'top': slug, 'top_name': name,
    'partner': slug-or-None, 'is_perfect': bool, 'combo_type': str}}.
    Picks rank-1 combo per pair (the recommendation actually shown)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    out = {}
    rows = conn.execute("""
        SELECT civ, opponent, top_unit_slug, top_unit_name,
               partner_slug, partner_name, partner_type,
               combo_type, combo_rank, sidekick_rank, is_perfect
        FROM matchup_combos
        WHERE combo_rank = 1 AND (sidekick_rank = 1 OR sidekick_rank = 0)
        ORDER BY civ, opponent, sidekick_rank ASC
    """).fetchall()
    # First row per (civ, opponent) wins (sidekick_rank=0 only when there is
    # no sidekick; sidekick_rank=1 is the best sidekick — order ASC puts 0
    # first, but we want the actual displayed top: prefer sidekick_rank=1 if
    # present, else sidekick_rank=0). Just take the first row we see and let
    # subsequent rows for same key overwrite — that gives sidekick=1.
    for r in rows:
        key = (r["civ"], r["opponent"])
        out[key] = {
            "top": r["top_unit_slug"],
            "top_name": r["top_unit_name"],
            "partner": r["partner_slug"],
            "partner_name": r["partner_name"],
            "partner_type": r["partner_type"],
            "combo_type": r["combo_type"],
            "is_perfect": bool(r["is_perfect"]),
        }
    conn.close()
    return out


def main():
    print("Loading...")
    old = fetch_top_combos(OLD_DB)
    new = fetch_top_combos(NEW_DB)
    overlap = set(old) & set(new)
    print(f"Old DB pairs: {len(old)}")
    print(f"New DB pairs: {len(new)}  (real-sim, partial)")
    print(f"Overlap:      {len(overlap)}")
    print()

    # 1. Top-unit changes
    same_top = 0
    diff_top = 0
    diff_partner_same_top = 0
    same_top_perfect_changed = 0
    for k in overlap:
        o, n = old[k], new[k]
        if o["top"] == n["top"]:
            same_top += 1
            if o["partner"] != n["partner"]:
                diff_partner_same_top += 1
            if o["is_perfect"] != n["is_perfect"]:
                same_top_perfect_changed += 1
        else:
            diff_top += 1
    print(f"Top-unit recommendation:")
    print(f"  same:                          {same_top:>5} ({same_top*100//len(overlap)}%)")
    print(f"  different:                     {diff_top:>5} ({diff_top*100//len(overlap)}%)")
    print(f"  same top but different partner:{diff_partner_same_top:>5}")
    print(f"  same top but perfect-flag flipped: {same_top_perfect_changed}")
    print()

    # 2. Top-unit distribution shifts
    old_top_counter = Counter(old[k]["top_name"] for k in overlap)
    new_top_counter = Counter(new[k]["top_name"] for k in overlap)
    print("Top units (in overlap pairs):")
    print(f"  {'Unit':<35} {'Old':>6} {'New':>6} {'Delta':>6}")
    print(f"  {'-' * 35} {'-' * 6} {'-' * 6} {'-' * 6}")
    all_units = set(old_top_counter) | set(new_top_counter)
    rows = []
    for unit in all_units:
        o_cnt = old_top_counter.get(unit, 0)
        n_cnt = new_top_counter.get(unit, 0)
        rows.append((unit, o_cnt, n_cnt, n_cnt - o_cnt))
    rows.sort(key=lambda r: -abs(r[3]))
    for unit, o_cnt, n_cnt, delta in rows[:20]:
        sign = "+" if delta > 0 else ""
        print(f"  {unit:<35} {o_cnt:>6} {n_cnt:>6}  {sign}{delta:>5}")
    print()

    # 3. Per-civ summary: which civs changed most
    civ_changes = defaultdict(lambda: {"same": 0, "diff": 0})
    for k in overlap:
        civ, _ = k
        if old[k]["top"] == new[k]["top"]:
            civ_changes[civ]["same"] += 1
        else:
            civ_changes[civ]["diff"] += 1
    print("Per-civ change breakdown (top 20 by change %):")
    print(f"  {'Civ':<15} {'Same':>5} {'Diff':>5} {'%Change':>8}")
    civ_rows = []
    for civ, d in civ_changes.items():
        total = d["same"] + d["diff"]
        if total == 0:
            continue
        pct = d["diff"] * 100.0 / total
        civ_rows.append((civ, d["same"], d["diff"], pct))
    civ_rows.sort(key=lambda r: -r[3])
    for civ, s, d, p in civ_rows[:20]:
        print(f"  {civ:<15} {s:>5} {d:>5}  {p:>7.1f}%")
    print()

    # 4. A few sample diffs (interesting cases)
    print("Sample changed recommendations (random 10):")
    print(f"  {'Civ':<12} {'vs':<12} {'OLD top + partner':<55} {'->':<3} {'NEW top + partner':<55}")
    print(f"  {'-' * 12} {'-' * 12} {'-' * 55} --- {'-' * 55}")
    diff_keys = [k for k in overlap if old[k]["top"] != new[k]["top"]]
    diff_keys.sort()
    # take a spread sample
    sample = diff_keys[::max(1, len(diff_keys) // 20)][:20]
    for k in sample:
        civ, opp = k
        o, n = old[k], new[k]
        old_str = o["top_name"]
        if o["partner_name"]:
            old_str += f" + {o['partner_name']}"
        new_str = n["top_name"]
        if n["partner_name"]:
            new_str += f" + {n['partner_name']}"
        print(f"  {civ:<12} {opp:<12} {old_str:<55} --> {new_str:<55}")


if __name__ == "__main__":
    main()
