"""Build the asset catalog the frontend consumes.

`build_catalog` is pure: given the sprite manifest + icon names + an `asset_base`,
it returns the catalog JSON. With asset_base="" the URLs are same-origin /static
paths (fallback mode); with asset_base="/assets" they point at the bucket-broker
route (which redirects to a presigned Railway Bucket URL)."""
import json
import os

from aoe2x.paths import WEBAPP_DIR  # Path: <repo>/apps/website (single source of truth)

MANIFEST_PATH = str(WEBAPP_DIR / "static" / "data" / "unit_sprites.json")
ICON_DIR = str(WEBAPP_DIR / "static" / "img" / "units")
_STATIC_PREFIX = "/static"


def _rewrite(url: str, asset_base: str) -> str:
    """/static/img/... -> {asset_base}/img/... when asset_base is set, else unchanged."""
    if not asset_base:
        return url
    return asset_base + url[len(_STATIC_PREFIX):] if url.startswith(_STATIC_PREFIX) else url


def load_manifest() -> dict:
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def icon_url(name: str, asset_base: str) -> str:
    return _rewrite(f"/static/img/units/{name}.png", asset_base)


def build_catalog(manifest: dict, icon_names: list, asset_base: str, build: str) -> dict:
    sprites = {}
    for name, e in manifest.items():
        entry = {"slug": e["slug"], "w": e["w"], "h": e["h"],
                 "ratio": e["ratio"], "cat": e["cat"],
                 "url": _rewrite(e["url"], asset_base)}
        if e.get("url_blue"):
            entry["url_blue"] = _rewrite(e["url_blue"], asset_base)
        sprites[name] = entry
    icons = {name: icon_url(name, asset_base) for name in icon_names}
    return {"build": build, "sprites": sprites, "icons": icons}


def synthesize_local(asset_base: str = "", build: str = "local") -> dict:
    """Catalog built entirely from in-repo files (fallback / publish source)."""
    manifest = load_manifest()
    icon_names = [os.path.splitext(f)[0] for f in os.listdir(ICON_DIR)
                  if f.endswith(".png")]
    return build_catalog(manifest, icon_names, asset_base, build)
