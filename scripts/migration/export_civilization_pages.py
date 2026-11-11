"""Build-only presentation projection for the native civilization components.

Metadata and copy come from the site page builders; the frozen M3 analysis is
grouped with the existing service. No scoring, mechanics or public JSON is changed.
"""
import json

from scripts.migration.site import pages as site_pages
from scripts.migration.site.content import LINE_NAMES, TIERS
from scripts.migration.site.sources import grouped_units


def export_pages(root, exports, data, media, catalog):
    version = data['components']['civilizations']['version']
    folder = exports / 'data' / version
    overview = json.loads((folder / 'overview.json').read_text())
    by_url = {item['url']: item for item in media['aliases'].values()}
    def image(url):
        if url in media['aliases']:
            item = media['aliases'][url]
            return {'url': item['url'], 'width': item['width'], 'height': item['height']}
        item = by_url.get(url)
        return {'url': url, 'width': item['width'] if item else 64,
                'height': item['height'] if item else 64}

    names = json.loads((root / 'aoe2x/assets/presentation.json').read_text())['icon_names']
    pages = {}
    roster = []
    for item in overview:
        slug = item['slug']
        head = site_pages.civilization_head(item)
        analysis = json.loads((folder / (slug + '.json')).read_text())
        emblem = item['emblem_url'] or \
            'https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/' + slug + '.png'
        groups = grouped_units(analysis)
        for units in groups.values():
            for unit in units:
                name = unit['unit_name']
                sprite = catalog['sprites'].get(name)
                icon = catalog['icons'].get(names.get(name, ''))
                unit['media'] = image(sprite['url'] if sprite else icon) if sprite or icon else None
                unit['sprite'] = bool(sprite)
                unit['animation_url'] = catalog['anims'].get(name)
        pages[slug] = {
            'name': item['name'], 'slug': slug, 'emblem': image(emblem),
            'strategy': analysis['strategic_description'], 'groups': groups,
            'title': head['title'], 'meta': head['meta'], 'links': head['links'],
            'structured': head['structured'],
        }
        roster.append({'name': item['name'], 'slug': slug, 'emblem': image(emblem)})
    frame = site_pages.civilizations_frame()
    return {'pages': pages, 'roster': roster, 'frame': frame,
            'tiers': {key: dict(value) for key, value in TIERS.items()}, 'lines': dict(LINE_NAMES)}
