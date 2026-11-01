# Prospective common-opponent review after phase 023

The live V3 phase-023 checkpoint completed 256 fights, 831 valid seeds, zero missing seeds, and an exact replay. Its inference table has 53,888 unresolved profile pairs. The adaptive selector ran actual fights before accepting any common-opponent guess. It has accepted **zero** guesses so far.

Sources: V3 campaign checkpoint `71d2f207`, `adaptive/phases/023-review.json`, and the phase-023 estimate archive whose manifest SHA-256 is `19b7737d2cbcde5fd9ecfab3e0bb85cbfa01c83e561fda41e477e651f86c396a`. The frozen common-opponent rule manifest SHA-256 is `d24f516e50e8a80253a6d97e060abbe343176b010d1fe36a9072867d42c150de`.

The frozen phase-019 rule pack has now received 117 eligible, independent prospective predictions through phases 020–023. Five families produced a wrong winner or called a mixed-seed fight decisive, so the selector disabled them and returned every unresolved candidate in those families to the simulation queue:

| Unit-line pair | Fresh predictions | Correct | Wrong, including close called decisive | Lesson |
|---|---:|---:|---:|---|
| Archer–archer | 9 | 3 | 6, including 5 close | Hand Cannoneer as the sole common opponent does not resolve close archer mirrors. |
| Archer–light cavalry | 8 | 5 | 3, including 1 close | Better results against Arbalester and Cavalry Archer did not guarantee survival against Hussar mobility. |
| Cavalry archer–knight | 8 | 5 | 3 | War Wagon–Konnik and War Wagon–Paladin counterexamples crossed the head-to-head boundary. |
| Knight–militia | 10 | 9 | 1 | Paladin and Champion benchmarks are insufficient across the family. |
| Light cavalry–militia | 8 | 6 | 2 | Champion advantages against Paladin did not transfer to Hussars. |

The remaining four families have 74 correct prospective predictions and no errors: cavalry archer–light cavalry 16/16, knight–light cavalry 16/16, knight–skirmisher 25/25, and militia–skirmisher 17/17. None has met the 60-pair and 12-distinct-profile promotion gate. Phase 024 therefore selected 32 further validation fights and 224 hard cases, with zero skipped predictions.

Raising the archer-mirror Hand Cannoneer margin from 0.10 to 0.15 would have removed the six observed failures, but it would retain only **one** prediction among ten phase-022 archer-mirror fights. Similar higher gaps leave no fresh predictions in the tested archer–light cavalry, cavalry archer–knight and light cavalry–militia cases. That is insufficient evidence to promote a narrower rule. A future rule version should choose common opponents that resemble the proposed head-to-head target and explicitly check range, reload, mobility, bonus classes and army counts. It must then collect fresh fights after the new rule is frozen; it cannot reuse these phase-022 failures as independent validation.

These ranking fingerprints are predictive features from the original engine, never current-engine observations. The five disabled rules have not contributed any inferred winner to the live result table. This review ran no simulations and changed no frozen physics or seed journal.
