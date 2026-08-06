# Ranged combat v1 — Arbalester vs Elite Skirmisher (2026-08-06)

Clean-room derivation of projectile combat from the first authorized ranged
archive, the dat, and the reference DB. No fitted constants.

## Source

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_ranged_arbalestervseliteskirm_2026-08-05.zip` | `CE7B5D34F9C41C1EE379DB08FFE4155E3A36D2757A06820283ED4453B004CF93` |

New ranged format: 5 ratios (5v10, 10v5, 15v20, 20v15, 20v20) x **5 repeats**
per ratio, armies up to 40 units. 25 fights, 6312 recorded shots.

## Unit identification

Both sides resolve to the Chinese stat groups (identical finals across an
11-civ / 17-civ cluster; Chinese matches the recorder's pattern):

- **Arbalester** (master 492, slug `arbalester`): HP 40, range 8, reload 1.7
  (tape cadence 1.716), pierce 10 -> 2.0 per hit on the skirmisher (PA 8),
  windup 0.770 s anim x 20/45 = 0.342 s, projectile 507 at speed 7.0.
- **Elite Skirmisher** (master 6, slug `imp_elite_skirm`): HP 35, range 8,
  reload 3.0 (tape 3.018), attack 7 + 4 anti-archer -> 7.0 per hit on the
  arbalester, windup 1.200 s anim x 19/45 = 0.507 s, min range 1.0
  (unexercised in these tapes — exported, not yet enforced), projectile 366
  at speed 7.0.

Off-value damage entries (5.0, 1.0) are overkill-clamped killing blows.

## Measured rules

1. **The ranged attack cycle IS the melee cycle** — same stop rule, same
   standstill gate, same windup frame, same reload cadence — with damage
   delivered by a projectile instead of a contact hit.
2. **Projectile reach is a EUCLIDEAN circle; melee reach stays Chebyshev.**
   Across 6312 shots the maximum fire distance is 8.56 = range 8 + 0.1
   tolerance + both 0.2 outlines, in formations full of diagonal geometry — a
   Chebyshev rule at range 8 would produce fire distances beyond 11, and none
   exist. The steppe phase's 30 diagonal-contact swings prove the melee
   (range 0-1) envelope is Chebyshev over outline boxes. Box adjacency for
   arms' reach; a range circle for shots. The movement stop rule follows the
   same metric split (collision boxes, max(range, 0.1)).
3. **The projectile is a physical point** flying the firer->target line at
   the projectile unit's dat speed (7.0; measured 7.34 p50 at the recorder's
   10 Hz missile sampling), aimed at the target's position at FIRE time
   (dat smart_mode 0: no leading). It hits the moment it meets the target's
   collision box — an APPROACHING target walks into it early (tape hits show
   displacement up to 1.04 toward the shooter) — and expires at its aim point
   if the target left its box (walked-away misses start at displacement
   0.23) or died mid-flight.
4. **98.7% of shots resolve deterministically**: 5141 hits, 1068 dead-target
   misses, 23 walked-away misses, and 80 (1.27%) unexplained stationary
   misses — the accuracy-roll residue (ref DB final accuracy 100 for both
   civs' groups). The deterministic engine does not simulate the residue;
   documented ~1% overshoot.
5. **The damage class rule generalizes**: archers carry their base attack in
   class 3 (no class-4 entry at all); class 4 and class 3 are ordinary armor
   classes under one shared rule, then bonus classes stack (the skirmisher's
   7.0 = pierce 7−4 plus anti-archer 4−0).
6. **Fight clock**: the tape's own 20v15 fights run 56.5-59.8 s; the engine's
   runaway guard ceiling was raised 3600 -> 9000 ticks (default unchanged at
   3600; ranged playbacks pass a higher maxTicks) so max-range attrition
   endgames are not censored.
7. **Idle rescue generalizes**: survivors of 40-unit ranged fights can end up
   beyond line of sight with no pursuit target; the AI-order rescue now also
   covers standing units with NO pursuit (post-acquisition), matching the
   tape AI whose designations are roster-wide and never LOS-gated. Melee
   playbacks are unaffected (all 10 prior matchups + the champion mirror stay
   bit-identical, 72/72 hashes).

## Circuit results (25 sampled acquisition orders, pursuit+orders config)

| Ratio | Tape band (signed winner-HP%) | Sim median | Band error |
|---|---|---|---|
| 5v10 | +86.9..+88.6 | +86.3 | 0.6 |
| 10v5 | −61.3..−58.3 | −61.3 | 0 |
| 15v20 | +66.0..+71.6 | +65.7 | 0.3 |
| 20v15 | −13.9..+8.2 (tape flips winner) | +12.6 | 4.4 |
| 20v20 | +41.6..+52.6 | +38.4 | 3.2 |

**Mean band error 1.70, 0 wrong winners, 25/25 sampled orders resolve on
every ratio.** The 20v15 residual sits on the knife edge the tape itself
flips across repeats.

## Files

- Engine: `src/combat/attacks.js` (`rangedSpec`, generalized
  `calculateDamage`, metric-split `isWithinStopRange`),
  `src/combat/targeting.js` (metric-split `isWithinReach`),
  `src/combat/world.js` (`releaseRangedShot`, stepped-flight projectile
  processing, tick-guard split), `src/combat/ai-orders.js` (pursuit-less idle
  rescue).
- Fixtures: `fixtures/unit_stats/arbalester_chinese_imperial.json`,
  `fixtures/unit_stats/elite_skirmisher_chinese_imperial.json` (exporter now
  emits a `ranged` block).
- Truth fixture: `calibration/fixtures/arbalester_vs_eliteskirm_basics.json`
  (5-repeat schema).
- Matchup: `src/matchup-playback.js` (`arbalester_vs_eliteskirm`).
- Tests: `tests/ranged-attack.test.mjs`; `tests/world-tick.test.mjs` ceiling
  test updated to 9000.
