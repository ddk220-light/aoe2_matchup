# Replay Analyzer

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

The Replay Analyzer is a self-contained subsystem that downloads or accepts AoE2:DE recorded games (`.aoe2record`), parses them server-side with the `mgz` library, reconstructs unit identities and a map backdrop, and plays the match back in an isometric canvas SPA. It also exports short shareable WebM highlight clips. It shares no data with the simulation engines (see [simulation-engines.md](simulation-engines.md)) or the data pipeline (see [data-pipeline.md](data-pipeline.md)); its only tie to the rest of the webapp is the `/replay` page route and nav entry in `webapp/app.py` (see [webapp.md](webapp.md)).

## Mounting and routes

`webapp/replay_core.py` defines a Flask `Blueprint` named `replay` (line 38). `webapp/app.py` registers it at import time inside a `try/except` (lines 54–67): the blueprint pulls heavy optional dependencies (`mgz`, `requests`, and — transitively through `clip_export.py` — Pillow and imageio-ffmpeg), so if any import fails the blueprint is simply not registered, a warning is logged, and the core simulator site boots without it. `REPLAY_ENABLED` gates the rest of the integration: a context processor (`inject_replay_enabled`) exposes it to every template so `base.html` hides the Replay nav tab when False, and the `/replay` page route (a plain `@app.route` in `app.py`, not part of the blueprint) returns a 503 notice (`templates/replay_disabled.html`) instead of rendering an SPA whose API calls would all 404.

The dependencies live in `webapp/requirements.txt` (what Railway installs): `requests`, Pillow, `imageio-ffmpeg`, and `mgz` pinned to the `sanduckhan/aoc-mgz` fork at a specific commit for DE save-version 67.x support. `aocref` (object/terrain name tables) arrives transitively with `mgz`; every use of it is wrapped in try/except and degrades to empty name maps.

| Route | Method | Handler | Purpose |
|---|---|---|---|
| `/replay` | GET | `app.py replay()` | Page shell; embeds the SPA in an iframe, forwards `?match=&profile=&t=` |
| `/replay/api/upload` | POST | `upload_replay()` | Parse an uploaded `.aoe2record` file, return processed JSON |
| `/replay/api/matches` | GET | `get_matches()` | Legacy: recent Land Nomad matches for every player in `players.csv` |
| `/replay/api/matches/<player_name>` | GET | `get_matches_for_player()` | Legacy: name search + last 10 matches in one call |
| `/replay/api/players` | GET | `search_players()` | AoE2 Companion profile search (`?search=`), top 15 by games played |
| `/replay/api/player/<int:profile_id>/matches` | GET | `get_player_matches()` | A profile's recent games (`?limit=`, default 10, max 25) |
| `/replay/api/load-match` | POST | `load_match()` | Download replay from aoe.ms (cached), parse, return processed JSON |
| `/replay/api/clip` | GET | `make_clip()` | Generate or reuse a cached WebM highlight clip |

The two `matches` endpoints marked legacy are not called by the current SPA (verified by grepping `webapp/static/replay/`); the frontend uses the `players` → `player/<id>/matches` → `load-match` flow.

## Server-side parsing: `process_replay()`

`process_replay(file)` in `webapp/replay_core.py` runs `mgz.model.parse_match()` and assembles one JSON document the SPA runs on entirely client-side. Its top-level keys:

| Key | Content |
|---|---|
| `match` | `map_name`, `map_size` (real dimension from `match.map.dimension`), `duration_seconds`, `duration_formatted` |
| `players` | name, `color_id`/hex/name (8-color table), civilization, team (list of teammate names) |
| `starting_units` | Header units with true spawn positions (falls back to first commanded position only if the header lacks one) |
| `actions` | Every player action: id, time, player, type, `subjects` (synthetic unit names `type_player_N`), `target`, `target_id`, x/y, amount |
| `walls` | WALL placements with start/end coordinates |
| `unit_deaths` | `{unit_name: death_time}` — see death heuristic below |
| `building_interactions` / `building_deletions` | Reconstructed building usage and removal events `{x, y, player, time}` |
| `terrain` | Flat terrain-id grid plus an id→hex palette |
| `map_objects` | Static GAIA resources (gold, stone, relics, forage, fish) as `{c, x, y}` |
| `animals` | Huntables/herdables with a `gone_at` timestamp |
| `source` | Only when loaded via `load-match`: `matchId`, `profileId`, `downloadUrl` |

Key reconstruction logic, all in `replay_core.py`:

- **Terrain and forests** (`_extract_terrain`): terrain names come from `aocref` when available, mapped to backdrop colors by keyword (`_terrain_hex`). Forests are additionally detected by tree density: a terrain id whose tiles carry trees on ≥ 40% of tiles is colored forest even when `aocref` has no name for it (DE bulk forest trees are unnamed class-10 GAIA objects — `_is_tree`).
- **Animals with `gone_at`** (`_extract_animals`): each boar/deer/sheep-category GAIA animal records the earliest timestamp any player action payload references its instance id (sheep get commanded, boar/deer get attacked). The frontend stops drawing the animal at `gone_at`, mimicking conversion or kill.
- **Building events** (`_analyze_buildings`): production and research actions name a building only by `instance_id` with no position. Because instance ids are assigned in creation order, the k-th producing id of a building class is paired with that player's k-th surviving BUILD order of the same class (class inferred from what the id trains/researches via `_unit_class`/`_tech_class`). A DELETE of an id that never produced is matched to the player's most recent unclaimed BUILD — an abandoned foundation; DELETEs of located buildings become razes. Interactions re-brighten buildings in the UI; deletions remove them.
- **Death heuristic**: `DEATH_THRESHOLD = 3 * 60` (180 s). A non-villager unit whose last action is more than 180 s before game end is assigned `unit_deaths[name] = last_action_time + 180`. Villagers are exempt server-side; the client (`playback.js getState()`) layers more rules on top: non-villager, non-siege units disappear immediately after their final command (except in the last 3 minutes of the game), villagers fade at 30 s idle and are dropped after 5 minutes idle, and siege is exempt because trebuchets keep firing after a single command.

## Unit classification: `webapp/unit_classifier.py`

Recorded games never state a produced unit's type — only starting (header) units are named — so types are reconstructed. `process_replay()` calls `unit_classifier.build_type_map(match)` (the "v2" classifier); if that raises, it falls back to the legacy single-function matcher `_classify_units()` inside `replay_core.py`, and if that also fails, to an empty map. (Both code paths now cite this document as the design reference; an earlier `CLASSIFIER_REWORK.md` design doc never made it into the repo.)

The v2 classifier is a staged, confidence-laddered pipeline (`_run()`), standalone with no Flask dependency:

1. **Stage 0 — context** (`build_context`): owner map, GAIA split (villager-only resources vs everything), per-unit behavior counters, co-command groups, and per-building production queues. SPECIAL/UNGARRISON actions carry object ids byte-shifted (`id << 8`); only ids that arrive via those actions are decoded, and `build_type_map` returns a `remap` so `process_replay` collapses the phantom duplicates. DE_QUEUE multiqueue is simulated by load-balancing each queued unit to the selected building that frees up soonest, using civ-aware train times (`train_times.json` extracted from the .dat database, plus a hardcoded fallback table and an Aztec 11%-faster military multiplier), quantised to the game's 20-ticks/sec clock. RESIGN truncates queues; `Unqueue` orders cancel the newest pending unit.
2. **Stage 1 — behavioral hard labels** (`behavioral_labels`): BUILD/REPAIR/WALL → villager (the only unambiguous villager signal); STANCE/FORMATION/PATROL/ATTACK_GROUND/DE_ATTACK_MOVE/GUARD → military. Gathering is a *soft* villager signal (co-selection contaminates it). A unit carrying both hard signals is left unknown.
3. **Stage 2 — co-command propagation** (`propagate_class`): class spreads across the co-command graph by unanimity, never overwriting hard labels.
4. **Stage 3 — production timeline** (`production_timeline`): per-building serial completion times yield each player's FIFO spawn stream, split per production line (archery/barracks/stable/siege/monastery/unique via `_TYPE_LINE`).
5. **Stage 4 — typing** (`assign_types`, then `refine_military`/`align_production`): co-command squads are typed as one blob against a production-quota budget; then an order-preserving match/skip dynamic program aligns commanded military units to FIFO slots (spawn must precede first command), claiming distinctive lines smallest-first so a 2-monk line is not absorbed by a mass archery line. Rescue passes recover raiders, scouts, and monks the DP skipped (the monk override keys on a unit ordering its own monastery, which is monk-exclusive among military).
6. **Stage 5 — finalize**: still-generic military units get the player's dominant produced military type; class-only villagers get `"villager"`.

The legacy fallback (`_classify_units`) is a simpler three-step version: behavioral hard labels, villager-quota resolution of unknowns, then greedy nearest-slot matching against a military-only queue.

## Replay sources, cache, and rate limiting

- **Direct upload**: `/replay/api/upload` accepts only `.aoe2record` files, writes to a `NamedTemporaryFile`, parses, deletes.
- **Player search**: the SPA's Find Player modal calls `/replay/api/players?search=` (AoE2 Companion `GET {API}/profiles`), then `/replay/api/player/<id>/matches` (Companion `GET {API}/matches`). The Companion base URL is `https://data.aoe2companion.com/api` with a custom User-Agent header.
- **Download**: `_fetch_replay_to_cache()` pulls `https://aoe.ms/replay/?gameId=<matchId>&profileId=<profileId>`, which returns a ZIP containing the `.aoe2record`. The record is extracted and atomically moved into the cache.
- **Cache**: `{tempdir}/aoe2_replay_cache/<matchId>.aoe2record`. Cache hits skip the download entirely, because aoe.ms rate-limits per IP.
- **Rate limiting**: on HTTP 429 the fetch retries up to 3 attempts, honoring `Retry-After` clamped to 1–5 s. A final 429 surfaces to the client as HTTP 429 with a user-facing "wait a minute" message (`load_match` and `make_clip` both map it).
- **Watchlist**: `webapp/players.csv` (21 players, `name,profileId`) feeds only the legacy `/replay/api/matches` endpoint, which batch-queries Companion in groups of 10 profile ids and filters to Land Nomad maps. The current SPA does not call it. The profile id `612690` (ddk220) is also the hardcoded fallback download perspective in `app.js`.

## Frontend SPA: `webapp/static/replay/`

The `/replay` page (`webapp/templates/replay.html`) embeds `/static/replay/index.html` in an iframe sized to fill the viewport below the nav. The iframe exists purely for CSS isolation — the SPA is full-screen with its own stylesheet (`style.css`) and would collide with the analyzer's per-template styles. `app.py replay()` whitelists and forwards the `match`, `profile`, and `t` query params into the iframe `src`.

| File | Lines | Role |
|---|---|---|
| `index.html` | 292 | Static shell: canvas, playback controls, Find Player / match detail / clip modals, loads the 4 scripts |
| `app.js` | 1779 | `App` class: wiring, match browsing, upload, save/load, deep links, production/tech/attack trackers, clip modal, render loop |
| `renderer.js` | 2413 | `Renderer` class: isometric canvas drawing — terrain backdrop, buildings, units, walls, animals, civ emblems |
| `playback.js` | 1318 | `Playback` class: the time engine — movement interpolation, A* pathfinding, death/idle rules, trebuchet projectiles |
| `storyteller.js` | 581 | `Storyteller` class: caption narration of milestones; currently **disabled** (the `initializeStoryteller()` call in `app.js` is commented out, and the `/stories/stories.json` it would fetch does not exist) |

**Rendering** (`renderer.js`): a rotated 2:1 isometric diamond projection (`toScreen`), zoom 0.25×–8× with pan-by-drag. The terrain grid plus static map objects are rendered once to an offscreen canvas (capped to a mobile-safe pixel budget) and blitted each frame. Units draw as player-colored shapes with WebP sprites from `assets/sprites/` (`sprites.json` maps normalized type names to files — the same normalize-key rule the server-side clip exporter mirrors); buildings draw as procedural isometric blocks or sprites; animals are hidden past their `gone_at`; player base labels show civ emblems from `assets/civs/`.

**Playback** (`playback.js`): pre-processes all actions into per-unit movement timelines, then interpolates positions between commands at the current playback time. It builds a tile obstacle grid (trees, resources, buildings, time-aware) and runs A* with path smoothing and a path cache so units route around forests instead of through them. Trebuchet/bombard "firing episodes" synthesize lobbed projectile animations (2 s windup, 10 s reload, 2.5 s flight). Death/idle rules are described above.

**Controls and deep links**: play/pause, step, start/end, speeds 1/2/4/8/12/16×, a scrub timeline that pauses the engine while dragging, zoom buttons, and keyboard shortcuts (Space, arrows, Home/End, 1/2/4/8 for speed, P for the production-rates panel, T for the tech panel — both panels are hidden by default). `app.js init()` reads `?match=&profile=` and auto-loads via `load-match` (profile defaults to `612690`); `?t=` accepts plain seconds or `mm:ss`/`hh:mm:ss`, seeks there and starts playing on first load. Without deep-link params, the SPA tries to fetch a `replay_data.json` default (not present in the repo, so it 404s) and falls through to the Find Player modal.

## Clip export: `webapp/clip_export.py`

`build_clip(match, focus_player, out_path)` renders a shareable WebM with pure Python (Pillow frames piped to ffmpeg) — no headless browser, so it runs on the python-slim Railway image.

- **Engagement detection** (`_windows`): attack orders are bucketed into 6 s bins; the densest bins (expanded one bin back, two forward) are chosen until the game-time budget — `MAX_OUT_SEC (30) × SPEED (4.0)` = 120 game-seconds — is filled, then merged and the last window trimmed to budget.
- **Camera** (`_focus_points` + `_camera`): each window frames the *engagement*, not the whole map — seeded on the focus player's attack locations (or all attacks if they issued fewer than 3), keeping only units near the battle centroid, projected isometrically with 4/96-percentile bounds and a zoom ceiling of `MAX_TW = 17` px/tile.
- **Rendering**: 960×540 at 20 fps; terrain re-uses `_terrain_hex`/`_load_terrain_names` imported from `replay_core`; units use the same `sprites.json` assets as the web UI (player-colored disc + sprite, focus player outlined white, villagers smaller); attack flashes decay over 1.2 s; a skip-aware timeline bar at the bottom shows the selected windows. Unit positions come from a clip-local rebuild (`_build`) that re-runs `unit_classifier.build_type_map`.
- **Encoding** (`_encode`): PNG frames → `libvpx-vp9` (`-crf 34`), via the `imageio_ffmpeg` bundled binary (system `ffmpeg` as fallback), written to a `.tmp.webm` and atomically renamed so a killed worker never leaves a half-written file in cache.
- **Caching**: `make_clip` writes `webapp/static/replay/clips/{matchId}_{sanitized_player}.webm` and reuses it on later requests. The response returns `clip_url` (the static file) and `view_url` (`/replay?match=&profile=` deep link), honoring `X-Forwarded-Proto` so shared links are https behind Railway.
- Note a cosmetic inconsistency: the route docstring and the SPA modal text say "8× speed" but `SPEED = 4.0` in `clip_export.py` — clips are actually 4×.

The clip button is only enabled for replays loaded by match id (browser or deep link), because the server re-downloads the replay by id; uploads and local files cannot generate clips.

## The `.aoe2ddkrecord` save format

`.aoe2ddkrecord` is not a binary format: it is exactly `JSON.stringify(app.data)` — the processed JSON returned by `process_replay()` (including `source` when the replay was loaded by id). The Save button (`app.js saveRecord()`) downloads it as `<matchId>.aoe2ddkrecord` (or `<map>_<duration>s` for uploads). The file picker accepts `.aoe2record`, `.aoe2ddkrecord`, and `.json`; the latter two are parsed entirely client-side (`loadJsonFile`) with no server round-trip, so a saved record replays without re-downloading from aoe.ms or re-parsing — the only server dependency left is the static assets. Clip export is disabled for records loaded this way (no match id).

## Integration boundaries (verified)

- `unit_classifier.py` is imported only by `replay_core.py` and `clip_export.py` (grep over all `*.py`). Nothing in the simulation engines, analysis pipeline, or other webapp routes uses it. Its one inbound data dependency on the rest of the project is `webapp/train_times.json`, which was extracted from the .dat database offline.
- Nothing flows from the replay subsystem into the sims, the databases, or the derived-data jobs. The replay JSON is ephemeral (returned to the browser, never stored server-side except the raw-replay temp cache and the clips directory).
- `clip_export.py` imports two color/name helpers from `replay_core.py`; otherwise the three replay modules are self-contained.
- `webapp/static/replay/assets/` (sprites, civ emblems) is private to this subsystem; the rest of the site uses `webapp/static/img/units/` icons instead.

## Update triggers

| If this changes | Update these sections |
|---|---|
| Routes added/removed in `replay_core.py` | Mounting and routes |
| `process_replay()` output keys | Server-side parsing; the `.aoe2ddkrecord` section (format = this JSON) |
| `unit_classifier.py` pipeline stages or fallback behavior | Unit classification |
| `DEATH_THRESHOLD` or `playback.js getState()` idle rules | Death heuristic paragraphs (server and client) |
| aoe.ms URL, cache location, or retry policy | Replay sources, cache, and rate limiting |
| Clip constants (`W/H`, `FPS`, `SPEED`, `MAX_OUT_SEC`, codec) | Clip export (and fix the 8×/4× UI text if touched) |
| `mgz` fork pin or new optional dependency in `webapp/requirements.txt` | Mounting and routes (dependency paragraph) |
| SPA file roles or storyteller re-enabled | Frontend SPA table |
| `players.csv` usage changes (endpoint adopted or deleted) | Replay sources (watchlist) and the legacy-route note |
