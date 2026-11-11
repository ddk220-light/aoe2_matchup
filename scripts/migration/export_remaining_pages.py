"""Build projections of the matchup, advisor, patch and /vs/ pages, preserving source data and copy."""
import json
import re

from scripts.migration.site import pages as site_pages
from scripts.migration.site.data import load_unit_for_landing, unique_units_list
from scripts.migration.site.patches import connect as patches_connect, ref_unit_name
from scripts.migration.site.sitemap import sitemap_xml
from scripts.migration.site.sources import REF_DB_PATH, connect_readonly, valid_civilizations


def export_pages(root):
    result = {'patch_units': {}, 'patch_builds': {}, 'icon_names': json.loads((root/'aoe2x/assets/presentation.json').read_text())['icon_names']}
    result['matchups'] = site_pages.matchups()
    result['advisor'] = site_pages.advisor()
    result['patch_index'] = site_pages.patch_hub()
    for patch in result['patch_index']['patches']:
        build = str(patch['build_number'])
        result['patch_builds'][build] = site_pages.patch_build(build)
    result['sitemap'] = sitemap_xml()
    conn = patches_connect()
    try:
        # Include ranking-only units too; the sitemap is not the route boundary.
        keys = conn.execute('SELECT p.build_number, c.civ_name, c.unit_slug FROM patch_unit_changes c JOIN patches p ON p.id=c.patch_id UNION SELECT p.build_number, c.my_civ, c.my_unit_slug FROM patch_matchup_changes c JOIN patches p ON p.id=c.patch_id UNION SELECT p.build_number, c.civ_name, c.unit_slug FROM patch_unit_ranking c JOIN patches p ON p.id=c.patch_id').fetchall()
    finally: conn.close()
    for build, civ, unit in keys:
        result['patch_units'][f'{build}/{civ}/{unit}'] = site_pages.patch_unit_page(build, civ, unit)
    # A known build accepts any unit/civ; Astro fills in this frame for unchanged units.
    result['empty_patch_frame'] = site_pages.patch_unit_page(next(iter(result['patch_builds'])), 'Unknown', 'not_a_unit')['frame']
    result['landing_frame'] = site_pages.matchup_landing_frame('Spanish', 'champion', 'Chinese', 'arbalester')
    conn = connect_readonly(REF_DB_PATH)
    try: keys = conn.execute('SELECT DISTINCT civ_name, unit_slug FROM ref_units').fetchall()
    finally: conn.close()
    result['landing_units'] = {civ + '/' + slug: load_unit_for_landing(civ, slug) for civ, slug in keys}
    for unit in result['landing_units'].values():
        unit['_speed'] = format(unit['final_speed'], '.2f') if unit['final_speed'] else '—'
    result['valid_civs'] = sorted(valid_civilizations())
    result['related_units'] = unique_units_list()
    result['unit_names'] = {civ + '/' + slug: ref_unit_name(civ, slug) for civ, slug in keys}
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
