from aoe2x.assets import catalog
import pytest


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


@pytest.mark.parametrize('name,slug,icon', [
    ('Mounted Crossbowman', 'mounted_crossbowman', 'Mounted_Crossbowman'),
    ('Heavy Mounted Crossbowman', 'heavy_mounted_crossbowman', 'Heavy_Mounted_Crossbowman'),
    ('Varangian Guard', 'varangian_guard', 'Varangian_Guard'),
    ('Elite Varangian Guard', 'elite_varangian_guard', 'Elite_Varangian_Guard'),
    ('Hearth Troop', 'hearth_troop', 'Hearth_Troop'),
    ('Elite Hearth Troop', 'elite_hearth_troop', 'Elite_Hearth_Troop'),
    ('Jarl', 'jarl', 'Jarl'),
    ('Elite Jarl', 'elite_jarl', 'Elite_Jarl'),
    ('Jomsviking', 'jomsviking', 'Jomsviking'),
    ('Elite Jomsviking', 'elite_jomsviking', 'Elite_Jomsviking'),
])
def test_new_units_resolve_through_the_same_catalog_as_existing_units(name, slug, icon):
    from apps.website.services.catalog import presentation
    cat = catalog.synthesize_local(asset_base='/assets', build='177723')
    assert presentation()['icon_names'][name] == icon
    assert cat['sprites'][name]['url'] == f'/assets/img/unit_sprites/{slug}.png'
    assert cat['icons'][icon] == f'/assets/img/units/{icon}.png'
    assert cat['anims'][name] == f'/assets/anim/{slug}.webp'


def test_longship_names_reuse_shared_longboat_assets():
    from apps.website.services.catalog import presentation
    cat = catalog.synthesize_local(asset_base='/assets', build='177723')
    for new, old in [('Longship', 'Longboat'), ('Elite Longship', 'Elite Longboat')]:
        assert cat['sprites'][new] == cat['sprites'][old]
        assert presentation()['icon_names'][new] == presentation()['icon_names'][old]
