# Civilization matchup inference: phase one

This is the complete inference-only table for the 555 finalized land-unit variants
across 56 civilizations. It uses the ranking campaign's 27-unit cost-balanced
army policy. The builder read saved records and static mechanics; it did not run
or replay any battles.

## Coverage

| Conclusion | Distinct profile pairs | Displayed cross-civ unit pairs |
|---|---:|---:|
| Corrected-engine observed winner | 182 | 2,254 |
| Directionally inferred winner | 319 | 1,317 |
| Equivalent mechanics, no intrinsic winner | 45 | 820 |
| Unresolved; requires a future test or rule validation | 68,370 | 146,832 |
| **Total** | **68,916** | **151,223** |

The table also records a tentative winner for 1,995 unresolved profile pairs
(17,935 displayed cells). These are **candidates**, not completed results. The
remaining unresolved rows have reasons such as absent compatible anchors, a
possible win boundary, an unsupported special effect, or an incomplete source
seed set. Reason counts overlap because one pair may have several blockers.

The underlying ranking bundle mixes original and corrected engine records. Its
7,600 selected and 77 preserved extra records were all inspected. Among 2,398
ranking source groups, 182 have unanimous completed corrected-engine evidence;
one has a completed corrected ten-seed set with varying outcomes, 156 have
incomplete corrected evidence, and 2,059 have none. The completed close case is
a same-unit mirror, so there are no directly observed close **cross-civilization**
profile pairs in this first table. Prior-engine results appear as prediction
evidence only; they are not counted as measured corrected-engine winners.

The narrow static-direction rule predicts 13 saved outcomes correctly across
eight distinct held-out target pairs, with no wrong winner or close fight called
decisive. A second rule transfers robust wins to related units when the replacement
remains within explicit limits for count, damage against that opponent, durability,
range, speed and first attack delay. It also transfers a robust win against a unit
to a sufficiently weaker replacement of the loser. The stronger-winner rule
matched 99 original-engine and seven corrected-engine held-out target pairs; the
weaker-loser rule matched 203 original-engine and six corrected-engine targets.
Neither had a wrong winner within those selected checks. Only **corrected-engine
fights serve as roots** for the 319 inferred outcomes. Original-engine records
help validate the general rule and flag contradictions; they do not become direct
current-engine results. The small corrected sample and absent coverage for many
special mechanics are real limits on these inferences.

Examples beyond Britons–Aztecs include a weaker Arbalester still losing to the
Aztec Elite Eagle Warrior, Light Cavalry variants losing to specific recorded
Halberdiers, and a stronger Heavy Cavalry Archer preserving a win against the
Viking Mounted Crossbowman. Each resolved row identifies its root matchup and
the rule used.

## Britons versus Aztecs

The Chinese Arbalester ranking fight is the corrected-engine anchor. Aztec
Pikemen lose to it, while Aztec Elite Eagles and Champions win. Briton Arbalesters
and Elite Longbowmen trade range, firing speed, accuracy, damage and sometimes
count against that benchmark. Both Pikeman cells now carry an **inferred Briton
win** through the validated robust-win rule. Eagle and Champion cells remain
possible win-boundary questions. See [review.md](review.md)
for the six rows.

## Files and reproduction

`civ-matchups.jsonl.gz` contains all displayed pairs; each row names the two
civilizations and units, outcome, candidate, evidence type, source or root IDs,
context, and explanation. `profile-matchups.jsonl.gz` holds one decision per
distinct mechanics pair. `variant-profiles.json` maps every unit variant to its
exact mechanics hash. `evidence-ledger.jsonl.gz` preserves run provenance.
`needs-sim.jsonl.gz` has one unresolved entry per distinct profile pair;
`requirements.jsonl.gz` groups rule-validation dependencies where possible.
`summary.json`, `rule-validation.json` and `tradeoff-validation.json` contain
coverage and held-out checks.
The final `manifest.json` freezes input and output hashes.

Run the static builder and validator from `aoe2x/js_simulation`:

```sh
node node/build-civ-matchup-inference.mjs --phase infer-only
python tools/validate_civ_matchups_phase_one.py
```

The validator checks input/output checksums, all expected civ/unit combinations,
pair alias expansion, winner direction, observed-run provenance, inferred roots,
unresolved requirements, and the Britons–Aztecs review. A second build produced
the same manifest hash. The current hash is
`5274d7adbc6c425f337c2cc287f7a162a798a04ce54b7358258e8f1be1d40a5e`.
