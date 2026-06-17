import importlib
from aoe2x.assets import config as cfg


def _reload(monkeypatch, **env):
    for k in ("CDN_BASE_URL", "DATABASE_URL", "ASSET_ENV", "R2_BUCKET",
              "R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return importlib.reload(cfg)


def test_disabled_when_unset(monkeypatch):
    c = _reload(monkeypatch)
    assert c.assets_enabled() is False
    assert c.cdn_base_url() == ""
    assert c.asset_env() == "local"


def test_enabled_requires_cdn_and_db(monkeypatch):
    c = _reload(monkeypatch, CDN_BASE_URL="https://cdn.example.com/")
    assert c.assets_enabled() is False  # DATABASE_URL missing
    c = _reload(monkeypatch, CDN_BASE_URL="https://cdn.example.com/",
                DATABASE_URL="postgresql://x")
    assert c.assets_enabled() is True
    assert c.cdn_base_url() == "https://cdn.example.com"  # trailing slash stripped


def test_asset_env(monkeypatch):
    c = _reload(monkeypatch, ASSET_ENV="staging")
    assert c.asset_env() == "staging"
