# Heavy Scorpion pass-through bolts — scorpion_vs_arbalester (2026-08-06)

Clean-room derivation of the scorpion bolt from the second ranged archive.
No fitted constants beyond two measured envelope values, both stated with
their measurements.

## Source

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_ranged_scorpionvsarbalester_2026-08-05.zip` | `E99220CE3FECCDC8F8EAEAFEA5070FF058D84F0B209836CEBC8941FF275EED02` |

5 ratios x 5 repeats (25 fights). The companion
`aoe2_golden_ranged_scorpionvschampion` archive
(`30235D984F503172123DFD2D4D24AB9AB513EE57A29C6825AF2252B7879B6EDB`)
contributed damage-table cross-checks; its fights involve the kiting AI and
are calibrated separately.

## Unit identification

**Heavy Scorpion, standard Imperial group** (master 542, slug
`heavy_scorpion`, exported as Japanese; the 22-civ group's finals are
identical): HP 60, range 8, min range 2, reload 3.6 (tape cadence 3.616),
pierce 15 -> 11.0 per full hit on the arbalester (PA 4) and 12.0 on the
champion (PA 5 + infantry-class 2), windup 0.800 s anim x 12/60 = 0.160 s,
projectile 627 at speed 6.0. Chinese (19 attack), Celts (reload 2.88),
Teutons (melee armor 5 vs the tape's champion hits of 17 = 18-1) and the
40-HP civs are all excluded by tape values.

## Measured bolt rules

1. **Pass-through**: dat `vanish_mode 1` on projectile 627 marks the bolt as
   continuing after impact. It damages EVERY enemy whose collision box
   crosses its line — up to 7 victims in one champion-blob shot — each victim
   once per bolt, struck in flight order.
2. **The firer's action target takes full class-rule damage; every other
   victim takes exactly HALF its own post-armor damage** — before or beyond
   the target. 577/577 full-damage hits are the action target; 5407 pass
   hits all measure exactly 0.5x (5.5 / 6.0, fractional HP like trample).
   The ref DB's `pass_through_percent` 0.4286 (projectile/unit attack ratio)
   is contradicted by tape; `PASS_THROUGH_DAMAGE_FRACTION = 0.5` is the
   measured rule.
3. **Corridor width**: victim lateral offsets from the firing line top out at
   0.38 (p99) = victim collision 0.2 + the projectile unit's own dat
   collision half-width 0.1, plus moving-victim blur. The engine uses
   collisionRadius(victim) + projectile_half_width.
4. **Bolt length**: victims appear up to ~3 tiles past the aim point, with
   the overshoot envelope's p95 plateauing at 2.97-3.00 across target
   distances wherever the arena leaves room. `BOLT_OVERSHOOT_TILES = 3.0`
   (measured constant, like the 0.1 melee contact tolerance). Interposed
   enemies short of the target are hit on the way (negative overshoot to
   -4.0 observed).
5. **Minimum range** (dat `min_range` 2.0): fire distances bottom out at
   2.19 center-to-center. `isWithinReach` for ranged units now refuses
   targets closer than min_range, which also removes them as engagement
   candidates. (The skirmisher's min range 1.0 thereby became live in the
   avs matchup: its circuit re-validates unchanged at mean 1.70.)

## Circuit results (25 sampled acquisition orders, pursuit+orders config)

| Ratio | Tape band | Sim median | Band error |
|---|---|---|---|
| 5v10 | −34.7..−25.3 | −26.7 | 0 |
| 10v5 | −94.3..−93.0 | −91.7 | 1.3 |
| 15v20 | −74.2..−67.1 | −67.1 | 0 |
| 20v15 | −90.2..−87.3 | −85.2 | 2.1 |
| 20v20 | −85.3..−80.7 | −83.7 | 0 |

**Mean band error 0.68, 0 wrong winners, 25/25 orders resolve per ratio** —
scorpions crush massed arbalesters in every recorded ratio, and the sim
agrees within ~2 points everywhere.

## Files

- Engine: `src/combat/attacks.js` (pass-through fields in `rangedSpec`,
  measured constants), `src/combat/targeting.js` (min-range gate),
  `src/combat/world.js` (bolt release + pass-through flight).
- Fixture: `fixtures/unit_stats/heavy_scorpion_japanese_imperial.json`
  (exporter emits `pass_through` + `projectile_half_width_tiles`; idle/walk
  animations now tolerate static siege sprites).
- Truth fixture: `calibration/fixtures/scorpion_vs_arbalester_basics.json`.
- Matchup: `src/matchup-playback.js` (`scorpion_vs_arbalester`).
- Tests: `tests/bolt-passthrough.test.mjs`.
