# Matchup timings: restart here

This branch contains the army-economics implementation, reviewed inputs,
production and research extraction, gathering simulations, online references,
historical experiment results, runtime database, UI integration and tests.
It branches from `0efe51cb4` on `feature/matchup-advisor-context`, originally based
on `simulations/civ-forecast-validation-2026-11-07`. It does not rerun the combat
campaign or replace saved matchup outcomes.

## Run the feature from a fresh checkout

```sh
git clone --branch matchup-timings https://github.com/ddk220-light/aoe2_matchup.git
cd aoe2_matchup
python3.12 -m venv .venv
.venv/bin/python -m pip install -r apps/website/requirements.txt -r tools/requirements-economy.txt pytest
ARMY_ECONOMICS_MODE=review .venv/bin/python -m flask --app apps.website.app run --port 5055
```

Open `http://127.0.0.1:5055/`. Select both civilizations and units on Battle
Simulation. Each team has investment, replacement-work and production summaries;
expand the comparison below the arena for upgrades, bonuses and assumptions.
The committed runtime database works immediately; source restoration is only
needed for rebuilding or inspecting the upstream research databases.

The feature defaults to `off`. `review` enables estimates; `released` additionally
requires the current release gate to pass. Neither setting deploys anything.
The current database passes the user-approved gate, but its gathering rates are
estimates: the API reports `status: estimate`, not measured validation.

## Restore the captured data and reproduce the runtime database

Two review databases exceed GitHub's 100 MiB file limit. Their adjacent `.sqlite.gz`
files preserve every byte. The restore utility verifies SHA-256 and length,
skips identical files and refuses to overwrite changed files.

```sh
.venv/bin/python tools/restore_army_economics_data.py
.venv/bin/python tools/build_army_context_runtime.py --require-release-ready
```

This restores both historical review databases and compiles the current
`army-context-2026-11-10` snapshot into `data/golden/army_context.db` and its
`.validation.json` report. The runtime has 56 civilizations and 1,031 profiles
(1,030 unit variants plus the War Chariot barrage mode).

For all captured upstream production, research and economy inputs:

```sh
.venv/bin/python tools/restore_army_economics_data.py --include-sources
```

This also restores 192 source/review files under
`data/local/army-economics/scratch/`. Three compressed source archives, their
inventory and checksums are in
`aoe2x/js_simulation/calibration/economy/handoff-data-2026-11-12/`.
The bundle includes decoded DAT snapshots, matching civilization tech trees,
unit/form/projectile research links, intermediate SQLite databases, CSVs and
review notes. Redundant ZIP bundles, environments and logs are omitted. Original
game DAT/graphics remain excluded under the repository's existing policy; their
decoded analysis inputs are included.

Historical Python extraction tools now default to these portable restored paths.
`ARMY_ECONOMY_SCRATCH` can select another scratch root. To re-extract from the
original game file, install `genieutils` and set `ARMY_ECONOMY_DAT` to its local
path. The captured DAT hash is
`d0aefd92428e2215d6f4d9b1d544901e6f171e19183f9e0b88218de5153a337f`.
The original executable build is not established; patch 188329 changes are present.
Absolute paths inside historical JSON are provenance, not fresh-checkout requirements.

## What is authoritative

| Layer | Files / purpose |
| --- | --- |
| Current specification | [army-economics.md](army-economics.md): accounting, API/UI contract, assumptions and exceptions |
| Runtime accounting | `aoe2x/army_economics.py`: batch purchases, weighted labor LP/dual, 60-second building requirement, research comparisons |
| Compiler | `tools/build_army_context_runtime.py`: provenance checks, source joins, modifiers, route choices, precomputed lookups and validation report |
| Reviewed source | `aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/army-context.sqlite` after restore |
| Special economy | `tools/special_economy.py`, `tools/run_special_economy.mjs`, `tools/army_context_policy.py` |
| Gathering engines | `tools/farm-gathering-sim.mjs`, `wood-gathering-sim.mjs`, `gold-mining-sim.mjs` |
| Source extraction | `tools/build_production_review.py`, `build_upgrade_review.py`, `build_economy_review.py`, `build_labor_inputs_review.py` |
| Page/API | `apps/website/services/army_context.py`, `routes/battles.py`, `static/js/battle/army-economics.js`, team-panel partial and playback integration |
| Research history | All dated folders under `aoe2x/js_simulation/calibration/economy/`: plans, CSVs, references, simulation outputs, screenshots and playback HTML |

Dated reports are historical. Their earlier blocker counts and provisional
recommendations are superseded by `data/golden/army_context.validation.json`,
`tools/army_context_policy.py` and the current specification. The raw source
review database is preserved; subsequent corrections live in the runtime compiler.

## Calculation and accepted decisions

The headline is **60-second army investment**, measured in weighted
villager-minutes. Combine (1) the displayed army's batch-rounded purchase bill,
(2) buildings required to train it within 60 seconds, and (3) net cost of
technologies common to both units. Apply food ×1, wood ×1, gold ×1.5 and stone ×3,
then minimize villager work over the civilization's resource-output vectors.
Recurring farm/pasture wood is a negative output, so funding food also requires
woodcutting. Coproduct resources meet the combined bill once, with no resale credit.

For each route, orders per building = `floor(60 / training_seconds)` and buildings
required = `ceil(purchase_orders / orders_per_building)`. Choose the route with
the lowest combined weighted work. Queues start with buildings and resources
ready. Physical building construction, rally travel and research queue elapsed
time are separate. Exclusive research costs and full/common research workloads
remain separately visible. Missing upgrades never become a research-speed bonus.

Live replacement work follows visible playback casualties, reuses starting
infrastructure and batch surplus, and does not charge upgrades again. It counts
mounted Konnik loss once, ignores reversible forms and auxiliary units, and
consumes every crossed snapshot even at high playback speed. Combat trajectories
remain independent of these estimates.

Final accepted assumptions as of 2026-11-12:

- Post-Imperial, all available upgrades, own civilization/team effects only.
- Timed gold only while actively gathering; full applicable aura coverage with
  no placement requirement or aura-building investment. Folwark coverage remains
  the reviewed eight of ten farms.
- Khitan pasture: immediate food credit; approximately 25.2 food per villager-minute
  from a published Hand Cart lifecycle test. It already includes rebuilding;
  renewal costs use the DAT's 110 wood per 1,035 food. This is a historical online
  proxy for post-Imperial, not a current-build accuracy claim.
- Controlled in-game gathering measurements are deferred. Their catalog remains
  available for future work; the present feature does not claim less-than-1% error.
- Berber Xebec and Chinese Fire Ship training routes, Flemish Revolution cost
  verification and Wei Tuntian income are explicitly excluded by the user.
- Four verified unit-price corrections apply to army-count resolution and labor
  together. Existing saved combat results are unchanged.

## Continue the work

For accounting/UI changes, use the committed runtime and Python/JS tests below.
For economy changes, inspect the reviewed source and evidence, update the relevant
model, rerun only affected simulations, then compile the runtime. The special
scenario file carries input/engine hashes and compilation rejects stale results.

```sh
node tools/run_special_economy.mjs
.venv/bin/python tools/build_army_context_runtime.py --require-release-ready
```

For a full reviewed-layout gathering rerun, set the output explicitly; some older
research scripts otherwise default to their original November 9 experiment:

```sh
ARMY_CONTEXT_OUT="$PWD/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10" node tools/run_army_economy.mjs
```

That refreshes base simulation outputs, not the source review tables automatically.
Use `build_army_context.py` and `review_late_game_economy.py` for source-ledger
reconstruction only after inspecting their input/output settings; those are
historical offline research steps. Do not overwrite the captured snapshots just
to experiment. Never resume the stopped full matchup recomputation.

## Checks

Use Python 3.12 and Node 22+ (the current checks ran on Node 24). Runtime needs
Flask; SciPy is an offline compiler/test dependency only.

```sh
.venv/bin/python -m pytest -q tests/test_special_economy.py tests/test_army_economics.py tests/test_army_observations.py tests/test_patch185872_battle_config.py
node --test --test-isolation=none tests/army_economics.test.mjs tests/battle_selection.test.mjs
```

For browser checks, install Playwright and Chromium, run the local server above,
and use:

```sh
QA_URL=http://127.0.0.1:5055 CHROME_PATH=/path/to/chromium node tests/browser/army-economics.cjs
```

The last feature verification passed 72 Python tests, six JavaScript tests and
desktop/mobile browser flows, including 64× Konnik playback, batch purchases,
pause/restart, pasture estimates and context-failure fallback. Unit tests also
check fixed-seed combat trajectories. New work should rerun the relevant checks.
