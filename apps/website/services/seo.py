"""Crawler policy and sitemap serialization shared by deployment environments."""
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlsplit, quote
from xml.etree import ElementTree as ET

def indexing_enabled(config, host, site_url, environment):
    override = config.get('SEARCH_INDEXING')
    if override is not None:
        return str(override).lower() in ('true', '1', 'yes')
    return environment.lower() in ('', 'production', 'prod') and host.split(':')[0] == urlsplit(site_url).hostname

def content_lastmod(golden_dir):
    path = Path(golden_dir) / 'derived_data_v3.metadata.json'
    try:
        value = json.loads(path.read_text(encoding='utf-8')).get('generated_at', '')[:10]
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
            try: lastmod = date.fromisoformat(lastmod).isoformat()
            except (ValueError, TypeError): continue
            ET.SubElement(url, 'lastmod').text = lastmod
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)
