# Sidekick Units Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** For each top unit in the matchup advisor, find the 2 best complementary "sidekick" units from the opposite resource pool that cover the top unit's weaknesses.

**Architecture:** Pure frontend — all data already exists in `simData`. Add a `_computeSidekicks()` function that scores candidates against the top unit's losses/draws, then extend `_buildTopCard()` to render sidekick sub-cards inline. Add CSS for the new sub-card styling.

**Tech Stack:** Vanilla JS (DOM manipulation), CSS

---

### Task 1: Include pop_wins/eco_wins in top unit objects

The current `_computeTopUnits()` returns objects with `losses` but not `pop_wins`/`eco_wins`. The sidekick scoring needs the top unit's draws to know what to score against.

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js:481-489`

**Step 1: Add pop_wins and eco_wins to the ranked.push() object**

In `_computeTopUnits()`, find the `ranked.push({...})` block at line 481-489. Change it to also include `goldPopWins` and `goldEcoWins`:

```javascript
        ranked.push({
            slug,
            entry,
            goldWins,
            goldWinCount: goldWins.length,
            goldPopWins,
            goldEcoWins,
            percentile: entry.percentile || 0,
            losses: d.losses || [],
            score,
        });
```

**Step 2: Verify nothing breaks**

Open the matchup advisor in browser, pick two civs, confirm "Top Units" section still renders correctly. The new fields are additive — existing code doesn't reference them yet.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: include pop_wins/eco_wins in top unit objects for sidekick scoring"
```

---

### Task 2: Add `_computeSidekicks()` function

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js` — insert new function after `_computeTopUnits()` (after line 499)

**Step 1: Write `_computeSidekicks()`**

Insert this function immediately after `_computeTopUnits()` (after line 499, before `_buildTopColumn()`):

```javascript
function _computeSidekicks(topItem, side, unitsBySlug, oppGoldSlugs) {
    /**Find the top 2 complementary sidekick units for a top unit.
     * Sidekick = opposite resource type (gold↔trash).
     * Scores against the top unit's losses and draws.**/
    const sideData = simData[side];
    if (!sideData) return [];

    const topIsGold = topItem.entry.stats && topItem.entry.stats.cost_gold > 0;

    // Top unit's weaknesses: losses + draws (opponent slugs)
    const topLosses = new Set((topItem.losses || []).filter((s) => oppGoldSlugs.has(s)));
    const topDraws = new Set([
        ...(topItem.goldPopWins || []),
        ...(topItem.goldEcoWins || []),
    ]);
    const allWeaknesses = new Set([...topLosses, ...topDraws]);

    if (allWeaknesses.size === 0) return [];

    // Score each candidate sidekick
    const ranked = [];
    for (const slug of Object.keys(sideData)) {
        const entry = unitsBySlug[slug];
        if (!entry) continue;
        if (slug === topItem.slug) continue;

        // Strict gold↔trash: sidekick must be opposite cost type
        const isGold = entry.stats && entry.stats.cost_gold > 0;
        if (isGold === topIsGold) continue;

        const d = sideData[slug];
        const skWins = new Set(d.wins || []);
        const skDraws = new Set([...(d.pop_wins || []), ...(d.eco_wins || [])]);

        let score = 0;
        const covered = [];

        for (const opp of topLosses) {
            if (skWins.has(opp)) { score += 3; covered.push(opp); }
            else if (skDraws.has(opp)) { score += 2; covered.push(opp); }
        }
        for (const opp of topDraws) {
            if (skWins.has(opp)) { score += 2; covered.push(opp); }
            else if (skDraws.has(opp)) { score += 1; covered.push(opp); }
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

    return ranked.slice(0, 2);
}
```

**Step 2: Verify no syntax errors**

Open browser console, reload the page, confirm no JS errors.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: add _computeSidekicks() scoring function"
```

---

### Task 3: Wire sidekick computation into rendering

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js` — modify `_buildTopColumn()` and `_buildTopCard()` signatures

**Step 1: Update `renderTopUnits()` to pass `side` and `unitsBySlug` to `_buildTopColumn()`**

In `renderTopUnits()`, change the two `_buildTopColumn` calls (lines 429, 433) to also pass `side` and `unitsBySlug`:

```javascript
    // Left side
    const leftCol = _buildTopColumn(leftTop, civLeft, rightGoldSlugs, "left", leftBySlug);
    body.appendChild(leftCol);

    // Right side
    const rightCol = _buildTopColumn(rightTop, civRight, leftGoldSlugs, "right", rightBySlug);
    body.appendChild(rightCol);
```

**Step 2: Update `_buildTopColumn()` to accept and forward new params**

Change the function signature at line 501 and update the inner `_buildTopCard` call:

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

    topUnits.forEach((item) => {
        const sidekicks = _computeSidekicks(item, side, unitsBySlug, oppGoldSlugs);
        const card = _buildTopCard(item, civName, oppGoldSlugs, sidekicks);
        col.appendChild(card);
    });

    return col;
}
```

**Step 3: Update `_buildTopCard()` to accept sidekicks param**

Change the signature at line 521 from:
```javascript
function _buildTopCard(item, civName, oppGoldSlugs) {
```
to:
```javascript
function _buildTopCard(item, civName, oppGoldSlugs, sidekicks) {
```

At the end of `_buildTopCard()`, before `return card;` (line 606), add sidekick sub-cards:

```javascript
    // Sidekick sub-cards
    if (sidekicks && sidekicks.length > 0) {
        const skSection = document.createElement("div");
        skSection.className = "ma-sidekick-section";

        sidekicks.forEach((sk, idx) => {
            const skCard = document.createElement("div");
            skCard.className = "ma-sidekick-card";

            // Name row: icon + label + name
            const skNameRow = document.createElement("div");
            skNameRow.className = "ma-sidekick-name-row";

            const skLabel = document.createElement("span");
            skLabel.className = "ma-sidekick-label";
            skLabel.textContent = idx === 0 ? "Best Sidekick:" : "Alt Sidekick:";

            const skIcon = document.createElement("img");
            skIcon.className = "ma-unit-icon";
            const skIconUrl = getIconUrl(sk.entry.unit_name);
            if (skIconUrl) skIcon.src = skIconUrl;
            skIcon.alt = sk.entry.unit_name;

            const skName = document.createElement("span");
            skName.className = "ma-sidekick-name";
            skName.textContent = sk.entry.unit_name;

            skNameRow.appendChild(skLabel);
            skNameRow.appendChild(skIcon);
            skNameRow.appendChild(skName);
            skCard.appendChild(skNameRow);

            // Summary: "Covers X of Y weaknesses"
            const skSummary = document.createElement("div");
            skSummary.className = "ma-sidekick-summary";
            skSummary.innerHTML = "Covers <strong>" + sk.covered.length + "</strong> of " + sk.totalWeaknesses + " weaknesses";
            skCard.appendChild(skSummary);

            // Covered icons row
            if (sk.covered.length > 0) {
                const covRow = document.createElement("div");
                covRow.className = "ma-sidekick-covers-row";
                const covIcons = document.createElement("div");
                covIcons.className = "ma-beats-icons";
                sk.covered.forEach((oppSlug) => {
                    const oppName = simData.name_map[oppSlug] || oppSlug;
                    const url = getIconUrl(oppName);
                    if (!url) return;
                    const img = document.createElement("img");
                    img.className = "ma-beats-icon";
                    img.src = url;
                    img.alt = oppName;
                    img.title = oppName;
                    covIcons.appendChild(img);
                });
                covRow.appendChild(covIcons);
                skCard.appendChild(covRow);
            }

            // Gap icons row — "Neither can beat:"
            if (sk.gap.length > 0) {
                const gapRow = document.createElement("div");
                gapRow.className = "ma-sidekick-gap-row";
                const gapLabel = document.createElement("span");
                gapLabel.className = "ma-beats-label ma-label-gap";
                gapLabel.textContent = "Neither can beat:";
                gapRow.appendChild(gapLabel);

                const gapIcons = document.createElement("div");
                gapIcons.className = "ma-beats-icons";
                sk.gap.forEach((oppSlug) => {
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
                skCard.appendChild(gapRow);
            }

            skSection.appendChild(skCard);
        });

        card.appendChild(skSection);
    }
```

**Step 4: Verify in browser**

Open matchup advisor, pick Franks vs Bohemians, confirm sidekick sub-cards appear below each top unit card. Check that:
- Sidekick names and icons render
- "Covers X of Y weaknesses" text appears
- Covered and gap icon rows display correctly
- No JS console errors

**Step 5: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "feat: wire sidekick computation into top unit card rendering"
```

---

### Task 4: Add CSS styles for sidekick sub-cards

**Files:**
- Modify: `webapp/static/css/matchup_advisor.css` — insert after `.ma-top-empty` (after line 474), before `/* --- Light Mode Overrides --- */`

**Step 1: Add dark theme (default) sidekick styles**

Insert after line 474 (after `.ma-top-empty` block), before the `/* --- Light Mode Overrides --- */` comment:

```css
.ma-sidekick-section {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.ma-sidekick-card {
    padding: 6px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.04);
}
.ma-sidekick-name-row {
    display: flex;
    align-items: center;
    gap: 4px;
}
.ma-sidekick-label {
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
}
.ma-sidekick-name {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text);
}
.ma-sidekick-summary {
    font-size: 0.68rem;
    color: var(--text-muted);
    margin: 2px 0;
}
.ma-sidekick-summary strong {
    color: var(--gold);
    font-weight: 700;
}
.ma-sidekick-covers-row {
    margin-top: 2px;
}
.ma-sidekick-gap-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    flex-wrap: wrap;
}
.ma-label-gap {
    color: #e74c3c;
    font-size: 0.62rem;
}
```

**Step 2: Add light mode overrides**

After the existing `[data-theme="light"] .ma-top-card` rule (line 554-557), add:

```css
[data-theme="light"] .ma-sidekick-card {
    background: rgba(0, 0, 0, 0.03);
    border-color: rgba(0, 0, 0, 0.05);
}
[data-theme="light"] .ma-sidekick-section {
    border-top-color: rgba(0, 0, 0, 0.08);
}
```

**Step 3: Verify styling in browser**

Check both dark and light themes. Sidekick sub-cards should be visually nested — slightly lighter/subtler than the parent top card, with clear separation.

**Step 4: Commit**

```bash
git add webapp/static/css/matchup_advisor.css
git commit -m "feat: add CSS styles for sidekick sub-cards"
```

---

### Task 5: Visual verification and final commit

**Step 1: Full end-to-end verification**

Open the matchup advisor and test with at least 3 civ pairs:
- Franks vs Bohemians (strong cavalry vs ranged)
- Britons vs Turks (archer vs gunpowder)
- Japanese vs Goths (infantry vs infantry spam)

For each, verify:
1. Top unit cards still render correctly with all existing info
2. Sidekick sub-cards appear below top units
3. Sidekick is opposite cost type (trash for gold top units, gold for trash)
4. "Covers X of Y" count matches the number of covered icons shown
5. "Neither can beat:" row only appears when there are gap units
6. No JS console errors
7. Both dark and light themes look correct
8. Mobile/responsive layout doesn't break (resize window to < 600px)

**Step 2: If any issues found, fix and commit**

**Step 3: Final squash or clean commit if needed**
