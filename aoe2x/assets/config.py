"""Env-driven config for the asset-storage feature (Railway Bucket + Postgres catalog).

`assets_enabled()` gates media serving: when False the app serves /static exactly
as before; when True, catalog URLs point at the same-origin `/assets/<key>` route,
which 302-redirects to a presigned URL on the (private) Railway Bucket. Reads
S3-compatible bucket credentials (Railway injects ENDPOINT/ACCESS_KEY_ID/etc.)."""
import os

# Same-origin route that brokers access to the private bucket via presigned redirects.
ASSET_ROUTE_PREFIX = "/assets"


def bucket_settings() -> dict:
    return {
        "endpoint_url": os.environ.get("BUCKET_ENDPOINT", ""),
        "aws_access_key_id": os.environ.get("BUCKET_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": os.environ.get("BUCKET_SECRET_ACCESS_KEY", ""),
        "bucket": os.environ.get("BUCKET_NAME", ""),
        "region": os.environ.get("BUCKET_REGION", "auto"),
    }


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "")


def asset_env() -> str:
    return os.environ.get("ASSET_ENV", "local")


def assets_enabled() -> bool:
    """True when the bucket is fully configured (controls media serving mode)."""
    s = bucket_settings()
    return bool(s["endpoint_url"] and s["aws_access_key_id"]
                and s["aws_secret_access_key"] and s["bucket"])
