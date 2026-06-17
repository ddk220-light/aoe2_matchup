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
