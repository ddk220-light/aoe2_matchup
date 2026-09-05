"""The shipped sizing evidence is complete and stays tied to its web assets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_geometry_covers_published_sprites():
    evidence = json.loads((ROOT / 'graphics/units/unit_sprite_geometry.json').read_text())
    manifest = json.loads((ROOT / 'apps/website/static/data/unit_sprites.json').read_text())
    units = evidence['units']
    assert set(units) == {entry['slug'] for entry in manifest.values()}
    for entry in manifest.values():
        geometry = units[entry['slug']]
        assert geometry['width'] > 0 and geometry['height'] > 0
        assert geometry['aspect_error'] <= .1
        assert (geometry['web_width'], geometry['web_height']) == (entry['w'], entry['h'])
        assert len(geometry['source_sha256']) == 64


def test_runtime_geometry_matches_extracted_evidence():
    evidence = json.loads((ROOT / 'graphics/units/unit_sprite_geometry.json').read_text())
    runtime = (ROOT / 'aoe2x/js_simulation/viewer/unit-sprite-geometry.js').read_text()
    assert f"NATIVE_REFERENCE_HEIGHT = {evidence['units']['halberdier']['height']}" in runtime
    for slug, entry in evidence['units'].items():
        assert f'"{slug}": {entry["height"]},' in runtime


def test_sprite_geometry_module_is_served_without_exposing_source_assets():
    from apps.website.app import app
    client = app.test_client()
    response = client.get('/v3-runtime/viewer/unit-sprite-geometry.js')
    assert response.status_code == 200
    assert b'NATIVE_SPRITE_HEIGHTS' in response.data
    assert client.get('/v3-runtime/viewer/battle-state.js').status_code == 404
    assert client.get('/v3-runtime/tests/production-mobile-presentation.test.mjs').status_code == 404
