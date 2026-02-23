# Double Gold Combo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When no top unit + sidekick combo fully covers all opponent gold units, show a "Best Gold Combo" card with two gold units that together handle the most opponents.

**Architecture:** Pure frontend — all data already exists in `simData`. Add `_computeGoldCombo()` that scores gold partners against the #1 top unit's weaknesses. Modify `_buildTopColumn()` to detect all-gaps condition and prepend a combo card. Add CSS for the combo card styling.

**Tech Stack:** Vanilla JS (DOM manipulation), CSS

---

### Task 1: Add `_computeGoldCombo()` function

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js` — insert new function after `_computeSidekicks()` (after line 571)

**Step 1: Write `_computeGoldCombo()`**

Insert this function immediately after `_computeSidekicks()` (after line 571, before `_buildTopColumn()` at line 573):

```javascript
function _computeGoldCombo(topItem, side, unitsBySlug, oppGoldSlugs) {
    /**Find the best gold unit partner for a top unit.
     * Same scoring as sidekicks but partner must be gold (not opposite cost type).
     * Used when no gold+trash sidekick can fully cover.**/
    const sideData = simData[side];
    if (!sideData) return null;

    // Top unit's weaknesses: losses + draws (opponent gold slugs)
    const topLosses = new Set((topItem.losses || []).filter((s) => oppGoldSlugs.has(s)));
    const topDraws = new Set([
        ...(topItem.goldPopWins || []),
        ...(topItem.goldEcoWins || []),
    ]);
    const allWeaknesses = new Set([...topLosses, ...topDraws]);

    if (allWeaknesses.size === 0) return null;

    // Score each gold unit as partner
    const ranked = [];
    for (const slug of Object.keys(sideData)) {
        const entry = unitsBySlug[slug];
        if (!entry) continue;
        if (slug === topItem.slug) continue;

        // Partner must be gold
        const isGold = !!(entry.stats && entry.stats.cost_gold > 0);
        if (!isGold) continue;

        const d = sideData[slug];
        const pWins = new Set(d.wins || []);
        const pDraws = new Set([...(d.pop_wins || []), ...(d.eco_wins || [])]);

        let score = 0;
        const covered = [];

        for (const opp of topLosses) {
            if (pWins.has(opp)) { score += 3; covered.push(opp); }
            else if (pDraws.has(opp)) { score += 2; covered.push(opp); }
        }
        for (const opp of topDraws) {
            if (pWins.has(opp)) { score += 2; covered.push(opp); }
            else if (pDraws.has(opp)) { score += 1; covered.push(opp); }
        }

        if (score === 0) continue;

        const coveredSet = new Set(covered);
        const gap = [...allWeaknesses].filter((s) => !coveredSet.has(s));

        ranked.push({
            slug,
            entry,
            score,
            percentile: entry.percentile || 0,
            covered,
            gap,
            totalWeaknesses: allWeaknesses.size,
        });
    }

    ranked.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return b.percentile - a.percentile;
    });

    return ranked.length > 0 ? ranked[0] : null;
}
```

**Step 2: Verify no syntax errors**

Open browser console, reload the page, confirm no JS errors.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: add _computeGoldCombo() function for double-gold pair scoring"
```

---

### Task 2: Wire gold combo into `_buildTopColumn()`

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js` — modify `_buildTopColumn()` at line 573

**Step 1: Add gap-checking logic and combo card generation**

Replace `_buildTopColumn()` (lines 573-591) with:

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

    // Compute sidekicks for each top unit and check if ALL have gaps
    const topWithSidekicks = topUnits.map((item) => {
        const sidekicks = _computeSidekicks(item, side, unitsBySlug, oppGoldSlugs);
        return { item, sidekicks };
    });

    const allHaveGaps = topWithSidekicks.every(({ sidekicks }) => {
        if (sidekicks.length === 0) return true; // no sidekick = gap
        return sidekicks[0].gap.length > 0; // best sidekick has gap
    });

    // If all combos have gaps, try double-gold combo with #1 top unit
    if (allHaveGaps && topUnits.length > 0) {
        const combo = _computeGoldCombo(topUnits[0], side, unitsBySlug, oppGoldSlugs);
        if (combo) {
            const comboCard = _buildGoldComboCard(topUnits[0], combo, civName, oppGoldSlugs);
            col.appendChild(comboCard);
        }
    }

    // Render top unit cards (with sidekicks already computed)
    topWithSidekicks.forEach(({ item, sidekicks }) => {
        const card = _buildTopCard(item, civName, oppGoldSlugs, sidekicks);
        col.appendChild(card);
    });

    return col;
}
```

**Step 2: Verify no syntax errors** (the `_buildGoldComboCard` function doesn't exist yet — just confirm no other errors)

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: wire gold combo detection into _buildTopColumn()"
```

---

### Task 3: Add `_buildGoldComboCard()` rendering function

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js` — insert after `_buildTopCard()` (after line 770, before the `/* ---- Rendering ---- */` comment)

**Step 1: Write `_buildGoldComboCard()`**

Insert after `_buildTopCard()`:

```javascript
function _buildGoldComboCard(topItem, partner, civName, oppGoldSlugs) {
    const card = document.createElement("div");
    card.className = "ma-gold-combo-card";

    // Header label
    const header = document.createElement("div");
    header.className = "ma-gold-combo-header";
    header.textContent = "Best Gold Combo";
    card.appendChild(header);

    // Unit pair row: both icons + names
    const pairRow = document.createElement("div");
    pairRow.className = "ma-gold-combo-pair";

    // Civ emblem (once)
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

    // "+" separator
    const plus = document.createElement("span");
    plus.className = "ma-gold-combo-plus";
    plus.textContent = "+";
    pairRow.appendChild(plus);

    // Partner icon + name
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

    card.appendChild(pairRow);

    // Summary: "Together cover X of Y opponent gold units"
    const totalOppGold = oppGoldSlugs.size;
    const topWins = new Set(topItem.goldWins || []);
    const topDraws = new Set([
        ...(topItem.goldPopWins || []),
        ...(topItem.goldEcoWins || []),
    ]);
    const partnerCovered = new Set(partner.covered || []);
    const allCovered = new Set([...topWins, ...topDraws, ...partnerCovered]);
    // Also add top unit's wins (which aren't weaknesses and thus aren't in partner.covered)
    const totalCovered = allCovered.size;

    const summary = document.createElement("div");
    summary.className = "ma-gold-combo-summary";
    summary.innerHTML = "Together cover <strong>" + totalCovered + "</strong> of " + totalOppGold + " opponent gold units";
    card.appendChild(summary);

    // Covered icons (all opponent gold units that at least one of the pair handles)
    const covIcons = document.createElement("div");
    covIcons.className = "ma-beats-icons";
    for (const oppSlug of allCovered) {
        const oppName = simData.name_map[oppSlug] || oppSlug;
        const url = getIconUrl(oppName);
        if (!url) continue;
        const img = document.createElement("img");
        img.className = "ma-beats-icon";
        img.src = url;
        img.alt = oppName;
        img.title = oppName;
        covIcons.appendChild(img);
    }
    card.appendChild(covIcons);

    // Gap row — opponent gold units neither can beat
    const allCoveredSet = allCovered;
    const comboGap = [];
    for (const oppSlug of oppGoldSlugs) {
        if (!allCoveredSet.has(oppSlug)) comboGap.push(oppSlug);
    }
    if (comboGap.length > 0) {
        const gapRow = document.createElement("div");
        gapRow.className = "ma-sidekick-gap-row";
        const gapLabel = document.createElement("span");
        gapLabel.className = "ma-beats-label ma-label-gap";
        gapLabel.textContent = "Can't beat:";
        gapRow.appendChild(gapLabel);

        const gapIcons = document.createElement("div");
        gapIcons.className = "ma-beats-icons";
        comboGap.forEach((oppSlug) => {
            const oppName = simData.name_map[oppSlug] || oppSlug;
            const url = getIconUrl(oppName);
            if (!url) return;
            const img = document.createElement("img");
            img.className = "ma-beats-icon loss";
            img.src = url;
            img.alt = oppName;
            img.title = oppName;
            gapIcons.appendChild(img);
        });
        gapRow.appendChild(gapIcons);
        card.appendChild(gapRow);
    }

    return card;
}
```

**Step 2: Verify in browser**

Open matchup advisor, pick two civs where all top+sidekick combos have gaps. The gold combo card should appear above the top unit cards.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: add _buildGoldComboCard() rendering function"
```

---

### Task 4: Add CSS styles for gold combo card

**Files:**
- Modify: `webapp/static/css/matchup_advisor.css` — insert after `.ma-label-gap` (after line 529), before `/* --- Light Mode Overrides --- */`

**Step 1: Add dark theme (default) gold combo styles**

Insert after line 529 (after `.ma-label-gap` block), before the `/* --- Light Mode Overrides --- */` comment:

```css
.ma-gold-combo-card {
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(218, 165, 32, 0.08);
    border: 1px solid rgba(218, 165, 32, 0.25);
    margin-bottom: 10px;
}
.ma-gold-combo-header {
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--gold);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 6px;
}
.ma-gold-combo-pair {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
    margin-bottom: 4px;
}
.ma-gold-combo-name {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text);
}
.ma-gold-combo-plus {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--gold);
    margin: 0 2px;
}
.ma-gold-combo-summary {
    font-size: 0.72rem;
    color: var(--text-muted);
    margin: 4px 0;
}
.ma-gold-combo-summary strong {
    color: var(--gold);
    font-weight: 700;
}
```

**Step 2: Add light mode overrides**

After the existing `[data-theme="light"] .ma-sidekick-section` rule (line 619), add:

```css
[data-theme="light"] .ma-gold-combo-card {
    background: rgba(218, 165, 32, 0.06);
    border-color: rgba(218, 165, 32, 0.2);
}
```

**Step 3: Verify styling in browser**

Check both dark and light themes. The gold combo card should have a subtle golden accent, visually distinct from the regular top unit cards below it.

**Step 4: Commit**

```bash
git add webapp/static/css/matchup_advisor.css
git commit -m "feat: add CSS styles for gold combo card"
```

---

### Task 5: Visual verification

**Step 1: Full end-to-end verification**

Open the matchup advisor and test with civ pairs:
- Find a pair where all top+sidekick combos have gaps — verify the gold combo card appears above top unit cards
- Find a pair where at least one top+sidekick has no gap — verify the gold combo card does NOT appear
- Verify the "Together cover X of Y" count is correct
- Verify covered and gap icon rows display correctly
- Check both dark and light themes
- No JS console errors

**Step 2: If any issues found, fix and commit**
