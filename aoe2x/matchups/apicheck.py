"""What visitors get from a serving DB: the advisor API responses and the export component version.

Points ``apps/backend/aoe2_api/services/advisor.py`` at a given DB file through
its module-level ``DATASET`` (the service resolves it at call time), clears the
service's caches, and reads the responses through the Flask test client - the
same calls ``scripts/migration/export_data.py`` makes. The live default is
restored afterwards. Nothing in the API code changes.

``component_version`` recomputes the ``advisor`` component version of
``export_data.py`` (``sha(encode({name: sha(encode(response.get_json()))}))``)
without writing an export, so a DB swap can be judged before a release build.
"""
from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path

from aoe2x.matchups.paths import REPO_ROOT


def _encode(value) -> bytes:
    # scripts/migration/export_data.py encode()
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@contextmanager
def advisor_db(path: Path):
    backend = str(REPO_ROOT / "apps" / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    import aoe2_api.services.advisor as advisor
    import aoe2_api.web as web
    original = advisor.DATASET
    advisor.DATASET = Path(path)
    advisor.advisor_catalog.cache_clear()
    advisor.advisor_matchups.cache_clear()
    try:
        web.app.config["TESTING"] = True
        with web.app.test_client() as client:
            yield client
    finally:
        advisor.DATASET = original
        advisor.advisor_catalog.cache_clear()
        advisor.advisor_matchups.cache_clear()


def responses(path: Path, evidence_ids: tuple = ()) -> dict:
    """``{"catalog": bytes, "<civ lower>": bytes, ...}`` (raw response bodies) plus evidence samples."""
    out, evidence = {}, {}
    with advisor_db(path) as client:
        r = client.get("/api/advisor-catalog")
        if r.status_code != 200:
            raise RuntimeError(f"/api/advisor-catalog -> {r.status_code}")
        out["catalog"] = r.data
        for name in r.get_json()["civilizations"]:
            m = client.get("/api/advisor-matchups/" + name)
            if m.status_code != 200:
                raise RuntimeError(f"/api/advisor-matchups/{name} -> {m.status_code}")
            out[name.lower()] = m.data
        for i in evidence_ids:
            e = client.get(f"/api/advisor-evidence/{i}")
            evidence[i] = (e.status_code, e.get_json())
    return {"files": out, "evidence": evidence}


def component_version(files: dict) -> str:
    inputs = {name: _sha(_encode(json.loads(data))) for name, data in sorted(files.items())}
    return _sha(_encode(inputs))


def compare(old: Path, new: Path, evidence_ids: tuple = (0,)) -> dict:
    a, b = responses(old, evidence_ids), responses(new, evidence_ids)
    fa, fb = a["files"], b["files"]
    names = sorted(set(fa) | set(fb))
    identical = [n for n in names if fa.get(n) == fb.get(n)]
    return {"files": len(names), "identical": len(identical),
            "different": [n for n in names if n in fa and n in fb and fa[n] != fb[n]],
            "onlyOld": sorted(set(fa) - set(fb)), "onlyNew": sorted(set(fb) - set(fa)),
            "bytesOld": sum(map(len, fa.values())), "bytesNew": sum(map(len, fb.values())),
            "componentVersionOld": component_version(fa), "componentVersionNew": component_version(fb),
            "evidenceStatus": {str(i): [a["evidence"][i][0], b["evidence"][i][0]] for i in evidence_ids}}
