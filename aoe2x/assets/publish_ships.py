"""Upload the region-sailed ship assets to the Railway bucket, organized under ships/.

Source tree (produced by graphics/units/build_ship_sails.py + make_civ_region.py):
    .scratch/ship_out/<region>/<ship>.png        -> ships/<region>/<ship>.png        (player2 red)
    .scratch/ship_out/<region>/<ship>_blue.png   -> ships/<region>/<ship>_blue.png   (player1 blue)
    .scratch/ship_out/<region>/<ship>.gif        -> ships/<region>/<ship>.gif         (animated)
    .scratch/ship_out/civ_region.json            -> ships/civ_region.json             (civ->region map)

Run LOCALLY with bucket creds in env. The clean way (no creds typed out):
    railway run python -m aoe2x.assets.publish_ships
    python -m aoe2x.assets.publish_ships --dry-run        # list only, no creds
"""
import argparse
import mimetypes
import os
from collections import Counter

from aoe2x.assets import bucket, config
from aoe2x.paths import REPO_ROOT

SRC = REPO_ROOT / ".scratch" / "ship_out"
PREFIX = "ships"


def plan(src=SRC):
    jobs = []
    if not src.is_dir():
        return jobs
    for entry in sorted(os.listdir(src)):
        p = src / entry
        if p.is_dir():                       # region folder
            for fn in sorted(os.listdir(p)):
                if fn.lower().endswith((".png", ".gif")):
                    jobs.append((str(p / fn), f"{PREFIX}/{entry}/{fn}"))
        elif entry == "civ_region.json":
            jobs.append((str(p), f"{PREFIX}/civ_region.json"))
    return jobs


def _ct(fn):
    ct, _ = mimetypes.guess_type(fn)
    return ct or "application/octet-stream"


def _summary(jobs):
    by = Counter(k.split("/")[-1].rsplit(".", 1)[-1] for _, k in jobs)
    total = sum(os.path.getsize(l) for l, _ in jobs)
    print(f"{len(jobs)} files, {total/1e6:.1f} MB total  ({dict(by)})")
    regions = Counter(k.split("/")[1] for _, k in jobs if k.count("/") >= 2)
    for r, n in sorted(regions.items()):
        print(f"  {PREFIX}/{r}/  {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs = plan()
    _summary(jobs)
    if args.dry_run:
        for local, key in jobs[:6]:
            print(f"  e.g. {key}")
        print("(dry-run — nothing uploaded)")
        return
    if not jobs:
        print("nothing to upload (run build_ship_sails.py + make_civ_region.py first)")
        return
    if not config.assets_enabled():
        raise SystemExit("BUCKET_* not set — run via `railway run python -m aoe2x.assets.publish_ships`")

    client = bucket._client()
    bkt = config.bucket_settings()["bucket"]
    for i, (local, key) in enumerate(jobs, 1):
        client.upload_file(local, bkt, key, ExtraArgs={"ContentType": _ct(local)})
        if i % 50 == 0 or i == len(jobs):
            print(f"  uploaded {i}/{len(jobs)}")
    print(f"done: {len(jobs)} files -> {bkt}/{PREFIX}/")


if __name__ == "__main__":
    main()
