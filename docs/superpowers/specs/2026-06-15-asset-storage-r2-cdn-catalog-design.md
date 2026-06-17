# Asset Storage — R2 + CDN + Queryable Catalog — Design Spec

**Date:** 2026-06-15
**Status:** Superseded storage backend (2026-06-17)

> **UPDATE 2026-06-17 — backend changed to Railway Bucket.** R2 + a custom CDN
> domain required migrating `aoe2matchup.com`'s DNS to Cloudflare (it's on Name.com),
> and Railway has no public buckets/CDN. We switched to an all-Railway design:
> media lives in a **private Railway Bucket** (S3-compatible, free bucket egress),
> served via a same-origin **`/assets/<key>` route that 302-redirects to a presigned
> URL** (browser pulls bytes straight from the bucket). The Postgres catalog, publish
> CLI, and frontend are unchanged in shape — only the storage creds (`BUCKET_*` instead
> of `R2_*`/`CDN_BASE_URL`) and the URL base (`/assets` instead of a CDN host) differ.
> Tradeoff: no global CDN edge (acceptable at current scale). Everything below that
> references R2/CDN now reads as Railway Bucket / the `/assets` route.

## Goal

Move binary assets and (eventually) richer media off git and out of the Railway
container into purpose-fit stores, so we can:

1. **Unblock rich media** — high-quality images and per-unit attack animations
   (frames/GIFs) without bloating git or the deploy image.
2. **Fix git + deploy bloat** — stop accreting binaries in git (`.git` is **641 MB**
   today, mostly re-committed `*.db` snapshots + an orphaned 47 MB `matchup_db.db`)
   and stop baking ~86 MB of binaries into every container.
3. **Queryable asset catalog** — look up assets through a store/API
   ("attack frames for unit X, team blue") instead of hardcoded file paths.

**Chosen architecture: "A+ hybrid"** (decided with user 2026-06-15):

- **Media → Cloudflare R2 + CDN.** R2's zero egress makes browser-served images/GIFs
  effectively free; S3-compatible; ~$0.015/GB stored.
- **Catalog (and future dynamic data) → Railway Postgres.** Stay in the Railway
  ecosystem (user preference); the catalog is the "queryable" layer.
- **Read-only stats stay SQLite.** `aoe2_reference.db`, `derived_data.db`,
  `pool_scores.db`, `patches.db` are build artifacts the app reads in-process in
  microseconds. We do **not** migrate them to Postgres — their git bloat is a
  hygiene problem (committing binaries), fixed by publishing them to R2 and pulling
  at deploy (Phase 2). The query layer (`combat_unit_loader`, rankings, pool scores)
  is unchanged.

## Current state (where things live today)

| Thing | Today | Size |
|---|---|---|
| Unit sprites (idle, ±_blue) | `apps/website/static/img/unit_sprites/*.png`, committed, Flask-served | 56 MB / 446 files |
| Unit icons + OG/favicon | `apps/website/static/img/{units,*.png}`, committed | ~5 MB |
| Stat DBs | `data/golden/*.db`, committed, opened as local SQLite | ~25 MB |
| Sprite/icon lookups (frontend) | hardcoded in `static/js/unit_sprites.js` (52 KB) + `NAME_TO_ICON` in `constants.js` (218 entries) | — |

Deploy model (`railway.json` + CLAUDE.md §7): *"committed artifacts ARE the
deployment"* — Railway rebuilds when `data/golden/`, `aoe2x/`, or `apps/website/`
change; `gunicorn` serves everything from the container filesystem. Every data/image
change is a git commit + full redeploy.

## Target architecture

Three stores, each holding what it is good at:

1. **Cloudflare R2 + CDN** — all binaries (media now; stat DB artifacts in Phase 2).
   Served to browsers via a CDN custom domain (e.g. `cdn.aoe2matchup.com`).
   Key layout (env- and build-scoped so staging ≠ prod). `<build>` is the existing
   game build identifier the app already keys data by (`patches_db.get_current_build()`):
   ```
   media/sprites/<build>/<unit>[_blue].png
   media/icons/<build>/<icon_id>.png
   media/frames/<build>/<unit>/attack_<team>_<NN>.png   # Phase 4 (animations)
   db/<env>/<build>/<name>.db                            # Phase 2
   ```
   `media/*` is content-addressed by `<build>` so it can be shared across
   environments; `db/<env>/*` is per-environment.

2. **Railway Postgres** — the queryable `assets` catalog (+ headroom for future
   dynamic features). One Postgres instance **per Railway environment** (staging,
   production) so test data never touches prod.

3. **SQLite (unchanged at runtime)** — read-only stats; files arrive via deploy
   (committed today; pulled from R2 in Phase 2).

### Data flow

```
OFFLINE  pipeline (extract→sim→derive) ─┐
         generate/collect media ────────┤
                                         ▼
                                publish step ──►  R2 (media + DB artifacts)
                                         └──────►  Railway Postgres (upsert `assets`)

DEPLOY   Railway build ──► (Phase 2: pull current-build DBs from R2) ──► gunicorn
                                         app reads SQLite (stats) + PG (catalog)

RUNTIME  browser ─► GET /api/assets/catalog ─► CDN URLs ─► images/GIFs from CDN
```

### Environment isolation (makes "test in staging" safe)

- Railway already scopes env vars per environment. Give **staging and production
  each their own Railway Postgres** and their own R2 credentials/prefix via env vars.
- Publishing/testing against staging never touches prod. Promotion stays the
  fast-forward `staging → main` merge; data is published to the prod prefix/PG when
  cutting a release.

## Prerequisites (user-provisioned — cannot be done from a code session)

1. Cloudflare: create an **R2 bucket** + **API token** (S3 access key/secret);
   set up the **CDN custom domain** (`cdn.aoe2matchup.com` → R2 bucket).
2. Railway: add the **Postgres plugin** to *both* the staging and production
   environments.
3. Env vars (per environment): `R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET`,
   `R2_BUCKET`, `CDN_BASE_URL`, `DATABASE_URL`, `ASSET_ENV` (`staging`|`production`).

Until these exist, the app must run unchanged via an **in-repo fallback** (below),
so development and the existing site are never blocked.

## Phase 1 — Media + catalog (the buildable unit)

Everything below is Phase 1 unless marked. Phases 2–4 are roadmap.

### Components & interfaces

- **`aoe2x/assets/config.py`** — reads env vars; exposes `asset_env`,
  `cdn_base_url`, R2 client config, and `assets_enabled` (true only when
  `CDN_BASE_URL` + `DATABASE_URL` are set). Single source of truth for "are we in
  R2 mode or fallback mode."
- **`aoe2x/assets/catalog.py`** — the `assets` catalog data access (Postgres):
  - Schema:
    ```sql
    CREATE TABLE assets (
      id          SERIAL PRIMARY KEY,
      unit        TEXT NOT NULL,          -- display name, e.g. "Arbalester"
      kind        TEXT NOT NULL,          -- 'sprite' | 'icon' | 'attack_frame'
      team        SMALLINT,               -- 1 | 2 | NULL (team-agnostic)
      variant     TEXT,                   -- e.g. 'blue' | NULL; frame index for frames
      url         TEXT NOT NULL,          -- CDN URL
      width       INT, height INT,
      frame_count INT,                    -- for animations (Phase 4)
      build       TEXT NOT NULL,
      UNIQUE (unit, kind, team, variant, build)
    );
    ```
  - `load_catalog(build) -> dict` builds the lookup the frontend needs; cached
    in-process (`lru_cache`/module global), refreshed on deploy.
- **`POST/Build publish` — `aoe2x/assets/publish.py`** (CLI):
  - Uploads `static/img/unit_sprites/*` and icons to R2 under `media/.../<build>/`.
  - Upserts catalog rows in Postgres for the current build.
  - Idempotent (skip-if-unchanged by content hash). Targets the env from `ASSET_ENV`.
- **App route — `GET /api/assets/catalog`** (in `app.py`): returns the cached
  catalog (unit → {sprite urls per team, icon url, …}) as JSON. Cheap, served once
  per page load. Falls back to a catalog synthesized from in-repo paths when
  `assets_enabled` is false.
- **Frontend — `static/js/constants.js`**: `spriteFor()` / `getIconUrl()` resolve
  URLs from the fetched catalog (absolute CDN URLs) instead of computing
  `/static/img/...` paths. `unit_sprites.js` (52 KB hardcoded map) becomes
  redundant once the catalog is the source; kept temporarily as fallback data.

### Fallback (so it runs before/without provisioning, and locally)

- If `assets_enabled` is false (no `CDN_BASE_URL`/`DATABASE_URL`), `/api/assets/catalog`
  returns URLs pointing at the existing `/static/img/...` files, and the frontend
  behaves exactly as today. This keeps local dev (the `.venv` setup) and the live
  site working throughout the migration.

### Git hygiene (Phase 1 portion)

- Stop committing **new** media; document the publish-to-R2 path. Existing in-repo
  images stay until cutover is verified, then are removed in a follow-up (their
  history shrink is Phase 3).

### Staging test plan

1. Provision staging R2 prefix + staging Railway Postgres + env vars.
2. Run `publish.py` against staging → media in R2, catalog rows in PG.
3. Deploy staging; load Battle Sim → confirm sprites/icons load from `cdn.…`
   (Network panel shows CDN origin, not the container), catalog API returns URLs,
   visual parity with today.
4. Toggle `assets_enabled` off → confirm clean fallback to `/static/img`.
5. Only then promote to production (provision prod R2 prefix + prod PG first).

## Roadmap (later phases — not in this plan)

- **Phase 2 — Stat DBs off git**: publish `data/golden/*.db` to R2; pull at deploy;
  stop committing; update `CLAUDE.md` (§7 "committed artifacts ARE the deployment")
  and `docs/architecture/runbooks.md`.
- **Phase 3 — Shrink `.git`**: BFG/`git-filter-repo` to drop historical binaries
  (destructive; rewrites SHAs; coordinate across `staging` + `main`; force-push).
- **Phase 4 — Attack animations**: generate per-unit attack frames → R2
  `media/frames/...` → catalog (`kind='attack_frame'`, `frame_count`) → frontend
  plays them on attack (replacing/augmenting the gold glow). Memory/perf budget
  evaluated then (decode only on-screen unit types; cap frame count).

## Error handling

- Publish step: fail loudly on R2/PG auth errors; idempotent re-runs.
- Runtime: catalog load failure → fall back to in-repo paths (never a blank page).
- Deploy (Phase 2): if DB pull fails, fail the deploy rather than serve stale/empty.

## Testing

- Unit: catalog round-trip (publish → load), fallback synthesis when disabled.
- Integration: `/api/assets/catalog` shape; frontend resolves a known unit to a CDN
  URL; `assets_enabled=false` parity with current behavior.
- Manual (staging, via local `.venv` + Claude Preview and the staging URL): visual
  parity + Network-panel origin check, per the staging test plan.

## Risks & open questions

- **CDN cache invalidation**: build-scoped keys (`<build>` in the path) sidestep
  stale-cache issues — new build = new URL. Confirmed approach.
- **Catalog as single source vs. `unit_sprites.js`**: keep the JS file as fallback
  data during Phase 1; remove after cutover.
- **Cost**: R2 at this scale is pennies/month; Railway Postgres adds a small
  always-on instance per environment (acceptable per "keep it in Railway").
- **Local dev**: relies on the fallback path (no R2/PG needed locally). Documented.
