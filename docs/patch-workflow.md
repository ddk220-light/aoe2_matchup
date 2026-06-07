# End-to-End Patch Workflow

How to take a new Age of Empires II:DE balance patch from the game's `.dat` all the way
to the deployed site (rankings, matchup advisor, patch page) — and keep the matchup
baseline trustworthy.

See also: [`matchup-baseline.md`](matchup-baseline.md) for the baseline methodology.

---

## 0. Branches (always)

| Branch    | Role |
|-----------|------|
| `staging` | All work lands here. Auto-deploys to the staging URL. |
| `main`    | Production. **Frozen** — only updated by `git merge --ff-only staging`. Never commit directly. |

Promotion is **fast-forward only**. If `--ff-only` refuses, the branches diverged — stop
and reconcile (a parallel session may have pushed; merge `origin/staging` into staging,
then ff main). Don't `git push origin main` unless the change has been smoke-tested.

The big sim-data DBs are committed (`aoe2_reference.db`, `aoe2_units.db`, `derived_data.db`,
`pool_scores.db`, `civ_power_units/<build>.json`, `patches.db`) — that's how each env
deploys its data. **`matchup_db.db` and the matchup baseline DB are NOT committed**
(too large); they're local caches / baselines-of-record.

---

## 1. Get the new `.dat`

Copy `empires2_x2_p1.dat` from the local AoE2:DE install into `extraction/`.

## 2. Re-extract → JSON  (needs `genieutils-py`; the conda python has it)

```
python -m extraction.run            # ~10s -> extraction/extracted_data/*.json
```

The pipeline archives the previous extraction + ref as the "before" for diffing.

## 3. Rebuild the reference DB  → `aoe2_reference.db`

```
python -m analysis.generate_reference        # ~30s, full audit trail
```

Then the **two correctness guards** that the raw extraction needs:

- **Phantom availability** — the availability model is a *blocklist* (a civ trains a unit
  unless its make-avail tech is in `disabled_techs`). Recent `.dat`s do NOT disable
  several "allowlist" lines (eagle, camel, champi, elephant, elephant archer, slinger,
  steppe lancer, fire lancer, paladin), so the blocklist lets every civ train them.
  `analysis/config_units.py` `_AVAILABILITY_OVERRIDES` pins each to its authoritative
  `civ_only` list. **If a new build adds/changes units or civs, re-validate these lists
  against SiegeEngineers `data/data.json`** (per-civ `Unit` lists, checked per upgrade
  tier — Cumans have Camel Rider but not Heavy Camel, etc.).
- **Surgical stat patches** the extraction can't get right:
  ```
  python -m analysis.patches.patch_mayan_archer_cost      # idempotent; restores full Mayan archer discount
  ```

## 4. Rebuild the main DB  → `aoe2_units.db`

```
python -m analysis.generate_main_db          # ~2s, flat unit_stats
```

Order note: `generate_main_db` reads the ref, so run the surgical ref patches **before**
it (or re-run it after) so `aoe2_units.db` matches `aoe2_reference.db`.

## 5. Verify availability

Spot-check a few civs against SiegeEngineers: no phantom units, correct per-civ top tiers
(`/api/top-unit/<civ>/<line>` should match — Koreans knight → Cavalier, etc.).

## 6. Re-sim matchups — choose full vs incremental

- **Full rebuild (clean baseline)** — when the sim engine changed, or you want a fresh
  trustworthy baseline:
  ```
  pypy3 -m webapp.rebuild_matchup_baseline --out D:/AI/matchup_baseline.db --workers 12
  ```
  ~4.5 h. Use `D:/AI/baseline_runner.py` (auto-restart) + `D:/AI/baseline_watchdog.py`
  (monitor/stop) for unattended runs. Preserve the result as
  `matchup_baseline_<build>.db` (baseline-of-record for future diffs).
- **Incremental (stat-only patch)** — only re-sim matchups touching changed units; keep
  the rest:
  ```
  pypy3 -m webapp.run_matchup_battles --force --changed-units changed_units_<build>.json --db <matchup_db>
  ```
  Much faster. The `--changed-units` JSON is the set of slugs whose stats changed
  (produced by the ref_units diff in `patch_pipeline`).

**Reliability rule:** never trust single-seed results for contested matchups. The baseline
uses the escalating multi-seed sampler and tags near-even fights `tossup`. Don't report a
toss-up as a confident win/loss.

## 7. Re-derive rankings (build-versioned)

Point the derive scripts at whichever matchup DB you produced in step 6:

```
python -m webapp.derive_unit_rankings --matchup-db <db> --build <build>     # battle_scores
python -m webapp.derive_pool_scores  --matchup-db <db> --out webapp/pool_scores.db --build <build>
python -c "import sys; sys.path.insert(0,'webapp'); import best_units; best_units.save_civ_power_units('<build>')"
```

`patch_pipeline.carry_forward_battle_scores` first copies the prior build's naval/siege
rows forward so the new build is a complete snapshot before land rows are re-derived.

## 8. Patch records + patch page

`webapp/patch_pipeline.py` orchestrates the diff + records:

- ref_units diff → `patch_unit_changes` (stat deltas) + the changed-slug set.
- matchup diff (before vs after, multi-seed via the verifier) → `patch_matchup_changes`
  with `old/new_winner`, scores, swing.
- ranking diff → `patch_unit_ranking`.
- inserts the `patches` row (summary_md, source_url, baseline_build), flips `is_current`.

The patch page (`/patches`) renders the pasted notes with **each changed unit's matchup
table inlined after its bullet** (collapsible, first open, ≤5 distinct-opponent matchups,
single scale, no same-line mirrors, no scorpions), showing each civ's **actual** unit
name (resolved from `ref_units`, not the line slug).

## 9. Verify → ship

```
PORT=5002 python3 webapp/app.py     # smoke-test rankings, advisor, patch page locally
```

Commit on `staging`, push, verify on the staging URL, then promote:

```
git checkout main && git merge --ff-only staging && git push origin main && git checkout staging
```

(Stash the noisy `webapp/matchup_db.db` modification before switching branches.)

---

## Gotchas learned (don't relearn these)

- **Sim non-determinism** → single-seed is unreliable for contested matchups. Use the
  escalating multi-seed baseline; surface `tossup` for near-even. More sims will NOT turn
  a genuine coin-flip definitive — that's the correct answer.
- **Full pipeline regen rewrites combat-prop columns on ALL rows.** For a *targeted* unit
  fix, patch rows surgically. For a new build, a full regen is expected — but **diff the
  result** to confirm only the intended rows changed (watch for unrelated drift).
- **`matchup_db.db` can be a patchwork of sim-engine versions.** Re-deriving from it mixes
  versions and changes unrelated rankings. A single clean baseline run avoids this.
- **PyPy SQLite**: use `isolation_level=None` (autocommit) for batch writers, or commits
  fail with "cannot commit — SQL statements in progress."
- **Unattended runs need auto-restart, not just detection.** A detect-and-stop watchdog
  leaves a crashed run idle for hours. Pair it with a resuming runner.
- **CPU**: 12 workers (= physical cores) is the thermal-safe sweet spot (~60% CPU) for
  CPU-bound sims; HT beyond that adds heat, not throughput. Core temp isn't readable
  without admin / LibreHardwareMonitor — the worker cap is the safeguard.
- **GPU can't help** this engine without a full vectorized rewrite + re-validation.
- **Build-version everything**: `battle_scores`, `pool_scores`, `civ_power_units/<build>.json`,
  `patches.db`. The UI reads the current build (`patches_db.get_current_build`).
- **Eagle line is Aztecs/Mayans only** per SiegeEngineers + the clean baseline (Incas
  excluded). Flagged in case it should include Incas — re-confirm if revisiting.
