# Unified Combo Card Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the separate top unit card, sidekick sub-card, and gold combo card with a single unified combo card that shows categorized gap icons (complete loss, pop-only win, eco-only win).

**Architecture:** Frontend-only refactor of `matchup_advisor.js` and `matchup_advisor.css`. Two old render functions (`_buildTopCard`, `_buildGoldComboCard`) are replaced by one new `_buildComboCard`. A new `_computeComboGap` function categorizes each gap opponent by the best result either combo unit achieves. The `_buildTopColumn` orchestrator is rewritten to select the best partner (trash sidekick vs gold combo) per top unit and render unified combo cards.

**Tech Stack:** Vanilla JS (DOM manipulation), CSS3 (dashed borders for visual cues)

---

### Task 1: Add gap icon CSS classes

**Files:**
- Modify: `webapp/static/css/matchup_advisor.css:398-410` (after existing `.ma-beats-icon.loss`)

**Step 1: Add new gap icon styles**

Insert after line 410 (after `.ma-beats-icon.loss`):

```css
/* --- Gap icon categories (combo card) --- */
.ma-gap-icon {
    width: 20px;
    height: 20px;
    border-radius: 3px;
    object-fit: cover;
    background: rgba(0, 0, 0, 0.3);
    transition: transform 0.15s ease;
}
.ma-gap-icon:hover {
    transform: scale(1.3);
    z-index: 1;
}
.ma-gap-icon.gap-loss {
    border: 2px solid #e74c3c;
    opacity: 1;
}
.ma-gap-icon.gap-pop {
    border: 2px dashed #3498db;
    opacity: 0.8;
}
.ma-gap-icon.gap-eco {
    border: 2px dashed #f39c12;
    opacity: 0.8;
}
```

**Step 2: Add light mode overrides for gap icons**

Insert after line 643 (after `[data-theme="light"] .ma-beats-icon.loss`):

```css
[data-theme="light"] .ma-gap-icon {
    background: rgba(0, 0, 0, 0.06);
}
[data-theme="light"] .ma-gap-icon.gap-loss {
    border-color: #c0392b;
}
[data-theme="light"] .ma-gap-icon.gap-pop {
    border-color: #2980b9;
}
[data-theme="light"] .ma-gap-icon.gap-eco {
    border-color: #d38400;
}
```

**Step 3: Add gap row container style**

Insert after the gap icon styles (after `.ma-gap-icon.gap-eco`):

```css
.ma-combo-gap-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 6px;
    flex-wrap: wrap;
}
```

**Step 4: Verify visually**

Run: `cd ~/aoe2-unit-analyzer/webapp && python app.py`

Open browser, select two civs in Matchup Advisor, confirm no regressions (new classes aren't used yet).

**Step 5: Commit**

```bash
git add webapp/static/css/matchup_advisor.css
git commit -m "feat: add gap icon CSS classes for unified combo card"
```

---

### Task 2: Add `_computeComboGap` function

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js:571` (insert before `_computeGoldCombo`)

**Step 1: Write `_computeComboGap`**

Insert at line 571 (before `function _computeGoldCombo`):

```javascript
function _computeComboGap(topSlug, partnerSlug, side, oppGoldSlugs) {
    /**Compute categorized gap for a combo (top unit + partner).
     * For each opponent gold unit, find the best result from either unit.
     * Returns { covered: number, total: number, gap: [{slug, category}] }
     *
     * Categories:
     *   "loss" — neither unit wins either sim
     *   "pop"  — best result is pop-only win (30v30 win, 3k loss)
     *   "eco"  — best result is eco-only win (3k win, 30v30 loss)
     *
     * Cross-coverage: if one unit has pop_win and other has eco_win
     * against the same opponent, that opponent is covered (not in gap).
     */
    const sideData = simData[side];
    if (!sideData) return { covered: 0, total: oppGoldSlugs.size, gap: [] };

    const topD = sideData[topSlug] || {};
    const partD = partnerSlug ? (sideData[partnerSlug] || {}) : {};

    const topWins = new Set(topD.wins || []);
    const topPop = new Set(topD.pop_wins || []);
    const topEco = new Set(topD.eco_wins || []);

    const partWins = new Set(partD.wins || []);
    const partPop = new Set(partD.pop_wins || []);
    const partEco = new Set(partD.eco_wins || []);

    let covered = 0;
    const gap = [];

    for (const oppSlug of oppGoldSlugs) {
        // Full win by either unit
        if (topWins.has(oppSlug) || partWins.has(oppSlug)) {
            covered++;
            continue;
        }

        // Cross-coverage: one has pop, other has eco
        const anyPop = topPop.has(oppSlug) || partPop.has(oppSlug);
        const anyEco = topEco.has(oppSlug) || partEco.has(oppSlug);
        if (anyPop && anyEco) {
            covered++;
            continue;
        }

        // Partial — in the gap
        if (anyPop) {
            gap.push({ slug: oppSlug, category: "pop" });
        } else if (anyEco) {
            gap.push({ slug: oppSlug, category: "eco" });
        } else {
            gap.push({ slug: oppSlug, category: "loss" });
        }
    }

    return { covered, total: oppGoldSlugs.size, gap };
}
```

**Step 2: Verify no syntax errors**

Run: `cd ~/aoe2-unit-analyzer/webapp && python app.py`

Load the matchup advisor page — should still work identically (function isn't called yet).

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: add _computeComboGap for categorized gap analysis"
```

---

### Task 3: Add `_buildComboCard` function

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js` (insert after `_computeComboGap`, before the old `_buildTopColumn`)

**Step 1: Write `_buildComboCard`**

Insert after `_computeComboGap`:

```javascript
function _buildComboCard(topItem, partner, partnerType, civName, oppGoldSlugs, side) {
    /**Build a unified combo card.
     * @param topItem     — top unit object from _computeTopUnits
     * @param partner     — partner object (from _computeSidekicks or _computeGoldCombo), or null for solo
     * @param partnerType — "trash" | "gold" | null (solo)
     * @param civName     — civ name string
     * @param oppGoldSlugs — Set of opponent gold unit slugs
     * @param side        — "left" | "right"
     */
    const card = document.createElement("div");
    card.className = "ma-gold-combo-card";

    // Header
    const header = document.createElement("div");
    header.className = "ma-gold-combo-header";
    if (partnerType === "trash") {
        header.textContent = "Best Combo";
    } else if (partnerType === "gold") {
        header.textContent = "Gold Combo";
    } else {
        header.textContent = topItem.entry.unit_name;
    }
    card.appendChild(header);

    // Unit pair row
    const pairRow = document.createElement("div");
    pairRow.className = "ma-gold-combo-pair";

    // Civ emblem
    const emblem = document.createElement("img");
    emblem.src = CIV_EMBLEM_BASE + civName.toLowerCase() + ".png";
    emblem.className = "ma-unit-emblem";
    emblem.alt = civName;
    pairRow.appendChild(emblem);

    // Top unit icon + name
    const icon1 = document.createElement("img");
    icon1.className = "ma-unit-icon";
    const url1 = getIconUrl(topItem.entry.unit_name);
    if (url1) icon1.src = url1;
    icon1.alt = topItem.entry.unit_name;
    pairRow.appendChild(icon1);

    const name1 = document.createElement("span");
    name1.className = "ma-gold-combo-name";
    name1.textContent = topItem.entry.unit_name;
    pairRow.appendChild(name1);

    // Partner (if present)
    if (partner) {
        const plus = document.createElement("span");
        plus.className = "ma-gold-combo-plus";
        plus.textContent = "+";
        pairRow.appendChild(plus);

        const icon2 = document.createElement("img");
        icon2.className = "ma-unit-icon";
        const url2 = getIconUrl(partner.entry.unit_name);
        if (url2) icon2.src = url2;
        icon2.alt = partner.entry.unit_name;
        pairRow.appendChild(icon2);

        const name2 = document.createElement("span");
        name2.className = "ma-gold-combo-name";
        name2.textContent = partner.entry.unit_name;
        pairRow.appendChild(name2);
    }

    card.appendChild(pairRow);

    // Compute gap
    const partnerSlug = partner ? partner.slug : null;
    const gapResult = _computeComboGap(topItem.slug, partnerSlug, side, oppGoldSlugs);

    // Summary
    const summary = document.createElement("div");
    summary.className = "ma-gold-combo-summary";
    const verb = partner ? "Together handle" : "Handles";
    summary.innerHTML = verb + " <strong>" + gapResult.covered + "</strong> of " + gapResult.total + " opponent gold units";
    card.appendChild(summary);

    // Gap row (only if there are gap opponents)
    if (gapResult.gap.length > 0) {
        const gapRow = document.createElement("div");
        gapRow.className = "ma-combo-gap-row";

        const gapLabel = document.createElement("span");
        gapLabel.className = "ma-beats-label ma-label-loss";
        gapLabel.textContent = "Can't beat:";
        gapRow.appendChild(gapLabel);

        const gapIcons = document.createElement("div");
        gapIcons.className = "ma-beats-icons";

        // Sort: complete losses first, then pop, then eco
        const categoryOrder = { loss: 0, pop: 1, eco: 2 };
        gapResult.gap.sort((a, b) => categoryOrder[a.category] - categoryOrder[b.category]);

        gapResult.gap.forEach(({ slug, category }) => {
            const oppName = simData.name_map[slug] || slug;
            const url = getIconUrl(oppName);
            if (!url) return;
            const img = document.createElement("img");
            img.className = "ma-gap-icon gap-" + category;
            img.src = url;
            img.alt = oppName;
            img.title = oppName + (category === "loss" ? " (complete loss)" : category === "pop" ? " (pop win only)" : " (eco win only)");
            gapIcons.appendChild(img);
        });

        gapRow.appendChild(gapIcons);
        card.appendChild(gapRow);
    }

    return card;
}
```

**Step 2: Verify no syntax errors**

Run: `cd ~/aoe2-unit-analyzer/webapp && python app.py`

Load matchup advisor — should still work (function isn't called yet).

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: add _buildComboCard unified renderer"
```

---

### Task 4: Rewrite `_buildTopColumn` to use unified combo cards

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js:641-698` (replace entire `_buildTopColumn` function)

**Step 1: Replace `_buildTopColumn`**

Replace lines 641-698 with:

```javascript
function _buildTopColumn(topUnits, civName, oppGoldSlugs, side, unitsBySlug) {
    const col = document.createElement("div");
    col.className = "ma-top-col ma-top-col-" + side;

    if (topUnits.length === 0) {
        const empty = document.createElement("div");
        empty.className = "ma-top-empty";
        empty.textContent = "No gold unit wins";
        col.appendChild(empty);
        return col;
    }

    // For each top unit, find the best partner and render a combo card
    const cards = [];
    for (const item of topUnits) {
        // Try trash sidekick (best one only)
        const sidekicks = _computeSidekicks(item, side, unitsBySlug, oppGoldSlugs);
        const bestSidekick = sidekicks.length > 0 ? sidekicks[0] : null;

        // Try gold combo
        const goldPartner = _computeGoldCombo(item, side, unitsBySlug, oppGoldSlugs);

        // Compute gaps for each option
        const sidekickGap = bestSidekick
            ? _computeComboGap(item.slug, bestSidekick.slug, side, oppGoldSlugs)
            : null;
        const goldGap = goldPartner
            ? _computeComboGap(item.slug, goldPartner.slug, side, oppGoldSlugs)
            : null;
        const soloGap = _computeComboGap(item.slug, null, side, oppGoldSlugs);

        // Pick the best option: smallest gap, prefer sidekick on tie
        let bestPartner = null;
        let bestType = null;
        let bestGapSize = soloGap.gap.length;

        if (sidekickGap && sidekickGap.gap.length <= bestGapSize) {
            bestPartner = bestSidekick;
            bestType = "trash";
            bestGapSize = sidekickGap.gap.length;
        }
        if (goldGap && goldGap.gap.length < bestGapSize) {
            bestPartner = goldPartner;
            bestType = "gold";
            bestGapSize = goldGap.gap.length;
        }

        cards.push({ item, partner: bestPartner, type: bestType, gapSize: bestGapSize });
    }

    // If any card has zero gap, filter to only zero-gap cards
    const anyPerfect = cards.some((c) => c.gapSize === 0);
    const filtered = anyPerfect ? cards.filter((c) => c.gapSize === 0) : cards;

    filtered.forEach(({ item, partner, type }) => {
        const card = _buildComboCard(item, partner, type, civName, oppGoldSlugs, side);
        col.appendChild(card);
    });

    return col;
}
```

**Step 2: Verify visually**

Run: `cd ~/aoe2-unit-analyzer/webapp && python app.py`

Open matchup advisor, select two civs (e.g., Franks vs Britons). Verify:
- Top Units section renders unified combo cards
- Cards show "Best Combo" / "Gold Combo" / solo unit name as header
- Gap icons appear with correct border styles (solid red / dashed blue / dashed orange)
- Hover tooltips explain the category

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: rewrite _buildTopColumn to use unified combo cards"
```

---

### Task 5: Remove dead code — old `_buildTopCard` and `_buildGoldComboCard`

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js` (delete `_buildTopCard` at old lines 701-878 and `_buildGoldComboCard` at old lines 880-998)

**Step 1: Delete `_buildTopCard` function**

Delete the entire `function _buildTopCard(item, civName, oppGoldSlugs, sidekicks)` block (was lines 701-878). This includes all the sidekick sub-card rendering code inside it.

**Step 2: Delete `_buildGoldComboCard` function**

Delete the entire `function _buildGoldComboCard(topItem, partner, civName, oppGoldSlugs)` block (was lines 880-998).

**Step 3: Verify no regressions**

Run: `cd ~/aoe2-unit-analyzer/webapp && python app.py`

Open matchup advisor, select two civs. Verify everything still works — the old functions are no longer called by anything.

**Step 4: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "refactor: remove dead _buildTopCard and _buildGoldComboCard"
```

---

### Task 6: Remove dead CSS — old sidekick styles

**Files:**
- Modify: `webapp/static/css/matchup_advisor.css`

**Step 1: Delete dead sidekick CSS rules**

Delete these rule blocks:
- `.ma-sidekick-section` (line 475-482)
- `.ma-sidekick-card` (line 483-488)
- `.ma-sidekick-name-row` (line 489-493)
- `.ma-sidekick-label` (line 494-501)
- `.ma-sidekick-name` (line 502-506)
- `.ma-sidekick-summary` (line 507-511)
- `.ma-sidekick-summary strong` (line 512-515)
- `.ma-sidekick-covers-row` (line 516-518)
- `.ma-sidekick-gap-row` (line 519-525)
- `.ma-label-gap` (line 526-529)

Also delete these light mode overrides:
- `[data-theme="light"] .ma-sidekick-card` (line 657-660)
- `[data-theme="light"] .ma-sidekick-section` (line 661-663)

**Step 2: Delete dead top card CSS rules that are no longer used**

Delete these rules that were only used by `_buildTopCard`:
- `.ma-top-card` (line 443-448)
- `.ma-top-summary` (line 449-453)
- `.ma-top-summary strong` (line 454-457)
- `.ma-top-beats-row` (line 458-460)
- `.ma-top-loss-row` (line 461-467)

Also delete light mode override:
- `[data-theme="light"] .ma-top-card` (line 653-656)

**Step 3: Verify visually**

Run the app, select two civs, confirm no visual regressions.

**Step 4: Commit**

```bash
git add webapp/static/css/matchup_advisor.css
git commit -m "refactor: remove dead sidekick and old top card CSS"
```

---

### Task 7: Visual verification and edge cases

**Files:** None (manual testing only)

**Step 1: Test with diverse matchups**

Run: `cd ~/aoe2-unit-analyzer/webapp && python app.py`

Test these matchups and verify combo cards render correctly:
- **Franks vs Britons** (standard matchup with strong gold units on both sides)
- **Goths vs Aztecs** (infantry civs, check trash sidekick combos)
- **Mongols vs Persians** (CA vs elephants, likely gold combo scenarios)
- **Spanish vs Turks** (gunpowder matchup)

For each, verify:
1. Combo cards appear in Top Units section
2. Gap icons show correct border styles
3. Hover tooltips show category description
4. "Together handle X of Y" count is correct
5. No gap icons for opponents that are actually covered

**Step 2: Test Castle Age toggle**

Switch to Castle Age and verify cards update correctly.

**Step 3: Test age switch back to Imperial**

Switch back to Imperial and verify no stale data.

**Step 4: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address edge cases found during visual testing"
```
