# AoE2 Matchup

**Explore civilizations, compare units, and watch battles unfold.**

This is the repository behind **[aoe2matchup.com](https://aoe2matchup.com)**:
an Age of Empires II: Definitive Edition website backed by extracted game data,
published unit rankings, and a shared JavaScript combat engine.

The codebase also includes tools for running controlled matchups in the real
game, recording observations, and comparing them with simulated outcomes.
It is both a player-facing website and a toolkit for understanding AoE2 combat.

## What the website offers

- **Battle Simulation** — select a civilization and unit for each side, choose
  independent resource budgets or unit counts (up to 27 per side), and watch
  the fight in the isometric Golden Arena. Includes animated units, projectiles,
  play/pause, speed controls, randomized restart, and an optional ranged-unit buffer.
- **Matchup-specific statistics** — remaining units and HP, team health bars,
  damage per hit, damage per second, estimated one-on-one time to kill, and
  relevant bonuses or special mechanics.
- **Civilization Overview** — explore the available civilizations, descriptions
  and building-grouped unit rosters, with links to their tech trees and wiki pages.
- **Unit Rankings** — compare published scores across infantry, ranged, cavalry,
  siege and naval categories, with explanations of the scoring methodology.
- **Responsive presentation** — layouts for phones and laptops, light/dark themes,
  and shareable civilization and matchup URLs.

The **Matchup Advisor** and **Patch pages** remain implemented and accessible
through their existing routes, but are hidden from the primary navigation.
Replay-analysis and video-automation tools are also retained in the repository;
they are not the current public battle simulator.

## How it works

```text
AoE2 game data
    -> extraction and reference-data generation
    -> versioned SQLite statistics + validated runtime mechanics
         -> Flask services -> HTML pages and JSON APIs
         -> shared V3 engine -> browser playback or Node batch results

Controlled live-game captures -> comparison and validation evidence
Published ranking results + methodology -> website ranking pages
```

The website uses **Flask and SQLite**. Battles run in a **browser Web Worker**
using the same **V3 JavaScript engine** that runs headlessly in Node.js.
The renderer consumes simulation snapshots; animation does not determine damage
or change the battle outcome.

V3 models reusable combat mechanics: movement, collision/overlap, targeting,
attack timing, projectiles, supported special abilities, and scenario diplomacy.
Unit mechanics come from validated runtime profiles rather than a separate
frontend set of hand-maintained combat stats.

Rankings are **published data**, not recalculated whenever a visitor opens a page.
Their accompanying metadata identifies the source engine, opponents, settings,
weights and normalization. Some categories retain historical ranking results;
they are not silently described as new V3 results.

## Useful parts to explore or build on

| If you want to… | Start here | What it provides |
| --- | --- | --- |
| Build an AoE2 data explorer or compare civilization-specific stats | [Reference data](data/golden/README.md), [database generators](aoe2x/dbgen/) | SQLite datasets and the code that generates fully upgraded reference statistics and runtime mechanics. |
| Run battles without the website | [V3 runtime](aoe2x/js_simulation/src/), [Node runner](aoe2x/js_simulation/node/headless-runner.mjs) | Seeded simulation, parallel workers, outcomes and deterministic event/final-state hashes. |
| Embed or adapt a battle viewer | [Golden Arena renderer](aoe2x/js_simulation/viewer/map-renderer.js), [playback modules](apps/website/static/js/battle/) | Snapshot-driven rendering, playback, worker lifecycle and team statistics, separate from combat rules. |
| Build another UI or consume matchup configuration | [Website services](apps/website/services/), [feature routes](apps/website/routes/) | Shared battle configuration, reference-data access, civilization analysis and ranking services behind HTML/API adapters. |
| Understand or extend ranking publication | [Ranking tools](aoe2x/rank/), [published methodology](data/golden/derived_data_v3.metadata.json) | Serving-database construction and explicit provenance for the displayed scores. |
| Compare simulations with the real game | [AOE2 Lab guide](docs/aoe2-lab.md), [lab package](aoe2x/lab/) | Configurable matchup plans, live captures, simulation batches, comparison outputs and optional Tailnet viewing. |
| Analyze recorded games | [Replay tooling](aoe2x/replay/), [legacy viewer host](apps/viewer/) | Replay classification and viewer components retained independently of the public site. |
| Inspect the original data pipeline | [Extraction](aoe2x/extract/), [gRPC tools](aoe2x/grpc/) | Game-data extraction and live observation tooling for research workflows. |

These are practical entry points, not a promise that every directory is a
standalone packaged SDK. Browser rendering needs its assets and scenario data;
live capture requires a configured game installation and local credentials.
See the component documentation before moving a module into another project.

## Run the website locally

Use **Python 3.11+** and **Node.js 22+** for the current development/test setup.
A game installation is not required to serve the committed website data or
run the JavaScript simulator.

From the repository root:

```bash
python -m venv .venv
# Activate the environment:
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

python -m pip install -e .
python -m pip install -r apps/website/requirements.txt
python apps/website/app.py
```

Open **http://localhost:5000**. Use [`.env.example`](.env.example) as a configuration
reference; keep credentials and machine-specific settings out of Git.
Some asset-storage and live-capture workflows require additional configuration.

For a headless battle, pass a V3 battle configuration to the Node runner:

```bash
node aoe2x/js_simulation/node/headless-runner.mjs --input battle-config.json --workers 2
```

The website's `POST /api/v3/battle-config` constructs these configurations from
civilization/unit selections. See the [backend contract tests](tests/test_architecture_baseline.py)
for small complete requests, including direct and buffered matchups.

For live-game automation, follow the separate **[AOE2 Lab setup](docs/aoe2-lab.md)**.
It requires Windows, AoE2:DE, the live-capture dependencies and local configuration;
it is not part of ordinary website startup.

## Architecture and maintenance

Start with **[Current website architecture](docs/architecture/CURRENT.md)** for
module ownership, data contracts, frontend lifecycle and release procedures.

- Serving database connections are read-only; generation tools own data writes.
- Battle selection, API requests, workers, playback, statistics and rendering
  have separate responsibilities. Stale requests and old worker messages cannot
  replace a newer run.
- Civilization pages include meaningful descriptions and grouped unit content
  before JavaScript runs. Navigation uses real links, with canonical URLs,
  structured metadata and a data-driven sitemap.
- Sitemap dates come from recorded revisions rather than deployment timestamps.
  Production is crawlable; staging is explicitly non-indexable.
- `GET /api/release` exposes portable identities for reference data, mechanics,
  engine source and published ranking metadata.

The active engine lives in **`aoe2x/js_simulation/src/`**. Older Python engines
under `aoe2x/sim/` and browser code under `static/js/engine/` remain for
historical features and compatibility. They are not the engine powering today's
interactive battle page. Older dated architecture/calibration documents should
be read in that context.

## Tests and release workflow

[CI](.github/workflows/ci.yml) separately checks website contracts, the active
V3 engine, frontend integration and required legacy behavior. Small pinned
battle/API baselines guard structural refactors against changed results.

Useful focused checks:

```bash
python -m pip install -r requirements-ci.txt
python -m pytest tests/test_architecture_baseline.py tests/test_architecture_contracts.py
node --test tests/frontend_architecture.test.mjs
```

The [browser smoke test](tests/browser/architecture-smoke.cjs) checks laptop/mobile
playback, selection changes, randomized restart and JavaScript-disabled
civilization content. See the architecture guide for its Playwright setup.

Changes are reviewed on **staging** before promotion to **main**.
Do not commit local credentials, raw experimental recordings, per-matchup
simulation dumps or generated screenshots. Preserve intentional calibration
evidence and compact validation statistics according to the lab workflow.

## Scope and reuse notes

This is an independent AoE2 project, not the game's official engine. Simulation
outputs are estimates validated against controlled observations, not a guarantee
of identical results in every game situation. Fixes should implement general
mechanics, not force a particular matchup's winner or remaining HP.

The repository currently has **no top-level license file**. The reusable
components above describe technical boundaries, not a blanket redistribution
license. Game imagery, names and third-party assets have their own ownership
and terms.

## Project history

The monorepo brings together the earlier **aoe2-unit-analyzer**, **aoe2record**
and **aoe2grpc** projects, preserving their history and research tooling.
The current website and shared V3 integration are maintained here.
