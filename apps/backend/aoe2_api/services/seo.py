"""Crawler policy shared by the API and the page builders (scripts/migration/site).

The sitemap is serialized by scripts/migration/site/sitemap.py.
"""
from urllib.parse import urlsplit

def indexing_enabled(config, host, site_url, environment):
    override = config.get('SEARCH_INDEXING')
    if override is not None:
        return str(override).lower() in ('true', '1', 'yes')
    return environment.lower() in ('', 'production', 'prod') and host.split(':')[0] == urlsplit(site_url).hostname
