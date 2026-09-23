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

**Scoped exception:** the civilization-page-only reference release in §8 uses a
main-based feature worktree and does not run the full patch/DLC pipeline below.
Production actions always require the owner's specific approval.

- All commands run from the repo root, on `staging` (`git checkout staging && git pull` first).
- "CPython" means a regular Python with `genieutils-py` installed (the conda `python` on this
  machine); "PyPy" means `pypy3` — the matchup sim runners hard-exit if not run under PyPy.
- The working matchup DB lives **outside the repo** (e.g. `D:/AI/matchup_db.db`,
  `D:/AI/matchup_baseline_177723.db`). A small `apps/website/matchup_db.db` is tracked in git, but the
  patch and baseline pipelines should be pointed at the external copy via `--matchup-db`/`--db`.
- `derive_unit_rankings.py` / `derive_pool_scores.py` now **require** `--matchup-db` and
  pre-flight the source DB (`matchup_db.preflight_derive_guard`): <40 distinct `my_civ`
  values aborts (anti-Armenians-stub guard; override `--allow-small-db`), and any rows at a
  non-current `sim_version` abort unless `--allow-stale` (legitimate after scoped
  `--changed-units` re-sims — `patch_pipeline` passes it automatically).

---

## 1. A new game patch lands

`aoe2x/batch/patch_pipeline.py` automates the middle of this runbook (steps 4 below); the head and
tail are manual. Deep detail: [`docs/patch-workflow.md`](../patch-workflow.md).

1. **Get the `.dat`.** Copy `empires2_x2_p1.dat` from the AoE2:DE install into `aoe2x/extract/`.
   The path is hardcoded in `extraction/run.py` (`main()` expects `data/inputs/empires2_x2_p1.dat`).
2. **Write the notes file.** Save the relevant patch notes as markdown, e.g. `notes_<build>.md`
   (repo root, untracked). The pipeline stores it verbatim as the patch page summary.
3. **If the patch adds or changes units/civs**, re-validate availability *before* running the
   pipeline: `_AVAILABILITY_OVERRIDES` in `aoe2x/dbgen/config_units.py` (the anti-phantom-unit
   allowlists) and `CIV_MISSING_UNITS` in `aoe2x/sim/unit_lines.py`, both against SiegeEngineers
   `data/data.json`. For a pure balance patch, skip this.
4. **Run the pipeline** (CPython with `genieutils-py`; `pypy3` must be resolvable or passed):

   ```
   python -m aoe2x.batch.patch_pipeline --build 178000 --release-date 2026-07-01 \
       --source-url https://www.ageofempires.com/news/...update-178000/ \
       --summary-file notes_178000.md --matchup-db D:/AI/matchup_db.db
   ```

   Optional flags: `--baseline-build` (defaults to the current build in `data/golden/patches.db`)
   and `--pypy` (defaults to `pypy3` on PATH). It runs, in order:

   1. Archives `data/inputs/extracted_data/` → `data/local/extracted_data_prev/` and
      `data/golden/aoe2_reference.db` → `apps/website/aoe2_reference_prev.db` (both untracked "before" snapshots).
   2. `python -m aoe2x.extract.run` → `python -m aoe2x.dbgen.generate_reference` →
      the surgical ref patches (idempotent: `aoe2x/dbgen/patches/patch_mayan_archer_cost.py`,
      `patch_rocket_cart_volley.py`) → `python -m aoe2x.dbgen.generate_main_db`
      (patches run BEFORE the main-db flatten so `aoe2_units.db` picks them up).
   3. Diffs `ref_units` before/after → stat deltas + `apps/website/changed_units_<build>.json`.
   4. Snapshots before-outcomes from the matchup DB for the changed slugs.
   5. `pypy3 -m aoe2x.batch.run_matchup_battles --force --changed-units apps/website/changed_units_<build>.json --db <matchup-db>`
      — the **incremental** re-sim (only matchups touching a changed slug).
   6. Diffs matchup outcomes → `patch_matchup_changes`.
   7. `carry_forward_battle_scores` (copies the prior build's `battle_scores` rows — including
      naval/siege rows the land derive does not own — to the new build), then
      `python -m aoe2x.rank.derive_unit_rankings --matchup-db <db> --build <build> --allow-stale` (→ `data/golden/derived_data.db`),
      `python -m aoe2x.rank.derive_pool_scores --matchup-db <db> --out data/golden/pool_scores.db --build <build> --allow-stale`
      (`--allow-stale` because the incremental re-sim leaves mixed `sim_version` rows),
      inserts the `patches` row, flips `is_current` to the new build, then
      `best_units.save_civ_power_units('<build>')` (→ `data/golden/civ_power_units/<build>.json`).
      The order matters: `save_civ_power_units` reads the *current* build's pool/battle scores.
   8. Diffs rankings → `patch_unit_ranking`; writes all patch records into `data/golden/patches.db`.

5. **Decide: incremental vs full re-sim.** The pipeline's step 5 is incremental. If the patch
   notes mention engine-relevant mechanics (or you want a fresh baseline-of-record), do a full
   rebuild instead and preserve it under the build number:

   ```
   pypy3 -m aoe2x.batch.rebuild_matchup_baseline --out D:/AI/matchup_baseline_<build>.db --workers 12
   ```

   (~4.5 h; flags verified: `--out`, `--workers`, `--dry-run`, `--sample N`.) Then re-run the
   three derive commands from step 4.7 pointed at the new baseline DB. See
   [`docs/matchup-baseline.md`](../matchup-baseline.md) for the unattended runner/watchdog setup.
6. **Manual follow-ups the pipeline does NOT do:**
   - `python -m aoe2x.advisor.top_units` if any civ's top tier per line could have changed (regenerates
     the committed `data/golden/civ_top_units.json`).
   - `python -m aoe2x.rank.derive_siege_scores --build <build>` only if siege/anti-building stats
     changed (otherwise the carry-forward keeps the prior rows; flags: `--build`, `--derived-db`).
   - Regenerate the golden baseline if `pytest tests/test_simulations.py` fails on golden keys —
     a stat change legitimately alters `get_matchup_sims` output:
     `python .golden/capture_baseline.py`, then commit `.golden/baseline.json`.
7. **Verify.** `pytest`; spot-check availability (`/api/top-unit/Koreans/knight` → Cavalier);
   `PORT=5002 python apps/website/app.py` and smoke-test `/patches`, `/matchup-advisor`, rankings.
8. **Commit on `staging` and promote.** Commit set: `data/golden/aoe2_reference.db`,
   `data/golden/aoe2_units.db`, `data/golden/derived_data.db`, `data/golden/pool_scores.db`,
   `data/golden/patches.db`, `data/golden/civ_power_units/<build>.json`, plus `data/golden/civ_top_units.json`
   and `.golden/baseline.json` if regenerated. Verify on the staging URL, then
   `git checkout main && git merge --ff-only staging && git push origin main && git checkout staging`.

**Build-number touchpoints** (everything is build-versioned; the UI reads
`patches_db.get_current_build()`):

| Artifact | Where the build number lives |
|---|---|
| `data/golden/patches.db` | `patches` row + `is_current` flag (set by the pipeline) |
| `data/golden/derived_data.db` | `battle_scores.build_number` column |
| `data/golden/pool_scores.db` | build column written by `derive_pool_scores --build` |
| `data/golden/civ_power_units/<build>.json` | filename |
| `apps/website/changed_units_<build>.json` | filename (input for incremental re-sims) |
| `D:/AI/matchup_baseline_<build>.db` | filename (local baseline-of-record, not committed) |

---

## 2. Simulation logic / combat mechanic change

Three engines exist; decide which ones the change applies to (details:
[`simulation-engines.md`](simulation-engines.md)):

| Engine | File | Consumed by |
|---|---|---|
| Abstract tick sim | `aoe2x/sim/simulation.py` | `best_units.get_matchup_sims` (default `sim_func`) → the live `/api/matchup-sims` advisor endpoint; `aoe2x/rank/compute_battle_scores.py`; the golden baseline |
| Position-based sim | `aoe2x/sim/simulation_real.py` | `aoe2x/batch/run_matchup_battles.py`, `aoe2x/batch/rebuild_matchup_baseline.py`, `aoe2x/batch/patch_resim.py`, `aoe2x/batch/verify_flips.py` → matchup DB → all derive scripts |
| Frontend canvas sim | `apps/website/static/js/engine/` (`battle_unit.js`, `sim.js`) — `simulate.js` is now just the page shell, `sim_renderer.js` the drawing layer | the Battle Sim page at `/` (legacy `/simulate` 301-redirects there), the lab harness `/static/lab/sim_harness.html`, and headless node runs (`tools/simjs/headless.mjs`); fetches stats from `/api/ref/combat-unit/<civ>/<slug>` |

*Condensed from [simulation-engines.md](simulation-engines.md) §4 — update both together.*

Steps:

1. Apply the change to the relevant engine(s). A mechanic that affects real battles usually
   needs all three (the JS sim mirrors but does not share code with the backend).
2. **Know the `sim_version` consequence.** `aoe2x/sim/sim_version.py` hashes exactly two files:
   `aoe2x/sim/simulation_real.py` and `aoe2x/dbgen/config_combat.py`. Every `matchup_db` row stores
   the hash; on the next `run_matchup_battles` run, rows with a stale hash are re-simulated
   automatically (no `--force` needed). Changing **`simulation.py` does not bump `sim_version`**
   — nothing in the matchup DB goes stale from it; only the live advisor sims and golden change.
3. Run the tests: `pytest tests/test_position_sim_abilities.py tests/test_simulations.py tests/test_sim_version.py`.
4. If `simulation.py` behavior changed intentionally: `python .golden/capture_baseline.py`,
   re-run `pytest tests/test_simulations.py`, commit `.golden/baseline.json`.
5. If `simulation_real.py` changed: full baseline rebuild (runbook 1, step 5) — do **not** mix
   engine versions in one matchup DB ("patchwork" gotcha in `docs/patch-workflow.md`). For a
   narrow change, §2a below covers re-simulating only the rows the change can reach, and the
   proof obligations that come with it. Then
   re-derive rankings, pool scores, and civ power units at the **current** build number.
   The derive CLIs enforce this: rows at a non-current `sim_version` abort the run unless
   `--allow-stale` is passed (and a <40-civ source DB aborts unless `--allow-small-db`).
6. The legacy round-robin/benchmark JSON chain is gone: `battle_scores.json` and its
   `app.py` loader were deleted — `/api/ref/unit-line` scores come solely from
   `derived_data.db` (plus the empty reference-DB fallback). Do not run
   `compute_battle_scores.py`.

### 2a. Carry-forward — re-simulating only what a change can touch

Step 5 above mandates a full rebuild for *any* `simulation_real.py` edit. That is
deliberately blunt: `sim_version` is a hash of the whole file, so a one-line change
stales all ~540k rows and costs ~6.5 h. Most fixes are narrow (the 2026-07 armour
damage-class fix touched 23 units; a trample fix touches the dozen units with an
AoE radius), so the rebuild is mostly re-deriving rows that cannot have changed.

Carry-forward copies the untouched rows into the new `sim_version` and re-sims only
the rest. **The whole risk is scoping.** A row copied forward under a version that
did not actually produce it is silent corruption, and it looks complete — strictly
worse than a slow rebuild. So a row may be carried forward only when the change
*provably* cannot alter its outcome, established one of three ways:

| Basis | Strength | Example |
|---|---|---|
| **Structural gate** | Proof | A kiting change cannot affect melee-vs-melee: the whole block sits behind `if self.is_ranged():`, so the branch never executes. |
| **Recorded branch-touch flag** | Proof, if recorded | The run records, per dedup group, which changed-behaviour branches any seed actually entered. Change branch X → re-sim exactly the groups whose X flag is set. |
| **Inference from stored aggregates** | **Not a proof — see below** | "This row's fight was short, so the 60 s cutoff never applied." |

**The averaging trap.** Never scope from a stored per-row field. Every numeric
column in `matchup_battles` is a *mean over 8–40 seeds* (`average_outcomes()`), so
a row whose `game_time_s` reads 45 s can still contain a seed that ran 70 s and hit
a 60 s cutoff. Averages cannot prove a per-seed claim. Anything scoped this way must
be treated as unproven and re-simmed, or promoted to a recorded flag.

**Branch-touch flags are the general mechanism** and the one worth building. Rather
than inferring blast radius from unit properties, have the engine set a bit whenever
it takes a branch whose behaviour a future change might alter, OR the bits across
every seed in a group, and store the mask beside `sim_version`. Blast radius then
becomes a lookup instead of an argument. The flags must already have been recorded
by the *previous* run to be usable, so add them before the next full rebuild — they
are what make every later narrow fix cheap.

**Required regardless of basis:**

1. Store provenance per row — a `simmed_at_version` alongside `sim_version`, so a
   copied row is always distinguishable from a simulated one. Without it, a later
   audit cannot tell which rows a given engine build actually produced.
2. **Verification sample.** After copying, re-sim a random sample (~300 groups) drawn
   from the *carried-forward* set under the new engine and assert the means are
   identical. Any mismatch means the scope was wrong → abort before writing. This
   costs about a minute and is the only thing standing between a wrong predicate and
   a corrupt baseline. It is not optional.
3. Re-run the completeness queries from runbook 1 (`groups_failed`, `groups_done
   WHERE n=0`) plus a count check: copied + re-simmed must equal the expected total.

**Worked example — removing `KITE_STOP_TIME`.** Below the cutoff no code path
differs, so the change looks tiny. Measured against the 540,920-row baseline:

| set | rows | share | status |
|---|---|---|---|
| melee-only (kite block unreachable) | 135,908 | 25.1% | **provably safe** — structural gate |
| ranged, mean fight < 60 s | 296,674 | 54.8% | *unproven* — mean, not max |
| ranged, mean fight ≥ 60 s | 108,338 | 20.0% | must re-sim |

Only the first band can be carried forward today. The 31,674 rows averaging 55–60 s
almost certainly contain seeds past the cutoff. Recording a `hit_kite_stop` flag
would move most of the middle band into the provable column — but only from the run
that records it onward.

**Rule of thumb:** carry-forward pays when the change is narrow. A kiting change
touches 74.9% of rows and saves ~2 h of 6.6 h — not worth debuting the mechanism on.
A single-ability or single-unit fix is 95%+ copyable and turns the rebuild into
minutes. Build it for the narrow case; do not let it debut on the widest one.

---

## 3. New combat stat column / new special ability

Since the Phase B registry refactor (2026-06-10, data-model-review §3.2), the storage/serving
chain is GENERATED from the ability registry — the old 6-file hand-sync is gone. The chain is:
**registry entry + config value + one handler per engine**, then regenerate.

1. **`aoe2x/dbgen/ability_registry.py`** — declare the ability/params: name (= combat-dict key),
   python type (drives the SQL column type), default (drives the DDL `DEFAULT` and every
   loader's null-coalesce), `ref_column` if it differs from the name, `audit` description
   (the `ref_special_effects` row text), `engines`, source, quirks. This single entry makes
   `generate_reference.py` create/write/audit the column (new columns append at the end of
   `ref_units` — the legacy order pin there needs no edit) and makes
   `combat_unit_loader.build_combat_dict_from_ref` emit the key. The Flask endpoint needs no
   change either: `/api/ref/combat-unit` does `SELECT * FROM ref_units` and delegates to that
   loader.
2. **`aoe2x/dbgen/config_combat.py`** — the curated value: `COMBAT_PROPERTIES` (standard units),
   `UNIQUE_COMBAT_PROPERTIES` (unique-unit abilities), or `CIV_COMBAT_PROPERTIES`
   (civ-conditional overrides). Later dicts win; the dat-extracted value is the base layer.
   (Skip if the value is dat-extracted — then extend `combat_properties.py` instead.)
3. **One handler per engine that models it** — `aoe2x/sim/simulation.py` (also add the key to its
   `_PREPARE_SCALAR_KEYS` pin in the same file: the abstract engine consumes a deliberate
   subset of the registry), `aoe2x/sim/simulation_real.py`, and
   `apps/website/static/js/engine/battle_unit.js` `BattleUnit` (**not** `simulate.js` — that is
   only the page shell now; `tests/test_ability_registry.py` scans the engine modules plus the
   page shell as its "js" source, so a key read only in the page — e.g. `pop_space` — still
   counts). Declare non-implementing engines honestly in the registry `engines` tuple and
   `tests/test_ability_registry.py::KNOWN_ENGINE_GAPS` — the presence-parity test fails on
   undeclared gaps.
   - **JS parity gate (mandatory after any `engine/` edit).** Run
     `node tools/simjs/parity_check.mjs` — it replays the 205-fight golden panel in
     `tools/simjs/golden/` and demands bit-exact state hashes (exit 0 = OK, 1 = divergence,
     2 = harness/meta error). A new ability that changes existing fights *will* fail it: that
     is the intended signal — re-capture the golden panel and record why in the commit
     message. Also run the engine unit tests: `node --test tests/js/engine/` (17 tests) and
     `node tests/test_frontend_projectile_miss.js`.
4. **Legacy `aoe2x/dbgen/generate_main_db.py`** (only if you care about `aoe2_units.db` — no app
   route reads it): its `unit_stats` `CREATE TABLE` + INSERT + bespoke
   `build_combat_dict_from_ref` still need hand edits;
   `tests/test_ability_registry.py::test_maindb_dict_keys_track_registry` fails until the new
   param is carried (or consciously excluded there).
5. Rebuild and re-sim: `python -m aoe2x.dbgen.generate_reference`, `python -m aoe2x.dbgen.generate_main_db`.
   Because `config_combat.py` is hashed into `sim_version`, **every** matchup row goes stale —
   plan a full re-sim (runbook 2, step 5), then re-derive and regenerate golden.

---

## 4. New unit or new civ (DLC)

1. **`extraction/extract_constants.py`** — `CIV_NAMES` is a positional list where the index is
   the dat civ ID (`None` for unused slots). A new civ must be added at its exact dat slot.
2. **`aoe2x/dbgen/config_units.py`** — add the unit to the age dicts (`FEUDAL_UNITS`,
   `CASTLE_UNITS`, `IMPERIAL_UNITS`, `UNIQUE_UNITS`) and re-validate `_AVAILABILITY_OVERRIDES`
   against SiegeEngineers (a module-level warning fires if an override slug no longer exists).
3. **`aoe2x/dbgen/config_combat.py`** — abilities the dat cannot express (runbook 3).
4. **`aoe2x/sim/unit_lines.py`** — register the unit in `UNIT_LINES` (line membership,
   `unique_units` per civ) and add any tech-tree gaps to `CIV_MISSING_UNITS`. This module is the
   single Python source for line definitions (imported by `app.py`, all derive scripts, and the
   sim runners).
5. **`apps/website/static/js/constants.js`** — `ENABLED_CIVS` (new civ), `NAME_TO_ICON` (new units),
   `UNIQUE_BUILDING` (only for unique units not trained at the Castle).
6. **Icons/art** — runbook 5.
7. Rebuild everything (runbook 1 steps 4–8: extraction → ref → main → full baseline re-sim,
   since a new roster invalidates the matchup universe → derive at the current/new build), then
   `python -m aoe2x.advisor.top_units` to refresh `data/golden/civ_top_units.json`.
8. SEO pages need **no manual step**: `/sitemap.xml` and the `/vs/...` landing pages are derived
   live from `ref_units` unique-unit rows (`apps/website/app.py` `_matchup_seed_pairs`).

Note: the pipeline civ list (`ORIGINAL_13_CIVS` in `aoe2x/dbgen/config_constants.py`) is now
derived from `extraction.extract_constants.CIV_NAMES`, so step 1 covers it automatically —
no separate `config_constants.py` edit. Webapp civ validation reads the reference DB via
`_valid_civs()`; the old dead copy in `apps/website/app.py` was deleted.

---

## 5. New unit icon / art

Icon files are flat PNGs in `apps/website/static/img/units/` (213 files), named by display name with
underscores (`Long_Swordsman.png`). The **single registry** is `NAME_TO_ICON` in
`apps/website/static/js/constants.js` (218 entries, display name → file basename); no template carries
its own copy. `getIconUrl()` in the same file builds the URL, and every page's JS
(`rankings.js`, `simulate.js`, `civ-detail.js`, `matchup.js`, `matchup_advisor.js`) consumes it.

1. Find the icon ID from the dat via genieutils (conda python):
   `dat.civs[0].units[UNIT_ID].icon_id`.
2. Fetch `https://aoe2techtree.net/img/Unit/{icon_id}.png` (fallback: Fandom wiki API).
3. Save as `apps/website/static/img/units/<Display_Name>.png` (underscores for spaces).
4. Add the entry to `NAME_TO_ICON` in `apps/website/static/js/constants.js`. The key is the
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
| `ENABLED_CIVS` (53) | `apps/website/static/js/constants.js` | civ dropdowns in `simulate.js`, `rankings.js` |
| `NAME_TO_ICON` (218) | `apps/website/static/js/constants.js` | all page JS via `getIconUrl()` |
| `UNIQUE_BUILDING` (13) | `apps/website/static/js/constants.js` | `simulate.js`, `civ-detail.js` |
| `UNIT_LINES` / `CIV_MISSING_UNITS` / `NAVAL_UNIT_LINES` | `aoe2x/sim/unit_lines.py` | `app.py`, `compute_battle_scores.py`, `derive_*`, `run_matchup_battles.py`, `top_units.py`, `best_units.py` |

The one cross-language sync that remains: `ENABLED_CIVS` (JS) must match the civs present in
`data/golden/aoe2_reference.db` (which come from `extraction/extract_constants.py` `CIV_NAMES`).
There is no automated check — after changing either side, load `/simulate` and confirm the civ
list, and run `pytest tests/test_footer.py` plus a quick `/api/ref/civ/<NewCiv>` call.

---

## 7. Hardcoded combat-property fix for a single unit

Two paths, depending on blast radius. Background: a **full pipeline regen rewrites the
combat-property columns on every row** of `aoe2_reference.db`/`aoe2_units.db`, so an
"innocent" rebuild can ship unintended drift on units you never touched.

**Path A — config fix + full rebuild** (fine when you intend a clean rebuild anyway):

1. Edit `aoe2x/dbgen/config_combat.py` (or `config_units.py` for stat overrides).
2. `python -m aoe2x.dbgen.generate_reference`, re-apply the surgical patches
   (`python -m aoe2x.dbgen.patches.patch_mayan_archer_cost`,
   `python -m aoe2x.dbgen.patches.patch_rocket_cart_volley`), then
   `python -m aoe2x.dbgen.generate_main_db`.
3. **Diff the result** before committing — only the intended rows should change. The
   `ref_diff.diff()` helper used by the patch pipeline (`aoe2x/batch/ref_diff.py`) is the tool.
4. Because `config_combat.py` is in the `sim_version` hash, all matchup rows are now stale.
   Either accept a full re-sim, or scope it:
   `pypy3 -m aoe2x.batch.run_matchup_battles --force --changed-units <slugs.json> --db <matchup_db>`
   — knowing this leaves the DB a mixed-`sim_version` patchwork (acceptable for a cosmetic hash
   bump where unchanged units genuinely sim identically).
5. Re-derive (runbook 1, step 4.7 commands) and regenerate golden if outputs moved.

**Path B — surgical DB patch** (when the pipeline itself can't produce the right value, or you
must not touch other rows): write an idempotent script in `aoe2x/dbgen/patches/` following
`aoe2x/dbgen/patches/patch_mayan_archer_cost.py` (recompute from base values so re-running is a
no-op; support a `--dry` preview). Patch `data/golden/aoe2_reference.db`, then re-run
`python -m aoe2x.dbgen.generate_main_db` so `aoe2_units.db` matches, and register the script in
`aoe2x/batch/patch_pipeline.py` step 2 so future full regens re-apply it. Then re-sim only the
affected slugs as in Path A step 4.

For before/after impact analysis of either path, `pypy3 -m aoe2x.batch.patch_resim --my-units
<units.json> --out <means.db> [--ref <ref.db>] [--seeds 15] [--workers N]` runs the changed
units against the full pool with multi-seed means, and `aoe2x/batch/verify_flips.py` adversarially
re-checks candidate flips (both PyPy-only).

---

## 8. Civilization-page-only reference release (Viking Sagas)

Verified locally on 2026-09-22 against installed game build **185872**. Use this
when civilization presentation is approved before simulations/rankings are ready.
It is **not** the full patch/DLC pipeline in §1/§4: do not rebuild golden databases,
derive rankings, rerun simulations, flip the current-build pointer, or extend Advisor
candidates. Unit media uses the existing shared asset catalog; an asset-catalog
publication does not authorize changing the simulation/ranking databases.

Owner correction (2026-09-23): retain the original Best Units titles, descriptions,
SEO wording and subtitles, with the civilization count updated to 56. Keep costs,
normal hover/click animations and in-place civilization selection. Do not add media
selectors or new keyboard/focus interactions. The explicit-question rule in
`AGENTS.md` applies to each additional change; inclusion in a plan is not approval.

### Inputs and isolated checkout

- Start a feature branch from current `origin/main` in a separate worktree. This
  release uses `codex/civilizations-viking-sagas`, based on `0ce703be`. Do not merge
  the unrelated video branch to obtain its assets.
- Use the installed `resources/_common/dat/empires2_x2_p1.dat` and sibling
  `CivTechTrees/*.json`. This release's DAT SHA256 is
  `4aa2f0a719e88e5f1502517eddb27c669aeb40c2fe9d8c4f3eec7751c01e7baa`.
  Verify public names against the installed English string table. Individual
  selected tree hashes are recorded in the generated supplement.
- Read the approved `graphics/units/` sources from revision `68e99758` in the
  original checkout. Source unit directories were unchanged from that revision.
  Keep the complete approved library on its existing branch; copy only the web
  bundle described below. No new sprite render or enhancement is needed.

### Build the page supplement and selected media

Run from the feature worktree with CPython, `genieutils-py`, and Pillow. Adapt
absolute source paths to the installed game and approved asset checkout:

```powershell
python -m aoe2x.assets.build_civilization_release `
  --dat D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat `
  --trees D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/CivTechTrees `
  --assets D:/AI/aoe2_matchup/graphics/units `
  --output apps/website/static `
  --extracted data/local/generated/civilizations-185872/extracted
```

The default extracts into that ignored local directory. `--reuse-extracted` is
only for an already extracted, identical DAT release, not a different game build.
This builder is specifically the 185872 release; a later release needs its own
reviewed identities/availability/provenance, not just a renamed JSON file.

Outputs:

- `apps/website/static/data/civilizations-185872.json`: 69 reference rows across
  16 affected civilizations. Danes, Saxons and Varangians each have 18 supported
  military rows at their highest available Imperial tier. Existing page combat
  categories exclude civilians, Monks, Petards and Siege Towers; Trebuchet uses
  the existing combat representation.
- Ten base/elite forms use the standard shared paths: `static/img/units/<Name>.png`
  and `<Name>_transparent.png`, `static/img/unit_sprites/<slug>.png`, and
  `static/anim/<slug>.webp`. The existing presentation icon map, `unit_sprites.json`
  / `unit_sprites.js`, and `unit_anims.json` register them just like older units.
  Conversion preserves all 390 source frames, alpha, durations and loop settings.
  The release's media inventory is build provenance, not a separate runtime lookup.
  Civilization rows carry no media overrides; cards show the available unit tier.
- `apps/website/static/img/civilizations/185872/`: three finished shields from
  `widgetui/textures/menu/civs/`, **not** the mask textures in `ingame/emblems`.
- These 43 files total 15,763,368 bytes; exact sources, hashes and animation
  metadata are recorded in the supplement's `media_inventory`.

Owner correction (2026-09-23): use the selected DAT 4x idle sprites and DAT 4x
attack GIFs just like the existing civilizations. Streaking is not permission
to substitute native-resolution stills or attack-frame posters. Idle PNGs use
the shared website's 384px bound; the lossless animated WebPs preserve the GIF
frames and timing. No originals are modified or regenerated.

All cards use the same sprite catalog and hover animation lookup. Longship names
are shared-catalog aliases of the existing Longboat assets. Ships without an
attack entry in that catalog remain still, exactly as in the other civilizations.

To publish only the ten selected idle sprites and media aliases (no DAT
extraction, AI inference, stat changes, or attack conversion):

```powershell
python -m aoe2x.assets.build_civilization_release --output apps/website/static --assets D:/AI/aoe2_matchup/graphics/units --refresh-idles
```

The shared food/wood/gold cost images are three unchanged game files, copied once
from `widgetui/textures/ingame/staticons/{food,wood,gold}.png` into
`apps/website/static/img/resources/` (not generated by the release builder):

| File | Bytes | SHA256 |
| --- | ---: | --- |
| food.png | 10,200 | `2335d250fdd905898f35bbc7d9a2920889201ad888bdc3284ce3536ef634ea2c` |
| wood.png | 9,441 | `427aac7fa89381bff4cc50a895ebda11654d257cdfacc425d39cce52bb799223` |
| gold.png | 11,940 | `fcca46c72630f27a6b242bf3aebfe879b6575aca835faad79ce8e4ec750eb86f` |

Total selected new media, including those cost images: **46 files / 15,794,949
bytes**. No source GIF library, recordings, caches, contact sheets or scratch
extraction outputs belong in this feature's commit set.

### Serving, verification and publication boundary

When the existing bucket configuration is enabled, the shared catalog supplies
`/assets/img/units/`, `/assets/img/unit_sprites/`, and `/assets/anim/` URLs. The
supplement loader rewrites only civilization emblem URLs. Before deploying this
correction, obtain publication approval and upload/verify the 40 relocated media
files at their canonical bucket keys. Keep the old bucket objects; this correction
does not authorize deleting them. The images/animations are byte-identical moves,
not regenerated assets. The three emblems and previously uploaded source GIFs
remain at their existing keys and do not require re-uploading.

The normal `/api/assets/catalog` path synthesizes its response from the committed
manifests when no catalog database is configured. Check the actual deployment's
catalog mode before promotion: the optional Postgres reader currently returns
only sprites/icons, not animations, so refreshing its rows alone is not sufficient.
That pre-existing limitation needs separate approval to address if that path is
used; this correction does not refactor it or authorize database writes. A
read-only production check on September 23 returned build 177723 with 223 sprites
and 193 animations, including `/assets/anim/arbalester.webp`. Verify the new shared
icon/sprite/animation entries before promotion without changing the game build or
ranking data. Production has a separate bucket: a staging upload does not update it.

`civilization_page_analysis` composes the supplement onto a copy of the existing
ranked analysis. Initial HTML and `/api/civilizations/<Name>` use that same data.
The civilization overview, selector and sitemap contain 56 civilizations; the
engine/Advisor catalogs and `/api/civ-power-units` stay unchanged. Actual supplied
rank fields continue to render normally. No scores or tiers are fabricated, and
no “not ranked yet” or other interim status UI is introduced.
The builder sets `published_at` to its generation date, so rebuilding identical
inputs on another day changes affected civilization sitemap `lastmod` dates.
The approved September 23 presentation release advances that date to 2026-09-23.
The civilization overview and affected detail pages use the later of this date
and the underlying data date; unrelated pages retain their own data date.

Run only the focused checks for this page release:

```powershell
python -B -m pytest tests/test_civilization_release.py tests/test_seo_civ_pages.py -q -p no:cacheprovider
node --test tests/civilization_media.test.cjs
python -B -m flask --app apps.website.app run --host 127.0.0.1 --port 5011 --no-debugger
```

The historical September 22 smoke check included preview controls and changed
navigation that the owner subsequently rejected. Those checks are not approval
to reintroduce them. Current focused tests require the original presentation,
shared unit assets, unchanged simulator availability, and retained resource costs.

Stage exact source, test, JSON, media and documentation paths. Review the entire
outgoing range against freshly fetched `origin/main`, including binary sizes,
not only the last commit. Golden DBs, published ranking JSON, engine code and the
current build must have no diff; preserve the original checkout's unrelated work.
If main advances, integrate it on the feature branch and repeat the focused
checks and outgoing-range review. **Stop before merging/pushing to main or
deploying, and obtain explicit approval for that production action.**

---

## Update triggers

| If this changes | Update these sections |
|---|---|
| `aoe2x/batch/patch_pipeline.py` steps or flags | §1 (and `docs/patch-workflow.md`) |
| `aoe2x/sim/sim_version.py` `DEFAULT_FILES` | §2, §3, §7 |
| `aoe2x/sim/combat_unit_loader.py` or either `prepare_combat_unit` | §3 |
| `apps/website/static/js/constants.js` structure (registries move/split) | §5, §6 |
| `aoe2x/sim/unit_lines.py` location or shape | §4, §6 |
| Derive scripts gain/lose argparse flags | §1, §2 (re-verify every command) |
| `.golden/capture_baseline.py` coverage or seed | §1, §2 |
| `aoe2x/dbgen/patches/` gains a new surgical patch | §1 step 4.2, §7 (and `patch_pipeline.py` itself) |
| Matchup DB schema or baseline workflow | §1, §7 (and `docs/matchup-baseline.md`) |
| Civilization supplement builder, page composition or media contract | §8 |
