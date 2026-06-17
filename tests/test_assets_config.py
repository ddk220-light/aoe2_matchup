import importlib
from aoe2x.assets import config as cfg

_BUCKET_KEYS = ("BUCKET_ENDPOINT", "BUCKET_ACCESS_KEY_ID", "BUCKET_SECRET_ACCESS_KEY",
                "BUCKET_NAME", "BUCKET_REGION")
_FULL_BUCKET = {
    "BUCKET_ENDPOINT": "https://storage.railway.app",
    "BUCKET_ACCESS_KEY_ID": "key",
    "BUCKET_SECRET_ACCESS_KEY": "secret",
    "BUCKET_NAME": "aoe2-assets-abc123",
}


def _reload(monkeypatch, **env):
    for k in _BUCKET_KEYS + ("DATABASE_URL", "ASSET_ENV"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return importlib.reload(cfg)


def test_disabled_when_unset(monkeypatch):
    c = _reload(monkeypatch)
    assert c.assets_enabled() is False
    assert c.asset_env() == "local"


def test_enabled_requires_all_bucket_creds(monkeypatch):
    # Missing the secret -> still disabled
    partial = dict(_FULL_BUCKET)
    del partial["BUCKET_SECRET_ACCESS_KEY"]
    c = _reload(monkeypatch, **partial)
    assert c.assets_enabled() is False
    # All four present -> enabled
    c = _reload(monkeypatch, **_FULL_BUCKET)
    assert c.assets_enabled() is True


def test_asset_env(monkeypatch):
    c = _reload(monkeypatch, ASSET_ENV="staging")
    assert c.asset_env() == "staging"


def test_bucket_settings(monkeypatch):
    c = _reload(monkeypatch, **_FULL_BUCKET)
    s = c.bucket_settings()
    assert s["endpoint_url"] == "https://storage.railway.app"
    assert s["bucket"] == "aoe2-assets-abc123"
    assert s["aws_access_key_id"] == "key"
    assert s["aws_secret_access_key"] == "secret"
    assert s["region"] == "auto"  # default when BUCKET_REGION unset
