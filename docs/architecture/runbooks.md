# Runbooks — when X changes, update Y

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This document is the consolidated checklist set for every recurring maintenance event in this
repo. Each section is a self-sufficient runbook: exact commands (verified against each script's
argparse), the files and databases touched, build-number touchpoints, and a verification step.
For the methodology behind the matchup baseline and the patch pipeline, see
[`docs/matchup-baseline.md`](../matchup-baseline.md) and [`docs/patch-workflow.md`](../patch-workflow.md).
Sibling architecture docs: [`data-pipeline.md`](data-pipeline.md), [`simulation-engines.md`](simulation-engines.md),
[`derived-data.md`](derived-data.md), [`webapp.md`](webapp.md), [`operations.md`](operations.md).

Conventions for every runbook below:

- All commands run from the repo root, on `staging` (`git checkout staging && git pull` first).
- "CPython" means a regular Python with `genieutils-py` installed (the conda `python` on this
  machine); "PyPy" means `pypy3` — the matchup sim runners hard-exit if not run under PyPy.
- The working matchup DB lives **outside the repo** (e.g. `D:/AI/matchup_db.db`,
  `D:/AI/matchup_baseline_177723.db`). A small `webapp/matchup_db.db` is tracked in git, but the
  patch and baseline pipelines should be pointed at the external copy via `--matchup-db`/`--db`.

---

## 1. A new game patch lands

`webapp/patch_pipeline.py` automates the middle of this runbook (steps 4 below); the head and
tail are manual. Deep detail: [`docs/patch-workflow.md`](../patch-workflow.md).

1. **Get the `.dat`.** Copy `empires2_x2_p1.dat` from the AoE2:DE install into `extraction/`.
   The path is hardcoded in `extraction/run.py` (`main()` expects `extraction/empires2_x2_p1.dat`).
2. **Write the notes file.** Save the relevant patch notes as markdown, e.g. `notes_<build>.md`
   (repo root, untracked). The pipeline stores it verbatim as the patch page summary.
3. **If the patch adds or changes units/civs**, re-validate availability *before* running the
   pipeline: `_AVAILABILITY_OVERRIDES` in `analysis/config_units.py` (the anti-phantom-unit
   allowlists) and `CIV_MISSING_UNITS` in `webapp/unit_lines.py`, both against SiegeEngineers
   `data/data.json`. For a pure balance patch, skip this.
4. **Run the pipeline** (CPython with `genieutils-py`; `pypy3` must be resolvable or passed):

   ```
   python -m webapp.patch_pipeline --build 178000 --release-date 2026-07-01 \
       --source-url https://www.ageofempires.com/news/...update-178000/ \
       --summary-file notes_178000.md --matchup-db D:/AI/matchup_db.db
   ```

   Optional flags: `--baseline-build` (defaults to the current build in `webapp/patches.db`)
   and `--pypy` (defaults to `pypy3` on PATH). It runs, in order:

   1. Archives `extraction/extracted_data/` → `extraction/extracted_data_prev/` and
      `webapp/aoe2_reference.db` → `webapp/aoe2_reference_prev.db` (both untracked "before" snapshots).
   2. `python -m extraction.run` → `python -m analysis.generate_reference` →
      `python -m analysis.generate_main_db` → `analysis/patches/patch_mayan_archer_cost.py`
      (the surgical ref patch; idempotent).
   3. Diffs `ref_units` before/after → stat deltas + `webapp/changed_units_<build>.json`.
   4. Snapshots before-outcomes from the matchup DB for the changed slugs.
   5. `pypy3 -m webapp.run_matchup_battles --force --changed-units webapp/changed_units_<build>.json --db <matchup-db>`
      — the **incremental** re-sim (only matchups touching a changed slug).
   6. Diffs matchup outcomes → `patch_matchup_changes`.
   7. `carry_forward_battle_scores` (copies the prior build's `battle_scores` rows — including
      naval/siege rows the land derive does not own — to the new build), then
      `python -m webapp.derive_unit_rankings --matchup-db <db> --build <build>` (→ `webapp/derived_data.db`),
      `python -m webapp.derive_pool_scores --matchup-db <db> --out webapp/pool_scores.db --build <build>`,
      inserts the `patches` row, flips `is_current` to the new build, then
      `best_units.save_civ_power_units('<build>')` (→ `webapp/civ_power_units/<build>.json`).
      The order matters: `save_civ_power_units` reads the *current* build's pool/battle scores.
   8. Diffs rankings → `patch_unit_ranking`; writes all patch records into `webapp/patches.db`.

5. **Decide: incremental vs full re-sim.** The pipeline's step 5 is incremental. If the patch
   notes mention engine-relevant mechanics (or you want a fresh baseline-of-record), do a full
   rebuild instead and preserve it under the build number:

   ```
   pypy3 -m webapp.rebuild_matchup_baseline --out D:/AI/matchup_baseline_<build>.db --workers 12
   ```

   (~4.5 h; flags verified: `--out`, `--workers`, `--dry-run`, `--sample N`.) Then re-run the
   three derive commands from step 4.7 pointed at the new baseline DB. See
   [`docs/matchup-baseline.md`](../matchup-baseline.md) for the unattended runner/watchdog setup.
6. **Manual follow-ups the pipeline does NOT do:**
   - `python -m webapp.top_units` if any civ's top tier per line could have changed (regenerates
     the committed `webapp/civ_top_units.json`).
   - `python -m webapp.derive_siege_scores --build <build>` only if siege/anti-building stats
     changed (otherwise the carry-forward keeps the prior rows; flags: `--build`, `--derived-db`).
   - Regenerate the golden baseline if `pytest tests/test_simulations.py` fails on golden keys —
     a stat change legitimately alters `get_matchup_sims` output:
     `python .golden/capture_baseline.py`, then commit `.golden/baseline.json`.
7. **Verify.** `pytest`; spot-check availability (`/api/top-unit/Koreans/knight` → Cavalier);
   `PORT=5002 python webapp/app.py` and smoke-test `/patches`, `/matchup-advisor`, rankings.
8. **Commit on `staging` and promote.** Commit set: `webapp/aoe2_reference.db`,
   `webapp/aoe2_units.db`, `webapp/derived_data.db`, `webapp/pool_scores.db`,
   `webapp/patches.db`, `webapp/civ_power_units/<build>.json`, plus `webapp/civ_top_units.json`
   and `.golden/baseline.json` if regenerated. Verify on the staging URL, then
   `git checkout main && git merge --ff-only staging && git push origin main && git checkout staging`.

**Build-number touchpoints** (everything is build-versioned; the UI reads
`patches_db.get_current_build()`):

| Artifact | Where the build number lives |
|---|---|
| `webapp/patches.db` | `patches` row + `is_current` flag (set by the pipeline) |
| `webapp/derived_data.db` | `battle_scores.build_number` column |
| `webapp/pool_scores.db` | build column written by `derive_pool_scores --build` |
| `webapp/civ_power_units/<build>.json` | filename |
| `webapp/changed_units_<build>.json` | filename (input for incremental re-sims) |
| `D:/AI/matchup_baseline_<build>.db` | filename (local baseline-of-record, not committed) |

---

## 2. Simulation logic / combat mechanic change

Three engines exist; decide which ones the change applies to (details:
[`simulation-engines.md`](simulation-engines.md)):

| Engine | File | Consumed by |
|---|---|---|
| Abstract tick sim | `webapp/simulation.py` | `best_units.get_matchup_sims` (default `sim_func`) → the live `/api/matchup-sims` advisor endpoint; `webapp/compute_battle_scores.py`; the golden baseline |
| Position-based sim | `webapp/simulation_real.py` | `webapp/run_matchup_battles.py`, `webapp/rebuild_matchup_baseline.py`, `webapp/patch_resim.py`, `webapp/verify_flips.py` → matchup DB → all derive scripts |
| Frontend canvas sim | `webapp/static/js/simulate.js` (`BattleUnit`, line ~345) | the Battle Sim page at `/` only (legacy `/simulate` 301-redirects there); fetches stats from `/api/ref/combat-unit/<civ>/<slug>` |

*Condensed from [simulation-engines.md](simulation-engines.md) §4 — update both together.*

Steps:

1. Apply the change to the relevant engine(s). A mechanic that affects real battles usually
   needs all three (the JS sim mirrors but does not share code with the backend).
2. **Know the `sim_version` consequence.** `webapp/sim_version.py` hashes exactly two files:
   `webapp/simulation_real.py` and `analysis/config_combat.py`. Every `matchup_db` row stores
   the hash; on the next `run_matchup_battles` run, rows with a stale hash are re-simulated
   automatically (no `--force` needed). Changing **`simulation.py` does not bump `sim_version`**
   — nothing in the matchup DB goes stale from it; only the live advisor sims and golden change.
3. Run the tests: `pytest tests/test_position_sim_abilities.py tests/test_simulations.py tests/test_sim_version.py`.
4. If `simulation.py` behavior changed intentionally: `python .golden/capture_baseline.py`,
   re-run `pytest tests/test_simulations.py`, commit `.golden/baseline.json`.
5. If `simulation_real.py` changed: full baseline rebuild (runbook 1, step 5) — do **not** mix
   engine versions in one matchup DB ("patchwork" gotcha in `docs/patch-workflow.md`) — then
   re-derive rankings, pool scores, and civ power units at the **current** build number.
6. The legacy round-robin/benchmark JSON chain is gone: `battle_scores.json` and its
   `app.py` loader were deleted — `/api/ref/unit-line` scores come solely from
   `derived_data.db` (plus the empty reference-DB fallback). Do not run
   `compute_battle_scores.py`.

---

## 3. New combat stat column / new special ability

This is the verified, current chain (the CLAUDE.md "rule 5" version of this list predates the
`combat_unit_loader`/`constants.js` refactors):

1. **`analysis/config_combat.py`** — add the property to `COMBAT_PROPERTIES` (standard units),
   `UNIQUE_COMBAT_PROPERTIES` (unique-unit abilities), or `CIV_COMBAT_PROPERTIES`
   (civ-conditional overrides). Later dicts win; the dat-extracted value is the base layer.
2. **`analysis/generate_reference.py`** — add the column to the `ref_units` `CREATE TABLE`
   (around line 219) and register it in the `special_props` name/description list (around
   line 968) so the audit trail records it.
3. **`analysis/generate_main_db.py`** — add the column to the `unit_stats` `CREATE TABLE`
   (line ~379) and to its own `build_combat_dict_from_ref` (line ~78).
4. **`webapp/combat_unit_loader.py`** `build_combat_dict_from_ref` — the canonical
   ref-row → combat-dict mapping shared by `webapp/app.py`, `webapp/best_units.py`, and
   `webapp/run_matchup_battles.py`. The Flask endpoint itself needs no change: `/api/ref/combat-unit`
   does `SELECT * FROM ref_units` and delegates entirely to this function.
5. **`webapp/simulation.py`** `prepare_combat_unit` (line ~87) **and**
   **`webapp/simulation_real.py`** `prepare_combat_unit` (line ~189) plus the stat-field name
   lists near lines 331–354 — both engines parse the dict independently.
6. **`webapp/static/js/simulate.js`** `BattleUnit` — only if the frontend sim must model it.
7. Rebuild and re-sim: `python -m analysis.generate_reference`, `python -m analysis.generate_main_db`.
   Because `config_combat.py` is hashed into `sim_version`, **every** matchup row goes stale —
   plan a full re-sim (runbook 2, step 5), then re-derive and regenerate golden.

---

## 4. New unit or new civ (DLC)

1. **`extraction/extract_constants.py`** — `CIV_NAMES` is a positional list where the index is
   the dat civ ID (`None` for unused slots). A new civ must be added at its exact dat slot.
2. **`analysis/config_units.py`** — add the unit to the age dicts (`FEUDAL_UNITS`,
   `CASTLE_UNITS`, `IMPERIAL_UNITS`, `UNIQUE_UNITS`) and re-validate `_AVAILABILITY_OVERRIDES`
   against SiegeEngineers (a module-level warning fires if an override slug no longer exists).
3. **`analysis/config_combat.py`** — abilities the dat cannot express (runbook 3).
4. **`webapp/unit_lines.py`** — register the unit in `UNIT_LINES` (line membership,
   `unique_units` per civ) and add any tech-tree gaps to `CIV_MISSING_UNITS`. This module is the
   single Python source for line definitions (imported by `app.py`, all derive scripts, and the
   sim runners).
5. **`webapp/static/js/constants.js`** — `ENABLED_CIVS` (new civ), `NAME_TO_ICON` (new units),
   `UNIQUE_BUILDING` (only for unique units not trained at the Castle).
6. **Icons/art** — runbook 5.
7. Rebuild everything (runbook 1 steps 4–8: extraction → ref → main → full baseline re-sim,
   since a new roster invalidates the matchup universe → derive at the current/new build), then
   `python -m webapp.top_units` to refresh `webapp/civ_top_units.json`.
8. SEO pages need **no manual step**: `/sitemap.xml` and the `/vs/...` landing pages are derived
   live from `ref_units` unique-unit rows (`webapp/app.py` `_matchup_seed_pairs`).

Note: the pipeline civ list (`ORIGINAL_13_CIVS` in `analysis/config_constants.py`) is now
derived from `extraction.extract_constants.CIV_NAMES`, so step 1 covers it automatically —
no separate `config_constants.py` edit. Webapp civ validation reads the reference DB via
`_valid_civs()`; the old dead copy in `webapp/app.py` was deleted.

---

## 5. New unit icon / art

Icon files are flat PNGs in `webapp/static/img/units/` (213 files), named by display name with
underscores (`Long_Swordsman.png`). The **single registry** is `NAME_TO_ICON` in
`webapp/static/js/constants.js` (218 entries, display name → file basename); no template carries
its own copy. `getIconUrl()` in the same file builds the URL, and every page's JS
(`rankings.js`, `simulate.js`, `civ-detail.js`, `matchup.js`, `matchup_advisor.js`) consumes it.

1. Find the icon ID from the dat via genieutils (conda python):
   `dat.civs[0].units[UNIT_ID].icon_id`.
2. Fetch `https://aoe2techtree.net/img/Unit/{icon_id}.png` (fallback: Fandom wiki API).
3. Save as `webapp/static/img/units/<Display_Name>.png` (underscores for spaces).
4. Add the entry to `NAME_TO_ICON` in `webapp/static/js/constants.js`. The key is the
   **display name** as it appears in `ref_units.unit_name` (e.g. `"Elite Plumed Archer"`).
5. Verify on `/simulate` (unit picker) and a civ detail page — a missing entry renders no image
   (`getIconUrl` returns `null`).

Generated portrait art (FLUX.2 hybrid renders) is a separate asset family under
`graphics/art/flux2_hybrid/` — see [`docs/flux2-unit-art-workflow.md`](../flux2-unit-art-workflow.md).
It does not feed `NAME_TO_ICON`.

---

## 6. Frontend constant change (enabled civs, unit lines, display mappings)

The old "keep four templates in sync" rule is obsolete. Today's single sources:

| Constant | Single source | Consumers |
|---|---|---|
| `ENABLED_CIVS` (53) | `webapp/static/js/constants.js` | civ dropdowns in `simulate.js`, `rankings.js` |
| `NAME_TO_ICON` (218) | `webapp/static/js/constants.js` | all page JS via `getIconUrl()` |
| `UNIQUE_BUILDING` (13) | `webapp/static/js/constants.js` | `simulate.js`, `civ-detail.js` |
| `UNIT_LINES` / `CIV_MISSING_UNITS` / `NAVAL_UNIT_LINES` | `webapp/unit_lines.py` | `app.py`, `compute_battle_scores.py`, `derive_*`, `run_matchup_battles.py`, `top_units.py`, `best_units.py` |

The one cross-language sync that remains: `ENABLED_CIVS` (JS) must match the civs present in
`webapp/aoe2_reference.db` (which come from `extraction/extract_constants.py` `CIV_NAMES`).
There is no automated check — after changing either side, load `/simulate` and confirm the civ
list, and run `pytest tests/test_footer.py` plus a quick `/api/ref/civ/<NewCiv>` call.

---

## 7. Hardcoded combat-property fix for a single unit

Two paths, depending on blast radius. Background: a **full pipeline regen rewrites the
combat-property columns on every row** of `aoe2_reference.db`/`aoe2_units.db`, so an
"innocent" rebuild can ship unintended drift on units you never touched.

**Path A — config fix + full rebuild** (fine when you intend a clean rebuild anyway):

1. Edit `analysis/config_combat.py` (or `config_units.py` for stat overrides).
2. `python -m analysis.generate_reference && python -m analysis.generate_main_db`
   (then re-apply `python -m analysis.patches.patch_mayan_archer_cost`).
3. **Diff the result** before committing — only the intended rows should change. The
   `ref_diff.diff()` helper used by the patch pipeline (`webapp/ref_diff.py`) is the tool.
4. Because `config_combat.py` is in the `sim_version` hash, all matchup rows are now stale.
   Either accept a full re-sim, or scope it:
   `pypy3 -m webapp.run_matchup_battles --force --changed-units <slugs.json> --db <matchup_db>`
   — knowing this leaves the DB a mixed-`sim_version` patchwork (acceptable for a cosmetic hash
   bump where unchanged units genuinely sim identically).
5. Re-derive (runbook 1, step 4.7 commands) and regenerate golden if outputs moved.

**Path B — surgical DB patch** (when the pipeline itself can't produce the right value, or you
must not touch other rows): write an idempotent script in `analysis/patches/` following
`analysis/patches/patch_mayan_archer_cost.py` (recompute from base values so re-running is a
no-op; support a `--dry` preview). Patch `webapp/aoe2_reference.db`, then re-run
`python -m analysis.generate_main_db` so `aoe2_units.db` matches, and register the script in
`webapp/patch_pipeline.py` step 2 so future full regens re-apply it. Then re-sim only the
affected slugs as in Path A step 4.

For before/after impact analysis of either path, `pypy3 -m webapp.patch_resim --my-units
<units.json> --out <means.db> [--ref <ref.db>] [--seeds 15] [--workers N]` runs the changed
units against the full pool with multi-seed means, and `webapp/verify_flips.py` adversarially
re-checks candidate flips (both PyPy-only).

---

## Update triggers

| If this changes | Update these sections |
|---|---|
| `webapp/patch_pipeline.py` steps or flags | §1 (and `docs/patch-workflow.md`) |
| `webapp/sim_version.py` `DEFAULT_FILES` | §2, §3, §7 |
| `webapp/combat_unit_loader.py` or either `prepare_combat_unit` | §3 |
| `webapp/static/js/constants.js` structure (registries move/split) | §5, §6 |
| `webapp/unit_lines.py` location or shape | §4, §6 |
| Derive scripts gain/lose argparse flags | §1, §2 (re-verify every command) |
| `.golden/capture_baseline.py` coverage or seed | §1, §2 |
| `analysis/patches/` gains a new surgical patch | §1 step 4.2, §7 (and `patch_pipeline.py` itself) |
| Matchup DB schema or baseline workflow | §1, §7 (and `docs/matchup-baseline.md`) |
