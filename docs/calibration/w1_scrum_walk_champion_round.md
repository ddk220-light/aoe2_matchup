# W1 scrum-walk — champion-gap round results (2026-08-02)

Context: first round against the consolidated STANDARD_UNITS golden set
(`aoe2_golden_STANDARD_UNITS_2026-08-02.zip`), champion-pair subset (63 fights,
13 pairs) ingested 2026-08-02 (manifest 240→284; 16 content-collisions
auto-reassigned to fresh `_rN` run_ids; melee gate re-pinned 95→123 in
`tests/test_calibration_filters.py`). Baseline board:
`data/calibration/runs/20260802T225801Z-champion-0802-base.json` — 60/63
winners, 19/63 winner-side HP within 90–110% of tape.

## The defect (measured, champion__vs__paladin family)

Damage streams + 10 Hz positions (forensics:
`.scratch/standard_units/melee_fragmentation_forensics.py`, probe runs
determinism-verified):

- Tape melee **fragments** in the endgame: surviving paladins have ZERO
  champions in melee reach (0.75 tiles, tape's own p90 hit distance) in
  9.5–40% of endgame samples, and counter-mob (1.30–1.43 paladins per
  champion late in r3/r4). Sim (flag off): never free (0.9%), champions
  0.90. Openings are exact in both (adjacency distributions identical t<15).
- Sim re-engagement gap (kill → first hit on next victim) is a constant
  2.02 s = exactly one reload; tape med 2.02 but p90 2.6–3.6 s.
- Tape units move 30–43% of living samples (5–9.5% moving WITH an enemy in
  reach); sim 25% (2.4%).
- Consequence: sim majority side keeps continuous multi-attacker contact,
  deletes the outnumbered tail ~3x faster than tape, winner keeps too much
  HP (champion 224–630 vs tape 14–518), and the paladin-upset runs (tape
  r3/r4) can never happen — 1v1 arithmetic (paladin kills champion in
  ~9.5 s, needs ~28 s to die) only pays off in fragmented duels.

## The change (W1.scrumWalk, flag-gated, default OFF)

Restored the stashed W1 work and finished the gate predicate to the designed
latch-OR-accumulator form (`battle_unit.js` `w1ScrumBlocked()`; the tree
carried a `V3A-LATCH-ONLY-PROBE` leftover that dropped the accumulator
clause). Blocked out-of-reach melee attacker drifts tangentially about its
lock (arc step = moveSpeed·dt/r, E1 rotate math, Σ1/d² sense comparison —
zero new constants). JS suite 377→**389/389** (11 W1 tests).

## Gates

- **OFF byte-identity**: `--w1 off` == defaults on melee+ranged samples;
  `--w1 scrumWalk` byte-identical on ranged/siege (predicate is
  melee-vs-melee scoped) — `champion__vs__arbalester`,
  `champion__vs__heavy_cav_archer`, `champion__vs__siege_onager`, 3 seeds.
- **123-fight melee gate** (`...T234840Z-melee-0802-w1-melee-only.json` vs
  `...T234932Z-melee-0802-off-melee-only.json`): **94 → 108 winners**
  (+25 fixed, −11 broke). paladin__vs__elite_steppe now 20–21/24 paladin
  (tape 20/24; off-engine was 0/24 — W1's original target, handoff §4).
- **Champion board (63)**: winners 60/63 (fixed r3/r4, broke base/r2 — tape
  spans champion+14 … paladin+343, sim lands paladin+137 on all four
  `paladin__vs__champion` layouts, i.e. INSIDE the tape's own range);
  **winner+HP in 90–110%: 19 → 23/63**. champion__vs__paladin_r14-16 ratios
  1.22/1.36/2.25 → 0.73/0.82/1.35.
- **Geometry with W1 on** (probe + `--w1`): paladin-free-late 0.9% → 18.2%
  (tape 9.5–40%); moving 25% → 47% (tape 30–43%); re-engage p90 2.02 →
  5.87 s (tape 2.6–3.6 — **overshoots ~2x**, max 23.75 s; the known
  residual — drift arc can hold too long).

## Remaining champion-board misses (40 fights, by family)

- heavy_cav_archer 13 (+1 flip): ratio 0.03–0.24 — the kite-escape stack
  (C3/C4/E1 built OFF + unbuilt E2 band law), NOT a melee defect.
- elite_elephant 6: sim elephant still too healthy (1.16–1.68 over).
- paladin 4: inside tape range but outside ±10% (W1 over/undershoot).
- foot-ranged (hand_cannoneer 2, imp_elite_skirm 2): 0.81–1.14 — C4's job.
- heavy_scorpion 2 (0.69/0.84), siege_onager 1 (0.82): siege texture.
- hussar 2, elite_steppe 2, halberdier 1: 0.89–1.46, near-band.

## Next

1. Re-engage overshoot (5.87 s vs tape ~3 s): measure where the drift holds
   too long (probably arc-holds-r past the point the tape cuts the corner).
2. E2 setpoint-band law + E1/C3/C4 composition for the 14-fight HCA block.
3. Elephant-family HP overshoot forensics.
4. Full-corpus gate before any default flip (handoff discipline); W1 stays
   OFF until then.
