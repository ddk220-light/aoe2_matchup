from aoe2x.assets import catalog


SAMPLE_MANIFEST = {
    "Arbalester": {"slug": "arbalester", "w": 272, "h": 384, "ratio": 1.412,
                   "cat": "square", "url": "/static/img/unit_sprites/arbalester.png",
                   "url_blue": "/static/img/unit_sprites/arbalester_blue.png"},
    "Knight": {"slug": "knight", "w": 378, "h": 384, "ratio": 1.016, "cat": "square",
               "url": "/static/img/unit_sprites/knight.png"},  # no url_blue
}


def test_fallback_uses_static_paths():
    cat = catalog.build_catalog(SAMPLE_MANIFEST, icon_names=["Arbalester"],
                                asset_base="", build="177723")
    assert cat["build"] == "177723"
    assert cat["sprites"]["Arbalester"]["url"] == "/static/img/unit_sprites/arbalester.png"
    assert cat["sprites"]["Arbalester"]["url_blue"] == "/static/img/unit_sprites/arbalester_blue.png"
    assert cat["icons"]["Arbalester"] == "/static/img/units/Arbalester.png"
    # missing url_blue is omitted (frontend falls back to url)
    assert "url_blue" not in cat["sprites"]["Knight"]


def test_asset_base_rewrites_to_broker_route():
    cat = catalog.build_catalog(SAMPLE_MANIFEST, icon_names=["Arbalester"],
                                asset_base="/assets", build="177723")
    # /static/... -> /assets/... so the same-origin broker route serves it
    assert cat["sprites"]["Arbalester"]["url"] == "/assets/img/unit_sprites/arbalester.png"
    assert cat["sprites"]["Arbalester"]["url_blue"] == "/assets/img/unit_sprites/arbalester_blue.png"
    assert cat["icons"]["Arbalester"] == "/assets/img/units/Arbalester.png"
