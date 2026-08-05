"""Game-free helpers importable without the OCR/nav stack.

These have no dependency on auto.vision / auto.platform_io / auto.grpc_capture
(the OCR + window-focus + gRPC layer), so they can be imported on any box —
CI, a headless checkout, the website process — without a running game.

  * log()                    — timestamped stdout + optional logfile append.
  * resolve_side()           — (civ, slug) -> (civ, unit_key, display_label).
  * RES_BUDGET               — equal-resources weighted-cost ceiling.
  * equal_resource_counts()  — counts for an equal-RESOURCE fight.

They are re-exported from their old homes (orchestrate_matchup / record_until_end)
for back-compat, so existing imports keep working.
"""
from __future__ import annotations

from datetime import datetime


def log(msg, logfile=None):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    if logfile:
        with open(logfile, "a") as f:
            f.write(line + "\n")


def resolve_side(civ: str, slug: str):
    """(civ, slug) -> (civ, unit_key, display_label) for build_run.

    The scenario unit key is the slug minus its civ suffix (unique-unit slugs carry
    one, e.g. 'elite_temple_guard_muisca' -> 'elite_temple_guard'); the label is the
    unit's display name from the reference DB.

    A ref-DB slug is a LINE label, not the unit: `paladin` is the knight line, and for a
    civ without the Paladin upgrade the row holds that civ's real top unit — Chinese
    `paladin` has unit_name 'Cavalier', 140 HP. Deriving the scenario const from the slug
    would field a 180 HP Paladin while every stat, cost and sim expectation came from the
    Cavalier row. So when the DB's unit_name resolves to a DIFFERENT const than the slug
    does, the name wins. Slug-derived stays the default: it is what the 91-matchup batch
    ran on, and unique-unit names ('Ratha (melee)') resolve only through the slug's
    override table."""
    from overlay.overlay_data import get_unit_card
    suffix = "_" + civ.lower()
    key = slug[: -len(suffix)] if slug.endswith(suffix) else slug
    label = get_unit_card(civ, slug)["name"]
    name_key = label.lower().replace(" ", "_").replace("-", "_")
    if name_key != key:
        from build_run import unit_const
        try:
            if unit_const(name_key) != unit_const(key):
                key = name_key
        except Exception:
            pass                     # name doesn't map to a const — keep the slug's key
    return (civ, key, label)


RES_BUDGET = 3000.0   # the cheaper side's total WEIGHTED cost must stay <= this


def equal_resource_counts(civ1, slug1, civ2, slug2, unit_cap=30):
    """Counts for an equal-RESOURCE fight. Per-unit costs come from the unit card,
    which already folds in civ cost bonuses (e.g. Mayan -30% archers), train
    batches (Blackwood Archers come 2 per train), and the website's resource
    weights (food 1.0 / wood 1.0 / gold 1.5 — overlay_data.COST_WEIGHT_*). The
    cheaper unit takes `unit_cap`, shrunk so its army never exceeds RES_BUDGET;
    the pricier unit's count is the largest that fits the same spend.
    Returns (n1, n2)."""
    from overlay.overlay_data import get_unit_card
    c1 = get_unit_card(civ1, slug1)["cost"]["weighted"] or 1
    c2 = get_unit_card(civ2, slug2)["cost"]["weighted"] or 1
    if c1 <= c2:                                   # side 1 cheaper -> it gets the cap
        n1 = max(1, min(unit_cap, int(RES_BUDGET // c1)))
        return n1, max(1, int(n1 * c1 // c2))
    n2 = max(1, min(unit_cap, int(RES_BUDGET // c2)))
    return max(1, int(n2 * c2 // c1)), n2
