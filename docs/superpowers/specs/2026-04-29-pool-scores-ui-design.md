# Pool Scores UI Integration — Design

**Status:** Implemented. **2026-04-29 update:** axis toggle removed from
v1 UI (HP-only). Cost and Speed axes are still computed in
`pool_scores.db` and returned in the API payload, but the UI hides them
because their rankings disagree with HP in ways that aren't useful to
surface yet (e.g., "cheap halberdiers rank well on cost but poorly on
HP"). Re-enabling is a UI change only — the lib code, schema, and API
all still support all three axes.

**Predecessor:** `2026-04-28-pool-ranking-redesign-design.md` (DB-generation stage,
implemented in commits `3bd3f6c..ca860fc`).

## Goal

Surface the six new pool-scores flavors (3 axes × 2 scales) on the
existing **Unit Rankings** page (`/`, `index.html`) via two
radio-button toggles. The score column and role-component breakdown
update live based on toggle state. No new page, no new server
roundtrips on toggle change.

## ✅ Locked-in design

### Toggles

Two radio-button groups added to `index.html`, between the Castle/
Imperial age toggle and the line tabs:

```
Score axis:    HP%   Resource cost   Speed              ← default HP%
Scale:         Pop   Cost   Average                     ← default Average
```

State is **transient** — not persisted in URL, sessionStorage, or
cookies. Refresh resets to defaults. (May revisit if users complain.)

The two toggles together select one of nine display values per unit:

| axis × scale | display value |
| --- | --- |
| HP × Pop | `pop_hp_score` |
| HP × Cost | `cost_hp_score` |
| HP × Average | `(pop_hp + cost_hp) / 2` |
| Cost × Pop | `pop_cost_score` |
| Cost × Cost | `cost_cost_score` |
| Cost × Average | `(pop_cost + cost_cost) / 2` |
| Speed × Pop | `pop_speed_score` |
| Speed × Cost | `cost_speed_score` |
| Speed × Average | `(pop_speed + cost_speed) / 2` |

Average is a naive arithmetic mean. Each axis's two values use
identical units (e.g. both pop_cost and cost_cost are weighted
resource counts), so the mean is meaningful. The role components
(GC/AC/AT/AA) are averaged the same way.

### Table columns

The existing line-tab structure stays. Within a tab, the current
table layout is preserved, except the score columns change for the
three covered pools:

**Removed (for infantry/stable/archer pools only):**
- `general_combat`, `anti_cav`, `anti_trash` (infantry)
- `ranged_effectiveness`, `anti_archer` (archery)
- `stable_effectiveness`, plus stable-specific columns

**Added:**
- `Score` — toggle-driven number (HP / Cost / Speed × Pop / Cost / Avg)
- `GC` — General Combat role mean
- `AC` / `AT` / `AA` — pool-specific role columns (only the ones that
  apply to the current pool; e.g. archer pool shows `GC + AA`, infantry
  shows `GC + AC + AT`, stable shows `GC + AC`)

**Unchanged:**
- All existing stats columns (HP, attack, melee armor, pierce armor,
  range, speed, reload, costs)
- Existing tech / unique-effect hover cards on civ and unit cells

### Score column behavior

- **Display:** raw computed value, two decimal places. **No
  normalization, no pool ranking, no median_delta.** Whatever the
  axis produces (e.g. HP +8.9, cost 3961.8, speed +1.2) is what's
  shown.
- **Sort direction:** descending by default for HP and Speed
  (higher = better), ascending for Cost (lower = better).
- **Header text:** updates with the toggle, e.g. `Score (HP, Avg)`,
  `Cost (Pop, lower=better)`, `Speed (Avg)`.
- **No speed or range weighting** in the score derivation. The
  pool-scores formula is `0.7×GC + 0.15×AC + 0.15×AT` for infantry,
  `0.7×GC + 0.30×AC` for stable, `0.7×GC + 0.30×AA` for archer —
  speed and range never enter the calculation. (This is a deliberate
  divergence from the legacy `derive_unit_rankings.py` pipeline,
  which speed-weighted some sub-lines.)

### Hover card content

The Score cell hover shows the **shape descriptors** for that unit at
the active scale:

- For Pop or Cost scale: descriptors from that scale's row.
- For Average scale: descriptors from both rows side-by-side
  (otherwise an "average shape" would be misleading).

Hover content includes:

```
Berserker — HP × Pop
final +8.9    GC −6.8   AC −1.6   AT +92.7
n=269   win 61.7%   cat-loss 27.1%   stddev 59.5
```

The GC / AC / AT / AA cell hovers explain the role's methodology in
the new system, replacing the legacy explanations:

```
GC (General Combat)
Average across militia, knight, and archer line opponents.
Within each line: mean adjusted_signed_score (λ=2 loss aversion),
deduped by fingerprint. Across lines: equally weighted mean.
```

A new top-level Score column hover explains the active axis and scale
combo and the loss-aversion convention. For the cost axis the hover
calls out "lower is better, units = weighted resources lost".

Existing tech and unique-effect hovers on civ and unit cells are
**preserved unchanged** — they're a separate concern from scoring.

### Pool coverage

The new toggles drive scoring for **infantry, stable, and archer**
tabs only — the three pools covered by `pool_scores.db`.

For **siege** and **naval** tabs:
- Continue to use the legacy `battle_scores` data and the existing
  composite columns (`anti_building_score`, `naval_effectiveness`,
  etc.).
- The new toggle UI is **hidden** on these tabs (not just disabled —
  hiding avoids the "why is this greyed out" question).
- A small note under the line-tabs reads "Toggles apply to infantry,
  stable, and archer pools (the three covered by the new ranking).
  Siege and naval still use the legacy composite score."
- When the user switches back to a covered tab, toggles reappear in
  their previous state.

This keeps existing siege/naval rankings intact while we extend pool
coverage in a future stage.

### Sub-line filters (existing behavior)

The current page lets users filter sub-lines within a tab (e.g. show
only militia + spear-line units within the infantry tab). This **stays
as-is** — the filter just hides rows; the pool-score values per
unit don't change. No new behavior needed.

### Default sort

When the user lands on a covered tab, the table sorts by the Score
column in the natural direction for the active axis (descending for
HP/speed, ascending for cost). Clicking the Score header flips
direction. Clicking any other column header behaves as today.

## Architecture & data flow

```
pool_scores.db.pool_scores  ──┐
                              ├─► /api/ref/unit-line/<slug>  ──► rankings.js
aoe2_reference.db.ref_units ──┘                                  (toggles, render, hover)
```

### API extension

The existing `/api/ref/unit-line/<line_slug>` endpoint already returns
one row per civ-unit with stats and legacy composite scores. We
**extend** it (don't add a new endpoint):

For each unit row, when the line maps to a covered pool, attach a
`pool_scores` field:

```json
{
  "civ_name": "Vikings",
  "unit_slug": "elite_berserk_vikings",
  "final_hp": 81,
  ...existing stats and legacy scores...
  "pool_scores": {
    "pool": "infantry",
    "scales": {
      "30v30": {
        "hp":   {"final": 8.9,  "gc": -6.8, "ac": -1.6, "at": 92.7},
        "cost": {"final": 3961.8, "gc": 4485.6, "ac": 5270.4, "at": 208.8},
        "speed":{"final": 1.2,  "gc": -9.8, "ac": -5.5, "at": 59.0},
        "shape": {"n": 269, "win_rate": 61.7, "decisive_win_rate": 53.4,
                  "big_win_rate": 47.1, "catastrophic_loss_rate": 27.1,
                  "stddev": 59.5, "mean": 35.2}
      },
      "3k": { ...same shape... }
    }
  }
}
```

For units in lines not covered by pool_scores (siege/naval, or any
unit whose `unit_to_pool()` returns None), the `pool_scores` key is
omitted entirely. The frontend uses presence/absence of this key to
decide whether to show the new toggle UI.

### Frontend state machine

Toggle changes are **pure client-side**. The full per-unit
`pool_scores` payload is fetched once per tab; toggling axis/scale just
re-reads the same data and re-renders the score column + hover.

```
fetch /api/ref/unit-line/infantry  →  cache rows
toggle axis=HP, scale=Avg          →  for each row, score = (pop_hp + cost_hp)/2
                                      role.gc = (pop_gc + cost_gc)/2 etc.
                                      re-sort and re-render table
toggle scale=Pop                   →  for each row, score = pop_hp
                                      role.gc = pop_gc etc.
                                      re-sort and re-render table
```

### Hover card data

Shape descriptors for each scale come from the same `pool_scores`
payload. The hover renderer picks fields based on the active toggle
state:

```js
function buildScoreHover(unitRow, axis, scale) {
  const ps = unitRow.pool_scores;
  if (!ps) return null;  // legacy or out-of-pool unit
  if (scale === "average") {
    return renderTwoColumnShape(ps.scales["30v30"], ps.scales["3k"], axis);
  }
  return renderShape(ps.scales[scale === "pop" ? "30v30" : "3k"], axis);
}
```

## Out of scope (deferred)

- **Profile labels** (DOMINANT / RELIABLE / WEAK / etc.) — the spec
  defines them but we don't surface them in v1. Shape descriptors in
  the hover are enough.
- **Cleaning up legacy `battle_scores` data and the
  `derive_unit_rankings.py` pipeline** — separate "deprecate legacy"
  task. Both pipelines coexist during transition.
- **Persisting toggle state** across sessions — transient for v1.
- **Adding siege/naval pools to `pool_scores.db`** — future stage;
  needs new role-formula brainstorming.
- **Cross-unit normalization or rank columns** — explicitly excluded
  per "no normalization on the score" decision.

## Non-goals

- Replacing or removing the legacy `battle_scores` table from
  `derived_data.db`. Both data sources coexist.
- Touching the matchup-advisor recommendations
  (`advisor_recommendations` table).
- Re-running matchup simulations.

## Testing strategy

- **Backend:** unit tests for the API extension — given a unit in a
  covered pool, the `pool_scores` field is present with the expected
  six final scores; given an out-of-pool unit, the field is omitted.
- **Frontend:** snapshot the DOM produced by the renderer for the
  three pools × axis/scale combinations. Smoke-test toggle clicks
  trigger re-render and re-sort.
- **Reference unit:** Viking Elite Berserk's `pool_scores` payload
  must match the values pinned in
  `tests/test_pool_scores_integration.py` (HP +8.9 / +31.6, cost
  3961.8 / 2506.9, speed +1.20 / +26.60).

## Reference values (display-time check)

When the implementation is done, the Berserker row on the **infantry
tab** should display, with default toggles (HP × Average):

- **Score:** `+20.25` (= (8.9 + 31.6) / 2)
- **GC:** `+5.28` (= (−6.8 + 17.4) / 2)
- **AC:** `+17.6` (= (−1.6 + 36.8) / 2)
- **AT:** `+92.8` (= (92.7 + 92.9) / 2)
- Hover shows Pop and 3k shape side-by-side.

Switching to **HP × Pop** should display Score `+8.9`, GC `−6.8`,
AC `−1.6`, AT `+92.7`. Switching to **Cost × Pop** should display
Score `3961.8` (sorted ascending across the table). Switching to
**Speed × Cost** should display Score `+26.6`.
