"""Smoke the packaged API and its release identity before deployment."""
import importlib.util
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
backend = root / 'apps/backend'
sys.path.insert(0, str(backend))
spec = importlib.util.spec_from_file_location('packaged_backend', backend / 'app.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
release = json.loads((root / 'apps/web/src/generated/release.json').read_text())
assert release['release_id'] == module.RELEASE['release_id']
with module.app.test_client() as client:
    for path in ['/api/assets/catalog', '/api/ref/unit-line/militia', '/api/ref/unit-line/knight', '/api/ref/civ/Franks']:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        assert response.is_json, path
        assert response.headers['X-AoE2-Release'] == release['release_id']
    rows = client.get('/api/ref/unit-line/militia').get_json()['imperial']
    assert any(row['civ_name'] == 'Varangians' for row in rows)
    response = client.post('/api/v3/battle-config', json={}, headers={'X-AoE2-Engine-Version': 'obsolete'})
    assert response.status_code == 409
    assert response.headers['Cache-Control'] == 'no-store'
print('Packaged API, finalized rankings, release identity and old-client boundary passed')
