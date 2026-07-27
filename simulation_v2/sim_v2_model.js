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
//   KITE = 1   wall-slide kiting (2026-07-19, in-game validated): the ship
//          moveAwayFromTarget retreats straight away and clamps to the canvas,
//          so kiters wall-pin in seconds and a FASTER ranged unit can never use
//          its speed edge — but the real arena + patrol AI lets it loop forever
//          (ETG-vs-Guecha in-game 3/3 decisive Guecha wins keeping 50-100%,
//          sim said 27/73 coin-flip). With KITE the pinned kiter slides along
//          the boundary toward whichever step ends farthest from its pursuer.
//          Calibrated: Guecha 30%->0% ETG (S -48, Guecha keeps 54% — matches
//          the tape), Genitour 40%->10%, slow-ranged rows stay losses, melee
//          rows (Konnik/Huskarl) BIT-IDENTICAL (patch touches only the ranged
//          retreat path). Slower kiters are still run down; corners still
//          catch kiters whose chaser cuts the diagonal.
process.env.KITE = "1";
//   KITE_CATCH = 1.15 tiles/s   interception gate on the kite decision
//          (2026-07-26, in-game validated: 20 diag recordings across 4 units).
//          In the rig every ranged army "kites" the same way (patrol loop on a
//          bounded arena); the OUTCOME is a race between the kiter's damage
//          killing the chaser and the chaser's cornering grinding the kiter.
//          Fleeing is therefore denied only when ALL THREE hold:
//            1. the kiter is FASTER than its chaser (slower kiters get run
//               down under the old dynamics, which the tapes confirm —
//               Blackwood beats champi while backpedaling),
//            2. the chaser can intercept the loop (absolute speed >= 1.15
//               tiles/s — Guecha 1.15 kites ETG 1.05 to a 3/3 win at ratio
//               1.10; champi 1.21 caught Xianbei 1.54 in 5/5 at ratio 1.27:
//               it is the chaser's ABSOLUTE speed, not the ratio), and
//            3. the kiter CANNOT meaningfully hurt the chaser (damage/hit
//               <= max(3, 5% of chaser HP)) — a kiter that hurts wins the
//               race before cornering bites: Gbeto (11/hit) and Mameluke
//               (10/hit, thrown MELEE class) beat champi 5/5 on tape, while
//               Xianbei (2/hit into 9 pierce armor) went 0/5.
//          Validated: champi-vs-Xianbei 0%->100% keeping 64% (tape 100%/78%);
//          champi-vs-Gbeto/Mameluke stay losses with Mameluke keeping 81%
//          (tape 79-91%); Blackwood/CKN/Champion + ETG-side kite anchors
//          (Guecha/Genitour/Arambai/WarElephant) all unchanged.
process.env.KITE_CATCH = "1.15";
//   TRAMPLE_CONE = 60 (degrees, full width)   angular gate for CONICAL blast
//          (2026-07-26, in-game validated). The dat's blast_attack_level=162 is
//          a cone ("100% damage in a conical shape" — Ibirapema); the ref schema
//          has no blast-shape column so config_combat models it as full trample —
//          fine in the position-less sims, catastrophic here: under ENVELOP the
//          swarm surrounds each trampler and a 360-degree blast hits ~6 units
//          where the real cone hits 1-2 in front (sim wiped 21 champi in 18s; the
//          tape is a 4/5 champi win). Splash now lands only within the front arc
//          for CONE_SLUGS (headless_sim). 60 degrees calibrated: champi-vs-
//          Ibirapema 0% -> 100% with champi keeping 13% (tape 80%/13.6%); 90+
//          degrees still loses the fight. Elephants keep true 360 trample + K=1.5.
process.env.TRAMPLE_CONE = "60";
process.env.BLOCK = "1";
process.env.GAP = "160";
process.env.BSP = "30";
//   ENVELOP = 1   melee envelopment (2026-07-24, in-game validated). A target can only
//          be touched by n = floor(pi / asin(ra/(rt+ra))) attackers at once (6 for equal
//          bodies, ~9 around something twice your radius); a saturated target counts as
//          unreachable, so overflow attackers take the next-nearest OPEN enemy and spill
//          around the front to the flanks and rear. Melee-vs-melee only — you cannot
//          saturate a unit that is running away, and re-picking a chase target would undo
//          KITE. Switches made while still MARCHING skip the RETARGET wind-up (no swing
//          has begun; charging it compounds per tick).
//          WHY: without it the sim's win-rate MOVED WITH ARMY SIZE at a fixed ratio —
//          ETG vs Warrior Priest read 73% ETG at 17v21 but 13-20% at 4v5-5v6, because a
//          crowd could never bring its numbers to bear. In game the WP won at BOTH sizes
//          (4v5 3/3, 17v21 keeping 9 of 21). With ENVELOP: 13% at 17v21, 40% at 4v5 —
//          favoured at every size, strongest when massed, matching the tape.
//          Recorded-tape suite 12/15 -> 14/15: it makes the Warrior Priest AND White
//          Feather Guard pins native losses (both were 75-88% sim WINS) with no
//          regressions — Battle Elephant, Guecha kite, Cataphract, Champion, Karambit,
//          Blackwood, Champi, Paladin, Centurion, Jian, Huskarl all unchanged. Only
//          Elite Konnik still misses, and it missed before this too (revive unit, bimodal).
process.env.ENVELOP = "1";
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
