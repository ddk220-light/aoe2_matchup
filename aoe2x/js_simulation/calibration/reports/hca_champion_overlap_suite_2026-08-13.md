# HCA versus Champion allied-overlap suite

Authorized source: `aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip`
SHA-256: `EB47F418B2D88BFB99D0083CF05DE153B329D531B0E179494DAE1A5CA3D921C5`
Scope: 25 tape recordings: five ratios × five repeats, compared with one current deterministic exact-placement simulation per ratio. Ratio notation is HCA count v Champion count.

## Technical summary

Deep friendly pass-through is not confined to 5v10. Every ratio contains Champion pairs below the current engine's 0.32-tile floor. Across all 25 tapes, the closest both-moving separation is 0.003 tiles and the robust p01 is 0.098; the five current simulations never go below 0.320. The depth and frequency grow with Champion crowd size, but the mechanism also appears in the five-Champion 10v5 fight.

## Deep overlap appears in every ratio

Smaller separation means deeper overlap. The literal minimum is the deepest sampled frame; p01 and p05 show the repeatable tail rather than relying on one frame. Only pair-frames below the normal 0.40-tile allied contact extent are included.

| Ratio | Pair condition | Tape min | Tape p01 | Tape p05 | Tape median | Sim min | Sim p01 | Sim p05 | Sim median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5v10 | both moving | 0.027 | 0.113 | 0.212 | 0.380 | 0.320 | 0.320 | 0.320 | 0.334 |
| 5v10 | one moving | 0.032 | 0.233 | 0.307 | 0.392 | 0.320 | 0.320 | 0.320 | 0.360 |
| 5v10 | both stopped | 0.038 | 0.120 | 0.228 | 0.395 | 0.320 | 0.320 | 0.341 | 0.382 |
| 10v5 | both moving | 0.093 | 0.095 | 0.097 | 0.279 | 0.320 | 0.320 | 0.320 | 0.365 |
| 10v5 | one moving | 0.329 | 0.329 | 0.334 | 0.400 | 0.327 | 0.334 | 0.352 | 0.360 |
| 10v5 | both stopped | — | — | — | — | — | — | — | — |
| 15v20 | both moving | 0.003 | 0.111 | 0.265 | 0.381 | 0.320 | 0.320 | 0.320 | 0.343 |
| 15v20 | one moving | 0.009 | 0.239 | 0.299 | 0.383 | 0.320 | 0.320 | 0.320 | 0.360 |
| 15v20 | both stopped | 0.086 | 0.086 | 0.303 | 0.400 | 0.360 | 0.360 | 0.360 | 0.377 |
| 20v15 | both moving | 0.016 | 0.085 | 0.272 | 0.383 | 0.320 | 0.320 | 0.320 | 0.349 |
| 20v15 | one moving | 0.025 | 0.244 | 0.285 | 0.381 | 0.320 | 0.320 | 0.320 | 0.360 |
| 20v15 | both stopped | 0.167 | 0.168 | 0.273 | 0.371 | 0.360 | 0.360 | 0.360 | 0.360 |
| 20v20 | both moving | 0.012 | 0.122 | 0.282 | 0.380 | 0.320 | 0.320 | 0.320 | 0.352 |
| 20v20 | one moving | 0.021 | 0.227 | 0.286 | 0.380 | 0.320 | 0.320 | 0.320 | 0.360 |
| 20v20 | both stopped | 0.056 | 0.172 | 0.307 | 0.398 | 0.320 | 0.320 | 0.320 | 0.320 |

## Attack-state cuts show penetration is usually inherited from movement

Both-attacking pairs can remain deeply overlapped, but the moving and one-attacker cuts usually reach the deepest separations. This supports a movement-created overlap that can persist after a unit stops, rather than an attack animation independently making allies intangible.

| Ratio | Pair condition | Tape min | Tape p01 | Tape p05 | Tape median | Sim min | Sim p01 | Sim p05 | Sim median |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5v10 | both swing/reload | 0.120 | 0.120 | 0.228 | 0.395 | 0.360 | 0.360 | 0.360 | 0.376 |
| 5v10 | one swing/reload | 0.027 | 0.272 | 0.326 | 0.400 | 0.320 | 0.320 | 0.338 | 0.361 |
| 5v10 | neither swing/reload | 0.027 | 0.141 | 0.253 | 0.380 | 0.320 | 0.320 | 0.320 | 0.338 |
| 5v10 | moving past stopped attacker | 0.032 | 0.292 | 0.331 | 0.400 | 0.320 | 0.320 | 0.360 | 0.360 |
| 10v5 | both swing/reload | — | — | — | — | — | — | — | — |
| 10v5 | one swing/reload | 0.366 | 0.366 | 0.366 | 0.369 | 0.360 | 0.360 | 0.360 | 0.360 |
| 10v5 | neither swing/reload | 0.093 | 0.095 | 0.097 | 0.314 | 0.320 | 0.320 | 0.320 | 0.360 |
| 10v5 | moving past stopped attacker | 0.366 | 0.366 | 0.366 | 0.369 | 0.360 | 0.360 | 0.360 | 0.360 |
| 15v20 | both swing/reload | 0.086 | 0.086 | 0.086 | 0.387 | 0.360 | 0.360 | 0.360 | 0.377 |
| 15v20 | one swing/reload | 0.029 | 0.274 | 0.315 | 0.400 | 0.320 | 0.320 | 0.320 | 0.360 |
| 15v20 | neither swing/reload | 0.003 | 0.176 | 0.284 | 0.379 | 0.320 | 0.320 | 0.320 | 0.344 |
| 15v20 | moving past stopped attacker | 0.029 | 0.249 | 0.325 | 0.400 | 0.320 | 0.320 | 0.320 | 0.360 |
| 20v15 | both swing/reload | — | — | — | — | — | — | — | — |
| 20v15 | one swing/reload | 0.270 | 0.273 | 0.320 | 0.400 | 0.330 | 0.342 | 0.360 | 0.360 |
| 20v15 | neither swing/reload | 0.016 | 0.120 | 0.275 | 0.379 | 0.320 | 0.320 | 0.320 | 0.358 |
| 20v15 | moving past stopped attacker | 0.270 | 0.298 | 0.334 | 0.400 | 0.360 | 0.360 | 0.360 | 0.360 |
| 20v20 | both swing/reload | 0.337 | 0.337 | 0.337 | 0.400 | 0.360 | 0.360 | 0.360 | 0.377 |
| 20v20 | one swing/reload | 0.247 | 0.282 | 0.327 | 0.400 | 0.320 | 0.320 | 0.320 | 0.360 |
| 20v20 | neither swing/reload | 0.012 | 0.160 | 0.278 | 0.378 | 0.320 | 0.320 | 0.320 | 0.357 |
| 20v20 | moving past stopped attacker | 0.247 | 0.297 | 0.328 | 0.400 | 0.326 | 0.346 | 0.360 | 0.360 |

## Deep-tail frequency, not only the extreme

The sub-0.32 shares quantify how often tape positions exceed the engine's ordinary moving/moving compression. Sub-0.20 and sub-0.10 expose the much deeper pass-through tail.

| Ratio | Pair condition | Tape <0.32 | Tape <0.20 | Tape <0.10 | Sim <0.32 | Sim <0.20 | Sim <0.10 |
|---|---|---:|---:|---:|---:|---:|---:|
| 5v10 | both moving | 12.44% | 4.23% | 0.68% | 0.00% | 0.00% | 0.00% |
| 5v10 | one moving | 6.95% | 0.67% | 0.08% | 0.00% | 0.00% | 0.00% |
| 5v10 | both stopped | 12.33% | 4.08% | 0.25% | 0.00% | 0.00% | 0.00% |
| 5v10 | moving past stopped attacker | 2.96% | 0.28% | 0.13% | 0.00% | 0.00% | 0.00% |
| 10v5 | both moving | 52.86% | 36.40% | 14.23% | 0.00% | 0.00% | 0.00% |
| 10v5 | one moving | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| 10v5 | both stopped | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| 10v5 | moving past stopped attacker | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| 15v20 | both moving | 9.56% | 2.49% | 0.89% | 0.00% | 0.00% | 0.00% |
| 15v20 | one moving | 8.73% | 0.60% | 0.18% | 0.00% | 0.00% | 0.00% |
| 15v20 | both stopped | 10.86% | 3.88% | 3.73% | 0.00% | 0.00% | 0.00% |
| 15v20 | moving past stopped attacker | 4.25% | 0.74% | 0.32% | 0.00% | 0.00% | 0.00% |
| 20v15 | both moving | 8.30% | 2.89% | 1.56% | 0.00% | 0.00% | 0.00% |
| 20v15 | one moving | 11.79% | 0.53% | 0.11% | 0.00% | 0.00% | 0.00% |
| 20v15 | both stopped | 17.53% | 2.22% | 0.00% | 0.00% | 0.00% | 0.00% |
| 20v15 | moving past stopped attacker | 3.20% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |
| 20v20 | both moving | 7.82% | 2.23% | 0.78% | 0.00% | 0.00% | 0.00% |
| 20v20 | one moving | 11.59% | 0.73% | 0.12% | 0.00% | 0.00% | 0.00% |
| 20v20 | both stopped | 6.74% | 1.16% | 0.47% | 0.00% | 0.00% | 0.00% |
| 20v20 | moving past stopped attacker | 3.35% | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

## Tape crowd flow turns over faster

Raw overlap frequency alone is misleading: current simulations can spend many frames compressed at their hard floor. Tape generally produces more distinct, shorter interactions and more confirmed pass-throughs per fight-second.

| Ratio | Champions | Tape episodes/s | Sim episodes/s | Tape pass-through/s | Sim pass-through/s | Tape median episode | Sim median episode |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5v10 | 10 | 3.62 | 1.70 | 0.64 | 0.34 | 0.180 s | 0.400 s |
| 10v5 | 5 | 0.27 | 0.45 | 0.00 | 0.06 | 0.118 s | 0.367 s |
| 15v20 | 20 | 9.12 | 2.02 | 1.13 | 0.24 | 0.134 s | 0.392 s |
| 20v15 | 15 | 4.67 | 1.78 | 0.61 | 0.27 | 0.134 s | 0.433 s |
| 20v20 | 20 | 7.86 | 2.85 | 1.02 | 0.25 | 0.132 s | 0.300 s |

## Contact conversion varies by ratio

Nearest-Champion distance is measured when the HCA begins its attack animation and when the projectile releases. Stop exposure is the share of HCA stopping episodes that receive melee hits.

| Ratio | Tape distance at start | Sim | Tape distance at release | Sim | Tape stops hit | Sim | Tape stops multi-hit | Sim |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5v10 | 1.56 | 1.79 | 1.03 | 1.25 | 21.2% | 15.8% | 6.1% | 0.0% |
| 10v5 | 3.68 | 2.79 | 2.78 | 2.31 | 0.0% | 7.1% | 0.0% | 0.0% |
| 15v20 | 1.64 | 2.27 | 1.26 | 1.78 | 8.5% | 4.1% | 1.1% | 1.2% |
| 20v15 | 2.64 | 2.94 | 1.98 | 2.36 | 1.3% | 2.8% | 0.0% | 0.7% |
| 20v20 | 2.18 | 2.78 | 1.71 | 2.18 | 3.4% | 4.2% | 0.7% | 0.0% |

## All-ratio pooled separation distribution

Pooling is used only for the collision distribution, not for battle outcomes, because the five ratios have different force sizes and winners.

| Pair condition | Tape n | Tape min | Tape p01 | Tape p05 | Tape median | Tape <0.32 | Sim n | Sim min | Sim p01 | Sim p05 | Sim median | Sim <0.32 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| both moving | 35428 | 0.003 | 0.098 | 0.239 | 0.380 | 10.28% | 5560 | 0.320 | 0.320 | 0.320 | 0.345 | 0.00% |
| one moving | 50319 | 0.009 | 0.235 | 0.295 | 0.384 | 9.38% | 4225 | 0.320 | 0.320 | 0.320 | 0.360 | 0.00% |
| both stopped | 10471 | 0.038 | 0.086 | 0.278 | 0.399 | 10.83% | 1143 | 0.320 | 0.320 | 0.320 | 0.377 | 0.00% |
| both swing/reload | 3770 | 0.086 | 0.086 | 0.086 | 0.400 | 12.63% | 418 | 0.360 | 0.360 | 0.360 | 0.377 | 0.00% |
| one swing/reload | 19660 | 0.027 | 0.278 | 0.320 | 0.400 | 4.94% | 3714 | 0.320 | 0.320 | 0.320 | 0.360 | 0.00% |
| neither swing/reload | 72788 | 0.003 | 0.140 | 0.271 | 0.379 | 11.06% | 6796 | 0.320 | 0.320 | 0.320 | 0.349 | 0.00% |
| moving past stopped attacker | 15945 | 0.029 | 0.283 | 0.328 | 0.400 | 3.54% | 2541 | 0.320 | 0.320 | 0.360 | 0.360 | 0.00% |

## Outcome context

| Ratio | HCA / Champion | Tape median duration | Sim duration | Tape winner HP | Sim winner HP | Tape survivors | Sim survivors |
|---|---|---:|---:|---:|---:|---:|---:|
| 5v10 | 5 / 10 | 41.08 s | 55.93 s | 316 | 140 | 7 | 2 |
| 10v5 | 10 / 5 | 14.91 s | 15.63 s | 787 | 748 | 10 | 10 |
| 15v20 | 15 / 20 | 49.78 s | 37.72 s | 674 | 899 | 13 | 14 |
| 20v15 | 20 / 15 | 24.62 s | 21.88 s | 1522 | 1496 | 20 | 20 |
| 20v20 | 20 / 20 | 35.73 s | 27.70 s | 1349 | 1457 | 19 | 20 |

## Scope, definitions, and limitations

- Champion overlap uses Chebyshev center separation because Genie obstruction is an axis-aligned box. Normal full contact is 0.40 tiles.
- Moving/stopped is inferred from consecutive decoded positions. Swing/reload is tape action state 7/6 and the equivalent current-engine action.
- A pass-through requires the moving Champion to cross from behind to ahead of the friendly blocker along its currently targeted HCA line while the pair overlaps. Target changes can make this conservative.
- Each tape ratio has five repeats; each simulation ratio has one deterministic exact-placement run. The simulation distribution therefore measures the present deterministic engine, not seed variance.
- The tape trace continues after the last death, but all per-second rates use the fixture's verified last-death time.

## Recommended next step

Test a general allied-transit rule behind an experiment flag: dynamic DAT-derived obstruction for ordinary movement, plus order-coherent pass-through for actively moving allies, while retaining full enemy and obstacle collision and preventing stopped units from initiating new penetration. Validate first against these per-ratio depth, turnover, and HCA-contact measures before considering a default engine change.
