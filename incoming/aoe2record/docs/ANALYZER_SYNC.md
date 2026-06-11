# Syncing replay features into aoe2-unit-analyzer

**Audience:** anyone (human or Claude session) working in the `aoe2-unit-analyzer`
repo who wants to pull the latest replay-viewer features from this repo.

**The relationship:** `aoe2record` is the **canonical** home of the replay viewer
and the unit classifier. The matchup website (`aoe2-unit-analyzer`, aoe2matchup.com)
embeds a downstream **copy** of the viewer, created by a one-time manual port
(analyzer commit `19eafb5`, 2026-06-04: server → Blueprint, UI copied with path
rewrites). The analyzer's "Find Player" flow (its commit `1c69df1`) has since been
upstreamed here, so as of 2026-06-10 this repo is strictly ahead. Develop replay
features HERE first; sync them downstream with this guide.

## File mapping (canonical → analyzer)

| aoe2record (canonical) | aoe2-unit-analyzer | Sync method |
|---|---|---|
| `visualizer/server.py` | `webapp/replay_core.py` | manual re-apply (structural fork, see below) |
| `visualizer/public/app.js` | `webapp/static/replay/app.js` | copy + URL rewrites |
| `visualizer/public/index.html` | `webapp/static/replay/index.html` | straight copy |
| `visualizer/public/style.css` | `webapp/static/replay/style.css` | straight copy |
| `visualizer/public/playback.js` | `webapp/static/replay/playback.js` | straight copy (byte-identical) |
| `visualizer/public/storyteller.js` | `webapp/static/replay/storyteller.js` | straight copy (byte-identical) |
| `visualizer/public/assets/**` | `webapp/static/replay/assets/**` | straight copy (byte-identical) |
| `visualizer/unit_classifier.py` | `webapp/unit_classifier.py` | straight copy (byte-identical) |
| `visualizer/train_times.json` | `webapp/train_times.json` | straight copy (byte-identical) |
| `visualizer/players.csv` | `webapp/players.csv` | straight copy (byte-identical) |
| `visualizer/clip_export.py` | `webapp/clip_export.py` | copy + exactly 2 line changes (below) |

Not ported (research/dev-only, the analyzer doesn't need them): `fetch_matches.py`,
`generate_data.py`, `worker.py` + `wrangler.toml` (Cloudflare experiment),
`watch_replays.py`, `eval_classifier.py`, `public/stories/`.

## Mechanical rewrite rules

When syncing **app.js** (the only UI file with embedded URLs):

| aoe2record | analyzer |
|---|---|
| `fetch("/api/...")` | `fetch("/replay/api/...")` |
| `/assets/...` (if any appear) | `/static/replay/assets/...` |

As of 2026-06-10 app.js contains exactly 6 fetch-prefix differences
(`/api/players`, `/api/player/<id>/matches`, `/api/load-match` ×2, `/api/clip`,
`/api/upload`) and nothing else. After a sync, verify with:

```powershell
git diff --no-index --ignore-cr-at-eol visualizer/public/app.js ../aoe2-unit-analyzer/webapp/static/replay/app.js
# every remaining hunk must be a /api/ vs /replay/api/ prefix
```

When syncing **clip_export.py**, re-apply exactly these 2 changes to the copy:
1. sprites dir: `public/assets/sprites` → `static/replay/assets/sprites`
2. import: `from server import _terrain_hex, _load_terrain_names` → `from replay_core import ...`

## Server-side changes (replay_core.py)

`replay_core.py` is a structural fork of `server.py`: Flask app → `Blueprint("replay")`,
every route prefixed `/replay`, static-serving routes (`/`, `/<path:path>`) and
`/api/default` dropped (the analyzer serves the UI via `templates/replay.html`
iframing `/static/replay/index.html`). When a server-side feature lands here,
re-apply it to `replay_core.py` by hand:

- `@app.route("/api/X")` → `@replay_bp.route("/replay/api/X")`
- `app.logger` → `log`
- helpers/constants (e.g. `AOE2_COMPANION_API`, `_fetch_replay_to_cache`) copy as-is

Current route parity (2026-06-10): `upload`, `matches`, `matches/<player_name>`,
`players`, `player/<int:profile_id>/matches`, `load-match`, `clip`.

## What's new to pull (as of 2026-06-10)

1. **Improved unit classifier** — `visualizer/unit_classifier.py` was replaced with
   the multi-agent-improved version (military-type accuracy: g0 80.9→84.7%,
   train game 78.9→90.8%, holdout non-regressed at 100%; drop-in compatible,
   same `build_type_map(match)` API, still reads `train_times.json` beside the
   module — that file is unchanged). Full verification report:
   `lab/_improve/REPORT.md`. To pull: straight-copy `visualizer/unit_classifier.py`
   over `webapp/unit_classifier.py`.
2. **Find Player flow** — already originated in the analyzer (`1c69df1`); now
   upstreamed here. Nothing to pull; UI files are at parity.

## Post-sync verification checklist (run in aoe2-unit-analyzer)

1. `python -m py_compile webapp/replay_core.py webapp/unit_classifier.py webapp/clip_export.py`
2. `node --check webapp/static/replay/app.js`
3. grep `webapp/static/replay` for `fetch("/api/` — must be ZERO hits (all must be `/replay/api/`)
4. Hash-compare the byte-identical files against aoe2record (playback.js, storyteller.js, unit_classifier.py, train_times.json, players.csv, assets/)
5. Smoke-test `/replay` on the **staging** environment (their flow: push staging → verify → `git merge --ff-only staging` into main → production)
