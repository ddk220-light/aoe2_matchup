"""Serving contract of the army-economics data component (/api/economy, static /data/<version>/ files)."""
import json
from pathlib import Path

import pytest

from aoe2_api.services.economy import ARTEFACT, economy_civilizations
from aoe2x.economy.artefact import Artefact, encode

ROOT = Path(__file__).resolve().parents[1]
ARTEFACT_DATA = Artefact(ARTEFACT)


def export_bytes(response):
    """What scripts/migration/export_data.py writes as the static file."""
    return json.dumps(response.get_json(), sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def test_all_civilizations_are_served_byte_identically_to_the_export(client):
    names = economy_civilizations()
    assert len(names) == 56 and names == sorted(names)
    metadata = client.get('/api/economy')
    assert metadata.status_code == 200 and metadata.mimetype == 'application/json'
    assert export_bytes(metadata) == metadata.data
    document = metadata.get_json()
    assert document['civilizations'] == names
    assert document['metadata'] == ARTEFACT_DATA.metadata
    units = 0
    for name in names:
        response = client.get('/api/economy/' + name)
        assert response.status_code == 200 and response.mimetype == 'application/json', name
        assert export_bytes(response) == response.data, name
        data = response.get_json()
        assert data['civ'] == name and data['civilization']['civ'] == name
        assert data['contextVersion'] == document['metadata']['contextVersion']
        assert data['schemaVersion'] == document['metadata']['schemaVersion']
        assert data['units'] == ARTEFACT_DATA.record(name)['units']
        assert response.data == encode(data).encode()
        units += len(data['units'])
    assert units == document['metadata']['profileCount'] == 1029


def test_unknown_civilization_has_the_advisor_error_shape(client):
    for name in ['Unknown', 'franks', 'FRANKS', 'metadata']:
        response = client.get('/api/economy/' + name)
        advisor = client.get('/api/advisor-matchups/' + name)
        assert response.status_code == advisor.status_code == 404
        assert response.get_json() == advisor.get_json() == {'error': 'Unknown civilization'}


def test_published_static_files_match_the_api_when_a_release_is_sealed(client):
    release = ROOT / 'apps/web/public/data/release.json'
    if not release.exists():
        pytest.skip('no sealed release (python scripts/migration/prepare_release.py)')
    component = json.loads(release.read_text())['components'].get('economy')
    if component is None or component.get('context_version') != ARTEFACT_DATA.metadata['contextVersion']:
        pytest.skip('sealed release predates this artefact')
    assert component['civilizations'] == economy_civilizations()
    assert set(component['files']) == {'metadata', *(n.lower() for n in component['civilizations'])}
    for name, record in component['files'].items():
        path = '/api/economy' if name == 'metadata' else '/api/economy/' + next(
            c for c in component['civilizations'] if c.lower() == name)
        static = (ROOT / 'apps/web/public' / record['url'].removeprefix('/')).read_bytes()
        assert client.get(path).data == static, name
        assert record['url'] == f"/data/{component['version']}/{name}.json"
