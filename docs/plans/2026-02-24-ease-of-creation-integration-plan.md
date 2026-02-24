# Ease of Creation Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate ease-of-creation data into matchup advisor combo cards — showing context-dependent statements (combat context + ease comparison) and sorting zero-gap combos by ease.

**Architecture:** Bake ease sub-scores into `civ_power_units.json` at pre-compute time (backend). All comparison logic (combat context, ease statements, sort order) runs in frontend JS alongside existing combo logic.

**Tech Stack:** Python/SQLite (backend data enrichment), vanilla JS (frontend logic), CSS (statement styling).

**Design doc:** `docs/plans/2026-02-24-ease-of-creation-integration-design.md`

---

### Task 1: Batch-load ease data in `best_units.py`

**Files:**
- Modify: `webapp/best_units.py:568-698` (`compute_civ_power_units`)

**Step 1: Add batch ease loader function**

Add above `compute_civ_power_units()` (around line 565):

```python
def _batch_fetch_ease_data(conn, civ_name):
    """Load ease-of-creation data for all units of a civ. Returns dict keyed by unit_slug."""
    rc = conn.cursor()
    rc.execute("""
        SELECT unit_slug, ease_score, is_castle_unit, creation_time,
               total_upgrade_cost, needs_castle_ut, movement_speed,
               score_not_castle, score_creation_time, score_upgrade_cost,
               score_no_castle_ut, score_speed
        FROM unit_creation_ease
        WHERE civ_name = ?
    """, [civ_name])
    result = {}
    for row in rc.fetchall():
        result[row["unit_slug"]] = {
            "score": round(row["ease_score"], 4),
            "is_castle_unit": bool(row["is_castle_unit"]),
            "creation_time": row["creation_time"],
            "total_upgrade_cost": row["total_upgrade_cost"],
            "needs_castle_ut": bool(row["needs_castle_ut"]),
            "sub_scores": {
                "not_castle": round(row["score_not_castle"], 4),
                "creation_time": round(row["score_creation_time"], 4),
                "upgrade_cost": round(row["score_upgrade_cost"], 4),
                "no_castle_ut": round(row["score_no_castle_ut"], 4),
                "speed": round(row["score_speed"], 4),
            },
        }
    return result
```

**Step 2: Pass ease data through compute_civ_power_units**

Inside `compute_civ_power_units()`, after line 596 (`techs_by_slug, effects_by_slug = _batch_fetch_civ_tech_data(conn, civ, db_age)`), add:

```python
            ease_by_slug = _batch_fetch_ease_data(conn, civ)
```

Note: ease data is age-independent (same for castle/imperial), so load it once per civ inside the age loop — it's the same dict both times, cheap enough.

**Step 3: Pass ease_by_slug to _build_unit_entry**

Update the `_build_unit_entry` call at line 622 to pass `ease_by_slug`:

```python
                            entry = _build_unit_entry(
                                row, civ, conn, db_age, reference_techs,
                                techs_by_slug, effects_by_slug, line_counts, score_type,
                                ease_by_slug,
                            )
```

**Step 4: Commit**

```bash
git add webapp/best_units.py
git commit -m "feat: batch-load ease data in compute_civ_power_units"
```

---

### Task 2: Add ease dict to `_build_unit_entry`

**Files:**
- Modify: `webapp/best_units.py:356-390` (`_build_unit_entry`)

**Step 1: Add ease_by_slug parameter and attach ease data**

Update function signature at line 356 to accept `ease_by_slug=None`:

```python
def _build_unit_entry(row, civ_name, conn, db_age, reference_techs, techs_by_slug, effects_by_slug, line_counts=None, score_type="", ease_by_slug=None):
```

Before the `return` dict (line 375), add:

```python
    ease = None
    if ease_by_slug:
        ease = ease_by_slug.get(slug)
```

Add `"ease": ease,` to the return dict, after `"special_effects"`:

```python
    return {
        "unit_slug": slug,
        "unit_name": unit_name or slug,
        "line_slug": row["line_slug"],
        "score": round(row["score_value"], 1),
        "rank": row["rank"],
        "percentile": percentile,
        "median_delta": round(row["median_delta"], 1),
        "strength": strength,
        "is_signature": strength == "signature",
        "stats": stats,
        "speed": speed,
        "missing_techs": missing,
        "bonus_abilities": bonus_abilities,
        "special_effects": special_effects,
        "ease": ease,
    }
```

**Step 2: Include ease in `_strip_siege_entries`**

Update `_strip_siege_entries` (line 393-414) to pass through ease data:

```python
        siege_data[line_slug] = [
            {
                "unit_slug": e["unit_slug"],
                "unit_name": e["unit_name"],
                "line_slug": e["line_slug"],
                "percentile": e["percentile"],
                "strength": e["strength"],
                "is_signature": e["is_signature"],
                "ease": e.get("ease"),
            }
            for e in entries
        ]
```

**Step 3: Commit**

```bash
git add webapp/best_units.py
git commit -m "feat: add ease dict to unit entries and siege passthrough"
```

---

### Task 3: Regenerate `civ_power_units.json`

**Files:**
- Modify: `webapp/civ_power_units.json` (auto-generated)

**Step 1: Run the regeneration**

```bash
cd /home/claude-wukong/aoe2-unit-analyzer
python -c "import sys; sys.path.insert(0, 'webapp'); from best_units import save_civ_power_units; save_civ_power_units()"
```

Expected: "Wrote webapp/civ_power_units.json (XX civs)"

**Step 2: Verify ease data in output**

```bash
python -c "
import json
with open('webapp/civ_power_units.json') as f:
    data = json.load(f)
# Check Britons imperial knight entry
britons = data['Britons']['imperial']['power_units']['cavalry']['knight']
print(json.dumps(britons[0].get('ease'), indent=2))
"
```

Expected: a dict with `score`, `is_castle_unit`, `sub_scores`, etc.

**Step 3: Commit**

```bash
git add webapp/civ_power_units.json
git commit -m "chore: regenerate civ_power_units.json with ease data"
```

---

### Task 4: Add JS helper functions

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js`

**Step 1: Add `_avgEase` helper**

Add before `_buildComboCard` (before line 699):

```javascript
function _avgEase(topItem, partner) {
    /**Compute average ease_score for a combo (top unit + optional partner).**/
    const topEase = topItem.entry.ease ? topItem.entry.ease.score : 0;
    if (!partner) return topEase;
    const partnerEase = partner.entry.ease ? partner.entry.ease.score : 0;
    return (topEase + partnerEase) / 2;
}

function _avgEaseSubs(topItem, partner) {
    /**Compute average ease sub_scores for a combo. Returns sub_scores dict or null.**/
    const topSubs = topItem.entry.ease ? topItem.entry.ease.sub_scores : null;
    if (!partner) return topSubs;
    const partSubs = partner.entry.ease ? partner.entry.ease.sub_scores : null;
    if (!topSubs && !partSubs) return null;
    if (!topSubs) return partSubs;
    if (!partSubs) return topSubs;
    const result = {};
    for (const key of Object.keys(topSubs)) {
        result[key] = (topSubs[key] + (partSubs[key] || 0)) / 2;
    }
    return result;
}
```

**Step 2: Add `_computeCombatContext` helper**

Add after the ease helpers:

```javascript
function _computeCombatContext(gapResult) {
    /**Generate combat context statement from gap categories.
     * Returns string or null (for zero-gap or all-loss gaps).**/
    if (gapResult.gap.length === 0) return null;

    const categories = new Set(gapResult.gap.map((g) => g.category));
    const hasLoss = categories.has("loss");
    const hasPop = categories.has("pop");
    const hasEco = categories.has("eco");

    // If all gaps are complete losses, no combat qualifier
    if (hasLoss && !hasPop && !hasEco) return null;

    if (hasPop && !hasEco && !hasLoss) {
        return "Loses on pop efficiency, but trades better on eco";
    }
    if (hasEco && !hasPop && !hasLoss) {
        return "Less eco-efficient, but more pop-efficient";
    }
    // Mixed
    if (hasPop && hasEco) {
        return "Mixed results \u2014 pop-efficient vs some, eco-efficient vs others";
    }
    // Pop or eco with some losses
    if (hasPop) return "Loses on pop efficiency, but trades better on eco";
    if (hasEco) return "Less eco-efficient, but more pop-efficient";
    return null;
}
```

**Step 3: Add `_computeEaseStatement` helper**

```javascript
function _computeEaseStatement(mySubs, oppSubs, myHasCastle, oppHasCastle) {
    /**Generate ease comparison statement.
     * @param mySubs    — my combo's average sub_scores dict
     * @param oppSubs   — opponent's best combo's average sub_scores dict
     * @param myHasCastle  — boolean, does my combo include a castle unit?
     * @param oppHasCastle — boolean, does opponent's combo include a castle unit?
     * Returns { text: string, isUpside: boolean } or null.**/
    if (!mySubs || !oppSubs) return null;

    const THRESHOLD = 0.15;
    const factors = [];

    // Castle: always include if asymmetric
    if (myHasCastle && !oppHasCastle) {
        factors.push({ key: "not_castle", delta: -(mySubs.not_castle - oppSubs.not_castle), text: "needs a Castle" });
    }

    // Creation time (higher = faster train = better)
    const ctDelta = mySubs.creation_time - oppSubs.creation_time;
    if (Math.abs(ctDelta) >= THRESHOLD) {
        factors.push({ key: "creation_time", delta: ctDelta, text: ctDelta > 0 ? "trains faster" : "slower to train" });
    }

    // Upgrade cost (higher = cheaper = better)
    const ucDelta = mySubs.upgrade_cost - oppSubs.upgrade_cost;
    if (Math.abs(ucDelta) >= THRESHOLD) {
        factors.push({ key: "upgrade_cost", delta: ucDelta, text: ucDelta > 0 ? "cheaper upgrades" : "costlier upgrades" });
    }

    // Castle unique tech: only if asymmetric
    if (!myHasCastle || !oppHasCastle) {
        const utDelta = mySubs.no_castle_ut - oppSubs.no_castle_ut;
        if (Math.abs(utDelta) >= THRESHOLD) {
            factors.push({ key: "no_castle_ut", delta: utDelta, text: utDelta > 0 ? "no Castle tech needed" : "needs a Castle unique tech" });
        }
    }

    // Speed (higher = faster = better)
    const spDelta = mySubs.speed - oppSubs.speed;
    if (Math.abs(spDelta) >= THRESHOLD) {
        factors.push({ key: "speed", delta: spDelta, text: spDelta > 0 ? "faster on the field" : "slower on the field" });
    }

    if (factors.length === 0) return null;

    // Sort by absolute delta descending, take top 3
    factors.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
    const top = factors.slice(0, 3);

    // Determine overall direction: positive factors = easier, negative = harder
    const avgDelta = top.reduce((sum, f) => sum + f.delta, 0) / top.length;
    const isUpside = avgDelta >= 0;

    const factorTexts = top.map((f) => f.text).join(" and ");
    let text;
    if (isUpside) {
        text = "Easier to mass \u2014 " + factorTexts;
    } else {
        text = "Harder to get going \u2014 " + factorTexts;
    }

    return { text, isUpside };
}
```

**Step 4: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: add ease helper functions for matchup advisor"
```

---

### Task 5: Integrate statements into `_buildComboCard`

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js:699-809` (`_buildComboCard`)

**Step 1: Update function signature**

Change line 699 to accept opponent ease data:

```javascript
function _buildComboCard(topItem, partner, partnerType, civName, gapResult, oppBestEase) {
```

`oppBestEase` is `{ subs: sub_scores_dict, hasCastle: boolean }` from the opponent's best combo, or `null`.

**Step 2: Add statements section after the gap row**

After the gap row block (after line 806, before `return card;`), add:

```javascript
    // Ease + combat context statements (only for combos with gaps)
    if (gapResult.gap.length > 0) {
        const mySubs = _avgEaseSubs(topItem, partner);
        const myHasCastle = !!(
            (topItem.entry.ease && topItem.entry.ease.is_castle_unit) ||
            (partner && partner.entry.ease && partner.entry.ease.is_castle_unit)
        );

        const combatCtx = _computeCombatContext(gapResult);
        const easeStmt = oppBestEase
            ? _computeEaseStatement(mySubs, oppBestEase.subs, myHasCastle, oppBestEase.hasCastle)
            : null;

        if (combatCtx || easeStmt) {
            const stmtDiv = document.createElement("div");
            let parts = [];
            if (combatCtx) parts.push(combatCtx);
            if (easeStmt) parts.push(easeStmt.text);

            if (parts.length > 0) {
                const cssClass = easeStmt
                    ? (easeStmt.isUpside ? "ma-ease-upside" : "ma-ease-downside")
                    : "ma-ease-neutral";
                stmtDiv.className = "ma-ease-statement " + cssClass;
                stmtDiv.textContent = parts.join(". ") + ".";
                card.appendChild(stmtDiv);
            }
        }
    }
```

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: add combat + ease statements to combo cards"
```

---

### Task 6: Update `_buildTopColumn` — pass opponent ease + sort by ease

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js:811-881` (`_buildTopColumn`)

**Step 1: Update function signature**

Change line 811 to accept opponent cards for ease comparison:

```javascript
function _buildTopColumn(topUnits, civName, oppGoldSlugs, side, unitsBySlug, oppBestEase) {
```

**Step 2: Add ease-based sort after dedup**

Replace lines 871-878 (the `anyPerfect` filter + `forEach`) with:

```javascript
    // If any card has zero gap, filter to only zero-gap cards
    const anyPerfect = cards.some((c) => c.gapSize === 0);
    let filtered = anyPerfect ? cards.filter((c) => c.gapSize === 0) : cards;

    // Sort: smallest gap first, then highest ease score
    filtered.sort((a, b) => {
        if (a.gapSize !== b.gapSize) return a.gapSize - b.gapSize;
        return _avgEase(b.item, b.partner) - _avgEase(a.item, a.partner);
    });

    filtered.forEach(({ item, partner, type, gapResult }) => {
        const card = _buildComboCard(item, partner, type, civName, gapResult, oppBestEase);
        col.appendChild(card);
    });
```

Note: `const filtered` becomes `let filtered` because we reassign after sort.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: sort combos by ease and pass opponent ease to cards"
```

---

### Task 7: Update `renderTopUnits` to compute and pass opponent ease

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js:390-438` (`renderTopUnits`)

**Step 1: Compute opponent's best combo ease after computing top units**

After line 412 (`const rightTop = ...`), add a helper to extract best combo ease from a side:

```javascript
    // Compute best combo ease for each side (to pass to opponent)
    function _bestComboEase(topUnits, side, unitsBySlug, oppGoldSlugs) {
        if (topUnits.length === 0) return null;
        const item = topUnits[0];
        // Find best partner (same logic as _buildTopColumn uses)
        const sidekicks = _computeSidekicks(item, side, unitsBySlug, oppGoldSlugs);
        const bestSidekick = sidekicks.length > 0 ? sidekicks[0] : null;
        const goldPartner = _computeGoldCombo(item, side, unitsBySlug, oppGoldSlugs);
        const sidekickGap = bestSidekick ? _computeComboGap(item.slug, bestSidekick.slug, side, oppGoldSlugs) : null;
        const goldGap = goldPartner ? _computeComboGap(item.slug, goldPartner.slug, side, oppGoldSlugs) : null;
        const soloGap = _computeComboGap(item.slug, null, side, oppGoldSlugs);

        let bestPartner = null;
        let bestGap = soloGap;
        if (sidekickGap && sidekickGap.gap.length <= bestGap.gap.length) { bestPartner = bestSidekick; bestGap = sidekickGap; }
        if (goldGap && goldGap.gap.length < bestGap.gap.length) { bestPartner = goldPartner; bestGap = goldGap; }

        const subs = _avgEaseSubs(item, bestPartner);
        const hasCastle = !!(
            (item.entry.ease && item.entry.ease.is_castle_unit) ||
            (bestPartner && bestPartner.entry.ease && bestPartner.entry.ease.is_castle_unit)
        );
        return { subs, hasCastle };
    }

    const leftBestEase = _bestComboEase(leftTop, "left", leftBySlug, rightGoldSlugs);
    const rightBestEase = _bestComboEase(rightTop, "right", rightBySlug, leftGoldSlugs);
```

**Step 2: Pass opponent ease to `_buildTopColumn`**

Update lines 429 and 433:

```javascript
    const leftCol = _buildTopColumn(leftTop, civLeft, rightGoldSlugs, "left", leftBySlug, rightBestEase);
    // ...
    const rightCol = _buildTopColumn(rightTop, civRight, leftGoldSlugs, "right", rightBySlug, leftBestEase);
```

Each side receives the *opponent's* best ease so it can compare against it.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: compute opponent ease and pass to column builders"
```

---

### Task 8: Add CSS styles for ease statements

**Files:**
- Modify: `webapp/static/css/matchup_advisor.css`

**Step 1: Add ease statement styles**

Add before the light mode overrides section (before line 528 `/* --- Light Mode Overrides --- */`):

```css
/* --- Ease statements on combo cards --- */
.ma-ease-statement {
    font-size: 0.68rem;
    line-height: 1.35;
    margin-top: 6px;
    padding: 5px 8px;
    border-radius: 6px;
    font-style: italic;
}
.ma-ease-upside {
    color: #7ebd7e;
    background: rgba(126, 189, 126, 0.08);
    border-left: 2px solid rgba(126, 189, 126, 0.3);
}
.ma-ease-downside {
    color: #d4856a;
    background: rgba(212, 133, 106, 0.08);
    border-left: 2px solid rgba(212, 133, 106, 0.3);
}
.ma-ease-neutral {
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.03);
    border-left: 2px solid rgba(255, 255, 255, 0.1);
}
```

**Step 2: Add light mode overrides**

Add inside the existing light mode section (after line 621 `[data-theme="light"] .ma-gold-combo-card`):

```css
[data-theme="light"] .ma-ease-upside {
    color: #3a7a3a;
    background: rgba(58, 122, 58, 0.06);
    border-left-color: rgba(58, 122, 58, 0.3);
}
[data-theme="light"] .ma-ease-downside {
    color: #a84832;
    background: rgba(168, 72, 50, 0.06);
    border-left-color: rgba(168, 72, 50, 0.3);
}
[data-theme="light"] .ma-ease-neutral {
    color: var(--text-muted);
    background: rgba(0, 0, 0, 0.02);
    border-left-color: rgba(0, 0, 0, 0.1);
}
```

**Step 3: Commit**

```bash
git add webapp/static/css/matchup_advisor.css
git commit -m "feat: add CSS styles for ease statements"
```

---

### Task 9: Manual smoke test

**Step 1: Start the webapp**

```bash
cd /home/claude-wukong/aoe2-unit-analyzer
python webapp/app.py
```

**Step 2: Verify in browser**

Open matchup advisor, select two civs (e.g., Britons vs Franks). Check:

1. Combo cards appear with statements below the gap row
2. Zero-gap combos are sorted easiest-first
3. Non-zero-gap combos show combat context + ease comparison
4. Statements have correct upside (green) / downside (red) styling
5. No JS console errors

**Step 3: Verify edge cases**

- Two civs where both have zero-gap combos (both should sort by ease, no statements)
- A civ with no gold unit wins (no combo cards, no crashes)
- Castle age mode (ease data should still be present)

**Step 4: Final commit if any fixes needed, then push**

```bash
git push origin main
```
