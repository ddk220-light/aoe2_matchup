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
//
// E12 RE-MEASURED THIS ON THE CORRECTED SCENARIO AND LEFT IT ALONE. Everything
// above was fitted with both armies in single-file columns 28 tiles apart; the
// recordings start them as blocks 8 tiles apart inside a walled 13.6-tile box
// (see engine/arena.js's TapeBox). Swept over the full 155-fight corpus, 20
// seeds, in tapebox mode -- winners matched / mean per-seed agreement:
//
//     weight        0.0      0.3      0.5      0.8      1.5
//     corpus     116/155  116/155  116/155  116/155  116/155
//     agreement   0.7465   0.7465   0.7465   0.7465   0.7465
//
// Not "roughly equal" -- BIT-IDENTICAL on every KPI, including all seven canary
// families. The per-tick vector is genuinely live (kiteSteering returns non-null
// on 100% of calls, mean magnitude 0.95 against a flee basis of 1.0), so this is
// not a dead code path; the weight simply does not decide any outcome once the
// fight starts at the tapes' real range. What does decide them is measured in
// KITE_COHESION_WEIGHT's E12 note below.
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
//
// E12 RE-MEASURED THIS ON THE CORRECTED SCENARIO AND LEFT IT ALONE. Same sweep
// as KITE_TANGENTIAL_WEIGHT's note above (full corpus, 20 seeds, tapebox), at
// tangential 0.8 -- winners matched / mean per-seed agreement:
//
//     weight        0.0      0.5      1.0      2.0      3.0
//     corpus     116/155  117/155  110/155  110/155  116/155
//     agreement   0.7497   0.7561   0.7103   0.7077   0.7465
//
// The response is NON-MONOTONIC with a 7-fight swing between adjacent points,
// and the best value is +1 fight (+0.010 agreement) over the incumbent. Not one
// canary family moves anywhere in the sweep. That is a noise landscape, not an
// optimum, so nothing was changed: re-fitting on it would be over-fitting.
//
// WHY THE KNOB CANNOT REACH THESE FIGHTS. The corrected geometry made the real
// cause measurable. Over the corpus, the tape's own median swing interval for a
// MELEE side, divided by the engine's:
//
//     melee vs melee              n=76    median 1.001   mean 1.018
//     melee chasing a RANGED foe  n=102   median 1.289   mean 1.493  p90 2.11
//
// A melee unit standing in a melee line swings at exactly the cadence the engine
// gives it. A melee unit CHASING a kiter swings ~29% slower on tape than in the
// engine -- it keeps losing and re-winning contact, and the engine models none
// of that. Worked example, champion__vs__heavy_cav_archer_r2: champion swing
// interval tape 2.846 s vs sim 2.017 s, so the champions land 84 hits where the
// tape gives them 42, and the Heavy Cav Archers are wiped instead of winning
// with 9 survivors. No steering weight can fix a chaser that swings twice as
// often as the real one; this is the melee analogue of E9's stand-and-shoot law
// and it is the next round's target.
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
// allowed to compress to.
//
// E11 TURNED THIS OFF (0.6 -> 1.0). Everything the block above describes was
// true, but the diagnosis was one level too shallow: the engine's floor was
// 37 px because its radius came from `outline_size` via a formula with a 10 px
// pedestal, and the .dat's real collision_size makes a mounted unit 7.5 px, not
// 18 px. The uncompressed floor is now 7.5 + 7.5 + 1 = 16 px = 0.53 tiles,
// which is already INSIDE the tape's measured 0.57-0.87 tile band -- so the
// compression this constant applied was pure double-counting, and at 0.6 it
// squeezed engaged pairs to 0.32 tiles, well below anything the tapes show.
//
// Measured over the full 155-fight corpus at the true radii (winners matched /
// mean per-seed agreement / mean |HP-remaining delta| in points):
//
//     factor          0.6            0.8            1.0
//     whole corpus   124/155 .825   134/155 .852   135/155 .864
//     basic melee     14/15  .930    14/15  .933    14/15  .930
//     basic mean|d|    5.65           4.81           4.16
//     all melee        7.88           7.43           6.37
//     canaries       2 flipped      all held       all held
//
// 1.0 wins on every axis. The E8 machinery is left in place and wired up (the
// predicate, both floors and their tests still work) so a future experiment can
// re-open it cheaply -- but at 1.0 it is a documented no-op.
export const COMBAT_PACK_FACTOR = 1.0;

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

// ===== MELEE CONTACT CHURN (E13) =====
// A melee unit in this engine, once it reaches a living target, NEVER stops
// hitting it. On tape it does, constantly. Measured over the 31 pure-melee
// recordings (both sides, 7,840 tape swings vs 8,051 engine swings, seed 1),
// by classifying every point where an attacker's next landed hit came more
// than reload+0.5 s after the previous one:
//
//   bout-end cause              tape          engine
//   KILL_SELF   (its own kill)   182  22.2%      69  24.1%
//   KILL_OTHER  (victim died)    339  41.3%     188  65.7%
//   LOST_SAME   (victim ALIVE,
//                resumes on it)  130  15.8%       8   2.8%
//   SWITCH_LIVE (victim ALIVE,
//                resumes else)   170  20.7%      21   7.3%
//   ------------------------------------------------------
//   breaks against a LIVING foe  300            29
//   per swing                    0.0383         0.0036
//
// A ten-fold gap, and it is the ONLY structural term the engine is missing:
// attackers-per-victim is distribution-identical (median 2, p90 3, max 4 on
// both), per-swing cadence against an engaged foe is identical (gap median
// 2.016 s tape vs 2.017 s engine), and neither stream shows any final-blow
// overkill at all (both clamp damage to HP actually removed). What the tape
// has and the engine does not is CHURN: shoving, being shoved, re-pathing
// around a body, and picking a different foe when one wanders off.
//
// Per-slug tape rates (live breaks / swings), which is where the ordering
// argument for the crowd term below comes from:
//
//   champion 0.056 | halberdier 0.055 | hussar 0.050 | paladin 0.038
//   heavy_camel 0.033 | elite_elephant 0.030 | elite_steppe 0.028
//
// Foot units and light cavalry -- the ones fielded 21-strong, packed
// shoulder to shoulder -- churn twice as much as the Elite Steppe Lancer,
// which has a full tile of reach and therefore never has to be in the shoving
// line at all. That is a crowding law, not a unit-identity law, so it is
// modelled as one (see MELEE_CHURN_CROWD_GAIN) rather than as a per-slug table.

// Base probability that a melee unit loses contact after a swing that did NOT
// kill its target. Kill-driven re-acquisition is already modelled (the engine
// nulls a dead target and re-runs findTarget), so this covers only the
// LOST_SAME + SWITCH_LIVE population above. 0 disables the whole mechanism.
// Swept over the 62-side melee gate (6 seeds, sides within 10 HP-points /
// mean |error|): 0.0 -> 33/10.61, 0.045 -> 41/8.69, 0.06 -> 47/6.95,
// 0.075 -> 45/8.04, 0.10 -> 46/7.93. The applied rate sits above the tape's
// measured 0.038 because the measurement is an UNDERCOUNT on both streams: a
// unit that breaks off a foe its allies then finish is scored KILL_OTHER, not
// LOST_SAME. At 0.06 applied, the engine's own measured live-break rate comes
// out at 0.028 against the tape's 0.038 -- i.e. still slightly under, which is
// the honest way to read this number.
export const MELEE_CHURN_PER_SWING = 0.06;

// Extra break probability per same-team unit contesting the same victim,
// beyond the first. `p = base * (1 + gain * (contesting - 1))`, capped at
// MELEE_CHURN_MAX. This is what turns one global rate into the measured
// per-slug spread without naming a single unit: a 21-champion side stacks
// several attackers on each of nine paladins and churns hard, while nine
// paladins swinging into a wall of champions each have the target to
// themselves and churn much less.
//
// MEASURED HARMFUL AND LEFT OFF (E13). Over the melee gate, 6 seeds, sides
// within 10 HP-points / mean |error|, against the flat 0.06 / 5.8 s point's
// 47 / 6.54:
//
//   gain 0.15 (base 0.055)   41 / 8.91
//   gain 0.25 (base 0.04 )   40 / 8.90
//
// Both are worse than flat on every block of the gate. The per-slug ordering
// the term was built to explain is real, but concentrating the churn on the
// crowded side is not how the tape produces it. The machinery is left wired
// up and tested so a future round can re-open it cheaply.
export const MELEE_CHURN_CROWD_GAIN = 0.0;
export const MELEE_CHURN_MAX = 0.25;

// Chance that a melee unit FUMBLES its re-acquisition after landing a killing
// blow -- the separately-measured half of the same story. The engine drops a
// dead target and picks the next one on the very next tick, always; a real
// unit often has to turn, walk and re-path first. Fraction of killing blows
// followed by a gap longer than reload + 0.5 s, over the same 31 pure-melee
// recordings:
//
//                          n     slow    fraction   median   p90
//   tape                  531     182      0.343     2.02   6.11
//   engine (pre-E13)      592      69      0.117     2.02   3.02
//   engine (churn only)   556      45      0.081     2.02   3.02
//
// The MEDIAN is identical on all three (a killer usually does have another
// foe already in reach), so this is a tail, not a flat delay -- which is why
// it is modelled as a probability rather than as an added cost on every kill.
// The churn term alone actually LOWERS the engine's rate (a unit that churned
// off is no longer the one landing the kill), so the two terms are genuinely
// independent and both are needed.
//
// 0.28 was picked by MEASUREMENT, not by scoreboard: it is the applied rate at
// which the engine's own slow-re-acquisition fraction lands on the tape's.
// Both candidates score within noise of each other on the melee gate (20
// seeds, sides within 10 HP-points / mean |error| / corpus winners):
//
//   applied  achieved   gate            corpus
//   0.28      0.342     46 / 5.77       126/155, agreement 0.800
//   0.40      0.412     47 / 5.55       126/155, agreement 0.807
//
// so the tie is broken by the one that reproduces the tape (0.342 vs a tape
// 0.343) rather than by the one a fifth of a point ahead on a noisy metric.
export const MELEE_KILL_REACQUIRE_FUMBLE = 0.28;

// Hit-to-hit gap a broken-off unit pays, in seconds -- it replaces the reload
// outright rather than adding to it, so this number IS the resulting gap.
// Shared by both terms above, because the tape gives them the same length:
// live-break gaps median 4.50 s / mean 5.79 s / p10 2.69 / p90 10.73 (n=300),
// post-kill slow gaps p90 6.11 s. Swept at 3.0 / 4.5 / 5.8 / 7.0 (see the
// experiment report); 3.0 and 7.0 both cost ~5 sides of the melee gate.
export const MELEE_CHURN_GAP_SECONDS = 5.8;

// ===== MELEE QUEUEING (E14) =====
// The stuck bar above (STUCK_PROGRESS_RATE) exists to stop a chaser trailing
// something it can never catch. In a melee SCRUM it does something else
// entirely, and that second job is a bug: a second-rank unit standing right
// behind the ally who currently has the contact slot makes no forward progress
// either, so after 0.8 s the bar blacklists the victim its own front rank is
// killing and sends it off to a DIFFERENT enemy. It is an anti-pile-on rule.
//
// Measured over the 31 pure-melee recordings (tools/simjs/melee_select_probe.mjs
// against the shipped E13 engine): 2654 of 6727 target re-acquisitions -- 39.5%,
// more than the 31.1% caused by the target actually dying -- are the stuck bar
// moving a melee unit OFF a living victim. The champion side of
// champion__vs__paladin alone pays 130 of them across 21 units. It fires at a
// median 0.61 tiles beyond the unit's own reach: exactly one unit-diameter
// back, i.e. the unit is queueing, not stuck.
//
// The consequence is a TIME smear, invisible to any whole-fight concentration
// metric (HHI, effective-victim count and Gini all match the tape to within
// 2%): the same total damage is delivered to the same victims, just more
// thinly spread over time, so victims die later and keep swinging longer.
// Time-to-kill from first touch, in the attacker's own reload periods, over
// the champion__vs__paladin family: tape 4.06-9.52, engine 12.62 (flat, every
// recording). Attackers per victim on that side: tape mean 2.08-3.09, engine
// 1.63.
//
// The fix is to say what the game says: a melee unit does not abandon a living
// melee foe it is already standing at. It waits for a slot. It only walks away
// when the crowd around that foe is already full -- which is what keeps the
// pile-on inside the tape's own measured cap instead of stacking the whole
// army onto one victim.
//
// MELEE_QUEUE_TILES -- how far beyond its own reach a unit may stand and still
// count as "at the fight" rather than "chasing". Fitted to the tape's contact
// crowd depth: over all 31 melee recordings, at the moment a victim is hit its
// nearest enemy sits at a median 0.54 tiles and its FOURTH nearest at 1.15 --
// a crowd 0.61 tiles deep behind the front rank. 0 disables the whole
// mechanism and is bit-identical to E13 (no rng draw is involved, so identity
// is structural, not statistical).
export const MELEE_QUEUE_TILES = 0.2;

// How many allies may already be queued on one victim before a further unit is
// sent elsewhere by the stuck bar as before. The tape's attackers-per-victim
// distribution (E13, same 31 recordings) is median 2 / p90 3 / max 4, and the
// ring above holds a median of 4 enemies at the moment of a hit -- so 4 is the
// tape's own ceiling, and the cap is what stops this mechanism from raising
// instantaneous attackers-per-victim above it.
export const MELEE_QUEUE_CAP = 4;

// Distance discount (tiles) a melee foe gets in findTarget when allies are
// already fighting it and its scrum is not yet at MELEE_QUEUE_CAP. The queue
// rule above stops a unit LEAVING a fight; this one decides which fight it
// JOINS when it has genuinely lost its target (kill, churn, or a blacklist
// that survived the queue test).
//
// Fitted to the retarget transition matrix over the 31 pure-melee recordings
// (tools/simjs/melee_target_forensics.py), specifically the share of all
// consecutive-hit pairs in which an attacker leaves a LIVING victim and its
// next landed blow is on a foe an ally hit inside the trailing reload window:
//
//   SWITCH_LIVE/ALLY     tape 0.1662   E13 0.1233   E14 queue-only 0.1345
//
// i.e. after the queue rule the engine still under-joins by ~20%. A DISCOUNT
// rather than an override is deliberate: it can only decide a close call, so
// a foe two tiles further away stays two tiles further away and the "walk to
// the nearest body" behaviour survives everywhere the scrum is not right
// there. 0 disables it and, together with the null return in scrumCounts(),
// is bit-identical to the queue-only engine.
export const MELEE_PILE_ON_TILES = 0.0;

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
