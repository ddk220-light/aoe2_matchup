// Role: engine — shared numeric/lookup constants for the battle sim.
//
// This module is the single source of these values: simulate.js (the page shell)
// and the lab harness import them from here — no duplicate copies exist.
// Any edit here changes sim behavior: re-run `node tools/simjs/parity_check.mjs`.

// ===== ROUND 5b — RANGED FIRE MODEL (master off-switches) =====
// Four independent rules, derived in docs/calibration/r5_ranged_forensics.md
// and specified in the Round-5b brief. Each is a MECHANISM, not a tuning
// constant: none of them introduces a fitted number (D1 reuses E9's measured
// pre-shot/recovery constants, D2 reuses the existing dat accuracy roll, D3
// and D4 carry no constant at all).
//
// Setting all four to false restores pre-R5b behaviour BIT-IDENTICALLY --
// that identity is asserted by tests/js/engine/r5b_offswitch.test.mjs and was
// verified against the base commit with a 3-seed hash of the ranged subset.
//
// Mutable rather than `const` booleans so a harness can A/B the marginal
// contributions without editing source between runs (calib_runner.mjs
// --r5b <spec>). The engine itself never reads an env var or a clock; the
// object is set once, before any fight is built, and is not touched again.
export const R5B = {
    // D1  stop-to-fire: the launch check runs every tick and the APPROACH is
    //     no longer gated behind the reload.
    stopToFire: true,
    // D2  ballistic lead + arrival resolution: aim ahead of a moving target,
    //     resolve the hit at arrival against where the target actually is.
    ballisticLead: true,
    // D3  in-flight damage accounting: don't launch at a target already
    //     covered by friendly projectiles in flight.
    inflightAccounting: true,
    // D4  approach margin + hysteresis: close to reach minus one body
    //     diameter instead of stopping on the reach lip.
    approachMargin: true,
};

/** Apply a partial override to {@link R5B}. Harness-only entry point. */
export function setR5B(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in R5B)) throw new Error(`setR5B: unknown flag ${k}`);
        R5B[k] = Boolean(overrides[k]);
    }
    return R5B;
}

// ===== ROUND 5d-1 — PROJECTILE / AIM CORRECTIONS (master off-switches) =====
// Two corrections to the R5b fire model, both measured in
// docs/calibration/r5c_targeting_forensics.md (Q0 and Q2). Kept in their OWN
// flag object rather than bolted onto R5B so the two are independently
// A/B-able and so R5B stays exactly the four rules its own tests count.
//
// Setting both to false restores 71cd4a9 (R5b as merged) BIT-IDENTICALLY --
// asserted by tests/js/engine/r5d1_projectile.test.mjs.
export const R5D1 = {
    // P1  reduced-damage displaced hits: a shot whose accuracy roll FAILED is
    //     displaced by the dat dispersion and, if its LANDING POINT still
    //     overlaps a body, applies exactly half the final post-armor damage,
    //     unrounded. Tape: 6.5 / 4.5 / 5.5 against fulls of 13 / 9 / 11, and
    //     26 of 27 land on the unit the shot was aimed at.
    //
    //     SHIPPED OFF FOR NOW -- correct in kind, net-negative in isolation.
    //     The engine's HC still LANDS fewer shots than the tape (72-83% vs
    //     78-81%), and the old failed-roll-pays-full bug was silently
    //     compensating for that shortfall; enabling P1 before the land rate
    //     closes flips hand_cannoneer__vs__heavy_camel (all six recordings).
    //     Flip to true and re-gate once the R5d-2 targeting/approach work
    //     raises the land rate. The mechanic itself is tape-exact and tested.
    reducedDamageHits: false,
    // P2  trailing-window lead: the intercept is computed from the target's
    //     displacement over the last LEAD_WINDOW_SECONDS, not from its
    //     instantaneous velocity on the launch tick (which R5c measured to be
    //     zero on 91-100% of shots, so the lead never fired at all).
    //
    //     SHIPPED OFF FOR NOW -- same compensating-error shape as P1. The
    //     lead is tape-true (full intercept, ratio ~1.0), but the engine does
    //     not yet model the tape's melee-chaser cadence loss vs kiters
    //     (chasers swing 1.29x slower on tape; ours chase at full cadence).
    //     With T1+T2 on, arming the kiters' lead flips the
    //     champion__vs__heavy_cav_archer family 8/9 -> 1/9 against tape and
    //     costs 8 corpus winners (145 -> 137) AND 0.65 HP-pts. Flip on and
    //     re-gate when the chaser-cadence mechanic lands (ranged-vs-melee
    //     round). Mechanism stays wired + tested under explicit override.
    trailingWindowLead: false,
};

/** Apply a partial override to {@link R5D1}. Harness-only entry point. */
export function setR5D1(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in R5D1)) throw new Error(`setR5D1: unknown flag ${k}`);
        R5D1[k] = Boolean(overrides[k]);
    }
    return R5D1;
}

// ===== ROUND 5d — RANGED TARGETING / APPROACH (master off-switches) =====
// Three rules measured in docs/calibration/r5c_targeting_forensics.md (Q1) and
// docs/calibration/r5c_depth_forensics.md. Like R5B these are MECHANISMS, not
// tuning constants: not one of them introduces a fitted number. T1 and T2 only
// change WHICH enemy an already-committed shot is given to; T3 deletes a piece
// of state (a latch) and carries no new quantity at all -- it reuses R5B's own
// `reach - one body diameter` margin as a continuous condition.
//
// Setting all three to false restores post-R5b / pre-R5d behaviour
// BIT-IDENTICALLY; that identity is asserted by
// tests/js/engine/r5d_targeting.test.mjs and was hash-verified against
// 71cd4a9 over the six ranged fights x 3 seeds.
//
// Deliberately a SEPARATE object from R5B rather than three more keys in it:
// `--r5b off` must keep meaning "the pre-R5b engine" and nothing else, and a
// sweep over R5B's four rules must not silently drag these along.
export const R5D = {
    // T1  per-shot re-selection: at every shot, pick the nearest enemy in
    //     reach whose death is not already covered by committed friendly
    //     damage -- not the unit's standing target, and not sticky.
    perShotSelect: true,
    // T2  same-tick claim ledger: a shot committed earlier in THIS tick counts
    //     as covering its victim for every later shooter in the same tick,
    //     regardless of arrival order (they were fired from the same frozen
    //     positions and cannot see each other's flight times).
    sameTickClaims: true,
    // T3  continuous re-approach: no `rangedClosed` latch -- a ranged unit
    //     approaches whenever its target is outside the R5B margin and holds
    //     inside it, with no memory of having once been closed.
    //
    //     SHIPPED OFF -- REFUTED by its own target fight: the R5B margin
    //     binds, not the latch's memory. T3-alone moves the HCA_vs_HC
    //     standoff p90 not at all (0.87 -> 0.87 vs the tape's 4.78), is worth
    //     0.07 HP-pts and zero winners on the full corpus, and costs a winner
    //     in combination with T1+T2. The tape's formation elongation has a
    //     different, still-unidentified mechanism. Code kept for the
    //     off-switch identity and future A/Bs.
    reapproach: false,
};

/** Apply a partial override to {@link R5D}. Harness-only entry point. */
export function setR5D(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in R5D)) throw new Error(`setR5D: unknown flag ${k}`);
        R5D[k] = Boolean(overrides[k]);
    }
    return R5D;
}

// ===== ROUND 5f — RANGED SELECTION + SILENCE ADVANCE (master off-switches) =====
// Three rules from docs/calibration/r5e_pick_forensics.md. Like R5B/R5D these
// are MECHANISMS: A2 and A3 carry no constant at all, and A1's single number
// (SILENCE_ADVANCE_CYCLES, below) is a MEASURED TAPE BREAKPOINT read off the
// M4b bucket table, not a value tuned against the scoreboard.
//
// Setting all three to false restores 716a522 (the R5d/R5d-1 engine)
// BIT-IDENTICALLY -- asserted by tests/js/engine/r5f_ranged.test.mjs and
// hash-verified against the base commit over the ranged and melee subsets.
//
// A SEPARATE object from R5B / R5D / R5D1, for the same reason those three are
// separate from each other: `--r5d off` has to keep meaning "the pre-R5d
// engine" exactly, and a sweep over R5d's rules must not silently drag these
// along.
export const R5F = {
    // A1  advance-on-silence: a ranged unit that has not LANDED a hit for more
    //     than SILENCE_ADVANCE_CYCLES of its own reload cycles, and still has a
    //     live target, ignores the R5b margin hold and closes. No new steering
    //     and no new movement machinery -- it flips one boolean in
    //     rangedShouldApproach(), so the unit walks the way it already walks.
    //
    //     R5e M4/M4b: the tape's archers close on 2.0% of the unit-steps in
    //     which they are trading on cooldown at a live victim, on 52.2% of the
    //     steps in which they have been silent for >2 cycles with a dead
    //     victim (median radial 0.200 t/s) and on 62.2% of the steps in which
    //     they are silent with a LIVE one (median radial 0.845 t/s = 55% of
    //     walk speed). The engine has the same amount of idle time (907.6
    //     unit-steps against the tape's 763) and closes on 20.9% of it at a
    //     median radial of exactly 0.000. The ride-in is a SILENCE behaviour,
    //     not a targeting one.
    //
    //     Scoped to units that have already fired at least once: the tape's
    //     separate "never fired" bin is the opening walk, and the engine
    //     already reproduces it (35.8% tape vs 33.3% engine).
    silenceAdvance: true,
    // A2  persist -> nearest-uncovered selection: a ranged unit KEEPS the
    //     victim of its previous shot while that victim is alive, in reach and
    //     not lethally covered; when any of those fails it re-picks the nearest
    //     reachable uncovered enemy (T1's rule, unchanged, including its plain-
    //     nearest all-covered fallback). Replaces T1's every-shot re-pick.
    //
    //     R5e M5: `persist->nearest` is the per-pick accuracy leader over the
    //     twelve tape sides (55.9%, above plain nearest's 53.4% and shipped
    //     T1's 53.0%) and is distributionally closer than either (delta near%
    //     +24.8 against nearest's +46.6 and T1's +34.3). R5e M2: in the open
    //     regime -- previous victim alive, in reach, uncovered -- the tape
    //     re-picks the same victim 52.0% of the time and the engine 76.4%,
    //     while the engine picks the strict nearest on 96.5% of those shots
    //     against the tape's 49.0%. T1's non-stickiness is not what was
    //     missing; T1 is not even the best member of the nearest family.
    persistVictim: true,
    // A3  plannedDamage correctness: a projectile whose accuracy roll FAILED
    //     advertises to the coverage machinery what it will actually deliver --
    //     half the post-armor damage when R5D1.reducedDamageHits is ON, the
    //     full value when it is OFF (a failed roll is then displaced by the dat
    //     dispersion and resolved on arrival, so it still pays full when it
    //     connects). One expression at fireProjectile time.
    //
    //     R5e M6 identified the failed-roll population exactly (25.7-26.4% on
    //     the three hand-cannoneer sides, 0.0% on all nine accuracy-100 sides)
    //     and measured that discounting it moves the corpus fallback rate 12.9%
    //     -> 11.8%. NOTE, honestly: that 11.8% is M6's ZERO weighting. With
    //     R5D1.reducedDamageHits shipped OFF this rule is a mathematical no-op
    //     (advertised === damage on every path), so it can only move anything
    //     once P1 is flipped on; the half weighting M6 measured for that case
    //     is 21.6->21.1 / 19.9->15.4 / 8.5->7.7 on the three HC sides.
    failedRollPlannedDamage: true,
};

/** Apply a partial override to {@link R5F}. Harness-only entry point. */
export function setR5F(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in R5F)) throw new Error(`setR5F: unknown flag ${k}`);
        R5F[k] = Boolean(overrides[k]);
    }
    return R5F;
}

// A1's threshold, in units of the shooter's OWN reload time. This is a
// MEASURED TAPE BREAKPOINT, in the same sense as the E9 cadence constants: it
// is the bucket edge at which the tape's own closing behaviour changes state,
// read off r5e_pick_forensics.md §4b and nothing else.
//
//   2:HCA, tape, close% by launch gap      <=1 cycle   1-2 cycles   >2 cycles
//     victim alive                            2.0         26.7         62.2
//     victim dead                            11.1         14.3         52.2
//
// The step is between the 1-2 and >2 bins and it is a 26x change against the
// modal state of the fight (n = 1,863 unit-steps on cooldown at a live
// victim). It was NOT swept: the forensics binned in whole cycles, so 2 is the
// only edge the measurement can support, and moving it would be fitting to the
// scoreboard rather than to the tape.
export const SILENCE_ADVANCE_CYCLES = 2;

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

// ===== BALLISTIC LEAD + ARRIVAL RESOLUTION (D2, Round 5b) =====
// All three numbers below are READ OUT OF THE .dat, not fitted. Source:
// D:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\dat\
// empires2_x2_p1.dat (11,076,546 bytes, 2026-06-02), parsed with
// genieutils-py the same way aoe2x/extract/extract_units.py does.
//
// PROJECTILE RADIUS. The projectile units these four fire -- 507 (arbalester),
// 380 (hand cannoneer), 478 (heavy cavalry archer), 366 (skirmisher) -- all
// carry collision_size_x = collision_size_y = 0.1 tiles. A shot therefore
// connects when its arrival point comes within (target collision radius + 0.1)
// tiles of the target's ACTUAL position. Sanity check against the tape: landed
// shots arrive a median 0.282 tiles from their victim (p99 0.421) for bodies of
// 0.2-0.25 tiles, i.e. right at 0.2 + 0.1 = 0.3, which is what the forensics'
// ON_TARGET_TILES = 0.45 screen was calibrated above.
export const PROJECTILE_RADIUS_TILES = 0.1;

// ACCURACY DISPERSION -- `Type50.accuracy_dispersion`, in tiles. This is the
// field the extraction pipeline DROPS (extract_units.py keeps only
// accuracy_percent), so it cannot come through the combat dict yet and is
// pinned here by slug until it does. Dat values:
//
//   arbalester (492)        accuracy 90  dispersion 0.33
//   heavy_cav_archer (474)  accuracy 80  dispersion 0.33
//   imp_elite_skirm (6)     accuracy 90  dispersion 0.33
//   hand_cannoneer (5)      accuracy 75  dispersion 0.50
//
// (Corpus-wide the field is far from arbitrary: 90 of the 243 units with a
// real projectile sit at exactly 0.33 -- the whole archer/skirm/cav-archer
// bulk -- 13 at 0.50, 14 at 0.75, 100 at 0.0.)
//
// What it does: an accuracy-roll FAILURE no longer teleports the shot to a
// random point up to MISS_SPREAD_RADIUS (2.0 tiles) away, it displaces the AIM
// POINT by up to the dispersion radius. The shot then flies and is resolved on
// arrival like any other, so a "missed" shot that still lands on the target's
// body connects. That composition is what reproduces the tape without a fitted
// number: the hand cannoneer fails its roll 25% of the time, and a uniform
// displacement in [0, 0.5] tiles clears a 0.2 + 0.1 = 0.3 tile body only 40% of
// the time, predicting 0.25 x 0.40 = 10% on-target failure against the tape's
// measured 4.3 / 7.7 / 11.6%.
//
// FALLBACK, deliberately conservative: a unit with no entry here keeps the
// legacy MISS_SPREAD behaviour (flat 2.0-tile scatter) rather than getting a
// guessed dispersion. These four are the units whose dat values were actually
// read; inventing a radius for the rest of the roster would be exactly the
// fitted constant this round is not allowed to add. The real fix is to carry
// accuracy_dispersion through extraction -> ref_units -> the combat dict, at
// which point ACCURACY_DISPERSION_BY_SLUG can be deleted in favour of the
// dict field (battle_unit.js already prefers the dict when it is present).
export const ACCURACY_DISPERSION_BY_SLUG = new Map([
    ["arbalester", 0.33],
    ["heavy_cav_archer", 0.33],
    ["imp_elite_skirm", 0.33],
    ["hand_cannoneer", 0.50],
]);

// ===== LEAD WINDOW (P2, Round 5d-1) =====
// The trailing window over which a target's motion is MEASURED before the
// intercept is solved. This is not a behaviour constant to be tuned -- it is
// the length of the ruler, and it is set to the length of the ruler the
// forensics themselves use.
//
// Why a window at all: R5b read `target.velX/velY`, the ground covered in the
// single previous tick. R5c Q2d measured what that produces -- ANY lead on
// 0.0-9.0% of shots on the nine accuracy-100 sides, median lead 0.000 tiles,
// four sides at exactly 0.0% -- because D1 stops a unit to fire and D4 parks
// it at the approach margin, so the instantaneous velocity of a unit being
// shot at is almost always exactly zero on the launch tick even when that
// unit has been walking for the last second and will keep walking through the
// whole ~1.1 s flight. A one-tick sample cannot see motion that is paused on
// the sampled tick; a trailing window can.
//
// Why 0.3 s: the tapes are 10 Hz position streams and the forensics'
// reconstruction (`ranged_fire_forensics.Fight`) interpolates between those
// frames, so 0.3 s is three recorded frames -- the shortest window over which
// the recordings themselves can state a direction, and the same window the Q2a
// model column `lead@0.3s` is evaluated at. Picking it matches the measurement
// to its instrument rather than fitting the engine to an outcome. (Q2a's
// verdict is that NO trailing-window length beats the oracle, because a
// sampled velocity is noisier than the exact one the game used -- 0.11 s,
// 0.3 s and 0.5 s all leave residuals at or above it. There is no best window
// to find, so there is nothing to tune: take the instrument's own.)
export const LEAD_WINDOW_SECONDS = 0.3;

// ===== MELEE CONTACT LOSS (E13 measurement, E14 mechanism) =====
// THE MEASUREMENT, which stands and is now a VALIDATION TARGET rather than a
// tuning target. Over the 31 pure-melee recordings (both sides, ~7,840 tape
// swings), classifying every point where an attacker's next landed hit came
// more than reload + 0.5 s after the previous one:
//
//   bout-end cause              tape          engine (pre-E13)
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
// plus: 34.3% of tape killing blows are followed by a re-acquisition slower
// than reload + 0.5 s, against 11.7% of the engine's; the live-break gap runs
// median 4.50 s / mean 5.79 s.
//
// WHAT E13 DID AND WHY IT WAS REMOVED. E13 injected those numbers directly:
// MELEE_CHURN_PER_SWING (0.06), MELEE_KILL_REACQUIRE_FUMBLE (0.28) and
// MELEE_CHURN_GAP_SECONDS (5.8), drawn against the rng after every melee
// swing. It scored well (melee-62 within-10 33 -> 46) and it is still the
// wrong model. A unit does not fight less because of a probability; it fights
// less because it is MOVING -- shoved out of the line, walking round a body,
// arriving at a foe that is already surrounded. A rate fitted to 21 champions
// against 9 paladins is not the rate for 5 against 40, and there is no honest
// way to write one number per unit per army size. All three constants and the
// maybeMeleeChurn hook are DELETED.
//
// WHAT REPLACED IT: two physical rules in battle_unit.js, neither carrying a
// fitted rate, with the numbers above kept only to check what EMERGES.
// See meleeTargetLock() / meleeBumpRetarget() for the full derivation.

// Rule 1 -- TARGET LOCK. The stuck bar may not blacklist a living MELEE target
// for a MELEE unit. Measured cause (tools/simjs/melee_select_probe.mjs, over
// the same 31 recordings, against the E13 engine): 2654 of 6727 melee target
// re-acquisitions -- 39.5%, more than the 31.1% caused by the target dying --
// were the bar firing on a unit standing a median 0.61 tiles past its own
// reach, i.e. queueing behind the front rank rather than stuck. Pursuits
// (ranged unit, or a ranged target) keep the bar unchanged. false restores the
// pre-E14 blacklist exactly.
export const MELEE_TARGET_LOCK = true;

// The one number rule 1 carries, and it is a MEASURED CEILING rather than a
// tuned rate: how many attackers a single victim can have in reach at once
// before a further unit locked on it is standing behind a full ring rather
// than queueing for a slot. The tape's attackers-per-victim distribution over
// all 31 pure-melee recordings is median 2 / p90 3 / MAX 4, on both streams
// (E13 measured this and the engine already reproduced 2/3/4 exactly) -- so 4
// is the recordings' own ceiling, not a knob that was turned until the
// scoreboard moved. Above the cap the stuck bar keeps its pre-E14 job.
//
// It is a COUNT, not a distance: occupancy is evaluated with each ally's own
// reach test, so no tolerance constant exists anywhere in the rule. Swept for
// honesty at 2 / 3 / 4 / 5 / 6 -- see the experiment report.
export const MELEE_CONTACT_SLOTS = 4;

// Rule 2 -- BUMP RETARGET. A melee unit that cannot reach its current target
// and is in body contact with a different living enemy switches to the one it
// is touching. This is a documented AoE2:DE behaviour, not a modelling choice:
// update 81058 (12 Apr 2023) shipped "Units will now retarget to a unit of the
// same type if they bump into them and cannot reach the current target", and
// players describe the same mechanic in the broader form (bump any enemy that
// is not your target and you switch to it). Every fight in this corpus fields
// one unit type per side, so the corpus cannot separate the two readings.
//
// There is no tolerance constant: "in contact" reuses resolveCollisions' own
// hard floor, radius + radius + 1 px, so the trigger fires on exactly the
// pairs the collision pass pushed apart this tick. false disables the rule.
export const MELEE_BUMP_RETARGET = true;

// ===== E15b: SWING RECOVERY + LANE-GATED RE-ACQUISITION =====
// E15's walk forensics (docs/calibration/e15_walk_forensics.md) corrected the
// premise E14 handed forward. With the engine's OWN reach formula
// (attack_range*TILE + MELEE_RANGE_BUFFER + both radii) instead of the
// too-small one every earlier probe used, the engine is NOT under-walking:
// moving-share is tape 39.21% vs engine 40.90%. What is wrong is WHERE the
// walking goes. Two measured signals survived that correction, and these two
// rules are their mechanisms. Neither reads the rng; neither scales with army
// size; neither names a unit.

// Rule 1 -- SWING RECOVERY PLANT (attack-animation completion).
//
// THE MEASUREMENT (report §6). Bin every melee sample by its position inside
// the reload cycle, measured from that unit's own last LANDED hit, and ask
// what share of them the unit spent moving:
//
//     phase   0-.1  .1-.2  .2-.3  .3-.4  .4-.5  .5-.6  .6-.7  .7-.8  .8-.9  .9-1
//     tape    0.90% 3.22%  4.85%  7.57% 11.69% 13.92% 14.16% 14.36% 14.26% 14.40%
//     engine  6.41% 5.15%  4.36%  4.25%  3.91%  4.00%  3.79%  3.60%  3.88%  6.19%
//
// The tape ramps monotonically 16x across the cycle and SATURATES by mid-cycle
// (bins .5-1.0 are flat at 13.9-14.4%). The engine has no swing-phase structure
// whatsoever -- flat, with symmetric bumps at both ends. A tape melee unit is
// immobilised by its own swing and released as the animation completes; it is
// NOT "planted whenever a foe is in reach", which is the step-function the
// engine currently implements.
//
// THE CONSTANT. 0.5 s is the attack animation's completion time, read off the
// ramp and nothing else: moving-share is 0.9% in phase 0-0.1 and reaches half
// its saturated value around phase 0.3-0.4. Over this corpus's melee reload
// times (~1.6-2.4 s in the units that dominate the sample) that half-point
// lands at ~0.5-0.9 s and the near-total plant in the first tenth at ~0.2 s;
// 0.5 s is the physical animation length those two brackets imply. It is a
// DURATION, not a fraction of reload -- an animation does not get longer
// because the unit reloads slower. It is NOT fitted to the scoreboard.
//
// SCOPE, exactly. It gates LOCOMOTION only, from the instant a melee swing
// LANDS (killing blows included -- the animation still has to finish):
//   * it does NOT delay the next swing -- reload timing is untouched;
//   * it does NOT apply to ranged units, which already own E9's
//     postFireRecovery, the same law in its stand-and-shoot form;
//   * it does NOT prevent turning, target selection, bump-retarget or being
//     shoved by resolveCollisions.
// It EXTENDS rather than double-counts the plant the engine already had: an
// in-reach melee unit with a cooldown running is already planted by
// battle_unit.js's `else { this.state = "attacking" }` branch, but that plant
// is gated on DISTANCE and evaporates the moment the victim dies or steps out
// of reach -- which is precisely when phase 0-0.1 of the tape's cycle says the
// unit must still be standing there finishing its swing. 0 disables the rule.
//
// SHIPPED AT 0 -- REFUTED AS DESIGNED (E15b marginal-effect runs). A single
// fixed-length plant is a step function; the tape's ramp is monotone across
// the whole reload cycle (0.9% -> 14.4%), so any one release point matches at
// most one bin: 0.5s over-corrected bins 0-0.2 (0.21% vs 0.90%), spiked at
// release (8.1% vs 4.9%) and then DECAYED where the tape keeps rising. Alone
// it cost 7 melee-gate sides; combined with lane re-acquisition it suppressed
// exactly the walking that rule induces (paladin_vs_steppe 5/6 -> 1/6). The
// ramp's late half is accumulated CONTACT LOSS, a mechanism still unbuilt --
// when that mechanism exists, revisit whether a short animation plant is
// needed at all. The code stays wired for the off-switch identity proof.
export const MELEE_SWING_RECOVERY_S = 0;

// Rule 2 -- LANE-GATED RE-ACQUISITION.
//
// THE MEASUREMENT (report §5). Over 2062 mid-fight lock births, which enemy
// does a freed melee unit actually take?
//
//                                        tape     engine
//     rank 1 (the nearest body)         25.27%    48.65%
//     rank > 3                          30.12%     4.50%
//     excess tiles over nearest, median  0.337     0.004
//     excess tiles over nearest, p90     1.836     0.594
//     path walked / straight line, med   1.278     1.036
//
// The engine's findTarget takes the strictly nearest living enemy, so inside a
// scrum the new victim is whichever body the collision floor parked against it
// -- always already in reach, never requiring a walk. The game walks a third of
// a tile past the closest enemy half the time and nearly two tiles past it a
// tenth of the time, and it ARCS there (1.278 path ratio).
//
// Saturation-avoidance, facing and uniform-radius were all measured and all
// REFUTED (§5). The one hypothesis the corpus supports is REACHABILITY: at
// those 2062 lock births the victim actually chosen had a blocked approach lane
// 25.0% of the time against 31.8% for the closer victims walked past. So the
// rule is: iterate living enemies nearest-first and take the first one you can
// actually walk to in a straight line.
//
// NO FREE CONSTANT. The corridor's half-width is the ATTACKER'S OWN COLLISION
// RADIUS -- the width of the body that has to fit through the gap. A candidate
// is unreachable when some other body (ally or enemy) would be inside that
// corridor, i.e. its centre lies within `other.radius + self.radius` of the
// segment from the attacker to the candidate. That is a geometric statement
// about whether this unit fits, not a tuned scalar.
//
// SCOPE, exactly. RE-ACQUISITION ONLY -- a unit's FIRST target of the fight is
// still the plain nearest enemy. This exemption is mandatory and was paid for:
// the unscoped variant (report §7) reads every front-rank unit's lane as
// blocked by the ally beside it at t=0, cross-assigns the line across the
// field, and took champion__vs__paladin margins from 21.9% to 6.7%. It applies
// to MELEE attackers only; ranged acquisition is unchanged. false restores the
// pre-E15b nearest-enemy rule exactly.
export const MELEE_LANE_REACQUIRE = true;

// Cost cap for rule 2, and ONLY a cost cap. The lane test is O(n) per
// candidate, so testing every enemy at every re-acquisition would be O(n^2)
// per event; beyond the nearest dozen bodies the candidate is so far away that
// the walk dominates any lane consideration anyway. If all 12 nearest are
// blocked the rule falls back to the plain nearest enemy, which is exactly the
// pre-E15b behaviour -- so the cap can only ever make the rule LESS active,
// never differently active. The corpus's largest army is 40 units, so this
// binds on roughly the nearest third of a big scrum.
export const MELEE_LANE_CANDIDATE_CAP = 12;

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
