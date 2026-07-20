"""Tests for SR.pick_filmed — the diversity rule for which fights get FILMED
(distinct from pick_showcase, which still drives the ranked-list cards).

Per category (up to per_cat=3): #1 = cost-extreme row (most expensive for
win/coin-flip categories, cheapest for loss categories — see SR._cost_key);
#2 = next row by the same cost ordering; #3 = if #1/#2 share a broad `class`,
the cost-extreme row of a DIFFERENT class (else just the next row by cost).
Categories with fewer than per_cat rows film everything they have.
"""
from aoe2x.analysis.story_rules_v2 import pick_filmed


def R(cat, cost, civ, slug, cls):
    """Minimal row as produced by build_v2_categorization.py."""
    return {"category": cat, "cost": cost, "civ": civ, "slug": slug, "class": cls}


def test_same_class_top_two_forces_diverse_third():
    # expected_win: cost-extreme = most expensive first. Top two both cavalry;
    # a cheaper infantry row exists further down and should be forced into #3
    # instead of the next (also-cavalry) row by cost.
    rows = [
        R("expected_win", 100, "A", "cav1", "cavalry"),
        R("expected_win", 90, "B", "cav2", "cavalry"),
        R("expected_win", 80, "C", "cav3", "cavalry"),
        R("expected_win", 70, "D", "inf1", "infantry"),
    ]
    out = pick_filmed(rows)
    picked = [(r["civ"], r["slug"]) for r in out["expected_win"]]
    assert picked == [("A", "cav1"), ("B", "cav2"), ("D", "inf1")]


def test_already_diverse_top_two_keeps_pure_cost_order():
    # Top two are already different classes -> #3 is just the next row by cost,
    # no diversity search needed.
    rows = [
        R("expected_win", 100, "A", "cav1", "cavalry"),
        R("expected_win", 90, "B", "rng1", "ranged"),
        R("expected_win", 80, "C", "inf1", "infantry"),
        R("expected_win", 70, "D", "cav2", "cavalry"),
    ]
    out = pick_filmed(rows)
    picked = [(r["civ"], r["slug"]) for r in out["expected_win"]]
    assert picked == [("A", "cav1"), ("B", "rng1"), ("C", "inf1")]


def test_same_class_top_two_no_other_class_falls_back_to_next_by_cost():
    # Every row is the same class -> no diverse candidate exists, so #3 falls
    # back to the plain next-by-cost row.
    rows = [
        R("expected_loss", 10, "A", "u1", "infantry"),
        R("expected_loss", 20, "B", "u2", "infantry"),
        R("expected_loss", 30, "C", "u3", "infantry"),
        R("expected_loss", 40, "D", "u4", "infantry"),
    ]
    out = pick_filmed(rows)
    picked = [(r["civ"], r["slug"]) for r in out["expected_loss"]]
    assert picked == [("A", "u1"), ("B", "u2"), ("C", "u3")]


def test_loss_category_uses_cheapest_first():
    rows = [
        R("expected_loss", 50, "A", "u1", "cavalry"),
        R("expected_loss", 10, "B", "u2", "cavalry"),
        R("expected_loss", 30, "C", "u3", "infantry"),
        R("expected_loss", 20, "D", "u4", "cavalry"),
    ]
    out = pick_filmed(rows)
    picked = [(r["civ"], r["slug"]) for r in out["expected_loss"]]
    # cheapest first: B(10), D(20) both cavalry -> #3 forced diverse: C(30) infantry
    assert picked == [("B", "u2"), ("D", "u4"), ("C", "u3")]


def test_fewer_than_per_cat_rows_films_all():
    rows = [
        R("unexpected_loss", 40, "A", "u1", "cavalry"),
        R("unexpected_loss", 20, "B", "u2", "infantry"),
    ]
    out = pick_filmed(rows)
    picked = [(r["civ"], r["slug"]) for r in out["unexpected_loss"]]
    assert picked == [("B", "u2"), ("A", "u1")]


def test_coin_flip_never_filmed():
    rows = [R("coin_flip", 50, "A", "u1", "cavalry")]
    out = pick_filmed(rows)
    assert out["coin_flip"] == []


def test_exclude_respected():
    rows = [
        R("expected_win", 100, "A", "cav1", "cavalry"),
        R("expected_win", 90, "B", "cav2", "cavalry"),
        R("expected_win", 80, "C", "inf1", "infantry"),
        R("expected_win", 70, "D", "cav3", "cavalry"),
    ]
    out = pick_filmed(rows, exclude=[("A", "cav1")])
    picked = [(r["civ"], r["slug"]) for r in out["expected_win"]]
    # A excluded -> top two are B, C (already different classes) -> #3 next by cost
    assert picked == [("B", "cav2"), ("C", "inf1"), ("D", "cav3")]


def test_per_cat_override():
    rows = [
        R("expected_win", 100, "A", "u1", "cavalry"),
        R("expected_win", 90, "B", "u2", "cavalry"),
        R("expected_win", 80, "C", "u3", "cavalry"),
    ]
    out = pick_filmed(rows, per_cat=2)
    picked = [(r["civ"], r["slug"]) for r in out["expected_win"]]
    assert picked == [("A", "u1"), ("B", "u2")]
