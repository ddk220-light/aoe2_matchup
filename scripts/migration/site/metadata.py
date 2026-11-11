"""Document <head> metadata for the generated page projections.

``head()`` returns the projection shape Astro consumes: ``title``, ``meta``
(attribute dicts in document order), ``links`` and ``structured`` (JSON-LD
source strings). Values are plain text; Astro escapes them when rendering.
"""
from . import config
from .templating import json_ld

DEFAULT_ROBOTS = 'index, follow, max-image-preview:large,max-snippet:-1'
FONTS = ('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700'
         '&family=JetBrains+Mono:wght@400;500&display=swap')


def website_json_ld(civilization_count):
    """The site-wide WebApplication JSON-LD (with ``sameAs`` social profiles)."""
    return json_ld('website.jsonld.html', site_url=config.site_url(), social_links=config.social_links(),
                   civilization_count=civilization_count)


def head(path, title, description, structured, *, canonical=None, og_type='website',
         stylesheets=(), host=config.BUILD_HOST):
    """Metadata of the page at ``path`` (canonical defaults to SITE_URL + path).

    ``host`` is the request host the page is built for; it decides the robots
    policy together with SEARCH_INDEXING and RAILWAY_ENVIRONMENT_NAME.
    """
    site = config.site_url()
    url = canonical or site + path
    image = site + '/static/img/og-default.png'
    tokens = config.verification_tokens()
    meta = [{'charset': 'UTF-8'},
            {'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0, viewport-fit=cover'},
            {'name': 'description', 'content': description},
            {'name': 'robots', 'content': DEFAULT_ROBOTS if config.search_indexing(host) else 'noindex, nofollow'}]
    if tokens['google']:
        meta.append({'name': 'google-site-verification', 'content': tokens['google']})
    if tokens['bing']:
        meta.append({'name': 'msvalidate.01', 'content': tokens['bing']})
    meta += [{'property': 'og:site_name', 'content': 'AoE2 Matchup'},
             {'property': 'og:type', 'content': og_type},
             {'property': 'og:title', 'content': title},
             {'property': 'og:description', 'content': description},
             {'property': 'og:url', 'content': url},
             {'property': 'og:image', 'content': image},
             {'property': 'og:image:width', 'content': '1200'},
             {'property': 'og:image:height', 'content': '630'},
             {'name': 'twitter:card', 'content': 'summary_large_image'},
             {'name': 'twitter:title', 'content': title},
             {'name': 'twitter:description', 'content': description},
             {'name': 'twitter:image', 'content': image}]
    links = [{'rel': 'canonical', 'href': url},
             {'rel': 'icon', 'type': 'image/png', 'href': '/static/img/favicon.png'},
             {'rel': 'preconnect', 'href': 'https://fonts.googleapis.com'},
             {'rel': 'preconnect', 'href': 'https://fonts.gstatic.com', 'crossorigin': None},
             {'href': FONTS, 'rel': 'stylesheet'},
             {'rel': 'stylesheet', 'href': '/static/css/base.css'}]
    links += [{'rel': 'stylesheet', 'href': href} for href in stylesheets]
    return {'title': title, 'meta': meta, 'links': links, 'structured': list(structured)}
