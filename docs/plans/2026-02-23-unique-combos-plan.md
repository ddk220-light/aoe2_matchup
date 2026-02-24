# Unique Combo Deduplication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent duplicate combo cards where the same two units appear with swapped top/partner roles.

**Architecture:** Add a seen-pairs filter in `_buildTopColumn` after card construction, before zero-gap filtering. Normalize pairs by sorting slugs so `(A,B)` and `(B,A)` produce the same key.

**Tech Stack:** Vanilla JavaScript (no build step, no test runner)

---

### Task 1: Add unique combo filter to `_buildTopColumn`

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js:858-863`

**Step 1: Add the dedup filter**

In `_buildTopColumn`, after line 858 (where cards are pushed) and before line 862 (zero-gap filter), insert:

```javascript
    // Deduplicate: drop cards with the same unit pair in swapped roles
    const seenPairs = new Set();
    cards = cards.filter((c) => {
        if (!c.partner) return true;
        const key = [c.item.slug, c.partner.slug].sort().join("|");
        if (seenPairs.has(key)) return false;
        seenPairs.add(key);
        return true;
    });
```

The `cards` array is ordered by top unit score (from `topUnits` which is pre-sorted), so the first card with a given pair is always the higher-scored one.

**Step 2: Manual verification**

1. Run the Flask app: `cd ~/aoe2-unit-analyzer && python webapp/app.py`
2. Open the matchup advisor page
3. Pick two civs that previously showed duplicate combos
4. Verify only one card appears per unique unit pair
5. Verify solo cards (no partner) still appear normally

**Step 3: Commit**

```bash
git add webapp/static/js/matchup_advisor.js
git commit -m "fix: deduplicate combo cards with swapped unit pairs"
```
