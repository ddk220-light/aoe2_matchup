# Improvement Backlog

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This backlog merges two sources: (1) a 7-area multi-agent code review in which every confirmed high/medium finding was adversarially re-verified by a skeptic agent (35 confirmed, 5 refuted, 15 low-severity passed through unverified) — recommendations below already incorporate the verifiers' corrections; and (2) a repo-organization audit covering file/folder structure, naming, dead-script archival, and the module-docstring inventory. Severity is high/medium/low; effort is S/M/L.

## Quick wins

The best value-for-effort items across both inputs. All are S effort except the Cumans/Dravidians fix (M, but it is a live data bug on the core feature).

| # | Item | Why now |
|---|------|---------|
| 1 | Regenerate the stale golden baseline | `pytest` is RED on clean checkouts of both `staging` and `main` (2 golden failures since 177723 data shipped without a baseline regen) — the main sim-drift guard is disarmed |
| 2 | Seed the live advisor RNG | `/api/matchup-sims` flips borderline verdicts between refreshes; `random.seed(GOLDEN_SEED)` at the top of `get_matchup_sims` reproduces the current baseline byte-identically |
| 3 | Fix cost-weight drift (wood 0.8 vs 0.7) | `best_units._calc_weighted_cost` was missed when commit `ba893a3` moved everything to 0.7 — delegate to `simulation_real.weighted_cost` |
| 4 | Restore Cumans Camel Rider / Dravidians Battle Elephant at Imperial | Both units missing from Imperial entirely (collateral of the phantom-unit purge); user-visible wrong data in rankings/advisor |
| 5 | Derive-script guardrails (`--matchup-db` required + staleness check) | One forgotten flag silently writes Armenians-only, stale-sim rows into the deployed `derived_data.db`; `derive_advisor_recs.py` has no flag at all |
| 6 | CI via GitHub Actions | 25 pytest files + 2 Node tests, zero automation; suite runs in ~37 s from committed artifacts alone; do after item 1 or CI is born red |
| 7 | Create `favicon.png` + `og-default.png` | Referenced on every page, exist nowhere; prod 404s both; every Reddit/Discord share (the primary marketing channel) loses its preview card |
| 8 | `git rm --cached` the 488 regenerable upscaled sprite PNGs | 153 MB of the 156.5 MB `graphics/extracted` tree is upscale output (originals: 3.4 MB); each ESRGAN re-run re-commits ~50–100 MB of churn |
| 9 | Backfill `patch_unit_ranking` for build 177723 | All 19 changed-unit patch pages falsely show "Ranking unchanged." — the diff data regenerates in one command |
| 10 | Fix "all 50 civilizations" SEO copy | Five templates say 50; the site has 53; these strings are Google's snippet for the main pages |

## Confirmed findings

### Architecture & repo

#### 260 MB of unconsumed art/sprites tracked — stop the churn, do NOT rewrite history
**Severity:** medium · **Effort:** M
Evidence: tracked tree is 314 MB; `graphics/extracted` = 733 PNGs / 156.5 MB (488 regenerable upscale variants = 153 MB) and `graphics/art` = 233 FLUX.2 files / 104 MB. Nothing under `webapp/` references either; `docs/architecture/operations.md:158` claims the sprites are "local, uncommitted" while 733 are tracked.
Recommendation: push `staging` as-is (origin already has every blob — `origin/staging` is merely stale); `git rm --cached` the upscale variants and gitignore them; fix `operations.md:158`; `git gc` locally (~617 MB loose objects). Keep `graphics/art` tracked (deliberate, documented). History rewrite only as a deliberate future decision touching both branches in lockstep.
Verifier: the original "rewrite the unpushed range before pushing" premise was refuted and harmful — the blobs are already ancestors of `origin/main`, so a local rewrite shrinks nothing and permanently breaks ff-only promotion.

#### The 53-civ list exists in three copies; one is dead, one is mechanically derivable
**Severity:** medium · **Effort:** S
Evidence: `extraction/extract_constants.py CIV_NAMES` (60 dat slots), `analysis/config_constants.py:81 ORIGINAL_13_CIVS` (53 entries, live — iterated by `generate_reference.py:1278/1524`), and a dead byte-identical copy at `webapp/app.py:682`. On the next DLC all three must be hand-edited or civs silently drop out — and the current new-civ runbook omits the `config_constants.py` edit entirely.
Recommendation: delete the `app.py` copy; replace the analysis literal with `sorted(c for c in CIV_NAMES[1:] if c)` (verified exact-order-equal, so DB output is unchanged); update `runbooks.md` §4; supersede the stale 2026-04-12 dat-update plan doc that mandates maintaining the dead copy. Renaming the constant is optional — see [Repo organization plan](#repo-organization-plan).

#### ORIGINAL_13_CIVS in app.py — 55 lines of dead code
**Severity:** low · **Effort:** S
Zero consumers (validation uses DB-derived `_valid_civs()`, `app.py:1377`). Delete `app.py:682-736` and trim the now-moot dead-code warnings in CLAUDE.md / `webapp.md:79,166` / `runbooks.md:190-191` / the webapp-architecture skill. See [Repo organization plan](#repo-organization-plan).

#### simulate_mixed_battle: 860 dead lines (27% of simulation.py)
**Severity:** low · **Effort:** S
`simulation.py:2310`→EOF, zero callers (its callers were deliberately deleted in `8a186c8`); the 2026-06-05 special-effects audit spent effort recommending bleed infrastructure for it. Delete it; rewrite the comment at `simulation.py:459-460` but **keep** `s.EXTRA_PROJ_ACCURACY = 0.85` (read at lines 949/1830 by live code). Not hashed into `sim_version`; cannot affect golden. See [Repo organization plan](#repo-organization-plan).

#### aoe2_units.db (stage 3) is ~95% dead weight, kept alive by one offline tool
**Severity:** medium · **Effort:** M
Evidence: `unit_stats` (11,554 rows × 100 cols) has exactly one SQL consumer — `scenario_builder/overlay/results.py:74`. The app reads only the 218-row `units` table (`app.py:463`) and the permanently-empty `unit_verifications` (`app.py:762` — the "verified" badge is always false; no frontend consumes it). `generate_main_db.py` carries a duplicated 180-line combat-dict builder that must mirror `webapp/combat_unit_loader.py` (CLAUDE.md sync rule 1); 3 of its last 6 commits were exactly that sync work.
Recommendation: (1) delete the dead verified-badge read + fields; (2) port `results.py load_unit()` to the `ref_units → build_combat_dict_from_ref → prepare_combat_unit` chain (template: `run_matchup_battles.py:74-88`; add Imperial→Castle fallback) after a one-time both-paths equivalence diff; (3) serve `/units` from `aoe2_reference.db` or `unit_lines.py` (ref names are per-civ — don't naive-SELECT); (4) only then retire `generate_main_db.py` + the DB, with a ~6-file doc/skill sweep. See [Repo organization plan](#repo-organization-plan).
Verifier: repo-size motivation is ~18× overstated (98 committed versions pack to 4.6 MB); the real payoff is killing the dual combat-column mapping.

#### Retired battle-scores chain still entangled
**Severity:** low · **Effort:** M
Evidence: `compute_battle_scores.py` (2,451 lines, retired as a pipeline) survives because `derive_siege_scores.py:35` and 3 test files import scoring symbols; `app.py:1030-1050` still loads the 342-byte `battle_scores.json` stub whose `_attach_scores` else-branch emits `-999` sentinels (harmless: `rankings.js` treats them as missing).
Recommendation — three independently-shippable pieces: (A) delete `simulate_mixed_battle` (above); (B) delete the stub + loader + else-branch, omitting score keys instead of `-999` (verified behavior-safe); (C) extract a focused `siege_naval_scoring.py` with the live closure (siege **and** naval — `compute_naval_role_scores` is the only naval regeneration path), delete `test_infantry_scoring.py` with the superseded infantry scoring, archive the rest. Budget a ~10-location doc ripple and relocate the `calc_weighted_cost` lockstep cross-ref (`simulation_real.py:78`). See [Repo organization plan](#repo-organization-plan).

#### Dead code with actively false comments: NO_ELITE_UNITS, UNITS_BY_AGE, AGE_NAMES
**Severity:** low · **Effort:** S
`NO_ELITE_UNITS` (`generate_main_db.py:45-51`) is dead since birth and its `_imp`-suffix comment is false (0 such slugs in either DB); `UNITS_BY_AGE`/`AGE_NAMES` (`config_units.py:677-687`) have zero consumers. Delete all three plus the stranded comment block at `generate_main_db.py:311-316` and the orphaned age-constant import at `config_units.py:10`; spare `FEUDAL_UNITS` (feeds `_PREVIOUS_AGE_NAMES`). No DB regen needed. See [Repo organization plan](#repo-organization-plan).

### Data pipeline

#### Cumans Camel Rider and Dravidians Battle Elephant are missing from Imperial age entirely
**Severity:** medium · **Effort:** M
Evidence: `_AVAILABILITY_OVERRIDES` (`analysis/config_units.py:1730-1748`) lists Cumans under `camel` but not `heavy_camel`, Dravidians under `elephant` but not `elite_elephant`, and is applied as whole-config `civ_only` — so the committed ref DB has those civ/unit pairs at Castle only, no Imperial row of any slug, despite the pipeline's best-available-tier convention (Turks `halberdier`@Imperial = "Spearman"). Collateral: the `("Dravidians","elite_elephant")` Wootz Steel `ignores_melee_armor` entry (`config_combat.py:234`) never applies. Absent from Imperial rankings, the matchup baseline, civ pages, and the advisor.
Recommendation: the per-civ upgrade gating is load-bearing — set those two slugs' default `"upgrades"` to `[]` and express Heavy Camel / Elite Battle Elephant via `"civ_upgrades"` (merge with the Hindustanis entry at `config_units.py:474-479`), then add Cumans/Dravidians to the base-tier override lists. Do **not** just widen `civ_only` — the upgrade techs are not in these civs' `disabled_techs`, so that alone re-creates the phantom tiers commit `253086d` removed. Regenerate, verify exactly 2 new rows, then sim/derive per `docs/patch-workflow.md` (no full re-derive).
Verifier: confirmed not intentional — `253086d`'s message names these as phantoms and only verified the Castle rows survived; the Imperial loss was collateral.

#### 21 orphan keys in config_combat.py match nothing in the ref DB
**Severity:** low · **Effort:** S
Evidence: 15/30 `COMBAT_PROPERTIES` keys (exact-match lookup vs civ-suffixed unique slugs, plus Feudal-only slugs), 1/52 `UNIQUE_COMBAT_PROPERTIES`, 5/89 `CIV_COMBAT_PROPERTIES` are dead. The same silent-no-op mechanism is how the Dravidian gap above went unnoticed, and a prior audit tuned the dead `(Poles, winged_hussar)` key without noticing.
Recommendation: add `tests/test_config_combat_keys.py` validating keys against the ref DB with per-dict semantics (exact / exact-or-prefix / exact-or-civ-prefix, mirroring `combat_properties.py:252-272`). Keep roster-conditional keys on an allowlist (Sicilians hand_cannoneer/heavy_camel, Dravidians elite_elephant, elite_xianbei_raider — they auto-activate if a patch adds the unit); delete the genuinely pointless ones.
Verifier: the 15 dead `COMBAT_PROPERTIES` keys carry only the vestigial `unit_category` (loader hardcodes `"military"`), so current behavioral impact is zero — the value is purely preventive.

#### Pipeline generators are untested and their sanity checks cannot fail the build
**Severity:** low · **Effort:** M
Evidence: no test imports `extraction/` or `analysis/`; `_run_sanity_checks` (`generate_main_db.py:940`) prints FAIL but never raises, and every check is `if row:`-guarded; a unit id missing from a new dat silently vanishes (`unit_analyzer.py:1080-1086`); `webapp/ref_diff.py:41-44` iterates only new keys, so the patch-day diff is blind to vanished units.
Recommendation (slimmed): (1) a pytest asserting invariants on the committed `aoe2_reference.db` (53 civs, per-civ minimum row count, one worked example); (2) make `ref_diff.py` report prev-only keys; (3) optionally make `_run_sanity_checks` exit nonzero (low value — `patch_pipeline` never runs it).
Verifier: "only guard is manual ref-diff" refuted — the golden regression exercises the committed ref DB live; the real blind spot is the ~33 civs outside the golden matchups.

#### genieutils-py is pinned nowhere
**Severity:** low · **Effort:** S
In neither requirements file; local install is 0.1.2 (conda). Add a one-line `extraction/requirements.txt` with `genieutils-py==0.1.2` and reference it from `data-pipeline.md`. numpy is imported only by the retired `compute_battle_scores.py` (and tests importing it) — pin or annotate; not a prod risk.

### Sim engines

#### Live Matchup Advisor endpoints are non-deterministic (unseeded RNG)
**Severity:** medium · **Effort:** S
Evidence: `simulation.py` rolls the unseeded module-level `random` (accuracy/stray/scatter/trample — lines 1128-1151, 1535, 2190-2230, 2680-2735, 3084); `POST /api/matchup-sims` (`app.py:1486`) reaches it via `best_units.get_matchup_sims` with no seed on the request path. Empirically reproduced: two identical calls return different results; refreshing the advisor can flip who-beats-whom for borderline matchups (win gate = both scenarios ≥10% HP).
Recommendation: `random.seed(20260411)` (GOLDEN_SEED) at the top of `get_matchup_sims` and `get_matchup_recommendations` — this reproduces the existing `.golden/baseline.json` byte-identically (the capture script already applies that exact seed externally), so no regen; run `capture_baseline.py` once to confirm the no-op. If per-matchup seeds are preferred, seed with a stable string (CPython hashes str seeds via SHA-512) and regenerate the baseline.
Verifier: do **not** use `simulation_real.deterministic_seed` — it is built on the salted builtin `hash()` and is not stable across restarts (it also has zero callers; the simulation-engines.md §6 claim that it is stable is wrong).

#### Cost-weight drift: best_units uses wood ×0.8 while the other two copies use ×0.7
**Severity:** medium · **Effort:** S
Evidence: `best_units.py:1091-1094` computes `0.8*wood + food + 1.5*gold`; `simulation_real.weighted_cost` and `compute_battle_scores.calc_weighted_cost` (explicit lockstep comment) use 0.7. Commit `ba893a3` moved everything to 0.7 and enumerated its call sites — `best_units` is absent, i.e. missed, not intentional. Sizes 3k-resource armies in `/api/matchup-sims` and Phase B recommendation sims differently from the batch baseline (e.g. 34 vs 35 arbalesters).
Recommendation: import `weighted_cost` from `simulation_real` (add it to the existing import at `best_units.py:1088` — it is not already imported) and delegate, keeping the `int(cost) if cost > 0 else 100` floor. Regenerate `.golden/baseline.json` (outputs shift) and add the delegation note to `README.md:108`.

#### Three-engine ability parity is hand-maintained with asymmetric test coverage (13 / 7 / 0)
**Severity:** medium · **Effort:** M
Evidence: 13 targeted ability tests for the position engine, 7 JS tests covering only the accuracy/miss model, zero targeted tests for `simulation.py`'s ability table (guarded only by 20 golden snapshots). The failure mode has shipped: `edc07ed` fixed real divergences (uncapped `attack_bonus_per_kill`, a Fire Archer charge mis-port that put +100 scores into shipped matchup data) caught only by manual wiki-checking.
Recommendation: shared ability fixture file + `tests/test_frontend_abilities.js` (reuse the proven brace-match extraction; assert the same 13 behaviors against the live `BattleUnit`), plus a tiny pytest wrapper shelling out to `node tests/test_frontend_*.js` so JS tests run on every `pytest`. Skip the cross-engine winner-agreement test (brittle to intentional model changes).

#### Combat-dict contract is unvalidated; simulation.prepare_combat_unit silently drops position-engine keys
**Severity:** low · **Effort:** S
Evidence: `build_combat_dict_from_ref` emits 96 keys; `simulation.prepare_combat_unit` returns a fixed 73-key dict omitting `charge_attack_range`, `charge_ignores_armor`, and `food/wood/gold_per_kill` — which `simulation_real.BattleUnit` reads. No live caller crosses the lossy funnel today (the production position-engine chain uses `simulation_real.prepare_combat_unit`'s passthrough), but it has already forced two workarounds.
Recommendation: switch to passthrough semantics (`out = dict(row)` then overwrite parsed fields) + a ~15-line contract test asserting `BattleUnit`'s read-list survives the funnel. No golden or sim_version impact.

### Derived data & patches

#### Derive scripts default --matchup-db to the committed Armenians-only stub
**Severity:** medium · **Effort:** S
Evidence: `webapp/matchup_db.db` (committed, 3.9 MB) holds 10,340 rows, one distinct `my_civ` ('Armenians'), stamped a stale sim_version. It is the default for `derive_unit_rankings.py:327` and `derive_pool_scores.py:38`; `derive_advisor_recs.py` has **no** `--matchup-db` flag at all. A flagless run silently rewrites the Armenians rows of the deployed `derived_data.db` with stale, mispooled output. The real baseline lives at `D:/AI/matchup_baseline_177723.db` (276 MB, outside the repo).
Recommendation: make `--matchup-db` required in both derive CLIs, add the flag to `derive_advisor_recs.py`, and add a CLI-layer sanity guard (`COUNT(DISTINCT my_civ) >= 50`, with `--allow-partial`). Guards must live in `main()` only — tests feed 1-civ synthetic DBs into the library functions. Stub deletion is optional hygiene with a ~4-doc sync; note `run_matchup_battles.py`/`rebuild_matchup_baseline.py` recreate the file at that path if run without `--db`.
Verifier: blast radius is the Armenians rows only (deletes are scoped per civ/unit), and the trap is already documented in `derived-data.md` — this finding converts documentation into enforcement.

#### Derive scripts have no sim_version guard, and the committed matchup_db.db is stale right now
**Severity:** medium · **Effort:** S
Evidence: `derive_unit_rankings.py` has zero `sim_version` references; the committed stub's rows are all at `9257ae65c734faa2` vs current `f6ab0051d5cd4fff`. A bare run today would bake pre-fix outcomes into the deployed `derived_data.db`.
Recommendation: CLI-layer staleness check in all three derivers (`SELECT COUNT(*) ... WHERE sim_version != ?` vs `compute_sim_version()`; abort unless `--allow-stale`). `--allow-stale` is required, not optional — the runbooks bless a mixed-version DB after scoped `--force --changed-units` re-sims.
Verifier: deployed data is NOT currently wrong (the 06-07 ranking refresh derived from the fully-current external baseline); this is a latent footgun, not an active bug.

#### Stat-only patches don't invalidate matchup rows — correctness depends on remembering --force
**Severity:** low · **Effort:** S
Evidence: `sim_version` hashes only code; `has_row_with_version` (`matchup_db.py:175`) matches (pair, scale, sim_version) only, yet each row already stores `dedup_group` — a fingerprint of final unit stats — computed right before the skip check (`run_matchup_battles.py:305-315`).
Recommendation: add an optional `dedup_group` parameter to the skip check so stat changes self-heal like code changes; keep `--force` as an escape hatch. Precedent: `rebuild_matchup_baseline.py`'s resume table is already fingerprint-keyed. Bonus: also closes the loader-changes-outside-the-hash staleness hole. Caveat: future `unit_fingerprint` edits trigger a surprise full re-sim (correct, but hours of PyPy time).

#### Naval rankings are fossilized: no standing script regenerates them
**Severity:** low · **Effort:** S
Evidence: all 3,260 naval `battle_scores` rows at 177723 are value-identical to 170934 — pure carry-forward; `compute_naval_role_scores` lives only in the retired module and writes to the wrong DB. The gap is documented (`derived-data.md:201-202`) but unremediated — if a patch buffs a warship there is nothing to run.
Recommendation: clone `derive_siege_scores.py` (~115 lines, direct template) into `derive_naval_scores.py`; add one runbook line ("only if warship stats changed"). Skip the proposed cross-build staleness check — carry-forward makes rows identical by design.

#### advisor_recommendations (5,618 rows) is write-only
**Severity:** low · **Effort:** S
Writers: `derive_advisor_recs.py` + schema in `derived_db.py:34-45`; sole reader: its own test. The live advisor runs on-the-fly sims from `civ_power_units/<build>.json`. Archive the script + test, leave the committed rows, mark the DDL "parked/legacy" — see [Repo organization plan](#repo-organization-plan).
Verifier: deletion reverses a deliberately documented "parked" status and abandons deferred consolidation Task 16 Step 4 — propose to the user first. The rows are full 53-civ data (stale, not "Armenians-only").

#### Incremental patch re-sim degrades the multi-seed baseline and records sampling noise
**Severity:** low · **Effort:** M
Evidence: `patch_pipeline.py:124-125` re-sims changed units via `run_matchup_battles --force` (1–3 seeds), overwriting n=8..40 escalating-sampler rows; `diff_outcomes` `min_swing=1.0` is below contested-matchup noise. Also: `matchup_means` names two incompatible schemas (`rebuild_matchup_baseline.py:55` vs `patch_resim.py:48`), and `verify_flips` crashes on the baseline variant.
Recommendation: extract the escalating sampler into a shared helper used by `run_matchup_battles` under `--force/--changed-units` (upserting `matchup_means`); gate or loudly caveat `diff_outcomes` output behind an SE-aware threshold; rename `patch_resim`'s table; fix the runbook's `--matchup-db` example (it points at the legacy 1–3-seed patchwork DB).
Verifier: the 346 committed `patch_matchup_changes` rows are NOT artifacts — they came from `verify_flips` (up to 72 seeds). The risk is forward-looking: a future session following the runbook literally would publish noisy diffs, because the verify_flips correction lives only in a commit message and one doc line.

#### No pre-commit verification of the derived DBs
**Severity:** low · **Effort:** M
Evidence: a partial derive (rankings re-run, pool scores forgotten; or a forgotten `civ_power_units/<build>.json`, masked by the legacy-JSON fallback) can ship.
Recommendation: skip the full `derive_all` orchestrator; build only `webapp/verify_derived.py` (~100 lines) asserting `battle_scores`/`pool_scores` cover 53 civs at the current build, the per-build civ-power-units JSON exists, and build numbers agree; call it at the end of `patch_pipeline.run()` and list it in runbooks §1. Do **not** wire `derive_advisor_recs` into any automation.
Verifier: "nothing verifies before commit" was overstated — `test_pool_scores_api.py`/`test_naval_rankings.py` run against the live committed DBs and would catch the headline forgotten-pool-scores case; the uncovered failures are stale-not-missing rows and the masked JSON fallback.

#### patch_unit_ranking is empty for build 177723 — patch pages falsely show "Ranking unchanged."
**Severity:** medium · **Effort:** S
Evidence: `patches.db` has `patch_unit_changes=19`, `patch_matchup_changes=346`, `patch_unit_ranking=0`; `app.py:426-429` + `patch_unit.html:38-49` render "Ranking unchanged." for all 19 changed units. Re-running `matchup_diff.diff_rankings` returns 1,643 rows today.
Recommendation: backfill via `diff_rankings` + `write_patch_records` under patch_id 2 (filter `old_score IS NULL` rows; restrict to UI-surfaced score types); document that the numbers blend patch effect with the 06-07 multi-seed re-derive. Add the guard as a pytest (every patch with unit changes has ranking rows) — the data was written by an ad-hoc finalize script, so a warning inside `patch_pipeline.run()` alone would not have caught it.

### Webapp & frontend

#### favicon.png and og-default.png are referenced on every page but don't exist
**Severity:** medium · **Effort:** S
Evidence: `base.html:49` links `static/img/favicon.png`; lines 26/31 set og:image/twitter:image to `static/img/og-default.png` with `summary_large_image`. Neither exists anywhere; live prod 404s both; the files were never committed (unfinished task, not a removal).
Recommendation: create both (512 px favicon; 1200×630 og image), verify on staging with a Discord paste, remove the known-issue note at `webapp.md:111` (the trigger row at `:189` already prescribes this).

#### Role/line-slug sets exist in four copies with a (currently inert) mangonel drift
**Severity:** low · **Effort:** M
Evidence: `app.py:1024-1028` (mangonel in SIEGE), `compute_battle_scores.py:585-672` (mangonel in HIDDEN), `best_units.py:29-30` (a fourth copy the original finding missed), plus the JS `UNIT_LINES` mirror in `rankings.js`. Behaviorally inert today (mangonel is excluded everywhere it matters), but the `unit_lines.py` TODO acknowledges the trap.
Recommendation (slimmed): fix the stale "21 keys" docstring (the dict has 26); add a pytest comparing only the `rankings.js` `UNIT_LINES` subLines against `unit_lines.py` sub_lines (the JS `*_SLUGS` sets are intentionally different UI sets — do not compare them); defer the four-site `*_LINE_SLUGS` extraction until role-scoring code is next touched.

### Replay

#### REPLAY_ENABLED is set but never read
**Severity:** low · **Effort:** S
Evidence: `app.py:58-67` sets it in the blueprint-import try/except; nothing reads it — the nav tab (`base.html:90`) and `/replay` route render regardless, so an import-time failure of the pinned mgz fork yields a broken SPA with generic errors.
Recommendation: inject via a context processor (mirror `inject_footer_config`), gate the nav tab, render a one-line notice on `/replay` when False; update `replay.md:9`.
Verifier: the "dep fails to install" trigger is wrong for Railway (a build failure keeps the previous deploy live) — only import-time failures hit this, hence low severity.

#### Shared clip URLs die on every redeploy; runtime caches grow unbounded
**Severity:** low · **Effort:** M
Evidence: clips are written to gitignored `webapp/static/replay/clips/` on Railway's ephemeral filesystem; any `webapp/` push redeploys and 404s every shared `clip_url`. Neither `CLIP_DIR` nor the replay download cache has eviction.
Recommendation (cheap tier first): make `view_url` the primary share field, relabel `clip_url` as temporary, add a ~20-line mtime-based cap on both caches. Fuller fix only if shared clips matter for marketing: a regenerate-on-miss `GET /replay/clip/...` route — it must include `profile_id` (the aoe.ms download needs it), and a cold link blocks one of the 2 sync gunicorn workers for up to ~60 s.

#### Concurrent clip renders collide on a fixed .tmp.webm and can cache a corrupt clip
**Severity:** low · **Effort:** S
Evidence: `clip_export.py:536` writes to the fixed `out_path + '.tmp.webm'` with `ffmpeg -y` then `os.replace` — two concurrent renders for the same match share the tmp inode and can cache garbage.
Recommendation: unique temp name via `tempfile.mkstemp(dir=...)` (~5 lines, mirrors the correct `NamedTemporaryFile` pattern at `replay_core.py:1550`). Skip the lockfile and worker-count bump — with unique names a duplicate render just wastes CPU once.

### Ops & testing

#### No CI: the test suite (including the golden regression) only runs when someone remembers
**Severity:** medium · **Effort:** S
Evidence: `.github/workflows` does not exist; pushes auto-deploy ungated. The verifiers' smoking gun: `pytest` fails RIGHT NOW on clean checkouts of both `staging` and `main` — two golden regressions (`Aztecs_vs_Armenians_imperial`, `Spanish_vs_Berbers_imperial`) broke when 177723 data shipped without regenerating `.golden/baseline.json` (CLAUDE.md rule 8 silently violated for ~weeks, through a production promotion). The main sim-drift guard is currently disarmed.
Recommendation: (0) first confirm the drift is intentional, regenerate the baseline, commit on `staging` — CI added before this is born red; (1) one GitHub Actions workflow (ubuntu, Python 3.12 + Node 20): `pip install -r webapp/requirements.txt pytest`, `pytest -q`, `node tests/test_sim_params.js`, `node tests/test_frontend_projectile_miss.js` (no npm install; suite runs ~37 s from committed artifacts, no .dat/PyPy); (2) add the 8-line ENABLED_CIVS-vs-DB parity test and 200-smoke-tests for the genuinely untested routes (`/api/ref/civ`, `/api/ref/combat-unit`, a `/vs/` page, `/sitemap.xml`); (3) optionally enable Railway's "wait for CI" so red blocks staging deploys; (4) pin numpy and fork the `sanduckhan/aoc-mgz` tarball dependency under your own account (if that user deletes the fork, every Railway build breaks).

## Low-severity findings (not adversarially verified)

| Title | Area | Effort | Recommendation |
|---|---|---|---|
| Two `.claude` agent/skill docs route sessions to the legacy DB via a dead macOS path | agent tooling | S | Rewrite `running-simulations` SKILL.md:17 and `unit-stats-analyzer.md` to query `ref_units` in `aoe2_reference.db` with repo-relative paths |
| `sim_version` excluding `simulation.py` — verified non-issue | sim infra | S | No structural change; optionally one docstring sentence noting golden is the abstract engine's only guard |
| Engine tuning constants comment-coupled Python↔JS (~4 numbers) | sim engines | S | Have the planned JS ability test regex-extract and assert equality (MISS_SPREAD, smoothing 0.3, stuck threshold); no build step |
| `patches.db` is 98% free pages (6.2 MB for ~88 KB); `INSERT OR REPLACE` orphans child rows on re-run | patches.db | S | `VACUUM` + commit; add an `update-summary` CLI; switch `insert_patch` to UPSERT so patch_id stays stable |
| Fallback build `"170934"` hardcoded at 9 call sites | build versioning | S | Single `FALLBACK_BUILD` in `patches_db.py`; derive scripts should `sys.exit` when `get_current_build()` is None — only serving paths soft-fall-back |
| Mangonel line-set drift — finish the `unit_lines.py` extraction | unit_lines registry | M | Move the five `*_LINE_SLUGS` sets into `unit_lines.py` as single source (covers four sites); codify mangonel as hidden |
| Legacy `civ_power_units.json` (1.78 MB) = byte-identical 170934 snapshot, silent stale fallback | committed artifacts | S | Delete the flat file and the legacy-fallback branch in `load_civ_power_units`; fail loudly instead of serving 2-builds-old data |
| flask-cors installed but never imported; inconsistent pins | dependencies | S | Remove flask-cors from `webapp/requirements.txt` (+ `operations.md:33`); pin numpy/requests/Pillow/imageio-ffmpeg |
| SEO copy says "all 50 civilizations" in 5 places — site has 53 | templates / SEO | S | Fix the five templates, or expose `civ_count` via a context processor so it can't drift |
| Civ emblems load exclusively from a third-party CDN, no onerror fallback | frontend | S | One-time download of the 53 emblems into `static/img/civs/`, repoint `CIV_EMBLEM_BASE` (mirrors the unit-icon migration) |
| No request size limit on replay upload (`MAX_CONTENT_LENGTH` unset) | replay | S | `app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024` — one line; real .aoe2record files are single-digit MB |
| Stale refs: nonexistent `CLASSIFIER_REWORK.md` cited 3×; clip advertised 8× but rendered 4× | replay | S | Point the three refs at `docs/architecture/replay.md`; fix the two 8× strings (or derive from `SPEED`) |
| aocref degradation is a silent bare `except` | replay | S | `except Exception` + one `log.warning` in both helpers (the dependency itself IS shipped — verified) |
| Dead deployment artifacts: `webapp/Procfile`, misleading root `requirements.txt`, orphaned 2.4 MB root CSV | tooling | S | Delete the Procfile + `armenians_matchups.csv`; make root requirements a pointer to `webapp/requirements.txt` |
| `ORIGINAL_13_CIVS` naming/duplication | constants | S | Superseded by the confirmed three-copies finding above |

## Rejected findings

Recorded so future reviews don't re-raise them.

| Claim | Why refuted |
|---|---|
| CLAUDE.md contradicts the code on 5 load-bearing claims | Stale — commit `8406d91` (2026-06-09) already rewrote CLAUDE.md with all five corrections. Residual: `operations.md:82/174` still warn about the old CLAUDE.md text — a 2-line cleanup |
| App serves rankings benchmarks from the frozen `battle_scores.json` Tarkan stub | Stub payload is unreachable (no `tarkan` line key exists; live Tarkan scores come from `derived_data.db`); `battle_cache.json` is untracked; the state is intentionally documented deferral. The live cleanup path is the confirmed "retired battle-scores chain" finding |
| `webapp/matchup_db.db` being committed violates CLAUDE.md rule 6 | Misreading of a rule already fixed in `8406d91`: "never commit" applies to the 200+ MB external baselines; the 3.9 MB snapshot is deliberately tracked (rule 7 deploy list). The recommended `git rm` would break documented defaults |
| `/api/top-units`, `top_units.py`, and `civ_top_units.json` are dead weight | Deliberate 4-day-old feature (imperial-only simplification Phase 1); documented smoke-check step in the patch workflow; Claude/operator lookups are the intended consumer |
| `PLAYER_COLORS` duplicated; replay command-sets should be unified | Palette divergence is intentional and documented (CLAUDE.md sync rule 4); the command-set copy is load-bearing — it is the fallback for exactly the case where `unit_classifier` fails to import |

## Repo organization plan

**Guiding constraint (verified):** the import topology is load-bearing: `railway.json` runs `cd webapp && gunicorn app:app` (flat imports; `app.py` must stay put); `tests/conftest.py` inserts `../webapp` and imports bare; every batch/derive script self-inserts its own dir so both `python webapp/foo.py` and `python -m webapp.foo` work; `watchPatterns: ["webapp/**"]` means anything moved out of `webapp/` stops triggering redeploys.

> ⚠ **`sim_version.py` hashes the byte content of `webapp/simulation_real.py` + `analysis/config_combat.py`.** Any edit — even a comment or docstring — invalidates all 491k baseline rows. Renames are safe (content hash; update `DEFAULT_FILES`), but every docstring pass MUST skip these two files.

### webapp/ flat-directory sprawl (31 .py files)

Verdict: **naming/docstring taxonomy, not subpackages** (moves are phase-3 optional). Moving e.g. `derive_pool_scores.py` into a subdir breaks ~6 touchpoints per file × ~12 files (`_here` inserts, `python -m` invocations in runbooks/memory docs, bare test imports, `patch_pipeline.py` subprocess strings). Instead, document the existing conventions (`derive_*` = offline job writing a derived DB; `*_db` = schema+IO; `*_lib` = pure functions; `*_query` = serve-time reader; `patch_*`/`*_diff` = patch tooling; `run_*`/`rebuild_*` = PyPy batch runners) and add a grep-able `Role:` tag as the first docstring line of each file (serving | engine | batch-runner | derive | patch-tooling | replay | legacy).

Phase-3 option: move the 12 offline-only files into `webapp/jobs/`. Side benefit: batch runners stop pointlessly triggering Railway redeploys.

### Misleading / inconsistent names

| Name | Finding | Verdict |
|---|---|---|
| `simulation.py` vs `simulation_real.py` | Names convey nothing; 2 vs 10+ importers + sim_version hash | **Keep names; fix via docstrings** ("Engine 1 of 3: ABSTRACT…" / "Engine 2 of 3: POSITION-BASED…") — `simulation_real.py`'s docstring must wait for the next forced full re-sim; at that point optionally rename → `sim_abstract.py`/`sim_position.py` (~16 refs + docs + skills + memory) |
| `templates/deprecated-civ.html` | Serves the LIVE `/civilizations/<civ>` page (`app.py:526`); `civ_detail.html` serves the selector (`app.py:518`). Inverted | **Rename both in one commit**: `civ_detail.html` → `civ_overview.html`; `deprecated-civ.html` → `civ_detail.html`. One `render_template` ref each |
| `templates/index.html` | Serves `/units`, not `/` | **Rename → `rankings.html`** (matches rankings.css/js). One ref (`app.py:511`) |
| `derived_db.py` | Confusable with `derive_*` jobs | Keep (optional rename, marginal) |
| `pool_scores_db/_lib/_query` | Clean three-way split, each with a matching test file | **Keep as-is** — the convention to converge on |
| `best_units.py` (1,640 lines) | Two unrelated features: civ-power-units compute/persist (lines 20–1064) + live Matchup Advisor recs/sims (1087–end) | **Split justified but phase-3**: → `civ_power_units_lib.py` + `matchup_advisor_api.py` with `best_units.py` as a re-export shim (golden imports `best_units.get_matchup_sims` — the shim keeps golden unchanged) |
| `ORIGINAL_13_CIVS` | Two copies, both 53 entries: `app.py:682` dead; `analysis/config_constants.py:81` LIVE | **Delete** the app.py copy (phase 2). Derive the analysis copy from `CIV_NAMES` (see the confirmed finding); rename → `PIPELINE_CIVS` optional (+2 use sites; `config.py` re-exports via `*`). Verify by import-check only — **NO DB regen** (a full regen rewrites combat-prop cols on all rows) |

### Dead or completed scripts → .old/

| Candidate | Evidence | Disposition |
|---|---|---|
| `webapp/migrate_baseline.py` | NOT dead: `test_versioning.py` imports it; `patch_pipeline.py:181` names it as the fresh-checkout bootstrap | **Keep** + one docstring status line |
| `webapp/compute_battle_scores.py` | Retired pipeline but LIVE library (siege import + 3 test files) | **Phase 1: keep + RETIRED banner docstring.** Phase 3: extract scoring lib, archive the rest — see the confirmed finding |
| `webapp/derive_advisor_recs.py` | Output read by nothing; only deriver with NO `--matchup-db` flag (reads the Armenians stub) | **Archive to `.old/webapp/`** with `tests/test_advisor_derive.py`; leave table rows; mark DDL "parked/legacy" in `derived_db.py`. Propose first — abandons deferred consolidation Task 16 Step 4 |
| `simulate_mixed_battle` (`simulation.py:2310`→3169) | Zero callers; last ~860 lines of the file | **Delete in phase 2** (not hashed into sim_version; cannot affect golden) |
| `NO_ELITE_UNITS` (`generate_main_db.py:45`) | Never referenced; comment actively false | **Delete in phase 2**; no DB regen needed |
| `analysis/patches/patch_mayan_archer_cost.py` | Re-applied by patch_pipeline | **Keep** |
| `scripts/build_reference_docs.py` | Active, tested by literal relative path | **Keep** |
| `armenians_matchups.csv` (root, tracked, 2.4 MB) | One-off export from the per-civ batching era | **git rm → `.old/`** |
| `webapp/battle_scores.json` stub | Loaded at startup; fallback branch unreachable | Leave; phase-3 removal with its `app.py` loader branch |

### Top-level folders

`scripts/` (1 file): keep — a test loads it by literal path. `reference/` (190 generated .md): keep committed — its purpose is post-patch diffing. `graphics/`, `scenario_builder/`, `marketing/`: fine. Docs convention going forward: new plans/specs → `docs/plans/` (`YYYY-MM-DD-name-{plan,design}.md`); audits → `docs/audits/`; the `superpowers/` split is a tooling artifact — leave history in place; optionally add a 5-line `docs/README.md`. The untracked-root-scratch sweep originally listed here was **already done 2026-06-09** (commit `857acbd`).

### Module-docstring audit

`analysis/` and `extraction/` are fully covered. Missing: `webapp/app.py`, `static/js/simulate.js` (a header is safe for the brace-matching test, which seeks `class BattleUnit`), `static/js/constants.js`. Stale: `unit_lines.py` ("21 keys" → 26), `.golden/capture_baseline.py` (claims a section that doesn't exist; references a long-merged branch), `unit_classifier.py` + `replay_core.py:1005` (nonexistent `CLASSIFIER_REWORK.md` → point at `docs/architecture/replay.md`), `replay_core.py` ("Flask server" → Blueprint), `compute_battle_scores.py` (RETIRED banner), `derive_pool_scores.py` (add the canonical `--matchup-db` command + warning), `migrate_baseline.py` + `derived_db.py` (one status line each).
⚠ **Exclusions: `simulation_real.py` and `config_combat.py`** (sim_version byte-hash — see the warning above).

## Phased roadmap

### Phase 1 — zero risk

- Regenerate `.golden/baseline.json` (suite is red on both branches); commit on staging → [No CI](#no-ci-the-test-suite-including-the-golden-regression-only-runs-when-someone-remembers)
- Docstring pass + `Role:` tags — **skip `simulation_real.py`/`config_combat.py`** → [Docstring audit](#module-docstring-audit)
- `git rm --cached` + gitignore the 488 upscaled sprite PNGs; push staging; fix `operations.md:158`; local `git gc` → [Graphics](#260-mb-of-unconsumed-artsprites-tracked--stop-the-churn-do-not-rewrite-history)
- Create `favicon.png` + `og-default.png` → [Favicon/OG](#faviconpng-and-og-defaultpng-are-referenced-on-every-page-but-dont-exist)
- Seed the advisor RNG (`get_matchup_sims` / `get_matchup_recommendations`) → [Unseeded RNG](#live-matchup-advisor-endpoints-are-non-deterministic-unseeded-rng)
- Fix cost-weight drift (delegate to `weighted_cost`; regen golden) → [Cost-weight drift](#cost-weight-drift-best_units-uses-wood-08-while-the-other-two-copies-use-07)
- Fix Cumans/Dravidians Imperial availability in `config_units.py` (upgrade-gating variant) → [Missing rows](#cumans-camel-rider-and-dravidians-battle-elephant-are-missing-from-imperial-age-entirely)
- Derive-script guardrails: required `--matchup-db`, advisor flag, civ-count + sim_version checks → [Stub default](#derive-scripts-default---matchup-db-to-the-committed-armenians-only-stub)
- GitHub Actions workflow (pytest + node tests); pin numpy; fork the aoc-mgz tarball → [No CI](#no-ci-the-test-suite-including-the-golden-regression-only-runs-when-someone-remembers)
- Backfill `patch_unit_ranking` for 177723 + coverage pytest → [Empty table](#patch_unit_ranking-is-empty-for-build-177723--patch-pages-falsely-show-ranking-unchanged)
- Archive `derive_advisor_recs.py` + its test (propose first); `git rm armenians_matchups.csv` → [Archival table](#dead-or-completed-scripts--old)
- Fix "50 civilizations" copy; SEO/template touch-ups → [Low-severity table](#low-severity-findings-not-adversarially-verified)
- Quick replay hardening: unique tmp name in `_encode`; `MAX_CONTENT_LENGTH`; aocref logging; 8×→4× strings → [Replay](#replay)
- Docs-convention note (`docs/plans/`, `docs/audits/`); root scratch sweep already done (`857acbd`) → [Top-level folders](#top-level-folders)

### Phase 2 — low-risk deletions/renames (grep-verify zero stale refs before each commit)

- Delete `ORIGINAL_13_CIVS` from `app.py`; derive the analysis copy from `CIV_NAMES` (rename optional); import-check only, no DB regen → [Three copies](#the-53-civ-list-exists-in-three-copies-one-is-dead-one-is-mechanically-derivable)
- Delete `simulate_mixed_battle` (+ fix the comment at `simulation.py:459`, keep `EXTRA_PROJ_ACCURACY`) → [Dead lines](#simulate_mixed_battle-860-dead-lines-27-of-simulationpy)
- Delete `NO_ELITE_UNITS`, `UNITS_BY_AGE`, `AGE_NAMES`, stranded comments → [False comments](#dead-code-with-actively-false-comments-no_elite_units-units_by_age-age_names)
- Template renames: `index`→`rankings`, `civ_detail`→`civ_overview`, `deprecated-civ`→`civ_detail` → [Renames table](#misleading--inconsistent-names)
- Orphan-key test for `config_combat.py` + delete the pointless keys (keep the roster-conditional allowlist) → [Orphan keys](#21-orphan-keys-in-config_combatpy-match-nothing-in-the-ref-db)
- `dedup_group`-aware skip check in `run_matchup_battles` → [Stat-only patches](#stat-only-patches-dont-invalidate-matchup-rows--correctness-depends-on-remembering---force)
- Combat-dict passthrough + contract test → [Contract](#combat-dict-contract-is-unvalidated-simulationprepare_combat_unit-silently-drops-position-engine-keys)
- `derive_naval_scores.py` (clone of the siege deriver) → [Naval](#naval-rankings-are-fossilized-no-standing-script-regenerates-them)
- `verify_derived.py` + wire into `patch_pipeline.run()` → [Verification](#no-pre-commit-verification-of-the-derived-dbs)
- Frontend ability tests + pytest node-wrapper → [Parity](#three-engine-ability-parity-is-hand-maintained-with-asymmetric-test-coverage-13--7--0)
- Replay polish: `REPLAY_ENABLED` context processor; cache caps + view_url-first share field → [Replay](#replay)

### Phase 3 — optional restructure

- `best_units.py` split → `civ_power_units_lib.py` + `matchup_advisor_api.py` with re-export shim → [Renames table](#misleading--inconsistent-names)
- Extract `siege_naval_scoring.py` from `compute_battle_scores.py`; delete `test_infantry_scoring.py` + superseded scoring; archive the remainder → [Battle-scores chain](#retired-battle-scores-chain-still-entangled)
- Remove the `battle_scores.json` stub + `app.py` loader branch + `-999` else-branch → [Battle-scores chain](#retired-battle-scores-chain-still-entangled)
- `webapp/jobs/` subpackage for the 12 offline-only files (~6 touchpoints each) → [Sprawl verdict](#webapp-flat-directory-sprawl-31-py-files)
- Engine renames (`sim_abstract.py`/`sim_position.py`) + `simulation_real.py` docstring — **bundled with the next forced full re-sim only** → [Renames table](#misleading--inconsistent-names)
- Retire `aoe2_units.db` + `generate_main_db.py` after migrating `scenario_builder` and `/units` → [Stage 3](#aoe2_unitsdb-stage-3-is-95-dead-weight-kept-alive-by-one-offline-tool)
- Escalating-sampler unification + `patch_means` rename → [Re-sim noise](#incremental-patch-re-sim-degrades-the-multi-seed-baseline-and-records-sampling-noise)
- Mangonel `*_LINE_SLUGS` consolidation into `unit_lines.py` (when role-scoring is next touched) → [Line slugs](#roleline-slug-sets-exist-in-four-copies-with-a-currently-inert-mangonel-drift)

## Do-not-touch list

- **Never rewrite pushed history.** The graphics blobs are already on `origin/main`; a local rewrite breaks ff-only promotion and shrinks nothing. Promotion stays `git merge --ff-only staging`.
- `webapp/app.py` location and flat imports (`railway.json` startCommand, Procfile).
- **`simulation_real.py` + `analysis/config_combat.py` byte content** (sim_version hash → 491k baseline rows). No docstring/comment edits outside a forced full re-sim.
- All committed serving data: `webapp/*.db`, `civ_power_units/`, `civ_top_units.json`, `train_times.json`, `players.csv`, the `battle_scores.json` stub (until phase 3), `webapp/patch_notes/`.
- `webapp/static/**` paths; the `scripts/build_reference_docs.py` path (a test loads it literally).
- `.golden/baseline.json` — regenerate only on intentional sim change, never hand-edit.
- The `webapp/**` watchPatterns implication: files moved out of `webapp/` stop triggering Railway redeploys.
- `PLAYER_COLORS` divergence and the replay legacy command-set copies (intentional — see rejected findings).
- `/api/top-units` + `civ_top_units.json` (documented smoke-check/operator feature — see rejected findings).

## Update triggers

| When | Update |
|---|---|
| An item here is completed | Strike or delete the entry and sweep the doc touchpoints listed in its finding |
| A new review/audit runs | Check the [Rejected findings](#rejected-findings) table first so refuted claims aren't re-raised |
| Next forced full re-sim | Execute the bundled phase-3 items: engine renames + `simulation_real.py` docstring |
| Next game patch / DLC | Re-verify the Cumans/Dravidians fix landed; confirm the new-civ runbook now covers `config_constants.py` |
| `.golden/baseline.json` regenerated | Re-check the "suite is red" quick win is resolved and CI (once added) is green |
