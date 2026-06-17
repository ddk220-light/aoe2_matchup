# Asset Storage Phase 1 — R2 + CDN + Catalog — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve unit media (sprites/icons) from Cloudflare R2 + CDN via a queryable catalog (Railway Postgres), with a transparent in-repo fallback so the app is never blocked before provisioning.

**Architecture:** A new `aoe2x/assets/` package owns config, the catalog (local-manifest synthesis + Postgres backend), and a publish CLI (boto3 → R2, upsert → Postgres). The Flask app exposes `GET /api/assets/catalog`; the frontend fetches it once and treats it as a drop-in replacement for the static `UNIT_SPRITES` map + icon resolution, falling back to today's behavior if the catalog is unavailable. Read-only stat DBs are untouched (Phase 2).

**Tech Stack:** Python 3 (boto3 for S3-compatible R2, psycopg[binary] for Postgres), Flask, vanilla JS frontend, pytest. Spec: `docs/superpowers/specs/2026-06-15-asset-storage-r2-cdn-catalog-design.md`.

---

## The catalog contract (used by every task — keep consistent)

`GET /api/assets/catalog` returns JSON. It is a **drop-in replacement** for the static `UNIT_SPRITES` map plus icon URLs:

```json
{
  "build": "177723",
  "sprites": {
    "Arbalester": {"slug":"arbalester","w":272,"h":384,"ratio":1.412,"cat":"square",
                   "url":"<abs url>","url_blue":"<abs url>"}
  },
  "icons": { "Arbalester": "<abs url>" }
}
```

- **Fallback mode** (`assets_enabled == False`): `url`/`url_blue`/icon are same-origin `/static/img/...` (identical to today).
- **R2 mode**: they are absolute `CDN_BASE_URL` URLs.
- Team→color (established): the frontend keeps `spriteFor(name, team)` logic — team 1 → `url_blue` (blue), team 2 → `url` (red).
- `sprites` is keyed by unit **display name**; `icons` is keyed by **icon id** (the file stem, e.g. `"Elite_Huskarl"`, `"Ratha"`). The frontend resolves a display name to its icon id via `NAME_TO_ICON`, then looks up the catalog by id — this de-dupes display names that share one icon (e.g. Ratha Melee/Ranged).

## File structure

| File | Responsibility |
|---|---|
| `apps/website/requirements.txt` (modify) | add `boto3`, `psycopg[binary]` |
| `aoe2x/assets/__init__.py` (create) | package marker |
| `aoe2x/assets/config.py` (create) | env-driven config; `assets_enabled` gate |
| `aoe2x/assets/catalog.py` (create) | local-manifest synthesis + catalog→JSON transform |
| `aoe2x/assets/catalog_pg.py` (create) | Postgres schema + load/upsert (R2 mode) |
| `aoe2x/assets/publish.py` (create) | CLI: upload media → R2, upsert catalog → Postgres |
| `apps/website/app.py` (modify) | `GET /api/assets/catalog` route + in-process cache |
| `apps/website/static/js/constants.js` (modify) | consume fetched catalog; fall back to static `UNIT_SPRITES`/`NAME_TO_ICON` |
| `apps/website/static/js/api_client.js` (modify) | one-time catalog fetch helper |
| `tests/test_assets_config.py`, `tests/test_assets_catalog.py`, `tests/test_assets_route.py` (create) | unit/integration tests |

Tasks 1–5 and 8 are fully testable **locally** (`.venv` + pytest + Claude Preview). Tasks 6–7 (R2 upload, live Postgres) contain complete code but are **verified in staging** after you provision services — each marks this explicitly.

---

### Task 1: Add dependencies

**Files:**
- Modify: `apps/website/requirements.txt`

- [ ] **Step 1: Add the two libraries**

Append to `apps/website/requirements.txt` (after `numpy`):

```
# Asset storage (Phase 1): R2 (S3-compatible) uploads + Postgres asset catalog
boto3>=1.34.0
psycopg[binary]>=3.1.0
```

- [ ] **Step 2: Install into the local venv**

Run: `.venv/bin/python -m pip install "boto3>=1.34.0" "psycopg[binary]>=3.1.0"`
Expected: installs cleanly; `.venv/bin/python -c "import boto3, psycopg; print('ok')"` prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add apps/website/requirements.txt
git commit -m "build: add boto3 + psycopg for asset storage (Phase 1)"
```

---

### Task 2: Asset config

**Files:**
- Create: `aoe2x/assets/__init__.py` (empty)
- Create: `aoe2x/assets/config.py`
- Test: `tests/test_assets_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assets_config.py
import importlib
from aoe2x.assets import config as cfg


def _reload(monkeypatch, **env):
    for k in ("CDN_BASE_URL", "DATABASE_URL", "ASSET_ENV", "R2_BUCKET",
              "R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return importlib.reload(cfg)


def test_disabled_when_unset(monkeypatch):
    c = _reload(monkeypatch)
    assert c.assets_enabled() is False
    assert c.cdn_base_url() == ""
    assert c.asset_env() == "local"


def test_enabled_requires_cdn_and_db(monkeypatch):
    c = _reload(monkeypatch, CDN_BASE_URL="https://cdn.example.com/")
    assert c.assets_enabled() is False  # DATABASE_URL missing
    c = _reload(monkeypatch, CDN_BASE_URL="https://cdn.example.com/",
                DATABASE_URL="postgresql://x")
    assert c.assets_enabled() is True
    assert c.cdn_base_url() == "https://cdn.example.com"  # trailing slash stripped


def test_asset_env(monkeypatch):
    c = _reload(monkeypatch, ASSET_ENV="staging")
    assert c.asset_env() == "staging"
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_assets_config.py -q`
Expected: FAIL (`ModuleNotFoundError: aoe2x.assets.config`).

- [ ] **Step 3: Implement**

```python
# aoe2x/assets/__init__.py   (empty file)
```

```python
# aoe2x/assets/config.py
"""Env-driven configuration for the asset-storage feature (R2 + Postgres catalog).

`assets_enabled()` is the single gate: when False the app serves media from the
in-repo /static files exactly as before. When True it serves CDN URLs and reads
the catalog from Postgres."""
import os


def cdn_base_url() -> str:
    return os.environ.get("CDN_BASE_URL", "").rstrip("/")


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def asset_env() -> str:
    return os.environ.get("ASSET_ENV", "local")


def r2_settings() -> dict:
    return {
        "endpoint_url": os.environ.get("R2_ENDPOINT", ""),
        "aws_access_key_id": os.environ.get("R2_ACCESS_KEY", ""),
        "aws_secret_access_key": os.environ.get("R2_SECRET", ""),
        "bucket": os.environ.get("R2_BUCKET", ""),
    }


def assets_enabled() -> bool:
    return bool(cdn_base_url()) and bool(database_url())
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `.venv/bin/python -m pytest tests/test_assets_config.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add aoe2x/assets/__init__.py aoe2x/assets/config.py tests/test_assets_config.py
git commit -m "feat(assets): env-driven config with assets_enabled gate"
```

---

### Task 3: Local catalog synthesis + CDN transform

Builds the catalog dict from the existing `static/data/unit_sprites.json` manifest and `NAME_TO_ICON`-equivalent icon files, and rewrites URLs to an optional CDN base. This is the fallback source AND the data the publish step will push.

**Files:**
- Create: `aoe2x/assets/catalog.py`
- Test: `tests/test_assets_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assets_catalog.py
from aoe2x.assets import catalog


SAMPLE_MANIFEST = {
    "Arbalester": {"slug": "arbalester", "w": 272, "h": 384, "ratio": 1.412,
                   "cat": "square", "url": "/static/img/unit_sprites/arbalester.png",
                   "url_blue": "/static/img/unit_sprites/arbalester_blue.png"},
    "Knight": {"slug": "knight", "w": 378, "h": 384, "ratio": 1.016, "cat": "square",
               "url": "/static/img/unit_sprites/knight.png"},  # no url_blue
}


def test_synthesize_local_uses_static_paths():
    cat = catalog.build_catalog(SAMPLE_MANIFEST, icon_names=["Arbalester"],
                                cdn_base="", build="177723")
    assert cat["build"] == "177723"
    assert cat["sprites"]["Arbalester"]["url"] == "/static/img/unit_sprites/arbalester.png"
    assert cat["sprites"]["Arbalester"]["url_blue"] == "/static/img/unit_sprites/arbalester_blue.png"
    assert cat["icons"]["Arbalester"] == "/static/img/units/Arbalester.png"
    # missing url_blue is omitted (frontend falls back to url)
    assert "url_blue" not in cat["sprites"]["Knight"]


def test_cdn_base_rewrites_absolute():
    cat = catalog.build_catalog(SAMPLE_MANIFEST, icon_names=["Arbalester"],
                                cdn_base="https://cdn.example.com", build="177723")
    assert cat["sprites"]["Arbalester"]["url"] == "https://cdn.example.com/img/unit_sprites/arbalester.png"
    assert cat["icons"]["Arbalester"] == "https://cdn.example.com/img/units/Arbalester.png"
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_assets_catalog.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# aoe2x/assets/catalog.py
"""Build the asset catalog the frontend consumes.

`build_catalog` is pure: given the sprite manifest + icon names + an (optional)
CDN base, it returns the catalog JSON. With cdn_base="" the URLs are same-origin
/static paths (fallback mode); otherwise they are absolute CDN URLs."""
import json
import os

from aoe2x.paths import WEBAPP_DIR  # Path: <repo>/apps/website (single source of truth)

MANIFEST_PATH = str(WEBAPP_DIR / "static" / "data" / "unit_sprites.json")
ICON_DIR = str(WEBAPP_DIR / "static" / "img" / "units")
_STATIC_PREFIX = "/static"


def _rewrite(url: str, cdn_base: str) -> str:
    """/static/img/... -> {cdn_base}/img/... when cdn_base is set, else unchanged."""
    if not cdn_base:
        return url
    return cdn_base + url[len(_STATIC_PREFIX):] if url.startswith(_STATIC_PREFIX) else url


def load_manifest() -> dict:
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def icon_url(name: str, cdn_base: str) -> str:
    return _rewrite(f"/static/img/units/{name}.png", cdn_base)


def build_catalog(manifest: dict, icon_names: list, cdn_base: str, build: str) -> dict:
    sprites = {}
    for name, e in manifest.items():
        entry = {"slug": e["slug"], "w": e["w"], "h": e["h"],
                 "ratio": e["ratio"], "cat": e["cat"],
                 "url": _rewrite(e["url"], cdn_base)}
        if e.get("url_blue"):
            entry["url_blue"] = _rewrite(e["url_blue"], cdn_base)
        sprites[name] = entry
    icons = {name: icon_url(name, cdn_base) for name in icon_names}
    return {"build": build, "sprites": sprites, "icons": icons}


def synthesize_local(cdn_base: str = "", build: str = "local") -> dict:
    """Catalog built entirely from in-repo files (fallback / publish source)."""
    manifest = load_manifest()
    icon_names = [os.path.splitext(f)[0] for f in os.listdir(ICON_DIR)
                  if f.endswith(".png")]
    return build_catalog(manifest, icon_names, cdn_base, build)
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `.venv/bin/python -m pytest tests/test_assets_catalog.py -q`
Expected: 2 passed.
(`aoe2x/paths.py` already exposes `WEBAPP_DIR = REPO_ROOT / "apps" / "website"` — used here.)

- [ ] **Step 5: Commit**

```bash
git add aoe2x/assets/catalog.py tests/test_assets_catalog.py
git commit -m "feat(assets): build catalog from sprite manifest with CDN rewrite"
```

---

### Task 4: `GET /api/assets/catalog` route (fallback mode testable now)

**Files:**
- Modify: `apps/website/app.py` (add route + cache near the other `/api/...` routes, e.g. after the armor-classes route ~line 705)
- Test: `tests/test_assets_route.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assets_route.py
import importlib, sys, os


def _client(monkeypatch):
    for k in ("CDN_BASE_URL", "DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)  # force fallback mode
    sys.path.insert(0, os.path.join(os.getcwd(), "apps", "website"))
    app_mod = importlib.import_module("app")
    importlib.reload(app_mod)
    app_mod.app.config["TESTING"] = True
    return app_mod.app.test_client()


def test_catalog_fallback_shape(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/assets/catalog")
    assert r.status_code == 200
    data = r.get_json()
    assert "sprites" in data and "icons" in data and "build" in data
    # fallback URLs are same-origin /static
    any_sprite = next(iter(data["sprites"].values()))
    assert any_sprite["url"].startswith("/static/img/unit_sprites/")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_assets_route.py -q`
Expected: FAIL (404 / route missing).

- [ ] **Step 3: Implement the route**

Add near the other API routes in `apps/website/app.py`:

```python
from functools import lru_cache
from aoe2x.assets import config as _assets_cfg
from aoe2x.assets import catalog as _assets_catalog


@lru_cache(maxsize=1)
def _catalog_payload():
    """Built once per process. In R2 mode reads Postgres; else synthesizes from
    the in-repo manifest. Restart/redeploy refreshes it (acceptable: catalog
    changes only at publish time)."""
    try:
        build = get_current_build()
    except Exception:
        build = "local"
    if _assets_cfg.assets_enabled():
        from aoe2x.assets import catalog_pg
        return catalog_pg.load_catalog(build, _assets_cfg.cdn_base_url())
    return _assets_catalog.synthesize_local(cdn_base="", build=str(build))


@app.route("/api/assets/catalog")
def assets_catalog():
    return jsonify(_catalog_payload())
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `.venv/bin/python -m pytest tests/test_assets_route.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py tests/test_assets_route.py
git commit -m "feat(assets): GET /api/assets/catalog with in-repo fallback"
```

---

### Task 5: Postgres catalog backend (code now, verified in staging)

**Files:**
- Create: `aoe2x/assets/catalog_pg.py`

> Verified in staging (Task 8) — needs a live `DATABASE_URL`. The code is complete and follows psycopg 3 usage; do not block on running it locally.

- [ ] **Step 1: Implement schema + load + upsert**

```python
# aoe2x/assets/catalog_pg.py
"""Postgres-backed asset catalog (R2 mode). Source of truth populated by
publish.py; read by the app via load_catalog()."""
import psycopg

from aoe2x.assets import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
  id          SERIAL PRIMARY KEY,
  unit        TEXT NOT NULL,
  kind        TEXT NOT NULL,          -- 'sprite' | 'icon'
  team        SMALLINT,               -- 1 | 2 | NULL
  variant     TEXT,
  url         TEXT NOT NULL,
  width       INT, height INT,
  frame_count INT,
  build       TEXT NOT NULL,
  meta        JSONB,
  UNIQUE (unit, kind, team, variant, build)
);
CREATE INDEX IF NOT EXISTS assets_build_idx ON assets (build);
"""


def _conn():
    return psycopg.connect(config.database_url())


def ensure_schema():
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)


def upsert_catalog(catalog: dict):
    """catalog is the dict from aoe2x.assets.catalog.build_catalog (CDN URLs)."""
    build = catalog["build"]
    rows = []
    for name, e in catalog["sprites"].items():
        rows.append((name, "sprite", 2, None, e["url"], e["w"], e["h"], build,
                     {"slug": e["slug"], "cat": e["cat"], "ratio": e["ratio"]}))
        if e.get("url_blue"):
            rows.append((name, "sprite", 1, "blue", e["url_blue"], e["w"], e["h"],
                         build, {"slug": e["slug"], "cat": e["cat"]}))
    for name, url in catalog["icons"].items():
        rows.append((name, "icon", None, None, url, None, None, build, None))
    with _conn() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO assets (unit,kind,team,variant,url,width,height,build,meta)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (unit,kind,team,variant,build)
               DO UPDATE SET url=EXCLUDED.url, width=EXCLUDED.width,
                             height=EXCLUDED.height, meta=EXCLUDED.meta""",
            [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
              psycopg.types.json.Jsonb(r[8]) if r[8] is not None else None)
             for r in rows])


def load_catalog(build: str, cdn_base: str) -> dict:
    """Reconstruct the frontend catalog JSON from the assets table."""
    sprites, icons = {}, {}
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT unit,kind,team,url,width,height,meta
                       FROM assets WHERE build=%s""", (str(build),))
        for unit, kind, team, url, w, h, meta in cur.fetchall():
            if kind == "icon":
                icons[unit] = url
            else:
                s = sprites.setdefault(unit, {})
                if team == 1:
                    s["url_blue"] = url
                else:
                    s.update({"url": url, "w": w, "h": h,
                              "slug": (meta or {}).get("slug"),
                              "cat": (meta or {}).get("cat"),
                              "ratio": (meta or {}).get("ratio")})
    return {"build": str(build), "sprites": sprites, "icons": icons}
```

- [ ] **Step 2: Commit**

```bash
git add aoe2x/assets/catalog_pg.py
git commit -m "feat(assets): Postgres catalog backend (schema, upsert, load)"
```

---

### Task 6: Publish CLI (code now, verified in staging)

**Files:**
- Create: `aoe2x/assets/publish.py`

> Verified in staging (Task 8) — needs live R2 + Postgres. Code is complete; `--dry-run` lists actions without network calls.

- [ ] **Step 1: Implement the CLI**

```python
# aoe2x/assets/publish.py
"""Publish media to R2 and the catalog to Postgres for the current build.

Usage:
  python -m aoe2x.assets.publish --build 177723 [--dry-run]
Requires env: R2_ENDPOINT/R2_ACCESS_KEY/R2_SECRET/R2_BUCKET, CDN_BASE_URL,
DATABASE_URL, ASSET_ENV."""
import argparse
import mimetypes
import os

import boto3

from aoe2x.assets import catalog, catalog_pg, config
from aoe2x.paths import WEBAPP_DIR

STATIC = str(WEBAPP_DIR / "static")


def _r2():
    s = config.r2_settings()
    return boto3.client("s3", endpoint_url=s["endpoint_url"],
                        aws_access_key_id=s["aws_access_key_id"],
                        aws_secret_access_key=s["aws_secret_access_key"]), s["bucket"]


def _upload_dir(client, bucket, local_dir, key_prefix, dry):
    n = 0
    for root, _, files in os.walk(local_dir):
        for fn in files:
            if not fn.lower().endswith(".png"):
                continue
            local = os.path.join(root, fn)
            key = f"{key_prefix}/{os.path.relpath(local, local_dir)}"
            if dry:
                print(f"PUT s3://{bucket}/{key}")
            else:
                client.upload_file(local, bucket, key,
                                   ExtraArgs={"ContentType": "image/png"})
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cdn = config.cdn_base_url()
    if not args.dry_run and not config.assets_enabled():
        raise SystemExit("CDN_BASE_URL + DATABASE_URL required (or use --dry-run)")

    # 1) media -> R2  (build-scoped keys; media shared across envs)
    if args.dry_run:
        client = bucket = None
    else:
        client, bucket = _r2()
    sprites_n = _upload_dir(client, bucket, os.path.join(STATIC, "img/unit_sprites"),
                            f"img/unit_sprites", args.dry_run) if not args.dry_run \
        else _upload_dir(None, None, os.path.join(STATIC, "img/unit_sprites"),
                         "img/unit_sprites", True)
    icons_n = _upload_dir(client if not args.dry_run else None,
                          bucket if not args.dry_run else None,
                          os.path.join(STATIC, "img/units"), "img/units", args.dry_run)
    print(f"media: {sprites_n} sprites, {icons_n} icons -> {'(dry)' if args.dry_run else bucket}")

    # 2) catalog -> Postgres
    cat = catalog.synthesize_local(cdn_base=cdn, build=args.build)
    if args.dry_run:
        print(f"catalog: {len(cat['sprites'])} sprites, {len(cat['icons'])} icons "
              f"(env={config.asset_env()}) [dry]")
    else:
        catalog_pg.ensure_schema()
        catalog_pg.upsert_catalog(cat)
        print(f"catalog: upserted for build {args.build} (env={config.asset_env()})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Local dry-run sanity check**

Run: `.venv/bin/python -m aoe2x.assets.publish --build local --dry-run`
Expected: prints `PUT s3://...` lines for sprites+icons and a catalog summary; no network calls, exit 0.

- [ ] **Step 3: Commit**

```bash
git add aoe2x/assets/publish.py
git commit -m "feat(assets): publish CLI (media -> R2, catalog -> Postgres) with --dry-run"
```

---

### Task 7: Frontend consumes the catalog (verify via local Preview)

Make `spriteFor`/`getIconUrl` read from the fetched catalog; fall back to the static `UNIT_SPRITES`/`NAME_TO_ICON` if the fetch fails. Minimal change — the catalog `sprites` map mirrors the `UNIT_SPRITES` shape.

**Files:**
- Modify: `apps/website/static/js/api_client.js` (add a one-time catalog loader)
- Modify: `apps/website/static/js/constants.js` (consume it in `spriteFor`/`getIconUrl`)

- [ ] **Step 1: Add the loader to `api_client.js`**

```javascript
// Fetch the asset catalog once; resolves to {build, sprites, icons} or null on failure.
let _assetCatalogPromise = null;
function loadAssetCatalog() {
  if (!_assetCatalogPromise) {
    _assetCatalogPromise = fetch("/api/assets/catalog")
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
  }
  return _assetCatalogPromise;
}
```

- [ ] **Step 2: Consume it in `constants.js`**

In `constants.js`, add a mutable override populated once the catalog loads, and make the resolvers prefer it. Replace the `spriteFor` / `getIconUrl` lookups so they read `_ASSET_SPRITES` / `_ASSET_ICONS` when present, else the static maps:

```javascript
// Catalog overrides (absolute CDN URLs in R2 mode); null until loaded → static fallback.
let _ASSET_SPRITES = null;   // same shape as UNIT_SPRITES
let _ASSET_ICONS = null;     // { "Arbalester": "<url>" }
if (typeof loadAssetCatalog === "function") {
  loadAssetCatalog().then((cat) => {
    if (cat) { _ASSET_SPRITES = cat.sprites; _ASSET_ICONS = cat.icons; }
  });
}

function spriteFor(name, team) {
  const map = _ASSET_SPRITES || (typeof UNIT_SPRITES !== "undefined" ? UNIT_SPRITES : null);
  const s = map ? map[name] : null;
  if (s && s.url) {
    return team === 1 && s.url_blue ? s.url_blue : s.url;
  }
  return getIconUrl(name);
}

function getIconUrl(name) {
  if (_ASSET_ICONS && _ASSET_ICONS[name]) return _ASSET_ICONS[name];
  const id = NAME_TO_ICON[name];
  return id ? `${ICON_BASE}${id}.png` : "";
}
```

(Keep the existing `hasSprite`/`spriteRatio` reading from `UNIT_SPRITES`; the static map remains loaded as fallback data.)

- [ ] **Step 3: Verify in the running app (fallback mode = identical to today)**

Start the app (`preview_start` "aoe2-flask"), resize to 1440×900, open Battle Sim, and confirm via `preview_eval`:
```javascript
(async () => { const c = await loadAssetCatalog();
  return { hasCatalog: !!c, sample: spriteFor('Arbalester', 1), icon: getIconUrl('Knight') }; })()
```
Expected: `hasCatalog: true`, `sample` = `/static/img/unit_sprites/arbalester_blue.png`, a valid icon URL. Then run a battle and screenshot — visual parity with today (sprites still load).

- [ ] **Step 4: Commit**

```bash
git add apps/website/static/js/api_client.js apps/website/static/js/constants.js
git commit -m "feat(assets): frontend reads sprite/icon URLs from the catalog (static fallback)"
```

---

### Task 8: Staging end-to-end verification (after you provision R2 + Postgres)

> Gated on provisioning (R2 bucket + token + CDN domain; staging Railway Postgres; env vars). No code; verification + de-risking.

- [ ] **Step 1:** Confirm staging env vars set: `R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET`, `R2_BUCKET`, `CDN_BASE_URL`, `DATABASE_URL`, `ASSET_ENV=staging`.
- [ ] **Step 2:** Run the publish against staging (from a shell with the staging env): `python -m aoe2x.assets.publish --build $(python -c "from aoe2x.batch.patches_db import get_current_build; print(get_current_build())")`. Expected: media uploaded, catalog upserted.
- [ ] **Step 3:** Push branch to `staging`; after Railway deploys, load the Battle Sim on the staging URL. In the browser Network panel, confirm **both sprite AND icon** requests hit `CDN_BASE_URL` (not the container) — check icons specifically, since they resolve via `NAME_TO_ICON` display→id then a catalog lookup by id (the catalog `icons` map is keyed by icon id / file stem, not display name). Confirm `/api/assets/catalog` returns absolute CDN URLs.
- [ ] **Step 4:** Visual parity check (sprites render, team colors correct) and run a battle.
- [ ] **Step 5:** Fallback check: temporarily unset `CDN_BASE_URL` on staging → confirm app falls back to `/static/img` cleanly (no broken images). Restore it.
- [ ] **Step 6:** Only then promote (provision prod R2 prefix + prod Postgres + prod env vars first, publish to prod, then fast-forward `staging → main`).

---

## Self-review notes

- **Spec coverage:** R2+CDN media (Tasks 6,8), Postgres catalog (Tasks 5,8), `/api/assets` (Task 4), frontend wiring (Task 7), fallback (Tasks 3,4,7), env isolation (Task 8), prerequisites (Task 8 gate). Phases 2–4 intentionally out of scope.
- **Consistency:** catalog contract (`{build, sprites{url,url_blue,...}, icons}`) is identical across catalog.py, catalog_pg.load_catalog, the route, and the frontend. Team mapping (1→blue/url_blue, 2→red/url) matches the shipped sim convention.
- **Local-testable now:** Tasks 1–4, 7 (+ Task 6 dry-run). **Staging-only:** Tasks 5/6 live paths, 8.
- **Paths:** all repo-anchored paths resolve through `aoe2x.paths.WEBAPP_DIR` (the existing single source of truth).
