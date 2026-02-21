# Per-Line Civ Detail Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the civ detail page to show individual unit lines with per-line normalization, replacing role-based grouping.

**Architecture:** Three-layer change: (1) `compute_battle_scores.py` switches stable/infantry normalization from pool-wide to per-line, removes anti_cav_pool; (2) `best_units.py` restructures from role-based to per-line output; (3) `matchup.js` + `matchup.css` renders per-line cards in 4 columns.

**Tech Stack:** Python (Flask backend, SQLite), vanilla JavaScript, CSS Grid.

---

### Task 1: Switch stable scoring to per-line normalization

**Files:**
- Modify: `webapp/compute_battle_scores.py:1385-1523` (function `compute_stable_role_scores`)

**Step 1: Add line tracking to stable scoring**

Currently `compute_stable_role_scores` pools all stable units into one dict. We need to track which sub-line each unit belongs to, then normalize per sub-line.

In `compute_stable_role_scores` (line ~1407), after the unit loop that builds `all_scores`, add a `sk_to_line` dict. The line_slug is already available from the outer loop variable.

Change the unit collection loop to track line membership:

```python
    # Collect stable units from all source lines
    all_units = []
    sk_to_line = {}  # track which sub-line each unit belongs to
    for line_slug in STABLE_LINE_SLUGS:
        units = build_line_units(line_slug, age)
        for u in units:
            all_units.append(u)
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            sk_to_line[sk] = line_slug
```

Then after scores are populated, set `sk_to_line` for each unit (around line 1477):

```python
        scores["_speed"] = cu["movement_speed"]
        all_scores[sk] = scores
        # sk_to_line already set above
```

**Step 2: Change normalization from pool-wide to per-line**

Replace the pool-wide normalization block (lines 1488-1494):

```python
    # Min-max normalize each benchmark score across all stable units (0-100)
    for bk in all_bench_keys:
        vals = [s[bk] for s in all_scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for s in all_scores.values():
            s[bk] = round((s[bk] - lo) / span * 100, 1)
```

With per-line normalization:

```python
    # Build line_groups for per-line normalization
    line_groups = {}
    for sk in all_scores:
        line = sk_to_line[sk]
        line_groups.setdefault(line, []).append(sk)

    # Min-max normalize each benchmark score per sub-line (0-100)
    for bk in all_bench_keys:
        for line, sks in line_groups.items():
            vals = [all_scores[sk][bk] for sk in sks]
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1
            for sk in sks:
                all_scores[sk][bk] = round((all_scores[sk][bk] - lo) / span * 100, 1)
```

**Step 3: Change speed weighting from pool to per-line**

Replace (line ~1512-1516):

```python
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "stable_effectiveness"],
        scope="pool",
    )
```

With:

```python
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "stable_effectiveness"],
        scope="per_line",
        line_groups=line_groups,
    )
```

**Step 4: Change return format from pooled to per-line**

Replace the return statement (line 1523):

```python
    return {f"stable|{age}": all_scores}
```

With per-line grouping:

```python
    # Regroup by sub-line for DB storage
    all_role_scores = {}
    for sk, scores in all_scores.items():
        line_slug = sk_to_line[sk]
        line_key = f"{line_slug}|{age}"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores

    return all_role_scores
```

**Step 5: Update `main()` and `--roles-only` to use per-line slugs for stable DB writes**

In both the `--roles-only` branch (line ~2266-2267) and the main branch (line ~2461-2462), change:

```python
        write_role_scores_to_db(stable_scores, ["stable"], STABLE_SCORE_TYPES)
```

To:

```python
        write_role_scores_to_db(stable_scores, STABLE_LINE_SLUGS, STABLE_SCORE_TYPES)
```

This tells `write_role_scores_to_db` to delete old entries for each sub-line slug (knight, camel, etc.) instead of just "stable".

**Step 6: Verify by running `--roles-only`**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 compute_battle_scores.py --roles-only`

Expected: Stable roles output shows units grouped by sub-line. Check DB:
```sql
SELECT DISTINCT line_slug FROM battle_scores WHERE line_slug IN ('knight','light_cav','camel','steppe_lancer','elephant');
```
Should return rows for each sub-line that has units.

**Step 7: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "refactor: switch stable scoring to per-line normalization"
```

---

### Task 2: Switch infantry scoring to per-line normalization

**Files:**
- Modify: `webapp/compute_battle_scores.py:1048-1186` (function `compute_infantry_role_scores`)

**Step 1: Change normalization from pool-wide to per-line**

The infantry function already has `sk_to_line`. Replace the pool-wide normalization block (lines 1129-1135):

```python
    # Normalize each benchmark score to 0–100 across ALL infantry units
    for key in bench_keys:
        vals = [s[key] for s in all_scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for s in all_scores.values():
            s[key] = round((s[key] - lo) / span * 100, 1)
```

With per-line normalization:

```python
    # Build line_groups for per-line normalization
    line_groups = {}
    for sk in all_scores:
        line = sk_to_line[sk]
        line_groups.setdefault(line, []).append(sk)

    # Normalize each benchmark score to 0–100 per infantry sub-line
    for key in bench_keys:
        for line, sks in line_groups.items():
            vals = [all_scores[sk][key] for sk in sks]
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1
            for sk in sks:
                all_scores[sk][key] = round((all_scores[sk][key] - lo) / span * 100, 1)
```

**Step 2: Change speed weighting from pool to per-line**

Replace (lines 1166-1170):

```python
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "militia_value", "raid_building", "anti_cav_value"],
        scope="pool",
    )
```

With:

```python
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "militia_value", "raid_building", "anti_cav_value"],
        scope="per_line",
        line_groups=line_groups,
    )
```

**Step 3: Verify and commit**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 compute_battle_scores.py --roles-only`

Expected: Infantry roles output still works, units grouped by sub-line in DB.

```bash
git add webapp/compute_battle_scores.py
git commit -m "refactor: switch infantry scoring to per-line normalization"
```

---

### Task 3: Remove anti_cav_pool from scoring pipeline

**Files:**
- Modify: `webapp/compute_battle_scores.py` — remove `compute_combined_anti_cav_scores()` function and all callers

**Step 1: Remove the function and its constants**

Delete these sections:
- Lines ~1823-1959: The entire `compute_combined_anti_cav_scores()` function, including `COMBINED_AC_BENCHMARKS` and `COMBINED_AC_KEYS` constants above it (lines ~1828-1843)

**Step 2: Remove callers in `main()`**

In the `--roles-only` branch (lines ~2273-2277), delete:

```python
            # Combined anti-cav pool (infantry + qualifying stable)
            ac_start = time.time()
            combined_ac = compute_combined_anti_cav_scores(stable_scores, age=role_age)
            write_role_scores_to_db(combined_ac, ["anti_cav_pool"], ["anti_cav_combined"])
            print(f"Combined anti-cav: {time.time() - ac_start:.1f}s")
```

In the main branch (lines ~2468-2471), delete:

```python
        ac_start = time.time()
        combined_ac = compute_combined_anti_cav_scores(stable_scores, age=role_age)
        write_role_scores_to_db(combined_ac, ["anti_cav_pool"], ["anti_cav_combined"])
        print(f"Combined anti-cav: {time.time() - ac_start:.1f}s")
```

**Step 3: Add cleanup for stale anti_cav_pool entries**

Add a cleanup function near `_cleanup_stale_siege_entries()`:

```python
def _cleanup_stale_anti_cav_pool():
    """Remove stale anti_cav_pool entries from battle_scores."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM battle_scores WHERE line_slug='anti_cav_pool'")
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"  Cleaned up {deleted} stale anti_cav_pool entries")
```

Call it in `main()` right after `_cleanup_stale_siege_entries()` in both code paths.

Also clean up stale "stable" entries (now stored per sub-line):

```python
def _cleanup_stale_stable_entries():
    """Remove stale pooled 'stable' entries from battle_scores."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM battle_scores WHERE line_slug='stable'")
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"  Cleaned up {deleted} stale pooled 'stable' entries")
```

**Step 4: Verify and commit**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 compute_battle_scores.py --roles-only`

Expected: No "Combined anti-cav" line in output. DB should have no `anti_cav_pool` or `stable` line_slug entries.

```bash
git add webapp/compute_battle_scores.py
git commit -m "refactor: remove anti_cav_pool from scoring pipeline"
```

---

### Task 4: Rewrite `best_units.py` with per-line data structure

**Files:**
- Modify: `webapp/best_units.py` — major rewrite of data definitions and `compute_civ_power_units()`

**Step 1: Replace ROLE_DEFS with COLUMN_DEFS and LINE_SCORE_TYPE**

Replace (lines 50-58):

```python
ROLE_DEFS = [
    ("cavalry", ["stable"], "stable_effectiveness"),
    ("ranged", ["archer", "cav_archer", "scorpion", "gunpowder"], "ranged_effectiveness"),
    ("infantry", ["militia", "shock_infantry"], "militia_value"),
    ("anti_archer", ["skirmisher"], "anti_archer"),
    ("siege", ["ram", "trebuchet", "bombard_cannon"], "anti_building_score"),
]
```

With:

```python
# Column definitions: (column_key, line_slugs)
COLUMN_DEFS = {
    "cavalry": ["light_cav", "knight", "camel", "steppe_lancer", "elephant"],
    "ranged": ["skirmisher", "archer", "cav_archer", "gunpowder", "scorpion"],
    "infantry": ["militia", "spear", "shock_infantry"],
    "siege": ["ram", "bombard_cannon", "trebuchet"],
}

# Per-line score type to use for ranking
LINE_SCORE_TYPE = {
    "light_cav": "stable_effectiveness",
    "knight": "stable_effectiveness",
    "camel": "stable_effectiveness",
    "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
    "skirmisher": "ranged_effectiveness",
    "archer": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness",
    "gunpowder": "ranged_effectiveness",
    "scorpion": "ranged_effectiveness",
    "militia": "militia_value",
    "spear": "militia_value",
    "shock_infantry": "militia_value",
    "ram": "anti_building_score",
    "bombard_cannon": "anti_building_score",
    "trebuchet": "anti_building_score",
}
```

**Step 2: Remove old role-based helpers**

Delete these functions/constants:
- `_build_role_dict()` (lines ~378-404)
- `_determine_narrative_key()` (lines ~407-460)
- `_ROLE_NAMES` dict (lines ~463-472)
- `SCOUT_SLUGS` constant (line 171)
- `SLOW_CAV_THRESHOLD` constant (line 174)

**Step 3: Rewrite `compute_civ_power_units()`**

Replace the function body (lines 629-787) with new per-line logic:

```python
def compute_civ_power_units():
    """Pre-compute power units for all civs. Returns dict keyed by civ_name."""
    conn = _get_db()
    rc = conn.cursor()

    # Get all civ names
    rc.execute("SELECT DISTINCT civ_name FROM battle_scores ORDER BY civ_name")
    all_civs = [row["civ_name"] for row in rc.fetchall()]

    # Build reference tech sets and line counts per age
    reference_techs_by_age = {
        "imperial": _build_reference_techs(conn, "Imperial"),
        "castle": _build_reference_techs(conn, "Castle"),
    }
    line_counts_by_age = {
        "imperial": _compute_line_counts(conn, "imperial"),
        "castle": _compute_line_counts(conn, "castle"),
    }

    result = {}

    for civ in all_civs:
        civ_data = {"imperial": None, "castle": None}

        for age_key in ["imperial", "castle"]:
            db_age = "Imperial" if age_key == "imperial" else "Castle"
            reference_techs = reference_techs_by_age[age_key]
            line_counts = line_counts_by_age[age_key]
            power_units = {}

            # Batch-fetch all techs and effects for this civ
            techs_by_slug, effects_by_slug = _batch_fetch_civ_tech_data(conn, civ, db_age)

            # Iterate columns and lines
            for col_key, line_slugs in COLUMN_DEFS.items():
                col_data = {}
                for line_slug in line_slugs:
                    score_type = LINE_SCORE_TYPE[line_slug]
                    rc.execute(
                        """SELECT unit_slug, line_slug, score_value, rank, median_delta
                            FROM battle_scores
                            WHERE civ_name = ?
                              AND LOWER(age) = ?
                              AND score_type = ?
                              AND line_slug = ?
                            ORDER BY score_value DESC
                            LIMIT 1""",
                        [civ, age_key, score_type, line_slug],
                    )
                    row = rc.fetchone()

                    # Filter trebuchets for civs that don't have them
                    if row and civ in CIVS_WITHOUT_TREBUCHET and row["unit_slug"] in _TREBUCHET_SLUGS:
                        row = None

                    if row:
                        entry = _build_unit_entry(
                            row, civ, conn, db_age, reference_techs,
                            techs_by_slug, effects_by_slug, line_counts, score_type
                        )
                        col_data[line_slug] = entry
                    else:
                        col_data[line_slug] = None

                power_units[col_key] = col_data

            # Build strength profile (per-line)
            strength_profile = {}
            for col_key, line_slugs in COLUMN_DEFS.items():
                for line_slug in line_slugs:
                    entry = power_units[col_key].get(line_slug)
                    strength_profile[line_slug] = entry["strength"] if entry else None

            # Build strategic summary
            all_line_slugs = [ls for slugs in COLUMN_DEFS.values() for ls in slugs]
            strong_areas = []
            weak_areas = []
            signature_areas = []
            for ls in all_line_slugs:
                s = strength_profile.get(ls)
                if s is None:
                    continue
                if s == "signature":
                    signature_areas.append(ls)
                    strong_areas.append(ls)
                elif s == "strong":
                    strong_areas.append(ls)
                elif s in ("weak", "poor"):
                    weak_areas.append(ls)

            # Determine which columns have strength
            strong_columns = []
            for col_key, line_slugs in COLUMN_DEFS.items():
                has_strong = any(
                    strength_profile.get(ls) in ("strong", "signature")
                    for ls in line_slugs
                )
                if has_strong:
                    strong_columns.append(col_key)

            total_strong_cols = len(strong_columns)
            if total_strong_cols >= 2:
                summary_key = "multi_flexible"
            elif total_strong_cols >= 1:
                summary_key = "one_area_strong"
            else:
                summary_key = "none_exceptional"

            primary_strength = strong_columns[0] if strong_columns else None

            strategic_summary = {
                "strong_areas": strong_areas,
                "strong_columns": strong_columns,
                "weak_areas": weak_areas,
                "signature_areas": signature_areas,
                "summary_key": summary_key,
                "primary_strength": primary_strength,
            }

            # Generate strategic description paragraph
            strategic_description = _generate_strategic_description(
                power_units, strong_columns, weak_areas, strength_profile
            )

            civ_data[age_key] = {
                "power_units": power_units,
                "strength_profile": strength_profile,
                "strategic_summary": strategic_summary,
                "strategic_description": strategic_description,
            }

        result[civ] = civ_data

    conn.close()
    return result
```

**Step 4: Rewrite `_generate_strategic_description()`**

Replace the entire function (lines ~475-626) with a simplified version that checks per-line strengths:

```python
def _generate_strategic_description(power_units, strong_columns, weak_areas, strength_profile):
    """Generate a multi-sentence strategic description for a civilization.

    Composes three parts:
    1. Primary playstyle (based on strongest column)
    2. Defensive assessment (spear/camel/skirm lines)
    3. Push strategy (siege lines + primary strength)
    """
    sentences = []

    # --- Part 1: Primary Playstyle ---
    combat_strong = [c for c in strong_columns if c in ("cavalry", "ranged", "infantry")]

    if len(combat_strong) >= 2:
        col_names = [c.capitalize() for c in combat_strong]
        sentences.append(
            "This civ is versatile, with strength across "
            + " and ".join([", ".join(col_names[:-1]), col_names[-1]] if len(col_names) > 2 else col_names)
            + " -- allowing flexible strategies that adapt to any opponent."
        )
    elif len(combat_strong) == 1:
        col = combat_strong[0]
        # Find the best unit in this column
        col_data = power_units.get(col, {})
        best_entry = None
        for entry in col_data.values():
            if entry and (best_entry is None or entry.get("percentile", 0) > best_entry.get("percentile", 0)):
                best_entry = entry
        best_name = best_entry["unit_name"] if best_entry else "their best unit"

        if col == "cavalry":
            sentences.append(
                f"This civ excels at mobile cavalry play -- able to raid,"
                f" flank, and apply pressure across the map with {best_name}."
            )
        elif col == "ranged":
            sentences.append(
                f"This civ has strong ranged options for concentrated pushes,"
                f" with {best_name} providing range advantage and sustained damage output."
            )
        elif col == "infantry":
            sentences.append(
                f"This civ has strong infantry for frontline pressure,"
                f" with {best_name} serving as the backbone of siege-backed pushes."
            )
    else:
        sentences.append(
            "This civ doesn't have a standout late-game powerhouse"
            " -- focus on early aggression and maintaining a lead."
        )

    # --- Part 2: Defensive Assessment ---
    spear_strength = strength_profile.get("spear")
    camel_strength = strength_profile.get("camel")
    skirm_strength = strength_profile.get("skirmisher")

    has_good_spear = spear_strength in ("strong", "signature")
    has_good_camel = camel_strength in ("strong", "signature")
    has_good_skirm = skirm_strength in ("strong", "signature")

    if has_good_spear and has_good_camel:
        sentences.append(
            "Excellent anti-cavalry options from both spears and camels"
            " -- very hard for cavalry-heavy opponents to find an opening."
        )
    elif has_good_camel:
        camel_data = power_units.get("cavalry", {}).get("camel")
        camel_name = camel_data["unit_name"] if camel_data else "camels"
        sentences.append(
            f"Can answer enemy cavalry with mobile {camel_name},"
            " allowing counter-raids and flexible responses."
        )
    elif has_good_spear:
        spear_data = power_units.get("infantry", {}).get("spear")
        spear_name = spear_data["unit_name"] if spear_data else "spearmen"
        sentences.append(
            f"Strong anti-cavalry defense with {spear_name} to hold"
            " positions against cavalry pushes."
        )
    else:
        sentences.append(
            "Anti-cavalry options are limited"
            " -- beware of knight-heavy opponents."
        )

    if has_good_skirm:
        sentences.append(
            "Good skirmishers help shut down archer compositions."
        )
    elif not has_good_spear and not has_good_camel:
        sentences[-1] = (
            "Limited counter options mean this civ must play aggressively"
            " and press its advantage before opponents can mass their army."
        )
    else:
        sentences.append(
            "Vulnerable to massed archers"
            " -- consider aggressive play before ranged compositions develop."
        )

    # --- Part 3: Push Strategy ---
    siege_data = power_units.get("siege", {})
    ram_entry = siege_data.get("ram")
    treb_entry = siege_data.get("trebuchet")
    bbc_entry = siege_data.get("bombard_cannon")

    has_good_ram = ram_entry and ram_entry["strength"] in ("signature", "strong")
    has_good_treb = treb_entry and treb_entry["strength"] in ("signature", "strong")
    has_good_bbc = bbc_entry and bbc_entry["strength"] in ("signature", "strong")
    infantry_strong = "infantry" in strong_columns
    ranged_strong = "ranged" in strong_columns

    if infantry_strong and has_good_ram:
        inf_data = power_units.get("infantry", {})
        best_inf = None
        for entry in inf_data.values():
            if entry and (best_inf is None or entry.get("percentile", 0) > best_inf.get("percentile", 0)):
                best_inf = entry
        inf_name = best_inf["unit_name"] if best_inf else "infantry"
        sentences.append(
            f"An infantry ram push is the signature play -- use {inf_name}"
            " as a meatshield to protect rams pushing into enemy bases."
        )
    elif ranged_strong and has_good_treb:
        rng_data = power_units.get("ranged", {})
        best_rng = None
        for entry in rng_data.values():
            if entry and (best_rng is None or entry.get("percentile", 0) > best_rng.get("percentile", 0)):
                best_rng = entry
        rng_name = best_rng["unit_name"] if best_rng else "ranged units"
        sentences.append(
            f"Pushing behind trebuchets maximizes the ranged advantage"
            f" -- set up trebs and let {rng_name} protect them."
        )
    elif has_good_bbc:
        sentences.append(
            "Bombard Cannons provide long-range siege power"
            " for breaking through fortified positions."
        )
    elif "siege" in strong_columns:
        sentences.append(
            "Solid siege options give flexibility in how to close out games."
        )
    else:
        sentences.append(
            "Siege options are limited -- look to win through"
            " open-field engagements rather than pushing fortifications."
        )

    return " ".join(sentences)
```

**Step 5: Update matchup recommendations (Phase B)**

In `COUNTER_MAP` (lines ~821-838), the structure queries by `line_slug` already, so no changes needed to the map itself.

In `get_matchup_recommendations()` (lines ~1009-1175), remove the reference to `anti_cav_pool`. The function reads from `power_units` and `battle_scores` DB directly — with the new structure, `power_units["cavalry"]["camel"]` replaces `power_units["anti_cavalry"]`. Update the opponent_strengths loop to check column-level data:

Change the opponent strength detection (lines ~1024-1048) to iterate columns:
```python
    for col_key in ["cavalry", "ranged", "infantry", "siege"]:
        col_data = civ_b_data["power_units"].get(col_key, {})
        for line_slug, entry in col_data.items():
            if entry and entry["strength"] in ("strong", "signature"):
                opponent_strengths.append({
                    "role": col_key,
                    "unit_slug": entry["unit_slug"],
                    "strength": entry["strength"],
                    "median_delta": entry["median_delta"],
                })
                break  # one strong unit per column is enough
```

**Step 6: Verify by regenerating civ_power_units.json**

Run:
```bash
cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 best_units.py
```

Expected: Writes `civ_power_units.json` with new per-line structure. Spot-check a civ:
```bash
python3 -c "import json; d=json.load(open('civ_power_units.json')); print(json.dumps(d['Franks']['imperial']['power_units']['cavalry'], indent=2))"
```
Should show `knight`, `light_cav`, etc. as separate entries.

**Step 7: Commit**

```bash
git add webapp/best_units.py
git commit -m "refactor: restructure best_units.py to per-line data model"
```

---

### Task 5: Update frontend (`matchup.js`)

**Files:**
- Modify: `webapp/static/js/matchup.js`

**Step 1: Replace constants**

Replace `ROLE_ORDER`, `ROLE_LABELS`, `COLUMN_LAYOUT`, and `NARRATIVES` (lines 8-72) with:

```javascript
const COLUMN_DEFS = {
    cavalry: ["light_cav", "knight", "camel", "steppe_lancer", "elephant"],
    ranged: ["skirmisher", "archer", "cav_archer", "gunpowder", "scorpion"],
    infantry: ["militia", "spear", "shock_infantry"],
    siege: ["ram", "bombard_cannon", "trebuchet"],
};

const COLUMN_LABELS = {
    cavalry: "Cavalry",
    ranged: "Ranged",
    infantry: "Infantry",
    siege: "Siege",
};

const LINE_NAMES = {
    light_cav: "Light Cavalry",
    knight: "Knight Line",
    camel: "Camel Line",
    steppe_lancer: "Steppe Lancer",
    elephant: "Battle Elephant",
    skirmisher: "Skirmisher",
    archer: "Archer Line",
    cav_archer: "Cavalry Archer",
    gunpowder: "Gunpowder",
    scorpion: "Scorpion",
    militia: "Militia Line",
    spear: "Spear Line",
    shock_infantry: "Shock Infantry",
    ram: "Rams",
    bombard_cannon: "Bombard Cannon",
    trebuchet: "Trebuchet",
};

const COLUMN_ORDER = ["cavalry", "ranged", "infantry", "siege"];
```

Keep `STRENGTH_COLORS` and `SUMMARY_TEMPLATES` unchanged.

**Step 2: Rewrite `renderAnalysis()`**

Replace the function body (lines 171-264) with:

```javascript
function renderAnalysis(civName, data) {
    var powerUnits = data.power_units || {};
    var summary = data.strategic_summary || {};
    var strategicDescription = data.strategic_description || "";
    var civSlug = civName.toLowerCase();
    var emblemUrl = CIV_EMBLEM_BASE + civSlug + ".png";
    var strongColumns = summary.strong_columns || [];
    var html = '';

    /* Hero: emblem + name + strategic description side-by-side */
    html += '<div class="analysis-hero">';
    html += '<img src="' + emblemUrl + '" class="analysis-emblem" alt="' + escapeHtml(civName) + '">';
    html += '<div class="analysis-hero-body">';
    html += '<h2 class="analysis-civ-name">' + escapeHtml(civName) + '</h2>';
    html += renderStrategicSummaryInline(summary, strategicDescription);
    html += '</div>';
    html += '</div>';

    /* Role columns grid — 4 columns with per-line sections */
    html += '<div class="role-columns">';

    for (var i = 0; i < COLUMN_ORDER.length; i++) {
        var colKey = COLUMN_ORDER[i];
        var lineSlugs = COLUMN_DEFS[colKey];
        var colData = powerUnits[colKey] || {};
        var colLabel = COLUMN_LABELS[colKey];

        /* Check if column has any strong/signature line */
        var colHasSig = false;
        var colIsStrong = strongColumns.indexOf(colKey) !== -1;
        for (var k = 0; k < lineSlugs.length; k++) {
            var entry = colData[lineSlugs[k]];
            if (entry && entry.is_signature) colHasSig = true;
        }

        var colClass = "role-column";
        if (colIsStrong) colClass += " col-strong";
        if (colHasSig) colClass += " has-signature";

        html += '<div class="' + colClass + '">';
        html += '<div class="role-header">' + escapeHtml(colLabel) + '</div>';

        /* Render each unit line */
        for (var j = 0; j < lineSlugs.length; j++) {
            var lineSlug = lineSlugs[j];
            var lineEntry = colData[lineSlug];
            var lineName = LINE_NAMES[lineSlug] || slugToName(lineSlug);

            html += '<div class="line-section">';
            html += '<div class="line-label">' + escapeHtml(lineName) + '</div>';

            if (lineEntry) {
                html += '<div class="unit-wrap">';
                html += renderUnitBadge(lineEntry);
                html += '</div>';
            } else {
                html += '<div class="line-unavailable">—</div>';
            }
            html += '</div>';
        }

        html += '</div>';
    }

    html += '</div>'; /* end role-columns */

    return html;
}
```

**Step 3: Remove `getNarrative()` function**

Delete the `getNarrative` function (lines ~267-278) — it's no longer called.

**Step 4: Update `renderStrategicSummaryInline()`**

The `SUMMARY_TEMPLATES` fallback still references `ROLE_LABELS` — update it to use `COLUMN_LABELS`:

```javascript
function renderStrategicSummaryInline(summary, strategicDescription) {
    if (!strategicDescription && (!summary || !summary.summary_key)) return "";
    var html = '';
    if (strategicDescription) {
        html += '<div class="analysis-hero-narrative">' + escapeHtml(strategicDescription) + '</div>';
    } else {
        var template = SUMMARY_TEMPLATES[summary.summary_key];
        if (template) {
            var strongColumns = summary.strong_columns || [];
            var primaryStrength = summary.primary_strength
                ? (COLUMN_LABELS[summary.primary_strength] || summary.primary_strength)
                : "";
            var areasText = strongColumns.map(function (a) {
                return COLUMN_LABELS[a] || a;
            }).join(", ");
            var narrativeText = template
                .replace("{areas}", areasText)
                .replace("{primary_strength}", primaryStrength);
            html += '<div class="analysis-hero-narrative">' + escapeHtml(narrativeText) + '</div>';
        }
    }
    return html;
}
```

**Step 5: Commit**

```bash
git add webapp/static/js/matchup.js
git commit -m "feat: update matchup.js for per-line civ detail layout"
```

---

### Task 6: Update frontend CSS (`matchup.css`)

**Files:**
- Modify: `webapp/static/css/matchup.css`

**Step 1: Remove old sub-section styles**

Delete the `.role-sub-section`, `.role-sub-header`, `.role-sub-narrative`, and their modifier classes (lines ~220-249).

**Step 2: Remove the fixed-height narrative block**

Delete or modify `.role-narrative` (lines ~207-218) — the fixed 3-line clamp is no longer needed since narratives are gone from columns.

**Step 3: Add new line-section styles**

Add after the `.role-header` section:

```css
/* --- Line Section (individual unit line within a column) --- */
.line-section {
    margin-bottom: 6px;
}

.line-label {
    color: var(--text-muted);
    font-size: 0.68rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 3px;
    padding-left: 2px;
}

.line-unavailable {
    color: var(--text-dim);
    font-size: 0.75rem;
    padding: 4px 8px;
    opacity: 0.4;
}
```

**Step 4: Commit**

```bash
git add webapp/static/css/matchup.css
git commit -m "feat: update matchup.css for per-line layout"
```

---

### Task 7: Run full pipeline and verify

**Step 1: Run the full scoring pipeline**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 compute_battle_scores.py --roles-only
```

**Step 2: Regenerate civ_power_units.json**

```bash
python3 best_units.py
```

**Step 3: Verify JSON structure**

```bash
python3 -c "
import json
d = json.load(open('civ_power_units.json'))
# Check structure
franks = d['Franks']['imperial']
print('Columns:', list(franks['power_units'].keys()))
print('Cavalry lines:', list(franks['power_units']['cavalry'].keys()))
print('Knight entry:', franks['power_units']['cavalry']['knight']['unit_name'] if franks['power_units']['cavalry']['knight'] else 'None')
print('Camel entry:', franks['power_units']['cavalry']['camel'])
print('Strength profile:', {k: v for k, v in franks['strength_profile'].items() if v})
print('Description:', franks['strategic_description'][:100])
"
```

Expected: Franks should have knight = Paladin (strong/signature), light_cav = Hussar, no camel/steppe/elephant. Strength profile shows per-line strengths.

**Step 4: Start webapp and test visually**

```bash
python3 app.py --port 5001
```

Open browser to `http://localhost:5001/civ-detail` (or whatever the route is). Click Franks — should see 4 columns with individual unit lines.

**Step 5: Spot-check 3-4 more civs**

Check civs with different profiles:
- **Aztecs** (no cavalry except eagle): cavalry column should show mostly "—" except eagle in shock_infantry
- **Chinese** (generic but complete tree): most lines should have entries
- **Bengalis** (elephants + unique units): elephant line should show Battle Elephant

**Step 6: Commit verified state**

```bash
git add webapp/civ_power_units.json webapp/aoe2_reference.db
git commit -m "data: regenerate scores and civ power units for per-line structure"
```

---

### Task 8: Clean up dead code

**Files:**
- Modify: `webapp/compute_battle_scores.py` — remove unused anti-cav scoring artifacts
- Modify: `webapp/best_units.py` — final dead code cleanup

**Step 1: Remove `ANTI_CAV_BENCHMARKS` if no longer referenced**

Check if `ANTI_CAV_BENCHMARKS` (used by the now-deleted `compute_anti_cav_scores`) is still needed. If `compute_anti_cav_scores` was called from `compute_infantry_role_scores` (line 1151), we need to decide: keep it (it feeds into `anti_cav_value` which feeds `militia_value` indirectly) or remove it.

**Important:** `compute_anti_cav_scores` adds `anti_cav_value` to infantry scores, which is included in the speed-weighting list. If we remove the function, we must also remove `anti_cav_value` from the speed-weighting list and `INFANTRY_ROLE_SCORE_TYPES`.

Actually — check if `anti_cav_value` is used in any composite. Looking at the infantry composite formula:
```python
militia_value = 0.50 * general_combat + 0.30 * anti_cav + 0.20 * raid_building
```

`anti_cav_value` is NOT used in `militia_value` — it's a separate score stored in the DB for the old anti-cav pool display. So it can be safely removed.

Remove:
- `compute_anti_cav_scores()` function (lines ~1747-1821)
- `ANTI_CAV_BENCHMARKS` constant (above it)
- The call at line 1151: `compute_anti_cav_scores(all_scores, sk_to_line, age)`
- `"anti_cav_value"` from the speed-weighting list (line 1168)
- From `INFANTRY_ROLE_SCORE_TYPES`: `"anti_cav_total"`, `"frontline"`, `"anti_cav_value"`, and all `"ac_vs_*"` entries

**Step 2: Remove stale comments/references**

Search for "anti_cav_pool", "anti_cav_combined", "anti_cav_value" mentions and remove them.

**Step 3: Verify everything still works**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 compute_battle_scores.py --roles-only && python3 best_units.py
```

**Step 4: Commit**

```bash
git add webapp/compute_battle_scores.py webapp/best_units.py
git commit -m "cleanup: remove anti_cav_pool and dead code from scoring pipeline"
```
