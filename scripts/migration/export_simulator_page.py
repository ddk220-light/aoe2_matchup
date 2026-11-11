"""Build-only simulator shell metadata, scoped media and frozen arena preview.

Configuration and computation stay in the existing Python/worker contracts.
"""
import hashlib
import json

from scripts.migration.site import pages as site_pages
from scripts.migration.site.sources import api


def export_page(root, exports, data, media):
    component = data['components']['simulator']
    files = component['files']
    names = {'Scout Cavalry'}
    for civ in component['civilizations']:
        units = json.loads((exports / files[civ.lower()]['url'].removeprefix('/')).read_text())
        names.update(unit['unit_name'] for rows in units['units_by_age'].values() for unit in rows)
    search = json.loads((exports / files['search']['url'].removeprefix('/')).read_text())
    names.update(item['name'] for item in search)
    catalog = site_pages.simulator_catalog()
    with api().app.test_client() as client:
        response = client.get('/api/v3/arena-preview')
        assert response.status_code == 200
        arena = response.get_json()
        response = client.get('/api/release')
        assert response.status_code == 200
        legacy_release = response.get_json()
    frame = site_pages.simulator_frame()
    encoded = json.dumps(arena, sort_keys=True, separators=(',', ':')).encode()
    arena_url = '/data/' + hashlib.sha256(encoded).hexdigest() + '/arena-preview.json'
    target = exports / arena_url.removeprefix('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    icon_names = {name: catalog['icon_names'][name] for name in sorted(names) if name in catalog['icon_names']}
    icons = {key: media['icons'][key] for key in sorted(set(icon_names.values())) if key in media['icons']}
    sprites = {name: {key: value for key, value in media['sprites'][name].items() if key != 'url_blue'}
               for name in sorted(names) if name in media['sprites']}
    sheets = {name: media['sheets'][name] for name in sorted(names) if name in media['sheets']}
    return {'about': site_pages.simulator_about(), 'frame': frame, 'arena_url': arena_url, 'legacy_release': legacy_release,
            'civilizations': catalog['civilizations'], 'civilization_emblems': catalog['civilization_emblems'],
            'icon_names': icon_names, 'unique_buildings': catalog['unique_buildings'], 'icons': icons,
            'sprites': sprites, 'sheets': sheets, 'search': search,
            'files': {civ: files[civ.lower()]['url'] for civ in component['civilizations']}}
