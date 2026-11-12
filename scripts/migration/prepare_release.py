"""Seal local approved artifacts once, before independent Vercel service builds.

No provider credentials, production HTTP calls, or data generation are involved.
Generated directories are disposable. Public assets use an explicit allowlist.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from export_data import export as export_data
from restore_retained import restore as restore_retained
from export_civilization_pages import export_pages
from export_ranking_pages import export_pages as export_ranking_pages
from export_simulator_page import export_page as export_simulator_page
from export_remaining_pages import export_pages as export_remaining_pages
from scripts.migration.site import pages as site_pages

BACKEND = ROOT / 'apps/backend/runtime'
PUBLIC = ROOT / 'apps/web/public'
GENERATED = ROOT / 'apps/web/src/generated'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()

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
civilization_pages = export_pages(ROOT, exports, data, media, public_catalog)
ranking_pages = export_ranking_pages(ROOT, exports, data, public_catalog)
simulator_page = export_simulator_page(ROOT, exports, data, public_catalog)
remaining_pages = export_remaining_pages(ROOT)
retained_manifest = restore_retained()
assert data['components']['engine']['version'] == retained_manifest['legacy_engine_version'], \
    'An engine change requires an explicit legacy-client compatibility release'
engine_version=data['components']['engine']['version']
engine_prefix=f'/releases/engine/{engine_version}'
# Head metadata, the methodology body and the shared catalog script of /about.
about = site_pages.about()

backend_sources = set()
# The API package lands at runtime/apps/backend/aoe2_api (apps/backend/app.py imports it from there).
for base in ['aoe2x/advisor', 'aoe2x/assets', 'aoe2x/batch', 'aoe2x/dbgen', 'aoe2x/rank', 'aoe2x/sim',
             'apps/backend/aoe2_api']:
    backend_sources.update(p for p in (ROOT/base).rglob('*.py') if '__pycache__' not in p.parts)
for name in ['aoe2x/__init__.py', 'aoe2x/paths.py', 'aoe2x/storage.py',
             'aoe2x/assets/presentation.json', 'aoe2x/js_simulation/__init__.py',
             'aoe2x/js_simulation/scenario_config.py']:
    path = ROOT/name
    if path.exists(): backend_sources.add(path)
backend_sources.update(p for p in (ROOT/'data/golden').rglob('*') if p.is_file() and p.suffix in ['.db', '.json'])
backend_sources.update((ROOT/'apps/backend/aoe2_api/data').glob('*.json'))
backend_sources.update((ROOT/'aoe2x/js_simulation').glob('*.py'))
# The existing release API fingerprints these sources; retain the same identity.
backend_sources.update((ROOT/'aoe2x/js_simulation/src').rglob('*.js'))
for name in ['golden_map.json', 'golden_formation_27v27.json', 'current_ranged_golden_formations.json']:
    backend_sources.add(ROOT/'aoe2x/js_simulation/fixtures'/name)
# No templates: the packaged API 404s every non-API path before any HTML route runs.

public_sources = {}
# Stylesheets and page scripts are bundled by the Astro app; only shared runtime files are copied.
# static/js/unit_sprites.js has no source: it is written below from the public catalog.
for name in ['img/favicon.png', 'img/og-default.png',
             'js/constants.js', 'js/api_client.js', 'js/v3_sim_worker.js']:
    public_sources['static/'+name] = ROOT/'apps/web/static'/name
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
# The build-side page builders and their verbatim snippets.
source_files.update(p for p in (ROOT/'scripts/migration/site').rglob('*') if p.is_file()
                    and p.suffix in ['.py', '.html'] and '__pycache__' not in p.parts)
for base in ['apps/web/src']:
    source_files.update(p for p in (ROOT/base).rglob('*') if p.is_file()
                        and not any(x in ['generated', '__pycache__'] or re.fullmatch(r'generated [0-9]+', x) for x in p.parts))
source_files.update(ROOT/'apps/backend'/p for p in ['app.py', 'advisor_cache.py', 'pyproject.toml', 'uv.lock', 'requirements.txt', '.python-version'])
# Every API package file (sources and data), so `check_release.mjs backend` sees any change after sealing.
source_files.update(p for p in (ROOT/'apps/backend/aoe2_api').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
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
