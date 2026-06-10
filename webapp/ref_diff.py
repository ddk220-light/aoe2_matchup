"""Role: patch-tooling — diff two aoe2_reference.db snapshots (prev vs new) at ref_units granularity.

Returns (deltas, changed_slugs):
  deltas        list of {civ_name, unit_slug, field, old_value, new_value}
  changed_slugs set of unit_slug whose stats changed for ANY civ (feeds the
                run_matchup_battles --changed-units incremental re-sim).
"""
import sqlite3

# Numeric ref_units columns whose change is a real game/balance change worth
# recording. base_* = raw .dat change; final_* would also catch tech/bonus
# shifts but we report base_* for clean "the game changed X" attribution.
DIFF_FIELDS = [
    "base_hp", "base_attack", "base_melee_armor", "base_pierce_armor",
    "base_range", "base_reload_time", "base_speed",
    "base_cost_food", "base_cost_wood", "base_cost_gold", "base_train_time",
]


def _load(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ref_units)")}
    fields = [f for f in DIFF_FIELDS if f in cols]
    rows = conn.execute(
        f"SELECT civ_name, unit_slug, age, {', '.join(fields)} FROM ref_units"
    ).fetchall()
    conn.close()
    out = {}
    for r in rows:
        out[(r["civ_name"], r["unit_slug"], r["age"])] = dict(r)
    return out, fields


def diff(prev_path, new_path):
    prev, pfields = _load(prev_path)
    new, nfields = _load(new_path)
    fields = [f for f in DIFF_FIELDS if f in pfields and f in nfields]
    deltas = []
    changed_slugs = set()
    for key, nrow in new.items():
        prow = prev.get(key)
        if prow is None:
            continue  # new unit/availability handled via notes, not stat diff
        civ, slug, _age = key
        for f in fields:
            ov, nv = prow.get(f), nrow.get(f)
            if ov is None and nv is None:
                continue
            if ov != nv:
                deltas.append({"civ_name": civ, "unit_slug": slug, "field": f,
                               "old_value": ov, "new_value": nv})
                changed_slugs.add(slug)
    # de-dup standard-unit deltas that repeat identically across civs is left to
    # the caller's display layer; changed_slugs is already a set.
    return deltas, changed_slugs
