# Latest Standard-Unit Calibration Design

## Objective

Calibrate standard-unit melee-versus-melee fights, followed by ranged-versus-ranged fights, against only the valid recordings in `aoe2_golden_STANDARD_UNITS_2026-08-02.zip`. Superseded recordings, legacy far-spawn melee recordings, frozen-position recordings, and the `legacy_pending_rerecord` gaps are excluded.

## Scope

The melee-class gate includes Champion, Halberdier, Elite Fire Lancer, Paladin, Hussar, Heavy Camel, Elite Steppe Lancer, and Elite Battle Elephant. Elite Fire Lancer remains in this gate at the user's direction, but any volley-specific correction must be isolated from ordinary melee behavior.

Only pair families represented by valid decoded recordings are scored. Missing pair families are reported as coverage gaps, never treated as passes or calibration evidence. After melee is resolved, the same latest-only method is applied to ranged-versus-ranged standard-unit families.

## Authoritative corpus migration

The August 2 archive is a replacement corpus, not an additive batch. Its valid decoded records replace superseded canonical records for the same standard-unit scope. Migration must:

1. Preserve an auditable backup/reference to the prior manifest state.
2. Import only the archive's valid decoded records.
3. Exclude `legacy_pending_rerecord` completely.
4. Rebuild spawn inputs from the imported recordings, including the new close-spawn layouts.
5. Make the active manifest unambiguous about archive provenance and content hashes.
6. Add a regression check proving no excluded legacy record enters a generated calibration board.

## Scoring contract

Scoring is performed per unordered unit-pair family using all valid latest repeats.

- First priority: modal winner must match the tape's modal winner.
- Second priority: simulated median winner HP must be within 20% of tape median winner HP.
- A result within 25% is reported as near-pass, not silently promoted to the 20% target.
- Split-winner or tied-modal tape families are labeled unstable and evaluated for distribution/range behavior; they do not drive a deterministic winner correction.
- Single-record families remain provisional and must not justify a broad mechanic change by themselves.

The top-three work queue is ordered by: wrong stable modal winner, then largest winner-HP error, then evidence strength/repeat count.

## Calibration strategy

Use the smallest shared mechanic that explains tape evidence across multiple affected families. Candidate areas include engagement/formation geometry, target acquisition and retarget timing, collision/contact throughput, reach, charge/volley handling, and attack cadence. Matchup-specific outcome multipliers and unit-pair exceptions are prohibited.

For each selected failure:

1. Reproduce it from latest tape inputs.
2. Compare tape and simulator timelines at first contact, target assignment, damage cadence, deaths, retargets, and survivor HP.
3. State one falsifiable root-cause hypothesis.
4. Add a failing focused test or deterministic calibration assertion.
5. Implement one narrow mechanic change.
6. Re-run the target family, all melee-class families, and the full automated suite.
7. Keep the change only if it improves the target without material regressions elsewhere.

## Deliverables and completion gates

Melee is complete when:

- every covered stable-winner melee family has the correct modal winner;
- every covered family is within 20% median winner HP where the tape evidence is stable, or any remaining 20-25% near-pass is explicitly itemized with evidence;
- unstable and single-record families are separately identified;
- all automated tests pass; and
- a latest-only board records corpus provenance, coverage, winner agreement, HP error, and exclusions.

Ranged-versus-ranged then follows the same workflow and produces an equivalent latest-only board. No production deployment, production data mutation, push, or merge is part of this work.
