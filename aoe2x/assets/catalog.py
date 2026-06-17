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
