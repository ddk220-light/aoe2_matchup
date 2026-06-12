# aoe2_comprehensive

The AoE2:DE data + tooling monorepo behind **[aoe2matchup.com](https://aoe2matchup.com)**
and the **replay visualizer** — organized as five independently-improvable
layers. Each layer can be consumed on its own; downstream layers only *refer*
to upstream ones.

```
┌ L1  data/inputs/      external inputs (game .dat, replays, captures, scraped art)
│                       → gitignored content; data/inputs/MANIFEST.md says how to fetch
├ L2  aoe2x/extract/    .dat → JSON extraction          (patch-dependent)
│     aoe2x/grpc/       live-game gRPC capture/decode   (patch-dependent)
│     (replay parsing = the pinned sanduckhan/aoc-mgz fork, see requirements)
├ L3  aoe2x/dbgen/      golden-database generators
│     data/golden/      the committed golden artifacts  (also published as
│                       GitHub Releases: data-v<build>)
├ L4  aoe2x/sim/        battle engines (abstract + positional 2D + frontend JS)
│     aoe2x/advisor/    matchup advisor
│     aoe2x/rank/       unit ranking / pool scoring
│     aoe2x/batch/      batch sim runners + patch pipeline (PyPy3)
│     aoe2x/replay/     replay-understanding classifier + THE viewer (blueprint + SPA)
└ L5  apps/website/     aoe2matchup.com (Flask; mounts the viewer at /replay)
      apps/viewer/      standalone replay viewer deployment (mounts it at /)
      apps/video/       YouTube matchup-video automation (runs the real game)
```

Supporting directories: `lab/` (gRPC ground-truth research + classifier
scoring harness), `tools/` (replay analyzers, downloaders, release
publishing), `scripts/` + `reference/` (reference-doc corpus), `graphics/`
(sprite tooling), `docs/` (architecture docs; `docs/aoe2record/` preserves
the absorbed aoe2record repo's docs), `tests/` + `.golden/` (golden
regression suite).

## Lineage

Merged 2026-06-11 from three repos, with full history (`git log --follow`
works across the moves): **aoe2-unit-analyzer** (this repo's trunk) ←
**aoe2record** (replay engine + lab, absorbed via subtree) ← **aoe2grpc**
(gRPC toolkit, previously absorbed into aoe2record). The old GitHub repos
remain as frozen archives; production still deploys from them until cutover.

## Quick start

```bash
pip install -e .                      # the aoe2x library (stdlib-only core)
pip install -r apps/website/requirements.txt   # website/viewer extras

PORT=5002 python apps/website/app.py  # the matchup website
python apps/viewer/server.py          # the standalone replay viewer
pytest                                # golden regression suite
```

Rebuilding data (per game patch — see `docs/architecture/runbooks.md`):

```bash
python -m aoe2x.extract.run               # data/inputs/empires2_x2_p1.dat → extracted JSONs
python -m aoe2x.dbgen.generate_reference  # → data/golden/aoe2_reference.db
pypy3 -m aoe2x.batch.rebuild_matchup_baseline --out D:/AI/matchup_baseline.db  # ~4.5h
python -m aoe2x.rank.derive_unit_rankings --matchup-db <baseline> --build <N>
```

## Consuming a single layer

- **Just the data** → download a `data-v<build>` GitHub Release (reference,
  derived, pool-score and patch DBs + civ power units + optionally the full
  491k-row matchup baseline). Every artifact's producer/consumer/regen
  command: `data/golden/README.md`.
- **Just the replay viewer** → `aoe2x/replay/` is a mountable Flask
  blueprint + SPA; `apps/viewer/server.py` is a 25-line example host. The
  classifier (`unit_classifier.py`) works standalone on a parsed mgz match
  via `build_type_map(match)`.
- **Just the sims** → `aoe2x/sim/` is stdlib-only; feed it combat dicts via
  `combat_unit_loader.build_combat_dict_from_ref()` from the reference DB.
- **Ground truth for classifiers** → `lab/README.md` documents the gRPC
  capture → decode → label → score loop and its verified accuracy numbers.

Each layer directory carries its own README with the full contract.

## Invariants (the ones that bite)

1. `aoe2x/sim/simulation_real.py` + `aoe2x/dbgen/config_combat.py` are
   byte-hashed into `sim_version` — the matchup-baseline cache key. Never
   edit them (even comments) outside a planned full re-sim.
2. Three sim engines must stay behavior-synced (abstract / positional /
   `apps/website/static/js/simulate.js`); golden tests pin them.
3. Committed data in `data/golden/` IS the deployment mechanism.
4. `aoe2x/replay/train_times.json` must sit beside `unit_classifier.py`.
5. gRPC mTLS certs live beside `aoe2x/grpc/` and are NEVER committed.
