"""Build-only metadata/media and page projection of the frozen rankings.

The original public row projection remains the shared input to Astro HTML and
client interaction. This never recalculates scores or changes eligibility.
"""
import json

from scripts.migration.site import pages as site_pages
from scripts.migration.site.content import UNIT_LINE_PAGES
from scripts.migration.site.data import rankings_overview


def export_pages(root, exports, data, catalog):
    component = data['components']['rankings']
    folder = exports / 'data' / component['version']
    lines = {slug: json.loads((folder / (slug + '.json')).read_text())
             for slug in component['files']}
    names = json.loads((root / 'aoe2x/assets/presentation.json').read_text())['icon_names']
    unit_names = {row['unit_name'] for line in lines.values() for row in line['imperial']}
    unit_names.update(['Champion', 'Arbalester', 'Paladin', 'Trebuchet', 'Galleon'])
    media = {name: {'sprite': catalog['sprites'].get(name, {}).get('url'),
                    'icon': catalog['icons'].get(names.get(name, '')),
                    'animation': catalog['anims'].get(name)} for name in sorted(unit_names)}
    media["civilization_emblems"] = site_pages.civilization_emblems()
    overview = rankings_overview()
    guides = {}
    for page in UNIT_LINE_PAGES:
        line = lines[page['line']]
        rows = sorted(line['imperial'], key=lambda row: (
            -(row.get('ranking_score') if isinstance(row.get('ranking_score'), (int, float)) else float('-inf')),
            row['civ_name']))
        guides[page['url']] = {**site_pages.unit_line_head(page, line), **page,
                                'heading': page['title'].split(' — ')[0] + ' Rankings',
                                'line_name': line['line_name'], 'building': line['building'], 'rows': rows}
    return {'frame': site_pages.rankings_frame(overview), 'overview': site_pages.rankings_overview_section(overview),
            'methods': site_pages.ranking_methods(), 'guides': guides,
            'default': lines['infantry'], 'media': media,
            'files': {slug: item['url'] for slug, item in component['files'].items()}}
