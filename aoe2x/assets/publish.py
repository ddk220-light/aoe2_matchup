"""Publish media to the Railway Bucket and the catalog to Postgres for a build.

Usage:
  python -m aoe2x.assets.publish --build 177723 [--dry-run]
Requires env: BUCKET_ENDPOINT/BUCKET_ACCESS_KEY_ID/BUCKET_SECRET_ACCESS_KEY/
BUCKET_NAME[/BUCKET_REGION], DATABASE_URL, ASSET_ENV."""
import argparse
import os

import boto3
from botocore.client import Config as _BotoConfig

from aoe2x.assets import catalog, catalog_pg, config
from aoe2x.paths import WEBAPP_DIR

STATIC = str(WEBAPP_DIR / "static")


def _bucket_client():
    s = config.bucket_settings()
    client = boto3.client(
        "s3",
        endpoint_url=s["endpoint_url"],
        aws_access_key_id=s["aws_access_key_id"],
        aws_secret_access_key=s["aws_secret_access_key"],
        region_name=s["region"] or "auto",
        config=_BotoConfig(signature_version="s3v4",
                           s3={"addressing_style": "virtual"}),
    )
    return client, s["bucket"]


def _upload_dir(client, bucket, local_dir, key_prefix, dry):
    n = 0
    for root, _, files in os.walk(local_dir):
        for fn in files:
            if not fn.lower().endswith(".png"):
                continue
            local = os.path.join(root, fn)
            rel = os.path.relpath(local, local_dir).replace(os.sep, "/")
            key = f"{key_prefix}/{rel}"
            if dry:
                print(f"PUT s3://{bucket or '<BUCKET_NAME>'}/{key}")
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

    if not args.dry_run and not config.assets_enabled():
        raise SystemExit("BUCKET_* required (or use --dry-run)")

    # 1) media -> bucket. Keys mirror the static layout so /assets/<key> maps 1:1.
    client, bucket = (None, None) if args.dry_run else _bucket_client()
    sprites_n = _upload_dir(client, bucket, os.path.join(STATIC, "img", "unit_sprites"),
                            "img/unit_sprites", args.dry_run)
    icons_n = _upload_dir(client, bucket, os.path.join(STATIC, "img", "units"),
                          "img/units", args.dry_run)
    print(f"media: {sprites_n} sprites, {icons_n} icons -> "
          f"{'(dry-run)' if args.dry_run else bucket}")

    # 2) catalog -> Postgres (optional). URLs point at the /assets broker route.
    # Without a DATABASE_URL the app synthesizes the same catalog from the in-repo
    # manifest at runtime, so the DB is only needed for the queryable-catalog feature.
    cat = catalog.synthesize_local(asset_base=config.ASSET_ROUTE_PREFIX, build=args.build)
    if args.dry_run:
        print(f"catalog: {len(cat['sprites'])} sprites, {len(cat['icons'])} icons "
              f"(env={config.asset_env()}) [dry-run]")
    elif config.database_url():
        catalog_pg.ensure_schema()
        catalog_pg.upsert_catalog(cat)
        print(f"catalog: upserted to Postgres for build {args.build} (env={config.asset_env()})")
    else:
        print("catalog: no DATABASE_URL — skipped Postgres; app will synthesize "
              "the catalog from the in-repo manifest at runtime")


if __name__ == "__main__":
    main()
