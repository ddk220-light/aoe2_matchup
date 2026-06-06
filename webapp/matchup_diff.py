"""Snapshot + diff matchup outcomes around a re-sim, and diff ranking snapshots.

row_score mirrors battle_outcome.signed_score but reads a DB row dict, so we can
compute the per-matchup signed score directly from matchup_battles columns.
"""
import sqlite3

_KEY = ("my_civ", "my_unit_slug", "opp_civ", "opp_unit_slug", "scale")


def row_score(row):
    w = row["winner"]
    if w == 0:
        return 0.0
    if w == 1:
        return round(100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"]), 4)
    return round(-100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"]), 4)


def _touches(row, changed_slugs):
    return row["my_unit_slug"] in changed_slugs or row["opp_unit_slug"] in changed_slugs


def snapshot(matchup_db_path, changed_slugs):
    """Capture {key: {winner, score}} for every matchup touching a changed slug."""
    conn = sqlite3.connect(matchup_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, winner, "
        "team1_hp_pct, team2_hp_pct FROM matchup_battles").fetchall()
    conn.close()
    out = {}
    for r in rows:
        if not _touches(r, changed_slugs):
            continue
        key = tuple(r[k] for k in _KEY)
        out[key] = {"winner": r["winner"], "score": row_score(r)}
    return out


def diff_outcomes(before_snapshot, after_db_path, changed_slugs, min_swing=1.0):
    """Compare a before-snapshot with the post-re-sim matchup DB.

    Returns a list of change dicts for matchups whose winner flipped OR whose
    score moved by >= min_swing."""
    conn = sqlite3.connect(after_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, winner, "
        "team1_hp_pct, team2_hp_pct FROM matchup_battles").fetchall()
    conn.close()
    changes = []
    for r in rows:
        if not _touches(r, changed_slugs):
            continue
        key = tuple(r[k] for k in _KEY)
        before = before_snapshot.get(key)
        if before is None:
            continue
        new_score = row_score(r)
        swing = round(new_score - before["score"], 4)
        if r["winner"] == before["winner"] and abs(swing) < min_swing:
            continue
        changes.append({
            "my_civ": r["my_civ"], "my_unit_slug": r["my_unit_slug"],
            "opp_civ": r["opp_civ"], "opp_unit_slug": r["opp_unit_slug"],
            "scale": r["scale"],
            "old_winner": before["winner"], "new_winner": r["winner"],
            "old_score": before["score"], "new_score": new_score, "swing": swing,
        })
    return changes


def diff_rankings(derived_db_path, old_build, new_build, changed_slugs):
    """Compare battle_scores between two builds for changed slugs.

    Returns list of {civ_name, unit_slug, score_type, old_score, new_score,
    old_rank, new_rank} for every (civ, slug, score_type) the unit has."""
    conn = sqlite3.connect(derived_db_path)
    conn.row_factory = sqlite3.Row

    def load(build):
        rows = conn.execute(
            "SELECT civ_name, unit_slug, score_type, score_value, rank "
            "FROM battle_scores WHERE build_number=?", (build,)).fetchall()
        return {(r["civ_name"], r["unit_slug"], r["score_type"]):
                (r["score_value"], r["rank"]) for r in rows}

    old = load(old_build)
    new = load(new_build)
    conn.close()
    out = []
    keys = set(old) | set(new)
    for (civ, slug, st) in keys:
        if slug not in changed_slugs:
            continue
        os_, or_ = old.get((civ, slug, st), (None, None))
        ns_, nr_ = new.get((civ, slug, st), (None, None))
        if (os_, or_) == (ns_, nr_):
            continue
        out.append({"civ_name": civ, "unit_slug": slug, "score_type": st,
                    "old_score": os_, "new_score": ns_,
                    "old_rank": or_, "new_rank": nr_})
    return out
