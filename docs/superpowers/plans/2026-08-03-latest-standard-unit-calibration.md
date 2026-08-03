# Latest Standard-Unit Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace superseded standard-unit calibration data with the August 2 authoritative corpus, resolve the three highest-priority melee-class failures, then calibrate ranged-versus-ranged families to the same winner and median-HP standard.

**Architecture:** Add explicit replacement-corpus semantics to the Python ingest layer, preserving provenance and excluding the archive's legacy folder. Extend scoring with family-level aggregation so repeats produce one stable modal-winner and median-winner-HP gate. Diagnose and fix combat behavior in the shared JavaScript simulator with narrow, test-first mechanic changes.

**Tech Stack:** Python 3, pytest, JSON/gzip/zipfile calibration pipeline, Node.js ES modules, Node test runner, JavaScript position simulator.

## Global Constraints

- Only valid decoded records from `aoe2_golden_STANDARD_UNITS_2026-08-02.zip` are authoritative.
- `legacy_pending_rerecord` and superseded far-spawn records are excluded.
- Melee-class includes Elite Fire Lancer, with volley behavior isolated from ordinary melee.
- Correct stable modal winner is mandatory; median winner HP target is within 20%, with 20-25% reported only as near-pass.
- Split/tied winner families are unstable and cannot drive deterministic winner corrections.
- No matchup-specific outcome multipliers or unit-pair exceptions.
- No production deployment, production data mutation, push, or merge.

---

### Task 1: Authoritative replacement-corpus import

**Files:**
- Modify: `aoe2x/calibration/ingest.py`
- Modify: `tests/test_calibration_ingest.py`
- Create: `data/calibration/corpora/standard_units_pre_20260802_manifest.json`
- Modify: `data/calibration/manifest.json`
- Modify: `data/calibration/spawns.json`
- Modify: `data/calibration/truth/*.json`

**Interfaces:**
- Produces: `ingest_zip(zip_path: str, *, replace_scope: str | None = None) -> list[str]`
- Produces: manifest top-level `active_corpus` object with archive SHA-256, archive name, imported run count, and exclusion rules.

- [ ] **Step 1: Write a failing isolated-storage test** proving `replace_scope="standard_units"` removes pre-existing scoped fights, imports only `standard_units/decoded/*.meta.json`, ignores `legacy_pending_rerecord`, and records archive provenance.
- [ ] **Step 2: Run `python -m pytest tests/test_calibration_ingest.py -k replacement -vv`** and confirm failure because replacement semantics do not exist.
- [ ] **Step 3: Implement archive-root discovery and replacement selection** without changing additive ingest behavior when `replace_scope` is absent.
- [ ] **Step 4: Run the focused ingest tests** and confirm they pass, then run `python -m pytest tests/test_calibration_ingest.py -q`.
- [ ] **Step 5: Save the pre-replacement manifest audit copy, then import the August 2 archive locally** with replacement semantics, regenerate truth/spawn artifacts through existing extraction commands, and verify zero imported paths originate under `legacy_pending_rerecord`.
- [ ] **Step 6: Commit only ingest code, tests, and authoritative calibration artifacts** with message `calibration: activate August 2 standard-unit corpus`.

### Task 2: Family-level latest-only gate

**Files:**
- Modify: `aoe2x/calibration/score.py`
- Modify: `tests/test_calibration_score.py`
- Modify: `aoe2x/calibration/filters.py`
- Modify: `tests/test_calibration_filters.py`

**Interfaces:**
- Produces: `aggregate_matchup_families(results: list[dict]) -> list[dict]`
- Family row fields: `matchup`, `n_tapes`, `tape_modal_winner`, `tape_winner_counts`, `stable_winner`, `tape_median_winner_hp`, `sim_modal_winner`, `sim_median_winner_hp`, `winner_match`, `hp_error_pct`, `hp_gate`.

- [ ] **Step 1: Write failing score tests** for a stable repeated family, a split/tied family, a single-record provisional family, a wrong-winner family, and exact 20%/25% boundaries.
- [ ] **Step 2: Run `python -m pytest tests/test_calibration_score.py -k family -vv`** and confirm the missing aggregator causes the expected failure.
- [ ] **Step 3: Implement deterministic family aggregation** using unordered matchup identity and medians computed only from runs won by each side's reported winner.
- [ ] **Step 4: Add latest-corpus filtering assertions** so active-corpus boards cannot include manifest entries from another archive hash or excluded source path.
- [ ] **Step 5: Run calibration score/filter tests** and confirm all pass.
- [ ] **Step 6: Commit** with message `calibration: score latest tapes by matchup family`.

### Task 3: Rebaseline and rank melee-class failures

**Files:**
- Create: `data/calibration/analysis/20260803_latest_melee_baseline.json`
- Create: `docs/calibration/LATEST_MELEE_STATUS_2026-08-03.md`

**Interfaces:**
- Consumes: active August 2 manifest and family aggregator.
- Produces: ranked covered-family board and an explicit coverage-gap list.

- [ ] **Step 1: Run simulator seeds for every valid melee-class recording** using imported close-spawn inputs and current committed mechanics.
- [ ] **Step 2: Generate a latest-only family board** and assert all rows share the active archive SHA-256.
- [ ] **Step 3: Rank failures** by stable wrong modal winner, absolute HP error, then tape count; select exactly the first three actionable families.
- [ ] **Step 4: Record first-contact time, active attackers over time, retarget delay, damage cadence, death curve, and survivor HP** for those three families in the analysis JSON.
- [ ] **Step 5: Commit the reproducible baseline and status report** with message `calibration: baseline latest melee families`.

### Task 4: Fix melee priority one

**Files:**
- Modify: `webapp/static/js/battle_simulator/position_sim.js`
- Modify: `tests/js/engine/sim.test.mjs`
- Modify: focused calibration analysis/status artifacts from Task 3.

- [ ] **Step 1: State one root-cause hypothesis from Task 3 evidence** and identify the shared mechanic whose current output falsifies tape behavior.
- [ ] **Step 2: Add one failing Node regression test** reproducing the mechanic-level discrepancy without naming a unit-pair exception.
- [ ] **Step 3: Run `node --test tests/js/engine/sim.test.mjs`** and verify the new assertion fails for the expected reason.
- [ ] **Step 4: Implement the smallest shared-mechanic correction** and rerun the focused Node test.
- [ ] **Step 5: Re-run all latest melee families**; retain the change only if priority one improves and no previously passing stable family flips or leaves the 25% band.
- [ ] **Step 6: Commit** with message `calibration: fix primary melee mechanic`.

### Task 5: Fix melee priorities two and three

**Files:**
- Modify: `webapp/static/js/battle_simulator/position_sim.js`
- Modify: `tests/js/engine/sim.test.mjs`
- Modify: `data/calibration/analysis/20260803_latest_melee_baseline.json`
- Modify: `docs/calibration/LATEST_MELEE_STATUS_2026-08-03.md`

- [ ] **Step 1: Repeat red-green verification for priority two** with a mechanic-level failing test and one narrow correction.
- [ ] **Step 2: Run the full melee board** and reject any correction that creates a stable winner regression.
- [ ] **Step 3: Repeat red-green verification for priority three** unless its tape family is unstable; if unstable, calibrate only a shared distribution mechanic supported by another stable family.
- [ ] **Step 4: Generate the final melee-class board** listing passes, near-passes, failures, unstable families, provisional families, and unrecorded gaps.
- [ ] **Step 5: Run `node --test tests/js/engine/*.test.mjs` and `python -m pytest tests/test_calibration_*.py -q`**.
- [ ] **Step 6: Commit** with message `calibration: resolve latest melee families`.

### Task 6: Ranged-versus-ranged baseline and fixes

**Files:**
- Create: `data/calibration/analysis/20260803_latest_ranged_baseline.json`
- Create: `docs/calibration/LATEST_RANGED_STATUS_2026-08-03.md`
- Modify: `webapp/static/js/battle_simulator/position_sim.js`
- Modify: `tests/js/engine/sim.test.mjs`

- [ ] **Step 1: Select ranged-versus-ranged standard-unit records from only the active August 2 corpus** and generate the family board.
- [ ] **Step 2: Rank the top three ranged failures** with the same winner-first ordering and capture projectile launch/impact, kiting/orbit, retarget, death-curve, and survivor-HP evidence.
- [ ] **Step 3: For each actionable failure, add and verify a failing shared-mechanic Node test before implementation.**
- [ ] **Step 4: Apply one narrow ranged-mechanic correction at a time**, rerunning both ranged and melee boards after each change.
- [ ] **Step 5: Generate the final ranged board** with stable, unstable, provisional, and gap classifications.
- [ ] **Step 6: Commit** with message `calibration: resolve latest ranged families`.

### Task 7: Full verification and handoff

**Files:**
- Modify: `docs/calibration/HANDOFF_2026-08-03.md`

- [ ] **Step 1: Run the complete JavaScript suite** with the repository's established Node test command and record totals.
- [ ] **Step 2: Run the complete Python suite** with `python -m pytest -q` and record totals.
- [ ] **Step 3: Re-run final latest-only melee and ranged boards from clean simulator outputs** and verify archive provenance plus exclusion counts.
- [ ] **Step 4: Audit `git diff` and `git status`** to ensure unrelated user files and earlier mixed-corpus boards are not staged.
- [ ] **Step 5: Write the handoff** with exact family counts, winner accuracy, 20% passes, 20-25% near-passes, remaining failures, unstable families, gaps, commits, and reproduction commands.
- [ ] **Step 6: Commit verification artifacts and handoff** with message `docs: hand off standard-unit calibration`.
