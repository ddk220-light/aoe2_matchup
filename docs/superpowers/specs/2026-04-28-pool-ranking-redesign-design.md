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

Raw range `[−100, +100]`. Positive means *my* side won; magnitude is
how decisive.

### ✅ Loss aversion (asymmetric weighting)

Before any aggregation, the raw signed_score is passed through a
piecewise-linear **loss multiplier**:

```
adjusted_score = signed_score              if signed_score ≥ 0
                 λ × signed_score          if signed_score < 0   (λ = 2.0)
```

This widens the gap between losses and wins of equal magnitude (e.g.
−25 becomes −50, while +25 stays +25) without compressing the
win/big-win gap (+25 vs +75 stays a 50-point spread). It preserves
linearity on each side of zero, so the weighted role formula still
combines correctly under the mean.

After this transform, the working range is `[−200, +100]`. All
downstream means, weighted sums, and shape descriptors operate on the
adjusted score. The reference values below were computed under
λ = 2.0.

A single parameter (λ) makes the asymmetry tunable. λ was chosen by
matching two stated criteria: gap(−25 → +25) widens, and gap(+25 →
+75) is unchanged. Empirically, this drops the Berserker pop_score
from +26 to +9 and cost_score from +42 to +32 — driven by the
archer-line and elephant-line losses being correctly weighted heavier.

### ✅ Two scores per unit, by scale

For each `(civ, unit_slug)` pair we compute two **independent** score
values from the same matchup data filtered by scale:

* `pop_score` uses only `scale = '30v30'` rows.
* `cost_score` uses only `scale = '3k'` rows.

The 3k scale already incorporates the `SCALE_3K_UNIT_CAP = 30` rule
(see `simulation_real.py`) — `cost_score` therefore reflects
cost-matched outcomes with the cap, and `pop_score` reflects fixed
population outcomes.

### ✅ Pools and role components

Each combat unit belongs to a **pool** based on its production
building (Barracks → infantry, Stable → stable, Archery Range →
archer). Each pool has its own role formula and role-specific line
sets, but they share General Combat (GC) as the dominant component.

**General combat (GC)** — average across the **militia**, **knight**,
and **archer** line opponents. Identical across all three pools.

**Anti-cav (AC) — infantry pool** — average across **knight**,
**camel**, **steppe_lancer**, **elephant**.

**Anti-cav (AC) — stable pool** — average across **knight**,
**camel**, **steppe_lancer**, **elephant**, **light_cav**. (Includes
light_cav because cavalry units fight light_cav for chase/skirmish
purposes; light_cav is "trash" only from an infantry's perspective.)

**Anti-trash (AT)** — only used by the infantry pool. Average across
**spear**, **skirmisher**, **light_cav**.

**Anti-archer (AA)** — only used by the archer pool. Average across
**archer**, **skirmisher**, **cav_archer**, **gunpowder**.

The knight line is intentionally counted in both GC and AC. For the
infantry pool it is ≈ 0.27 effective weight in the final score.

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

### ✅ Final score per pool, per scale

Each pool has its own role-weighting formula. All weights sum to 1.0,
so the final score remains comparable across pools (it's still an
expected adjusted-score against a uniformly-random opponent in the
unit's pool-specific role mix).

```
infantry: final_score = 0.70 × GC + 0.15 × AC_inf + 0.15 × AT
stable:   final_score = 0.70 × GC + 0.30 × AC_stb
archer:   final_score = 0.70 × GC + 0.30 × AA
```

**Pool determination** uses `UNIT_LINES[line]['building']`:
- `Barracks` → infantry pool (militia, spear, shock_infantry, plus
  every barracks-built unique unit)
- `Stable` → stable pool (knight, light_cav, camel, steppe_lancer,
  elephant, plus every stable-built unique unit)
- `Archery Range` → archer pool (archer, skirmisher, cav_archer,
  gunpowder, plus every archery-range-built unique unit)

Castle-built unique units are assigned to a pool by the line they map
to in `UNIT_LINES[line]['unique_units']` — e.g. Berserker is in the
militia line so it joins the infantry pool; Mangudai is in the
cav_archer line so it joins the archer pool.

Anti-trash is intentionally low-weighted in the infantry pool:
trash-killing is a niche role (one player has gold, the other has run
out), not a primary infantry job. Stable and archer pools have no AT
component because their units are themselves the trash-counters or
not viable trash-counters.

### ✅ Additional scoring axes: resource cost and speed

The HP-based score above answers "did I win, and by how much HP?" but
doesn't capture two other meaningful dimensions of a battle: the
*economic* cost of fighting it, and how *quickly* it resolved. We
compute both as additional axes alongside HP, using identical role
and aggregation machinery (avg-of-line-means, role weights 0.70 /
0.15 / 0.15, λ = 2 loss aversion, dedup by `dedup_group`).

#### Resource cost axis

Per-battle weighted resource cost, reusing the existing weighting from
`webapp/best_units.py:_calc_weighted_cost`:

```
weighted_cost(food, wood, gold) = 0.8 × wood + 1.0 × food + 1.5 × gold
```

Per-battle "cost of the battle" from my perspective:

```
my_total_cost   = my_count × weighted_cost(my_food, my_wood, my_gold)
opp_total_cost  = opp_count × weighted_cost(opp_food, opp_wood, opp_gold)
my_spent        = my_total_cost × (1 − my_hp_pct)
opp_remaining   = opp_total_cost × opp_hp_pct

if I won:    cost = my_spent
if I lost:   cost = λ × (my_spent + opp_remaining)        # λ = 2
if tie:      cost = my_spent + opp_remaining              # no λ multiplier
```

Higher cost = worse battle for me; 0 = ideal (clean win, no losses).
Range is `[0, ∞)`, where the upper end is bounded by `λ × (my_total_cost
+ opp_total_cost)` for a total wipe.

The cost is **not normalized** per battle. Heavier units (paladin,
elephant) naturally produce larger absolute cost numbers than lighter
ones (skirmisher, militia) — this is intentional, capturing the real
economic damage of losing expensive units. Cross-unit comparisons
should account for the magnitude scaling (e.g. when ranking, sort
within a unit class rather than across all units mixed).

#### Speed-to-win axis

Per-battle linear speed, capped at `T_MAX = 120s` (the empirical max
of observed `game_time_s` values across the matchup data):

```
speed_factor = max(0, 1 − game_time_s / T_MAX)

if I won:    speed = +100 × speed_factor
if I lost:   speed = −λ × 100 × speed_factor              # λ = 2
if tie:      speed = 0
```

A 0s annihilation win = +100, a 120s+ win = 0. A 0s loss (gets wiped
instantly) = −200 with λ=2, a 120s+ loss = 0. Range
`[−200, +100]`.

Higher speed = better. Both wins and losses are penalized when fast
(fast wins are good, fast losses are bad); slow battles regress
toward zero regardless of outcome.

#### Reference values for Berserker

| scale | HP score (λ=2) | resource cost (raw) | speed (T_MAX=120) |
| --- | ---: | ---: | ---: |
| 30v30 | +8.9 | 3961.8 | +1.20 |
| 3k    | +31.6 | 2506.9 | +26.60 |

The 3k vs 30v30 gap is large on all three axes: cap-30 saves Berserker
from elephant-line wipes (cost 14212 → 7033) and lets it actually win
the knight matchup (HP +0.04 → +0.43, speed −15 → +46).

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

Viking Elite Berserk is the canonical reference unit. Pinned by
`tests/test_pool_scores_integration.py` against the live
`webapp/matchup_db.db`.

**Final-score reference (matches spec ±0.5 in the regression test):**

| scale | HP score | resource cost | speed |
| --- | ---: | ---: | ---: |
| 30v30 | **+8.9** (GC −6.8, AC −1.6, AT +92.7) | **3961.8** | **+1.20** |
| 3k    | **+31.6** (GC +17.4, AC +36.8, AT +92.9) | **2506.9** | **+26.60** |

**Shape descriptors (re-pinned to current matchup_db snapshot, 2026-04-28):**

* 30v30 overall: n=269, win-rate ≈ 61.71%, catastrophic-loss-rate ≈ 27.14%

The shape descriptors will drift as more battles are added to
matchup_db (the original brainstorming numbers were taken at n=238;
current snapshot has n=269 deduped opponents). The integration test
re-pins to current data with ±3.0% tolerance. If a future batch
materially shifts these numbers, update the test and this section
together.

Final scores are robust against population shifts (role-weighted means
of line means barely move when a few new battles are added), so they
remain pinned to ±0.5 against spec.

## Resolved decisions

1. ✅ **Other pools.** Stable and archer pools defined above with
   pool-specific role formulas.
2. ✅ **Storage.** A new SQLite database, `webapp/pool_scores.db`,
   keyed by `(civ_name, unit_slug, scale, axis)` with a single
   `pool_scores` table containing the final score, role components,
   and shape descriptors. Separate from `derived_data.db` to keep
   schemas independent and let us iterate on this without colliding
   with the existing rankings pipeline.
3. ✅ **Pipeline integration.** A new script,
   `webapp/derive_pool_scores.py`. Inputs are `matchup_db.db` (raw
   battles) and `webapp/unit_lines.py` (line classification — same
   source of truth as `derive_unit_rankings.py`). Does not modify the
   existing `derive_unit_rankings.py` or `derived_data.db`.
4. ⏸ **UI integration.** Deferred to a later stage. This spec covers
   only DB generation; the UI will pick which of the six flavors
   (3 axes × 2 scales) to surface in a follow-up.
5. ⏸ **Old `battle_scores` table stays.** No deprecation in this
   stage; both tables coexist while the new score is validated.
6. ⏸ **Threshold tuning.** Defer until the full unit population's
   distribution is computable. Profile labels are derived at display
   time, so thresholds can be tuned without re-running the pipeline.
7. ⏸ **Cross-unit normalization.** Not in scope for this stage; the
   stored score is the raw expected adjusted-score in each axis.

## Non-goals

* Replacing `matchup_battles` or any raw simulation data — those stay
  as-is.
* Touching the matchup-advisor recommendations (`advisor_recommendations`
  table) — separate concern.
* Re-running simulations — this is a pure derivation change.

## Architecture sketch

```
matchup_db.matchup_battles  ──┐
                              │
unit_lines.UNIT_LINES       ──┴─►  derive_pool_scores.py  ──►  pool_scores.db
                                                                (table: pool_scores)
```

### `pool_scores` table schema

One row per `(civ_name, unit_slug, scale, axis)`. Six rows per
`(civ_name, unit_slug)` total (3 axes × 2 scales).

| column | type | notes |
| --- | --- | --- |
| `civ_name`            | TEXT     | e.g. "Vikings" |
| `unit_slug`           | TEXT     | e.g. "elite_berserk_vikings" |
| `pool`                | TEXT     | "infantry" / "stable" / "archer" |
| `scale`               | TEXT     | "30v30" / "3k" |
| `axis`                | TEXT     | "hp" / "cost" / "speed" |
| `final_score`         | REAL     | weighted role sum |
| `gc`                  | REAL     | GC role mean (always present) |
| `ac`                  | REAL NULL | AC role mean (infantry/stable only) |
| `at`                  | REAL NULL | AT role mean (infantry only) |
| `aa`                  | REAL NULL | AA role mean (archer only) |
| `n`                   | INTEGER  | total deduped opponents (overall) |
| `mean`                | REAL     | overall mean adjusted_score (= final_score for hp axis; same shape for others) |
| `stddev`              | REAL     | population stddev across all deduped rows |
| `win_rate`            | REAL     | % of deduped rows where raw signed_score > 0 |
| `decisive_win_rate`   | REAL     | % where raw signed_score > +30 |
| `big_win_rate`        | REAL     | % where raw signed_score > +50 |
| `catastrophic_loss_rate` | REAL  | % where raw signed_score < −50 |
| `sim_version`         | TEXT     | passthrough from underlying battles |
| `derived_at`          | TEXT     | ISO timestamp of derivation |

Win/loss rate fields are computed from the **raw** signed_score (not
the loss-aversion-adjusted one), so they describe the underlying
distribution and remain comparable to the existing `battle_scores`
table during transition.

Per-line breakdowns (e.g. "Berserker vs archer line: −12") are NOT
stored — they're only an intermediate calculation. If the UI later
wants to drill into them, that becomes a follow-up extension.

### Pool / line lookup

The script imports `UNIT_LINES` from `webapp/unit_lines.py` directly.
A unit's pool is determined by looking up the line it belongs to (via
`castle_slug`, `imperial_slug`, `extra_imperial_slugs`, and
`unique_units`) and reading `UNIT_LINES[line]['building']`.

## Notes for self-review later

* Consistency: ensure the line-membership convention used in
  `derive_pool_scores.py` matches what `derive_unit_rankings.py`
  already uses, so units classify the same way across both pipelines
  during the transition.
* The reference values for Berserker were computed from
  `webapp/matchup_db.db` at the all-53-civ snapshot post sim
  improvements (`sim_version` matching commit `ba893a3` line). If the
  sim engine changes, expected values must be regenerated.
