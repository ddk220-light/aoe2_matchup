# Combat Calibration Rig

*Last verified: 2026-07-30 · branch `improved-simulation` · corpus: 75 fights / 69 matchups*

Fits the JS battle engine (`apps/website/static/js/engine/`) to REAL Age of Empires II
fights recorded at ~60 Hz, by scoring the engine's own emitted combat events against the
recording's events through **one shared metric implementation**. Supersedes the old
outcome-only tape corpus (`aoe2x/validation/tape_corpus.json`, 38 win/loss rows) as the
validation authority for combat dynamics; that corpus's win/loss bit stays retired.
Design doc: `docs/superpowers/specs/2026-07-30-combat-calibration-design.md`. Implementation
plan: `docs/superpowers/plans/2026-07-30-combat-calibration.md`.

## 1. What the rig is

```
drop.zip ──ingest──────> D:/AI/aoe2_golden/tapes/<run_id>/        (external, large)
                         data/calibration/manifest.json           (in repo)

tape streams ─────┐
                   ├──extract_card──> data/calibration/truth/<run_id>.json
engine ──eventLog──┘   (Task 2's ONE metric implementation)

data/calibration/combat_dicts.json ──> tools/simjs/calib_runner.mjs
                                        (20 seeds/fight, tape-shaped events)
                                        ──> D:/AI/aoe2_golden/simruns/<run_id>/seed-<n>.json

score.py: extract_card(sim events) vs the tape's truth card
          ──> data/calibration/runs/<stamp>-<label>.json  (the scoreboard)
```

Five independently-testable stages, each its own module:

| Stage | File | Task |
|---|---|---|
| Ingest a drop, resolve civs, build the manifest | `aoe2x/calibration/ingest.py` | 1 |
| The shared metric extractor | `aoe2x/calibration/extract.py` | 2 |
| Engine event recorder (opt-in `sim.eventLog`) | `apps/website/static/js/engine/{sim,battle_unit}.js` | 3 |
| 20-seed sim runner over the manifest | `tools/simjs/calib_runner.mjs` (+ `dump_calib_dicts.py`) | 4 |
| **Scorer + BASELINE scoreboard** | `aoe2x/calibration/score.py` | **5 (this doc)** |

**The one load-bearing property:** `aoe2x.calibration.extract.extract_card(damage_events,
missile_events, composition) -> dict` is called on tape events AND on the JS engine's own
sim-run events, with zero branching on origin. If tape and sim were ever measured by
different code, the whole calibration exercise would be meaningless — a metric could
silently mean two different things in the two worlds. `score.py` never computes a metric
itself; it only compares two already-`extract_card`-derived cards.

## 2. Running the rig end to end

```bash
# 1. Ingest a new drop (idempotent; skips already-ingested content by hash).
python -m aoe2x.calibration.ingest <path/to/drop.zip>

# 2. Refresh combat dicts + truth cards + sim runs whenever the manifest grows
#    (e.g. new recordings landed since the last sim run).
python tools/simjs/dump_calib_dicts.py          # ~instant
python -m aoe2x.calibration.extract --all       # ~1s for 75 fights
node tools/simjs/calib_runner.mjs --seeds 20    # ~35s for 75 fights x 20 seeds

# 3. Score the whole corpus and write a labeled scoreboard.
python -m aoe2x.calibration.score --all --label baseline
# -> data/calibration/runs/<stamp>-baseline.json
```

`score.py` also accepts `--run-id <run_id>` (repeatable) to score a subset, and `--seeds N`
to read fewer than 20 seed files.

## 3. Metric definitions (verified against the drop's own `GROUND_TRUTH.md`)

Owned by `extract.py`, restated here for reference — see that module's docstring for the
full derivation:

- **Swing grouping**: a side's damage events grouped by `attacker` (unit instance, not
  owner); consecutive events from the same attacker within `SWING_EPS = 0.60s` are ONE
  swing (lets one trampling hit that damages several victims still count as one swing).
  Raised from `0.15s` on 2026-07-30: a slow projectile (siege onager, heavy scorpion,
  elite fire lancer) spreads one shot's multi-victim damage over more than 0.15s of
  flight, so the old value split a single shot into several "swings" and manufactured
  churn — a defect in the rig, not in the engine. Corpus effect: gated MISMATCH
  756 → 726, all other units' cards bit-identical (the Elite Battle Elephant's 402
  multi-victim swings all span ≤ 0.15s, so real trample is untouched). See
  `calibration-gap-analysis.md` §3.3.
- **`swing_interval_median`**: per attacking unit, the median gap between its own
  consecutive swings; then the median of THOSE per-unit medians across the side.
- **`swing_interval_fastest`**: the minimum gap pooled over ALL units — NOT the minimum of
  the per-unit medians.
- **`churn`**: `swing_interval_median − swing_interval_fastest`.
- **`projectiles_fired`**: count of DISTINCT missile `id`s for that owner (the missile
  stream is a ~60 Hz position tracker; raw row counts are ~18x too high).
- **`effective_accuracy`**: `hits_landed / projectiles_fired`. **Can legitimately exceed
  1.0** for a trampling ranged unit (one projectile can register hits on several victims —
  the corpus's Chinese Elite Fire Lancer does this). Never clamped anywhere in this rig.
- **Trample stats**: within the swing groups, a swing with >1 distinct victim is a
  "multi-hit" swing. `trample_multi_rate` = multi-hit swings / total swings.
  `trample_victims_mean/max` over multi-hit swings. `splash_fraction` = modal non-maximal
  per-hit damage ÷ modal maximal per-hit damage within multi-hit swings.
- **Known, deliberate definitional difference**: the Elite Battle Elephant's
  `swing_interval_median` is **6.246s** under this rig's definition vs the drop's own
  published **5.672s** — their extractor filters long idle gaps (36.6s/25.6s/23.0s) out of
  that unit's gap list before taking the median; this rig does not copy that filtering,
  because the filter would have to apply identically to sim events too, and "idle gap"
  isn't a concept sim events naturally carry the same way. 6.246 is asserted in
  `tests/test_calibration_extract.py` as the authoritative value.
- **Not implemented, on purpose**: `mean_distance_tiles`. The design's metric table lists
  it as reported-only, but `extract_card` consumes only damage + missile event streams —
  no unit-position stream at all (see its own docstring) — so no truth card in this corpus
  carries it. Adding a second, position-based metric path here to compute it would violate
  the one-extractor rule, so it is omitted rather than approximated.

## 4. Verdicts

Per metric x side: **MATCH** if the tape value lies inside the 20-seed sim distribution's
`[p10, p90]` band, OR within the metric's own tolerance of the sim median. **MISMATCH**
otherwise. **INCONCLUSIVE** downgrades an apparent MISMATCH when the tape's OWN sample is
too small to trust it: fewer than 5 swing gaps for an interval metric, or (for a rate
metric) a binomial 95% CI wider than the tolerance. INCONCLUSIVE never *upgrades* a MATCH.

Per-fight verdict is the worst of its gated metrics' verdicts (`MISMATCH > INCONCLUSIVE >
MATCH`), reported as `PASS` / `MISMATCH` / `INCONCLUSIVE`. INCONCLUSIVE fights are the
**reroll request list** — matchups that need re-recording (more repeats, or longer fights)
before a verdict can be trusted.

**Gated** (decide PASS/FAIL): `swing_interval_median`, `swing_interval_fastest`, `churn`,
`effective_accuracy`, `damage_histogram` (per damage-value bucket + a rollup row),
`hits_landed`, `damage_dealt`, `kills`, `survivors`, `hp_remaining`, and the trample stats
— but the trample stats are gated only for a fight where either the tape or at least one
sim seed shows `trample_multi_rate > 0`; a unit that never demonstrably tramples in either
world has nothing to compare.

**Reported only** (never gate): `first_blood`, `duration_s` (fight-level, not per-side).
The JS engine fights in an open 30x20 box; the tape's arena is 16x16 with ~39% solid tiles
— a deliberate, accepted geometry mismatch (design spec §7), so movement-dependent metrics
are informational only.

## 5. Tolerance choices, and why

Tolerances are NOT one uniform number. They come from the corpus's only two 4-repeat
recording families — `champion__vs__arbalester{,_r2,_r3,_r4}` and
`champion__vs__heavy_cav_archer{,_r2,_r3,_r4}` — which are the only place the real game's
own run-to-run noise floor is directly observable (measured with `python` one-liners over
the truth cards; see `git log` for this task's exploration). Three findings drove every
number below:

**1. Variance is asymmetric by role, and the role must be decided per fight, not per
matchup.** For each side of every scored fight, `score.py` computes a `winner`/`loser` role
from **that fight's own tape outcome** (ranked by `(survivors, hp_remaining, kills)`) —
not a fixed label per matchup, because the heavy-cav-archer family's winner actually flips
between repeats (Champion wins once, Heavy Cavalry Archer wins the other three). Measured
repeat spreads:

| metric (role) | arbalester family | heavy-cav-archer family |
|---|---|---|
| `swing_interval_median` (winner) | 0.007s (1.991–1.998) | 0.031s (2.001–2.032, using its 3 winner repeats) |
| `swing_interval_median` (loser) | 0.556s (2.372–2.928) | 1.313s |
| `swing_interval_fastest` (winner) | 0.254s (17.5%) | 0.358s (20.1%) |
| `churn` (winner) | 0.260s (47.6%) | 0.893s |
| `damage_dealt` (loser) | 80 (60.4%) | up to 447 (61–111%) |
| `survivors` (winner) | 2 (11.4%) | up to 9 (69%) |
| `hp_remaining` (winner) | 80 (13.6%) | up to 447 (93%) |
| `effective_accuracy` (winner, ranged) | 0.003 | 0.041 |
| `duration_s` (whole fight) | 12.5s (23.6%) | 18.2s (23.6%) |

**2. Order statistics are noisier than the median, even on the stable side.**
`swing_interval_fastest` (a single `min()`) and `churn` (derived from it) swing by
17.5–20% on the WINNING side — far more than the median's 0.3–1.5% — simply because a
minimum over a finite sample is a noisier statistic than a median. They get their own,
wider tolerance band even for the "stable" role.

**3. Rate metrics are comparatively stable.** `effective_accuracy` on the winning
(ranged) side varies by only 0.003–0.041 absolute across repeats — a flat 0.05 tolerance
covers this with headroom in both directions.

Resulting tolerance table (`aoe2x/calibration/score.py`, `INTERVAL_TOL` / `RATE_TOL` /
`COUNT_TOL_FLOOR` / `COUNT_TOL_REL`):

| metric class | winner-role tolerance | loser-role tolerance | basis |
|---|---|---|---|
| `swing_interval_median` | `max(0.05s, 5%)` | `max(0.30s, 25%)` | direct repeat spread (0.007–0.031s vs up to 1.313s) |
| `swing_interval_fastest`, `churn` | `max(0.30s, 20%)` | `max(0.50s, 35%)` | order-statistic noise (17.5–20% even on the winner) |
| `effective_accuracy` | `0.05` (both roles) | `0.05` | repeat spread ≤0.041; no losing-ranged-side repeat exists, same number used, flagged as an assumption |
| `trample_multi_rate`, damage-histogram buckets | `0.08` | `0.08` | no repeat data for a trampling unit exists in this corpus; chosen slightly looser than accuracy's 0.05 as a documented assumption pending more repeats |
| count metrics (`hits_landed`, `damage_dealt`, `kills`, `survivors`, `hp_remaining`, trample victim counts, `splash_fraction`) | `max(floor, 15%)` | `max(floor, 60%)` | loser-side relative spread reached 60–111% in both families; the sim's own 20-seed `[p10,p90]` band is the PRIMARY match test for these — the flat tolerance is a fallback, not the main gate |
| `duration_s` (reported only) | `max(5s, 25%)` | — | matches the ~23.6% duration spread measured in BOTH repeat families |

Binomial-CI note: `effective_accuracy` (and `trample_multi_rate`, and each damage-histogram
bucket fraction) use a 95% CI (`Z=1.96`) computed from the tape's own denominator
(`projectiles_fired`, `swing_count`, or bucket `hits_landed` respectively) to decide the
INCONCLUSIVE downgrade. The CI helper clamps its **own working probability** to `[0, 1]`
before computing `sqrt(p(1-p)/n)` — a CI on a proportion above 1 is meaningless — but that
clamp is purely internal to the width estimate; the actual tape/sim values compared and
reported are never clamped (verified by `test_effective_accuracy_above_one_is_never_
clamped`, which pins a real trampling-unit accuracy of 2.43 surviving untouched).

## 6. BASELINE results (this task's scoreboard)

`data/calibration/runs/20260730T093504Z-baseline.json` — all 75 manifest fights, 0 load
failures.

| verdict | fights |
|---|---|
| PASS | 6 |
| MISMATCH | 67 |
| INCONCLUSIVE | 2 |

PASS: `elite_steppe__vs__arbalester`, `champion__vs__halberdier`, `champion__vs__heavy_camel`,
`champion__vs__paladin`, `halberdier__vs__heavy_camel`, `heavy_cav_archer__vs__heavy_camel`.

INCONCLUSIVE (the reroll list — record these again, ideally with more repeats or a longer
engagement): `halberdier__vs__arbalester` (accuracy CI too wide at n=221 near p≈0.5;
`churn` has only 2 swing gaps), `champion__vs__arbalester_r2` (only 3 swing gaps and 12
histogram-bucket hits on the Champion side — this specific repeat recording, unlike its 3
siblings, is simply too short on that side to score).

### Gated-metric mismatch ranking (fight count out of 75, most common first)

| rank | metric | fights mismatched | top units involved |
|---|---|---|---|
| 1 | `swing_interval_median` | 53 | Saracens/heavy_cav_archer (13), Chinese/elite_fire_lancer (12), Chinese/champion (5) |
| 2 | `hp_remaining` | 52 | Saracens/heavy_cav_archer (8), Chinese/champion (6), Aztecs/siege_onager (6) |
| 3 | `churn` | 51 | Chinese/elite_fire_lancer (11), Saracens/heavy_cav_archer (8), Japanese/heavy_scorpion (7) |
| 4 | `survivors` | 44 | Saracens/heavy_cav_archer (7), Chinese/champion (6), Chinese/halberdier (5) |
| 5 | `damage_histogram` (rollup) | 37 | Chinese/elite_fire_lancer (13), Japanese/heavy_scorpion (7), Aztecs/siege_onager (7) |
| 6 | `kills` | 35 | Chinese/champion (8), Japanese/heavy_scorpion (4), Saracens/heavy_cav_archer (4) |
| 7 | `hits_landed` | 32 | Chinese/champion (5), Aztecs/siege_onager (5), Japanese/heavy_scorpion (4) |
| 8 | `effective_accuracy` | 27 | Chinese/elite_fire_lancer (8), Japanese/heavy_scorpion (5), Chinese/arbalester (5) |
| 9 | `trample_victims_max` | 26 | Burmese/elite_elephant, Chinese/elite_fire_lancer, Chinese/champion (as opponent-side victim tallies) |
| 10 | `swing_interval_fastest` | 26 | Japanese/heavy_scorpion, Aztecs/siege_onager, Chinese/elite_fire_lancer |

Full ranking (36 rows including every individual damage-histogram bucket) is in the
scoreboard's `mismatch_ranking` field.

### Reading the baseline: this is the expected shape, not a scorer bug

- `swing_interval_median`/`churn` dominate because **the JS engine has no crowd-churn
  mechanism at all** (Task 6, not yet done) — `simulation_real.py` has one
  (`CHURN_MAX`), the JS engine does not (`grep -i churn apps/website/static/js/engine/*.js`
  returns nothing). This is the single largest, already-diagnosed gap.
- `effective_accuracy` mismatches concentrate on ranged units firing at large targets
  (Elite Fire Lancer, Heavy Scorpion, Arbalester) — the known "hit-capture vs. target
  radius" gap (Task 7).
- `trample_victims_max`/`_mean`/`splash_fraction` mismatch whenever the tape's unit
  tramples but the sim shows `trample_multi_rate = 0.0` in every one of its 20 seeds
  (confirmed directly for `hand_cannoneer__vs__elite_elephant`'s Elite Battle Elephant) —
  the trample mechanism's radius/percent needs auditing (Task 8).
- `hand_cannoneer__vs__elite_elephant`'s `duration_s` (reported, not gated) is `MATCH`
  by this scorer only because the sim's own 20-seed spread is enormous (`p10=150.5s,
  p90=537.3s`) — the median (264s) is still 74% above the tape's 152.31s. This IS the
  already-diagnosed pursuit/thrash defect (Task 10): the huge seed-to-seed duration
  variance is itself a symptom, not a coincidence that happens to save the verdict.

## 7. Calibration backlog (ranked, for Phase 2)

1. **Crowd churn** (Task 6) — the largest and most pervasive gap: `swing_interval_median`,
   `swing_interval_fastest`, and `churn` mismatch in up to 53/75, 26/75, and 51/75 fights
   respectively, concentrated on Saracens Heavy Cavalry Archer, Chinese Elite Fire Lancer,
   Chinese Champion, and Japanese Heavy Scorpion — all high-crowd-density matchups.
2. **Effective accuracy against large targets** (Task 7) — 27/75 fights, concentrated on
   Elite Fire Lancer, Heavy Scorpion, and Arbalester vs. large-hitbox opponents.
3. **Trample audit and fit** (Task 8) — `trample_victims_max/mean`, `splash_fraction`
   mismatch in 19–26/75 fights; the sim shows zero trample activity for the Elite Battle
   Elephant across all 20 seeds where the tape shows a 13% multi-hit rate.
4. **Reload-model investigation** (Task 9) — `swing_interval_fastest` mismatches (26/75)
   include cases below paper reload; needs the dedicated investigation this task's plan
   already scopes.
5. **Pursuit/thrash fix** (Task 10) — not itself gated (duration is reported-only) but the
   single largest reported-metric gap: `hand_cannoneer__vs__elite_elephant` runs ~290s in
   a representative seed against a 152.31s tape, and the resulting p10–p90 sim spread
   (150–537s) is itself evidence of the mechanism thrashing rather than resolving cleanly.

## 8. Tests

`tests/test_calibration_score.py` — 7 tests: MATCH/MISMATCH/INCONCLUSIVE each triggered
by synthetic card pairs, a metric present on only one side does not crash, a >1.0
`effective_accuracy` is never clamped (including inside the binomial-CI helper), and one
end-to-end smoke test against real corpus data (`elite_steppe__vs__arbalester`).

```bash
python -m pytest tests/test_calibration_score.py -v   # 7 passed
python -m pytest                                       # full suite, no regressions
```
