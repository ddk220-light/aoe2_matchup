# Inferred 2026 matchup results from the local PC

All **10,193 selected contexts**, representing **19,647 displayed table cells**, now have at least one completed observation across the original and supplemental journals: **10,552 completed seeds** in total.

## Evidence and sampling status

| Dataset | Contexts with completed results | Completed seeds | Status |
| --- | ---: | ---: | --- |
| Original one-three-ten campaign | 10,191 | 10,550 | Two seed-0 contexts exhausted all watchdog steps |
| Owner-requested alternate seed 1 | 2 additional | 2 | Both completed on the same frozen engine |

The original campaign uses one seed for 10,022 contexts, three seeds for 166, and ten seeds for three. Its reviewed results and snapshot are preserved byte-for-byte. The original `manifest.json` says `complete: true` because its queue is exhausted; its two blocked entries have not been silently converted into reviewed results. The supplemental seed-1 observations are explicitly separate from the fixed-seed campaign's review policy.

No recovery engine was used. No simulation code, website database, or production deployment is changed by this publication.

## Files for later analysis

- `manifest.json`, `results.jsonl.gz`, `blocked.jsonl.gz`, `reused.jsonl.gz`: original verified export. The compact seed-array order is `manifest.json.seedFields`.
- `evidence/runs.jsonl.gz`: all 10,550 full original seed records, compressed without changing the journal bytes. Includes both starting and remaining HP totals, survivor counts, army counts, outcome/winner, seed, timestamps, wall duration, ticks/simulated duration, engine/Node identity, context/profile/scenario identities, and final-state/event-log hashes.
- `evidence/jobs.jsonl.gz`: all context inputs and metadata. Join original or supplemental `matchupId` to job `id` for civilization/unit `teamKeys`, costs, orientation, and displayed-cell counts. Owner 2 is `teamKeys[0]` (unit); owner 3 is `teamKeys[1]` (opponent).
- `evidence/attempts.jsonl.gz`: failed attempts, including both seed-0 timeout histories. These are diagnostic evidence, never completed outcomes. Historical local progress paths are provenance references; full progress logs remain on the PC.
- `evidence/sessions.jsonl.gz`: original pause/resume and recovery session history.
- `alternate-seed-1/runs.jsonl`: two additional full seed records. Append these to the original journal for observation-level analysis, keeping the `purpose: alternate_seed_probe` label. They carry `sourceRunId`/`sourceRunHash` rather than asserting membership in the original campaign journal. `outcome` is relative to owner 2; raw `engineOutcome` describes engine termination.
- `alternate-seed-1/results.jsonl`, `contexts.json`, `jobs.jsonl`, `manifest.json`: raw results and exact supplemental inputs/provenance. Its README and verification receipts detail the two outcomes.
- `verification/`: original export/field/hash validation, runtime receipt, and 60/60 identical Windows replay checks.
- `publication-manifest.json`: package file hashes, combined coverage and source snapshot identity. The original campaign manifest continues to cover only its original export.

Both supplemental losing armies finished with zero HP and zero survivors:

| Matchup (seed 1) | Winner | Winner survivors | Winner HP remaining / starting | Simulated seconds |
| --- | --- | ---: | ---: | ---: |
| Lithuanian Elite Skirmishers vs Jurchen Hussars | Jurchen Hussars | 22 | 2,011 / 2,185 | 31.017 |
| Saxon Elite Skirmishers vs Polish Paladins | Polish Paladins | 17 | 2,191 / 2,660 | 29.800 |

## Runtime and reproducibility

Source checkout: `matchup-runs` commit `71ad0fc4993a36dc198823bcabeb51bd408e6c3a`; run config: `aoe2x/matchups/configs/inferred-2026-resim-pc.json`. Engine: `frozen-civ-matchups-v3`; Node: v24.22.1. The original frozen mechanics, scenarios, army counts and owner orientation were used for both seed-1 tests.

The original batch calibrated to 18 parallel workers at BelowNormal priority, averaging 80.52% total CPU under full load across 153 samples. A later affinity limit used 19 of 24 logical processors. Elapsed time including calibration and retry tail was 3.088 hours, adding 10,156 seeds to 394 existing valid seeds (3,288.7 new seeds/hour). One supervisor restart preserved completed records; the pilot journal prefix remained byte-identical. Both supplemental seeds completed in approximately three seconds each using two parallel workers. Temporary keep-awake ended with the processes; power settings were unchanged.

Original export snapshot SHA-256: `673d7f8a27bc5a1bc3fa38db70d293602cf3dd28f19766778a670ae1d0edbeca`.
