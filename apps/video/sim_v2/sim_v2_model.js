// ============================================================================
// ALTERNATE SIMULATION MODEL v2 — "position-aware + randomness"
// ============================================================================
// The webapp flanking sim (apps/website/static/js/simulate.js) with a physical
// fix package calibrated against 20 per-unit in-game decodes of ETG vs Huskarl
// (see ETG_SIM_INVESTIGATION.md §11). It is defined ENTIRELY as a frozen set of
// transforms applied to the REAL simulate.js at load time — no fork, so it stays
// in lockstep with the shipped combat code. The ONLY differences from ship:
//
//   RTRUE  collision radius = outline_size * TILE_SIZE (the GAME's true body,
//          ~6px for infantry) instead of the RENDERING formula 10+outline*20
//          (~14px). The fat render radius was leaking into physics and jamming
//          melee; true radii restore the game's ~90% engagement. (root-cause fix)
//   ADELAY/AJIT = 0.4 / 0.8   melee ARRIVAL wind-up: first swing after any move
//          pays max(cd, 0.4 + rand*0.8)s (the ship melee branch had NO first-swing
//          gate — it struck the instant it was in range).
//   RETARGET/JITTER = 1.5 / 0.8   ADDITIVE cooldown when switching to a new target
//          (walk + re-face after your target dies); reproduces the t6-10s
//          death-reshuffle stall where the coin-flip basins bifurcate.
//   CHURN = 2.25 (crowd-scaled, CROWDN=6)   per-swing +rand[0,2.25)*min(1,neighbors/6)
//          for melee only; crowd interference that decays the ETG ramp window and
//          vanishes in the thinned-out mop-up. RECALIBRATED 3.5 -> 2.25 (2026-07-07):
//          3.5 was tuned before the attack-ramp fix (f8cc9fe) weakened ETG, so it
//          then OVER-penalized the ramping Temple Guard — the shipped sim was wrong
//          on BOTH ETG-vs-Konnik (5% ETG, in-game 80% — the revive swarm out-grinds a
//          ramp that never builds) AND ETG-vs-Huskarl (20%, in-game 55%). 2.25 lands
//          Konnik 75% / Huskarl 60% (both bimodal, matching the game) with the
//          recorded 33-matchup suite unchanged at 27/33 (MAE 30.0 -> 30.1).
//   Spawn: BLOCK compact grid, GAP=160px centers, BSP=30px (1 tile) spacing —
//          the ~16x16 arena cluster, not the ship full-height line (which prevents
//          envelopment entirely).
//
// RANDOMNESS: Math.random is the seeded mulberry32 in headless_sim; the wind-up
// JITTER/CHURN terms consume it, so per-seed variance mirrors the game's own
// engine-timing nondeterminism. Same seed -> identical fight (deterministic).
//
// Validated: ETG-vs-Huskarl 13v21 over 20 seeds -> 70% ETG, S mean +8, sd 12,
// BIMODAL (both basins) vs game 55% / +3.6 / sd 21; 12-fight suite 11/12.
// ============================================================================
process.env.RTRUE = "1";
process.env.ADELAY = "0.4";
process.env.AJIT = "0.8";
process.env.RETARGET = "1.5";
process.env.JITTER = "0.8";
process.env.CHURN = "2.25";
process.env.CROWDN = "6";
//   TRAMPLE_K = 1.5   packing compensation for the trample blast radius: the V2
//          arena packs ~1.5x looser than the game's melee blob, so the 0.5-tile
//          blast is scaled up to reach the neighbours it hits in-game (else a
//          big trampler lands on ~1 unit/swing, not several). Validated on the
//          recorded ETG set: vs-elephant HP-margin MAE 9.5 -> 7.1, no regressions.
process.env.TRAMPLE_K = "1.5";
//   GRAZE_K = 1.5   the SAME packing compensation, for the miss-graze radius. A
//          missed projectile (accuracy roll fail) grazes any unit whose body it
//          lands on — Arambai deal FULL damage on a graze (miss_damage_percent=1),
//          so massed Arambai melt a packed blob. RTRUE shrinks the collision dot
//          the ship graze test used, so scattered shots fell in the gaps (measured:
//          30% connect == base accuracy, i.e. the graze was DEAD). The fix tests
//          the visible bodyRadius instead; GRAZE_K scales it by the same 1.5x the
//          V2 arena packs looser (coverage is areal, so 1.5x radius restores the
//          2.25x density drop). Validated: ETG-vs-Arambai flips +16 -> -28 (in-game
//          'loss'), recorded suite unchanged at 27/33, MAE 30.5 -> 30.0.
process.env.GRAZE_K = "1.5";
process.env.BLOCK = "1";
process.env.GAP = "160";
process.env.BSP = "30";
//   SLOT = 4   ENVELOPMENT. Melee target selection treats an enemy whose contact
//          ring already holds >= SLOT attackers as "full", so overflow attackers
//          pick the next-nearest enemy and slide around to the flanks/rear —
//          encirclement emerges (no fudge multiplier). Without it the sim caps the
//          numerically-superior side's ENGAGED count at frontage-parity with the
//          smaller side, silently discarding its numbers. Root-caused on ETG(12)
//          vs White Feather Guard(21) (2026-07-07): the 5 in-game rolls are a clean
//          0/5 ETG LOSS (WFG keeps ~11/21) because all 21 WFG engage the 12 ETG,
//          yet the no-SLOT sim let only ~8 WFG engage (= the ETG frontage) and
//          called it an 80% ETG WIN. With SLOT=4 the WFG bring ~10 units to bear
//          and the sim flips to a 100% WFG win keeping ~9-10/21 — matching the
//          rolls. Stable plateau at SLOT 4-6 (identical); SLOT=3 is still bimodal.
//          This is the principled fix for the whole "outnumbered high-HP unit
//          over-rated vs a cheaper swarm" class (WFG / Konnik / Huskarl), not a
//          per-matchup override. (Supersedes the old "SLOT superseded by RTRUE"
//          note — RTRUE fixed body radius, but engagement still needed SLOT.)
process.env.SLOT = process.env.SLOT || "4";
// Pin the sim time-cap and ramp so a caller passing positional argv (which
// headless_sim reads as RAMP/SEEDS/MAXS fallbacks) can NEVER shorten the fight.
// (Bug found 2026-07-06: sim_one_v2 passed the opponent count as argv[4], which
// became MAX_S=14s and truncated elephant/champi fights into fake stalemates.)
process.env.MAXS = process.env.MAXS || "180";
process.env.SEEDS = process.env.SEEDS || "8";
process.env.RAMP = process.env.RAMP || "window";
// RAMP stays the shipped 5s-window ramp (the file already has it). SLOT=4 is now
// enabled (see the ENVELOPMENT knob above); no SPAWN=game (that is Huskarl-specific).

module.exports = require("./headless_sim");
