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
//   CHURN = 3.5 (crowd-scaled, CROWDN=6)   per-swing +rand[0,3.5)*min(1,neighbors/6)
//          for melee only; crowd interference that decays the ETG ramp window and
//          vanishes in the thinned-out mop-up.
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
process.env.CHURN = "3.5";
process.env.CROWDN = "6";
process.env.BLOCK = "1";
process.env.GAP = "160";
process.env.BSP = "30";
// Pin the sim time-cap and ramp so a caller passing positional argv (which
// headless_sim reads as RAMP/SEEDS/MAXS fallbacks) can NEVER shorten the fight.
// (Bug found 2026-07-06: sim_one_v2 passed the opponent count as argv[4], which
// became MAX_S=14s and truncated elephant/champi fights into fake stalemates.)
process.env.MAXS = process.env.MAXS || "180";
process.env.SEEDS = process.env.SEEDS || "8";
process.env.RAMP = process.env.RAMP || "window";
// RAMP stays the shipped 5s-window ramp (the file already has it). No SLOT
// (superseded by RTRUE), no SPAWN=game (that is Huskarl-specific).

module.exports = require("./headless_sim");
