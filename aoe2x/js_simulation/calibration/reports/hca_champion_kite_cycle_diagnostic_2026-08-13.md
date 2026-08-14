# HCA versus Champion kite-cycle diagnostic

Authorized source: `aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip`
SHA-256: `EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5`
Comparison: five tape repeats of 5 HCA vs 10 Champions against one deterministic current-engine run with exact tape placement.

## Finding

The HCA move leg and firing timing are already very close to tape. Champion overlap is bimodal: most tape overlap is shallow, but a repeatable deep tail lets pursuing allies pass almost through the same center. The current simulation instead clamps ordinary allied entry at 0.32/0.36 tiles and leaves those contacts compressed for longer. Tape Champions create roughly twice as many brief overlap/pass-through episodes per fight-second.

## Recurrent firing-cycle evidence

| Metric | Unit | Tape median of run medians | Current sim median | Sim − tape |
|---|---:|---:|---:|---:|
| Path between recurrent attack starts | tiles | 1.02 | 1.03 | 0.01 |
| Time moving between attack starts | s | 0.66 | 0.67 | 0.00 |
| Arrival/stop → attack animation starts | s | 0.02 | 0.02 | 0.00 |
| Attack animation starts → next movement | s | 1.34 | 1.33 | -0.00 |
| Projectile release → next movement | s | 0.44 | 0.43 | -0.01 |
| Nearest Champion when attack animation starts | tiles | 1.56 | 1.79 | 0.22 |
| Nearest Champion at projectile release | tiles | 1.03 | 1.25 | 0.22 |

## Champion allied-overlap evidence

A pair is counted as overlapping when its Chebyshev center separation is below the two full 0.20-tile radii (0.40 tiles). A pass-through requires a moving Champion to cross from behind to ahead of the stopped ally along its current HCA target line while the pair overlaps.

| Metric | Tape median across five runs | Current sim | Sim / tape |
|---|---:|---:|---:|
| Pair-frame overlap rate, both moving | 3.7% | 3.8% | 1.02x |
| Pair-frame overlap rate, one moving | 7.2% | 13.6% | 1.89x |
| Pair-frame overlap rate, both stopped | 11.4% | 15.8% | 1.38x |
| Median separation while overlapped | 0.398 tiles | 0.360 tiles | 0.90x |
| All overlap episodes / fight-second | 3.62 | 1.70 | 0.47x |
| Pass-through episodes / fight-second | 0.64 | 0.34 | 0.53x |
| Moving through stopped attacker / fight-second | 1.39 | 0.80 | 0.58x |
| Median overlap-episode duration | 0.184 s | 0.400 s | 2.17x |

### Closest observed allied separations

Smaller separation means deeper overlap. The literal minimum is the single deepest sampled frame; p01 is a more robust description of repeatable deep overlap. All rows include only overlapping pair-frames below 0.40 tiles.

| Pair condition | Tape min | Tape p01 | Tape p05 | Tape median | Sim min | Sim p01 | Sim p05 | Sim median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Both moving | 0.027 | 0.113 | 0.212 | 0.380 | 0.320 | 0.320 | 0.320 | 0.334 |
| One moving, one stopped | 0.032 | 0.233 | 0.307 | 0.392 | 0.320 | 0.320 | 0.320 | 0.360 |
| Both stopped | 0.038 | 0.228 | 0.228 | 0.400 | 0.320 | 0.320 | 0.341 | 0.382 |
| Both in swing/reload | 0.120 | 0.120 | 0.228 | 0.395 | 0.360 | 0.360 | 0.360 | 0.376 |
| Exactly one in swing/reload | 0.027 | 0.272 | 0.326 | 0.400 | 0.320 | 0.320 | 0.338 | 0.361 |
| Neither in swing/reload | 0.027 | 0.186 | 0.228 | 0.387 | 0.320 | 0.320 | 0.320 | 0.338 |
| Moving past stopped swing/reload ally | 0.032 | 0.292 | 0.331 | 0.400 | 0.320 | 0.320 | 0.360 | 0.360 |

| Pair condition | Tape below 0.32 | Tape below 0.20 | Tape below 0.10 | Sim below 0.32 |
|---|---:|---:|---:|---:|
| Both moving | 12.43% | 4.23% | 0.68% | 0.00% |
| One moving, one stopped | 6.95% | 0.67% | 0.08% | 0.00% |
| Both stopped | 9.26% | 0.63% | 0.04% | 0.00% |
| Both in swing/reload | 12.71% | 4.81% | 0.00% | 0.00% |
| Exactly one in swing/reload | 4.06% | 0.62% | 0.25% | 0.00% |
| Neither in swing/reload | 9.94% | 1.19% | 0.16% | 0.00% |
| Moving past stopped swing/reload ally | 2.96% | 0.28% | 0.13% | 0.00% |

## Stop exposure

| Metric | Tape median across runs | Current sim |
|---|---:|---:|
| Stops receiving ≥1 Champion hit | 22.5% | 15.8% |
| Stops receiving multiple Champion hits | 6.1% | 0.0% |
| Champion hit-equivalents over the fight | 30.8 | 35.0 |

## Outcome context

| Metric | Tape median | Current sim |
|---|---:|---:|
| Champion HP remaining | 316 | 140 |
| Champion survivors | 7 | 2 |
| Duration | 41.08 s | 55.93 s |

## Interpretation and caveats

- Tape overlap happens in all three states: both Champions moving, one moving past a stopped ally, and both stopped after crowding. The most gameplay-relevant case is a pursuing Champion entering the footprint of a friendly Champion that has stopped to attack or reload, then continuing toward the HCA.
- The engine's collision solver already shrinks moving allied collision extents, but it hard-floors entry at 0.32/0.36 tiles while local avoidance plans around the ally's full 0.40-tile combined extent. The tape's sub-0.32 tail means merely aligning avoidance to 0.32/0.36 will improve flow but cannot reproduce every observed pass-through.
- The 0.897 s HCA attack delay is present in both sources; the current engine uses 54 ticks, matching the DAT-derived value.
- The comparison does not prove a single causal fix. Arrival-to-attack behavior, formation translation, and Champion contact conversion can interact.
- Tape timing is measured from decoded action-state transitions; sim timing is measured from attack-start/readyTick events. Those are the closest observable equivalents.
- The browser process on port 5011 was stale during the user's observation; this report runs the current module in-process and verifies the exact five HCA starting cells.
