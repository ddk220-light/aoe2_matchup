# Shared enemy pair-transit calibration

This report validates the experiment-gated shared pair-interaction engine against
the authorized golden tapes for the enemy-overlap cases that motivated it. The
engine contains no War Wagon-, HCA-, Paladin-, Boyar-, civilization-, or matchup-
specific overlap constant.

## Golden sources

- Phase 2 archive SHA-256:
  `B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6`
- Dedicated HCA-versus-Paladin archive SHA-256:
  `8902DE64B120E6302860F8F9B35B572523B29B4C0F305C65A7DA6D0C286F7968`

The runner rejects either corpus if its manifest hash differs. It reads only
project-local clean-room fixtures and tape traces under `calibration/`.

## Implemented physics

The world builds one `PairInteractionSnapshot` per tick and passes it through
path planning, local avoidance, movement stopping, contact capture, collision,
and final geometry validation.

- Ordinary enemy pairs remain hard.
- A melee pursuer may reserve one non-target enemy in its immediate swept
  corridor. Deep transit is deterministic and one-to-one.
- Direct pursuit contact is tracked separately from the deep-transit slot.
- Compression is derived from each unit's sourced DAT
  `min_collision_size_multiplier`; no fitted overlap radius is used.
- A larger direct target remains hard, preventing small melee units from
  entering a large ranged body merely because they are attacking it.
- A moving ranged formation member may flow through one stationary engaged
  melee body instead of being permanently captured by it.
- Released or otherwise published overlap becomes inherited contact. It may
  persist or separate but may not deepen.
- A moving inherited pair spends its proposed speed along the collision normal
  until it clears. This prevents stable interpenetrating stacks without a
  timeout or unit-specific escape force.
- Inherited direct engagement does not consume the separate deep-transit slot;
  inherited corridor/formation contacts do, preserving the one-to-one packing
  invariant.
- Recovery uses the same square/Chebyshev footprint geometry as final collision
  validation, so a legal published contact cannot crash on the next tick.

## Comparison method

`pairShare` is the number of live cross-owner pair observations whose square
footprints overlap divided by all live cross-owner pair observations. Depth is
the conditional median of `full pair extent - Chebyshev separation` while the
pair overlaps.

The report gate compares no more simulation runs than there are recorded golden
tapes. This matters for Boyar-HCA: it has one tape, so its canonical simulation
is the evidence-matched result. Additional simulations that reshuffle synthetic
acquisition-delay ranks are retained in `report.json` as stress diagnostics but
cannot be treated as additional tape samples.

The comparison band is the recorded tape range expanded by 25 percent. A row
also requires the golden winner sign.

## Accepted result

| Golden row | Tape pair overlap | Sim pair overlap | Tape median depth | Sim median depth | Winner | Gate |
|---|---:|---:|---:|---:|---|---|
| War Wagon vs Paladin | 0.780% | 0.595% | 0.068600 | 0.125000 | correct | comparable |
| War Wagon vs Champion | 0.570% | 0.747% | 0.086900 | 0.040000 | correct | comparable |
| HCA vs Paladin 20v15 | 0.342% | 0.296% | 0.065228 | 0.061043 | correct | comparable |
| Boyar vs HCA | 0.450% | 0.373% | 0.065602 | 0.076164 | correct | comparable |

Recorded-run coverage is 4/4 War Wagon-Paladin, 4/4 War Wagon-Champion, 5/5
HCA-Paladin, and 1/1 Boyar-HCA.

This acceptance is specifically for overlap frequency, conditional depth, and
winner direction. It does not claim identical episode texture: the War Wagon
runs still create fewer overlap episodes than tape, and some simulated episodes
last longer. That is retained in `report.json` for future movement sequencing
work rather than force-fitted with a duration constant.

## Reproduce

From `aoe2x/js_simulation`:

```powershell
node calibration/reports/shared_enemy_pair_transit_2026-08-18/run_overlap_experiment.mjs --row=elite_war_wagon_vs_paladin --samples=4
node calibration/reports/shared_enemy_pair_transit_2026-08-18/run_overlap_experiment.mjs --row=elite_war_wagon_vs_champion --samples=4
node calibration/reports/shared_enemy_pair_transit_2026-08-18/run_overlap_experiment.mjs --row=heavy_cav_archer_vs_paladin_20v15 --samples=5
node calibration/reports/shared_enemy_pair_transit_2026-08-18/run_overlap_experiment.mjs --row=elite_boyar_vs_heavy_cav_archer --samples=1
node calibration/reports/shared_enemy_pair_transit_2026-08-18/run_overlap_experiment.mjs --report-only
```

Each completed simulation sample is written atomically to `checkpoints/`. A
rerun reuses a checkpoint only when the experiment revision, engine signature,
and both source hashes match.

Focused verification:

```powershell
node --test tests/pair-interactions.test.mjs tests/enemy-transit.test.mjs
node --test --test-name-pattern='path waypoint|reserved enemy-transit|inherited enemy overlap|enabled world tick|pairwise enemy transit state' tests/movement-collision.test.mjs tests/world-tick.test.mjs
```

The broader legacy fixture suite currently includes pre-existing assertions
whose hard-coded unit stats/timing and deliberately overlapping start geometry
no longer match the branch's already-accepted engine. Those failures are not
used as evidence for this change; all pair-transit-focused assertions and all
four golden gates pass.
