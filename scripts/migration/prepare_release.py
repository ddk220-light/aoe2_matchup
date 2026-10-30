"""Seal local approved artifacts once, before independent Vercel service builds.

No provider credentials, production HTTP calls, or data generation are involved.
Generated directories are disposable. Public assets use an explicit allowlist.
"""
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from export_data import export as export_data
from restore_retained import restore as restore_retained
from export_civilization_pages import export_pages
from export_ranking_pages import export_pages as export_ranking_pages
from export_simulator_page import export_page as export_simulator_page
from export_remaining_pages import export_pages as export_remaining_pages

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'apps/backend/runtime'
PUBLIC = ROOT / 'apps/web/public'
GENERATED = ROOT / 'apps/web/src/generated'
sys.path[:0] = [str(ROOT / 'apps/website'), str(ROOT)]
import app as website

def digest(data):
    return hashlib.sha256(data).hexdigest()

def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()

class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = []; self.links = []; self.title = ''; self.in_title = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta': self.meta.append(attrs)
        if tag == 'link': self.links.append(attrs)
        if tag == 'title': self.in_title = True
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
    def handle_data(self, value):
        if self.in_title: self.title += value

with website.app.test_client() as client:
    response = client.get('/about', base_url='https://aoe2matchup.com')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    catalog_response = client.get('/api/assets/catalog')
    assert catalog_response.status_code == 200
    public_catalog = catalog_response.get_json()
# M3 publishes only an already validated immutable media manifest.
media_dir = ROOT/'docs/migration/milestone-3'
media = json.loads((media_dir/'media-manifest.json').read_text())
publication = json.loads((media_dir/'media-publication.json').read_text())
assert digest((media_dir/'media-manifest.json').read_bytes()) == publication['media_version']
assert publication['verified_objects'] == publication['unique_objects']
public_catalog = json.loads((media_dir/'source-catalog.json').read_text())
def resolve_media(value):
    if isinstance(value, str) and value.startswith(('/static/', '/assets/')):
        assert value in media['aliases'], f'Unpublished media: {value}'
        return media['aliases'][value]['url']
    if isinstance(value, dict): return {k:resolve_media(v) for k,v in value.items()}
    if isinstance(value, list): return [resolve_media(v) for v in value]
    return value
public_catalog = resolve_media(public_catalog)
exports = ROOT/'.migration-cache/exports'
data = export_data(exports)
civilization_pages = export_pages(ROOT, website, exports, data, media, public_catalog, Head)
ranking_pages = export_ranking_pages(ROOT, website, exports, data, public_catalog, Head)
simulator_page = export_simulator_page(ROOT, website, exports, data, public_catalog, Head)
remaining_pages = export_remaining_pages(ROOT, website, Head)
retained_manifest = restore_retained()
assert data['components']['engine']['version'] == retained_manifest['legacy_engine_version'], \
    'An engine change requires an explicit legacy-client compatibility release'
engine_version=data['components']['engine']['version']
engine_prefix=f'/releases/engine/{engine_version}'
head_html = html.split('<head>', 1)[1].split('</head>', 1)[0]
head = Head(); head.feed(head_html)
scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.S)
plain = [s for s in scripts if s.strip() and not s.lstrip().startswith('{')]
theme_start = next(s for s in plain if 'before paint' in s)
nav_script = next(s for s in plain if 'setNavH' in s)
theme_script = next(s for s in plain if 'function applyTheme' in s)
catalog_script = next(s for s in plain if 'window.SITE_CATALOG =' in s)
structured = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
for value in structured: json.loads(value)
nav = re.search(r'<nav class="site-nav">.*?</nav>', html, re.S).group()
footer = re.search(r'<footer\b.*?</footer>', html, re.S).group()
body = html.split('</nav>', 1)[1].split('</script>', 1)[1].split('<footer', 1)[0].strip()
about = {'title': head.title, 'meta': head.meta, 'links': head.links,
         'structured': structured, 'style': re.search(r'<style>(.*?)</style>', head_html, re.S).group(1),
         'body': body, 'nav': nav, 'footer': footer, 'theme_start': theme_start,
         'nav_script': nav_script, 'theme_script': theme_script, 'catalog_script': catalog_script}

backend_sources = set()
for base in ['aoe2x/advisor', 'aoe2x/assets', 'aoe2x/batch', 'aoe2x/dbgen', 'aoe2x/rank', 'aoe2x/sim',
             'apps/website/services', 'apps/website/routes']:
    backend_sources.update(p for p in (ROOT/base).rglob('*.py') if '__pycache__' not in p.parts)
for name in ['aoe2x/__init__.py', 'aoe2x/paths.py', 'aoe2x/storage.py',
             'aoe2x/assets/presentation.json', 'aoe2x/js_simulation/__init__.py',
             'aoe2x/js_simulation/scenario_config.py', 'apps/website/app.py']:
    path = ROOT/name
    if path.exists(): backend_sources.add(path)
backend_sources.update(p for p in (ROOT/'data/golden').rglob('*') if p.is_file() and p.suffix in ['.db', '.json'])
backend_sources.update((ROOT/'apps/website/static/data').glob('*.json'))
backend_sources.update((ROOT/'aoe2x/js_simulation').glob('*.py'))
# The existing release API fingerprints these sources; retain the same identity.
backend_sources.update((ROOT/'aoe2x/js_simulation/src').rglob('*.js'))
for name in ['golden_map.json', 'golden_formation_27v27.json', 'current_ranged_golden_formations.json']:
    backend_sources.add(ROOT/'aoe2x/js_simulation/fixtures'/name)
# Imported framework helpers resolve templates relative to their original file.
backend_sources.update((ROOT/'apps/website/templates').glob('*.html'))

public_sources = {}
for name in ['css/base.css', 'img/favicon.png', 'img/og-default.png',
             'js/constants.js', 'js/unit_sprites.js', 'js/api_client.js', 'js/v3_sim_worker.js']:
    public_sources['static/'+name] = ROOT/'apps/website/static'/name
engine = ROOT/'aoe2x/js_simulation'
for path in (engine/'src').rglob('*.js'):
    public_sources['v3-runtime/'+path.relative_to(engine).as_posix()] = path
for name in ['map-renderer.js', 'unit-sprite-geometry.js']:
    public_sources['v3-runtime/viewer/'+name] = engine/'viewer'/name

# Cache only paths known to exist, so an initially missing immutable path does
# not accidentally receive a one-year error cache policy.
immutable_paths = ['/data/'+path.relative_to(exports/'data').as_posix()
                   for path in (exports/'data').rglob('*.json')]
catalog_url=f"/data/{publication['media_version']}/catalog.js"
immutable_paths.append(catalog_url)
immutable_paths += [engine_prefix+'/'+name for name in public_sources if name.startswith('v3-runtime/')]
immutable_paths.append(engine_prefix+'/worker.js')
for directory in sorted((ROOT/'.migration-cache/retained').glob('*')):
    immutable_paths += ['/releases/site/'+directory.name+'/'+path.relative_to(directory).as_posix()
                        for path in directory.rglob('*') if path.is_file()]
config = json.loads((ROOT/'vercel.json').read_text())
config['headers'] = [rule for rule in config['headers'] if not rule['source'].startswith(('/data/','/releases/'))]
config['headers'] += [{'source':path,'headers':[{'key':'Cache-Control','value':'public, max-age=31536000, immutable'}]}
                       for path in sorted(set(immutable_paths))]
config['headers'].append({'source':'/data/release.json','headers':[{'key':'Cache-Control','value':'no-store'}]})
(ROOT/'vercel.json').write_bytes(json_bytes(config))

source_files = backend_sources | set(public_sources.values())
for base in ['apps/web/src']:
    source_files.update(p for p in (ROOT/base).rglob('*') if p.is_file()
                        and not any(x in ['generated', '__pycache__'] or re.fullmatch(r'generated [0-9]+', x) for x in p.parts))
source_files.update(ROOT/'apps/backend'/p for p in ['app.py', 'advisor_cache.py', 'pyproject.toml', 'uv.lock', 'requirements.txt', '.python-version'])
source_files.update(ROOT/p for p in ['vercel.json', 'apps/web/astro.config.mjs', 'apps/web/package.json',
                                    'apps/web/package-lock.json', 'scripts/migration/prepare_release.py',
                                    'scripts/migration/check_release.mjs', 'scripts/migration/build_service.sh', 'scripts/migration/export_data.py',
                                    'scripts/migration/export_civilization_pages.py',
                                    'scripts/migration/export_ranking_pages.py',
                                    'scripts/migration/export_simulator_page.py',
                                    'scripts/migration/export_remaining_pages.py',
                                    'scripts/migration/restore_retained.py',
                                    'scripts/migration/validate_exports.mjs',
                                    'scripts/migration/schemas/projections.json',
                                    'scripts/migration/package.json', 'scripts/migration/package-lock.json',
                                    'docs/migration/milestone-3/retained-release.json',
                                    'docs/migration/milestone-3/media-manifest.json',
                                    'docs/migration/milestone-3/source-catalog.json',
                                    'docs/migration/milestone-3/media-publication.json'])
source_hashes = {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(source_files)}
release_id = digest(json_bytes({'sources':source_hashes, 'about':digest(json_bytes(about)),
                               'public_catalog':digest(json_bytes(public_catalog)), 'data':data,
                               'media':publication['media_version']}))
# Build into temporary directories; only publish after every artifact has copied.
stages = [p.with_name(p.name+'.next') for p in [BACKEND, PUBLIC, GENERATED]]
for stage in stages:
    shutil.rmtree(stage, ignore_errors=True); stage.mkdir(parents=True)
b, p, g = stages
for path in sorted(backend_sources):
    target = b/path.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
for name, path in sorted(public_sources.items()):
    target = p/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
# Resolve the classic bootstrap before any client rendering; its async catalog
# request must never replace an already downloaded local sprite with Blob.
bootstrap='window._AOE2_MEDIA_CATALOG = '+json.dumps(public_catalog,separators=(',',':'))+';\n'
bootstrap+='const UNIT_SPRITES = window._AOE2_MEDIA_CATALOG.sprites;\n'
for key in ['sprites','icons','anims','sheets']:
    bootstrap+=f'window._ASSET_{key.upper()} = window._AOE2_MEDIA_CATALOG.{key};\n'
(p/'static/js/unit_sprites.js').write_text(bootstrap)
catalog_file=p/catalog_url.removeprefix('/')
catalog_file.parent.mkdir(parents=True,exist_ok=True);catalog_file.write_text(bootstrap)
api_script=(p/'static/js/api_client.js').read_text()
assert api_script.count('let _assetCatalogPromise = null;')==1
(p/'static/js/api_client.js').write_text(api_script.replace('let _assetCatalogPromise = null;',
    'let _assetCatalogPromise = window._AOE2_MEDIA_CATALOG ? Promise.resolve(window._AOE2_MEDIA_CATALOG) : null;'))
shutil.copytree(exports/'data',p/'data',dirs_exist_ok=True)
(g/'data-manifest.json').write_bytes(json_bytes(data))
(g/'media-manifest.json').write_bytes(json_bytes(media))
(g/'public-catalog.json').write_bytes(json_bytes(public_catalog))
engine_folder=p/engine_prefix.removeprefix('/')
shutil.copytree(p/'v3-runtime',engine_folder/'v3-runtime')
worker=(p/'static/js/v3_sim_worker.js').read_text()
(engine_folder/'worker.js').write_text(worker.replace('"/v3-runtime/',f'"{engine_prefix}/v3-runtime/'))
retained = []
for directory in sorted((ROOT/'.migration-cache/retained').glob('*')):
    if directory.is_dir():
        shutil.copytree(directory,p/'releases/site'/directory.name)
        retained.append(directory.name)
# Baseline source samples are isolated review assets, never product media.
inventory=json.loads((media_dir/'media-inventory.json').read_text())
gallery=[]
for alias,label in [('/assets/img/units/Champion.png','Unit icon'),
    ('/assets/img/unit_sprites/champion.png','Full sprite'),
    ('/assets/anim/champion.webp','Animated WebP'),('/assets/sheets/champion.webp','Attack sheet')]:
    asset=inventory['aliases'][alias]
    original=p/'migration-review/sources'/Path(asset['pathname']).name
    original.parent.mkdir(parents=True,exist_ok=True)
    cached=ROOT/'.migration-cache/media'/Path(asset['pathname']).name
    if not cached.exists():
        from urllib.request import urlopen
        with urlopen(media['aliases'][alias]['url'],timeout=30) as response: sample_bytes=response.read()
        assert digest(sample_bytes)==asset['sha256']
        cached.parent.mkdir(parents=True,exist_ok=True);cached.write_bytes(sample_bytes)
    shutil.copyfile(cached,original)
    assert digest(original.read_bytes()) == asset['sha256']
    gallery.append({'alias':alias,'label':label,'source_url':'/migration-review/sources/'+original.name})
(g/'gallery.json').write_bytes(json_bytes(gallery))
(b/'public-catalog.json').write_bytes(json_bytes(public_catalog))
(g/'about.json').write_bytes(json_bytes(about))
(g/'civilization-pages.json').write_bytes(json_bytes(civilization_pages))
(g/'ranking-pages.json').write_bytes(json_bytes(ranking_pages))
(g/'simulator-page.json').write_bytes(json_bytes(simulator_page))
(g/'remaining-pages.json').write_bytes(json_bytes(remaining_pages))
manifest = {'schema_version': 2, 'release_id': release_id, 'production_baseline': '2581cd3534b22a3c1d65fe5dfa251aec073b1ed3',
            'components': {**data['components'],'media':{'schema_version':1,'version':publication['media_version'],
                'manifest_url':publication['manifest_url'],'unique_bytes':publication['unique_bytes']}},
            'engine_worker_url':engine_prefix+'/worker.js',
            'retention': {'previous_site_releases':retained,'supported_simulation_versions':[data['components']['simulator']['version']],
                         'supported_engine_versions':[engine_version], 'size_budget_bytes':200_000_000,
                         'previous_public_archive':retained_manifest,
                         'garbage_collection':'manual owner review after old-tab and rollback reference audit'},
            'source_sha256': source_hashes,
            'backend': {path.relative_to(b).as_posix(): digest(path.read_bytes()) for path in sorted(b.rglob('*')) if path.is_file()},
            'frontend': {path.relative_to(p).as_posix(): digest(path.read_bytes()) for path in sorted(p.rglob('*')) if path.is_file()},
            'about_sha256': digest((g/'about.json').read_bytes()),
            'backend_bytes': sum(path.stat().st_size for path in b.rglob('*') if path.is_file()),
            'frontend_public_bytes': sum(path.stat().st_size for path in p.rglob('*') if path.is_file())}
manifest['components']['media']['catalog_url']=catalog_url
manifest['generated'] = {path.name:digest(path.read_bytes()) for path in sorted(g.glob('*.json'))}
assert manifest['frontend_public_bytes'] < manifest['retention']['size_budget_bytes']
(p/'data/release.json').write_bytes(json_bytes({k:manifest[k] for k in ['schema_version','release_id','components','engine_worker_url','retention']}))
manifest['frontend']['data/release.json']=digest((p/'data/release.json').read_bytes())
manifest['frontend_public_bytes']+= (p/'data/release.json').stat().st_size
for folder in [b, g]: (folder/'release.json').write_bytes(json_bytes(manifest))
for target, stage in zip([BACKEND, PUBLIC, GENERATED], stages):
    shutil.rmtree(target, ignore_errors=True); stage.rename(target)
print(json.dumps({k:manifest[k] for k in ['release_id', 'backend_bytes', 'frontend_public_bytes']}))
