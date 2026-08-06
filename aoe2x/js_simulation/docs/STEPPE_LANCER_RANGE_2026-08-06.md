# Steppe Lancer range-1 mechanics — measured rules and circuit results (2026-08-06)

Clean-room derivation of the Elite Steppe Lancer's 1-range melee mechanics from
the three authorized steppe archives, the dat, and the reference DB. No fitted
constants: every number below is a dat field, a ref-DB final, or a measured
tape invariant with the measurement stated.

## Sources

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_basics_championvssteppe_2026-08-05_complete.zip` | `E9489E7CD3857A37CCB0CB7027237A4583C180EE7DC6203E45408D77F624515A` |
| `aoe2_golden_basics_paladinvssteppe_2026-08-05_complete.zip` | `83E53EA3FEAB1B05FCDD52C16DBD1E80357FF54779AEB1BE940C4B903DD51B41` |
| `aoe2_golden_basics_steppevselephant_2026-08-05_complete.zip` | `5B6A076AD7DF48279290B04521EC86BCC2FF04850309F356C4A98295571ED3E3` |

9 ratios × 3 repeats per archive (1v1 1v2 2v1 2v3 3v2 3v5 3v6 5v3 6v3), full-
rate `raw recordings/*.frames.bin` decoded with `tools/decode_tape_frames.py`.

## Unit identification

The steppe side is the **Cumans Elite Steppe Lancer** (master 1372, ref slug
`elite_steppe`): tape HP 100 and swing cadence ~2.02 s eliminate Khitans
(HP 80), Mongols (HP 124), and Jurchens (reload 1.6); observed damage
11/hit vs Champions (15 − 4) and 9/hit vs Elephants (15 − 6) confirms
attack 15 / melee armor 3; the Cuman-only speed 1.6785560 (Steppe Husbandry,
`ref_stat_chain` final step) matches the traces. Fixture:
`fixtures/unit_stats/elite_steppe_lancer_cumans_imperial.json`
(range 1.0, reload 2.0, attack delay 1.5 s × 13/60 frames = 0.325 s,
collision half-extent 0.25, outline half-extent 0.4, blast gated off).

## Measured rules

1. **Attack eligibility is Chebyshev over OUTLINE boxes: gap ≤ range + 0.1.**
   `outline_size` is a distinct dat field from `collision_size` (Champion
   0.2/0.2, Paladin 0.4/0.25, Steppe Lancer 0.4/0.25, Battle Elephant
   0.5/0.25). Across 2158 stationary swings in the three steppe archives the
   outline Chebyshev gap never exceeds range + 0.1 (lancer envelope top
   1.0850 of 1.1; Champion −0.05 of 0.1), while the collision-box gap reaches
   1.33 — collision-based reach is impossible. Euclidean outline distance is
   refuted by 30 diagonal-contact swings (outline Euclid up to 0.135 > 0.1
   while Chebyshev is −0.06). Engine: `isWithinReach` / `outlineChebyshevGap`
   in `src/combat/targeting.js`.
2. **Movement stop is over COLLISION boxes: gap ≤ max(range, 0.1).**
   Approach stops are victim-invariant only in collision terms: p50 0.95,
   p90 0.995 against every victim type, with no mass in (1.0, 1.1] — the
   lancer stops at gap 1.0, range-0 units keep the long-established 0.1.
   Units walk deep INSIDE their outline attack envelope before stopping.
   Engine: `isWithinStopRange` in `src/combat/attacks.js`.
3. **A swing starts only from a standstill** — stop rule satisfied against the
   engaged target, or the unit did not move this tick (blocked or parked).
   Approaching lancers never swing mid-walk in the tapes; blocked back-line
   lancers swing from the outer envelope. This split is what produces the
   lancer's signature stacking: 801 of 1507 lancer hits (53%) land while a
   closer ally to the victim exists — the back line fighting over the front
   line. Engine: the moved/stop gate in `progressAttacks`.
4. **Pursuit-priority applies at stop range, not outline range.** A unit
   prefers its pursuit target once it has closed to its stop distance
   (identical to the old collision engine for range-0 units). Widening the
   priority to the outline envelope re-focuses fire enough to swing
   paladin_vs_elephant 5v3 from band error 0.4 to 10.7; blocked units farther
   out engage through the outline fallback instead.
5. **Attack-action persistence:** a unit shoved out of reach that tries to
   close and is fully blocked keeps its attack cycle on its live target
   (LOS-bounded). Measured directly: a pve 5v3 paladin fights from collision
   gap 0.523–0.575 for 25 s after the scrum separates the pair (action state
   cycling 6/7, same target throughout); lancer tail hits lag their reach by
   exactly one reload. Champions show zero persistence cases in ~1200 swings
   across five archives — they are never pushed apart — and the champion
   mirror stays bit-identical with the rule in place.
6. **No engagement before first acquisition.** Outline reach can span the
   spawn bands (steppe-vs-elephant 1v1 spawns sit at exactly outline gap
   1.1) but no unit ever swings before its acquisition delay has run.

## Circuit results (25 sampled acquisition orders, pursuit+orders config)

Signed winner-HP% band scoring vs the 3-repeat tape bands:

| Matchup | Mean band error | Wrong winners | Worst ratio |
|---|---|---|---|
| champion_vs_steppe | 0.77 | 0 | 5v3 +4.3 |
| paladin_vs_steppe | 1.87 | 0 | 2v3 −13.8 |
| steppe_vs_elephant | 0.41 | 0 | 5v3 +1.9 |
| champion_vs_elephant (regression) | 0.38 | 0 | — unchanged from elephant phase |
| paladin_vs_elephant (regression) | 0.21 | 0 | better than elephant phase (0.26) |
| champion_vs_paladin (regression) | 1.07 | 0 | 9v4 6.6 — **was 3.60 / worst 10.1** |

The outline/stop-range split measured on the steppe tapes retroactively fixed
most of the champion-vs-paladin residual (15v10 −10.1 → 4.2, 9v4 +10.0 → 6.6).

**Accepted residual:** paladin_vs_steppe 2v3 (−44.4 median vs tape
−19.4..−30.6). Knife edge: all three lancers open on paladin 1628 (spawn
nearest), whose death takes exactly 18 lancer hits (180.0 damage on 180 HP).
The identity order is 2.7 off the band (1628 survives at 10 HP, 17 hits);
sampled orders kill 1628 in 41/201 runs vs the game's 3/3. Same
sampling-over-dispersion class as the documented cvp 9v4/15v10 residuals.

## Files

- Engine: `src/combat/targeting.js`, `src/combat/attacks.js`,
  `src/combat/world.js` (movedIds/blockedIds plumbing, persistence,
  acquisition gate).
- Fixtures: `fixtures/unit_stats/elite_steppe_lancer_cumans_imperial.json`,
  `calibration/fixtures/{champion_vs_steppe,paladin_vs_steppe,steppe_vs_elephant}_basics.json`.
- Matchups: `src/matchup-playback.js` (three new entries; viewer picks them up
  from `/api/matchup/list` automatically).
- Tests: `tests/steppe-range.test.mjs` (stop range, outline Chebyshev reach,
  back-line stacking world run, pre-acquisition gate);
  `tests/world-tick.test.mjs` stop-range test updated.
