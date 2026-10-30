"""Build-only presentation projection for the native civilization components.

Read metadata and copy from the existing pages and group the frozen M3 analysis
with the existing service. No scoring, mechanics or public JSON is changed.
"""
import json
import re


def export_pages(root, website, exports, data, media, catalog, head_parser):
    from apps.website.services.catalog import grouped_units

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

    logic = (root / 'apps/website/static/js/matchup.js').read_text()
    tiers = {key: {'label': label, 'hint': hint} for key, label, hint in
             re.findall(r'(\w+):\s*\{ label: "([^"]+)",\s*hint: "([^"]+)"', logic)}
    assert len(tiers) == 6
    line_block = logic.split('const LINE_NAMES = {', 1)[1].split('};', 1)[0]
    lines = dict(re.findall(r'(\w+): "([^"]+)"', line_block))
    names = json.loads((root / 'aoe2x/assets/presentation.json').read_text())['icon_names']
    pages = {}
    roster = []
    with website.app.test_client() as client:
        for item in overview:
            slug = item['slug']
            response = client.get('/civilizations/' + slug, base_url='https://aoe2matchup.com')
            assert response.status_code == 200, slug
            html = response.get_data(as_text=True)
            head = head_parser()
            head.feed(html.split('<head>', 1)[1].split('</head>', 1)[0])
            head.links = [link for link in head.links if link.get('href') != '/static/css/matchup.css']
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
                'title': head.title, 'meta': head.meta, 'links': head.links,
                'structured': re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S),
            }
            roster.append({'name': item['name'], 'slug': slug, 'emblem': image(emblem)})
        response = client.get('/civilizations', base_url='https://aoe2matchup.com')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        head = head_parser()
        head.feed(html.split('<head>', 1)[1].split('</head>', 1)[0])
        head.links = [link for link in head.links if link.get('href') != '/static/css/matchup.css']
        frame = {'title': head.title, 'meta': head.meta, 'links': head.links,
                 'structured': re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S),
                 'nav': re.search(r'<nav class="site-nav">.*?</nav>', html, re.S).group(),
                 'footer': re.search(r'<footer\b.*?</footer>', html, re.S).group()}
    return {'pages': pages, 'roster': roster, 'frame': frame, 'tiers': tiers, 'lines': lines}
