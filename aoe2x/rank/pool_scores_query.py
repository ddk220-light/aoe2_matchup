"""Role: serving — query helper for pool_scores.db.

Loads structured per-unit payloads keyed by (civ_name, unit_slug).
Used by the /api/ref/unit-line endpoint to attach pool-scores data
to each unit row in the rankings view.
"""
import json
import os
import sqlite3

from aoe2x.paths import WEBAPP_DIR as _DATA_DIR

DEFAULT_DB_PATH = os.path.join(str(_DATA_DIR), "pool_scores.db")

_SHAPE_KEYS = ("n", "mean", "stddev", "win_rate", "decisive_win_rate",
               "big_win_rate", "catastrophic_loss_rate")
_ROLE_KEYS = ("gc", "ac", "at", "aa")


def load_pool_scores(db_path: str,
                     civ_unit_pairs: list[tuple[str, str]],
                     build_number: str | None = None) -> dict:
    """Return {(civ_name, unit_slug): payload, ...} for known units.

    Each scale's per-axis dict gains a `role_line_means` key with the
    decoded JSON breakdown (`{}` when the DB column is NULL).

    Units not present in pool_scores.db are simply absent from the result.
    Empty input → empty dict. Missing DB file → empty dict.
    """
    if not civ_unit_pairs or not os.path.exists(db_path):
        return {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ", ".join("(?, ?)" for _ in civ_unit_pairs)
        params: list[str] = []
        for civ, slug in civ_unit_pairs:
            params.extend((civ, slug))
        sql = f"""
            SELECT civ_name, unit_slug, pool, scale, axis,
                   final_score, gc, ac, at, aa,
                   n, mean, stddev,
                   win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate,
                   role_line_means
            FROM pool_scores
            WHERE (civ_name, unit_slug) IN ({placeholders})
        """
        if build_number is not None:
            sql += " AND build_number = ?"
            params.append(build_number)
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    finally:
        conn.close()

    result: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["civ_name"], row["unit_slug"])
        unit_payload = result.setdefault(key, {
            "pool": row["pool"],
            "scales": {},
        })
        scale_payload = unit_payload["scales"].setdefault(row["scale"], {
            "hp": None, "cost": None, "speed": None, "shape": None,
        })
        rlm_raw = row["role_line_means"]
        rlm = json.loads(rlm_raw) if rlm_raw else {}
        scale_payload[row["axis"]] = {
            "final": row["final_score"],
            **{k: row[k] for k in _ROLE_KEYS},
            "role_line_means": rlm,
        }
        if scale_payload["shape"] is None:
            scale_payload["shape"] = {k: row[k] for k in _SHAPE_KEYS}

    return result
