"""Postgres-backed asset catalog (R2 mode). Source of truth populated by
publish.py; read by the app via load_catalog()."""
import psycopg
from psycopg.types.json import Jsonb

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
              Jsonb(r[8]) if r[8] is not None else None)
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
