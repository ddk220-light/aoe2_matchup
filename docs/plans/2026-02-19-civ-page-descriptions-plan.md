# Civ Page Descriptions & Categorization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the `/civilizations` page with score-based categorization (top 25% per role = "good"), rich strategic descriptions, and template renaming.

**Architecture:** Backend changes in `best_units.py` compute per-role 75th percentile thresholds, reclassify units as signature/good/average, and generate a `strategic_description` paragraph. Frontend changes in `matchup.js` render the new description in the hero section. Templates are renamed for clarity.

**Tech Stack:** Python (best_units.py), JavaScript (matchup.js), Jinja2 (templates), Flask (app.py)

---

### Task 1: Rename Templates

**Files:**
- Rename: `webapp/templates/civ_detail.html` -> `webapp/templates/deprecated-civ.html`
- Rename: `webapp/templates/matchup_advisor.html` -> `webapp/templates/civ_detail.html`
- Modify: `webapp/app.py:77-89`
- Modify: `webapp/templates/civ_select.html:1` (obsolete comment references matchup_advisor.html)

**Step 1: Rename files**

```bash
cd webapp/templates
mv civ_detail.html deprecated-civ.html
mv matchup_advisor.html civ_detail.html
```

**Step 2: Update app.py route references**

In `webapp/app.py`, line 81, change:
```python
return render_template("matchup_advisor.html", civs=civs, active_nav="civ_select")
```
to:
```python
return render_template("civ_detail.html", civs=civs, active_nav="civ_select")
```

In `webapp/app.py`, line 89, change:
```python
return render_template("civ_detail.html", civ_name=civ_name, active_nav="civ_detail")
```
to:
```python
return render_template("deprecated-civ.html", civ_name=civ_name, active_nav="civ_detail")
```

**Step 3: Update obsolete comment in civ_select.html**

In `webapp/templates/civ_select.html`, line 1, change the comment from referencing `matchup_advisor.html` to `civ_detail.html`.

**Step 4: Verify the app starts and `/civilizations` loads**

```bash
cd webapp && source ../venv/bin/activate && python3 app.py --port 5001 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/civilizations
# Expected: 200
kill %1
```

**Step 5: Commit**

```bash
git add webapp/templates/deprecated-civ.html webapp/templates/civ_detail.html webapp/app.py webapp/templates/civ_select.html
git commit -m "refactor: rename templates (matchup_advisor -> civ_detail, old civ_detail -> deprecated-civ)"
```

---

### Task 2: Score-Based Categorization in best_units.py

**Files:**
- Modify: `webapp/best_units.py:46-65` (_classify_strength and surrounding code)
- Modify: `webapp/best_units.py:295-322` (_build_unit_entry — pass threshold)
- Modify: `webapp/best_units.py:411-506` (compute_civ_power_units — compute thresholds)

**Step 1: Add per-role threshold computation**

In `webapp/best_units.py`, add a new function after `_classify_strength` (around line 66):

```python
def _compute_role_thresholds(conn):
    """Compute 75th percentile score threshold per role for categorization.

    Returns dict: {role_key: threshold_score}
    """
    rc = conn.cursor()
    thresholds = {}
    for role_key, line_slugs, score_type in ROLE_DEFS:
        placeholders = ",".join("?" for _ in line_slugs)
        rc.execute(
            f"""SELECT score_value FROM battle_scores
                WHERE LOWER(age) = 'imperial'
                  AND score_type = ?
                  AND line_slug IN ({placeholders})
                ORDER BY score_value ASC""",
            [score_type] + line_slugs,
        )
        scores = [row["score_value"] for row in rc.fetchall()]
        if scores:
            idx = int(len(scores) * 0.75)
            thresholds[role_key] = scores[min(idx, len(scores) - 1)]
        else:
            thresholds[role_key] = 0
    return thresholds
```

**Step 2: Update `_classify_strength` to use score-based thresholds**

Replace the current `_classify_strength` function (lines 57-65):

```python
def _classify_strength(score, rank, threshold):
    """Classify a unit's strength tier based on score percentile.

    Args:
        score: the unit's absolute score for this role
        rank: percentile rank (1=best, 50=worst)
        threshold: 75th percentile score for this role
    """
    if score is not None and score >= threshold:
        if rank is not None and rank <= 5:
            return "signature"
        return "good"
    return "average"
```

**Step 3: Update `_build_unit_entry` to accept and pass threshold**

In `_build_unit_entry` (line 295), add `role_threshold` parameter:

Change signature from:
```python
def _build_unit_entry(row, civ_name, conn, db_age, reference_techs, techs_by_slug, effects_by_slug):
```
to:
```python
def _build_unit_entry(row, civ_name, conn, db_age, reference_techs, techs_by_slug, effects_by_slug, role_threshold=0):
```

Change line 305 from:
```python
    strength = _classify_strength(row["rank"], row["median_delta"])
```
to:
```python
    strength = _classify_strength(row["score_value"], row["rank"], role_threshold)
```

**Step 4: Update `compute_civ_power_units` to compute and pass thresholds**

In `compute_civ_power_units` (line 411), after the `reference_techs` line (line 421), add:

```python
    # Compute per-role 75th percentile thresholds for categorization
    role_thresholds = _compute_role_thresholds(conn)
```

Then update the `_build_unit_entry` calls (around line 448-452) to pass the threshold:

Change:
```python
                all_units = [
                    _build_unit_entry(row, civ, conn, db_age, reference_techs,
                                      techs_by_slug, effects_by_slug)
                    for row in rc.fetchall()
                ]
```
to:
```python
                threshold = role_thresholds.get(role_key, 0)
                all_units = [
                    _build_unit_entry(row, civ, conn, db_age, reference_techs,
                                      techs_by_slug, effects_by_slug, threshold)
                    for row in rc.fetchall()
                ]
```

**Step 5: Update strategic summary to use "good" instead of "strong"**

In `compute_civ_power_units`, update the strength checks (around line 474):

Change:
```python
                elif entry["strength"] in ("strong", "signature"):
                    strong_areas.append(rk)
                elif entry["strength"] == "weak":
                    weak_areas.append(rk)
```
to:
```python
                elif entry["strength"] in ("good", "signature"):
                    strong_areas.append(rk)
                # No more "weak" tier — anything below threshold is "average"
```

**Step 6: Update matchup recommendations strength check**

In `get_matchup_recommendations` (line 746), change:
```python
        if entry and entry["strength"] in ("strong", "signature"):
```
to:
```python
        if entry and entry["strength"] in ("good", "signature"):
```

**Step 7: Regenerate civ_power_units.json and verify**

```bash
cd webapp && source ../venv/bin/activate && python3 best_units.py
# Expected: "Wrote .../civ_power_units.json (50 civs)" (or however many enabled civs)
```

Verify the JSON has the new categories:
```bash
python3 -c "import json; d=json.load(open('civ_power_units.json')); u=d['Franks']['imperial']['power_units']['cavalry']['all_units'][0]; print(u['strength'])"
# Expected: "signature" or "good" (not "strong" or "weak")
```

**Step 8: Commit**

```bash
git add webapp/best_units.py webapp/civ_power_units.json
git commit -m "feat: score-based categorization (top 25% per role = good)"
```

---

### Task 3: Update Frontend for New Categories

**Files:**
- Modify: `webapp/static/js/matchup.js:17-22` (STRENGTH_COLORS)

**Step 1: Update STRENGTH_COLORS**

Replace the `STRENGTH_COLORS` object (lines 17-22):

```javascript
const STRENGTH_COLORS = {
    signature: { bg: "rgba(201, 168, 76, 0.2)", text: "var(--gold)", label: "Signature" },
    good: { bg: "rgba(46, 204, 113, 0.15)", text: "#2ecc71", label: "Good" },
    average: { bg: "rgba(255, 255, 255, 0.05)", text: "var(--text-muted)", label: "Average" },
};
```

Remove the `strong` and `weak` entries — they are no longer produced by the backend.

**Step 2: Verify page renders correctly**

Start the server and click a civ. Units should show "Signature", "Good", or "Average" labels instead of the old 4-tier system.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup.js
git commit -m "feat(frontend): update strength tiers to signature/good/average"
```

---

### Task 4: Generate Strategic Description in Python

**Files:**
- Modify: `webapp/best_units.py` — add `_generate_strategic_description` function and call it

**Step 1: Add the description generator function**

Add this function after `_determine_narrative_key` (after line 407):

```python
# Role labels for description text
_ROLE_NAMES = {
    "cavalry": "cavalry",
    "ranged": "ranged",
    "infantry": "infantry",
    "anti_cavalry": "anti-cavalry",
    "anti_archer": "anti-archer",
    "siege": "siege",
}


def _generate_strategic_description(power_units, strong_areas, weak_areas):
    """Generate a multi-sentence strategic description for a civilization.

    Composes three parts:
    1. Primary playstyle (based on strongest combat role)
    2. Defensive assessment (based on anti_cav + anti_archer)
    3. Push strategy (based on siege + primary strength)
    """
    sentences = []

    # --- Part 1: Primary Playstyle ---
    # Determine primary combat roles (cavalry, ranged, infantry only — not counter or siege roles)
    combat_strong = [r for r in strong_areas if r in ("cavalry", "ranged", "infantry")]

    if len(combat_strong) >= 2:
        area_names = [_ROLE_NAMES[r] for r in combat_strong]
        sentences.append(
            "This civ is versatile, with strength across "
            + " and ".join([", ".join(area_names[:-1]), area_names[-1]] if len(area_names) > 2 else area_names)
            + " -- allowing flexible strategies that adapt to any opponent."
        )
    elif len(combat_strong) == 1:
        role = combat_strong[0]
        entry = power_units.get(role)
        best_name = entry["unit_name"] if entry else "their best unit"

        if role == "cavalry":
            narrative_key = entry["narrative_key"] if entry else ""
            if narrative_key == "cav_strong_slow":
                sentences.append(
                    f"This civ fields powerful but slower cavalry like {best_name},"
                    " favoring head-on engagements over mobility."
                )
            else:
                sentences.append(
                    f"This civ excels at mobile cavalry play -- able to raid,"
                    f" flank, and apply pressure across the map with {best_name}."
                )
        elif role == "ranged":
            sentences.append(
                f"This civ has strong ranged options for concentrated pushes,"
                f" with {best_name} providing range advantage and sustained damage output."
            )
        elif role == "infantry":
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
    anticav_entry = power_units.get("anti_cavalry")
    antiarcher_entry = power_units.get("anti_archer")
    anticav_strong = "anti_cavalry" in strong_areas
    antiarcher_strong = "anti_archer" in strong_areas

    if anticav_strong and antiarcher_strong:
        sentences.append(
            "Defensively well-rounded, with solid options to shut down"
            " both cavalry and ranged threats."
        )
    elif anticav_strong and not antiarcher_strong:
        sentences.append(
            "Can hold the line against cavalry, but vulnerable to massed archers"
            " -- consider aggressive play before ranged compositions develop."
        )
    elif not anticav_strong and antiarcher_strong:
        sentences.append(
            "Good tools against ranged units, but lacks reliable anti-cavalry"
            " -- beware of knight-heavy opponents."
        )
    else:
        sentences.append(
            "Limited counter options mean this civ must play aggressively"
            " and press its advantage before opponents can mass their army."
        )

    # --- Part 3: Push Strategy ---
    siege_entry = power_units.get("siege")
    siege_units = siege_entry["all_units"] if siege_entry else []
    infantry_strong = "infantry" in strong_areas

    # Check siege sub-lines
    ram_units = [u for u in siege_units if u["line_slug"] == "ram"]
    treb_units = [u for u in siege_units if u["line_slug"] == "trebuchet"]
    bbc_units = [u for u in siege_units if u["line_slug"] == "bombard_cannon"]

    has_good_ram = any(u["strength"] in ("signature", "good") for u in ram_units)
    has_good_treb = any(u["strength"] in ("signature", "good") for u in treb_units)
    has_good_bbc = any(u["strength"] in ("signature", "good") for u in bbc_units)

    ranged_strong = "ranged" in strong_areas
    best_inf_name = ""
    if infantry_strong:
        inf_entry = power_units.get("infantry")
        best_inf_name = inf_entry["unit_name"] if inf_entry else "infantry"
    best_ranged_name = ""
    if ranged_strong:
        ranged_entry = power_units.get("ranged")
        best_ranged_name = ranged_entry["unit_name"] if ranged_entry else "ranged units"

    if infantry_strong and has_good_ram:
        sentences.append(
            f"An infantry ram push is the signature play -- use {best_inf_name}"
            " as a meatshield to protect rams pushing into enemy bases."
        )
    elif ranged_strong and has_good_treb:
        sentences.append(
            f"Pushing behind trebuchets maximizes the ranged advantage"
            f" -- set up trebs and let {best_ranged_name} protect them."
        )
    elif has_good_bbc:
        sentences.append(
            "Bombard Cannons provide long-range siege power"
            " for breaking through fortified positions."
        )
    elif "siege" in strong_areas:
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

**Step 2: Call the description generator in `compute_civ_power_units`**

In `compute_civ_power_units`, after the `strategic_summary` dict is built (after line 495), add:

```python
            # Generate strategic description paragraph
            strategic_description = _generate_strategic_description(
                power_units, strong_areas, weak_areas
            )
```

Then add it to the `civ_data[age_key]` dict (around line 497):

Change:
```python
            civ_data[age_key] = {
                "power_units": power_units,
                "strength_profile": strength_profile,
                "strategic_summary": strategic_summary,
            }
```
to:
```python
            civ_data[age_key] = {
                "power_units": power_units,
                "strength_profile": strength_profile,
                "strategic_summary": strategic_summary,
                "strategic_description": strategic_description,
            }
```

**Step 3: Regenerate and verify**

```bash
cd webapp && source ../venv/bin/activate && python3 best_units.py
```

Spot-check a few civs:
```bash
python3 -c "
import json
d = json.load(open('civ_power_units.json'))
for civ in ['Franks', 'Britons', 'Goths', 'Byzantines', 'Huns']:
    desc = d[civ]['imperial'].get('strategic_description', 'MISSING')
    print(f'{civ}: {desc[:120]}...')
"
```

Expected output: Each civ shows a 2-3 sentence description covering playstyle, defense, and push strategy.

**Step 4: Commit**

```bash
git add webapp/best_units.py webapp/civ_power_units.json
git commit -m "feat: generate strategic description paragraphs for all civs"
```

---

### Task 5: Render Strategic Description in Frontend Hero Section

**Files:**
- Modify: `webapp/static/js/matchup.js:155-173` (renderAnalysis hero section)
- Modify: `webapp/static/js/matchup.js:314-360` (renderStrategicSummaryInline)

**Step 1: Update `renderAnalysis` to pass `strategic_description` to hero**

In `renderAnalysis` (around line 156), extract the description:

After `var summary = data.strategic_summary || {};` (line 158), add:
```javascript
    var strategicDescription = data.strategic_description || "";
```

Change line 171 from:
```javascript
    html += renderStrategicSummaryInline(summary);
```
to:
```javascript
    html += renderStrategicSummaryInline(summary, strategicDescription);
```

**Step 2: Replace `renderStrategicSummaryInline` to use the new description**

Replace the entire `renderStrategicSummaryInline` function (lines 314-360):

```javascript
/* ---- Strategic summary renderer (inline, for hero section) ---- */
function renderStrategicSummaryInline(summary, strategicDescription) {
    if (!strategicDescription && (!summary || !summary.summary_key)) return "";

    var html = '';

    /* Main strategic description paragraph */
    if (strategicDescription) {
        html += '<div class="analysis-hero-narrative">' + escapeHtml(strategicDescription) + '</div>';
    } else {
        /* Fallback to old template if no description generated */
        var template = SUMMARY_TEMPLATES[summary.summary_key];
        if (template) {
            var strongAreas = summary.strong_areas || [];
            var primaryStrength = summary.primary_strength
                ? (ROLE_LABELS[summary.primary_strength] || summary.primary_strength)
                : "";
            var areasText = strongAreas.map(function (a) {
                return ROLE_LABELS[a] || a;
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

This removes the strength/weakness pills (replaced by the richer paragraph) while keeping a fallback to the old template system if `strategic_description` is missing.

**Step 3: Verify the page renders**

Start the server, click a civ, and confirm:
- Hero section shows the multi-sentence strategic description
- No pills (strengths/weaknesses) below it
- Per-role narratives still appear inside each column
- Unit badges show "Signature", "Good", or "Average"

**Step 4: Commit**

```bash
git add webapp/static/js/matchup.js
git commit -m "feat(frontend): render strategic description in hero section"
```

---

### Task 6: Final Verification & Cleanup

**Files:**
- Review: All modified files

**Step 1: Full end-to-end test**

```bash
cd webapp && source ../venv/bin/activate && python3 best_units.py && python3 app.py --port 5001
```

Open `http://localhost:5001/civilizations` in browser. Click through several civs:
- **Franks** (cavalry civ) — should mention mobile cavalry, Paladin
- **Britons** (archer civ) — should mention ranged push, trebuchets
- **Goths** (infantry civ) — should mention infantry frontline, ram push
- **Byzantines** (flexible civ) — should mention versatility
- **Huns** (cavalry + weak eco) — should mention cavalry mobility

Verify:
1. Description is 2-3 sentences covering playstyle, defense, push strategy
2. Units categorized as signature/good/average (no "strong"/"weak")
3. Per-role narratives still work inside columns
4. No JavaScript errors in console
5. `/civilizations/<civ_name>` still works (loads deprecated-civ.html)

**Step 2: Check for any remaining references to old names**

```bash
grep -r "matchup_advisor" webapp/ --include="*.py" --include="*.html" --include="*.js"
grep -r '"strong"' webapp/static/js/matchup.js
grep -r '"weak"' webapp/static/js/matchup.js
```

Expected: No matches for `matchup_advisor` in code. No `"strong"` or `"weak"` in STRENGTH_COLORS (the NARRATIVES dict still uses "strong"/"weak" in English text, which is fine).

**Step 3: Commit any cleanup**

```bash
git add -A && git commit -m "chore: final cleanup for civ page descriptions"
```
