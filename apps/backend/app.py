"""Thin Vercel entrypoint around the frozen, read-only domain application."""
import importlib.util
import json
from pathlib import Path
import sys
import time
import resource
import uuid

from flask import abort, g, jsonify, request
from advisor_cache import ExactCache

STARTED = time.perf_counter()
BOOT_ID = uuid.uuid4().hex

RUNTIME = Path(__file__).resolve().parent/'runtime'
RELEASE = json.loads((RUNTIME/'release.json').read_text())
sys.path.insert(0, str(RUNTIME))
spec = importlib.util.spec_from_file_location('aoe2_legacy_web', RUNTIME/'apps/website/app.py')
website = importlib.util.module_from_spec(spec)
spec.loader.exec_module(website)
PUBLIC_CATALOG = json.loads((RUNTIME/'public-catalog.json').read_text())
# Freeze the existing projection; the server must not scan unpublished images
# or consult Railway to construct asset metadata. M3 publishes the media bytes.
website._catalog_payload = lambda: PUBLIC_CATALOG
app = website.app
advisor_cache = ExactCache(RELEASE["release_id"])
website.get_matchup_sims = advisor_cache.wrap("sims", website.get_matchup_sims)
website.get_matchup_recommendations = advisor_cache.wrap("recommendations", website.get_matchup_recommendations)
# This project is an isolated candidate, with no production domain or credentials.
app.config.update(SEARCH_INDEXING='false', MAX_CONTENT_LENGTH=4_500_000)
INITIALIZATION_MS = (time.perf_counter()-STARTED)*1000

def candidate_boundary():
    g.migration_started = time.perf_counter()
    if not request.path.startswith('/api/') and request.path != '/_internal/release':
        abort(404)
    if request.path.startswith('/api/v3/'):
        versions = RELEASE['retention']
        for header,key in [('X-AoE2-Simulation-Version','supported_simulation_versions'),
                           ('X-AoE2-Engine-Version','supported_engine_versions')]:
            requested = request.headers.get(header)
            if requested and requested not in versions[key]:
                return jsonify(error='This simulation release is no longer supported. Reload the page.',
                               requested_version=requested, supported_versions=versions[key]), 409

# Run before legacy canonical redirects, including responses that return early.
app.before_request_funcs.setdefault(None, []).insert(0, candidate_boundary)

@app.after_request
def candidate_headers(response):
    response.headers['X-AoE2-Release'] = RELEASE['release_id']
    response.headers['X-AoE2-Simulation-Version'] = RELEASE['components']['simulator']['version']
    response.headers['X-AoE2-Engine-Version'] = RELEASE['components']['engine']['version']
    response.headers['Cache-Control'] = 'no-store'
    if request.endpoint == 'cached_advisor' and response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        response.headers['Vercel-CDN-Cache-Control'] = 'public, s-maxage=31536000'
    response.headers['Server-Timing'] = f"backend;dur={(time.perf_counter()-g.migration_started)*1000:.2f}"
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1024 if sys.platform == 'linux' else 1)
    response.headers['Server-Timing'] += f', rss;desc="{rss}"'
    return response

@app.get('/_internal/release')
def internal_release():
    return jsonify(schema_version=1, release_id=RELEASE['release_id'],
                   production_baseline=RELEASE['production_baseline'],
                   backend_bytes=RELEASE['backend_bytes'],
                   frontend_public_bytes=RELEASE['frontend_public_bytes'],
                   runtime={'python':sys.version.split()[0], 'boot_id':BOOT_ID,
                            'initialization_ms':round(INITIALIZATION_MS, 2),
                            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                * (1024 if sys.platform == 'linux' else 1)})

@app.get('/api/cached-advisor/<revision>/<kind>/<age>/<left>/<right>')
def cached_advisor(revision, kind, age, left, right):
    if revision != RELEASE['release_id']:
        return jsonify(error='This advisor release is no longer supported. Reload the page.'), 409
    if kind not in {'sims', 'recommendations'}:
        abort(404)
    for civ in (left, right):
        error = website._validate_civ_name(civ)
        if error: return error
    error = website._validate_age(age)
    if error: return error
    function = website.get_matchup_sims if kind == 'sims' else website.get_matchup_recommendations
    result = function(left, right, age.lower())
    if 'error' in result: return jsonify(result), 400
    return jsonify(result)
