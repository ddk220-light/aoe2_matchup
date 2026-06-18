"""S3 client for the private Railway Bucket + presigned GET URLs.

The bucket is private (Railway has no public object URLs), so the app serves media
by 302-redirecting `/assets/<key>` to a short-lived presigned URL; the browser then
fetches the bytes straight from the bucket (bucket egress is free). Presigning is a
local signing operation — no network call."""
import boto3
from botocore.client import Config as _BotoConfig

from aoe2x.assets import config

_PRESIGN_TTL = 86400  # seconds (1 day)
_client_cache = None


def _client():
    global _client_cache
    if _client_cache is None:
        s = config.bucket_settings()
        _client_cache = boto3.client(
            "s3",
            endpoint_url=s["endpoint_url"],
            aws_access_key_id=s["aws_access_key_id"],
            aws_secret_access_key=s["aws_secret_access_key"],
            region_name=s["region"] or "auto",
            config=_BotoConfig(signature_version="s3v4",
                               s3={"addressing_style": "virtual"}),
        )
    return _client_cache


def presigned_get(key: str, expires: int = _PRESIGN_TTL) -> str:
    s = config.bucket_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s["bucket"], "Key": key},
        ExpiresIn=expires,
    )
