# Phase 003 inference gate repair

The 256 phase-003 fights produced 789 complete seed records, no blocked pairs,
and an exact replay. The inference refresh stopped at validation because an R2
inference cited the first proposed tradeoff family rather than the validated
family that supported its outcome. The saved fights and V3 combat source were
unchanged.

Reviewing that failed gate also exposed an actual R2 transfer gap. The
corrected-engine ranking root has 27 Flemish Militia beating 24 Hussars in
seeds 0, 1, and 2, with 894–901 militia HP remaining. Phase 003 measured 27
Elite Huskarls losing to **27** Hussars in all three seeds, with 664 Hussar HP
remaining. The tradeoff rule compared the replacement's count and nominal
damage but failed to check that the fixed opponent gained three units when
both cost-balanced army sizes were recalculated.

R2 now abstains if a transferred winner faces more opponents, or a transferred
loser faces fewer opponents. Inferred provenance lists only direct roots in
the selected validated family. The validator independently checks that count
condition for every inferred R2 root. The held-out rule check now reports zero
counterexamples: stronger-winner has 88 original-engine and 20 corrected-engine
targets; weaker-loser has 189 and 49. Both modes pass their existing thresholds.

The rebuilt full table validates at 68,916 profile pairs and 151,223 displayed
cells, with 66,395 unresolved profile pairs. Phase 003 can be checkpointed and
the adaptive queue resumed from its saved records. No combat calculation or
saved run was modified during this repair.
