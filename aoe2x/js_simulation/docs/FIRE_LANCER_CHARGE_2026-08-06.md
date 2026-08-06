# Fire Lancer charge mechanics — measured rules and circuit results (2026-08-06)

Clean-room derivation of the Elite Fire Lancer's charge-projectile attack from
the four authorized firelancer archives, the dat, and the reference DB. No
fitted constants: every number is a dat field, a ref-DB final, or a measured
tape invariant with the measurement stated.

## Sources

| Archive | SHA-256 |
|---|---|
| `aoe2_golden_basics_championvsfirelancer_2026-08-05_complete.zip` | `5153D9DA1B36746747CA5DEEF131DAB1C79B4B88FA12DA9362250D0C16026D34` |
| `aoe2_golden_basics_paladinvsfirelancer_2026-08-05_complete.zip` | `D11AD63EADC47F5B530755FD872C7351F577CABD8167037629D71018E9AF575D` |
| `aoe2_golden_basics_firelancervssteppe_2026-08-05_complete.zip` | `3F86AD81941BF9A04B47328495EDD4F928B4D13CEAEABF8A925869F97FD3C563` |
| `aoe2_golden_basics_firelancervselephant_2026-08-05_complete.zip` | `3047D2EFD6102E2D6594B8AE7BD96DEC57B9A73C1A664A903E8F1E2670885ED9` |

9 ratios x 3 repeats per archive (108 fights), full-rate `raw recordings/
*.frames.bin` decoded with `tools/decode_tape_frames.py`, plus the archives'
`decoded/*.damage.jsonl.gz` and `decoded/*.missiles.jsonl.gz` streams.

## Unit identification

The fire side is the **Chinese Elite Fire Lancer** (master 1903, ref slug
`elite_fire_lancer`): measured walk speed is exactly 1.1616 tiles/s across
30,665 full-rate samples (`ref_stat_chain` final 1.1616011; the only other
attack-14 candidate, Khitans, moves 1.06), melee damage is 10 vs Champions /
24 vs Paladins / 26 vs Steppe Lancers / **38 vs Elephants** (the +15 cavalry
and +15 elephant bonus classes both land), cadence 2.016 s (reload 2.0 rules
out Jurchens' 1.6), and HP is 85. Champions deal 21 to it — their +8
anti-eagle bonus applies because the Fire Lancer carries armor class 29.
Fixture: `fixtures/unit_stats/elite_fire_lancer_chinese_imperial.json`
(collision/outline 0.2/0.2, melee windup 1.25 s anim x 10/30 = 0.4167 s,
tape floor 0.418).

## Measured charge rules (all dat-sourced unless stated)

1. **The charge fires `max_total_projectiles` = 3 projectiles of unit 1925 as
   the unit's FIRST attack cycle** (`charge_type` 6, `charge_projectile_unit`
   1925). Units spawn with full charge (`max_charge` 1.0); all 265 recorded
   volleys are opening attacks; at `recharge_rate` 1/30 s no fight leaves a
   unit in combat 28 s after firing, so refire semantics are untestable and
   the engine simply runs the dat regen.
2. **The charge cycle runs on the dat `special_graphic` 13067 animation**
   (30 frames x 0.0667 s = 2.000 s; `charge_event` 5 selects it) with the
   volley released on animation frame `frame_delay` 10: 2.000 x 10/30 =
   **0.6667 s windup** — tape floor 0.668 across 265 volleys, one render
   frame wide. Melee cycles keep the 1.25 s attack graphic (release 0.4167 s).
3. **Fired from a standstill at the acquisition target, 1.5–5.2 tiles out**
   (line of sight 6.0 bounds it), with no closing beforehand, and the unit
   stands through the whole 2.0 s charge animation: first post-volley
   movement at +1.408 s p50 (p10–p90 spread 16 ms) = animation end 1.333 s
   plus the recorder's 0.05-tile movement-detection lag. The unit's regular
   reload (2.0 s) runs from the charge swing start (minimum charge-to-melee
   swing gap 2.016 s).
4. **Each projectile deals the class-matched attack total with the victim's
   armor VALUES ignored**: Champions (pierce armor 5), Paladins (7), Steppe
   Lancers (6) and Elephants (9) all take exactly 3.0 — 684/684 damage
   events, which is projectile 1925's class-3 pierce amount alone. Flight at
   the projectile's dat speed 7.5 tiles/s (measured 7.34 p50 at 10 Hz
   sampling); a projectile whose target dies mid-flight vanishes (the two
   zero-damage volleys).
5. **Volley spread — accepted residual.** 88% of tape hits land on the
   volley's target and 2.58 of 3 projectiles land on average,
   victim-size-independent (events-per-volley is statistically identical
   against 0.2-box Champions and 0.5-box Elephants). The in-game scatter
   (dat dispersion 0.3, spawning area 2x2) is not resolvable at the
   recorder's 10 Hz missile sampling — measured side-shot aim offsets range
   5–40 degrees off the target line. The engine flies all three projectiles
   at the target: ~1 damage/volley overshoot, which crosses no kill
   threshold in any recorded matchup (all four opponents' hits-to-kill are
   unchanged by 3 vs 9 charge damage).
6. **Completing the charge cycle re-enters combat through the engine's
   acquisition reaction lag** (the unit's own measured draw from
   Uniform[0.952, 1.708] s — no new constants). Across byte-identical cvf 1v1
   repeats the first post-charge melee swing lands at 5.56 / 5.87 / 6.85 s —
   a 1.3 s spread carrying the acquisition-roll signature, incompatible with
   any deterministic cycle rule; walking units (fvs/fve) still close during
   the lag and swing ~0.6 s after reach entry. Without this rule the sim
   swings at the earliest edge of every band and each lancer gains a full
   melee hit (cvf mean band error 6.32 instead of 2.41).

## Circuit results (25 sampled acquisition orders, pursuit+orders config)

| Matchup | Mean band error | Wrong winners | Worst ratio |
|---|---|---|---|
| champion_vs_firelancer | 2.41 | 0 | 2v3 +8.6 |
| paladin_vs_firelancer | 0.40 | 0 | 3v5 +3.0 |
| firelancer_vs_steppe | 3.57 | 0 | 3v5 +13.0 |
| firelancer_vs_elephant | 0.72 | 0 | 6v3 −4.0 |

Regression: all six previously converged matchups and the champion mirror are
**bit-identical** (72/72 final-state and event-log hashes unchanged), and the
test suite keeps exactly its 26 pre-existing failures (124/150 pass, 4 new
charge tests).

**Accepted residuals:** firelancer_vs_steppe 3v5 (+13.0) and 3v6 (+10.3) are
systematic — even the sim's sampled minimum sits above the tape band, the
documented over-focus class from the cvp phase (sim fire lancers land ~1
fewer melee hit each against the lancer crowd). champion_vs_firelancer 2v3
(+8.6) is sampling-class: the tape band [33.7, 42] lies inside the sim spread
[34.1, 58.4] and the median draws high.

## Files

- Engine: `src/combat/attacks.js` (`chargeSpec`, `chargeProjectileDamage`),
  `src/combat/world.js` (charge cycle in `progressAttacks`,
  `releaseChargeVolley`, `processChargeProjectiles`, `holdsForChargeVolley`
  movement hold, post-charge re-acquisition), `src/combat/unit-state.js`
  (gated `charge` + `acquireDelayTicks` unit state).
- Fixture: `fixtures/unit_stats/elite_fire_lancer_chinese_imperial.json`
  (exporter now emits a `charge` block).
- Truth fixtures: `calibration/fixtures/{champion_vs_firelancer,
  paladin_vs_firelancer,firelancer_vs_steppe,firelancer_vs_elephant}_basics.json`.
- Matchups: `src/matchup-playback.js` (four new entries; the viewer lists
  them via `/api/matchup/list`).
- Tests: `tests/fire-lancer-charge.test.mjs`.
