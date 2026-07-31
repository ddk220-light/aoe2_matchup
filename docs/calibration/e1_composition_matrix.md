# E1 composition matrix — do C2A / P2 / P1 compose with orbitKite?

**Question.** E1.orbitKite reproduces the tapes' kiting geometry but drops the
full board 194/216 → 181/216, all in ranged-vs-melee knife edges, because the
orbiting kiter is caught mid-orbit by a full-cadence chaser. Three tape-true
kiter-side mechanisms are built, wired, tested and shipped OFF — C2A
(contact break, `contactBreak,breakPriority`), P2 (trailing-window intercept
lead, `R5D1.trailingWindowLead`) and P1 (reduced-damage displaced hits,
`R5D1.reducedDamageHits`). Each was refuted in isolation during Phase C while
the kiter was physically boxed in — a blocker E1 has removed. This round
measures whether they compose with E1. **Measurement only: no flag default
changed.**

## Method

- Runner: `node tools/simjs/calib_runner.mjs --seeds 20 --workers 8 --tags-file
  <subset> --out-dir <dir>` plus per-config `--e1/--c2a/--r5d1` overrides
  (shipped defaults for everything else); arena `tapebox` (default), tape
  first-frame spawns. Scored with `python -m aoe2x.calibration.score --tags
  <subset> --sim-runs-dir <dir>` — the exact flow of the night boards.
- **Subset (matrix runs): 133 fights** = ranged-vs-melee (102) +
  ranged-vs-ranged (6) + **siege-involved (25)**. Pure melee-vs-melee (83) is
  excluded on proof, not assumption: those fights contain no projectile-firing
  unit (P1/P2 live only in the shared ranged launch path,
  `aimPointFor`/`willHit`) and no ranged victim (C2A's latch needs a melee hit
  on a non-siege ranged unit) — and the final full-corpus run confirmed the
  whole melee class **byte-identical** to night-final (0 of 1660 seed files
  differ). Siege fights were *included* rather than assumed inert because the
  siege lines fire through the same launch path: P2 did in fact move them
  (measured below), so the "untouched by ranged scoping" claim is false for
  P2+siege and the subset choice was load-bearing.
- Config A (E1 solo) reuses the existing full-gate run
  (`20260731T145539Z-e1-orbitkite-on.json`), sliced to the same 133 fights.
  Night-final baseline: `20260731T112133Z-night-final.json` (194/216; subset
  slice 127/133 — r-v-m 97/102, r-v-r 6/6).
- E1 spec is `orbitKite` alone (pure tangent — the shipped variant; the blend
  was refuted in the E1 round). C2A spec is the full pair
  `contactBreak,breakPriority`.
- KPI methodology validated by reproducing the E1 round's published ledger
  numbers exactly: control (night-final files) champ dmg/run 145.0 / camel
  590.5 / HC land 85.3%; E1-on 720.0 / 539.6 / ~84%.
- Determinism check: the subset run of the winning config and its later
  full-corpus run are byte-identical on all 133×20 shared seed files.

Scoreboards (data/calibration/runs/):
`20260731T150703Z-e1mx-B-e1-c2a-tags=…7bf53a20.json`,
`…150706Z-e1mx-C-e1-p2-…`, `…150708Z-e1mx-D-e1-c2a-p2-…`,
`…150711Z-e1mx-E-e1-p1-…`, `…150713Z-e1mx-F-e1-c2a-p2-p1-…`,
full corpus: `20260731T151026Z-e1mx-FULL-E-e1-p1.json`.

## Matrix (subset: 133 fights, 20 seeds)

Winners and mean side HP-pts (100·|Δhp_remaining|/army max HP — the hp_pts
convention; fight pts = mean of its two sides).

| config | subset winners | r-v-m | r-v-r | siege | mean pts |
|---|---|---|---|---|---|
| night-final (no E1) | 127/133 | 97/102 · 9.90 | 6/6 · 2.33 | 24/25 · 9.62 | 9.51 |
| A: E1 | 114/133 | 84/102 · 16.13 | 6/6 · 2.33 | 24/25 · 9.62 | 14.28 |
| B: E1+C2A | 113/133 | 83/102 · 19.93 | 6/6 · 2.33 | 24/25 · 9.62 | 17.20 |
| C: E1+P2 | 114/133 | 84/102 · 15.65 | 6/6 · 2.16 | 24/25 · 9.25 | 13.84 |
| D: E1+C2A+P2 | 112/133 | 82/102 · 19.28 | 6/6 · 2.16 | 24/25 · 9.25 | 16.62 |
| **E: E1+P1** | **115/133** | 84/102 · 16.65 | 6/6 · 2.77 | **25/25** · 9.09 | 14.60 |
| F: E1+C2A+P2+P1 | 112/133 | 82/102 · 20.61 | 6/6 · 2.45 | 24/25 · 8.83 | 17.57 |

### Knife-edge families (winners / mean fight pts)

| family | night-final | A: E1 | B | C | D | E | F |
|---|---|---|---|---|---|---|---|
| champion__vs__arbalester (6) | 6/6 · 1.9 | 0/6 · 53.2 | 0/6 · 59.5 | 0/6 · 55.1 | 0/6 · 58.5 | 0/6 · 53.2 | 0/6 · 58.5 |
| champion__vs__heavy_cav_archer (9) | 8/9 · 18.4 | 1/9 · 32.6 | 1/9 · 45.1 | 1/9 · 32.6 | 1/9 · 45.0 | 1/9 · 32.6 | 1/9 · 45.0 |
| halberdier__vs__heavy_cav_archer (6) | 6/6 · 4.4 | 6/6 · 13.1 | 6/6 · 13.1 | 6/6 · 13.1 | 6/6 · 13.1 | 6/6 · 13.1 | 6/6 · 13.1 |
| hand_cannoneer__vs__heavy_camel (6) | 6/6 · 19.5 | 6/6 · 15.8 | 6/6 · 19.3 | 6/6 · **10.5** | 6/6 · 14.7 | 6/6 · 20.4 | 6/6 · 29.3 (agr 0.55) |
| arbalester__vs__elite_steppe (6) | 6/6 · 11.3 | 6/6 · 14.9 | 6/6 · 19.0 | 6/6 · 14.9 | 6/6 · 18.9 | 6/6 · 14.9 | 6/6 · 18.9 |

### KPI ledgers (20 seeds)

| KPI | ledger target | control | A: E1 | B | C | D | E | F |
|---|---|---|---|---|---|---|---|---|
| champ dmg/run, champ_vs_arb | ~603 | 145 | 720 | 720 | 720 | 720 | 720 | 720 |
| camel dmg/run, HC_vs_camel | ~273 | 591 | 540 | 607 | 468 | 551 | 642 | 723 |
| HC land rate, same fight | ~86% | 85.3% | 83.9% | 86.4% | 90.0% | 91.2% | **86.7%** | 93.7% |

720 exactly = the arbalester army's whole HP pool (18×40): in every config,
every seed, the arbs still get wiped — no kiter-side mechanism moves the
champion knife edge at all. (P1 raises the *measured* land rate partly by
adding half-damage displaced hits as landed events; P2 raises the true one by
better lead.)

### Canaries (4)

Every E1 config: champion__vs__arbalester **FAIL 0/6 (agr 0.0)**;
halberdier__vs__heavy_cav_archer PASS 6/6; arbalester__vs__elite_steppe PASS
6/6; hand_cannoneer__vs__heavy_camel PASS 6/6 (agr: A/C 1.00, D/E 0.90,
B 0.85, F 0.55 — F is one seed-flip from losing the P1 canary family).

## What composes, what doesn't

- **C2A is strictly negative under E1** (B vs A: −1 winner, +2.9 mean pts,
  champ_vs_arb 53.2 → 59.5, champ_vs_HCA 32.6 → 45.1, and +2 to +9 pts of
  drag across a dozen uninvolved r-v-m families). The break bearing no longer
  fights a boxed-in geometry — it now fights the *orbit*, kicking the kiter
  off its tape-shaped circle. Refuted in composition, same verdict as
  isolation.
- **P2 is orthogonal to the E1 losses.** C vs A: zero winner flips, and the
  two champion knife-edge families are pts-identical — the lead does not
  touch what E1 broke. It *does* fix real things: HC_vs_camel 15.8 → 10.5 pts
  (best of any config), camel dmg/run 540 → 468 (toward the 273 ledger), and
  it moves siege fights (siege_onager__vs__hussar −7.8 pts,
  heavy_scorpion__vs__heavy_camel −5.2, but elite_fire_lancer__vs__siege_onager
  +6.8) — net siege pts 9.62 → 9.25, winners unchanged. Its cost: HC land
  rate overshoots to 90% (the compensating-error account in constants.js,
  live and measurable).
- **P1 is surgical and net-positive on winners.** E vs A: touches only three
  families ≥2 pts, gains hand_cannoneer__vs__heavy_scorpion (−14.5 pts, the
  one siege fight night-final loses → siege 25/25), loses nothing. Cost:
  HC_vs_camel +4.6 pts and agr 1.0 → 0.9, camel dmg/run drifts to 642 — the
  documented P1 knife-edge risk, short of a flip.
- **The full stack F is the worst config** (112/133, 17.57 pts, HC_vs_camel
  agr 0.55): C2A's drag plus P1+P2 stacking their land-rate overshoots
  (93.7%).

## Decision and full-corpus gate

Priority order (canaries → subset winners → KPI proximity → mean pts):
canaries tie at 3/4 (champion__vs__arbalester fails 0/6 in *every* E1
config), so subset winners decide: **E (E1 + P1), 115/133**, with the best
land-rate KPI (86.7% vs ~86% ledger) as confirmation. Note C ties A at
114/133 with better mean pts (13.84) and the best camel KPI — if the later
re-gate weighs pts over winners, C is the runner-up to revisit.

Full corpus, config E (`--e1 orbitKite --r5d1 reducedDamageHits`), 216×20,
standard scoring — `20260731T151026Z-e1mx-FULL-E-e1-p1.json`:

| board | winners | r-v-m | r-v-r | melee | siege | mean pts |
|---|---|---|---|---|---|---|
| night-final | 194/216 | 97/102 · 9.90 | 6/6 · 2.33 | 67/83 · 6.43 | 24/25 · 9.62 | 8.32 |
| E: E1+P1 | **182/216** | 84/102 · 16.65 | 6/6 · 2.77 | 67/83 · 6.43 (bit-identical) | **25/25** · 9.09 | 11.46 |

Winner flips vs night-final: **gained 2** (champion__vs__heavy_cav_archer
base, hand_cannoneer__vs__heavy_scorpion), **lost 14** (champion__vs__
arbalester ×6, champion__vs__heavy_cav_archer_r2–r9 ×8, all agr 1.0 → 0.0).

### Every fight ≥2 pts worse than night-final under E (66 — none silent)

Families move as blocks (repeats share one engine fight); per-family Δ:

| family (fights ≥2 pts worse) | pts NF → E (Δ) | winner |
|---|---|---|
| champion__vs__arbalester (6) | 0.35–3.82 → 50.3–55.8 (+48.5…+52.0) | LOST ×6 |
| champion__vs__hand_cannoneer (1) | 7.68 → 28.93 (+21.3) | kept |
| champion__vs__heavy_cav_archer_r2–r9 (8) | 2.8–29.4 → 18.2–44.8 (+15.4) | LOST ×8 |
| arbalester__vs__elite_fire_lancer (1) | 13.99 → 26.73 (+12.7) | kept |
| halberdier__vs__heavy_cav_archer (5 of 6) | 1.8–5.7 → 12.0–16.0 (+10.2) | kept |
| hand_cannoneer__vs__elite_elephant (2) | 11.7–15.7 → 20.9–24.9 (+9.2) | kept |
| elite_fire_lancer__vs__hand_cannoneer (1) | 4.97 → 12.53 (+7.6) | kept |
| arbalester__vs__heavy_camel (1) | 10.48 → 16.67 (+6.2) | kept |
| hand_cannoneer__vs__elite_steppe (1) | 22.13 → 27.55 (+5.4) | kept |
| halberdier__vs__arbalester (1) | 1.35 → 6.73 (+5.4) | kept |
| champion__vs__heavy_cav_archer base (1) | 5.31 → 10.07 (+4.8) | gained |
| heavy_cav_archer__vs__heavy_camel (6) | 0.4–5.6 → 4.2–9.3 (+3.8) | kept |
| elite_steppe__vs__arbalester (1) | 29.67 → 33.24 (+3.6) | already-lost |
| arbalester__vs__elite_steppe (6) | 8.6–13.4 → 12.1–17.0 (+3.6) | kept |
| heavy_cav_archer__vs__paladin (1) | 4.81 → 8.37 (+3.6) | kept |
| hand_cannoneer__vs__paladin (6) | 19.4–33.4 → 22.9–36.9 (+3.5) | kept ×5, already-lost ×1 |
| heavy_cav_archer__vs__elite_steppe (6) | 1.4–11.4 → 4.9–14.9 (+3.5) | kept |
| heavy_cav_archer__vs__elite_elephant (1) | 2.21 → 5.12 (+2.9) | kept |
| arbalester__vs__paladin (3) | 8.9–14.4 → 11.6–17.1 (+2.7) | kept |
| arbalester__vs__hussar (1) | 12.71 → 15.16 (+2.5) | kept |
| hand_cannoneer__vs__hussar (6) | 17.5–35.8 → 19.9–38.2 (+2.4) | kept ×4, already-lost ×2 |
| halberdier__vs__hand_cannoneer (1) | 1.00 → 3.00 (+2.0) | kept |

≥2 pts **better**: hand_cannoneer__vs__heavy_scorpion (33.1 → 18.7, −14.5,
winner gained) and heavy_cav_archer__vs__hussar (9.15 → 4.64, −4.5).
(hand_cannoneer__vs__heavy_camel is +0.9 vs night-final — under the 2-pt bar
but listed here for the canary record.)

## Verdict

**No kiter-side composition pays for E1.** The best stack (E1+P1) recovers 1
of the 13 winners E1 costs — and that one (hand_cannoneer__vs__heavy_scorpion)
is a P1 effect that has nothing to do with the orbit. The champion knife
edges are untouched by all three mechanisms (arbs wiped every seed, champ
dmg/run pinned at 720 vs ledger ~603 in every config): the deficit is on the
**chaser side** — the tape's melee chaser swings 1.29× slower while pursuing
a kiter (C1), ours chases at full cadence through the orbit. Same unlock as
the E1 round concluded: the melee-chaser cadence-loss mechanism. C2A should
be considered refuted *in composition as well as isolation*; P2 and P1 remain
the strongest candidates to re-gate alongside E1 once the cadence mechanism
lands (P2 for pts/KPIs, P1 for the siege winner), with the F-stack's
land-rate overshoot (93.7%) as the thing to watch.

All flag defaults unchanged; engine/runner/tests untouched (this round wrote
only scoreboard JSONs and this file).
