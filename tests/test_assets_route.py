import importlib, sys, os


def _client(monkeypatch):
    for k in ("CDN_BASE_URL", "DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)  # force fallback mode
    sys.path.insert(0, os.path.join(os.getcwd(), "apps", "website"))
    app_mod = importlib.import_module("app")
    importlib.reload(app_mod)
    app_mod.app.config["TESTING"] = True
    return app_mod.app.test_client()


def test_catalog_fallback_shape(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/assets/catalog")
    assert r.status_code == 200
    data = r.get_json()
    assert "sprites" in data and "icons" in data and "build" in data
    # fallback URLs are same-origin /static
    any_sprite = next(iter(data["sprites"].values()))
    assert any_sprite["url"].startswith("/static/img/unit_sprites/")
