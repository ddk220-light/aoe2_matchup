# Phase-024 common-opponent rule refinement

The original adaptive estimator treated one prospective wrong winner as a
reason to disable a whole unit-family rule. This candidate changes the
selection loop: each completed phase records the counterexamples, proposes a
narrower benchmark/margin/context rule, and reserves prospective fights to
test it. The established V3 fight source, seed policy, and journals are
unchanged. Ranking margins remain predictive features, not observed results.

The phase-024 audit found six families with prospective failures or close
fights called decisive. Five have a narrower candidate with zero errors on
the *screened* historical and prospective cases, but the prospective samples
are still small:

| Family | Revised comparison | Screened historical | Screened prospective |
| --- | --- | ---: | ---: |
| Archer–archer | Hand Cannoneer, margin gap ≥0.20 | 20/20 | 4/4 |
| Archer–light cavalry | Arbalester, gap ≥0.35; exclude repeating-volley units | 54/54 | 3/3 |
| Cavalry archer–knight | Arbalester, gap ≥0.35 | 45/45 | 2/2 |
| Knight–militia | Spanish and Turk Paladins agree, gap ≥0.10 each | 94/94 | 7/7 |
| Light cavalry–militia | Champion and Turk Paladin agree, gap ≥0.10 each | 33/33 | 4/4 |

Archer–gunpowder has a newly observed close fight that defeats its broad
rule; no screened replacement has enough evidence yet. It remains an active
research cohort and receives a distinct set of probes. Chu Ko Nu's repeating
volley caused a historical failure for the broader archer–light cavalry
candidate, which is why that mode is excluded pending its own rule. The
screened ratios are **not** accuracy estimates: candidates were revised using
these same cases. No new rule has earned a skip.

`plan_civ_refinement_loop.py` archives each candidate's hash and the phase
after which it was introduced. Only independently completed *later* phases
count toward promotion. A rule needs at least 20 error-free historical
predictions, 60 later independent prospective predictions across 12 distinct
profiles, no wrong winners or close fights called decisive, and a caught-up
exact V2 replay with no changed result. A new counterexample changes the
rule hash and resets prospective credit. The snapshot records all failures,
source hashes, and future probe keys. In phase 024 it proposes 48 refinement
probes across the six affected families; the remaining 208 phase slots remain
available to the existing rule probes and high-value hard cases. The
end-to-end selector test selected 48 refinement probes, 32 existing rule
probes, and 176 hard cases, with no duplicate pair and no simulated fight.

When a revised rule eventually passes the gate, the selector will preserve
its per-pair winner prediction and benchmark margins in a separate verified
refinement journal, with a rule hash. A future final table must read this
journal as inferred evidence, not as a simulated fight. The live phase-025
plan was already selected under the previous selector; this branch targets
subsequent phases without modifying a frozen combat runtime file.
