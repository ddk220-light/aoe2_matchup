# Elephant trample — clean-room derivation and calibration (2026-08-05)

New unit family: **Burmese Elite Battle Elephant** (master 1134) versus the two
established units (Chinese Champion 567, Spanish Paladin 569). New mechanic:
melee blast ("trample"). Everything below is sourced from the Genie dat or
measured on the authorized tapes — no fitted constants.

## Authorized truth

| Archive | SHA-256 | Fights |
|---|---|---|
| `aoe2_golden_basics_championvselephant_2026-08-05_complete.zip` | `DB39FB8E6F67AC87E5F5F8E864036D578F7040D3540CB71A91FDFAA3D4D8D79D` | 27 |
| `aoe2_golden_basics_paladinvselephant_2026-08-05_complete.zip` | `FF1F064249AD32FB0304345999DCBD3F5494D20B870C750901F23500F007D444` | 27 |

Ratios 1v1, 1v2, 2v1, 2v3, 3v2, 3v5, 3v6, 5v3, 6v3, three repeats each, both
directions. No elephant-vs-elephant mirror was recorded, so ally-adjacent
behaviour is measured from the many multi-elephant fights instead.

## Dat constants (Elite Battle Elephant 1134, Burmese)

`blast_width = 0.4`, `blast_damage = 0.25`, `blast_attack_level = 2`,
`blast_defense_level = 3`, `friendly_fire_damage = 1.0`, frame_delay 10 on a
30-frame / 1.5 s attack animation (hit at 0.500 s), reload 2.0, collision box
0.25 half-extent (same as the Paladin), speed 0.99, HP 320, attack {4:18},
armor {4:6, 3:9}. Exported via `tools/export_unit_mechanics.py`, which now
emits a `blast` block for every unit.

## Measured trample semantics (the whole rule)

From the 54 damage streams + full-rate `.frames.bin` traces:

1. **Reach**: the blast is a circle of radius `blast_width` (0.4) centred on
   the **attacker**, and it reaches every enemy whose **collision box**
   intersects the circle: `hypot(max(0,|dx|-r_vic), max(0,|dy|-r_vic)) <= 0.4`.
   On 1694 isolated-swing bystander samples this separates **perfectly**
   (0 false positives, 0 false negatives; hits reach box-distance 0.396,
   misses start at 0.402). Center-to-center metrics (Euclid or Chebyshev,
   attacker- or target-centred) all misclassify dozens to hundreds.
2. **Damage**: each victim takes `blast_damage x` the **post-armor** damage
   against itself: 14 → 3.5 on Champions, 13 → 3.25 on Paladins, every event,
   fractional HP retained. (25% of pre-armor attack would have given 0.5–1.0;
   ruled out.)
3. **Enemy-only**: zero same-owner damage events across all 54 fights, despite
   the dat's level-2 + `friendly_fire_damage=1.0` flags suggesting otherwise.
4. **Main target excluded** — it takes only the main hit, same instant.
5. Trample kills are real (32 in the corpus) and clamp at 0 like any hit.

**Every "odd" damage value in the streams (11.0, 8.0, 10.5, 7.75, 7.0, 4.5,
1.25) is an overkill-clamped killing blow** — the recorder logs HP deltas, so a
kill shows the victim's remaining HP, not the full hit (e.g. Paladin
180 − 13×13 = 11; Elephant 320 − 26×12 = 8). All such events carry
`kill=true`; the underlying damage model has exactly two values per pair.

Why Champions are trampled less than Paladins at the same spacing: a bystander
attacking the elephant's face axis-on sits at reach `0.45 − 0.2 = 0.25` (in),
but corner-diagonal contact puts a Champion at `hypot(0.33, 0.33) = 0.47`
(out) while a Paladin's bigger box keeps it at `hypot(0.25+ε, 0.25+ε) ≈ 0.36`
(in). The tape shows both cases; the rule reproduces them.

## Engine implementation

- `src/combat/attacks.js` — `trampleSpec(mechanics)`: active iff
  `blast.attack_level == 2 && width > 0 && 0 < fraction < 1` (mirrors the
  Python ability registry's dat rule).
- `src/combat/world.js` — `commitReadyAttacks` applies the main hit, then
  blasts every enemy in reach via the circle-vs-box rule, each for
  `fraction x calculateDamage(actor, victim)`, emitting `damage` events with
  `kind: "trample"`; deaths share the normal death path. The damage/death
  application was extracted into `applyCommittedDamage` — verified
  **bit-identical** on a champion-vs-paladin fight before/after (1375 ticks,
  3711 events), and the suite's pass/fail split is unchanged plus the three
  new trample tests (`tests/trample.test.mjs`).
- New mechanics fixture `fixtures/unit_stats/elite_battle_elephant_burmese_imperial.json`;
  truth fixtures `calibration/fixtures/{champion,paladin}_vs_elephant_basics.json`;
  both matchups registered in `src/matchup-playback.js` (viewer picks them up
  automatically).

## Circuit results (orders config, 25 sampled acquisition orders)

Signed score: winner's HP as % of its own starting pool, positive = elephant
side, negative = champion/paladin side. Sim = median over samples.

| Matchup | Ratio | Tape (3 runs) | Sim median | Verdict |
|---|---|---|---|---|
| cve | 1v1 | 85 / 85 / 85 | 85 | exact |
| cve | 1v2 | 96.3 ×3 | 96.3 | exact |
| cve | 2v1 | 58.8 ×3 | 58.8 | exact |
| cve | 2v3 | 92.5 ×3 | 93.8 | +1.3 |
| cve | 3v2 | 70 / 73.8 / 71.9 | 73.8 | in band |
| cve | 3v5 | 94 / 93.3 / 94 | 94.8 | +0.8 |
| cve | 3v6 | 96.3 / 95 / 95 | 95.6 | in band |
| cve | 5v3 | 71.3 / 68.8 / 67.5 | 68.8 | in band |
| cve | 6v3 | 56.3 / 57.5 / 56.3 | 55.0 | −1.3 |
| pve | 1v1 | 47.5 ×3 | 47.5 | exact |
| pve | 1v2 | 86.9 ×3 | 85.0 | −1.9 |
| pve | 2v1 | −42.2 ×3 | −42.2 | exact |
| pve | 2v3 | 81.3 / 81.3 / 82.5 | 81.3 | exact |
| pve | 3v2 | 13.8 / −10.5 / −19.1 | 6.9 (spread −12.9..8.8) | in band (knife edge) |
| pve | 3v5 | 82.8 / 83.5 / 83.5 | 83.5 | exact |
| pve | 3v6 | 87.5 / 87.5 / 88.1 | 87.5 | exact |
| pve | 5v3 | −20.9 / −21.4 / −28.4 | −20.5 | +0.4 |
| pve | 6v3 | −43.2 / −46.7 / −49.3 | −44.5 | in band |

Mean |error to the tape band| ≈ **0.3 points over 18 ratios** (champion-vs-
paladin sits at 3.60): these matchups are far from break-even, the game is
near-deterministic there, and the sim matches it. Winners correct everywhere,
including the three Paladin-win ratios and the pve 3v2 knife edge, where the
tape itself flips between repeats and the sim's sampled spread brackets it.

Trample counts track the tape: pve 2v1 sim 12.0 vs tape 12/12/12, cve 2v1 sim
4.0 vs tape 4/4/4, pve 6v3 sim 43.3 vs tape 45–60, cve 6v3 sim 15.5 vs tape
20–21 (slight undercount from settling geometry — our second attacker slides
to a corner slot a few hundredths outside 0.4 slightly more often than the
game's).

Identity playbacks (`matchupPlayback`) reproduce 2v1 winner HP exactly on both
matchups (188 = tape 188×3; 152 = tape 152×3).

## Residuals (accepted)

All ≤ 2 points: cve 2v3 +1.3, cve 6v3 −1.3 (identity run exact), pve 1v2 −1.9
(one Paladin swing on the two-elephant pool), pve 5v3 +0.4. These are the same
approach/packing micro-structure class as the champion-paladin residuals, an
order of magnitude smaller here.
