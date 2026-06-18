"""Publish the *extra* generated assets to the Railway Bucket.

These are the full-resolution / source media that the routine publish
(`aoe2x.assets.publish`) does NOT cover, because they live in the un-committed
`graphics/` workspace rather than the web `/static` tree:

  attack GIFs          graphics/units/<slug>/<slug>_attack_dir06_dat4x.gif      -> gifs/<slug>.gif
  transparent icons    graphics/units/<slug>/icon_transparent.png              -> img/units_transparent/<slug>.png
  full-res red sprite  graphics/units/<slug>/<slug>_idle_dir06_dat4x.png       -> img/unit_sprites_full/<slug>.png
  full-res blue sprite graphics/units/<slug>/<slug>_idle_dir06_dat4x_blue.png  -> img/unit_sprites_full/<slug>_blue.png
  flux2 images         graphics/flux2/**                                        -> generated/flux2/<rel>
  nano banana images   graphics/nanobanana/**                                   -> generated/nanobanana/<rel>
  youtube thumbnails   graphics/youtube/**                                      -> generated/youtube/<rel>

The full-res sprites are the dat4x upscales that `sync_web_sprites.py` downscales
into the web copies (img/unit_sprites) — i.e. the originals, not the downscaled
ones.

`graphics/` is un-committed and ~GB-scale, so this runs LOCALLY (where graphics/
lives) with the BUCKET_* creds in the environment. The clean way is `railway run`
so Railway injects the bucket credentials without them ever being typed out:

  railway run python -m aoe2x.assets.publish_extras            # real upload
  python -m aoe2x.assets.publish_extras --dry-run             # list only, no creds
  python -m aoe2x.assets.publish_extras --only gifs,youtube   # a subset
"""
import argparse
import mimetypes
import os
from collections import Counter

from aoe2x.assets import bucket, config
from aoe2x.paths import REPO_ROOT

GRAPHICS = REPO_ROOT / "graphics"
UNITS = GRAPHICS / "units"
_IDLE = "idle_dir06_dat4x"        # IDLE_DIR_ANGLE=6, dat4x upscale (the web-sprite source)
_GENERATED_DIRS = ("flux2", "nanobanana", "youtube")

CATEGORIES = ("gifs", "transparent", "sprites_full", "flux2", "nanobanana", "youtube")


def plan(only=None):
    """Return [(local_path, bucket_key), ...] to upload. Pure — no network/creds,
    so `--dry-run` works without the bucket configured."""
    cats = set(only) if only else set(CATEGORIES)
    jobs = []

    if UNITS.is_dir() and (cats & {"gifs", "transparent", "sprites_full"}):
        for slug in sorted(os.listdir(UNITS)):
            d = UNITS / slug
            if not d.is_dir():
                continue
            if "gifs" in cats:
                gif = d / f"{slug}_attack_dir06_dat4x.gif"
                if gif.exists():
                    jobs.append((str(gif), f"gifs/{slug}.gif"))
            if "transparent" in cats:
                t = d / "icon_transparent.png"
                if t.exists():
                    jobs.append((str(t), f"img/units_transparent/{slug}.png"))
            if "sprites_full" in cats:
                red = d / f"{slug}_{_IDLE}.png"
                if red.exists():
                    jobs.append((str(red), f"img/unit_sprites_full/{slug}.png"))
                blue = d / f"{slug}_{_IDLE}_blue.png"
                if blue.exists():
                    jobs.append((str(blue), f"img/unit_sprites_full/{slug}_blue.png"))

    for cat in _GENERATED_DIRS:
        if cat not in cats:
            continue
        base = GRAPHICS / cat
        if not base.is_dir():
            continue
        for root, _, files in os.walk(base):
            for fn in files:
                local = os.path.join(root, fn)
                rel = os.path.relpath(local, base).replace(os.sep, "/")
                jobs.append((local, f"generated/{cat}/{rel}"))

    return jobs


def _content_type(fn):
    ct, _ = mimetypes.guess_type(fn)
    return ct or "application/octet-stream"


def _summary(jobs):
    by_pref = Counter(k.split("/")[0] for _, k in jobs)
    total = sum(os.path.getsize(l) for l, _ in jobs)
    print(f"{len(jobs)} files, {total / 1e6:.1f} MB total")
    for pref, n in sorted(by_pref.items()):
        print(f"  {pref:<22} {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would upload (no creds needed).")
    ap.add_argument("--only", help="Comma list of categories: " + ",".join(CATEGORIES))
    args = ap.parse_args()

    only = None
    if args.only:
        only = [c.strip() for c in args.only.split(",") if c.strip()]
        bad = [c for c in only if c not in CATEGORIES]
        if bad:
            raise SystemExit(f"unknown --only category {bad}; choices: {list(CATEGORIES)}")

    jobs = plan(only)
    _summary(jobs)

    if args.dry_run:
        for local, key in jobs[:8]:
            print(f"  e.g. {key}  <- {os.path.relpath(local, REPO_ROOT)}")
        print("(dry-run — nothing uploaded)")
        return

    if not jobs:
        print("nothing to upload")
        return

    if not config.assets_enabled():
        raise SystemExit(
            "BUCKET_* not set — run via `railway run python -m aoe2x.assets.publish_extras` "
            "so Railway injects the bucket creds (or export them), or use --dry-run. "
            "Nothing uploaded.")

    client = bucket._client()
    bkt = config.bucket_settings()["bucket"]
    for i, (local, key) in enumerate(jobs, 1):
        client.upload_file(local, bkt, key,
                           ExtraArgs={"ContentType": _content_type(local)})
        if i % 50 == 0 or i == len(jobs):
            print(f"  uploaded {i}/{len(jobs)}")
    print(f"done: {len(jobs)} files -> {bkt}")


if __name__ == "__main__":
    main()
