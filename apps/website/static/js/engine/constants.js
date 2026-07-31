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

// ===== PHASE B2 — THE MELEE BUMP VALVE, MADE REACHABLE (master off-switch) ==
// One rule, and it deletes a bug rather than adding a model. Derived from
// docs/calibration/b1_engagement_forensics.md §2b / §8.2 and the correction to
// it recorded in docs/calibration/b2_bump_contact.md. It introduces NO new
// constant -- it asks an existing engine floor instead of the wrong one.
//
// THE DEFECT B1 MEASURED. E14's rule 2 (MELEE_BUMP_RETARGET, below) asks "am I
// in body contact with an enemy that is not my target" with
// `dist <= this.radius + enemy.radius + 1`, which is byte-for-byte the
// `minDist` Simulation.resolveCollisions enforces as the MINIMUM cross-team
// separation. Measured over 40 asymmetric melee fights x 20 seeds: the valve
// was eligible on 0.2% of frozen ticks and fired 900 times against 21 080
// stuck-bar trips, while units froze on victims a median 0.37 tiles past reach
// for up to 35.6 s. The rule was wired, tested, documented -- and unreachable.
//
// WHY -- AND B1 IS ONE PIXEL OFF. B1 read the failure as a timing artifact:
// the resolver pushes a pair to the floor at the END of a tick, so the rule's
// `<=` re-measurement on the NEXT tick lands just outside. It is not a timing
// artifact, and rewiring the rule to consume the resolver's own contact event
// does not fix it (measured: 0.002 eligible, against 0.001 for the old test --
// see the B2 report). The engine separates bodies in TWO passes, and the pair
// never reaches the hard one:
//
//     resolveCollisions   hard floor   radius + radius + 1   (end of tick)
//     calculateAvoidance  soft floor   radius + radius + 2   (during movement)
//
// The soft floor is ONE PIXEL WIDER. Two enemies pressed together therefore
// settle against the SOFT floor, one pixel outside the hard one, and the hard
// pass never touches them at all -- which is exactly B1's measured "nearest
// hittable foe sits a median 1.0-1.7 px past the bump floor". The cross-team
// standoff is held by the soft pass; the bump asked the hard pass; the two
// differ by 1 px, and that pixel is the whole rule.
//
// THE FIX. Ask both passes, which between them are the engine's entire
// definition of a body:
//   * the SOFT floor as a live test, `dist < radius + radius + 2` -- quoted
//     from calculateAvoidance, not chosen. This is the term that fires:
//     eligibility on a frozen tick goes 0.001 -> 0.321.
//   * the HARD pass's own recorded contact EVENT (resolveCollisions ->
//     BattleUnit.bumpContacts), for the rarer case where bodies really do
//     overlap. Consulted as an event rather than re-derived from a distance,
//     because by the time the rule runs the pair HAS been pushed.
// `<= hard floor` implies `< soft floor`, so the soft term subsumes the pre-B2
// trigger and the new rule is a strict superset of the old one: nothing that
// used to bump can stop bumping.
//
// Every other gate on E14 rule 2 is UNCHANGED: melee unit, living melee
// target, target out of reach, candidate alive and melee and not the current
// target, nearest candidate wins. The lock rule (rule 1) is untouched.
//
// No fitted constant is admitted anywhere. `+3 px` would cover 0.788 of frozen
// ticks and `+5 px` 1.000 -- both were measured and both were REJECTED: the
// first is a number chosen for its coverage, and the second is not a contact
// test at all (for 0-range melee, radius+radius+5 IS reach, so it would silently
// rewrite the rule as "retarget to anything you can hit").
//
// Setting the flag to false restores 716a522 BIT-IDENTICALLY -- asserted by
// tests/js/engine/b2_bump_contact.test.mjs and hash-verified over the ranged
// subset x 3 seeds.
export const B2 = {
    // B2a  reachable bump contact: "bumped" is the soft body floor the engine
    //      actually holds cross-team pairs at, plus the hard pass's own contact
    //      event -- not a re-measurement against a floor nothing ever reaches.
    resolverContactBump: true,
    // B2b  "...AND CANNOT REACH THE CURRENT TARGET". The other half of update
    //      81058's sentence, which E14 rendered as `!inRange()` -- "is not
    //      swinging at it right now". Those are different claims: a unit
    //      walking at a foe five tiles away and closing normally is not in
    //      reach, but it can reach, and the tape does not show it abandoning
    //      the walk because a body brushed past.
    //
    //      Measured: with B2a alone the valve is reachable and the freeze is
    //      gone (outnumbered WASTED share of alive 0.075 -> 0.009, worst lock
    //      episode 35.6 s -> 2.2 s, halberdier__vs__paladin swinging share
    //      0.31x -> 1.06x of tape), but it fires on units that were never
    //      stuck and the healthy majority OVERSHOOTS: pooled old-corpus
    //      outnumbered share 0.98x -> 1.11x, superior 1.01x -> 1.18x,
    //      halberdier__vs__hussar 1.54x -> 2.00x, corpus winners 194 -> 190.
    //      With B2b the same collapse fix survives intact while the majority
    //      comes back: 1.05x / 1.03x, hussar exactly 1.54x, winners 194.
    //
    //      So "cannot reach" is read as the engine's own existing
    //      unreachability verdict: the stuck bar (moveTowardTarget) reached
    //      0.8 s of no progress against this target and E14's lock re-armed it
    //      instead of releasing. That is precisely the 21 080 stuck-bar trips
    //      B1 counted. The latch is the TARGET it tripped on
    //      (`meleeStuckOn`), so it clears itself the instant the unit picks a
    //      different foe, and it is dropped the moment the unit is in reach.
    //      No new constant: the 0.8 s bar and the lock are both pre-existing.
    //
    //      Meaningless on its own -- with B2a off the trigger is unreachable
    //      whatever gates it -- so it is a NARROWING of B2a, not a fifth rule.
    stuckGatedBump: true,
};

/** Apply a partial override to {@link B2}. Harness-only entry point. */
export function setB2(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in B2)) throw new Error(`setB2: unknown flag ${k}`);
        B2[k] = Boolean(overrides[k]);
    }
    return B2;
}

// ===== ROUND 5f — RANGED SELECTION + SILENCE ADVANCE (master off-switches) =====
// Three rules from docs/calibration/r5e_pick_forensics.md. Like R5B/R5D these
// are MECHANISMS: A2 and A3 carry no constant at all, and A1's single number
// (SILENCE_ADVANCE_CYCLES, below) is a MEASURED TAPE BREAKPOINT read off the
// M4b bucket table, not a value tuned against the scoreboard.
//
// Setting them all to false restores 716a522 (the R5d/R5d-1 engine)
// BIT-IDENTICALLY -- asserted by tests/js/engine/r5f_ranged.test.mjs and
// hash-verified against the base commit over the ranged and melee subsets.
//
// SHIPPED STATE: A1 off, A2 off, A3 on (and A3 is a proven no-op while
// R5D1.reducedDamageHits is off), i.e. the R5f engine is bit-identical to
// 716a522 on the whole corpus. Each flag's own note below carries the numbers
// that decided it. Nothing here was tuned: the flags are on/off and the one
// constant, SILENCE_ADVANCE_CYCLES, is a measured tape bucket edge.
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
    //
    //     SHIPPED OFF -- the mechanism is REAL and MEASURABLY LIVE, and it
    //     still costs. Over the six ranged fights, 20 seeds, A1 alone:
    //       * silence occupancy (its own predicate) 9.5% -> 8.1% of ranged
    //         unit-steps, and the share of those steps spent CLOSING goes
    //         26.3% -> 46.2% (tape 52.2-62.2). It is not inert.
    //       * HCA_vs_HC standoff p90 0.97 -> 1.15 tiles (tape 4.78) and the
    //         hand-cannoneer side 0.67 -> 1.29 (tape 4.85).
    //       * but the ranged board's mean per-side HP error goes 2.33 -> 2.91
    //         pts and HCA_vs_HC 13.92 -> 16.42 (sum of both sides), i.e. the
    //         archers survive with MORE hp, not less. On the full 216-fight
    //         corpus it is a wash: 194/216 winners either way, +0.03 HP-pts.
    //     And M4b says where the extra closing lands: with the LANDED clock
    //     the "<=1 cycle / victim alive" bucket -- the modal state of the
    //     fight, which the tape closes on 2.0% of -- goes 3.5% -> 8.4%. The
    //     rule produces closing, in partly the wrong state. Kept wired and
    //     tested; the tape's elongation needs something this is not.
    silenceAdvance: false,
    // A1b WHICH CLOCK A1 READS. Not a tuning knob -- a choice between two
    //     definitions of the same word, both of which have a claim:
    //       false (default) = LANDED. The R5f brief's wording: the clock
    //           resets when a projectile this unit fired actually put damage
    //           on a body, so a unit whose shots keep grounding stays silent.
    //       true            = LAUNCHED. The statistic r5e_pick_forensics.md
    //           §4b actually bins by ("how long since that unit last fired"),
    //           i.e. the definition under which the tape's 2.0% / 52.2% /
    //           62.2% closing shares were measured in the first place.
    //     Exactly one is used; the flag has no effect with silenceAdvance off.
    //     Measured both ways over the six ranged fights -- see the round
    //     report; the default is the brief's.
    silenceClockOnLaunch: false,
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
    //
    //     SHIPPED OFF -- REFUTED, and by a single, clean cause. A2 moves the
    //     pick distribution toward the tape exactly as M1/M2/M5 predict (mean
    //     dist.pct over the twelve sides 0.140 -> 0.179 against a tape 0.234;
    //     open-regime near% on HCA_vs_HC 2:HCA 94.7 -> 74.0 against a tape
    //     50.0; ex p90 0.12 -> 0.45 against 1.54) and it costs SEVEN corpus
    //     winners doing it: 194/216 -> 187/216, +1.30 HP-pts. Every one of
    //     those seven is the same fight: the nine-recording
    //     champion__vs__heavy_cav_archer family goes 8/9 -> 1/9, i.e. A2
    //     exactly undoes what R5d shipped T1 to fix. Melee is untouched
    //     (bit-identical) and pure ranged-vs-ranged holds 6/6 winners; the
    //     whole loss is ranged-vs-melee (77/82 -> 70/82, +3.18 HP-pts).
    //
    //     Read honestly, that is the scope of the evidence catching up with
    //     the rule: R5e measured persistence on SIX ranged-vs-ranged
    //     recordings, and this engine applies it to every ranged unit in the
    //     corpus, including 82 fights against melee where nothing was
    //     measured. Scoping the rule by what its target is would be inventing
    //     a mechanism the tape has not shown, so it ships off whole.
    persistVictim: false,
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
    //
    //     SHIPPED ON, and PROVABLY FREE: with R5D1.reducedDamageHits off, a
    //     full 216-fight x 20-seed corpus run with this rule alone is
    //     BYTE-IDENTICAL to base. It ships on so that the correction is
    //     already in place the day P1 is flipped on, not because it bought
    //     anything today.
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

// ===== PHASE C2-a — THE KITER'S CONTACT BREAK (master off-switches) =====
// Two rules, from docs/calibration/c1_chaser_cadence.md M2. Like R5B/R5D/B2/R5F
// these are MECHANISMS, and this pair is unusually strict about it: NEITHER
// rule introduces a number at all. The break's bearing is a basis, not a
// weight; the break's end is a distance the engine already computes for other
// reasons (an attacker's own reach, plus the fleeing body's own diameter).
//
// WHAT C1 MEASURED. E12's headline was that a melee unit chasing a RANGED one
// swings 1.29x slower on tape than in this engine; C1 confirmed it (T/E median
// 1.22 over 29 melee-swing families) and decomposed it. The chaser is NOT
// reload-limited on tape, it is CONTACT-limited: it is inside its own reach for
// 0.66 s of each cycle against this engine's 1.81 s, and 97.2% of its cycles
// lose contact against this engine's 54.1%.
//
// C1 M2 then located the cause on the KITER, not the chaser, and it is not a
// duty-cycle or phase-race defect (2b refutes both: the tape's chaser lands
// 9.9% of its blows on a STOPPED victim, this engine's 55.2%). After taking a
// melee hit the tape's kiter:
//   (a) starts moving in a median 0.08 s -- ONE 10 Hz sample, i.e. as fast as
//       the recorder can see. This engine's takes 0.42 s.
//   (b) runs along the vector away from THE UNIT THAT HIT IT, cos 0.88 pooled
//       over the 29 families (0.69-0.96, 28 of 29 at or above 0.79). This
//       engine's runs at cos 0.61 -- and cos to the enemy CENTROID is no better
//       (0.78 tape vs 0.67 engine), so it is not "flees the centroid instead":
//       the flee vector is less aligned with BOTH bases.
//   (c) converts that into 1.03 tiles of RADIAL separation inside one chaser
//       reload, against this engine's 0.05, and is out of reach after 0.08 s
//       against this engine's 0.42.
//
// WHY THE ENGINE'S BEARING IS WRONG, precisely. E10a gave every group-kiting
// side a SHARED retreat basis -- back away from the enemy CENTROID, one bearing
// per side per tick -- to stop twelve archers milling in twelve directions.
// That fixed dispersal and is not being undone here. But a centroid is an
// average over an entire enemy army, and the unit that just put a blade in you
// is one member of it: at the moment of contact the shared basis is exactly the
// wrong resolution. C-a does not weaken E10a's basis; it says the basis is
// SUPERSEDED, for as long as a specific melee unit is in touching distance, by
// the one threat the tape shows the kiter actually answers.
//
// NO WEIGHT, DELIBERATELY. A blend `w * awayFromHitter + (1-w) * awayFromCentroid`
// tuned until cos lands on 0.88 would be a fitted constant wearing a
// measurement's clothes. The break REPLACES the radial basis outright (w = 1)
// and the measured cos is then an EMERGENT number, not a target: the orbit,
// cohesion, avoidance and velocity-smoothing terms that already act on a kiting
// unit are what pull the realised heading off the pure radial. Whether that
// lands near the tape's 0.88 is a prediction this rule can FAIL, and the C2
// report states what it actually came out at.
//
// ===== SHIPPED STATE: BOTH OFF. THE PREDICTION FAILED, AND MEASURABLY SO. =====
// Both rules are wired, tested and A/B-able (`--c2a contactBreak,breakPriority`),
// and both ship OFF, so this file is byte-identical to 0e2dbc5 on the whole
// corpus. The numbers, from docs/calibration/c2a_contact_break.md:
//
//   full corpus, 216 fights x 20 seeds     base 194/216   C-a 187/216
//     ranged-v-ranged  6/6 -> 6/6   melee 67/83 -> 67/83   siege 24/25 -> 24/25
//     (those three are BYTE-identical, as designed)
//     ranged-v-melee  97/102 -> 90/102,  +4.50 HP-pts
//   every one of the seven lost winners is champion__vs__heavy_cav_archer,
//   8/9 -> 1/9 -- the one family that gates P2, and it flips the same way P2
//   and R5f-A2 flip it.
//
// WHY, measured rather than guessed (tools/simjs/c2a_break_probe.mjs). The
// mechanism is LIVE -- a break occupies 18.2% of kiter unit-ticks and lasts a
// median 2.73 s -- and it moves several quantities toward the tape (post-hit
// seconds-to-leave-reach 0.42 -> 0.29 against a tape 0.08; chaser hits landed
// on a STOPPED victim 55.2% -> 42.4% against a tape 9.9%). What it does NOT
// move is the thing it was built to move:
//
//   cos(flee, away-from-the-hitter)   tape 0.88   base 0.61   C-a 0.63
//   victim radial displacement/reload tape 1.03   base 0.05   C-a 0.09 tiles
//
// The probe says why in one line: on a break tick the radial basis is a
// MINORITY of the vector moveAwayFromTarget sums.
//
//   |radial basis|      1.000  (unit, by construction)
//   |orbit + cohesion|  1.213
//   |avoidance|         2.259
//   cos(pre-smoothing heading, break bearing)  0.415
//   cos(actual tick step,      break bearing)  0.235
//
// The realised heading is decided by KITE_COHESION_WEIGHT (3.0) and by
// calculateAvoidance's unbounded body-repulsion sum, not by which unit vector
// the basis is. No CHOICE of basis can reach cos 0.88 here; only a re-weighting
// could, and that would be a fitted constant that also undoes E10a.
//
// And the cost has a name. Swapping E10a's shared basis for a per-hitter one
// partially reinstates the exact defect E10a was built to remove -- the ball
// MILLS: cos to the enemy centroid goes 0.67 -> 0.39 (tape 0.78) while cos to
// the hitter buys +0.02. On tape the two bases are nearly collinear (0.88 and
// 0.78); in this engine they are not, and forcing one costs the other. The
// bearing rule ALONE (contactBreak, breakPriority off) already costs the full
// seven winners, so the loss is the basis change, not the shot suppression.
//
// WHAT WOULD MAKE IT TESTABLE AGAIN -- stated as a prediction, not a hope. C1
// M3 measured that the tape's chaser is stationary at 100% of its landed hits
// (`cStep` 0.000 in every one of the 29 families) and is in reach 0.66 s per
// cycle against this engine's 1.81 s. This engine's chaser walks back into
// contact inside the same reload, so a break that ends at "reach + one body
// diameter" is re-entered immediately and the kiter pays the retreat without
// ever collecting the separation. The counterpart rule is the chaser's
// stop-to-swing commitment, not anything on the kiter. Re-gate C-a WITH that,
// and only then against P1/P2.
export const C2A = {
    // C-a1 CONTACT BREAK. A melee hit on a non-siege ranged unit latches the
    //      HITTER. While that hitter is within escape distance (below), the
    //      kiter's retreat basis is "straight away from the hitter" instead of
    //      E10a's shared centroid basis; group cohesion and the orbit term are
    //      untouched and still added on top.
    //
    //      The trigger is a MELEE hit, so ranged-vs-ranged is unreachable BY
    //      CONSTRUCTION (no melee attacker exists in those fights) and
    //      melee-vs-melee is unreachable by the victim-side isRanged() gate.
    //      Siege is excluded by minAttackRange > 0 -- the same clause
    //      kiteSteering uses, and for the same reason: Siege Onager (3.0) and
    //      Heavy Scorpion (2.0) own a competing repositioning path (tooClose)
    //      and do not run a kite circuit at all.
    //
    //      THE END CONDITION IS PHYSICAL, NOT A TIMER. The break ends when the
    //      hitter is further away than `its own reach + the kiter's body
    //      diameter` -- i.e. when the kiter has put a whole body's width of
    //      daylight between itself and the edge of what that unit can hit. Both
    //      terms are quantities the engine already computes (inRange()'s own
    //      arithmetic, and the radius every unit carries); there is no time
    //      constant and no decay. Read against the corpus this lands at
    //      0.62 + 2*0.23 ~ 1.07 tiles for a champion chasing a Heavy Cav
    //      Archer, which is the same order as the 1.03 tiles of radial
    //      separation C1 measured the tape's kiter opening per reload -- a
    //      consistency check on the criterion, not its derivation.
    //
    //      SHIPPED OFF -- see the measured verdict above. ALONE it costs the
    //      same seven winners the pair costs (champion__vs__heavy_cav_archer
    //      8/9 -> 1/9, +2.03 HP-pts corpus), because the basis swap trades
    //      E10a's centroid alignment (0.67 -> 0.39, tape 0.78) for +0.02 of
    //      hitter alignment (0.61 -> 0.63, tape 0.88).
    contactBreak: false,
    // C-a2 THE BREAK OUTRANKS STOP-TO-FIRE. While the break is live the kiter
    //      does not stop to shoot: R5B-D1's `cooldown expired and something in
    //      reach -> fire` test, and the settled/approach arm below it, are both
    //      skipped in favour of the retreat. This is what produces (a) -- the
    //      departure inside one tick -- because the engine's kiter otherwise
    //      spends its post-hit ticks either parked taking a shot or walking
    //      TOWARD the foe that just hit it.
    //
    //      What it does NOT override: the committed-shot windup and E9's
    //      post-fire recovery. Those are measured physical commitments of an
    //      animation already in progress, they are shared with the ranged
    //      round, and overriding them would be a different claim than the one
    //      C1 M2 measured. The residual post-hit latency they impose is
    //      reported honestly in the C2 round report rather than legislated away.
    //
    //      Meaningless on its own -- with C-a1 off nothing is ever latched, so
    //      the break is never live -- so this is a WIDENING of C-a1, not a
    //      second mechanism.
    //
    //      SHIPPED OFF with C-a1. It costs no ADDITIONAL winners on top of the
    //      bearing rule (187/216 either way), and it is the half that does the
    //      most measurable good: it is what takes post-hit seconds-to-leave-
    //      reach 0.42 -> 0.29 and stopped-victim hits 55.2% -> 42.4%. It also
    //      costs the kiter 41% of its shots in champion__vs__heavy_cav_archer
    //      (46 980 -> 27 720 launches over 180 runs) for 0.04 tiles of extra
    //      separation -- a bad trade only because the separation never arrives.
    breakPriority: false,
};

/** Apply a partial override to {@link C2A}. Harness-only entry point. */
export function setC2A(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in C2A)) throw new Error(`setC2A: unknown flag ${k}`);
        C2A[k] = Boolean(overrides[k]);
    }
    return C2A;
}

// ===== PHASE C2-B — THE MELEE SWING: WHEN IT MAY BEGIN, WHEN IT LANDS =====
// Two rules read straight off docs/calibration/c1_chaser_cadence.md §M3 and
// docs/calibration/e15c_contact_forensics.md §2. Neither carries a constant of
// any kind: C-b costs the engine's own tick and C-c moves an existing test,
// nothing is fitted and nothing is timed.
//
// SCOPE. Units whose attack is MELEE and which are not siege -- concretely, the
// `else` arm of update()'s isRanged() split, minus the charge-projectile
// (Fire Lancer) sub-branch that fires before melee reach is ever tested. Ranged
// units never enter the code either rule touches, so ranged-vs-ranged is
// bit-identical with both flags on (asserted by c2b_melee_swing.test.mjs).
//
// A SEPARATE object from R5B / R5D / R5D1 / B2 / R5F, for the reason all of
// those are separate from each other: `--b2 off` has to keep meaning "the
// pre-B2 engine" exactly, and a C2 sweep must not silently drag anything else
// along.
//
// Setting both to false restores 0e2dbc5 BIT-IDENTICALLY. That is structural,
// not merely tested: with the flags off the only new statement that executes is
// the bookkeeping write to `meleeWasMoving`, a field nothing else reads.
export const C2B = {
    // C-b  STOP-TO-SWING. A melee swing may not BEGIN on a tick the unit spent
    //      walking: the unit halts, and the swing starts from the stop.
    //      This is R5b's stop-to-fire for the other half of the army, and it is
    //      asked the same way -- the instantaneous "was I stepping on the tick
    //      my cooldown came up", not a latched "did I move this cycle".
    //
    //      C1 M3, over 29 melee-chases-ranged families: a hit landed while BOTH
    //      parties were moving is 0.0000 per chaser-second on tape in EVERY
    //      SINGLE FAMILY (the tape chaser's own displacement at the instant its
    //      blow lands is 0.000 tiles, everywhere), against 19.8% of the
    //      engine's hits at a median 0.046 tiles of step -- 0.13-0.24 in the
    //      champion families, which at 10 Hz is a walking unit, not collision
    //      jitter.
    //
    //      THE HALT COSTS THE ENGINE'S OWN TICK AND NOTHING ELSE. No stop
    //      overhead is charged (RANGED_STOP_OVERHEAD is a ranged-tape number
    //      and stays there), no reload is touched: hit-to-hit is still
    //      reloadTime plus however many ticks the unit spent arriving. A unit
    //      that closed early and stood waiting out its reload -- which is every
    //      unit in a melee scrum, E15c measuring them planted at p90 0.0 tiles
    //      of displacement -- pays nothing at all, because it was not stepping
    //      when the cooldown expired.
    //
    //      The movement fact is the unit's OWN locomotion decision
    //      (`meleeWasMoving`, set only by update()'s melee move branches), NOT
    //      its measured displacement: a planted unit shoved by
    //      resolveCollisions has not decided to walk and is not gated.
    stopToSwing: false,
    // C-c  WINDUP-COMMIT: reach is tested once, at swing START, and the blow
    //      lands on schedule even if the victim has drifted out of reach by the
    //      time it resolves (the victim must still be ALIVE).
    //
    //      C1 M3: the engine applies damage exactly at its own inRange()
    //      boundary and never past it -- `dHit` equals `reach` to two digits in
    //      all 29 families, 0.99x. The tape lands at 1.43x reach (median 0.91
    //      tiles against a champion's 0.62-tile reach, p90 1.52). E15c §2 saw
    //      the same thing from the other side inside melee scrums: 7.46% of
    //      tape samples are a unit SUSTAINING -- already landing hits on -- a
    //      victim it is standing 0-0.5 tiles OUTSIDE reach of, against 0.31% in
    //      the engine, i.e. "the engine has no state in which a unit fights
    //      from a hair outside the reach line".
    //
    //      HALF OF THIS RULE IS ALREADY THE ENGINE'S BEHAVIOUR and the flag
    //      does not touch it: a melee unit with frame_delay > 0 (paladin 0.433,
    //      heavy_camel 0.333, elite_elephant 0.167, hussar 0.167, elite_steppe
    //      0.217) commits in update()'s committedAttack branch, which checks
    //      only `state !== "dead"` at the landing. Pinned by test so a later
    //      round cannot delete it by accident.
    //
    //      WHAT THE FLAG CHANGES is the frame_delay-0 case -- champion and
    //      halberdier, the two heaviest chasers in the corpus -- where the
    //      swing resolves in the same tick it is decided, so there is no
    //      interval for a victim to drift in. The swing is given the engine's
    //      SMALLEST RESOLVABLE INTERVAL, one tick, and no more: the reach test
    //      moves to the tick the swing begins and the blow lands at the end of
    //      it. That is a tick-granularity fact, not a duration -- see the
    //      honest limit below.
    //
    //      HONEST LIMIT, stated because the number matters. One tick at 60 Hz
    //      is 0.0167 s, in which a 1.54 t/s heavy cavalry archer covers 0.026
    //      tiles: this rule can carry a champion's resolution reach from 0.99x
    //      to roughly 1.03x, NOT to the tape's 1.43x. Reproducing 1.43x needs
    //      the damage frame of a frame_delay-0 swing to lag its start by
    //      ~0.2 s, and NOTHING in the data supports that: `attack_delay` IS the
    //      dat's own damage frame (extract_units.py:471, `frame_delay / 60`)
    //      and it is 0 for both units. A 0.2 s melee lag would be a fitted
    //      constant, so it is not here. The gap is reported, not closed.
    committedSwingLands: false,
};

/** Apply a partial override to {@link C2B}. Harness-only entry point. */
export function setC2B(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in C2B)) throw new Error(`setC2B: unknown flag ${k}`);
        C2B[k] = Boolean(overrides[k]);
    }
    return C2B;
}

// ===== PHASE C2-C — PURE FLIGHT DURING A CONTACT BREAK =====
// One rule, one flag, and NOT a new mechanism: it changes what
// moveAwayFromTarget SUMS while C2A's contact break is live. Nothing here
// introduces a number, a weight or a threshold -- every term it selects or
// drops already exists, and the rule is a state-conditioned choice between
// them.
//
// WHY, and it is a measurement rather than an intuition. C2A built the break
// (latch the melee unit that hit this kiter; flee away from it with priority
// over stop-to-fire until a physical escape criterion) and it FAILED in
// isolation. tools/simjs/c2a_break_probe.mjs says why in three lines --
// magnitudes of the terms moveAwayFromTarget adds, on ticks where a break is
// live, over 86 chase fights x 5 seeds:
//
//   |radial basis|      1.000   <- the break's bearing, unit by construction
//   |orbit + cohesion|  1.249
//   |avoidance|         2.221
//   cos(actual tick step, break bearing)  0.276   (tape 0.88)
//
// The break's own bearing is 22% of a 4.47-magnitude sum. C2A's report draws
// the correct conclusion and closes the obvious door: "the realised heading is
// not basis-limited... do not rebuild this as a different basis; it will move
// the cosine by ~0.02 again." So C-c does not touch the basis. It asks what
// the OTHER 78% is doing there, and the answer is that both terms are
// FORMATION behaviours applied to a unit that is not in formation:
//
//  * ORBIT + COHESION (kiteSteering's tangential and cohesion contributions,
//    E5a/E10) exist to turn twelve individually-fleeing archers into one
//    translating ball. That is a group-manoeuvre force. A unit with a blade in
//    it is not manoeuvring with the group; C1 M2 measured the tape's just-hit
//    kiter beelining away from its toucher at cos 0.88 -- and note that on
//    tape the two bases are near-collinear (0.88 to the hitter AND 0.78 to the
//    enemy centroid at once), so a tape kiter in flight is not trading one for
//    the other. It is simply running.
//
//  * AVOIDANCE is two different forces sharing one loop (calculateAvoidance).
//    Below `minDist` it is a body-overlap resolution -- physics, "I cannot walk
//    through you" -- with force 3..8. Between 1.0x and 1.5x `minDist` it is a
//    SOCIAL band with a flat force 0.5 per neighbour, which is spacing, not
//    physics. A fleeing unit must still not walk through bodies; it has no
//    reason to keep polite spacing from them.
//    (The spec expected the social band to be most of the 2.221. IT IS NOT --
//    measured at 8.5%. See the shipped-state note on `pureFlight` below; the
//    expectation was wrong and the rule is nearly a no-op on this term.)
//
// WHAT SURVIVES A BREAK, therefore: the break bearing, actual imminent-overlap
// avoidance, the arena's obstacle steer (also physics -- a unit cannot flee
// through a tree), the velocity smoothing, and every commitment C2A already
// declined to override (the committed shot windup, E9's fireRecovery). What
// does not: the two group-formation terms and the social spacing band.
//
// NO CONSTANT, CHECKED TWICE. The orbit/cohesion drop is a term selection --
// KITE_TANGENTIAL_WEIGHT and KITE_COHESION_WEIGHT keep their values and keep
// applying to every unit not in a break, and to every tick of every unit once
// its break ends. The avoidance narrowing is a BAND selection between two
// bands the function already computes and already distinguishes (`overlap > 0`
// is the existing test); no distance, force or weight is edited. Setting the
// flag false restores the pre-C2C engine bit-identically -- structurally, not
// merely by test, because the flag gates only which of two existing
// expressions is evaluated.
//
// SCOPE IS INHERITED, NOT RE-DECLARED. The rule is reachable only on a tick
// where `contactBreakHitter()` is non-null, which requires C2A.contactBreak on
// AND a melee hit on a non-siege ranged body. So ranged-vs-ranged (no melee
// attacker exists), melee-vs-melee (the victim-side isRanged() gate) and siege
// (minAttackRange > 0) are unreachable by exactly the construction C2A already
// proved byte-identical over the full corpus.
export const C2C = {
    // C-c PURE FLIGHT. While a contact break is live, this unit's movement is
    //     composed of the break bearing plus COLLISION avoidance only:
    //       1. kiteSteering's orbit + cohesion contribution (`steering.x/y`) is
    //          not added. The retreat BASIS is unaffected -- C2A already
    //          replaced it with the hitter radial for the duration of the
    //          break, so `steering` is simply unread while pure flight holds;
    //       2. calculateAvoidance is evaluated over imminent-overlap pairs
    //          only (`dist < minDist`, the band it already scores with
    //          `overlap > 0`), dropping the 1.0-1.5x social band's flat 0.5.
    //
    //     Both revert on the tick the break ends -- which is a distance, not a
    //     timer -- so a kiting ball is a ball again the moment its touched
    //     member is clear, and a unit that never takes a melee hit never sees
    //     this rule at all.
    //
    //     MEANINGLESS WITHOUT C2A.contactBreak: with that off, no break is
    //     ever live and this flag can never fire. It is a modifier of C2A's
    //     state, not a third mechanism.
    //
    //     ===== SHIPPED OFF. THE PREDICTION FAILED, AND SO DID THE PREMISE. ==
    //     Full numbers: docs/calibration/c2c_pure_flight.md. The rule is LIVE
    //     and does exactly what it says -- |orbit+cohesion| 1.379 -> 0.000,
    //     |avoidance| 1.875 -> 1.716, basis share of the summed magnitudes
    //     22% -> 37% -- and the realised heading does not move:
    //
    //       cos(actual tick step, break bearing)   C-a 0.276   C-a+C-c 0.276
    //       cos(flee, away-from-the-hitter)        C-a 0.63    C-a+C-c 0.64
    //       victim radial displ / reload (tiles)   C-a 0.087   C-a+C-c 0.046
    //
    //     TWO THINGS THIS ROUND ESTABLISHED, both worth more than the rule.
    //
    //     (1) THE SOCIAL BAND WAS NEVER THE PROBLEM. C2A read
    //     calculateAvoidance's 2.221 as a social force; narrowing to genuine
    //     overlap removes 8.5% of it (1.875 -> 1.716). A unit with a break
    //     live is inside a scrum, so nearly every body within 1.5x minDist of
    //     it is ALREADY overlapping at force 3..8. That sum is collision
    //     physics and there is nothing social left to take out of it.
    //
    //     (2) THE HEADING IS NOT REACHABLE BY TERM SELECTION. C2A showed no
    //     CHOICE of basis moves the realised cosine; this shows no SELECTION
    //     of terms does either -- 37% of the sum still yields 0.276. The
    //     kiter cannot beeline because it is physically boxed in by bodies,
    //     not because it is badly steered. Do not write a third rule in this
    //     region; measure the packing (COMBAT_PACK_FACTOR, minDist,
    //     resolveCollisions) instead, which is where the 0.05-tiles-per-reload
    //     cap on radial displacement actually lives.
    //
    //     COST: corpus 194 -> 187 (C-a) -> 181 (C-a+C-c).
    //     champion__vs__heavy_cav_archer stays 1/9 -- so the Phase-C chain's
    //     own falsifiable test ("if the kiter LEAVES, the chaser's output
    //     falls") came back NEGATIVE: champion damage per run 943 -> 960
    //     against a required ~603. A second canary breaks on top,
    //     hand_cannoneer__vs__heavy_camel 6/6 -> 0/6 (camel damage per run
    //     591 -> 768, tape 273) -- the same shape, the kiter paying retreat
    //     time for separation that never arrives.
    pureFlight: false,
};

/** Apply a partial override to {@link C2C}. Harness-only entry point. */
export function setC2C(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in C2C)) throw new Error(`setC2C: unknown flag ${k}`);
        C2C[k] = Boolean(overrides[k]);
    }
    return C2C;
}

// ===== PHASE D2 — SIEGE PROJECTILE / BLAST MECHANICS =====
// Four rules read off docs/calibration/d1_siege_forensics.md §2 (the scorpion
// bolt) and §3 (the onager stone). Kept in their OWN object for the same reason
// C2A is separate from C2B: `--d2 off` has to keep meaning "the pre-D2 engine"
// exactly, and a D2 sweep must not drag a melee flag along.
//
// Setting all four to false restores bb2e6fa BIT-IDENTICALLY, and that is
// STRUCTURAL, not merely tested: with the flags off, every statement D2 adds is
// either inside an `if (D2.x)` or a write to a field nothing else reads, no D2
// path draws from sim.rng, and Projectile.update's new branch is unreachable
// because nothing ever attaches a `sweep` descriptor. Asserted by
// tests/js/engine/d2_siege.test.mjs.
//
// SCOPE. boltCorridor touches only units with pass_through_percent > 0 (in this
// corpus: the scorpion line). blastZeroPoint / projectileArc / blastDebris touch
// only units with splash_radius > 0 (the onager line). A fight with neither
// cannot reach any D2 statement, which is what makes the melee and ranged
// subsets byte-identical with every flag ON.
export const D2 = {
    // S1  BOLT CORRIDOR. A pass-through bolt stops being "primary + one nearby
    //     body" and becomes a LINE that keeps flying. It pays 1.00x to its aim
    //     target on arrival (unchanged) and exactly 0.50x of its own post-armor
    //     damage, unrounded, to every OTHER enemy body whose centre comes within
    //     (that body's radius + the projectile's radius) of the swept path --
    //     once per bolt, no cap on victims, and including bodies BEHIND the aim
    //     point, because the bolt flies BOLT_TOTAL_FLIGHT_TILES and not merely
    //     to the target.
    //
    //     D1 §2.1: 1041 of 1510 attributed tape events sit at EXACTLY 0.500x of
    //     that fight's full hit and 403 at 1.000x, with nothing in between (the
    //     66 stragglers are all HP-clamped killing blows) and no bolt in the
    //     corpus has more than one full-damage victim. §2.2: 2.56 victims per
    //     landed bolt (max 10) against the engine's hard ceiling of 2, and the
    //     victims are COLLINEAR -- perpendicular distance to the bolt's own line
    //     is p99 0.373 / 0.458-0.665 / 0.837 for victim collision_size 0.20 /
    //     0.25 / 0.50, i.e. it is a line test against the body, not a radius
    //     around a point. §2.5: (victims x fraction) accounts for the scorpion's
    //     entire 24% damage-per-shot deficit with nothing left over.
    //
    //     The dat agrees this is the right unit to do it to: projectile 627
    //     (Heavy Scorpion) carries vanish_mode = 1, which is Genie's own boolean
    //     for "this projectile passes through units", against 0 on the onager
    //     stone 656; and HWBAL's blast_attack_level is 3, the level this repo's
    //     own ability_registry.py already classifies as pass_through.
    boltCorridor: false,
    // S2a BLAST ZERO POINT. E4's linear-from-full-at-the-body-edge falloff keeps
    //     its SHAPE and moves its zero crossing from splash_radius (1.5 tiles)
    //     to BLAST_FALLOFF_ZERO_TILES (1.667). D1 §3.2 regressed the tape's
    //     non-kill blast events (n=470): frac = 1.0728 - 0.6436 x edge, i.e.
    //     clamped-full out to edge 0.113 and ZERO at edge 1.667, against E4's
    //     zero at 1.500. The shipped rule therefore under-pays every off-centre
    //     victim by a mean +0.095 of full damage (6-11 pp across the 0.2-1.4
    //     tile bands), which is where the onager's shot_x = 0.91 comes from.
    blastZeroPoint: false,
    // S2b PROJECTILE ARC. The stone is lobbed, not thrown flat: its dat
    //     projectile_arc = 0.4 sets the apex of a parabola whose span is the
    //     shot, so the path it actually flies is longer than the straight line
    //     the engine flies it along, at the same dat speed. See
    //     arcFlightFactor() below for the derivation -- no fitted constant, the
    //     multiplier falls out of arc = 0.4 analytically.
    projectileArc: false,
    // S2c BLAST DEBRIS. One onager shot is TEN projectiles: 1 x master 656
    //     (Projectile Mangonel (Primary), the unit's own projectile_unit_id) and
    //     9 x master 369 (Secondary), a ratio D1 §3.1 measured as exactly 9.000
    //     in every recording. Each fragment that lands on a body deals exactly
    //     1.00 damage (master 369's type_50.attacks is empty, so every hit
    //     bottoms out on the minimum-damage floor). Numerically small by
    //     construction -- see the measured verdict in the D2 round report.
    //
    //     SHIPPED ON -- the one D2 rule the board endorses (-0.52 opponent-side
    //     HP error, -1.03 onager-side, no row worse by >0.2) and a dat fact,
    //     not a hypothesis. Its golden-panel / matchup re-sim obligations fold
    //     into the campaign-end recapture already queued (parity_check has been
    //     deliberately red since the campaign's first behavior change).
    blastDebris: true,
};

/** Apply a partial override to {@link D2}. Harness-only entry point. */
export function setD2(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in D2)) throw new Error(`setD2: unknown flag ${k}`);
        D2[k] = Boolean(overrides[k]);
    }
    return D2;
}

// ===== E1 — ORBIT KITE (the kiter's retreat bearing) =====
// One mechanism, from the paired measurement docs
// docs/calibration/e1_kite_orbit_tapes.md / e1_kite_orbit_engine.md (metrics in
// data/calibration/analysis/e1_kite_orbit_*.json). Over the 78 ranged-vs-melee
// kite tapes the kiting side ORBITS the fight centre clockwise-on-screen in
// 78/78 recordings (median +1.13 revolutions, sign consistency 0.94, not one
// counterclockwise tape), holds its radius (r-slope −0.030 tiles/s) and moves
// tangential-first (tan/rad 1.77) — straight through ground the enemy held
// earlier (reuse 0.54). The engine at the same spawns instead flees RADIALLY:
// r-slope +0.146 t/s outward in 78/78 fights, hits the wall band in a median
// 5 s, ends 90% of final-quarter frames pinned, and 86% of its kiter deaths
// happen within 2 tiles of a wall. The tapes have no wall-pinning failure mode
// at all.
//
// The rule: with orbitKite on, a group-kiting unit's retreat BEARING stops
// being "away from the threat" and becomes "along the clockwise arc about the
// fight centre C at my current radius" — the waypoint is C + rotate(d, s/r)
// where d = pos − C and s is the EXISTING per-tick kite step distance
// (moveSpeed × dt; no new magnitude constant). C is computed ONCE per battle
// (scenario.js: midpoint of the two sides' spawn centroids — the tape boards'
// own reference point). ONLY THE BASIS CHANGES: the orbit/cohesion steering
// terms, avoidance, velocity smoothing, arena constraint, and every trigger
// for entering/leaving the kite state are byte-for-byte untouched (the C2
// rounds adversarially refuted touching any of them). A live C2A contact
// break still supersedes the basis exactly as it does the radial one.
//
// SIGN CONVENTION (tested in tests/js/engine/e1_orbit_kite.test.mjs): the
// tape boards define positive Δθ = increasing atan2 in game tile coordinates
// = CLOCKWISE on screen under the iso mapping sx = x − y, sy = (x + y)/2.
// TapeBox.worldToTile is a positive uniform scale (no axis flip), so
// increasing atan2 in engine world coordinates is the same rotation sense:
// rotate(d, +φ) = (dx·cosφ − dy·sinφ, dx·sinφ + dy·cosφ).
//
// orbitBlend is the ONE knob the E1 brief permits, at a MEASURED value only:
// instead of the pure tangent, blend tangent : existing-away-basis at
// E1_ORBIT_TANRAD : 1 — the tape corpus's own tangential:radial displacement
// ratio (1.77, e1_kite_orbit_tapes.json aggregate). Meaningless without
// orbitKite.
//
// MEASURED VERDICT (E1 round, docs/calibration/e1_orbit_kite.md). Pure
// tangent is the better variant on every geometry axis (dev subset, 3 seeds:
// median sweep +0.57 rev vs blend +0.38; r-slope +0.041 vs +0.159; the blend
// re-adds the radial push the avoidance sum already supplies and balloons
// the radius). With orbitKite on, the full 78-fight kite corpus goes from
// +0.10 to +0.54 median revolutions, sign consistency 0.68 → 0.97 (78/78
// clockwise), cornering 0.90 → 0.60, wall-death fraction 0.86 → 0.28 — the
// tapes' geometry, directionally, on every metric.
//
// SHIPPED OFF, deliberately, and here is the honest reason: the outcome
// board pays for the faithful geometry. A kiter that orbits at held radius
// stays reachable by a chaser that the engine still lets swing at FULL
// cadence — the tape's melee-chasing-a-kiter cadence loss (1.29x slower,
// E12/C1) is unmodeled — so the champion families catch the orbiting ball:
// full corpus 194/216 → 181/216, all 13 net losses in champion__vs__
// arbalester (6, a canary) and champion__vs__heavy_cav_archer repeats (8−1).
// This is the SAME knife edge that already holds P1/P2/C2a off. Melee,
// siege and ranged-vs-ranged are bit-identical with the flag on (the
// kiteSteering gate). Flip orbitKite when the chaser-cadence mechanism
// lands, and re-gate P1+P2 in the same round — E1-on moves both of their
// blocked ledgers the right way (champion dmg/run 145 → 720 vs ledger ~603;
// camel dmg/run 591 → 540 vs ledger ~273 with HC land rate held 85.3 →
// 84.1%).
//
// Both flags ship OFF until then — the defaults test pins that, and
// calib_runner's --e1 spec is the A/B entry point.
export const E1 = {
    // The orbit basis itself (mechanism above).
    orbitKite: false,
    // Tangent:radial blend at the measured 1.77:1 instead of pure tangent.
    orbitBlend: false,
};

/** Apply a partial override to {@link E1}. Harness-only entry point. */
export function setE1(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in E1)) throw new Error(`setE1: unknown flag ${k}`);
        E1[k] = Boolean(overrides[k]);
    }
    return E1;
}

// The tape corpus's tangential:radial displacement ratio — the ONLY value
// orbitBlend is allowed to blend at (data/calibration/analysis/
// e1_kite_orbit_tapes.json, aggregate over all 78 tapes; per-kiter means run
// 1.67–1.81). A MEASURED tape quantity, same category as E9's recovery
// constants — never tuned against the scoreboard.
export const E1_ORBIT_TANRAD = 1.77;

// Degenerate-centre guard, in tiles: inside this radius of C the arc has no
// usable tangent (and φ = s/r blows up), so the unit falls back to the
// existing radial retreat for the tick. From the E1 brief, not fitted.
export const E1_ORBIT_MIN_RADIUS_TILES = 0.5;

// ===== C3 — POST-SWING PLANT (the melee chaser's halt after a landed blow) ====
// One mechanism, from docs/calibration/c3_chaser_pursuit_forensics.md
// (measurements in data/calibration/analysis/c3_chaser_pursuit.json). Over the
// six chaser families (five distinct melee chaser classes) the tape's melee
// chaser, after every LANDED swing on a ranged kiter, stands planted for a
// median 0.64–0.74 s — with ZERO halts under 0.2 s in any family (n = 29–301
// windows per family). The E1-on engine's chasers halt 0.0 s (65–84 % of
// windows under 0.2 s): they swing and keep walking. That halt is, measured,
// ~100 % of the kiter's per-reload escape (+0.50…+0.78 tiles of the +1.03
// accrue while the chaser stands; §Q3 split), and inserting it into
// `interval ≈ max(reload, halt + re-close)` reproduces the tape's measured
// swing cycle in 5/6 families — including the halberdier control, whose 3.0 s
// reload swallows halt + re-close entirely, which is why the engine already
// matches the tape there and why this rule must not change such fights.
//
// The rule: when a MELEE unit LANDS a swing on a RANGED victim, it may not
// MOVE for POST_SWING_PLANT_S seconds. Movement ONLY — implemented as a stamp
// on the E15b `moveLockUntil` field, read by the same meleeMoveLocked()
// predicate, so a planted unit still turns, re-targets, reloads, is shoved by
// resolveCollisions, and (the halberdier invariant) still SWINGS on schedule:
// update()'s in-reach attack branch is tested BEFORE the plant branch, so a
// victim still in reach when the cooldown expires is hit at bare reloadTime.
// The plant does not delay a committed windup or its damage either — it is
// stamped at hit RESOLUTION (performAttackOn), after the blow has landed.
//
// SCOPE: melee attacker, RANGED NON-SIEGE victim only (the victim's own
// is_ranged flag, the same scoping the pursuit-bar and MELEE_TARGET_LOCK
// rules use). C2B refuted a melee-vs-melee plant — the tape's melee-scrum
// moving-share is a monotone ramp across the reload cycle, not a step
// (e15_walk_forensics §6, MELEE_SWING_RECOVERY_S rationale above) — so a
// melee victim never stamps the lock and melee-vs-melee is bit-identical
// with the flag on. Ranged attackers never reach the stamp (they fire
// projectiles, not performAttackOn) and meleeMoveLocked() excludes them
// besides. SIEGE victims never stamp either (C4-round refinement): the
// plant was measured on chasers pursuing ranged KITERS, siege carries
// is_ranged = 1 in the combat dicts, and the C4 full gate traced the
// siege-attacker HP-pts regressions to champions/halberdiers planting
// against onagers/scorpions. The victim test excludes the dat's Siege
// Weapons armor class (20) — not minAttackRange, whose 1.0 on the Imperial
// Elite Skirmisher would wrongly exclude a foot kiter. Re-measure when the
// new onager tape lands.
//
// SHIPPED OFF until the C3 iteration round's boards land: flipping it changes
// every melee-chases-ranged fight in the corpus, so it ships through the same
// A/B gate discipline as E1.orbitKite (whose knife edge — the unmodeled
// chaser-cadence loss — this rule is the measured mechanism FOR).
export const C3 = {
    // The 0.7 s post-landing movement lock on melee-vs-ranged (above).
    postSwingPlant: false,
};

/** Apply a partial override to {@link C3}. Harness-only entry point. */
export function setC3(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in C3)) throw new Error(`setC3: unknown flag ${k}`);
        C3[k] = Boolean(overrides[k]);
    }
    return C3;
}

// The plant's duration, in seconds. A MEASURED TAPE QUANTITY, same category as
// E9's recovery constants: the tape's post-landing halt median is 0.64–0.74 s
// across all six chaser families / five chaser classes (c3_chaser_pursuit.json
// §Q3 — champion 0.74, halberdier 0.72, heavy_camel 0.71, paladin 0.64,
// hussar 0.71), reading as a fixed swing-commit + recovery interval, not a
// speed- or class-dependent one. 0.7 is the centre of that measured band; any
// adjustment must stay inside 0.64–0.74 and record its reason here. NOT tuned
// against the scoreboard.
export const POST_SWING_PLANT_S = 0.7;

// ===== C4 — FLEE DURING RELOAD (the hunted kiter's run-commitment) ===========
// One mechanism, from docs/calibration/c1_chaser_cadence.md M2 (Table 2b) and
// the composed-cycle residual the C3 round measured
// (docs/calibration/c3_post_swing_plant.md §"What moved"). The tape cycle for
// a ranged kiter hunted by melee is FIRE -> RUN THE WHOLE RELOAD WINDOW ->
// HALT (stop-to-fire) -> FIRE. C1 Table 2b measures the run: the tape's foot
// shooters move in 2.7-3.4 s CONTINUOUS stretches (hand_cannoneer moveMed
// 3.35 s, imp_elite_skirm 2.71 s, ~one full reload window each) with ONE stop
// of ~0.62 s per cycle (stops/min 16-18 at reload 3.0-3.45) -- the fire halt
// and nothing else. The engine's same units move in 0.3-0.4 s dribbles at
// ~2x the tape's stopped duty cycle (stopFrac 0.36-0.46 vs 0.18-0.20).
//
// Where the engine's extra standing lives, measured at the state level (C4
// round probe): mid-reload the hunted kiter is already IN the kite arm most
// of the window -- the standing that is a DECISION rather than physics is
//   (1) E9's post-fire recovery freeze (0.20-0.43 s per cycle, 11-42 % of
//       reload ticks depending on unit), and
//   (2) the R5B reloading park (the settle arm), reachable mid-reload when
//       the unit's own target is not melee.
// E9's recovery was measured on the RANGED corpus ("over kiting cycles",
// ranged-vs-ranged): an un-hunted shooter really does stand 0.33 s after the
// launch. The C1 ranged-vs-melee tapes show the opposite for a HUNTED one:
// its single 0.62 s halt per cycle is the pre-shot windup alone
// (hand_cannoneer attack_delay 0.43 + 0.15 stop overhead = 0.58), i.e. it is
// running again the moment the missile leaves. Both are tape facts; the
// hunted/un-hunted split is what reconciles them.
//
// The rule: with fleeDuringReload on, a FOOT ranged unit that is (a)
// MID-RELOAD (attackCooldown > 0, cannot fire yet) and (b) currently the
// TARGET of at least one living MELEE enemy (the engine's own target
// bookkeeping -- no distance constant, no timer constant) KEEPS MOVING
// through the reload window along the EXISTING kite-retreat basis (the same
// moveAwayFromTarget + kiteSteering call the kite arm already makes: E1's
// orbit waypoint when E1.orbitKite is on, today's radial basis otherwise).
// Concretely the two parks above stop holding it: the post-fire recovery no
// longer freezes a hunted kiter (it still blocks the un-hunted), and the
// settle arm is outranked by the kite arm while a hunter is on it.
//
// WHAT IT DOES NOT TOUCH. Firing is never delayed: the predicate requires
// attackCooldown > 0, so at reload expiry the stop-to-fire law (R5B-D1),
// the windup and its halt cost run exactly as today (`wasMoving` is written
// by the same arms that always wrote it). The committed-shot windup still
// freezes (an animation in flight, same as C2A's refusal). E1's waypoint
// math, C2A's break and C3's plant are untouched and orthogonal. Scope is
// the C1 corpus's own: non-siege ranged victims only (minAttackRange > 0 --
// Siege Onager 3.0, Heavy Scorpion 2.0 -- is excluded by the same clause
// kiteSteering and C2A use; siege owns a competing repositioning path and
// was excluded from the C1 measurement by construction). Ranged-vs-ranged
// fights have no melee hunter, so they are unreachable by construction;
// melee units never read any of this.
//
// FOOT SHOOTERS ONLY (refinement, this round's gate). C1 M2's class split
// is explicit: the run-commitment is measured on the 0.96 t/s FOOT shooters
// (stopped duty ~2x too high in-engine, runs 8x too short), while the
// mounted heavy_cav_archer's duty cycle is "already right" (0.688 engine vs
// 0.659 tape) and its tape stopMed 1.26 s equals its own windup + post-fire
// recovery -- the tape's mounted archer pays its recovery even while
// hunted. Arming it was out-of-evidence and measurably wrong (C4-alone
// flipped the halberdier__vs__heavy_cav_archer control 6/6 -> 0/6, and the
// HCA-as-kiter families paid +2.4..+3.8 HP-pts on the first C4 full gate).
// A hunted unit carrying the dat's Cavalry (8) or Cavalry Archer (28)
// armor class is therefore NOT armed -- a class fact, not a fitted speed
// threshold.
//
// SHIPPED OFF until the C4 iteration boards land -- same A/B gate discipline
// as E1.orbitKite / C3.postSwingPlant, whose composed cycle this rule is the
// third leg of. `--c4 fleeDuringReload` on calib_runner.mjs (and
// dump_kite_tracks.mjs) is the entry point; the intended pairing is
// `--e1 orbitKite --c3 postSwingPlant --c4 fleeDuringReload`.
export const C4 = {
    // The hunted kiter's run-commitment through the reload window (above).
    fleeDuringReload: false,
};

/** Apply a partial override to {@link C4}. Harness-only entry point. */
export function setC4(overrides) {
    for (const k of Object.keys(overrides)) {
        if (!(k in C4)) throw new Error(`setC4: unknown flag ${k}`);
        C4[k] = Boolean(overrides[k]);
    }
    return C4;
}

// ---- D2 measured / dat quantities -------------------------------------------

// TOTAL BOLT FLIGHT, in tiles from the muzzle. A MEASURED TAPE CONSTANT, in the
// same category as E9's post-fire recovery, and labelled as one because the dat
// does NOT contain it: `tools/simjs/d1_dat_audit.py` reads projectile 627's own
// `max_range` as 0.0 (the fire-graphic variants 628/1114 carry 20.0, the stone
// 656 carries 25.0 -- neither is 10.6), so there is no field to derive it from.
//
// What the tape says (D1 §2.3, n=647 bolts): the bolt flies a NEAR-CONSTANT
// 10.6 tiles regardless of how far its target is -- median 10.56, p10 9.45,
// p90 10.66, and 271 of 647 land in the single 10.6 bin, truncated below only
// where the arena wall cuts the flight short. The unit's own range is 8, so the
// bolt overruns its maximum range by ~2.6 tiles and keeps damaging bodies the
// whole way (median 5.07 tiles past the body it paid full damage to, against the
// engine's 0.00).
//
// HONEST LIMIT ON THE PARAMETRISATION. A one-range corpus cannot separate
// "range + 2.6" from "range x 1.32": every scorpion in these 13 recordings is a
// fully-upgraded Heavy Scorpion at range 8. The AoE2 wiki's pass-through page
// says range upgrades "also increase the extra range that the projectile
// travels", which favours the multiplicative reading, but that is a sentence and
// not a measurement. The flat measured total is used because it is what was
// actually observed; a recording of a non-upgraded Scorpion (range 7) would
// settle it in one fight.
export const BOLT_TOTAL_FLIGHT_TILES = 10.6;

// PASS-THROUGH FRACTION. Not a fitted number and deliberately NOT the dict's
// `pass_through_percent`: that column is a PIPELINE-DERIVED quantity (projectile
// 627's own attack 6 / the unit's attack 14 = 0.4286) which the engine then
// floors, giving 0.333x of full against a Persian Hussar. The tape pays exactly
// 0.500x, unfloored -- 1041 of 1510 events, flat across every distance bucket
// from 0 to 12 tiles flown (D1 §2.1) -- and the AoE2 wiki states the same rule
// in words: only the targeted unit takes full damage, every other unit hit takes
// half. Applied to each victim's OWN post-armor damage, which is algebraically
// the same as the community's "half attack against half armour" phrasing
// ((A-D)/2 === A/2 - D/2) everywhere short of the minimum-damage clamp, which no
// event in this corpus reaches.
export const PASS_THROUGH_FRACTION = 0.5;

// BLAST FALLOFF ZERO POINT, in tiles beyond the victim's own body edge. The
// measured zero crossing of D1 §3.2's regression (n=470 non-kill blast events):
// frac = 1.0728 - 0.6436 x edge crosses zero at edge = 1.667. Re-expressed as
// `frac = 1 - edge / 1.667` -- the same straight line through the same zero, with
// the intercept clamped at 1.0 rather than carrying the fit's 1.0728 (a unit
// cannot take more than full damage, and the 1.07 is the regression absorbing
// the near-band's HP-clamped kills).
//
// WHY A TILE COUNT AND NOT A RATIO OF splash_radius. The measurement exists for
// exactly one blast radius -- the Siege Onager's 1.5 -- so "1.667 tiles" and
// "1.111 x splash_radius" fit the data identically and nothing in this corpus
// separates them. The absolute form is used because it does not silently
// legislate a shape for the Mangonel (blast 1.0), the Onager (1.25) or the
// Bombard Cannon, none of which appear in any recording. The consequence is
// deliberate and stated: with S2a on, EVERY blast unit's zero point moves to
// 1.667 tiles past the body edge. That is a claim about the blast law, not about
// the Siege Onager, and it is the claim the tape supports.
export const BLAST_FALLOFF_ZERO_TILES = 1.667;

// BLAST DEBRIS: how many secondary projectiles a blast shot throws, and how far
// they scatter. The count is the dat's (`secondary_projectile_unit` 369 on the
// Siege Onager) and the tape's, which agree exactly: D1 §3.1 counted 6 primary /
// 54 secondary and 19 / 171, ratio 9.000 in every recording.
//
// The scatter radius is measured: fragment offsets from the primary stone's
// landing point run median 0.628, p90 0.954, max 2.033 tiles, forward component
// median +0.039 and lateral median -0.010 -- i.e. isotropic about the stone. An
// equal-area sample of a disc of radius 1.0 has median radius 0.707 and p90
// 0.949, which is the measured distribution to within its own noise.
export const BLAST_DEBRIS_COUNT = 9;
export const BLAST_DEBRIS_SCATTER_TILES = 1.0;
export const BLAST_DEBRIS_DAMAGE = 1;

// PER-SLUG DAT FALLBACKS for the six fields D1 §6 found the pipeline drops
// (`blast_attack_level`, `projectile_arc`, `vanish_mode`, `hit_mode`, the
// secondary-projectile count, and the projectile's own `collision_x`). Same
// contract as ACCURACY_DISPERSION_BY_SLUG above and for the same reason: the
// values are read out of the live dat by tools/simjs/d1_dat_audit.py, the combat
// dict has no column for them yet, and the engine PREFERS the dict field
// whenever one shows up (battle_unit.js reads `stats.<field> ?? the map`). When
// the ref-DB registry carries them these maps get deleted, not edited.
//
// Dat values (empires2_x2_p1.dat, via d1_dat_audit.py):
//
//   HWBAL 542 (heavy_scorpion)  blast_attack_level 3  proj 627  arc 0.0
//                               vanish_mode 1  hit_mode 1  collision_x 0.1
//   SNAGR 588 (siege_onager)    blast_attack_level 1  proj 656  arc 0.4
//                               vanish_mode 0  hit_mode 0  collision_x 0.1
//                               secondary_projectile_unit 369 x 9
//
// Only these two slugs are pinned. A unit with no entry gets no D2 behaviour it
// would not already have had: arc defaults to 0 (no flight-time change),
// secondary count to 0 (no debris). Inventing values for the rest of the roster
// is exactly the fitted constant this round is not allowed to add.
export const PROJECTILE_ARC_BY_SLUG = new Map([
    ["heavy_scorpion", 0.0],
    ["siege_onager", 0.4],
]);
export const VANISH_MODE_BY_SLUG = new Map([
    ["heavy_scorpion", 1],
    ["siege_onager", 0],
]);
export const BLAST_ATTACK_LEVEL_BY_SLUG = new Map([
    ["heavy_scorpion", 3],
    ["siege_onager", 1],
]);
export const SECONDARY_PROJECTILE_COUNT_BY_SLUG = new Map([
    ["heavy_scorpion", 0],
    ["siege_onager", 9],
]);

// ARC -> FLIGHT-TIME MULTIPLIER. Derived, not fitted.
//
// The dat's Projectile Arc (attribute 69) is documented as "controls the maximum
// height of the fired projectile", as a fraction of the shot's span: arc 0.4
// means the stone peaks 0.4 x (muzzle-to-impact distance) above the line. The
// projectile's dat `speed` is its speed ALONG THAT PATH, so a lobbed stone
// covering the same ground takes longer than a flat one -- which is exactly the
// sign of D1 §3.4's residual (engine stone 1.16 s against the tape's 1.88 s in
// the close-range fights, even though the engine's median range is slightly
// SHORTER, so distance cannot explain it; scorpion projectile 627 has arc 0.0
// and its tape flight times already match a straight 6.0 tiles/s).
//
// For a symmetric parabola of span D and apex h = arc x D, write k = 4 x arc.
// Then y = 4h(x/D)(1 - x/D), dy/dx = k(1 - 2x/D), and the path length is
//
//   L = integral_0^D sqrt(1 + k^2 (1 - 2x/D)^2) dx
//     = D x [ sqrt(1 + k^2)/2 + asinh(k)/(2k) ]
//
// so time-of-flight = (L / D) x the straight-line time. The bracket is what this
// function returns. It is 1.0 at arc 0 (the limit, and the value the code
// short-circuits to), and 1.3338 at the stone's arc = 0.4 -- i.e. the D1 gap is
// predicted to close by a third, NOT to vanish. That is stated up front as the
// rule's own honest limit: it lands squarely on the hussar recording's 1.28x
// residual and leaves roughly half of the camel recording's 1.62x on the table.
//
// The alternative reading -- that Genie gives the stone a constant HORIZONTAL
// speed and solves a ballistic vertical -- predicts flight time D/speed exactly,
// i.e. no change at all from today's engine, which the measurement rules out.
export function arcFlightFactor(arc) {
    if (!(arc > 0)) return 1;
    const k = 4 * arc;
    return Math.sqrt(1 + k * k) / 2 + Math.asinh(k) / (2 * k);
}

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
//
// PHASE B2 CORRECTION: that last sentence was the INTENT and it was not what
// the code did. resolveCollisions' floor is 1 px NARROWER than the soft floor
// calculateAvoidance holds cross-team pairs at, so the hard pass never sees a
// pressed-together pair and the trigger fired on 0.2% of the ticks it was
// written for. Contact is now the soft floor plus the hard pass's own contact
// event (see the B2 flag object at the top of this file); this flag still
// ships true and still disables the whole rule when false.
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
