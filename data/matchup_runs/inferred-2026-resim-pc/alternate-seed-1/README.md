# Alternate-seed results

Owner requested testing another seed for the two seed-0 timeouts. Both seed-1 battles finished using the same frozen-civ-matchups-v3 engine, Node v24.22.1, original contexts, army counts and scenarios. Two workers ran in parallel.

| Context | Seed | Winner | Winner survivors | Winner remaining / starting HP | Simulated seconds | Wall seconds |
|---|---:|---|---:|---:|---:|---:|
| Lithuanians Elite Skirmisher vs Jurchens Hussar | 1 | Jurchens Hussar | 22 | 2011 / 2185 | 31.017 | 2.981 |
| Saxons Elite Skirmisher vs Poles Paladin | 1 | Poles Paladin | 17 | 2191 / 2660 | 29.8 | 2.688 |

Both losing armies have zero HP and zero survivors. `runs.jsonl` preserves the normalized per-seed analysis records; `results.jsonl` preserves raw engine results. `contexts.json`, `jobs.jsonl`, and `manifest.json` preserve inputs and engine provenance. `coverage-verification.json` verifies the combined coverage.

Together with the parent runs.jsonl, there are now 10,552 completed seeds spanning all 10,193 contexts. The original campaign export and seed-0 timeout evidence remain unchanged. These are explicitly labelled supplemental seed-1 observations; they do not silently replace seed 0 in the original one-three-ten review policy. No recovery engine, website database update, or publication was performed.
