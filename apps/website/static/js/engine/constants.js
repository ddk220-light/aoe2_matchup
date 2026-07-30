// Role: engine — shared numeric/lookup constants for the battle sim.
//
// This module is the single source of these values: simulate.js (the page shell)
// and the lab harness import them from here — no duplicate copies exist.
// Any edit here changes sim behavior: re-run `node tools/simjs/parity_check.mjs`.

// ===== CONSTANTS =====
export const CANVAS_WIDTH = 900;
export const CANVAS_HEIGHT = 600;
export const TILE_SIZE = 30;

export const MELEE_RANGE_BUFFER = 5;

// Stuck-detection progress bar (moveTowardTarget), expressed as a RATE
// (px/s) rather than a bare per-substep constant. 30 px/s = 1.0 tile/s.
// At dt = 1/60 this is EXACTLY today's historical `- 0.5` literal
// (30 * (1/60) === 0.5 in IEEE-754, pinned by a test) -- a provable no-op
// at the current tick rate. Load-bearing only if dt ever changes: the old
// bare literal meant 1.0 tile/s at 60fps but 0.5 tile/s at 30Hz, silently
// coupling "stuck" semantics to the tick rate. See
// docs/superpowers/specs/2026-07-29-target-thrash-design.md §2.
export const STUCK_PROGRESS_RATE = 30;

// Fraction of the ACHIEVABLE closing rate a chaser must actually deliver
// before the stuck bar (above) brands it blocked, used only while its target
// is actively kiting away. Chasing a fleeing unit closes the gap at the SPEED
// DIFFERENCE, not at the chaser's own speed, so the flat 1.0 tile/s bar is
// unreachable for every melee unit slower than 1.6 t/s chasing a 0.6 t/s
// Siege Onager -- they blacklist it every 0.8 s and never engage at all.
// A chaser that is SLOWER than its fleeing target still gets a bar of 0 and
// still blacklists normally: that is what keeps melee re-targeting off an
// uncatchable kiting archer instead of trailing it forever.
export const PURSUIT_BAR_FRACTION = 0.5;

// Minimum speed advantage (px/s) a chaser needs over its fleeing target
// before the relaxed bar applies at all. Below this the chase is not worth
// committing to -- a Champion (1.06 t/s) trailing an Arbalester (0.96 t/s)
// closes at 0.1 t/s and would need half a minute to cross three tiles, so
// blacklisting and re-targeting really IS the right behaviour there. The
// Siege Onager cases this exists for sit far above it (0.39-1.00 t/s).
export const PURSUIT_MIN_ADVANTAGE = 7.5;

// ===== GROUP-KITE STEERING (E5a) =====
// The recorded tapes' ranged sides are driven by ddkSquareV25, which -- ONLY
// while `gKiteOK` (its own range out-ranges the enemy MEDIAN) -- walks the whole
// army around a clockwise square patrol as ONE ball, with stop-and-volley
// pauses. The engine's kiters instead flee radially and individually, so the
// ball disperses, chasers lose contact, and fights run ~20% long.
// BattleUnit.kiteSteering() adds two boids-style terms on top of the existing
// radial flee + separation, ONLY for units whose side passes that same
// out-ranges gate (see kiteSteering for the exact predicate, including the
// min-range/siege exclusion that keeps every siege fight bit-identical).
//
// These three numbers are the only tuning knobs. They are weights in the same
// (unnormalised) space as calculateAvoidance's separation force, which is 0.5
// per neighbour in the 1.0-1.5x-minDist band and 3..8 per neighbour once
// overlapping -- so a weight near 1-2 is "comparable to separation", not
// "negligible" (the radial flee term is only 1.0 and is already swamped when
// crowded; that is the dispersal bug).

// Tangential (orbit) weight, BEFORE kiteSteering's speed-margin scaling. The
// flee direction is rotated off pure-radial by atan(weight): 1.0 -> 45 deg,
// 1.5 -> 56 deg, 2.0 -> 63 deg. Higher = more circling, less distance gained,
// so chasers keep contact longer.
//
// Pinned by the champion__vs__heavy_cav_archer REPEAT FAMILY (E5a tuned it on
// 4 recordings; the corpus now has 9, and the tape gives the Heavy Cav Archers
// 8 of them) held against the halberdier__vs__heavy_cav_archer family (6
// recordings, halberdiers 6 of 6). Those two straddle this knob and nothing else
// does: the chasers are near-identical in speed (champion 1.06, halberdier
// 1.10 t/s), so what has to separate the outcomes is the halberdier's
// anti-cavalry bonus, not the steering.
//
// RE-TUNED 1.5 -> 0.8 IN E10, because the E10 shared retreat basis (see
// kiteSteering) changed what this weight DOES. Pre-E10 each kiter orbited a
// shared centroid while fleeing its own target, so the two terms fought each
// other and a big weight was needed to get any group rotation at all. With one
// shared retreat bearing the orbit is no longer fighting anything, and 1.5
// over-rotates: the ball trades so much radial recession for angle that the
// chasers close on it. Measured, 10 seeds x both families, at
// KITE_COHESION_WEIGHT 3.0 (share of seeds the TAPE's winner takes):
//
//     weight            0.5   0.75   0.8    1.0    1.25   1.5    2.0
//     champ family HCA  0.83  0.67   0.80   0.33   0.00   0.00   0.00  (tape 0.89)
//     halb family halb  0.50  0.83   1.00   1.00   1.00   1.00   1.00  (tape 1.00)
//
// 0.8 is the only value that satisfies BOTH: the largest weight the champion
// family survives and the smallest at which the halberdier family is still
// perfect. Confirmed at 20 seeds -- champion family HCA 162/180 = 0.90,
// halberdier family halb 120/120 = 1.00. Below 0.8 the halberdiers collapse
// (they have to catch the ball, and they win by damage once they do); above it
// the champions catch it too and the tape's 8-of-9 flips.
export const KITE_TANGENTIAL_WEIGHT = 0.8;

// Cohesion weight -- pull toward the side's own living centroid. Balances
// against separation to set the formation's equilibrium spacing: too low and
// the ball disperses (today's behaviour), too high and units pile into the
// collision floor. Note the engine CANNOT reach the tape's 0.6-tile
// nearest-neighbour spacing: two 14 px-radius archers bottom out at
// radius+radius+1 = 29 px = 0.97 tiles in resolveCollisions.
//
// This term used to be nearly invisible to the 20-seed scorer (subset gated
// mismatches: 0.0 -> 49, 1.0 -> 50, 2.0 -> 49, 3.0 -> 48) and was kept at 2.0
// on a tape-signature argument instead: heavy_cav_archer__vs__elite_elephant
// seed 1, with cohesion the ball holds (nearest-neighbour 1.32 -> 1.26 tiles,
// COMPRESSING as the tape does) and the fight ends at 59.7 s; without it the
// last survivors scatter to opposite corners and it grinds to 555.6 s.
//
// RE-TUNED 2.0 -> 3.0 IN E10. It stopped being invisible the moment the gate
// widened: pre-E10 the whole steering vector was nulled for any side without a
// speed margin, so every FOOT-archer ball -- the ones that mill worst, because
// they cannot outrun anything -- got no cohesion at all. Now that they do, this
// weight is what decides whether the ball holds together while it backs away.
// Measured, 10 seeds x three families, at KITE_TANGENTIAL_WEIGHT 0.8 (share of
// seeds the TAPE's winner takes):
//
//     weight             1.0    1.5    2.0    3.0    4.0
//     champ-vs-HCA       0.10   0.40   0.80   0.80   0.80   (tape 0.89)
//     halb-vs-HCA        1.00   0.80   0.90   1.00   1.00   (tape 1.00)
//     HC-vs-camel        0.30   1.00   1.00   1.00   1.00   (tape 1.00)
//
// 3.0 is the smallest weight where all three are simultaneously at their best;
// 2.0 costs the halberdier canary a tenth and 4.0 buys nothing. It stays well
// clear of "units pile into the collision floor" -- resolveCollisions' hard
// floor is unchanged and E8's packing already sets the equilibrium spacing.
export const KITE_COHESION_WEIGHT = 3.0;

// Distance (tiles) at which the cohesion pull reaches full strength; inside it
// the pull ramps down linearly to zero at the centroid. Without the ramp a unit
// sitting on the centroid still gets a full-magnitude arbitrary-direction kick.
export const KITE_COHESION_RAMP_TILES = 2.0;

// ===== COMBAT-PACK COMPRESSION (E8) =====
// The recorded tapes pack BOTH sides far tighter than this engine can. Measured
// same-side nearest-neighbour distance, mid-fight, over the six
// paladin__vs__elite_steppe recordings: 0.60-0.87 tiles, and COMPRESSING toward
// the end. The engine sits at 1.27-1.46 tiles because resolveCollisions' hard
// floor is `a.radius + b.radius + 1` (two 18 px cavalry => 37 px = 1.233 tiles)
// and calculateAvoidance's soft floor is 2 px wider still. 90.3% of tape
// same-side neighbour pairs sit BELOW the engine's own hard floor.
//
// That gap is not cosmetic -- it decides which units can fight at all. A melee
// unit with attack_range >= 1.0 tile (Elite Steppe Lancer, Fire Lancer) reaches
// 1.0*30 + MELEE_RANGE_BUFFER + both radii = 71 px past its own centre, so a
// SECOND RANK standing behind the contact line still reaches the enemy. The
// arithmetic:
//
//   front-rank lancer sits at the cross-team floor           37 px from a paladin
//   a collinear second-rank lancer needs                     <= 71 px total
//   => same-side spacing must be                             <= 34 px (1.13 tiles)
//   but the engine's same-side floor is                      37 px (1.23 tiles)
//
// The second rank is therefore impossible BY CONSTRUCTION, missing by 3 px --
// no amount of steering tuning can produce it. At the tape's 0.6-tile spacing
// (18 px) it works, and a THIRD rank (73 px) still does not: exactly the two
// engaged ranks the tapes show. A 0-range melee unit (Paladin, reach 41 px)
// would need 4 px of same-side spacing for a second rank, so it gains nothing
// from any realistic compression -- the asymmetry is intrinsic to reach, which
// is exactly the Steppe Lancer's real-game edge. Concurrent distinct attackers
// per 2.5 s window, tape vs sim (paladin__vs__elite_steppe family):
//
//                       tape mean    sim mean
//     Elite Steppe (21)     11.4         9.1
//     Paladin (15)           5.4         6.5
//     ratio steppe:paladin   2.13        1.39
//
// So: when BOTH units of a SAME-TEAM pair are engaged in a fight at contact
// range, their pairwise minimum separation is multiplied by COMBAT_PACK_FACTOR
// in BOTH resolveCollisions (hard) and calculateAvoidance (soft). Cross-team
// pairs and out-of-combat spacing are untouched -- the contact line itself, and
// every approach march, keeps today's geometry.

// Fraction of the normal same-team minimum separation that an engaged pair is
// allowed to compress to. 0.6 * 37 px = 22.2 px = 0.74 tiles, inside the tape's
// 0.57-0.87 tile band and comfortably under the 34 px a second rank of
// 1.0-tile-reach melee needs. Lower than ~0.45 and units start visually
// occupying the same tile; higher than ~0.92 and the second rank never forms.
export const COMBAT_PACK_FACTOR = 0.6;

// How far PAST its own effective reach (in tiles) a unit may be from its living
// target and still count as "in the fight" for packing. Load-bearing: the rank
// this fix exists to create is BY DEFINITION out of reach of everything, so a
// strict in-reach predicate would exclude precisely the units that need to
// compress. 1.5 tiles is one full body-plus-gap behind the contact line.
export const COMBAT_PACK_SLACK_TILES = 1.5;

// Whether ranged units may pack too. The tapes pack universally, but the
// engine's ranged formations are already fitted by the group-kite constants
// above (KITE_COHESION_WEIGHT was tuned against today's floor), so this gate
// exists to measure the global-vs-melee-only trade. `false` = only melee
// attackers compress; ranged units keep today's spacing exactly.
export const COMBAT_PACK_RANGED = true;

// ===== RANGED STAND-AND-SHOOT COST (E9) =====
// Measured over every tape in D:/AI/aoe2_golden/tapes (140 recordings, 21,296
// missile-launch-to-missile-launch gaps, six ranged units). Launches come from
// the ~60 Hz missile stream (first row of each projectile flight, ids split on
// a >3 s gap because the game recycles them); stationarity comes from the 10 Hz
// unit position stream.
//
// THE LAW (one rule, no per-unit tuning, no siege exception):
//
//   A ranged unit that STOOD STILL for a whole fire cycle re-fires at exactly
//   its reload time. A unit that MOVED at any point during the cycle pays a
//   stand-and-shoot cost: its shot lands on the next FIRE_CYCLE_QUANTUM
//   boundary, i.e. cycle = ceil(reload / Q) * Q.
//
// Per-shot split of all 21,296 gaps by "did this unit move during the cycle":
//
//   unit               reload  pred ceil(r/Q)*Q | stood n   median | moved n  median
//   arbalester          1.70        2.000       |   614     1.718  |  6816    2.000
//   heavy_cav_archer    1.80        2.000       |   509     1.820  |  6650    2.008
//   hand_cannoneer      3.45        4.000       |   132     3.468  |  4961    3.998
//   imp_elite_skirm     3.00        3.333       |   341     3.018  |  1705    3.334
//   heavy_scorpion      3.60        4.000       |   409     3.616  |    85    4.020
//   siege_onager        6.00        6.000       |    68     6.026  |    30    6.028
//
// Every "stood" median is reload + one tape tick; every "moved" median is the
// quantised prediction, to within 0.02 s. This is what discriminates the two
// candidate cadence models: the cost is NOT additive (additive predicts
// hand_cannoneer 3.45 + recovery 0.33 = 3.78, but the tape says 4.00, and
// predicts heavy_cav_archer 2.23 against a tape 2.006). Reload runs
// CONCURRENTLY with the post-fire recovery; the whole cadence residual is the
// quantum, so cycle = max(ceil(reload/Q)*Q, windup + recovery).
//
// Note the corollary for siege: heavy_scorpion looked exempt when its gaps were
// pooled (3.616 == reload flat) purely because it stands still for 83% of its
// shots. On the 85 shots where it DID move it quantises to 4.020 like everything
// else, so siege needs no special-casing -- the movement gate handles it.
export const FIRE_CYCLE_QUANTUM = 2 / 3;

// Stop/turn overhead paid BEFORE the shot, on top of attack_delay, whenever the
// unit had to halt to fire. Measured as (time the unit was already stationary
// when the missile launched) - attack_delay, debiased by +0.05 s for the 10 Hz
// sampling grid (an observed window is uniformly truncated over one 0.1 s bin):
//
//   arbalester +0.044 | hand_cannoneer +0.141 | heavy_cav_archer +0.173 |
//   imp_elite_skirm +0.238                                  mean +0.149
//
// One shared value covers all four to within 0.11 s, and this constant is the
// LOW-STAKES one: because the cadence is pinned by the quantum above, moving
// the overhead only shifts WHERE in the cycle the unit is frozen, never how
// often it shoots.
export const RANGED_STOP_OVERHEAD = 0.15;

// Post-fire recovery: after the missile leaves, the unit cannot move for this
// long. Measured as the time from launch to the unit's next position change,
// over kiting cycles only, same +0.05 s debias:
//
//   imp_elite_skirm 0.201 (n=1659) | arbalester 0.326 (n=6761) |
//   hand_cannoneer  0.331 (n=4882) | heavy_cav_archer 0.427 (n=6370)
//
// Unlike the two constants above this one does NOT collapse to a single value:
// the spread is better than 2x and every distribution is tight and unimodal
// (heavy_cav_archer is 0.30/0.35/0.40 = 563/2965/2519 samples, imp_elite_skirm
// is 0.05/0.10/0.15 = 605/653/166). So the default below carries the two units
// that genuinely share it and the other two are named overrides. This is the
// constant that sets a kiter's effective speed, which is the whole point of the
// experiment -- forcing heavy_cav_archer onto a shared 0.33 would hand it back
// 0.10 s of movement per 2.0 s cycle it does not have on tape.
//
// The per-slug heavy_cav_archer value was also checked ON THE SCOREBOARD, not
// just against the tape, because that unit's two families are the campaign's
// judged targets. Sweeping only this number (10 seeds x the two families):
//
//   HCA recovery      0.33     0.43 (tape)   0.55
//   halberdier win   60/60      60/60       60/60    (tape 6/6 -- unaffected)
//   champion HCA win  0/90       9/90        0/90    (tape 8/9)
//
// The response is non-monotonic and the tape-measured 0.43 is also the best of
// the three: freezing the HCA LESS makes it lose harder, because a more mobile
// kiter in this engine disperses out of its own ball and trades its DPS uptime
// for distance it does not need. So this constant is not the champion family's
// problem and cannot be its fix -- see the experiment report.
export const RANGED_POST_FIRE_RECOVERY = 0.33;
export const RANGED_POST_FIRE_RECOVERY_BY_SLUG = new Map([
    ["heavy_cav_archer", 0.43],
    ["imp_elite_skirm", 0.20],
]);

// ===== ADJUSTABLE PRE-BATTLE CONDITIONS =====
// Lithuanian relic bonus: the reference DB bakes in all 4 relics (+1 base
// melee attack each) for these units. The rail picker lets the user dial
// 0-4; setupTeam applies the delta vs the baked-in 4 client-side.
export const RELIC_MAX = 4;
export const RELIC_BONUS_UNITS = new Set(["paladin", "elite_leitis_lithuanians"]);
// Units that snowball +1 attack per kill up to attack_bonus_per_kill (cap 4):
// Jaguar Warrior (Aztecs), Tiger Cavalry (Wei). "Starting kills" pre-loads
// that counter so the battle can start mid-rampage.
export const KILL_BONUS_MAX = 4;
export const KILL_BONUS_UNITS = new Set([
    "elite_jaguar_warrior_aztecs",
    "elite_tiger_cavalry_wei",
]);
