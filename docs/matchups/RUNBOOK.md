# Matchup rerun runbook

Step-by-step for re-running unit-vs-unit matchups and (when wanted) updating the
Matchup Advisor's data on the website. Tools: `python -m aoe2x.matchups <command>`
(`aoe2x/matchups/README.md`). Design: [RERUN_SYSTEM_PROPOSAL.md](RERUN_SYSTEM_PROPOSAL.md).

**What visitors see changes in exactly one step:** copying a new DB to
`data/golden/civ_matchups_first_pass.db` and releasing it (step 9 below). Every
step before that only writes outside the repository (`$MATCHUP_RUNS_STORE`, default
`~/.cache/aoe2-matchup-runs`) or into a scratch path. Nothing here commits, pushes,
deploys or uses the network.

Conventions:

- Run from the repo root on a checkout of `staging` (CLAUDE.md git rules).
- `$OLD` = the bundle the published results were simulated with. Today:
  `aoe2x/matchups/bundles/campaign-2026-185872-188329.json.gz` (`201cec0c…`).
- `$PUB` = `data/golden/civ_matchups_first_pass.db` (the published DB).
- `$W` = a work directory outside the repo, e.g. `$HOME/matchup-work/<runId>`.
- Node 24 (`/opt/node24/bin/node` here). Any Node recorded in
  `aoe2x/matchups/engines/frozen-civ-matchups-v3/ENGINE.json` `node.verified` is accepted.
- The 2026 result index must exist: `python -m aoe2x.matchups import-results`
  (needs the research branch; writes `$MATCHUP_RUNS_STORE/baselines/campaign-2026/result-index.jsonl.gz`,
  sha256 `d672f226…`). Or restore it from the records archive (`derived/result-index.jsonl.gz`,
  [RECORDS_TRIAGE.md](RECORDS_TRIAGE.md)).

---

## Scenario 1: a balance patch changes some units

### 1. Make the mechanics bundle from the new reference DB

Regenerate the reference DB for the new game build as usual
([docs/architecture/runbooks.md](../architecture/runbooks.md) §1), **copy it outside the repo**
(the live `data/golden/aoe2_reference_simulation.db` is a simulator input of the site), then:

```bash
python -m aoe2x.matchups export-bundle --reference-db $W/aoe2_reference_simulation-NNNNNN.db \
    --game-build NNNNNN --out $W/bundle-NNNNNN.json.gz
```

Expected: JSON with `variants` (555 for the 2026 roster rule), `profiles`, `civilizations`, `bundleHash`.

### 2. Diff and plan (what changed, what it costs)

```bash
python -m aoe2x.matchups diff-bundles $OLD $W/bundle-NNNNNN.json.gz --config single-civ-example \
    --out $W/plan --run-id patch-NNNNNN
```

`--config` only supplies the battle setup (the 2026 one) and the default result index; with
`--run-id` the command writes `$W/plan/config.json`, a ready run config. Output (`$W/plan/plan.md`):
units changed with the changed mechanics fields, profiles new/gone, and the split of all profile
pairs into **simulate** / **reuse** (measured result) / **keep** (rule-inferred or other-engine
result of two unchanged profiles) / **identity**, then the cost: expected seeds, worker-hours,
hours on 4 workers (and a conservative figure), and contexts by civilization.

Example (synthetic patch: Franks Paladin +1 melee attack, measured on this branch):

```
units changed: 1 ... combat profiles: 373 kept, 1 new, 1 gone
  - Franks|paladin: attack_classes (profile d5d8e97099 -> b76666fcc2)
368 new battles (contexts) must be simulated; 58,244 reuse a measured result,
10,259 keep a stored (inferred or other-engine) result, 45 are identical-unit pairs.
expected seeds: 1,214 ... 3.3 worker-hours = about 0.8 hours on 4 workers (conservative: 5.8 worker-hours, 1.5 h)
```

Rule of thumb: **one changed profile = about 368 contexts ≈ 1,200 seeds ≈ 1–2 h on 4 workers.**
The first figure uses the step-3 measurement (1,490 seeds/h, a sample biased to fast fights); a
real 40-context slice of this patch ran at ≈ 650 seeds/h (mean 16.6 s per seed), so plan with the
conservative figure.
A change applied to every civilization's version of a unit changes many profiles (for example
~30 Arbalester profiles exist): multiply.

Optional: `--priors` also writes `priors.jsonl.gz` (the previous version's outcome of the same
cells) and switches the config to `forecastSource: "priors-file"`, so a changed pair can be
confirmed with one decisive seed. Owner default (Q3) is **no prior** (at least 3 seeds per new context).

### 3. Inventory and dry run

```bash
python -m aoe2x.matchups inventory $W/plan/config.json
python -m aoe2x.matchups run $W/plan/config.json --dry-run
```

Expected: `"contexts": 368, "reused": 0, "scheduled": 368` and a one-line `summary`
("368 battles to simulate (~1,214 seeds, ~3.3 worker-hours, ...)"). The schedule is exactly the
plan's (`selection.contexts`); everything else stays in the baseline.

### 4. Run under the supervisor

Where: any machine with this checkout, Python 3.11+ and Node 24; long runs in `tmux`/`screen`.
More workers = proportionally faster (`--workers N`, one per core).

```bash
python -m aoe2x.matchups supervise $W/plan/config.json --node /opt/node24/bin/node --workers 4
```

- **Status** (any time, another terminal): `python -m aoe2x.matchups status $W/plan/config.json`
  - contexts complete / remaining / blocked, seeds saved, rate, ETA, liveness.
- **Stop:** `touch <records>/STOP` (or Ctrl-C / SIGTERM the supervisor). **Resume:** remove `STOP`,
  run the same `supervise` command again. A killed machine resumes the same way; nothing is re-run.
- **Blocked contexts** (a seed timed out at all four watchdog steps 180→600→1800→3600 s) are listed
  by `status`; they are not retried unless `run --retry-blocked`.
- Records go to `$MATCHUP_RUNS_STORE/<runId>` (`output.records`). Never commit them.

### 5. Export

```bash
python -m aoe2x.matchups export $W/plan/config.json
```

Expected: `"complete": true`, `counts.reviewed` = scheduled contexts (minus blocked), and the
snapshot directory `<records>/export` (`manifest.json`, `results.jsonl.gz`, `reused.jsonl.gz`,
`blocked.jsonl.gz`). Re-running gives byte-identical files.

### 6. Build the new serving DB (scratch path)

```bash
python -m aoe2x.matchups build-db $W/plan/config.json --previous-db $PUB \
    --snapshot <records>/export --out $W/civ_matchups_first_pass.db
```

- `--previous-db` keeps every unit id and evidence id that still exists, so untouched cells are
  byte-identical in the API; blocked contexts keep the previous release's result with flag 4.
- A partial run is refused ("N displayed cell(s) ... have no result"). To publish anyway, add
  `--carry-unsimulated`: the missing cells keep the previous release's result, flagged.
- Costs shown on the site (`units.data.costs`) come from `--costs-db` (default: the live
  `data/golden/aoe2_reference_simulation.db`). If the patch changed costs, pass the new reference
  DB (`--costs-db $W/aoe2_reference_simulation-NNNNNN.db`) or `--costs bundle` (the simulated costs).
- Expected: `bytes` ≈ 19.6 MB for the 2026 roster (refused at ≥ 95 MiB), `counts`.

### 7. Audit and release summary

```bash
python -m aoe2x.matchups audit-db $W/civ_matchups_first_pass.db --config $W/plan/config.json \
    --snapshot <records>/export --previous-db $PUB --api --md $W/release-summary.md --json $W/audit.json
```

Exit 0 = every check passed. `$W/release-summary.md` starts with a plain-language summary
(cells whose winner/army sizes change, contexts re-simulated, cells kept without re-simulation,
size), then the advisor API comparison (responses byte-identical, per-civilization-pair identity,
advisor component version old → new), units, cells by status and by civilization, evidence-type
changes, the re-simulated contexts and the verification table.

What to look for: only the patched units' civilizations appear under "By civilization"; the
re-simulated list equals the plan's schedule; "Verification against inputs: PASSED".

### 8. Owner review

Read `$W/release-summary.md` (and `$W/plan/plan.md`). Decide whether to publish. If not, stop
here: nothing has changed for visitors.

### 9. Put the DB in place and run the site's own checks — **this changes what visitors see**

```bash
cp $W/civ_matchups_first_pass.db data/golden/civ_matchups_first_pass.db
python scripts/migration/prepare_release.py
node scripts/migration/check_release.mjs frontend
node scripts/migration/check_release.mjs backend
python scripts/migration/verify_build.py
python -m pytest tests/test_advisor_first_pass.py tests/test_matchups_release.py tests/test_matchups_tooling.py
node --test tests/advisor_model.test.mjs
git checkout vercel.json
```

Expected: in `apps/web/src/generated/release.json` only `components.advisor.version` changes
(`engine`, `simulator`, `civilizations`, `rankings`, `media` stay the same) plus the DB hash and
`backend_bytes`. If `engine` or `simulator` changed, stop: something else was modified.

First compact-DB release only: the 2026 importer tests read the full 2026 evidence chains that the
compact DB no longer carries (list in `aoe2x/matchups/README.md`, "Serving DB"); retire or repoint
them in the same commit (owner decision).

### 10. Commit on `staging`, verify the preview, promote

```bash
git checkout staging
git add data/golden/civ_matchups_first_pass.db docs/releases/<date>-matchups-<runId>.md
git commit -m "Matchup advisor: <runId> (<N> contexts re-simulated)"
git push origin staging        # builds the protected preview deployment
```

Add `$W/release-summary.md` as the release note (`docs/releases/`). Small run files that are worth
keeping in the repo: `$W/plan/config.json`, `plan.md`, the snapshot `manifest.json` (not the
records). The owner verifies the matchup advisor on the preview; promotion is fast-forward only and
needs the owner's explicit go (CLAUDE.md):

```bash
git checkout main && git merge --ff-only staging && git push origin main
```

Then archive the run's records (outside git):
`python -m aoe2x.matchups archive <records> --config $W/plan/config.json --out $W/<runId>-records.tar.gz`.

---

## Scenario 2: a DLC adds civilizations

Same steps as scenario 1, with these differences.

0. **Site prerequisites first** ([docs/architecture/runbooks.md](../architecture/runbooks.md) §4): the
   new civilizations must exist in the reference DB, `presentation.json` (unit icons), the civilization
   supplement/power units (the advisor catalog reads `civilization_page_analysis(<civ>)` and an emblem
   for every civilization it lists), and the live site's civ roster. The advisor DB alone does not
   add a civilization to the site.
1. `export-bundle` from the new reference DB (step 1). The roster rule picks the new civs' Imperial
   infantry/ranged/cavalry automatically; a new unit line must be in `UNIT_LINES` first.
2. `diff-bundles` (step 2) reports `civilizations added` and `units added`. **Identity and reuse:**
   combat profiles ignore the civilization name, so a new civ's unit whose fully upgraded stats equal
   an existing profile (generic units without a civ bonus) reuses every result of that profile;
   only new profiles need battles, against every profile of every other civilization (~2,200–3,600
   contexts per new civ ≈ 7,100–12,000 seeds ≈ 19–32 worker-hours, conservatively 34–58;
   `plan.md` gives the exact figure). Measured on a synthetic clone of the Franks under a new name: 10 units
   added, 0 new profiles, **15 contexts** to simulate (Franks-internal profile pairs that never met
   across civilizations), 6 new identity pairs, 5,550 new cells.
3. `build-db ... --previous-db $PUB`: existing units keep their ids, new units get new ids, and
   every civilization's API response changes (each gains an opponent). Pass the new reference DB
   with `--costs-db` (the new civilization is not in the live one) or use `--costs bundle`.
4. In the release summary expect `units added`, `cells added` ≈ new units × other units, and the
   new civilization in every row of "By civilization".

---

## Scenario 3: same data, different conditions (analysis only; the website is not touched)

Example: equal resource weights, or a smaller army cap. (The cap is limited to 1–27: the recorded
formations have 27 cells per side. An army cap of 40 needs new scenario formations, i.e. a new
scenario set and a new `engine`/setup identity.)

1. Copy a config and change only the battle rules, with sorted orientation and **no** baseline:

   ```bash
   cp aoe2x/matchups/configs/units-vs-civs-example.json $W/config.json
   # edit: "runId": "weights-equal-2027-01", "battle": {..., "resourceWeights": {"food": 1, "wood": 1, "gold": 1},
   #       "orientation": {"rule": "sorted-profile-hash"}}; remove selection.baselineResults
   python -m aoe2x.matchups validate-config $W/config.json
   python -m aoe2x.matchups run $W/config.json --dry-run
   ```

   Any battle-rule change changes the setup hash and every context, so nothing is reused (the dry run
   shows `reused: 0`). A full roster is ≈ 68,900 contexts ≈ 227,000 seeds ≈ 12 days on 4 workers; use
   `selection.civilizations` / `selection.units` / `against` to study a slice.

2. Run, status, export: scenario 1 steps 4–5.
3. Analyse: `<records>/export/results.jsonl.gz` has one row per context (outcome, seeds, physical
   context). For a **full-roster** run you can also build a scratch DB and compare it with the
   published one to count flipped matchups:

   ```bash
   python -m aoe2x.matchups build-db $W/config.json --no-index --snapshot <records>/export --out $W/analysis.db
   python -m aoe2x.matchups audit-db $W/analysis.db --config $W/config.json --no-index \
       --snapshot <records>/export --compare $PUB --md $W/conditions-vs-published.md
   ```

   Never copy an analysis DB into `data/golden/`: its results describe different battles than the
   site explains ("Fully upgraded units, army sizes adjusted so both sides cost the same").

---

## Troubleshooting

| Symptom | Meaning / action |
|---|---|
| `run error: ... was built for a different ...` | The inventory under `<records>/inventory` is from another config: re-run `inventory <config>`. |
| exit 75 from `run` | Another runner holds the lock. `status` shows it; `unlock` only clears a dead owner's lock. |
| `build-db error: ... have no result` | The run is incomplete (see `status`), or the snapshot is from another run. |
| `build-db error: ... different setup` | The index/snapshot results were simulated under other battle rules than this config. |
| `build-db error: ... result index ...` | The run used another baseline index than the build; rebuild with the same index. |
| `audit-db` exit 1 | A check failed; the table at the end of the summary names it with an example. |
| release.json `engine`/`simulator` changed | Not caused by the advisor DB; find the other modified input before releasing. |
