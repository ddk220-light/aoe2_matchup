# tests/test_infantry_scoring.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
from compute_battle_scores import MILITIA_ROLE_BENCHMARKS, INFANTRY_ROLE_SCORE_TYPES


def test_militia_benchmarks_imperial_has_new_ac_opponents():
    keys = [k for k, *_ in MILITIA_ROLE_BENCHMARKS["imperial"]]
    assert "ac_30v30_vs_battle_elephant" in keys
    assert "ac_30v30_vs_heavy_camel" in keys
    assert "ac_30v30_vs_steppe_lancer" in keys
    assert "ac_3k_vs_battle_elephant" in keys
    assert "ac_3k_vs_heavy_camel" in keys
    assert "ac_3k_vs_steppe_lancer" in keys


def test_militia_benchmarks_imperial_drops_old_ac_opponents():
    keys = [k for k, *_ in MILITIA_ROLE_BENCHMARKS["imperial"]]
    assert "ac_30v30_vs_elephant" not in keys
    assert "ac_30v30_vs_hussar" not in keys
    assert "ac_3k_vs_elephant" not in keys
    assert "ac_3k_vs_hussar" not in keys


def test_militia_benchmarks_imperial_has_anti_trash():
    keys = [k for k, *_ in MILITIA_ROLE_BENCHMARKS["imperial"]]
    assert "at_30v30_vs_halb" in keys
    assert "at_30v30_vs_hussar" in keys
    assert "at_30v30_vs_elite_skirm" in keys
    assert "at_3k_vs_halb" in keys
    assert "at_3k_vs_hussar" in keys
    assert "at_3k_vs_elite_skirm" in keys


def test_militia_benchmarks_castle_uses_castle_age_slugs():
    castle_bench = {k: (civ, slug) for k, civ, slug, *_ in MILITIA_ROLE_BENCHMARKS["castle"]}
    assert castle_bench.get("ac_30v30_vs_battle_elephant") == ("Khmer", "elephant")
    assert castle_bench.get("ac_30v30_vs_steppe_lancer") == ("Mongols", "steppe_lancer")
    assert castle_bench.get("ac_30v30_vs_heavy_camel") == ("Turks", "camel")
    assert castle_bench.get("at_30v30_vs_halb") == ("Spanish", "pikeman")
    assert castle_bench.get("at_30v30_vs_hussar") == ("Spanish", "light_cav")
    assert castle_bench.get("at_30v30_vs_elite_skirm") == ("Spanish", "elite_skirm")


def test_infantry_role_score_types_has_new_keys():
    new_keys = [
        "anti_trash",
        "ac_30v30_vs_battle_elephant", "ac_30v30_vs_heavy_camel", "ac_30v30_vs_steppe_lancer",
        "ac_3k_vs_battle_elephant",   "ac_3k_vs_heavy_camel",   "ac_3k_vs_steppe_lancer",
        "at_30v30_vs_halb", "at_30v30_vs_hussar", "at_30v30_vs_elite_skirm",
        "at_3k_vs_halb",   "at_3k_vs_hussar",   "at_3k_vs_elite_skirm",
    ]
    for key in new_keys:
        assert key in INFANTRY_ROLE_SCORE_TYPES, f"Missing: {key}"


def test_infantry_role_score_types_drops_old_keys():
    old_keys = [
        "ac_30v30_vs_elephant", "ac_30v30_vs_hussar",
        "ac_3k_vs_elephant",   "ac_3k_vs_hussar",
        "ac_30v30_vs_elephant_raw", "ac_30v30_vs_hussar_raw",
        "ac_3k_vs_elephant_raw",   "ac_3k_vs_hussar_raw",
    ]
    for key in old_keys:
        assert key not in INFANTRY_ROLE_SCORE_TYPES, f"Should be removed: {key}"


def test_militia_formula_weights():
    gc, ac, at_ = 80.0, 60.0, 40.0
    expected = round(0.75 * gc + 0.10 * ac + 0.15 * at_, 1)
    assert expected == 72.0
