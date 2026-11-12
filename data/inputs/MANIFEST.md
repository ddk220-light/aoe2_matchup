# Layer-1 inputs — everything this project takes from the outside

Nothing in this directory (except this manifest and the .gitignore) is
committed. Each input below lists: what it is, where it comes from, where it
lands, and what consumes it.

## Files you place here

| Input | Source | Lands at | Consumed by |
|---|---|---|---|
| `empires2_x2_p1.dat` | your AoE2:DE install (`steamapps/common/AoE2DE/resources/_common/dat/`) | `data/inputs/empires2_x2_p1.dat` | `python -m aoe2x.extract.run` |
| extracted JSONs | generated FROM the .dat by that command | `data/inputs/extracted_data/*.json` | `aoe2x.dbgen.generate_reference` |

## Live network inputs (fetched at runtime/build time)

| Input | Endpoint | Used by |
|---|---|---|
| AoE2 Companion API | `https://data.aoe2companion.com/api` (player search, match history) | `aoe2x/replay/blueprint.py` (both apps' replay browser) |
| aoe.ms replay downloads | `https://aoe.ms/replay?gameId=…&profileId=…` (rate-limited; responses cached in `%TEMP%/aoe2_replay_cache`) | `aoe2x/replay/blueprint.py`, `tools/download_replays.py` |
| aoe2techtree data | `https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/…` | `scripts/build_reference_docs.py`, `tools/analyzers/unit_analyzer.py` |
| Fandom wiki scraping | unit descriptions/flavor text | `scripts/build_reference_docs.py` |
| Civ emblem CDN | `https://backend.cdn.aoe2companion.com/...` (hotlinked by the frontend) | `apps/web/static/js/constants.js` (`CIV_EMBLEM_BASE`) |

## Live local-machine inputs

| Input | Source | Used by |
|---|---|---|
| Game gRPC stream | AoE2:DE CadeRemote API, `ipv6:[::1]:4341`, mTLS (certs beside `aoe2x/grpc/`, NEVER committed — see `aoe2x/grpc/README.md`) | `aoe2x/grpc/` recorder; `lab/` capture; `apps/video` sidecars |
| Savegame folder | `~/Games/Age of Empires 2 DE/<steam-id>/savegame/` | lab eval replays; `apps/viewer/tools/watch_replays.py` |
| The game itself | UI automation (pydirectinput / Tesseract OCR) + scenario staging into the game's scenario folder | `apps/video` pipeline |

## Committed-but-external-origin assets

| Asset | Origin | Lives at |
|---|---|---|
| unit icon PNGs | scraped (wiki), curated | `data/media/img/units/` (authoring copy; served from Blob) |
| viewer sprites/terrain | extracted + upscaled game art (see `graphics/`) | `aoe2x/replay/public/assets/` |
| scenario template | self-authored | `apps/video/templates/default3.aoe2scenario` |

## Tool/dependency inputs

| Dependency | Pin | Needed by |
|---|---|---|
| `mgz` (replay parser) | fork tarball `sanduckhan/aoc-mgz@a1683d8` (DE save v67.x) — local clone at `C:\dev\aoe2\aoc-mgz-67x`, override `$env:MGZ_PATH` | replay layer, lab |
| `genieutils-py` | unpinned; lives in the conda python | `aoe2x.extract` |
| PyPy3 | on PATH | `aoe2x.batch` runners |
| ffmpeg, Tesseract, headless Chrome | on PATH | `apps/video` |

## Secrets (env vars, never committed)

`SOCIAL_DISCORD_URL`, `SOCIAL_YOUTUBE_URL`, `SOCIAL_INSTAGRAM_URL`, `SITE_URL`,
`SEARCH_INDEXING`, `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION` — read at
build time by `scripts/migration/site/config.py` (and `SITE_URL`/`SEARCH_INDEXING`
by `apps/backend/aoe2_api/web.py`); set them in the Vercel project.
gRPC mTLS keypair — files beside `aoe2x/grpc/`.

## Generated-but-external (size)

`D:/AI/archive/matchup_baseline_<build>.db` (~288 MB, ~522k rows) — produced by
`pypy3 -m aoe2x.batch.rebuild_matchup_baseline`, kept outside the repo. Backed
up (2026-07-05) to BOTH Railway buckets (`aoe2-assets` staging /
`aoe2-assets-prod` production) under `data/matchup_baseline_<build>.db`.
