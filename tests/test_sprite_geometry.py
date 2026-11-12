"""The shipped sizing evidence is complete and stays tied to its web assets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_geometry_covers_published_sprites():
    evidence = json.loads((ROOT / 'graphics/units/unit_sprite_geometry.json').read_text())
    manifest = json.loads((ROOT / 'data/media/data/unit_sprites.json').read_text())
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


def test_sprite_geometry_module_is_published_without_exposing_source_assets():
    # /v3-runtime/ is published by the release build: engine src/*.js plus exactly
    # two viewer modules; fixtures, tests and other viewer files stay unpublished.
    import re
    module = (ROOT / 'aoe2x/js_simulation/viewer/unit-sprite-geometry.js').read_text()
    assert 'NATIVE_SPRITE_HEIGHTS' in module
    release = (ROOT / 'scripts/migration/prepare_release.py').read_text()
    viewer = re.search(r"for name in \[([^\]]*)\]:\n    public_sources\['v3-runtime/viewer/'\+name\]", release)
    assert viewer, 'prepare_release must publish an explicit viewer allowlist'
    assert sorted(re.findall(r"'([^']+)'", viewer.group(1))) == ['map-renderer.js', 'unit-sprite-geometry.js']
    assert "for path in (engine/'src').rglob('*.js'):" in release
    assert (ROOT / 'aoe2x/js_simulation/viewer/battle-state.js').exists()  # exists, but is not published
