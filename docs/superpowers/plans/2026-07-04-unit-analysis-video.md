# Unit Analysis Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-unique-unit "analysis video" pipeline: an analysis module that classifies every opponent into expected/unexpected wins/counters (+ even) and emits a storyboard JSON, plus the recorder-side refactors so the Windows box can turn a storyboard into one stitched video.

**Architecture:** Two decoupled phases joined by the storyboard JSON contract (spec: `docs/superpowers/specs/2026-07-04-unit-analysis-video-design.md`). Phase 1 (`aoe2x/analysis/`) runs anywhere; Phase 2 (`apps/video/`) refactors the recording pipeline (path fixes, manifest-driven queue runner, overlay slots, new cards) and adds the storyboard-consuming orchestrator. The validated reference implementation of all Phase-1 rules is `docs/superpowers/specs/2026-07-04-unit-analysis-video-prototype.py` — constants and behavior must match it.

**Tech Stack:** Python 3 (repo `.venv`), sqlite3, `aoe2x.sim.simulation_real` (position engine), pytest; Phase 2: existing ffmpeg/compose stack in `apps/video/overlay/`.

**Phase independence:** Phase 1 (Tasks 1–5) and Phase 2 (Tasks 6–12) are independently shippable. Phase 1 alone produces the storyboard + printed analysis. Run Phase-2 recording tasks on the Windows checkout.

---

## File structure

**Phase 1 — create:**
- `aoe2x/analysis/__init__.py` — empty package marker
- `aoe2x/analysis/story_rules.py` — pure classification rules (no I/O, no sim)
- `aoe2x/analysis/opponent_pool.py` — pool building from ref DB + unique_units.json
- `aoe2x/analysis/matchup_sources.py` — `LocalSimSource` / `MatchupDbSource`
- `aoe2x/analysis/captions.py` — "why" caption templating
- `aoe2x/analysis/unit_video_story.py` — CLI + storyboard assembly
- `tests/test_story_rules.py`, `tests/test_opponent_pool.py`, `tests/test_matchup_sources.py`, `tests/test_captions.py`, `tests/test_unit_video_story.py`

**Phase 2 — modify:**
- `apps/video/auto/config.py` — single source of repo-root paths
- `apps/video/overlay/overlay_data.py:23-25`, `apps/video/overlay/results.py:30-37`, `apps/video/auto/build_unique_list.py:28` — stale path fixes
- `tests/test_pure.py:283-294` — un-skip the path test
- `apps/video/auto/orchestrate_matchup.py:93-124` — move pure helpers out
- `apps/video/auto/run_guecha_sweep.py`, `apps/video/auto/batch_matchups.py` — become thin callers of the queue runner
- `apps/video/overlay/compose.py` — `extra_overlays` param + gif intro segment
- `apps/video/overlay/render_card.py` — 3 new cards

**Phase 2 — create:**
- `apps/video/auto/pure.py` — game-free helpers (resolve_side, equal_resource_counts, log)
- `apps/video/auto/queue_runner.py` — manifest-driven matchup queue
- `apps/video/auto/chapters.py` — chapter/label helpers (moved from batch_matchups)
- `apps/video/overlay/assets.py` — hi-res image / attack-gif resolver (placeholder-friendly)
- `apps/video/auto/run_unit_analysis_video.py` — storyboard consumer
- `apps/video/tests/test_queue_runner.py`, `apps/video/tests/test_chapters.py` (follow the existing `apps/video/tests/` layout)

---

# Phase 1 — Analysis module

### Task 1: `story_rules.py` — pure classification rules

**Files:**
- Create: `aoe2x/analysis/__init__.py`, `aoe2x/analysis/story_rules.py`
- Test: `tests/test_story_rules.py`

All constants and functions are ports from the prototype (`docs/superpowers/specs/2026-07-04-unit-analysis-video-prototype.py`) — same names, same values.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_story_rules.py
"""Classification rules for the unit-analysis-video storyboard.

Boundary values pinned by the Temple Guard calibration session
(docs/superpowers/specs/2026-07-04-unit-analysis-video-design.md).
"""
import pytest

from aoe2x.analysis.story_rules import (
    WIN_T, B_T, B_STRONG, E_T, OUTLIER_MARGIN, WEIGHTS,
    categorize, rps, bonus_gain, expectation_from_components,
    classify, prefer_uniques, dedupe_line,
)


def R(S, B, E=0.0, ranged=False, kited=False, is_unique=True, slug="x", gold=50):
    """Minimal result row as produced by unit_video_story."""
    return {"S": S, "E": E, "factors": {"bonus": B, "rps": 0.0, "cost": 0.0},
            "ranged": ranged, "kited": kited, "is_unique": is_unique,
            "slug": slug, "gold": gold}


def test_constants_match_calibration():
    assert (WIN_T, B_T, B_STRONG, E_T, OUTLIER_MARGIN) == (15.0, 0.2, 0.45, 0.15, 15.0)
    assert WEIGHTS == {"bonus": 0.5, "rps": 0.3, "cost": 0.2}


# --- categorize ---------------------------------------------------------
def test_categorize_thrown_weapon_infantry_is_archer():
    assert categorize("elite_gbeto_malians", "Infantry", True, 1.0) == "archer"

def test_categorize_slow_eagle_class_is_infantry():
    # Temple Guard: eagle armor class but 1.05 speed -> plays like infantry
    assert categorize("elite_temple_guard_muisca", "Infantry", False, 1.05) == "infantry"

def test_categorize_fast_eagle_stays_eagle():
    assert categorize("elite_eagle", "Infantry", False, 1.3) == "eagle"

def test_categorize_ranged_cavalry_is_cav_archer():
    assert categorize("elite_mangudai_mongols", "Cavalry", True, 1.4) == "cav_archer"

def test_categorize_gunpowder_keywords():
    assert categorize("elite_janissary_turks", "Infantry", True, 0.96) == "gunpowder"


# --- rps ----------------------------------------------------------------
def test_rps_antisymmetric():
    assert rps("spear", "cavalry") == -rps("cavalry", "spear")

def test_rps_same_category_zero():
    assert rps("infantry", "infantry") == 0.0


# --- bonus_gain ---------------------------------------------------------
def test_bonus_gain_applies_class_bonus_minus_bonus_armor():
    # attacker: 16 base, +8 vs class 8; defender has class 8 with 0 bonus armor,
    # 2 melee armor -> base_eff = 14, gain = 8/14
    g = bonus_gain('{"4": 16, "8": 8}', 16, '{"4": 2, "3": 0, "8": 0}', False)
    assert g == pytest.approx(8 / 14)

def test_bonus_gain_zero_when_no_matching_class():
    assert bonus_gain('{"4": 16, "8": 8}', 16, '{"4": 0, "3": 0}', False) == 0.0


# --- classify: every row lands in exactly one of five categories --------
def test_even_band():
    assert classify(R(S=14.9, B=0.9)) == "even"
    assert classify(R(S=-14.9, B=-0.9)) == "even"

def test_expected_win_by_bonus():
    assert classify(R(S=50, B=0.2)) == "expected_win"

def test_no_bonus_win_split_by_prior():
    assert classify(R(S=50, B=0.0, E=0.1)) == "expected_win"
    assert classify(R(S=50, B=0.0, E=-0.1)) == "unexpected_win"

def test_unexpected_win_their_bonus():
    assert classify(R(S=20, B=-0.2)) == "unexpected_win"

def test_expected_counter_dedicated_bonus():
    assert classify(R(S=-50, B=-0.45)) == "expected_counter"

def test_expected_counter_kited():
    assert classify(R(S=-50, B=0.6, ranged=True, kited=True)) == "expected_counter"

def test_expected_counter_bad_prior():
    assert classify(R(S=-50, B=0.0, E=-0.16)) == "expected_counter"

def test_unexpected_counter_melee_small_bonus():
    # obuch case: melee, incidental bonus, prior not clearly negative
    assert classify(R(S=-42, B=-0.32, E=-0.08)) == "unexpected_counter"

def test_ranged_no_bonus_loss_defaults_expected():
    assert classify(R(S=-50, B=0.0, ranged=True, kited=False)) == "expected_counter"


# --- prefer_uniques ------------------------------------------------------
def test_generic_needs_outlier_margin():
    items = [R(79.1, 0.4, is_unique=False, slug="heavy_camel"),
             R(60.4, 0.5, slug="shriv"),
             R(57.5, 0.6, slug="tiger"),
             R(51.3, 0.6, is_unique=False, slug="paladin"),
             R(48.0, 0.5, slug="kona")]
    picks = prefer_uniques(items)
    # camel beats shriv by 18.7 >= 15 -> stays; paladin (51.3 vs kona 48.0) doesn't
    assert [p["slug"] for p in picks] == ["heavy_camel", "shriv", "tiger"]

def test_all_generic_when_no_uniques_left():
    items = [R(50, 0.4, is_unique=False, slug="a"), R(40, 0.4, is_unique=False, slug="b")]
    assert len(prefer_uniques(items)) == 2


# --- dedupe_line ---------------------------------------------------------
def test_ratha_forms_collapse():
    items = [R(34, 0.6, slug="elite_ratha_(melee)_bengalis"),
             R(20, 0.5, slug="elite_ratha_(ranged)_bengalis")]
    assert len(dedupe_line(items)) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_story_rules.py -x -q`
Expected: `ModuleNotFoundError: No module named 'aoe2x.analysis'`

- [ ] **Step 3: Implement**

Create empty `aoe2x/analysis/__init__.py`, then:

```python
# aoe2x/analysis/story_rules.py
"""Pure classification rules for unit-analysis-video storyboards.

No I/O, no sim — operates on plain dicts. Reference implementation +
calibration history: docs/superpowers/specs/2026-07-04-unit-analysis-video-prototype.py
and the matching design doc. Constants are calibrated; change them only with
a re-run of the Temple Guard validation.
"""
import json
import math

WIN_T = 15.0          # |S| <= WIN_T  -> "even"
B_T = 0.2             # meaningful bonus threshold
B_STRONG = 0.45       # dedicated-counter bonus threshold
E_T = 0.15            # clearly-negative prior threshold
OUTLIER_MARGIN = 15.0 # generic staple must beat next unique by this much |S|
WEIGHTS = {"bonus": 0.5, "rps": 0.3, "cost": 0.2}

GUNPOWDER_KEYS = ("janissary", "conquistador", "organ_gun", "hand_cannoneer",
                  "hussite", "ribauldequin", "fire_thrower", "grenadier")

RPS = {
    "eagle": {"archer": .5, "skirm": .4, "cav_archer": .4, "siege": .6,
              "gunpowder": .4, "infantry": -.5, "spear": .2, "cavalry": -.3,
              "light_cav": .0, "camel": .0, "elephant": -.2},
    "infantry": {"spear": .4, "eagle": .5, "siege": .5, "elephant": .2,
                 "archer": -.4, "cav_archer": -.5, "cavalry": -.2,
                 "gunpowder": -.3, "skirm": .3},
    "spear": {"cavalry": .7, "light_cav": .6, "camel": .5, "elephant": .7,
              "archer": -.6, "skirm": -.5, "cav_archer": -.6,
              "gunpowder": -.5, "siege": .2},
    "archer": {"infantry": .4, "spear": .6, "elephant": .3, "siege": .2,
               "cavalry": -.4, "light_cav": -.3, "camel": -.3, "skirm": -.5},
    "skirm": {"archer": .5, "cav_archer": .4, "spear": .5,
              "cavalry": -.5, "light_cav": -.4, "gunpowder": .2},
    "cav_archer": {"infantry": .5, "spear": .6, "siege": .3, "elephant": .2,
                   "cavalry": -.2, "camel": -.2},
    "cavalry": {"archer": .4, "skirm": .5, "siege": .6, "gunpowder": .5,
                "cav_archer": .2, "light_cav": .3, "camel": -.5},
    "light_cav": {"siege": .6, "archer": .3, "skirm": .4, "gunpowder": .4,
                  "camel": -.4},
    "camel": {"elephant": .3, "cav_archer": .3, "infantry": -.3,
              "archer": -.3},
    "elephant": {"siege": .4, "gunpowder": .2},
    "siege": {"gunpowder": .2},
    "gunpowder": {},
}


def categorize(slug, unit_class_name, is_ranged, speed):
    s = slug.lower()
    if any(k in s for k in GUNPOWDER_KEYS):
        return "gunpowder"
    if "ballista_elephant" in s:
        return "siege"
    if "camel" in s:
        return "camel"
    if "elephant" in s:
        return "elephant"
    cat = None
    if any(k in s for k in ("eagle", "fire_lancer", "temple_guard")):
        cat = "eagle"
    elif any(k in s for k in ("halberdier", "pikeman", "spearman", "kamayuk")):
        cat = "spear"
    elif "skirm" in s or "genitour" in s:
        cat = "skirm"
    elif (s in ("hussar", "winged_hussar") or "huszar" in s
          or "shrivamsha" in s or s == "elite_steppe" or "steppe_lancer" in s):
        cat = "light_cav"
    if cat is None:
        uc = (unit_class_name or "").lower()
        if uc == "siege" or s in ("siege_onager", "heavy_scorpion",
                                  "mounted_trebuchet_khitans"):
            cat = "siege"
        elif "cavalry" in uc:
            cat = "cav_archer" if is_ranged else "cavalry"
        elif uc == "archer":
            cat = "archer"
        elif uc == "infantry" and is_ranged:
            cat = "archer"       # thrown-weapon infantry (gbeto, axeman, chakram)
        else:
            cat = "infantry"
    if cat == "eagle" and speed < 1.2:
        cat = "infantry"         # eagle-classed but infantry-speed (Temple Guard)
    return cat


def rps(a, b):
    if a == b:
        return 0.0
    if b in RPS.get(a, {}):
        return RPS[a][b]
    if a in RPS.get(b, {}):
        return -RPS[b][a]
    return 0.0


def bonus_gain(attacks_json, base_atk, opp_armors_json, attacker_ranged):
    """Relative extra damage from class bonuses vs this opponent."""
    atts = {int(k): v for k, v in json.loads(attacks_json or "{}").items()}
    arms = {int(k): v for k, v in json.loads(opp_armors_json or "{}").items()}
    base_armor = arms.get(3, 0) if attacker_ranged else arms.get(4, 0)
    base_eff = max((base_atk or 0) - base_armor, 1.0)
    gain = 0.0
    for cls, amt in atts.items():
        if cls in (3, 4):        # base melee / base pierce
            continue
        if cls in arms:
            eff = amt - arms[cls]
            if eff > 0:
                gain += eff
    return gain / base_eff


def expectation_from_components(B, R, C):
    E = WEIGHTS["bonus"] * B + WEIGHTS["rps"] * R + WEIGHTS["cost"] * C
    return max(-1.0, min(1.0, E))


def cost_component(subject_cost, opponent_cost):
    return max(-1.0, min(1.0,
        math.log(max(subject_cost, 1) / max(opponent_cost, 1)) / math.log(3)))


def bonus_component(gain_subject, gain_opponent):
    return math.tanh(gain_subject - gain_opponent)


def classify(r):
    """Assign a result row to exactly one of the five categories."""
    B = r["factors"]["bonus"]
    if abs(r["S"]) <= WIN_T:
        return "even"
    if r["S"] > WIN_T:
        if B >= B_T:
            return "expected_win"
        if B <= -B_T:
            return "unexpected_win"
        return "expected_win" if r["E"] >= 0 else "unexpected_win"
    if B <= -B_STRONG or r["kited"] or r["E"] < -E_T:
        return "expected_counter"
    if not r["ranged"]:
        return "unexpected_counter"
    return "expected_counter"


SORTS = {
    "expected_win":       lambda r: -r["S"],
    "unexpected_win":     lambda r: (r["factors"]["bonus"], r["S"]),
    "expected_counter":   lambda r: (r["S"], r["factors"]["bonus"]),
    "unexpected_counter": lambda r: -r["S"],
    "even":               lambda r: -r["S"],
}

# Top-3 pick eligibility (stricter than list membership; see design doc).
PICK_FILTERS = {
    "expected_win":       lambda r: r["factors"]["bonus"] >= B_T and r["gold"] > 0,
    "unexpected_win":     lambda r: r["factors"]["bonus"] <= -B_T,
    "expected_counter":   lambda r: True,
    "unexpected_counter": lambda r: True,
}


def dedupe_line(items):
    seen, out = set(), []
    for r in items:
        key = r["slug"].split("_(")[0]      # ratha melee/ranged collapse
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def prefer_uniques(items, margin=OUTLIER_MARGIN):
    """Top-3 favoring uniques; a generic takes a slot only when it outclasses
    the next unique by >= margin points of |S|."""
    picks, rest = [], list(items)
    while rest and len(picks) < 3:
        head = rest.pop(0)
        if head["is_unique"]:
            picks.append(head)
            continue
        next_uni = next((r for r in rest if r["is_unique"]), None)
        if next_uni is None or abs(head["S"]) - abs(next_uni["S"]) >= margin:
            picks.append(head)
    return picks
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_story_rules.py -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add aoe2x/analysis/__init__.py aoe2x/analysis/story_rules.py tests/test_story_rules.py
git commit -m "feat(analysis): pure classification rules for unit-analysis videos"
```

---

### Task 2: `opponent_pool.py` — pool building

**Files:**
- Create: `aoe2x/analysis/opponent_pool.py`
- Test: `tests/test_opponent_pool.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_opponent_pool.py
from aoe2x.analysis.opponent_pool import (
    build_pool, load_subject, STAPLES, NAVAL_KEYWORDS, PASSIVE_KEYWORDS,
)


def test_staples_have_no_heavy_scorpion():
    assert "heavy_scorpion" not in [s for s, _ in STAPLES]


def test_pool_for_temple_guard():
    pool = build_pool("Muisca", "elite_temple_guard_muisca")
    slugs = [o["slug"] for o in pool]
    assert "elite_temple_guard_muisca" not in slugs          # no mirror
    assert not any("turtle_ship" in s for s in slugs)        # no naval
    assert not any("flaming_camel" in s for s in slugs)      # no passive
    assert 70 <= len(pool) <= 85
    # staples present and canonical (not e.g. Cavalier under the paladin slug)
    pal = next(o for o in pool if o["slug"] == "paladin")
    assert pal["name"] == "Paladin"
    assert pal["is_unique"] is False
    # uniques flagged
    jag = next(o for o in pool if o["slug"] == "elite_jaguar_warrior_aztecs")
    assert jag["is_unique"] is True


def test_staple_civ_avoids_discounts():
    # modal stats+cost pick: Berbers' discounted hussar must not be chosen
    pool = build_pool("Muisca", "elite_temple_guard_muisca")
    hussar = next(o for o in pool if o["slug"] == "hussar")
    assert hussar["civ"] != "Berbers"


def test_subject_loads_with_stats():
    s = load_subject("Muisca", "elite_temple_guard_muisca")
    assert s["combat"]["hp"] > 0 and s["cost"] > 0 and s["cat"] == "infantry"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_opponent_pool.py -x -q`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# aoe2x/analysis/opponent_pool.py
"""Build the opponent pool: validated unique units + generic land staples.

Uniques come from apps/video/auto/unique_units.json (the validated list the
video sweep uses). Staples are line-imperial slugs pinned to a canonical
top-upgrade name, with the civ picked as the modal stats+cost variant so civ
discounts/bonuses don't skew equal-resource fights.
"""
import json
import sqlite3
from collections import Counter

from aoe2x.paths import GOLDEN_DIR, REPO_ROOT
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
from aoe2x.sim.simulation import prepare_combat_unit
from aoe2x.analysis.story_rules import categorize

REF_DB = GOLDEN_DIR / "aoe2_reference.db"
UNIQUE_UNITS_JSON = REPO_ROOT / "apps" / "video" / "auto" / "unique_units.json"

STAPLES = [
    ("champion", "Champion"), ("halberdier", "Halberdier"),
    ("arbalester", "Arbalester"), ("imp_elite_skirm", "Elite Skirmisher"),
    ("heavy_cav_archer", "Heavy Cavalry Archer"), ("paladin", "Paladin"),
    ("hussar", "Hussar"), ("heavy_camel", "Heavy Camel Rider"),
    ("elite_steppe", "Elite Steppe Lancer"),
    ("elite_elephant", "Elite Battle Elephant"),
    ("siege_onager", "Siege Onager"),
    ("hand_cannoneer", "Hand Cannoneer"), ("elite_eagle", "Elite Eagle Warrior"),
]

NAVAL_KEYWORDS = ("turtle_ship", "caravel", "longboat", "thirisadai",
                  "lou_chuan", "dromon", "galley", "cannon_galleon")
PASSIVE_KEYWORDS = ("siege_ram", "battering_ram", "trebuchet", "petard",
                    "flaming_camel", "armored_elephant", "siege_elephant")

_SIG_COLS = ("final_hp", "final_attack", "final_melee_armor",
             "final_pierce_armor", "final_speed", "final_attacks_json",
             "final_armors_json", "final_cost_food", "final_cost_wood",
             "final_cost_gold")


def _connect():
    db = sqlite3.connect(str(REF_DB))
    db.row_factory = sqlite3.Row
    return db


def _get_row(db, civ, slug):
    return db.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ, slug)).fetchone()


def _pack(row, is_unique):
    speed = row["final_speed"] or 1.0
    return {
        "civ": row["civ_name"], "slug": row["unit_slug"], "name": row["unit_name"],
        "atk": row["final_attack"], "attacks": row["final_attacks_json"],
        "armors": row["final_armors_json"],
        "cost": ((row["final_cost_food"] or 0) + (row["final_cost_wood"] or 0)
                 + (row["final_cost_gold"] or 0)),
        "gold": row["final_cost_gold"] or 0,
        "ranged": bool(row["is_ranged"]), "speed": speed,
        "is_unique": is_unique,
        "cat": categorize(row["unit_slug"], row["unit_class_name"],
                          bool(row["is_ranged"]), speed),
        "combat": prepare_combat_unit(build_combat_dict_from_ref(row)),
    }


def modal_civ(db, slug, canonical_name):
    rows = db.execute(
        f"SELECT civ_name, {', '.join(_SIG_COLS)} FROM ref_units"
        " WHERE unit_slug=? AND age='Imperial' AND unit_name=?",
        (slug, canonical_name)).fetchall()
    if not rows:
        return None
    sig, by_sig = Counter(), {}
    for r in rows:
        key = tuple(r[c] for c in _SIG_COLS)
        sig[key] += 1
        by_sig.setdefault(key, r["civ_name"])
    return by_sig[sig.most_common(1)[0][0]]


def load_subject(civ, slug):
    db = _connect()
    row = _get_row(db, civ, slug)
    if row is None:
        raise SystemExit(f"no Imperial ref row for {civ}/{slug}")
    return _pack(row, is_unique=True)


def build_pool(subject_civ, subject_slug):
    db = _connect()
    pool = []
    for u in json.loads(UNIQUE_UNITS_JSON.read_text()):
        if u["slug"] == subject_slug:
            continue
        if any(k in u["slug"] for k in NAVAL_KEYWORDS + PASSIVE_KEYWORDS):
            continue
        row = _get_row(db, u["civ"], u["slug"])
        if row is None:
            continue                       # dat-build drift; skip loudly upstream
        pool.append(_pack(row, is_unique=True))
    for slug, canonical in STAPLES:
        civ = modal_civ(db, slug, canonical)
        if civ is None:
            raise SystemExit(f"staple {slug} ({canonical}) not found in ref DB")
        pool.append(_pack(_get_row(db, civ, slug), is_unique=False))
    return pool
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_opponent_pool.py -q`
Expected: all pass. If `test_staple_civ_avoids_discounts` fails because the modal pick IS Berbers, inspect with
`sqlite3 data/golden/aoe2_reference.db "SELECT civ_name, final_cost_food, final_cost_gold FROM ref_units WHERE unit_slug='hussar' AND unit_name='Hussar'"` — cost columns must be in the signature (they are in `_SIG_COLS`); a genuine failure means the discount shows in costs and the test assumption holds.

- [ ] **Step 5: Commit**

```bash
git add aoe2x/analysis/opponent_pool.py tests/test_opponent_pool.py
git commit -m "feat(analysis): opponent pool builder (uniques + canonical staples)"
```

---

### Task 3: `matchup_sources.py` — S measurement backends

**Files:**
- Create: `aoe2x/analysis/matchup_sources.py`
- Test: `tests/test_matchup_sources.py` (uses `tests/fixtures/berserker_matchups.db`)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_matchup_sources.py
import os
import sqlite3
import pytest

from aoe2x.analysis.matchup_sources import MatchupDbSource, LocalSimSource

FIXTURE = "tests/fixtures/berserker_matchups.db"


def _any_fixture_pair():
    db = sqlite3.connect(FIXTURE)
    row = db.execute(
        "SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, "
        "team1_hp_pct, team2_hp_pct FROM matchup_battles WHERE scale='3k' LIMIT 1"
    ).fetchone()
    db.close()
    return row


def test_db_source_returns_margin_from_3k_scale():
    my_civ, my_slug, opp_civ, opp_slug, hp1, hp2 = _any_fixture_pair()
    src = MatchupDbSource(FIXTURE)
    s = src.score({"civ": my_civ, "slug": my_slug},
                  {"civ": opp_civ, "slug": opp_slug})
    assert s == pytest.approx((hp1 - hp2) * 100, abs=1e-6)


def test_db_source_missing_pair_raises_keyerror():
    src = MatchupDbSource(FIXTURE)
    with pytest.raises(KeyError):
        src.score({"civ": "Muisca", "slug": "no_such_unit"},
                  {"civ": "Aztecs", "slug": "also_missing"})


@pytest.mark.skipif(not os.environ.get("RUN_SLOW"),
                    reason="position-engine sim, ~1 min; RUN_SLOW=1 to enable")
def test_local_sim_source_smoke():
    from aoe2x.analysis.opponent_pool import load_subject, build_pool
    subj = load_subject("Muisca", "elite_temple_guard_muisca")
    halb = next(o for o in build_pool("Muisca", "elite_temple_guard_muisca")
                if o["slug"] == "halberdier")
    s = LocalSimSource(seeds=(1, 2)).score(subj, halb)
    assert s > 15   # calibration run: ETG beats halbs decisively
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_matchup_sources.py -x -q`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# aoe2x/analysis/matchup_sources.py
"""S-measurement backends: the Windows matchup baseline DB, or fresh local
position-engine sims. Both return the same margin: S in [-100, 100] =
(subject_hp_frac - opponent_hp_frac) * 100 at equal resources (3k budget).
"""
import sqlite3
import statistics

BUDGET = 3000


class MatchupDbSource:
    """Reads matchup_battles rows (scale='3k') from a baseline DB
    (schema: aoe2x/batch/matchup_db.py)."""

    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)

    def score(self, subject, opponent):
        row = self.db.execute(
            "SELECT team1_hp_pct, team2_hp_pct FROM matchup_battles"
            " WHERE my_civ=? AND my_unit_slug=? AND opp_civ=? AND opp_unit_slug=?"
            " AND scale='3k'",
            (subject["civ"], subject["slug"], opponent["civ"], opponent["slug"]),
        ).fetchone()
        if row is None:
            raise KeyError(
                f"no 3k row for {subject['civ']}/{subject['slug']} vs "
                f"{opponent['civ']}/{opponent['slug']}")
        return (row[0] - row[1]) * 100.0


class LocalSimSource:
    """Fresh simulation_real battles, mean margin over seeds."""

    def __init__(self, seeds=(1, 2, 3, 4, 5, 6, 7, 8), budget=BUDGET):
        self.seeds = seeds
        self.budget = budget

    def score(self, subject, opponent):
        from aoe2x.sim.simulation_real import simulate_real_battle
        margins = []
        for seed in self.seeds:
            _, _, _, hp1, hp2 = simulate_real_battle(
                subject["combat"], opponent["combat"], self.budget,
                seed=seed, _legacy_tuple=True, return_hp=True)
            margins.append((hp1 - hp2) * 100.0)
        return statistics.fmean(margins)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_matchup_sources.py -q`
Expected: 2 pass, 1 skipped. Then once: `RUN_SLOW=1 .venv/bin/pytest tests/test_matchup_sources.py -q` → 3 pass.

- [ ] **Step 5: Commit**

```bash
git add aoe2x/analysis/matchup_sources.py tests/test_matchup_sources.py
git commit -m "feat(analysis): matchup-db and local-sim score backends"
```

---

### Task 4: `captions.py` — "why" captions

**Files:**
- Create: `aoe2x/analysis/captions.py`
- Test: `tests/test_captions.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_captions.py
from aoe2x.analysis.captions import why_caption, hidden_mechanics


def _r(cat, B=0.0, S=50.0, kited=False):
    return {"category": cat, "S": S, "kited": kited,
            "factors": {"bonus": B, "rps": 0.0, "cost": 0.0}}


def test_expected_win_cites_bonus():
    c = why_caption(_r("expected_win", B=0.55), subject_name="Elite Temple Guard",
                    opp_name="Elite Steppe Lancer",
                    subject_bonus_vs_opp=[("Cavalry", 8)], opp_bonus_vs_subject=[],
                    mechanics=[])
    assert "+8 vs Cavalry" in c


def test_unexpected_win_cites_survived_bonus():
    c = why_caption(_r("unexpected_win", B=-0.76, S=28.1),
                    subject_name="Elite Temple Guard",
                    opp_name="Elite White Feather Guard",
                    subject_bonus_vs_opp=[],
                    opp_bonus_vs_subject=[("Infantry", 8)], mechanics=[])
    assert "+8 vs Infantry" in c and "wins" in c.lower()


def test_expected_counter_kited():
    c = why_caption(_r("expected_counter", B=0.0, S=-100, kited=True),
                    subject_name="Elite Temple Guard", opp_name="Elite Chu Ko Nu",
                    subject_bonus_vs_opp=[], opp_bonus_vs_subject=[], mechanics=[])
    assert "kite" in c.lower() or "range" in c.lower()


def test_unexpected_counter_cites_mechanic():
    c = why_caption(_r("unexpected_counter", B=-0.32, S=-42),
                    subject_name="Elite Temple Guard", opp_name="Elite Obuch",
                    subject_bonus_vs_opp=[], opp_bonus_vs_subject=[],
                    mechanics=["strips 1 armor per hit"])
    assert "strips 1 armor per hit" in c


def test_hidden_mechanics_reads_ability_columns():
    row = {"armor_strip_per_hit": 1, "charge_attack_melee": 0,
           "charge_recharge_time": 0, "bleed_dps": 0, "bleed_duration": 0,
           "trample_percent": 0, "splash_on_hit_radius": 0,
           "attack_bonus_per_kill": 0, "dodge_shield_max": 0}
    assert hidden_mechanics(row) == ["strips 1 armor per hit"]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_captions.py -x -q` → `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# aoe2x/analysis/captions.py
"""Template 'why' captions from classification factors + real stat values."""


def _fmt_bonuses(pairs):
    return ", ".join(f"+{int(amt)} vs {cls}" for cls, amt in pairs)


def hidden_mechanics(row):
    """Human phrases for ability columns that explain no-bonus upsets.
    `row` is a dict-like ref_units row (sqlite3.Row works)."""
    out = []
    if row["armor_strip_per_hit"]:
        out.append(f"strips {int(row['armor_strip_per_hit'])} armor per hit")
    if row["charge_attack_melee"]:
        out.append(f"+{int(row['charge_attack_melee'])} charged attack"
                   f" every {int(row['charge_recharge_time'])}s")
    if row["bleed_dps"]:
        out.append(f"bleed {int(row['bleed_dps'])} dps for"
                   f" {int(row['bleed_duration'])}s (ignores armor)")
    if row["trample_percent"]:
        out.append(f"trample splash ({int(row['trample_percent'])}%)")
    if row["splash_on_hit_radius"]:
        out.append("splash damage on hit")
    if row["attack_bonus_per_kill"]:
        out.append(f"+{int(row['attack_bonus_per_kill'])} attack per kill")
    if row["dodge_shield_max"]:
        out.append(f"dodges first {int(row['dodge_shield_max'])} hits")
    return out


def why_caption(r, *, subject_name, opp_name, subject_bonus_vs_opp,
                opp_bonus_vs_subject, mechanics):
    cat = r["category"]
    if cat == "expected_win":
        if subject_bonus_vs_opp:
            return (f"{subject_name}'s {_fmt_bonuses(subject_bonus_vs_opp)} "
                    f"applies — {opp_name} melts.")
        return f"No counter relationship — {subject_name} simply out-stats it."
    if cat == "unexpected_win":
        if opp_bonus_vs_subject:
            return (f"{opp_name} lands {_fmt_bonuses(opp_bonus_vs_subject)} all "
                    f"fight — {subject_name} tanks it and wins with "
                    f"{max(int(r['S']), 0)}% of the army left.")
        return f"The prior said no — {subject_name} wins anyway."
    if cat == "expected_counter":
        if r["kited"]:
            return (f"{opp_name} kites — {subject_name} never gets to swing. "
                    f"Range beats slow melee, no bonus needed.")
        if opp_bonus_vs_subject:
            return (f"The textbook answer: {opp_name}'s "
                    f"{_fmt_bonuses(opp_bonus_vs_subject)} shreds {subject_name}.")
        return f"{opp_name} is simply the wrong fight to take."
    # unexpected_counter
    if mechanics:
        return (f"No meaningful bonus either way — but {opp_name} "
                f"{mechanics[0]}, and the 'safe' brawl falls apart.")
    return (f"A straight melee fight {subject_name} should survive — "
            f"{opp_name} wins it on raw output.")
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_captions.py -q` → all pass

- [ ] **Step 5: Commit**

```bash
git add aoe2x/analysis/captions.py tests/test_captions.py
git commit -m "feat(analysis): templated why-captions incl. hidden-mechanic detection"
```

---

### Task 5: `unit_video_story.py` — CLI + storyboard assembly + golden test

**Files:**
- Create: `aoe2x/analysis/unit_video_story.py`
- Test: `tests/test_unit_video_story.py`

- [ ] **Step 1: Write failing tests** (storyboard assembly from a frozen score table — no sims; pins the Temple Guard calibration)

```python
# tests/test_unit_video_story.py
import json

from aoe2x.analysis.unit_video_story import build_storyboard


class FrozenSource:
    """Score backend returning canned margins keyed by opponent slug."""
    def __init__(self, table):
        self.table = table

    def score(self, subject, opponent):
        return self.table[opponent["slug"]]


def test_storyboard_structure_and_temple_guard_picks():
    # Frozen from the calibration run (abstract engine, 2026-07-04): the
    # rules must keep producing these 12 given these margins.
    subject_civ, subject_slug = "Muisca", "elite_temple_guard_muisca"
    scores = json.loads(open("tests/fixtures/etg_frozen_scores.json").read())
    sb = build_storyboard(subject_civ, subject_slug, FrozenSource(scores))

    assert sb["schema_version"] == 1
    assert len(sb["segments"]) == 12
    cats = [s["category"] for s in sb["segments"]]
    assert cats == (["expected_win"] * 3 + ["unexpected_win"] * 3
                    + ["expected_counter"] * 3 + ["unexpected_counter"] * 3)

    def picks(cat):
        return [s["opponent"]["slug"] for s in sb["segments"]
                if s["category"] == cat]

    assert picks("expected_win") == [
        "heavy_camel", "elite_shrivamsha_rider_gurjaras",
        "elite_tiger_cavalry_wei"]
    assert picks("unexpected_win") == [
        "elite_white_feather_guard_shu", "elite_huskarl_goths",
        "elite_ghulam_hindustanis"]
    assert picks("expected_counter") == [
        "elite_chakram_thrower_gurjaras", "grenadier_jurchens",
        "elite_chu_ko_nu_chinese"]
    assert picks("unexpected_counter") == [
        "elite_urumi_swordsman_dravidians", "elite_obuch_poles",
        "elite_liao_dao_khitans"]

    # exhaustive: every pool unit appears in exactly one category list
    listed = [u["slug"] for lst in sb["category_lists"].values() for u in lst]
    assert sorted(listed) == sorted(scores.keys())
    assert set(sb["category_lists"].keys()) == {
        "expected_win", "unexpected_win", "expected_counter",
        "unexpected_counter", "even"}
    # counts precomputed for the recorder
    assert all(s["counts"]["subject"] > 0 for s in sb["segments"])
```

- [ ] **Step 2: Generate the frozen-scores fixture**

Run the committed prototype and capture its full table as `{slug: S}`:

```bash
.venv/bin/python - <<'EOF'
import importlib.util, json, sys, io, contextlib
spec = importlib.util.spec_from_file_location(
    "proto", "docs/superpowers/specs/2026-07-04-unit-analysis-video-prototype.py")
proto = importlib.util.module_from_spec(spec)
# The prototype's main() prints; we want its internals. Reuse its data path:
spec.loader.exec_module(proto)   # module-level code only defines things
subj_row = proto.get_row("Muisca", "elite_temple_guard_muisca")
subj = proto.pack(subj_row, is_unique=True)
table = {}
uniques = json.load(open("apps/video/auto/unique_units.json"))
for u in uniques:
    if u["slug"] == "elite_temple_guard_muisca":
        continue
    if any(k in u["slug"] for k in proto.NAVAL_KEYWORDS + proto.PASSIVE_KEYWORDS):
        continue
    row = proto.get_row(u["civ"], u["slug"])
    if row is None:
        continue
    opp = proto.pack(row, is_unique=True)
    _, _, _, hp1, hp2 = proto.simulate_battle(subj["combat"], opp["combat"],
                                              proto.BUDGET, return_hp=True)
    table[opp["slug"]] = round((hp1 - hp2) * 100.0, 1)
for slug, canonical in proto.STAPLES:
    civ = proto.modal_civ(slug, canonical)
    row = proto.get_row(civ, slug)
    opp = proto.pack(row, is_unique=False)
    _, _, _, hp1, hp2 = proto.simulate_battle(subj["combat"], opp["combat"],
                                              proto.BUDGET, return_hp=True)
    table[opp["slug"]] = round((hp1 - hp2) * 100.0, 1)
json.dump(table, open("tests/fixtures/etg_frozen_scores.json", "w"),
          indent=0, sort_keys=True)
print(len(table), "scores frozen")
EOF
```

Expected: `76 scores frozen`. **Note:** the abstract engine has run-to-run RNG (no seed pinned); the fixture freezes ONE observed table — that is its purpose (pin the rules, not the sims). Verify the frozen table still yields the 12 approved picks before committing: if a borderline pick differs (Urumi vs Serjeant ordering is the sensitive one), re-run the generation once; if it still differs, STOP and flag — do not hand-edit the fixture.

- [ ] **Step 3: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_unit_video_story.py -x -q`
Expected: `ModuleNotFoundError` (build_storyboard doesn't exist)

- [ ] **Step 4: Implement**

```python
# aoe2x/analysis/unit_video_story.py
"""Build a unit-analysis-video storyboard: classify every opponent, pick the
top-3 per category, emit storyboard JSON + printed summary.

CLI:
  python -m aoe2x.analysis.unit_video_story Muisca elite_temple_guard_muisca \
      --source local-sim --out storyboards/elite_temple_guard_muisca.json
  ... --source matchup-db --matchup-db D:/AI/matchup_baseline_170934.db
"""
import argparse
import datetime
import json
import sqlite3

from aoe2x.paths import GOLDEN_DIR
from aoe2x.analysis import story_rules as SR
from aoe2x.analysis.captions import why_caption, hidden_mechanics
from aoe2x.analysis.matchup_sources import (
    BUDGET, LocalSimSource, MatchupDbSource)
from aoe2x.analysis.opponent_pool import build_pool, load_subject

CATEGORY_ORDER = ("expected_win", "unexpected_win",
                  "expected_counter", "unexpected_counter")

_MECH_COLS = ("armor_strip_per_hit", "charge_attack_melee",
              "charge_recharge_time", "bleed_dps", "bleed_duration",
              "trample_percent", "splash_on_hit_radius",
              "attack_bonus_per_kill", "dodge_shield_max")


def _class_names(db):
    return dict(db.execute("SELECT id, name FROM armor_classes"))


def _bonus_pairs(att_json, opp_armors_json, names):
    atts = {int(k): v for k, v in json.loads(att_json or "{}").items()}
    arms = {int(k): v for k, v in json.loads(opp_armors_json or "{}").items()}
    return [(names.get(c, str(c)), a) for c, a in sorted(atts.items())
            if c not in (3, 4) and c in arms and a - arms[c] > 0]


def _evaluate(subject, opponent, source):
    S = source.score(subject, opponent)
    gs = SR.bonus_gain(subject["attacks"], subject["atk"],
                       opponent["armors"], subject["ranged"])
    go = SR.bonus_gain(opponent["attacks"], opponent["atk"],
                       subject["armors"], opponent["ranged"])
    B = SR.bonus_component(gs, go)
    Rv = SR.rps(subject["cat"], opponent["cat"])
    C = SR.cost_component(subject["cost"], opponent["cost"])
    kited = (opponent["ranged"] and not subject["ranged"]
             and opponent["speed"] - subject["speed"] > -0.15)
    r = {
        "civ": opponent["civ"], "slug": opponent["slug"],
        "name": opponent["name"], "cat": opponent["cat"],
        "gold": opponent["gold"], "is_unique": opponent["is_unique"],
        "ranged": opponent["ranged"], "kited": kited,
        "S": round(S, 1), "E": round(SR.expectation_from_components(B, Rv, C), 2),
        "factors": {"bonus": round(B, 2), "rps": round(Rv, 2),
                    "cost": round(C, 2)},
    }
    r["surprise"] = round(r["S"] / 100.0 - r["E"], 2)
    r["category"] = SR.classify(r)
    return r


def _counts(subject, opponent, budget=BUDGET):
    return {"subject": max(1, round(budget / max(subject["cost"], 1))),
            "opponent": max(1, round(budget / max(opponent["cost"], 1)))}


def build_storyboard(subject_civ, subject_slug, source, build="170934"):
    subject = load_subject(subject_civ, subject_slug)
    pool = build_pool(subject_civ, subject_slug)
    by_slug = {o["slug"]: o for o in pool}
    results = [_evaluate(subject, o, source) for o in pool]

    db = sqlite3.connect(str(GOLDEN_DIR / "aoe2_reference.db"))
    db.row_factory = sqlite3.Row
    names = _class_names(db)

    lists = {k: sorted([r for r in results if r["category"] == k],
                       key=SR.SORTS[k])
             for k in (*CATEGORY_ORDER, "even")}

    segments, order = [], 0
    for cat in CATEGORY_ORDER:
        candidates = SR.dedupe_line(
            [r for r in lists[cat] if SR.PICK_FILTERS[cat](r)])
        for rank, r in enumerate(SR.prefer_uniques(candidates), 1):
            r["picked"] = True
            order += 1
            opp = by_slug[r["slug"]]
            mech_row = db.execute(
                f"SELECT {', '.join(_MECH_COLS)} FROM ref_units"
                " WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
                (r["civ"], r["slug"])).fetchone()
            segments.append({
                "order": order, "category": cat, "rank": rank,
                "opponent": {"civ": r["civ"], "slug": r["slug"],
                             "name": r["name"]},
                "score": r["S"], "expectation": r["E"],
                "surprise": r["surprise"],
                "counts": _counts(subject, opp),
                "why": why_caption(
                    r, subject_name=subject["name"], opp_name=r["name"],
                    subject_bonus_vs_opp=_bonus_pairs(
                        subject["attacks"], opp["armors"], names),
                    opp_bonus_vs_subject=_bonus_pairs(
                        opp["attacks"], subject["armors"], names),
                    mechanics=hidden_mechanics(mech_row)),
                "why_factors": r["factors"],
            })

    return {
        "schema_version": 1,
        "build": build,
        "subject": {"civ": subject_civ, "slug": subject_slug,
                    "name": subject["name"],
                    "stats": {"cost": subject["cost"],
                              "speed": subject["speed"]}},
        "generated": {
            "source": type(source).__name__,
            "budget_res": BUDGET,
            "date": datetime.date.today().isoformat(),
            "params": {"WIN_T": SR.WIN_T, "B_T": SR.B_T,
                       "B_STRONG": SR.B_STRONG, "E_T": SR.E_T,
                       "OUTLIER_MARGIN": SR.OUTLIER_MARGIN,
                       "weights": SR.WEIGHTS},
        },
        "segments": segments,
        "category_lists": {
            cat: [{"rank": i, "name": r["name"], "civ": r["civ"],
                   "slug": r["slug"], "score": r["S"],
                   "picked": bool(r.get("picked"))}
                  for i, r in enumerate(items, 1)]
            for cat, items in lists.items()},
        "all_results": [{k: r[k] for k in
                         ("slug", "civ", "S", "E", "surprise", "category",
                          "factors")} for r in results],
    }


def print_summary(sb):
    print(f"\n=== {sb['subject']['name']} ({sb['subject']['civ']}) — "
          f"{len(sb['all_results'])} opponents ===")
    for seg in sb["segments"]:
        print(f"  {seg['order']:>2}. [{seg['category']}] #{seg['rank']} "
              f"{seg['opponent']['name']} ({seg['opponent']['civ']}) "
              f"S={seg['score']:+.1f}  — {seg['why']}")
    for cat, items in sb["category_lists"].items():
        print(f"\n### {cat} — {len(items)}")
        for u in items:
            mark = "*" if u["picked"] else " "
            print(f"  {mark}{u['rank']:>2}. {u['score']:>6}  "
                  f"{u['name']} ({u['civ']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("civ")
    ap.add_argument("slug")
    ap.add_argument("--source", choices=("local-sim", "matchup-db"),
                    default="local-sim")
    ap.add_argument("--matchup-db")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.source == "matchup-db":
        if not args.matchup_db:
            raise SystemExit("--matchup-db required with --source matchup-db")
        source = MatchupDbSource(args.matchup_db)
    else:
        source = LocalSimSource(seeds=tuple(range(1, args.seeds + 1)))

    sb = build_storyboard(args.civ, args.slug, source)
    print_summary(sb)
    if args.out:
        with open(args.out, "w") as f:
            json.dump(sb, f, indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_unit_video_story.py -q`
Expected: pass. If a pick differs from the approved 12, diff the frozen score against the classify() inputs before touching thresholds — thresholds are user-approved.

- [ ] **Step 6: End-to-end smoke on the real engine (once, ~10–20 min)**

```bash
mkdir -p storyboards
RUN_SLOW=1 .venv/bin/python -m aoe2x.analysis.unit_video_story \
    Muisca elite_temple_guard_muisca --source local-sim --seeds 2 \
    --out storyboards/elite_temple_guard_muisca.json
```

Expected: summary prints 12 segments + 5 lists; JSON written. The position engine's picks may differ from the abstract-engine fixture at the margins — that is data, not a bug; eyeball that the lists still tell the same story (archers/gunpowder counter, cavalry melts, melee-mechanics upsets). `storyboards/` output is a local artifact — do not commit it.

- [ ] **Step 7: Full suite + commit**

Run: `.venv/bin/pytest -q` — no regressions.

```bash
git add aoe2x/analysis/unit_video_story.py tests/test_unit_video_story.py tests/fixtures/etg_frozen_scores.json
git commit -m "feat(analysis): storyboard CLI with golden Temple Guard picks"
```

---

# Phase 2 — Video pipeline (run on the Windows checkout for recording; Tasks 6–9 are testable anywhere)

### Task 6: Fix stale repo-layout paths (BLOCKING for everything in apps/video)

**Files:**
- Modify: `apps/video/auto/config.py`, `apps/video/overlay/overlay_data.py:23-25`, `apps/video/overlay/results.py:30-37`, `apps/video/auto/build_unique_list.py:28`
- Test: `tests/test_pure.py:283-294` (existing, silently skipping today)

- [ ] **Step 1: Make the skipping test fail instead**

In `tests/test_pure.py` locate the test around line 283 that skips when the DB path is missing, and replace the skip with an assertion:

```python
def test_overlay_data_paths_exist():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path("apps/video")))
    from overlay import overlay_data
    assert Path(overlay_data.REF_DB).exists(), overlay_data.REF_DB
    assert Path(overlay_data.ICON_DIR).exists(), overlay_data.ICON_DIR
```

Run: `.venv/bin/pytest tests/test_pure.py::test_overlay_data_paths_exist -q`
Expected: FAIL (path points at `apps/data/golden/...`)

- [ ] **Step 2: Centralize roots in `auto/config.py`**

Add near the top of `apps/video/auto/config.py`:

```python
from pathlib import Path

# apps/video/auto/config.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "data" / "golden"
REF_DB = GOLDEN_DIR / "aoe2_reference.db"
UNITS_DB = GOLDEN_DIR / "aoe2_units.db"
ICON_DIR = REPO_ROOT / "apps" / "website" / "static" / "img" / "units"
```

- [ ] **Step 3: Point the three broken modules at it**

- `overlay/overlay_data.py:23-25`: delete the local `_REPO/REF_DB/ICON_DIR` computation; replace with `from auto.config import REF_DB, ICON_DIR` (overlay modules already run with `apps/video` on sys.path — same pattern as their `from auto import ...` siblings; if this module currently lacks the `sys.path` bootstrap, copy the 3-line `HERE/SB/sys.path.insert` header from `overlay/results.py`).
- `overlay/results.py:30-37`: fix `parents[2]` → `parents[3]` for the repo-root sys.path insert (so `from aoe2x.sim import simulation_real` resolves deliberately), and `UNITS_DB` → `from auto.config import UNITS_DB`.
- `auto/build_unique_list.py:28`: `REF_DB = REPO / "webapp" / "aoe2_reference.db"` → `from auto.config import REF_DB`.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/test_pure.py -q` — passes.
Run: `cd apps/video && ../../.venv/bin/python -c "from auto.build_unique_list import enumerate_uniques; u, s = enumerate_uniques(); print(len(u))"` — prints 66.

- [ ] **Step 5: Commit**

```bash
git add apps/video/auto/config.py apps/video/overlay/overlay_data.py apps/video/overlay/results.py apps/video/auto/build_unique_list.py tests/test_pure.py
git commit -m "fix(video): repair stale repo-layout paths, single root in auto.config"
```

---

### Task 7: Extract game-free helpers (`auto/pure.py`)

**Files:**
- Create: `apps/video/auto/pure.py`
- Modify: `apps/video/auto/orchestrate_matchup.py:93-124` (remove `resolve_side`, `equal_resource_counts`, `RES_BUDGET`; import from `pure`), `apps/video/auto/record_until_end.py:88` (move `log()`; re-export for back-compat)
- Test: `apps/video/tests/test_pure_module.py`

- [ ] **Step 1: Write failing test**

```python
# apps/video/tests/test_pure_module.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_pure_imports_without_nav_stack():
    for m in ("auto.vision", "auto.platform_io", "auto.grpc_capture"):
        sys.modules.pop(m, None)
    from auto import pure  # noqa: F401
    assert "auto.vision" not in sys.modules
    assert "auto.platform_io" not in sys.modules


def test_equal_resource_counts_moved():
    from auto.pure import equal_resource_counts, RES_BUDGET
    c1, c2 = equal_resource_counts({"cost_food": 70, "cost_wood": 0, "cost_gold": 45},
                                   {"cost_food": 60, "cost_wood": 0, "cost_gold": 0})
    assert c1 > 0 and c2 > c1 and RES_BUDGET > 0
```

Run: `.venv/bin/pytest apps/video/tests/test_pure_module.py -q` → FAIL (`no module auto.pure`)

- [ ] **Step 2: Move the code**

Create `apps/video/auto/pure.py` with a module docstring ("Game-free helpers importable without the OCR/nav stack") and move — verbatim, no logic changes — `RES_BUDGET`, `resolve_side()`, `equal_resource_counts()` from `orchestrate_matchup.py:93-124` and `log()` from `record_until_end.py:88`. In the source modules replace the moved code with `from auto.pure import RES_BUDGET, resolve_side, equal_resource_counts` / `from auto.pure import log` so all existing callers keep working. Note: `equal_resource_counts`'s exact signature is whatever `orchestrate_matchup.py:93-124` defines — adjust the test above to the real signature when moving (the test as written assumes cost-dict inputs; if the real function takes DB rows or (civ, slug) pairs, mirror that).

- [ ] **Step 3: Verify**

Run: `.venv/bin/pytest apps/video/tests/test_pure_module.py tests/test_pure.py -q` → pass
Run: `cd apps/video && ../../.venv/bin/python -c "import auto.orchestrate_matchup"` → imports clean (on a machine without game deps this may fail on OTHER imports — acceptable; the pure module itself must import clean everywhere).

- [ ] **Step 4: Commit**

```bash
git add apps/video/auto/pure.py apps/video/auto/orchestrate_matchup.py apps/video/auto/record_until_end.py apps/video/tests/test_pure_module.py
git commit -m "refactor(video): game-free helpers in auto.pure"
```

---

### Task 8: Manifest-driven queue runner

**Files:**
- Create: `apps/video/auto/queue_runner.py`
- Test: `apps/video/tests/test_queue_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/video/tests/test_queue_runner.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto.queue_runner import run_matchup_queue


def spec(i, **kw):
    d = {"civ1": "Muisca", "slug1": "elite_temple_guard_muisca",
         "civ2": "Aztecs", "slug2": f"opp_{i}", "name": f"clip_{i}",
         "label": f"Label {i}", "category": "expected_win", "why": "because"}
    d.update(kw)
    return d


def fake_runner_factory(fail_names=(), calls=None):
    def fake_run(s, out_dir):
        if calls is not None:
            calls.append(s["name"])
        if s["name"] in fail_names:
            raise RuntimeError("boom")
        p = Path(out_dir) / f"{s['name']}.mp4"
        p.write_bytes(b"fake")
        return p
    return fake_run


def test_writes_manifest_with_metadata(tmp_path):
    specs = [spec(1), spec(2)]
    res = run_matchup_queue(specs, tmp_path, run_one=fake_runner_factory())
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert [c["label"] for c in m["clips"]] == ["Label 1", "Label 2"]
    assert all(c["status"] == "done" and c["category"] == "expected_win"
               for c in m["clips"])
    assert len(res.done) == 2 and not res.failed


def test_resume_skips_existing(tmp_path):
    calls = []
    run_matchup_queue([spec(1)], tmp_path,
                      run_one=fake_runner_factory(calls=calls))
    run_matchup_queue([spec(1), spec(2)], tmp_path,
                      run_one=fake_runner_factory(calls=calls))
    assert calls == ["clip_1", "clip_2"]      # clip_1 not re-run


def test_failure_recorded_and_queue_continues(tmp_path):
    res = run_matchup_queue([spec(1), spec(2)], tmp_path,
                            run_one=fake_runner_factory(fail_names=("clip_1",)))
    m = json.loads((tmp_path / "manifest.json").read_text())
    st = {c["name"]: c["status"] for c in m["clips"]}
    assert st == {"clip_1": "failed", "clip_2": "done"}
    assert [s["name"] for s in res.failed] == ["clip_1"]
```

Run: `.venv/bin/pytest apps/video/tests/test_queue_runner.py -q` → FAIL

- [ ] **Step 2: Implement**

```python
# apps/video/auto/queue_runner.py
"""Run a queue of matchup recordings with resume-skip, per-clip failure
isolation, and a metadata manifest (out_dir/manifest.json) that stitching,
chapters, and recompose read INSTEAD of parsing filenames.

Spec dict: {civ1, slug1, civ2, slug2, name, label, category, why, ...} —
extra keys are preserved into the manifest untouched.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from auto.pure import log

MANIFEST = "manifest.json"


@dataclass
class QueueResult:
    done: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)


def _load_manifest(out_dir):
    p = Path(out_dir) / MANIFEST
    if p.exists():
        return json.loads(p.read_text())
    return {"clips": []}


def _save_manifest(out_dir, manifest):
    (Path(out_dir) / MANIFEST).write_text(json.dumps(manifest, indent=1))


def run_matchup_queue(specs, out_dir, *, run_one, on_recover=None):
    """run_one(spec, out_dir) -> Path of finished clip (or raises).
    on_recover() is called after a failure (e.g. return_to_editor)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(out_dir)
    by_name = {c["name"]: c for c in manifest["clips"]}
    result = QueueResult()

    for s in specs:
        entry = by_name.get(s["name"])
        clip_path = out_dir / f"{s['name']}.mp4"
        if entry and entry.get("status") == "done" and clip_path.exists():
            log(f"skip (done): {s['name']}")
            result.skipped.append(s)
            continue
        entry = dict(s)
        try:
            path = run_one(s, out_dir)
            entry.update(status="done", path=str(path), ts=time.time())
            result.done.append(s)
        except Exception as e:                          # noqa: BLE001
            log(f"FAILED {s['name']}: {e}")
            entry.update(status="failed", error=str(e), ts=time.time())
            result.failed.append(s)
            if on_recover:
                try:
                    on_recover()
                except Exception as re:                 # noqa: BLE001
                    log(f"recovery also failed: {re}")
        by_name[s["name"]] = entry
        # rebuild in spec order, keeping clips from older runs (unknown names) first
        known = {s2["name"] for s2 in specs}
        manifest["clips"] = ([c for c in manifest["clips"]
                              if c.get("name") not in known]
                             + [by_name[s2["name"]] for s2 in specs
                                if s2["name"] in by_name])
        _save_manifest(out_dir, manifest)
    return result
```

- [ ] **Step 3: Run tests** → pass.

- [ ] **Step 4: Commit**

```bash
git add apps/video/auto/queue_runner.py apps/video/tests/test_queue_runner.py
git commit -m "feat(video): manifest-driven matchup queue runner"
```

---

### Task 9: Chapters/stitch from manifest; sweep + batch become callers

**Files:**
- Create: `apps/video/auto/chapters.py`
- Modify: `apps/video/auto/run_guecha_sweep.py` (stitch: labels from manifest, drop the filename regex at :83-85; matchup loop → `run_matchup_queue`), `apps/video/auto/batch_matchups.py` (move `write_chapters`+`_civ_adj` out at :62-84; loop → `run_matchup_queue`)
- Test: `apps/video/tests/test_chapters.py`

- [ ] **Step 1: Write failing test**

```python
# apps/video/tests/test_chapters.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto.chapters import write_chapters


def test_chapter_lines_from_labels(tmp_path):
    out = tmp_path / "chapters.txt"
    write_chapters([("Intro", 12.0), ("Expected win #1 — Heavy Camel Rider", 20.5),
                    ("Expected win #2 — Shrivamsha Rider", 18.0)], out)
    lines = out.read_text().splitlines()
    assert lines[0].startswith("00:00")
    assert "Expected win #1" in lines[1]
    assert lines[2].startswith("00:32")   # 12.0 + 20.5 -> 32s floor
```

Run: `.venv/bin/pytest apps/video/tests/test_chapters.py -q` → FAIL

- [ ] **Step 2: Implement `auto/chapters.py`**

Move `write_chapters` (`batch_matchups.py:72-84`) and `_civ_adj` (`batch_matchups.py:62-69`) verbatim into `apps/video/auto/chapters.py`; keep signature `write_chapters(entries, out_path)` where entries are `(label, duration_seconds)`. In `batch_matchups.py` replace the definitions with `from auto.chapters import write_chapters, _civ_adj`. Adjust the moved code only if its current signature differs (mirror the real one and fix the test accordingly — the label/duration pairing is the contract that matters).

- [ ] **Step 3: Rewire `run_guecha_sweep.py`**

- Replace the matchup loop (lines 144-170) with `run_matchup_queue(specs, OUT_DIR, run_one=..., on_recover=return_to_editor)` where each spec carries `name=matchup_name(...)`, `label=f"vs {opp_name}"`, and the existing per-matchup kwargs; `run_one` wraps the current `run_matchup(...)` call.
- Replace `stitch()`'s filename-regex label recovery (lines 83-85) with reading `manifest.json` and passing `(label, path)` pairs; chapter durations still via the existing `_duration()` probe.
- Keep the CLI flags (`--only`, `--limit`, `--stitch-only`, `--record-only`) working — they filter/short-circuit the spec list, not the runner.

- [ ] **Step 4: Rewire `batch_matchups.py`** — same pattern: build specs (it already has the right dict shape at :51-58), keep `preflight()` before the queue, replace its loop with `run_matchup_queue`, chapters from manifest labels instead of `.replace('Elite ', '')` munging (line 224).

- [ ] **Step 5: Verify**

Run: `.venv/bin/pytest apps/video/tests/ tests/test_pure.py -q` → pass.
Dry check (no game): `cd apps/video && ../../.venv/bin/python -m auto.batch_matchups --dry-run` with its sample list → prints planned queue, exits 0.

- [ ] **Step 6: Commit**

```bash
git add apps/video/auto/chapters.py apps/video/auto/run_guecha_sweep.py apps/video/auto/batch_matchups.py apps/video/tests/test_chapters.py
git commit -m "refactor(video): chapters+stitch read the manifest; sweep/batch use queue runner"
```

---

### Task 10: Compose — `extra_overlays` + gif-capable intro + asset resolver

**Files:**
- Modify: `apps/video/overlay/compose.py` (`make_live_overlay_video` at :405-582; `_card_segment` at :89-105)
- Create: `apps/video/overlay/assets.py`
- Test: `apps/video/tests/test_compose_args.py`

- [ ] **Step 1: Write failing test for the pure graph-builder piece**

```python
# apps/video/tests/test_compose_args.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overlay.compose import extra_overlay_filters
from overlay.assets import AssetResolver


def test_extra_overlay_filters_chain():
    filters, n_inputs = extra_overlay_filters(
        [("banner.png", "0", "40", 0.0, 5.0, 0.4),
         ("caption.png", "(W-w)/2", "H-h-60", 1.0, 20.0, 0.0)],
        first_input_index=3, upstream="[v0]")
    assert n_inputs == 2
    joined = ";".join(filters)
    assert "enable='between(t,0.0,5.0)'" in joined
    assert "enable='between(t,1.0,20.0)'" in joined
    assert joined.count("overlay=") == 2


def test_asset_resolver_placeholders(tmp_path, monkeypatch):
    monkeypatch.delenv("AOE2_MEDIA_DIR", raising=False)
    r = AssetResolver()
    assert r.hi_res_image("elite_temple_guard_muisca") is None
    assert r.attack_gif("elite_temple_guard_muisca") is None
    monkeypatch.setenv("AOE2_MEDIA_DIR", str(tmp_path))
    (tmp_path / "gifs").mkdir()
    gif = tmp_path / "gifs" / "elite_temple_guard_muisca.gif"
    gif.write_bytes(b"GIF89a")
    assert AssetResolver().attack_gif("elite_temple_guard_muisca") == gif
```

Run: `.venv/bin/pytest apps/video/tests/test_compose_args.py -q` → FAIL

- [ ] **Step 2: Implement**

In `overlay/compose.py` add the pure helper (near the top, after imports):

```python
def extra_overlay_filters(extra_overlays, first_input_index, upstream):
    """Filter-graph fragments for timed PNG overlays.
    extra_overlays: [(png_path, x_expr, y_expr, t_start, t_end, fade_s)].
    Returns (filter_strings, n_extra_inputs); caller appends the PNGs as
    ffmpeg inputs starting at first_input_index and chains from `upstream`."""
    filters, cur = [], upstream
    for i, (_, x, y, t0, t1, fade) in enumerate(extra_overlays):
        idx = first_input_index + i
        src = f"[{idx}:v]"
        if fade:
            src_lbl = f"[xf{i}]"
            filters.append(
                f"[{idx}:v]format=rgba,fade=t=out:st={t1 - fade}:d={fade}:alpha=1{src_lbl}")
            src = src_lbl
        out = f"[xo{i}]"
        filters.append(
            f"{cur}{src}overlay={x}:{y}:enable='between(t,{t0},{t1})'{out}")
        cur = out
    return filters, len(extra_overlays)
```

Then in `make_live_overlay_video(...)` add keyword arg `extra_overlays=()`; at the point after the existing overlay chain's last labeled node (follow the `idx` bookkeeping dict at :463-492), append the PNGs as inputs and splice `extra_overlay_filters(...)` into the `-filter_complex` string, rewiring the final map label. In `_card_segment` add `gif_path=None`: when set, add `-ignore_loop 0 -i {gif_path}` input and an `overlay` node positioning it (`x=(W-w)/2:y=H*0.32`), and cap with the existing `-t` duration; encode params unchanged (`_x264()`/`_AAC`) so `concat_videos` keeps stream-copying.

Create `overlay/assets.py`:

```python
# apps/video/overlay/assets.py
"""Resolve optional hi-res media (Windows box / bucket mirror). Returns None
when AOE2_MEDIA_DIR is unset or the file is absent — callers degrade to
static cards. Expected layout: $AOE2_MEDIA_DIR/gifs/<slug>.gif,
$AOE2_MEDIA_DIR/hires/<slug>.png."""
import os
from pathlib import Path


class AssetResolver:
    def __init__(self, root=None):
        env = os.environ.get("AOE2_MEDIA_DIR")
        self.root = Path(root or env) if (root or env) else None

    def _find(self, rel):
        if not self.root:
            return None
        p = self.root / rel
        return p if p.exists() else None

    def hi_res_image(self, slug):
        return self._find(f"hires/{slug}.png")

    def attack_gif(self, slug):
        return self._find(f"gifs/{slug}.gif")
```

- [ ] **Step 3: Run tests** → pass. (The full ffmpeg path is exercised on the Windows box; the pure fragment builder is what CI covers.)

- [ ] **Step 4: Commit**

```bash
git add apps/video/overlay/compose.py apps/video/overlay/assets.py apps/video/tests/test_compose_args.py
git commit -m "feat(video): timed extra overlays, gif intro input, media resolver"
```

---

### Task 11: New cards — category banner, why pill, ranked list

**Files:**
- Modify: `apps/video/overlay/render_card.py` (new `build_*_html` + `render_*` pairs, following the existing pattern: shared `_css()`/`PALETTE` at :25-30/:201-268, `_screenshot()` at :619)
- Test: `apps/video/tests/test_card_html.py`

- [ ] **Step 1: Write failing tests** (HTML builders only — rendering needs the screenshot browser; builders are pure)

```python
# apps/video/tests/test_card_html.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overlay.render_card import (
    build_category_banner_html, build_caption_pill_html,
    build_ranked_list_html,
)


def test_banner_contains_title_and_index():
    h = build_category_banner_html("Unexpected Counters", 4, 4)
    assert "Unexpected Counters" in h and "4/4" in h


def test_caption_pill_escapes_and_includes_text():
    h = build_caption_pill_html("Obuch strips 1 armor per hit — the tank <breaks>")
    assert "strips 1 armor per hit" in h and "<breaks>" not in h


def test_ranked_list_rows_and_pick_marker():
    rows = [{"rank": 1, "name": "Elite Skirmisher", "civ": "Armenians",
             "score": 81.0, "picked": False},
            {"rank": 2, "name": "Heavy Camel Rider", "civ": "Persians",
             "score": 79.1, "picked": True}]
    h = build_ranked_list_html("Expected Wins — full ranking", rows)
    assert "Elite Skirmisher" in h and "Heavy Camel Rider" in h
    assert h.index("Elite Skirmisher") < h.index("Heavy Camel Rider")
    assert "picked" in h            # css class marks recorded entries
```

Run: `.venv/bin/pytest apps/video/tests/test_card_html.py -q` → FAIL

- [ ] **Step 2: Implement** — three `build_*_html(...)` functions in `render_card.py` using the module's existing `_css()` + `PALETTE` (reuse the panel markup conventions of `build_unit_panel_html`; `html.escape()` all user-visible strings; ranked list = two-column flex rows, `class="row picked"` when `picked`), plus matching `render_category_banner(path, ...)`, `render_caption_pill(path, ...)`, `render_ranked_list(path, ...)` that call the existing `_screenshot()` + `_autocrop()` exactly like `render_unit_panel` does.

- [ ] **Step 3: Run tests** → pass.

- [ ] **Step 4: Visual spot-check (optional on Mac, required once on Windows):**
`cd apps/video && ../../.venv/bin/python -c "from overlay.render_card import render_ranked_list; render_ranked_list('/tmp/rl.png', 'Expected Wins', [{'rank':1,'name':'X','civ':'Y','score':50.0,'picked':True}])"` then eyeball the PNG.

- [ ] **Step 5: Commit**

```bash
git add apps/video/overlay/render_card.py apps/video/tests/test_card_html.py
git commit -m "feat(video): banner, caption-pill and ranked-list cards"
```

---

### Task 12: `run_unit_analysis_video.py` — storyboard consumer

**Files:**
- Create: `apps/video/auto/run_unit_analysis_video.py`
- Test: `apps/video/tests/test_unit_analysis_video_plan.py`

- [ ] **Step 1: Write failing test for the planning half (game-free)**

```python
# apps/video/tests/test_unit_analysis_video_plan.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto.run_unit_analysis_video import build_plan

SB = {
    "schema_version": 1,
    "subject": {"civ": "Muisca", "slug": "elite_temple_guard_muisca",
                "name": "Elite Temple Guard", "stats": {}},
    "segments": [
        {"order": 1, "category": "expected_win", "rank": 1,
         "opponent": {"civ": "Persians", "slug": "heavy_camel",
                      "name": "Heavy Camel Rider"},
         "score": 79.1, "counts": {"subject": 26, "opponent": 37},
         "why": "bonus applies", "why_factors": {}},
        {"order": 2, "category": "unexpected_counter", "rank": 1,
         "opponent": {"civ": "Poles", "slug": "elite_obuch_poles",
                      "name": "Elite Obuch"},
         "score": -42.2, "counts": {"subject": 26, "opponent": 33},
         "why": "armor strip", "why_factors": {}},
    ],
    "category_lists": {
        "expected_win": [{"rank": 1, "name": "Heavy Camel Rider",
                          "civ": "Persians", "slug": "heavy_camel",
                          "score": 79.1, "picked": True}],
        "unexpected_win": [], "expected_counter": [],
        "unexpected_counter": [{"rank": 1, "name": "Elite Obuch",
                                "civ": "Poles", "slug": "elite_obuch_poles",
                                "score": -42.2, "picked": True}],
        "even": [{"rank": 1, "name": "Elite Berserk", "civ": "Vikings",
                  "slug": "elite_berserk_vikings", "score": 0.4,
                  "picked": False}],
    },
}


def test_build_plan_orders_and_labels(tmp_path):
    sb_path = tmp_path / "sb.json"
    sb_path.write_text(json.dumps(SB))
    plan = build_plan(sb_path)
    kinds = [step["kind"] for step in plan]
    # intro first, then per category: banner -> fights -> ranked card; even card last
    assert kinds[0] == "intro"
    assert kinds[1] == "banner" and plan[1]["category"] == "expected_win"
    assert kinds[2] == "fight" and plan[2]["spec"]["slug2"] == "heavy_camel"
    assert "ranked_card" in kinds and kinds[-1] == "even_card"
    fight = plan[2]["spec"]
    assert fight["label"] == "Expected Win #1 — Heavy Camel Rider"
    assert fight["category"] == "expected_win" and fight["why"] == "bonus applies"
```

Run: `.venv/bin/pytest apps/video/tests/test_unit_analysis_video_plan.py -q` → FAIL

- [ ] **Step 2: Implement**

```python
# apps/video/auto/run_unit_analysis_video.py
"""Turn an analysis storyboard JSON into a stitched unit-analysis video.

  python -m auto.run_unit_analysis_video path/to/storyboard.json --out DIR
  ... --dry-run          # print the plan, touch nothing
  ... --stitch-only      # re-join existing clips + cards

Plan structure (build_plan): a flat list of steps —
  intro -> per category in storyboard order:
  banner -> 3 fight specs (queue_runner) -> ranked_card -> ... -> even_card.
Fight recording uses the existing run_matchup pipeline; cards render via
overlay.render_card; hi-res/gif intro degrades gracefully when
AOE2_MEDIA_DIR is unset (overlay.assets.AssetResolver).
"""
import argparse
import json
from pathlib import Path

CATEGORY_TITLES = {
    "expected_win": "Expected Win", "unexpected_win": "Unexpected Win",
    "expected_counter": "Expected Counter",
    "unexpected_counter": "Unexpected Counter",
}
CATEGORY_ORDER = ("expected_win", "unexpected_win",
                  "expected_counter", "unexpected_counter")


def build_plan(storyboard_path):
    sb = json.loads(Path(storyboard_path).read_text())
    subj = sb["subject"]
    plan = [{"kind": "intro", "subject": subj}]
    n_cats = len(CATEGORY_ORDER)
    for ci, cat in enumerate(CATEGORY_ORDER, 1):
        segs = [s for s in sb["segments"] if s["category"] == cat]
        if not segs:
            continue
        plan.append({"kind": "banner", "category": cat,
                     "title": f"{CATEGORY_TITLES[cat]}s",
                     "index": ci, "total": n_cats})
        for s in segs:
            plan.append({"kind": "fight", "spec": {
                "civ1": subj["civ"], "slug1": subj["slug"],
                "civ2": s["opponent"]["civ"], "slug2": s["opponent"]["slug"],
                "name": f"{cat}_{s['rank']}_{s['opponent']['slug']}",
                "label": (f"{CATEGORY_TITLES[cat]} #{s['rank']} — "
                          f"{s['opponent']['name']}"),
                "category": cat, "why": s["why"], "score": s["score"],
                "counts": s["counts"],
            }})
        plan.append({"kind": "ranked_card", "category": cat,
                     "title": f"{CATEGORY_TITLES[cat]}s — full ranking",
                     "rows": sb["category_lists"][cat]})
    plan.append({"kind": "even_card",
                 "rows": sb["category_lists"].get("even", [])})
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stitch-only", action="store_true")
    args = ap.parse_args()

    plan = build_plan(args.storyboard)
    if args.dry_run:
        for step in plan:
            label = step.get("spec", {}).get("label") or step.get(
                "title") or step["kind"]
            print(f"{step['kind']:>12}  {label}")
        return

    # Recording/composition half — Windows box with game + media.
    from auto.queue_runner import run_matchup_queue
    from auto.orchestrate_matchup import run_matchup, return_to_editor
    from auto import chapters  # noqa: F401  (stitch step)
    from overlay.assets import AssetResolver  # noqa: F401  (intro step)
    out = Path(args.out)
    fights = [st["spec"] for st in plan if st["kind"] == "fight"]

    def run_one(spec, out_dir):
        return run_matchup(spec["civ1"], spec["slug1"],
                           spec["civ2"], spec["slug2"],
                           name=spec["name"], out_dir=out_dir)

    if not args.stitch_only:
        run_matchup_queue(fights, out, run_one=run_one,
                          on_recover=return_to_editor)
    # Card rendering + intro + stitch: compose cards per plan order, build the
    # (label, path) list from the manifest + card segments, then
    # overlay.compose.concat_videos + chapters.write_chapters. Implemented on
    # the Windows checkout where ffmpeg output can actually be verified.
    raise SystemExit("recording plan executed; stitch step runs on Windows — "
                     "see docs/superpowers/specs/2026-07-04-unit-analysis-video-design.md")


if __name__ == "__main__":
    main()
```

**Note:** `run_matchup(...)`'s real signature is at `orchestrate_matchup.py:434` — match its actual parameter names when wiring `run_one` (name/mode/caps kwargs). The final stitch block is intentionally the last thing implemented, on the Windows box, because its output can only be verified there; everything above it (plan, queue, cards, chapters, overlays) is already tested.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest apps/video/tests/test_unit_analysis_video_plan.py -q` → pass
Run: `cd apps/video && ../../.venv/bin/python -m auto.run_unit_analysis_video ../../storyboards/elite_temple_guard_muisca.json --out /tmp/x --dry-run` (storyboard from Task 5 Step 6) → prints ~13-step plan.

- [ ] **Step 4: Full suite + commit**

Run: `.venv/bin/pytest -q` → no regressions.

```bash
git add apps/video/auto/run_unit_analysis_video.py apps/video/tests/test_unit_analysis_video_plan.py
git commit -m "feat(video): storyboard-driven unit-analysis video orchestrator (plan+queue)"
```

---

## Verification (end of plan)

1. `.venv/bin/pytest -q` — full suite green.
2. `RUN_SLOW=1 .venv/bin/pytest tests/test_matchup_sources.py -q` — real-engine backend works.
3. Storyboard regenerated end-to-end (Task 5 Step 6) and `--dry-run` plan prints correctly (Task 12 Step 3).
4. On Windows later: point `--source matchup-db` at `D:/AI/matchup_baseline_<build>.db`, regenerate the storyboard, run `run_unit_analysis_video` without `--dry-run`, eyeball one recorded fight + the stitched compilation.

## Explicitly out of scope

- Deleting the legacy compose chain (`make_real_video.py`, `compose.py:625-664` era, `hud._draw_side`, `results.py:148` stub) — separate cleanup PR.
- Website/SSR exposure of the analysis lists — video-only per the design decisions log.
- The Windows-side stitch implementation detail beyond the seam left in Task 12 (verifiable only with game + ffmpeg output on that box).
