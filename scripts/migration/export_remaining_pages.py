"""Build projections of existing page contexts, preserving source data and copy."""
import json
import re
from xml.etree import ElementTree


def export_pages(root, website, head_parser):
    contexts = {}
    render = website.render_template
    def capture(name, **kwargs):
        contexts['value'] = kwargs
        return render(name, **kwargs)
    def metadata(html):
        head = head_parser(); head.feed(html.split('<head>', 1)[1].split('</head>', 1)[0])
        return {'title': head.title, 'meta': head.meta, 'links': head.links,
                'structured': re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S),
                'nav': re.search(r'<nav class="site-nav">.*?</nav>', html, re.S).group(),
                'footer': re.search(r'<footer\b.*?</footer>', html, re.S).group()}
    result = {'patch_units': {}, 'patch_builds': {}, 'icon_names': json.loads((root/'aoe2x/assets/presentation.json').read_text())['icon_names']}
    website.render_template = capture
    try:
        with website.app.test_client() as client:
            def page(path):
                r = client.get(path, base_url=website.SITE_URL); assert r.status_code == 200, path
                value = {**contexts['value'], 'frame': metadata(r.get_data(as_text=True))}
                value.pop('active_nav', None)
                return value
            result['matchups'] = page('/matchups')
            result['advisor'] = page('/matchup-advisor')
            result['patch_index'] = page('/patches')
            for patch in result['patch_index']['patches']:
                build = str(patch['build_number'])
                result['patch_builds'][build] = page('/patches/' + build)
            sitemap = client.get('/sitemap.xml').get_data(as_text=True)
            result['sitemap'] = sitemap
            conn = website._patches_conn()
            try:
                # Include ranking-only units too; the sitemap is not the route boundary.
                keys = conn.execute('SELECT p.build_number, c.civ_name, c.unit_slug FROM patch_unit_changes c JOIN patches p ON p.id=c.patch_id UNION SELECT p.build_number, c.my_civ, c.my_unit_slug FROM patch_matchup_changes c JOIN patches p ON p.id=c.patch_id UNION SELECT p.build_number, c.civ_name, c.unit_slug FROM patch_unit_ranking c JOIN patches p ON p.id=c.patch_id').fetchall()
            finally: conn.close()
            for build, civ, unit in keys:
                key = f'{build}/{civ}/{unit}'
                result['patch_units'][key] = page('/patches/' + key)
            # Original route succeeds for any unit/civ when the build exists.
            result['empty_patch_frame'] = page('/patches/' + next(iter(result['patch_builds'])) + '/Unknown/not_a_unit')['frame']
            result['landing_frame'] = page('/vs/Spanish/champion/Chinese/arbalester')['frame']
    finally: website.render_template = render
    conn = website.get_ref_db()
    try: keys = conn.execute('SELECT DISTINCT civ_name, unit_slug FROM ref_units').fetchall()
    finally: conn.close()
    result['landing_units'] = {civ + '/' + slug: website._load_unit_for_landing(civ, slug) for civ, slug in keys}
    for unit in result['landing_units'].values():
        unit['_speed'] = format(unit['final_speed'], '.2f') if unit['final_speed'] else '—'
    result['valid_civs'] = sorted(website._valid_civs())
    result['related_units'] = website._unique_units_list()
    result['unit_names'] = {civ + '/' + slug: website._ref_unit_name(civ, slug) for civ, slug in keys}
    # Apply the already-existing post-render wrapper at build time, so notes work without JS.
    def wrap(value):
        if isinstance(value, str) and '<table class="mtable">' in value:
            return re.sub(r'(<table class="mtable">.*?</table>)', r'<div class="mtable-scroll scroll-x">\1</div>', value, flags=re.S)
        if isinstance(value, dict):
            result = {k: str(v) if k in {'old_value', 'new_value', 'old_score', 'new_score'} else wrap(v) for k, v in value.items()}
            if 'swing' in value: result['_swing_text'] = format(value['swing'], '+.0f')
            return result
        if isinstance(value, list): return [wrap(v) for v in value]
        return value
    return wrap(result)
