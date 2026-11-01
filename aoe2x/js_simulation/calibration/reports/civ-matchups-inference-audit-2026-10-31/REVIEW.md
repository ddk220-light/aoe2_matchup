# Civilization-matchup inference audit (phase 17 snapshot)

## Two-sided rule and next-test scheduling (v4)

The same frozen phase-17 evidence now supports a second, stricter transfer:
one completed direct fight may cover a target where **both** armies have
changed. The root stays a direct corrected-engine result. The replacement
winner must be no weaker and the replacement loser no stronger against both
opposing profiles, with the actual 27-unit cost-balanced army counts and
scenario checked at all four corners. A root must have at least 25% winner HP
in every recorded seed. No inferred intermediate becomes evidence.

Held-out validation requires three measured target pairs and two independent
roots per family, with zero wrong winners and zero close fights called
decisive. Families without that support remain unresolved. The enabled
two-sided families made no wrong or close-as-decisive calls on the saved
phase-17 evidence. Its 119 added decisions use 68 distinct direct roots and
cover 176 displayed cells. Combining this with the earlier narrow-effect
rule yields 6,449 inferred profile pairs, 45 equivalent, 107 close, 4,423
observed, and 57,999 unresolved. The original 4,520 inferred decisions are
unchanged. The full versioned table, evidence ledger, validation files, and
needs-simulation list are in
`calibration/campaigns/civ-matchups-inference-two-sided-audit-2026-11-01/`.
`AUDIT_V4.json` hashes those outputs, and
`new-two-sided-inferences.jsonl.gz` isolates the 119 new decisions.

`test-priority.json` evaluates each unresolved profile pair as a hypothetical
direct test with either side winning. For each outcome, it counts currently
unresolved targets that could pass the validated R1 rule. It counts R2 and R3
targets only on the **conditional** assumption that every winning seed retains
at least 50% and 25% of starting HP respectively. These are prospective gains,
never results or guaranteed savings: a close fight transfers nothing, and
future evidence can conflict. The scheduler's shortlist uses marginal coverage across both
possible winners, limits repeated unit-line pairings, and defers same-line
ranking gaps under five points as possible close fights. The ranking score
affects test order only; it never supplies a winner or substitutes for a
compatible corrected-engine seed set.

The scan evaluated all 57,999 unresolved profile pairs. Its first five
diversified candidates, shown as the two possible decisive-winner gains, are:

| Candidate fight (balanced counts) | Additional profile pairs if either side wins |
| --- | ---: |
| Hindustani Hussar 27 vs Bulgarian Hussar 27 | 16 / 18 |
| Lithuanian Elite Skirmisher 27 vs Briton Light Cavalry 23 | 14 / 14 |
| Bulgarian Elite Skirmisher 27 vs Lithuanian Halberdier 27 | 15 / 13 |
| Cuman Heavy Cavalry Archer 20 vs Bohemian Halberdier 27 | 13 / 14 |
| Goth Hussar 27 vs Jurchen Hussar 27 | 14 / 13 |

The 20-candidate diverse shortlist has 244 marginal prospective transfers
under the decisive, robust-margin assumptions. It is a **priority list**, not
a claim that those 244 fights are already settled or that 20 new fights can
replace the remaining simulation campaign. Most added opportunity is the R2
tradeoff rule and requires at least 50% winner HP; the list should be
recomputed after each phase because new direct results change its value.

This audit branch does not change the running frozen V3 selector or its run
journals. Use the audited rules and priority list in a separately versioned
selection pass after validation on the compatible V2 replay records. Preserve
existing V3 and V2 seeds, counts, orientation, and provenance.

This is an **offline inference experiment**, not a change to the live campaign.
It reads the immutable phase-17 checkpoint `6686ba0e` and its ranking anchors;
no combat simulation or replay was run. `AUDIT.json` lists the SHA-256 of every
input and the two inference-build hashes. `new-inferences.jsonl.gz` contains
the 1,810 new decisions with direct roots, rule versions, and explanations.
`rule-validation.json` and `tradeoff-validation.json` contain the complete
held-out family breakdown.

## Result

| Measure | Frozen phase-17 rule | Narrow audited rule |
| --- | ---: | ---: |
| Observed profile pairs | 4,423 | 4,423 |
| Inferred profile pairs | 4,520 | 6,330 |
| Equivalent profile pairs | 45 | 45 |
| Close/uncertain profile pairs | 107 | 107 |
| Unresolved profile pairs | 59,928 | 58,118 |

The extra 1,810 profile-pair decisions expand to 3,992 civilization/unit cells:
927 use the static directional rule and 883 use the tradeoff rule. All 4,520
previous inferred outcomes remain identical. Every new decision has a complete
corrected-engine direct root; the 1,810 decisions refer to 257 distinct roots.
No old-engine record was promoted to a direct result.

The change recognizes four effects that cannot alter the winner in these
homogeneous, zero-buffer armies: `combat_gold_per_animation_second`,
`gold_per_kill`, and `death_resource_refund_fraction` affect resource totals;
`speed_attack_aura_recipient` requires an allied source with
`speed_attack_aura_group`, which no same-type force here supplies. A recipient
is admitted only when its own profile has no such source. Every other active
effect remains blocked unless the existing rule explicitly supports it.
The 27-unit cost formula, both recalculated army counts, opponent-specific
damage and armor classes, reload, range, speed, collision, and source
orientation remain unchanged.

Held-out validation hides each measured target pair, its aliases, reverse
view, and all seeds. The audited static rule made 1,493 correct predictions
against 706 distinct targets, with zero wrong winners and zero close fights
called decisive. The tradeoff rule had 246 corrected-engine held-out targets
in stronger-winner mode and 199 in weaker-loser mode, with zero wrong in
either. For a **newly admitted effect**, a tradeoff family also needs at least
three corrected-engine held-out targets and two independent roots. This keeps
455 less-tested candidate transfers unresolved. The rule does not chain an
inferred result into another inference.

A broader experiment also ignored `nearby_attack_group`. It produced two
wrong static held-out predictions and five wrong tradeoff predictions,
including knight-versus-knight and spear-versus-knight cases. That field is
not admitted. This is why the narrow result should replace neither physics
nor validation with a blanket “same class wins” rule.

## How rankings can help next

The published ranking score is useful for **choosing a benchmark**, not for
declaring a winner. Of 14,165 decided same-line comparisons against the same
observed opponent, a higher overall ranking score lost where the lower score
won in 676 cases. Even at a 20-point score gap, 53 of 7,648 comparisons
inverted. Most ranking rows also contain older-engine runs, so their scores
cannot be treated as corrected-engine measurements: only 608 of the 3,591
published opponent-breakdown rows contain any corrected-engine run.

Use ranking and opponent-specific benchmark scores to select a strong and a
weak candidate within a mechanics family. A direct result can then transfer
only when the replacement's actual balanced count, damage against that exact
opponent, incoming damage, durability, timing, mobility, geometry, and effects
support the direction. If a known loser is replaced by a stronger unit, the
fight may cross the win boundary and remains unresolved. If both armies
change, the audited two-sided rule applies only in families with independent
corrected-engine held-out support; an inferred intermediate result cannot
serve as a new root.

Three families merit such work. In the phase-17 direct evidence, knights beat
skirmishers in all 67 completed profile pairs, militia-line units beat
skirmishers in all 84, and militia-line units beat spears in all 68. Their
remaining unresolved counts are 1,161, 1,704, and 2,166 respectively.
These are candidate family boundaries, not settled results: the sampled
profiles and forest-pocket pathing can affect the outcome. The weakest saved
knight-versus-skirmisher win retained 49% of starting HP, so this family is
promising for mechanical bounding and targeted validation.

The live V3 runner must continue using its frozen rule. To realize these
savings, create a separately versioned inference/selection phase over saved
seeds, rerun the held-out checks as more fights finish, and validate again on
compatible V2 evidence. Do not alter existing journals, reclassify incomplete
seeds, or silently skip a scheduled fight based only on the ranking score.
