# New Pool Ranking Score — Design (in progress)

**Status:** Brainstorming, partial. Locked-in sections marked ✅. Open
questions tracked at the bottom and will be resolved before the
implementation plan is written.

## Goal

Replace the current pool-normalized composite ranking
(`derived_data.battle_scores`) with a new score that:

1. Uses **two separate axes** per unit — one for population-limited
   battles (30v30) and one for cost-matched battles (3k). The
   population axis answers "how good is this unit when both players
   field equal numbers"; the cost axis answers "how good is this unit
   when both players spend equal resources".
2. Aggregates raw signed-score outcomes from `matchup_db.matchup_battles`
   directly via mean (no pool normalization, no speed multiplier) so
   each axis is interpretable as expected signed_score against a
   uniformly-random opponent in the role pool.
3. Reports both a **headline score** (the mean) and **shape
   descriptors** (stddev, win-rate, etc.) so the UI can label units as
   DOMINANT / RELIABLE / HARD-COUNTERED / NICHE / etc., showing
   players whether the score is consistent or hides hard counters.

The redesign starts with infantry. The same machinery extends to
ranged and stable pools in later passes (open question — see below).

## Locked-in design

### ✅ Atomic score per battle

Reuses the existing `signed_score` definition from
`webapp/derive_unit_rankings.py`:

```
signed_score(battle) = 100 × (winner_hp% − loser_hp%)
                       × (+1 if team1 won, −1 if team2 won)
                       (0 if winner == 0)
```

Range `[−100, +100]`. Positive means *my* side won; magnitude is how
decisive.

### ✅ Two scores per unit, by scale

For each `(civ, unit_slug)` pair we compute two **independent** score
values from the same matchup data filtered by scale:

* `pop_score` uses only `scale = '30v30'` rows.
* `cost_score` uses only `scale = '3k'` rows.

The 3k scale already incorporates the `SCALE_3K_UNIT_CAP = 30` rule
(see `simulation_real.py`) — `cost_score` therefore reflects
cost-matched outcomes with the cap, and `pop_score` reflects fixed
population outcomes.

### ✅ Three role components

For infantry the score has three role components, all in the same
shape (signed_score average):

* **General combat (GC)** — average across the **militia**, **knight**,
  and **archer** line opponents.
* **Anti-cav (AC)** — average across the **knight**, **camel**,
  **steppe_lancer**, and **elephant** line opponents.
* **Anti-trash (AT)** — average across the **spear**, **skirmisher**,
  and **light_cav** line opponents.

The knight line is intentionally counted in both GC and AC. It is the
single most-weighted line in the final score (≈ 0.27 weight when
combined across roles), reflecting that knights are the central
mid/late-game threat for an infantry unit to face.

### ✅ Line membership

For a given role component, all units that map to one of its lines at
imperial age are eligible opponents. This includes:

* The standard line-head slug (e.g. `champion`, `paladin`, `arbalester`).
* Any `extra_imperial_slugs` (e.g. condottiero, secondary line heads).
* All civ unique-unit slugs that map to that line via
  `UNIT_LINES[line]['unique_units']`.

We do **not** filter by elite vs non-elite; only imperial-age units
participate.

### ✅ Within-line aggregation: mean with dedup

Within a single line, all eligible-opponent rows are pulled from
`matchup_battles` for the unit at the chosen scale. Rows sharing the
same `dedup_group` are collapsed to a single representative (the
fingerprint dedup already done by `run_matchup_battles.py`). The
line's contribution is the **mean signed_score** of the deduped rows.

### ✅ Across-line aggregation: mean (avg-of-means)

Each role component is the **simple mean of its constituent line
means**, regardless of how many opponents each line had. This gives
each line equal weight, so a line that happens to have many unique
units (e.g. militia) does not dominate.

Mean is preferred over median because:

* Catastrophic losses against specific units (e.g. Plumed Archer for
  Berserker) represent real strategic risk you face when your
  opponent picks that civ — not statistical noise. Mean preserves
  this signal proportionally; median hides it.
* Mean is linear, so the weighted role formula combines correctly.

### ✅ Final score per scale

```
final_score(scale) = 0.70 × GC(scale)
                   + 0.15 × AC(scale)
                   + 0.15 × AT(scale)
```

Anti-trash is intentionally low-weighted: trash-killing is a niche
role (one player has gold, the other has run out), not a primary
infantry job.

### ✅ Shape descriptors stored alongside the score

For each `(unit, scale, role)` and the overall `(unit, scale)`
aggregate, we store:

* `n` — number of unique opponents (post-dedup).
* `mean` — the score itself.
* `stddev` — population stddev of the underlying signed_scores.
* `win_rate` — % of matchups where signed_score > 0.
* `decisive_win_rate` — % where signed_score > +30.
* `big_win_rate` — % where signed_score > +50.
* `catastrophic_loss_rate` — % where signed_score < −50.

These let the UI describe the *shape* of a unit's performance without
re-querying raw battles.

### ✅ Profile labels (computed at display time, not stored)

The label is a one-word description derived from the shape
descriptors. Evaluation order is most-specific first.

| Label              | Rule                                                          |
| ------------------ | ------------------------------------------------------------- |
| **DOMINANT**       | win-rate ≥ 80% AND catastrophic-loss-rate ≤ 5%                |
| **RELIABLE**       | win-rate ≥ 65% AND catastrophic-loss-rate ≤ 10%               |
| **HARD-COUNTERED** | win-rate ≥ 60% AND catastrophic-loss-rate ≥ 15%               |
| **NICHE**          | big-win-rate ≥ 25% AND win-rate ≤ 55% AND cat-loss-rate < 25% |
| **VOLATILE**       | 45% ≤ win-rate ≤ 60% AND stddev ≥ 50                          |
| **WEAK**           | win-rate ≤ 35% AND catastrophic-loss-rate ≥ 15%               |
| **EVEN-TRADE**     | 40% ≤ win-rate ≤ 60% AND stddev ≤ 15                          |
| **SOLID**          | default fallback                                              |

The label is computed at query/render time so thresholds can be tuned
without re-running the pipeline. If a sortable column is needed
later, the label can be materialized as a derived column.

### ✅ Reference unit & validation

Viking Elite Berserk is the canonical reference unit. The
implementation must reproduce:

* Pop score: **+26.2** (GC +13.0, AC +21.2, AT +92.7)
* Cost score: **+41.6** (GC +29.7, AC +45.8, AT +92.9)
* Pop overall profile: **SOLID** (mean +35.2, win 72%, cat-loss 13%)
* Cost overall profile: **RELIABLE** (mean +51.3, win 85%, cat-loss 7%)

A regression test will pin these values to four decimal places (or
within an explicit tolerance, decided in implementation).

## Open questions

The following will be resolved during the rest of the brainstorming
session before the implementation plan is written.

1. **Other pools.** Does the same role-set apply to ranged and stable
   units? E.g. for a knight-line unit, what does its GC / AC / AT
   weighting look like, and which line-set defines each role?
   Specifically — does a knight unit's "anti_cav" still average over
   the same lines, or is it a different set?
2. **Storage.** New table vs add columns to existing
   `derived_data.battle_scores` vs new DB? Likely a new table
   `derived_data.unit_pool_scores` keyed by `(civ, unit_slug, scale)`
   with the role components and shape descriptors as columns.
3. **Pipeline integration.** New script vs extending
   `derive_unit_rankings.py`. Inputs are still `matchup_db.db` +
   `aoe2_reference.db` for line classification.
4. **UI integration.** Which page surfaces the new score, and in what
   form. Likely a new column or panel on the existing unit-line page,
   showing both pop and cost scores plus the profile label.
5. **Whether the old `battle_scores` table stays.** Could be deprecated
   once the new score is live, but keeping both for a transition is
   fine.
6. **Threshold tuning across the unit population.** Once we compute
   the labels for all infantry, the thresholds may need adjustment
   (e.g. if 90% of units land in SOLID, the rules are too tight).
7. **Cross-unit normalization.** Currently each unit's score is its
   raw expected signed_score. There is no pool normalization. Do we
   want a separate column showing rank within line / pool, similar to
   the existing `rank` and `median_delta` in `battle_scores`?

## Non-goals

* Replacing `matchup_battles` or any raw simulation data — those stay
  as-is.
* Touching the matchup-advisor recommendations (`advisor_recommendations`
  table) — separate concern.
* Re-running simulations — this is a pure derivation change.

## Architecture sketch (subject to open questions above)

```
matchup_db.matchup_battles  ──┐
                              │
aoe2_reference.db.ref_units ──┼─►  derive_pool_scores.py  ──►  derived_data.unit_pool_scores
                              │
unit_lines.UNIT_LINES       ──┘                                  (one row per civ × unit × scale)
```

Each row of `unit_pool_scores` will contain:

* identity: `civ_name`, `unit_slug`, `pool` (infantry / ranged /
  stable), `scale` ('30v30' or '3k')
* score: `final_score`, `gc`, `ac`, `at` (or pool-specific role
  columns)
* shape: `n`, `stddev`, `win_rate`, `decisive_win_rate`,
  `big_win_rate`, `catastrophic_loss_rate`

## Notes for self-review later

* Consistency: ensure the line-membership convention used in
  `derive_pool_scores.py` matches what `derive_unit_rankings.py`
  already uses, so units classify the same way across both pipelines
  during the transition.
* The reference values for Berserker were computed from
  `webapp/matchup_db.db` at the all-53-civ snapshot post sim
  improvements (`sim_version` matching commit `ba893a3` line). If the
  sim engine changes, expected values must be regenerated.
