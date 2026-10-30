"""Build-only metadata/media and page projection of the frozen rankings.

The original public row projection remains the shared input to Astro HTML and
client interaction. This never recalculates scores or changes eligibility.
"""
import json
import re


def export_pages(root, website, exports, data, catalog, head_parser):
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
    media["civilization_emblems"] = {
        name: civ["emblem_url"]
        for name, civ in website.load_civilization_supplement()["civilizations"].items()
    }
    def metadata(html):
        head = head_parser(); head.feed(html.split('<head>', 1)[1].split('</head>', 1)[0])
        return {'title': head.title, 'meta': head.meta,
                'links': [l for l in head.links if l.get('href') != '/static/css/rankings.css'],
                'structured': re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S),
                'nav': re.search(r'<nav class="site-nav">.*?</nav>', html, re.S).group(),
                'footer': re.search(r'<footer\b.*?</footer>', html, re.S).group()}
    with website.app.test_client() as client:
        response = client.get('/units', base_url='https://aoe2matchup.com'); assert response.status_code == 200
        html = response.get_data(as_text=True)
        frame = metadata(html)
        overview = re.search(r'<section id="rankings-ssr".*?</section>', html, re.S).group()
        methods = json.loads(re.search(r'window.RANKING_METHODS = (.*?);</script>', html).group(1))
        guides = {}
        for page in website._UNIT_LINE_PAGES:
            response = client.get('/units/' + page['url'], base_url='https://aoe2matchup.com')
            assert response.status_code == 200
            line = lines[page['line']]
            rows = sorted(line['imperial'], key=lambda row: (
                -(row.get('ranking_score') if isinstance(row.get('ranking_score'), (int, float)) else float('-inf')),
                row['civ_name']))
            guides[page['url']] = {**metadata(response.get_data(as_text=True)), **page,
                                    'heading': page['title'].split(' — ')[0] + ' Rankings',
                                    'line_name': line['line_name'], 'building': line['building'], 'rows': rows}
    return {'frame': frame, 'overview': overview, 'methods': methods, 'guides': guides,
            'default': lines['infantry'], 'media': media,
            'files': {slug: item['url'] for slug, item in component['files'].items()}}
