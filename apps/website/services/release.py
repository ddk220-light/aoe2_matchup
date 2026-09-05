"""Portable identities for the deployed data, runtime, and published rankings."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from aoe2x.dbgen.v3_mechanics import MECHANICS_SCHEMA_VERSION

@lru_cache(maxsize=1)
def release_metadata(repo_root, golden_dir):
    root, golden = Path(repo_root), Path(golden_dir)
    ranking = json.loads((golden / 'derived_data_v3.metadata.json').read_text(encoding='utf-8'))
    runtime = root / 'aoe2x/js_simulation/src'
    digest = hashlib.sha256()
    for path in sorted(runtime.rglob('*.js')):
        digest.update(path.relative_to(runtime).as_posix().encode())
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return {
        'schema_version':1,
        'game_build':ranking['game_build'],
        'mechanics_schema_version':MECHANICS_SCHEMA_VERSION,
        'reference_sha256':hashlib.sha256((golden / 'aoe2_reference.db').read_bytes()).hexdigest(),
        'engine':{'name':'simulationv3','source_sha256':digest.hexdigest()},
        'rankings':{key:ranking[key] for key in ('engine_revision','mechanics_build','generated_at','published_stages','retained_retail_lines')},
        'ranking_methodology_version':ranking.get('methodology',{}).get('schema_version'),
    }
