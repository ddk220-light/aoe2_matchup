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
| Civ emblem CDN | `https://backend.cdn.aoe2companion.com/...` (hotlinked by the frontend) | `apps/website/static/js/constants.js` |

## Live local-machine inputs

| Input | Source | Used by |
|---|---|---|
| Game gRPC stream | AoE2:DE CadeRemote API, `ipv6:[::1]:4341`, mTLS (certs beside `aoe2x/grpc/`, NEVER committed — see `aoe2x/grpc/README.md`) | `aoe2x/grpc/` recorder; `lab/` capture; `apps/video` sidecars |
| Savegame folder | `~/Games/Age of Empires 2 DE/<steam-id>/savegame/` | lab eval replays; `apps/viewer/tools/watch_replays.py` |
| The game itself | UI automation (pydirectinput / Tesseract OCR) + scenario staging into the game's scenario folder | `apps/video` pipeline |

## Committed-but-external-origin assets

| Asset | Origin | Lives at |
|---|---|---|
| 248 unit icon PNGs | scraped (wiki), curated | `apps/website/static/img/units/` |
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

`CONTACT_FORM_ENDPOINT`, `SOCIAL_DISCORD_URL`, `SOCIAL_YOUTUBE_URL`,
`SOCIAL_INSTAGRAM_URL`, `SITE_URL` — read by `apps/website/app.py`.
gRPC mTLS keypair — files beside `aoe2x/grpc/`.

## Generated-but-external (size)

`D:/AI/matchup_baseline_<build>.db` (~276 MB, 491k rows) — produced by
`pypy3 -m aoe2x.batch.rebuild_matchup_baseline`, kept outside the repo;
published zipped as a `data-v<build>` release asset.
