"""The published sitemap.xml (moved from the website's /sitemap.xml route)."""
from datetime import date
import json
import os
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from . import config
from .content import UNIT_LINE_PAGES
from .data import matchup_seed_pairs, popular_matchup_links
from .patches import connect as patches_connect
from .sources import (GOLDEN_DIR, PATCHES_DB_PATH, RANKING_LAND_LINES, REF_DB_PATH, civilization_page_names,
                      connect_readonly, load_civilization_supplement, reference_civilizations)

STATIC_PAGES = ('/', '/matchup-advisor', '/units', '/civilizations', '/matchups', '/about', '/patches')


def content_lastmod(golden_dir=GOLDEN_DIR, *, rankings=False):
    """Recorded generation date of the published data (ISO date), or None."""
    path = Path(golden_dir) / 'derived_data_v3.metadata.json'
    try:
        metadata = json.loads(path.read_text(encoding='utf-8'))
        if not rankings:
            metadata = metadata.get('retained_source_metadata', metadata)
        value = metadata.get('generated_at', '')[:10]
        return date.fromisoformat(value).isoformat()
    except (OSError, ValueError, TypeError):
        return None


def sitemap_document(site_url, entries):
    """entries are validated (path, revision date) pairs; omit unknown dates."""
    root = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    seen = set()
    for path, lastmod in entries:
        if path in seen or '?' in path or path.startswith('/api/'):
            continue
        seen.add(path)
        url = ET.SubElement(root, 'url')
        ET.SubElement(url, 'loc').text = site_url.rstrip('/') + quote(path, safe='/')
        if lastmod:
            try:
                lastmod = date.fromisoformat(lastmod).isoformat()
            except (ValueError, TypeError):
                continue
            ET.SubElement(url, 'lastmod').text = lastmod
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def entries(patches_db=None):
    """(path, lastmod) for every published page, in sitemap order."""
    lastmod = content_lastmod()
    ranking_lastmod = content_lastmod(rankings=True)
    supplement = load_civilization_supplement()
    civ_lastmod = max(lastmod or '', supplement['published_at'])
    result = [(path, civ_lastmod if path == '/civilizations' else ranking_lastmod if path in {'/units', '/about'} else lastmod)
              for path in STATIC_PAGES]
    result.extend((f'/civilizations/{name.lower()}', civ_lastmod if name in supplement['civilizations'] else lastmod)
                  for name in civilization_page_names(reference_civilizations(), supplement))
    result.extend((f"/units/{page['url']}", ranking_lastmod if page['line'] in RANKING_LAND_LINES else lastmod)
                  for page in UNIT_LINE_PAGES)
    conn = connect_readonly(REF_DB_PATH)
    try:
        available = {(row[0], row[1]) for row in conn.execute('SELECT civ_name, unit_slug FROM ref_units')}
    finally:
        conn.close()
    for _, path in popular_matchup_links():
        _, _, ca, ua, cb, ub = path.split('/')
        if (ca, ua) in available and (cb, ub) in available:
            result.append((path, lastmod))
    result.extend((f'/vs/{ca}/{ua}/{cb}/{ub}', lastmod) for ca, ua, cb, ub in matchup_seed_pairs()
                  if (ca, ua) in available and (cb, ub) in available)
    patches_db = patches_db or PATCHES_DB_PATH
    if os.path.exists(patches_db):
        conn = patches_connect(patches_db)
        try:
            for patch in conn.execute('SELECT id, build_number, release_date FROM patches').fetchall():
                result.append((f"/patches/{patch['build_number']}", patch['release_date']))
                rows = conn.execute('SELECT civ_name, unit_slug FROM patch_unit_changes WHERE patch_id=? UNION '
                                    'SELECT my_civ, my_unit_slug FROM patch_matchup_changes WHERE patch_id=?',
                                    (patch['id'], patch['id']))
                result.extend((f"/patches/{patch['build_number']}/{row[0]}/{row[1]}", patch['release_date'])
                              for row in rows)
        finally:
            conn.close()
    return result


def sitemap_xml(patches_db=None):
    """The sitemap document text for SITE_URL."""
    return sitemap_document(config.site_url(), entries(patches_db)).decode('utf-8')
