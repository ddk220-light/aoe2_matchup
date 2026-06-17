"""Publish media to R2 and the catalog to Postgres for the current build.

Usage:
  python -m aoe2x.assets.publish --build 177723 [--dry-run]
Requires env: R2_ENDPOINT/R2_ACCESS_KEY/R2_SECRET/R2_BUCKET, CDN_BASE_URL,
DATABASE_URL, ASSET_ENV."""
import argparse
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
                print(f"PUT s3://{bucket or '<R2_BUCKET>'}/{key}")
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

    # 1) media -> R2 (build-scoped keys; media shared across envs)
    client, bucket = (None, None) if args.dry_run else _r2()
    sprites_n = _upload_dir(client, bucket, os.path.join(STATIC, "img", "unit_sprites"),
                            "img/unit_sprites", args.dry_run)
    icons_n = _upload_dir(client, bucket, os.path.join(STATIC, "img", "units"),
                          "img/units", args.dry_run)
    print(f"media: {sprites_n} sprites, {icons_n} icons -> "
          f"{'(dry-run)' if args.dry_run else bucket}")

    # 2) catalog -> Postgres
    cat = catalog.synthesize_local(cdn_base=cdn, build=args.build)
    if args.dry_run:
        print(f"catalog: {len(cat['sprites'])} sprites, {len(cat['icons'])} icons "
              f"(env={config.asset_env()}) [dry-run]")
    else:
        catalog_pg.ensure_schema()
        catalog_pg.upsert_catalog(cat)
        print(f"catalog: upserted for build {args.build} (env={config.asset_env()})")


if __name__ == "__main__":
    main()
