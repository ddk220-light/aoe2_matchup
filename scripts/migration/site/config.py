"""Environment-driven site settings, read with the same names and defaults as the API.

The pages are built for the production host (``BUILD_HOST``); the indexing
policy itself is the API's ``indexing_enabled`` so crawler headers and the
robots meta tag can never disagree.
"""
import os
from urllib.parse import urlsplit

from .sources import indexing_enabled

BUILD_HOST = 'aoe2matchup.com'
YOUTUBE_CHANNEL_URL = 'https://www.youtube.com/@AoE2Matchup'


def site_url():
    """Public site URL for canonical URLs, sitemap and Open Graph tags."""
    return os.environ.get('SITE_URL', 'https://aoe2matchup.com').rstrip('/')


def site_host():
    """The host the pages are served from when built for ``SITE_URL``."""
    return urlsplit(site_url()).netloc


def search_indexing(host=BUILD_HOST):
    """Whether pages served from ``host`` may be indexed (robots meta tag)."""
    return indexing_enabled({'SEARCH_INDEXING': os.environ.get('SEARCH_INDEXING')}, host, site_url(),
                            os.environ.get('RAILWAY_ENVIRONMENT_NAME', ''))


def verification_tokens():
    """Search Console / Bing Webmaster HTML-tag verification tokens, or None when unset."""
    return {'google': os.environ.get('GOOGLE_SITE_VERIFICATION') or None,
            'bing': os.environ.get('BING_SITE_VERIFICATION') or None}


def social_links():
    """Public profiles (JSON-LD ``sameAs``); YouTube has a stable default, the rest are optional."""
    return {
        'discord': os.environ.get('SOCIAL_DISCORD_URL') or None,
        'youtube': os.environ.get('SOCIAL_YOUTUBE_URL') or YOUTUBE_CHANNEL_URL,
        'instagram': os.environ.get('SOCIAL_INSTAGRAM_URL') or None,
    }

